from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from edgefinder.api.app import create_app
from edgefinder.config import Config
from edgefinder.db import connect, migrate


def _migrate(config: Config) -> None:
    conn = connect(config.storage.database)
    migrate(conn)
    conn.close()


def test_health_reports_schema_version(config: Config) -> None:
    _migrate(config)
    client = TestClient(create_app(config, frontend_dist=None))

    response = client.get("/api/health")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["schema_version"] >= 1


def test_spa_serves_files_and_falls_back_to_index(config: Config, tmp_path: Path) -> None:
    _migrate(config)
    dist = tmp_path / "dist"
    (dist / "assets").mkdir(parents=True)
    (dist / "index.html").write_text("<!doctype html><title>edgefinder</title>", encoding="utf-8")
    (dist / "assets" / "app.js").write_text("console.log(1)", encoding="utf-8")
    (dist / "manifest.webmanifest").write_text("{}", encoding="utf-8")
    (tmp_path / "secret.txt").write_text("geheim", encoding="utf-8")
    client = TestClient(create_app(config, frontend_dist=dist))

    assert "edgefinder" in client.get("/").text
    assert "edgefinder" in client.get("/asset/EURUSD").text
    assert client.get("/assets/app.js").text == "console.log(1)"
    assert client.get("/manifest.webmanifest").text == "{}"
    assert client.get("/api/unknown").status_code == 404
    assert client.get("/api/health").status_code == 200
    # Kein Ausbruch aus dem Build-Verzeichnis
    assert "geheim" not in client.get("/%2e%2e/secret.txt").text
    assert "geheim" not in client.get("/..%2fsecret.txt").text
