-- 0005: Admin-Rolle und Job-Warteschlange für den Admin-Bereich.
--
-- `users.is_admin`: wird ausschließlich per CLI auf dem Server gesetzt (`edgefinder admin grant`),
-- es gibt keinen API-Weg dorthin. `admin_jobs`: Aufträge aus der Weboberfläche; die API schreibt nur
-- Zeilen, ein getrennter systemd-Dienst (`edgefinder admin run`) arbeitet sie ab. Ein Teil-Index
-- erzwingt höchstens einen wartenden/laufenden Eintrag je Job-Typ (auch bei gleichzeitigen Aufrufen).
-- `admin_audit`: Protokoll der Admin-Aktionen (Zeit, Akteur, Aktion).

ALTER TABLE users ADD COLUMN is_admin INTEGER NOT NULL DEFAULT 0 CHECK (is_admin IN (0, 1));

CREATE TABLE admin_jobs (
    id                    INTEGER PRIMARY KEY,
    job                   TEXT NOT NULL CHECK (length(job) <= 32),
    requested_by_user_id  INTEGER REFERENCES users (id) ON DELETE SET NULL,
    requested_at          TEXT NOT NULL,
    started_at            TEXT,
    finished_at           TEXT,
    status                TEXT NOT NULL CHECK (status IN ('queued', 'running', 'ok', 'error', 'rejected')),
    summary               TEXT CHECK (summary IS NULL OR length(summary) <= 500),
    log_tail              TEXT CHECK (log_tail IS NULL OR length(log_tail) <= 8192)
) STRICT;
CREATE UNIQUE INDEX idx_admin_jobs_active ON admin_jobs (job) WHERE status IN ('queued', 'running');
CREATE INDEX idx_admin_jobs_recent ON admin_jobs (id DESC);

CREATE TABLE admin_audit (
    id      INTEGER PRIMARY KEY,
    at      TEXT NOT NULL,
    actor   TEXT NOT NULL CHECK (length(actor) <= 254),
    action  TEXT NOT NULL CHECK (length(action) <= 64),
    detail  TEXT NOT NULL CHECK (length(detail) <= 500)
) STRICT;
