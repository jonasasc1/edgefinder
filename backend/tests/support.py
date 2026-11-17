"""Gemeinsame Hilfen für die Fetcher-Tests (Uhr, Fixtures, Mock-HTTP)."""

from __future__ import annotations

import json
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import httpx

FIXTURES = Path(__file__).parent / "fixtures"
NOW = datetime(2026, 11, 17, 12, 0, tzinfo=UTC)
TEST_FRED_KEY = "test-fred-key-0123456789"
TEST_CFTC_TOKEN = "test-cftc-token-abcdef"


class FakeClock:
    """Feste Uhr; `sleep` lässt die Zeit voranschreiten, statt wirklich zu warten."""

    def __init__(self, start: datetime = NOW) -> None:
        self.now = start
        self.sleeps: list[float] = []

    def __call__(self) -> datetime:
        return self.now

    def sleep(self, seconds: float) -> None:
        self.sleeps.append(seconds)
        self.now += timedelta(seconds=seconds)


def fixture_bytes(name: str) -> bytes:
    return (FIXTURES / name).read_bytes()


def fixture_json(name: str) -> Any:
    return json.loads(fixture_bytes(name))


def mock_client(handler: Callable[[httpx.Request], httpx.Response]) -> httpx.Client:
    return httpx.Client(transport=httpx.MockTransport(handler))


def economies_with(config_data: dict[str, Any], indicators: dict[str, Any]) -> dict[str, Any]:
    """Alle Volkswirtschaften der Konfiguration, aber nur die übergebenen Indikatoren.

    `indicators` hat die Form {"US": {"indicators": {...}}}.
    """
    return {
        code: {"name": e["name"], "indicators": indicators.get(code, {}).get("indicators", {})}
        for code, e in config_data["economies"].items()
    }
