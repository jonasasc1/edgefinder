from __future__ import annotations

import httpx
import pytest
from support import economies_with, fixture_bytes, fixture_json, mock_client

from edgefinder.fetchers.eurostat import (
    EcbFetcher,
    EurostatFetcher,
    parse_ecb_csv,
    parse_jsonstat,
)
from edgefinder.fetchers.macro import period_start

GDP = "namq_10_gdp?s_adj=SCA&unit=CLV_PCH_SM&na_item=B1GQ&geo=EA21"
HICP_CH = "prc_hicp_minr?coicop18=TOTAL&unit=RCH_A&geo=CH"
DFR = "FM/D.U2.EUR.4F.KR.DFR.LEV"


def _indicator(source: str, series: str) -> dict:
    return {
        "label": "x", "source": source, "series": series, "category": "growth",
        "transform": "level", "higher_is": "bullish",
    }  # fmt: skip


def test_period_start_handles_all_frequencies() -> None:
    assert period_start("2026-Q3") == "2026-07-01"
    assert period_start("2026-Q1") == "2026-01-01"
    assert period_start("2026-09") == "2026-09-01"
    assert period_start("2026") == "2026-01-01"
    assert period_start("2026-11-17") == "2026-11-17"


def test_parse_jsonstat_quarterly_gdp() -> None:
    rows = parse_jsonstat(fixture_json("eurostat_namq_10_gdp_ea21.json"))
    assert rows == sorted(rows)
    assert all(vintage == "" for _, vintage, _ in rows)
    assert rows[0][0] == "2025-01-01"  # 2025-Q1
    assert rows[-1][0] == "2026-07-01"  # 2026-Q3
    assert all(date.endswith(("-01-01", "-04-01", "-07-01", "-10-01")) for date, _, _ in rows)


def test_parse_jsonstat_monthly_hicp_skips_missing_months() -> None:
    payload = fixture_json("eurostat_hicp_ch.json")
    rows = parse_jsonstat(payload)
    assert 0 < len(rows) <= payload["size"][-1]
    assert rows[0][0].startswith("2026-")


def test_parse_jsonstat_rejects_ambiguous_filter() -> None:
    with pytest.raises(ValueError, match="nicht eindeutig"):
        parse_jsonstat(fixture_json("eurostat_ambiguous.json"))


def test_parse_jsonstat_empty_result() -> None:
    assert parse_jsonstat(fixture_json("eurostat_empty.json")) == []


def test_parse_ecb_csv() -> None:
    rows = parse_ecb_csv(fixture_bytes("ecb_dfr.csv").decode())
    assert rows[0] == ("2026-11-09", "", 2.5)
    assert len(rows) >= 5


def _eurostat(make_config, config_data, db, clock, secrets, handler, series=(GDP, HICP_CH)):
    indicators = {
        "EZ": {"indicators": {f"i{n}": _indicator("eurostat", s) for n, s in enumerate(series)}}
    }
    config = make_config(economies=economies_with(config_data, indicators))
    return EurostatFetcher(
        config, secrets, db, client=mock_client(handler), sleep=clock.sleep, clock=clock
    )


def _eurostat_handler(request: httpx.Request) -> httpx.Response:
    name = "eurostat_hicp_ch.json" if "prc_hicp_minr" in request.url.path else (
        "eurostat_namq_10_gdp_ea21.json"
    )  # fmt: skip
    return httpx.Response(200, content=fixture_bytes(name))


def test_eurostat_fetch_builds_query_and_stores(
    make_config, config_data, secrets, db, clock
) -> None:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return _eurostat_handler(request)

    result = _eurostat(make_config, config_data, db, clock, secrets, handler).run()

    assert result.status == "success", result.errors
    params = {r.url.path.rsplit("/", 1)[-1]: r.url.params for r in seen}
    assert params["namq_10_gdp"]["geo"] == "EA21"
    assert params["namq_10_gdp"]["unit"] == "CLV_PCH_SM"
    assert params["namq_10_gdp"]["sinceTimePeriod"] == "2011-11"  # 15 Jahre zurück
    assert params["prc_hicp_minr"]["geo"] == "CH"
    stored = db.execute(
        "SELECT series_id, COUNT(*) FROM macro_observations WHERE source='eurostat' GROUP BY 1"
    ).fetchall()
    assert {row[0] for row in stored} == {GDP, HICP_CH}
    assert db.execute("SELECT COUNT(*) FROM macro_observations").fetchone()[0] == result.items


def test_eurostat_empty_series_is_reported_and_others_continue(
    make_config, config_data, secrets, db, clock
) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if "namq_10_gdp" in request.url.path:
            return httpx.Response(200, content=fixture_bytes("eurostat_empty.json"))
        return _eurostat_handler(request)

    result = _eurostat(make_config, config_data, db, clock, secrets, handler).run()

    assert result.status == "partial"
    assert "Antwort ohne Werte" in result.errors[0]
    assert db.execute(
        "SELECT COUNT(*) FROM macro_observations WHERE series_id=?", (HICP_CH,)
    ).fetchone()[0]


def test_ecb_fetch(make_config, config_data, secrets, db, clock) -> None:
    indicators = {"EZ": {"indicators": {"policy_rate": _indicator("ecb", DFR)}}}
    config = make_config(economies=economies_with(config_data, indicators))
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, content=fixture_bytes("ecb_dfr.csv"))

    result = EcbFetcher(
        config, secrets, db, client=mock_client(handler), sleep=clock.sleep, clock=clock
    ).run()

    assert result.status == "success", result.errors
    assert seen[0].url.path.endswith("/service/data/" + DFR)
    assert seen[0].url.params["format"] == "csvdata"
    assert seen[0].url.params["startPeriod"] == "2011-11-17"
    row = db.execute(
        "SELECT source, vintage_date, value FROM macro_observations WHERE date='2026-11-09'"
    ).fetchone()
    assert tuple(row) == ("ecb", "", 2.5)


def test_ecb_failure_is_isolated_from_eurostat(
    make_config, config_data, secrets, db, clock
) -> None:
    indicators = {"EZ": {"indicators": {"policy_rate": _indicator("ecb", DFR)}}}
    config = make_config(economies=economies_with(config_data, indicators))
    ecb = EcbFetcher(
        config, secrets, db, client=mock_client(lambda r: httpx.Response(404)), sleep=clock.sleep,
        clock=clock,
    )  # fmt: skip
    assert ecb.run().status == "error"
    eurostat = _eurostat(make_config, config_data, db, clock, secrets, _eurostat_handler).run()
    assert eurostat.status == "success"


def test_shipped_config_has_series_for_all_economies(config) -> None:
    for code, economy in config.economies.items():
        assert economy.indicators, f"{code} hat keine Makro-Serien"
    sources = {i.source for e in config.economies.values() for i in e.indicators.values()}
    assert sources == {"fred", "eurostat", "ecb"}
