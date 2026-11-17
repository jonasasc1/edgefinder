"""FRED (St. Louis Fed) inkl. ALFRED-Vintages für `macro_observations`.

Je Serie zwei Abrufe:
1. aktueller (ggf. revidierter) Stand → `vintage_date = ''`
2. alle Vorabstände (`realtime_start=1776-07-04 … 9999-12-31`) → `vintage_date` = Datum, ab dem
   der Wert in dieser Höhe veröffentlicht war (für Backtests ohne Vorgriff auf Revisionen).
"""

from __future__ import annotations

import logging
from typing import Any

from edgefinder.fetchers.base import Fetcher, FetchError
from edgefinder.fetchers.macro import configured_series, store_observations

log = logging.getLogger(__name__)

REALTIME_FIRST = "1776-07-04"  # frühester Wert, den die FRED-API für realtime_start erlaubt
REALTIME_LAST = "9999-12-31"
PAGE_LIMIT = 100_000  # FRED-Maximum je Antwort


def parse_observations(payload: dict[str, Any], *, vintage: bool) -> list[tuple[str, str, float]]:
    """FRED-JSON → (date, vintage_date, value); fehlende Werte ('.') entfallen."""
    rows = []
    for obs in payload["observations"]:
        if obs["value"] in (".", "", None):
            continue
        rows.append((obs["date"], obs["realtime_start"] if vintage else "", float(obs["value"])))
    return rows


class FredFetcher(Fetcher):
    source = "fred"

    def series_ids(self) -> list[str]:
        return configured_series(self.config, self.source)

    def _observations(
        self, series_id: str, key: str, params: dict[str, str], *, vintage: bool
    ) -> list[tuple[str, str, float]]:
        url = f"{self.options['base_url']}/series/observations"
        rows: list[tuple[str, str, float]] = []
        offset = 0
        while True:
            query = {
                "series_id": series_id,
                "api_key": key,
                "file_type": "json",
                "limit": str(PAGE_LIMIT),
                "offset": str(offset),
                **params,
            }
            response = self.http.get(url, query)
            payload = response.json()
            if "observations" not in payload:
                raise FetchError(f"{series_id}: Antwort ohne Beobachtungen")
            suffix = "vintages" if vintage else "current"
            self.save_raw(f"{series_id}_{suffix}_{offset}", response.content)
            rows.extend(parse_observations(payload, vintage=vintage))
            offset += PAGE_LIMIT
            if offset >= int(payload.get("count", 0)):
                return rows

    def _vintages(self, series_id: str, key: str, start: str) -> list[tuple[str, str, float]]:
        params = {
            "observation_start": start,
            "realtime_start": REALTIME_FIRST,
            "realtime_end": REALTIME_LAST,
        }
        try:
            return self._observations(series_id, key, params, vintage=True)
        except FetchError as exc:
            if exc.status != 400:
                raise
            # ALFRED erlaubt höchstens 2000 Vintage-Daten. Das trifft tägliche Marktdaten
            # (z. B. DGS10), die nicht revidiert werden; der aktuelle Stand genügt dort.
            log.info(
                "%s: keine Vintages abrufbar (zu viele Vorabstände), nur aktueller Stand", series_id
            )
            return []

    def fetch(self) -> int:
        if self.secrets.fred_api_key is None:
            raise FetchError("FRED_API_KEY fehlt (.env)")
        key = self.secrets.fred_api_key.get_secret_value()
        start = self.history_start().strftime("%Y-%m-%d")
        with_vintages = bool(self.options.get("vintages", True))
        total = 0
        for series_id in self.series_ids():
            with self.unit(series_id):
                rows = self._observations(
                    series_id, key, {"observation_start": start}, vintage=False
                )
                if with_vintages:
                    rows += self._vintages(series_id, key, start)
                store_observations(self, series_id, rows)
                total += len(rows)
        return total
