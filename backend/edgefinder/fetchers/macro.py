"""Gemeinsames für die Makro-Quellen (FRED, Eurostat, ECB)."""

from __future__ import annotations

from datetime import date

from edgefinder.config import Config
from edgefinder.db import transaction
from edgefinder.fetchers.base import Fetcher


def configured_series(config: Config, source: str) -> list[str]:
    """Alle in config.yaml verwendeten Serien einer Quelle (ohne Doppelte)."""
    return sorted(
        {
            indicator.series
            for economy in config.economies.values()
            for indicator in economy.indicators.values()
            if indicator.source == source
        }
    )


def period_start(label: str) -> str:
    """Zeitraum-Label (2026-03, 2026-Q3, 2026, 2026-03-15) → Startdatum YYYY-MM-DD."""
    if "-Q" in label:
        year, quarter = label.split("-Q")
        return date(int(year), 3 * (int(quarter) - 1) + 1, 1).isoformat()
    parts = label.split("-")
    if len(parts) == 1:
        return date(int(parts[0]), 1, 1).isoformat()
    if len(parts) == 2:
        return date(int(parts[0]), int(parts[1]), 1).isoformat()
    return date(int(parts[0]), int(parts[1]), int(parts[2])).isoformat()


def store_observations(
    fetcher: Fetcher, series_id: str, rows: list[tuple[str, str, float]]
) -> None:
    """Schreibt Beobachtungen einer Serie atomar (Revisionen überschreiben alte Werte)."""
    with transaction(fetcher.conn):
        fetcher.conn.executemany(
            "INSERT OR REPLACE INTO macro_observations (source, series_id, date, vintage_date,"
            " value) VALUES (?, ?, ?, ?, ?)",
            [(fetcher.source, series_id, date, vintage, value) for date, vintage, value in rows],
        )
