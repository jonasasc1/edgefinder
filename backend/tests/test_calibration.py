"""Eichung: Kennzahlen von Hand nachgerechnet, Evidenzregeln inkl. Grenzfälle, kein Look-ahead,
Datei, API und Faktor-Übereinstimmung."""

from __future__ import annotations

import json
import sqlite3
from datetime import date, timedelta
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from test_cli_fetch import cli_env  # noqa: F401

from edgefinder import cli
from edgefinder.api.app import create_app
from edgefinder.backtest import calibration as cal
from edgefinder.config import CalibrationConfig, Config
from edgefinder.scoring.agreement import agreement

RULES = CalibrationConfig()  # Standardwerte = config.yaml (min_t 2, n_eff 30/10, floor 5)


def _cell(n_eff: float, edge: float | None, t: float | None = 3.0, hit=0.6, base_hit=0.5):
    return {"n_eff": n_eff, "edge": edge, "t": t, "hit": hit, "base_hit": base_hit}


def _cells(total, train, oos):
    return {"all": total, "train": train, "oos": oos}


# ---------------------------------------------------------------- Kennzahlen
def test_cell_matches_hand_calculation() -> None:
    rows = [(0.02, 1), (-0.01, 1), (0.03, 1), (0.00, 1)]  # bullish; Basis: Ø 0,01, 50 % steigend
    out = cal.cell(rows, 0.01, 0.5, overlap=2.0, z=1.96)
    assert out["n"] == 4 and out["n_eff"] == 2.0
    assert out["mean"] == pytest.approx(0.01) and out["median"] == pytest.approx(0.01)
    assert out["hit"] == 0.5  # 0.02 und 0.03 steigen
    assert out["edge"] == pytest.approx(0.0)
    # bearish: Rendite −0,02 bei Basis 0,01 → Vorteil in Signalrichtung +0,03
    bear = cal.cell([(-0.02, -1)], 0.01, 0.6, overlap=1.0, z=1.96)
    assert bear["edge"] == pytest.approx(0.03) and bear["hit"] == 1.0
    assert bear["base_hit"] == pytest.approx(0.4)  # Basis fallend = 1 − 0,6
    # Konfidenzband: Ø ± z · sd · √(overlap/n)
    sd = 0.0182574  # Stichproben-Std. von 0.02, −0.01, 0.03, 0.0
    se = sd * (2.0 / 4) ** 0.5
    assert out["ci"][0] == pytest.approx(0.01 - 1.96 * se, abs=2e-5)
    assert out["ci"][1] == pytest.approx(0.01 + 1.96 * se, abs=2e-5)


def test_cell_neutral_has_no_direction_and_empty_is_small() -> None:
    out = cal.cell([(0.01, 0), (-0.01, 0), (0.02, 0)], 0.0, 0.5, 1.0, 1.96)
    assert out["hit"] is None and out["base_hit"] is None
    assert cal.cell([], 0.0, 0.5, 1.0, 1.96) == {"n": 0, "n_eff": 0.0}


def test_mixed_directions_use_signal_direction() -> None:
    out = cal.cell([(0.02, 1), (-0.02, -1)], 0.0, 0.5, 1.0, 1.96)
    assert out["mean"] == pytest.approx(0.02)  # Short-Gewinn zählt positiv
    assert out["hit"] == 1.0


# ---------------------------------------------------------------- Evidenzregeln
def test_evidence_proven() -> None:
    ok = _cells(_cell(100, 0.01), _cell(50, 0.01), _cell(50, 0.01))
    assert cal.evidence(ok, 1, RULES) == cal.BELEGT


@pytest.mark.parametrize(
    ("change", "expected"),
    [
        ({"all": _cell(100, 0.01, t=1.99)}, cal.SCHWACH),  # t knapp unter 2
        ({"all": _cell(100, 0.01, t=2.0)}, cal.BELEGT),  # Grenze zählt
        ({"all": _cell(29.9, 0.01)}, cal.SCHWACH),  # n_eff knapp unter 30
        ({"all": _cell(30, 0.01)}, cal.BELEGT),
        ({"train": _cell(9.9, 0.01)}, cal.SCHWACH),  # Zeitraum zu klein für „belegt“
        ({"oos": _cell(10, 0.01)}, cal.BELEGT),
        ({"all": _cell(100, 0.01, hit=0.5, base_hit=0.5)}, cal.SCHWACH),  # Treffer nicht über Basis
        ({"oos": _cell(50, -0.001)}, cal.KEIN_VORTEIL),  # Vorzeichen wechselt
        ({"train": _cell(50, 0.0)}, cal.KEIN_VORTEIL),  # exakt null
        ({"all": _cell(100, -0.01, t=-4)}, cal.KEIN_VORTEIL),  # falsch herum
        ({"oos": _cell(4.9, 0.01)}, cal.ZU_WENIG),  # unter Untergrenze
        ({"oos": _cell(5, 0.01)}, cal.SCHWACH),
        ({"oos": {"n": 0, "n_eff": 0.0}}, cal.ZU_WENIG),  # Zeitraum ohne Daten
    ],
)
def test_evidence_borderlines(change: dict, expected: str) -> None:
    cells = _cells(_cell(100, 0.01), _cell(50, 0.01), _cell(50, 0.01))
    cells.update(change)
    assert cal.evidence(cells, 1, RULES) == expected


def test_evidence_neutral_and_agreement_min_t() -> None:
    ok = _cells(_cell(100, 0.01, t=2.5), _cell(50, 0.01), _cell(50, 0.01))
    assert cal.evidence(ok, 0, RULES) == cal.NEUTRAL  # keine Richtungsaussage
    assert cal.evidence(ok, 1, RULES) == cal.BELEGT
    assert cal.evidence(ok, 1, RULES, min_t=2.7) == cal.SCHWACH  # strengere Übereinstimmungs-Regel


def test_config_rules_validate() -> None:
    with pytest.raises(ValueError, match="floor_n_eff"):
        CalibrationConfig(floor_n_eff=20, min_n_eff_period=10)


# ---------------------------------------------------------------- synthetische Historie
def _seed(db: sqlite3.Connection, *, predictive: bool, asset: str = "EURUSD") -> None:
    """Freitags-Scores 2018–2022; Rendite der folgenden 5 Handelstage = ±1 % (+ kleines Rauschen),
    Vorzeichen = Score (vorausschauend) oder umgekehrt. Zwischentage: linear interpoliert."""
    fridays, day = [], date(2018, 1, 5)
    while day <= date(2022, 12, 30):
        fridays.append(day)
        day += timedelta(days=7)
    price, price_rows, score_rows = 100.0, [], []
    for i, friday in enumerate(fridays):
        score = (4.0, -4.0, 0.0, 4.0, -4.0, 4.0, 0.0)[i % 7]
        sign = (1 if score >= 0 else -1) * (1 if predictive else -1)
        r = (0.01 + 0.002 * ((i * 7) % 5 - 2) / 2) * sign if score else 0.0
        price_rows.append((asset, friday.isoformat(), price))
        for k in range(1, 5):  # Mo–Do
            step = friday + timedelta(days=3 + k - 1)
            price_rows.append((asset, step.isoformat(), price * (1 + r) ** (k / 5)))
        label = "Bullish" if score > 0 else ("Bearish" if score < 0 else "Neutral")
        score_rows.append((asset, "swing", friday.isoformat(), score, label, 1.0, "backfill", "t"))
        price *= 1 + r
    db.executemany("INSERT INTO prices (asset_id, date, close) VALUES (?, ?, ?)", price_rows)
    db.executemany(
        "INSERT INTO scores (asset_id, profile, date, score, label, coverage, origin, computed_at)"
        " VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        score_rows,
    )
    db.execute(
        "INSERT INTO score_components SELECT id, 'trend', CASE WHEN score > 0 THEN 0.5"
        " WHEN score < 0 THEN -0.5 ELSE 0 END, 1, 1, '', '{}' FROM scores"
        " WHERE asset_id = ?",
        (asset,),
    )


def _forex(data: dict[str, Any]) -> dict[str, Any]:
    return data["classes"]["swing"]["forex"]


def test_known_result_predictive(config: Config, db: sqlite3.Connection) -> None:
    _seed(db, predictive=True)
    data = cal.build_calibration(db, config)
    h5 = _forex(data)["5"]
    bull = h5["Bullish"]["all"]
    assert bull["hit"] == 1.0 and bull["up"] == 1.0
    assert 0.009 < bull["mean"] < 0.011 and bull["edge"] > 0.008
    assert bull["n"] > 100 and bull["n_eff"] == bull["n"]  # Horizont 5 = Stichtag-Abstand
    bear = h5["Bearish"]["all"]
    assert bear["hit"] == 1.0 and bear["mean"] < -0.009 and bear["edge"] > 0.008
    assert h5["Bullish"]["evidence"] == cal.BELEGT
    assert h5["directional"]["evidence"] == cal.BELEGT
    assert h5["Neutral"]["evidence"] == cal.NEUTRAL and h5["Neutral"]["all"]["hit"] is None
    assert h5["Stark bullish"]["evidence"] == cal.ZU_WENIG  # nie vorgekommen
    # Training und OOS getrennt nach Stichtag
    train, oos = h5["Bullish"]["train"], h5["Bullish"]["oos"]
    assert train["n"] + oos["n"] == bull["n"] and train["n"] > 30 and oos["n"] > 30
    assert data["params"]["primary_horizon"] == {"swing": 10, "long_term": 60}
    assert data["summary"]["swing"]["forex"]["horizon"] == 10


def test_known_result_reversed_has_no_edge(config: Config, db: sqlite3.Connection) -> None:
    _seed(db, predictive=False)
    h5 = _forex(cal.build_calibration(db, config))["5"]
    assert h5["Bullish"]["all"]["hit"] == 0.0
    assert h5["Bullish"]["evidence"] == cal.KEIN_VORTEIL
    assert h5["directional"]["evidence"] == cal.KEIN_VORTEIL


def test_train_cell_ignores_later_prices(config: Config, db: sqlite3.Connection) -> None:
    """Look-ahead: Kurse nach dem Training verändern die Training-Zelle nicht (Zuordnung nach
    Stichtag, Forward-Fenster ab Stichtag)."""
    _seed(db, predictive=True)
    before = _forex(cal.build_calibration(db, config))["5"]["Bullish"]["train"]
    db.execute("DELETE FROM prices WHERE date > '2020-06-30'")
    after = _forex(cal.build_calibration(db, config))["5"]["Bullish"]
    assert after["train"] == before
    assert after["oos"]["n"] < _forex(cal.build_calibration(db, config))["5"]["Bullish"]["all"]["n"]


def test_window_beyond_last_price_is_dropped(config: Config, db: sqlite3.Connection) -> None:
    _seed(db, predictive=True)
    full = _forex(cal.build_calibration(db, config))
    assert full["20"]["directional"]["all"]["n"] < full["5"]["directional"]["all"]["n"]
    assert full["20"]["directional"]["all"]["n_eff"] == pytest.approx(
        full["20"]["directional"]["all"]["n"] / 4, abs=0.1
    )


def test_split_by_signal_day(config_data: dict, make_config) -> None:
    config_data["backtest"]["calibration"]["train_end"] = "2019-12-31"
    cfg = make_config(backtest=config_data["backtest"])
    assert cfg.backtest.calibration.train_end == date(2019, 12, 31)
    obs = [
        (type("O", (), {"day": d})(), 0.0, 1) for d in ("2019-12-27", "2019-12-31", "2020-01-03")
    ]
    parts = cal._split(obs, "2019-12-31")
    assert len(parts["train"]) == 2 and len(parts["oos"]) == 1


def test_asset_level_needs_enough_data(config: Config, db: sqlite3.Connection) -> None:
    _seed(db, predictive=True)
    data = cal.build_calibration(db, config)
    assets = data["assets"]["swing"]["EURUSD"]
    assert "Bullish" in assets and set(assets["Bullish"]) == {"all", "train", "oos"}
    assert "Stark bullish" not in assets  # n_eff < 30 → „zu wenig Daten“ (Eintrag fehlt)


def test_deterministic_and_small_file(
    config: Config, db: sqlite3.Connection, tmp_path: Path
) -> None:
    _seed(db, predictive=True)
    from datetime import UTC, datetime

    now = datetime(2026, 11, 21, tzinfo=UTC)
    a = cal.build_calibration(db, config, now=now)
    b = cal.build_calibration(db, config, now=now)
    p1, p2 = tmp_path / "a.json", tmp_path / "b.json"
    cal.write_calibration(a, p1)
    cal.write_calibration(b, p2)
    assert p1.read_bytes() == p2.read_bytes()
    assert p1.stat().st_size < 500_000
    assert cal.load_calibration(p1)["generated_at"] == "2026-11-21"
    assert cal.load_calibration(tmp_path / "fehlt.json") is None
    (tmp_path / "kaputt.json").write_text("{", encoding="utf-8")
    assert cal.load_calibration(tmp_path / "kaputt.json") is None


def test_agreement_blocks_and_markdown(
    config: Config, db: sqlite3.Connection, tmp_path: Path
) -> None:
    _seed(db, predictive=True)
    data = cal.build_calibration(db, config)
    block = data["agreement"]["swing"]["forex"]
    assert block["threshold"] == 0.7
    assert block["high"]["all"]["n"] > 0  # Faktor trend stimmt mit dem Score überein
    assert block["low"]["all"]["n"] == 0
    labels = {"swing": "Swing", "long_term": "Langfristig"}
    md = cal.render_markdown(data, labels, {"forex": "Forex"})
    assert "Kalibrierung" in md and "belegt" in md and "Faktor-Übereinstimmung" in md
    report = tmp_path / "report.md"
    report.write_text("# Report\n\nText\n", encoding="utf-8")
    cal.update_report(report, md)
    cal.update_report(report, md + "\nzweiter Lauf\n")  # ersetzt statt anhängen
    text = report.read_text(encoding="utf-8")
    assert (
        text.count(cal.MARK_START) == 1 and "zweiter Lauf" in text and text.startswith("# Report")
    )


def test_cli_calibrate(cli_env: Path, tmp_path: Path) -> None:  # noqa: F811
    assert cli.main(["migrate"]) == 0
    assert cli.main(["calibrate", "--out", str(tmp_path / "x.json")]) == 1  # noch keine Scores
    conn = sqlite3.connect(cli_env)
    conn.execute("PRAGMA foreign_keys = ON")
    _seed(conn, predictive=True)
    conn.commit()
    conn.close()
    out, report = tmp_path / "cal.json", tmp_path / "r.md"
    assert cli.main(["calibrate", "--out", str(out), "--report", str(report)]) == 0
    assert json.loads(out.read_text(encoding="utf-8"))["version"] == cal.VERSION
    assert cal.MARK_START in report.read_text(encoding="utf-8")


# ---------------------------------------------------------------- Faktor-Übereinstimmung
def test_agreement_counts_and_weights() -> None:
    items = [(0.5, 0.4), (0.3, 0.2), (-0.4, 0.2), (0.05, 0.1), (None, 0.1)]
    a = agreement(items, 3.0, 0.15)
    assert a["total"] == 4 and a["bullish"] == 2 and a["bearish"] == 1 and a["neutral"] == 1
    assert a["same"] == 2 and a["weight_share"] == pytest.approx(0.6 / 0.9)
    b = agreement(items, -3.0, 0.15)
    assert b["same"] == 1 and b["weight_share"] == pytest.approx(0.2 / 0.9)
    assert agreement(items, 0.0, 0.15)["weight_share"] is None
    assert agreement([(None, 1.0)], 1.0, 0.15) is None
    assert agreement([(0.15, 1.0)], 1.0, 0.15)["bullish"] == 1  # Grenze zählt als Signal


# ---------------------------------------------------------------- API
@pytest.fixture
def client(config: Config, tmp_path: Path, db: sqlite3.Connection) -> TestClient:
    _seed(db, predictive=True, asset="EURUSD")
    _seed(db, predictive=False, asset="SPX")
    cfg = config.model_copy(
        update={
            "backtest": config.backtest.model_copy(
                update={"calibration_file": tmp_path / "cal.json"}
            )
        }
    )
    cal.write_calibration(cal.build_calibration(db, cfg), cfg.backtest.calibration_file)
    return TestClient(create_app(cfg, frontend_dist=None))


def test_api_asset_calibration(client: TestClient) -> None:
    body = client.get("/api/assets/EURUSD/calibration?profile=swing").json()
    assert body["available"] and body["asset_class"] == "forex" and body["horizon"] == 10
    assert body["bucket"]["direction"] in (-1, 0, 1)
    assert body["evidence"] in {"belegt", "schwach", "kein_vorteil", "zu_wenig_daten", "neutral"}
    assert body["note"] and body["train_end"] == "2019-12-31" and body["data_through"]
    assert len(body["chart"]) == 5 and body["horizons"] == [5, 10, 20]
    assert set(body["stats"]) == {"all", "train", "oos"}
    assert body["asset_status"] in ("ok", "zu_wenig_daten")


def test_api_no_edge_class_and_summary(client: TestClient) -> None:
    summary = client.get("/api/calibration/summary").json()
    assert summary["available"] and "swing" in summary["profiles"]
    assert summary["profiles"]["swing"]["forex"]["evidence"] in {
        "belegt",
        "schwach",
        "kein_vorteil",
        "zu_wenig_daten",
    }
    assert summary["profiles"]["swing"]["index"]["horizon"] == 10


def test_scorecard_counter_trend_and_agreement(client: TestClient, db: sqlite3.Connection) -> None:
    last = db.execute("SELECT max(id) FROM scores WHERE asset_id = 'SPX'").fetchone()[0]
    db.execute(
        "UPDATE score_components SET inputs = ? WHERE score_id = ?", ('{"mode": "reversal"}', last)
    )
    db.execute("UPDATE score_components SET subscore = 0.5 WHERE score_id = ?", (last,))
    db.execute("UPDATE scores SET score = 5 WHERE id = ?", (last,))
    body = client.get("/api/assets/SPX/scorecard?profile=swing").json()
    trend = next(r for sec in body["sections"] for r in sec["rows"] if r["key"] == "trend")
    assert trend["counter_trend"] is True
    assert body["agreement"]["total"] == 1 and body["agreement"]["same"] == 1
    assert body["agreement"]["weight_share"] == 1.0 and body["agreement"]["high"] is True
    eurusd = client.get("/api/assets/EURUSD/scorecard?profile=swing").json()
    row = next(r for sec in eurusd["sections"] for r in sec["rows"] if r["key"] == "trend")
    assert row["counter_trend"] is False  # kein Umkehr-Modus (Forex)


def test_api_errors_and_missing_file(client: TestClient, config: Config, db) -> None:
    assert client.get("/api/assets/EURUSD/calibration?profile=nope").status_code == 422
    assert client.get("/api/assets/XXX/calibration").status_code == 404
    assert client.get("/api/assets/AAPL/calibration").status_code == 404  # noch kein Score
    # ohne Datei: kein Fehler, nur „nicht verfügbar“
    missing = config.backtest.model_copy(update={"calibration_file": Path("/nonexistent/cal.json")})
    other = TestClient(
        create_app(config.model_copy(update={"backtest": missing}), frontend_dist=None)
    )
    note = other.get("/api/assets/EURUSD/calibration").json()
    assert note["available"] is False and note["note"] == "missing" and note["evidence"] is None
    assert other.get("/api/calibration/summary").json() == {
        "available": False,
        "generated_at": None,
        "first_date": None,
        "data_through": None,
        "train_end": None,
        "min_t": None,
        "min_n_eff": None,
        "profiles": {},
    }
