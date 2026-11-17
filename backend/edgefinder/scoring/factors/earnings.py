"""Earnings: Überraschung (EPS tatsächlich vs. Schätzung) der letzten `quarters` Meldungen.

Gewichtetes Mittel der Überraschung in % (neueste Meldung doppelt so stark wie die älteste,
linear), Teilscore = tanh(Mittel / 10). Nur bereits gemeldete Quartale (Datum ≤ Stichtag).
"""

from __future__ import annotations

from typing import Any

from edgefinder.scoring.factors import FactorResult, rounded, sign_word, squash, unavailable

SCALE_PCT = 10.0


def compute(reports: list[tuple[str, float | None]], params: dict[str, Any]) -> FactorResult:
    """reports: (Meldedatum, Surprise in %), aufsteigend, nur gemeldete, bis Stichtag."""
    quarters = int(params.get("quarters", 2))
    valid = [(d, s) for d, s in reports if s is not None][-quarters:]
    if not valid:
        return unavailable("Earnings: keine gemeldeten Quartale mit Überraschung vorhanden.")
    weights = [
        1.0 + i / max(1, len(valid) - 1) if len(valid) > 1 else 1.0 for i in range(len(valid))
    ]
    mean = sum(w * s for w, (_, s) in zip(weights, valid, strict=True)) / sum(weights)
    score = squash(mean, SCALE_PCT)
    beats = sum(1 for _, s in valid if s > 0)
    reason = (
        f"Gewinnüberraschung der letzten {len(valid)} Quartale im Schnitt {mean:+.1f} % "
        f"({beats} von {len(valid)} über Erwartung, zuletzt {valid[-1][1]:+.1f} % am "
        f"{valid[-1][0]}) → {sign_word(score)}."
    )
    return FactorResult(
        score,
        reason,
        {
            "quarters": [{"date": d, "surprise_pct": s} for d, s in valid],
            "weighted_mean_pct": rounded(mean, 3),
        },
    )
