"""Score-Engine: Gewichtung, Renormierung, Labels, Look-Ahead, Idempotenz, Cross-Forex."""

from __future__ import annotations

import math
import sqlite3
from datetime import date, timedelta

import pytest

from edgefinder.config import Config
from edgefinder.scoring.data import DataStore
from edgefinder.scoring.engine import ScoreEngine, combine
from edgefinder.scoring.factors import FactorResult, unavailable
from edgefinder.scoring.labels import label_for

EUR, GBP = "099741", "096742"  # CFTC-Codes aus config.yaml


def _fr(score: float | None) -> FactorResult:
    return FactorResult(score, "x") if score is not None else unavailable("fehlt")


def test_combine_renormalizes_missing_factors() -> None:
    weights = {"a": 0.5, "b": 0.3, "c": 0.2}
    score, coverage, comps = combine(weights, {"a": _fr(0.8), "b": _fr(None), "c": _fr(-0.2)})
    assert coverage == pytest.approx(0.7)
    assert score == pytest.approx(10 * (0.8 * 0.5 / 0.7 + -0.2 * 0.2 / 0.7))
    by_name = {c.factor: c for c in comps}
    assert by_name["b"].subscore is None
    assert by_name["b"].effective_weight == 0.0
    assert sum(c.effective_weight for c in comps) == pytest.approx(1.0)


def test_combine_bounds_and_empty() -> None:
    score, coverage, _ = combine({"a": 1.0}, {"a": _fr(1.0)})
    assert score == 10.0
    assert coverage == 1.0
    assert combine({"a": 0.6, "b": 0.4}, {"a": _fr(None), "b": _fr(None)}) is None
    low, _, _ = combine({"a": 0.5, "b": 0.5}, {"a": _fr(-1.0), "b": _fr(-1.0)})
    assert low == -10.0


@pytest.mark.parametrize(
    ("score", "label"),
    [
        (10, "Stark bullish"),
        (6.0, "Stark bullish"),
        (5.99, "Bullish"),
        (2.0, "Bullish"),
        (1.99, "Neutral"),
        (0, "Neutral"),
        (-2.0, "Neutral"),
        (-2.01, "Bearish"),
        (-6.0, "Bearish"),
        (-6.01, "Stark bearish"),
        (-10, "Stark bearish"),
    ],
)
def test_labels_from_config(config: Config, score: float, label: str) -> None:
    assert label_for(score, config.scoring) == label


# ---------------------------------------------------------------- Testdaten
def _seed_prices(db: sqlite3.Connection, asset_id: str, start: date, end: date, drift: float):
    rows, day, i = [], start, 0
    while day <= end:
        rows.append((asset_id, day.isoformat(), 100 * math.exp(drift * i + 0.004 * math.sin(i))))
        day += timedelta(days=1)
        i += 1
    db.executemany("INSERT INTO prices (asset_id, date, close) VALUES (?, ?, ?)", rows)


def _seed_cot(db: sqlite3.Connection, code: str, sign: int, last: date = date(2026, 11, 10)):
    weeks = 120
    rows = []
    for i in range(weeks):
        report = last - timedelta(weeks=weeks - 1 - i)
        rows.append((code, report.isoformat(), 1000, sign * 10 * i * i, 0))
    db.executemany(
        "INSERT INTO cot_reports (contract_code, report_date, open_interest, noncomm_long,"
        " noncomm_short) VALUES (?, ?, ?, ?, ?)",
        [(c, d, oi, max(n, 0), max(-n, 0)) for c, d, oi, n, _ in rows],
    )


@pytest.fixture
def seeded(db: sqlite3.Connection) -> sqlite3.Connection:
    for asset, drift in (("EURGBP", 0.002), ("EURUSD", -0.002)):
        _seed_prices(db, asset, date(2025, 1, 1), date(2026, 11, 17), drift)
    _seed_cot(db, EUR, +1)
    _seed_cot(db, GBP, -1)
    return db


def test_forex_cross_derives_cot_from_both_currencies(config: Config, seeded) -> None:
    engine = ScoreEngine(config, seeded)
    asset = config.assets_by_id["EURGBP"]
    result = engine.score_asset(asset, "swing", date(2026, 11, 13))
    cot = next(c for c in result.components if c.factor == "cot")
    assert cot.inputs["EUR"]["subscore"] > 0
    assert cot.inputs["GBP"]["subscore"] < 0
    # Differenz/2 statt Differenz: dämpft die Sättigung bei ±1
    expected = (cot.inputs["EUR"]["subscore"] - cot.inputs["GBP"]["subscore"]) / 2
    assert cot.subscore == pytest.approx(expected, abs=1e-3)
    assert abs(cot.subscore) < abs(cot.inputs["EUR"]["subscore"] - cot.inputs["GBP"]["subscore"])
    assert "/ 2" in cot.reason
    assert "," in cot.reason  # deutsches Dezimalzeichen
    assert "EUR" in cot.reason
    assert "GBP" in cot.reason


def test_forex_cross_without_one_currency_drops_cot(config: Config, seeded) -> None:
    # EURUSD: für USD (098662) gibt es im Testdatensatz keinen COT → Faktor entfällt
    engine = ScoreEngine(config, seeded)
    result = engine.score_asset(config.assets_by_id["EURUSD"], "swing", date(2026, 11, 13))
    cot = next(c for c in result.components if c.factor == "cot")
    assert cot.subscore is None
    assert cot.effective_weight == 0.0
    assert result.coverage < 1.0
    assert sum(c.effective_weight for c in result.components) == pytest.approx(1.0)


def test_no_prices_means_no_score(config: Config, db: sqlite3.Connection) -> None:
    engine = ScoreEngine(config, db)
    assert engine.score_asset(config.assets_by_id["EURGBP"], "swing", date(2026, 11, 13)) is None
    assert engine.run_day(date(2026, 11, 13), ["EURGBP"]) == []


# ---------------------------------------------------------------- Look-Ahead
def test_cot_visible_only_from_release_friday(config: Config, seeded) -> None:
    store = DataStore(seeded, config)
    # Bericht vom Dienstag 2026-11-10, Veröffentlichung Freitag 2026-11-13
    assert store.cot(EUR, date(2026, 11, 12))[-1].report_date == "2026-11-03"
    assert store.cot(EUR, date(2026, 11, 13))[-1].report_date == "2026-11-10"


def test_future_data_does_not_change_past_score(config: Config, seeded) -> None:
    as_of = date(2026, 9, 30)
    before = ScoreEngine(config, seeded).score_asset(
        config.assets_by_id["EURGBP"], "long_term", as_of
    )
    # extreme Kurse und COT nach dem Stichtag dürfen nichts verändern
    seeded.execute("UPDATE prices SET close = close * 50 WHERE date > ?", (as_of.isoformat(),))
    seeded.execute("UPDATE cot_reports SET noncomm_long = 0 WHERE report_date > '2026-09-25'")
    after = ScoreEngine(config, seeded).score_asset(
        config.assets_by_id["EURGBP"], "long_term", as_of
    )
    assert before is not None
    assert after is not None
    assert after.score == pytest.approx(before.score)
    assert [c.subscore for c in after.components] == [c.subscore for c in before.components]


def test_macro_uses_vintage_published_by_as_of(config: Config, db: sqlite3.Connection) -> None:
    db.executemany(
        "INSERT INTO macro_observations (source, series_id, date, vintage_date, value)"
        " VALUES ('fred', 'UNRATE', ?, ?, ?)",
        [
            ("2026-01-01", "", 4.5),  # aktueller (revidierter) Stand
            ("2026-01-01", "2026-02-06", 4.0),  # Erstveröffentlichung
            ("2026-01-01", "2026-03-06", 4.5),  # Revision
            ("2026-02-01", "", 4.6),  # nie mit Vintage veröffentlicht vor dem Stichtag
            ("2026-02-01", "2026-03-06", 4.6),
        ],
    )
    store = DataStore(db, config)
    assert store.macro_series("fred", "UNRATE", date(2026, 2, 1)) == []
    assert store.macro_series("fred", "UNRATE", date(2026, 2, 10)) == [("2026-01-01", 4.0)]
    assert store.macro_series("fred", "UNRATE", date(2026, 3, 10)) == [
        ("2026-01-01", 4.5),
        ("2026-02-01", 4.6),
    ]


def test_macro_without_vintages_uses_publication_lag(
    config: Config, db: sqlite3.Connection
) -> None:
    db.executemany(
        "INSERT INTO macro_observations (source, series_id, date, vintage_date, value)"
        " VALUES ('ecb', 'S', ?, '', ?)",
        [(f"2025-{m:02d}-01", float(m)) for m in range(1, 13)],
    )
    store = DataStore(db, config)
    visible = store.macro_series("ecb", "S", date(2025, 6, 1))
    assert visible[-1][0] == "2025-04-01"  # Monatswerte: ca. 50 Tage Verzögerung
    assert store.macro_series("ecb", "S", date(2030, 1, 1))[-1][0] == "2025-12-01"


def test_other_sources_respect_publication_dates(config: Config, db: sqlite3.Connection) -> None:
    db.execute("INSERT INTO aaii_sentiment VALUES ('2026-11-11', 30, 20, 50, 'x')")
    db.execute("INSERT INTO short_interest VALUES ('AAPL', '2026-10-30', 1e6, 1e7, 2.0)")
    db.execute("INSERT INTO earnings VALUES ('AAPL', '2026-11-02', 1.9, 2.1, 10.5)")
    db.execute("INSERT INTO earnings VALUES ('AAPL', '2027-01-28', 2.9, NULL, NULL)")
    store = DataStore(db, config)
    assert store.aaii(date(2026, 11, 11)) == []
    assert len(store.aaii(date(2026, 11, 12))) == 1
    assert store.short_interest("AAPL", date(2026, 11, 9)) == []
    assert len(store.short_interest("AAPL", date(2026, 11, 10))) == 1
    assert store.earnings("AAPL", date(2026, 11, 1)) == []
    assert store.earnings("AAPL", date(2026, 12, 1)) == [("2026-11-02", 10.5)]


# ---------------------------------------------------------------- Persistenz
def _count(db: sqlite3.Connection, table: str) -> int:
    return db.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]  # noqa: S608 (nur Testtabellen)


def test_persist_is_idempotent_and_updates(config: Config, seeded) -> None:
    engine = ScoreEngine(config, seeded)
    day = date(2026, 11, 13)
    first = engine.run_day(day, ["EURGBP"])
    scores, components = _count(seeded, "scores"), _count(seeded, "score_components")
    assert scores == 2  # zwei Profile
    assert components == 10  # 5 Faktoren × 2 Profile
    engine.run_day(day, ["EURGBP"])
    assert _count(seeded, "scores") == scores
    assert _count(seeded, "score_components") == components
    row = seeded.execute(
        "SELECT score, label, coverage, origin FROM scores WHERE profile = 'swing'"
    ).fetchone()
    swing = next(r for r in first if r.profile == "swing")
    assert row["score"] == pytest.approx(swing.score)
    assert -10 <= row["score"] <= 10
    assert row["label"] == swing.label
    assert row["origin"] == "backfill"
    reasons = seeded.execute("SELECT reason, inputs FROM score_components").fetchall()
    assert all(r["reason"] and r["inputs"].startswith("{") for r in reasons)


def test_run_range_skips_weekends(config: Config, seeded) -> None:
    engine = ScoreEngine(config, seeded)
    count = engine.run_range(date(2026, 11, 9), date(2026, 11, 15), ["EURGBP"])  # Mo–So
    assert count == 5 * 2
    dates = {r[0] for r in seeded.execute("SELECT date FROM scores")}
    assert "2026-11-14" not in dates
    assert "2026-11-13" in dates


def test_failing_factor_becomes_unavailable(config: Config, seeded, monkeypatch) -> None:
    from edgefinder.scoring.factors import trend

    def boom(*args, **kwargs):
        raise RuntimeError("kaputt")

    monkeypatch.setattr(trend, "compute", boom)
    result = ScoreEngine(config, seeded).score_asset(
        config.assets_by_id["EURGBP"], "swing", date(2026, 11, 13)
    )
    comp = next(c for c in result.components if c.factor == "trend")
    assert comp.subscore is None
