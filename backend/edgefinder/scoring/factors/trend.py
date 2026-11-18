"""Trend: Kurs gegen SMA, schneller gegen langsamen SMA und Rate of Change.

Alle drei Maße werden durch die Volatilität (Std. der Tagesrenditen der letzten 60 Tage ×
√Horizont) geteilt, damit Forex und Aktien vergleichbar sind, dann tanh(z / 2). Teilscore =
Mittel der drei Komponenten.

Umkehr-Modus (`reverse=True`, Swing-Profil für Indizes/Aktien, siehe `reversal_classes` in
`config.yaml`): Der Backtest zeigt dort Kurzfrist-Umkehr (Rendite der letzten Wochen sagt die
nächsten Wochen mit umgekehrtem Vorzeichen voraus). Der Teilscore ist dann das Negative des
Trend-Scores: stark gestiegen/überdehnt → bearish, stark gefallen → bullish.
"""

from __future__ import annotations

import itertools
import math
import statistics
from typing import Any

from edgefinder.scoring.factors import FactorResult, de, rounded, sign_word, squash, unavailable

VOL_DAYS = 60
Z_SCALE = 2.0


def _sma(closes: list[float], n: int) -> float:
    return sum(closes[-n:]) / n


def compute(closes: list[float], params: dict[str, Any], reverse: bool = False) -> FactorResult:
    """closes: Schlusskurse aufsteigend bis zum Stichtag."""
    fast, slow = (int(x) for x in params.get("sma_days", [20, 50]))
    roc_days = int(params.get("roc_days", 20))
    needed = max(slow, roc_days + 1, VOL_DAYS // 2) + 1
    if len(closes) < needed or closes[-1] <= 0:
        return unavailable(f"Trend: zu wenig Kurse ({len(closes)}, nötig {needed}).")
    recent = closes[-(VOL_DAYS + 1) :]
    returns = [math.log(b / a) for a, b in itertools.pairwise(recent) if a > 0 and b > 0]
    vol = statistics.pstdev(returns) if len(returns) > 5 else 0.0
    if vol <= 0:
        return unavailable("Trend: keine Kursbewegung (Volatilität 0).")
    price = closes[-1]
    sma_fast, sma_slow = _sma(closes, fast), _sma(closes, slow)
    dist = price / sma_slow - 1
    cross = sma_fast / sma_slow - 1
    roc = price / closes[-1 - roc_days] - 1
    z_dist = dist / (vol * math.sqrt(slow))
    z_cross = cross / (vol * math.sqrt(slow))
    z_roc = roc / (vol * math.sqrt(roc_days))
    parts = [squash(z, Z_SCALE) for z in (z_dist, z_cross, z_roc)]
    trend_score = sum(parts) / len(parts)
    score = -trend_score if reverse else trend_score
    above = "über" if dist >= 0 else "unter"
    reason = (
        f"Kurs {de(price, '.4g')} liegt {de(abs(dist) * 100, '.1f')} % {above} dem "
        f"{slow}-Tage-Schnitt; "
        f"{fast}-Tage-Schnitt {'über' if cross >= 0 else 'unter'} {slow}-Tage-Schnitt "
        f"({de(cross * 100, '+.1f')} %); Veränderung über {roc_days} Tage "
        f"{de(roc * 100, '+.1f')} % → "
    )
    if reverse:
        if abs(score) <= 0.15:
            reason += "Kurzfrist-Umkehr: keine klare Überdehnung."
        else:
            direction = "nach oben" if trend_score > 0 else "nach unten"
            outlook = "Rückschlag" if score < 0 else "Erholung"
            reason += f"Kurzfrist-Umkehr: überdehnt {direction} → {outlook} wahrscheinlicher."
    else:
        reason += f"Trend {sign_word(score, 'aufwärts', 'abwärts')}."
    return FactorResult(
        score,
        reason,
        {
            "close": price,
            f"sma_{fast}": rounded(sma_fast, 6),
            f"sma_{slow}": rounded(sma_slow, 6),
            "dist_to_slow_pct": rounded(dist * 100, 3),
            "cross_pct": rounded(cross * 100, 3),
            "roc_pct": rounded(roc * 100, 3),
            "daily_vol_pct": rounded(vol * 100, 3),
            "components": [rounded(p, 3) for p in parts],
            "mode": "reversal" if reverse else "trend",
        },
    )
