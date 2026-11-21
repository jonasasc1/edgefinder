"""Crash-Dämpfung der Trend-Umkehr (Swing, Indizes/Aktien): Train 2013-2019 / OOS 2020+.

Nutzt gespeicherte Teilscores des Backfills; ersetzt nur den Trend-Teilscore (Umkehr-Beitrag ×
Faktor, wenn der Kurs in 20 Tagen extrem gefallen ist), Gesamtscore renormiert neu:
    cd backend && uv run python scripts/crash_research.py
"""

from __future__ import annotations

import dataclasses
import math
import statistics
import sys
from bisect import bisect_right
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from longterm_research import combine

from edgefinder.backtest import analysis as A
from edgefinder.config import load_config
from edgefinder.db import connect

PROFILE, H = "swing", 10
SPLITS = {"TRAIN": ("2013-01-01", "2019-12-31"), "OOS": ("2020-01-01", "2099-01-01")}
# (Name, Schwelle ROC20 in %, Faktor auf den Umkehr-Beitrag)
VARIANTS = [
    ("V0 Basis", None, 1.0),
    ("V1 ROC20 <= -35 %: neutral", -35.0, 0.0),
    ("V2 ROC20 <= -35 %: x0,5", -35.0, 0.5),
    ("V3 ROC20 <= -25 %: neutral", -25.0, 0.0),
]


def main() -> None:
    cfg = load_config()
    conn = connect(cfg.storage.database)
    obs = [
        o
        for o in A.load_observations(conn, cfg, (H,), profiles=(PROFILE,))
        if o.asset_class in ("index", "stock")
    ]
    ids = {o.score_id for o in obs}
    comps: dict[int, dict[str, tuple[float | None, float]]] = {}
    for sid, f, s, w in conn.execute(
        "SELECT score_id, factor, subscore, weight FROM score_components"
    ):
        if sid in ids:
            comps.setdefault(sid, {})[f] = (s, w)
    prices: dict[str, tuple[list[str], list[float]]] = {}
    for a in {o.asset_id for o in obs}:
        rows = conn.execute(
            "SELECT date, close FROM prices WHERE asset_id=? ORDER BY date", (a,)
        ).fetchall()
        prices[a] = ([r[0] for r in rows], [r[1] for r in rows])
    roc = {}
    for o in obs:
        d, c = prices[o.asset_id]
        i = bisect_right(d, o.day) - 1
        roc[o.score_id] = (c[i] / c[i - 20] - 1) * 100 if i >= 20 else None
    buckets = A.buckets_from_labels(cfg.scoring.labels)
    # Sanity: Rekombination der Basis = gespeicherter Score
    diffs = [abs(combine(comps[o.score_id]) - o.score) for o in obs if o.score_id in comps]
    print("max Abweichung Rekombination:", max(diffs))
    for label, (lo, hi) in SPLITS.items():
        print("==", label)
        for cls in ("index", "stock"):
            sub = [o for o in obs if o.asset_class == cls and lo <= o.day <= hi]
            events = sum(1 for o in sub if (roc[o.score_id] or 0) <= -35)
            print(
                f"  {cls}: Stichtage mit ROC20<=-35 %: {events}, <=-25 %: "
                f"{sum(1 for o in sub if (roc[o.score_id] or 0) <= -25)}"
            )
            for name, thr, factor in VARIANTS:
                rows = []
                for o in sub:
                    c = dict(comps[o.score_id])
                    r = roc[o.score_id]
                    if (
                        thr is not None
                        and r is not None
                        and r <= thr
                        and c.get("trend", (None,))[0] is not None
                    ):
                        c["trend"] = (c["trend"][0] * factor, c["trend"][1])
                    rows.append(dataclasses.replace(o, score=combine(c)))
                s = A.summarize(rows, H, buckets, min_signals=30)
                crash = [
                    (rr.forward[H], o.score, rr.score)
                    for o, rr in zip(sub, rows, strict=True)
                    if (roc[o.score_id] or 0) <= -35 and o.forward.get(H) is not None
                ]
                crash_mean = statistics.fmean(x[0] for x in crash) if crash else float("nan")
                print(
                    f"  {cls:6s} {name:28s} n={s['n']:5d} ic={s['ic']:+.3f} t={s['ic_t']:+.1f} "
                    f"hit={(s['directional']['hit_rate'] or math.nan):.3f} "
                    f"crash-Faelle n={len(crash)} oe-Rendite {crash_mean:+.3%}"
                )


if __name__ == "__main__":
    main()
