from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any

import pytest
import yaml
from support import TEST_FRED_KEY

from edgefinder import cli
from edgefinder.config import Secrets
from edgefinder.fetchers.base import Fetcher


def _fake(source: str, outcome: str, calls: list[str]) -> type[Fetcher]:
    class Fake(Fetcher):
        def fetch(self) -> int:
            calls.append(self.source)
            if outcome == "error":
                raise RuntimeError("Quelle down")
            return 3

    Fake.source = source
    return Fake


@pytest.fixture
def cli_env(config_data: dict[str, Any], tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    config_data["storage"] = {
        "database": str(tmp_path / "cli.db"),
        "raw_dir": str(tmp_path / "raw"),
    }
    path = tmp_path / "config.yaml"
    path.write_text(yaml.safe_dump(config_data, allow_unicode=True), encoding="utf-8")
    monkeypatch.setenv("EDGEFINDER_CONFIG", str(path))
    monkeypatch.setattr(
        cli, "load_secrets", lambda: Secrets(_env_file=None, fred_api_key=TEST_FRED_KEY)
    )
    return tmp_path / "cli.db"


def test_fetch_single_source_runs_migrations_and_logs(
    cli_env: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls: list[str] = []
    monkeypatch.setattr(cli, "FETCHERS", {"fred": _fake("fred", "ok", calls)})

    assert cli.main(["fetch", "fred"]) == 0

    assert calls == ["fred"]
    conn = sqlite3.connect(cli_env)
    assert conn.execute("SELECT source, status, items FROM fetch_runs").fetchall() == [
        ("fred", "success", 3)
    ]


def test_fetch_all_continues_after_failure_and_signals_it(
    cli_env: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls: list[str] = []
    monkeypatch.setattr(
        cli,
        "FETCHERS",
        {"cftc": _fake("cftc", "error", calls), "fred": _fake("fred", "ok", calls)},
    )

    assert cli.main(["fetch", "all"]) == 1

    assert calls == ["cftc", "fred"]  # cftc fiel aus, fred lief trotzdem
    conn = sqlite3.connect(cli_env)
    statuses = dict(conn.execute("SELECT source, status FROM fetch_runs"))
    assert statuses == {"cftc": "error", "fred": "success"}


def test_disabled_source_is_skipped(
    cli_env: Path, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    path = Path(tmp_path / "config.yaml")
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    data["sources"]["fred"]["enabled"] = False
    path.write_text(yaml.safe_dump(data, allow_unicode=True), encoding="utf-8")
    calls: list[str] = []
    monkeypatch.setattr(cli, "FETCHERS", {"fred": _fake("fred", "ok", calls)})

    assert cli.main(["fetch", "fred"]) == 0
    assert calls == []


def test_unknown_source_is_rejected() -> None:
    with pytest.raises(SystemExit):
        cli.main(["fetch", "gibtsnicht"])
