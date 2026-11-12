from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from edgefinder.db import MigrationError, applied_versions, connect, migrate
from edgefinder.db.migrate import discover


@pytest.fixture
def conn(tmp_path: Path):
    connection = connect(tmp_path / "sub" / "test.db")
    yield connection
    connection.close()


def _write(directory: Path, name: str, sql: str) -> None:
    directory.mkdir(exist_ok=True)
    (directory / name).write_text(sql, encoding="utf-8")


def test_shipped_migrations_apply_and_are_idempotent(conn: sqlite3.Connection) -> None:
    first = migrate(conn)
    second = migrate(conn)

    assert [migration.version for migration in first] == [m.version for m in discover()]
    assert second == []
    tables = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    assert {"prices", "cot_reports", "macro_observations", "scores", "score_components"} <= tables


def test_connection_uses_wal_and_foreign_keys(conn: sqlite3.Connection) -> None:
    assert conn.execute("PRAGMA journal_mode").fetchone()[0] == "wal"
    assert conn.execute("PRAGMA foreign_keys").fetchone()[0] == 1


def test_score_components_cascade_and_constraints(conn: sqlite3.Connection) -> None:
    migrate(conn)
    conn.execute(
        "INSERT INTO scores (asset_id, profile, date, score, label, coverage, computed_at) "
        "VALUES ('EURUSD', 'swing', '2026-01-02', 4.2, 'Bullish', 1.0, '2026-01-02T07:30:00+00:00')"
    )
    score_id = conn.execute("SELECT id FROM scores").fetchone()[0]
    conn.execute(
        "INSERT INTO score_components (score_id, factor, subscore, weight, effective_weight, "
        "reason) VALUES (?, 'cot', 0.5, 0.25, 0.25, 'Test')",
        (score_id,),
    )

    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "INSERT INTO scores (asset_id, profile, date, score, label, coverage, computed_at) "
            "VALUES ('EURUSD', 'swing', '2026-01-03', 11, 'x', 1.0, 'x')"
        )
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "INSERT INTO scores (asset_id, profile, date, score, label, coverage, computed_at) "
            "VALUES ('EURUSD', 'swing', '2026-01-02', 1, 'x', 1.0, 'x')"
        )

    conn.execute("DELETE FROM scores WHERE id = ?", (score_id,))
    assert conn.execute("SELECT count(*) FROM score_components").fetchone()[0] == 0


def test_failed_migration_rolls_back_completely(conn: sqlite3.Connection, tmp_path: Path) -> None:
    directory = tmp_path / "migrations"
    _write(directory, "0001_ok.sql", "CREATE TABLE a (id INTEGER PRIMARY KEY);")
    _write(
        directory,
        "0002_broken.sql",
        "CREATE TABLE b (id INTEGER PRIMARY KEY);\nINSERT INTO missing VALUES (1);",
    )

    with pytest.raises(MigrationError, match="0002_broken"):
        migrate(conn, directory)

    tables = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    assert "a" in tables
    assert "b" not in tables
    assert list(applied_versions(conn)) == [1]


def test_modified_applied_migration_is_detected(conn: sqlite3.Connection, tmp_path: Path) -> None:
    directory = tmp_path / "migrations"
    _write(directory, "0001_ok.sql", "CREATE TABLE a (id INTEGER PRIMARY KEY);")
    migrate(conn, directory)
    _write(directory, "0001_ok.sql", "CREATE TABLE a (id INTEGER PRIMARY KEY, x TEXT);")

    with pytest.raises(MigrationError, match="verändert"):
        migrate(conn, directory)


def test_gap_in_numbering_is_rejected(tmp_path: Path) -> None:
    directory = tmp_path / "migrations"
    _write(directory, "0001_a.sql", "SELECT 1;")
    _write(directory, "0003_c.sql", "SELECT 1;")

    with pytest.raises(MigrationError, match="lückenlos"):
        discover(directory)


def test_database_newer_than_code_is_rejected(conn: sqlite3.Connection, tmp_path: Path) -> None:
    directory = tmp_path / "migrations"
    _write(directory, "0001_a.sql", "SELECT 1;")
    _write(directory, "0002_b.sql", "SELECT 1;")
    migrate(conn, directory)
    (directory / "0002_b.sql").unlink()

    with pytest.raises(MigrationError, match="fehlt"):
        migrate(conn, directory)
