from __future__ import annotations

import json
from datetime import timedelta

import httpx
from support import fixture_bytes, mock_client

from edgefinder.fetchers.finra import FinraFetcher, finra_symbol, parse_rows


def _fetcher(config, secrets, db, clock, handler) -> FinraFetcher:
    return FinraFetcher(
        config, secrets, db, client=mock_client(handler), sleep=clock.sleep, clock=clock
    )


def _ok(request: httpx.Request) -> httpx.Response:
    return httpx.Response(200, content=fixture_bytes("finra_consolidated_short_interest.json"))


def _stocks(make_config, config_data, tickers):
    config_data["assets"]["stocks"] = [
        s for s in config_data["assets"]["stocks"] if s["ticker"] in tickers
    ]
    return make_config(assets=config_data["assets"])


def test_finra_symbol_drops_class_separator() -> None:
    assert finra_symbol("BRK-B") == "BRKB"
    assert finra_symbol("AAPL") == "AAPL"


def test_parse_rows_maps_symbols_back_to_config_tickers() -> None:
    records = json.loads(fixture_bytes("finra_consolidated_short_interest.json"))
    rows = parse_rows(records, {"AAPL": "AAPL", "BRKB": "BRK-B"})
    assert ("BRK-B", "2026-10-30", 15232424.0, 4459554, 3.42) in rows
    assert {row[0] for row in rows} == {"AAPL", "BRK-B"}  # GOOGL nicht angefragt → ignoriert
    assert len(rows) == 4


def test_fetch_posts_filter_and_stores_rows(make_config, config_data, secrets, db, clock) -> None:
    config = _stocks(make_config, config_data, {"AAPL", "BRK-B", "GOOGL"})
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return _ok(request)

    result = _fetcher(config, secrets, db, clock, handler).run()

    assert result.status == "success", result.errors
    assert result.items == 6 and result.requests == 1
    assert seen[0].method == "POST" and seen[0].url.path.endswith("consolidatedShortInterest")
    body = json.loads(seen[0].content)
    assert sorted(body["domainFilters"][0]["values"]) == ["AAPL", "BRKB", "GOOGL"]
    assert body["compareFilters"][0]["fieldValue"] == "2024-11-16"  # 2 Jahre Erstladung, -1 Tag
    row = db.execute("SELECT * FROM short_interest WHERE ticker='BRK-B' ORDER BY 2 DESC").fetchone()
    assert (row["settlement_date"], row["days_to_cover"]) == ("2026-10-30", 3.42)
    assert db.execute("SELECT COUNT(*) FROM raw_files WHERE source='finra'").fetchone()[0] == 1


def test_later_runs_only_fetch_recent_window(make_config, config_data, secrets, db, clock) -> None:
    config = _stocks(make_config, config_data, {"AAPL", "BRK-B", "GOOGL"})
    _fetcher(config, secrets, db, clock, _ok).run()
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return _ok(request)

    clock.now += timedelta(days=3)
    second = _fetcher(config, secrets, db, clock, handler).run()
    assert second.status == "success"
    assert json.loads(seen[0].content)["compareFilters"][0]["fieldValue"] == "2026-09-20"
    assert db.execute("SELECT COUNT(*) FROM short_interest").fetchone()[0] == 6  # idempotent


def test_ticker_without_data_gives_partial(make_config, config_data, secrets, db, clock) -> None:
    config = _stocks(make_config, config_data, {"AAPL", "MSFT"})  # MSFT nicht im Fixture
    result = _fetcher(config, secrets, db, clock, _ok).run()
    assert result.status == "partial" and result.items == 2
    assert "MSFT" in result.errors[0]


def test_stale_ticker_gives_partial(make_config, config_data, secrets, db, clock) -> None:
    config = _stocks(make_config, config_data, {"AAPL"})
    clock.now += timedelta(days=90)  # Fixture-Daten sind dann > 45 Tage alt
    result = _fetcher(config, secrets, db, clock, _ok).run()
    assert result.status == "partial" and "delistet" in result.errors[0]


def test_bad_request_is_an_error_without_retry(config, secrets, db, clock) -> None:
    result = _fetcher(config, secrets, db, clock, lambda r: httpx.Response(400, json={})).run()
    assert result.status == "error" and result.requests == 1


def test_server_error_is_retried(config, secrets, db, clock) -> None:
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        return httpx.Response(502) if len(calls) < 3 else _ok(request)

    result = _fetcher(config, secrets, db, clock, handler).run()
    assert result.requests == 3 and result.items > 0


def test_unexpected_payload_is_an_error(config, secrets, db, clock) -> None:
    result = _fetcher(
        config, secrets, db, clock, lambda r: httpx.Response(200, json={"x": 1})
    ).run()
    assert result.status == "error"
