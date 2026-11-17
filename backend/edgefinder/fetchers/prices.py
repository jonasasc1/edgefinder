"""Kurse (Tagesdaten) für alle Assets und Earnings (Schätzung vs. Ist) der Aktien via yfinance.

yfinance ist eine inoffizielle Yahoo-Schnittstelle und kann ohne Vorwarnung ausfallen oder
Daten ändern. Jeder Abruf läuft deshalb mit Retry und Mindestabstand; ein fehlendes Symbol
macht den Lauf nur „partial“.
"""

from __future__ import annotations

import math
from collections.abc import Callable
from datetime import date, timedelta
from typing import TYPE_CHECKING, Protocol

from edgefinder.config import StockAsset
from edgefinder.db import transaction
from edgefinder.fetchers.base import Fetcher, call_with_retry

if TYPE_CHECKING:
    import pandas as pd

OVERLAP_DAYS = 10  # beim Nachladen etwas zurückgehen, um Korrekturen zu übernehmen
EARNINGS_LIMIT = 12  # Quartale (inkl. des nächsten, noch nicht gemeldeten Termins)


class PriceProvider(Protocol):
    def history(self, symbol: str, start: date) -> pd.DataFrame: ...

    def earnings(self, symbol: str, limit: int) -> pd.DataFrame | None: ...


class YFinanceProvider:
    def history(self, symbol: str, start: date) -> pd.DataFrame:
        import yfinance

        return yfinance.Ticker(symbol).history(
            start=start.isoformat(), auto_adjust=False, actions=False
        )

    def earnings(self, symbol: str, limit: int) -> pd.DataFrame | None:
        import yfinance

        return yfinance.Ticker(symbol).get_earnings_dates(limit=limit)


def _number(value: object) -> float | None:
    if value is None:
        return None
    number = float(value)  # type: ignore[arg-type]
    return None if math.isnan(number) else number


def bars_from_frame(frame: pd.DataFrame) -> list[tuple[str, ...]]:
    """yfinance-History → (date, open, high, low, close, adj_close, volume); ohne Close entfällt."""
    rows = []
    for stamp, record in frame.iterrows():
        close = _number(record.get("Close"))
        if close is None:
            continue
        rows.append(
            (
                stamp.strftime("%Y-%m-%d"),  # Handelstag in der Zeitzone der Börse
                _number(record.get("Open")),
                _number(record.get("High")),
                _number(record.get("Low")),
                close,
                _number(record.get("Adj Close")),
                _number(record.get("Volume")),
            )
        )
    return rows


def earnings_from_frame(
    frame: pd.DataFrame,
) -> list[tuple[str, float | None, float | None, float | None]]:
    """yfinance-Earnings → (date, eps_estimate, eps_actual, surprise_pct)."""
    rows = []
    for stamp, record in frame.iterrows():
        estimate = _number(record.get("EPS Estimate"))
        actual = _number(record.get("Reported EPS"))
        surprise = _number(record.get("Surprise(%)"))
        if surprise is None and estimate and actual is not None:
            surprise = (actual - estimate) / abs(estimate) * 100
        rows.append((stamp.strftime("%Y-%m-%d"), estimate, actual, surprise))
    return rows


class PricesFetcher(Fetcher):
    source = "prices"

    def __init__(self, *args, provider: PriceProvider | None = None, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.provider: PriceProvider = provider or YFinanceProvider()

    def _count_request(self) -> None:
        self.extra_requests += 1

    def _call[T](self, func: Callable[[], T]) -> T:
        return call_with_retry(
            self.source,
            func,
            self.limiter,
            self.retry,
            sleep=self.sleep,
            on_request=self._count_request,
        )

    def _start_for(self, asset_id: str) -> date:
        row = self.conn.execute(
            "SELECT MAX(date) FROM prices WHERE asset_id = ?", (asset_id,)
        ).fetchone()
        if row[0]:
            return date.fromisoformat(row[0]) - timedelta(days=OVERLAP_DAYS)
        return self.history_start().date()

    def fetch(self) -> int:
        total = 0
        for asset in self.config.assets.all():
            symbol = asset.price_symbol if isinstance(asset, StockAsset) else asset.yfinance
            with self.unit(f"Kurse {asset.id} ({symbol})"):
                total += self._fetch_prices(asset.id, symbol)
            if isinstance(asset, StockAsset):
                with self.unit(f"Earnings {asset.id} ({symbol})"):
                    total += self._fetch_earnings(asset.ticker, symbol)
        return total

    def _fetch_prices(self, asset_id: str, symbol: str) -> int:
        start = self._start_for(asset_id)
        frame = self._call(lambda: self.provider.history(symbol, start))
        if frame is None or frame.empty:
            raise ValueError("keine Kursdaten geliefert")
        self.save_raw(f"{asset_id}_prices", frame.to_csv().encode(), ".csv")
        rows = bars_from_frame(frame)
        with transaction(self.conn):
            self.conn.executemany(
                "INSERT OR REPLACE INTO prices (asset_id, date, open, high, low, close,"
                " adj_close, volume) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                [(asset_id, *row) for row in rows],
            )
        return len(rows)

    def _fetch_earnings(self, ticker: str, symbol: str) -> int:
        frame = self._call(lambda: self.provider.earnings(symbol, EARNINGS_LIMIT))
        if frame is None or frame.empty:
            raise ValueError("keine Earnings-Daten geliefert")
        self.save_raw(f"{ticker}_earnings", frame.to_csv().encode(), ".csv")
        rows = earnings_from_frame(frame)
        with transaction(self.conn):
            # Noch nicht gemeldete Termine werden von Yahoo gelegentlich verschoben.
            self.conn.execute(
                "DELETE FROM earnings WHERE ticker = ? AND eps_actual IS NULL", (ticker,)
            )
            self.conn.executemany(
                "INSERT OR REPLACE INTO earnings (ticker, earnings_date, eps_estimate,"
                " eps_actual, surprise_pct) VALUES (?, ?, ?, ?, ?)",
                [(ticker, *row) for row in rows],
            )
        return len(rows)
