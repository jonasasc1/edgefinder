"""Datenzugriff der Score-Engine: liest aus SQLite und liefert nur Stand bis zum Stichtag.

Jede Tabelle wird je Schlüssel einmal komplett geladen (Cache) und dann nach Stichtag
zugeschnitten; so bleibt der Rückwärtslauf über Jahre schnell. Look-Ahead-Schutz:

* Kurse: Datum ≤ Stichtag.
* COT: Berichtsdatum ist ein Dienstag, Veröffentlichung Freitag (+ `COT_RELEASE_LAG_DAYS`);
  erst ab dann sichtbar.
* Makro: Beobachtung mit Vintage-Zeilen (ALFRED) → jüngste Vintage ≤ Stichtag, Beobachtungen
  ohne frühere Vintage fehlen. Serien ohne Vintages (Eurostat, EZB, tägliche Marktdaten):
  Beobachtungsdatum + geschätzte Veröffentlichungsverzögerung ≤ Stichtag. Im Live-Lauf
  (Stichtag ≥ heute) ist alles Geladene sichtbar, die Verzögerung entfällt.
* AAII: Umfragedatum (Mittwoch) + 1 Tag. Short Interest: Stichtag der Daten + 11 Tage (FINRA
  veröffentlicht ca. 7 Handelstage später). Fundamentaldaten und Form 4: Einreichungsdatum ≤
  Stichtag. Earnings: Meldedatum ≤ Stichtag.
"""

from __future__ import annotations

import itertools
import sqlite3
import statistics
from bisect import bisect_right
from datetime import UTC, date, datetime, timedelta

from edgefinder.config import Config
from edgefinder.scoring.factors.cot import CotPoint
from edgefinder.scoring.factors.fundamentals import Fact
from edgefinder.scoring.factors.insider import InsiderTrade
from edgefinder.scoring.factors.macro import EconomyData, IndicatorData
from edgefinder.scoring.factors.short_interest import ShortPoint

COT_RELEASE_LAG_DAYS = 3
AAII_RELEASE_LAG_DAYS = 1
SHORT_INTEREST_LAG_DAYS = 11
# Geschätzte Veröffentlichungsverzögerung (Tage ab Beobachtungsdatum = Periodenbeginn) für
# Serien ohne Vintages, nach typischem Abstand der Beobachtungen
PUBLICATION_LAG_DAYS = {"daily": 1, "weekly": 5, "monthly": 50, "quarterly": 135}


def _frequency(dates: list[str]) -> str:
    if len(dates) < 3:
        return "monthly"
    recent = dates[-31:]
    gaps = [
        (date.fromisoformat(b) - date.fromisoformat(a)).days for a, b in itertools.pairwise(recent)
    ]
    median = statistics.median(gaps)
    if median <= 4:
        return "daily"
    if median <= 10:
        return "weekly"
    if median <= 45:
        return "monthly"
    return "quarterly"


def _today() -> date:
    return datetime.now(UTC).date()


class DataStore:
    def __init__(self, conn: sqlite3.Connection, config: Config) -> None:
        self.conn = conn
        self.config = config
        self._cache: dict[tuple, object] = {}

    def _cached(self, key: tuple, loader):
        if key not in self._cache:
            self._cache[key] = loader()
        return self._cache[key]

    # ------------------------------------------------------------------ Kurse
    def prices(self, asset_id: str, as_of: date) -> tuple[list[str], list[float]]:
        def load() -> tuple[list[str], list[float]]:
            rows = self.conn.execute(
                "SELECT date, close FROM prices WHERE asset_id = ? ORDER BY date", (asset_id,)
            ).fetchall()
            return [r[0] for r in rows], [r[1] for r in rows]

        dates, closes = self._cached(("prices", asset_id), load)
        end = bisect_right(dates, as_of.isoformat())
        return dates[:end], closes[:end]

    # ------------------------------------------------------------------ COT
    def cot(self, contract_code: str, as_of: date) -> list[CotPoint]:
        def load() -> list[CotPoint]:
            rows = self.conn.execute(
                "SELECT report_date, noncomm_long - noncomm_short, open_interest FROM cot_reports"
                " WHERE contract_code = ? ORDER BY report_date",
                (contract_code,),
            ).fetchall()
            return [CotPoint(r[0], float(r[1]), r[2]) for r in rows]

        points: list[CotPoint] = self._cached(("cot", contract_code), load)
        limit = (as_of - timedelta(days=COT_RELEASE_LAG_DAYS)).isoformat()
        return [p for p in points if p.report_date <= limit]

    # ------------------------------------------------------------------ Makro
    def _macro_rows(self, source: str, series_id: str):
        def load():
            rows = self.conn.execute(
                "SELECT date, vintage_date, value FROM macro_observations"
                " WHERE source = ? AND series_id = ? ORDER BY date, vintage_date",
                (source, series_id),
            ).fetchall()
            vintages: dict[str, list[tuple[str, float]]] = {}
            current: list[tuple[str, float]] = []
            for d, v, value in rows:
                if v == "":
                    current.append((d, value))
                else:
                    vintages.setdefault(d, []).append((v, value))
            return vintages, current

        return self._cached(("macro", source, series_id), load)

    def macro_series(
        self,
        source: str,
        series_id: str,
        as_of: date,
        lag_days: dict[str, int] | None = None,
        fixed_lag: int | None = None,
    ) -> list[tuple[str, float]]:
        vintages, current = self._macro_rows(source, series_id)
        live = as_of >= _today()
        lags = lag_days or PUBLICATION_LAG_DAYS
        stamp = as_of.isoformat()
        out: list[tuple[str, float]] = []
        if not vintages:
            if live:
                return [row for row in current if row[0] <= stamp]
            lag = fixed_lag or lags[_frequency([d for d, _ in current])]
            cutoff = (as_of - timedelta(days=lag)).isoformat()
            return [row for row in current if row[0] <= cutoff]
        for d, value in current:
            versions = vintages.get(d)
            if versions is None:
                if live and d <= stamp:
                    out.append((d, value))
                continue
            known = [val for v, val in versions if v <= stamp]
            if known:
                out.append((d, known[-1]))
        return out

    def economy(self, code: str, as_of: date) -> EconomyData:
        economy = self.config.economies[code]
        data = EconomyData(code, economy.name)
        for key, ind in economy.indicators.items():
            series = self.macro_series(
                ind.source, ind.series, as_of, fixed_lag=ind.publication_lag_days
            )
            if series:
                data.indicators[key] = IndicatorData(
                    key, ind.label, ind.category, ind.transform, ind.higher_is, series
                )
        return data

    # ------------------------------------------------------------------ Sentiment
    def retail(self, symbol: str, as_of: date) -> list[tuple[str, float]]:
        def load() -> list[tuple[str, float]]:
            rows = self.conn.execute(
                "SELECT observed_at, long_pct FROM retail_sentiment WHERE source = 'myfxbook'"
                " AND symbol = ? ORDER BY observed_at",
                (symbol,),
            ).fetchall()
            return [(r[0], r[1]) for r in rows]

        rows: list[tuple[str, float]] = self._cached(("retail", symbol), load)
        limit = as_of.isoformat() + "T23:59:59"
        return [r for r in rows if r[0] <= limit]

    def aaii(self, as_of: date) -> list[tuple[str, float, float]]:
        def load() -> list[tuple[str, float, float]]:
            rows = self.conn.execute(
                "SELECT week_date, bullish, bearish FROM aaii_sentiment ORDER BY week_date"
            ).fetchall()
            return [(r[0], r[1], r[2]) for r in rows]

        rows: list[tuple[str, float, float]] = self._cached(("aaii",), load)
        limit = (as_of - timedelta(days=AAII_RELEASE_LAG_DAYS)).isoformat()
        return [r for r in rows if r[0] <= limit]

    # ------------------------------------------------------------------ Aktien
    def fundamentals(self, ticker: str, as_of: date) -> dict[str, list[Fact]]:
        def load() -> dict[str, list[Fact]]:
            rows = self.conn.execute(
                "SELECT concept, period_start, period_end, value, filed FROM fundamentals"
                " WHERE ticker = ? AND unit IN ('USD', 'USD/shares') ORDER BY filed",
                (ticker,),
            ).fetchall()
            facts: dict[str, list[Fact]] = {}
            for concept, start, end, value, filed in rows:
                facts.setdefault(concept, []).append(Fact(start, end, value, filed))
            return facts

        facts: dict[str, list[Fact]] = self._cached(("fundamentals", ticker), load)
        limit = as_of.isoformat()
        return {c: [f for f in fs if f.filed <= limit] for c, fs in facts.items()}

    def earnings(self, ticker: str, as_of: date) -> list[tuple[str, float | None]]:
        def load() -> list[tuple[str, float | None]]:
            rows = self.conn.execute(
                "SELECT earnings_date, surprise_pct FROM earnings WHERE ticker = ?"
                " AND eps_actual IS NOT NULL ORDER BY earnings_date",
                (ticker,),
            ).fetchall()
            return [(r[0], r[1]) for r in rows]

        rows: list[tuple[str, float | None]] = self._cached(("earnings", ticker), load)
        return [r for r in rows if r[0] <= as_of.isoformat()]

    def short_interest(self, ticker: str, as_of: date) -> list[ShortPoint]:
        def load() -> list[ShortPoint]:
            rows = self.conn.execute(
                "SELECT settlement_date, short_interest, days_to_cover FROM short_interest"
                " WHERE ticker = ? ORDER BY settlement_date",
                (ticker,),
            ).fetchall()
            return [ShortPoint(r[0], r[1], r[2]) for r in rows]

        points: list[ShortPoint] = self._cached(("short", ticker), load)
        limit = (as_of - timedelta(days=SHORT_INTEREST_LAG_DAYS)).isoformat()
        return [p for p in points if p.settlement_date <= limit]

    def insider(self, ticker: str, as_of: date) -> tuple[list[InsiderTrade], bool]:
        def load():
            trades = self.conn.execute(
                "SELECT transaction_date, transaction_code, shares, price, filed_at"
                " FROM insider_trades WHERE ticker = ? ORDER BY transaction_date",
                (ticker,),
            ).fetchall()
            seen = self.conn.execute(
                "SELECT MIN(filed_at) FROM sec_filings_seen WHERE ticker = ?", (ticker,)
            ).fetchone()[0]
            return trades, seen

        rows, first_seen = self._cached(("insider", ticker), load)
        limit = as_of.isoformat()
        trades = [InsiderTrade(r[0], r[1], r[2], r[3]) for r in rows if r[4][:10] <= limit]
        return trades, first_seen is not None and first_seen[:10] <= limit
