# ruff: noqa: E501  (lange deutsche Tabellen-/Textzeilen im Markdown-Anhang)
"""Eichung: Was hat ein Score in einem bestimmten Bereich historisch gebracht?

Aus den gespeicherten Backfill-Scores (wöchentlich) und den Kursen wird je **Profil × Assetklasse
× Score-Bereich × Horizont** berechnet: n, n_eff (Überlappung), Trefferquote, Basisrate, Ø/Median
der Forward-Rendite, Vorteil gegenüber der unbedingten Durchschnittsrendite (`edge`, in
Signalrichtung), t-Wert mit n_eff und Konfidenzband – gesamt, Training (≤ `train_end`) und
Out-of-Sample. Dazu je Asset (nur bei n_eff ≥ `asset_min_n_eff`) und eine Zusatzauswertung nach
Faktor-Übereinstimmung. Daraus entsteht die **Evidenzstufe** nach festen Regeln aus `config.yaml`.

Look-Ahead: Es gilt exakt die Logik von `analysis.py` (Forward-Rendite ab letztem Kurs ≤ Stichtag,
Fenster über den letzten Kurs hinaus entfallen). Training/OOS wird nach dem **Stichtag** getrennt.
Die Eichung beschreibt die Vergangenheit – sie ist keine Prognose.
"""

from __future__ import annotations

import json
import math
import re
import statistics
from collections import defaultdict
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

from edgefinder.backtest.analysis import (
    STEP_TRADING_DAYS,
    Bucket,
    Observation,
    bucket_of,
    buckets_from_labels,
    factor_analysis,
    load_observations,
)
from edgefinder.config import CalibrationConfig, Config
from edgefinder.scoring.agreement import agreement

VERSION = 1
PERIODS = ("all", "train", "oos")
DIRECTIONAL = "directional"  # alle bullishen und bearishen Bereiche, Rendite in Signalrichtung
BELEGT, SCHWACH, KEIN_VORTEIL, ZU_WENIG, NEUTRAL = (
    "belegt",
    "schwach",
    "kein_vorteil",
    "zu_wenig_daten",
    "neutral",
)
LEVELS = (BELEGT, SCHWACH, KEIN_VORTEIL, ZU_WENIG, NEUTRAL)
Row = tuple[Observation, float, int]  # Beobachtung, Forward-Rendite, Richtung des Bereichs


# ---------------------------------------------------------------------------- Kennzahlen
def _r(value: float | None, digits: int) -> float | None:
    return None if value is None else round(value, digits)


def cell(
    rows: list[tuple[float, int]],
    base_mean: float | None,
    base_up: float | None,
    overlap: float,
    z: float,
) -> dict[str, Any]:
    """Kennzahlen einer Menge (Rendite, Richtung). Richtung 0 = neutral (keine Richtungsaussage).

    `edge` = Ø (Rendite − Basis-Ø) in Signalrichtung, `t` dazu mit n_eff. Gemischte Richtungen
    (Bereich „directional“): `mean`/`median` sind Renditen in Signalrichtung (Short = −Rendite).
    """
    n = len(rows)
    out: dict[str, Any] = {"n": n, "n_eff": _r(n / overlap, 1)}
    if not n or base_mean is None or base_up is None:
        return out
    mixed = len({d for _, d in rows}) > 1
    returns = [(d * r if mixed else r) for r, d in rows]
    signed_excess = [(d if d else 1) * (r - base_mean) for r, d in rows]
    mean = statistics.fmean(returns)
    edge = statistics.fmean(signed_excess)
    sd = statistics.stdev(returns) if n > 1 else 0.0
    sd_edge = statistics.stdev(signed_excess) if n > 1 else 0.0
    se = sd * math.sqrt(overlap / n)
    directional = [(r, d) for r, d in rows if d]
    hit = base_hit = None
    if directional:
        hit = sum(d * r > 0 for r, d in directional) / len(directional)
        base_hit = statistics.fmean(base_up if d > 0 else 1 - base_up for _, d in directional)
    se_edge = sd_edge * math.sqrt(overlap / n)
    out.update(
        {
            "up": _r(sum(r > 0 for r, _ in rows) / n, 4),
            "base_up": _r(base_up, 4),
            "hit": _r(hit, 4),
            "base_hit": _r(base_hit, 4),
            "mean": _r(mean, 5),
            "median": _r(statistics.median(returns), 5),
            "base_mean": _r(base_mean, 5),
            "edge": _r(edge, 5),
            "t": _r(edge / se_edge, 2) if se_edge > 0 else None,
            "edge_se": _r(se_edge, 5),
            "ci": [_r(mean - z * se, 5), _r(mean + z * se, 5)],
        }
    )
    return out


def evidence(
    cells: dict[str, dict[str, Any]],
    direction: int,
    rules: CalibrationConfig,
    min_t: float | None = None,
) -> str:
    """Evidenzstufe aus den Zellen „all/train/oos“ (feste Regeln, Werte aus `config.yaml`)."""
    if direction == 0:
        return NEUTRAL
    parts = [cells.get(p, {}) for p in PERIODS]
    if any((c.get("n_eff") or 0) < rules.floor_n_eff or c.get("edge") is None for c in parts):
        return ZU_WENIG
    total, train, oos = parts
    if not all(c["edge"] > 0 for c in parts):
        return KEIN_VORTEIL  # Vorzeichen wechselt, null oder falsch herum
    solid = (
        (total["t"] or 0) >= (rules.min_t if min_t is None else min_t)
        and total["n_eff"] >= rules.min_n_eff
        and train["n_eff"] >= rules.min_n_eff_period
        and oos["n_eff"] >= rules.min_n_eff_period
        and (total["hit"] or 0) > (total["base_hit"] or 0)
    )
    return BELEGT if solid else SCHWACH


# ---------------------------------------------------------------------------- Aufbau
def _split(rows: list[Row], train_end: str) -> dict[str, list[Row]]:
    return {
        "all": rows,
        "train": [x for x in rows if x[0].day <= train_end],
        "oos": [x for x in rows if x[0].day > train_end],
    }


def _bucket_cells(
    rows: list[Row],
    buckets: list[Bucket],
    keys: list[str],
    rules: CalibrationConfig,
    overlap: float,
) -> dict[str, dict[str, Any]]:
    """{Bereich: {all, train, oos, evidence}} für eine Beobachtungsmenge (Klasse oder Asset)."""
    parts = _split(rows, rules.train_end.isoformat())
    base: dict[str, tuple[float | None, float | None]] = {}
    for period, items in parts.items():
        rets = [r for _, r, _ in items]
        base[period] = (
            statistics.fmean(rets) if rets else None,
            sum(r > 0 for r in rets) / len(rets) if rets else None,
        )
    out: dict[str, dict[str, Any]] = {}
    for key in keys:
        direction = 0
        if key == DIRECTIONAL:
            direction = 1
        else:
            direction = next(b.direction for b in buckets if b.label == key)

        def pick(x: Row, key=key) -> bool:
            return x[2] != 0 if key == DIRECTIONAL else _label(x[0], buckets) == key

        cells = {
            period: cell(
                [(r, d) for o, r, d in items if pick((o, r, d))],
                base[period][0],
                base[period][1],
                overlap,
                rules.confidence_z,
            )
            for period, items in parts.items()
        }
        out[key] = {**cells, "evidence": evidence(cells, direction, rules)}
    return out


def _label(o: Observation, buckets: list[Bucket]) -> str:
    return bucket_of(o.score, buckets).label


def _rows(obs: list[Observation], horizon: int, buckets: list[Bucket]) -> list[Row]:
    return [
        (o, o.forward[horizon], bucket_of(o.score, buckets).direction)
        for o in obs
        if o.forward.get(horizon) is not None
    ]


def _agreement_by_obs(conn, obs: list[Observation], threshold: float) -> dict[int, float | None]:
    ids = {o.score_id for o in obs}
    comps: dict[int, list[tuple[float | None, float]]] = defaultdict(list)
    for sid, sub, weight in conn.execute("SELECT score_id, subscore, weight FROM score_components"):
        if sid in ids:
            comps[sid].append((sub, weight))
    out: dict[int, float | None] = {}
    for o in obs:
        info = agreement(comps.get(o.score_id, []), o.score, threshold)
        out[o.score_id] = info["weight_share"] if info else None
    return out


def build_calibration(
    conn,
    config: Config,
    *,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Komplette Eichung als JSON-fähiges Dict (Datei `backtest.calibration_file`)."""
    bt = config.backtest
    rules = bt.calibration
    profiles = tuple(config.profiles)
    horizons = {p: tuple(bt.horizons.get(p, (5, 10, 20))) for p in profiles}
    primary = {p: bt.primary_horizon.get(p, horizons[p][0]) for p in profiles}
    all_h = tuple(sorted({h for hs in horizons.values() for h in hs}))
    # Eichung nur aus dem Backfill: die Live-Signale bleiben der unabhängige Forward-Test
    obs = load_observations(conn, config, all_h, profiles=profiles, origin="backfill")
    if (
        bt.score_weekday is not None
    ):  # nur die wöchentlichen Stichtage (tägliche Live-Läufe überlappen)
        obs = [o for o in obs if date.fromisoformat(o.day).weekday() == bt.score_weekday]
    buckets = buckets_from_labels(config.scoring.labels)
    keys = [b.label for b in buckets] + [DIRECTIONAL]
    step = STEP_TRADING_DAYS if bt.score_weekday is not None else 1
    classes = list(dict.fromkeys(a.asset_class.value for a in config.assets.all()))
    share = _agreement_by_obs(conn, obs, config.scoring.signal_threshold)
    result: dict[str, Any] = {
        "version": VERSION,
        "generated_at": (now or datetime.now(UTC)).date().isoformat(),
        "first_date": min((o.day for o in obs), default=None),
        "data_through": max((o.day for o in obs), default=None),
        "scores": len(obs),
        "params": {
            "train_end": rules.train_end.isoformat(),
            "min_t": rules.min_t,
            "min_n_eff": rules.min_n_eff,
            "min_n_eff_period": rules.min_n_eff_period,
            "floor_n_eff": rules.floor_n_eff,
            "asset_min_n_eff": rules.asset_min_n_eff,
            "confidence_z": rules.confidence_z,
            "agreement_threshold": rules.agreement_threshold,
            "agreement_min_t": rules.agreement_min_t,
            "signal_threshold": config.scoring.signal_threshold,
            "step_trading_days": step,
            "horizons": {p: list(h) for p, h in horizons.items()},
            "primary_horizon": primary,
            "buckets": [b.__dict__ for b in buckets],
            "min_signals": bt.min_signals,
        },
        "classes": {},
        "assets": {},
        "agreement": {},
        "summary": {},
        "factor_ic": _factor_ic(conn, config, obs, primary),
    }
    for profile in profiles:
        p_obs = [o for o in obs if o.profile == profile]
        result["classes"][profile] = {}
        result["agreement"][profile] = {}
        result["summary"][profile] = {}
        for klass in classes:
            c_obs = [o for o in p_obs if o.asset_class == klass]
            if not c_obs:
                continue
            by_h: dict[str, Any] = {}
            for h in horizons[profile]:
                overlap = max(1.0, h / step)
                by_h[str(h)] = _bucket_cells(
                    _rows(c_obs, h, buckets), buckets, keys, rules, overlap
                )
            result["classes"][profile][klass] = by_h
            ph = str(primary[profile])
            d = by_h[ph][DIRECTIONAL]
            result["summary"][profile][klass] = {
                "horizon": primary[profile],
                "evidence": d["evidence"],
                "n_eff": d["all"].get("n_eff"),
                "hit": d["all"].get("hit"),
                "base_hit": d["all"].get("base_hit"),
                "edge": d["all"].get("edge"),
                "t": d["all"].get("t"),
                "edge_train": d["train"].get("edge"),
                "edge_oos": d["oos"].get("edge"),
            }
            result["agreement"][profile][klass] = _agreement_block(
                c_obs, primary[profile], buckets, share, rules, step
            )
        # je Asset (nur Kennwert-Horizont, nur belastbare Zellen)
        h = primary[profile]
        overlap = max(1.0, h / step)
        assets: dict[str, Any] = {}
        for asset_id in sorted({o.asset_id for o in p_obs}):
            cells = _bucket_cells(
                _rows([o for o in p_obs if o.asset_id == asset_id], h, buckets),
                buckets,
                keys,
                rules,
                overlap,
            )
            kept = {
                k: {p: v[p] for p in PERIODS}
                for k, v in cells.items()
                if (v["all"].get("n_eff") or 0) >= rules.asset_min_n_eff
            }
            if kept:
                assets[asset_id] = kept
        result["assets"][profile] = assets
    return result


def _factor_ic(
    conn, config: Config, obs: list[Observation], primary: dict[str, int]
) -> dict[str, Any]:
    """Backtest-IC je Faktor (Kennwert-Horizont): Referenz für die Faktor-Drift der Live-Bilanz."""
    out: dict[str, Any] = {}
    for row in factor_analysis(conn, config, obs, primary):
        out.setdefault(row["profile"], {}).setdefault(row["asset_class"], {})[row["factor"]] = {
            "ic": _r(row["ic"], 4),
            "ic_t": _r(row["ic_t"], 2),
            "n": row["n"],
        }
    return out


def _agreement_block(
    c_obs: list[Observation],
    horizon: int,
    buckets: list[Bucket],
    share: dict[int, float | None],
    rules: CalibrationConfig,
    step: int,
) -> dict[str, Any]:
    """Richtungssignale (bullish/bearish) getrennt nach hoher/niedriger Faktor-Übereinstimmung."""
    overlap = max(1.0, horizon / step)
    rows = [x for x in _rows(c_obs, horizon, buckets) if x[2] != 0]
    out: dict[str, Any] = {"horizon": horizon, "threshold": rules.agreement_threshold}
    for name, pred in (
        ("high", lambda s: s is not None and s >= rules.agreement_threshold),
        ("low", lambda s: s is not None and s < rules.agreement_threshold),
    ):
        sel = [x for x in rows if pred(share.get(x[0].score_id))]
        parts = _split(sel, rules.train_end.isoformat())
        base_parts = _split(_rows(c_obs, horizon, buckets), rules.train_end.isoformat())
        cells = {}
        for period in PERIODS:
            rets = [r for _, r, _ in base_parts[period]]
            cells[period] = cell(
                [(r, d) for _, r, d in parts[period]],
                statistics.fmean(rets) if rets else None,
                sum(r > 0 for r in rets) / len(rets) if rets else None,
                overlap,
                rules.confidence_z,
            )
        out[name] = {
            **cells,
            "evidence": evidence(cells, 1, rules, min_t=rules.agreement_min_t),
        }
    return out


# ---------------------------------------------------------------------------- Datei, Report
def write_calibration(data: dict[str, Any], path: Path) -> None:
    """Deterministisch (feste Reihenfolge, Einrückung 1) – sauberer Git-Diff."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")


def load_calibration(path: Path) -> dict[str, Any] | None:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return data if isinstance(data, dict) and data.get("version") == VERSION else None


LEVEL_TEXT = {
    BELEGT: "belegt",
    SCHWACH: "schwach",
    KEIN_VORTEIL: "kein Vorteil",
    ZU_WENIG: "zu wenig Daten",
    NEUTRAL: "neutral (keine Richtungsaussage)",
}


def _pct(x: float | None, digits: int = 1, sign: bool = False) -> str:
    if x is None:
        return "–"
    return f"{x * 100:{'+' if sign else ''}.{digits}f} %".replace(".", ",")


def _num(x: float | None, fmt: str = "+.1f") -> str:
    return "–" if x is None else format(x, fmt).replace(".", ",")


def render_markdown(
    data: dict[str, Any], labels: dict[str, str], class_names: dict[str, str]
) -> str:
    """Kurze Kalibrierungstabelle für den Report-Anhang (Kennwert-Horizont, Richtungssignale)."""
    p = data["params"]
    lines = [
        "## Anhang: Kalibrierung (Eichung der Score-Bereiche)",
        "",
        f"Erzeugt {data['generated_at']} · Stichtage {data['first_date']} bis {data['data_through']} · "
        f"Training bis {p['train_end']}, Out-of-Sample danach · Datei `docs/calibration.json`, "
        "Befehl `uv run edgefinder calibrate`.",
        "",
        "**Vorteil (`edge`)** = Ø Forward-Rendite der Signale in Signalrichtung minus Ø Rendite aller "
        "Beobachtungen der Klasse im gleichen Zeitraum. **Stufen:** *belegt* = Vorteil in Gesamt, Training "
        f"und OOS positiv, t ≥ {p['min_t']:g} (mit n_eff), n_eff ≥ {p['min_n_eff']:g} (je Zeitraum ≥ "
        f"{p['min_n_eff_period']:g}) und Trefferquote über der Basis; *schwach* = gleichsinnig, aber t oder "
        "Stichprobe zu klein; *kein Vorteil* = Vorzeichen wechselt, null oder falsch herum; *zu wenig Daten* = "
        f"n_eff < {p['floor_n_eff']:g} in einem Zeitraum. Die Rechnung ist ein Blick zurück, keine Prognose; "
        "Assets einer Klasse sind korreliert (t optimistisch).",
        "",
        "### Richtungssignale je Profil und Klasse (bullish + bearish gepoolt, Kennwert-Horizont)",
        "",
        "| Profil | Klasse | Horizont | Stufe | n_eff | Trefferquote | Basis-Treffer | Vorteil | t | Vorteil Training | Vorteil OOS |",
        "|---|---|---|---|---|---|---|---|---|---|---|",
    ]
    for profile, by_class in data["summary"].items():
        for klass, s in by_class.items():
            lines.append(
                f"| {labels.get(profile, profile)} | {class_names.get(klass, klass)} | {s['horizon']} T | "
                f"**{LEVEL_TEXT[s['evidence']]}** | {_num(s['n_eff'], '.0f')} | {_pct(s['hit'])} | "
                f"{_pct(s['base_hit'])} | {_pct(s['edge'], 2, True)} | {_num(s['t'])} | "
                f"{_pct(s['edge_train'], 2, True)} | {_pct(s['edge_oos'], 2, True)} |"
            )
    lines += [
        "",
        "### Je Score-Bereich (Kennwert-Horizont)",
        "",
        "| Profil | Klasse | Bereich | Stufe | n_eff | Treffer | Basis (steigend) | Ø Rendite | Vorteil | Vorteil Training | Vorteil OOS |",
        "|---|---|---|---|---|---|---|---|---|---|---|",
    ]
    for profile, by_class in data["classes"].items():
        ph = str(p["primary_horizon"][profile])
        for klass, by_h in by_class.items():
            for b in p["buckets"]:
                c = by_h[ph][b["label"]]
                a = c["all"]
                lines.append(
                    f"| {labels.get(profile, profile)} | {class_names.get(klass, klass)} | {b['label']} | "
                    f"{LEVEL_TEXT[c['evidence']]} | {_num(a.get('n_eff'), '.0f')} | {_pct(a.get('hit'))} | "
                    f"{_pct(a.get('base_up'))} | {_pct(a.get('mean'), 2, True)} | {_pct(a.get('edge'), 2, True)} | "
                    f"{_pct(c['train'].get('edge'), 2, True)} | {_pct(c['oos'].get('edge'), 2, True)} |"
                )
    lines += [
        "",
        f"### Faktor-Übereinstimmung ≥ {p['agreement_threshold'] * 100:.0f} % (Richtungssignale, Kennwert-Horizont)",
        "",
        "| Profil | Klasse | Gruppe | Stufe | n_eff | Trefferquote | Vorteil | Vorteil Training | Vorteil OOS |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    for profile, by_class in data["agreement"].items():
        for klass, block in by_class.items():
            for name, title in (("high", "hoch"), ("low", "niedrig")):
                c = block[name]
                a = c["all"]
                lines.append(
                    f"| {labels.get(profile, profile)} | {class_names.get(klass, klass)} | {title} | "
                    f"{LEVEL_TEXT[c['evidence']]} | {_num(a.get('n_eff'), '.0f')} | {_pct(a.get('hit'))} | "
                    f"{_pct(a.get('edge'), 2, True)} | {_pct(c['train'].get('edge'), 2, True)} | "
                    f"{_pct(c['oos'].get('edge'), 2, True)} |"
                )
    lines.append("")
    return "\n".join(lines)


MARK_START, MARK_END = "<!-- calibration:start -->", "<!-- calibration:end -->"


def update_report(report: Path, section: str) -> None:
    """Setzt den Kalibrierungs-Anhang zwischen die Marker (oder hängt ihn an)."""
    text = report.read_text(encoding="utf-8") if report.exists() else ""
    block = f"{MARK_START}\n{section}\n{MARK_END}\n"
    pattern = re.compile(re.escape(MARK_START) + r".*?" + re.escape(MARK_END) + r"\n?", re.S)
    if pattern.search(text):
        text = pattern.sub(lambda _: block, text)
    else:
        text = text.rstrip("\n") + "\n\n" + block
    report.write_text(text, encoding="utf-8")
