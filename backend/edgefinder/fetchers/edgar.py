"""SEC EDGAR: Fundamentaldaten (companyfacts, XBRL) und Insider-Trades (Form 4).

- Die SEC verlangt einen User-Agent mit Kontakt (`CONTACT_EMAIL` aus der .env); ohne ihn läuft
  der Fetcher nicht. Limit der SEC: 10 Requests/s, konfiguriert sind deutlich weniger.
- companyfacts sind groß (mehrere MB je Ticker): je Ticker nur alle `fundamentals_refresh_days`
  neu laden, Rohdaten gzip-komprimiert ablegen.
- Form 4: aus `submissions` die Einreichungen der letzten `insider_lookback_days` Tage, je neue
  Einreichung das XML laden und nur offene Marktkäufe/-verkäufe (Code P/S, nicht abgeleitet)
  speichern. Jede ausgewertete Einreichung steht in `sec_filings_seen`.
"""

from __future__ import annotations

import gzip
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
from typing import Any

from edgefinder.db import transaction
from edgefinder.fetchers.base import Fetcher, FetchError, iso

TICKERS_URL = "https://www.sec.gov/files/company_tickers.json"
ARCHIVES_URL = "https://www.sec.gov/Archives/edgar/data"
TICKERS_STATE = "tickers"
OPEN_MARKET_CODES = frozenset({"P", "S"})


def _text(node: ET.Element | None, path: str) -> str | None:
    found = node.find(path) if node is not None else None
    if found is None or found.text is None:
        return None
    return found.text.strip() or None


def parse_company_tickers(data: dict[str, Any]) -> dict[str, tuple[int, str]]:
    """company_tickers.json → {TICKER: (CIK, Name)}; bei doppelten Tickern gewinnt der erste."""
    result: dict[str, tuple[int, str]] = {}
    for entry in data.values():
        result.setdefault(str(entry["ticker"]).upper(), (int(entry["cik_str"]), entry["title"]))
    return result


def parse_facts(
    data: dict[str, Any],
    ticker: str,
    concepts: list[str],
    forms: set[str],
    filed_since: str,
) -> list[tuple[Any, ...]]:
    """companyfacts → Zeilen für `fundamentals` (`concepts` als „taxonomie:Name“)."""
    rows = []
    facts = data.get("facts", {})
    for concept in concepts:
        taxonomy, _, name = concept.partition(":")
        for unit, entries in facts.get(taxonomy, {}).get(name, {}).get("units", {}).items():
            for entry in entries:
                if entry.get("form") not in forms or entry.get("filed", "") < filed_since:
                    continue
                if entry.get("val") is None or not entry.get("end"):
                    continue
                rows.append(
                    (
                        ticker,
                        concept,
                        unit,
                        entry.get("start") or "",
                        entry["end"],
                        entry.get("fy"),
                        entry.get("fp"),
                        entry["form"],
                        entry["filed"],
                        float(entry["val"]),
                    )
                )
    return rows


def recent_form4(submissions: dict[str, Any], since: str) -> list[tuple[str, str, str]]:
    """submissions → [(Accession, Datum, Dateiname des XML)] für Form 4 seit `since`."""
    recent = submissions.get("filings", {}).get("recent", {})
    found = []
    for accession, filed, form, document in zip(
        recent.get("accessionNumber", []),
        recent.get("filingDate", []),
        recent.get("form", []),
        recent.get("primaryDocument", []),
        strict=False,
    ):
        if form != "4" or filed < since:
            continue
        # primaryDocument zeigt auf die HTML-Darstellung („xslF345X05/datei.xml“);
        # das rohe XML liegt unter dem reinen Dateinamen.
        found.append((accession, filed, document.rsplit("/", 1)[-1]))
    return found


def parse_form4(xml: bytes, accession: str, ticker: str, filed: str) -> list[tuple[Any, ...]]:
    """Form-4-XML → Zeilen für `insider_trades` (nur nicht abgeleitete Käufe/Verkäufe P/S)."""
    root = ET.fromstring(xml)  # noqa: S314 – SEC-Dokumente, kein DTD-/Entity-Gebrauch erwartet
    owners = root.findall("reportingOwner")
    name = "; ".join(filter(None, (_text(o, "reportingOwnerId/rptOwnerName") for o in owners)))
    first = owners[0] if owners else None
    title = _text(first, "reportingOwnerRelationship/officerTitle")
    if title is None and first is not None:
        if _text(first, "reportingOwnerRelationship/isDirector") in ("1", "true"):
            title = "Director"
        elif _text(first, "reportingOwnerRelationship/isTenPercentOwner") in ("1", "true"):
            title = "10% Owner"
    rows = []
    for line_no, tx in enumerate(root.findall("nonDerivativeTable/nonDerivativeTransaction"), 1):
        code = _text(tx, "transactionCoding/transactionCode")
        shares = _text(tx, "transactionAmounts/transactionShares/value")
        direction = _text(tx, "transactionAmounts/transactionAcquiredDisposedCode/value")
        day = _text(tx, "transactionDate/value")
        if (
            code not in OPEN_MARKET_CODES
            or shares is None
            or direction not in ("A", "D")
            or not day
        ):
            continue
        price = _text(tx, "transactionAmounts/transactionPricePerShare/value")
        rows.append(
            (
                accession,
                line_no,
                ticker,
                name or "unbekannt",
                title,
                day[:10],
                code,
                1 if direction == "A" else 0,
                float(shares),
                float(price) if price else None,
                filed,
            )
        )
    return rows


class EdgarFetcher(Fetcher):
    source = "edgar"

    def _headers(self) -> dict[str, str]:
        if self.secrets.contact_email is None:
            raise FetchError("edgar: CONTACT_EMAIL fehlt in der .env (User-Agent-Pflicht der SEC)")
        contact = self.secrets.contact_email.get_secret_value()
        return {"User-Agent": f"edgefinder/0.1 (private research; {contact})"}

    def _get(self, url: str) -> Any:
        return self.http.get(url, headers=self._headers())

    def fetch(self) -> int:
        if not self.secrets.contact_email:
            raise FetchError("edgar: CONTACT_EMAIL fehlt in der .env (User-Agent-Pflicht der SEC)")
        stocks = self.config.assets.stocks
        self._update_cik_map([stock.ticker for stock in stocks])
        total = 0
        for stock in stocks:
            cik = self._cik(stock.ticker)
            with self.unit(f"{stock.ticker} Fundamentaldaten"):
                if cik is None:
                    raise ValueError("kein CIK (Ticker nicht in company_tickers.json)")
                total += self._fundamentals(stock.ticker, cik)
            with self.unit(f"{stock.ticker} Form 4"):
                if cik is not None:
                    total += self._insider(stock.ticker, cik)
        return total

    # ------------------------------------------------------------ CIK
    def _cik(self, ticker: str) -> int | None:
        row = self.conn.execute(
            "SELECT cik FROM sec_companies WHERE ticker = ?", (ticker,)
        ).fetchone()
        return int(row[0]) if row else None

    def _update_cik_map(self, tickers: list[str]) -> None:
        """company_tickers.json laden, wenn älter als die Frist oder ein Ticker noch fehlt."""
        refresh = timedelta(days=float(self.options.get("cik_refresh_days", 7)))
        state = self.get_state(TICKERS_STATE)
        known = {self._cik(t) is not None for t in tickers} == {True}
        if state and known and self.clock() - datetime.fromisoformat(state[1]) < refresh:
            return
        response = self._get(self.options.get("tickers_url", TICKERS_URL))
        mapping = parse_company_tickers(response.json())
        self.save_raw("company_tickers", response.content)
        now = iso(self.clock())
        with transaction(self.conn):
            for ticker in tickers:
                if ticker.upper() in mapping:
                    cik, title = mapping[ticker.upper()]
                    self.conn.execute(
                        "INSERT INTO sec_companies (ticker, cik, title, updated_at)"
                        " VALUES (?,?,?,?) ON CONFLICT (ticker) DO UPDATE SET cik = excluded.cik,"
                        " title = excluded.title, updated_at = excluded.updated_at",
                        (ticker, cik, title, now),
                    )
        self.set_state(TICKERS_STATE, now)

    # ------------------------------------------------------------ Fundamentaldaten
    def _fundamentals(self, ticker: str, cik: int) -> int:
        key = f"facts:{ticker}"
        refresh = timedelta(days=float(self.options.get("fundamentals_refresh_days", 3)))
        state = self.get_state(key)
        if state and self.clock() - datetime.fromisoformat(state[1]) < refresh:
            return 0
        response = self._get(f"{self.options['base_url']}/api/xbrl/companyfacts/CIK{cik:010d}.json")
        data = response.json()
        self.save_raw(f"companyfacts_{ticker}", gzip.compress(response.content), ".json.gz")
        since = self.history_start(int(self.options.get("fundamentals_history_years", 10)))
        rows = parse_facts(
            data,
            ticker,
            list(self.options["fundamentals_concepts"]),
            set(self.options.get("fundamentals_forms", ["10-K", "10-Q"])),
            since.strftime("%Y-%m-%d"),
        )
        if not rows:
            raise ValueError("companyfacts enthält keines der konfigurierten Konzepte")
        with transaction(self.conn):
            self.conn.executemany(
                "INSERT OR REPLACE INTO fundamentals (ticker, concept, unit, period_start,"
                " period_end, fiscal_year, fiscal_period, form, filed, value)"
                " VALUES (?,?,?,?,?,?,?,?,?,?)",
                rows,
            )
        self.set_state(key, iso(self.clock()))
        return len(rows)

    # ------------------------------------------------------------ Insider (Form 4)
    def _insider(self, ticker: str, cik: int) -> int:
        lookback = int(self.options.get("insider_lookback_days", 365))
        since = (self.clock() - timedelta(days=lookback)).strftime("%Y-%m-%d")
        response = self._get(f"{self.options['base_url']}/submissions/CIK{cik:010d}.json")
        self.save_raw(f"submissions_{ticker}", gzip.compress(response.content), ".json.gz")
        stored = 0
        for accession, filed, document in recent_form4(response.json(), since):
            if self.conn.execute(
                "SELECT 1 FROM sec_filings_seen WHERE accession = ?", (accession,)
            ).fetchone():
                continue
            with self.unit(f"{ticker} Form 4 {accession}"):
                stored += self._form4(ticker, cik, accession, filed, document)
        return stored

    def _form4(self, ticker: str, cik: int, accession: str, filed: str, document: str) -> int:
        archives = self.options.get("archives_url", ARCHIVES_URL)
        url = f"{archives}/{cik}/{accession.replace('-', '')}/{document}"
        response = self._get(url)
        self.save_raw(f"form4_{ticker}_{accession}", response.content, ".xml")
        rows = parse_form4(response.content, accession, ticker, filed)
        with transaction(self.conn):
            self.conn.executemany(
                "INSERT OR REPLACE INTO insider_trades (accession, line_no, ticker, owner_name,"
                " owner_title, transaction_date, transaction_code, acquired, shares, price,"
                " filed_at) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                rows,
            )
            self.conn.execute(
                "INSERT OR REPLACE INTO sec_filings_seen (accession, ticker, form, filed_at,"
                " trades, fetched_at) VALUES (?,?,?,?,?,?)",
                (accession, ticker, "4", filed, len(rows), iso(self.clock())),
            )
        return len(rows)
