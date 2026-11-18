"""Kleine Statistik-Helfer für den Backtest (nur Standardbibliothek)."""

from __future__ import annotations

import math
import statistics
from collections.abc import Sequence


def ranks(values: Sequence[float]) -> list[float]:
    """Ränge 1..n, bei Gleichstand der mittlere Rang."""
    order = sorted(range(len(values)), key=values.__getitem__)
    out = [0.0] * len(values)
    i = 0
    while i < len(order):
        j = i
        while j + 1 < len(order) and values[order[j + 1]] == values[order[i]]:
            j += 1
        mean_rank = (i + j) / 2 + 1
        for k in range(i, j + 1):
            out[order[k]] = mean_rank
        i = j + 1
    return out


def pearson(xs: Sequence[float], ys: Sequence[float]) -> float | None:
    if len(xs) != len(ys) or len(xs) < 3:
        return None
    mx, my = statistics.fmean(xs), statistics.fmean(ys)
    sxx = sum((x - mx) ** 2 for x in xs)
    syy = sum((y - my) ** 2 for y in ys)
    if sxx <= 0 or syy <= 0:
        return None
    return sum((x - mx) * (y - my) for x, y in zip(xs, ys, strict=True)) / math.sqrt(sxx * syy)


def spearman(xs: Sequence[float], ys: Sequence[float]) -> float | None:
    """Rangkorrelation (Information Coefficient); None bei < 3 Paaren oder ohne Streuung."""
    if len(xs) != len(ys):
        raise ValueError("Längen passen nicht")
    return pearson(ranks(xs), ranks(ys))


def t_from_corr(corr: float, n_eff: float) -> float | None:
    """t-Wert einer Korrelation bei (effektiv) `n_eff` unabhängigen Beobachtungen."""
    if n_eff <= 2 or abs(corr) >= 1:
        return None
    return corr * math.sqrt((n_eff - 2) / (1 - corr * corr))


def mean_or_none(values: Sequence[float]) -> float | None:
    return statistics.fmean(values) if values else None


def median_or_none(values: Sequence[float]) -> float | None:
    return statistics.median(values) if values else None


def diff_t(a: Sequence[float], b: Sequence[float], overlap: float) -> float | None:
    """t-Wert der Mittelwertdifferenz a − b; `overlap` (≥ 1) verkleinert die Stichproben auf
    effektive Größen (überlappende Renditefenster sind keine unabhängigen Beobachtungen)."""
    if len(a) < 2 or len(b) < 2:
        return None
    var_a, var_b = statistics.variance(a), statistics.variance(b)
    se2 = var_a * overlap / len(a) + var_b * overlap / len(b)
    if se2 <= 0:
        return None
    return (statistics.fmean(a) - statistics.fmean(b)) / math.sqrt(se2)
