"""Versionierte Migrationen: fortlaufend nummerierte SQL-Dateien in `migrations/`.

Jede Migration läuft in einer eigenen Transaktion. Bereits angewendete Migrationen
dürfen nicht mehr verändert werden; das wird über eine Prüfsumme erkannt.
"""

from __future__ import annotations

import hashlib
import re
import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

MIGRATIONS_DIR = Path(__file__).parent / "migrations"
_FILENAME = re.compile(r"^(\d{4})_([a-z0-9_]+)\.sql$")


class MigrationError(RuntimeError):
    pass


@dataclass(frozen=True)
class Migration:
    version: int
    name: str
    sql: str

    @property
    def checksum(self) -> str:
        return hashlib.sha256(self.sql.encode("utf-8")).hexdigest()


def discover(directory: Path = MIGRATIONS_DIR) -> list[Migration]:
    migrations: list[Migration] = []
    for path in sorted(directory.glob("*.sql")):
        match = _FILENAME.match(path.name)
        if not match:
            raise MigrationError(f"Ungültiger Migrationsname: {path.name} (erwartet NNNN_name.sql)")
        migrations.append(
            Migration(int(match.group(1)), match.group(2), path.read_text(encoding="utf-8"))
        )
    versions = [migration.version for migration in migrations]
    if versions != list(range(1, len(versions) + 1)):
        raise MigrationError(f"Migrationen müssen lückenlos ab 0001 nummeriert sein: {versions}")
    return migrations


def _ensure_table(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS schema_migrations (
            version     INTEGER PRIMARY KEY,
            name        TEXT NOT NULL,
            checksum    TEXT NOT NULL,
            applied_at  TEXT NOT NULL
        ) STRICT
        """
    )


def applied_versions(conn: sqlite3.Connection) -> dict[int, str]:
    """Angewendete Versionen mit ihrer Prüfsumme."""
    _ensure_table(conn)
    rows = conn.execute("SELECT version, checksum FROM schema_migrations ORDER BY version")
    return {row[0]: row[1] for row in rows}


def migrate(conn: sqlite3.Connection, directory: Path = MIGRATIONS_DIR) -> list[Migration]:
    """Wendet alle ausstehenden Migrationen an und gibt sie zurück."""
    migrations = discover(directory)
    applied = applied_versions(conn)

    known = {migration.version: migration for migration in migrations}
    for version, checksum in applied.items():
        migration = known.get(version)
        if migration is None:
            raise MigrationError(
                f"Datenbank enthält Migration {version:04d}, die im Code fehlt "
                "(älterer Code-Stand als die Datenbank?)"
            )
        if migration.checksum != checksum:
            raise MigrationError(
                f"Migration {version:04d}_{migration.name} wurde nach dem Anwenden verändert"
            )

    pending = [migration for migration in migrations if migration.version not in applied]
    for migration in pending:
        _apply(conn, migration)
    return pending


def _apply(conn: sqlite3.Connection, migration: Migration) -> None:
    if not sqlite3.complete_statement(migration.sql.strip() or ";"):
        raise MigrationError(f"Migration {migration.version:04d} endet nicht mit einem Semikolon")
    applied_at = datetime.now(UTC).isoformat(timespec="seconds")
    try:
        conn.execute("BEGIN IMMEDIATE")
        # executescript führt mehrere Anweisungen aus; bei autocommit bleibt die oben
        # geöffnete Transaktion bestehen, sodass ein Fehler alles zurückrollt.
        conn.executescript(migration.sql)
        conn.execute(
            "INSERT INTO schema_migrations (version, name, checksum, applied_at) "
            "VALUES (?, ?, ?, ?)",
            (migration.version, migration.name, migration.checksum, applied_at),
        )
        conn.execute("COMMIT")
    except sqlite3.Error as exc:
        if conn.in_transaction:
            conn.execute("ROLLBACK")
        raise MigrationError(
            f"Migration {migration.version:04d}_{migration.name} fehlgeschlagen: {exc}"
        ) from exc
