"""COT: Positionierung der Non-Commercials (CFTC Legacy, Futures Only).

Netto = Long − Short, relativ zum Open Interest (vergleichbar über die Jahre). Teilscore =
0,7 × Perzentil des Niveaus + 0,3 × Perzentil der Veränderung über `change_weeks`, jeweils über
die letzten `percentile_weeks` Berichte, auf [-1, +1] abgebildet. Große Netto-Longs im
historischen Vergleich sind bullish (Trendfolger-Lesart).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from edgefinder.scoring.factors import (
    FactorResult,
    pct_to_unit,
    percentile,
    rounded,
    sign_word,
    unavailable,
)

LEVEL_WEIGHT = 0.7
MIN_REPORTS = 52  # mindestens ein Jahr Historie


@dataclass(frozen=True)
class CotPoint:
    report_date: str
    net: float  # Non-Commercial Long − Short
    open_interest: float | None = None

    @property
    def net_rel(self) -> float:
        if self.open_interest:
            return self.net / self.open_interest
        return self.net


def compute(points: list[CotPoint], params: dict[str, Any], name: str = "") -> FactorResult:
    weeks = int(params.get("percentile_weeks", 156))
    change_weeks = int(params.get("change_weeks", 4))
    window = points[-weeks:]
    if len(window) < max(MIN_REPORTS, change_weeks + 10):
        return unavailable(
            f"COT: zu wenig Historie ({len(window)} Wochen, nötig {MIN_REPORTS}).",
            reports=len(window),
        )
    values = [point.net_rel for point in window]
    current = values[-1]
    level_pct = percentile(current, values)
    changes = [values[i] - values[i - change_weeks] for i in range(change_weeks, len(values))]
    change = changes[-1]
    change_pct = percentile(change, changes)
    score = LEVEL_WEIGHT * pct_to_unit(level_pct) + (1 - LEVEL_WEIGHT) * pct_to_unit(change_pct)
    last = window[-1]
    direction = "Netto-Long" if last.net >= 0 else "Netto-Short"
    trend = "aufgebaut" if change > 0 else "abgebaut"
    reason = (
        f"Non-Commercials {name + ': ' if name else ''}{direction} von {last.net:.0f} Kontrakten "
        f"(Stand {last.report_date}), Perzentil {level_pct:.0f} der letzten {len(window)} Wochen; "
        f"in {change_weeks} Wochen {trend} (Perzentil {change_pct:.0f}) → "
        f"{sign_word(score)}."
    )
    return FactorResult(
        score,
        reason,
        {
            "report_date": last.report_date,
            "net": last.net,
            "net_rel": rounded(current, 5),
            "level_percentile": rounded(level_pct, 1),
            "change_percentile": rounded(change_pct, 1),
            "weeks": len(window),
            "change_weeks": change_weeks,
        },
    )
