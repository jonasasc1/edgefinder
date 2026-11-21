"""Bilanz (Forward-Test) je Asset: Signal-Historie mit Ergebnis oder „läuft bis …“."""

from __future__ import annotations

import sqlite3
from datetime import date
from typing import Any

from edgefinder.api import schemas as s
from edgefinder.backtest.analysis import bucket_of, buckets_from_labels
from edgefinder.backtest.live import DIRECTION, add_weekdays
from edgefinder.config import Asset, Config

DEFAULT_LIMIT = 60
MAX_LIMIT = 500


def build_asset_trackrecord(
    config: Config,
    conn: sqlite3.Connection,
    asset: Asset,
    profile: str,
    group: dict[str, Any] | None,
    limit: int = DEFAULT_LIMIT,
) -> s.AssetTrackrecordOut:
    """Neueste Live-Signale zuerst; je Horizont ausgewertet (Rendite, Treffer) oder laufend."""
    version_now = config.scoring.model_version
    horizons = config.backtest.horizons.get(profile, ())
    primary = config.backtest.primary_horizon.get(profile) or (horizons[0] if horizons else 0)
    buckets = buckets_from_labels(config.scoring.labels)
    rows = conn.execute(
        "SELECT date, score, label, model_version FROM scores"
        " WHERE origin = 'live' AND asset_id = ? AND profile = ? ORDER BY date DESC",
        (asset.id, profile),
    ).fetchall()
    outcomes: dict[tuple[str, int, str], Any] = {
        (r["signal_date"], r["horizon_days"], r["model_version"]): r
        for r in conn.execute(
            "SELECT signal_date, horizon_days, model_version, exit_date, forward_return_pct, hit"
            " FROM signal_outcomes WHERE asset_id = ? AND profile = ?",
            (asset.id, profile),
        )
    }
    signals: list[s.AssetSignalOut] = []
    evaluated = open_ = 0
    for row in rows:
        version = row["model_version"] or version_now
        items: list[s.SignalHorizonOut] = []
        for h in horizons:
            found = outcomes.get((row["date"], h, version))
            if found:
                items.append(
                    s.SignalHorizonOut(
                        horizon_days=h,
                        status="ausgewertet",
                        exit_date=found["exit_date"],
                        return_pct=found["forward_return_pct"],
                        hit=None if found["hit"] is None else bool(found["hit"]),
                    )
                )
            else:
                due = add_weekdays(date.fromisoformat(row["date"]), h)
                items.append(
                    s.SignalHorizonOut(horizon_days=h, status="laeuft", due_date=due.isoformat())
                )
        if any(i.status == "ausgewertet" for i in items):
            evaluated += 1
        else:
            open_ += 1
        if len(signals) < limit:
            signals.append(
                s.AssetSignalOut(
                    signal_date=row["date"],
                    score=row["score"],
                    label=row["label"],
                    direction=DIRECTION[bucket_of(row["score"], buckets).direction],
                    model_version=version,
                    horizons=items,
                )
            )
    return s.AssetTrackrecordOut(
        asset_id=asset.id,
        profile=profile,
        model_version=version_now,
        live_since=rows[-1]["date"] if rows else None,
        evaluated=evaluated,
        open=open_,
        primary_horizon=primary,
        class_status=group["status"] if group else "zu_frueh",
        signals=signals,
    )
