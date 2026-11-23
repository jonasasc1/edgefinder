"""Makro: Wachstum, Inflation, Arbeitsmarkt (und bei Forex Zinsen) je Volkswirtschaft.

Indikator-Score: Veränderung des (transformierten) Werts über `change_months`, gemessen als
z-Wert gegen alle gleich langen Veränderungen der letzten `history_years`; Teilscore =
Richtung × tanh(z / 2), Richtung aus `higher_is` der Konfiguration. Kategorie-Score = Mittel
der verfügbaren Indikatoren (ohne `info_only`-Reihen, die nur
angezeigt werden). Serien ohne frischen Wert (älter als `max_age_days`) oder ohne
genug Historie entfallen; fehlt eine ganze Kategorie, entfällt sie.

* Forex: je Kategorie Differenz Basis − Quote (begrenzt auf ±1); zusätzlich Zinskategorie:
  Differenz von Leitzins, 2J- und 10J-Rendite (soweit beide Seiten vorhanden, frisch ≤
  `rates_max_age_days`), je tanh(Differenz / 2 Prozentpunkte).
* Indizes: Wachstum und Arbeitsmarkt der Volkswirtschaft des Index (Inflation nicht, ihre
  Wirkung auf Aktien ist uneindeutig).
* Rohstoffe: `macro_driver` laut Konfiguration (safe_haven / cyclical) auf US-Daten. Edelmetalle:
  nur US-Inflation (Zinsen/Rendite/Dollar gehen seit Modell 2026-11-23 nicht mehr in den Score ein).
Teilscore Macro = Mittel der verfügbaren Kategorien.
"""

from __future__ import annotations

import calendar
import statistics
from bisect import bisect_right
from dataclasses import dataclass, field
from datetime import date
from typing import Any

from edgefinder.scoring.factors import FactorResult, clamp, de, rounded, squash, unavailable

Z_SCALE = 2.0
RATE_SCALE_PP = 2.0
MIN_CHANGES = 24
GROWTH, INFLATION, LABOR, RATES = "growth", "inflation", "labor", "rates"
RATE_KEYS = ("policy_rate", "yield_2y", "yield_10y")
CATEGORY_LABEL = {
    GROWTH: "Wachstum",
    INFLATION: "Inflation",
    LABOR: "Arbeitsmarkt",
    RATES: "Zinsen",
}


@dataclass
class IndicatorData:
    key: str
    label: str
    category: str
    transform: str  # level | yoy | diff (Score) | mom | sma (nur Anzeige)
    higher_is: str  # bullish | bearish
    series: list[tuple[str, float]] = field(default_factory=list)  # (Datum, Wert), aufsteigend
    info_only: bool = False  # nur Anzeige, nie im Score (auch display_only-Reihen)
    window: int | None = None  # Fenster für transform sma


@dataclass
class EconomyData:
    code: str
    name: str
    indicators: dict[str, IndicatorData] = field(default_factory=dict)


@dataclass(frozen=True)
class CategoryScore:
    category: str
    score: float
    details: list[str]
    inputs: dict[str, Any]


def _shift_months(day: date, months: int) -> date:
    total = day.year * 12 + (day.month - 1) - months
    year, month = divmod(total, 12)
    month += 1
    last = calendar.monthrange(year, month)[1]
    return date(year, month, min(day.day, last))


def _value_at_or_before(
    dates: list[str], values: list[float], day: date, tolerance_days: int
) -> tuple[str, float] | None:
    index = bisect_right(dates, day.isoformat()) - 1
    if index < 0:
        return None
    if (day - date.fromisoformat(dates[index])).days > tolerance_days:
        return None
    return dates[index], values[index]


def transformed(ind: IndicatorData) -> list[tuple[str, float]]:
    """Wendet `transform` an: level, yoy (Vorjahresveränderung in %), diff (Änderung zum Vorwert),
    mom (Änderung zum Vorwert in %) und sma (gleitender Mittelwert über `window` Beobachtungen)."""
    series = ind.series
    if ind.transform == "level":
        return list(series)
    if ind.transform == "diff":
        return [(series[i][0], series[i][1] - series[i - 1][1]) for i in range(1, len(series))]
    if ind.transform == "mom":
        return [
            (series[i][0], (series[i][1] / series[i - 1][1] - 1) * 100)
            for i in range(1, len(series))
            if series[i - 1][1] > 0
        ]
    if ind.transform == "sma":
        window = ind.window or 0
        if window < 2:
            return []
        values_sma = [v for _, v in series]
        return [
            (series[i][0], sum(values_sma[i - window + 1 : i + 1]) / window)
            for i in range(window - 1, len(series))
        ]
    dates = [d for d, _ in series]
    values = [v for _, v in series]
    out: list[tuple[str, float]] = []
    for d, v in series:
        ref = _value_at_or_before(dates, values, _shift_months(date.fromisoformat(d), 12), 20)
        if ref is not None and ref[1] > 0 and ref[0] != d:
            out.append((d, (v / ref[1] - 1) * 100))
    return out


def expectation_of(values: list[tuple[str, float]], window: int) -> float | None:
    """Modell-Erwartung für den letzten Wert: Mittel der bis dahin veröffentlichten `window` Werte
    davor (der aktuelle Wert selbst und alles Spätere zählt nie mit, also kein Look-ahead).
    Gibt es weniger als `window` Vorwerte, gibt es keine Erwartung (None)."""
    prior = [v for _, v in values[:-1]]
    if window < 1 or len(prior) < window:
        return None
    return sum(prior[-window:]) / window


def _fresh(series: list[tuple[str, float]], as_of: date, max_age_days: int) -> bool:
    return bool(series) and (as_of - date.fromisoformat(series[-1][0])).days <= max_age_days


def indicator_score(
    ind: IndicatorData, as_of: date, params: dict[str, Any]
) -> tuple[float, dict[str, Any]] | None:
    months = int(params.get("change_months", 3))
    history_years = int(params.get("history_years", 10))
    max_age = int(params.get("max_age_days", 270))
    series = transformed(ind)
    if not _fresh(series, as_of, max_age):
        return None
    dates = [d for d, _ in series]
    values = [v for _, v in series]
    cutoff = _shift_months(as_of, history_years * 12).isoformat()
    changes: list[float] = []
    current_change: float | None = None
    for i, (d, v) in enumerate(series):
        ref = _value_at_or_before(dates, values, _shift_months(date.fromisoformat(d), months), 45)
        if ref is None or ref[0] == d:
            continue
        change = v - ref[1]
        if i == len(series) - 1:
            current_change = change
            ref_date = ref[0]
        if d >= cutoff:
            changes.append(change)
    if current_change is None or len(changes) < MIN_CHANGES:
        return None
    std = statistics.pstdev(changes)
    if std <= 0:
        return None
    z = (current_change - statistics.fmean(changes)) / std
    direction = 1.0 if ind.higher_is == "bullish" else -1.0
    score = squash(direction * z, Z_SCALE)
    return score, {
        "date": dates[-1],
        "value": rounded(values[-1], 4),
        "ref_date": ref_date,
        "change": rounded(current_change, 4),
        "z": rounded(z, 3),
        "score": rounded(score, 3),
    }


def _describe(ind: IndicatorData, info: dict[str, Any], months: int, score: float) -> str:
    verdict = "stützt" if score > 0.15 else "belastet" if score < -0.15 else "neutral für"
    return (
        f"{ind.label} {de(info['value'], 'g')} ({info['date'][:7]}, "
        f"{de(info['change'], '+g')} seit "
        f"{months} Monaten) {verdict} die Währung/den Markt"
    )


def category_scores(
    economy: EconomyData,
    as_of: date,
    params: dict[str, Any],
    categories: tuple[str, ...] = (GROWTH, INFLATION, LABOR),
) -> dict[str, CategoryScore]:
    months = int(params.get("change_months", 3))
    result: dict[str, CategoryScore] = {}
    for category in categories:
        scores: list[float] = []
        details: list[str] = []
        inputs: dict[str, Any] = {}
        for key, ind in economy.indicators.items():
            if ind.category != category or ind.info_only:
                continue
            scored = indicator_score(ind, as_of, params)
            if scored is None:
                continue
            score, info = scored
            scores.append(score)
            inputs[key] = info
            details.append(_describe(ind, info, months, score))
        if scores:
            result[category] = CategoryScore(category, sum(scores) / len(scores), details, inputs)
    return result


def rate_levels(
    economy: EconomyData, as_of: date, params: dict[str, Any]
) -> dict[str, tuple[float, str, str]]:
    """Frische Zins-/Renditeniveaus: Schlüssel → (Wert, Datum, Label)."""
    max_age = int(params.get("rates_max_age_days", 120))
    out: dict[str, tuple[float, str, str]] = {}
    for key in RATE_KEYS:
        ind = economy.indicators.get(key)
        if ind is not None and _fresh(ind.series, as_of, max_age):
            value_date, value = ind.series[-1]
            out[key] = (value, value_date, ind.label)
    return out


def _mean_result(
    parts: dict[str, CategoryScore], header: str, extra: dict[str, Any] | None = None
) -> FactorResult:
    if not parts:
        return unavailable(f"Makro: {header} – keine aktuellen Serien verfügbar.")
    score = sum(p.score for p in parts.values()) / len(parts)
    texts = [
        f"{CATEGORY_LABEL[c]} ({de(p.score, '+.2f')}): " + "; ".join(p.details)
        for c, p in parts.items()
    ]
    reason = f"{header}: " + " | ".join(texts) + "."
    inputs = {c: {"score": rounded(p.score, 3), **p.inputs} for c, p in parts.items()}
    inputs.update(extra or {})
    return FactorResult(clamp(score), reason, inputs)


def compute_economy(economy: EconomyData, as_of: date, params: dict[str, Any]) -> FactorResult:
    """Indizes: Wachstum und Arbeitsmarkt der Volkswirtschaft."""
    parts = category_scores(economy, as_of, params, (GROWTH, LABOR))
    return _mean_result(parts, economy.name)


def compute_forex(
    base: tuple[str, EconomyData],
    quote: tuple[str, EconomyData],
    as_of: date,
    params: dict[str, Any],
) -> FactorResult:
    (base_ccy, base_eco), (quote_ccy, quote_eco) = base, quote
    base_scores = category_scores(base_eco, as_of, params)
    quote_scores = category_scores(quote_eco, as_of, params)
    parts: dict[str, CategoryScore] = {}
    for category in (GROWTH, INFLATION, LABOR):
        if category in base_scores and category in quote_scores:
            b, q = base_scores[category], quote_scores[category]
            parts[category] = CategoryScore(
                category,
                clamp(b.score - q.score),
                [f"{base_ccy} {de(b.score, '+.2f')} vs. {quote_ccy} {de(q.score, '+.2f')}"],
                {base_ccy: b.inputs, quote_ccy: q.inputs},
            )
    base_rates = rate_levels(base_eco, as_of, params)
    quote_rates = rate_levels(quote_eco, as_of, params)
    rate_scores: list[float] = []
    rate_details: list[str] = []
    rate_inputs: dict[str, Any] = {}
    for key in RATE_KEYS:
        if key in base_rates and key in quote_rates:
            diff = base_rates[key][0] - quote_rates[key][0]
            score = squash(diff, RATE_SCALE_PP)
            rate_scores.append(score)
            label = base_rates[key][2].split(" (")[0]
            rate_details.append(
                f"{label} {base_ccy} {de(base_rates[key][0], '.2f')} % vs. {quote_ccy} "
                f"{de(quote_rates[key][0], '.2f')} % (Differenz {de(diff, '+.2f')} Punkte)"
            )
            rate_inputs[key] = {
                base_ccy: {"value": base_rates[key][0], "date": base_rates[key][1]},
                quote_ccy: {"value": quote_rates[key][0], "date": quote_rates[key][1]},
                "diff": rounded(diff, 3),
                "score": rounded(score, 3),
            }
    if rate_scores:
        parts[RATES] = CategoryScore(
            RATES, sum(rate_scores) / len(rate_scores), rate_details, rate_inputs
        )
    return _mean_result(parts, f"{base_ccy}/{quote_ccy}")


def compute_commodity(
    driver: str | None, us: EconomyData, as_of: date, params: dict[str, Any]
) -> FactorResult:
    if driver == "cyclical":
        cyclical = category_scores(us, as_of, params, (GROWTH, LABOR))
        return _mean_result(cyclical, "US-Konjunktur (zyklischer Rohstoff)")
    if driver == "safe_haven":
        parts = category_scores(us, as_of, params, (INFLATION,))
        return _mean_result(parts, "US-Inflation (Edelmetall)")
    return unavailable("Makro: für diesen Rohstoff ist kein `macro_driver` konfiguriert.")
