"""Verbindungsaufbau mit einheitlichen PRAGMAs."""

from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

BUSY_TIMEOUT_MS = 10_000


def connect(path: Path | str) -> sqlite3.Connection:
    """Öffnet die Datenbank (legt das Verzeichnis bei Bedarf an).

    WAL erlaubt gleichzeitiges Lesen durch die API, während ein Fetcher schreibt.
    Transaktionen werden explizit gesteuert (autocommit), siehe `transaction()`.
    """
    if str(path) != ":memory:":
        Path(path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path, autocommit=True)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    # (False Positive: Konstante (int), PRAGMA erlaubt keine Parameter; siehe ERGEBNIS.md)
    # nosemgrep
    conn.execute(f"PRAGMA busy_timeout = {BUSY_TIMEOUT_MS}")
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA synchronous = NORMAL")
    return conn


@contextmanager
def transaction(conn: sqlite3.Connection) -> Iterator[sqlite3.Connection]:
    """Eine Schreib-Transaktion: bei Fehler komplett zurückgerollt, sonst committed."""
    conn.execute("BEGIN IMMEDIATE")
    try:
        yield conn
    except BaseException:
        conn.execute("ROLLBACK")
        raise
    conn.execute("COMMIT")
