from __future__ import annotations

import httpx
from support import fixture_bytes, mock_client

from edgefinder.fetchers.aaii import AaiiFetcher, parse_survey


def _fetcher(config, secrets, db, clock, handler) -> AaiiFetcher:
    return AaiiFetcher(
        config, secrets, db, client=mock_client(handler), sleep=clock.sleep, clock=clock
    )


def _ok(request: httpx.Request) -> httpx.Response:
    return httpx.Response(200, content=fixture_bytes("aaii_sentimentsurvey.html"))


def test_parse_survey_reads_current_and_recent_weeks() -> None:
    weeks = parse_survey(fixture_bytes("aaii_sentimentsurvey.html").decode())
    assert weeks == {
        "2026-11-11": (30.8, 17.8, 51.4),
        "2026-11-04": (34.1, 17.5, 48.4),
        "2026-10-28": (37.8, 20.7, 41.4),
        "2026-10-21": (36.9, 17.3, 45.8),
    }


def test_parse_survey_ignores_pages_without_results() -> None:
    assert parse_survey("<html><body>Just a moment...</body></html>") == {}


def test_fetch_stores_weeks_and_raw_html(config, secrets, db, clock) -> None:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return _ok(request)

    result = _fetcher(config, secrets, db, clock, handler).run()

    assert result.status == "success", result.errors
    assert result.items == 4 and result.requests == 1
    row = db.execute("SELECT * FROM aaii_sentiment WHERE week_date='2026-11-11'").fetchone()
    assert (row["bullish"], row["neutral"], row["bearish"]) == (30.8, 17.8, 51.4)
    assert db.execute("SELECT COUNT(*) FROM raw_files WHERE source='aaii'").fetchone()[0] == 1
    agent = seen[0].headers["user-agent"]
    assert agent.startswith("edgefinder/") and "research" in agent  # ehrlich, kein Browser-UA
    assert "Mozilla" not in agent


def test_fetch_is_idempotent_and_keeps_history(config, secrets, db, clock) -> None:
    _fetcher(config, secrets, db, clock, _ok).run()
    db.execute("DELETE FROM aaii_sentiment WHERE week_date='2026-10-21'")  # ältere Wochen bleiben
    second = _fetcher(config, secrets, db, clock, _ok).run()
    assert second.status == "success"
    assert db.execute("SELECT COUNT(*) FROM aaii_sentiment").fetchone()[0] == 4


def test_blocked_with_403_is_an_error_without_fallback(config, secrets, db, clock) -> None:
    result = _fetcher(config, secrets, db, clock, lambda r: httpx.Response(403)).run()
    assert result.status == "error" and result.requests == 1  # 403 wird nicht wiederholt
    assert "403" in result.errors[0]
    assert db.execute("SELECT COUNT(*) FROM aaii_sentiment").fetchone()[0] == 0


def test_challenge_page_with_200_is_an_error(config, secrets, db, clock) -> None:
    page = httpx.Response(200, text="<html><title>Just a moment...</title></html>")
    result = _fetcher(config, secrets, db, clock, lambda r: page).run()
    assert result.status == "error"
    assert "Bot-Schutz" in result.errors[0]
    assert db.execute("SELECT COUNT(*) FROM aaii_sentiment").fetchone()[0] == 0


def test_server_error_is_retried(config, secrets, db, clock) -> None:
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        return httpx.Response(503) if len(calls) == 1 else _ok(request)

    result = _fetcher(config, secrets, db, clock, handler).run()
    assert result.status == "success" and result.requests == 2


def test_implausible_week_is_skipped_as_partial(config, secrets, db, clock) -> None:
    html = fixture_bytes("aaii_sentimentsurvey.html").decode().replace("45.8%", "5.8%")
    result = _fetcher(config, secrets, db, clock, lambda r: httpx.Response(200, text=html)).run()
    assert result.status == "partial" and result.items == 3
    assert "2026-10-21" in result.errors[0]
