# ruff: noqa: E501, S603, S607  (lange deutsche Texte; Skripte mit festen Argumenten)
"""Claude-Prüfagent (Etappe q): Job, Schutzmechanismen, Paketbau ohne Secrets, Endpunkte, Hooks, Skripte."""

from __future__ import annotations

import importlib.util
import json
import os
import shutil
import subprocess
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest
from fastapi.testclient import TestClient
from test_accounts import _as, _client

from edgefinder import admin_jobs, claude_review, cli, maintenance
from edgefinder import claude_scrub as scrub_mod
from edgefinder.config import Config
from edgefinder.db import connect

REPO = Path(__file__).resolve().parents[2]
CR = REPO / "deploy" / "claude-review"
ADMIN = "jonas@example.com"
OTHER = "anna@example.com"
JSON_H = {"Content-Type": "application/json"}
SECRET_KEY = "sk-ant-api03-GEHEIMER-SCHLUESSEL-1234567890"
SECRET_BEARER = "Bearer abcdef1234567890SECRETTOKEN"
SECRET_ENV = "FRED_API_KEY=0123456789abcdef0123456789abcdef"
EMAIL = "privat.person@example.org"


def _load(path: Path, name: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def source(tmp_path: Path) -> Path:
    """Kleiner Quelltext-Baum mit Dingen, die NICHT ins Paket gehören."""
    src = tmp_path / "src"
    (src / "backend" / "edgefinder").mkdir(parents=True)
    (src / "backend" / "edgefinder" / "app.py").write_text(
        f'KEY = "{SECRET_KEY}"\n', encoding="utf-8"
    )
    (src / "backend" / "edgefinder" / "__pycache__").mkdir()
    (src / "backend" / "edgefinder" / "__pycache__" / "x.pyc").write_bytes(b"\0")
    (src / "backend" / "edgefinder" / "x.pyc").write_bytes(b"\0")
    (src / "frontend" / "node_modules" / "p").mkdir(parents=True)
    (src / "frontend" / "node_modules" / "p" / "i.js").write_text("evil", encoding="utf-8")
    (src / "frontend" / "dist").mkdir()
    (src / "frontend" / "dist" / "a.js").write_text("dist", encoding="utf-8")
    (src / "frontend" / "src").mkdir()
    (src / "frontend" / "src" / "a.ts").write_text("export const a = 1;\n", encoding="utf-8")
    (src / "frontend" / "package-lock.json").write_text("{}", encoding="utf-8")
    (src / "data").mkdir()
    (src / "data" / "edgefinder.db").write_bytes(b"SQLite format 3")
    (src / "backend" / "data").mkdir()
    (src / "backend" / "data" / "x.json").write_text("{}", encoding="utf-8")
    (src / ".env").write_text(f"{SECRET_ENV}\n", encoding="utf-8")
    (src / "backend" / ".env.local").write_text(f"{SECRET_ENV}\n", encoding="utf-8")
    (src / "deploy").mkdir()
    (src / "deploy" / "deploy_key").write_text(
        "-----BEGIN OPENSSH PRIVATE KEY-----\nAAAA\n-----END OPENSSH PRIVATE KEY-----\n",
        encoding="utf-8",
    )
    (src / "deploy" / "x.pem").write_text("pem", encoding="utf-8")
    (src / "deploy" / "run.sh").write_text("#!/bin/sh\necho hi\n", encoding="utf-8")
    (src / ".venv" / "bin").mkdir(parents=True)
    (src / ".venv" / "bin" / "python").write_text("py", encoding="utf-8")
    (src / "config.yaml").write_text(
        f"admin:\n  note: 'token: {SECRET_BEARER}'\n", encoding="utf-8"
    )
    (src / "CLAUDE.md").write_text("# Regeln\n", encoding="utf-8")
    (src / "secret_link.py").symlink_to(src / ".env")
    (src / "backend" / "link.py").symlink_to(src / ".env")
    return src


def _claude_config(
    config: Config, config_data: dict[str, Any], tmp_path: Path, src: Path, **over: Any
) -> Config:
    base = tmp_path / "claude"
    (base / "runs").mkdir(parents=True)
    (base / "inbox").mkdir()
    data = {**config_data, "storage": config_data["storage"]}
    data["storage"] = {
        "database": str(config.storage.database),
        "raw_dir": str(config.storage.raw_dir),
    }
    data["claude"] = {"enabled": True, "base_dir": str(base), "source_dir": str(src), **over}
    return Config.model_validate(data)


@pytest.fixture
def cconfig(config: Config, config_data: dict[str, Any], tmp_path: Path, source: Path) -> Config:
    return _claude_config(config, config_data, tmp_path, source)


def _setup(config: Config) -> TestClient:
    client = _client(config)
    client.get("/api/me", headers=_as(OTHER))
    client.get("/api/me", headers=_as(ADMIN))
    conn = connect(config.storage.database)
    admin_jobs.set_admin(conn, ADMIN, True)
    conn.close()
    return client


def _post(client: TestClient, who: str = ADMIN) -> Any:
    return client.post("/api/admin/claude", json={}, headers=_as(who))


def _fake_run(
    config: Config, run_id: int, state: str | None, created: datetime | None = None, **status: Any
) -> Path:
    """Lauf-Verzeichnis nachbauen (wie der Dienst es hinterlässt)."""
    base = claude_review.run_dir(config, run_id)
    (base / "input").mkdir(parents=True)
    (base / "output").mkdir()
    stamp = (created or datetime.now(UTC)).isoformat(timespec="seconds")
    (base / "request.json").write_text(
        json.dumps({"id": run_id, "created_at": stamp}), encoding="utf-8"
    )
    if state:
        (base / "status.json").write_text(
            json.dumps({"state": state, "started_at": stamp, **status}), encoding="utf-8"
        )
    return base


def _insert_job(
    config: Config, status: str = "ok", at: datetime | None = None, job: str = "claude_review"
) -> int:
    conn = connect(config.storage.database)
    uid = conn.execute("SELECT id FROM users WHERE email = ?", (ADMIN,)).fetchone()[0]
    stamp = (at or datetime.now(UTC)).isoformat(timespec="seconds")
    rid = conn.execute(
        "INSERT INTO admin_jobs (job, requested_by_user_id, requested_at, started_at, finished_at, status) VALUES (?, ?, ?, ?, ?, ?)",
        (job, uid, stamp, stamp, stamp if status in ("ok", "error") else None, status),
    ).lastrowid
    conn.commit()
    conn.close()
    assert rid
    return rid


# ------------------------------------------------------------------ Allowlist und Konfiguration
def test_allowlist_job_and_config() -> None:
    assert "claude_review" in admin_jobs.JOBS
    from edgefinder.config import load_config

    config = load_config(REPO / "config.yaml")
    assert "claude_review" in config.admin.jobs
    assert config.claude.enabled is False  # Standard bis zur Installation
    assert config.claude.cooldown_minutes == 30
    assert config.claude.max_runs_per_day == 3


def test_claude_config_is_validated(config_data: dict[str, Any]) -> None:
    for bad in (
        {"cooldown_minutes": -1},
        {"max_runs_per_day": 0},
        {"max_turns": 0},
        {"runtime_max_seconds": 5},
        {"unbekannt": 1},
    ):
        with pytest.raises(ValueError):
            Config.model_validate({**config_data, "claude": bad})


# ------------------------------------------------------------------ Lauf-ID
@pytest.mark.parametrize(
    "value",
    [
        "0",
        "-1",
        "01",
        "1.5",
        "1e3",
        " 1",
        "1 ",
        "../1",
        "1/..",
        "١٢",
        "",
        "abc",
        "1000000000",
        "+5",
        "1\n",
    ],
)
def test_run_id_validation_rejects(value: str) -> None:
    assert claude_review.valid_run_id(value) is None


def test_run_id_validation_accepts() -> None:
    assert claude_review.valid_run_id("7") == 7
    assert claude_review.valid_run_id(123456789) == 123456789
    assert claude_review.valid_run_id(True) is None or isinstance(
        claude_review.valid_run_id(True), int
    )


def test_run_dir_needs_int(cconfig: Config) -> None:
    for bad in ("1", "../x", -1, 0, True):
        with pytest.raises(ValueError):
            claude_review.run_dir(cconfig, bad)  # type: ignore[arg-type]
    assert claude_review.run_dir(cconfig, 3) == cconfig.claude.base_dir / "runs" / "3"


# ------------------------------------------------------------------ Paketbau
def _all_text(root: Path) -> str:
    return "\n".join(
        p.read_text(encoding="utf-8", errors="replace") for p in root.rglob("*") if p.is_file()
    )


def test_package_contains_no_secrets_or_excluded_files(cconfig: Config) -> None:
    conn = connect(cconfig.storage.database)
    from edgefinder.db import migrate

    migrate(conn)
    conn.execute(
        "INSERT INTO fetch_runs (source, started_at, finished_at, status, error) VALUES ('fred', ?, ?, 'error', ?)",
        (
            datetime.now(UTC).isoformat(),
            datetime.now(UTC).isoformat(),
            f"HTTP 401 https://x/y?api_key=ABCDEFSECRET&z=1 {SECRET_BEARER} von {EMAIL}",
        ),
    )
    conn.commit()
    (cconfig.data_dir / maintenance.REVIEW_NAME).write_text(
        f"# Bericht\nkontakt {EMAIL} {SECRET_KEY}\n", encoding="utf-8"
    )
    request = claude_review.build_package(conn, cconfig, 5)
    conn.close()

    pkg = claude_review.run_dir(cconfig, 5) / "input"
    names = {p.relative_to(pkg).as_posix() for p in pkg.rglob("*") if p.is_file()}
    assert {
        "MANIFEST.json",
        "fetch-runs.json",
        "data-status.json",
        "scores-stats.json",
        "calibration-summary.json",
        "review.md",
    } <= names
    assert "snapshot/backend/edgefinder/app.py" in names
    assert "snapshot/frontend/src/a.ts" in names
    assert "snapshot/CLAUDE.md.txt" in names  # nicht als Anweisungsdatei ladbar
    assert "snapshot/CLAUDE.md" not in names
    # Ausschlüsse
    for forbidden in (
        "node_modules",
        "dist",
        ".venv",
        "__pycache__",
        "data",
        ".env",
        "package-lock.json",
        ".pem",
        "deploy_key",
        ".pyc",
        ".db",
        "link.py",
        "secret_link",
    ):
        assert not [
            n
            for n in names
            if forbidden in n.split("/") or (forbidden != "data" and forbidden in n)
        ], forbidden
    # Secrets/E-Mail dürfen nirgends im Paket stehen (Quelltext, Config, Fehlertexte, Bericht)
    text = _all_text(pkg)
    for secret in (
        SECRET_KEY,
        "ABCDEFSECRET",
        "abcdef1234567890SECRETTOKEN",
        EMAIL,
        "0123456789abcdef0123456789abcdef",
        "OPENSSH PRIVATE KEY",
    ):
        assert secret not in text, secret
    assert "[GESCHWAERZT]" in text
    # Anforderung: feste Felder, Inbox atomar geschrieben
    inbox = json.loads((claude_review.inbox_dir(cconfig) / "5.json").read_text(encoding="utf-8"))
    assert inbox == request
    assert set(request) == {
        "id",
        "created_at",
        "max_turns",
        "runtime_max_seconds",
        "journal_hours",
        "package_bytes",
    }
    assert not list(claude_review.inbox_dir(cconfig).glob(".*"))


def test_package_size_limit_cleans_up(
    config: Config, config_data: dict[str, Any], tmp_path: Path, source: Path
) -> None:
    big = _claude_config(config, config_data, tmp_path, source, max_package_mb=1)
    (source / "backend" / "big.txt").write_text("x" * 590_000, encoding="utf-8")
    (source / "backend" / "big2.txt").write_text("y" * 590_000, encoding="utf-8")
    conn = connect(big.storage.database)
    from edgefinder.db import migrate

    migrate(conn)
    with pytest.raises(claude_review.PackageError, match="MB"):
        claude_review.build_package(conn, big, 9)
    conn.close()
    assert not claude_review.run_dir(big, 9).exists()
    assert not list(claude_review.inbox_dir(big).iterdir())


def test_empty_source_is_an_error(
    config: Config, config_data: dict[str, Any], tmp_path: Path
) -> None:
    empty = tmp_path / "leer"
    empty.mkdir()
    cfg = _claude_config(config, config_data, tmp_path, empty)
    conn = connect(cfg.storage.database)
    from edgefinder.db import migrate

    migrate(conn)
    with pytest.raises(claude_review.PackageError):
        claude_review.build_package(conn, cfg, 2)
    assert not claude_review.run_dir(cfg, 2).exists()


def test_git_head_without_subprocess(tmp_path: Path) -> None:
    (tmp_path / ".git" / "refs" / "heads").mkdir(parents=True)
    (tmp_path / ".git" / "HEAD").write_text("ref: refs/heads/main\n", encoding="utf-8")
    sha = "a" * 40
    (tmp_path / ".git" / "refs" / "heads" / "main").write_text(sha + "\n", encoding="utf-8")
    assert claude_review.git_head(tmp_path) == sha
    assert claude_review.git_head(tmp_path / "nichts") is None


def test_module_never_starts_programs() -> None:
    text = (REPO / "backend" / "edgefinder" / "claude_review.py").read_text(encoding="utf-8")
    assert "subprocess" not in text and "os.system" not in text and "Popen" not in text


# ------------------------------------------------------------------ Job über API und Runner
def test_full_flow_post_then_runner_builds_package(cconfig: Config) -> None:
    client = _setup(cconfig)
    response = _post(client)
    assert response.status_code == 202, response.text
    job_id = response.json()["id"]
    assert response.json()["job"] == "claude_review"
    assert admin_jobs.run_queue(cconfig) == 1
    job = admin_jobs.get_job(connect(cconfig.storage.database), job_id)
    assert job and job["status"] == "ok", job
    assert (claude_review.inbox_dir(cconfig) / f"{job_id}.json").is_file()
    assert (claude_review.run_dir(cconfig, job_id) / "input" / "MANIFEST.json").is_file()
    # Lauf ist „wartet auf Dienst“, ein zweiter Start wird abgelehnt (aktiver Lauf)
    listing = client.get("/api/admin/claude/runs", headers=_as(ADMIN)).json()
    assert listing["runs"][0]["state"] == "queued"
    assert listing["overview"]["active_id"] == job_id
    again = _post(client)
    assert again.status_code == 409


def test_not_enabled_or_not_installed_is_409(
    config: Config, config_data: dict[str, Any], tmp_path: Path, source: Path
) -> None:
    off = _claude_config(config, config_data, tmp_path, source, enabled=False)
    client = _setup(off)
    response = _post(client)
    assert response.status_code == 409 and "nicht aktiviert" in response.json()["detail"]
    overview = client.get("/api/admin/overview", headers=_as(ADMIN)).json()
    assert overview["claude"]["enabled"] is False
    assert all(j["job"] != "claude_review" for j in overview["jobs"])
    shutil.rmtree(off.claude.base_dir / "runs")
    on = Config.model_validate(
        {
            **off.model_dump(mode="json"),
            "claude": {**off.claude.model_dump(mode="json"), "enabled": True},
        }
    )
    client2 = _setup(on)
    response = _post(client2)
    assert response.status_code == 409 and "nicht installiert" in response.json()["detail"]


def test_run_job_requires_enabled(config: Config) -> None:
    conn = connect(config.storage.database)
    from edgefinder.db import migrate

    migrate(conn)
    run = claude_review.run_job(conn, config)
    assert run.errors == ["claude.enabled ist false"]


def test_cooldown_and_daily_limit(cconfig: Config) -> None:
    client = _setup(cconfig)
    now = datetime.now(UTC)
    first = _insert_job(cconfig, "ok", now - timedelta(minutes=5))
    _fake_run(cconfig, first, "ok", now - timedelta(minutes=5), duration_seconds=60)
    cooled = _post(client)
    assert cooled.status_code == 429 and "Abkühlzeit" in cooled.json()["detail"]
    assert int(cooled.headers["retry-after"]) > 0
    # Abkühlzeit vorbei, aber Tageslimit (3 in 24 h) erreicht
    conn = connect(cconfig.storage.database)
    conn.execute(
        "UPDATE admin_jobs SET requested_at = ? WHERE id = ?",
        ((now - timedelta(hours=2)).isoformat(timespec="seconds"), first),
    )
    conn.commit()
    conn.close()
    for hours in (3, 4):
        rid = _insert_job(cconfig, "ok", now - timedelta(hours=hours))
        _fake_run(cconfig, rid, "ok", now - timedelta(hours=hours))
    limited = _post(client)
    assert limited.status_code == 429 and "Tageslimit" in limited.json()["detail"]
    # ältere als 24 h zählen nicht mehr
    conn = connect(cconfig.storage.database)
    conn.execute(
        "UPDATE admin_jobs SET requested_at = ?",
        ((now - timedelta(hours=30)).isoformat(timespec="seconds"),),
    )
    conn.commit()
    conn.close()
    assert _post(client).status_code == 202


def test_failed_package_jobs_do_not_count_against_daily_limit(cconfig: Config) -> None:
    client = _setup(cconfig)
    for _ in range(4):
        _insert_job(cconfig, "error", datetime.now(UTC) - timedelta(hours=1))
    assert _post(client).status_code == 202


def test_run_states(cconfig: Config) -> None:
    now = datetime.now(UTC)
    _fake_run(cconfig, 1, None, now - timedelta(minutes=1))
    assert claude_review.run_state(cconfig, 1, now)["state"] == "queued"
    _fake_run(cconfig, 2, None, now - timedelta(minutes=30))
    assert claude_review.run_state(cconfig, 2, now)["state"] == "stale"
    _fake_run(cconfig, 3, "running", now - timedelta(minutes=2))
    assert claude_review.run_state(cconfig, 3, now)["state"] == "running"
    _fake_run(cconfig, 4, "running", now - timedelta(hours=2))
    assert claude_review.run_state(cconfig, 4, now)["state"] == "stale"
    _fake_run(cconfig, 5, "ok", now, turns=7, cost_usd=0.5, duration_seconds=90, exit_code=0)
    state = claude_review.run_state(cconfig, 5, now)
    assert state["state"] == "ok" and state["turns"] == 7 and state["duration_seconds"] == 90
    _fake_run(cconfig, 6, "kaputt", now)
    assert claude_review.run_state(cconfig, 6, now)["state"] == "error"
    assert claude_review.run_state(cconfig, 99, now)["state"] == "missing"


# ------------------------------------------------------------------ Endpunkte
GET_PATHS = ["/api/admin/claude/runs", "/api/admin/claude/runs/1", "/api/admin/claude/runs/1/audit"]


def test_endpoints_are_admin_only_and_no_store(cconfig: Config) -> None:
    client = _setup(cconfig)
    for path in GET_PATHS:
        assert client.get(path).status_code == 401, path
        denied = client.get(path, headers=_as(OTHER))
        assert denied.status_code == 403 and denied.json() == {"detail": "Kein Zugriff."}, path
        assert denied.headers["cache-control"] == "no-store"
    assert client.post("/api/admin/claude", json={}).status_code == 401
    assert _post(client, OTHER).status_code == 403
    ok = client.get("/api/admin/claude/runs", headers=_as(ADMIN))
    assert ok.status_code == 200 and ok.headers["cache-control"] == "no-store"


def test_post_requires_json_same_origin_and_empty_body(cconfig: Config) -> None:
    client = _setup(cconfig)
    assert (
        client.post(
            "/api/admin/claude", content="{}", headers=_as(ADMIN, **{"Content-Type": "text/plain"})
        ).status_code
        == 415
    )
    assert (
        client.post(
            "/api/admin/claude", json={}, headers=_as(ADMIN, **{"Sec-Fetch-Site": "cross-site"})
        ).status_code
        == 403
    )
    assert (
        client.post(
            "/api/admin/claude", json={}, headers=_as(ADMIN, Origin="https://evil.example")
        ).status_code
        == 403
    )
    assert (
        client.post("/api/admin/claude", json={"job": "score"}, headers=_as(ADMIN)).status_code
        == 422
    )
    assert (
        client.post(
            "/api/admin/claude", content="x" * 1000, headers=_as(ADMIN, **JSON_H)
        ).status_code
        == 413
    )


@pytest.mark.parametrize(
    "segment",
    [
        "..",
        "..%2f..%2fetc%2fpasswd",
        "%2e%2e",
        "01",
        "-1",
        "abc",
        "1e3",
        "0",
        "1%00",
        "1%2f..",
        "٣",
        "1.0",
        "99999999999",
    ],
)
def test_run_id_path_traversal_is_404(cconfig: Config, segment: str) -> None:
    client = _setup(cconfig)
    for suffix in ("", "/audit"):
        response = client.get(f"/api/admin/claude/runs/{segment}{suffix}", headers=_as(ADMIN))
        assert response.status_code in (404, 405, 422), (segment, suffix, response.status_code)
        assert "root:" not in response.text


def test_run_detail_reads_only_fixed_files(cconfig: Config, tmp_path: Path) -> None:
    client = _setup(cconfig)
    jid = _insert_job(cconfig, "ok")
    base = _fake_run(cconfig, jid, "ok", turns=3)
    out = base / "output"
    (out / "analysis.md").write_text(f"# Analyse\n\nText {SECRET_KEY}\n", encoding="utf-8")
    (out / "proposal-2.diff").write_text("--- a\n+++ b\n", encoding="utf-8")
    (out / "proposal-1.diff").write_text("diff eins\n", encoding="utf-8")
    (out / "proposal-x.diff").write_text("falscher Name", encoding="utf-8")
    (out / "notes.md").write_text("nicht erlaubt", encoding="utf-8")
    (base / "audit.jsonl").write_text(
        json.dumps({"event": "PreToolUse", "tool": "Read"}) + "\n", encoding="utf-8"
    )
    detail = client.get(f"/api/admin/claude/runs/{jid}", headers=_as(ADMIN)).json()
    assert detail["state"] == "ok" and detail["has_audit"] is True
    assert "# Analyse" in detail["analysis_md"] and SECRET_KEY not in detail["analysis_md"]
    assert [p["name"] for p in detail["proposals"]] == ["proposal-1.diff", "proposal-2.diff"]
    # unbekannter Lauf (kein Auftrag) → 404, auch wenn ein Verzeichnis existiert
    _fake_run(cconfig, 77, "ok")
    assert client.get("/api/admin/claude/runs/77", headers=_as(ADMIN)).status_code == 404


def test_symlink_and_oversize_outputs_are_not_served(cconfig: Config, tmp_path: Path) -> None:
    client = _setup(cconfig)
    jid = _insert_job(cconfig, "ok")
    base = _fake_run(cconfig, jid, "ok")
    secret = tmp_path / "geheim.txt"
    secret.write_text("TOPSECRET-INHALT", encoding="utf-8")
    (base / "output" / "analysis.md").symlink_to(secret)
    (base / "output" / "proposal-1.diff").write_text(
        "x" * (claude_review.MAX_PROPOSAL_BYTES + 1), encoding="utf-8"
    )
    (base / "audit.jsonl").symlink_to(secret)
    detail = client.get(f"/api/admin/claude/runs/{jid}", headers=_as(ADMIN)).json()
    assert detail["analysis_md"] is None and detail["proposals"] == []
    assert "TOPSECRET" not in json.dumps(detail)
    assert client.get(f"/api/admin/claude/runs/{jid}/audit", headers=_as(ADMIN)).status_code == 404
    # Lauf-Verzeichnis selbst als Symlink
    other = tmp_path / "fremd"
    (other / "output").mkdir(parents=True)
    (other / "output" / "analysis.md").write_text("FREMD", encoding="utf-8")
    jid2 = _insert_job(cconfig, "ok")
    claude_review.run_dir(cconfig, jid2).symlink_to(other)
    assert "FREMD" not in json.dumps(
        client.get(f"/api/admin/claude/runs/{jid2}", headers=_as(ADMIN)).json()
    )


def test_audit_is_paginated_truncated_and_scrubbed(cconfig: Config) -> None:
    client = _setup(cconfig)
    jid = _insert_job(cconfig, "ok")
    base = _fake_run(cconfig, jid, "ok")
    lines = [
        json.dumps(
            {"event": "PostToolUse", "tool": "Bash", "result": f"zeile {i} {EMAIL} {SECRET_KEY}"}
        )
        for i in range(250)
    ]
    (base / "audit.jsonl").write_text(
        "\n".join(lines) + "\nkein json " + SECRET_KEY + "\n", encoding="utf-8"
    )
    first = client.get(f"/api/admin/claude/runs/{jid}/audit?limit=100", headers=_as(ADMIN)).json()
    assert first["total"] == 251 and len(first["entries"]) == 100 and first["offset"] == 0
    assert SECRET_KEY not in json.dumps(first) and EMAIL not in json.dumps(first)
    last = client.get(
        f"/api/admin/claude/runs/{jid}/audit?offset=250&limit=100", headers=_as(ADMIN)
    ).json()
    assert (
        len(last["entries"]) == 1
        and "raw" in last["entries"][0]
        and SECRET_KEY not in json.dumps(last)
    )
    for query in ("limit=0", "limit=5000", "offset=-1", "limit=abc", "offset=99999999"):
        assert (
            client.get(
                f"/api/admin/claude/runs/{jid}/audit?{query}", headers=_as(ADMIN)
            ).status_code
            == 422
        ), query


def test_cleanup_removes_old_runs_only(cconfig: Config) -> None:
    old = _fake_run(cconfig, 1, "ok")
    new = _fake_run(cconfig, 2, "ok")
    past = (datetime.now(UTC) - timedelta(days=cconfig.claude.retention_days + 1)).timestamp()
    os.utime(old / "request.json", (past, past))
    (cconfig.claude.base_dir / "runs" / "keine-zahl").mkdir()
    assert claude_review.cleanup_runs(cconfig, dry_run=True) == 1
    assert old.exists()
    assert claude_review.cleanup_runs(cconfig) == 1
    assert (
        not old.exists()
        and new.exists()
        and (cconfig.claude.base_dir / "runs" / "keine-zahl").exists()
    )


def test_cleanup_command_includes_runs(cconfig: Config, monkeypatch: pytest.MonkeyPatch) -> None:
    old = _fake_run(cconfig, 1, "ok")
    past = (datetime.now(UTC) - timedelta(days=400)).timestamp()
    os.utime(old / "request.json", (past, past))
    monkeypatch.setattr("edgefinder.cli.load_config", lambda: cconfig)
    assert cli.main(["cleanup"]) == 0
    assert not old.exists()


# ------------------------------------------------------------------ Scrubbing
def test_scrub_masks_secrets_and_emails() -> None:
    text = f"{SECRET_KEY} {SECRET_BEARER} {SECRET_ENV} https://u:pw@host/x?token=abc123 {EMAIL} jwt eyJhbGciOiJIUzI1.eyJzdWIiOiIxMjM0NTY3.SflKxwRJSMeKKF2QT4"
    out = scrub_mod.scrub(text)
    for secret in (
        "GEHEIMER",
        "abcdef1234567890SECRETTOKEN",
        "0123456789abcdef",
        "pw@",
        "abc123",
        "privat.person",
        "SflKxw",
    ):
        assert secret not in out, secret
    assert "p***@example.org" in out
    assert scrub_mod.scrub("normaler Text 2026-11-22 INFO ok") == "normaler Text 2026-11-22 INFO ok"
    assert "j***@example.com" in scrub_mod.mask_emails("jonas@example.com")
    assert "@example.com" in scrub_mod.scrub_secrets("a@example.com")  # Quelltext: Adressen bleiben


def test_hook_copy_of_scrub_is_identical() -> None:
    assert (CR / "hooks" / "scrub.py").read_bytes() == (
        REPO / "backend" / "edgefinder" / "claude_scrub.py"
    ).read_bytes()


# ------------------------------------------------------------------ Einstellungen, Hook, Skripte
@pytest.fixture(scope="module")
def settings() -> dict[str, Any]:
    return json.loads((CR / "settings.json").read_text(encoding="utf-8"))


def test_settings_json_forbids_everything_dangerous(settings: dict[str, Any]) -> None:
    perm = settings["permissions"]
    deny = set(perm["deny"])
    for tool in ("WebFetch", "WebSearch", "Task", "Skill", "mcp__*"):
        assert tool in deny, tool
    for cmd in (
        "curl",
        "wget",
        "ssh",
        "scp",
        "nc",
        "sudo",
        "systemctl",
        "apt",
        "apt-get",
        "pip",
        "npm",
        "git",
        "bash",
        "sh",
        "rm",
    ):
        assert f"Bash({cmd} *)" in deny and f"Bash({cmd})" in deny, cmd
    for path in (
        "//var/lib/claude-review/.claude/**",
        "//var/lib/edgefinder/**",
        "//opt/edgefinder/**",
        "//etc/**",
        "Read(~/**)",
    ):
        assert any(path in d for d in deny), path
    allow = perm["allow"]
    assert "Write(./output/**)" in allow and "Edit(./output/**)" in allow
    assert not any(a.startswith("Write(") and "output" not in a for a in allow)
    bash = [a for a in allow if a.startswith("Bash(")]
    assert bash and not any(
        any(bad in a for bad in ("curl", "ssh", "sudo", "bash ", "sh ")) for a in bash
    )
    assert any("-m pytest" in a for a in bash)
    assert not any(a.startswith(("WebFetch", "WebSearch")) for a in allow)
    assert settings["enabledPlugins"] == {} and "mcpServers" not in settings
    assert settings["autoMemoryEnabled"] is False
    env = settings["env"]
    assert env["DISABLE_AUTOUPDATER"] == "1" and env["DISABLE_TELEMETRY"] == "1"
    assert env["CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC"] == "1"
    for event in ("PreToolUse", "PostToolUse", "Stop"):
        commands = [h["command"] for group in settings["hooks"][event] for h in group["hooks"]]
        assert commands and all("/opt/claude-review/hooks/audit.py" in c for c in commands)
    assert not any("allow" in str(settings.get(k, "")) for k in ("apiKeyHelper",))
    text = (CR / "settings.json").read_text(encoding="utf-8")
    assert "sk-ant" not in text and "token" not in text.lower().replace("tokens", "")


@pytest.fixture(scope="module")
def audit() -> ModuleType:
    return _load(CR / "hooks" / "audit.py", "claude_audit")


def _event(tool: str, **tool_input: Any) -> dict[str, Any]:
    return {
        "hook_event_name": "PreToolUse",
        "tool_name": tool,
        "tool_input": tool_input,
        "session_id": "abcdef1234567890",
    }


def test_hook_policy(audit: ModuleType, tmp_path: Path) -> None:
    base = tmp_path / "runs" / "5"
    (base / "output").mkdir(parents=True)
    (base / "input").mkdir()
    (base / "input" / "a.txt").write_text("x", encoding="utf-8")
    d = audit.decide
    assert d(_event("Read", file_path=str(base / "input" / "a.txt")), base)[0] == "allow"
    assert d(_event("Read", file_path="/etc/passwd"), base)[0] == "deny"
    assert d(_event("Read", file_path="input/../../../etc/passwd"), base)[0] == "deny"
    assert d(_event("Read", file_path="~/.claude/.credentials.json"), base)[0] == "deny"
    assert d(_event("Grep", pattern="x", path="/var/lib/edgefinder"), base)[0] == "deny"
    assert (
        d(_event("Write", file_path=str(base / "output" / "analysis.md"), content="x"), base)[0]
        == "allow"
    )
    assert (
        d(_event("Write", file_path=str(base / "output" / "proposal-3.diff"), content="x"), base)[0]
        == "allow"
    )
    assert (
        d(_event("Write", file_path=str(base / "output" / "evil.sh"), content="x"), base)[0]
        == "deny"
    )
    assert (
        d(_event("Write", file_path=str(base / "input" / "a.txt"), content="x"), base)[0] == "deny"
    )
    assert d(_event("Edit", file_path="/etc/cron.d/x"), base)[0] == "deny"
    for tool in ("WebFetch", "WebSearch", "Task", "Skill", "mcp__x__y", "NotebookEdit", ""):
        assert d(_event(tool, url="https://x"), base)[0] == "deny", tool
    assert d(_event("Bash", command="ls input | head -5"), base)[0] == "allow"
    assert (
        d(
            _event(
                "Bash", command="grep -c fehler input/journal.txt && wc -l input/fetch-runs.json"
            ),
            base,
        )[0]
        == "allow"
    )
    assert (
        d(
            _event(
                "Bash",
                command="/opt/claude-review/venv/bin/python -m pytest -q input/snapshot/backend/tests",
            ),
            base,
        )[0]
        == "allow"
    )
    for bad in (
        "curl https://example.org",
        "wget x",
        "ssh x",
        "nc -z 10.0.0.1 22",
        "sudo ls",
        "systemctl stop x",
        "cat /etc/passwd",
        "cat ~/.claude/.credentials.json",
        "cat input/../../x",
        "ls > /tmp/x",
        "ls; rm -rf /",
        "ls `id`",
        "ls $(id)",
        "echo hi\nrm x",
        "ls &",
        "python3 -c 'print(1)'",
        "/opt/claude-review/venv/bin/python -c 'import os'",
        "/opt/claude-review/venv/bin/python -m pip install x",
        "git push",
        "bash -c ls",
        "env",
        "cat input/x | sh",
        "",
    ):
        assert d(_event("Bash", command=bad), base)[0] == "deny", bad
    assert (
        d(_event("Read", file_path=str(base)), None)[0] == "deny"
    )  # ohne gültiges Lauf-Verzeichnis nichts erlaubt


def test_hook_audit_masks_secrets_and_writes_jsonl(audit: ModuleType, tmp_path: Path) -> None:
    base = tmp_path / "run"
    base.mkdir()
    event = {
        "hook_event_name": "PostToolUse",
        "tool_name": "Bash",
        "tool_input": {"command": f"grep {SECRET_KEY} x"},
        "tool_response": {"stdout": f"{SECRET_BEARER} {EMAIL} " + "z" * 5000},
        "session_id": "s1",
    }
    entry = audit.record(event, "allow", "", base)
    line = (base / "audit.jsonl").read_text(encoding="utf-8")
    for secret in (SECRET_KEY, "abcdef1234567890SECRETTOKEN", EMAIL):
        assert secret not in line
    assert "GESCHWAERZT" in line and "p***@example.org" in line
    assert len(entry["result"]) < 900 and "Zeichen]" in entry["result"]
    assert json.loads(line)["event"] == "PostToolUse"
    pre = audit.record(_event("Bash", command="curl x"), "deny", "nicht erlaubt", base)
    assert pre["decision"] == "deny" and pre["reason"] == "nicht erlaubt"
    assert len((base / "audit.jsonl").read_text(encoding="utf-8").splitlines()) == 2


def test_hook_main_denies_when_log_not_writable(
    audit: ModuleType, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    import io

    base = Path("/var/lib/claude-review/runs/5")  # existiert hier nicht → Schreiben scheitert
    monkeypatch.setenv("CLAUDE_REVIEW_RUN_DIR", str(base))
    monkeypatch.setattr(
        "sys.stdin", io.StringIO(json.dumps(_event("Read", file_path=str(base / "input" / "a"))))
    )
    assert audit.main() == 0
    out = json.loads(capsys.readouterr().out)
    assert out["hookSpecificOutput"]["permissionDecision"] == "deny"
    assert "Protokoll nicht schreibbar" in out["hookSpecificOutput"]["permissionDecisionReason"]


def test_all_scripts_pass_bash_syntax_check() -> None:
    scripts = [
        CR / "install.sh",
        CR / "bin" / "run.sh",
        REPO / "deploy" / "install.sh",
        REPO / "deploy" / "deploy.sh",
        REPO / "deploy" / "sync-units.sh",
    ]
    for script in scripts:
        result = subprocess.run(
            ["bash", "-n", str(script)], capture_output=True, text=True, check=False
        )
        assert result.returncode == 0, f"{script}: {result.stderr}"
    shellcheck = shutil.which("shellcheck")
    if shellcheck:
        for script in scripts[:2]:
            result = subprocess.run(
                [shellcheck, "-S", "warning", str(script)],
                capture_output=True,
                text=True,
                check=False,
            )
            assert result.returncode == 0, result.stdout


def test_python_helpers_compile() -> None:
    for script in (CR / "bin" / "prepare.py", CR / "bin" / "finish.py", CR / "hooks" / "audit.py"):
        compile(script.read_text(encoding="utf-8"), str(script), "exec")


def test_install_script_has_dry_run_and_shows_plan() -> None:
    text = (CR / "install.sh").read_text(encoding="utf-8")
    assert "--dry-run" in text and "--apply-firewall" in text and "Was dieses Skript ändert" in text
    assert "curl | bash" in text and "| bash" not in text.replace("curl | bash", "")
    assert "npm ci" in text and "package-lock.json" in text
    assert "claude login" not in text and "setup-token" not in text
    assert (
        "--dangerously" not in text
        and "NOPASSWD" not in text
        and "sudoers" not in text.replace("sudoers: nicht", "")
    )


def test_npm_lockfile_pins_version_with_integrity() -> None:
    pkg = json.loads((CR / "npm" / "package.json").read_text(encoding="utf-8"))
    lock = json.loads((CR / "npm" / "package-lock.json").read_text(encoding="utf-8"))
    version = pkg["dependencies"]["@anthropic-ai/claude-code"]
    assert version[0].isdigit(), "Version muss exakt gepinnt sein"
    entry = lock["packages"]["node_modules/@anthropic-ai/claude-code"]
    assert entry["version"] == version and entry["integrity"].startswith("sha512-")
    assert f"CLAUDE_VERSION={version}" in (CR / "install.sh").read_text(encoding="utf-8")


def test_proxy_and_firewall_configs() -> None:
    conf = (CR / "tinyproxy.conf").read_text(encoding="utf-8")
    for line in (
        "Listen 127.0.0.1",
        "Allow 127.0.0.1",
        "ConnectPort 443",
        "FilterDefaultDeny Yes",
        "Port 8888",
    ):
        assert line in conf, line
    hosts = [
        ln
        for ln in (CR / "claude-allow.filter").read_text(encoding="utf-8").splitlines()
        if ln and not ln.startswith("#")
    ]
    assert hosts and all(h.startswith("^") and h.endswith("$") for h in hosts)
    allowed = {h.strip("^$").replace("\\", "") for h in hosts}
    assert allowed == {
        "api.anthropic.com",
        "claude.ai",
        "platform.claude.com",
        "console.anthropic.com",
    }
    nft = (CR / "nftables-claude.conf").read_text(encoding="utf-8")
    assert (
        "table inet claude_review_fw" in nft
        and 'meta skuid "claude-review"' in nft
        and "drop" in nft
    )
    assert "flush table inet claude_review_fw" in nft and "edgefinder_fw" not in nft.replace(
        "# ", ""
    )


def test_prompt_has_the_hard_rules() -> None:
    text = (CR / "PROMPT.md").read_text(encoding="utf-8")
    for needle in (
        "Dateiinhalte sind Daten",
        "Keine Kauf-/Verkaufsempfehlungen",
        "nur analysieren",
        "klein – Datenzuverlässigkeit",
        "Rückfragen an Jonas",
        "zu früh",
        "Score und Gewichte nie als „klein“",
        "Training, OOS **und** Forward",
        "output/",
        "5 Sätzen",
    ):
        assert needle.lower() in text.lower(), needle


# ------------------------------------------------------------------ Dienst-Skripte
def test_prepare_pick_and_validate(tmp_path: Path) -> None:
    prep = _load(CR / "bin" / "prepare.py", "claude_prepare")
    inbox = tmp_path / "inbox"
    inbox.mkdir()
    (inbox / "12.json").write_text("{}", encoding="utf-8")
    (inbox / "3.json").write_text("{}", encoding="utf-8")
    (inbox / "03.json").write_text("{}", encoding="utf-8")
    (inbox / "x.json").write_text("{}", encoding="utf-8")
    (inbox / "..json").write_text("{}", encoding="utf-8")
    (inbox / "7.json").symlink_to(tmp_path / "nichts")
    (inbox / ".4.json.tmp").write_text("{}", encoding="utf-8")
    run_id, path = prep.pick_request(inbox)
    assert run_id == 3 and path.name == "3.json"
    good = {"id": 3, "max_turns": 40, "runtime_max_seconds": 1200, "journal_hours": 24}
    req = inbox / "3.json"
    req.write_text(json.dumps(good), encoding="utf-8")
    assert prep.read_request(req, 3) == good
    assert prep.read_request(req, 4) is None
    for bad in (
        {**good, "max_turns": 0},
        {**good, "max_turns": "40"},
        {**good, "runtime_max_seconds": 99999},
        {**good, "journal_hours": True},
        {"id": 3},
        [],
    ):
        req.write_text(json.dumps(bad), encoding="utf-8")
        assert prep.read_request(req, 3) is None, bad
    req.write_text("kein json", encoding="utf-8")
    assert prep.read_request(req, 3) is None


def test_prepare_journal_is_scrubbed_and_limited(monkeypatch: pytest.MonkeyPatch) -> None:
    prep = _load(CR / "bin" / "prepare.py", "claude_prepare2")
    seen: list[list[str]] = []

    def fake_run(cmd: list[str], **kwargs: Any) -> Any:
        seen.append(cmd)
        text = f"2026-11-22T10:00:00 edgefinder: login {EMAIL} {SECRET_BEARER} {SECRET_KEY}\n" * 2
        return subprocess.CompletedProcess(
            cmd, 0, stdout=text + "a" * (prep.JOURNAL_MAX + 10), stderr=""
        )

    monkeypatch.setattr(prep.subprocess, "run", fake_run)
    text = prep.journal_text(24)
    for secret in (EMAIL, "abcdef1234567890SECRETTOKEN", SECRET_KEY):
        assert secret not in text
    assert len(text) <= prep.JOURNAL_MAX + 100
    cmd = seen[0]
    assert cmd[0] == "/usr/bin/journalctl" and "--since" in cmd and "-24h" in cmd
    assert not any(a for a in cmd if ";" in a or " " in a.strip())


@pytest.fixture
def stub_env(tmp_path: Path) -> dict[str, Any]:
    """Attrappe für die Installation: APP mit Skripten und einem Stub-`claude`, BASE mit einem Lauf."""
    app = tmp_path / "app"
    (app / "bin").mkdir(parents=True)
    (app / "hooks").mkdir()
    (app / "node_modules" / ".bin").mkdir(parents=True)
    for name in ("run.sh", "finish.py"):
        shutil.copy(CR / "bin" / name, app / "bin" / name)
    shutil.copy(CR / "hooks" / "scrub.py", app / "hooks" / "scrub.py")
    (app / "PROMPT.md").write_text("Prompt v1\n", encoding="utf-8")
    (app / "settings.json").write_text("{}", encoding="utf-8")
    base = tmp_path / "base"
    run = base / "runs" / "7"
    for sub in ("input", "output"):
        (run / sub).mkdir(parents=True)
    (run / "request.json").write_text(
        json.dumps({"id": 7, "max_turns": 12, "runtime_max_seconds": 120}), encoding="utf-8"
    )
    runtime = tmp_path / "runtime"
    runtime.mkdir()
    (runtime / "current").write_text("7\n", encoding="utf-8")
    env = {
        **os.environ,
        "CLAUDE_REVIEW_BASE": str(base),
        "CLAUDE_REVIEW_APP": str(app),
        "CLAUDE_REVIEW_RUNTIME": str(runtime),
    }
    return {"app": app, "base": base, "run": run, "runtime": runtime, "env": env}


def _stub(app: Path, body: str) -> None:
    path = app / "node_modules" / ".bin" / "claude"
    path.write_text("#!/usr/bin/env bash\n" + body, encoding="utf-8")
    path.chmod(0o755)


def _run_wrapper(env: dict[str, Any]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["bash", str(Path(env["app"]) / "bin" / "run.sh")],
        env=env["env"],
        capture_output=True,
        text=True,
        check=False,
        timeout=60,
    )


def test_wrapper_with_stub_claude_ok(stub_env: dict[str, Any]) -> None:
    _stub(
        stub_env["app"],
        f"""echo "ARGS: $*" >&2
echo "$CLAUDE_REVIEW_RUN_DIR" > "$CLAUDE_REVIEW_RUN_DIR/output/where.txt"
printf '# Analyse\\n' > "$CLAUDE_REVIEW_RUN_DIR/output/analysis.md"
echo '{{"type":"system","note":"{SECRET_KEY} {EMAIL}"}}'
echo '{{"type":"result","subtype":"success","is_error":false,"num_turns":5,"total_cost_usd":0.1234,"result":"fertig"}}'
""",
    )
    done = _run_wrapper(stub_env)
    assert done.returncode == 0, done.stderr
    run = stub_env["run"]
    status = json.loads((run / "status.json").read_text(encoding="utf-8"))
    assert (
        status["state"] == "ok"
        and status["turns"] == 5
        and status["cost_usd"] == 0.1234
        and status["exit_code"] == 0
    )
    assert status["duration_seconds"] >= 0
    transcript = (run / "transcript.jsonl").read_text(encoding="utf-8")
    assert SECRET_KEY not in transcript and EMAIL not in transcript and "GESCHWAERZT" in transcript
    stderr = (run / "claude.stderr").read_text(encoding="utf-8")
    for flag in (
        "-p Prompt v1",
        "--output-format stream-json",
        "--verbose",
        "--max-turns 12",
        "--strict-mcp-config",
        "--no-session-persistence",
        "--settings",
    ):
        assert flag in stderr, flag
    assert str(run) in (run / "output" / "where.txt").read_text(encoding="utf-8")
    assert "Lauf 7 ok" in done.stdout


def test_wrapper_failure_timeout_and_missing_analysis(stub_env: dict[str, Any]) -> None:
    _stub(
        stub_env["app"],
        'echo \'{"type":"result","is_error":true,"result":"Not logged in"}\'\nexit 1\n',
    )
    assert _run_wrapper(stub_env).returncode == 0
    status = json.loads((stub_env["run"] / "status.json").read_text(encoding="utf-8"))
    assert (
        status["state"] == "error"
        and status["exit_code"] == 1
        and "Not logged in" in status["message"]
    )
    # exit 0, aber keine analysis.md → Fehler
    _stub(stub_env["app"], 'echo \'{"type":"result","is_error":false,"num_turns":1}\'\n')
    _run_wrapper(stub_env)
    status = json.loads((stub_env["run"] / "status.json").read_text(encoding="utf-8"))
    assert status["state"] == "error" and "analysis.md" in status["message"]


def test_wrapper_rejects_bad_id_and_missing_request(stub_env: dict[str, Any]) -> None:
    _stub(stub_env["app"], "exit 0\n")
    (stub_env["runtime"] / "current").write_text("../../etc\n", encoding="utf-8")
    bad = _run_wrapper(stub_env)
    assert bad.returncode == 2 and "ungültige Lauf-ID" in bad.stderr
    (stub_env["runtime"] / "current").unlink()
    none = _run_wrapper(stub_env)
    assert none.returncode == 0 and "keine vorbereitete Anforderung" in none.stdout
    (stub_env["runtime"] / "current").write_text("8\n", encoding="utf-8")  # Lauf 8 existiert nicht
    assert _run_wrapper(stub_env).returncode == 2


def test_wrapper_sets_isolation_environment(stub_env: dict[str, Any]) -> None:
    _stub(
        stub_env["app"],
        'env | grep -E "^(HTTPS?_PROXY|NO_PROXY|DISABLE_[A-Z_]*|CLAUDE_CODE_[A-Z_]*|ENABLE_[A-Z_]*|CLAUDE_REVIEW_RUN_DIR|HOME)=" >&2\nexit 0\n',
    )
    _run_wrapper(stub_env)
    err = (stub_env["run"] / "claude.stderr").read_text(encoding="utf-8")
    for needle in (
        "HTTPS_PROXY=http://127.0.0.1:8888",
        "DISABLE_AUTOUPDATER=1",
        "DISABLE_TELEMETRY=1",
        "CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC=1",
        "ENABLE_CLAUDEAI_MCP_SERVERS=false",
    ):
        assert needle in err, needle


# ------------------------------------------------------------------ systemd
def test_claude_units_match_config_and_are_sandboxed() -> None:
    from edgefinder import systemd
    from edgefinder.config import load_config

    config = load_config(REPO / "config.yaml")
    files = systemd.generate_claude(config)
    out = CR / "systemd"
    assert {p.name for p in out.glob("claude-review*")} == set(files)
    for name, content in files.items():
        assert (out / name).read_text(encoding="utf-8") == content, name
    service = files["claude-review.service"]
    for line in (
        "User=claude-review",
        "NoNewPrivileges=true",
        "ProtectSystem=strict",
        "ReadWritePaths=/var/lib/claude-review",
        "PrivateTmp=true",
        "PrivateDevices=true",
        "ProtectHome=true",
        "MemoryMax=700M",
        "CPUQuota=50%",
        "Nice=19",
        "RuntimeMaxSec=1200",
        "IPAddressDeny=any",
        "IPAddressAllow=localhost",
        "RestrictAddressFamilies=AF_UNIX AF_INET",
        "SyslogIdentifier=claude-review",
        "ExecStartPre=+/opt/claude-review/bin/prepare.py",
        "ExecStart=/opt/claude-review/bin/run.sh",
        "CapabilityBoundingSet=\n",
    ):
        assert line in service, line
    assert (
        "InaccessiblePaths=/var/lib/claude-review/inbox /opt/edgefinder /var/lib/edgefinder"
        in service
    )
    assert "AF_INET6" not in service and "MemoryDenyWriteExecute" not in service  # node braucht JIT
    assert "PathChanged=/var/lib/claude-review/inbox" in files["claude-review.path"]
    assert "claude-review.timer" not in files  # kein Zeitplan, kein Fallback-Timer
    # gehört nicht in die edgefinder-Units (sync-units.sh installiert nur edgefinder*)
    assert not list((REPO / "deploy" / "systemd").glob("claude-review*"))


def test_admin_and_cleanup_units_can_write_claude_dirs() -> None:
    admin = (REPO / "deploy" / "systemd" / "edgefinder-adminjobs.service").read_text(
        encoding="utf-8"
    )
    assert (
        "ReadWritePaths=/var/lib/edgefinder -/var/lib/claude-review/inbox -/var/lib/claude-review/runs"
        in admin
    )
    cleanup = (REPO / "deploy" / "systemd" / "edgefinder-cleanup.service").read_text(
        encoding="utf-8"
    )
    assert "-/var/lib/claude-review/runs" in cleanup and "inbox" not in cleanup
    web = (REPO / "deploy" / "systemd" / "edgefinder.service").read_text(encoding="utf-8")
    assert "claude-review" not in web  # Webprozess schreibt dort nie
