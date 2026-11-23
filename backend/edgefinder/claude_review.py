# ruff: noqa: E501  (lange deutsche Texte)
"""Claude-Prüfagent (Etappe q): Eingabepaket bauen, Läufe lesen, Schutzprüfungen.

Der Webprozess und der Admin-Runner starten **nie** Programme. Dieses Modul schreibt nur Dateien
(feste Pfade unter `claude.base_dir`), und zwar:

  staging/<id>/input/…         Eingabepaket (edgefinder-eigen, nur Zwischenlager)
  staging/<id>/request.json    Parameter des Laufs (nur für die Anzeige „queued“)
  inbox/<id>.json              Anforderung (löst die systemd-`.path`-Unit `claude-review.path` aus)

`runs/` gehört root und ist für den Webprozess nur lesbar: `prepare.py` (root, `ExecStartPre=+`) übernimmt
das Paket per Deskriptor-Operationen nach `runs/<id>/input` (root-eigen, für den Agenten nur lesbar).
Grund: Sicherheitsbefund /security-review 2026-11-23 (TOCTOU edgefinder → root in einem edgefinder-eigenen
Lauf-Verzeichnis). Den Rest (journald-Auszug, `output/`, Protokolle, Status) erzeugt der getrennte Dienst
`claude-review.service` (Benutzer `claude-review`, Sandbox, Netz nur zum lokalen Allowlist-Proxy).
Lauf-IDs sind ausschließlich Zahlen (= ID des Admin-Auftrags); es gibt keine Pfadparameter vom Client.
"""

from __future__ import annotations

import contextlib
import json
import logging
import math
import os
import re
import shutil
import sqlite3
import stat
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from edgefinder import maintenance
from edgefinder.claude_scrub import scrub, scrub_secrets
from edgefinder.config import Config

log = logging.getLogger(__name__)

JOB = "claude_review"
RUN_ID_RE = re.compile(r"[1-9][0-9]{0,8}")
PROPOSAL_RE = re.compile(r"^proposal-[0-9]{1,3}\.diff$")
MAX_ANALYSIS_BYTES = 200_000
MAX_PROPOSAL_BYTES = 100_000
MAX_PROPOSALS = 10
MAX_AUDIT_LINE = 2_000
MAX_AUDIT_PAGE = 200
MAX_AUDIT_BYTES = 8_000_000
MAX_STATUS_BYTES = 20_000
QUEUED_STALE_SECONDS = 15 * 60  # länger „wartet“ = Dienst nicht gestartet (Unit fehlt?)
RUNNING_GRACE_SECONDS = 180
LIST_LIMIT = 20

# Quelltext-Schnappschuss: nur diese Wurzeln, nur Textendungen, feste Ausschlüsse
SNAPSHOT_ROOTS = ("backend", "frontend", "deploy", "docs")
SNAPSHOT_ROOT_FILES = ("config.yaml", "CLAUDE.md", "README.md", "pyproject.toml", "uv.lock")
SNAPSHOT_EXCLUDE_DIRS = frozenset(
    {
        "data",
        "node_modules",
        "dist",
        ".venv",
        ".git",
        "__pycache__",
        ".pytest_cache",
        ".ruff_cache",
        ".mypy_cache",
        ".claude",
        "coverage",
        "npm",  # deploy/claude-review/npm (nur Installationsquelle)
    }
)
SNAPSHOT_EXTENSIONS = frozenset(
    {".py", ".ts", ".tsx", ".js", ".mjs", ".cjs", ".css", ".html", ".md", ".yaml", ".yml", ".json"}
    | {".toml", ".sh", ".conf", ".service", ".timer", ".path", ".txt", ".sql", ".lock"}
)
SNAPSHOT_EXCLUDE_NAMES = frozenset({"package-lock.json"})
SNAPSHOT_EXCLUDE_PATTERNS = (
    re.compile(r"^\.env"),
    re.compile(r"(?i)\.(pem|key|crt|p12|pfx|db|sqlite3?|log)$"),
    re.compile(r"(?i)^(id_[a-z0-9]+|deploy_key.*|.*\.secret)$"),
)
SNAPSHOT_MAX_FILE_BYTES = 600_000
# Dateinamen im Paket = Prüfung von prepare.py (root); Unzulässiges wird schon hier übersprungen
PACKAGE_NAME_RE = re.compile(r"[A-Za-z0-9._+@=~,()\[\] -]{1,128}")
STAGING_KEEP_DAYS = 2  # Zwischenlager ist nach der Übernahme durch prepare.py nutzlos


class PackageError(Exception):
    """Eingabepaket nicht baubar (z. B. zu groß); die Meldung ist für den Admin bestimmt."""


def valid_run_id(value: object) -> int | None:
    """Lauf-ID nur als positive Zahl ohne führende Nullen (kein Pfad, kein Vorzeichen)."""
    text = str(value)
    return int(text) if isinstance(value, int | str) and RUN_ID_RE.fullmatch(text) else None


def runs_dir(config: Config) -> Path:
    return config.claude.base_dir / "runs"


def staging_dir(config: Config) -> Path:
    return config.claude.base_dir / "staging"


def inbox_dir(config: Config) -> Path:
    return config.claude.base_dir / "inbox"


def run_dir(config: Config, run_id: int) -> Path:
    """Fester Pfad `runs/<Zahl>`; `run_id` muss ein `int` sein (Aufrufer validieren mit `valid_run_id`)."""
    if not isinstance(run_id, int) or isinstance(run_id, bool) or run_id < 1:
        raise ValueError("Ungültige Lauf-ID")
    return runs_dir(config) / str(run_id)


def installed(config: Config) -> bool:
    """Installiert = die Arbeitsverzeichnisse existieren (legt `install.sh` an)."""
    return runs_dir(config).is_dir() and inbox_dir(config).is_dir() and staging_dir(config).is_dir()


def _now() -> datetime:
    return datetime.now(UTC)


def _iso(moment: datetime) -> str:
    return moment.isoformat(timespec="seconds")


# ---------------------------------------------------------------------------- Dateien lesen
def read_regular(path: Path, limit: int) -> str | None:
    """Reguläre Datei (kein Symlink) als Text lesen; zu groß, fehlend oder kein UTF-8 → None.

    `O_NOFOLLOW`: der Agent schreibt in `output/`; ein dort abgelegter Symlink darf nie gelesen werden.
    """
    try:
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    except OSError:
        return None
    try:
        info = os.fstat(fd)
        if not stat.S_ISREG(info.st_mode) or info.st_size > limit:
            return None
        with os.fdopen(fd, "rb", closefd=False) as handle:
            data = handle.read(limit + 1)
        return data.decode("utf-8") if len(data) <= limit else None
    except (OSError, UnicodeDecodeError):
        return None
    finally:
        os.close(fd)


def _read_json(path: Path, limit: int = MAX_STATUS_BYTES) -> dict[str, Any] | None:
    text = read_regular(path, limit)
    if text is None:
        return None
    try:
        data = json.loads(text)
    except ValueError:
        return None
    return data if isinstance(data, dict) else None


def _safe_dir(path: Path) -> bool:
    return path.is_dir() and not path.is_symlink()


# ---------------------------------------------------------------------------- Lauf-Status
def _age_seconds(stamp: str | None, now: datetime) -> float | None:
    if not stamp:
        return None
    try:
        return (now - datetime.fromisoformat(stamp)).total_seconds()
    except ValueError:
        return None


def run_state(config: Config, run_id: int, now: datetime | None = None) -> dict[str, Any]:
    """Zustand eines Laufs aus den Dateien: queued/running/ok/error/timeout/stale.

    Ohne `status.json` wartet der Lauf auf den Dienst; zu lange Wartezeit oder ein „running“ ohne Ende
    nach `runtime_max_seconds` (Dienst abgestürzt) gilt als Fehler, damit nichts ewig „aktiv“ bleibt.
    """
    now = now or _now()
    base = run_dir(config, run_id)
    if not _safe_dir(base):
        # noch nicht von prepare.py (root) übernommen: Anforderung liegt im Zwischenlager
        staged = _read_json(staging_dir(config) / str(run_id) / "request.json")
        if staged is None or not _safe_dir(staging_dir(config) / str(run_id)):
            return {"state": "missing"}
        base = staging_dir(config) / str(run_id)
    request = _read_json(base / "request.json") or {}
    status = _read_json(base / "status.json")
    created = request.get("created_at")
    if status is None or not status.get("state"):
        age = _age_seconds(created, now)
        if age is not None and age > QUEUED_STALE_SECONDS:
            return {
                "state": "stale",
                "created_at": created,
                "message": "Dienst hat den Lauf nicht gestartet (claude-review.path/-service prüfen).",
            }
        return {"state": "queued", "created_at": created}
    state = str(status.get("state"))
    out: dict[str, Any] = {
        key: status.get(key)
        for key in (
            "started_at",
            "finished_at",
            "duration_seconds",
            "exit_code",
            "turns",
            "cost_usd",
            "message",
        )
        if status.get(key) is not None
    }
    out["created_at"] = created
    if state == "running":
        age = _age_seconds(status.get("started_at"), now)
        if age is not None and age > config.claude.runtime_max_seconds + RUNNING_GRACE_SECONDS:
            state = "stale"
            out["message"] = "Lauf wurde nicht ordentlich beendet (Dienst abgebrochen)."
    out["state"] = state if state in {"running", "ok", "error", "timeout", "stale"} else "error"
    return out


ACTIVE_STATES = frozenset({"preparing", "queued", "running"})


def list_runs(
    conn: sqlite3.Connection, config: Config, now: datetime | None = None
) -> list[dict[str, Any]]:
    """Letzte Läufe: Admin-Aufträge (`claude_review`) verknüpft mit dem Dateistatus (neueste zuerst)."""
    now = now or _now()
    rows = conn.execute(
        "SELECT id, requested_at, started_at, finished_at, status, summary FROM admin_jobs "
        "WHERE job = ? ORDER BY id DESC LIMIT ?",
        (JOB, LIST_LIMIT),
    ).fetchall()
    runs: list[dict[str, Any]] = []
    for row in rows:
        entry: dict[str, Any] = {"id": row["id"], "requested_at": row["requested_at"]}
        state = run_state(config, row["id"], now)
        if state["state"] == "missing":
            # kein Paket: Auftrag wartet/läuft noch oder ist fehlgeschlagen
            if row["status"] in ("queued", "running"):
                entry.update(state="preparing", message="Eingabepaket wird vorbereitet.")
            else:
                entry.update(
                    state="error", message=(row["summary"] or "Kein Eingabepaket erzeugt.")[:300]
                )
        else:
            entry.update(state)
        started, finished = entry.get("started_at"), entry.get("finished_at")
        if entry.get("duration_seconds") is None and started and finished:
            with contextlib.suppress(ValueError):
                entry["duration_seconds"] = round(
                    (
                        datetime.fromisoformat(finished) - datetime.fromisoformat(started)
                    ).total_seconds()
                )
        runs.append(entry)
    return runs


def active_run_id(
    conn: sqlite3.Connection, config: Config, now: datetime | None = None
) -> int | None:
    for run in list_runs(conn, config, now):
        if run["state"] in ACTIVE_STATES:
            return int(run["id"])
    return None


def limits(conn: sqlite3.Connection, config: Config, now: datetime | None = None) -> dict[str, Any]:
    """Abkühlzeit und Tageslimit (rollierend 24 h; zählt Aufträge, die ein Paket erzeugt haben oder noch laufen)."""
    now = now or _now()
    since = _iso(now - timedelta(hours=24))
    rows = conn.execute(
        "SELECT requested_at FROM admin_jobs WHERE job = ? AND requested_at >= ? "
        "AND status IN ('queued', 'running', 'ok') ORDER BY requested_at DESC",
        (JOB, since),
    ).fetchall()
    wait = 0
    if rows and config.claude.cooldown_minutes > 0:
        due = datetime.fromisoformat(rows[0][0]) + timedelta(minutes=config.claude.cooldown_minutes)
        wait = max(0, math.ceil((due - now).total_seconds()))
    return {
        "runs_today": len(rows),
        "max_runs_per_day": config.claude.max_runs_per_day,
        "cooldown_minutes": config.claude.cooldown_minutes,
        "wait_seconds": wait,
    }


def check_allowed(conn: sqlite3.Connection, config: Config, now: datetime | None = None) -> None:
    """Schutzprüfungen vor dem Einreihen; wirft `AdminJobError` (409 aktiv/nicht bereit, 429 Limits)."""
    from edgefinder.admin_jobs import AdminJobError  # Zirkelbezug vermeiden

    now = now or _now()
    if not config.claude.enabled:
        raise AdminJobError(409, "Der Claude-Prüfagent ist nicht aktiviert (siehe Anleitung).")
    if not installed(config):
        raise AdminJobError(409, "Der Claude-Prüfagent ist auf diesem Server nicht installiert.")
    if active_run_id(conn, config, now) is not None:
        raise AdminJobError(409, "Es läuft bereits eine Claude-Analyse.")
    info = limits(conn, config, now)
    if info["runs_today"] >= info["max_runs_per_day"]:
        raise AdminJobError(
            429,
            f"Tageslimit erreicht ({info['max_runs_per_day']} Analysen in 24 h; schützt das Abo-Kontingent).",
            3600,
        )
    if info["wait_seconds"]:
        raise AdminJobError(
            429,
            f"Abkühlzeit: bitte in {max(1, round(info['wait_seconds'] / 60))} Min. erneut versuchen.",
            info["wait_seconds"],
        )


def overview(
    conn: sqlite3.Connection, config: Config, now: datetime | None = None
) -> dict[str, Any]:
    now = now or _now()
    info = limits(conn, config, now)
    active = active_run_id(conn, config, now)
    return {
        "enabled": config.claude.enabled,
        "installed": installed(config),
        "active_id": active,
        "max_turns": config.claude.max_turns,
        "runtime_max_seconds": config.claude.runtime_max_seconds,
        "retention_days": config.claude.retention_days,
        **info,
    }


def get_run(conn: sqlite3.Connection, config: Config, run_id: int) -> dict[str, Any] | None:
    """Status, `analysis.md` und Vorschläge (nur Text). Feste Dateinamen, Größenlimits, kein Symlink."""
    now = _now()
    row = conn.execute(
        "SELECT id FROM admin_jobs WHERE id = ? AND job = ?", (run_id, JOB)
    ).fetchone()
    if row is None:
        return None
    entry = next((r for r in list_runs(conn, config, now) if r["id"] == run_id), None)
    if entry is None:  # älter als die Liste: Status direkt aus den Dateien
        entry = {"id": run_id, **run_state(config, run_id, now)}
        if entry["state"] == "missing":
            entry["state"] = "error"
    if not _safe_dir(run_dir(config, run_id)):
        entry["state"] = "error"
        return {**entry, "analysis_md": None, "proposals": [], "has_audit": False}
    out_dir = run_dir(config, run_id) / "output"
    analysis = None
    proposals: list[dict[str, str]] = []
    if _safe_dir(out_dir):
        analysis = read_regular(out_dir / "analysis.md", MAX_ANALYSIS_BYTES)
        names = sorted(
            (e.name for e in _scandir(out_dir) if PROPOSAL_RE.match(e.name)),
            key=lambda n: int(n[9:-5]),
        )
        for name in names[:MAX_PROPOSALS]:
            text = read_regular(out_dir / name, MAX_PROPOSAL_BYTES)
            if text is not None:
                proposals.append({"name": name, "text": scrub_secrets(text)})
    return {
        **entry,
        "analysis_md": scrub_secrets(analysis) if analysis is not None else None,
        "proposals": proposals,
        "has_audit": (run_dir(config, run_id) / "audit.jsonl").is_file(),
    }


def _scandir(path: Path) -> list[os.DirEntry[str]]:
    try:
        with os.scandir(path) as it:
            return [e for e in it if e.is_file(follow_symlinks=False)]
    except OSError:
        return []


def read_audit(config: Config, run_id: int, offset: int, limit: int) -> dict[str, Any] | None:
    """Zeilen aus `audit.jsonl` (JSON je Zeile, gekürzt, noch einmal geschwärzt); paginiert."""
    path = run_dir(config, run_id) / "audit.jsonl"
    offset = max(0, offset)
    limit = max(1, min(limit, MAX_AUDIT_PAGE))
    text = read_regular(path, MAX_AUDIT_BYTES)
    if text is None:
        return None
    lines = [ln for ln in text.splitlines() if ln.strip()]
    entries: list[Any] = []
    for line in lines[offset : offset + limit]:
        try:
            item = json.loads(scrub(line[: MAX_AUDIT_LINE * 4]))
        except ValueError:
            item = {"raw": scrub(line[:MAX_AUDIT_LINE])}
        entries.append(item)
    return {"total": len(lines), "offset": offset, "limit": limit, "entries": entries}


# ---------------------------------------------------------------------------- Eingabepaket
def snapshot_files(source: Path) -> Iterator[tuple[Path, str]]:
    """(Pfad, relativer Name) der Schnappschuss-Dateien; `os.walk` mit festen Ausschlüssen, ohne Symlinks."""
    for name in SNAPSHOT_ROOT_FILES:
        path = source / name
        if path.is_file() and not path.is_symlink():
            yield path, name
    for root_name in SNAPSHOT_ROOTS:
        top = source / root_name
        if not _safe_dir(top):
            continue
        for current, dirs, files in os.walk(top, followlinks=False):
            dirs[:] = sorted(
                d
                for d in dirs
                if d not in SNAPSHOT_EXCLUDE_DIRS and not (Path(current) / d).is_symlink()
            )
            for file in sorted(files):
                path = Path(current) / file
                if (
                    path.is_symlink()
                    or file in SNAPSHOT_EXCLUDE_NAMES
                    or path.suffix.lower() not in SNAPSHOT_EXTENSIONS
                    or any(p.search(file) for p in SNAPSHOT_EXCLUDE_PATTERNS)
                ):
                    continue
                yield path, path.relative_to(source).as_posix()


def git_head(source: Path) -> str | None:
    """Commit-Hash aus `.git` ohne Programmaufruf (HEAD → Ref/packed-refs); None, wenn nicht lesbar."""
    try:
        head = (source / ".git" / "HEAD").read_text(encoding="utf-8").strip()
        if not head.startswith("ref: "):
            return head[:40] if re.fullmatch(r"[0-9a-f]{40}", head) else None
        ref = head[5:]
        loose = source / ".git" / ref
        if loose.is_file():
            return loose.read_text(encoding="utf-8").strip()[:40]
        for line in (source / ".git" / "packed-refs").read_text(encoding="utf-8").splitlines():
            if line.endswith(" " + ref):
                return line.split()[0][:40]
    except (OSError, UnicodeDecodeError):
        pass
    return None


class _Writer:
    """Schreibt Dateien ins Paket und zählt Bytes (Limit); alles mit Modus 0640."""

    def __init__(self, root: Path, limit: int, max_entries: int = 20_000) -> None:
        self.root = root
        self.limit = limit
        self.max_entries = max_entries  # Dateien + Verzeichnisse (so zählt prepare.py)
        self.total = 0
        self.files: dict[str, int] = {}
        self.dirs: set[Path] = set()

    def write(self, name: str, text: str) -> None:
        data = text.encode("utf-8")
        self.total += len(data)
        if self.total > self.limit:
            raise PackageError(
                f"Eingabepaket größer als {self.limit // (1024 * 1024)} MB (Limit claude.max_package_mb)."
            )
        target = self.root / name
        self.dirs.update(p for p in Path(name).parents if p != Path())
        if len(self.files) + 1 + len(self.dirs) > self.max_entries:
            raise PackageError(
                f"Eingabepaket hat mehr als {self.max_entries} Dateien (Limit claude.max_package_files)."
            )
        target.parent.mkdir(parents=True, exist_ok=True, mode=0o750)
        target.write_bytes(data)
        target.chmod(0o640)
        self.files[name] = len(data)


def _json_text(data: Any) -> str:
    return json.dumps(data, ensure_ascii=False, indent=1, default=str) + "\n"


def _fetch_runs_export(
    conn: sqlite3.Connection, config: Config, now: datetime
) -> list[dict[str, Any]]:
    since = _iso(now - timedelta(days=config.claude.fetch_runs_days))
    rows = conn.execute(
        "SELECT id, source, started_at, finished_at, status, items, requests, error FROM fetch_runs "
        "WHERE started_at >= ? ORDER BY id",
        (since,),
    )
    return [{**dict(r), "error": scrub((r["error"] or "")[:500]) or None} for r in rows]


def _data_status(conn: sqlite3.Connection, config: Config, now: datetime) -> dict[str, Any]:
    since = _iso(now - timedelta(days=config.claude.fetch_runs_days))
    watched = [(n, s.stale_after_hours) for n, s in config.sources.items() if s.enabled]
    watched += [
        (maintenance.SOURCE_MAINTAIN, config.maintenance.maintain_stale_after_hours),
        (maintenance.SOURCE_EVALUATE, config.maintenance.evaluate_stale_after_hours),
    ]
    sources = []
    for name, hours in watched:
        last = conn.execute(
            "SELECT MAX(finished_at) FROM fetch_runs WHERE source = ? AND status = 'success'",
            (name,),
        ).fetchone()[0]
        counts = {
            r["status"]: r["n"]
            for r in conn.execute(
                "SELECT status, count(*) AS n FROM fetch_runs WHERE source = ? AND started_at >= ? GROUP BY status",
                (name, since),
            )
        }
        total = sum(counts.values())
        age_h = None
        if last:
            age_h = round((now - datetime.fromisoformat(last)).total_seconds() / 3600, 1)
        sources.append(
            {
                "source": name,
                "stale_after_hours": hours,
                "last_success": last,
                "age_hours": age_h,
                "stale": last is None or (age_h is not None and age_h > hours),
                "runs_in_window": total,
                "by_status": counts,
                "success_rate": round(counts.get("success", 0) / total, 3) if total else None,
            }
        )
    return {
        "generated_at": _iso(now),
        "window_days": config.claude.fetch_runs_days,
        "sources": sources,
        "stale": [s["source"] for s in sources if s["stale"]],
    }


def _scores_stats(conn: sqlite3.Connection) -> dict[str, Any]:
    """Nur Kennzahlen je Profil (keine Rohzeilen): Anzahl, Zeitraum, Mittelwert/Streuung, Label-Verteilung."""
    profiles: dict[str, Any] = {}
    for r in conn.execute(
        "SELECT profile, count(*) AS n, min(date) AS first, max(date) AS last, avg(score) AS mean, "
        "avg(score * score) AS sq, avg(coverage) AS coverage, count(DISTINCT asset_id) AS assets FROM scores GROUP BY profile"
    ):
        mean = r["mean"] or 0.0
        var = max(0.0, (r["sq"] or 0.0) - mean * mean)
        profiles[r["profile"]] = {
            "rows": r["n"],
            "assets": r["assets"],
            "first_date": r["first"],
            "last_date": r["last"],
            "mean_score": round(mean, 3),
            "std_score": round(math.sqrt(var), 3),
            "mean_coverage": round(r["coverage"] or 0.0, 3),
            "labels": {},
            "origins": {},
        }
    for r in conn.execute(
        "SELECT profile, label, count(*) AS n FROM scores GROUP BY profile, label"
    ):
        profiles[r["profile"]]["labels"][r["label"]] = r["n"]
    for r in conn.execute(
        "SELECT profile, origin, count(*) AS n FROM scores GROUP BY profile, origin"
    ):
        profiles[r["profile"]]["origins"][r["origin"]] = r["n"]
    per_day = [
        {"date": r["date"], "rows": r["n"], "mean_coverage": round(r["c"], 3)}
        for r in conn.execute(
            "SELECT date, count(*) AS n, avg(coverage) AS c FROM scores GROUP BY date ORDER BY date DESC LIMIT 14"
        )
    ]
    return {"profiles": profiles, "last_days": per_day}


def _calibration_summary(config: Config) -> dict[str, Any]:
    cal = maintenance.load_current_calibration(config)
    if not cal:
        return {"available": False}
    summary: dict[str, Any] = {"available": True}
    for key, value in cal.items():
        if isinstance(value, str | int | float | bool) or value is None:
            summary[key] = value
        elif isinstance(value, dict | list):
            summary[key] = {"type": type(value).__name__, "size": len(value)}
    return summary


def build_package(
    conn: sqlite3.Connection,
    config: Config,
    run_id: int,
    notes: list[str] | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Eingabepaket nach `runs/<id>/input` schreiben und danach die Anforderung in die Inbox legen.

    Nur Python-Dateioperationen. Alles, was Secrets enthalten könnte, wird geschwärzt (Quelltext:
    Secrets; Texte aus Fehlermeldungen/Berichten zusätzlich E-Mail-Adressen). Bei Fehlern wird
    das halbfertige Verzeichnis entfernt; die Anforderung entsteht erst ganz am Ende (atomar).
    """
    now = now or _now()
    base = staging_dir(config) / str(run_id)
    if base.exists() or run_dir(config, run_id).exists():
        raise PackageError(f"Lauf {run_id} existiert schon.")
    staging_dir(config).mkdir(parents=True, exist_ok=True)
    base.mkdir(mode=0o750)
    try:
        writer = _Writer(
            base / "input",
            config.claude.max_package_mb * 1024 * 1024,
            config.claude.max_package_files,
        )
        (base / "input").mkdir(mode=0o750)
        for name in (maintenance.REVIEW_NAME, maintenance.DRIFT_NAME):
            text = read_regular(config.data_dir / name, 2_000_000)
            if text is not None:
                writer.write(name, scrub(text))
        writer.write("calibration-summary.json", _json_text(_calibration_summary(config)))
        writer.write("fetch-runs.json", _json_text(_fetch_runs_export(conn, config, now)))
        writer.write("data-status.json", _json_text(_data_status(conn, config, now)))
        writer.write("scores-stats.json", _json_text(_scores_stats(conn)))
        source = config.claude.source_dir
        skipped = 0
        for path, rel in snapshot_files(source):
            text = read_regular(path, SNAPSHOT_MAX_FILE_BYTES)
            if text is None:
                skipped += 1
                continue
            if not all(PACKAGE_NAME_RE.fullmatch(part) for part in Path(rel).parts):
                skipped += 1  # prepare.py würde das ganze Paket wegen des Namens ablehnen
                continue
            if Path(rel).name == "CLAUDE.md":
                rel += ".txt"  # nicht als Anweisungsdatei ladbar (Daten, keine Anweisungen)
            writer.write(f"snapshot/{rel}", scrub_secrets(text))
        snapshot_count = sum(1 for n in writer.files if n.startswith("snapshot/"))
        if snapshot_count == 0:
            raise PackageError("Quelltext-Schnappschuss ist leer (claude.source_dir prüfen).")
        manifest = {
            "run_id": run_id,
            "created_at": _iso(now),
            "source_commit": git_head(source),
            "model_version": config.scoring.model_version,
            "notes": notes or [],
            "later_added_by_service": {
                "journal.txt": f"journald der edgefinder-Dienste, letzte {config.claude.journal_hours} h, geschwärzt"
            },
            "snapshot_files": snapshot_count,
            "snapshot_skipped": skipped,
            "files": writer.files,
        }
        writer.write("MANIFEST.json", _json_text(manifest))
        request = {
            "id": run_id,
            "created_at": _iso(now),
            "max_turns": config.claude.max_turns,
            "runtime_max_seconds": config.claude.runtime_max_seconds,
            "journal_hours": config.claude.journal_hours,
            "package_bytes": writer.total,
            # Grenzen für prepare.py (root); dort zusätzlich harte Obergrenzen
            "max_package_bytes": config.claude.max_package_mb * 1024 * 1024,
            "max_package_files": config.claude.max_package_files,
            "retention_days": config.claude.retention_days,
        }
        _write_atomic(base / "request.json", _json_text(request))
        inbox = inbox_dir(config)
        inbox.mkdir(parents=True, exist_ok=True)
        _write_atomic(inbox / f"{run_id}.json", _json_text(request))
    except BaseException:
        shutil.rmtree(base, ignore_errors=True)
        raise
    return request


def _write_atomic(path: Path, text: str) -> None:
    tmp = path.with_name(f".{path.name}.tmp")
    tmp.write_text(text, encoding="utf-8")
    tmp.chmod(0o640)
    tmp.replace(path)


# ---------------------------------------------------------------------------- Job + Aufräumen
def run_job(conn: sqlite3.Connection, config: Config) -> maintenance.Run:
    """Allowlist-Job `claude_review`: Prüfbericht neu rechnen, Paket bauen, Anforderung schreiben."""
    run = maintenance.Run()
    if not config.claude.enabled:
        run.errors.append("claude.enabled ist false")
        return run
    row = conn.execute(
        "SELECT id FROM admin_jobs WHERE job = ? AND status = 'running' ORDER BY id DESC LIMIT 1",
        (JOB,),
    ).fetchone()
    if row is None:
        run.errors.append("Kein laufender Auftrag zur Lauf-ID")
        return run
    run_id = int(row["id"])
    notes: list[str] = []
    review = maintenance.run_review(conn, config)
    if review.errors:
        notes = [scrub(e)[:300] for e in review.errors]
        log.warning("Prüfbericht mit Fehlern; Paket enthält Hinweise: %s", "; ".join(notes))
    try:
        request = build_package(conn, config, run_id, notes)
    except PackageError as exc:
        run.errors.append(str(exc))
        return run
    run.items = int(request["package_bytes"])
    log.info(
        "Claude-Eingabepaket %d geschrieben (%d Bytes), Anforderung in der Inbox", run_id, run.items
    )
    return run


def _remove_old(root: Path, cutoff: datetime, *, dry_run: bool) -> int:
    removed = 0
    for entry in os.scandir(root):
        if not entry.is_dir(follow_symlinks=False) or not RUN_ID_RE.fullmatch(entry.name):
            continue
        marker = Path(entry.path) / "request.json"
        try:
            mtime = datetime.fromtimestamp(
                (marker if marker.exists() else Path(entry.path)).stat().st_mtime, UTC
            )
        except OSError:
            continue
        if mtime < cutoff:
            if not dry_run:
                shutil.rmtree(entry.path, ignore_errors=True)
            removed += 1
    return removed


def cleanup_runs(config: Config, now: datetime | None = None, *, dry_run: bool = False) -> int:
    """Zwischenlager (> 2 Tage) und Läufe älter als `claude.retention_days` löschen.

    `runs/` gehört root: der Webbenutzer kann dort nicht löschen; das übernimmt `prepare.py` (root) beim
    nächsten Lauf. Ist `runs/` nicht beschreibbar, wird es hier übersprungen.
    """
    now = now or _now()
    removed = 0
    staging = staging_dir(config)
    if _safe_dir(staging):
        removed += _remove_old(staging, now - timedelta(days=STAGING_KEEP_DAYS), dry_run=dry_run)
    root = runs_dir(config)
    if _safe_dir(root) and os.access(root, os.W_OK):
        removed += _remove_old(
            root, now - timedelta(days=config.claude.retention_days), dry_run=dry_run
        )
    return removed
