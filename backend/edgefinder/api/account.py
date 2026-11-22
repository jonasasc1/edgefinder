"""Konto-Endpunkte unter /api/me: Auto-Provisionierung, Einstellungen, Favoriten.

Jede Abfrage läuft über die `user_id` der Identität (Cloudflare Access), nie über Client-Eingaben.
Schreibende Aufrufe: nur `application/json`, passender `Origin`, begrenzte Größe. Alle Antworten
sind `Cache-Control: no-store` (siehe app.py).
"""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from typing import Annotated, Any, Literal

from fastapi import APIRouter, HTTPException, Request
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from edgefinder.api import guard
from edgefinder.api.auth import AuthError, IdentityResolver
from edgefinder.config import Config
from edgefinder.db import connect, transaction

LAST_SEEN_INTERVAL = timedelta(minutes=5)  # kein Schreib-Sturm bei jedem Aufruf
MAX_FAVORITES = 100
MAX_PREFERENCES_BYTES = 2048
MAX_FAVORITES_BYTES = 8192
MAX_DISPLAY_NAME = 64


class Preferences(BaseModel):
    """Persönliche Einstellungen (Werte wie im Frontend); unbekannte Schlüssel werden abgelehnt."""

    model_config = ConfigDict(extra="forbid", strict=True)

    profile: Literal["swing", "long_term"] = "swing"
    view: Literal["cards", "list"] = "cards"
    sort: Literal["score-desc", "score-asc", "change-1d", "change-7d", "name"] = "score-desc"
    theme: Literal["system", "light", "dark"] = "system"
    fx: Literal["full", "calm"] = "full"  # calm = „Effekte reduzieren“ (zusätzlich zum System)
    filter: Literal["all", "forex", "index", "commodity", "stock"] = "all"


class FavoritesIn(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    asset_ids: list[Annotated[str, Field(min_length=1, max_length=32)]] = Field(
        max_length=MAX_FAVORITES
    )


class MeOut(BaseModel):
    email: str
    is_admin: bool
    display_name: str
    created_at: str
    preferences: Preferences
    favorites: list[str]


class FavoritesOut(BaseModel):
    favorites: list[str]


def _now() -> datetime:
    return datetime.now(UTC)


def _iso(moment: datetime) -> str:
    return moment.isoformat(timespec="seconds")


def provision(conn: sqlite3.Connection, email: str, now: datetime | None = None) -> sqlite3.Row:
    """Konto zur E-Mail holen; legt es beim ersten Aufruf an (idempotent, race-sicher)."""
    moment = now or _now()
    stamp = _iso(moment)
    name = email.split("@", 1)[0][:MAX_DISPLAY_NAME]
    conn.execute(
        "INSERT INTO users (email, display_name, created_at, last_seen_at) VALUES (?, ?, ?, ?) "
        "ON CONFLICT (email) DO NOTHING",
        (email, name, stamp, stamp),
    )
    user = conn.execute(
        "SELECT id, email, display_name, created_at, last_seen_at, is_admin FROM users "
        "WHERE email = ?",
        (email,),
    ).fetchone()
    # Nur gelegentlich schreiben: höchstens alle LAST_SEEN_INTERVAL
    conn.execute(
        "UPDATE users SET last_seen_at = ? WHERE id = ? AND last_seen_at < ?",
        (stamp, user["id"], _iso(moment - LAST_SEEN_INTERVAL)),
    )
    return user


def read_preferences(conn: sqlite3.Connection, user_id: int) -> Preferences:
    row = conn.execute("SELECT data FROM user_preferences WHERE user_id = ?", (user_id,)).fetchone()
    if row is None:
        return Preferences()
    try:
        return Preferences.model_validate(json.loads(row["data"]))
    except (ValueError, ValidationError):
        return Preferences()  # Altlast aus einer früheren Version: sicher auf Standard


def write_preferences(conn: sqlite3.Connection, user_id: int, patch: dict[str, Any]) -> Preferences:
    with transaction(conn):
        merged = read_preferences(conn, user_id).model_copy(update=patch)
        conn.execute(
            "INSERT INTO user_preferences (user_id, data, updated_at) VALUES (?, ?, ?) "
            "ON CONFLICT (user_id) DO UPDATE SET data = excluded.data, "
            "updated_at = excluded.updated_at",
            (user_id, merged.model_dump_json(), _iso(_now())),
        )
    return merged


def read_favorites(conn: sqlite3.Connection, user_id: int) -> list[str]:
    rows = conn.execute(
        "SELECT asset_id FROM user_favorites WHERE user_id = ? ORDER BY position", (user_id,)
    )
    return [row["asset_id"] for row in rows]


def write_favorites(conn: sqlite3.Connection, user_id: int, asset_ids: list[str]) -> list[str]:
    stamp = _iso(_now())
    with transaction(conn):
        conn.execute("DELETE FROM user_favorites WHERE user_id = ?", (user_id,))
        conn.executemany(
            "INSERT INTO user_favorites (user_id, asset_id, position, created_at) "
            "VALUES (?, ?, ?, ?)",
            [(user_id, asset_id, position, stamp) for position, asset_id in enumerate(asset_ids)],
        )
    return asset_ids


def _validation_detail(prefix: str, exc: ValidationError) -> str:
    # Nur Ort und Meldung, nie die Eingabewerte.
    parts = []
    for error in exc.errors()[:5]:
        where = ".".join(str(part) for part in error["loc"]) or "Body"
        parts.append(f"{where}: {error['msg']}")
    return f"{prefix}: " + "; ".join(parts)


def create_account_router(config: Config, resolver: IdentityResolver) -> APIRouter:
    router = APIRouter(prefix="/api/me")
    extra_hosts = {host.strip().lower() for host in config.auth.public_hosts}

    @contextmanager
    def db() -> Iterator[sqlite3.Connection]:
        conn = connect(config.storage.database)
        try:
            yield conn
        finally:
            conn.close()

    def identity(request: Request) -> str:
        try:
            return resolver.email_for(request.headers)
        except AuthError as exc:
            raise HTTPException(status_code=exc.status, detail=exc.detail) from exc

    def check_origin(request: Request) -> None:
        guard.check_origin(request, extra_hosts)

    read_json = guard.read_json

    def snapshot(conn: sqlite3.Connection, user: sqlite3.Row) -> MeOut:
        return MeOut(
            email=user["email"],
            is_admin=bool(user["is_admin"]),
            display_name=user["display_name"],
            created_at=user["created_at"],
            preferences=read_preferences(conn, user["id"]),
            favorites=read_favorites(conn, user["id"]),
        )

    @router.get("", response_model=MeOut)
    def me(request: Request) -> MeOut:
        """Eigenes Konto; legt es beim ersten authentifizierten Aufruf an."""
        email = identity(request)
        with db() as conn:
            return snapshot(conn, provision(conn, email))

    @router.put("/preferences", response_model=Preferences)
    async def put_preferences(request: Request) -> Preferences:
        """Teilupdate der Einstellungen; unbekannte Schlüssel oder Werte werden abgelehnt."""
        check_origin(request)
        email = identity(request)
        data = await read_json(request, MAX_PREFERENCES_BYTES)
        try:
            patch = Preferences.model_validate(data)
        except ValidationError as exc:
            raise HTTPException(
                status_code=422, detail=_validation_detail("Ungültige Einstellungen", exc)
            ) from exc

        def save() -> Preferences:
            with db() as conn:
                user = provision(conn, email)
                changes = patch.model_dump(include=patch.model_fields_set)
                return write_preferences(conn, user["id"], changes)

        return await run_in_threadpool(save)

    @router.put("/favorites", response_model=FavoritesOut)
    async def put_favorites(request: Request) -> FavoritesOut:
        """Komplette geordnete Favoritenliste ersetzen (letzter Stand gewinnt)."""
        check_origin(request)
        email = identity(request)
        data = await read_json(request, MAX_FAVORITES_BYTES)
        try:
            body = FavoritesIn.model_validate(data)
        except ValidationError as exc:
            raise HTTPException(
                status_code=422, detail=_validation_detail("Ungültige Favoriten", exc)
            ) from exc
        ids = body.asset_ids
        if len(set(ids)) != len(ids):
            raise HTTPException(status_code=422, detail="Ungültige Favoriten: Doppelte Einträge.")
        if any(asset_id not in config.assets_by_id for asset_id in ids):
            raise HTTPException(status_code=422, detail="Ungültige Favoriten: unbekanntes Asset.")

        def save() -> FavoritesOut:
            with db() as conn:
                user = provision(conn, email)
                return FavoritesOut(favorites=write_favorites(conn, user["id"], ids))

        return await run_in_threadpool(save)

    return router
