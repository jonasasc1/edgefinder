from __future__ import annotations

import httpx
from support import TEST_FRED_KEY, economies_with, fixture_bytes, fixture_json, mock_client

from edgefinder.config import Secrets
from edgefinder.fetchers.fred import FredFetcher, parse_observations

INDICATORS = {
    "US": {
        "name": "USA",
        "indicators": {
            "gdp": {
                "label": "BIP", "source": "fred", "series": "GDPC1", "category": "growth",
                "transform": "yoy", "higher_is": "bullish",
            },
            "yield_10y": {
                "label": "Rendite", "source": "fred", "series": "DGS10", "category": "rates",
                "transform": "level", "higher_is": "bullish",
            },
        },
    }
}  # fmt: skip


def _handler(seen: list[httpx.Request]):
    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        params = request.url.params
        vintages = "realtime_start" in params
        name = f"fred_{params['series_id'].lower()}_{'vintages' if vintages else 'current'}"
        if params["series_id"] == "DGS10" and vintages:
            return httpx.Response(400, content=fixture_bytes("fred_dgs10_too_many_vintages.json"))
        return httpx.Response(200, content=fixture_bytes(f"{name}.json"))

    return handler


def _fetcher(config, secrets, db, clock, handler):
    return FredFetcher(
        config, secrets, db, client=mock_client(handler), sleep=clock.sleep, clock=clock
    )


def test_parse_observations_skips_missing_values() -> None:
    payload = fixture_json("fred_dgs10_current.json")
    assert any(obs["value"] == "." for obs in payload["observations"])
    rows = parse_observations(payload, vintage=False)
    assert len(rows) == len(payload["observations"]) - 1
    assert all(vintage == "" for _, vintage, _ in rows)


def test_fetch_stores_current_values_and_vintages(
    config_data, make_config, secrets, db, clock
) -> None:
    config = make_config(economies=economies_with(config_data, INDICATORS))
    seen: list[httpx.Request] = []
    result = _fetcher(config, secrets, db, clock, _handler(seen)).run()

    assert result.status == "success", result.errors
    assert result.requests == 4  # je Serie aktuell + Vintages
    series = {r.url.params["series_id"] for r in seen}
    assert series == {"GDPC1", "DGS10"}
    assert all(r.url.params["api_key"] == TEST_FRED_KEY for r in seen)
    assert "observation_start" in seen[0].url.params

    # ALFRED: dieselbe Beobachtung mit mehreren Vorabständen, jeder mit eigenem vintage_date
    rows = db.execute(
        "SELECT vintage_date, value FROM macro_observations"
        " WHERE series_id='GDPC1' AND date='2025-04-01' ORDER BY vintage_date"
    ).fetchall()
    assert rows[0]["vintage_date"] == ""  # aktueller Stand
    dated = [r for r in rows if r["vintage_date"]]
    assert len(dated) >= 2
    assert len({r["value"] for r in dated}) >= 2  # Revision sichtbar
    assert rows[0]["value"] == dated[-1]["value"]


def test_daily_series_without_vintages_keeps_current_values(
    config_data, make_config, secrets, db, clock
) -> None:
    config = make_config(economies=economies_with(config_data, INDICATORS))
    result = _fetcher(config, secrets, db, clock, _handler([])).run()
    rows = db.execute(
        "SELECT COUNT(*), SUM(vintage_date != '') FROM macro_observations WHERE series_id='DGS10'"
    ).fetchone()
    assert result.status == "success"  # 400 „zu viele Vintages“ ist kein Fehler
    assert rows[0] > 0
    assert not rows[1]


def test_vintages_can_be_disabled(config_data, make_config, secrets, db, clock) -> None:
    config_data["sources"]["fred"]["options"]["vintages"] = False
    config = make_config(
        economies=economies_with(config_data, INDICATORS), sources=config_data["sources"]
    )
    seen: list[httpx.Request] = []
    result = _fetcher(config, secrets, db, clock, _handler(seen)).run()
    assert result.requests == 2
    assert all("realtime_start" not in r.url.params for r in seen)


def test_failing_series_does_not_block_others(config_data, make_config, secrets, db, clock) -> None:
    config = make_config(economies=economies_with(config_data, INDICATORS))

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.params["series_id"] == "GDPC1":
            return httpx.Response(400, text=f"Bad Request {request.url.params['api_key']}")
        return _handler([])(request)

    result = _fetcher(config, secrets, db, clock, handler).run()

    assert result.status == "partial"
    assert db.execute("SELECT COUNT(*) FROM macro_observations WHERE series_id='DGS10'").fetchone()[
        0
    ]
    assert not db.execute(
        "SELECT COUNT(*) FROM macro_observations WHERE series_id='GDPC1'"
    ).fetchone()[0]
    assert TEST_FRED_KEY not in " ".join(result.errors)


def test_missing_api_key_is_an_error(config_data, make_config, db, clock) -> None:
    config = make_config(economies=economies_with(config_data, INDICATORS))
    secrets = Secrets(_env_file=None)  # type: ignore[call-arg]
    result = _fetcher(config, secrets, db, clock, _handler([])).run()
    assert result.status == "error"
    assert "FRED_API_KEY" in result.errors[0]
    assert result.requests == 0


def test_shipped_config_series_are_requested_once(config, secrets, db, clock) -> None:
    # jede Serie nur einmal, auch wenn sie in mehreren Indikatoren vorkommt
    ids = FredFetcher(
        config, secrets, db, client=mock_client(lambda r: httpx.Response(500))
    ).series_ids()
    assert len(ids) == len(set(ids)) > 20
    assert "GDPC1" in ids
