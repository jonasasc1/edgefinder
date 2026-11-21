# ruff: noqa: E501  (lange deutsche Texte)
"""Wartungszyklus: Live-Signale auswerten, Eichung neu erzeugen, Drift-Bericht (Etappe o).

Der Zyklus **misst und meldet**. Er ändert nie Gewichte oder Faktoren und deployt nichts; Modelländerungen
laufen im Modellpflege-Zyklus (CLAUDE.md) mit Freigabe von Jonas. Jeder Lauf steht in `fetch_runs`
(Quellen `evaluate` und `maintain`) und erscheint so im Datenstatus.
"""

from __future__ import annotations

import gc
import json
import logging
import sqlite3
from collections import defaultdict
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any

from edgefinder.backtest import calibration, live
from edgefinder.config import Config

log = logging.getLogger(__name__)

CALIBRATION_NAME = "calibration.json"
DRIFT_NAME = "drift-report.json"
REVIEW_NAME = "review.md"
SOURCE_EVALUATE = "evaluate"
SOURCE_MAINTAIN = "maintain"
MAX_ERROR_LENGTH = 1000


def calibration_paths(config: Config) -> list[Path]:
    """Eichungsdateien in Lesereihenfolge: erst Datenverzeichnis (Wartung), dann Git-Fallback."""
    return [config.data_dir / CALIBRATION_NAME, config.backtest.calibration_file]


@dataclass
class Run:
    items: int = 0
    errors: list[str] = field(default_factory=list)


@contextmanager
def recorded_run(conn: sqlite3.Connection, source: str) -> Iterator[Run]:
    """Lauf in `fetch_runs` protokollieren (success/partial/error); Ausnahmen werden gesammelt."""
    started = datetime.now(UTC).isoformat(timespec="seconds")
    run_id = conn.execute(
        "INSERT INTO fetch_runs (source, started_at, status) VALUES (?, ?, 'running')",
        (source, started),
    ).lastrowid
    run = Run()
    try:
        yield run
    except Exception as exc:
        log.exception("%s: Lauf abgebrochen", source)
        run.errors.append(f"{type(exc).__name__}: {exc}")
    status = "success" if not run.errors else ("partial" if run.items else "error")
    conn.execute(
        "UPDATE fetch_runs SET finished_at = ?, status = ?, items = ?, error = ? WHERE id = ?",
        (
            datetime.now(UTC).isoformat(timespec="seconds"),
            status,
            run.items,
            "; ".join(run.errors)[:MAX_ERROR_LENGTH] or None,
            run_id,
        ),
    )


def run_evaluate(conn: sqlite3.Connection, config: Config) -> Run:
    with recorded_run(conn, SOURCE_EVALUATE) as run:
        result = live.evaluate(conn, config)
        run.items = result.created
        log.info(
            "Auswertung: %d neue Ergebnisse, %d Horizonte laufen noch, %d ohne Einstiegskurs",
            result.created,
            result.open,
            result.unpriced,
        )
    return run


# ---------------------------------------------------------------------------- Backfill
def missing_dates(conn: sqlite3.Connection, config: Config, today: date) -> list[date]:
    """Stichtage (Wochentag `backtest.score_weekday`) ab `backtest.start` bis gestern ohne Score."""
    have = {r[0] for r in conn.execute("SELECT DISTINCT date FROM scores")}
    weekday = config.backtest.score_weekday
    out = []
    day = config.backtest.start
    while day < today:
        wanted = day.weekday() < 5 and (weekday is None or day.weekday() == weekday)
        if wanted and day.isoformat() not in have:
            out.append(day)
        day += timedelta(days=1)
    return out


def stale_backfill(conn: sqlite3.Connection, config: Config) -> int:
    """Backfill-Zeilen eines anderen Modellstands (`scoring.model_version`)."""
    return conn.execute(
        "SELECT COUNT(*) FROM scores WHERE origin = 'backfill' AND COALESCE(model_version, '') != ?",
        (config.scoring.model_version,),
    ).fetchone()[0]


def backfill(conn: sqlite3.Connection, config: Config, *, today: date | None = None) -> int:
    """Fehlende wöchentliche Stichtage nachrechnen; bei neuer `model_version` komplett neu.

    Jahr für Jahr mit frischer Engine (Speicher), Live-Zeilen bleiben unberührt (siehe `persist`).
    """
    from edgefinder.scoring.engine import ScoreEngine

    today = today or datetime.now(UTC).date()
    stale = stale_backfill(conn, config)
    if stale:
        log.info(
            "Neue Modellversion %s: %d alte Backfill-Scores werden neu gerechnet",
            config.scoring.model_version,
            stale,
        )
        conn.execute(
            "DELETE FROM scores WHERE origin = 'backfill'"
        )  # Komponenten: ON DELETE CASCADE
    days = missing_dates(conn, config, today)
    by_year: dict[int, list[date]] = defaultdict(list)
    for day in days:
        by_year[day.year].append(day)
    count = 0
    for year, items in sorted(by_year.items()):
        engine = ScoreEngine(config, conn)
        for day in items:
            count += len(engine.run_day(day, detail=False))
        del engine
        gc.collect()
        log.info("Backfill %d: %d Stichtage, bisher %d Scores", year, len(items), count)
    return count


# ---------------------------------------------------------------------------- Dateien
def write_json_atomic(path: Path, data: dict[str, Any], *, indent: int | None = 1) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=indent) + "\n", encoding="utf-8")
    tmp.replace(path)  # atomar: die API liest nie eine halbe Datei


def load_current_calibration(config: Config) -> dict[str, Any] | None:
    for path in calibration_paths(config):
        data = calibration.load_calibration(path)
        if data:
            return data
    return None


def run_maintain(conn: sqlite3.Connection, config: Config, *, today: date | None = None) -> Run:
    """(a) Backfill ergänzen, (b) Eichung erzeugen, (c) Drift-Bericht und Review; jeder Schritt für sich."""
    with recorded_run(conn, SOURCE_MAINTAIN) as run:

        def step(name: str, func: Any) -> Any:
            try:
                return func()
            except Exception as exc:  # ein Schritt darf die folgenden nicht verhindern
                log.exception("Wartung: %s fehlgeschlagen", name)
                run.errors.append(f"{name}: {type(exc).__name__}: {exc}")
                return None

        step("Auswertung", lambda: live.evaluate(conn, config))
        added = step("Backfill", lambda: backfill(conn, config, today=today))
        run.items = added or 0
        data = step("Eichung", lambda: calibration.build_calibration(conn, config))
        if data and data["scores"]:
            path = config.data_dir / CALIBRATION_NAME
            step("Eichung schreiben", lambda: write_json_atomic(path, data))
            log.info(
                "Eichung: %d Scores (%s bis %s) → %s",
                data["scores"],
                data["first_date"],
                data["data_through"],
                path,
            )
        elif data is not None:
            run.errors.append("Eichung: keine Scores vorhanden")
        data = data or load_current_calibration(config)
        report = step(
            "Drift-Bericht", lambda: live.build_trackrecord(conn, config, data, today=today)
        )
        if report:
            step(
                "Bericht schreiben", lambda: write_json_atomic(config.data_dir / DRIFT_NAME, report)
            )
            step(
                "Review schreiben",
                lambda: (config.data_dir / REVIEW_NAME).write_text(
                    render_review(report, config), encoding="utf-8"
                ),
            )
    return run


# ---------------------------------------------------------------------------- Review-Vorlage
STATUS_TEXT = {
    live.ZU_FRUEH: "zu früh",
    live.IM_RAHMEN: "im Rahmen",
    live.SCHWAECHER: "schwächer als die Eichung",
    live.BESSER: "besser als die Eichung",
    live.GEGENLAEUFIG: "gegenläufig",
    live.OHNE_EICHUNG: "ohne Eichung",
    "kein_vergleich": "kein Vergleich",
}


def _pct(value: float | None, digits: int = 1) -> str:
    return "–" if value is None else f"{value * 100:.{digits}f} %".replace(".", ",")


def render_review(report: dict[str, Any], config: Config) -> str:
    """Kurze Markdown-Vorlage für den nächsten Modellpflege-Termin (nur Zahlen, keine Empfehlung)."""
    lines = [
        f"# Modellpflege-Vorlage (Stand {report['today']}, Modell {report['model_version']})",
        "",
        f"Live seit {report['live_since'] or '–'}; ausgewertet: {report['evaluated']} Signale "
        f"(wöchentlich in den Gruppen: {report['evaluated_weekly']}), offen: {report['open']}. "
        f"Fortschritt Eichung: {round(report['progress'] * 100)} % "
        f"({report['calibrated_groups']} von {len(report['groups'])} Gruppen geeicht).",
        "",
        "## Gruppen (Profil × Klasse, wöchentliche Signale)",
        "",
        "| Profil | Klasse | n / n_eff | Wochen | Treffer (Basis) | Vorteil live | Vorteil Eichung | Status |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for g in report["groups"]:
        lines.append(
            f"| {config.profiles[g['profile']].label} | {g['asset_class']} | {g['n']} / {g['n_eff']} "
            f"| {g['weeks']} | {_pct(g['hit'])} ({_pct(g['base_hit'])}) | {_pct(g['edge'], 2)} "
            f"| {_pct(g['cal_edge'], 2)} | {STATUS_TEXT.get(g['status'], g['status'])} |"
        )
    warn = [f for f in report["factors"] if f["warn"]]
    lines += ["", "## Faktor-Warnungen", ""]
    if warn:
        lines += [
            f"- {f['factor']} ({f['asset_class']}, {f['profile']}): seit {f['weeks_against']} Wochen "
            f"gegenläufig (IC live {f['ic']}, Backtest {f['backtest_ic']})"
            for f in warn
        ]
    else:
        lines.append("Keine.")
    lines += [
        "",
        "## Ablauf (CLAUDE.md „Modellpflege-Zyklus“)",
        "",
        "1. Hypothese ökonomisch begründen, nicht nur „sieht besser aus“.",
        "2. Test auf Training/OOS **und** Forward-Zeitraum seit der letzten Änderung (nie zum Tuning benutzen).",
        "3. Höchstens 2–3 Varianten; Mindestabstand zur letzten Änderung beachten.",
        "4. Vorschlag mit Zahlen an Jonas; nur nach Freigabe übernehmen, `scoring.model_version` erhöhen.",
        "",
        "Diese Vorlage misst und meldet; sie empfiehlt nichts und ändert nichts.",
        "",
    ]
    return "\n".join(lines)
