"""Myfxbook Community Outlook (Long/Short-Verhältnis der Privatanleger).

Gratis-Limit: 100 Requests / 24 h (Login zählt mit). Der Zähler steht persistent in
`request_log`; die Konfiguration hält mit `daily_request_limit` Abstand dazu. Die Session ist
IP-gebunden und läuft nach ca. einem Monat ab. Sie liegt in `source_state` und wird bei
„Invalid session“ oder nach `session_max_age_days` automatisch erneuert (höchstens ein
Login je Lauf). Nach einem fehlgeschlagenen Login folgt für `login_retry_hours` kein neuer
Versuch, damit falsche Zugangsdaten das Konto nicht sperren.

Der Session-Token steht in der Query-URL: er wird nie geloggt, nie in Rohdaten abgelegt und
in Fehlermeldungen geschwärzt. Die Login-Antwort wird nicht gespeichert.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from edgefinder.db import transaction
from edgefinder.fetchers.base import Fetcher, FetchError, iso

SESSION_KEY = "session"
LOGIN_FAILED_KEY = "login_failed"


def parse_rows(data: dict[str, Any], observed_at: str) -> list[tuple[Any, ...]]:
    """Outlook-Antwort → Zeilen für `retail_sentiment`. Symbole ohne Prozentwerte entfallen."""
    rows = []
    for symbol in data.get("symbols", []):
        long_pct, short_pct = symbol.get("longPercentage"), symbol.get("shortPercentage")
        if not symbol.get("name") or long_pct is None or short_pct is None:
            continue
        rows.append(
            (
                "myfxbook",
                symbol["name"],
                observed_at,
                float(long_pct),
                float(short_pct),
                symbol.get("longVolume"),
                symbol.get("shortVolume"),
                symbol.get("longPositions"),
                symbol.get("shortPositions"),
                symbol.get("avgLongPrice"),
                symbol.get("avgShortPrice"),
            )
        )
    return rows


def _is_session_error(message: str) -> bool:
    return "session" in message.lower()


class MyfxbookFetcher(Fetcher):
    source = "myfxbook"

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self._session: str | None = None
        self._fresh = False

    def scrub(self, text: str) -> str:
        text = super().scrub(text)
        if self._session:
            text = text.replace(self._session, "***")
        return text

    # ------------------------------------------------------------ Session
    def _login(self) -> str:
        email, password = self.secrets.myfxbook_email, self.secrets.myfxbook_password
        if email is None or password is None:
            raise FetchError("myfxbook: MYFXBOOK_EMAIL/MYFXBOOK_PASSWORD fehlen in der .env")
        failed = self.get_state(LOGIN_FAILED_KEY)
        if failed is not None:
            wait = timedelta(hours=float(self.options.get("login_retry_hours", 12)))
            until = datetime.fromisoformat(failed[1]) + wait
            if self.clock() < until:
                raise FetchError(
                    f"myfxbook: letzter Login fehlgeschlagen ({failed[0]}); nächster Versuch"
                    f" frühestens {iso(until)} (Zugangsdaten in .env prüfen)"
                )
        response = self.http.get(
            f"{self.options['base_url']}/login.json",
            {
                "email": email.get_secret_value(),
                "password": password.get_secret_value(),
            },
        )
        data = response.json()
        token = data.get("session")
        if data.get("error") or not token:
            message = str(data.get("message") or "ohne Meldung")[:200]
            self.set_state(LOGIN_FAILED_KEY, message)
            raise FetchError(f"myfxbook: Login fehlgeschlagen: {message}")
        self.clear_state(LOGIN_FAILED_KEY)
        self.set_state(SESSION_KEY, token)
        self._session = token
        self._fresh = True
        return token

    def _current_session(self) -> str:
        stored = self.get_state(SESSION_KEY)
        if stored is not None:
            age = self.clock() - datetime.fromisoformat(stored[1])
            if age < timedelta(days=float(self.options.get("session_max_age_days", 25))):
                self._session = stored[0]
                return stored[0]
        return self._login()

    def _outlook(self, session: str) -> tuple[dict[str, Any], bytes]:
        response = self.http.get(
            f"{self.options['base_url']}/get-community-outlook.json", {"session": session}
        )
        return response.json(), response.content

    # ------------------------------------------------------------ Ablauf
    def fetch(self) -> int:
        if not (self.secrets.myfxbook_email and self.secrets.myfxbook_password):
            raise FetchError("myfxbook: MYFXBOOK_EMAIL/MYFXBOOK_PASSWORD fehlen in der .env")
        session = self._current_session()
        fresh = self._fresh  # in diesem Lauf frisch angemeldet
        data, content = self._outlook(session)
        if (
            data.get("error")
            and not fresh  # frische Session abgelehnt: nicht noch einmal anmelden
            and _is_session_error(str(data.get("message", "")))
        ):
            self.clear_state(SESSION_KEY)  # abgelaufen oder IP gewechselt → einmal neu anmelden
            data, content = self._outlook(self._login())
        if data.get("error"):
            raise FetchError(f"myfxbook: {str(data.get('message') or 'Fehler ohne Meldung')[:200]}")
        if not isinstance(data.get("symbols"), list):
            raise ValueError("Unerwartete Myfxbook-Antwort (keine Symbolliste)")

        self.save_raw("community-outlook", content)
        rows = parse_rows(data, iso(self.clock()))
        with transaction(self.conn):
            self.conn.executemany(
                "INSERT OR REPLACE INTO retail_sentiment (source, symbol, observed_at, long_pct,"
                " short_pct, long_volume, short_volume, long_positions, short_positions,"
                " avg_long_price, avg_short_price) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                rows,
            )
        available = {row[1] for row in rows}
        for asset in self.config.assets.all():
            symbol = getattr(asset, "myfxbook", None)
            if symbol and symbol not in available:
                with self.unit(f"Asset {asset.id}"):
                    raise ValueError(f"Symbol {symbol} fehlt im Community Outlook")
        return len(rows)
