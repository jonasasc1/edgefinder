from __future__ import annotations

import sqlite3
from datetime import date, timedelta
from pathlib import Path

import pytest
from test_cli_fetch import cli_env  # noqa: F401

from edgefinder import cli


def _seed(db_path: Path) -> None:
    conn = sqlite3.connect(db_path)
    day = date(2025, 1, 1)
    rows = []
    for i in range(500):
        rows.append(("EURGBP", (day + timedelta(days=i)).isoformat(), 100 + i * 0.01 + (i % 7)))
    conn.executemany("INSERT INTO prices (asset_id, date, close) VALUES (?, ?, ?)", rows)
    conn.commit()
    conn.close()


def test_score_command_as_of_and_idempotent(cli_env: Path) -> None:  # noqa: F811
    assert cli.main(["migrate"]) == 0
    _seed(cli_env)
    assert cli.main(["score", "--as-of", "2026-03-02", "--asset", "EURGBP"]) == 0
    assert cli.main(["score", "--as-of", "2026-03-02", "--asset", "EURGBP"]) == 0
    conn = sqlite3.connect(cli_env)
    assert conn.execute("SELECT COUNT(*) FROM scores").fetchone()[0] == 2
    conn.close()


def test_score_command_range_and_errors(cli_env: Path) -> None:  # noqa: F811
    assert cli.main(["migrate"]) == 0
    _seed(cli_env)
    assert (
        cli.main(["score", "--from", "2026-03-02", "--to", "2026-03-06", "--asset", "EURGBP"]) == 0
    )
    conn = sqlite3.connect(cli_env)
    assert conn.execute("SELECT COUNT(*) FROM scores").fetchone()[0] == 10
    conn.close()
    assert cli.main(["score", "--asset", "NOPE"]) == 2
    assert cli.main(["score", "--as-of", "2026-03-02", "--from", "2026-03-01"]) == 2
    assert cli.main(["score", "--from", "2026-03-06", "--to", "2026-03-02"]) == 2
    assert cli.main(["score", "--as-of", "2026-03-02", "--asset", "AAPL"]) == 1  # keine Kurse


def test_bad_date_is_rejected(cli_env: Path) -> None:  # noqa: F811
    with pytest.raises(SystemExit):
        cli.main(["score", "--as-of", "morgen"])
