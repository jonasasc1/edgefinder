"""Laden und Validieren von config.yaml sowie der Secrets aus .env."""

from __future__ import annotations

import os
from datetime import date
from enum import StrEnum
from functools import cached_property
from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

DEFAULT_CONFIG_PATH = Path("config.yaml")
CONFIG_ENV_VAR = "EDGEFINDER_CONFIG"


class AssetClass(StrEnum):
    FOREX = "forex"
    INDEX = "index"
    COMMODITY = "commodity"
    STOCK = "stock"


# Welche Teilscores es je Assetklasse gibt. Die Gewichte in den Profilen müssen genau
# diese Faktoren abdecken.
FACTORS: dict[AssetClass, frozenset[str]] = {
    AssetClass.FOREX: frozenset({"cot", "retail_sentiment", "macro", "trend", "seasonality"}),
    AssetClass.INDEX: frozenset(
        {"cot", "retail_sentiment", "macro", "trend", "seasonality", "aaii"}
    ),
    AssetClass.COMMODITY: frozenset({"cot", "retail_sentiment", "macro", "trend", "seasonality"}),
    AssetClass.STOCK: frozenset(
        {
            "fundamentals",
            "earnings",
            "trend",
            "short_interest",
            "insider",
            "seasonality",
            "aaii",
        }
    ),
}

WEIGHT_TOLERANCE = 1e-6


class _Model(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class ServerConfig(_Model):
    host: str
    port: int = Field(ge=1, le=65535)


class StorageConfig(_Model):
    database: Path
    raw_dir: Path
    raw_retention_days: int = Field(default=30, gt=0)


class RetryConfig(_Model):
    attempts: int = Field(ge=1, le=10)
    backoff_seconds: float = Field(gt=0)
    max_backoff_seconds: float = Field(gt=0)
    timeout_seconds: float = Field(gt=0)


class SourceConfig(_Model):
    enabled: bool = True
    # OnCalendar-Ausdruck oder Liste davon (mehrere Uhrzeiten mit verschiedenen Minuten)
    schedule: str | list[str]
    stale_after_hours: int = Field(gt=0)
    min_interval_seconds: float = Field(ge=0)
    daily_request_limit: int | None = Field(default=None, gt=0)
    retry: RetryConfig | None = None
    options: dict[str, Any] = Field(default_factory=dict)


class Indicator(_Model):
    label: str
    source: Literal["fred", "eurostat", "ecb", "ons", "statcan", "abs", "imf"]
    series: str
    category: Literal["growth", "inflation", "labor", "rates"]
    transform: Literal["level", "yoy", "diff"]
    higher_is: Literal["bullish", "bearish"]
    # Geschätzte Verzögerung (Tage ab Periodenbeginn) bis zur Veröffentlichung, nur für Serien
    # ohne Vintages; None = Schätzung nach Frequenz (scoring/data.py)
    publication_lag_days: int | None = Field(default=None, gt=0)
    # Nur Info: wird angezeigt (Scorecard, Makro-Seite), geht aber weder in Teilscore noch in das
    # Kategorie-Mittel ein
    info_only: bool = False


class Economy(_Model):
    name: str
    indicators: dict[str, Indicator] = Field(default_factory=dict)


class Currency(_Model):
    economy: str
    cftc_code: str | None = None


class ForexAsset(_Model):
    id: str
    name: str
    base: str
    quote: str
    yfinance: str
    myfxbook: str | None = None

    asset_class: Literal[AssetClass.FOREX] = AssetClass.FOREX


class IndexAsset(_Model):
    id: str
    name: str
    economy: str
    yfinance: str
    cftc_code: str | None = None
    myfxbook: str | None = None

    asset_class: Literal[AssetClass.INDEX] = AssetClass.INDEX


class CommodityAsset(_Model):
    id: str
    name: str
    yfinance: str
    cftc_code: str | None = None
    myfxbook: str | None = None
    macro_driver: Literal["safe_haven", "cyclical"] | None = None

    asset_class: Literal[AssetClass.COMMODITY] = AssetClass.COMMODITY


class StockAsset(_Model):
    id: str
    name: str
    ticker: str
    yfinance: str | None = None

    asset_class: Literal[AssetClass.STOCK] = AssetClass.STOCK

    @property
    def price_symbol(self) -> str:
        return self.yfinance or self.ticker


Asset = ForexAsset | IndexAsset | CommodityAsset | StockAsset


class AssetsConfig(_Model):
    forex: tuple[ForexAsset, ...] = ()
    indices: tuple[IndexAsset, ...] = ()
    commodities: tuple[CommodityAsset, ...] = ()
    stocks: tuple[StockAsset, ...] = ()

    def all(self) -> tuple[Asset, ...]:
        return (*self.forex, *self.indices, *self.commodities, *self.stocks)


class ScoreLabel(_Model):
    min: float
    label: str


class ScoringConfig(_Model):
    schedule: str | list[str]
    # Version des Modells (Gewichte, Faktoren, Labels). Bei JEDER Änderung daran erhöhen: Scores und
    # Live-Auswertungen tragen sie mit, damit ein Umbau die Live-Bilanz nicht vermischt.
    model_version: str = Field(default="2026-11-21", min_length=1, max_length=40)
    labels: tuple[ScoreLabel, ...]
    # Scorecard (Detailseite): ab diesem |Teilscore| (−1…+1) gilt ein Signal als bullish/bearish.
    signal_threshold: float = Field(default=0.15, gt=0, lt=1)
    # Earnings: Überraschung innerhalb ±x % gilt als neutral.
    earnings_neutral_pct: float = Field(default=1.0, ge=0)

    @model_validator(mode="after")
    def _check_labels(self) -> ScoringConfig:
        mins = [entry.min for entry in self.labels]
        if not mins:
            raise ValueError("scoring.labels darf nicht leer sein")
        if mins != sorted(mins, reverse=True):
            raise ValueError("scoring.labels müssen absteigend nach `min` sortiert sein")
        if mins[-1] > -10:
            raise ValueError("scoring.labels: das letzte Label muss bei min = -10 beginnen")
        return self

    def label_for(self, score: float) -> str:
        for entry in self.labels:
            if score >= entry.min:
                return entry.label
        return self.labels[-1].label


class ProfileNotice(_Model):
    """Hinweis zu einem Profil für bestimmte Assetklassen; Eintrag entfernen = Hinweis weg."""

    asset_classes: list[AssetClass] = Field(min_length=1)
    level: Literal["info"] = "info"
    text: str = Field(min_length=1)


class Profile(_Model):
    label: str
    horizon: str
    notices: list[ProfileNotice] = Field(default_factory=list)
    params: dict[str, dict[str, Any]] = Field(default_factory=dict)
    weights: dict[AssetClass, dict[str, float]]

    @model_validator(mode="after")
    def _check_weights(self) -> Profile:
        for asset_class in AssetClass:
            weights = self.weights.get(asset_class)
            if weights is None:
                raise ValueError(f"Gewichte für Assetklasse '{asset_class}' fehlen")
            expected = FACTORS[asset_class]
            if set(weights) != expected:
                missing = sorted(expected - set(weights))
                unknown = sorted(set(weights) - expected)
                raise ValueError(
                    f"Gewichte für '{asset_class}': fehlend {missing}, unbekannt {unknown}"
                )
            if any(weight < 0 for weight in weights.values()):
                raise ValueError(f"Gewichte für '{asset_class}' dürfen nicht negativ sein")
            total = sum(weights.values())
            if abs(total - 1.0) > WEIGHT_TOLERANCE:
                raise ValueError(
                    f"Gewichte für '{asset_class}' summieren sich zu {total:.4f} statt 1"
                )
        return self


class CalibrationConfig(_Model):
    """Regeln der Eichung (`edgefinder calibrate`) und der Evidenzstufen; nichts davon im Code."""

    train_end: date = date(2019, 12, 31)  # Training = Stichtage ≤ train_end, Out-of-Sample danach
    min_t: float = Field(default=2.0, gt=0)  # „belegt“: t des Vorteils (mit n_eff) mindestens
    min_n_eff: float = Field(default=30.0, gt=0)  # „belegt“: n_eff Gesamt mindestens
    min_n_eff_period: float = Field(default=10.0, gt=0)  # „belegt“: n_eff je Training und OOS
    floor_n_eff: float = Field(default=5.0, gt=0)  # darunter (Gesamt/Training/OOS): zu wenig Daten
    asset_min_n_eff: float = Field(default=30.0, gt=0)  # Einzel-Asset-Kennzahlen erst ab hier
    confidence_z: float = Field(default=1.96, gt=0)  # Breite des Konfidenzbands (95 %)
    agreement_threshold: float = Field(default=0.7, gt=0, le=1)  # „hohe Übereinstimmung“ ab Anteil
    # Übereinstimmungs-Gruppen sind 2 Profile × 4 Klassen = 8 Tests: strengeres t (Bonferroni,
    # α = 0,05/8 zweiseitig ≈ 2,7), sonst käme ein Zufallstreffer zu leicht als „belegt“ durch.
    agreement_min_t: float = Field(default=2.7, gt=0)

    @model_validator(mode="after")
    def _check(self) -> CalibrationConfig:
        if not self.floor_n_eff <= self.min_n_eff_period <= self.min_n_eff:
            raise ValueError("calibration: floor_n_eff ≤ min_n_eff_period ≤ min_n_eff nötig")
        return self


class BacktestConfig(_Model):
    """Backfill (Stichtage) und Auswertung des Backtests (Etappe h)."""

    # Wochentag der Backfill-Stichtage (0 = Montag … 4 = Freitag); None = jeder Werktag
    score_weekday: int | None = Field(default=4, ge=0, le=4)
    start: date = date(2013, 1, 1)  # frühester Stichtag des Backfills
    output_dir: Path = Path("data/backtest")
    # Horizonte in Handelstagen je Profil; `primary_horizon` ist der Kennwert in den Kurztabellen
    horizons: dict[str, tuple[int, ...]] = Field(
        default_factory=lambda: {"swing": (5, 10, 20), "long_term": (20, 60, 120)}
    )
    primary_horizon: dict[str, int] = Field(default_factory=lambda: {"swing": 10, "long_term": 60})
    min_signals: int = Field(default=30, ge=1)  # darunter wird ein Wert als „zu wenig“ markiert
    calibration_file: Path = Path(
        "docs/calibration.json"
    )  # versionierte Eichung (ohne Backfill-DB)
    calibration: CalibrationConfig = Field(default_factory=CalibrationConfig)

    @model_validator(mode="after")
    def _check_horizons(self) -> BacktestConfig:
        for profile, days in self.horizons.items():
            if not days or any(d < 1 for d in days):
                raise ValueError(f"backtest.horizons.{profile}: Handelstage ≥ 1 nötig")
            primary = self.primary_horizon.get(profile)
            if primary is not None and primary not in days:
                raise ValueError(f"backtest.primary_horizon.{profile} muss in horizons stehen")
        return self


class MaintenanceConfig(_Model):
    """Wartungsjobs (Timer werden mit `edgefinder gen-systemd` erzeugt)."""

    cleanup_schedule: str = "Sun *-*-* 03:30:00 Europe/Vienna"
    # Forward-Auswertung der Live-Signale (`edgefinder evaluate`), täglich nach dem Score-Lauf
    evaluate_schedule: str = "*-*-* 00:10:00 Europe/Vienna"
    evaluate_stale_after_hours: int = Field(default=48, ge=1)
    # Eichung neu erzeugen (`edgefinder maintain`): Backfill ergänzen, calibrate, Drift-Bericht
    maintain_schedule: str = "Sun *-*-* 04:30:00 Europe/Vienna"
    maintain_stale_after_hours: int = Field(default=216, ge=1)


class FactorDriftConfig(_Model):
    """Faktor-Drift: Spearman-IC je Faktor live gegen Backtest (nur Meldung, keine Änderung)."""

    min_n_eff: float = Field(default=20.0, gt=0)  # darunter „zu früh“
    min_weeks: int = Field(default=8, ge=1)  # Stichtage (Wochen) mit Auswertung
    min_abs_ic: float = Field(default=0.03, ge=0)  # schwächerer Backtest-IC: kein Vergleich
    counter_t: float = Field(default=1.5, gt=0)  # gegenläufig: falsches Vorzeichen und |t| ≥
    warn_weeks: int = Field(default=4, ge=1)  # Warnung ab so vielen Wochen in Folge gegenläufig


class DoneConfig(_Model):
    """Kriterien „geeicht“: Aussage belastbar geprüft – ausdrücklich NICHT „profitabel“."""

    min_n_eff: float = Field(default=30.0, gt=0)  # je Gruppe (Profil × Klasse) live n_eff
    min_months: float = Field(default=6.0, gt=0)  # Live-Zeitraum der Gruppe in Monaten
    min_weeks: int = Field(default=26, ge=1)  # Stichtage (Wochen) mit Auswertung
    statuses: tuple[str, ...] = ("im_rahmen", "besser")  # erlaubter Drift-Status


class LiveConfig(_Model):
    """Live-Bilanz (Forward-Test) und Drift-Status gegen die Eichung (`backtest/live.py`)."""

    min_n_eff: float = Field(default=10.0, gt=0)  # darunter Drift-Status „zu_frueh“
    min_weeks: int = Field(
        default=8, ge=1
    )  # Stichtage (Wochen): Signale derselben Woche sind nicht unabhängig
    counter_t: float = Field(default=2.0, gt=0)  # „gegenläufig“: Vorteil < 0 und t ≤ −counter_t
    chart_min_weeks: int = Field(default=4, ge=2)  # Zeitverlauf erst ab so vielen Wochen
    factor: FactorDriftConfig = Field(default_factory=FactorDriftConfig)
    done: DoneConfig = Field(default_factory=DoneConfig)


ADMIN_JOB_NAMES = ("review", "maintain", "score", "evaluate")


class AdminConfig(_Model):
    """Admin-Bereich: Allowlist der Jobs, die aus der Weboberfläche angestoßen werden dürfen.

    Bewusst nur lesende/rechnende Jobs: keine Fetcher (Rate-Limits), kein Rebuild, kein Löschen.
    """

    jobs: list[Literal["review", "maintain", "score", "evaluate"]] = Field(
        default_factory=lambda: list(ADMIN_JOB_NAMES)
    )
    cooldown_minutes: int = Field(default=10, ge=0, le=1440)
    cooldown_overrides: dict[str, int] = Field(default_factory=lambda: {"review": 2})
    max_queue: int = Field(default=4, ge=1, le=20)
    log_tail_bytes: int = Field(default=4096, ge=256, le=8192)

    @model_validator(mode="after")
    def _check(self) -> AdminConfig:
        if unknown := sorted(set(self.cooldown_overrides) - set(ADMIN_JOB_NAMES)):
            raise ValueError(f"admin.cooldown_overrides: unbekannter Job {', '.join(unknown)}")
        return self

    def cooldown_for(self, job: str) -> int:
        return self.cooldown_overrides.get(job, self.cooldown_minutes)


class AuthConfig(_Model):
    """Identität der Benutzer (Cloudflare Access); Team-Domain und AUD stehen nur in der .env."""

    # header: E-Mail aus Cf-Access-Authenticated-User-Email (Firewall lässt nur cloudflared durch).
    # jwt: Signatur des Cf-Access-Jwt-Assertion prüfen (braucht CF_ACCESS_TEAM_DOMAIN + _AUD).
    # off: keine Identität aus Headern (nur dev_email).
    # Sind beide .env-Werte gesetzt, gilt automatisch der strikte JWT-Modus.
    mode: Literal["header", "jwt", "off"] = "header"
    dev_email: str | None = None  # nur lokale Entwicklung: Ersatz, wenn kein Header kommt
    # Zusätzliche öffentliche Hostnamen für die Origin-Prüfung (nur nötig, falls cloudflared den
    # Host-Header umschreibt, z. B. `httpHostHeader`); Host und X-Forwarded-Host gelten immer.
    public_hosts: list[str] = Field(default_factory=list)


class Config(_Model):
    server: ServerConfig
    storage: StorageConfig
    sources: dict[str, SourceConfig]
    retry: RetryConfig
    economies: dict[str, Economy]
    currencies: dict[str, Currency]
    assets: AssetsConfig
    scoring: ScoringConfig
    profiles: dict[str, Profile]
    auth: AuthConfig = Field(default_factory=AuthConfig)
    admin: AdminConfig = Field(default_factory=AdminConfig)
    backtest: BacktestConfig = Field(default_factory=BacktestConfig)
    maintenance: MaintenanceConfig = Field(default_factory=MaintenanceConfig)
    live: LiveConfig = Field(default_factory=LiveConfig)

    @model_validator(mode="after")
    def _check_references(self) -> Config:
        errors: list[str] = []

        seen: set[str] = set()
        for asset in self.assets.all():
            if asset.id in seen:
                errors.append(f"Asset-ID '{asset.id}' ist doppelt vergeben")
            seen.add(asset.id)

        for code, currency in self.currencies.items():
            if currency.economy not in self.economies:
                errors.append(f"Währung {code}: unbekannte Volkswirtschaft '{currency.economy}'")

        for pair in self.assets.forex:
            for side in (pair.base, pair.quote):
                if side not in self.currencies:
                    errors.append(f"Forex {pair.id}: unbekannte Währung '{side}'")
            if pair.base == pair.quote:
                errors.append(f"Forex {pair.id}: Basis- und Kurswährung sind identisch")

        for index in self.assets.indices:
            if index.economy not in self.economies:
                errors.append(f"Index {index.id}: unbekannte Volkswirtschaft '{index.economy}'")

        if not self.profiles:
            errors.append("Mindestens ein Profil ist erforderlich")

        if errors:
            raise ValueError("; ".join(errors))
        return self

    @cached_property
    def assets_by_id(self) -> dict[str, Asset]:
        return {asset.id: asset for asset in self.assets.all()}

    @property
    def data_dir(self) -> Path:
        """Schreibbares Datenverzeichnis (Ordner der Datenbank): Eichung/Berichte der Wartung."""
        return self.storage.database.parent

    def retry_for(self, source: str) -> RetryConfig:
        """Retry-Einstellungen einer Quelle, sonst der globale Standard."""
        return self.sources[source].retry or self.retry


class Secrets(BaseSettings):
    """Secrets aus der Umgebung bzw. .env. Werte nie loggen oder ausgeben."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    fred_api_key: SecretStr | None = None
    cftc_app_token: SecretStr | None = None
    myfxbook_email: SecretStr | None = None
    myfxbook_password: SecretStr | None = None
    contact_email: SecretStr | None = None
    # Cloudflare Access (JWT-Modus): Team-Domain (…cloudflareaccess.com) und Application-AUD-Tag
    cf_access_team_domain: str | None = None
    cf_access_aud: SecretStr | None = None

    @field_validator("*", mode="before")
    @classmethod
    def _empty_as_missing(cls, value: object) -> object:
        # Leere Einträge aus der .env-Vorlage gelten als „nicht gesetzt“.
        if isinstance(value, str) and not value.strip():
            return None
        return value


def config_path() -> Path:
    return Path(os.environ.get(CONFIG_ENV_VAR) or DEFAULT_CONFIG_PATH)


def load_config(path: Path | None = None) -> Config:
    path = path or config_path()
    with path.open(encoding="utf-8") as handle:
        data = yaml.safe_load(handle)
    if not isinstance(data, dict):
        raise ValueError(f"{path}: Konfiguration muss ein YAML-Mapping sein")
    return Config.model_validate(data)


def load_secrets(env_file: Path | None = None) -> Secrets:
    if env_file is not None:
        return Secrets(_env_file=env_file)
    return Secrets()
