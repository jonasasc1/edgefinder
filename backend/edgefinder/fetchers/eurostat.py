"""Eurostat (JSON-stat) und EZB (SDMX-CSV) für `macro_observations`.

Eurostat-Serien stehen in config.yaml als "Datensatz?Filter" (ein Wert je Dimension), EZB-Serien
als "Dataflow/Schlüssel". Zeiträume werden auf den Periodenbeginn abgebildet (Quartal
2026-Q3 → 2026-07-01), wie bei FRED. Beide Quellen liefern nur den aktuellen Stand
(`vintage_date = ''`), keine Vorabstände.
"""

from __future__ import annotations

import csv
import io
from typing import Any
from urllib.parse import parse_qsl

from edgefinder.fetchers.base import Fetcher, FetchError
from edgefinder.fetchers.macro import configured_series, period_start, store_observations


def parse_jsonstat(payload: dict[str, Any]) -> list[tuple[str, str, float]]:
    """Eurostat-JSON-stat → (date, '', value). Verlangt genau eine Zeitreihe."""
    if "error" in payload:
        raise FetchError(f"Eurostat-Fehler: {payload['error']}"[:200])
    ids, sizes = payload["id"], payload["size"]
    if 0 in sizes:  # Filter passt auf nichts (z. B. unbekannter Code)
        return []
    time_pos = ids.index("time")
    others = [size for pos, size in enumerate(sizes) if pos != time_pos]
    if any(size != 1 for size in others):
        raise ValueError(
            f"Filter nicht eindeutig (Dimensionen {dict(zip(ids, sizes, strict=True))})"
        )
    labels = payload["dimension"]["time"]["category"]["index"]
    by_position = {position: label for label, position in labels.items()}
    rows = []
    for position, value in payload.get("value", {}).items():
        if value is None:
            continue
        rows.append((period_start(by_position[int(position)]), "", float(value)))
    return sorted(rows)


def parse_ecb_csv(text: str) -> list[tuple[str, str, float]]:
    """EZB-SDMX-CSV (csvdata) → (date, '', value)."""
    rows = []
    for record in csv.DictReader(io.StringIO(text)):
        if record.get("OBS_VALUE") in (None, ""):
            continue
        rows.append((period_start(record["TIME_PERIOD"]), "", float(record["OBS_VALUE"])))
    return sorted(rows)


class EurostatFetcher(Fetcher):
    source = "eurostat"

    def fetch(self) -> int:
        since = self.history_start().strftime("%Y-%m")
        total = 0
        for series in configured_series(self.config, self.source):
            with self.unit(series):
                dataset, _, query = series.partition("?")
                params = dict(parse_qsl(query, strict_parsing=True))
                params |= {"format": "JSON", "lang": "EN", "sinceTimePeriod": since}
                response = self.http.get(f"{self.options['base_url']}/{dataset}", params)
                self.save_raw(series, response.content)
                rows = parse_jsonstat(response.json())
                if not rows:
                    raise FetchError("Antwort ohne Werte")
                store_observations(self, series, rows)
                total += len(rows)
        return total


class EcbFetcher(Fetcher):
    source = "ecb"

    def fetch(self) -> int:
        since = self.history_start().strftime("%Y-%m-%d")
        total = 0
        for series in configured_series(self.config, self.source):
            with self.unit(series):
                response = self.http.get(
                    f"{self.options['base_url']}/{series}",
                    {"format": "csvdata", "startPeriod": since, "detail": "dataonly"},
                )
                self.save_raw(series, response.content, ".csv")
                rows = parse_ecb_csv(response.text)
                if not rows:
                    raise FetchError("Antwort ohne Werte")
                store_observations(self, series, rows)
                total += len(rows)
        return total
