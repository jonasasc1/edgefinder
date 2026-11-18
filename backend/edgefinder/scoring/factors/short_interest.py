"""Short Interest (FINRA, zweiwöchentlich), invertiert: steigender Leerverkauf ist bearish.

Teilscore = 0,6 × (−tanh(Veränderung der Short-Stücke über `change_periods` Meldungen / 25 %))
+ 0,4 × (−Perzentil-Einheit der Days-to-Cover über die gesamte Historie). Ohne Days-to-Cover
zählt nur die Veränderung.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from edgefinder.scoring.factors import (
    FactorResult,
    de,
    pct_to_unit,
    percentile,
    rounded,
    sign_word,
    squash,
    unavailable,
)

CHANGE_SCALE = 0.25
CHANGE_WEIGHT = 0.6
MIN_POINTS = 4


@dataclass(frozen=True)
class ShortPoint:
    settlement_date: str
    short_interest: float
    days_to_cover: float | None = None


def compute(points: list[ShortPoint], params: dict[str, Any]) -> FactorResult:
    periods = int(params.get("change_periods", 2))
    if len(points) < max(MIN_POINTS, periods + 1):
        return unavailable(
            f"Short Interest: zu wenig Meldungen ({len(points)}).", points=len(points)
        )
    last, ref = points[-1], points[-1 - periods]
    if ref.short_interest <= 0:
        return unavailable("Short Interest: Vergleichswert ungültig.")
    change = last.short_interest / ref.short_interest - 1
    change_score = -squash(change, CHANGE_SCALE)
    dtc_values = [p.days_to_cover for p in points if p.days_to_cover is not None]
    inputs: dict[str, Any] = {
        "settlement_date": last.settlement_date,
        "short_interest": last.short_interest,
        "change_pct": rounded(change * 100, 2),
        "change_periods": periods,
    }
    text = (
        f"Short Interest {de(last.short_interest / 1e6, '.1f')} Mio. Aktien "
        f"({last.settlement_date}), {de(change * 100, '+.1f')} % in {periods} Meldungen"
    )
    if last.days_to_cover is not None and len(dtc_values) >= MIN_POINTS:
        pct = percentile(last.days_to_cover, dtc_values)
        score = CHANGE_WEIGHT * change_score + (1 - CHANGE_WEIGHT) * -pct_to_unit(pct)
        inputs.update({"days_to_cover": last.days_to_cover, "dtc_percentile": rounded(pct, 1)})
        text += f", Days-to-Cover {de(last.days_to_cover, '.1f')} (Perzentil {de(pct, '.0f')})"
    else:
        score = change_score
    return FactorResult(score, f"{text} → {sign_word(score)}.", inputs)
