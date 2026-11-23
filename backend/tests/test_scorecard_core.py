"""Scorecard „Kernzeilen“ (EdgeFinder-Muster): Transforms mom/sma, Modell-Erwartung ohne Look-ahead,
Surprise, Release-Kalender (FRED), display_only-Indikatoren (Score unverändert), Migration 0006."""

from __future__ import annotations

import copy
import importlib
import sqlite3
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any

import httpx
import pytest
from pydantic import ValidationError
from support import economies_with, fixture_bytes, mock_client

from edgefinder.api.scorecard import build_scorecard
from edgefinder.config import Config
from edgefinder.db import connect, migrate
from edgefinder.fetchers.fred import (
    FredFetcher,
    calendar_series,
    parse_release_dates,
    parse_release_id,
)
from edgefinder.scoring.data import DataStore
from edgefinder.scoring.factors import macro as macro_f

TODAY = datetime.now(UTC).date()


def _daily(values: list[float], start: date = date(2026, 1, 1)) -> list[tuple[str, float]]:
    return [((start + timedelta(days=i)).isoformat(), v) for i, v in enumerate(values)]


def _ind(transform: str, values: list[float], window: int | None = None) -> macro_f.IndicatorData:
    return macro_f.IndicatorData(
        "k", "k", "growth", transform, "bullish", _daily(values), window=window
    )


# ------------------------------------------------------------------ Transforms
def test_mom_is_percent_change_to_previous_value() -> None:
    values = macro_f.transformed(_ind("mom", [100.0, 101.0, 100.0, 103.0]))
    assert [round(v, 4) for _, v in values] == [1.0, -0.9901, 3.0]
    assert [d for d, _ in values] == ["2026-01-02", "2026-01-03", "2026-01-04"]


def test_sma_uses_trailing_window_only() -> None:
    values = macro_f.transformed(_ind("sma", [1.0, 2.0, 3.0, 4.0, 10.0], window=3))
    assert [round(v, 4) for _, v in values] == [2.0, 3.0, 5.6667]
    assert values[0][0] == "2026-01-03"  # erster Wert erst nach `window` Beobachtungen
    assert macro_f.transformed(_ind("sma", [1.0, 2.0], window=3)) == []
    # Der Wert eines Tages hängt nicht von späteren Tagen ab (kein Look-ahead)
    short = macro_f.transformed(_ind("sma", [1.0, 2.0, 3.0, 4.0], window=3))
    assert short == values[:2]


def test_qoq_series_is_level_transform() -> None:
    values = macro_f.transformed(_ind("level", [0.2, 2.5, 2.2, 3.4]))
    assert [v for _, v in values] == [0.2, 2.5, 2.2, 3.4]


# ------------------------------------------------------------------ Erwartung
def test_expectation_is_mean_of_previous_values_without_look_ahead() -> None:
    series = _daily([1.0, 2.0, 3.0, 4.0, 100.0])
    assert macro_f.expectation_of(series, 3) == pytest.approx(3.0)  # 2, 3, 4 (nicht der Wert 100)
    # Ein späterer Wert ändert die Erwartung für den früheren Stichtag nicht
    assert macro_f.expectation_of(series[:4], 3) == pytest.approx(2.0)
    assert macro_f.expectation_of(series[:4], 3) == macro_f.expectation_of([*series[:4]], 3)
    assert macro_f.expectation_of(series[:3], 3) is None  # zu wenige Vorwerte
    assert macro_f.expectation_of(series, 0) is None


def test_nfp_expectation_uses_monthly_changes() -> None:
    nfp = _ind("diff", [100.0, 110.0, 130.0, 135.0, 160.0, 170.0, 180.0, 210.0])
    changes = macro_f.transformed(nfp)  # 10, 20, 5, 25, 10, 10, 30
    assert macro_f.expectation_of(changes, 6) == pytest.approx((10 + 20 + 5 + 25 + 10 + 10) / 6)
    assert changes[-1][1] - macro_f.expectation_of(changes, 6) == pytest.approx(30 - 80 / 6)


# ------------------------------------------------------------------ Konfiguration
def _indicator(**kw: Any) -> dict[str, Any]:
    base = {
        "label": "x", "source": "fred", "series": "RSAFS", "category": "growth",
        "transform": "level", "higher_is": "bullish",
    }  # fmt: skip
    return base | kw


def _with_indicator(config_data: dict[str, Any], key: str, **kw: Any) -> dict[str, Any]:
    data = copy.deepcopy(config_data)
    data["economies"]["US"]["indicators"][key] = _indicator(**kw)
    return data


@pytest.mark.parametrize(
    "kw",
    [
        {"transform": "sma", "display_only": True},  # Fenster fehlt
        {"transform": "level", "window": 5},  # Fenster ohne sma
        {"transform": "mom"},  # mom nur für display_only
        {"transform": "sma", "window": 5},  # sma nur für display_only
        {"display_only": True, "info_only": True},
        {"expectation": {"method": "median", "window": 3}},
        {"expectation": {"method": "mean_last", "window": 0}},
    ],
)
def test_config_rejects_invalid_indicator_options(config_data, kw) -> None:
    with pytest.raises(ValidationError):
        Config.model_validate(_with_indicator(config_data, "bad", **kw))


def test_config_accepts_display_only_transforms(config_data) -> None:
    data = _with_indicator(
        config_data, "ok", transform="sma", window=21, display_only=True,
        expectation={"method": "mean_last", "window": 5},
    )  # fmt: skip
    assert Config.model_validate(data).economies["US"].indicators["ok"].window == 21


def test_config_rejects_unknown_scorecard_core_indicator(config_data) -> None:
    data = copy.deepcopy(config_data)
    data["scorecard"]["core"][0]["rows"].append({"key": "gibt_es_nicht", "label": "?"})
    with pytest.raises(ValidationError, match="gibt_es_nicht"):
        Config.model_validate(data)


def test_shipped_config_has_the_14_core_rows(config: Config) -> None:
    groups = {g.key: [r.key for r in g.rows] for g in config.scorecard.core}
    assert groups == {
        "inflation": ["cpi", "ppi", "pce", "yield_2y_sma"],
        "jobs": ["payrolls", "unemployment", "jobless", "adp", "jolts"],
        "growth": ["gdp_qoq", "pmi_manufacturing", "pmi_services", "retail_sales_mom",
                   "consumer_confidence"],
    }  # fmt: skip
    assert sum(len(v) for v in groups.values()) == 14
    us = config.economies["US"].indicators
    for key in ("gdp_qoq", "retail_sales_mom", "yield_2y_sma", "services_philly"):
        assert us[key].display_only


# ------------------------------------------------------------------ Release-Kalender
def _calendar_handler(seen: list[httpx.Request], fail_dates: bool = False):
    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        path = request.url.path
        if path.endswith("/series/release"):
            return httpx.Response(200, content=fixture_bytes("fred_series_release_cpiaucsl.json"))
        if path.endswith("/release/dates"):
            if fail_dates:
                return httpx.Response(500, content=b"{}")
            return httpx.Response(200, content=fixture_bytes("fred_release_dates_10.json"))
        return httpx.Response(200, content=fixture_bytes("fred_gdpc1_current.json"))

    return handler


def _cpi_config(config_data, make_config) -> Config:
    indicators = {
        "US": {
            "indicators": {
                "cpi": _indicator(series="CPIAUCSL", category="inflation", transform="yoy"),
                "yield_10y": _indicator(series="DGS10", category="rates"),
            }
        }
    }
    data = {"economies": economies_with(config_data, indicators)}
    data["scorecard"] = {
        "core": [{"key": "inflation", "label": "I", "category": "inflation",
                  "rows": [{"key": "cpi", "label": "CPI YoY"}]}]
    }  # fmt: skip
    return make_config(**data)


def test_parse_release_helpers() -> None:
    assert parse_release_id({"releases": [{"id": 10}]}) == 10
    assert parse_release_id({}) is None
    payload = {
        "release_dates": [{"date": "2026-12-10"}, {"date": "2026-11-01"}, {"date": "2026-11-24"}]
    }
    assert parse_release_dates(payload, "2026-11-23") == ["2026-11-24", "2026-12-10"]


def test_calendar_series_are_core_fred_series_without_rates(config: Config) -> None:
    series = calendar_series(config)
    assert {"CPIAUCSL", "PAYEMS", "A191RL1Q225SBEA", "GARBNDIF066MSFRBPHI"} <= set(series)
    assert "DGS2" not in series and "FEDFUNDS" not in series


def test_calendar_fetch_stores_future_dates_once_per_day(
    config_data, make_config, secrets, db, clock, monkeypatch
) -> None:
    config = _cpi_config(config_data, make_config)
    seen: list[httpx.Request] = []

    def fetcher() -> FredFetcher:
        return FredFetcher(
            config, secrets, db, client=mock_client(_calendar_handler(seen)),
            sleep=clock.sleep, clock=clock,
        )  # fmt: skip

    result = fetcher().run()
    assert result.status == "success", result.errors
    rows = db.execute(
        "SELECT series_id, release_date FROM macro_release_calendar ORDER BY release_date"
    ).fetchall()
    today = clock().date().isoformat()
    assert [r[0] for r in rows] == ["CPIAUCSL"] * len(rows) and rows
    assert all(r[1] >= today for r in rows)
    calls = [r.url.path for r in seen if "release" in r.url.path]
    assert len(calls) == 2  # series/release + release/dates (CPI), keine Zins-Serie
    seen.clear()
    assert fetcher().run().status == "success"
    assert not [r for r in seen if "release" in r.url.path]  # höchstens 1x täglich je Serie


def test_calendar_error_makes_run_partial_not_failed(
    config_data, make_config, secrets, db, clock
) -> None:
    config = _cpi_config(config_data, make_config)
    fetcher = FredFetcher(
        config, secrets, db, client=mock_client(_calendar_handler([], fail_dates=True)),
        sleep=clock.sleep, clock=clock,
    )  # fmt: skip
    result = fetcher.run()
    assert result.status == "partial"
    assert any("calendar:CPIAUCSL" in e for e in result.errors)
    assert db.execute("SELECT COUNT(*) FROM macro_release_calendar").fetchone()[0] == 0
    assert db.execute("SELECT COUNT(*) FROM macro_observations").fetchone()[0] > 0


def test_migration_0006_on_fresh_and_existing_database(tmp_path: Path) -> None:
    migrate_module = importlib.import_module("edgefinder.db.migrate")

    old = connect(tmp_path / "old.db")
    migrate_dir = tmp_path / "m5"
    migrate_dir.mkdir()
    for path in migrate_module.MIGRATIONS_DIR.glob("000[1-5]_*.sql"):
        (migrate_dir / path.name).write_bytes(path.read_bytes())
    migrate(old, migrate_dir)
    old.execute("INSERT INTO macro_observations VALUES ('fred','X','2026-01-01','',1.0)")
    applied = migrate(old)
    assert [m.version for m in applied] == [6]
    assert old.execute("SELECT COUNT(*) FROM macro_observations").fetchone()[0] == 1
    old.execute(
        "INSERT INTO macro_release_calendar VALUES ('X','2026-12-01','2026-11-23T00:00:00Z')"
    )
    with pytest.raises(sqlite3.IntegrityError):
        old.execute(
            "INSERT INTO macro_release_calendar VALUES ('X','2026-12-01','2026-11-23T00:00:00Z')"
        )
    fresh = connect(tmp_path / "fresh.db")
    migrate(fresh)
    tables = {r[0] for r in fresh.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    assert "macro_release_calendar" in tables


# ------------------------------------------------------------------ Scorecard
def _monthly_obs(db: sqlite3.Connection, series: str, values: list[float]) -> None:
    month = date(TODAY.year, TODAY.month, 1)
    n = len(values)
    for i, value in enumerate(values):
        year, mon = divmod(month.year * 12 + month.month - 1 - (n - 1 - i) - 1, 12)
        db.execute(
            "INSERT OR REPLACE INTO macro_observations (source, series_id, date, vintage_date,"
            " value) VALUES ('fred', ?, ?, '', ?)",
            (series, date(year, mon + 1, 1).isoformat(), value),
        )


def _score_row(db: sqlite3.Connection, asset: str) -> None:
    db.execute(
        "INSERT INTO scores (asset_id, profile, date, score, label, coverage, computed_at)"
        " VALUES (?, 'swing', ?, 1.0, 'Neutral', 0.9, '2026-11-17T10:00:00+00:00')",
        (asset, TODAY.isoformat()),
    )


@pytest.fixture
def seeded(config: Config, db: sqlite3.Connection) -> sqlite3.Connection:
    _score_row(db, "GOLD")
    _score_row(db, "SPX")
    _monthly_obs(db, "GDPC1", [100 + i for i in range(20)])
    _monthly_obs(db, "A191RL1Q225SBEA", [1.0, 2.0, 3.0, 2.0, 1.0, 4.0])
    _monthly_obs(db, "RSAFS", [100.0 + i for i in range(30)])
    _monthly_obs(db, "PAYEMS", [1000.0, 1010.0, 1030.0, 1035.0, 1060.0, 1070.0, 1080.0, 1110.0])
    _monthly_obs(db, "GACDFSA066MSFRBPHI", [10.0, 20.0, 30.0, 6.0])
    _monthly_obs(db, "GACDISA066MSFRBNY", [10.0, 20.0, 30.0, 8.0])
    _monthly_obs(db, "GARBNDIF066MSFRBPHI", [-20.0, -10.0, -30.0])
    _monthly_obs(db, "BACDINA066MNFRBNY", [-10.0, -12.0, -14.0])
    soon = (TODAY + timedelta(days=1)).isoformat()
    later = (TODAY + timedelta(days=9)).isoformat()
    db.executemany(
        "INSERT INTO macro_release_calendar VALUES (?, ?, 'x')",
        [("PAYEMS", later), ("RSAFS", soon), ("BACDINA066MNFRBNY", soon)],
    )
    return db


def _rows(config: Config, db: sqlite3.Connection, asset: str, key: str) -> dict[str, Any]:
    asset_obj = next(a for a in config.assets.all() if a.id == asset)
    card = build_scorecard(config, db, asset_obj, "swing", TODAY)
    section = next(sec for sec in card.sections if sec.key == key)
    return {r.key: r for r in section.rows} | {"_section": section}


def test_core_rows_expectation_surprise_and_order(config: Config, seeded) -> None:
    rows = _rows(config, seeded, "SPX", "core-jobs")
    nfp = rows["US-payrolls"]
    # Änderungen: 10, 20, 5, 25, 10, 10, 30 → Erwartung = Mittel der 6 Änderungen davor
    assert nfp.value == 30.0 and nfp.previous == 10.0 and nfp.change == 20.0
    assert nfp.expectation == pytest.approx(round((10 + 20 + 5 + 25 + 10 + 10) / 6, 4))
    assert nfp.surprise == pytest.approx(round(30 - 80 / 6, 4))
    assert nfp.unit == "k" and nfp.date is not None
    assert nfp.next_date == (TODAY + timedelta(days=9)).isoformat() and nfp.soon is False
    assert next(r.label for r in rows["_section"].rows) == "Non-Farm Payroll"
    assert rows["_section"].kind == "core"


def test_growth_rows_display_only_and_soon_star(config: Config, seeded) -> None:
    rows = _rows(config, seeded, "SPX", "core-growth")
    gdp = rows["US-gdp_qoq"]
    assert gdp.display_only and gdp.value == 4.0 and gdp.previous == 1.0
    assert gdp.expectation == pytest.approx(2.0)  # Mittel der 4 Quartale davor: 2, 3, 2, 1
    retail = rows["US-retail_sales_mom"]
    assert retail.display_only and retail.value == pytest.approx(100 * 1 / 128, abs=1e-3)
    assert retail.soon and retail.next_date == (TODAY + timedelta(days=1)).isoformat()


def test_substitute_pmi_is_mean_with_member_values(config: Config, seeded) -> None:
    rows = _rows(config, seeded, "SPX", "core-growth")
    mfg = rows["US-pmi_manufacturing"]
    assert mfg.substitute and mfg.display_only
    assert mfg.value == pytest.approx(7.0)  # (6 + 8) / 2
    assert mfg.previous == pytest.approx(30.0)
    assert [m.value for m in mfg.members or []] == [6.0, 8.0]
    assert "Philadelphia" in (mfg.members or [])[0].label
    services = rows["US-pmi_services"]
    assert services.value == pytest.approx((-30.0 + -14.0) / 2)  # Texas fehlt: nur 2 Mitglieder
    assert len(services.members or []) == 2
    assert services.soon  # BACDINA066MNFRBNY erscheint morgen
    assert rows["_section"].label == "Economic growth"


def test_sma_row_reports_rising_or_falling(config: Config, db: sqlite3.Connection) -> None:
    _score_row(db, "SPX")
    start = TODAY - timedelta(days=59)
    values = [4.0 + (0.01 * i if i < 40 else 0.4 - 0.02 * (i - 40)) for i in range(60)]
    for i, value in enumerate(values):
        db.execute(
            "INSERT INTO macro_observations VALUES ('fred','DGS2',?, '', ?)",
            ((start + timedelta(days=i)).isoformat(), value),
        )
    rows = _rows(config, db, "SPX", "core-inflation")
    row = rows["US-yield_2y_sma"]
    expected = sum(values[-21:]) / 21
    assert row.value == pytest.approx(expected, abs=1e-3)
    assert row.previous == pytest.approx(sum(values[-42:-21]) / 21, abs=1e-3)
    assert row.text is not None and row.text.startswith("Rendite ")
    assert ("steigt" in row.text) == (row.value > row.previous)  # type: ignore[operator]
    assert row.soon is False and row.next_date is None  # Tageswerte: kein Stern


def test_group_rating_comes_from_group_score(config: Config, seeded) -> None:
    seeded.execute("DELETE FROM score_components")
    sid = seeded.execute("SELECT id FROM scores WHERE asset_id='SPX'").fetchone()[0]
    seeded.execute(
        "INSERT INTO score_components VALUES (?, 'macro', 0.7, 1.0, 1.0, 'x', ?)",
        (sid, '{"growth": {"score": 0.7}, "labor": {"score": -0.7}}'),
    )
    growth = _rows(config, seeded, "SPX", "core-growth")["_section"]
    jobs = _rows(config, seeded, "SPX", "core-jobs")["_section"]
    infl = _rows(config, seeded, "SPX", "core-inflation")["_section"]
    assert (growth.rating, jobs.rating) == ("Stark bullish", "Stark bearish")
    assert infl.rating is None and infl.in_score is False  # Index: Inflation nur Info


def test_gold_flips_rates_pill_and_strips_non_score_groups(config: Config, seeded) -> None:
    jobs = _rows(config, seeded, "GOLD", "core-jobs")
    assert jobs["_section"].in_score is False
    assert all(r.signal is None for r in jobs.values() if hasattr(r, "signal"))


# ------------------------------------------------------------------ Score unverändert
def test_display_only_indicators_never_change_the_score(
    config: Config, config_data, make_config, seeded
) -> None:
    store = DataStore(seeded, config)
    params = {"change_months": 3, "history_years": 10, "max_age_days": 400}
    with_display = store.economy("US", TODAY)
    assert with_display.indicators["gdp_qoq"].info_only  # intern wie info_only behandelt
    stripped = copy.deepcopy(config_data)
    for key in [k for k, v in stripped["economies"]["US"]["indicators"].items()
                if v.get("display_only")]:  # fmt: skip
        del stripped["economies"]["US"]["indicators"][key]
    stripped["scorecard"]["core"] = []
    plain_config = make_config(**{"economies": stripped["economies"], "scorecard": {"core": []}})
    plain = DataStore(seeded, plain_config).economy("US", TODAY)
    for categories in (("growth", "inflation", "labor"), ("growth", "labor")):
        a = macro_f.category_scores(with_display, TODAY, params, categories)
        b = macro_f.category_scores(plain, TODAY, params, categories)
        assert {k: v.score for k, v in a.items()} == {k: v.score for k, v in b.items()}
    assert macro_f.compute_commodity("safe_haven", with_display, TODAY, params).subscore == (
        macro_f.compute_commodity("safe_haven", plain, TODAY, params).subscore
    )
