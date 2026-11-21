-- 0004: Live-Signal-Journal (Forward-Test) und Modellversion der Scores.
--
-- `scores.model_version`: Version des Modells (config.yaml: scoring.model_version) zum Zeitpunkt der
-- Berechnung. Bestehende Zeilen gehören zum Modellstand 2026-11-21 (Stand dieser Migration); das ist
-- eine Tatsache über den Code zum Deploy-Zeitpunkt, daher hier fest eingetragen. Spätere Läufe schreiben
-- die Version aus der Konfiguration.
ALTER TABLE scores ADD COLUMN model_version TEXT;
UPDATE scores SET model_version = '2026-11-21' WHERE model_version IS NULL;

-- Je Live-Signal und Horizont (Handelstage) eine Zeile, sobald der Horizont abgelaufen ist. Die Zeile
-- friert Score, Label und Richtung ein (spätere Score-Neuberechnungen ändern die Bilanz nicht).
CREATE TABLE signal_outcomes (
    id                 INTEGER PRIMARY KEY,
    asset_id           TEXT    NOT NULL,
    profile            TEXT    NOT NULL,
    signal_date        TEXT    NOT NULL,
    asset_class        TEXT    NOT NULL,
    score              REAL    NOT NULL,
    label              TEXT    NOT NULL,
    direction          TEXT    NOT NULL CHECK (direction IN ('bullish', 'bearish', 'neutral')),
    model_version      TEXT    NOT NULL,
    horizon_days       INTEGER NOT NULL CHECK (horizon_days >= 1),
    entry_date         TEXT    NOT NULL,   -- letzter Kurs <= Signaltag
    entry_price        REAL    NOT NULL,
    exit_date          TEXT    NOT NULL,   -- horizon_days Handelstage der Kursreihe später
    exit_price         REAL    NOT NULL,
    forward_return_pct REAL    NOT NULL,
    hit                INTEGER CHECK (hit IN (0, 1)),   -- NULL = neutral (keine Richtungsaussage)
    evaluated_at       TEXT    NOT NULL,
    UNIQUE (asset_id, profile, signal_date, horizon_days, model_version)
) STRICT;
CREATE INDEX idx_signal_outcomes_group ON signal_outcomes (model_version, profile, asset_class, signal_date);
CREATE INDEX idx_signal_outcomes_asset ON signal_outcomes (asset_id, profile, signal_date);
