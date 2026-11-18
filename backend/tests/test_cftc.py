from __future__ import annotations

from datetime import timedelta

import httpx
from support import TEST_CFTC_TOKEN, fixture_bytes, fixture_json, mock_client

from edgefinder.config import Secrets
from edgefinder.fetchers import cftc
from edgefinder.fetchers.cftc import CftcFetcher, parse_rows

CODES = {"099741", "209742", "240743"}  # im Fixture enthalten


def _config(make_config, config_data):
    """Nur die Kontrakte, die das Fixture enthält (EUR, Nasdaq, Nikkei)."""
    for currency in config_data["currencies"].values():
        if currency["cftc_code"] not in CODES:
            currency["cftc_code"] = None
    for key in ("indices", "commodities"):
        for asset in config_data["assets"][key]:
            if asset.get("cftc_code") not in CODES:
                asset["cftc_code"] = None
    return make_config(currencies=config_data["currencies"], assets=config_data["assets"])


def _fetcher(config, secrets, db, clock, handler):
    return CftcFetcher(
        config, secrets, db, client=mock_client(handler), sleep=clock.sleep, clock=clock
    )


def _ok(request: httpx.Request) -> httpx.Response:
    return httpx.Response(200, content=fixture_bytes("cftc_legacy_futures.json"))


def test_parse_rows_maps_legacy_columns() -> None:
    rows = parse_rows(fixture_json("cftc_legacy_futures.json"))
    by_key = {(row[0], row[1]): row for row in rows}
    nikkei = by_key["240743", "2026-11-10"]
    # code, date, name, OI, nc_long, nc_short, nc_spread, comm_long, comm_short, nr_long, nr_short
    assert nikkei[3:] == (27258, 5791, 4106, 211, 16170, 8581, 5086, 14360)
    assert nikkei[2].startswith("NIKKEI STOCK AVERAGE YEN DENOM")
    assert {row[0] for row in rows} == CODES


def test_parse_rows_skips_records_without_positions() -> None:
    record = {"cftc_contract_market_code": "X", "report_date_as_yyyy_mm_dd": "2026-01-06T00:00:00"}
    assert parse_rows([record]) == []


def test_fetch_stores_reports_and_logs_run(make_config, config_data, secrets, db, clock) -> None:
    config = _config(make_config, config_data)
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return _ok(request)

    result = _fetcher(config, secrets, db, clock, handler).run()

    assert result.status == "success", result.errors
    assert result.requests == 1
    rows = db.execute("SELECT COUNT(*) FROM cot_reports").fetchone()[0]
    assert rows == result.items == len(parse_rows(fixture_json("cftc_legacy_futures.json")))
    query = seen[0].url.params
    assert "6dca-aqww" in seen[0].url.path
    assert "'099741'" in query["$where"]
    assert "'098662'" not in query["$where"]
    assert "2011-11-1" in query["$where"]  # history_years = 15 ab 2026-11-17
    assert "x-app-token" not in seen[0].headers
    assert db.execute("SELECT COUNT(*) FROM raw_files WHERE source='cftc'").fetchone()[0] == 1


def test_fetch_is_idempotent(make_config, config_data, secrets, db, clock) -> None:
    config = _config(make_config, config_data)
    first = _fetcher(config, secrets, db, clock, _ok).run()
    second = _fetcher(config, secrets, db, clock, _ok).run()
    assert db.execute("SELECT COUNT(*) FROM cot_reports").fetchone()[0] == first.items
    assert second.status == "success"


def test_app_token_is_sent_as_header(make_config, config_data, db, clock) -> None:
    config = _config(make_config, config_data)
    secrets = Secrets(_env_file=None, cftc_app_token=TEST_CFTC_TOKEN)  # type: ignore[call-arg]
    seen: list[httpx.Request] = []
    _fetcher(config, secrets, db, clock, lambda r: (seen.append(r), _ok(r))[1]).run()
    assert seen[0].headers["x-app-token"] == TEST_CFTC_TOKEN
    assert TEST_CFTC_TOKEN not in str(seen[0].url)


def test_pagination(make_config, config_data, secrets, db, clock, monkeypatch) -> None:
    config = _config(make_config, config_data)
    records = fixture_json("cftc_legacy_futures.json")
    monkeypatch.setattr(cftc, "PAGE_SIZE", 4)
    offsets: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        offset = int(request.url.params["$offset"])
        offsets.append(str(offset))
        return httpx.Response(200, json=records[offset : offset + 4])

    result = _fetcher(config, secrets, db, clock, handler).run()
    assert result.items == len(parse_rows(records))
    assert len(offsets) == len(records) // 4 + 1


def test_missing_contract_is_reported_as_partial(make_config, secrets, db, clock) -> None:
    # volle Konfiguration (16 Kontrakte), Antwort enthält nur 3 → die übrigen fallen auf
    config = make_config()
    result = _fetcher(config, secrets, db, clock, _ok).run()
    assert result.status == "partial"
    assert any("Kontrakt 098662: ValueError: keine Daten" in error for error in result.errors)
    assert not any("240743" in error for error in result.errors)


def test_discontinued_contract_is_detected(make_config, config_data, secrets, db, clock) -> None:
    config = _config(make_config, config_data)
    clock.now += timedelta(days=60)  # letzte Meldung 2026-11-10 ist dann > 45 Tage alt
    result = _fetcher(config, secrets, db, clock, _ok).run()
    assert result.status == "partial"
    assert any("eingestellt" in error for error in result.errors)


def test_http_failure_marks_run_as_error(make_config, secrets, db, clock) -> None:
    result = _fetcher(make_config(), secrets, db, clock, lambda r: httpx.Response(404)).run()
    assert result.status == "error"
    assert db.execute("SELECT COUNT(*) FROM cot_reports").fetchone()[0] == 0
