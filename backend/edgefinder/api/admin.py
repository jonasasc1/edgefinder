# ruff: noqa: E501  (lange deutsche Texte)
"""Admin-Endpunkte unter /api/admin (nur für Konten mit `users.is_admin = 1`).

Autorisierung bei JEDEM Aufruf anhand der Identität (Cloudflare Access) und der DB-Zeile: nicht angemeldet
→ 401, angemeldet ohne Admin-Rolle (oder ohne Konto) → 403 mit immer gleicher Meldung. Die Rolle lässt
sich über die API nicht setzen (nur CLI). Der Webprozess startet nichts: `POST /jobs` schreibt eine Zeile
in `admin_jobs` und berührt die Trigger-Datei, ein getrennter Dienst führt den Auftrag aus. Berichte
kommen aus festen Dateien im Datenverzeichnis (keine Pfadparameter). Alle Antworten `no-store` (app.py).
"""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, Query, Request, Response
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from edgefinder import admin_jobs, claude_review, maintenance
from edgefinder.api import guard
from edgefinder.api.auth import AuthError, IdentityResolver
from edgefinder.backtest import live
from edgefinder.config import Config
from edgefinder.db import connect

MAX_BODY_BYTES = 256
MAX_REVIEW_BYTES = 200_000
MAX_DRIFT_BYTES = 1_000_000
MAX_USERS = 500
REPORT_FILENAME = "edgefinder-pruefbericht.md"
NO_ACCESS = "Kein Zugriff."


class JobIn(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    job: str = Field(min_length=1, max_length=32)


class EmptyIn(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


def _read_text(path: Path, limit: int) -> tuple[str, str] | None:
    """(Inhalt, Änderungszeit ISO) einer festen Datei; None, wenn sie fehlt oder zu groß ist."""
    try:
        stat = path.stat()
        if stat.st_size > limit:
            return None
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return None
    return text, datetime.fromtimestamp(stat.st_mtime, UTC).isoformat(timespec="seconds")


def create_admin_router(config: Config, resolver: IdentityResolver) -> APIRouter:
    router = APIRouter(prefix="/api/admin")
    extra_hosts = {host.strip().lower() for host in config.auth.public_hosts}

    @contextmanager
    def db() -> Iterator[sqlite3.Connection]:
        conn = connect(config.storage.database)
        try:
            yield conn
        finally:
            conn.close()

    def require_admin(request: Request) -> tuple[int, str]:
        """(user_id, E-Mail) des Admins; 401 ohne Identität, 403 ohne Rolle (frische DB-Abfrage)."""
        try:
            email = resolver.email_for(request.headers)
        except AuthError as exc:
            raise HTTPException(status_code=exc.status, detail=exc.detail) from exc
        with db() as conn:
            row = conn.execute(
                "SELECT id, is_admin FROM users WHERE email = ?", (email,)
            ).fetchone()
        if row is None or not row["is_admin"]:
            raise HTTPException(status_code=403, detail=NO_ACCESS)
        return row["id"], email

    # ------------------------------------------------------------------ Übersicht
    def overview_data() -> dict[str, Any]:
        now = datetime.now(UTC)
        with db() as conn:
            success = {
                r["source"]: r["last"]
                for r in conn.execute(
                    "SELECT source, MAX(finished_at) AS last FROM fetch_runs"
                    " WHERE status = 'success' GROUP BY source"
                )
            }
            last_run = {
                r["source"]: r
                for r in conn.execute(
                    "SELECT source, status, started_at, error FROM fetch_runs WHERE id IN"
                    " (SELECT MAX(id) FROM fetch_runs GROUP BY source)"
                )
            }
            scored = conn.execute("SELECT MAX(date), MAX(computed_at) FROM scores").fetchone()
            calibration = maintenance.load_current_calibration(config)
            try:
                track = live.build_trackrecord(conn, config, calibration)
            except Exception:  # Übersicht bleibt nutzbar
                track = None
            watched = [(n, s.stale_after_hours) for n, s in config.sources.items() if s.enabled]
            watched += [
                (maintenance.SOURCE_MAINTAIN, config.maintenance.maintain_stale_after_hours),
                (maintenance.SOURCE_EVALUATE, config.maintenance.evaluate_stale_after_hours),
            ]
            runs = []
            for name, hours in watched:
                last = success.get(name)
                run = last_run.get(name)
                stale = not last or now - datetime.fromisoformat(last) > timedelta(hours=hours)
                runs.append(
                    {
                        "source": name,
                        "last_success": last,
                        "last_run_status": run["status"] if run else None,
                        "last_run_at": run["started_at"] if run else None,
                        "last_error": (run["error"] or "")[:300]
                        if run and run["status"] != "success"
                        else None,
                        "stale_after_hours": hours,
                        "stale": stale,
                    }
                )
            active = {
                r["job"]: r["id"]
                for r in conn.execute(
                    "SELECT id, job FROM admin_jobs WHERE status IN ('queued', 'running')"
                )
            }
            jobs = [
                {
                    "job": name,
                    "cooldown_minutes": config.admin.cooldown_for(name),
                    "wait_seconds": admin_jobs.cooldown_wait(conn, config, name, now),
                    "active_id": active.get(name),
                }
                for name in config.admin.jobs
                if name != claude_review.JOB  # eigener Abschnitt „Claude-Analyse“
            ]
            recent = admin_jobs.recent_jobs(conn)
            claude_info = claude_review.overview(conn, config, now)
            for entry in recent:
                entry.pop("log_tail", None)  # Logauszug nur auf Abruf (GET /jobs/{id})
        return {
            "now": now.isoformat(timespec="seconds"),
            "model_version": config.scoring.model_version,
            "last_score_date": scored[0],
            "last_scored_at": scored[1],
            "calibration": {
                "available": bool(calibration),
                "generated_at": calibration.get("generated_at") if calibration else None,
                "first_date": calibration.get("first_date") if calibration else None,
                "data_through": calibration.get("data_through") if calibration else None,
            },
            "live": {
                "live_since": track["live_since"] if track else None,
                "evaluated": track["evaluated"] if track else None,
                "open": track["open"] if track else None,
                "progress": track["progress"] if track else None,
            },
            "runs": runs,
            "jobs": jobs,
            "recent_jobs": [e for e in recent if e["job"] != claude_review.JOB],
            "claude": claude_info,
        }

    @router.get("/overview")
    def overview(request: Request) -> dict[str, Any]:
        require_admin(request)
        return overview_data()

    # ------------------------------------------------------------------ Aufträge
    @router.post("/jobs", status_code=202)
    async def create_job(request: Request) -> dict[str, Any]:
        guard.check_origin(request, extra_hosts)
        user_id, email = require_admin(request)
        data = await guard.read_json(request, MAX_BODY_BYTES)
        try:
            body = JobIn.model_validate(data)
        except ValidationError as exc:
            raise HTTPException(status_code=422, detail="Ungültiger Auftrag.") from exc

        def enqueue() -> dict[str, Any]:
            with db() as conn:
                return admin_jobs.enqueue(conn, config, body.job, user_id, email)

        try:
            created = await run_in_threadpool(enqueue)
        except admin_jobs.AdminJobError as exc:
            headers = {"Retry-After": str(exc.retry_after)} if exc.retry_after else None
            raise HTTPException(status_code=exc.status, detail=exc.detail, headers=headers) from exc
        admin_jobs.touch_trigger(config)
        return created

    @router.get("/jobs/{job_id}")
    def job(job_id: int, request: Request) -> dict[str, Any]:
        require_admin(request)
        with db() as conn:
            found = admin_jobs.get_job(conn, job_id)
        if found is None:
            raise HTTPException(status_code=404, detail="Auftrag nicht gefunden.")
        return found

    # ------------------------------------------------------------------ Claude-Prüfagent
    # Feste Pfade unter claude.base_dir/runs/<Zahl>; der Client liefert nur die Zahl (validiert).
    def parse_run_id(run_id: str) -> int:
        value = claude_review.valid_run_id(run_id)
        if value is None:
            raise HTTPException(status_code=404, detail="Lauf nicht gefunden.")
        return value

    @router.post("/claude", status_code=202)
    async def start_claude(request: Request) -> dict[str, Any]:
        guard.check_origin(request, extra_hosts)
        user_id, email = require_admin(request)
        data = await guard.read_json(request, MAX_BODY_BYTES)
        try:
            EmptyIn.model_validate(data)
        except ValidationError as exc:
            raise HTTPException(status_code=422, detail="Ungültige Anfrage.") from exc

        def enqueue() -> dict[str, Any]:
            with db() as conn:
                return admin_jobs.enqueue(conn, config, claude_review.JOB, user_id, email)

        try:
            created = await run_in_threadpool(enqueue)
        except admin_jobs.AdminJobError as exc:
            headers = {"Retry-After": str(exc.retry_after)} if exc.retry_after else None
            raise HTTPException(status_code=exc.status, detail=exc.detail, headers=headers) from exc
        admin_jobs.touch_trigger(config)
        created.pop("log_tail", None)
        return created

    @router.get("/claude/runs")
    def claude_runs(request: Request) -> dict[str, Any]:
        require_admin(request)
        with db() as conn:
            return {
                "overview": claude_review.overview(conn, config),
                "runs": claude_review.list_runs(conn, config),
            }

    @router.get("/claude/runs/{run_id}")
    def claude_run(run_id: str, request: Request) -> dict[str, Any]:
        require_admin(request)
        number = parse_run_id(run_id)
        with db() as conn:
            found = claude_review.get_run(conn, config, number)
        if found is None:
            raise HTTPException(status_code=404, detail="Lauf nicht gefunden.")
        return found

    @router.get("/claude/runs/{run_id}/audit")
    def claude_audit(
        run_id: str,
        request: Request,
        offset: int = Query(default=0, ge=0, le=1_000_000),
        limit: int = Query(default=100, ge=1, le=claude_review.MAX_AUDIT_PAGE),
    ) -> dict[str, Any]:
        require_admin(request)
        number = parse_run_id(run_id)
        page = claude_review.read_audit(config, number, offset, limit)
        if page is None:
            raise HTTPException(status_code=404, detail="Kein Protokoll vorhanden.")
        return page

    # ------------------------------------------------------------------ Bericht
    @router.get("/report")
    def report(request: Request) -> dict[str, Any]:
        require_admin(request)
        review = _read_text(config.data_dir / maintenance.REVIEW_NAME, MAX_REVIEW_BYTES)
        drift_raw = _read_text(config.data_dir / maintenance.DRIFT_NAME, MAX_DRIFT_BYTES)
        drift: Any = None
        if drift_raw:
            try:
                drift = json.loads(drift_raw[0])
            except ValueError:
                drift = None
        return {
            "review_md": review[0] if review else None,
            "review_updated_at": review[1] if review else None,
            "drift": drift,
            "drift_updated_at": drift_raw[1] if drift_raw else None,
            "filename": REPORT_FILENAME,
        }

    @router.get("/report.md")
    def report_md(request: Request) -> Response:
        require_admin(request)
        review = _read_text(config.data_dir / maintenance.REVIEW_NAME, MAX_REVIEW_BYTES)
        if review is None:
            raise HTTPException(status_code=404, detail="Noch kein Prüfbericht vorhanden.")
        return Response(
            review[0],
            media_type="text/markdown; charset=utf-8",
            headers={"Content-Disposition": f'attachment; filename="{REPORT_FILENAME}"'},
        )

    # ------------------------------------------------------------------ Konten (nur lesen)
    @router.get("/users")
    def users(request: Request) -> dict[str, Any]:
        require_admin(request)
        with db() as conn:
            rows = conn.execute(
                "SELECT u.email, u.created_at, u.last_seen_at, u.is_admin, "
                "(SELECT count(*) FROM user_favorites f WHERE f.user_id = u.id) AS favorites "
                "FROM users u ORDER BY u.created_at, u.id LIMIT ?",
                (MAX_USERS,),
            ).fetchall()
        return {
            "users": [
                {
                    "email": r["email"],
                    "created_at": r["created_at"],
                    "last_seen_at": r["last_seen_at"],
                    "favorites": r["favorites"],
                    "is_admin": bool(r["is_admin"]),
                }
                for r in rows
            ]
        }

    return router
