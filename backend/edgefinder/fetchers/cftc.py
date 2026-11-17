"""CFTC Commitments of Traders (Legacy, Futures Only) über die Socrata-API."""

from __future__ import annotations

from datetime import timedelta
from typing import Any

from edgefinder.db import transaction
from edgefinder.fetchers.base import Fetcher

PAGE_SIZE = 10_000
# Meldet ein konfigurierter Kontrakt so lange nichts mehr, ist er vermutlich eingestellt.
STALE_AFTER_DAYS = 45

SELECT_FIELDS = (
    "cftc_contract_market_code",
    "market_and_exchange_names",
    "report_date_as_yyyy_mm_dd",
    "open_interest_all",
    "noncomm_positions_long_all",
    "noncomm_positions_short_all",
    "noncomm_postions_spread_all",  # sic: Tippfehler im Dataset
    "comm_positions_long_all",
    "comm_positions_short_all",
    "nonrept_positions_long_all",
    "nonrept_positions_short_all",
)


def _int(value: Any) -> int | None:
    if value in (None, ""):
        return None
    return int(float(value))


def parse_rows(records: list[dict[str, Any]]) -> list[tuple[Any, ...]]:
    """Socrata-Datensätze → Zeilen für `cot_reports`. Ohne Non-Commercial-Werte: übersprungen."""
    rows = []
    for record in records:
        long, short = (
            _int(record.get("noncomm_positions_long_all")),
            _int(record.get("noncomm_positions_short_all")),
        )
        if long is None or short is None:
            continue
        rows.append(
            (
                record["cftc_contract_market_code"].strip(),
                record["report_date_as_yyyy_mm_dd"][:10],
                record.get("market_and_exchange_names"),
                _int(record.get("open_interest_all")),
                long,
                short,
                _int(record.get("noncomm_postions_spread_all")),
                _int(record.get("comm_positions_long_all")),
                _int(record.get("comm_positions_short_all")),
                _int(record.get("nonrept_positions_long_all")),
                _int(record.get("nonrept_positions_short_all")),
            )
        )
    return rows


class CftcFetcher(Fetcher):
    source = "cftc"

    def contract_codes(self) -> list[str]:
        codes = {c.cftc_code for c in self.config.currencies.values() if c.cftc_code}
        codes |= {
            asset.cftc_code
            for asset in (*self.config.assets.indices, *self.config.assets.commodities)
            if asset.cftc_code
        }
        return sorted(codes)

    def _query(self, codes: list[str], since: str, offset: int) -> dict[str, str]:
        code_list = ",".join(f"'{code}'" for code in codes)
        return {
            "$select": ",".join(SELECT_FIELDS),
            "$where": f"cftc_contract_market_code in({code_list})"
            f" AND report_date_as_yyyy_mm_dd >= '{since}'",
            "$order": "report_date_as_yyyy_mm_dd,cftc_contract_market_code",
            "$limit": str(PAGE_SIZE),
            "$offset": str(offset),
        }

    def fetch(self) -> int:
        codes = self.contract_codes()
        since = self.history_start(int(self.options["history_years"])).strftime("%Y-%m-%d")
        url = f"{self.options['base_url']}/{self.options['dataset']}.json"
        headers = {}
        if self.secrets.cftc_app_token is not None:
            headers["X-App-Token"] = self.secrets.cftc_app_token.get_secret_value()

        records: list[dict[str, Any]] = []
        offset = 0
        while True:
            response = self.http.get(url, self._query(codes, since, offset), headers)
            page = response.json()
            if not isinstance(page, list):
                raise ValueError("Unerwartete Socrata-Antwort (keine Liste)")
            self.save_raw(f"{self.options['dataset']}_offset{offset}", response.content)
            records.extend(page)
            if len(page) < PAGE_SIZE:
                break
            offset += PAGE_SIZE

        rows = parse_rows(records)
        with transaction(self.conn):
            self.conn.executemany(
                "INSERT OR REPLACE INTO cot_reports (contract_code, report_date, market_name,"
                " open_interest, noncomm_long, noncomm_short, noncomm_spread, comm_long,"
                " comm_short, nonrept_long, nonrept_short) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                rows,
            )
        self._check_coverage(codes, rows)
        return len(rows)

    def _check_coverage(self, codes: list[str], rows: list[tuple[Any, ...]]) -> None:
        latest: dict[str, str] = {}
        for row in rows:
            latest[row[0]] = max(latest.get(row[0], ""), row[1])
        limit = (self.clock() - timedelta(days=STALE_AFTER_DAYS)).strftime("%Y-%m-%d")
        for code in codes:
            with self.unit(f"Kontrakt {code}"):
                if code not in latest:
                    raise ValueError("keine Daten im Abrufzeitraum (Code falsch oder eingestellt?)")
                if latest[code] < limit:
                    raise ValueError(f"letzte Meldung {latest[code]} (Kontrakt eingestellt?)")
