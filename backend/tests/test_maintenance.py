"""Wartungszyklus (Backfill, Eichung, Drift-Bericht), CLI-Befehle und Bilanz-API."""

from __future__ import annotations

import json
import sqlite3
from datetime import UTC, date, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from test_live import _bdays, _prices, _score

from edgefinder import cli, maintenance
from edgefinder.api.app import create_app
from edgefinder.config import Config
from edgefinder.db import connect


def _backfill_scores(db, weeks: int = 60) -> None:
    """Wöchentliche Backfill-Scores mit Kursen (EURUSD, GOLD) – genug für die Eichung."""
    start = date(2025, 1, 3)
    for asset, daily in (("EURUSD", 0.0004), ("GOLD", -0.0003)):
        _prices(db, asset, date(2024, 12, 1), date(2026, 11, 20), daily)
    for i in range(weeks):
        day = start + timedelta(weeks=i)
        for asset in ("EURUSD", "GOLD"):
            for profile in ("swing", "long_term"):
                _score(
                    db,
                    asset,
                    profile,
                    day,
                    4.0 if i % 2 else -4.0,
                    origin="backfill",
                    version="2026-11-21",
                )


def test_missing_dates_only_missing_fridays(config: Config, db: sqlite3.Connection):
    today = date(2026, 11, 21)
    all_days = maintenance.missing_dates(db, config, today)
    assert all(d.weekday() == 4 and d < today for d in all_days)
    assert all_days[0] >= config.backtest.start
    _score(db, "EURUSD", "swing", date(2026, 11, 13), 1.0, origin="backfill")
    after = maintenance.missing_dates(db, config, today)
    assert date(2026, 11, 13) not in after and len(after) == len(all_days) - 1
    assert today not in after  # heute ist „live“, kein Backfill


def test_backfill_rebuild_on_new_model_version(config, db, monkeypatch):
    monkeypatch.setattr(maintenance, "missing_dates", lambda *_: [])
    _score(db, "EURUSD", "swing", date(2026, 11, 6), 1.0, origin="backfill", version="alt")
    live_id = _score(db, "EURUSD", "swing", date(2026, 11, 18), 1.0, origin="live", version="alt")
    assert maintenance.stale_backfill(db, config) == 1
    maintenance.backfill(db, config, today=date(2026, 11, 21))
    left = db.execute("SELECT id, origin FROM scores").fetchall()
    assert [(r["id"], r["origin"]) for r in left] == [
        (live_id, "live")
    ]  # Backfill neu, Live bleibt


def test_backfill_computes_missing_days_in_blocks(config, db, monkeypatch):
    calls: list[date] = []

    class FakeEngine:
        def __init__(self, *_): ...

        def run_day(self, day, *_a, **_k):
            calls.append(day)
            return [object()]

    monkeypatch.setattr("edgefinder.scoring.engine.ScoreEngine", FakeEngine)
    monkeypatch.setattr(
        maintenance, "missing_dates", lambda *_: [date(2025, 12, 26), date(2026, 1, 2)]
    )
    assert maintenance.backfill(db, config, today=date(2026, 11, 21)) == 2
    assert calls == [date(2025, 12, 26), date(2026, 1, 2)]


def test_run_maintain_writes_files_and_records_run(config, db, monkeypatch):
    monkeypatch.setattr(maintenance, "backfill", lambda *_a, **_k: 7)
    _backfill_scores(db)
    run = maintenance.run_maintain(db, config, today=date(2026, 11, 21))
    assert run.errors == [] and run.items == 7
    cal = json.loads((config.data_dir / "calibration.json").read_text())
    assert cal["version"] == 1 and "factor_ic" in cal and cal["scores"] > 0
    report = json.loads((config.data_dir / "drift-report.json").read_text())
    assert report["model_version"] == config.scoring.model_version and len(report["groups"]) == 8
    review = (config.data_dir / "review.md").read_text()
    assert "Modellpflege-Vorlage" in review and "empfiehlt nichts" in review
    row = db.execute("SELECT status, items FROM fetch_runs WHERE source = 'maintain'").fetchone()
    assert (row["status"], row["items"]) == ("success", 7)
    # Die API liest zuerst die Datei im Datenverzeichnis
    assert maintenance.calibration_paths(config)[0] == config.data_dir / "calibration.json"
    assert maintenance.load_current_calibration(config)["generated_at"] == cal["generated_at"]


def test_run_maintain_errors_are_recorded_not_raised(config, db, monkeypatch):
    def boom(*_a, **_k):
        raise RuntimeError("kaputt")

    monkeypatch.setattr(maintenance, "backfill", boom)
    run = maintenance.run_maintain(
        db, config, today=date(2026, 11, 21)
    )  # keine Scores: auch Eichung leer
    assert any(e.startswith("Backfill: RuntimeError") for e in run.errors)
    assert any("Eichung" in e for e in run.errors)
    row = db.execute("SELECT status, error FROM fetch_runs WHERE source = 'maintain'").fetchone()
    assert row["status"] == "error" and "kaputt" in row["error"]
    assert (config.data_dir / "drift-report.json").exists()  # Bericht trotz Fehlern


def test_calibration_excludes_live_rows(config, db):
    """Die Eichung stammt nur aus dem Backfill: Live-Signale bleiben der unabhängige Test."""
    from edgefinder.backtest import calibration

    _backfill_scores(db, weeks=20)
    _score(db, "EURUSD", "swing", date(2025, 11, 7), 4.0, origin="live")  # eigener Tag
    data = calibration.build_calibration(db, config)
    assert data["scores"] == 20 * 2 * 2


def test_cli_evaluate_and_maintain_commands(config, db, monkeypatch, capsys):
    _prices(db, "EURUSD", date(2026, 10, 1), date(2026, 11, 20))
    _score(db, "EURUSD", "swing", date(2026, 11, 6), 4.0)
    monkeypatch.setattr(cli, "load_config", lambda: config)
    assert cli.main(["evaluate"]) == 0
    conn = connect(config.storage.database)
    assert conn.execute("SELECT COUNT(*) FROM signal_outcomes").fetchone()[0] == 2
    assert conn.execute(
        "SELECT status, items FROM fetch_runs WHERE source = 'evaluate'"
    ).fetchone()[:] == ("success", 2)
    conn.close()
    out = config.data_dir / "review-x.md"
    assert cli.main(["review-report", "--out", str(out)]) == 0
    assert out.read_text().startswith("# Modellpflege-Vorlage")


# ------------------------------------------------------------------ API
@pytest.fixture
def client(config: Config, db: sqlite3.Connection) -> TestClient:
    today = datetime.now(UTC).date()
    days = _bdays(today - timedelta(days=60), today)
    for i, day in enumerate(days):
        db.execute(
            "INSERT INTO prices (asset_id, date, close) VALUES ('EURUSD', ?, ?)",
            (day.isoformat(), 100 + i * 0.1),
        )
    old, recent = days[-18], days[-3]
    _score(db, "EURUSD", "swing", old, 4.0, "Bullish")
    _score(db, "EURUSD", "swing", recent, -4.0, "Bearish")
    maintenance.run_evaluate(db, config)
    return TestClient(create_app(config, frontend_dist=None))


def test_trackrecord_endpoint_contract(client: TestClient, config: Config):
    body = client.get("/api/trackrecord", params={"profile": "swing"}).json()
    assert body["model_version"] == config.scoring.model_version
    assert body["evaluated"] == 1 and body["open"] == 1
    assert {g["profile"] for g in body["groups"]} == {"swing"} and len(body["groups"]) == 4
    assert all(g["status"] == "zu_frueh" for g in body["groups"])
    assert body["criteria"]["min_weeks"] == config.live.done.min_weeks
    both = client.get("/api/trackrecord").json()
    assert {g["profile"] for g in both["groups"]} == set(config.profiles)
    assert client.get("/api/trackrecord", params={"profile": "nein"}).status_code == 422


def test_asset_trackrecord_endpoint(client: TestClient):
    body = client.get("/api/assets/EURUSD/trackrecord", params={"profile": "swing"}).json()
    assert body["asset_id"] == "EURUSD" and body["class_status"] == "zu_frueh"
    assert body["evaluated"] == 1 and body["open"] == 1 and body["primary_horizon"] == 10
    newest, oldest = body["signals"]  # neueste zuerst
    assert newest["direction"] == "bearish" and {h["status"] for h in newest["horizons"]} == {
        "laeuft"
    }
    assert all(h["due_date"] for h in newest["horizons"])
    done = {h["horizon_days"]: h for h in oldest["horizons"]}
    assert (
        done[5]["status"] == "ausgewertet" and done[5]["hit"] is True and done[5]["return_pct"] > 0
    )
    assert done[20]["status"] == "laeuft"
    assert client.get("/api/assets/NOPE/trackrecord").status_code == 404
    assert client.get("/api/assets/EURUSD/trackrecord", params={"profile": "x"}).status_code == 422


def test_status_lists_maintenance_jobs(client: TestClient, db, config):
    sources = {s["source"]: s for s in client.get("/api/status").json()["sources"]}
    assert (
        sources["evaluate"]["last_run_status"] == "success"
        and sources["evaluate"]["stale"] is False
    )
    assert sources["maintain"]["stale"] is True and sources["maintain"]["last_run_status"] is None
    assert sources["maintain"]["stale_after_hours"] == config.maintenance.maintain_stale_after_hours


def test_existing_contracts_unchanged(client: TestClient):
    assert client.get("/api/profiles").status_code == 200
    assert "groups" not in client.get("/api/calibration/summary").json()
