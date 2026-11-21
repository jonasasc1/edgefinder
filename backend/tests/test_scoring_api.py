"""API-Endpunkte der Etappe d (TestClient, synthetische Daten)."""

from __future__ import annotations

import json
import sqlite3
from datetime import UTC, date, datetime, timedelta

import pytest
from fastapi.testclient import TestClient

from edgefinder.api.app import create_app
from edgefinder.config import Config

TODAY = datetime.now(UTC).date()


def _score(db, asset, profile, day: date, score: float, label: str, factors=()):
    cur = db.execute(
        "INSERT INTO scores (asset_id, profile, date, score, label, coverage, computed_at)"
        " VALUES (?, ?, ?, ?, ?, 0.8, ?) RETURNING id",
        (asset, profile, day.isoformat(), score, label, "2026-11-17T10:00:00+00:00"),
    )
    sid = cur.fetchone()[0]
    for factor, sub, weight in factors:
        db.execute(
            "INSERT INTO score_components VALUES (?, ?, ?, ?, ?, ?, ?)",
            (sid, factor, sub, weight, weight, f"Begründung {factor}", json.dumps({"x": 1})),
        )


@pytest.fixture
def client(config: Config, db: sqlite3.Connection) -> TestClient:
    for i in range(10):
        day = TODAY - timedelta(days=9 - i)
        _score(db, "EURUSD", "swing", day, -2.0 + i * 0.5, "Neutral")
        _score(db, "EURUSD", "long_term", day, 1.0, "Neutral")
        db.execute(
            "INSERT INTO prices (asset_id, date, close) VALUES ('EURUSD', ?, ?)",
            (day.isoformat(), 1.1 + i / 100),
        )
    _score(db, "GOLD", "swing", TODAY - timedelta(days=1), 1.5, "Neutral", [("cot", 0.5, 1.0)])
    _score(db, "GOLD", "swing", TODAY, 2.5, "Bullish", [("cot", 0.6, 0.6), ("trend", None, 0.0)])
    db.execute(
        "INSERT INTO cot_reports (contract_code, report_date, open_interest, noncomm_long,"
        " noncomm_short) VALUES ('099741', '2026-11-10', 1000, 300, 100)"
    )
    db.execute("INSERT INTO aaii_sentiment VALUES ('2026-11-11', 30, 20, 50, 'x')")
    db.execute(
        "INSERT INTO retail_sentiment (source, symbol, observed_at, long_pct, short_pct)"
        " VALUES ('myfxbook', 'EURUSD', ?, 70, 30)",
        (datetime.now(UTC).isoformat(timespec="seconds"),),
    )
    db.execute(
        "INSERT INTO fetch_runs (source, started_at, finished_at, status) VALUES"
        " ('cftc', ?, ?, 'success')",
        (
            (datetime.now(UTC) - timedelta(hours=1)).isoformat(),
            (datetime.now(UTC) - timedelta(hours=1)).isoformat(),
        ),
    )
    db.execute(
        "INSERT INTO fetch_runs (source, started_at, finished_at, status, error) VALUES"
        " ('fred', '2020-01-01T00:00:00+00:00', '2020-01-01T00:01:00+00:00', 'success', NULL)"
    )
    db.execute(
        "INSERT INTO fetch_runs (source, started_at, finished_at, status, error) VALUES"
        " ('prices', ?, ?, 'error', 'kaputt')",
        (datetime.now(UTC).isoformat(), datetime.now(UTC).isoformat()),
    )
    db.execute("INSERT INTO earnings VALUES ('AAPL', '2026-11-02', 1.9, 2.1, 10.5)")
    db.execute(
        "INSERT INTO fundamentals VALUES ('AAPL', 'us-gaap:Revenues', 'USD', '2025-01-01',"
        " '2025-12-31', 2025, 'FY', '10-K', '2026-02-01', 100.0)"
    )
    return TestClient(create_app(config, frontend_dist=None))


def test_profiles(client: TestClient) -> None:
    body = client.get("/api/profiles").json()
    assert [p["key"] for p in body] == ["swing", "long_term"]
    assert body[0]["label"] == "Swing"


def test_assets_list_with_changes(client: TestClient) -> None:
    body = client.get("/api/assets").json()
    by_id = {a["id"]: a for a in body}
    assert len(body) == len({a["id"] for a in body}) > 30
    eurusd = by_id["EURUSD"]["scores"]
    assert eurusd["swing"]["score"] == 2.5
    assert eurusd["swing"]["change_1d"] == 0.5
    assert eurusd["swing"]["change_7d"] == 3.5
    assert eurusd["long_term"]["change_1d"] == 0.0
    assert by_id["GOLD"]["scores"]["swing"]["change_1d"] == 1.0
    assert by_id["GOLD"]["scores"]["swing"]["change_7d"] is None  # keine Historie
    assert by_id["GOLD"]["scores"]["long_term"] is None
    assert by_id["AAPL"]["scores"] == {"swing": None, "long_term": None}


def test_assets_empty_database(config: Config, db: sqlite3.Connection) -> None:
    body = TestClient(create_app(config, frontend_dist=None)).get("/api/assets").json()
    assert all(a["scores"]["swing"] is None for a in body)


def test_sparklines_bulk(client: TestClient) -> None:
    body = client.get("/api/sparklines?days=5&profile=swing").json()
    assert body["profile"] == "swing" and body["days"] == 5
    eur = body["series"]["EURUSD"]
    assert 5 <= len(eur) <= 6  # Stichtag minus 5 Tage bis heute
    assert eur == sorted(eur) and eur[-1] == [TODAY.isoformat(), 2.5]
    assert [d for d, _ in body["series"]["GOLD"]] == [
        (TODAY - timedelta(days=1)).isoformat(),
        TODAY.isoformat(),
    ]
    assert "SPX" not in body["series"]  # Assets ohne Score fehlen
    assert client.get("/api/sparklines?profile=nope").status_code == 422
    assert client.get("/api/sparklines?days=1").status_code == 422


def test_sparklines_empty_database(config: Config, db: sqlite3.Connection) -> None:
    body = TestClient(create_app(config, frontend_dist=None)).get("/api/sparklines").json()
    assert body["series"] == {}


def test_asset_detail(client: TestClient) -> None:
    body = client.get("/api/assets/GOLD").json()
    swing = body["profiles"]["swing"]
    assert swing["score"]["label"] == "Bullish"
    assert [c["factor"] for c in swing["components"]] == ["cot", "trend"]
    assert swing["components"][0]["reason"] == "Begründung cot"
    assert swing["components"][0]["inputs"] == {"x": 1}
    assert swing["components"][1]["subscore"] is None
    assert body["profiles"]["long_term"] is None
    eur = client.get("/api/assets/EURUSD").json()
    assert eur["last_price"]["close"] == pytest.approx(1.19)
    assert eur["last_price"]["change_1d_pct"] > 0
    past = client.get(f"/api/assets/GOLD?date={(TODAY - timedelta(days=1)).isoformat()}").json()
    assert past["profiles"]["swing"]["score"]["score"] == 1.5
    assert client.get("/api/assets/NOPE").status_code == 404


def test_history_ranges(client: TestClient) -> None:
    body = client.get("/api/assets/EURUSD/history?days=30").json()
    assert len(body["scores"]["swing"]) == 10
    assert len(body["prices"]) == 10
    start = (TODAY - timedelta(days=2)).isoformat()
    narrow = client.get(f"/api/assets/EURUSD/history?from={start}").json()
    assert len(narrow["scores"]["swing"]) == 3
    assert client.get(f"/api/assets/EURUSD/history?from={TODAY}&to={start}").status_code == 422
    assert client.get("/api/assets/EURUSD/history?days=0").status_code == 422
    assert client.get("/api/assets/NOPE/history").status_code == 404


def test_cot_endpoint(client: TestClient) -> None:
    body = client.get("/api/assets/EURUSD/cot").json()
    names = [s["name"] for s in body["series"]]
    assert names == ["EUR", "USD"]  # beide Währungen des Paares
    point = body["series"][0]["points"][0]
    assert point["net"] == 200
    assert point["net_pct_oi"] == 20.0
    assert body["series"][1]["points"] == []
    assert client.get("/api/assets/AAPL/cot").json()["series"] == []


def test_sentiment_endpoint(client: TestClient) -> None:
    fx = client.get("/api/assets/EURUSD/sentiment").json()
    assert fx["retail_symbol"] == "EURUSD"
    assert fx["retail"][0]["long_pct"] == 70
    assert fx["aaii"] == []
    spx = client.get("/api/assets/SPX/sentiment").json()
    assert spx["retail_symbol"] is None
    assert spx["aaii"][0]["bearish"] == 50


def test_fundamentals_endpoint(client: TestClient) -> None:
    stock = client.get("/api/assets/AAPL/fundamentals").json()
    assert stock["kind"] == "stock"
    assert stock["facts"][0]["concept"] == "us-gaap:Revenues"
    assert stock["earnings"][0]["surprise_pct"] == 10.5
    fx = client.get("/api/assets/EURUSD/fundamentals").json()
    assert fx["kind"] == "macro"
    assert [e["code"] for e in fx["macro"]["economies"]] == ["EZ", "US"]
    gold = client.get("/api/assets/GOLD/fundamentals").json()
    assert [e["code"] for e in gold["macro"]["economies"]] == ["US"]
    assert client.get("/api/assets/EURUSD/fundamentals?profile=x").status_code == 422


def test_macro_heatmap_marks_missing_series(client: TestClient) -> None:
    body = client.get("/api/macro").json()
    assert {e["code"] for e in body["economies"]} >= {"US", "EZ", "JP"}
    us = next(e for e in body["economies"] if e["code"] == "US")
    assert us["indicators"][0]["value"] is None
    assert us["indicators"][0]["fresh"] is False
    assert body["change_months"] == 3


def test_changes(client: TestClient) -> None:
    body = client.get("/api/changes?since=1d").json()
    assert body["date"] == TODAY.isoformat()
    first = body["changes"][0]
    assert first["asset_id"] == "GOLD"  # größte Bewegung (+1.0)
    assert first["delta"] == 1.0
    assert first["label_changed"] is True
    assert first["previous_label"] == "Neutral"
    week = client.get("/api/changes?since=7d").json()
    assert any(c["asset_id"] == "EURUSD" and c["delta"] == 3.5 for c in week["changes"])
    assert client.get("/api/changes?since=3d").status_code == 422


def test_status_flags_stale_sources(client: TestClient) -> None:
    body = client.get("/api/status").json()
    by = {s["source"]: s for s in body["sources"]}
    assert by["cftc"]["stale"] is False
    assert by["fred"]["stale"] is True  # Erfolg 2020
    assert by["aaii"]["stale"] is True  # nie gelaufen
    assert by["aaii"]["last_success"] is None
    assert by["prices"]["last_run_status"] == "error"
    assert by["prices"]["last_error"] == "kaputt"
    assert body["last_score_date"] == TODAY.isoformat()


def test_health_still_works(client: TestClient) -> None:
    assert client.get("/api/health").json()["status"] == "ok"


def test_profiles_expose_notices(client: TestClient) -> None:
    body = {p["key"]: p for p in client.get("/api/profiles").json()}

    assert body["swing"]["notices"] == []
    (notice,) = body["long_term"]["notices"]
    assert notice["asset_classes"] == ["index", "stock"]
    assert notice["level"] == "info"
    assert "Vorhersagewert" in notice["text"]
    # bestehende Felder unverändert
    assert {"key", "label", "horizon"} <= set(body["long_term"])


def test_profiles_without_notices_in_config(config: Config, db: sqlite3.Connection) -> None:
    config.profiles["long_term"].notices.clear()
    client = TestClient(create_app(config, frontend_dist=None))

    assert all(p["notices"] == [] for p in client.get("/api/profiles").json())
