"""Live-Bilanz: Auswertung, Gruppen-Kennzahlen, Drift-Status, Faktor-Drift (synthetische Daten)."""
# ruff: noqa: E501

from __future__ import annotations

import sqlite3
from datetime import UTC, date, datetime, timedelta

import pytest

from edgefinder.backtest import live
from edgefinder.config import Config
from edgefinder.scoring.engine import AssetScore, Component, ScoreEngine

NOW = datetime(2026, 12, 31, tzinfo=UTC)


def _bdays(start: date, end: date) -> list[date]:
    out, day = [], start
    while day <= end:
        if day.weekday() < 5:
            out.append(day)
        day += timedelta(days=1)
    return out


def _prices(db, asset: str, start: date, end: date, daily: float = 0.001) -> list[date]:
    days = _bdays(start, end)
    for i, day in enumerate(days):
        db.execute(
            "INSERT INTO prices (asset_id, date, close) VALUES (?, ?, ?)",
            (asset, day.isoformat(), 100 * (1 + daily) ** i),
        )
    return days


def _score(db, asset, profile, day: date, score, label="Bullish", origin="live", version=None):
    return db.execute(
        "INSERT INTO scores (asset_id, profile, date, score, label, coverage, origin, computed_at,"
        " model_version) VALUES (?, ?, ?, ?, ?, 1.0, ?, 'x', ?) RETURNING id",
        (asset, profile, day.isoformat(), score, label, origin, version),
    ).fetchone()[0]


def _outcomes(db, asset="EURUSD", profile="swing"):
    return db.execute(
        "SELECT * FROM signal_outcomes WHERE asset_id = ? AND profile = ?"
        " ORDER BY signal_date, horizon_days",
        (asset, profile),
    ).fetchall()


# ------------------------------------------------------------------ evaluate
def test_evaluate_horizon_boundaries_and_idempotence(config: Config, db: sqlite3.Connection):
    signal = date(2026, 11, 6)  # Freitag
    days = _prices(db, "EURUSD", date(2026, 10, 1), date(2026, 11, 20))
    _score(db, "EURUSD", "swing", signal, 4.0)
    result = live.evaluate(db, config, now=NOW)
    rows = _outcomes(db)
    # Horizonte swing: 5, 10, 20. Nach 11-06 gibt es 10 Handelstage bis 11-20, nicht 20.
    assert [r["horizon_days"] for r in rows] == [5, 10]
    idx = days.index(signal)
    for r in rows:
        assert r["entry_date"] == "2026-11-06"
        assert r["exit_date"] == days[idx + r["horizon_days"]].isoformat()
        assert r["forward_return_pct"] == pytest.approx(
            ((1.001) ** r["horizon_days"] - 1) * 100, abs=1e-3
        )
        assert (r["direction"], r["hit"], r["model_version"]) == (
            "bullish",
            1,
            config.scoring.model_version,
        )
    assert (result.created, result.open) == (2, 1)
    # idempotent
    again = live.evaluate(db, config, now=NOW)
    assert (again.created, again.open) == (0, 1)
    assert len(_outcomes(db)) == 2
    # später kommen Kurse dazu: nur der neue Horizont wird ergänzt, alte Zeilen bleiben unverändert
    before = [tuple(r) for r in rows]
    for day in _bdays(date(2026, 11, 21), date(2026, 12, 10)):
        db.execute(
            "INSERT INTO prices (asset_id, date, close) VALUES ('EURUSD', ?, 50)",
            (day.isoformat(),),
        )
    live.evaluate(db, config, now=NOW)
    after = _outcomes(db)
    assert [r["horizon_days"] for r in after] == [5, 10, 20]
    assert [tuple(r) for r in after[:2]] == before


def test_evaluate_direction_neutral_bearish_and_backfill_ignored(config, db):
    _prices(db, "EURUSD", date(2026, 10, 1), date(2026, 11, 20), daily=-0.002)
    _score(db, "EURUSD", "swing", date(2026, 11, 2), 0.5, "Neutral")
    _score(db, "EURUSD", "swing", date(2026, 11, 3), -4.0, "Bearish")
    _score(db, "EURUSD", "swing", date(2026, 11, 4), 4.0, "Bullish")
    _score(db, "EURUSD", "swing", date(2026, 11, 5), 4.0, "Bullish", origin="backfill")
    live.evaluate(db, config, now=NOW)
    by_day = {r["signal_date"]: r for r in _outcomes(db) if r["horizon_days"] == 5}
    assert by_day["2026-11-02"]["direction"] == "neutral" and by_day["2026-11-02"]["hit"] is None
    assert by_day["2026-11-02"]["forward_return_pct"] < 0  # Rendite wird trotzdem gespeichert
    assert by_day["2026-11-03"]["hit"] == 1  # bearish, Kurs fällt
    assert by_day["2026-11-04"]["hit"] == 0  # bullish, Kurs fällt
    assert "2026-11-05" not in by_day  # Backfill ist kein Live-Signal


def test_evaluate_without_prices_and_without_lookahead(config, db):
    # Kurse enden am Signaltag: nichts auswertbar (kein Look-ahead, nichts erfunden)
    _prices(db, "EURUSD", date(2026, 10, 1), date(2026, 11, 6))
    _score(db, "EURUSD", "swing", date(2026, 11, 6), 4.0)
    # Einstiegskurs > 7 Tage vor dem Signal: gar nicht auswertbar
    _score(db, "GOLD", "swing", date(2026, 11, 6), 4.0)
    db.execute("INSERT INTO prices (asset_id, date, close) VALUES ('GOLD', '2026-10-01', 10)")
    result = live.evaluate(db, config, now=NOW)
    assert result.created == 0 and result.open == 3 and result.unpriced == 3
    assert db.execute("SELECT COUNT(*) FROM signal_outcomes").fetchone()[0] == 0


def test_evaluate_no_gap_interpolation(config, db):
    # Fehlende Handelstage in der Reihe werden nicht aufgefüllt: Horizont zählt vorhandene Kurse
    days = _bdays(date(2026, 10, 1), date(2026, 11, 20))
    skipped = date(2026, 11, 9)
    for i, day in enumerate(days):
        if day != skipped:
            db.execute(
                "INSERT INTO prices (asset_id, date, close) VALUES ('EURUSD', ?, ?)",
                (day.isoformat(), 100 + i),
            )
    _score(db, "EURUSD", "swing", date(2026, 11, 6), 4.0)
    live.evaluate(db, config, now=NOW)
    five = next(r for r in _outcomes(db) if r["horizon_days"] == 5)
    assert five["exit_date"] == "2026-11-16"  # 5 vorhandene Kurse später (9.11. fehlt)


def test_model_version_is_separated(config, db):
    _prices(db, "EURUSD", date(2026, 10, 1), date(2026, 11, 20))
    _score(db, "EURUSD", "swing", date(2026, 11, 2), 4.0, version="alt")
    _score(db, "EURUSD", "swing", date(2026, 11, 3), 4.0, version=config.scoring.model_version)
    live.evaluate(db, config, now=NOW)
    versions = {r["signal_date"]: r["model_version"] for r in _outcomes(db)}
    assert versions == {"2026-11-02": "alt", "2026-11-03": config.scoring.model_version}
    report = live.build_trackrecord(db, config, None, today=date(2026, 11, 21))
    assert report["evaluated"] == 1  # nur der aktuelle Modellstand zählt in der Bilanz


def test_persist_never_overwrites_live_rows(config, db):
    engine = ScoreEngine(config, db)
    comp = (Component("trend", 0.5, 1.0, 1.0, "r"),)
    day = date(2026, 11, 6)
    engine.persist(AssetScore("EURUSD", "swing", day, 5.0, "Bullish", 1.0, comp), "live")
    engine.persist(
        AssetScore("EURUSD", "swing", day, -5.0, "Bearish", 1.0, comp), "backfill", detail=False
    )
    row = db.execute("SELECT score, origin, model_version FROM scores").fetchone()
    assert tuple(row) == (5.0, "live", config.scoring.model_version)
    assert db.execute("SELECT COUNT(*) FROM score_components").fetchone()[0] == 1


# ------------------------------------------------------------------ Drift-Status
def _cell(n_eff=40.0, edge=0.01, t=3.0):
    return {"n": 80, "n_eff": n_eff, "edge": edge, "t": t}


CAL = {"edge": 0.02, "edge_se": 0.002}  # Band 0,0161 … 0,0239


@pytest.mark.parametrize(
    ("live_cell", "weeks", "expected"),
    [
        (_cell(n_eff=3), 20, "zu_frueh"),  # n_eff zu klein
        (_cell(), 3, "zu_frueh"),  # zu wenige Wochen
        (_cell(edge=0.02), 20, "im_rahmen"),
        (_cell(edge=0.01), 20, "schwaecher"),
        (_cell(edge=0.03), 20, "besser"),
        (_cell(edge=-0.01, t=-2.5), 20, "gegenlaeufig"),
        (
            _cell(edge=-0.01, t=-1.0),
            20,
            "schwaecher",
        ),  # falsches Vorzeichen, aber nicht signifikant
    ],
)
def test_drift_status(config, live_cell, weeks, expected):
    assert live.drift_status(live_cell, CAL, weeks, config) == expected


def test_drift_status_without_calibration(config):
    assert live.drift_status(_cell(), None, 20, config) == "ohne_eichung"
    assert live.drift_status(_cell(n_eff=1), None, 20, config) == "zu_frueh"


# ------------------------------------------------------------------ Gruppen/Faktoren
def _insert_outcome(db, asset, klass, day, score, ret_pct, h=10, profile="swing"):
    label = "Bullish" if score >= 2 else "Bearish" if score <= -2 else "Neutral"
    direction = "bullish" if score >= 2 else "bearish" if score <= -2 else "neutral"
    hit = None if direction == "neutral" else int((ret_pct > 0) == (direction == "bullish"))
    db.execute(
        "INSERT INTO signal_outcomes (asset_id, profile, signal_date, asset_class, score, label,"
        " direction, model_version, horizon_days, entry_date, entry_price, exit_date, exit_price,"
        " forward_return_pct, hit, evaluated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 100, ?, 100, ?, ?, 'x')",
        (asset, profile, day, klass, score, label, direction, "2026-11-21", h, day,
         (date.fromisoformat(day) + timedelta(days=14)).isoformat(), ret_pct, hit),
    )  # fmt: skip


def _fridays(n: int) -> list[date]:
    start = date(2026, 1, 2)
    return [start + timedelta(weeks=i) for i in range(n)]


def _fill_forex(db, sign: float, weeks: int = 40):
    """Je Woche bullish (+), bearish (−) und neutral; `sign` = +1: Signale treffen, −1: Gegenteil."""
    for i, friday in enumerate(_fridays(weeks)):
        noise = 0.2 * ((i % 5) - 2)
        day = friday.isoformat()
        _insert_outcome(db, "EURUSD", "forex", day, 4.0, sign * 1.0 + noise)
        _insert_outcome(db, "GBPUSD", "forex", day, -4.0, -sign * 1.0 + noise)
        _insert_outcome(db, "USDJPY", "forex", day, 0.0, 0.0 + noise / 2)


def _forex_group(report):
    return next(
        g for g in report["groups"] if g["profile"] == "swing" and g["asset_class"] == "forex"
    )


CAL_FILE = {
    "generated_at": "2026-11-21",
    "classes": {
        "swing": {"forex": {"10": {"directional": {"all": {"edge": 0.01, "edge_se": 0.002}}}}}
    },
}


def test_group_counter_signal(config, db):
    _fill_forex(db, -1)
    g = _forex_group(live.build_trackrecord(db, config, CAL_FILE, today=date(2026, 11, 21)))
    assert g["status"] == "gegenlaeufig" and g["edge"] < 0 and g["t"] < -2
    assert g["hit"] == 0.0 and g["n"] == 80 and g["weeks"] == 40  # neutral zählt nicht zu n
    assert g["n_eff"] == 40.0  # 80 ÷ Überlappung (10 Tage ÷ 5)


def test_group_hit_and_edge_against_calibration(config, db):
    _fill_forex(db, 1)
    g = _forex_group(live.build_trackrecord(db, config, CAL_FILE, today=date(2026, 11, 21)))
    assert g["hit"] == 1.0 and g["edge"] == pytest.approx(0.01, abs=2e-3)
    assert (
        g["status"] == "im_rahmen" and g["cal_edge_ci"][0] < g["edge"] < g["cal_edge_ci"][1] + 0.001
    )
    assert (
        g["progress"] > 0.5
    )  # n_eff 40 ≥ 30, aber erst 40 Wochen/~9 Monate: Kriterien bald erfüllt


def test_group_too_early_and_only_weekly_signals_count(config, db):
    _fill_forex(db, 1, weeks=3)
    # tägliche Signale (Montag) dürfen die Kennzahlen nicht aufblähen
    for friday in _fridays(3):
        _insert_outcome(db, "EURUSD", "forex", (friday + timedelta(days=3)).isoformat(), 4.0, 5.0)
    g = _forex_group(live.build_trackrecord(db, config, CAL_FILE, today=date(2026, 11, 21)))
    assert g["status"] == "zu_frueh" and g["n"] == 6 and g["weeks"] == 3
    assert g["calibrated"] is False


def test_factor_drift_counter_and_warning(config, db):
    assets = ["EURUSD", "GBPUSD", "USDJPY", "USDCHF", "AUDUSD", "USDCAD"]
    for week, friday in enumerate(_fridays(12)):
        for k, asset in enumerate(assets):
            sub = (k - 2.5) / 3 + 0.01 * week  # Rangfolge je Woche gleich
            sid = _score(db, asset, "swing", friday, 3.0, version="2026-11-21")
            db.execute(
                "INSERT INTO score_components VALUES (?, 'trend', ?, 1, 1, '', '{}')", (sid, sub)
            )
            noise = 0.4 * ((week * 7 + k * 3) % 5 - 2)  # Gegenteil des Backtests, mit Rauschen
            _insert_outcome(db, asset, "forex", friday.isoformat(), 3.0, -sub * 5 + noise)
    cal = {"factor_ic": {"swing": {"forex": {"trend": {"ic": 0.1, "ic_t": 2.0, "n": 900}}}}}
    factors = live.build_factor_drift(db, config, cal, "2026-11-21")
    trend = next(f for f in factors if f["factor"] == "trend")
    assert trend["status"] == "gegenlaeufig" and trend["ic"] < -0.9 and trend["weeks_against"] == 12
    assert trend["warn"] is True
    # ohne Backtest-Referenz: kein Vergleich, keine Warnung
    other = live.build_factor_drift(db, config, {}, "2026-11-21")[0]
    assert other["status"] == "kein_vergleich" and other["warn"] is False


def test_factor_drift_too_early(config, db):
    sid = _score(db, "EURUSD", "swing", date(2026, 11, 6), 3.0, version="2026-11-21")
    db.execute("INSERT INTO score_components VALUES (?, 'trend', 0.3, 1, 1, '', '{}')", (sid,))
    _insert_outcome(db, "EURUSD", "forex", "2026-11-06", 3.0, 1.0)
    assert live.build_factor_drift(db, config, {}, "2026-11-21")[0]["status"] == "zu_frueh"


def test_trackrecord_header_numbers_when_empty(config, db):
    for offset in (0, 1):
        _score(db, "EURUSD", "swing", date(2026, 11, 18) + timedelta(days=offset), 3.0)
    report = live.build_trackrecord(db, config, None, today=date(2026, 11, 21))
    assert report["live_since"] == "2026-11-18" and report["evaluated"] == 0 and report["open"] == 2
    assert report["earliest_due"] == "2026-12-02"  # 18.11. + 10 Werktage (Kennwert-Horizont swing)
    assert all(g["status"] == "zu_frueh" for g in report["groups"])
    assert report["progress"] == 0.0 and report["calibrated_groups"] == 0
