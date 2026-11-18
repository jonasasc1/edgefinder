"""JSON-Endpunkte unter /api (nur lesend). Pro Request eine eigene SQLite-Verbindung (WAL)."""

from __future__ import annotations

import json
import sqlite3
from bisect import bisect_right
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, date, datetime, timedelta
from typing import Annotated, Literal

from fastapi import APIRouter, HTTPException, Query

from edgefinder.api import schemas as s
from edgefinder.config import Asset, AssetClass, Config, ForexAsset, IndexAsset, StockAsset
from edgefinder.db import connect
from edgefinder.scoring.data import DataStore
from edgefinder.scoring.factors import macro as macro_factor

SINCE_DAYS = {"1d": 1, "7d": 7}
WINDOW_DAYS = 14  # Rückblick für Veränderung 1d/7d (Wochenenden/Feiertage überbrücken)
MAX_HISTORY_DAYS = 3650
MAX_SPARKLINE_DAYS = 365


def _asset_or_404(config: Config, asset_id: str) -> Asset:
    asset = config.assets_by_id.get(asset_id)
    if asset is None:
        raise HTTPException(status_code=404, detail=f"Unbekanntes Asset '{asset_id}'")
    return asset


def _latest_score_date(conn: sqlite3.Connection) -> str | None:
    return conn.execute("SELECT MAX(date) FROM scores").fetchone()[0]


def _before(history: list[tuple[str, float, str]], day: str) -> tuple[float, str] | None:
    """Letzter Score (Wert, Label) mit Datum ≤ `day`; `history` aufsteigend."""
    index = bisect_right([h[0] for h in history], day) - 1
    return (history[index][1], history[index][2]) if index >= 0 else None


def _recent_scores(
    conn: sqlite3.Connection, latest: str, asset_id: str | None = None
) -> dict[tuple[str, str], list[tuple[str, float, str, float]]]:
    """(Asset, Profil) → [(Datum, Score, Label, Abdeckung)] der letzten WINDOW_DAYS bis `latest`."""
    start = (date.fromisoformat(latest) - timedelta(days=WINDOW_DAYS)).isoformat()
    sql = (
        "SELECT asset_id, profile, date, score, label, coverage FROM scores"
        " WHERE date >= ? AND date <= ?"
    )
    params: list[str] = [start, latest]
    if asset_id is not None:
        sql += " AND asset_id = ?"
        params.append(asset_id)
    out: dict[tuple[str, str], list[tuple[str, float, str, float]]] = {}
    # (False Positive: SQL nur aus festen Fragmenten, Werte als ?-Parameter, s. ERGEBNIS.md)
    # nosemgrep
    for row in conn.execute(sql + " ORDER BY date", params):
        out.setdefault((row[0], row[1]), []).append((row[2], row[3], row[4], row[5]))
    return out


def _score_out(history: list[tuple[str, float, str, float]]) -> s.ScoreOut:
    day, score, label, coverage = history[-1]
    pairs = [(d, v, lb) for d, v, lb, _ in history]
    changes: dict[int, float | None] = {}
    for days in SINCE_DAYS.values():
        ref = _before(pairs[:-1], (date.fromisoformat(day) - timedelta(days=days)).isoformat())
        changes[days] = round(score - ref[0], 3) if ref else None
    return s.ScoreOut(
        date=day,
        score=round(score, 3),
        label=label,
        coverage=round(coverage, 3),
        change_1d=changes[1],
        change_7d=changes[7],
    )


def _macro_out(
    config: Config, store: DataStore, codes: list[str], profile: str, as_of: date
) -> s.MacroOut:
    params = config.profiles[profile].params.get("macro", {})
    max_age = int(params.get("max_age_days", 270))
    economies: list[s.MacroEconomyOut] = []
    for code in codes:
        data = store.economy(code, as_of)
        rows: list[s.MacroIndicatorOut] = []
        for key, ind in config.economies[code].indicators.items():
            series = data.indicators.get(key)
            if series is None:
                rows.append(
                    s.MacroIndicatorOut(
                        key=key,
                        label=ind.label,
                        category=ind.category,
                        higher_is=ind.higher_is,
                        date=None,
                        value=None,
                        change=None,
                        score=None,
                        fresh=False,
                    )
                )
                continue
            values = macro_factor.transformed(series)
            fresh = bool(values) and (as_of - date.fromisoformat(values[-1][0])).days <= max_age
            scored = macro_factor.indicator_score(series, as_of, params)
            rows.append(
                s.MacroIndicatorOut(
                    key=key,
                    label=ind.label,
                    category=ind.category,
                    higher_is=ind.higher_is,
                    date=values[-1][0] if values else None,
                    value=round(values[-1][1], 4) if values else None,
                    change=scored[1]["change"] if scored else None,
                    score=round(scored[0], 3) if scored else None,
                    fresh=fresh,
                )
            )
        economies.append(
            s.MacroEconomyOut(code=code, name=config.economies[code].name, indicators=rows)
        )
    return s.MacroOut(change_months=int(params.get("change_months", 3)), economies=economies)


def _economy_codes(config: Config, asset: Asset) -> list[str]:
    """Volkswirtschaften, die in das Makro-Teilscore des Assets eingehen."""
    match asset:
        case ForexAsset():
            return [config.currencies[asset.base].economy, config.currencies[asset.quote].economy]
        case IndexAsset():
            return [asset.economy]
        case StockAsset():
            return []
        case _:
            return ["US"]


def create_router(config: Config) -> APIRouter:
    router = APIRouter(prefix="/api")
    default_profile = next(iter(config.profiles))

    @contextmanager
    def db() -> Iterator[sqlite3.Connection]:
        conn = connect(config.storage.database)
        try:
            yield conn
        finally:
            conn.close()

    @router.get("/backtest")
    def backtest() -> dict:
        """Letzter Backtest (JSON aus `backtest.output_dir`, erzeugt von `edgefinder backtest`)."""
        path = config.backtest.output_dir / "backtest.json"
        if not path.is_file():
            raise HTTPException(status_code=404, detail="Noch kein Backtest gelaufen")
        return json.loads(path.read_text(encoding="utf-8"))

    def _profile_or_422(profile: str) -> str:
        if profile not in config.profiles:
            raise HTTPException(status_code=422, detail=f"Unbekanntes Profil '{profile}'")
        return profile

    @router.get("/profiles", response_model=list[s.ProfileOut])
    def profiles() -> list[s.ProfileOut]:
        return [
            s.ProfileOut(key=key, label=p.label, horizon=p.horizon)
            for key, p in config.profiles.items()
        ]

    @router.get("/assets", response_model=list[s.AssetOut])
    def assets() -> list[s.AssetOut]:
        with db() as conn:
            latest = _latest_score_date(conn)
            history = _recent_scores(conn, latest) if latest else {}
        out: list[s.AssetOut] = []
        for asset in config.assets.all():
            scores = {
                profile: _score_out(history[(asset.id, profile)])
                if (asset.id, profile) in history
                else None
                for profile in config.profiles
            }
            out.append(
                s.AssetOut(
                    id=asset.id, name=asset.name, asset_class=asset.asset_class.value, scores=scores
                )
            )
        return out

    @router.get("/sparklines", response_model=s.SparklinesOut)
    def sparklines(
        days: Annotated[int, Query(ge=2, le=MAX_SPARKLINE_DAYS)] = 30,
        profile: str = default_profile,
    ) -> s.SparklinesOut:
        """Score-Verlauf aller Assets in einem Abruf (für Mini-Verläufe in Listen und Karten)."""
        _profile_or_422(profile)
        with db() as conn:
            latest = _latest_score_date(conn)
            series: dict[str, list[tuple[str, float]]] = {}
            if latest:
                start = (date.fromisoformat(latest) - timedelta(days=days)).isoformat()
                for row in conn.execute(
                    "SELECT asset_id, date, score FROM scores WHERE profile = ? AND date >= ?"
                    " AND date <= ? ORDER BY date",
                    (profile, start, latest),
                ):
                    if row["asset_id"] in config.assets_by_id:
                        series.setdefault(row["asset_id"], []).append(
                            (row["date"], round(row["score"], 3))
                        )
        return s.SparklinesOut(profile=profile, days=days, series=series)

    @router.get("/assets/{asset_id}", response_model=s.AssetDetailOut)
    def asset_detail(
        asset_id: str, as_of: Annotated[date | None, Query(alias="date")] = None
    ) -> s.AssetDetailOut:
        asset = _asset_or_404(config, asset_id)
        profile_out: dict[str, s.ProfileDetailOut | None] = {}
        with db() as conn:
            for profile in config.profiles:
                row = conn.execute(
                    "SELECT id, date FROM scores WHERE asset_id = ? AND profile = ?"
                    " AND date <= ? ORDER BY date DESC LIMIT 1",
                    (asset_id, profile, (as_of or date.max).isoformat()),
                ).fetchone()
                if row is None:
                    profile_out[profile] = None
                    continue
                history = _recent_scores(conn, row["date"], asset_id).get((asset_id, profile), [])
                comps = conn.execute(
                    "SELECT factor, subscore, weight, effective_weight, reason, inputs"
                    " FROM score_components WHERE score_id = ? ORDER BY effective_weight DESC,"
                    " factor",
                    (row["id"],),
                ).fetchall()
                profile_out[profile] = s.ProfileDetailOut(
                    score=_score_out(history),
                    components=[
                        s.ComponentOut(
                            factor=c["factor"],
                            subscore=c["subscore"],
                            weight=c["weight"],
                            effective_weight=round(c["effective_weight"], 4),
                            reason=c["reason"],
                            inputs=json.loads(c["inputs"]),
                        )
                        for c in comps
                    ],
                )
            closes = conn.execute(
                "SELECT date, close FROM prices WHERE asset_id = ? ORDER BY date DESC LIMIT 2",
                (asset_id,),
            ).fetchall()
        last_price = None
        if closes:
            change = (
                round((closes[0]["close"] / closes[1]["close"] - 1) * 100, 3)
                if len(closes) > 1 and closes[1]["close"]
                else None
            )
            last_price = s.PriceOut(
                date=closes[0]["date"], close=closes[0]["close"], change_1d_pct=change
            )
        return s.AssetDetailOut(
            id=asset.id,
            name=asset.name,
            asset_class=asset.asset_class.value,
            last_price=last_price,
            profiles=profile_out,
        )

    @router.get("/assets/{asset_id}/history", response_model=s.HistoryOut)
    def history(
        asset_id: str,
        date_from: Annotated[date | None, Query(alias="from")] = None,
        date_to: Annotated[date | None, Query(alias="to")] = None,
        days: Annotated[int, Query(ge=1, le=MAX_HISTORY_DAYS)] = 365,
    ) -> s.HistoryOut:
        _asset_or_404(config, asset_id)
        end = date_to or datetime.now(UTC).date()
        start = date_from or end - timedelta(days=days)
        if start > end:
            raise HTTPException(status_code=422, detail="`from` liegt nach `to`")
        with db() as conn:
            scores: dict[str, list[tuple[str, float]]] = {p: [] for p in config.profiles}
            for row in conn.execute(
                "SELECT profile, date, score FROM scores WHERE asset_id = ? AND date BETWEEN ?"
                " AND ? ORDER BY date",
                (asset_id, start.isoformat(), end.isoformat()),
            ):
                scores.setdefault(row["profile"], []).append((row["date"], round(row["score"], 3)))
            prices = [
                (r["date"], r["close"])
                for r in conn.execute(
                    "SELECT date, close FROM prices WHERE asset_id = ? AND date BETWEEN ? AND ?"
                    " ORDER BY date",
                    (asset_id, start.isoformat(), end.isoformat()),
                )
            ]
        return s.HistoryOut(asset_id=asset_id, scores=scores, prices=prices)

    @router.get("/assets/{asset_id}/cot", response_model=s.CotOut)
    def cot(asset_id: str, weeks: Annotated[int, Query(ge=1, le=520)] = 156) -> s.CotOut:
        asset = _asset_or_404(config, asset_id)
        contracts: list[tuple[str, str]] = []  # (Name, Kontraktcode)
        match asset:
            case ForexAsset():
                for ccy in (asset.base, asset.quote):
                    code = config.currencies[ccy].cftc_code
                    if code:
                        contracts.append((ccy, code))
            case StockAsset():
                pass
            case _:
                if asset.cftc_code:
                    contracts.append((asset.name, asset.cftc_code))
        series: list[s.CotSeriesOut] = []
        with db() as conn:
            for name, code in contracts:
                rows = conn.execute(
                    "SELECT report_date, noncomm_long, noncomm_short, open_interest FROM"
                    " (SELECT * FROM cot_reports WHERE contract_code = ? ORDER BY report_date"
                    " DESC LIMIT ?) ORDER BY report_date",
                    (code, weeks),
                ).fetchall()
                points = [
                    s.CotPointOut(
                        report_date=r["report_date"],
                        long=r["noncomm_long"],
                        short=r["noncomm_short"],
                        net=r["noncomm_long"] - r["noncomm_short"],
                        open_interest=r["open_interest"],
                        net_pct_oi=round(
                            (r["noncomm_long"] - r["noncomm_short"]) / r["open_interest"] * 100, 2
                        )
                        if r["open_interest"]
                        else None,
                    )
                    for r in rows
                ]
                series.append(s.CotSeriesOut(contract_code=code, name=name, points=points))
        return s.CotOut(asset_id=asset_id, series=series)

    @router.get("/assets/{asset_id}/sentiment", response_model=s.SentimentOut)
    def sentiment(
        asset_id: str,
        days: Annotated[int, Query(ge=1, le=MAX_HISTORY_DAYS)] = 90,
        weeks: Annotated[int, Query(ge=1, le=520)] = 156,
    ) -> s.SentimentOut:
        asset = _asset_or_404(config, asset_id)
        symbol = getattr(asset, "myfxbook", None)
        retail: list[s.RetailPointOut] = []
        aaii: list[s.AaiiPointOut] = []
        start = (datetime.now(UTC) - timedelta(days=days)).isoformat(timespec="seconds")
        with db() as conn:
            if symbol:
                retail = [
                    s.RetailPointOut(
                        observed_at=r["observed_at"],
                        long_pct=r["long_pct"],
                        short_pct=r["short_pct"],
                    )
                    for r in conn.execute(
                        "SELECT observed_at, long_pct, short_pct FROM retail_sentiment WHERE"
                        " source = 'myfxbook' AND symbol = ? AND observed_at >= ? ORDER BY"
                        " observed_at",
                        (symbol, start),
                    )
                ]
            if asset.asset_class in (AssetClass.INDEX, AssetClass.STOCK):
                rows = conn.execute(
                    "SELECT week_date, bullish, neutral, bearish FROM (SELECT * FROM aaii_sentiment"
                    " ORDER BY week_date DESC LIMIT ?) ORDER BY week_date",
                    (weeks,),
                ).fetchall()
                aaii = [s.AaiiPointOut(**dict(r)) for r in rows]
        return s.SentimentOut(asset_id=asset_id, retail_symbol=symbol, retail=retail, aaii=aaii)

    @router.get("/assets/{asset_id}/fundamentals", response_model=s.FundamentalsOut)
    def fundamentals(asset_id: str, profile: str = default_profile) -> s.FundamentalsOut:
        asset = _asset_or_404(config, asset_id)
        _profile_or_422(profile)
        with db() as conn:
            if isinstance(asset, StockAsset):
                ticker = asset.ticker
                facts = conn.execute(
                    "SELECT concept, unit, period_start, period_end, value, filed FROM ("
                    " SELECT *, ROW_NUMBER() OVER (PARTITION BY concept ORDER BY period_end DESC,"
                    " filed DESC) AS n FROM fundamentals WHERE ticker = ?) WHERE n <= 8"
                    " ORDER BY concept, period_end DESC",
                    (ticker,),
                ).fetchall()
                earnings = conn.execute(
                    "SELECT earnings_date, eps_estimate, eps_actual, surprise_pct FROM earnings"
                    " WHERE ticker = ? ORDER BY earnings_date DESC LIMIT 12",
                    (ticker,),
                ).fetchall()
                short = conn.execute(
                    "SELECT settlement_date, short_interest, days_to_cover FROM short_interest"
                    " WHERE ticker = ? ORDER BY settlement_date DESC LIMIT 26",
                    (ticker,),
                ).fetchall()
                insider = conn.execute(
                    "SELECT transaction_date, owner_name, owner_title, transaction_code AS code,"
                    " shares, price FROM insider_trades WHERE ticker = ? ORDER BY"
                    " transaction_date DESC LIMIT 50",
                    (ticker,),
                ).fetchall()
                return s.FundamentalsOut(
                    asset_id=asset_id,
                    kind="stock",
                    facts=[s.FactOut(**dict(r)) for r in facts],
                    earnings=[s.EarningsOut(**dict(r)) for r in earnings],
                    short_interest=[s.ShortInterestOut(**dict(r)) for r in short],
                    insider=[s.InsiderOut(**dict(r)) for r in insider],
                )
            codes = _economy_codes(config, asset)
            macro = _macro_out(
                config, DataStore(conn, config), codes, profile, datetime.now(UTC).date()
            )
        return s.FundamentalsOut(asset_id=asset_id, kind="macro", macro=macro)

    @router.get("/macro", response_model=s.MacroOut)
    def macro(profile: str = default_profile) -> s.MacroOut:
        _profile_or_422(profile)
        with db() as conn:
            return _macro_out(
                config,
                DataStore(conn, config),
                list(config.economies),
                profile,
                datetime.now(UTC).date(),
            )

    @router.get("/changes", response_model=s.ChangesOut)
    def changes(since: Literal["1d", "7d"] = "1d") -> s.ChangesOut:
        days = SINCE_DAYS[since]
        with db() as conn:
            latest = _latest_score_date(conn)
            history = _recent_scores(conn, latest) if latest else {}
        out: list[s.ChangeOut] = []
        if latest:
            ref_day = (date.fromisoformat(latest) - timedelta(days=days)).isoformat()
            for (asset_id, profile), rows in history.items():
                asset = config.assets_by_id.get(asset_id)
                if asset is None or rows[-1][0] != latest:
                    continue
                ref = _before([(d, v, lb) for d, v, lb, _ in rows[:-1]], ref_day)
                if ref is None:
                    continue
                _, score, label, _ = rows[-1]
                out.append(
                    s.ChangeOut(
                        asset_id=asset_id,
                        name=asset.name,
                        asset_class=asset.asset_class.value,
                        profile=profile,
                        score=round(score, 3),
                        previous_score=round(ref[0], 3),
                        delta=round(score - ref[0], 3),
                        label=label,
                        previous_label=ref[1],
                        label_changed=label != ref[1],
                    )
                )
        out.sort(key=lambda c: abs(c.delta), reverse=True)
        return s.ChangesOut(since=since, date=latest, changes=out)

    @router.get("/status", response_model=s.StatusOut)
    def status() -> s.StatusOut:
        now = datetime.now(UTC)
        with db() as conn:
            success = {
                r["source"]: r["last"]
                for r in conn.execute(
                    "SELECT source, MAX(finished_at) AS last FROM fetch_runs"
                    " WHERE status = 'success' GROUP BY source"
                )
            }
            last_run = {
                r["source"]: r
                for r in conn.execute(
                    "SELECT source, status, started_at, error FROM fetch_runs WHERE id IN"
                    " (SELECT MAX(id) FROM fetch_runs GROUP BY source)"
                )
            }
            scored = conn.execute("SELECT MAX(date), MAX(computed_at) FROM scores").fetchone()
        sources: list[s.SourceStatusOut] = []
        for name, source in config.sources.items():
            last = success.get(name)
            stale = True
            if last:
                age = now - datetime.fromisoformat(last)
                stale = age > timedelta(hours=source.stale_after_hours)
            run = last_run.get(name)
            sources.append(
                s.SourceStatusOut(
                    source=name,
                    enabled=source.enabled,
                    last_success=last,
                    last_run_status=run["status"] if run else None,
                    last_run_at=run["started_at"] if run else None,
                    last_error=run["error"] if run and run["status"] != "success" else None,
                    stale_after_hours=source.stale_after_hours,
                    stale=stale and source.enabled,
                )
            )
        return s.StatusOut(
            now=now.isoformat(timespec="seconds"),
            sources=sources,
            last_score_date=scored[0],
            last_scored_at=scored[1],
        )

    return router
