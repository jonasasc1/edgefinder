"""Saisonalität: Ø Rendite im Kalenderfenster der letzten `years` Jahre.

Für jedes Vorjahr wird die Rendite vom gleichen Kalendertag über `forward_days` Kalendertage
gemessen. Teilscore = tanh(t / 3) mit t = Mittel / (Std / √n) (t-Statistik der Renditen);
mindestens 3 Jahre nötig. Saisonalität ist ein schwacher Faktor und bleibt daher gedämpft.
"""

from __future__ import annotations

import statistics
from bisect import bisect_right
from datetime import date, timedelta
from typing import Any

from edgefinder.scoring.factors import FactorResult, de, rounded, sign_word, squash, unavailable

MIN_YEARS = 3
T_SCALE = 3.0
MAX_GAP_DAYS = 7  # Kurs muss höchstens so weit vor dem Fenstergrenze liegen


def _close_on_or_before(
    dates: list[str], closes: list[float], day: date
) -> tuple[date, float] | None:
    index = bisect_right(dates, day.isoformat()) - 1
    if index < 0:
        return None
    found = date.fromisoformat(dates[index])
    if (day - found).days > MAX_GAP_DAYS:
        return None
    return found, closes[index]


def _shift_years(day: date, years: int) -> date:
    try:
        return day.replace(year=day.year - years)
    except ValueError:  # 29. Februar
        return day.replace(year=day.year - years, day=28)


def compute(
    dates: list[str], closes: list[float], as_of: date, params: dict[str, Any]
) -> FactorResult:
    years = int(params.get("years", 10))
    forward = int(params.get("forward_days", 21))
    returns: list[float] = []
    for k in range(1, years + 1):
        start_day = _shift_years(as_of, k)
        start = _close_on_or_before(dates, closes, start_day)
        end = _close_on_or_before(dates, closes, start_day + timedelta(days=forward))
        if start is None or end is None or end[0] <= start[0] or start[1] <= 0:
            continue
        returns.append(end[1] / start[1] - 1)
    if len(returns) < MIN_YEARS:
        return unavailable(
            f"Saisonalität: nur {len(returns)} Vorjahre mit Kursen (nötig {MIN_YEARS}).",
            years_used=len(returns),
        )
    mean = statistics.fmean(returns)
    std = statistics.stdev(returns)
    t_stat = mean / (std / len(returns) ** 0.5) if std > 0 else 0.0
    score = squash(t_stat, T_SCALE)
    hits = sum(1 for r in returns if r > 0)
    reason = (
        f"In den nächsten {forward} Tagen war der Kurs in den letzten {len(returns)} Jahren im "
        f"Schnitt {de(mean * 100, '+.2f')} % (in {hits} von {len(returns)} Jahren im "
        f"Plus) → saisonal "
        f"{sign_word(score)}."
    )
    return FactorResult(
        score,
        reason,
        {
            "years_used": len(returns),
            "mean_return_pct": rounded(mean * 100, 3),
            "hit_rate": rounded(hits / len(returns), 3),
            "t_stat": rounded(t_stat, 3),
            "forward_days": forward,
        },
    )
