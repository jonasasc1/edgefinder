"""`edgefinder cleanup`: nur Rohdateien über der Aufbewahrungsfrist verschwinden."""

from __future__ import annotations

import sqlite3
from datetime import UTC, datetime, timedelta
from pathlib import Path

from test_cli_fetch import cli_env  # noqa: F401

from edgefinder import cli
from edgefinder.cleanup import cleanup_raw
from edgefinder.db import connect, migrate

NOW = datetime(2026, 11, 18, 12, 0, tzinfo=UTC)


def _add(conn: sqlite3.Connection, raw_dir: Path, name: str, age_days: int, *, create=True):
    relative = f"fred/{name}.json"
    if create:
        (raw_dir / "fred").mkdir(parents=True, exist_ok=True)
        (raw_dir / relative).write_bytes(b"x" * 100)
    stamp = (NOW - timedelta(days=age_days)).isoformat(timespec="seconds")
    conn.execute(
        "INSERT INTO raw_files (source, key, path, sha256, bytes, fetched_at)"
        " VALUES ('fred', ?, ?, 'h', 100, ?)",
        (name, relative, stamp),
    )


def test_cleanup_deletes_only_old_files(tmp_path: Path) -> None:
    conn = connect(tmp_path / "t.db")
    migrate(conn)
    raw = tmp_path / "raw"
    _add(conn, raw, "old", 31)
    _add(conn, raw, "edge", 29)
    _add(conn, raw, "new", 1)
    _add(conn, raw, "gone", 90, create=False)
    conn.execute("INSERT INTO prices (asset_id, date, close) VALUES ('X', '2020-01-01', 1)")

    dry = cleanup_raw(conn, raw, 30, now=NOW, dry_run=True)
    assert (dry.files, dry.rows, dry.missing) == (1, 2, 1)
    assert (raw / "fred/old.json").exists()

    result = cleanup_raw(conn, raw, 30, now=NOW)
    assert (result.files, result.bytes, result.rows, result.missing) == (1, 100, 2, 1)
    assert not (raw / "fred/old.json").exists()
    assert (raw / "fred/edge.json").exists()
    assert (raw / "fred/new.json").exists()
    left = {r[0] for r in conn.execute("SELECT key FROM raw_files")}
    assert left == {"edge", "new"}
    assert conn.execute("SELECT COUNT(*) FROM prices").fetchone()[0] == 1  # normalisiert bleibt


def test_cleanup_ignores_paths_outside_raw_dir(tmp_path: Path) -> None:
    conn = connect(tmp_path / "t.db")
    migrate(conn)
    victim = tmp_path / "keep.txt"
    victim.write_text("wichtig")
    conn.execute(
        "INSERT INTO raw_files (source, key, path, sha256, bytes, fetched_at)"
        " VALUES ('x', 'k', '../keep.txt', 'h', 1, '2000-01-01T00:00:00+00:00')"
    )
    result = cleanup_raw(conn, tmp_path / "raw", 30, now=NOW)
    assert result.rows == 0
    assert victim.exists()


def test_cleanup_command(cli_env: Path) -> None:  # noqa: F811
    assert cli.main(["migrate"]) == 0
    assert cli.main(["cleanup", "--dry-run"]) == 0
    assert cli.main(["cleanup", "--days", "7"]) == 0
