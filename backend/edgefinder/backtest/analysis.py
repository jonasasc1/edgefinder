"""Backtest-Auswertung: gespeicherte Scores gegen die spätere Kursentwicklung.

Ablauf: Scores (Tabelle `scores`, Stichtage aus dem Backfill) → Forward-Rendite je Stichtag und
Horizont (Handelstage, aus der Kursreihe des Assets) → Kennzahlen je Profil, Assetklasse,
Horizont und Score-Bereich (Bucket aus `scoring.labels`).

Look-Ahead: Der Score eines Stichtags kennt nur Daten bis zu diesem Tag (siehe `scoring/data.py`).
Die Forward-Rendite startet am letzten Schlusskurs ≤ Stichtag und endet `h` Handelstage der
Kursreihe später; spätere Kurse fließen nie in den Score ein. Ein Fenster, das über den letzten
vorhandenen Kurs hinausreicht, wird ausgelassen (keine Teilfenster).
"""

from __future__ import annotations

import sqlite3
import statistics
from bisect import bisect_right
from collections import defaultdict
from dataclasses import dataclass
from datetime import UTC, date, datetime
from typing import Any

from edgefinder.backtest.stats import (
    diff_t,
    mean_or_none,
    median_or_none,
    spearman,
    t_from_corr,
)
from edgefinder.config import AssetClass, Config, ScoreLabel

MAX_STALE_DAYS = 7  # letzter Kurs darf höchstens so weit vor dem Stichtag liegen
MIN_CROSS_SECTION = 5  # Assets je Stichtag für den Querschnitts-IC
ALL = "all"
STEP_TRADING_DAYS = 5  # Abstand wöchentlicher Stichtage in Handelstagen (Überlappungsmaß)


@dataclass(frozen=True)
class Observation:
    asset_id: str
    asset_class: str
    profile: str
    day: str
    score: float
    coverage: float
    score_id: int
    forward: dict[int, float | None]  # Handelstage → einfache Rendite (None = nicht verfügbar)


@dataclass(frozen=True)
class Bucket:
    label: str
    low: float
    high: float  # exklusiv (letzter Bucket inklusive +10)
    direction: int  # +1 bullish, −1 bearish, 0 neutral (enthält die Null)


def buckets_from_labels(labels: tuple[ScoreLabel, ...]) -> list[Bucket]:
    """Score-Bereiche aus `scoring.labels` (absteigend sortiert). Richtung: liegt die Null im
    Bereich → neutral, sonst nach Vorzeichen."""
    out: list[Bucket] = []
    upper = 10.0
    for entry in labels:
        low = entry.min
        direction = 1 if low >= 0 else (-1 if upper <= 0 else 0)
        out.append(Bucket(entry.label, low, upper, direction))
        upper = low
    return out


def bucket_of(score: float, buckets: list[Bucket]) -> Bucket:
    for bucket in buckets:
        if score >= bucket.low:
            return bucket
    return buckets[-1]


def forward_returns(
    dates: list[str], closes: list[float], as_of: str, horizons: tuple[int, ...]
) -> dict[int, float | None]:
    """Einfache Rendite vom letzten Kurs ≤ `as_of` bis `h` Handelstage später."""
    base = bisect_right(dates, as_of) - 1
    out: dict[int, float | None] = dict.fromkeys(horizons)
    if base < 0:
        return out
    gap = (date.fromisoformat(as_of) - date.fromisoformat(dates[base])).days
    if gap > MAX_STALE_DAYS or closes[base] <= 0:
        return out
    for h in horizons:
        if base + h < len(closes):
            out[h] = closes[base + h] / closes[base] - 1.0
    return out


# ---------------------------------------------------------------------------- Laden
def load_observations(
    conn: sqlite3.Connection,
    config: Config,
    horizons: tuple[int, ...],
    *,
    profiles: tuple[str, ...] | None = None,
    classes: tuple[str, ...] | None = None,
    since: str | None = None,
    until: str | None = None,
) -> list[Observation]:
    prices: dict[str, tuple[list[str], list[float]]] = {}
    query = "SELECT id, asset_id, profile, date, score, coverage FROM scores WHERE 1 = 1"
    args: list[Any] = []
    if since:
        query += " AND date >= ?"
        args.append(since)
    if until:
        query += " AND date <= ?"
        args.append(until)
    out: list[Observation] = []
    # (False Positive: SQL nur aus festen Fragmenten, Werte als ?-Parameter, s. ERGEBNIS.md)
    # nosemgrep
    for score_id, asset_id, profile, day, score, coverage in conn.execute(
        query + " ORDER BY date, asset_id, profile", args
    ):
        asset = config.assets_by_id.get(asset_id)
        if asset is None or (profiles and profile not in profiles):
            continue
        if classes and asset.asset_class.value not in classes:
            continue
        if asset_id not in prices:
            rows = conn.execute(
                "SELECT date, close FROM prices WHERE asset_id = ? ORDER BY date", (asset_id,)
            ).fetchall()
            prices[asset_id] = ([r[0] for r in rows], [r[1] for r in rows])
        dates, closes = prices[asset_id]
        out.append(
            Observation(
                asset_id,
                asset.asset_class.value,
                profile,
                day,
                score,
                coverage,
                score_id,
                forward_returns(dates, closes, day, horizons),
            )
        )
    return out


# ---------------------------------------------------------------------------- Kennzahlen
def _rate(hits: int, n: int) -> float | None:
    return hits / n if n else None


def summarize(
    obs: list[Observation],
    horizon: int,
    buckets: list[Bucket],
    *,
    min_signals: int,
    step: int = STEP_TRADING_DAYS,
) -> dict[str, Any]:
    """Kennzahlen einer Beobachtungsmenge für einen Horizont (nur Beobachtungen mit Rendite)."""
    rows = [(o, o.forward[horizon]) for o in obs if o.forward.get(horizon) is not None]
    returns = [r for _, r in rows]
    overlap = max(1.0, horizon / step)
    result: dict[str, Any] = {
        "horizon": horizon,
        "n": len(rows),
        "n_eff": round(len(rows) / overlap, 1),
        "overlap_factor": round(overlap, 2),
        "enough": len(rows) >= min_signals,
        "base_up": _rate(sum(r > 0 for r in returns), len(returns)),
        "base_mean": mean_or_none(returns),
        "buckets": [],
    }
    by_bucket: dict[str, list[float]] = defaultdict(list)
    for o, r in rows:
        by_bucket[bucket_of(o.score, buckets).label].append(r)
    for bucket in buckets:
        values = by_bucket.get(bucket.label, [])
        hit = None
        if bucket.direction:
            hit = _rate(sum(bucket.direction * r > 0 for r in values), len(values))
        result["buckets"].append(
            {
                "label": bucket.label,
                "low": bucket.low,
                "high": bucket.high,
                "direction": bucket.direction,
                "n": len(values),
                "enough": len(values) >= min_signals,
                "up_share": _rate(sum(r > 0 for r in values), len(values)),
                "hit_rate": hit,
                "mean": mean_or_none(values),
                "median": median_or_none(values),
            }
        )
    bull = [r for o, r in rows if bucket_of(o.score, buckets).direction > 0]
    bear = [r for o, r in rows if bucket_of(o.score, buckets).direction < 0]
    directional = [
        (bucket_of(o.score, buckets).direction, r)
        for o, r in rows
        if bucket_of(o.score, buckets).direction
    ]
    hits = sum(d * r > 0 for d, r in directional)
    result["bullish"] = {
        "n": len(bull),
        "hit_rate": _rate(sum(r > 0 for r in bull), len(bull)),
        "mean": mean_or_none(bull),
    }
    result["bearish"] = {
        "n": len(bear),
        "hit_rate": _rate(sum(r < 0 for r in bear), len(bear)),
        "mean": mean_or_none(bear),
    }
    result["directional"] = {
        "n": len(directional),
        "enough": len(directional) >= min_signals,
        "hit_rate": _rate(hits, len(directional)),
        "mean_signed": mean_or_none([d * r for d, r in directional]),
    }
    result["spread"] = (
        mean_or_none(bull) - mean_or_none(bear) if bull and bear else None  # type: ignore[operator]
    )
    result["spread_t"] = diff_t(bull, bear, overlap)
    ic = spearman([o.score for o, _ in rows], returns) if len(rows) >= 3 else None
    result["ic"] = ic
    result["ic_t"] = t_from_corr(ic, len(rows) / overlap) if ic is not None else None
    cs = _cross_section_ic(rows)
    result["ic_cs"] = cs["mean"]
    result["ic_cs_dates"] = cs["dates"]
    result["ic_cs_t"] = (
        cs["mean"] / (cs["std"] / (cs["dates"] / overlap) ** 0.5)
        if cs["mean"] is not None and cs["std"] and cs["dates"] / overlap > 1
        else None
    )
    return result


def _cross_section_ic(rows: list[tuple[Observation, float]]) -> dict[str, Any]:
    """Mittlerer Spearman-IC je Stichtag über die Assets (nur Tage mit ≥ 5 Assets)."""
    by_day: dict[str, list[tuple[float, float]]] = defaultdict(list)
    for o, r in rows:
        by_day[o.day].append((o.score, r))
    ics = []
    for pairs in by_day.values():
        if len(pairs) >= MIN_CROSS_SECTION:
            ic = spearman([p[0] for p in pairs], [p[1] for p in pairs])
            if ic is not None:
                ics.append(ic)
    return {
        "mean": mean_or_none(ics),
        "std": statistics.stdev(ics) if len(ics) > 1 else None,
        "dates": len(ics),
    }


# ---------------------------------------------------------------------------- Gesamtlauf
def _classes_present(obs: list[Observation]) -> list[str]:
    order = [c.value for c in AssetClass]
    present = {o.asset_class for o in obs}
    return [c for c in order if c in present]


def run_backtest(
    conn: sqlite3.Connection,
    config: Config,
    *,
    profiles: tuple[str, ...] | None = None,
    classes: tuple[str, ...] | None = None,
    horizon_days: int | None = None,
    since: str | None = None,
    until: str | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Komplette Auswertung als JSON-fähiges Dict (Grundlage für Markdown-Report und API)."""
    bt = config.backtest
    wanted_profiles = tuple(profiles or config.profiles)
    horizons_by_profile = {
        p: ((horizon_days,) if horizon_days else tuple(bt.horizons.get(p, (5, 10, 20))))
        for p in wanted_profiles
    }
    primary = {
        p: horizon_days or bt.primary_horizon.get(p, horizons_by_profile[p][0])
        for p in wanted_profiles
    }
    all_horizons = tuple(sorted({h for hs in horizons_by_profile.values() for h in hs}))
    obs = load_observations(
        conn, config, all_horizons, profiles=wanted_profiles, classes=classes, since=since,
        until=until,
    )  # fmt: skip
    step = STEP_TRADING_DAYS if bt.score_weekday is not None else 1
    buckets = buckets_from_labels(config.scoring.labels)
    present = _classes_present(obs)
    groups: list[dict[str, Any]] = []
    yearly: list[dict[str, Any]] = []
    for profile in wanted_profiles:
        profile_obs = [o for o in obs if o.profile == profile]
        for asset_class in [*present, ALL]:
            subset = (
                profile_obs
                if asset_class == ALL
                else [o for o in profile_obs if o.asset_class == asset_class]
            )
            if not subset:
                continue
            for h in horizons_by_profile[profile]:
                if asset_class == ALL:
                    groups.append(
                        _pooled_group(
                            profile,
                            h,
                            h == primary[profile],
                            subset,
                            buckets,
                            bt.min_signals,
                            step,
                            groups,
                        )
                    )
                    continue
                groups.append(
                    {
                        "profile": profile,
                        "asset_class": asset_class,
                        "primary": h == primary[profile],
                        **summarize(subset, h, buckets, min_signals=bt.min_signals, step=step),
                    }
                )
            years = sorted({o.day[:4] for o in subset})
            for year in years:
                part = [o for o in subset if o.day[:4] == year]
                s = summarize(
                    part, primary[profile], buckets, min_signals=bt.min_signals, step=step
                )
                yearly.append(
                    {
                        "profile": profile,
                        "asset_class": asset_class,
                        "year": year,
                        "horizon": primary[profile],
                        "n": s["n"],
                        "ic": s["ic"],
                        "hit_rate": s["directional"]["hit_rate"],
                        "directional_n": s["directional"]["n"],
                        "spread": s["spread"],
                    }
                )
    return {
        "generated_at": (now or datetime.now(UTC)).isoformat(timespec="seconds"),
        "scores": len(obs),
        "dates": len({o.day for o in obs}),
        "first_date": min((o.day for o in obs), default=None),
        "last_date": max((o.day for o in obs), default=None),
        "profiles": {p: config.profiles[p].label for p in wanted_profiles},
        "classes": present,
        "horizons": {p: list(h) for p, h in horizons_by_profile.items()},
        "primary_horizon": primary,
        "step_trading_days": step,
        "min_signals": bt.min_signals,
        "buckets": [b.__dict__ for b in buckets],
        "groups": groups,
        "factors": factor_analysis(conn, config, obs, primary),
        "yearly": yearly,
        "coverage": coverage_by_year(conn, obs),
    }


def _pooled_group(profile, h, is_primary, subset, buckets, min_signals, step, groups):
    """„Alle Klassen“: Trefferquote/Buckets gepoolt; IC und Spread als n-gewichtetes Mittel der
    Klassenwerte (gepoolt würden unterschiedliche Basisrenditen der Klassen sie verfälschen)."""
    pooled = summarize(subset, h, buckets, min_signals=min_signals, step=step)
    parts = [
        g for g in groups
        if g["profile"] == profile and g["horizon"] == h and g["asset_class"] != ALL
    ]  # fmt: skip

    def weighted(key: str) -> float | None:
        items = [(g["n"], g[key]) for g in parts if g[key] is not None]
        total = sum(n for n, _ in items)
        return sum(n * v for n, v in items) / total if total else None

    pooled["ic"] = weighted("ic")
    pooled["ic_t"] = (
        t_from_corr(pooled["ic"], pooled["n_eff"]) if pooled["ic"] is not None else None
    )
    pooled["spread"] = weighted("spread")
    pooled["spread_t"] = None
    pooled["weighted_classes"] = True
    return {"profile": profile, "asset_class": ALL, "primary": is_primary, **pooled}


def _components(conn: sqlite3.Connection, ids: set[int]) -> dict[int, dict[str, float | None]]:
    out: dict[int, dict[str, float | None]] = defaultdict(dict)
    for score_id, factor, subscore in conn.execute(
        "SELECT score_id, factor, subscore FROM score_components"
    ):
        if score_id in ids:
            out[score_id][factor] = subscore
    return out


def factor_analysis(
    conn: sqlite3.Connection, config: Config, obs: list[Observation], primary: dict[str, int]
) -> list[dict[str, Any]]:
    """IC je Teilscore (Spearman Teilscore vs. Forward-Rendite, Horizont = Kennwert des Profils)
    sowie Verfügbarkeit; Hinweis für Gewichts-Tuning (keine Änderung ohne Jonas)."""
    comps = _components(conn, {o.score_id for o in obs})
    out: list[dict[str, Any]] = []
    for profile, horizon in primary.items():
        for asset_class in _classes_present(obs):
            subset = [o for o in obs if o.profile == profile and o.asset_class == asset_class]
            if not subset:
                continue
            weights = config.profiles[profile].weights[AssetClass(asset_class)]
            overlap = max(1.0, horizon / (STEP_TRADING_DAYS))
            for factor, weight in weights.items():
                pairs = [
                    (comps[o.score_id][factor], o.forward[horizon])
                    for o in subset
                    if comps.get(o.score_id, {}).get(factor) is not None
                    and o.forward.get(horizon) is not None
                ]
                ic = spearman([p[0] for p in pairs], [p[1] for p in pairs]) if pairs else None
                available = sum(
                    1 for o in subset if comps.get(o.score_id, {}).get(factor) is not None
                )
                out.append(
                    {
                        "profile": profile,
                        "asset_class": asset_class,
                        "factor": factor,
                        "horizon": horizon,
                        "weight": weight,
                        "n": len(pairs),
                        "availability": available / len(subset),
                        "ic": ic,
                        "ic_t": t_from_corr(ic, len(pairs) / overlap) if ic is not None else None,
                    }
                )
    return out


def coverage_by_year(conn: sqlite3.Connection, obs: list[Observation]) -> list[dict[str, Any]]:
    """Abdeckung je Assetklasse und Jahr: Anzahl Scores, mittlere Gewichts-Abdeckung und Anteil
    der Scores, in denen ein Faktor verfügbar war (Profil `swing`, falls vorhanden)."""
    first_profile = min((o.profile for o in obs), default=None)
    chosen = [o for o in obs if o.profile == ("swing" if _has(obs, "swing") else first_profile)]
    comps = _components(conn, {o.score_id for o in chosen})
    groups: dict[tuple[str, str], list[Observation]] = defaultdict(list)
    for o in chosen:
        groups[(o.asset_class, o.day[:4])].append(o)
    out = []
    for (asset_class, year), items in sorted(groups.items()):
        factors: dict[str, int] = defaultdict(int)
        names: set[str] = set()
        for o in items:
            for factor, subscore in comps.get(o.score_id, {}).items():
                names.add(factor)
                if subscore is not None:
                    factors[factor] += 1
        out.append(
            {
                "asset_class": asset_class,
                "year": year,
                "n": len(items),
                "mean_coverage": statistics.fmean(o.coverage for o in items),
                "factors": {f: factors[f] / len(items) for f in sorted(names)},
            }
        )
    return out


def _has(obs: list[Observation], profile: str) -> bool:
    return any(o.profile == profile for o in obs)
