"""Nationale Inflationsquellen für `macro_observations` (UK, CA, AU, JP, NZ).

FRED/Eurostat/EZB haben für diese Länder keine aktuelle Gratis-Reihe (siehe CLAUDE.md). Alle
Quellen hier sind kostenlos, ohne Account und live geprüft (2026-11-18):

* `ons`     UK-CPI-Jahresrate (CSV-Generator der ONS-Webseite; die alte JSON-API `api.ons.gov.uk`
            ist seit 2024-11 abgeschaltet). Serie: "CDID/Datensatz", z. B. "D7G7/mm23".
* `statcan` Kanada-CPI-Index über den Web Data Service (POST, Vektor-ID, z. B. "41690973").
* `abs`     Australien-CPI-Index (Quartal) über die ABS-Data-API (SDMX-CSV), "Dataflow/Schlüssel".
* `imf`     Japan (monatlich) und Neuseeland (Quartal): CPI-Index der IMF-SDMX-API. Ersatz für
            e-Stat (verlangt appId/Account) bzw. Stats NZ (Schlüssel nötig, Zertifikat
            abgelaufen). Der IMF-Wert erscheint etwas später als die nationale Veröffentlichung,
            dafür steht `publication_lag_days` an der Serie.

Zeiträume stehen auf dem Periodenbeginn, es gibt nur den aktuellen Stand (`vintage_date = ''`).
"""

from __future__ import annotations

import csv
import io
import re
from datetime import date
from typing import Any

from edgefinder.fetchers.base import Fetcher, FetchError
from edgefinder.fetchers.macro import configured_series, period_start, store_observations

MONTHS = {
    name: number
    for number, name in enumerate(
        ("JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"), 1
    )
}
ONS_MONTH_ROW = re.compile(r'^"(\d{4}) ([A-Z]{3})","([^"]*)"$')


def parse_ons_csv(text: str) -> list[tuple[str, str, float]]:
    """ONS-CSV: nur die Monatszeilen ("2026 OCT","3.6"); Jahres-/Quartalszeilen entfallen."""
    rows = []
    for line in text.lstrip("﻿").splitlines():
        match = ONS_MONTH_ROW.match(line.strip())
        if match is None or match.group(2) not in MONTHS or not match.group(3).strip():
            continue
        day = date(int(match.group(1)), MONTHS[match.group(2)], 1)
        rows.append((day.isoformat(), "", float(match.group(3))))
    return sorted(rows)


def parse_statcan(payload: Any) -> list[tuple[str, str, float]]:
    """StatCan WDS (getDataFromVectorsAndLatestNPeriods) → (date, '', value)."""
    rows = []
    for item in payload:
        if item.get("status") != "SUCCESS":
            raise FetchError(f"StatCan-Antwort: Status {item.get('status')}")
        for point in item["object"]["vectorDataPoint"]:
            if point.get("value") is None:
                continue
            rows.append((period_start(point["refPer"]), "", float(point["value"])))
    return sorted(rows)


def parse_sdmx_csv(text: str) -> list[tuple[str, str, float]]:
    """SDMX-CSV (ABS, IMF): TIME_PERIOD/OBS_VALUE; IMF-Monate "2026-M09" → 2026-09-01."""
    rows = []
    for record in csv.DictReader(io.StringIO(text)):
        value, label = record.get("OBS_VALUE"), record.get("TIME_PERIOD")
        if not value or not label:
            continue
        label = re.sub(r"-M(\d{2})$", r"-\1", label)
        rows.append((period_start(label), "", float(value)))
    return sorted(rows)


class OnsFetcher(Fetcher):
    source = "ons"

    def fetch(self) -> int:
        since = self.history_start().date().isoformat()
        total = 0
        for series in configured_series(self.config, self.source):
            with self.unit(series):
                cdid, _, dataset = series.partition("/")
                if not dataset:
                    raise FetchError("Serie muss 'CDID/Datensatz' lauten")
                uri = f"/economy/inflationandpriceindices/timeseries/{cdid.lower()}/{dataset}"
                response = self.http.get(self.options["base_url"], {"format": "csv", "uri": uri})
                self.save_raw(series, response.content, ".csv")
                rows = [r for r in parse_ons_csv(response.text) if r[0] >= since]
                if not rows:
                    raise FetchError("Antwort ohne Monatswerte")
                store_observations(self, series, rows)
                total += len(rows)
        return total


class StatcanFetcher(Fetcher):
    source = "statcan"

    def fetch(self) -> int:
        years = int(self.options.get("history_years", 15))
        latest_n = years * 12 + 13  # genug Monate, auch für Vorjahresvergleiche
        total = 0
        for series in configured_series(self.config, self.source):
            with self.unit(series):
                response = self.http.post_json(
                    f"{self.options['base_url']}/getDataFromVectorsAndLatestNPeriods",
                    [{"vectorId": int(series), "latestN": latest_n}],
                )
                self.save_raw(series, response.content)
                rows = parse_statcan(response.json())
                if not rows:
                    raise FetchError("Antwort ohne Werte")
                store_observations(self, series, rows)
                total += len(rows)
        return total


class AbsFetcher(Fetcher):
    source = "abs"

    def fetch(self) -> int:
        start = self.history_start().year
        total = 0
        for series in configured_series(self.config, self.source):
            with self.unit(series):
                response = self.http.get(
                    f"{self.options['base_url']}/data/{series}",
                    {"startPeriod": f"{start}-Q1", "format": "csv"},
                    {"Accept": "application/vnd.sdmx.data+csv"},
                )
                self.save_raw(series, response.content, ".csv")
                rows = parse_sdmx_csv(response.text)
                if not rows:
                    raise FetchError("Antwort ohne Werte")
                store_observations(self, series, rows)
                total += len(rows)
        return total


class ImfFetcher(Fetcher):
    source = "imf"

    def fetch(self) -> int:
        start = self.history_start().strftime("%Y-%m")
        agency = self.options.get("agency", "IMF.STA")
        total = 0
        for series in configured_series(self.config, self.source):
            with self.unit(series):
                dataflow, _, key = series.partition("/")
                if not key:
                    raise FetchError("Serie muss 'Dataflow/Schlüssel' lauten")
                response = self.http.get(
                    f"{self.options['base_url']}/data/{agency},{dataflow}/{key}",
                    {"startPeriod": start},
                    {"Accept": "application/vnd.sdmx.data+csv"},
                )
                self.save_raw(series, response.content, ".csv")
                rows = parse_sdmx_csv(response.text)
                if not rows:
                    raise FetchError("Antwort ohne Werte")
                store_observations(self, series, rows)
                total += len(rows)
        return total
