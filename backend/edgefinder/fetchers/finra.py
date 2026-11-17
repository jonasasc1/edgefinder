"""FINRA Short Interest (konsolidiert, zweiwöchentlich) über die öffentliche Daten-API.

Die API braucht für diesen Datensatz keinen Account (live geprüft 2026-11-17). Der Abruf ist
eine POST-Abfrage mit Filtern; Sortierung ist nur mit festem Abrechnungsdatum erlaubt und
wird nicht genutzt.
"""

from __future__ import annotations

import re
from datetime import timedelta
from typing import Any

from edgefinder.db import transaction
from edgefinder.fetchers.base import Fetcher

API_URL = "https://api.finra.org/data/group/otcMarket/name/consolidatedShortInterest"
PAGE_SIZE = 5000
# Meldet ein Ticker so lange nichts mehr, ist er vermutlich umbenannt oder delistet.
STALE_AFTER_DAYS = 45


def finra_symbol(ticker: str) -> str:
    """FINRA führt Klassen-Aktien ohne Trenner (BRK-B → BRKB, live geprüft)."""
    return re.sub(r"[-./ ]", "", ticker).upper()


def parse_rows(records: list[dict[str, Any]], tickers: dict[str, str]) -> list[tuple[Any, ...]]:
    """FINRA-Datensätze → Zeilen für `short_interest`; `tickers` bildet FINRA-Symbol → Ticker ab."""
    rows = []
    for record in records:
        ticker = tickers.get(str(record.get("symbolCode", "")).upper())
        quantity = record.get("currentShortPositionQuantity")
        if ticker is None or quantity is None or not record.get("settlementDate"):
            continue
        rows.append(
            (
                ticker,
                record["settlementDate"][:10],
                float(quantity),
                record.get("averageDailyVolumeQuantity"),
                record.get("daysToCoverQuantity"),
            )
        )
    return rows


class FinraFetcher(Fetcher):
    source = "finra"

    def fetch(self) -> int:
        tickers = {finra_symbol(stock.ticker): stock.ticker for stock in self.config.assets.stocks}
        if not tickers:
            return 0
        latest = self.conn.execute("SELECT MAX(settlement_date) FROM short_interest").fetchone()[0]
        if latest:  # Revisionen der letzten Meldungen mitnehmen
            since = (self.clock() - timedelta(days=60)).date()
        else:
            since = self.history_start(int(self.options.get("history_years", 2))).date()
        since -= timedelta(days=1)  # GREATER ist exklusiv
        rows: list[tuple[Any, ...]] = []
        offset = 0
        while True:
            payload = {
                "limit": PAGE_SIZE,
                "offset": offset,
                "compareFilters": [
                    {
                        "compareType": "GREATER",
                        "fieldName": "settlementDate",
                        "fieldValue": since.isoformat(),
                    }
                ],
                "domainFilters": [{"fieldName": "symbolCode", "values": sorted(tickers)}],
            }
            response = self.http.post_json(
                self.options.get("url", API_URL), payload, {"Accept": "application/json"}
            )
            page = response.json()
            if not isinstance(page, list):
                raise ValueError("Unerwartete FINRA-Antwort (keine Liste)")
            self.save_raw(f"consolidatedShortInterest_offset{offset}", response.content)
            rows.extend(parse_rows(page, tickers))
            if len(page) < PAGE_SIZE:
                break
            offset += PAGE_SIZE

        with transaction(self.conn):
            self.conn.executemany(
                "INSERT OR REPLACE INTO short_interest (ticker, settlement_date, short_interest,"
                " avg_daily_volume, days_to_cover) VALUES (?,?,?,?,?)",
                rows,
            )
        self._check_coverage(tickers.values())
        return len(rows)

    def _check_coverage(self, tickers: Any) -> None:
        limit = (self.clock() - timedelta(days=STALE_AFTER_DAYS)).strftime("%Y-%m-%d")
        for ticker in tickers:
            with self.unit(f"Ticker {ticker}"):
                latest = self.conn.execute(
                    "SELECT MAX(settlement_date) FROM short_interest WHERE ticker = ?", (ticker,)
                ).fetchone()[0]
                if latest is None:
                    raise ValueError("keine Short-Interest-Daten (FINRA-Symbol unbekannt?)")
                if latest < limit:
                    raise ValueError(f"letzte Meldung {latest} (Ticker umbenannt oder delistet?)")
