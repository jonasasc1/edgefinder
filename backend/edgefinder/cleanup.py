"""Aufräumen der Rohdaten: Dateien in `raw_dir` und ihre `raw_files`-Einträge nach Ablauf löschen.

Die normalisierten Tabellen (Kurse, Makro, COT, …) bleiben unberührt; die Rohdateien sind nur
für Nachvollziehbarkeit und Neuverarbeitung gedacht.
"""

from __future__ import annotations

import contextlib
import logging
import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path

from edgefinder.db import transaction

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class CleanupResult:
    files: int  # gelöschte Dateien
    bytes: int  # freigegebene Bytes
    rows: int  # gelöschte raw_files-Einträge
    missing: int  # Einträge, deren Datei schon fehlte


def cleanup_raw(
    conn: sqlite3.Connection,
    raw_dir: Path,
    retention_days: int,
    *,
    now: datetime | None = None,
    dry_run: bool = False,
) -> CleanupResult:
    """Löscht Rohdateien mit `fetched_at` älter als `retention_days` Tage."""
    cutoff = ((now or datetime.now(UTC)) - timedelta(days=retention_days)).isoformat(
        timespec="seconds"
    )
    rows = conn.execute(
        "SELECT id, path FROM raw_files WHERE fetched_at < ? ORDER BY id", (cutoff,)
    ).fetchall()
    root = raw_dir.resolve()
    files = freed = missing = 0
    done: list[int] = []
    for row_id, relative in rows:
        target = (root / relative).resolve()
        if not target.is_relative_to(root):  # Schutz: nie außerhalb von raw_dir löschen
            log.warning("raw_files-Pfad außerhalb von raw_dir ignoriert: %s", relative)
            continue
        if target.is_file():
            freed += target.stat().st_size
            files += 1
            if not dry_run:
                target.unlink()
        else:
            missing += 1
        done.append(row_id)
    if not dry_run:
        with transaction(conn):
            conn.executemany("DELETE FROM raw_files WHERE id = ?", [(i,) for i in done])
        _remove_empty_dirs(root)
    return CleanupResult(files, freed, len(done), missing)


def _remove_empty_dirs(root: Path) -> None:
    if not root.is_dir():
        return
    for directory in sorted((p for p in root.rglob("*") if p.is_dir()), reverse=True):
        with contextlib.suppress(OSError):
            directory.rmdir()  # nur leere Verzeichnisse; sonst OSError
