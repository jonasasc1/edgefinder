"""Eichung je Asset: Was hat der aktuelle Score-Bereich historisch gebracht?

Liest die versionierte Datei `backtest.calibration_file` (erzeugt von `edgefinder calibrate`),
braucht also keine Backfill-DB. Liefert Zahlen und Textbausteine-Daten, keinen Fließtext; die
Oberfläche formuliert sachlich ohne Handlungsempfehlung.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any

from edgefinder.api import schemas as s
from edgefinder.backtest.calibration import (
    BELEGT,
    DIRECTIONAL,
    KEIN_VORTEIL,
    NEUTRAL,
    SCHWACH,
    ZU_WENIG,
    load_calibration,
)
from edgefinder.config import Asset, Config
from edgefinder.scoring.agreement import agreement as factor_agreement

# Hinweis-Code je Lage; das Frontend wählt daraus den Satz.
NOTES = {
    BELEGT: "proven",
    SCHWACH: "weak",
    KEIN_VORTEIL: "no_edge",
    ZU_WENIG: "few_data",
    NEUTRAL: "neutral",
}


class CalibrationStore:
    """Datei lesen, bei geänderter Änderungszeit neu laden (kein Neustart nötig)."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self._mtime: float | None = None
        self._data: dict[str, Any] | None = None

    def get(self) -> dict[str, Any] | None:
        try:
            mtime = self.path.stat().st_mtime
        except OSError:
            return None
        if mtime != self._mtime:
            self._data, self._mtime = load_calibration(self.path), mtime
        return self._data


def _meta(cal: dict[str, Any] | None) -> dict[str, Any]:
    if not cal:
        return {"available": False}
    return {
        "available": True,
        "generated_at": cal["generated_at"],
        "first_date": cal["first_date"],
        "data_through": cal["data_through"],
        "train_end": cal["params"]["train_end"],
        "min_t": cal["params"]["min_t"],
        "min_n_eff": cal["params"]["min_n_eff"],
    }


def summary_out(cal: dict[str, Any] | None) -> s.CalibrationSummaryOut:
    if not cal:
        return s.CalibrationSummaryOut(available=False)
    return s.CalibrationSummaryOut(**_meta(cal), profiles=cal["summary"])


def _agreement_group(
    cal: dict[str, Any], profile: str, klass: str, share: float | None
) -> dict[str, Any] | None:
    block = cal["agreement"].get(profile, {}).get(klass)
    if not block or share is None:
        return None
    key = "high" if share >= block["threshold"] else "low"
    return {
        "group": key,
        "threshold": block["threshold"],
        "horizon": block["horizon"],
        "evidence": block[key]["evidence"],
        "stats": {p: block[key][p] for p in ("all", "train", "oos")},
        "other_evidence": block["low" if key == "high" else "high"]["evidence"],
        "min_t": cal["params"].get("agreement_min_t"),
    }


def build_calibration_out(
    config: Config,
    conn: sqlite3.Connection,
    cal: dict[str, Any] | None,
    asset: Asset,
    profile: str,
) -> s.AssetCalibrationOut | None:
    """None, wenn der Asset noch keinen Score hat."""
    row = conn.execute(
        "SELECT id, date, score, label FROM scores WHERE asset_id = ? AND profile = ?"
        " ORDER BY date DESC LIMIT 1",
        (asset.id, profile),
    ).fetchone()
    if row is None:
        return None
    base = {
        "asset_id": asset.id,
        "profile": profile,
        "asset_class": asset.asset_class.value,
        "as_of": row["date"],
        "score": row["score"],
        "label": row["label"],
    }
    klass = asset.asset_class.value
    by_class = (cal or {}).get("classes", {}).get(profile, {}).get(klass)
    if not cal or not by_class:
        return s.AssetCalibrationOut(
            **base, **_meta(cal), note="missing" if not cal else "few_data"
        )
    params = cal["params"]
    buckets = params["buckets"]
    # gleiche Zuordnung wie im Backtest: erstes Label, dessen Untergrenze erreicht ist
    bucket = next((b for b in buckets if row["score"] >= b["low"]), buckets[-1])
    horizon = params["primary_horizon"][profile]
    cells = by_class[str(horizon)]
    chart = [
        {
            "key": b["label"],
            "label": b["label"],
            "low": b["low"],
            "high": b["high"],
            "direction": b["direction"],
            "evidence": cells[b["label"]]["evidence"],
            **{p: cells[b["label"]][p] for p in ("all", "train", "oos")},
        }
        for b in buckets
    ]
    current = cells[bucket["label"]]
    direct = cells[DIRECTIONAL]
    asset_cells = cal["assets"].get(profile, {}).get(asset.id, {}).get(bucket["label"])
    comps = conn.execute(
        "SELECT subscore, effective_weight FROM score_components WHERE score_id = ?",
        (row["id"],),
    ).fetchall()
    info = factor_agreement(
        [(c["subscore"], c["effective_weight"]) for c in comps],
        row["score"],
        params["signal_threshold"],
    )
    agr = (
        _agreement_group(cal, profile, klass, info["weight_share"])
        if info and bucket["direction"] != 0
        else None
    )
    evidence = current["evidence"]
    return s.AssetCalibrationOut(
        **base,
        **_meta(cal),
        horizon=horizon,
        horizons=list(params["horizons"][profile]),
        bucket={k: bucket[k] for k in ("label", "low", "high", "direction")},
        evidence=evidence,
        class_evidence=direct["evidence"],
        note=NOTES[evidence],
        stats={p: current[p] for p in ("all", "train", "oos")},
        class_directional={p: direct[p] for p in ("all", "train", "oos")},
        by_horizon={
            h: {
                "evidence": hc[bucket["label"]]["evidence"],
                **{p: hc[bucket["label"]][p] for p in ("all", "train", "oos")},
            }
            for h, hc in by_class.items()
        },
        asset_stats=({p: asset_cells[p] for p in ("all", "train", "oos")} if asset_cells else None),
        asset_status="ok" if asset_cells else "zu_wenig_daten",
        asset_min_n_eff=params["asset_min_n_eff"],
        chart=chart,
        agreement=agr,
    )
