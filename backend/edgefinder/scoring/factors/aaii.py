"""AAII-Anlegerumfrage (marktweit, USA), konträr und bewusst moderat.

Spanne = Bullish% − Bearish%, gemittelt über `smoothing_weeks`. Mit mindestens `min_weeks`
Wochen Historie: Perzentil der Spanne über `history_weeks`. Sonst (Historie wird erst
aufgebaut, die Seite zeigt nur 4 Wochen): z-Wert gegen den langjährigen Durchschnitt
(`fallback_mean`, `fallback_std`, Startwerte). Teilscore = −MAX × Perzentil-Einheit
(bzw. −MAX × tanh(z / 1,5)), MAX = 0,6: extreme Euphorie ist konträr bearish.
"""

from __future__ import annotations

from typing import Any

from edgefinder.scoring.factors import (
    FactorResult,
    pct_to_unit,
    percentile,
    rounded,
    squash,
    unavailable,
)

MAX_ABS = 0.6


def compute(weeks: list[tuple[str, float, float]], params: dict[str, Any]) -> FactorResult:
    """weeks: (Umfragedatum, bullish %, bearish %), aufsteigend, bis Stichtag."""
    if not weeks:
        return unavailable("AAII: keine Umfragedaten vorhanden.")
    smoothing = int(params.get("smoothing_weeks", 1))
    history = int(params.get("history_weeks", 156))
    min_weeks = int(params.get("min_weeks", 26))
    window = weeks[-history:]
    spreads = [bull - bear for _, bull, bear in window]
    n = max(1, smoothing)
    smoothed = [
        sum(spreads[max(0, i - n + 1) : i + 1]) / len(spreads[max(0, i - n + 1) : i + 1])
        for i in range(len(spreads))
    ]
    current = smoothed[-1]
    if len(window) >= min_weeks:
        pct = percentile(current, smoothed)
        score = -MAX_ABS * pct_to_unit(pct)
        method = "percentile"
        detail = f"Perzentil {pct:.0f} der letzten {len(window)} Wochen"
        extra = {"percentile": rounded(pct, 1)}
    else:
        mean = float(params.get("fallback_mean", 6.5))
        std = float(params.get("fallback_std", 16.0))
        z = (current - mean) / std
        score = -MAX_ABS * squash(z, 1.5)
        method = "historical_norm"
        detail = (
            f"{z:+.1f} Standardabweichungen vom langjährigen Durchschnitt "
            f"(erst {len(window)} Wochen eigene Historie)"
        )
        extra = {"z": rounded(z, 3)}
    mood = "Euphorie" if current > 0 else "Pessimismus"
    contrarian = "bearish" if score < -0.1 else "bullish" if score > 0.1 else "neutral"
    reason = (
        f"AAII-Umfrage ({window[-1][0]}): Bullish − Bearish = {current:+.1f} Punkte, {detail}; "
        f"{mood} unter Privatanlegern ist konträr moderat {contrarian}."
    )
    return FactorResult(
        score,
        reason,
        {"week": window[-1][0], "spread": rounded(current, 2), "method": method, **extra},
    )
