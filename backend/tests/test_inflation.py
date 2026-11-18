"""Nationale Inflationsquellen (ONS, StatCan, ABS, IMF): Parser und Fetcher gegen Fixtures."""

from __future__ import annotations

import json
from datetime import date

import httpx
import pytest
from support import economies_with, fixture_bytes, fixture_json, mock_client

from edgefinder.fetchers import FETCHERS
from edgefinder.fetchers.inflation import (
    AbsFetcher,
    ImfFetcher,
    OnsFetcher,
    StatcanFetcher,
    parse_ons_csv,
    parse_sdmx_csv,
    parse_statcan,
)
from edgefinder.scoring.data import DataStore

SERIES = {
    "ons": ("UK", "D7G7/mm23"),
    "statcan": ("CA", "41690973"),
    "abs": ("AU", "CPI/1.10001.10.50.Q"),
    "imf": ("JP", "CPI/JPN.CPI._T.IX.M"),
}


def _indicator(source: str, series: str, **extra) -> dict:
    return {
        "label": "CPI", "source": source, "series": series, "category": "inflation",
        "transform": "yoy", "higher_is": "bullish", **extra,
    }  # fmt: skip


def _run(fetcher_cls, make_config, config_data, secrets, db, clock, handler):
    source = fetcher_cls.source
    economy, series = SERIES[source]
    indicators = {economy: {"indicators": {"cpi": _indicator(source, series)}}}
    config = make_config(economies=economies_with(config_data, indicators))
    return fetcher_cls(
        config, secrets, db, client=mock_client(handler), sleep=clock.sleep, clock=clock
    ).run()


def _stored(db, series: str) -> list[tuple[str, float]]:
    return [
        (r[0], r[1])
        for r in db.execute(
            "SELECT date, value FROM macro_observations WHERE series_id = ? ORDER BY date",
            (series,),
        )
    ]


def test_all_sources_registered() -> None:
    assert {"ons", "statcan", "abs", "imf"} <= set(FETCHERS)


def test_parse_ons_csv_uses_only_monthly_rows() -> None:
    rows = parse_ons_csv(fixture_bytes("ons_cpi_d7g7.csv").decode())
    assert rows[-1] == ("2026-10-01", "", 3.6)
    assert ("2026-09-01", "", 3.5) in rows
    assert len(rows) == 26
    assert all(day.endswith("-01") and len(day) == 10 for day, _, _ in rows)  # keine Quartale/Jahre
    assert rows == sorted(rows)


def test_parse_ons_csv_ignores_empty_and_garbage() -> None:
    assert parse_ons_csv('"Title","x"\n"2026 OCT",""\n"2026 XYZ","1"\n"2026 Q3","1"\n') == []


def test_parse_statcan() -> None:
    rows = parse_statcan(fixture_json("statcan_cpi_v41690973.json"))
    assert rows[-1] == ("2026-10-01", "", 170.4)
    assert rows == sorted(rows)
    with pytest.raises(Exception, match="Status FAILED"):
        parse_statcan([{"status": "FAILED"}])


def test_parse_sdmx_csv_abs_quarters_and_imf_months() -> None:
    abs_rows = parse_sdmx_csv(fixture_bytes("abs_cpi_quarterly.csv").decode())
    assert abs_rows[-1] == ("2026-07-01", "", 103.64)  # 2026-Q3 = Periodenbeginn Juli
    assert abs_rows == sorted(abs_rows)
    imf_rows = parse_sdmx_csv(fixture_bytes("imf_cpi_jpn_monthly.csv").decode())
    assert imf_rows[-1] == ("2026-09-01", "", 114.5)  # "2026-M09"
    assert imf_rows[0] == ("2025-06-01", "", 111.7)


def test_ons_fetch(make_config, config_data, secrets, db, clock) -> None:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, content=fixture_bytes("ons_cpi_d7g7.csv"))

    result = _run(OnsFetcher, make_config, config_data, secrets, db, clock, handler)
    assert result.status == "success", result.errors
    assert seen[0].url.params["uri"] == "/economy/inflationandpriceindices/timeseries/d7g7/mm23"
    assert seen[0].url.params["format"] == "csv"
    assert _stored(db, "D7G7/mm23")[-1] == ("2026-10-01", 3.6)
    assert db.execute("SELECT COUNT(*) FROM raw_files WHERE source='ons'").fetchone()[0] == 1
    assert db.execute("SELECT status FROM fetch_runs WHERE source='ons'").fetchone()[0] == "success"


def test_statcan_fetch_posts_vector(make_config, config_data, secrets, db, clock) -> None:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, content=fixture_bytes("statcan_cpi_v41690973.json"))

    result = _run(StatcanFetcher, make_config, config_data, secrets, db, clock, handler)
    assert result.status == "success", result.errors
    assert seen[0].method == "POST"
    assert json.loads(seen[0].content) == [{"vectorId": 41690973, "latestN": 193}]
    assert _stored(db, "41690973")[-1] == ("2026-10-01", 170.4)


def test_abs_fetch_requests_csv(make_config, config_data, secrets, db, clock) -> None:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, content=fixture_bytes("abs_cpi_quarterly.csv"))

    result = _run(AbsFetcher, make_config, config_data, secrets, db, clock, handler)
    assert result.status == "success", result.errors
    assert seen[0].url.path.endswith("/data/CPI/1.10001.10.50.Q")
    assert seen[0].url.params["startPeriod"] == "2011-Q1"
    assert "csv" in seen[0].headers["accept"]
    assert _stored(db, "CPI/1.10001.10.50.Q")[-1] == ("2026-07-01", 103.64)


def test_imf_fetch_requests_key(make_config, config_data, secrets, db, clock) -> None:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, content=fixture_bytes("imf_cpi_jpn_monthly.csv"))

    result = _run(ImfFetcher, make_config, config_data, secrets, db, clock, handler)
    assert result.status == "success", result.errors
    assert seen[0].url.path.endswith("/data/IMF.STA,CPI/JPN.CPI._T.IX.M")
    assert _stored(db, "CPI/JPN.CPI._T.IX.M")[-1] == ("2026-09-01", 114.5)


def test_failure_is_isolated_and_logged(make_config, config_data, secrets, db, clock) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(404)

    result = _run(OnsFetcher, make_config, config_data, secrets, db, clock, handler)
    assert result.status == "error"
    assert "HTTP 404" in result.errors[0]
    assert db.execute("SELECT status FROM fetch_runs").fetchone()[0] == "error"


def test_empty_answer_is_an_error(make_config, config_data, secrets, db, clock) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=b'"Title","x"\n')

    result = _run(OnsFetcher, make_config, config_data, secrets, db, clock, handler)
    assert result.status == "error"
    assert "Antwort ohne Monatswerte" in result.errors[0]


def test_fixed_publication_lag_overrides_frequency_estimate(config, db) -> None:
    rows = [(f"2026-{m:02d}-01", "", 100.0 + m) for m in range(1, 10)]
    db.executemany(
        "INSERT INTO macro_observations (source, series_id, date, vintage_date, value)"
        " VALUES ('imf', 'S', ?, ?, ?)",
        rows,
    )
    store = DataStore(db, config)
    as_of = date(2026, 10, 30)
    default = store.macro_series("imf", "S", as_of)  # monatlich: 50 Tage → bis 2026-09-10
    assert default[-1][0] == "2026-09-01"
    late = store.macro_series("imf", "S", as_of, fixed_lag=75)  # bis 2026-08-16
    assert late[-1][0] == "2026-08-01"
