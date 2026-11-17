-- 0002: SEC EDGAR – CIK-Zuordnung und Merkliste bereits ausgewerteter Form-4-Einreichungen.
-- 0001 deckt fundamentals, insider_trades, short_interest und aaii_sentiment schon ab.

-- Ticker (wie in config.yaml, z. B. BRK-B) → CIK aus company_tickers.json der SEC
CREATE TABLE sec_companies (
    ticker      TEXT PRIMARY KEY,
    cik         INTEGER NOT NULL,
    title       TEXT,
    updated_at  TEXT NOT NULL
) STRICT, WITHOUT ROWID;

-- Jede ausgewertete Form-4-Einreichung (auch ohne Marktkäufe/-verkäufe), damit sie nicht
-- erneut geladen wird. `trades` = Anzahl gespeicherter P/S-Transaktionen.
CREATE TABLE sec_filings_seen (
    accession   TEXT PRIMARY KEY,
    ticker      TEXT NOT NULL,
    form        TEXT NOT NULL,
    filed_at    TEXT NOT NULL,
    trades      INTEGER NOT NULL,
    fetched_at  TEXT NOT NULL
) STRICT, WITHOUT ROWID;
CREATE INDEX idx_sec_filings_seen_ticker ON sec_filings_seen (ticker, filed_at DESC);
