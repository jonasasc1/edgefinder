-- 0003: Benutzerkonten (Identität kommt von Cloudflare Access, die App führt keine Freigabeliste).
-- Gespeichert werden nur E-Mail, Favoriten und Einstellungen. Die E-Mail ist normalisiert
-- (trim, Kleinbuchstaben) und die einzige Identität; `display_name` dient nur der Anzeige.

CREATE TABLE users (
    id            INTEGER PRIMARY KEY,
    email         TEXT NOT NULL UNIQUE CHECK (email = lower(trim(email)) AND length(email) <= 254),
    display_name  TEXT NOT NULL,
    created_at    TEXT NOT NULL,
    last_seen_at  TEXT NOT NULL
) STRICT;

-- Geordnete Favoriten je Konto (position = Reihenfolge ab 0); asset_id gegen die Config geprüft (API).
CREATE TABLE user_favorites (
    user_id     INTEGER NOT NULL REFERENCES users (id) ON DELETE CASCADE,
    asset_id    TEXT NOT NULL,
    position    INTEGER NOT NULL CHECK (position >= 0),
    created_at  TEXT NOT NULL,
    PRIMARY KEY (user_id, asset_id)
) STRICT, WITHOUT ROWID;
CREATE INDEX idx_user_favorites_order ON user_favorites (user_id, position);

-- Einstellungen als JSON-Text (Schema streng in der API validiert, siehe api/account.py).
CREATE TABLE user_preferences (
    user_id     INTEGER PRIMARY KEY REFERENCES users (id) ON DELETE CASCADE,
    data        TEXT NOT NULL CHECK (json_valid(data)),
    updated_at  TEXT NOT NULL
) STRICT;
