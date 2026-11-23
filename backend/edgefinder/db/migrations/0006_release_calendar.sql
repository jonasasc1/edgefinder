-- 0006: Veröffentlichungskalender der Makro-Serien (nur Anzeige: Stern „bald neue Daten“).
--
-- Termine kommen von der FRED-Release-API (`release/dates` mit zukünftigen Terminen) und werden
-- höchstens einmal täglich je Serie erneuert (der Fetcher ersetzt die künftigen Termine einer Serie).
-- Die Termine fließen nie in einen Score ein (kein Look-ahead-Thema, nur Anzeige).

CREATE TABLE macro_release_calendar (
    series_id     TEXT NOT NULL,
    release_date  TEXT NOT NULL,   -- YYYY-MM-DD, geplanter Veröffentlichungstermin
    fetched_at    TEXT NOT NULL,   -- UTC, ISO 8601
    PRIMARY KEY (series_id, release_date)
);

CREATE INDEX idx_macro_release_calendar_date ON macro_release_calendar (release_date);
