"""Langfrist-Profil: Faktor-Diagnose und Varianten (Train 2013-2019 / OOS 2020+).

Nutzt die gespeicherten Teilscores des Backfills (nur lesend, keine Neuberechnung):
    cd backend && uv run python scripts/longterm_research.py
Varianten ersetzen/umgewichten einzelne Teilscores, Gesamtscore wird renormiert neu gebildet.
"""

from __future__ import annotations

import dataclasses
import sys

from edgefinder.backtest import analysis as A
from edgefinder.config import load_config
from edgefinder.db import connect

PROFILE, H = "long_term", 60
SPLITS = {"TRAIN": ("2013-01-01", "2019-12-31"), "OOS": ("2020-01-01", "2099-01-01")}
CLASSES = ("index", "stock", "forex", "commodity")


def combine(comps: dict[str, tuple[float | None, float]], flip=(), mult=None) -> float | None:
    """Gesamtscore 0..±10 aus (Teilscore, Gewicht); flip = Faktoren mit umgekehrtem Vorzeichen."""
    mult = mult or {}
    num = den = 0.0
    for f, (s, w) in comps.items():
        if s is None:
            continue
        w = w * mult.get(f, 1.0)
        num += (-s if f in flip else s) * w
        den += w
    return 10 * num / den if den else None


VARIANTS = {
    "V0 Basis": {},
    "VA Makro x0,5": {"mult": {"macro": 0.5}},
    "VB Trend umgekehrt": {"flip": ("trend",)},
    "VC Makro umgekehrt": {"flip": ("macro",)},
    "VD Makro x0,5 + Trend x0,5": {"mult": {"macro": 0.5, "trend": 0.5}},
}


def main() -> None:
    cfg = load_config()
    conn = connect(cfg.storage.database)
    obs = [o for o in A.load_observations(conn, cfg, (H,)) if o.profile == PROFILE]
    ids = {o.score_id for o in obs}
    comps: dict[int, dict[str, tuple[float | None, float]]] = {}
    query = "SELECT score_id, factor, subscore, weight FROM score_components"
    for sid, f, s, w in conn.execute(query):
        if sid in ids:
            comps.setdefault(sid, {})[f] = (s, w)
    buckets = A.buckets_from_labels(cfg.scoring.labels)
    fmt = lambda x, f: "  -  " if x is None else format(x, f)  # noqa: E731
    for label, (lo, hi) in SPLITS.items():
        print("==", label)
        for cls in CLASSES:
            sub = [o for o in obs if o.asset_class == cls and lo <= o.day <= hi]
            # Faktor-IC (je Teilscore als Score)
            for f in sorted({k for o in sub for k in comps[o.score_id]}):
                rows = [
                    dataclasses.replace(o, score=comps[o.score_id][f][0] * 10)
                    for o in sub
                    if comps[o.score_id].get(f, (None, 0))[0] is not None
                ]
                if len(rows) < 60:
                    continue
                r = A.summarize(rows, H, buckets, min_signals=30)
                print(
                    f"  faktor {cls:9s} {f:16s} n={r['n']:5d} "
                    f"ic={fmt(r['ic'], '+.3f')} t={fmt(r['ic_t'], '+.1f')}"
                )
            for name, kw in VARIANTS.items():
                rows = []
                for o in sub:
                    ns = combine(comps[o.score_id], **kw)
                    if ns is not None:
                        rows.append(dataclasses.replace(o, score=ns))
                r = A.summarize(rows, H, buckets, min_signals=30)
                d = r["directional"]["hit_rate"]
                print(
                    f"  {cls:9s} {name:28s} n={r['n']:5d} neff={r['n_eff']:6.0f} "
                    f"hit={fmt(d, '.3f')} "
                    f"base={fmt(r['base_up'], '.3f')} spread={fmt(r['spread'], '+.4f')} "
                    f"ic={fmt(r['ic'], '+.3f')} t={fmt(r['ic_t'], '+.1f')}"
                )


if __name__ == "__main__":
    sys.exit(main())
