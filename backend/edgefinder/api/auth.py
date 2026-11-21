"""Identität der Benutzer aus Cloudflare Access (Header- oder strikter JWT-Modus).

Cloudflare Access ist die Zugangskontrolle; die App führt keine eigene Freigabeliste. Header und
Token werden nie geloggt. Fehlt die Identität, gibt es keinen „anonymen“ Ersatz.
"""

from __future__ import annotations

import logging
import re
import threading
import time
from collections.abc import Callable, Mapping
from typing import Any

import httpx
import jwt

from edgefinder.config import AuthConfig, Secrets

log = logging.getLogger(__name__)

EMAIL_HEADER = "cf-access-authenticated-user-email"
JWT_HEADER = "cf-access-jwt-assertion"
MAX_EMAIL_LENGTH = 254
JWKS_TTL_SECONDS = 3600  # Schlüssel höchstens eine Stunde alt (Cloudflare rotiert selten)
JWKS_MIN_REFETCH_SECONDS = 60  # unbekannte `kid`: höchstens ein Abruf pro Minute
JWT_LEEWAY_SECONDS = 30
_EMAIL = re.compile(
    r"^[^@\s<>\"',;:()\[\]\\]+@[A-Za-z0-9](?:[A-Za-z0-9.-]*[A-Za-z0-9])?\.[A-Za-z]{2,}$"
)
_TEAM = re.compile(r"^[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?$")

JwksFetcher = Callable[[str], dict[str, Any]]


class AuthError(Exception):
    """Identität fehlt oder ist ungültig; `status` ist der passende HTTP-Status."""

    def __init__(self, detail: str, status: int = 401) -> None:
        super().__init__(detail)
        self.detail = detail
        self.status = status


def normalize_email(value: str) -> str:
    """trim + Kleinbuchstaben; Format und Länge werden geprüft (sonst `ValueError`)."""
    email = value.strip().lower()
    if not email or len(email) > MAX_EMAIL_LENGTH or not _EMAIL.match(email):
        raise ValueError("ungültige E-Mail-Adresse")
    return email


def team_slug(value: str) -> str:
    """`team`, `team.cloudflareaccess.com` oder `https://team.cloudflareaccess.com/` → `team`."""
    slug = value.strip().lower().removeprefix("https://").removeprefix("http://")
    slug = slug.split("/")[0].removesuffix(".cloudflareaccess.com")
    if not _TEAM.match(slug):
        raise ValueError("CF_ACCESS_TEAM_DOMAIN ungültig (erwartet <team>.cloudflareaccess.com)")
    return slug


def _fetch_jwks(url: str) -> dict[str, Any]:
    response = httpx.get(url, timeout=5.0, follow_redirects=False)
    response.raise_for_status()
    data = response.json()
    if not isinstance(data, dict):
        raise ValueError("JWKS ist kein Objekt")
    return data


class IdentityResolver:
    def __init__(
        self,
        auth: AuthConfig,
        secrets: Secrets | None = None,
        *,
        fetch_jwks: JwksFetcher = _fetch_jwks,
        clock: Callable[[], float] = time.time,
    ) -> None:
        self._dev_email = normalize_email(auth.dev_email) if auth.dev_email else None
        self._fetch = fetch_jwks
        self._clock = clock
        self._lock = threading.Lock()
        self._keys: dict[str, Any] = {}
        self._fetched_at = 0.0
        self._attempted_at = -JWKS_MIN_REFETCH_SECONDS
        team = secrets.cf_access_team_domain if secrets else None
        aud = None
        if secrets and secrets.cf_access_aud:
            aud = secrets.cf_access_aud.get_secret_value()
        have_both = bool(team and aud)
        if auth.mode == "jwt" and not have_both:
            raise ValueError(
                "auth.mode=jwt braucht CF_ACCESS_TEAM_DOMAIN und CF_ACCESS_AUD in der .env"
            )
        if auth.mode == "off":
            self.mode = "off"
        elif have_both:
            self.mode = "jwt"  # beide Werte gesetzt = strikt
        else:
            self.mode = "header"
        self._aud = aud
        self._issuer = ""
        self._certs_url = ""
        if self.mode == "jwt" and team:
            slug = team_slug(team)
            self._issuer = f"https://{slug}.cloudflareaccess.com"
            self._certs_url = f"{self._issuer}/cdn-cgi/access/certs"

    # -------------------------------------------------------------- Öffentliche Schnittstelle
    def email_for(self, headers: Mapping[str, str]) -> str:
        """Normalisierte E-Mail der anfragenden Person oder `AuthError`."""
        headers = {name.lower(): value for name, value in headers.items()}
        if self.mode == "jwt":
            return self._email_from_jwt(headers.get(JWT_HEADER))
        if self.mode == "header":
            raw = headers.get(EMAIL_HEADER)
            if raw is not None and raw.strip():
                return self._clean(raw)
        if self._dev_email:
            return self._dev_email
        raise AuthError(
            "Nicht angemeldet: Cloudflare Access hat keine Identität übermittelt. "
            "Bitte die Seite über den freigegebenen Hostnamen öffnen."
        )

    # -------------------------------------------------------------- Intern
    @staticmethod
    def _clean(raw: str) -> str:
        try:
            return normalize_email(raw)
        except ValueError as exc:
            raise AuthError("Ungültige Identität: die E-Mail-Adresse ist nicht zulässig.") from exc

    def _email_from_jwt(self, token: str | None) -> str:
        if not token:
            raise AuthError("Nicht angemeldet: das Cloudflare-Access-Token fehlt.")
        try:
            kid = jwt.get_unverified_header(token).get("kid")
            key = self._key(kid) if isinstance(kid, str) else None
            if key is None:
                raise AuthError("Ungültiges Cloudflare-Access-Token (unbekannter Schlüssel).")
            claims = jwt.decode(
                token,
                key,
                algorithms=["RS256"],
                audience=self._aud,
                issuer=self._issuer,
                leeway=JWT_LEEWAY_SECONDS,
                options={"require": ["exp", "aud", "iss"]},
            )
        except jwt.PyJWTError as exc:
            # Nur die Fehlerart, nie das Token.
            log.info("Cloudflare-Access-Token abgelehnt: %s", type(exc).__name__)
            raise AuthError("Ungültiges oder abgelaufenes Cloudflare-Access-Token.") from exc
        email = claims.get("email")
        if not isinstance(email, str):
            raise AuthError("Das Cloudflare-Access-Token enthält keine E-Mail-Adresse.")
        return self._clean(email)

    def _key(self, kid: str) -> Any | None:
        with self._lock:
            now = self._clock()
            due = now - self._fetched_at > JWKS_TTL_SECONDS or kid not in self._keys
            if due and now - self._attempted_at >= JWKS_MIN_REFETCH_SECONDS:
                self._refresh(now)
            return self._keys.get(kid)

    def _refresh(self, now: float) -> None:
        self._attempted_at = now
        try:
            data = self._fetch(self._certs_url)
            keys: dict[str, Any] = {}
            for entry in data.get("keys", []):
                if isinstance(entry, dict) and entry.get("kty") == "RSA" and entry.get("kid"):
                    keys[str(entry["kid"])] = jwt.PyJWK(entry).key
        except Exception as exc:  # Netz, JSON, Schlüsselformat
            log.warning("JWKS-Abruf fehlgeschlagen: %s", type(exc).__name__)
            if not self._keys:
                raise AuthError("Anmeldedienst derzeit nicht erreichbar.", status=503) from exc
            return  # alte Schlüssel weiterverwenden
        self._keys = keys
        self._fetched_at = now
