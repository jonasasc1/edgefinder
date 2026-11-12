"""Laden und Validieren von config.yaml sowie der Secrets aus .env."""

from __future__ import annotations

import os
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


class RetryConfig(_Model):
    attempts: int = Field(ge=1, le=10)
    backoff_seconds: float = Field(gt=0)
    max_backoff_seconds: float = Field(gt=0)
    timeout_seconds: float = Field(gt=0)


class SourceConfig(_Model):
    enabled: bool = True
    schedule: str
    stale_after_hours: int = Field(gt=0)
    min_interval_seconds: float = Field(ge=0)
    daily_request_limit: int | None = Field(default=None, gt=0)
    retry: RetryConfig | None = None
    options: dict[str, Any] = Field(default_factory=dict)


class Indicator(_Model):
    label: str
    source: Literal["fred", "eurostat", "ecb"]
    series: str
    category: Literal["growth", "inflation", "labor", "rates"]
    transform: Literal["level", "yoy", "diff"]
    higher_is: Literal["bullish", "bearish"]


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
    schedule: str
    labels: tuple[ScoreLabel, ...]

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


class Profile(_Model):
    label: str
    horizon: str
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
