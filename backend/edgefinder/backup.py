"""Konsistente Sicherung der SQLite-Datenbank (Online-Backup, auch bei laufendem Dienst)."""

from __future__ import annotations

import contextlib
import logging
import sqlite3
from datetime import UTC, datetime
from pathlib import Path

log = logging.getLogger(__name__)

PREFIX = "edgefinder-"
SUFFIX = ".db"


def backup_database(
    database: Path, backup_dir: Path, keep: int, now: datetime | None = None
) -> Path:
    """Schreibt `edgefinder-<UTC-Zeit>.db` nach `backup_dir`, prüft sie und löscht ältere.

    Es entsteht erst eine `.partial`-Datei, die nach erfolgreicher `integrity_check`-Prüfung
    umbenannt wird; ein Abbruch hinterlässt also nie eine scheinbar gültige Sicherung.
    """
    if not database.is_file():
        raise FileNotFoundError(f"Datenbank nicht gefunden: {database}")
    stamp = (now or datetime.now(UTC)).strftime("%Y%m%dT%H%M%SZ")
    backup_dir.mkdir(parents=True, exist_ok=True)
    target = backup_dir / f"{PREFIX}{stamp}{SUFFIX}"
    partial = target.with_suffix(".partial")
    source = sqlite3.connect(database)
    try:
        dest = sqlite3.connect(partial)
        try:
            source.backup(dest)
            result = dest.execute("PRAGMA integrity_check").fetchone()[0]
        finally:
            dest.close()
    finally:
        source.close()
    if result != "ok":
        partial.unlink(missing_ok=True)
        raise RuntimeError(f"Sicherung fehlerhaft (integrity_check: {result})")
    partial.replace(target)
    for old in sorted(backup_dir.glob(f"{PREFIX}*{SUFFIX}"))[:-keep]:
        with contextlib.suppress(OSError):
            old.unlink()
            log.info("Alte Sicherung gelöscht: %s", old.name)
    return target
