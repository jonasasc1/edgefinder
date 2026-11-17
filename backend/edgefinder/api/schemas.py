"""Pydantic-Schemas der JSON-API (alle Zeiten UTC/ISO 8601, Tagesdaten YYYY-MM-DD)."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel


class ProfileOut(BaseModel):
    key: str
    label: str
    horizon: str


class ScoreOut(BaseModel):
    date: str
    score: float
    label: str
    coverage: float
    change_1d: float | None = None
    change_7d: float | None = None


class AssetOut(BaseModel):
    id: str
    name: str
    asset_class: str
    scores: dict[str, ScoreOut | None]  # je Profil


class ComponentOut(BaseModel):
    factor: str
    subscore: float | None
    weight: float
    effective_weight: float
    reason: str
    inputs: dict[str, Any]


class ProfileDetailOut(BaseModel):
    score: ScoreOut
    components: list[ComponentOut]


class PriceOut(BaseModel):
    date: str
    close: float
    change_1d_pct: float | None = None


class AssetDetailOut(BaseModel):
    id: str
    name: str
    asset_class: str
    last_price: PriceOut | None
    profiles: dict[str, ProfileDetailOut | None]


class HistoryOut(BaseModel):
    asset_id: str
    scores: dict[str, list[tuple[str, float]]]  # Profil → [(Datum, Score)]
    prices: list[tuple[str, float]]  # [(Datum, Schlusskurs)]


class CotPointOut(BaseModel):
    report_date: str
    long: int
    short: int
    net: int
    net_pct_oi: float | None
    open_interest: int | None


class CotSeriesOut(BaseModel):
    contract_code: str
    name: str  # Währung bzw. Asset
    points: list[CotPointOut]


class CotOut(BaseModel):
    asset_id: str
    series: list[CotSeriesOut]


class RetailPointOut(BaseModel):
    observed_at: str
    long_pct: float
    short_pct: float


class AaiiPointOut(BaseModel):
    week_date: str
    bullish: float
    neutral: float
    bearish: float


class SentimentOut(BaseModel):
    asset_id: str
    retail_symbol: str | None
    retail: list[RetailPointOut]
    aaii: list[AaiiPointOut]  # marktweit; leer bei Forex/Rohstoffen


class MacroIndicatorOut(BaseModel):
    key: str
    label: str
    category: str
    higher_is: str
    date: str | None
    value: float | None  # nach `transform` (z. B. Vorjahresveränderung in %)
    change: float | None
    score: float | None  # [-1, +1] aus Sicht der Währung/des Marktes (None = zu wenig Daten)
    fresh: bool


class MacroEconomyOut(BaseModel):
    code: str
    name: str
    indicators: list[MacroIndicatorOut]


class MacroOut(BaseModel):
    change_months: int
    economies: list[MacroEconomyOut]


class FactOut(BaseModel):
    concept: str
    unit: str
    period_start: str
    period_end: str
    value: float
    filed: str


class EarningsOut(BaseModel):
    earnings_date: str
    eps_estimate: float | None
    eps_actual: float | None
    surprise_pct: float | None


class ShortInterestOut(BaseModel):
    settlement_date: str
    short_interest: float
    days_to_cover: float | None


class InsiderOut(BaseModel):
    transaction_date: str
    owner_name: str
    owner_title: str | None
    code: str
    shares: float
    price: float | None


class FundamentalsOut(BaseModel):
    asset_id: str
    kind: Literal["stock", "macro", "none"]
    facts: list[FactOut] = []
    earnings: list[EarningsOut] = []
    short_interest: list[ShortInterestOut] = []
    insider: list[InsiderOut] = []
    macro: MacroOut | None = None


class ChangeOut(BaseModel):
    asset_id: str
    name: str
    asset_class: str
    profile: str
    score: float
    previous_score: float
    delta: float
    label: str
    previous_label: str
    label_changed: bool


class ChangesOut(BaseModel):
    since: str
    date: str | None
    changes: list[ChangeOut]


class SourceStatusOut(BaseModel):
    source: str
    enabled: bool
    last_success: str | None
    last_run_status: str | None
    last_run_at: str | None
    last_error: str | None
    stale_after_hours: int
    stale: bool


class StatusOut(BaseModel):
    now: str
    sources: list[SourceStatusOut]
    last_score_date: str | None
    last_scored_at: str | None
