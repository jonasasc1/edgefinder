from __future__ import annotations

import logging
import sqlite3
from datetime import timedelta

import httpx
import pytest
from support import TEST_FRED_KEY, FakeClock, mock_client

from edgefinder.config import Config, Secrets
from edgefinder.fetchers.base import (
    Fetcher,
    FetchError,
    HttpClient,
    RateLimiter,
    RateLimitExceeded,
    call_with_retry,
)


class DummyFetcher(Fetcher):
    source = "fred"

    def __init__(self, *args, behaviour, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.behaviour = behaviour

    def fetch(self) -> int:
        return self.behaviour(self)


def _dummy(config: Config, secrets: Secrets, db: sqlite3.Connection, clock: FakeClock, behaviour):
    return DummyFetcher(
        config, secrets, db, sleep=clock.sleep, clock=clock, behaviour=behaviour,
        client=mock_client(lambda request: httpx.Response(200)),
    )  # fmt: skip


def _limiter(config: Config, db: sqlite3.Connection, clock: FakeClock, source: str = "cftc"):
    return RateLimiter(db, source, config.sources[source], sleep=clock.sleep, clock=clock)


def test_rate_limiter_enforces_min_interval(config, db, clock) -> None:
    limiter = _limiter(config, db, clock, "fred")  # 0,6 s Abstand
    limiter.wait()
    limiter.wait()
    clock.now += timedelta(seconds=5)
    limiter.wait()

    assert clock.sleeps == [pytest.approx(0.6)]
    assert db.execute("SELECT COUNT(*) FROM request_log WHERE source='fred'").fetchone()[0] == 3


def test_rate_limiter_is_per_source(config, db, clock) -> None:
    _limiter(config, db, clock, "fred").wait()
    _limiter(config, db, clock, "cftc").wait()
    assert clock.sleeps == []


def test_rate_limiter_daily_limit_blocks_and_expires(config_data, make_config, db, clock) -> None:
    config_data["sources"]["myfxbook"]["daily_request_limit"] = 2
    config = make_config(sources=config_data["sources"])
    limiter = _limiter(config, db, clock, "myfxbook")
    limiter.wait()
    limiter.wait()
    with pytest.raises(RateLimitExceeded):
        limiter.wait()
    clock.now += timedelta(hours=25)
    limiter.wait()  # alte Requests zählen nicht mehr


def _client(config, db, clock, handler, source="fred") -> HttpClient:
    return HttpClient(
        source,
        _limiter(config, db, clock, source),
        config.retry,
        client=mock_client(handler),
        sleep=clock.sleep,
    )


def test_http_retries_with_exponential_backoff(config, db, clock) -> None:
    statuses = iter([503, 429, 200])
    http = _client(config, db, clock, lambda request: httpx.Response(next(statuses), text="ok"))

    assert http.get("https://example.org/x").text == "ok"
    assert http.requests == 3
    # backoff_seconds = 2 → 2 s, dann 4 s (Rate-Limit-Wartezeit 0,6 s ist darin enthalten)
    assert [round(s) for s in clock.sleeps if s >= 2] == [2, 4]


def test_http_honours_retry_after(config, db, clock) -> None:
    answers = iter([httpx.Response(429, headers={"Retry-After": "17"}), httpx.Response(200)])
    http = _client(config, db, clock, lambda request: next(answers))
    http.get("https://example.org/x")
    assert 17 in clock.sleeps


def test_http_client_errors_are_not_retried(config, db, clock) -> None:
    http = _client(config, db, clock, lambda request: httpx.Response(404))
    with pytest.raises(FetchError, match="HTTP 404") as info:
        http.get("https://example.org/x")
    assert http.requests == 1
    assert info.value.status == 404


def test_http_gives_up_after_configured_attempts(config, db, clock) -> None:
    http = _client(config, db, clock, lambda request: httpx.Response(500))
    with pytest.raises(FetchError, match="nach 4 Versuchen"):
        http.get("https://example.org/x")
    assert http.requests == config.retry.attempts


def test_http_retries_transport_errors(config, db, clock) -> None:
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        if len(calls) < 3:
            raise httpx.ConnectTimeout("zu langsam", request=request)
        return httpx.Response(200)

    assert _client(config, db, clock, handler).get("https://example.org/x").status_code == 200
    assert len(calls) == 3


def test_errors_never_contain_query_or_api_key(config, db, clock) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError(f"kaputt: {request.url}", request=request)

    http = _client(config, db, clock, handler)
    with pytest.raises(FetchError) as info:
        http.get("https://example.org/data", {"api_key": TEST_FRED_KEY})
    assert TEST_FRED_KEY not in str(info.value)
    assert "api_key" not in str(info.value)

    http = _client(config, db, clock, lambda request: httpx.Response(400))
    with pytest.raises(FetchError) as info:
        http.get("https://example.org/data", {"api_key": TEST_FRED_KEY})
    assert TEST_FRED_KEY not in str(info.value)


def test_httpx_request_logging_is_silenced() -> None:
    # httpx loggt URLs samt API-Key auf INFO; das darf nie ausgegeben werden.
    assert logging.getLogger("httpx").getEffectiveLevel() >= logging.WARNING


def test_call_with_retry_retries_any_exception(config, db, clock) -> None:
    attempts = []

    def flaky() -> str:
        attempts.append(1)
        if len(attempts) < 3:
            raise RuntimeError("Yahoo hat Rate-Limit")
        return "fertig"

    result = call_with_retry(
        "prices", flaky, _limiter(config, db, clock, "prices"), config.retry, sleep=clock.sleep
    )
    assert result == "fertig"
    assert len(attempts) == 3


def test_call_with_retry_raises_after_last_attempt(config, db, clock) -> None:
    def broken() -> str:
        raise RuntimeError("tot")

    with pytest.raises(FetchError, match="RuntimeError: tot nach 4 Versuchen"):
        call_with_retry(
            "prices", broken, _limiter(config, db, clock, "prices"), config.retry,
            sleep=clock.sleep,
        )  # fmt: skip


def _run_row(db: sqlite3.Connection) -> sqlite3.Row:
    return db.execute("SELECT * FROM fetch_runs ORDER BY id DESC LIMIT 1").fetchone()


def test_run_success_is_logged(config, secrets, db, clock) -> None:
    result = _dummy(config, secrets, db, clock, lambda fetcher: 7).run()

    row = _run_row(db)
    assert (result.status, result.items) == ("success", 7)
    assert (row["status"], row["items"], row["error"]) == ("success", 7, None)
    assert row["started_at"].startswith("2026-11-17T12:00:00")
    assert row["finished_at"] is not None


def test_run_with_failed_units_is_partial_and_continues(config, secrets, db, clock) -> None:
    def behaviour(fetcher: Fetcher) -> int:
        total = 0
        for name in ("A", "B", "C"):
            with fetcher.unit(name):
                if name == "B":
                    raise ValueError(f"kaputt mit {TEST_FRED_KEY}")
                total += 1
        return total

    result = _dummy(config, secrets, db, clock, behaviour).run()

    assert (result.status, result.items) == ("partial", 2)
    row = _run_row(db)
    assert row["status"] == "partial"
    assert "B: ValueError" in row["error"]
    assert TEST_FRED_KEY not in row["error"]  # Secret geschwärzt


def test_run_crash_is_error_and_does_not_raise(config, secrets, db, clock) -> None:
    def behaviour(fetcher: Fetcher) -> int:
        raise FetchError("Quelle down")

    result = _dummy(config, secrets, db, clock, behaviour).run()
    assert result.status == "error"
    assert _run_row(db)["error"] == "FetchError: Quelle down"


def test_failing_source_does_not_block_another(config, secrets, db, clock) -> None:
    def down(fetcher: Fetcher) -> int:
        raise FetchError("down")

    _dummy(config, secrets, db, clock, down).run()
    ok = _dummy(config, secrets, db, clock, lambda fetcher: 1).run()
    assert ok.status == "success"


def test_save_raw_writes_file_and_index(config, secrets, db, clock) -> None:
    fetcher = _dummy(config, secrets, db, clock, lambda f: 0)
    fetcher.run_id = None
    path = fetcher.save_raw("GDPC1/current?x=1", b'{"a": 1}')

    assert path.read_bytes() == b'{"a": 1}'
    assert path.is_relative_to(config.storage.raw_dir / "fred" / "2026-11-17")
    row = db.execute("SELECT * FROM raw_files").fetchone()
    assert (row["source"], row["key"], row["bytes"]) == ("fred", "GDPC1/current?x=1", 8)
    assert len(row["sha256"]) == 64
    assert row["path"].startswith("fred/2026-11-17/")
