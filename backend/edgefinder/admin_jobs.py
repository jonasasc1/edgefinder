# ruff: noqa: E501  (lange deutsche Texte)
"""Admin-Bereich: Rolle, Job-Warteschlange und Runner (Etappe p).

Der Webprozess ist gehärtet und startet nie Programme. Er schreibt nur Zeilen in `admin_jobs` und
berührt eine Trigger-Datei; der systemd-Dienst `edgefinder-adminjobs` (`edgefinder admin run`) arbeitet
die Warteschlange ab. Ausgeführt wird ausschließlich, was in `JOBS` steht (feste Python-Funktionen,
kein Shell, keine Client-Eingabe im Befehl). Die Allowlist steht zusätzlich in `config.yaml: admin.jobs`.
"""

from __future__ import annotations

import logging
import sqlite3
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import Any

from edgefinder import claude_review, maintenance
from edgefinder.config import Config
from edgefinder.db import connect, migrate, transaction

log = logging.getLogger(__name__)

TRIGGER_NAME = ".adminjobs.trigger"
MAX_SUMMARY = 300
ACTIVE = ("queued", "running")
RECENT_LIMIT = 20

JobFunc = Callable[[sqlite3.Connection, Config], maintenance.Run]
# Feste Allowlist: Name → Python-Funktion. Nichts anderes wird je ausgeführt.
JOBS: dict[str, JobFunc] = {
    "review": lambda conn, config: maintenance.run_review(conn, config),
    "maintain": lambda conn, config: maintenance.run_maintain(conn, config),
    "score": lambda conn, config: maintenance.run_score(conn, config),
    "evaluate": lambda conn, config: maintenance.run_evaluate(conn, config),
    # Eingabepaket für den Claude-Prüfagenten bauen (läuft selbst nicht; Dienst `claude-review`)
    "claude_review": claude_review.run_job,
}


class AdminJobError(Exception):
    """Auftrag abgelehnt; `status` ist der HTTP-Status (409 aktiv, 429 Abkühlzeit/Queue voll)."""

    def __init__(self, status: int, detail: str, retry_after: int | None = None) -> None:
        super().__init__(detail)
        self.status = status
        self.detail = detail
        self.retry_after = retry_after


def _now() -> datetime:
    return datetime.now(UTC)


def _iso(moment: datetime) -> str:
    return moment.isoformat(timespec="seconds")


def audit(conn: sqlite3.Connection, actor: str, action: str, detail: str = "") -> None:
    """Admin-Aktion protokollieren (Tabelle + Journal); nie Header, Token oder Inhalte."""
    conn.execute(
        "INSERT INTO admin_audit (at, actor, action, detail) VALUES (?, ?, ?, ?)",
        (_iso(_now()), actor[:254], action[:64], detail[:500]),
    )
    log.info("Admin-Aktion: %s %s (%s)", action, detail, actor)


# ---------------------------------------------------------------------------- Rolle (nur CLI)
def set_admin(conn: sqlite3.Connection, email: str, value: bool, *, force: bool = False) -> str:
    """Admin-Rolle vergeben/entziehen. Legt das Konto bei `grant` an. Gibt eine Meldung zurück.

    `revoke` entfernt den letzten Admin nur mit `force`; unbekannte Konten ergeben `LookupError`.
    """
    stamp = _iso(_now())
    with transaction(conn):
        if value:
            name = email.split("@", 1)[0][:64]
            conn.execute(
                "INSERT INTO users (email, display_name, created_at, last_seen_at) "
                "VALUES (?, ?, ?, ?) ON CONFLICT (email) DO NOTHING",
                (email, name, stamp, stamp),
            )
        row = conn.execute("SELECT id, is_admin FROM users WHERE email = ?", (email,)).fetchone()
        if row is None:
            raise LookupError(f"Kein Konto für {email}")
        if not value and row["is_admin"]:
            admins = conn.execute("SELECT count(*) FROM users WHERE is_admin = 1").fetchone()[0]
            if admins <= 1 and not force:
                raise PermissionError("Das ist der letzte Admin; zum Entfernen --force angeben.")
        conn.execute("UPDATE users SET is_admin = ? WHERE id = ?", (int(value), row["id"]))
        audit(conn, "cli", "admin_grant" if value else "admin_revoke", email)
    return f"{email}: Admin {'vergeben' if value else 'entzogen'}"


def list_admins(conn: sqlite3.Connection) -> list[str]:
    return [r[0] for r in conn.execute("SELECT email FROM users WHERE is_admin = 1 ORDER BY email")]


# ---------------------------------------------------------------------------- Warteschlange
def job_row(row: sqlite3.Row) -> dict[str, Any]:
    return {key: row[key] for key in row.keys() if key != "requested_by_user_id"}  # noqa: SIM118


JOB_COLUMNS = (
    "j.id, j.job, u.email AS requested_by, j.requested_at, j.started_at, j.finished_at, "
    "j.status, j.summary, j.log_tail"
)


def get_job(conn: sqlite3.Connection, job_id: int) -> dict[str, Any] | None:
    row = conn.execute(
        f"SELECT {JOB_COLUMNS} FROM admin_jobs j LEFT JOIN users u ON u.id = j.requested_by_user_id "  # noqa: S608
        "WHERE j.id = ?",
        (job_id,),
    ).fetchone()
    return job_row(row) if row else None


def recent_jobs(conn: sqlite3.Connection, limit: int = RECENT_LIMIT) -> list[dict[str, Any]]:
    rows = conn.execute(
        f"SELECT {JOB_COLUMNS} FROM admin_jobs j LEFT JOIN users u ON u.id = j.requested_by_user_id "  # noqa: S608
        "ORDER BY j.id DESC LIMIT ?",
        (limit,),
    )
    return [job_row(r) for r in rows]


def cooldown_wait(
    conn: sqlite3.Connection, config: Config, job: str, now: datetime | None = None
) -> int:
    """Sekunden bis der Job-Typ wieder angestoßen werden darf (0 = jetzt)."""
    now = now or _now()
    minutes = config.admin.cooldown_for(job)
    row = conn.execute(
        "SELECT MAX(finished_at) FROM admin_jobs WHERE job = ? AND status IN ('ok', 'error')",
        (job,),
    ).fetchone()
    if not row[0] or minutes <= 0:
        return 0
    due = datetime.fromisoformat(row[0]) + timedelta(minutes=minutes)
    return max(0, int((due - now).total_seconds()) + 1)


def enqueue(
    conn: sqlite3.Connection,
    config: Config,
    job: str,
    user_id: int,
    actor: str,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Auftrag in die Warteschlange legen (Allowlist, ein aktiver je Typ, Abkühlzeit, Queue-Länge)."""
    now = now or _now()
    if job not in JOBS or job not in config.admin.jobs:
        raise AdminJobError(422, "Unbekannter oder nicht erlaubter Auftrag.")
    with transaction(conn):
        if conn.execute(
            "SELECT 1 FROM admin_jobs WHERE job = ? AND status IN ('queued', 'running')", (job,)
        ).fetchone():
            raise AdminJobError(409, "Dieser Auftrag wartet oder läuft bereits.")
        active = conn.execute(
            "SELECT count(*) FROM admin_jobs WHERE status IN ('queued', 'running')"
        ).fetchone()[0]
        if active >= config.admin.max_queue:
            raise AdminJobError(
                429, "Die Warteschlange ist voll; bitte später erneut versuchen.", 30
            )
        if (
            job == claude_review.JOB
        ):  # eigene Prüfungen: aktiviert, installiert, aktiver Lauf, Limits
            claude_review.check_allowed(conn, config, now)
        wait = cooldown_wait(conn, config, job, now)
        if wait:
            raise AdminJobError(
                429, f"Abkühlzeit: bitte in {max(1, round(wait / 60))} Min. erneut versuchen.", wait
            )
        try:
            job_id = conn.execute(
                "INSERT INTO admin_jobs (job, requested_by_user_id, requested_at, status) "
                "VALUES (?, ?, ?, 'queued')",
                (job, user_id, _iso(now)),
            ).lastrowid
        except sqlite3.IntegrityError as exc:  # Teil-Index: parallel eingereihter Auftrag
            raise AdminJobError(409, "Dieser Auftrag wartet oder läuft bereits.") from exc
        audit(conn, actor, "job_requested", f"{job} (#{job_id})")
    created = get_job(conn, job_id) if job_id is not None else None
    if created is None:
        raise AdminJobError(500, "Auftrag konnte nicht gelesen werden.")
    return created


def touch_trigger(config: Config) -> bool:
    """Trigger-Datei berühren (startet die `.path`-Unit). Fehler sind nicht fatal: der Timer holt nach."""
    try:
        path = config.data_dir / TRIGGER_NAME
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(_iso(_now()) + "\n", encoding="utf-8")
        return True
    except OSError as exc:
        log.warning("Trigger-Datei nicht schreibbar: %s", type(exc).__name__)
        return False


# ---------------------------------------------------------------------------- Runner
class _Tail(logging.Handler):
    """Sammelt die Log-Zeilen eines Auftrags (nur die letzten Bytes werden gespeichert)."""

    def __init__(self) -> None:
        super().__init__(level=logging.INFO)
        self.lines: list[str] = []
        self.setFormatter(logging.Formatter("%(levelname)s %(name)s: %(message)s"))

    def emit(self, record: logging.LogRecord) -> None:
        self.lines.append(self.format(record))
        if len(self.lines) > 400:
            del self.lines[:100]


def _tail(lines: list[str], limit: int) -> str:
    text = "\n".join(lines)
    return text[-limit:]


def _claim(conn: sqlite3.Connection) -> sqlite3.Row | None:
    with transaction(conn):
        row = conn.execute(
            "SELECT id, job FROM admin_jobs WHERE status = 'queued' ORDER BY id LIMIT 1"
        ).fetchone()
        if row is None:
            return None
        conn.execute(
            "UPDATE admin_jobs SET status = 'running', started_at = ? WHERE id = ?",
            (_iso(_now()), row["id"]),
        )
    return row


def _finish(
    conn: sqlite3.Connection, job_id: int, status: str, summary: str, tail: str | None
) -> None:
    conn.execute(
        "UPDATE admin_jobs SET status = ?, finished_at = ?, summary = ?, log_tail = ? WHERE id = ?",
        (status, _iso(_now()), summary[:MAX_SUMMARY], tail, job_id),
    )


def run_queue(config: Config, jobs: dict[str, JobFunc] | None = None) -> int:
    """Wartende Aufträge der Reihe nach ausführen; gibt die Anzahl abgearbeiteter Aufträge zurück.

    Läuft unter der Jobsperre (flock im Dienst), also nie gleichzeitig mit Timer-Jobs oder einem zweiten
    Runner. Zeilen, die noch „running“ zeigen, stammen daher von einem abgebrochenen Runner.
    """
    jobs = JOBS if jobs is None else jobs
    admin_conn = connect(config.storage.database)
    migrate(admin_conn)
    done = 0
    try:
        crashed = admin_conn.execute(
            "UPDATE admin_jobs SET status = 'error', finished_at = ?, "
            "summary = 'Runner wurde unterbrochen' WHERE status = 'running'",
            (_iso(_now()),),
        ).rowcount
        if crashed:
            log.warning("%d unterbrochene Aufträge als Fehler markiert", crashed)
        while (row := _claim(admin_conn)) is not None:
            job_id, name = row["id"], row["job"]
            if name not in jobs or name not in config.admin.jobs:
                _finish(admin_conn, job_id, "rejected", "Nicht (mehr) in der Allowlist", None)
                audit(admin_conn, "runner", "job_rejected", f"{name} (#{job_id})")
                done += 1
                continue
            handler = _Tail()
            root = logging.getLogger()
            root.addHandler(handler)
            previous_level = root.level
            if previous_level == logging.NOTSET or previous_level > logging.INFO:
                root.setLevel(logging.INFO)  # der Logauszug soll Fortschritt zeigen
            status, summary = "ok", ""
            try:
                work = connect(config.storage.database)
                try:
                    run = jobs[name](work, config)
                finally:
                    work.close()
                if run.errors:
                    status = "error"
                    summary = "; ".join(run.errors)
                else:
                    summary = f"Fertig ({run.items} Einträge)"
            except Exception as exc:  # ein Auftrag darf den Runner nie beenden
                log.exception("Auftrag %s (#%d) fehlgeschlagen", name, job_id)
                status, summary = "error", f"{type(exc).__name__}: {exc}"
            finally:
                root.removeHandler(handler)
                root.setLevel(previous_level)
            _finish(
                admin_conn,
                job_id,
                status,
                summary,
                _tail(handler.lines, config.admin.log_tail_bytes),
            )
            audit(admin_conn, "runner", f"job_{status}", f"{name} (#{job_id})")
            done += 1
    finally:
        admin_conn.close()
    return done
