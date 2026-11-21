"""FastAPI-Anwendung: JSON-API unter /api und Auslieferung des Frontend-Builds."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from edgefinder import __version__
from edgefinder.api.account import create_account_router
from edgefinder.api.auth import IdentityResolver
from edgefinder.api.routes import create_router
from edgefinder.config import Config, Secrets
from edgefinder.db import applied_versions, connect

FRONTEND_DIST = Path("frontend/dist")
REVALIDATE = {"sw.js", "manifest.webmanifest", "theme-init.js"}


def create_app(
    config: Config,
    frontend_dist: Path | None = FRONTEND_DIST,
    secrets: Secrets | None = None,
    resolver: IdentityResolver | None = None,
) -> FastAPI:
    app = FastAPI(
        title="edgefinder",
        version=__version__,
        docs_url="/api/docs",
        redoc_url=None,
        openapi_url="/api/openapi.json",
    )

    @app.middleware("http")
    async def no_store_for_account(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        """Konto-Antworten (auch Fehler) dürfen nie zwischengespeichert werden."""
        response = await call_next(request)
        if request.url.path == "/api/me" or request.url.path.startswith("/api/me/"):
            response.headers["Cache-Control"] = "no-store"
        return response

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
    app.include_router(
        create_account_router(config, resolver or IdentityResolver(config.auth, secrets))
    )

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
            # Service Worker und Manifest müssen immer neu geprüft werden (sonst bleibt eine
            # alte App-Version hängen); gehashte Dateien unter /assets sind davon nicht betroffen.
            headers = {"Cache-Control": "no-cache"} if path in REVALIDATE else None
            return FileResponse(candidate, headers=headers)
        return FileResponse(root / "index.html", headers={"Cache-Control": "no-cache"})
