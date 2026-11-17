"""Faktoren der Score-Engine: ein Modul je Faktor.

Jede Faktorfunktion nimmt aufbereitete Daten (nur Stand bis zum Stichtag) und die Parameter
des Profils und liefert ein `FactorResult`: Teilscore in [-1, +1] (None = nicht berechenbar),
die Eingangswerte und eine deutsche Begründung.
"""

from __future__ import annotations

import math
from bisect import bisect_left, bisect_right
from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class FactorResult:
    subscore: float | None
    reason: str
    inputs: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.subscore is not None and not -1.0 <= self.subscore <= 1.0:
            raise ValueError(f"Teilscore außerhalb [-1, 1]: {self.subscore}")


def unavailable(reason: str, **inputs: Any) -> FactorResult:
    """Faktor entfällt (Daten fehlen); die Engine renormiert die Gewichte."""
    return FactorResult(None, reason, dict(inputs))


def clamp(value: float, low: float = -1.0, high: float = 1.0) -> float:
    return max(low, min(high, value))


def squash(value: float, scale: float) -> float:
    """Glättet einen Rohwert weich auf (-1, 1): tanh(value / scale)."""
    return math.tanh(value / scale)


def percentile(value: float, sample: Sequence[float]) -> float:
    """Perzentil (0..100) von `value` in `sample` (Mid-Rank bei Gleichstand)."""
    if not sample:
        raise ValueError("leere Stichprobe")
    ordered = sorted(sample)
    below = bisect_left(ordered, value)
    equal = bisect_right(ordered, value) - below
    return 100.0 * (below + 0.5 * equal) / len(ordered)


def pct_to_unit(pct: float) -> float:
    """Perzentil 0..100 → [-1, +1] (50 = 0)."""
    return (pct - 50.0) / 50.0


def sign_word(score: float, positive: str = "bullish", negative: str = "bearish") -> str:
    if score > 0.15:
        return positive
    if score < -0.15:
        return negative
    return "neutral"


def rounded(value: float | None, digits: int = 4) -> float | None:
    return None if value is None else round(value, digits)
