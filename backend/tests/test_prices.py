from __future__ import annotations

from datetime import date

import pandas as pd
import pytest
from support import FIXTURES

from edgefinder.fetchers.prices import (
    PricesFetcher,
    bars_from_frame,
    earnings_from_frame,
)


def _frame(name: str, tz: str) -> pd.DataFrame:
    """Aufgezeichnete yfinance-Tabelle (CSV) wieder mit Zeitzone des Börsenplatzes laden."""
    frame = pd.read_csv(FIXTURES / name, index_col=0)
    frame.index = pd.to_datetime(frame.index, utc=True).tz_convert(tz)
    return frame


class FakeProvider:
    def __init__(self, fail: set[str] | None = None) -> None:
        self.fail = fail or set()
        self.history_calls: list[tuple[str, date]] = []
        self.earnings_calls: list[str] = []
        self.earnings_frame = _frame("yf_aapl_earnings.csv", "America/New_York")

    def history(self, symbol: str, start: date) -> pd.DataFrame:
        self.history_calls.append((symbol, start))
        if symbol in self.fail:
            raise RuntimeError("Yahoo: Too Many Requests")
        if symbol == "AAPL":
            return _frame("yf_aapl_history.csv", "America/New_York")
        return _frame("yf_eurusd_history.csv", "Europe/London")

    def earnings(self, symbol: str, limit: int) -> pd.DataFrame | None:
        self.earnings_calls.append(symbol)
        return self.earnings_frame


@pytest.fixture
def small_config(make_config, config_data):
    forex = [a for a in config_data["assets"]["forex"] if a["id"] == "EURUSD"]
    stocks = [a for a in config_data["assets"]["stocks"] if a["id"] == "AAPL"]
    return make_config(assets={"forex": forex, "stocks": stocks})


def _fetcher(config, secrets, db, clock, provider) -> PricesFetcher:
    return PricesFetcher(config, secrets, db, sleep=clock.sleep, clock=clock, provider=provider)


def test_bars_from_frame_uses_exchange_day_and_floats() -> None:
    rows = bars_from_frame(_frame("yf_eurusd_history.csv", "Europe/London"))
    assert rows[0][0] == "2026-11-09"
    assert rows[-1][0] == "2026-11-17"
    _, open_, high, low, close, adj_close, volume = rows[0]
    assert (open_, high, low, close, adj_close, volume) == pytest.approx(
        (1.1148520708, 1.1205737591, 1.1147402525, 1.1147277355, 1.1147277355, 0.0)
    )


def test_bars_from_frame_drops_rows_without_close() -> None:
    frame = _frame("yf_eurusd_history.csv", "Europe/London")
    frame.iloc[2, frame.columns.get_loc("Close")] = float("nan")
    rows = bars_from_frame(frame)
    assert len(rows) == len(frame) - 1
    assert "2026-11-11" not in {row[0] for row in rows}


def test_earnings_from_frame_keeps_estimate_vs_actual_and_upcoming_date() -> None:
    rows = earnings_from_frame(_frame("yf_aapl_earnings.csv", "America/New_York"))
    by_date = {row[0]: row for row in rows}
    assert by_date["2027-01-28"] == ("2027-01-28", 2.91, None, None)  # noch nicht gemeldet
    assert by_date["2026-11-02"] == ("2026-11-02", 1.98, 2.1, 5.8)


def test_earnings_surprise_is_computed_when_missing() -> None:
    frame = pd.DataFrame(
        {"EPS Estimate": [2.0], "Reported EPS": [2.2], "Surprise(%)": [float("nan")]},
        index=pd.DatetimeIndex(["2026-11-02 16:00"], tz="America/New_York"),
    )
    assert earnings_from_frame(frame)[0][3] == pytest.approx(10.0)


def test_fetch_stores_prices_and_earnings(small_config, secrets, db, clock) -> None:
    provider = FakeProvider()
    result = _fetcher(small_config, secrets, db, clock, provider).run()

    assert result.status == "success", result.errors
    assert [call[0] for call in provider.history_calls] == ["EURUSD=X", "AAPL"]
    assert provider.earnings_calls == ["AAPL"]  # nur Aktien
    assert db.execute("SELECT COUNT(*) FROM prices WHERE asset_id='EURUSD'").fetchone()[0] == 7
    assert db.execute("SELECT COUNT(*) FROM prices WHERE asset_id='AAPL'").fetchone()[0] == 7
    assert db.execute("SELECT COUNT(*) FROM earnings WHERE ticker='AAPL'").fetchone()[0] == 6
    assert result.requests == 3  # 2x Kurse + 1x Earnings
    assert db.execute("SELECT COUNT(*) FROM raw_files WHERE source='prices'").fetchone()[0] == 3
    first_start = provider.history_calls[0][1]
    assert first_start == date(2011, 11, 17)  # history_years = 15


def test_second_run_loads_incrementally_without_duplicates(
    small_config, secrets, db, clock
) -> None:
    _fetcher(small_config, secrets, db, clock, FakeProvider()).run()
    provider = FakeProvider()
    _fetcher(small_config, secrets, db, clock, provider).run()

    assert provider.history_calls[0][1] == date(2026, 11, 7)  # letzter Kurs 17.11. minus 10 Tage
    assert db.execute("SELECT COUNT(*) FROM prices WHERE asset_id='EURUSD'").fetchone()[0] == 7


def test_postponed_earnings_date_replaces_old_upcoming_row(
    small_config, secrets, db, clock
) -> None:
    _fetcher(small_config, secrets, db, clock, FakeProvider()).run()
    provider = FakeProvider()
    provider.earnings_frame = provider.earnings_frame.rename(
        index={pd.Timestamp("2027-01-28 16:00", tz="America/New_York"): pd.Timestamp(
            "2027-02-04 16:00", tz="America/New_York")}
    )  # fmt: skip
    _fetcher(small_config, secrets, db, clock, provider).run()

    dates = [
        r[0] for r in db.execute("SELECT earnings_date FROM earnings WHERE eps_actual IS NULL")
    ]
    assert dates == ["2027-02-04"]


def test_failing_symbol_is_partial_and_does_not_block_others(
    small_config, secrets, db, clock
) -> None:
    provider = FakeProvider(fail={"EURUSD=X"})
    result = _fetcher(small_config, secrets, db, clock, provider).run()

    assert result.status == "partial"
    assert "Kurse EURUSD (EURUSD=X)" in result.errors[0]
    assert db.execute("SELECT COUNT(*) FROM prices WHERE asset_id='AAPL'").fetchone()[0] == 7
    assert sum(1 for call in provider.history_calls if call[0] == "EURUSD=X") == 4  # Retries
    assert result.requests == 4 + 1 + 1


def test_empty_frame_is_an_error(small_config, secrets, db, clock) -> None:
    class Empty(FakeProvider):
        def history(self, symbol: str, start: date) -> pd.DataFrame:
            return pd.DataFrame()

        def earnings(self, symbol: str, limit: int) -> pd.DataFrame | None:
            return None

    result = _fetcher(small_config, secrets, db, clock, Empty()).run()
    assert result.status == "error"
    assert any("keine Kursdaten" in error for error in result.errors)
    assert any("keine Earnings-Daten" in error for error in result.errors)


def test_all_configured_assets_have_a_price_symbol(config) -> None:
    from edgefinder.config import StockAsset

    for asset in config.assets.all():
        symbol = asset.price_symbol if isinstance(asset, StockAsset) else asset.yfinance
        assert symbol
