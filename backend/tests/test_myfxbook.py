from __future__ import annotations

import logging
from datetime import timedelta

import httpx
import pytest
from support import NOW, fixture_bytes, fixture_json, mock_client

from edgefinder.config import Secrets
from edgefinder.fetchers.base import iso
from edgefinder.fetchers.myfxbook import MyfxbookFetcher, parse_rows

# Reine Testwerte, keine echten Zugangsdaten
EMAIL = "test-user@example.invalid"
PASSWORD = "test-pass-w0rd-xyz"
TOKEN = "TESTSESSION0001"
TOKEN2 = "TESTSESSION0002"


@pytest.fixture
def mfx_secrets() -> Secrets:
    return Secrets(_env_file=None, myfxbook_email=EMAIL, myfxbook_password=PASSWORD)  # type: ignore[call-arg]


class FakeMyfxbook:
    """Simuliert login.json und get-community-outlook.json; zählt Requests je Endpunkt."""

    def __init__(self, tokens: list[str], valid: set[str] | None = None) -> None:
        self.tokens = list(tokens)  # werden der Reihe nach bei Logins vergeben
        self.valid = valid if valid is not None else set(tokens)
        self.login_ok = True
        self.fail_status: list[int] = []  # vorgemerkte HTTP-Fehler für den nächsten Request
        self.calls: list[tuple[str, dict[str, str]]] = []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        endpoint = request.url.path.rsplit("/", 1)[-1]
        self.calls.append((endpoint, dict(request.url.params)))
        if self.fail_status:
            return httpx.Response(self.fail_status.pop(0))
        if endpoint == "login.json":
            if not self.login_ok:
                return httpx.Response(
                    200, json={"error": True, "message": "Invalid email or password."}
                )
            return httpx.Response(
                200, json={"error": False, "message": "", "session": self.tokens.pop(0)}
            )
        if request.url.params.get("session") not in self.valid:
            return httpx.Response(200, json={"error": True, "message": "Invalid session."})
        return httpx.Response(200, content=fixture_bytes("myfxbook_community_outlook.json"))

    def count(self, endpoint: str) -> int:
        return sum(1 for name, _ in self.calls if name == endpoint)


def _fetcher(config, secrets, db, clock, fake) -> MyfxbookFetcher:
    return MyfxbookFetcher(
        config, secrets, db, client=mock_client(fake), sleep=clock.sleep, clock=clock
    )


def _rows(db) -> int:
    return db.execute("SELECT COUNT(*) FROM retail_sentiment").fetchone()[0]


def test_parse_rows_maps_fields() -> None:
    rows = parse_rows(fixture_json("myfxbook_community_outlook.json"), "2026-11-17T12:00:00+00:00")
    eurusd = next(row for row in rows if row[1] == "EURUSD")
    assert eurusd[0] == "myfxbook"
    assert eurusd[3] + eurusd[4] == 100
    assert len(rows) == 17


def test_parse_rows_skips_symbols_without_percentages() -> None:
    data = {"symbols": [{"name": "X"}, {"name": "Y", "longPercentage": 60, "shortPercentage": 40}]}
    assert [row[1] for row in parse_rows(data, "t")] == ["Y"]


def test_first_run_logs_in_and_stores_everything(config, mfx_secrets, db, clock, caplog) -> None:
    fake = FakeMyfxbook([TOKEN])
    with caplog.at_level(logging.DEBUG):
        result = _fetcher(config, mfx_secrets, db, clock, fake).run()

    assert result.status == "success", result.errors
    assert result.requests == 2
    assert (fake.count("login.json"), fake.count("get-community-outlook.json")) == (1, 1)
    assert result.items == _rows(db) == 17
    state = db.execute("SELECT value FROM source_state WHERE source='myfxbook' AND key='session'")
    assert state.fetchone()[0] == TOKEN
    assert db.execute("SELECT COUNT(*) FROM raw_files WHERE source='myfxbook'").fetchone()[0] == 1

    # Der Token darf nirgends sonst auftauchen: Logs, Lauf-Protokoll, Rohdaten
    raw = next((config.storage.raw_dir / "myfxbook").rglob("*.json")).read_text()
    error = db.execute("SELECT error FROM fetch_runs").fetchone()[0]
    for secret in (TOKEN, PASSWORD, EMAIL):
        assert secret not in raw
        assert secret not in caplog.text
        assert secret not in (error or "")


def test_session_is_reused_across_runs(config, mfx_secrets, db, clock) -> None:
    fake = FakeMyfxbook([TOKEN])
    _fetcher(config, mfx_secrets, db, clock, fake).run()
    clock.now += timedelta(hours=4)
    second = _fetcher(config, mfx_secrets, db, clock, fake).run()

    assert second.status == "success" and second.requests == 1
    assert fake.count("login.json") == 1
    assert db.execute("SELECT COUNT(DISTINCT observed_at) FROM retail_sentiment").fetchone()[0] == 2


def test_invalid_session_triggers_exactly_one_relogin(config, mfx_secrets, db, clock) -> None:
    fake = FakeMyfxbook([TOKEN2], valid={TOKEN2})
    seed = _fetcher(config, mfx_secrets, db, clock, fake)
    seed.set_state("session", TOKEN)  # abgelaufen oder IP-Wechsel: Server kennt ihn nicht mehr
    result = _fetcher(config, mfx_secrets, db, clock, fake).run()

    assert result.status == "success", result.errors
    assert [name for name, _ in fake.calls] == [
        "get-community-outlook.json",
        "login.json",
        "get-community-outlook.json",
    ]
    assert seed.get_state("session")[0] == TOKEN2


def test_persistent_invalid_session_does_not_loop(config, mfx_secrets, db, clock) -> None:
    fake = FakeMyfxbook([TOKEN, TOKEN2], valid=set())
    result = _fetcher(config, mfx_secrets, db, clock, fake).run()
    assert result.status == "error"
    assert result.requests == 2  # Login + Outlook; eine frische Session wird nicht erneut erneuert
    assert fake.count("login.json") == 1


def test_session_older_than_max_age_is_renewed(config, mfx_secrets, db, clock) -> None:
    fake = FakeMyfxbook([TOKEN, TOKEN2])
    _fetcher(config, mfx_secrets, db, clock, fake).run()
    clock.now += timedelta(days=26)
    result = _fetcher(config, mfx_secrets, db, clock, fake).run()
    assert result.status == "success" and result.requests == 2
    assert fake.count("login.json") == 2


def test_failed_login_is_not_retried_until_pause_over(config, mfx_secrets, db, clock) -> None:
    fake = FakeMyfxbook([TOKEN])
    fake.login_ok = False
    first = _fetcher(config, mfx_secrets, db, clock, fake).run()
    assert first.status == "error" and "Login fehlgeschlagen" in first.errors[0]
    assert first.requests == 1

    clock.now += timedelta(hours=4)  # nächster Timer-Lauf, Pause (12 h) läuft noch
    second = _fetcher(config, mfx_secrets, db, clock, fake).run()
    assert second.status == "error" and second.requests == 0
    assert "nächster Versuch" in second.errors[0]

    clock.now += timedelta(hours=9)
    fake.login_ok = True
    third = _fetcher(config, mfx_secrets, db, clock, fake).run()
    assert third.status == "success"
    assert _fetcher(config, mfx_secrets, db, clock, fake).get_state("login_failed") is None


def test_missing_credentials_make_no_request(config, db, clock) -> None:
    fake = FakeMyfxbook([TOKEN])
    empty = Secrets(_env_file=None)  # type: ignore[call-arg]
    result = _fetcher(config, empty, db, clock, fake).run()
    assert result.status == "error" and result.requests == 0 and fake.calls == []
    assert "MYFXBOOK_EMAIL" in result.errors[0]


def test_daily_limit_is_enforced_across_processes(config, mfx_secrets, db, clock) -> None:
    """80 Requests in den letzten 24 h (persistent in request_log) → kein weiterer Request."""
    for minutes in range(80):
        db.execute(
            "INSERT INTO request_log (source, requested_at) VALUES ('myfxbook', ?)",
            (iso(NOW - timedelta(minutes=10 + minutes), "microseconds"),),
        )
    fake = FakeMyfxbook([TOKEN])
    result = _fetcher(config, mfx_secrets, db, clock, fake).run()
    assert result.status == "error" and fake.calls == []
    assert "Tageslimit" in result.errors[0]


def test_daily_limit_stops_between_login_and_outlook(config, mfx_secrets, db, clock) -> None:
    for minutes in range(79):
        db.execute(
            "INSERT INTO request_log (source, requested_at) VALUES ('myfxbook', ?)",
            (iso(NOW - timedelta(minutes=10 + minutes), "microseconds"),),
        )
    fake = FakeMyfxbook([TOKEN])
    result = _fetcher(config, mfx_secrets, db, clock, fake).run()
    assert result.status == "error"
    assert [name for name, _ in fake.calls] == ["login.json"]  # der 81. Request wird nie gesendet
    total = db.execute("SELECT COUNT(*) FROM request_log WHERE source='myfxbook'").fetchone()[0]
    assert total == 80


def test_old_requests_fall_out_of_the_window(config, mfx_secrets, db, clock) -> None:
    for minutes in range(80):
        db.execute(
            "INSERT INTO request_log (source, requested_at) VALUES ('myfxbook', ?)",
            (iso(NOW - timedelta(hours=25, minutes=minutes), "microseconds"),),
        )
    result = _fetcher(config, mfx_secrets, db, clock, FakeMyfxbook([TOKEN])).run()
    assert result.status == "success"


def test_retry_after_server_error_counts_every_attempt(config, mfx_secrets, db, clock) -> None:
    fake = FakeMyfxbook([TOKEN])
    fake.fail_status = [503, 502]
    result = _fetcher(config, mfx_secrets, db, clock, fake).run()
    assert result.status == "success"
    assert result.requests == 4  # 2 Fehlversuche + Login + Outlook
    assert db.execute("SELECT COUNT(*) FROM request_log").fetchone()[0] == 4
    assert 2.0 in clock.sleeps and 4.0 in clock.sleeps  # Exponential Backoff


def test_persistent_server_error_message_has_no_query(config, mfx_secrets, db, clock) -> None:
    fake = FakeMyfxbook([TOKEN])
    fake.fail_status = [500] * 10
    result = _fetcher(config, mfx_secrets, db, clock, fake).run()
    assert result.status == "error"
    assert PASSWORD not in result.errors[0] and EMAIL not in result.errors[0]
    assert "login.json" in result.errors[0]


def test_missing_mapped_symbol_gives_partial(
    make_config, config_data, mfx_secrets, db, clock
) -> None:
    config_data["assets"]["indices"][0]["myfxbook"] = "NOSUCHSYMBOL"
    config = make_config(assets=config_data["assets"])
    result = _fetcher(config, mfx_secrets, db, clock, FakeMyfxbook([TOKEN])).run()
    assert result.status == "partial"
    assert "NOSUCHSYMBOL" in result.errors[0]
    assert result.items == 17  # die übrigen Symbole sind gespeichert


def test_api_error_other_than_session_is_reported(config, mfx_secrets, db, clock) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("login.json"):
            return httpx.Response(200, json={"error": False, "session": TOKEN})
        return httpx.Response(200, json={"error": True, "message": "Rate limit exceeded"})

    fetcher = MyfxbookFetcher(
        config, mfx_secrets, db, client=mock_client(handler), sleep=clock.sleep, clock=clock
    )
    result = fetcher.run()
    assert result.status == "error" and "Rate limit exceeded" in result.errors[0]
    assert TOKEN not in result.errors[0]


def test_scrub_hides_session_token(config, mfx_secrets, db, clock) -> None:
    fetcher = _fetcher(config, mfx_secrets, db, clock, FakeMyfxbook([TOKEN]))
    fetcher._session = TOKEN
    assert fetcher.scrub(f"x {TOKEN} {PASSWORD} {EMAIL}") == "x *** *** ***"
