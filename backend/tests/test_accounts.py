"""Benutzerkonten: Identität (Header/JWT), Auto-Provisionierung, Isolation, Validierung, CSRF."""

from __future__ import annotations

import shutil
import sqlite3
import time
from pathlib import Path
from typing import Any

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi.testclient import TestClient
from pydantic import SecretStr

from edgefinder.api.app import create_app
from edgefinder.api.auth import IdentityResolver, normalize_email, team_slug
from edgefinder.config import AuthConfig, Config, Secrets
from edgefinder.db import connect, migrate
from edgefinder.db.migrate import MIGRATIONS_DIR

EMAIL_HEADER = "Cf-Access-Authenticated-User-Email"
JWT_HEADER = "Cf-Access-Jwt-Assertion"
JSON = {"Content-Type": "application/json"}
ISSUER = "https://acme.cloudflareaccess.com"
AUD = "aud-tag-1234"


def _db(config: Config) -> None:
    conn = connect(config.storage.database)
    migrate(conn)
    conn.close()


def _client(config: Config, **kwargs: Any) -> TestClient:
    _db(config)
    return TestClient(create_app(config, frontend_dist=None, **kwargs))


def _as(email: str, **extra: str) -> dict[str, str]:
    return {EMAIL_HEADER: email, **extra}


@pytest.fixture
def client(config: Config) -> TestClient:
    return _client(config)


# ------------------------------------------------------------------ Header-Modus
def test_first_call_provisions_account_with_defaults(client: TestClient) -> None:
    response = client.get("/api/me", headers=_as("Anna.Muster@Example.com "))

    assert response.status_code == 200
    body = response.json()
    assert body["email"] == "anna.muster@example.com"
    assert body["display_name"] == "anna.muster"
    assert body["favorites"] == []
    assert body["preferences"] == {
        "profile": "swing",
        "view": "cards",
        "sort": "score-desc",
        "theme": "system",
        "fx": "full",
        "filter": "all",
    }
    assert response.headers["cache-control"] == "no-store"


def test_provisioning_is_idempotent_and_case_insensitive(
    client: TestClient, config: Config
) -> None:
    first = client.get("/api/me", headers=_as("a@example.com")).json()
    second = client.get("/api/me", headers=_as("  A@EXAMPLE.COM")).json()

    assert first["created_at"] == second["created_at"]
    conn = connect(config.storage.database)
    assert conn.execute("SELECT count(*) FROM users").fetchone()[0] == 1
    conn.close()


def test_last_seen_is_written_at_most_every_few_minutes(client: TestClient, config: Config) -> None:
    client.get("/api/me", headers=_as("a@example.com"))
    conn = connect(config.storage.database)
    conn.execute("UPDATE users SET last_seen_at = '2000-01-01T00:00:00+00:00'")
    client.get("/api/me", headers=_as("a@example.com"))
    refreshed = conn.execute("SELECT last_seen_at FROM users").fetchone()[0]
    assert refreshed > "2020"
    client.get("/api/me", headers=_as("a@example.com"))
    assert conn.execute("SELECT last_seen_at FROM users").fetchone()[0] == refreshed
    conn.close()


def test_no_identity_gives_401_without_anonymous_fallback(client: TestClient) -> None:
    for method, path in (
        ("get", "/api/me"),
        ("put", "/api/me/preferences"),
        ("put", "/api/me/favorites"),
    ):
        response = client.request(method.upper(), path, headers=JSON, content=b"{}")
        assert response.status_code == 401
        assert "Nicht angemeldet" in response.json()["detail"]
        assert response.headers["cache-control"] == "no-store"


@pytest.mark.parametrize(
    "value", ["", "   ", "kein-at", "a@b", "a b@example.com", "<x>@example.com"]
)
def test_invalid_email_is_rejected(client: TestClient, value: str) -> None:
    assert client.get("/api/me", headers=_as(value)).status_code == 401


def test_too_long_email_is_rejected(client: TestClient) -> None:
    assert client.get("/api/me", headers=_as("a" * 250 + "@example.com")).status_code == 401


def test_normalize_email_and_team_slug() -> None:
    assert normalize_email("  Foo@Bar.DE ") == "foo@bar.de"
    with pytest.raises(ValueError):
        normalize_email("foo")
    assert team_slug("https://Acme.cloudflareaccess.com/") == "acme"
    assert team_slug("acme") == "acme"
    with pytest.raises(ValueError):
        team_slug("evil.com/x@y")


def test_dev_email_only_when_header_missing(config_data: dict[str, Any], tmp_path: Path) -> None:
    config_data["storage"] = {"database": str(tmp_path / "d.db"), "raw_dir": str(tmp_path / "r")}
    config_data["auth"] = {"dev_email": "Dev@Example.com"}
    client = _client(Config.model_validate(config_data))

    assert client.get("/api/me").json()["email"] == "dev@example.com"
    assert client.get("/api/me", headers=_as("x@example.com")).json()["email"] == "x@example.com"


def test_off_mode_ignores_headers(config_data: dict[str, Any], tmp_path: Path) -> None:
    config_data["storage"] = {"database": str(tmp_path / "d.db"), "raw_dir": str(tmp_path / "r")}
    config_data["auth"] = {"mode": "off", "dev_email": "dev@example.com"}
    client = _client(Config.model_validate(config_data))

    assert client.get("/api/me", headers=_as("x@example.com")).json()["email"] == "dev@example.com"


def test_market_endpoints_need_no_identity(client: TestClient) -> None:
    assert client.get("/api/health").status_code == 200
    assert client.get("/api/assets").status_code == 200
    assert client.get("/api/profiles").status_code == 200
    assert client.get("/api/macro").status_code == 200
    assert "no-store" not in client.get("/api/assets").headers.get("cache-control", "")


# ------------------------------------------------------------------ Einstellungen / Favoriten
def test_preferences_partial_update_persists(client: TestClient) -> None:
    headers = {**JSON, **_as("a@example.com")}
    assert (
        client.put("/api/me/preferences", headers=headers, json={"theme": "dark"}).status_code
        == 200
    )
    response = client.put(
        "/api/me/preferences", headers=headers, json={"view": "list", "fx": "calm"}
    )

    assert response.json() == {
        "profile": "swing",
        "view": "list",
        "sort": "score-desc",
        "theme": "dark",
        "fx": "calm",
        "filter": "all",
    }
    assert client.get("/api/me", headers=headers).json()["preferences"] == response.json()
    assert response.headers["cache-control"] == "no-store"


@pytest.mark.parametrize(
    "payload",
    [
        {"unbekannt": 1},
        {"theme": "pink"},
        {"profile": None},
        {"sort": "zufall"},
        {"fx": True},
        {"filter": "crypto"},
        [],
        "text",
    ],
)
def test_preferences_validation(client: TestClient, payload: Any) -> None:
    headers = {**JSON, **_as("a@example.com")}
    response = client.put("/api/me/preferences", headers=headers, json=payload)

    assert response.status_code == 422
    assert "pink" not in response.text  # Eingaben werden nicht zurückgespiegelt


def test_preferences_size_limit_and_bad_json(client: TestClient) -> None:
    headers = {**JSON, **_as("a@example.com")}
    big = client.put(
        "/api/me/preferences", headers=headers, content=b'{"theme":"' + b"x" * 5000 + b'"}'
    )
    bad = client.put("/api/me/preferences", headers=headers, content=b"{kaputt")

    assert big.status_code == 413
    assert bad.status_code == 400


def test_favorites_roundtrip_keeps_order(client: TestClient, config: Config) -> None:
    headers = {**JSON, **_as("a@example.com")}
    ids = list(config.assets_by_id)[:3][::-1]

    response = client.put("/api/me/favorites", headers=headers, json={"asset_ids": ids})

    assert response.json() == {"favorites": ids}
    assert client.get("/api/me", headers=headers).json()["favorites"] == ids
    client.put("/api/me/favorites", headers=headers, json={"asset_ids": ids[:1]})
    assert client.get("/api/me", headers=headers).json()["favorites"] == ids[:1]


def test_favorites_validation(client: TestClient, config: Config) -> None:
    headers = {**JSON, **_as("a@example.com")}
    known = next(iter(config.assets_by_id))

    def put(payload: Any) -> int:
        return client.put("/api/me/favorites", headers=headers, json=payload).status_code

    assert put({"asset_ids": ["NOPE"]}) == 422
    assert put({"asset_ids": [known, known]}) == 422
    assert put({"asset_ids": [known], "x": 1}) == 422
    assert put({"asset_ids": [1]}) == 422
    assert put({"asset_ids": ["A" * 40]}) == 422
    assert put({"asset_ids": [f"A{n}" for n in range(101)]}) == 422
    assert put(["EURUSD"]) == 422
    assert client.get("/api/me", headers=headers).json()["favorites"] == []


# ------------------------------------------------------------------ Isolation
def test_accounts_are_isolated(client: TestClient, config: Config) -> None:
    a = {**JSON, **_as("a@example.com")}
    b = {**JSON, **_as("b@example.com")}
    ids = list(config.assets_by_id)

    client.put("/api/me/favorites", headers=a, json={"asset_ids": ids[:2]})
    client.put("/api/me/preferences", headers=a, json={"theme": "dark"})

    seen_b = client.get("/api/me", headers=b).json()
    assert seen_b["favorites"] == [] and seen_b["preferences"]["theme"] == "system"
    client.put("/api/me/favorites", headers=b, json={"asset_ids": ids[2:3]})
    client.put("/api/me/preferences", headers=b, json={"theme": "light"})

    seen_a = client.get("/api/me", headers=a).json()
    assert seen_a["favorites"] == ids[:2] and seen_a["preferences"]["theme"] == "dark"
    assert client.get("/api/me", headers=b).json()["favorites"] == ids[2:3]


def test_client_cannot_choose_user_id(client: TestClient) -> None:
    a = {**JSON, **_as("a@example.com")}
    client.get("/api/me", headers=_as("b@example.com"))
    for payload in ({"user_id": 2, "theme": "dark"}, {"email": "b@example.com"}):
        assert client.put("/api/me/preferences", headers=a, json=payload).status_code == 422
    assert client.get("/api/me?user_id=2&email=b@example.com", headers=a).json()["email"] == (
        "a@example.com"
    )
    assert client.get("/api/me", headers=_as("b@example.com")).json()["preferences"]["theme"] == (
        "system"
    )


# ------------------------------------------------------------------ CSRF
def test_write_requires_json_content_type(client: TestClient) -> None:
    for content_type in ("text/plain", "application/x-www-form-urlencoded", "multipart/form-data"):
        response = client.put(
            "/api/me/preferences",
            headers={**_as("a@example.com"), "Content-Type": content_type},
            content=b'{"theme":"dark"}',
        )
        assert response.status_code == 415
    assert (
        client.put("/api/me/preferences", headers=_as("a@example.com"), content=b"{}").status_code
        == 415
    )


def test_origin_must_match_host(client: TestClient) -> None:
    base = {**JSON, **_as("a@example.com")}

    def put(headers: dict[str, str]) -> int:
        body = {"theme": "dark"}
        return client.put("/api/me/preferences", headers=headers, json=body).status_code

    assert put({**base, "Origin": "https://evil.example"}) == 403
    assert put({**base, "Origin": "null"}) == 403
    assert put({**base, "Origin": "http://testserver"}) == 200  # Host des Test-Clients
    assert (
        put({**base, "Origin": "https://egiant.example", "X-Forwarded-Host": "egiant.example"})
        == 200
    )
    assert put({**base, "Sec-Fetch-Site": "cross-site"}) == 403
    assert put({**base, "Sec-Fetch-Site": "same-origin"}) == 200
    assert put(base) == 200  # ohne Origin (z. B. curl) erlaubt


def test_public_hosts_from_config(config_data: dict[str, Any], tmp_path: Path) -> None:
    config_data["storage"] = {"database": str(tmp_path / "d.db"), "raw_dir": str(tmp_path / "r")}
    config_data["auth"] = {"public_hosts": ["egiant.example"]}
    client = _client(Config.model_validate(config_data))

    response = client.put(
        "/api/me/preferences",
        headers={**JSON, **_as("a@example.com"), "Origin": "https://egiant.example"},
        json={"theme": "dark"},
    )
    assert response.status_code == 200


def test_no_cors_headers(client: TestClient) -> None:
    response = client.options(
        "/api/me",
        headers={"Origin": "https://evil.example", "Access-Control-Request-Method": "PUT"},
    )
    assert "access-control-allow-origin" not in response.headers


# ------------------------------------------------------------------ JWT-Modus
class Jwt:
    """Lokales RSA-Schlüsselpaar + gemockte JWKS."""

    def __init__(self) -> None:
        self.key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        self.calls = 0

    def jwks(self, kid: str = "k1", key: rsa.RSAPrivateKey | None = None) -> dict[str, Any]:
        public = (key or self.key).public_key()
        jwk = jwt.algorithms.RSAAlgorithm.to_jwk(public, as_dict=True)
        return {"keys": [{**jwk, "kid": kid, "alg": "RS256", "use": "sig"}]}

    def token(self, **overrides: Any) -> str:
        now = int(time.time())
        claims: dict[str, Any] = {
            "aud": [AUD],
            "iss": ISSUER,
            "email": "Jwt.User@Example.com",
            "iat": now,
            "exp": now + 600,
        }
        claims.update(overrides)
        key = overrides.pop("_key", None) or self.key
        return jwt.encode(
            {k: v for k, v in claims.items() if k != "_key"}, key, "RS256", {"kid": "k1"}
        )


@pytest.fixture
def jwtenv(config: Config) -> tuple[TestClient, Jwt]:
    env = Jwt()

    def fetch(url: str) -> dict[str, Any]:
        assert url == f"{ISSUER}/cdn-cgi/access/certs"
        env.calls += 1
        return env.jwks()

    secrets = Secrets(
        _env_file=None,
        cf_access_team_domain="acme.cloudflareaccess.com",
        cf_access_aud=SecretStr(AUD),
    )  # type: ignore[call-arg]
    resolver = IdentityResolver(config.auth, secrets, fetch_jwks=fetch)
    return _client(config, resolver=resolver), env


def test_jwt_valid_token_provisions_account(jwtenv: tuple[TestClient, Jwt]) -> None:
    client, env = jwtenv

    response = client.get("/api/me", headers={JWT_HEADER: env.token()})

    assert response.status_code == 200
    assert response.json()["email"] == "jwt.user@example.com"
    client.get("/api/me", headers={JWT_HEADER: env.token()})
    assert env.calls == 1  # JWKS gecacht


def test_jwt_ignores_plain_email_header(jwtenv: tuple[TestClient, Jwt]) -> None:
    client, _ = jwtenv

    assert client.get("/api/me", headers=_as("evil@example.com")).status_code == 401


def test_jwt_missing_header(jwtenv: tuple[TestClient, Jwt]) -> None:
    client, _ = jwtenv

    assert client.get("/api/me").status_code == 401


@pytest.mark.parametrize(
    "overrides",
    [
        {"aud": ["anderer-tag"]},
        {"iss": "https://evil.cloudflareaccess.com"},
        {"exp": int(time.time()) - 3600},
        {"email": None},
        {"email": "kein-email"},
    ],
)
def test_jwt_bad_claims(jwtenv: tuple[TestClient, Jwt], overrides: dict[str, Any]) -> None:
    client, env = jwtenv

    assert client.get("/api/me", headers={JWT_HEADER: env.token(**overrides)}).status_code == 401


def test_jwt_wrong_signature(jwtenv: tuple[TestClient, Jwt]) -> None:
    client, env = jwtenv
    other = rsa.generate_private_key(public_exponent=65537, key_size=2048)

    assert client.get("/api/me", headers={JWT_HEADER: env.token(_key=other)}).status_code == 401
    assert client.get("/api/me", headers={JWT_HEADER: "kein.jwt.token"}).status_code == 401


def test_jwt_none_algorithm_is_rejected(jwtenv: tuple[TestClient, Jwt]) -> None:
    client, _ = jwtenv
    token = jwt.encode(
        {"aud": [AUD], "iss": ISSUER, "email": "x@example.com", "exp": int(time.time()) + 60},
        key=None,
        algorithm="none",
        headers={"kid": "k1"},
    )

    assert client.get("/api/me", headers={JWT_HEADER: token}).status_code == 401


def test_jwt_refetches_on_unknown_kid_but_rate_limited(config: Config) -> None:
    env = Jwt()
    now = [1_000_000.0]
    served = {"kid": "old"}

    def fetch(url: str) -> dict[str, Any]:
        env.calls += 1
        return env.jwks(kid=served["kid"])

    secrets = Secrets(_env_file=None, cf_access_team_domain="acme", cf_access_aud=SecretStr(AUD))  # type: ignore[call-arg]
    resolver = IdentityResolver(config.auth, secrets, fetch_jwks=fetch, clock=lambda: now[0])
    token = env.token()  # kid "k1"
    headers = {JWT_HEADER: token}

    with pytest.raises(Exception):  # noqa: B017 - AuthError, Kennung k1 unbekannt
        resolver.email_for(headers)
    assert env.calls == 1
    served["kid"] = "k1"
    with pytest.raises(Exception):  # noqa: B017 - innerhalb 60 s kein neuer Abruf
        resolver.email_for(headers)
    assert env.calls == 1
    now[0] += 61
    assert resolver.email_for(headers) == "jwt.user@example.com"
    assert env.calls == 2


def test_jwks_outage_uses_cached_keys_or_503(config: Config) -> None:
    env = Jwt()
    now = [1_000_000.0]
    fail = {"on": False}

    def fetch(url: str) -> dict[str, Any]:
        if fail["on"]:
            raise OSError("offline")
        return env.jwks()

    secrets = Secrets(_env_file=None, cf_access_team_domain="acme", cf_access_aud=SecretStr(AUD))  # type: ignore[call-arg]
    resolver = IdentityResolver(config.auth, secrets, fetch_jwks=fetch, clock=lambda: now[0])
    headers = {JWT_HEADER: env.token()}

    fail["on"] = True
    from edgefinder.api.auth import AuthError

    with pytest.raises(AuthError) as err:
        resolver.email_for(headers)
    assert err.value.status == 503
    fail["on"] = False
    now[0] += 61
    assert resolver.email_for(headers)
    fail["on"] = True
    now[0] += 7200  # Schlüssel abgelaufen, Abruf schlägt fehl: alte Schlüssel bleiben gültig
    assert resolver.email_for({JWT_HEADER: env.token()})


def test_mode_jwt_without_env_values_fails_closed(config: Config) -> None:
    auth = AuthConfig(mode="jwt")

    with pytest.raises(ValueError, match="CF_ACCESS"):
        IdentityResolver(auth, Secrets(_env_file=None))  # type: ignore[call-arg]


def test_secrets_empty_values_mean_header_mode() -> None:
    secrets = Secrets(_env_file=None, cf_access_team_domain="", cf_access_aud="")  # type: ignore[call-arg]

    assert IdentityResolver(AuthConfig(), secrets).mode == "header"
    both = Secrets(_env_file=None, cf_access_team_domain="acme", cf_access_aud="x")  # type: ignore[call-arg]
    assert IdentityResolver(AuthConfig(), both).mode == "jwt"
    assert IdentityResolver(AuthConfig(mode="off"), both).mode == "off"


# ------------------------------------------------------------------ Migration
def _migrations_up_to(version: int, target: Path) -> Path:
    target.mkdir()
    for path in sorted(MIGRATIONS_DIR.glob("*.sql")):
        if int(path.name[:4]) <= version:
            shutil.copy(path, target / path.name)
    return target


def test_migration_0003_on_fresh_and_existing_database(tmp_path: Path) -> None:
    fresh = sqlite3.connect(tmp_path / "fresh.db", autocommit=True)
    migrate(fresh)
    tables = {r[0] for r in fresh.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    assert {"users", "user_favorites", "user_preferences"} <= tables

    old = connect(tmp_path / "old.db")
    migrate(old, _migrations_up_to(2, tmp_path / "m2"))
    old.execute(
        "INSERT INTO scores (asset_id, profile, date, score, label, coverage, computed_at) "
        "VALUES ('EURUSD', 'swing', '2026-01-02', 4.2, 'Bullish', 1.0, 'x')"
    )
    applied = migrate(old)

    assert [m.version for m in applied] == [3, 4]
    assert old.execute("SELECT count(*) FROM scores").fetchone()[0] == 1
    old.execute(
        "INSERT INTO users (email, display_name, created_at, last_seen_at) "
        "VALUES ('a@b.de','a','x','x')"
    )
    with pytest.raises(sqlite3.IntegrityError):  # E-Mail muss normalisiert sein
        old.execute(
            "INSERT INTO users (email, display_name, created_at, last_seen_at) "
            "VALUES ('A@B.de','a','x','x')"
        )
    with pytest.raises(sqlite3.IntegrityError):  # Fremdschlüssel
        old.execute("INSERT INTO user_favorites VALUES (99, 'X', 0, 'x')")
    old.execute("DELETE FROM users")
    assert old.execute("SELECT count(*) FROM user_favorites").fetchone()[0] == 0


def test_deleting_user_cascades(client: TestClient, config: Config) -> None:
    headers = {**JSON, **_as("a@example.com")}
    client.put(
        "/api/me/favorites", headers=headers, json={"asset_ids": [next(iter(config.assets_by_id))]}
    )
    client.put("/api/me/preferences", headers=headers, json={"theme": "dark"})
    conn = connect(config.storage.database)

    conn.execute("DELETE FROM users")

    assert conn.execute("SELECT count(*) FROM user_favorites").fetchone()[0] == 0
    assert conn.execute("SELECT count(*) FROM user_preferences").fetchone()[0] == 0
    conn.close()
