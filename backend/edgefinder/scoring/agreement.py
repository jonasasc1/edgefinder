"""Faktor-Übereinstimmung: Wie viele (und wie viel gewichtete) Faktoren zeigen in die Richtung
des Gesamtscores? Reine Rechnung auf vorhandenen Teilscores (Live-Scorecard und Backtest nutzen
dieselbe Funktion).

Ein Faktor zeigt bullish/bearish ab |Teilscore| ≥ Schwelle (`scoring.signal_threshold`), sonst
neutral. Der Gewichtsanteil bezieht sich auf die verfügbaren Faktoren (Gewichte renormiert).
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any


def agreement(
    items: Iterable[tuple[float | None, float]], score: float, threshold: float
) -> dict[str, Any] | None:
    """items: (Teilscore oder None, Gewicht). None, wenn kein Faktor verfügbar ist."""
    bull = bear = neutral = 0
    w_bull = w_bear = w_total = 0.0
    for sub, weight in items:
        if sub is None or weight <= 0:
            continue
        w_total += weight
        if sub >= threshold:
            bull += 1
            w_bull += weight
        elif sub <= -threshold:
            bear += 1
            w_bear += weight
        else:
            neutral += 1
    total = bull + bear + neutral
    if not total or w_total <= 0:
        return None
    direction = 1 if score > 0 else (-1 if score < 0 else 0)
    same = bull if direction > 0 else (bear if direction < 0 else 0)
    w_same = w_bull if direction > 0 else (w_bear if direction < 0 else 0.0)
    return {
        "direction": direction,
        "total": total,
        "bullish": bull,
        "bearish": bear,
        "neutral": neutral,
        "same": same,
        "weight_share": w_same / w_total if direction else None,
        "bullish_share": w_bull / w_total,
        "bearish_share": w_bear / w_total,
    }
