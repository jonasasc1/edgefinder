# ruff: noqa: E501  (lange deutsche Texte)
"""Gemeinsame Schutzprüfungen für schreibende Aufrufe (CSRF) und JSON-Bodys mit Größenlimit."""

from __future__ import annotations

import json
from collections.abc import Collection
from urllib.parse import urlsplit

from fastapi import HTTPException, Request


def check_origin(request: Request, extra_hosts: Collection[str]) -> None:
    """`Sec-Fetch-Site` nur same-origin/none; `Origin` muss zu Host/X-Forwarded-Host/public_hosts passen."""
    site = request.headers.get("sec-fetch-site")
    if site is not None and site not in ("same-origin", "none"):
        raise HTTPException(status_code=403, detail="Anfrage von fremder Herkunft abgelehnt.")
    origin = request.headers.get("origin")
    if origin is None:
        return
    allowed = set(extra_hosts)
    for value in (request.headers.get("host"), request.headers.get("x-forwarded-host")):
        if value:
            allowed.add(value.split(",")[0].strip().lower())
    if origin == "null" or urlsplit(origin).netloc.lower() not in allowed:
        raise HTTPException(status_code=403, detail="Anfrage von fremder Herkunft abgelehnt.")


async def read_json(request: Request, limit: int) -> object:
    media = request.headers.get("content-type", "").split(";")[0].strip().lower()
    if media != "application/json":
        raise HTTPException(status_code=415, detail="Erwartet wird Content-Type: application/json.")
    declared = request.headers.get("content-length", "")
    if declared.isdigit() and int(declared) > limit:
        raise HTTPException(status_code=413, detail="Anfrage zu groß.")
    body = bytearray()
    async for chunk in request.stream():
        body.extend(chunk)
        if len(body) > limit:
            raise HTTPException(status_code=413, detail="Anfrage zu groß.")
    try:
        return json.loads(bytes(body))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Der Body ist kein gültiges JSON.") from exc
