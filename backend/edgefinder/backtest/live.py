# ruff: noqa: E501  (lange deutsche Texte)
"""Live-Bilanz (Forward-Test): Signale, die das Programm HEUTE gibt, gegen den realen Kurs prüfen.

Das ist der eigentliche Test des Modells. Die Eichung (`calibration.py`) beschreibt die Vergangenheit,
auf der das Modell entworfen wurde; nur Signale nach dem Start des Live-Betriebs sind echte Vorhersagen.
Dieses Modul **misst und meldet** (Bilanz, Drift gegen die Eichung, Faktor-Drift, Fortschritt). Es ändert
nie das Modell: Änderungen entstehen im Modellpflege-Zyklus (CLAUDE.md) mit Freigabe von Jonas.

Ablauf:
1. `evaluate`: jedes Live-Signal (`scores.origin = 'live'`) bekommt je Horizont (`backtest.horizons`) eine
   Zeile in `signal_outcomes`, sobald `h` Handelstage der Kursreihe nach dem Einstieg vorliegen. Einstieg ist
   der letzte Schlusskurs ≤ Signaltag (wie im Backtest); fehlende Kurse werden nie interpoliert.
2. `build_trackrecord`: Kennzahlen je Profil × Klasse nur aus den **wöchentlichen** Signalen (wie die
   Eichung; tägliche Signale überlappen), Drift-Status gegen die Eichung, Faktor-Drift, Fortschritt.
Gerechnet wird je Modellversion getrennt (`scoring.model_version`): ein Umbau mischt die Bilanz nicht.
"""

from __future__ import annotations

import sqlite3
import statistics
from bisect import bisect_right
from collections import defaultdict
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from typing import Any

from edgefinder.backtest.analysis import (
    MAX_STALE_DAYS,
    STEP_TRADING_DAYS,
    bucket_of,
    buckets_from_labels,
)
from edgefinder.backtest.calibration import DIRECTIONAL, cell
from edgefinder.backtest.stats import spearman, t_from_corr
from edgefinder.config import Config
from edgefinder.db.connection import transaction

DIRECTION = {1: "bullish", -1: "bearish", 0: "neutral"}
ZU_FRUEH, IM_RAHMEN, SCHWAECHER, BESSER, GEGENLAEUFIG, OHNE_EICHUNG = (
    "zu_frueh",
    "im_rahmen",
    "schwaecher",
    "besser",
    "gegenlaeufig",
    "ohne_eichung",
)
STATUSES = (ZU_FRUEH, IM_RAHMEN, SCHWAECHER, BESSER, GEGENLAEUFIG, OHNE_EICHUNG)


def add_weekdays(day: date, count: int) -> date:
    """`count` Werktage nach `day` (Näherung für Handelstage ohne Börsenkalender)."""
    while count > 0:
        day += timedelta(days=1)
        if day.weekday() < 5:
            count -= 1
    return day


# ---------------------------------------------------------------------------- Auswertung
@dataclass(frozen=True)
class EvaluateResult:
    created: int  # neue Outcome-Zeilen
    open: int  # Signal × Horizont, deren Horizont noch läuft
    unpriced: int  # ohne Einstiegskurs (zu weit entfernt), nie auswertbar


def evaluate(
    conn: sqlite3.Connection, config: Config, *, now: datetime | None = None
) -> EvaluateResult:
    """Forward-Rendite für alle abgelaufenen Horizonte der Live-Scores; idempotent."""
    stamp = (now or datetime.now(UTC)).isoformat(timespec="seconds")
    buckets = buckets_from_labels(config.scoring.labels)
    version_now = config.scoring.model_version
    done = {
        (a, p, d, h, v)
        for a, p, d, h, v in conn.execute(
            "SELECT asset_id, profile, signal_date, horizon_days, model_version FROM signal_outcomes"
        )
    }
    prices: dict[str, tuple[list[str], list[float]]] = {}
    created = open_ = unpriced = 0
    rows = conn.execute(
        "SELECT asset_id, profile, date, score, label, model_version FROM scores"
        " WHERE origin = 'live' ORDER BY date, asset_id, profile"
    ).fetchall()
    with transaction(conn):
        for asset_id, profile, day, score, label, version in rows:
            asset = config.assets_by_id.get(asset_id)
            horizons = config.backtest.horizons.get(profile)
            if asset is None or not horizons:
                continue
            version = version or version_now
            todo = [h for h in horizons if (asset_id, profile, day, h, version) not in done]
            if not todo:
                continue
            if asset_id not in prices:
                found = conn.execute(
                    "SELECT date, close FROM prices WHERE asset_id = ? ORDER BY date", (asset_id,)
                ).fetchall()
                prices[asset_id] = ([r[0] for r in found], [r[1] for r in found])
            dates, closes = prices[asset_id]
            base = bisect_right(dates, day) - 1
            if (
                base < 0
                or closes[base] <= 0
                or (date.fromisoformat(day) - date.fromisoformat(dates[base])).days > MAX_STALE_DAYS
            ):
                unpriced += len(todo)
                continue
            direction = bucket_of(score, buckets).direction
            for h in todo:
                if base + h >= len(closes):
                    open_ += 1
                    continue
                ret = closes[base + h] / closes[base] - 1.0
                hit = None if direction == 0 else int(direction * ret > 0)
                conn.execute(
                    "INSERT OR IGNORE INTO signal_outcomes (asset_id, profile, signal_date,"
                    " asset_class, score, label, direction, model_version, horizon_days,"
                    " entry_date, entry_price, exit_date, exit_price, forward_return_pct, hit,"
                    " evaluated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (
                        asset_id,
                        profile,
                        day,
                        asset.asset_class.value,
                        score,
                        label,
                        DIRECTION[direction],
                        version,
                        h,
                        dates[base],
                        closes[base],
                        dates[base + h],
                        closes[base + h],
                        round(ret * 100, 4),
                        hit,
                        stamp,
                    ),
                )
                created += 1
    return EvaluateResult(created, open_, unpriced)


# ---------------------------------------------------------------------------- Kennzahlen
def _is_weekly(day: str, weekday: int | None) -> bool:
    return weekday is None or date.fromisoformat(day).weekday() == weekday


def _load(conn: sqlite3.Connection, version: str, profile: str | None) -> list[sqlite3.Row]:
    query = (
        "SELECT asset_id, profile, asset_class, signal_date, score, label, direction,"
        " horizon_days, exit_date, forward_return_pct, hit FROM signal_outcomes"
        " WHERE model_version = ?"
    )
    args: list[Any] = [version]
    if profile:
        query += " AND profile = ?"
        args.append(profile)
    # (False Positive: SQL nur aus festen Fragmenten, Werte als ?-Parameter, s. ERGEBNIS.md)
    # nosemgrep
    return conn.execute(query + " ORDER BY signal_date", args).fetchall()


def drift_status(
    live: dict[str, Any],
    cal: dict[str, Any] | None,
    weeks: int,
    config: Config,
) -> str:
    """Drift-Status des Live-Vorteils gegen das Konfidenzband des Vorteils in der Eichung."""
    rules = config.live
    edge, t = live.get("edge"), live.get("t")
    if (live.get("n_eff") or 0) < rules.min_n_eff or weeks < rules.min_weeks or edge is None:
        return ZU_FRUEH
    if edge < 0 and t is not None and t <= -rules.counter_t:
        return GEGENLAEUFIG
    if not cal or cal.get("edge") is None or cal.get("edge_se") is None:
        return OHNE_EICHUNG
    z = config.backtest.calibration.confidence_z
    low, high = cal["edge"] - z * cal["edge_se"], cal["edge"] + z * cal["edge_se"]
    if edge < low:
        return SCHWAECHER
    if edge > high:
        return BESSER
    return IM_RAHMEN


def _ratio(value: float, target: float) -> float:
    return max(0.0, min(1.0, value / target))


def group_progress(n_eff: float, months: float, weeks: int, config: Config) -> float:
    """Anteil (0…1) der Kriterien „geeicht“: der am weitesten entfernte Teil zählt."""
    done = config.live.done
    return min(
        _ratio(n_eff, done.min_n_eff),
        _ratio(months, done.min_months),
        _ratio(weeks, done.min_weeks),
    )


def _group_rows(rows: list[sqlite3.Row], horizon: int, weekday: int | None) -> list[sqlite3.Row]:
    return [
        r for r in rows if r["horizon_days"] == horizon and _is_weekly(r["signal_date"], weekday)
    ]


def _cell_of(
    sel: list[tuple[float, int]], base: list[float], overlap: float, z: float
) -> dict[str, Any]:
    if not base:
        return {"n": 0, "n_eff": 0.0}
    return cell(sel, statistics.fmean(base), sum(r > 0 for r in base) / len(base), overlap, z)


def build_groups(
    rows: list[sqlite3.Row], config: Config, calibration: dict[str, Any] | None
) -> list[dict[str, Any]]:
    """Gruppen-Bilanz je Profil × Klasse (Kennwert-Horizont, nur wöchentliche Signale)."""
    buckets = buckets_from_labels(config.scoring.labels)
    z = config.backtest.calibration.confidence_z
    weekday = config.backtest.score_weekday
    out: list[dict[str, Any]] = []
    classes = list(dict.fromkeys(a.asset_class.value for a in config.assets.all()))
    for profile in config.profiles:
        horizon = (
            config.backtest.primary_horizon.get(profile) or config.backtest.horizons[profile][0]
        )
        overlap = max(1.0, horizon / STEP_TRADING_DAYS) if weekday is not None else 1.0
        for klass in classes:
            sel = [
                r
                for r in _group_rows(rows, horizon, weekday)
                if r["profile"] == profile and r["asset_class"] == klass
            ]
            pairs = [(r["forward_return_pct"] / 100, bucket_of(r["score"], buckets)) for r in sel]
            base = [p[0] for p in pairs]
            directional = [(r, b.direction) for r, b in pairs if b.direction]
            live = _cell_of(directional, base, overlap, z)
            by_bucket = {
                b.label: _cell_of(
                    [(r, bb.direction) for r, bb in pairs if bb.label == b.label], base, overlap, z
                )
                for b in buckets
            }
            dir_days = sorted(
                {
                    r["signal_date"]
                    for r, b in zip(sel, (p[1] for p in pairs), strict=True)
                    if b.direction
                }
            )
            weeks = len(dir_days)
            last_exit = max((r["exit_date"] for r in sel), default=None)
            months = 0.0
            if dir_days and last_exit:
                months = max(
                    0.0,
                    (date.fromisoformat(last_exit) - date.fromisoformat(dir_days[0])).days / 30.44,
                )
            cal = None
            if calibration:
                cal = (
                    calibration.get("classes", {})
                    .get(profile, {})
                    .get(klass, {})
                    .get(str(horizon), {})
                    .get(DIRECTIONAL, {})
                    .get("all")
                )
            status = drift_status(live, cal, weeks, config)
            progress = group_progress(live.get("n_eff") or 0.0, months, weeks, config)
            calibrated = progress >= 1.0 and status in config.live.done.statuses
            out.append(
                {
                    "profile": profile,
                    "asset_class": klass,
                    "horizon": horizon,
                    "n": live.get("n", 0),
                    "n_eff": live.get("n_eff", 0.0),
                    "weeks": weeks,
                    "months": round(months, 1),
                    "hit": live.get("hit"),
                    "base_hit": live.get("base_hit"),
                    "edge": live.get("edge"),
                    "edge_ci": _edge_ci(live, z),
                    "t": live.get("t"),
                    "mean": live.get("mean"),
                    "cal_edge": cal.get("edge") if cal else None,
                    "cal_edge_ci": _edge_ci(cal, z) if cal else None,
                    "cal_hit": cal.get("hit") if cal else None,
                    "status": status,
                    "progress": round(progress, 3),
                    "calibrated": calibrated,
                    "buckets": by_bucket,
                }
            )
    return out


def _edge_ci(c: dict[str, Any] | None, z: float) -> list[float] | None:
    if not c or c.get("edge") is None or c.get("edge_se") is None:
        return None
    return [round(c["edge"] - z * c["edge_se"], 5), round(c["edge"] + z * c["edge_se"], 5)]


# ---------------------------------------------------------------------------- Faktor-Drift
def build_factor_drift(
    conn: sqlite3.Connection, config: Config, calibration: dict[str, Any] | None, version: str
) -> list[dict[str, Any]]:
    """IC je Faktor (Teilscore vs. Forward-Rendite) live gegen Backtest; nur Meldung."""
    rules = config.live.factor
    weekday = config.backtest.score_weekday
    primary = {
        p: config.backtest.primary_horizon.get(p) or config.backtest.horizons[p][0]
        for p in config.profiles
    }
    sql = (
        "SELECT o.profile, o.asset_class, o.signal_date, sc.factor, sc.subscore,"  # noqa: S608
        " o.forward_return_pct FROM signal_outcomes o"
        " JOIN scores s ON s.asset_id = o.asset_id AND s.profile = o.profile AND s.date = o.signal_date"
        " JOIN score_components sc ON sc.score_id = s.id"
        " WHERE o.model_version = ? AND sc.subscore IS NOT NULL AND ("
        + " OR ".join("(o.profile = ? AND o.horizon_days = ?)" for _ in primary)
        + ") ORDER BY o.signal_date"
    )
    args: list[Any] = [version]
    for profile, horizon in primary.items():
        args += [profile, horizon]
    data: dict[tuple[str, str, str], list[tuple[str, float, float]]] = defaultdict(list)
    # nosemgrep (feste SQL-Fragmente, Werte als Parameter)
    for profile, klass, day, factor, sub, ret in conn.execute(sql, args):
        if _is_weekly(day, weekday):
            data[(profile, klass, factor)].append((day, sub, ret / 100))
    out: list[dict[str, Any]] = []
    for (profile, klass, factor), items in sorted(data.items()):
        overlap = max(1.0, primary[profile] / STEP_TRADING_DAYS) if weekday is not None else 1.0
        ic = spearman([i[1] for i in items], [i[2] for i in items])
        n_eff = len(items) / overlap
        weeks = len({i[0] for i in items})
        t = t_from_corr(ic, n_eff) if ic is not None else None
        ref = (calibration or {}).get("factor_ic", {}).get(profile, {}).get(klass, {}).get(factor)
        bt_ic = ref.get("ic") if ref else None
        status, against = ZU_FRUEH, 0
        if ic is not None and n_eff >= rules.min_n_eff and weeks >= rules.min_weeks:
            if bt_ic is None or abs(bt_ic) < rules.min_abs_ic:
                status = "kein_vergleich"
            elif ic * bt_ic < 0 and t is not None and abs(t) >= rules.counter_t:
                status = GEGENLAEUFIG
            elif ic * bt_ic > 0 and abs(ic) < abs(bt_ic) / 2:
                status = SCHWAECHER
            else:
                status = IM_RAHMEN
            against = _weeks_against(items, bt_ic) if bt_ic else 0
        out.append(
            {
                "profile": profile,
                "asset_class": klass,
                "factor": factor,
                "n": len(items),
                "n_eff": round(n_eff, 1),
                "weeks": weeks,
                "ic": None if ic is None else round(ic, 4),
                "ic_t": None if t is None else round(t, 2),
                "backtest_ic": bt_ic,
                "status": status,
                "weeks_against": against,
                "warn": status == GEGENLAEUFIG and against >= rules.warn_weeks,
            }
        )
    return out


def _weeks_against(items: list[tuple[str, float, float]], bt_ic: float) -> int:
    """Wochen in Folge (zuletzt), in denen der bis dahin kumulierte Live-IC das falsche Vorzeichen hatte."""
    days = sorted({i[0] for i in items})
    streak = 0
    for day in reversed(days):
        part = [i for i in items if i[0] <= day]
        ic = spearman([i[1] for i in part], [i[2] for i in part])
        if ic is None or ic * bt_ic >= 0:
            break
        streak += 1
    return streak


# ---------------------------------------------------------------------------- Zeitverlauf
def build_series(
    rows: list[sqlite3.Row], config: Config
) -> dict[str, dict[str, list[dict[str, Any]]]]:
    """Kumulierte Treffer-Differenz (Treffer − erwartete Treffer nach Basisrate) je Profil × Klasse."""
    buckets = buckets_from_labels(config.scoring.labels)
    weekday = config.backtest.score_weekday
    out: dict[str, dict[str, list[dict[str, Any]]]] = {}
    for profile in config.profiles:
        horizon = (
            config.backtest.primary_horizon.get(profile) or config.backtest.horizons[profile][0]
        )
        out[profile] = {}
        sel = [r for r in _group_rows(rows, horizon, weekday) if r["profile"] == profile]
        for klass in sorted({r["asset_class"] for r in sel}):
            cls = [r for r in sel if r["asset_class"] == klass]
            base_up = sum(r["forward_return_pct"] > 0 for r in cls) / len(cls)
            by_day: dict[str, float] = defaultdict(float)
            for r in cls:
                direction = bucket_of(r["score"], buckets).direction
                if direction:
                    expected = base_up if direction > 0 else 1 - base_up
                    by_day[r["exit_date"]] += (
                        int(direction * r["forward_return_pct"] > 0) - expected
                    )
            total, series = 0.0, []
            for day in sorted(by_day):
                total += by_day[day]
                series.append({"date": day, "value": round(total, 3)})
            out[profile][klass] = series
    return out


# ---------------------------------------------------------------------------- Gesamtbericht
def build_trackrecord(
    conn: sqlite3.Connection,
    config: Config,
    calibration: dict[str, Any] | None,
    *,
    profile: str | None = None,
    today: date | None = None,
) -> dict[str, Any]:
    """Alles für Seite „Bilanz“ und Drift-Bericht (JSON-fähig, ein Modellstand)."""
    today = today or datetime.now(UTC).date()
    version = config.scoring.model_version
    rows = _load(conn, version, profile)
    profiles = [profile] if profile else list(config.profiles)
    groups = [g for g in build_groups(rows, config, calibration) if g["profile"] in profiles]
    live_since = conn.execute("SELECT MIN(date) FROM scores WHERE origin = 'live'").fetchone()[0]
    evaluated = defaultdict(int)  # Profil → ausgewertete Signale (Kennwert-Horizont, alle Tage)
    for r in rows:
        horizon = config.backtest.primary_horizon.get(r["profile"])
        if r["horizon_days"] == horizon:
            evaluated[r["profile"]] += 1
    open_signals = 0
    earliest: date | None = None
    for p in profiles:
        horizon = config.backtest.primary_horizon.get(p) or config.backtest.horizons[p][0]
        done_days = {
            (r["asset_id"], r["signal_date"])
            for r in rows
            if r["profile"] == p and r["horizon_days"] == horizon
        }
        for asset_id, day in conn.execute(
            "SELECT asset_id, date FROM scores WHERE origin = 'live' AND profile = ?"
            " AND COALESCE(model_version, ?) = ?",
            (p, version, version),
        ):
            if (asset_id, day) in done_days:
                continue
            open_signals += 1
            due = add_weekdays(date.fromisoformat(day), horizon)
            earliest = due if earliest is None or due < earliest else earliest
    weekly_first = None
    if live_since:
        weekly_first = date.fromisoformat(live_since)
        weekday = config.backtest.score_weekday
        while weekday is not None and weekly_first.weekday() != weekday:
            weekly_first += timedelta(days=1)
    max_h = max(
        (
            config.backtest.primary_horizon.get(p) or config.backtest.horizons[p][0]
            for p in profiles
        ),
        default=0,
    )
    reliable_from = (
        add_weekdays(weekly_first + timedelta(weeks=config.live.min_weeks - 1), max_h)
        if weekly_first
        else None
    )
    done_cfg = config.live.done
    done_from = (
        add_weekdays(weekly_first + timedelta(days=round(done_cfg.min_months * 30.44)), max_h)
        if weekly_first
        else None
    )
    series = build_series(rows, config)
    mean_progress = statistics.fmean([g["progress"] for g in groups]) if groups else 0.0
    return {
        "model_version": version,
        "generated_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "today": today.isoformat(),
        "live_since": live_since,
        "evaluated": sum(evaluated.values()),
        "evaluated_weekly": sum(g["n"] for g in groups),
        "open": open_signals,
        "earliest_due": earliest.isoformat() if earliest else None,
        "reliable_from": reliable_from.isoformat() if reliable_from else None,
        "done_from": done_from.isoformat() if done_from else None,
        "calibration_date": (calibration or {}).get("generated_at"),
        "groups": groups,
        "factors": build_factor_drift(conn, config, calibration, version),
        "series": {p: s for p, s in series.items() if p in profiles},
        "progress": round(mean_progress, 3),
        "calibrated_groups": sum(g["calibrated"] for g in groups),
        "criteria": {
            "min_n_eff": done_cfg.min_n_eff,
            "min_months": done_cfg.min_months,
            "min_weeks": done_cfg.min_weeks,
            "statuses": list(done_cfg.statuses),
            "min_weeks_status": config.live.min_weeks,
            "min_n_eff_status": config.live.min_n_eff,
        },
    }
