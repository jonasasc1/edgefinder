"""Retail-Sentiment (Myfxbook Community Outlook), konträr.

Mittel des Long-Anteils der letzten `smoothing_days` Tage; Teilscore =
−(Long% − 50) / 25, begrenzt auf [-1, +1]. Wenn die Masse stark long ist, ist das konträr
bearish (und umgekehrt).
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any

from edgefinder.scoring.factors import FactorResult, clamp, de, rounded, unavailable

SCALE = 25.0  # Prozentpunkte Abstand von 50 %, ab denen der Teilscore ±1 erreicht
MAX_AGE_DAYS = 7  # ältere Beobachtungen gelten als fehlend


def compute(
    observations: list[tuple[str, float]], as_of: date, params: dict[str, Any]
) -> FactorResult:
    """observations: (Datum/Zeitstempel ISO, Long-Anteil in %), aufsteigend, bis Stichtag."""
    if not observations:
        return unavailable("Retail-Sentiment: keine Daten vorhanden.")
    days = int(params.get("smoothing_days", 3))
    latest_day = date.fromisoformat(observations[-1][0][:10])
    if (as_of - latest_day).days > MAX_AGE_DAYS:
        return unavailable(
            f"Retail-Sentiment: letzte Messung vom {latest_day} ist zu alt.",
            last_observed=latest_day.isoformat(),
        )
    start = (as_of - timedelta(days=days)).isoformat()
    recent = [value for stamp, value in observations if stamp[:10] > start]
    if not recent:
        recent = [observations[-1][1]]
    mean_long = sum(recent) / len(recent)
    score = clamp(-(mean_long - 50.0) / SCALE)
    contrarian = "bearish" if score < -0.15 else "bullish" if score > 0.15 else "neutral"
    reason = (
        f"Privatanleger sind im Schnitt zu {de(mean_long, '.0f')} % long ({days}-Tage-Mittel, "
        f"{len(recent)} Messungen); die Masse liegt oft falsch, konträr daher {contrarian}."
    )
    return FactorResult(
        score,
        reason,
        {"long_pct": rounded(mean_long, 2), "measurements": len(recent), "smoothing_days": days},
    )
