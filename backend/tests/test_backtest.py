"""Backtest: Forward-Rendite ohne Look-Ahead, Buckets, Kennzahlen (von Hand nachgerechnet)."""

from __future__ import annotations

import json
import math
import sqlite3
import statistics
from datetime import date, timedelta
from pathlib import Path
from typing import Any

import pytest
from test_cli_fetch import cli_env  # noqa: F401
from test_engine import _seed_cot, _seed_prices

from edgefinder import cli
from edgefinder.backtest.analysis import (
    Observation,
    bucket_of,
    buckets_from_labels,
    coverage_by_year,
    forward_returns,
    run_backtest,
    summarize,
)
from edgefinder.backtest.report import render_markdown, write_report
from edgefinder.backtest.stats import ranks, spearman, t_from_corr
from edgefinder.config import Config
from edgefinder.scoring.engine import ScoreEngine


# ---------------------------------------------------------------- Statistik
def test_ranks_average_ties_and_spearman_matches_reference() -> None:
    assert ranks([10, 20, 20, 5]) == [2.0, 3.5, 3.5, 1.0]
    xs, ys = [8, 3, 3, 0, -3, -8], [0.05, 0.02, -0.01, 0.01, -0.02, 0.03]
    expected = statistics.correlation([6, 4.5, 4.5, 3, 2, 1], [6, 4, 2, 3, 1, 5])
    assert spearman(xs, ys) == pytest.approx(expected)
    assert spearman([1, 2, 3, 4], [2, 4, 6, 8]) == pytest.approx(1.0)
    assert spearman([1, 2, 3, 4], [8, 6, 4, 2]) == pytest.approx(-1.0)
    assert spearman([1, 1, 1], [1, 2, 3]) is None  # keine Streuung
    assert spearman([1, 2], [1, 2]) is None  # zu wenig Paare
    assert t_from_corr(0.5, 2) is None
    assert t_from_corr(0.5, 102) == pytest.approx(0.5 * math.sqrt(100 / 0.75))


# ---------------------------------------------------------------- Forward-Rendite
def _series() -> tuple[list[str], list[float]]:
    start = date(2026, 1, 5)  # Montag; nur Werktage
    days, closes, i = [], [], 0
    day = start
    while len(days) < 30:
        if day.weekday() < 5:
            days.append(day.isoformat())
            closes.append(100.0 + i)
            i += 1
        day += timedelta(days=1)
    return days, closes


def test_forward_return_counts_trading_days_from_last_close() -> None:
    dates, closes = _series()
    fr = forward_returns(dates, closes, "2026-01-09", (1, 5))  # Freitag, Index 4 (Kurs 104)
    assert fr[1] == pytest.approx(105 / 104 - 1)
    assert fr[5] == pytest.approx(109 / 104 - 1)
    weekend = forward_returns(dates, closes, "2026-01-11", (5,))  # Sonntag → Freitagskurs
    assert weekend[5] == fr[5]


def test_forward_return_edge_cases() -> None:
    dates, closes = _series()
    assert forward_returns(dates, closes, "2025-12-31", (5,)) == {5: None}  # vor den Kursen
    assert forward_returns(dates, closes, "2026-02-12", (5,))[5] is None  # Fenster ragt hinaus
    assert forward_returns(dates, closes, "2026-02-12", (1,))[1] is not None
    assert forward_returns(dates, closes, "2026-03-30", (1,)) == {1: None}  # Kurs veraltet


def test_forward_return_ignores_data_before_and_never_uses_beyond_horizon() -> None:
    dates, closes = _series()
    base = forward_returns(dates, closes, "2026-01-09", (5,))[5]
    changed = list(closes)
    for i in range(10, len(changed)):  # alles nach Tag h ändern
        changed[i] *= 3
    assert forward_returns(dates, changed, "2026-01-09", (5,))[5] == base


# ---------------------------------------------------------------- Buckets
def test_buckets_follow_config_labels(config: Config) -> None:
    buckets = buckets_from_labels(config.scoring.labels)
    assert [b.label for b in buckets] == [
        "Stark bullish", "Bullish", "Neutral", "Bearish", "Stark bearish"
    ]  # fmt: skip
    assert [b.direction for b in buckets] == [1, 1, 0, -1, -1]
    assert bucket_of(2.0, buckets).label == "Bullish"
    assert bucket_of(1.99, buckets).label == "Neutral"
    assert bucket_of(-2.0, buckets).label == "Neutral"
    assert bucket_of(-2.01, buckets).label == "Bearish"
    assert bucket_of(10, buckets).label == "Stark bullish"
    assert bucket_of(-10, buckets).label == "Stark bearish"


# ---------------------------------------------------------------- Kennzahlen
def _obs(score: float, ret: float | None, day: str = "2026-01-02", asset: str = "A") -> Observation:
    return Observation(asset, "forex", "swing", day, score, 1.0, 0, {5: ret})


def test_summarize_known_example(config: Config) -> None:
    buckets = buckets_from_labels(config.scoring.labels)
    data = [
        _obs(8, 0.05), _obs(3, 0.02), _obs(3, -0.01), _obs(0, 0.01), _obs(-3, -0.02),
        _obs(-8, 0.03), _obs(5, None),
    ]  # fmt: skip
    s = summarize(data, 5, buckets, min_signals=3, step=5)
    assert s["n"] == 6  # Beobachtung ohne Rendite zählt nicht
    assert s["base_up"] == pytest.approx(4 / 6)
    assert s["base_mean"] == pytest.approx((0.05 + 0.02 - 0.01 + 0.01 - 0.02 + 0.03) / 6)
    by = {b["label"]: b for b in s["buckets"]}
    assert by["Stark bullish"]["n"] == 1 and by["Stark bullish"]["hit_rate"] == 1.0
    assert by["Bullish"]["n"] == 2 and by["Bullish"]["hit_rate"] == 0.5
    assert by["Bullish"]["mean"] == pytest.approx(0.005)
    assert by["Neutral"]["hit_rate"] is None and by["Neutral"]["n"] == 1
    assert by["Bearish"]["hit_rate"] == 1.0  # Rendite −2 % bei bearish
    assert by["Stark bearish"]["hit_rate"] == 0.0  # Rendite +3 % bei bearish
    assert s["bullish"]["n"] == 3 and s["bullish"]["mean"] == pytest.approx(0.02)
    assert s["bullish"]["hit_rate"] == pytest.approx(2 / 3)
    assert s["bearish"]["n"] == 2 and s["bearish"]["mean"] == pytest.approx(0.005)
    assert s["bearish"]["hit_rate"] == pytest.approx(0.5)
    assert s["spread"] == pytest.approx(0.015)
    d = s["directional"]
    assert d["n"] == 5 and d["hit_rate"] == pytest.approx(3 / 5)
    assert d["mean_signed"] == pytest.approx((0.05 + 0.02 - 0.01 + 0.02 - 0.03) / 5)
    expected_ic = statistics.correlation([6, 4.5, 4.5, 3, 2, 1], [6, 4, 2, 3, 1, 5])
    assert s["ic"] == pytest.approx(expected_ic)
    assert s["enough"] is True and s["overlap_factor"] == 1.0


def test_summarize_flags_small_samples_and_empty(config: Config) -> None:
    buckets = buckets_from_labels(config.scoring.labels)
    s = summarize([_obs(5, 0.01), _obs(-5, -0.01)], 5, buckets, min_signals=30)
    assert s["enough"] is False and s["directional"]["enough"] is False
    empty = summarize([], 5, buckets, min_signals=30)
    assert empty["n"] == 0 and empty["ic"] is None and empty["spread"] is None
    assert empty["base_up"] is None and empty["directional"]["hit_rate"] is None
    only_bull = summarize([_obs(5, 0.01)] * 4, 5, buckets, min_signals=1)
    assert only_bull["spread"] is None  # ohne bearishe Seite kein Spread
    assert only_bull["ic"] is None  # keine Streuung


def test_summarize_overlap_reduces_effective_sample(config: Config) -> None:
    buckets = buckets_from_labels(config.scoring.labels)
    data = [_obs(i - 10, (i - 10) / 100) for i in range(20)]
    short = summarize(data, 5, buckets, min_signals=1, step=5)
    data60 = [
        Observation("A", "forex", "swing", "d", o.score, 1, 0, {60: o.forward[5]}) for o in data
    ]
    long = summarize(data60, 60, buckets, min_signals=1, step=5)
    assert short["n_eff"] == 20.0
    assert long["n_eff"] == pytest.approx(20 / 12, abs=0.1)
    assert long["overlap_factor"] == 12.0


def test_cross_section_ic_needs_five_assets(config: Config) -> None:
    buckets = buckets_from_labels(config.scoring.labels)
    day1 = [_obs(s, r, "2026-01-02", f"A{i}") for i, (s, r) in enumerate(
        [(1, 0.01), (2, 0.02), (3, 0.03), (4, 0.04), (5, 0.05)])]  # fmt: skip
    day2 = [_obs(s, r, "2026-01-09", f"A{i}") for i, (s, r) in enumerate(
        [(1, 0.05), (2, 0.04), (3, 0.03), (4, 0.02), (5, 0.01)])]  # fmt: skip
    thin = [_obs(1, 0.1, "2026-01-16", "A0"), _obs(2, 0.2, "2026-01-16", "A1")]
    s = summarize(day1 + day2 + thin, 5, buckets, min_signals=1)
    assert s["ic_cs_dates"] == 2  # der Tag mit 2 Assets zählt nicht
    assert s["ic_cs"] == pytest.approx(0.0)  # +1 und −1


# ---------------------------------------------------------------- Look-Ahead im Score
def test_score_ignores_future_data(config: Config, db: sqlite3.Connection) -> None:
    for asset, drift in (("EURGBP", 0.002),):
        _seed_prices(db, asset, date(2025, 1, 1), date(2026, 11, 17), drift)
    _seed_cot(db, "099741", +1)
    _seed_cot(db, "096742", -1)
    as_of = date(2026, 6, 5)
    full = ScoreEngine(config, db).score_asset(config.assets_by_id["EURGBP"], "swing", as_of)
    db.execute("DELETE FROM prices WHERE date > ?", (as_of.isoformat(),))
    db.execute("DELETE FROM cot_reports WHERE report_date > ?", ((as_of).isoformat(),))
    cut = ScoreEngine(config, db).score_asset(config.assets_by_id["EURGBP"], "swing", as_of)
    assert full is not None and cut is not None
    assert cut.score == pytest.approx(full.score)
    assert {c.factor: c.subscore for c in cut.components} == {
        c.factor: c.subscore for c in full.components
    }


# ---------------------------------------------------------------- Gesamtlauf
def _seed_history(db: sqlite3.Connection, *, predictive: bool) -> None:
    """Kurs mit wechselnden Phasen; Score = Vorzeichen der Phase (vorausschauend oder verkehrt)."""
    start = date(2024, 1, 1)
    rows, closes, day, i = [], [], start, 0
    price = 100.0
    while day < date(2025, 7, 1):
        if day.weekday() < 5:
            phase = (i // 10) % 2  # 10 Handelstage steigend, 10 fallend
            price *= 1.004 if phase == 0 else 0.996
            rows.append(("EURUSD", day.isoformat(), price))
            closes.append(price)
            i += 1
        day += timedelta(days=1)
    db.executemany("INSERT INTO prices (asset_id, date, close) VALUES (?, ?, ?)", rows)
    score_rows = []
    for idx in range(0, len(rows) - 10, 5):  # Stichtag alle 5 Handelstage
        d = rows[idx][1]
        future_up = closes[idx + 5] > closes[idx]
        up = future_up if predictive else not future_up
        score_rows.append(("EURUSD", "swing", d, 5.0 if up else -5.0, "x", 0.8, "backfill", "t"))
    db.executemany(
        "INSERT INTO scores (asset_id, profile, date, score, label, coverage, origin, computed_at)"
        " VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        score_rows,
    )
    db.execute(
        "INSERT INTO score_components SELECT id, 'trend', CASE WHEN score > 0 THEN 0.5 ELSE -0.5"
        " END, 0.3, 0.3, '', '{}' FROM scores"
    )


@pytest.mark.parametrize(("predictive", "sign"), [(True, 1), (False, -1)])
def test_run_backtest_end_to_end(
    config: Config, db: sqlite3.Connection, predictive: bool, sign: int
) -> None:
    _seed_history(db, predictive=predictive)
    result = run_backtest(db, config, profiles=("swing",), horizon_days=5)
    assert result["scores"] > 50
    forex = next(g for g in result["groups"] if g["asset_class"] == "forex")
    assert forex["horizon"] == 5 and forex["primary"]
    assert sign * forex["ic"] > 0.7
    assert forex["directional"]["hit_rate"] == pytest.approx(1.0 if predictive else 0.0)
    assert sign * forex["spread"] > 0
    pooled = result["groups"][-1]
    assert pooled["asset_class"] == "all" and pooled["ic"] == pytest.approx(forex["ic"])
    trend = next(f for f in result["factors"] if f["factor"] == "trend")
    assert sign * trend["ic"] > 0.7 and trend["availability"] == 1.0
    assert result["coverage"][0]["mean_coverage"] == pytest.approx(0.8)
    assert {y["year"] for y in result["yearly"]} == {"2024", "2025"}


def test_run_backtest_filters_and_unknown_assets(config: Config, db: sqlite3.Connection) -> None:
    _seed_history(db, predictive=True)
    db.execute(
        "INSERT INTO scores (asset_id, profile, date, score, label, coverage, origin, computed_at)"
        " VALUES ('GONE', 'swing', '2024-02-02', 5, 'x', 1, 'backfill', 't')"
    )  # Asset nicht mehr in config.yaml → ignoriert
    assert run_backtest(db, config, classes=("stock",))["scores"] == 0
    full = run_backtest(db, config, profiles=("swing",))
    assert full["horizons"] == {"swing": [5, 10, 20]}
    later = run_backtest(db, config, profiles=("swing",), since="2025-01-01")
    assert later["first_date"] >= "2025-01-01" and later["scores"] < full["scores"]
    # letzte Stichtage ohne volles Fenster: n sinkt mit dem Horizont
    n = {g["horizon"]: g["n"] for g in full["groups"] if g["asset_class"] == "forex"}
    assert n[5] >= n[10] > n[20] > 0


def test_coverage_by_year(config: Config, db: sqlite3.Connection) -> None:
    _seed_history(db, predictive=True)
    obs_result = run_backtest(db, config, profiles=("swing",))
    assert all(0 < c["mean_coverage"] <= 1 for c in obs_result["coverage"])
    assert obs_result["coverage"][0]["factors"] == {"trend": 1.0}
    assert coverage_by_year(db, []) == []


# ---------------------------------------------------------------- Report und CLI
def test_report_rendering(config: Config, db: sqlite3.Connection, tmp_path: Path) -> None:
    _seed_history(db, predictive=True)
    result = run_backtest(db, config, profiles=("swing",))
    text = render_markdown(result)
    headings = ["# Backtest-Report", "## Überblick", "Überlappung/Autokorrelation", "## Faktoren"]
    headings += ["## Stabilität nach Jahr", "## Abdeckung je Zeitraum"]
    for heading in headings:
        assert heading in text
    assert "⚠" in text  # kleine Stichproben markiert
    assert "Stark bullish" in text and "Trend" in text
    paths = write_report(result, tmp_path / "out")
    assert json.loads(paths["json"].read_text())["scores"] == result["scores"]
    assert paths["markdown"].read_text().startswith("# Backtest-Report")
    custom = write_report(result, tmp_path / "out", tmp_path / "docs" / "r.md")
    assert custom["markdown"].exists()


@pytest.fixture
def bt_dir(config_data: dict[str, Any], tmp_path: Path) -> Path:
    config_data["backtest"]["output_dir"] = str(tmp_path / "bt")
    return tmp_path / "bt"


def test_backtest_command(bt_dir: Path, cli_env: Path) -> None:  # noqa: F811
    assert cli.main(["migrate"]) == 0
    assert cli.main(["backtest"]) == 1  # noch keine Scores
    conn = sqlite3.connect(cli_env)
    _seed_history(conn, predictive=True)
    conn.commit()
    conn.close()
    assert (
        cli.main(["backtest", "--profile", "swing", "--class", "forex", "--horizon-days", "5"]) == 0
    )
    assert (bt_dir / "backtest.json").exists() and (bt_dir / "backtest-report.md").exists()
    assert cli.main(["backtest", "--profile", "nope"]) == 2
    assert cli.main(["backtest", "--class", "nope"]) == 2
    assert cli.main(["backtest", "--horizon-days", "0"]) == 2
