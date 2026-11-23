"""Pydantic-Schemas der JSON-API (alle Zeiten UTC/ISO 8601, Tagesdaten YYYY-MM-DD)."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel


class ProfileNoticeOut(BaseModel):
    asset_classes: list[str]
    level: str
    text: str


class ProfileOut(BaseModel):
    key: str
    label: str
    horizon: str
    notices: list[ProfileNoticeOut] = []


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


class SparklinesOut(BaseModel):
    profile: str
    days: int
    series: dict[str, list[tuple[str, float]]]  # Asset → [(Datum, Score)]


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
    info_only: bool = False  # nur Anzeige, nicht im Score


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


Signal = Literal["bullish", "bearish", "neutral"]


class ScorecardTileOut(BaseModel):
    """Teilscore einer Gruppe (Technik, Sentiment, Institutionell, Makro) als −10…+10."""

    key: Literal["technical", "sentiment", "institutional", "macro"]
    label: str
    score: float | None  # gewichtetes Mittel der Faktor-Teilscores (effektive Gewichte) × 10
    weight: float  # Summe der effektiven Gewichte der Gruppe (Anteil am Gesamtscore)
    signal: Signal | None
    factors: list[str]  # Faktoren mit Daten, die in die Gruppe eingehen


class ScorecardMemberOut(BaseModel):
    """Einzelwert einer Misch-Zeile (Ersatz-PMI aus Regional-Fed-Umfragen), für den Tooltip."""

    label: str
    value: float
    date: str


class ScorecardRowOut(BaseModel):
    """Eine Tabellenzeile; nicht belegte Felder sind None (die Oberfläche zeigt „–“)."""

    key: str
    label: str
    side: str | None = None  # Währung/Volkswirtschaft bei Forex (Basis, Quote)
    unit: str = ""  # "%", "count", "k", "index", "x", "shares", "usd" oder leer
    change_unit: str | None = None  # None = wie `unit`; "pp" = Prozentpunkte
    value: float | None = None  # Actual
    previous: float | None = None  # Vorwert
    change: float | None = None  # Änderung zum Vorwert
    date: str | None = None
    signal: Signal | None = None
    score: float | None = None  # −1…+1
    long_pct: float | None = None  # Long-Anteil (COT, Retail, AAII bullish)
    short_pct: float | None = None
    percentile: float | None = (
        None  # COT: Perzentil der Netto-Position in der eigenen Historie (0–100)
    )
    estimate: float | None = None  # nur Earnings (EPS-Schätzung)
    surprise_pct: float | None = None  # nur Earnings
    text: str | None = None
    note: str | None = None  # Begründung aus der Engine (Tooltip)
    next_date: str | None = None  # nächster sicher bekannter Termin
    soon: bool = False  # nächster Termin liegt in den nächsten Tagen (Stern)
    info_only: bool = False  # Indikator nur zur Information, ohne Pille und nicht im Score
    expectation: float | None = None  # Modell-Erwartung (gleitender Durchschnitt, KEIN Konsens)
    surprise: float | None = None  # Actual − Modell-Erwartung, Einheit wie `unit`/`change_unit`
    display_only: bool = False  # nur Anzeige: Pille ist Lesart, geht nicht in den Score ein
    substitute: bool = False  # Ersatz (z. B. Regional-Fed-Umfragen statt ISM-PMI)
    members: list[ScorecardMemberOut] | None = None  # Einzelwerte einer Misch-Zeile
    counter_trend: bool = False  # Trend-Signal erwartet eine Bewegung gegen den Kurstrend (Umkehr)


class ScorecardSectionOut(BaseModel):
    key: str
    group: Literal["technical", "sentiment", "institutional", "macro"]
    label: str
    kind: Literal["indicator", "core", "crowd", "positioning", "earnings"]
    signal: Signal | None
    score: float | None  # −1…+1
    rating: str | None = (
        None  # Gruppenlabel aus dem Gruppenscore (scoring.labels), nur bei Makro-Kern
    )
    collapsed: bool = False  # „Weitere Indikatoren“: standardmäßig zugeklappt
    rows: list[ScorecardRowOut]
    empty_reason: str | None = None  # warum keine Zeilen da sind
    in_score: bool = True  # False: nur zur Information, geht nicht in den Score ein


class AgreementOut(BaseModel):
    """Wie viele der Faktoren (und welcher Gewichtsanteil) zeigen in Richtung des Gesamtscores."""

    direction: Literal[-1, 0, 1]  # Richtung des Gesamtscores (0 = exakt null)
    total: int  # Faktoren mit Daten
    bullish: int
    bearish: int
    neutral: int
    same: int  # Faktoren in Richtung des Gesamtscores
    weight_share: float | None  # Gewichtsanteil der gleichgerichteten Faktoren (0–1)
    bullish_share: float
    bearish_share: float
    threshold: float  # ab diesem Anteil gilt die Übereinstimmung als hoch
    high: bool


class ScorecardOut(BaseModel):
    asset_id: str
    profile: str
    as_of: str | None  # Datum des Scores
    signal_threshold: float
    agreement: AgreementOut | None = None
    tiles: list[ScorecardTileOut]
    sections: list[ScorecardSectionOut]


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


class CalibrationSummaryOut(BaseModel):
    """Evidenzstufe je Profil × Klasse (Richtungssignale, Kennwert-Horizont) für die Übersicht."""

    available: bool
    generated_at: str | None = None
    first_date: str | None = None
    data_through: str | None = None
    train_end: str | None = None
    min_t: float | None = None
    min_n_eff: float | None = None
    profiles: dict[str, dict[str, dict[str, Any]]] = {}


class AssetCalibrationOut(BaseModel):
    """Eichung des aktuellen Score-Bereichs eines Assets (Zahlen und Bausteine, kein Fließtext)."""

    asset_id: str
    profile: str
    asset_class: str
    as_of: str
    score: float
    label: str
    available: bool = False
    generated_at: str | None = None
    first_date: str | None = None
    data_through: str | None = None
    train_end: str | None = None
    min_t: float | None = None
    min_n_eff: float | None = None
    horizon: int | None = None
    horizons: list[int] = []
    bucket: dict[str, Any] | None = None
    # belegt | schwach | kein_vorteil | zu_wenig_daten | neutral
    evidence: str | None = None
    class_evidence: str | None = None  # Stufe der Klasse insgesamt (alle Richtungssignale)
    # Hinweis-Code: proven | weak | no_edge | few_data | neutral | missing
    note: str
    stats: dict[str, dict[str, Any]] | None = None  # Klasse + Bereich: all/train/oos
    class_directional: dict[str, dict[str, Any]] | None = None
    by_horizon: dict[str, dict[str, Any]] = {}
    asset_stats: dict[str, dict[str, Any]] | None = None  # nur bei genug Daten
    asset_status: Literal["ok", "zu_wenig_daten"] | None = None
    asset_min_n_eff: float | None = None
    chart: list[dict[str, Any]] = []  # alle Bereiche der Klasse (Kennwert-Horizont)
    agreement: dict[str, Any] | None = None  # Eichung der aktuellen Faktor-Übereinstimmung


# ---------------------------------------------------------------------------- Bilanz (Forward-Test)
DriftStatus = Literal[
    "zu_frueh", "im_rahmen", "schwaecher", "besser", "gegenlaeufig", "ohne_eichung"
]


class TrackGroupOut(BaseModel):
    """Live-Bilanz einer Gruppe (Profil × Klasse, Kennwert-Horizont, wöchentliche Signale)."""

    profile: str
    asset_class: str
    horizon: int
    n: int
    n_eff: float
    weeks: int
    months: float
    hit: float | None = None
    base_hit: float | None = None
    edge: float | None = None  # Bruchteil (0,01 = 1 %)
    edge_ci: list[float] | None = None
    t: float | None = None
    mean: float | None = None
    cal_edge: float | None = None
    cal_edge_ci: list[float] | None = None
    cal_hit: float | None = None
    status: DriftStatus
    progress: float
    calibrated: bool
    buckets: dict[str, dict[str, Any]] = {}


class FactorDriftOut(BaseModel):
    profile: str
    asset_class: str
    factor: str
    n: int
    n_eff: float
    weeks: int
    ic: float | None = None
    ic_t: float | None = None
    backtest_ic: float | None = None
    status: str  # zu_frueh | im_rahmen | schwaecher | gegenlaeufig | kein_vergleich
    weeks_against: int
    warn: bool


class SeriesPointOut(BaseModel):
    date: str
    value: float


class TrackCriteriaOut(BaseModel):
    min_n_eff: float
    min_months: float
    min_weeks: int
    statuses: list[str]
    min_weeks_status: int
    min_n_eff_status: float


class TrackrecordOut(BaseModel):
    model_version: str
    generated_at: str
    today: str
    live_since: str | None = None
    evaluated: int
    evaluated_weekly: int
    open: int
    earliest_due: str | None = None  # Näherung (Werktage), nicht Börsenkalender
    reliable_from: str | None = None
    done_from: str | None = None
    calibration_date: str | None = None
    groups: list[TrackGroupOut]
    factors: list[FactorDriftOut]
    series: dict[str, dict[str, list[SeriesPointOut]]]
    progress: float
    calibrated_groups: int
    criteria: TrackCriteriaOut


class SignalHorizonOut(BaseModel):
    horizon_days: int
    status: Literal["ausgewertet", "laeuft"]
    due_date: str | None = None  # bei „laeuft“: voraussichtliches Ende (Näherung)
    exit_date: str | None = None
    return_pct: float | None = None
    hit: bool | None = None  # None = neutral oder offen


class AssetSignalOut(BaseModel):
    signal_date: str
    score: float
    label: str
    direction: Literal["bullish", "bearish", "neutral"]
    model_version: str
    horizons: list[SignalHorizonOut]


class AssetTrackrecordOut(BaseModel):
    asset_id: str
    profile: str
    model_version: str
    live_since: str | None = None
    evaluated: int  # Signale mit mindestens einem ausgewerteten Horizont
    open: int  # Signale ohne ausgewerteten Horizont
    primary_horizon: int
    class_status: (
        DriftStatus  # Drift-Status der Gruppe (Profil × Klasse): „zu früh“ = keine Aussage
    )
    signals: list[AssetSignalOut]
