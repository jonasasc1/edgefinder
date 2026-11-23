from __future__ import annotations

import copy
import sqlite3
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any

import pytest
import yaml
from support import TEST_FRED_KEY, FakeClock

from edgefinder.config import Config, Secrets
from edgefinder.db import connect, migrate

REPO_ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture(scope="session")
def _config_data() -> dict[str, Any]:
    with (REPO_ROOT / "config.yaml").open(encoding="utf-8") as handle:
        return yaml.safe_load(handle)


@pytest.fixture
def config_data(_config_data: dict[str, Any]) -> dict[str, Any]:
    """Veränderbare Kopie der ausgelieferten config.yaml."""
    return copy.deepcopy(_config_data)


@pytest.fixture
def config(config_data: dict[str, Any], tmp_path: Path) -> Config:
    """Gültige Konfiguration, deren Daten in ein temporäres Verzeichnis zeigen."""
    config_data["storage"] = {
        "database": str(tmp_path / "test.db"),
        "raw_dir": str(tmp_path / "raw"),
    }
    return Config.model_validate(config_data)


# ---------------------------------------------------------------- Fetcher-Tests
@pytest.fixture
def clock() -> FakeClock:
    return FakeClock()


@pytest.fixture
def secrets() -> Secrets:
    # `_env_file=None`: Tests dürfen nie die echte .env lesen.
    return Secrets(_env_file=None, fred_api_key=TEST_FRED_KEY)  # type: ignore[call-arg]


@pytest.fixture
def db(config: Config) -> Iterator[sqlite3.Connection]:
    conn = connect(config.storage.database)
    migrate(conn)
    yield conn
    conn.close()


@pytest.fixture
def make_config(config_data: dict[str, Any], tmp_path: Path) -> Callable[..., Config]:
    """Konfiguration mit Änderungen: `make_config(economies=..., assets=...)`."""

    def build(**sections: Any) -> Config:
        data = copy.deepcopy(config_data)
        data.update(sections)
        # Tests mit verkleinerter Aktienliste: Vorgänger-CIKs nur für vorhandene Ticker behalten
        options = data["sources"]["edgar"]["options"]
        present = {stock["ticker"] for stock in data["assets"]["stocks"]}
        options["predecessor_ciks"] = {
            t: c for t, c in options.get("predecessor_ciks", {}).items() if t in present
        }
        # verkleinerte Volkswirtschaften: Kernzeilen nur für vorhandene Indikatoren behalten
        known = {k for eco in data["economies"].values() for k in eco["indicators"]}
        for group in data.get("scorecard", {}).get("core", []):
            group["rows"] = [
                r
                for r in group["rows"]
                if all(k in known for k in (r.get("members") or [r["key"]]))
            ]
        data["storage"] = {"database": str(tmp_path / "t.db"), "raw_dir": str(tmp_path / "raw")}
        return Config.model_validate(data)

    return build
