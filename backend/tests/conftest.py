from __future__ import annotations

import copy
from pathlib import Path
from typing import Any

import pytest
import yaml

from edgefinder.config import Config

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
