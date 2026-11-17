"""Fundamentaldaten (SEC companyfacts): Wachstum, Margen, Bewertung gegen eigene Historie.

Alle Werte sind Trailing-Twelve-Months (TTM): Geschäftsjahr + laufendes Jahr bis Stichtag −
Vorjahreszeitraum (10-Q enthalten nur Jahresteilwerte).

* Wachstum: annualisiertes Wachstum des TTM-Umsatzes über `growth_quarters` Quartale
  (4 = Vorjahr, 12 = 3-Jahres-CAGR); Score = tanh(g / 20 %).
* Margen: operative (sonst Netto-)Marge. Niveau tanh((Marge − 10 %) / 15 %) und Veränderung
  über `growth_quarters` Quartale tanh(Δ / 5 Punkte); Score = Mittel beider.
* Bewertung: KGV = Kurs / TTM-EPS (verwässert), Perzentil des aktuellen KGV unter den
  Quartalsenden der letzten `valuation_years`; günstig vs. eigene Historie ist bullish,
  Score = −0,7 × Perzentil-Einheit (nur ≥ 6 Stützstellen, EPS > 0).
Teilscore = Mittel der verfügbaren Komponenten.
"""

from __future__ import annotations

from bisect import bisect_right
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any

from edgefinder.scoring.factors import (
    FactorResult,
    pct_to_unit,
    percentile,
    rounded,
    sign_word,
    squash,
    unavailable,
)

REVENUE_CONCEPTS = (
    "us-gaap:RevenueFromContractWithCustomerExcludingAssessedTax",
    "us-gaap:Revenues",
)
OPERATING_INCOME = "us-gaap:OperatingIncomeLoss"
NET_INCOME = "us-gaap:NetIncomeLoss"
EPS = "us-gaap:EarningsPerShareDiluted"

GROWTH_SCALE = 0.20
MARGIN_PAR = 0.10
MARGIN_SCALE = 0.15
MARGIN_CHANGE_SCALE = 0.05
VALUATION_MAX = 0.7
MIN_VALUATION_POINTS = 6
TOLERANCE_DAYS = 6


@dataclass(frozen=True)
class Fact:
    period_start: str
    period_end: str
    value: float
    filed: str = ""


def _days(start: str, end: str) -> int:
    return (date.fromisoformat(end) - date.fromisoformat(start)).days


def _find(
    index: dict[tuple[str, str], Fact], start: date, end: date, tol: int = TOLERANCE_DAYS
) -> Fact | None:
    for (s, e), fact in index.items():
        if abs((date.fromisoformat(s) - start).days) <= tol and (
            abs((date.fromisoformat(e) - end).days) <= tol
        ):
            return fact
    return None


def ttm_series(facts: list[Fact]) -> list[tuple[str, float]]:
    """TTM-Wert je Periodenende (aufsteigend). Nur Dauerwerte (Umsatz, Gewinn, EPS)."""
    index: dict[tuple[str, str], Fact] = {}
    for fact in facts:
        if not fact.period_start:
            continue
        key = (fact.period_start, fact.period_end)
        if key not in index or fact.filed >= index[key].filed:
            index[key] = fact
    out: dict[str, float] = {}
    for (start_s, end_s), fact in index.items():
        duration = _days(start_s, end_s)
        if 350 <= duration <= 380:
            out[end_s] = fact.value
            continue
        if duration >= 350 or duration < 60:
            continue
        # Jahresteilwert (Q1, 6M, 9M): Geschäftsjahr davor + YTD − YTD im Vorjahr
        start, end = date.fromisoformat(start_s), date.fromisoformat(end_s)
        prior_ytd = _find(index, start - timedelta(days=365), end - timedelta(days=365))
        fy_end = start - timedelta(days=1)
        full_year = None
        for (s, e), cand in index.items():
            if 350 <= _days(s, e) <= 380 and abs((date.fromisoformat(e) - fy_end).days) <= 6:
                full_year = cand
                break
        if prior_ytd is not None and full_year is not None:
            out.setdefault(end_s, full_year.value + fact.value - prior_ytd.value)
    return sorted(out.items())


def _first_series(
    facts: dict[str, list[Fact]], concepts: tuple[str, ...]
) -> list[tuple[str, float]]:
    best: list[tuple[str, float]] = []
    for concept in concepts:
        series = ttm_series(facts.get(concept, []))
        if series and (not best or series[-1][0] > best[-1][0]):
            best = series
    return best


def _at_or_before(series: list[tuple[str, float]], day: str) -> tuple[str, float] | None:
    index = bisect_right([d for d, _ in series], day) - 1
    return series[index] if index >= 0 else None


def compute(
    facts: dict[str, list[Fact]],
    price_dates: list[str],
    closes: list[float],
    as_of: date,
    params: dict[str, Any],
) -> FactorResult:
    quarters = int(params.get("growth_quarters", 4))
    years = int(params.get("valuation_years", 5))
    revenue = _first_series(facts, REVENUE_CONCEPTS)
    profit = _first_series(facts, (OPERATING_INCOME,)) or _first_series(facts, (NET_INCOME,))
    profit_name = "operative Marge" if ttm_series(facts.get(OPERATING_INCOME, [])) else "Nettomarge"
    parts: list[float] = []
    texts: list[str] = []
    inputs: dict[str, Any] = {}

    # Wachstum
    if len(revenue) > 1 and revenue[-1][1] > 0:
        ref = _at_or_before(
            revenue,
            (date.fromisoformat(revenue[-1][0]) - timedelta(days=91 * quarters)).isoformat(),
        )
        if ref is not None and ref[1] > 0 and ref[0] != revenue[-1][0]:
            span_years = _days(ref[0], revenue[-1][0]) / 365.25
            growth = (revenue[-1][1] / ref[1]) ** (1 / span_years) - 1
            score = squash(growth, GROWTH_SCALE)
            parts.append(score)
            texts.append(
                f"Umsatz (TTM) wächst {growth * 100:+.1f} % p. a. über {quarters} Quartale"
            )
            inputs["growth"] = {
                "revenue_ttm": revenue[-1][1],
                "period_end": revenue[-1][0],
                "ref_period_end": ref[0],
                "cagr_pct": rounded(growth * 100, 2),
                "score": rounded(score, 3),
            }

    # Marge
    if revenue and profit:
        margin_series = []
        for end, value in profit:
            rev = _at_or_before(revenue, end)
            if rev and rev[1] > 0 and _days(rev[0], end) <= TOLERANCE_DAYS:
                margin_series.append((end, value / rev[1]))
        if margin_series:
            end, margin = margin_series[-1]
            level_score = squash(margin - MARGIN_PAR, MARGIN_SCALE)
            ref_m = _at_or_before(
                margin_series,
                (date.fromisoformat(end) - timedelta(days=91 * quarters)).isoformat(),
            )
            scores = [level_score]
            text = f"{profit_name} {margin * 100:.1f} %"
            inputs["margin"] = {"period_end": end, "margin_pct": rounded(margin * 100, 2)}
            if ref_m is not None and ref_m[0] != end:
                delta = margin - ref_m[1]
                scores.append(squash(delta, MARGIN_CHANGE_SCALE))
                text += f" ({delta * 100:+.1f} Punkte in {quarters} Quartalen)"
                inputs["margin"]["change_pts"] = rounded(delta * 100, 2)
            score = sum(scores) / len(scores)
            inputs["margin"]["score"] = rounded(score, 3)
            parts.append(score)
            texts.append(text)

    # Bewertung
    eps = ttm_series(facts.get(EPS, []))
    if eps and closes:
        latest_eps = eps[-1][1]
        cutoff = (as_of - timedelta(days=365 * years)).isoformat()
        pes: list[float] = []
        for end, value in eps:
            if end < cutoff or value <= 0:
                continue
            idx = bisect_right(price_dates, end) - 1
            if idx >= 0 and _days(price_dates[idx], end) <= 7:
                pes.append(closes[idx] / value)
        if latest_eps > 0 and len(pes) >= MIN_VALUATION_POINTS:
            current_pe = closes[-1] / latest_eps
            pct = percentile(current_pe, pes)
            score = -VALUATION_MAX * pct_to_unit(pct)
            parts.append(score)
            texts.append(f"KGV {current_pe:.1f} liegt im Perzentil {pct:.0f} der eigenen Historie")
            inputs["valuation"] = {
                "pe": rounded(current_pe, 2),
                "percentile": rounded(pct, 1),
                "points": len(pes),
                "eps_ttm": latest_eps,
                "score": rounded(score, 3),
            }

    if not parts:
        return unavailable("Fundamentaldaten: keine auswertbaren SEC-Daten vorhanden.")
    total = sum(parts) / len(parts)
    return FactorResult(total, "; ".join(texts) + f" → {sign_word(total)}.", inputs)
