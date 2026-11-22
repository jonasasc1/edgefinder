# ruff: noqa: E501  (lange deutsche Texte)
"""Admin-Bereich: Rolle, Gating, Allowlist, Warteschlange, Runner, Berichte, CSRF, Migration, CLI."""

from __future__ import annotations

import json
import logging
import sqlite3
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from test_accounts import JSON, _as, _client, _migrations_up_to

from edgefinder import admin_jobs, cli, maintenance
from edgefinder.config import Config
from edgefinder.db import connect, migrate

ADMIN = "jonas@example.com"
OTHER = "anna@example.com"
GET_ENDPOINTS = [
    "/api/admin/overview",
    "/api/admin/jobs/1",
    "/api/admin/report",
    "/api/admin/report.md",
    "/api/admin/users",
]


def _setup(config: Config) -> TestClient:
    client = _client(config)
    client.get("/api/me", headers=_as(OTHER))
    client.get("/api/me", headers=_as(ADMIN))
    conn = connect(config.storage.database)
    admin_jobs.set_admin(conn, ADMIN, True)
    conn.close()
    return client


@pytest.fixture
def client(config: Config) -> TestClient:
    return _setup(config)


def _variant(config: Config, config_data: dict[str, Any], **overrides: Any) -> Config:
    """Gleiche Konfiguration (gleiche Test-DB) mit anderen Werten unter `admin:`."""
    data = {**config_data, "admin": {**config_data["admin"], **overrides}}
    return Config.model_validate(data)


def _post(client: TestClient, job: str, who: str = ADMIN, **extra: str) -> Any:
    return client.post("/api/admin/jobs", json={"job": job}, headers=_as(who, **extra))


# ------------------------------------------------------------------ Gating
def test_unauthenticated_is_401_and_non_admin_403_everywhere(client: TestClient) -> None:
    for path in GET_ENDPOINTS:
        assert client.get(path).status_code == 401, path
        denied = client.get(path, headers=_as(OTHER))
        assert denied.status_code == 403, path
        assert denied.json() == {"detail": "Kein Zugriff."}
        assert denied.headers["cache-control"] == "no-store"
    assert _post(client, "review", OTHER).status_code == 403
    assert client.post("/api/admin/jobs", json={"job": "review"}).status_code == 401


def test_unknown_account_is_403_and_not_provisioned(client: TestClient, config: Config) -> None:
    assert client.get("/api/admin/overview", headers=_as("neu@example.com")).status_code == 403
    conn = connect(config.storage.database)
    assert (
        conn.execute("SELECT count(*) FROM users WHERE email='neu@example.com'").fetchone()[0] == 0
    )


def test_me_reports_is_admin_only_from_database(client: TestClient) -> None:
    assert client.get("/api/me", headers=_as(ADMIN)).json()["is_admin"] is True
    assert client.get("/api/me", headers=_as(OTHER)).json()["is_admin"] is False


def test_admin_cannot_be_set_via_request_data(client: TestClient, config: Config) -> None:
    spoof = {
        "X-Admin": "1",
        "X-Is-Admin": "true",
        "Cf-Access-Authenticated-User-Email-Admin": "1",
        "X-Forwarded-User": ADMIN,
    }
    assert client.get("/api/admin/overview", headers=_as(OTHER, **spoof)).status_code == 403
    for body in ({"is_admin": True}, {"theme": "dark", "is_admin": True}):
        r = client.put("/api/me/preferences", json=body, headers=_as(OTHER))
        assert r.status_code == 422
    assert (
        client.put(
            "/api/me/favorites", json={"asset_ids": [], "is_admin": 1}, headers=_as(OTHER)
        ).status_code
        == 422
    )
    for method in ("put", "post", "patch"):
        r = getattr(client, method)("/api/me", json={"is_admin": True}, headers=_as(OTHER))
        assert r.status_code in (404, 405)
    conn = connect(config.storage.database)
    assert conn.execute("SELECT is_admin FROM users WHERE email = ?", (OTHER,)).fetchone()[0] == 0


def test_revoke_takes_effect_immediately(client: TestClient, config: Config) -> None:
    assert client.get("/api/admin/overview", headers=_as(ADMIN)).status_code == 200
    conn = connect(config.storage.database)
    admin_jobs.set_admin(conn, OTHER, True)
    admin_jobs.set_admin(conn, ADMIN, False)
    assert client.get("/api/admin/overview", headers=_as(ADMIN)).status_code == 403
    assert client.get("/api/admin/overview", headers=_as(OTHER)).status_code == 200


def test_header_ignored_in_off_mode_gives_401(config: Config, config_data: dict[str, Any]) -> None:
    config_data["auth"] = {"mode": "off"}
    client = _client(Config.model_validate(config_data))
    assert client.get("/api/admin/overview", headers=_as(ADMIN)).status_code == 401


# ------------------------------------------------------------------ Warteschlange
def test_enqueue_writes_row_trigger_and_audit(client: TestClient, config: Config) -> None:
    r = _post(client, "review")
    assert r.status_code == 202
    body = r.json()
    assert body["job"] == "review" and body["status"] == "queued" and body["requested_by"] == ADMIN
    assert (config.data_dir / admin_jobs.TRIGGER_NAME).is_file()
    conn = connect(config.storage.database)
    audit = conn.execute(
        "SELECT actor, action, detail FROM admin_audit WHERE action = 'job_requested'"
    ).fetchall()
    assert [tuple(a) for a in audit] == [(ADMIN, "job_requested", f"review (#{body['id']})")]
    fetched = client.get(f"/api/admin/jobs/{body['id']}", headers=_as(ADMIN))
    assert fetched.json()["status"] == "queued"
    assert client.get("/api/admin/jobs/999", headers=_as(ADMIN)).status_code == 404
    assert client.get("/api/admin/jobs/abc", headers=_as(ADMIN)).status_code == 422


@pytest.mark.parametrize("job", ["fetch", "cleanup", "rm -rf /", "", "REVIEW", "../x", "x" * 40])
def test_allowlist_rejects_everything_else(client: TestClient, job: str) -> None:
    assert _post(client, job).status_code == 422


def test_job_must_be_string_and_no_extra_fields(client: TestClient) -> None:
    for body in ({"job": 1}, {"job": "review", "args": ["x"]}, {}, [], "review"):
        r = client.post("/api/admin/jobs", json=body, headers=_as(ADMIN))
        assert r.status_code == 422, body


def test_config_allowlist_can_narrow(config: Config, config_data: dict[str, Any]) -> None:
    client = _setup(_variant(config, config_data, jobs=["evaluate"]))
    assert _post(client, "score").status_code == 422
    assert _post(client, "evaluate").status_code == 202


def test_second_active_job_of_same_type_is_409(client: TestClient) -> None:
    assert _post(client, "maintain").status_code == 202
    assert _post(client, "maintain").status_code == 409
    assert _post(client, "evaluate").status_code == 202


def test_cooldown_after_finish_is_429_with_retry_after(client: TestClient, config: Config) -> None:
    job = _post(client, "score").json()
    assert admin_jobs.run_queue(config, {"score": lambda c, cfg: maintenance.Run(items=3)}) == 1
    r = _post(client, "score")
    assert r.status_code == 429 and int(r.headers["retry-after"]) > 0
    conn = connect(config.storage.database)
    old = (datetime.now(UTC) - timedelta(minutes=11)).isoformat(timespec="seconds")
    conn.execute("UPDATE admin_jobs SET finished_at = ? WHERE id = ?", (old, job["id"]))
    assert _post(client, "score").status_code == 202


def test_review_has_shorter_cooldown(config: Config) -> None:
    assert config.admin.cooldown_for("review") == 2
    assert config.admin.cooldown_for("maintain") == 10


def test_queue_length_limit(config: Config, config_data: dict[str, Any]) -> None:
    client = _setup(_variant(config, config_data, max_queue=2))
    assert _post(client, "review").status_code == 202
    assert _post(client, "maintain").status_code == 202
    assert _post(client, "score").status_code == 429


def test_unique_index_blocks_parallel_duplicates(config: Config) -> None:
    conn = connect(config.storage.database)
    migrate(conn)
    sql = "INSERT INTO admin_jobs (job, requested_at, status) VALUES ('review', 'x', ?)"
    conn.execute(sql, ("queued",))
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(sql, ("running",))
    conn.execute("UPDATE admin_jobs SET status = 'ok'")
    conn.execute(sql, ("queued",))


# ------------------------------------------------------------------ Runner
def test_runner_executes_in_order_and_captures_log(client: TestClient, config: Config) -> None:
    first = _post(client, "evaluate").json()
    second = _post(client, "score").json()
    calls: list[str] = []

    def fake(name: str, errors: list[str] | None = None) -> Any:
        def run(conn: sqlite3.Connection, cfg: Config) -> maintenance.Run:
            calls.append(name)
            logging.getLogger("edgefinder.test").info("Zeile aus %s", name)
            return maintenance.Run(items=2, errors=errors or [])

        return run

    jobs = {"evaluate": fake("evaluate"), "score": fake("score", ["Scores: kaputt"])}
    assert admin_jobs.run_queue(config, jobs) == 2
    assert calls == ["evaluate", "score"]
    a = client.get(f"/api/admin/jobs/{first['id']}", headers=_as(ADMIN)).json()
    b = client.get(f"/api/admin/jobs/{second['id']}", headers=_as(ADMIN)).json()
    assert a["status"] == "ok" and "Zeile aus evaluate" in a["log_tail"] and a["finished_at"]
    assert b["status"] == "error" and "kaputt" in b["summary"]
    assert admin_jobs.run_queue(config, jobs) == 0


def test_runner_survives_exception_and_limits_log(client: TestClient, config: Config) -> None:
    _post(client, "evaluate")

    def boom(conn: sqlite3.Connection, cfg: Config) -> maintenance.Run:
        for i in range(500):
            logging.getLogger("x").info("Zeile %d %s", i, "y" * 50)
        raise RuntimeError("kaputt " + "z" * 1000)

    admin_jobs.run_queue(config, {"evaluate": boom})
    row = client.get("/api/admin/jobs/1", headers=_as(ADMIN)).json()
    assert row["status"] == "error" and row["summary"].startswith("RuntimeError: kaputt")
    assert len(row["summary"]) <= admin_jobs.MAX_SUMMARY
    assert len(row["log_tail"]) <= config.admin.log_tail_bytes


def test_runner_rejects_job_missing_from_allowlist_and_marks_crashed(config: Config) -> None:
    conn = connect(config.storage.database)
    migrate(conn)
    conn.execute(
        "INSERT INTO admin_jobs (job, requested_at, status) VALUES ('fetch', 'x', 'queued')"
    )
    conn.execute(
        "INSERT INTO admin_jobs (job, requested_at, status) VALUES ('score', 'x', 'running')"
    )
    assert admin_jobs.run_queue(config) == 1
    rows = {r["job"]: r["status"] for r in conn.execute("SELECT job, status FROM admin_jobs")}
    assert rows == {"fetch": "rejected", "score": "error"}


def test_runner_has_no_shell_or_process_path() -> None:
    source = (Path(admin_jobs.__file__)).read_text(encoding="utf-8")
    api = (Path(admin_jobs.__file__).parent / "api" / "admin.py").read_text(encoding="utf-8")
    for text in (source, api):
        for forbidden in ("subprocess", "os.system", "shell=True", "popen", "systemctl", "eval("):
            assert forbidden not in text
    assert set(admin_jobs.JOBS) == {"review", "maintain", "score", "evaluate"}


def test_real_review_and_evaluate_on_small_db(client: TestClient, config: Config) -> None:
    assert _post(client, "review").status_code == 202
    assert admin_jobs.run_queue(config) == 1
    job = client.get("/api/admin/jobs/1", headers=_as(ADMIN)).json()
    assert job["status"] == "ok", job
    assert (config.data_dir / maintenance.REVIEW_NAME).is_file()
    assert (config.data_dir / maintenance.DRIFT_NAME).is_file()
    conn = connect(config.storage.database)
    sources = {r[0] for r in conn.execute("SELECT source FROM fetch_runs")}
    assert "evaluate" in sources


def test_real_score_job_without_prices_reports_error(client: TestClient, config: Config) -> None:
    _post(client, "score")
    admin_jobs.run_queue(config)
    job = client.get("/api/admin/jobs/1", headers=_as(ADMIN)).json()
    assert job["status"] in ("ok", "error") and job["finished_at"]


# ------------------------------------------------------------------ Bericht, Übersicht, Konten
def test_report_only_serves_fixed_files(client: TestClient, config: Config) -> None:
    empty = client.get("/api/admin/report", headers=_as(ADMIN)).json()
    assert empty["review_md"] is None and empty["drift"] is None
    assert client.get("/api/admin/report.md", headers=_as(ADMIN)).status_code == 404
    (config.data_dir / maintenance.REVIEW_NAME).write_text("# Bericht\nZahlen", encoding="utf-8")
    (config.data_dir / maintenance.DRIFT_NAME).write_text('{"groups": []}', encoding="utf-8")
    (config.data_dir / "geheim.txt").write_text("nicht ausliefern", encoding="utf-8")
    report = client.get("/api/admin/report", headers=_as(ADMIN)).json()
    assert report["review_md"].startswith("# Bericht") and report["drift"] == {"groups": []}
    md = client.get("/api/admin/report.md", headers=_as(ADMIN))
    assert md.text.startswith("# Bericht")
    assert md.headers["content-disposition"] == 'attachment; filename="edgefinder-pruefbericht.md"'
    assert md.headers["content-type"].startswith("text/markdown")
    for path in ("/api/admin/report?path=../geheim.txt", "/api/admin/report.md?file=geheim.txt"):
        assert "nicht ausliefern" not in client.get(path, headers=_as(ADMIN)).text
    assert client.get("/api/admin/report/geheim.txt", headers=_as(ADMIN)).status_code == 404


def test_report_ignores_oversized_files(client: TestClient, config: Config) -> None:
    (config.data_dir / maintenance.REVIEW_NAME).write_text("x" * 300_000, encoding="utf-8")
    assert client.get("/api/admin/report", headers=_as(ADMIN)).json()["review_md"] is None


def test_overview_shape(client: TestClient, config: Config) -> None:
    _post(client, "review")
    body = client.get("/api/admin/overview", headers=_as(ADMIN)).json()
    assert body["model_version"] == config.scoring.model_version
    assert {j["job"] for j in body["jobs"]} == {"review", "maintain", "score", "evaluate"}
    review = next(j for j in body["jobs"] if j["job"] == "review")
    assert review["active_id"] == 1 and review["cooldown_minutes"] == 2
    assert body["recent_jobs"][0]["status"] == "queued"
    assert {r["source"] for r in body["runs"]} >= {"maintain", "evaluate"}
    assert "calibration" in body and "live" in body


def test_users_list_read_only(client: TestClient) -> None:
    client.put("/api/me/favorites", json={"asset_ids": ["EURUSD"]}, headers=_as(OTHER))
    body = client.get("/api/admin/users", headers=_as(ADMIN)).json()["users"]
    by = {u["email"]: u for u in body}
    assert by[OTHER]["favorites"] == 1 and by[OTHER]["is_admin"] is False
    assert by[ADMIN]["is_admin"] is True
    for method in ("delete", "put", "patch"):
        assert getattr(client, method)("/api/admin/users", headers=_as(ADMIN)).status_code == 405


# ------------------------------------------------------------------ CSRF
def test_csrf_checks_on_post(client: TestClient) -> None:
    body = json.dumps({"job": "review"})
    h = _as(ADMIN, **JSON)
    assert (
        client.post(
            "/api/admin/jobs", content=body, headers={**h, "Origin": "https://evil.example"}
        ).status_code
        == 403
    )
    assert (
        client.post("/api/admin/jobs", content=body, headers={**h, "Origin": "null"}).status_code
        == 403
    )
    assert (
        client.post(
            "/api/admin/jobs", content=body, headers={**h, "Sec-Fetch-Site": "cross-site"}
        ).status_code
        == 403
    )
    assert (
        client.post(
            "/api/admin/jobs", content=body, headers=_as(ADMIN, **{"Content-Type": "text/plain"})
        ).status_code
        == 415
    )
    assert client.post("/api/admin/jobs", content="x" * 1000, headers=h).status_code == 413
    assert client.post("/api/admin/jobs", content="{kaputt", headers=h).status_code == 400
    ok = client.post(
        "/api/admin/jobs",
        content=body,
        headers={**h, "Origin": "http://testserver", "Sec-Fetch-Site": "same-origin"},
    )
    assert ok.status_code == 202


def test_non_admin_gets_403_before_body_errors(client: TestClient) -> None:
    r = client.post("/api/admin/jobs", content="{kaputt", headers=_as(OTHER, **JSON))
    assert r.status_code == 403


# ------------------------------------------------------------------ Migration, CLI
def test_migration_0005_on_fresh_and_existing_database(tmp_path: Path) -> None:
    old = connect(tmp_path / "old.db")
    migrate(old, _migrations_up_to(4, tmp_path / "m4"))
    old.execute(
        "INSERT INTO users (email, display_name, created_at, last_seen_at) VALUES ('a@b.de','a','x','x')"
    )
    applied = migrate(old)
    assert [m.version for m in applied] == [5]
    assert old.execute("SELECT is_admin FROM users").fetchone()[0] == 0
    with pytest.raises(sqlite3.IntegrityError):
        old.execute("UPDATE users SET is_admin = 2")
    with pytest.raises(sqlite3.IntegrityError):
        old.execute("INSERT INTO admin_jobs (job, requested_at, status) VALUES ('x','x','weird')")
    fresh = connect(tmp_path / "fresh.db")
    migrate(fresh)
    tables = {r[0] for r in fresh.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    assert {"admin_jobs", "admin_audit"} <= tables


def test_cli_grant_revoke_list(
    config: Config, monkeypatch: pytest.MonkeyPatch, capsys: Any
) -> None:
    monkeypatch.setattr(cli, "load_config", lambda: config)
    assert cli.main(["admin", "grant", "  Jonas@Example.com "]) == 0
    assert cli.main(["admin", "list"]) == 0
    assert capsys.readouterr().out.splitlines()[-1] == ADMIN
    conn = connect(config.storage.database)
    assert conn.execute("SELECT is_admin FROM users WHERE email=?", (ADMIN,)).fetchone()[0] == 1
    assert cli.main(["admin", "grant", "kein-mail"]) == 2
    assert cli.main(["admin", "revoke", "unbekannt@example.com"]) == 1
    assert cli.main(["admin", "revoke", ADMIN]) == 1  # letzter Admin
    assert conn.execute("SELECT is_admin FROM users WHERE email=?", (ADMIN,)).fetchone()[0] == 1
    assert cli.main(["admin", "grant", OTHER]) == 0
    assert cli.main(["admin", "revoke", ADMIN]) == 0  # nicht der letzte
    assert cli.main(["admin", "revoke", OTHER, "--force"]) == 0
    assert admin_jobs.list_admins(conn) == []
    actions = [r[0] for r in conn.execute("SELECT action FROM admin_audit")]
    assert actions.count("admin_grant") == 2 and actions.count("admin_revoke") == 2


def test_cli_admin_run_empty_queue(config: Config, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(cli, "load_config", lambda: config)
    assert cli.main(["admin", "run"]) == 0
