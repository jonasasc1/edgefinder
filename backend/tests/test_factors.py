"""Faktoren der Score-Engine: Grenzfälle und fehlende Daten (synthetische Daten)."""

from __future__ import annotations

import math
import re
from datetime import date, timedelta

import pytest

from edgefinder.scoring.factors import (
    FactorResult,
    de,
    pct_to_unit,
    percentile,
)
from edgefinder.scoring.factors import aaii as aaii_f
from edgefinder.scoring.factors import cot as cot_f
from edgefinder.scoring.factors import earnings as earnings_f
from edgefinder.scoring.factors import fundamentals as fund_f
from edgefinder.scoring.factors import insider as insider_f
from edgefinder.scoring.factors import macro as macro_f
from edgefinder.scoring.factors import retail_sentiment as retail_f
from edgefinder.scoring.factors import seasonality as season_f
from edgefinder.scoring.factors import short_interest as short_f
from edgefinder.scoring.factors import trend as trend_f

AS_OF = date(2026, 11, 17)


def _in_range(result: FactorResult) -> None:
    assert result.subscore is not None
    assert -1.0 <= result.subscore <= 1.0
    assert result.reason
    assert isinstance(result.inputs, dict)


def test_factor_result_rejects_out_of_range() -> None:
    with pytest.raises(ValueError):
        FactorResult(1.5, "x")


def test_de_formats_german_numbers() -> None:
    assert de(1.101, ".3f") == "1,101"
    assert de(2.4, ".1f") == "2,4"
    assert de(-0.456, "+.2f") == "-0,46"
    assert de(0.456, "+.2f") == "+0,46"
    assert de(1234567.0, ".0f") == "1.234.567"
    assert de(1.1012, ".4g") == "1,101"
    assert de(12.5, "g") == "12,5"


def test_reasons_use_decimal_comma() -> None:
    trend = trend_f.compute(_prices(300, 0.001), {"sma_days": [20, 50], "roc_days": 20})
    assert trend.subscore is not None
    assert re.search(r"\d,\d", trend.reason) and not re.search(r"\d\.\d", trend.reason)


def test_percentile_helpers() -> None:
    assert percentile(5, [1, 2, 3, 4, 5]) == pytest.approx(90.0)
    assert percentile(3, [3, 3, 3]) == pytest.approx(50.0)
    assert pct_to_unit(100) == 1.0
    assert pct_to_unit(0) == -1.0
    with pytest.raises(ValueError):
        percentile(1, [])


# ---------------------------------------------------------------- COT
def _cot(nets: list[float]) -> list[cot_f.CotPoint]:
    start = date(2023, 1, 3)
    return [
        cot_f.CotPoint((start + timedelta(weeks=i)).isoformat(), n, 1000.0)
        for i, n in enumerate(nets)
    ]


def test_cot_extreme_long_is_bullish_extreme_short_bearish() -> None:
    up = cot_f.compute(_cot([float(i * i) for i in range(120)]), {"percentile_weeks": 156})
    down = cot_f.compute(_cot([float(-i * i) for i in range(120)]), {"percentile_weeks": 156})
    _in_range(up)
    _in_range(down)
    assert up.subscore > 0.8
    assert down.subscore < -0.8
    assert "Netto-Long" in up.reason
    assert "Netto-Short" in down.reason


def test_cot_too_little_history_is_unavailable() -> None:
    result = cot_f.compute(_cot([1.0] * 20), {})
    assert result.subscore is None
    assert cot_f.compute([], {}).subscore is None


def test_cot_without_open_interest_uses_net() -> None:
    points = [
        cot_f.CotPoint(p.report_date, p.net, None) for p in _cot([float(i) for i in range(80)])
    ]
    assert cot_f.compute(points, {}).subscore > 0


# ---------------------------------------------------------------- Retail
def test_retail_is_contrarian() -> None:
    long_heavy = retail_f.compute(
        [(f"2026-11-1{d}T10:00:00", 85.0) for d in range(5, 8)], AS_OF, {}
    )
    short_heavy = retail_f.compute([("2026-11-17T10:00:00", 15.0)], AS_OF, {})
    assert long_heavy.subscore == -1.0
    assert short_heavy.subscore == 1.0
    balanced = retail_f.compute([("2026-11-17T10:00:00", 50.0)], AS_OF, {})
    assert balanced.subscore == 0.0


def test_retail_missing_or_stale_is_unavailable() -> None:
    assert retail_f.compute([], AS_OF, {}).subscore is None
    assert retail_f.compute([("2026-10-01T10:00:00", 80.0)], AS_OF, {}).subscore is None


# ---------------------------------------------------------------- Trend
def _prices(n: int, drift: float, noise: float = 0.004) -> list[float]:
    return [100 * math.exp(drift * i + noise * math.sin(i * 1.7)) for i in range(n)]


def test_trend_up_down_and_edge_cases() -> None:
    params = {"sma_days": [20, 50], "roc_days": 20}
    up = trend_f.compute(_prices(120, 0.004), params)
    down = trend_f.compute(_prices(120, -0.004), params)
    _in_range(up)
    _in_range(down)
    assert up.subscore > 0.3
    assert down.subscore < -0.3
    assert trend_f.compute(_prices(30, 0.01), params).subscore is None  # zu wenig Kurse
    assert trend_f.compute([100.0] * 120, params).subscore is None  # keine Volatilität
    assert trend_f.compute([], params).subscore is None


# ---------------------------------------------------------------- Saisonalität
def _seasonal_prices(rise_in_window: bool) -> tuple[list[str], list[float]]:
    dates: list[str] = []
    closes: list[float] = []
    day = date(2010, 1, 1)
    price = 100.0
    while day <= AS_OF:
        window = (day.month, day.day) >= (11, 17) and (day.month, day.day) <= (12, 8)
        step = 0.003 if window else 0.0
        price *= 1 + (step if rise_in_window else -step)
        dates.append(day.isoformat())
        closes.append(price)
        day += timedelta(days=1)
    return dates, closes


def test_seasonality_positive_negative_and_missing() -> None:
    params = {"years": 10, "forward_days": 21}
    d, c = _seasonal_prices(True)
    assert season_f.compute(d, c, AS_OF, params).subscore > 0.5
    d, c = _seasonal_prices(False)
    assert season_f.compute(d, c, AS_OF, params).subscore < -0.5
    assert season_f.compute(d[-100:], c[-100:], AS_OF, params).subscore is None
    assert season_f.compute([], [], AS_OF, params).subscore is None


# ---------------------------------------------------------------- AAII
def _aaii(spread: float, n: int) -> list[tuple[str, float, float]]:
    start = date(2024, 1, 3)
    return [((start + timedelta(weeks=i)).isoformat(), 40 + spread, 40) for i in range(n)]


def test_aaii_contrarian_and_moderate() -> None:
    euphoric = aaii_f.compute(_aaii(60, 4), {"min_weeks": 26})  # Fallback-Norm
    fearful = aaii_f.compute(_aaii(-60, 4), {"min_weeks": 26})
    assert -0.6 <= euphoric.subscore < -0.3
    assert 0.3 < fearful.subscore <= 0.6
    assert euphoric.inputs["method"] == "historical_norm"
    rising = [(d, 40 + i, 40.0) for i, (d, _, _) in enumerate(_aaii(0, 60))]
    result = aaii_f.compute(rising, {"min_weeks": 26, "history_weeks": 156})
    assert result.inputs["method"] == "percentile"
    assert result.subscore < -0.5
    assert aaii_f.compute([], {}).subscore is None


# ---------------------------------------------------------------- Makro
def _monthly(values: list[float], end: date = date(2026, 9, 1)) -> list[tuple[str, float]]:
    out = []
    year, month = end.year, end.month
    for v in reversed(values):
        out.append((date(year, month, 1).isoformat(), v))
        month -= 1
        if month == 0:
            year, month = year - 1, 12
    return list(reversed(out))


def _ind(key: str, values: list[float], higher_is: str = "bullish", category: str = "growth"):
    return macro_f.IndicatorData(key, key, category, "level", higher_is, _monthly(values))


MP = {"change_months": 3, "history_years": 10}


def test_macro_indicator_direction_and_freshness() -> None:
    rising = [float(i) + (i % 3) * 0.1 for i in range(100)]
    for_bullish = macro_f.indicator_score(_ind("g", [*rising, 150.0]), AS_OF, MP)
    for_bearish = macro_f.indicator_score(_ind("u", [*rising, 150.0], "bearish"), AS_OF, MP)
    assert for_bullish is not None
    assert for_bearish is not None
    assert for_bullish[0] > 0 > for_bearish[0]
    assert for_bullish[0] == pytest.approx(-for_bearish[0])
    stale = macro_f.indicator_score(_ind("g", rising), date(2028, 1, 1), MP)
    assert stale is None
    assert macro_f.indicator_score(_ind("g", [1.0, 2.0, 3.0]), AS_OF, MP) is None


def test_macro_yoy_and_diff_transform() -> None:
    yoy = macro_f.IndicatorData(
        "i",
        "i",
        "growth",
        "yoy",
        "bullish",
        _monthly([100.0 * 1.02 ** (i / 12) for i in range(36)]),
    )
    values = macro_f.transformed(yoy)
    assert values[-1][1] == pytest.approx(2.0, abs=0.01)
    diff = macro_f.IndicatorData("n", "n", "labor", "diff", "bullish", _monthly([1.0, 4.0, 9.0]))
    assert [v for _, v in macro_f.transformed(diff)] == [3.0, 5.0]


def _economy(code: str, trend: float, rate: float | None = None) -> macro_f.EconomyData:
    series = [50 + trend * (i / 10) ** 2 + (i % 5) * 0.3 for i in range(100)]
    eco = macro_f.EconomyData(code, code)
    eco.indicators["gdp"] = _ind("gdp", series)
    if rate is not None:
        rates = macro_f.IndicatorData(
            "policy_rate", "Leitzins (X)", "rates", "level", "bullish", _monthly([rate] * 100)
        )
        eco.indicators["policy_rate"] = rates
    return eco


def test_macro_forex_difference_and_rates() -> None:
    strong, weak = _economy("A", 0.5, 5.0), _economy("B", -0.5, 1.0)
    result = macro_f.compute_forex(("AAA", strong), ("BBB", weak), AS_OF, MP)
    mirror = macro_f.compute_forex(("BBB", weak), ("AAA", strong), AS_OF, MP)
    _in_range(result)
    assert result.subscore > 0.5
    assert mirror.subscore == pytest.approx(-result.subscore)
    assert "rates" in result.inputs  # Zinsdifferenz eingeflossen


def test_macro_forex_missing_series_drops_component() -> None:
    no_rate = macro_f.compute_forex(
        ("AAA", _economy("A", 0.5, 5.0)), ("BBB", _economy("B", -0.5)), AS_OF, MP
    )
    assert "rates" not in no_rate.inputs  # nur eine Seite hat einen Zins
    assert no_rate.subscore is not None
    empty = macro_f.compute_forex(
        ("AAA", macro_f.EconomyData("A", "A")), ("BBB", macro_f.EconomyData("B", "B")), AS_OF, MP
    )
    assert empty.subscore is None


def test_macro_commodity_drivers() -> None:
    us = macro_f.EconomyData("US", "USA")
    us.indicators["gdp"] = _ind("gdp", [float(i) + (i % 3) * 0.1 for i in range(100)] + [150.0])
    assert macro_f.compute_commodity("cyclical", us, AS_OF, MP).subscore > 0
    assert macro_f.compute_commodity("safe_haven", us, AS_OF, MP).subscore is None  # nur BIP
    us.indicators["yield_10y"] = _ind(
        "yield_10y", [float(i) + (i % 3) * 0.1 for i in range(100)] + [150.0], category="rates"
    )
    assert macro_f.compute_commodity("safe_haven", us, AS_OF, MP).subscore < 0  # Renditen steigen
    assert macro_f.compute_commodity(None, us, AS_OF, MP).subscore is None


def test_macro_safe_haven_uses_real_yield_policy_rate_and_dollar() -> None:
    rising = [float(i) + (i % 3) * 0.1 for i in range(100)] + [150.0]
    falling = [-v for v in rising]
    us = macro_f.EconomyData("US", "USA")
    us.indicators["real_yield_10y"] = _ind("real_yield_10y", falling, category="rates")
    only_real = macro_f.compute_commodity("safe_haven", us, AS_OF, MP)
    assert only_real.subscore > 0.5  # fallende Realrendite stützt Gold
    assert set(only_real.inputs) == {"rates"}
    assert "Realrendite" in only_real.reason and "stützt Edelmetalle" in only_real.reason

    us.indicators["dollar_index"] = _ind("dollar_index", rising, category="rates")
    both = macro_f.compute_commodity("safe_haven", us, AS_OF, MP)
    assert set(both.inputs) == {"rates", "dollar", "dollar_index"} or "dollar" in both.inputs
    assert both.inputs["dollar"]["score"] < 0  # starker Dollar belastet
    assert both.subscore == pytest.approx(
        (both.inputs["rates"]["score"] + both.inputs["dollar"]["score"]) / 2, abs=1e-3
    )

    us.indicators["policy_rate"] = _ind("policy_rate", rising, category="rates")
    three = macro_f.compute_commodity("safe_haven", us, AS_OF, MP)
    assert set(three.inputs["rates"]) >= {"policy_rate", "real_yield_10y", "score"}
    assert "belastet Edelmetalle" in three.reason
    # Zyklische Rohstoffe bleiben unberührt vom Dollar
    assert macro_f.compute_commodity("cyclical", us, AS_OF, MP).subscore is None


def test_macro_index_uses_growth_and_labor() -> None:
    eco = _economy("A", 0.5)
    result = macro_f.compute_economy(eco, AS_OF, MP)
    _in_range(result)
    assert macro_f.compute_economy(macro_f.EconomyData("A", "A"), AS_OF, MP).subscore is None


# ---------------------------------------------------------------- Fundamentals
def _annual(concept_values: dict[int, float]) -> list[fund_f.Fact]:
    return [
        fund_f.Fact(f"{y}-01-01", f"{y}-12-31", v, f"{y + 1}-02-15")
        for y, v in concept_values.items()
    ]


def test_fundamentals_growth_and_margin() -> None:
    facts = {
        "us-gaap:Revenues": _annual({2023: 100.0, 2024: 130.0, 2025: 170.0}),
        "us-gaap:OperatingIncomeLoss": _annual({2023: 20.0, 2024: 30.0, 2025: 50.0}),
    }
    result = fund_f.compute(facts, [], [], AS_OF, {"growth_quarters": 4})
    _in_range(result)
    assert result.subscore > 0.3
    assert "growth" in result.inputs
    assert "margin" in result.inputs
    shrinking = {
        "us-gaap:Revenues": _annual({2023: 170.0, 2024: 130.0, 2025: 100.0}),
        "us-gaap:NetIncomeLoss": _annual({2023: 5.0, 2024: 0.0, 2025: -10.0}),
    }
    assert fund_f.compute(shrinking, [], [], AS_OF, {}).subscore < 0


def test_fundamentals_empty_is_unavailable() -> None:
    assert fund_f.compute({}, [], [], AS_OF, {}).subscore is None


def test_ttm_from_quarterly_ytd() -> None:
    facts = [
        *_annual({2024: 400.0}),
        fund_f.Fact("2025-01-01", "2025-03-31", 120.0, "2025-05-01"),
        fund_f.Fact("2024-01-01", "2024-03-31", 100.0, "2024-05-01"),
    ]
    ttm = dict(fund_f.ttm_series(facts))
    assert ttm["2024-12-31"] == 400.0
    assert ttm["2025-03-31"] == pytest.approx(420.0)  # 400 + 120 - 100


def test_fundamentals_valuation_cheap_vs_history_is_bullish() -> None:
    eps = [
        fund_f.Fact(f"{y}-01-01", f"{y}-12-31", 5.0, f"{y + 1}-02-01") for y in range(2018, 2026)
    ]
    dates = [f"{y}-12-31" for y in range(2018, 2026)] + ["2026-11-17"]
    closes = [100.0 + 10 * i for i in range(8)] + [60.0]
    result = fund_f.compute({fund_f.EPS: eps}, dates, closes, AS_OF, {"valuation_years": 10})
    assert result.subscore > 0.3
    assert "valuation" in result.inputs


# ---------------------------------------------------------------- Earnings
def test_earnings_surprise() -> None:
    good = earnings_f.compute([("2026-02-01", 10.0), ("2026-05-01", 15.0)], {"quarters": 2})
    bad = earnings_f.compute([("2026-05-01", -20.0)], {"quarters": 2})
    assert good.subscore > 0.6
    assert bad.subscore < -0.5
    assert earnings_f.compute([], {}).subscore is None
    assert earnings_f.compute([("2026-05-01", None)], {}).subscore is None


# ---------------------------------------------------------------- Short Interest
def _short(values: list[float], dtc: float | None = None) -> list[short_f.ShortPoint]:
    start = date(2025, 1, 15)
    return [
        short_f.ShortPoint((start + timedelta(days=15 * i)).isoformat(), v, dtc)
        for i, v in enumerate(values)
    ]


def test_short_interest_rising_is_bearish() -> None:
    rising = short_f.compute(_short([100, 110, 130, 160, 200]), {"change_periods": 2})
    falling = short_f.compute(_short([200, 160, 130, 110, 100]), {"change_periods": 2})
    assert rising.subscore < -0.3
    assert falling.subscore > 0.3
    assert short_f.compute(_short([100, 110]), {}).subscore is None
    assert short_f.compute(_short([0, 0, 0, 0, 0]), {}).subscore is None


def test_short_interest_days_to_cover_included() -> None:
    points = [short_f.ShortPoint(f"2025-0{i + 1}-15", 100.0, float(i + 1)) for i in range(6)]
    result = short_f.compute(points, {"change_periods": 2})
    assert "dtc_percentile" in result.inputs
    assert result.subscore < 0  # höchster Days-to-Cover


# ---------------------------------------------------------------- Insider
def test_insider_buys_vs_sells_and_coverage() -> None:
    buys = [insider_f.InsiderTrade("2026-10-01", "P", 1000, 50.0)] * 3
    sells = [insider_f.InsiderTrade("2026-10-01", "S", 1000, 50.0)] * 3
    assert insider_f.compute(buys, True, AS_OF, {}).subscore == 1.0
    assert insider_f.compute(sells, True, AS_OF, {}).subscore < 0
    # Verkäufe zählen weniger: gleich große Käufe/Verkäufe → leicht bullish
    mixed = insider_f.compute(buys + sells, True, AS_OF, {})
    assert mixed.subscore > 0
    none = insider_f.compute([], True, AS_OF, {})
    assert none.subscore == 0.0
    assert insider_f.compute([], False, AS_OF, {}).subscore is None


def test_insider_lookback_window() -> None:
    old = [insider_f.InsiderTrade("2025-01-01", "P", 1000, 50.0)] * 3
    assert insider_f.compute(old, True, AS_OF, {"lookback_days": 90}).subscore == 0.0
    assert insider_f.compute(old, True, AS_OF, {"lookback_days": 900}).subscore == 1.0


def test_trend_reversal_mode_flips_sign() -> None:
    params = {"sma_days": [20, 50], "roc_days": 20}
    up = trend_f.compute(_prices(120, 0.004), params)
    up_rev = trend_f.compute(_prices(120, 0.004), params, reverse=True)
    down_rev = trend_f.compute(_prices(120, -0.004), params, reverse=True)
    assert up_rev.subscore == pytest.approx(-up.subscore)
    assert up_rev.subscore < -0.3 < 0.3 < down_rev.subscore
    assert "Rückschlag" in up_rev.reason and "Erholung" in down_rev.reason
    assert up_rev.inputs["mode"] == "reversal" and up.inputs["mode"] == "trend"
    assert trend_f.compute(_prices(30, 0.01), params, reverse=True).subscore is None


def test_macro_info_only_indicator_stays_out_of_score() -> None:
    wave = [50 + (i % 7) * 0.4 + i * 0.05 for i in range(100)]
    plain = macro_f.EconomyData("A", "A")
    plain.indicators["gdp"] = _ind("gdp", wave)
    with_info = macro_f.EconomyData("A", "A")
    with_info.indicators["gdp"] = _ind("gdp", wave)
    ppi = _ind("ppi", [float(i * i % 11) for i in range(100)], category="growth")
    ppi.info_only = True
    with_info.indicators["ppi"] = ppi
    assert macro_f.indicator_score(ppi, AS_OF, MP) is not None  # bewertbar, aber nur Info
    expected = macro_f.category_scores(plain, AS_OF, MP)
    got = macro_f.category_scores(with_info, AS_OF, MP)
    assert got["growth"].score == pytest.approx(expected["growth"].score)
    assert "ppi" not in got["growth"].inputs
    ppi.info_only = False
    assert macro_f.category_scores(with_info, AS_OF, MP)["growth"].score != pytest.approx(
        expected["growth"].score
    )
