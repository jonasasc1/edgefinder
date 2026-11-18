"""Insider-Transaktionen (SEC Form 4, Code P = Kauf, S = Verkauf) der letzten `lookback_days`.

Verkäufe sind oft routinemäßig (Vergütung, Steuern) und zählen nur zu 20 %. Verhältnis =
(Käufe − 0,2 × Verkäufe) / (Käufe + 0,2 × Verkäufe) in Dollar, mit Vertrauensfaktor
min(1, Anzahl Transaktionen / 3); negative Werte werden halbiert. Ohne jede Transaktion im
Zeitraum: 0 (neutral), sofern für den Ticker Form-4-Daten geladen wurden, sonst entfällt der Faktor.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any

from edgefinder.scoring.factors import FactorResult, clamp, de, rounded, sign_word, unavailable

SALE_WEIGHT = 0.2
NEGATIVE_DAMPING = 0.5
FULL_CONFIDENCE_TRADES = 3


@dataclass(frozen=True)
class InsiderTrade:
    date: str
    code: str  # P oder S
    shares: float
    price: float | None

    @property
    def value(self) -> float:
        return self.shares * (self.price or 0.0)


def compute(
    trades: list[InsiderTrade], has_coverage: bool, as_of: date, params: dict[str, Any]
) -> FactorResult:
    days = int(params.get("lookback_days", 90))
    if not has_coverage:
        return unavailable("Insider: noch keine Form-4-Daten für diesen Ticker geladen.")
    start = (as_of - timedelta(days=days)).isoformat()
    recent = [t for t in trades if start < t.date <= as_of.isoformat() and t.code in ("P", "S")]
    buys = [t for t in recent if t.code == "P"]
    sells = [t for t in recent if t.code == "S"]
    buy_value = sum(t.value for t in buys)
    sell_value = sum(t.value for t in sells)
    inputs = {
        "buys": len(buys),
        "sells": len(sells),
        "buy_value": rounded(buy_value, 0),
        "sell_value": rounded(sell_value, 0),
        "lookback_days": days,
    }
    if not recent:
        return FactorResult(
            0.0, f"Keine Insider-Käufe oder -Verkäufe in {days} Tagen → neutral.", inputs
        )
    weighted_sells = SALE_WEIGHT * sell_value
    denominator = buy_value + weighted_sells
    ratio = (buy_value - weighted_sells) / denominator if denominator > 0 else 0.0
    if ratio < 0:
        ratio *= NEGATIVE_DAMPING
    confidence = min(1.0, len(recent) / FULL_CONFIDENCE_TRADES)
    score = clamp(ratio * confidence)
    reason = (
        f"Insider in {days} Tagen: {len(buys)} Käufe ({de(buy_value / 1e6, '.2f')} Mio. $) und "
        f"{len(sells)} Verkäufe ({de(sell_value / 1e6, '.2f')} Mio. $); Verkäufe zählen "
        f"nur zu 20 % → "
        f"{sign_word(score)}."
    )
    return FactorResult(score, reason, inputs)
