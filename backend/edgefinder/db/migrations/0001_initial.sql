-- 0001: Grundschema
-- Konventionen: Zeitpunkte als UTC-ISO-8601-Text, Tagesdaten als YYYY-MM-DD.
-- asset_id verweist auf die IDs aus config.yaml (bewusst ohne Fremdschlüssel, damit
-- Historie erhalten bleibt, wenn ein Asset aus der Konfiguration entfernt wird).

-- ---------------------------------------------------------------- Betrieb
CREATE TABLE fetch_runs (
    id            INTEGER PRIMARY KEY,
    source        TEXT    NOT NULL,
    started_at    TEXT    NOT NULL,
    finished_at   TEXT,
    status        TEXT    NOT NULL CHECK (status IN ('running', 'success', 'partial', 'error')),
    items         INTEGER NOT NULL DEFAULT 0,
    requests      INTEGER NOT NULL DEFAULT 0,
    error         TEXT
) STRICT;
CREATE INDEX idx_fetch_runs_source ON fetch_runs (source, started_at DESC);

-- Index der auf Platte abgelegten Rohantworten (storage.raw_dir)
CREATE TABLE raw_files (
    id          INTEGER PRIMARY KEY,
    run_id      INTEGER REFERENCES fetch_runs (id) ON DELETE SET NULL,
    source      TEXT    NOT NULL,
    key         TEXT    NOT NULL,
    path        TEXT    NOT NULL,
    sha256      TEXT    NOT NULL,
    bytes       INTEGER NOT NULL,
    fetched_at  TEXT    NOT NULL
) STRICT;
CREATE INDEX idx_raw_files_source ON raw_files (source, key, fetched_at DESC);

-- Jeder ausgehende Request; Grundlage für Tageslimits (z. B. Myfxbook 100/24 h)
CREATE TABLE request_log (
    id            INTEGER PRIMARY KEY,
    source        TEXT NOT NULL,
    requested_at  TEXT NOT NULL
) STRICT;
CREATE INDEX idx_request_log_source ON request_log (source, requested_at);

-- Kleiner Zustandsspeicher je Quelle (z. B. Session, letzter Abrufstand)
CREATE TABLE source_state (
    source      TEXT NOT NULL,
    key         TEXT NOT NULL,
    value       TEXT NOT NULL,
    updated_at  TEXT NOT NULL,
    PRIMARY KEY (source, key)
) STRICT, WITHOUT ROWID;

-- ---------------------------------------------------------------- Marktdaten
CREATE TABLE prices (
    asset_id   TEXT NOT NULL,
    date       TEXT NOT NULL,
    open       REAL,
    high       REAL,
    low        REAL,
    close      REAL NOT NULL,
    adj_close  REAL,
    volume     REAL,
    PRIMARY KEY (asset_id, date)
) STRICT, WITHOUT ROWID;

-- CFTC Commitments of Traders, Legacy-Report (Futures Only)
CREATE TABLE cot_reports (
    contract_code    TEXT    NOT NULL,
    report_date      TEXT    NOT NULL,
    market_name      TEXT,
    open_interest    INTEGER,
    noncomm_long     INTEGER NOT NULL,
    noncomm_short    INTEGER NOT NULL,
    noncomm_spread   INTEGER,
    comm_long        INTEGER,
    comm_short       INTEGER,
    nonrept_long     INTEGER,
    nonrept_short    INTEGER,
    PRIMARY KEY (contract_code, report_date)
) STRICT, WITHOUT ROWID;

-- Makro-Zeitreihen (FRED, Eurostat, ECB). vintage_date = Datum, an dem der Wert so
-- veröffentlicht war ('' = aktueller, ggf. revidierter Stand); erlaubt Backtests ohne
-- Vorgriff auf spätere Revisionen.
CREATE TABLE macro_observations (
    source        TEXT NOT NULL,
    series_id     TEXT NOT NULL,
    date          TEXT NOT NULL,
    vintage_date  TEXT NOT NULL DEFAULT '',
    value         REAL NOT NULL,
    PRIMARY KEY (source, series_id, date, vintage_date)
) STRICT, WITHOUT ROWID;

-- ---------------------------------------------------------------- Sentiment
CREATE TABLE retail_sentiment (
    source           TEXT NOT NULL,
    symbol           TEXT NOT NULL,
    observed_at      TEXT NOT NULL,
    long_pct         REAL NOT NULL,
    short_pct        REAL NOT NULL,
    long_volume      REAL,
    short_volume     REAL,
    long_positions   INTEGER,
    short_positions  INTEGER,
    avg_long_price   REAL,
    avg_short_price  REAL,
    PRIMARY KEY (source, symbol, observed_at)
) STRICT, WITHOUT ROWID;

CREATE TABLE aaii_sentiment (
    week_date   TEXT PRIMARY KEY,
    bullish     REAL NOT NULL,
    neutral     REAL NOT NULL,
    bearish     REAL NOT NULL,
    fetched_at  TEXT NOT NULL
) STRICT, WITHOUT ROWID;

-- ---------------------------------------------------------------- Aktien
-- SEC companyfacts (XBRL), ein Wert je Konzept/Periode/Einreichung
CREATE TABLE fundamentals (
    ticker         TEXT NOT NULL,
    concept        TEXT NOT NULL,
    unit           TEXT NOT NULL,
    period_start   TEXT NOT NULL DEFAULT '',
    period_end     TEXT NOT NULL,
    fiscal_year    INTEGER,
    fiscal_period  TEXT,
    form           TEXT,
    filed          TEXT NOT NULL,
    value          REAL NOT NULL,
    PRIMARY KEY (ticker, concept, unit, period_start, period_end, filed)
) STRICT, WITHOUT ROWID;

CREATE TABLE earnings (
    ticker         TEXT NOT NULL,
    earnings_date  TEXT NOT NULL,
    eps_estimate   REAL,
    eps_actual     REAL,
    surprise_pct   REAL,
    PRIMARY KEY (ticker, earnings_date)
) STRICT, WITHOUT ROWID;

-- SEC Form 4, eine Zeile je Transaktion
CREATE TABLE insider_trades (
    accession         TEXT    NOT NULL,
    line_no           INTEGER NOT NULL,
    ticker            TEXT    NOT NULL,
    owner_name        TEXT    NOT NULL,
    owner_title       TEXT,
    transaction_date  TEXT    NOT NULL,
    transaction_code  TEXT    NOT NULL,
    acquired          INTEGER NOT NULL CHECK (acquired IN (0, 1)),
    shares            REAL    NOT NULL,
    price             REAL,
    filed_at          TEXT    NOT NULL,
    PRIMARY KEY (accession, line_no)
) STRICT, WITHOUT ROWID;
CREATE INDEX idx_insider_trades_ticker ON insider_trades (ticker, transaction_date DESC);

CREATE TABLE short_interest (
    ticker            TEXT NOT NULL,
    settlement_date   TEXT NOT NULL,
    short_interest    REAL NOT NULL,
    avg_daily_volume  REAL,
    days_to_cover     REAL,
    PRIMARY KEY (ticker, settlement_date)
) STRICT, WITHOUT ROWID;

-- ---------------------------------------------------------------- Scores
-- Ein Gesamtscore je Asset, Profil und Tag (Historie für Verlauf und Backtest)
CREATE TABLE scores (
    id           INTEGER PRIMARY KEY,
    asset_id     TEXT    NOT NULL,
    profile      TEXT    NOT NULL,
    date         TEXT    NOT NULL,
    score        REAL    NOT NULL CHECK (score BETWEEN -10 AND 10),
    label        TEXT    NOT NULL,
    coverage     REAL    NOT NULL CHECK (coverage BETWEEN 0 AND 1),  -- Anteil verfügbarer Gewichte
    origin       TEXT    NOT NULL DEFAULT 'live' CHECK (origin IN ('live', 'backfill')),
    computed_at  TEXT    NOT NULL,
    UNIQUE (asset_id, profile, date)
) STRICT;
CREATE INDEX idx_scores_profile_date ON scores (profile, date);

-- Teilscores mit Begründung; subscore NULL = Faktor nicht verfügbar
CREATE TABLE score_components (
    score_id          INTEGER NOT NULL REFERENCES scores (id) ON DELETE CASCADE,
    factor            TEXT    NOT NULL,
    subscore          REAL    CHECK (subscore BETWEEN -1 AND 1),
    weight            REAL    NOT NULL,   -- Gewicht laut Profil
    effective_weight  REAL    NOT NULL,   -- nach Renormierung über verfügbare Faktoren
    reason            TEXT    NOT NULL,   -- deutsche Begründung für das Dashboard
    inputs            TEXT    NOT NULL DEFAULT '{}',  -- JSON der Eingangswerte
    PRIMARY KEY (score_id, factor)
) STRICT, WITHOUT ROWID;
