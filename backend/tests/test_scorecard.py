"""Scorecard-Endpunkt: Gruppen-Teilscores, Zeilen mit Long/Short, Vorwert, Earnings."""

from __future__ import annotations

import json
import sqlite3
from datetime import UTC, date, datetime, timedelta

import pytest
from fastapi.testclient import TestClient

from edgefinder.api.app import create_app
from edgefinder.api.scorecard import Component, signal_of, tile_scores
from edgefinder.config import Config

TODAY = datetime.now(UTC).date()


def _score(db, asset, profile, factors):
    sid = db.execute(
        "INSERT INTO scores (asset_id, profile, date, score, label, coverage, computed_at)"
        " VALUES (?, ?, ?, 2.0, 'Bullish', 0.9, '2026-11-17T10:00:00+00:00') RETURNING id",
        (asset, profile, TODAY.isoformat()),
    ).fetchone()[0]
    for factor, sub, eff, inputs in factors:
        db.execute(
            "INSERT INTO score_components VALUES (?, ?, ?, ?, ?, ?, ?)",
            (sid, factor, sub, eff, eff, f"Begründung {factor}", json.dumps(inputs)),
        )


@pytest.fixture
def client(config: Config, db: sqlite3.Connection) -> TestClient:
    _score(
        db,
        "EURUSD",
        "swing",
        [
            ("trend", 0.5, 0.4, {"dist_to_slow_pct": -1.5}),
            ("seasonality", -0.3, 0.1, {"mean_return_pct": 0.2, "forward_days": 21}),
            (
                "cot",
                0.6,
                0.3,
                {
                    "EUR": {"subscore": 0.8, "level_percentile": 91.0, "weeks": 156},
                    "USD": {"subscore": -0.4, "level_percentile": 12.0, "weeks": 156},
                },
            ),
            ("retail_sentiment", None, 0.0, {}),
        ],
    )
    for code, long_, short in (("099741", 300, 100), ("098662", 100, 300)):
        for week, delta in ((date(2026, 11, 3), 0), (date(2026, 11, 10), 20)):
            db.execute(
                "INSERT INTO cot_reports (contract_code, report_date, open_interest, noncomm_long,"
                " noncomm_short) VALUES (?, ?, 1000, ?, ?)",
                (code, week.isoformat(), long_ + delta, short - delta),
            )
    _score(db, "SPX", "swing", [("macro", 0.1, 1.0, {"growth": {"score": 0.1}})])
    month = date(TODAY.year, TODAY.month, 1)
    for i in range(15):  # US-Inflation (CPI): Index steigt 0,3 % je Monat
        year, mon = divmod(month.year * 12 + month.month - 1 - (14 - i), 12)
        db.execute(
            "INSERT INTO macro_observations (source, series_id, date, vintage_date, value)"
            " VALUES ('fred', 'CPIAUCSL', ?, '', ?)",
            (date(year, mon + 1, 1).isoformat(), 300 * 1.003**i),
        )
    now = datetime.now(UTC)
    for hours, long_ in ((30, 60.0), (0, 65.0)):
        db.execute(
            "INSERT INTO retail_sentiment (source, symbol, observed_at, long_pct, short_pct)"
            " VALUES ('myfxbook', 'EURUSD', ?, ?, ?)",
            ((now - timedelta(hours=hours)).isoformat(timespec="seconds"), long_, 100 - long_),
        )
    _score(
        db,
        "AAPL",
        "swing",
        [("earnings", 0.5, 0.3, {}), ("trend", 0.2, 0.7, {"dist_to_slow_pct": 3.0})],
    )
    db.execute("INSERT INTO earnings VALUES ('AAPL', '2026-08-01', 1.9, 2.1, 10.5)")
    db.execute("INSERT INTO earnings VALUES ('AAPL', '2026-05-01', 2.0, 1.9, -5.0)")
    soon = (TODAY + timedelta(days=5)).isoformat()
    db.execute("INSERT INTO earnings VALUES ('AAPL', ?, 2.2, NULL, NULL)", (soon,))
    return TestClient(create_app(config, frontend_dist=None))


def _sections(body: dict) -> dict:
    return {sec["key"]: sec for sec in body["sections"]}


def test_tiles_weighted_and_scaled(client: TestClient) -> None:
    body = client.get("/api/assets/EURUSD/scorecard").json()
    tiles = {t["key"]: t for t in body["tiles"]}
    # (0.4 * 0.5 + 0.1 * -0.3) / 0.5 * 10 = 3.4
    assert tiles["technical"]["score"] == 3.4
    assert tiles["technical"]["signal"] == "bullish"
    assert tiles["technical"]["weight"] == 0.5
    assert tiles["institutional"]["score"] == 6.0
    assert tiles["sentiment"]["score"] is None  # nur Faktoren ohne Daten
    assert tiles["macro"]["score"] is None
    assert body["signal_threshold"] == 0.15


def test_forex_cot_rows_long_short_change_and_signal(client: TestClient) -> None:
    sec = _sections(client.get("/api/assets/EURUSD/scorecard").json())["cot"]
    eur, usd = sec["rows"]
    assert (eur["side"], eur["long_pct"], eur["short_pct"]) == ("EUR", 80.0, 20.0)
    assert eur["change"] == 5.0  # 75 % → 80 %
    assert eur["signal"] == "bullish" and usd["signal"] == "bearish"
    assert eur["date"] == "2026-11-10"
    assert sec["kind"] == "positioning"


def test_crowd_row_uses_retail_with_24h_change(client: TestClient) -> None:
    row = _sections(client.get("/api/assets/EURUSD/scorecard").json())["crowd"]["rows"][0]
    assert (row["long_pct"], row["short_pct"], row["change"]) == (65.0, 35.0, 5.0)


def test_macro_rows_have_previous_and_change(client: TestClient) -> None:
    body = client.get("/api/assets/EURUSD/scorecard").json()
    keys = [k for k in _sections(body) if k.startswith("macro-")]
    assert keys == ["macro-growth", "macro-inflation", "macro-labor", "macro-rates"]
    rows = [r for k in keys for r in _sections(body)[k]["rows"]]
    for row in rows:
        assert row["side"] in ("EUR", "USD")
        if row["previous"] is not None:
            assert row["change"] == pytest.approx(row["value"] - row["previous"], abs=1e-3)
    assert all(r["estimate"] is None and r["surprise_pct"] is None for r in rows)


def test_stock_earnings_have_estimate_actual_surprise(client: TestClient) -> None:
    body = client.get("/api/assets/AAPL/scorecard").json()
    assert {t["key"]: t["label"] for t in body["tiles"]}["macro"] == "Fundamentals"
    sec = _sections(body)["earnings"]
    nxt, newest, older = sec["rows"]
    assert nxt["label"] == "Nächste Zahlen" and nxt["soon"] is True and nxt["estimate"] == 2.2
    assert (newest["value"], newest["estimate"], newest["surprise_pct"]) == (2.1, 1.9, 10.5)
    assert newest["signal"] == "bullish" and older["signal"] == "bearish"
    assert _sections(body)["fundamentals"]["rows"] == []
    assert _sections(body)["fundamentals"]["empty_reason"]


def test_index_shows_inflation_and_rates_as_info_only(client: TestClient) -> None:
    secs = _sections(client.get("/api/assets/SPX/scorecard").json())
    keys = [k for k in secs if "macro-" in k]
    assert keys == ["macro-growth", "macro-inflation", "macro-labor", "macro-rates"]
    assert secs["macro-growth"]["in_score"] is True
    for key in ("macro-inflation", "macro-rates"):
        assert secs[key]["in_score"] is False
        assert secs[key]["signal"] is None and secs[key]["score"] is None
    cpi = secs["macro-inflation"]["rows"][0]
    assert cpi["label"] == "Inflation (CPI)" and cpi["value"] == pytest.approx(3.6, abs=0.1)
    assert cpi["signal"] is None and cpi["score"] is None  # keine Währungs-Lesart bei Indizes


def test_cot_row_has_percentile_and_neutral_reading(client: TestClient) -> None:
    eur, usd = _sections(client.get("/api/assets/EURUSD/scorecard").json())["cot"]["rows"]
    assert (eur["percentile"], usd["percentile"]) == (91.0, 12.0)
    assert (
        eur["text"] == "Non-Commercials Netto-Long (+240 Kontrakte), 91 % im 3-Jahres-Perzentil "
        "der eigenen Historie"
    )
    # Widerspruch Long-Anteil vs. Pille: USD Long 30 % und Perzentil 12 % → bearish, konsistent
    assert usd["long_pct"] == 30.0 and usd["signal"] == "bearish"
    assert usd["text"].startswith("Non-Commercials Netto-Short")


def test_unknown_asset_and_profile(client: TestClient) -> None:
    assert client.get("/api/assets/NOPE/scorecard").status_code == 404
    assert client.get("/api/assets/EURUSD/scorecard?profile=x").status_code == 422


def test_asset_without_score_still_returns_rows(client: TestClient) -> None:
    body = client.get("/api/assets/GOLD/scorecard").json()
    assert body["tiles"] == [] and body["as_of"] is None


def test_signal_threshold_and_tile_weights() -> None:
    assert signal_of(0.15, 0.15) == "bullish"
    assert signal_of(-0.14, 0.15) == "neutral"
    assert signal_of(None, 0.15) is None
    comps = {"trend": Component(1.0, 0.0, "", {}), "cot": Component(-0.5, 1.0, "", {})}
    tiles = {t.key: t for t in tile_scores(comps, 0.15, False)}
    assert tiles["technical"].score is None  # Gewicht 0 zählt nicht
    assert tiles["institutional"].score == -5.0
