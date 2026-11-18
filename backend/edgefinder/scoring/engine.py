"""Score-Engine: Faktoren je Asset und Profil berechnen, gewichten, speichern.

Gesamtscore = Σ (effektives Gewicht × Teilscore) × 10 in [-10, +10]. Fehlende Faktoren (kein
Teilscore) werden aus der Summe genommen, die übrigen Gewichte auf 1 renormiert; die Abdeckung
(Anteil der verfügbaren Gewichte am Profil) wird mitgespeichert. Alle Daten kommen über den
`DataStore` und enden am Stichtag (`as_of`), siehe dort.
"""

from __future__ import annotations

import json
import logging
import sqlite3
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, timedelta
from typing import Any

from edgefinder.config import (
    Asset,
    AssetClass,
    Config,
    ForexAsset,
    Profile,
    StockAsset,
)
from edgefinder.db import transaction
from edgefinder.scoring.data import DataStore
from edgefinder.scoring.factors import FactorResult, de, unavailable
from edgefinder.scoring.factors import aaii as aaii_factor
from edgefinder.scoring.factors import cot as cot_factor
from edgefinder.scoring.factors import earnings as earnings_factor
from edgefinder.scoring.factors import fundamentals as fundamentals_factor
from edgefinder.scoring.factors import insider as insider_factor
from edgefinder.scoring.factors import macro as macro_factor
from edgefinder.scoring.factors import retail_sentiment as retail_factor
from edgefinder.scoring.factors import seasonality as seasonality_factor
from edgefinder.scoring.factors import short_interest as short_factor
from edgefinder.scoring.factors import trend as trend_factor
from edgefinder.scoring.labels import label_for

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class Component:
    factor: str
    subscore: float | None
    weight: float
    effective_weight: float
    reason: str
    inputs: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class AssetScore:
    asset_id: str
    profile: str
    as_of: date
    score: float
    label: str
    coverage: float
    components: tuple[Component, ...]


def combine(
    weights: dict[str, float], results: dict[str, FactorResult]
) -> tuple[float, float, list[Component]] | None:
    """Gewichten mit Renormierung. Gibt (Score, Abdeckung, Komponenten) oder None (keine Daten)."""
    available = {f: w for f, w in weights.items() if results[f].subscore is not None and w > 0}
    total_weight = sum(weights.values())
    covered = sum(available.values())
    components: list[Component] = []
    for factor, weight in weights.items():
        result = results[factor]
        effective = weight / covered if factor in available else 0.0
        components.append(
            Component(factor, result.subscore, weight, effective, result.reason, result.inputs)
        )
    if covered <= 0:
        return None
    score = 10.0 * sum(
        c.effective_weight * c.subscore for c in components if c.subscore is not None
    )
    return max(-10.0, min(10.0, score)), covered / total_weight, components


class _Context:
    """Zwischenspeicher je Stichtag: Währungs-/Volkswirtschaftsdaten gelten für mehrere Assets."""

    def __init__(self) -> None:
        self.memo: dict[tuple, Any] = {}

    def get(self, key: tuple, build: Callable[[], Any]) -> Any:
        if key not in self.memo:
            self.memo[key] = build()
        return self.memo[key]


class ScoreEngine:
    def __init__(self, config: Config, conn: sqlite3.Connection) -> None:
        self.config = config
        self.conn = conn
        self.store = DataStore(conn, config)

    # ------------------------------------------------------------------ Faktoren
    def _factors(
        self, asset: Asset, profile_key: str, as_of: date, ctx: _Context
    ) -> dict[str, FactorResult]:
        profile = self.config.profiles[profile_key]
        weights = profile.weights[asset.asset_class]
        compute: dict[str, Callable[[], FactorResult]] = {}
        params = profile.params
        dates, closes = self.store.prices(asset.id, as_of)

        compute["trend"] = lambda: trend_factor.compute(closes, params.get("trend", {}))
        compute["seasonality"] = lambda: seasonality_factor.compute(
            dates, closes, as_of, params.get("seasonality", {})
        )
        compute["aaii"] = lambda: aaii_factor.compute(
            self.store.aaii(as_of), params.get("aaii", {})
        )

        match asset:
            case ForexAsset():
                compute["cot"] = lambda: self._forex_cot(asset, profile, as_of, ctx)
                compute["macro"] = lambda: self._forex_macro(asset, profile_key, as_of, ctx)
                compute["retail_sentiment"] = lambda: self._retail(asset.myfxbook, profile, as_of)
            case StockAsset():
                compute["fundamentals"] = lambda: fundamentals_factor.compute(
                    self.store.fundamentals(asset.ticker, as_of),
                    dates,
                    closes,
                    as_of,
                    params.get("fundamentals", {}),
                )
                compute["earnings"] = lambda: earnings_factor.compute(
                    self.store.earnings(asset.ticker, as_of), params.get("earnings", {})
                )
                compute["short_interest"] = lambda: short_factor.compute(
                    self.store.short_interest(asset.ticker, as_of), params.get("short_interest", {})
                )
                compute["insider"] = lambda: self._insider(asset, profile, as_of)
            case _:  # Index, Rohstoff
                compute["cot"] = lambda: self._single_cot(asset.cftc_code, profile, as_of)
                compute["retail_sentiment"] = lambda: self._retail(asset.myfxbook, profile, as_of)
                compute["macro"] = lambda: self._other_macro(asset, profile_key, as_of, ctx)

        results: dict[str, FactorResult] = {}
        for factor in weights:
            try:
                results[factor] = compute[factor]()
            except Exception:
                log.exception("Faktor %s für %s fehlgeschlagen", factor, asset.id)
                results[factor] = unavailable(f"{factor}: Berechnung fehlgeschlagen.")
        return results

    def _retail(self, symbol: str | None, profile: Profile, as_of: date) -> FactorResult:
        if symbol is None:
            return unavailable("Retail-Sentiment: für dieses Asset nicht verfügbar.")
        return retail_factor.compute(
            self.store.retail(symbol, as_of), as_of, profile.params.get("retail_sentiment", {})
        )

    def _single_cot(
        self, code: str | None, profile: Profile, as_of: date, name: str = ""
    ) -> FactorResult:
        if code is None:
            return unavailable("COT: für dieses Asset gibt es keinen CFTC-Report.")
        return cot_factor.compute(self.store.cot(code, as_of), profile.params.get("cot", {}), name)

    def _forex_cot(
        self, asset: ForexAsset, profile: Profile, as_of: date, ctx: _Context
    ) -> FactorResult:
        sides: dict[str, FactorResult] = {}
        for ccy in (asset.base, asset.quote):
            sides[ccy] = ctx.get(
                ("cot", ccy, profile.label),
                lambda ccy=ccy: self._single_cot(
                    self.config.currencies[ccy].cftc_code, profile, as_of, ccy
                ),
            )
        base, quote = sides[asset.base], sides[asset.quote]
        if base.subscore is None or quote.subscore is None:
            return unavailable(
                f"COT: für {asset.base} oder {asset.quote} fehlen Daten.",
                **{asset.base: base.inputs, asset.quote: quote.inputs},
            )
        # Differenz/2 (= Mittel aus Basis und umgekehrter Quote): bleibt in [-1, 1] und sättigt
        # nur, wenn beide Seiten extrem gegensätzlich stehen (Differenz zweier Perzentil-
        # Scores erreichte sonst schon bei moderaten Werten ±1).
        score = (base.subscore - quote.subscore) / 2
        reason = (
            f"Cross aus Währungspositionierung: ({asset.base} {de(base.subscore, '+.2f')} minus "
            f"{asset.quote} {de(quote.subscore, '+.2f')}) / 2 = {de(score, '+.2f')}. "
            f"{base.reason} {quote.reason}"
        )
        return FactorResult(
            score,
            reason,
            {
                asset.base: {"subscore": round(base.subscore, 4), **base.inputs},
                asset.quote: {"subscore": round(quote.subscore, 4), **quote.inputs},
            },
        )

    def _economy(self, code: str, as_of: date, ctx: _Context) -> macro_factor.EconomyData:
        return ctx.get(("economy", code), lambda: self.store.economy(code, as_of))

    def _forex_macro(
        self, asset: ForexAsset, profile_key: str, as_of: date, ctx: _Context
    ) -> FactorResult:
        params = self.config.profiles[profile_key].params.get("macro", {})
        base = self._economy(self.config.currencies[asset.base].economy, as_of, ctx)
        quote = self._economy(self.config.currencies[asset.quote].economy, as_of, ctx)
        return macro_factor.compute_forex((asset.base, base), (asset.quote, quote), as_of, params)

    def _other_macro(
        self, asset: Asset, profile_key: str, as_of: date, ctx: _Context
    ) -> FactorResult:
        params = self.config.profiles[profile_key].params.get("macro", {})
        if asset.asset_class is AssetClass.INDEX:
            economy = self._economy(asset.economy, as_of, ctx)  # type: ignore[union-attr]
            return macro_factor.compute_economy(economy, as_of, params)
        us = self._economy("US", as_of, ctx)
        return macro_factor.compute_commodity(
            asset.macro_driver,  # type: ignore[union-attr]
            us,
            as_of,
            params,
        )

    def _insider(self, asset: StockAsset, profile: Profile, as_of: date) -> FactorResult:
        trades, covered = self.store.insider(asset.ticker, as_of)
        return insider_factor.compute(trades, covered, as_of, profile.params.get("insider", {}))

    # ------------------------------------------------------------------ Berechnung
    def score_asset(
        self, asset: Asset, profile_key: str, as_of: date, ctx: _Context | None = None
    ) -> AssetScore | None:
        ctx = ctx or _Context()
        dates, _ = self.store.prices(asset.id, as_of)
        if not dates:  # ohne Kurse kein Score (Asset existierte noch nicht / nicht geladen)
            return None
        results = self._factors(asset, profile_key, as_of, ctx)
        weights = self.config.profiles[profile_key].weights[asset.asset_class]
        combined = combine(weights, results)
        if combined is None:
            return None
        score, coverage, components = combined
        return AssetScore(
            asset.id,
            profile_key,
            as_of,
            score,
            label_for(score, self.config.scoring),
            coverage,
            tuple(components),
        )

    def persist(self, result: AssetScore, origin: str, computed_at: datetime | None = None) -> None:
        """Ein Eintrag je Asset/Profil/Tag; erneuter Lauf überschreibt (idempotent)."""
        stamp = (computed_at or datetime.now(UTC)).isoformat(timespec="seconds")
        with transaction(self.conn):
            row = self.conn.execute(
                "INSERT INTO scores (asset_id, profile, date, score, label, coverage, origin,"
                " computed_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)"
                " ON CONFLICT (asset_id, profile, date) DO UPDATE SET score = excluded.score,"
                " label = excluded.label, coverage = excluded.coverage, origin = excluded.origin,"
                " computed_at = excluded.computed_at RETURNING id",
                (
                    result.asset_id,
                    result.profile,
                    result.as_of.isoformat(),
                    result.score,
                    result.label,
                    result.coverage,
                    origin,
                    stamp,
                ),
            ).fetchone()
            score_id = row[0]
            self.conn.execute("DELETE FROM score_components WHERE score_id = ?", (score_id,))
            self.conn.executemany(
                "INSERT INTO score_components (score_id, factor, subscore, weight,"
                " effective_weight, reason, inputs) VALUES (?, ?, ?, ?, ?, ?, ?)",
                [
                    (
                        score_id,
                        c.factor,
                        c.subscore,
                        c.weight,
                        c.effective_weight,
                        c.reason,
                        json.dumps(c.inputs, ensure_ascii=False, default=str),
                    )
                    for c in result.components
                ],
            )

    def run_day(self, as_of: date, asset_ids: Iterable[str] | None = None) -> list[AssetScore]:
        """Alle (oder die gewählten) Assets mit allen Profilen für einen Stichtag."""
        wanted = set(asset_ids) if asset_ids is not None else None
        origin = "live" if as_of >= datetime.now(UTC).date() else "backfill"
        results: list[AssetScore] = []
        contexts = {profile: _Context() for profile in self.config.profiles}
        for asset in self.config.assets.all():
            if wanted is not None and asset.id not in wanted:
                continue
            for profile in self.config.profiles:
                result = self.score_asset(asset, profile, as_of, contexts[profile])
                if result is None:
                    log.warning("%s/%s am %s: keine Daten, kein Score", asset.id, profile, as_of)
                    continue
                self.persist(result, origin)
                results.append(result)
        return results

    def run_range(self, start: date, end: date, asset_ids: Iterable[str] | None = None) -> int:
        """Rückwärtsberechnung (Backtest, Etappe h): jeder Werktag von `start` bis `end`."""
        count = 0
        day = start
        while day <= end:
            if day.weekday() < 5:
                count += len(self.run_day(day, asset_ids))
            day += timedelta(days=1)
        return count
