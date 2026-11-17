"""FastAPI-Anwendung: JSON-API unter /api und Auslieferung des Frontend-Builds."""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from edgefinder import __version__
from edgefinder.api.routes import create_router
from edgefinder.config import Config
from edgefinder.db import applied_versions, connect

FRONTEND_DIST = Path("frontend/dist")


def create_app(config: Config, frontend_dist: Path | None = FRONTEND_DIST) -> FastAPI:
    app = FastAPI(
        title="edgefinder",
        version=__version__,
        docs_url="/api/docs",
        redoc_url=None,
        openapi_url="/api/openapi.json",
    )

    @app.get("/api/health")
    def health() -> dict[str, object]:
        """Für Deploy-Smoke-Test und Monitoring: Prozess läuft, Datenbank lesbar."""
        try:
            conn = connect(config.storage.database)
            try:
                schema_version = max(applied_versions(conn), default=0)
            finally:
                conn.close()
        except Exception as exc:
            raise HTTPException(status_code=503, detail="Datenbank nicht erreichbar") from exc
        return {"status": "ok", "version": __version__, "schema_version": schema_version}

    app.include_router(create_router(config))

    if frontend_dist is not None and (frontend_dist / "index.html").is_file():
        _mount_frontend(app, frontend_dist)

    return app


def _mount_frontend(app: FastAPI, dist: Path) -> None:
    """SPA ausliefern: Dateien aus dem Build, sonst index.html (Client-Routing)."""
    assets = dist / "assets"
    if assets.is_dir():
        app.mount("/assets", StaticFiles(directory=assets), name="assets")

    root = dist.resolve()

    @app.get("/{path:path}", include_in_schema=False)
    def spa(path: str) -> FileResponse:
        if path.startswith("api/"):
            raise HTTPException(status_code=404)
        candidate = (root / path).resolve()
        if path and candidate.is_file() and candidate.is_relative_to(root):
            return FileResponse(candidate)
        return FileResponse(root / "index.html", headers={"Cache-Control": "no-cache"})
