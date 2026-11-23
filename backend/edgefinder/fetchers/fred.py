"""FRED (St. Louis Fed) inkl. ALFRED-Vintages für `macro_observations`.

Je Serie zwei Abrufe:
1. aktueller (ggf. revidierter) Stand → `vintage_date = ''`
2. alle Vorabstände (`realtime_start=1776-07-04 … 9999-12-31`) → `vintage_date` = Datum, ab dem
   der Wert in dieser Höhe veröffentlicht war (für Backtests ohne Vorgriff auf Revisionen).
"""

from __future__ import annotations

import logging
from typing import Any

from edgefinder.config import Config
from edgefinder.db import transaction
from edgefinder.fetchers.base import Fetcher, FetchError, iso
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


CALENDAR_LIMIT = 20  # nächste Termine je Release (reicht für den Stern „bald neue Daten“)


def calendar_series(config: Config) -> list[str]:
    """FRED-Serien, deren nächster Veröffentlichungstermin angezeigt wird: die der Kernzeilen
    der Scorecard (`scorecard.core`, inkl. Mitglieder von Misch-Zeilen)."""
    wanted: set[str] = set()
    for group in config.scorecard.core:
        for row in group.rows:
            wanted.update(row.members or [row.key])
    return sorted(
        {
            ind.series
            for economy in config.economies.values()
            for key, ind in economy.indicators.items()
            if ind.source == "fred" and key in wanted and ind.category != "rates"
        }
    )


def parse_release_id(payload: dict[str, Any]) -> int | None:
    """`series/release` → ID des ersten Releases (None, wenn keiner genannt ist)."""
    releases = payload.get("releases") or []
    return int(releases[0]["id"]) if releases else None


def parse_release_dates(payload: dict[str, Any], today: str) -> list[str]:
    """`release/dates` → Termine ab `today` (aufsteigend, ohne Doppelte)."""
    dates = {str(item["date"]) for item in payload.get("release_dates") or []}
    return sorted(d for d in dates if d >= today)


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

    def _release_id(self, series_id: str, key: str) -> int | None:
        """Release einer Serie (einmal ermittelt, dann in `source_state` gemerkt)."""
        state = self.get_state(f"release_id:{series_id}")
        if state is not None:
            return int(state[0])
        response = self.http.get(
            f"{self.options['base_url']}/series/release",
            {"series_id": series_id, "api_key": key, "file_type": "json"},
        )
        self.save_raw(f"{series_id}_release", response.content)
        release_id = parse_release_id(response.json())
        if release_id is not None:
            self.set_state(f"release_id:{series_id}", str(release_id))
        return release_id

    def _release_dates(self, release_id: int, key: str, today: str) -> list[str]:
        response = self.http.get(
            f"{self.options['base_url']}/release/dates",
            {
                "release_id": str(release_id),
                "api_key": key,
                "file_type": "json",
                "realtime_start": today,
                "realtime_end": REALTIME_LAST,
                "include_release_dates_with_no_data": "true",
                "sort_order": "asc",
                "limit": str(CALENDAR_LIMIT),
            },
        )
        payload = response.json()
        if "release_dates" not in payload:
            raise FetchError(f"Release {release_id}: Antwort ohne Termine")
        self.save_raw(f"release_{release_id}_dates", response.content)
        return parse_release_dates(payload, today)

    def fetch_calendar(self, key: str) -> None:
        """Nächste Veröffentlichungstermine je Serie (höchstens 1× je Tag und Serie).
        Fehler je Serie → `partial`, die Beobachtungen bleiben davon unberührt."""
        if not self.options.get("release_calendar", True):
            return
        today = self.clock().date().isoformat()
        by_release: dict[int, list[str]] = {}
        for series_id in calendar_series(self.config):
            with self.unit(f"calendar:{series_id}"):
                done = self.get_state(f"calendar:{series_id}")
                if done is not None and done[0] == today:
                    continue
                release_id = self._release_id(series_id, key)
                if release_id is None:
                    raise FetchError(f"{series_id}: kein Release bei FRED")
                if release_id not in by_release:
                    by_release[release_id] = self._release_dates(release_id, key, today)
                self._store_calendar(series_id, by_release[release_id], today)
                self.set_state(f"calendar:{series_id}", today)

    def _store_calendar(self, series_id: str, dates: list[str], today: str) -> None:
        fetched = iso(self.clock())
        with transaction(self.conn):
            self.conn.execute(
                "DELETE FROM macro_release_calendar WHERE series_id = ? AND release_date >= ?",
                (series_id, today),
            )
            self.conn.executemany(
                "INSERT OR REPLACE INTO macro_release_calendar (series_id, release_date,"
                " fetched_at) VALUES (?, ?, ?)",
                [(series_id, d, fetched) for d in dates],
            )

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
        self.fetch_calendar(key)
        return total
