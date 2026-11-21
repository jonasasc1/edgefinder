# ERGEBNIS – Pflicht-Checks vor Deploy (Etappe g, Stand 2026-11-18, aktualisiert nach Nacharbeiten)

Kein Deploy erfolgt. Alle Checks lokal auf der Agent-VM (nice/ionice). Jonas hat am 2026-11-18 bestätigt: die Semgrep-Funde sind
False Positives, der Gitleaks-Fund ist ein Testwert (Zustimmung zur Ausnahme).

| # | Befehl (2026-11-18) | Kurzfazit | Funde |
|---|---|---|---|
| 1 | `semgrep scan --config p/default --config p/secrets --metrics=off --error .` (`--config auto` geht mit `--metrics=off` nicht) | 9 Funde, alle False Positive (Jonas bestätigt). 4 Backend-Stellen mit `# nosemgrep` + Begründung markiert (Rest: 5 Frontend-Dev-Skripte, nicht angefasst). Aktueller Lauf: 5 Treffer, alle Dev-Skripte | ERROR 9 → 5 offen (alle FP), Warning 0 |
| 2 | `gitleaks git --redact .` (11 Commits) und `gitleaks dir --redact .` | Testwert in `backend/tests/test_myfxbook.py:16` per `.gitleaksignore` (Fingerprints) ausgenommen; danach **0 Funde** | 0 (vorher 1) |
| 3a | `pip-audit -r <uv export --frozen --no-dev>` (Stand vor den Nacharbeiten; keine Abhängigkeit geändert) | keine bekannten Schwachstellen | 0 |
| 3b | `npm audit --omit=dev` (frontend, unverändert) | keine Schwachstellen | 0 |
| 4 | `/security-review` | **offen, wird von Claude-Hauptsession ausgeführt** | – |

## Semgrep-Details (alle ERROR, Bewertung: False Positive)
- `backend/edgefinder/api/routes.py:58` und `backend/edgefinder/backtest/analysis.py:116-118` (sqlalchemy-execute-raw-query): SQL wird aus festen Fragmenten zusammengesetzt, alle Werte laufen als `?`-Parameter; keine Nutzereingabe im SQL-Text.
- `backend/edgefinder/db/connection.py:24` (formatted-sql-query, 2 Treffer): `PRAGMA busy_timeout = {BUSY_TIMEOUT_MS}` mit Konstante (int), PRAGMA lässt keine Parameter zu.
- `frontend/scripts/make-icons.mjs:60`, `frontend/scripts/screenshots.mjs:136,146,155,168` (Playwright goto/evaluate/setContent): lokale Dev-Skripte (Screenshots/Icons), nie auf „trading“ im Betrieb, URLs/Quellen fest.
- Bewertung 2026-11-18 (Jonas: ja, False Positive): Backend-Stellen mit `# nosemgrep` markiert (`routes.py`, `analysis.py`, `connection.py`);
  die 5 Frontend-Skript-Funde bleiben unmarkiert (Frontend nicht angefasst) und gelten als dokumentierte False Positives.
- Neuer Code dieser Etappe (backup.py, systemd.py, deploy/*.sh) ohne Funde.

## Gitleaks-Detail
- `backend/tests/test_myfxbook.py:16` (Commit 5e9436b): Dummy-Zugangsdaten im Test („Reine Testwerte“). Ausnahme in `.gitleaksignore`
  (Fingerprint Git-Scan und Verzeichnis-Scan), mit Zustimmung von Jonas 2026-11-18.

## Nicht geprüft
- `shellcheck` und `nft` sind auf der Agent-VM nicht installiert: `install.sh`, `deploy.sh`, `sync-units.sh` nur mit `bash -n` und Dry-Run/Stub geprüft, `nftables.conf` nicht per `nft -c`.

## /security-review (2026-11-18)

- Befehl: `/security-review` über das gesamte Projekt (noch nie deployt; Vergleich gegen leeren Basis-Commit, 224 Dateien).
- Geprüft im Detail: SPA-Auslieferung (`api/app.py`), alle SQL-Stellen in `api/routes.py`, `cleanup.py` (Löschpfade),
  `deploy/deploy.sh`, `frontend/public/sw.js`, Server-Konfiguration.
- Ergebnis: **0 Funde** (High 0, Medium 0, Low 0).
  - SPA: Pfad wird per `resolve()` + `is_relative_to(root)` begrenzt, kein Path-Traversal.
  - SQL: feste Fragmente, Werte nur als `?`-Parameter; Asset-IDs werden gegen die Config geprüft.
  - `cleanup`: löscht nie außerhalb von `raw_dir`.
  - `deploy.sh`: `--ref` nur als Hex-Hash (Regex), Variablen quotiert (`@Q`).
  - Service Worker: nur gleiche Herkunft, API-Antworten max. 24 h, keine Secrets.
- Hinweis (kein Fund): `server.host: 0.0.0.0` und die API hat keine eigene Anmeldung. Der Schutz besteht nur aus
  Firewall (8420 nur von 10.10.20.20) und Cloudflare Access. Bis die Firewall aktiv ist, ist Port 8420 im LAN offen
  (öffentliche Marktdaten, keine Secrets). Daher Firewall direkt nach dem ersten Deploy aktivieren.

## Pflicht-Checks vor Deploy Nr. 2 (2026-11-18, Änderungen seit 8d6772d: Bugfix + Scorecard)

| Schritt | Befehl | Ergebnis |
|---|---|---|
| Lint/Tests | `uv run ruff check .`, `uv run pytest` | grün |
| Semgrep | `semgrep scan --config p/default --config p/secrets --metrics=off --severity ERROR .` | 0 Funde (ERROR) |
| Gitleaks | `gitleaks git --redact .` | 0 Funde (22 Commits) |
| pip-audit | `uv export --frozen --no-dev … \| pip-audit -r … --no-deps` | 0 Funde |
| npm audit | `npm audit --omit=dev` | 0 Funde |
| /security-review | gegen 8d6772d (26 Dateien) | 0 Funde |

/security-review im Detail: neuer Endpunkt `/api/assets/{id}/scorecard` (`api/scorecard.py`): alle SQL-Abfragen mit
festem Text und `?`-Parametern, Schlüssel (Symbol, Kontraktcode) stammen aus der Config, Asset-ID wird gegen die Config
geprüft. Service Worker: nur gleiche Herkunft, HTML-/404-Antworten werden unter `/assets` weder gespeichert noch
ausgeliefert, Cache-Version = Build-Hash. `chunkError.ts`: Auto-Reload höchstens 1× je 30 s (keine Schleife).

## Pflicht-Checks vor Deploy Nr. 3 (2026-11-20, Änderungen seit 3e2c8e9: Makro, COT-Pille, E-Giant-Redesign)

| Schritt | Befehl | Ergebnis |
|---|---|---|
| Lint/Tests | ruff, pytest (258), `npm run lint`, `npm test` (18), Build, `check:nav` | grün |
| Semgrep | `semgrep scan --config p/default --config p/secrets --metrics=off --severity ERROR .` | 0 Funde (ERROR) |
| Gitleaks | `gitleaks git --redact .` | 0 Funde |
| pip-audit | Lockfile ohne dev | 0 Funde |
| npm audit | `npm audit --omit=dev` | 0 Funde |
| /security-review | gegen 3e2c8e9 (65 Dateien) | 0 Funde |

/security-review im Detail: keine XSS-Senken im neuen Frontend (kein `dangerouslySetInnerHTML`, `innerHTML`, `eval`,
`document.write`, `postMessage`); Storage nur `sessionStorage`-Flag fürs Intro; Battery-API nur lesend; Service Worker nur
umbenannt; Backend: keine neuen SQL-Abfragen (Scorecard-Erweiterung nur Textformatierung aus vorhandenen Eingangswerten);
neue Konfig-Serien sind statische Werte aus `config.yaml`.

## Nachtrag Deploy Nr. 3 (2026-11-21): Änderungen seit 5ef7612 (Slogan, `info_only`)

Ruff, pytest, `npm run lint`/`build`/`test`, `check:nav` grün; Semgrep (ERROR) 0 Funde; Gitleaks 0; npm audit 0.
Delta klein (21 Dateien): keine XSS-Senken (`dangerouslySetInnerHTML`, `innerHTML`, `eval` in den neuen Zeilen: 0), keine neuen
SQL-Abfragen, `info_only` ist ein validiertes Bool-Feld aus `config.yaml`. Manuelle Durchsicht, kein Fund.

## Pflicht-Checks vor Deploy Nr. 4 (2026-11-21, Änderungen seit 3820600: Benutzerkonten, Langfrist-Prüfung, Konto-Frontend)

| Schritt | Befehl | Ergebnis |
|---|---|---|
| Lint/Tests | ruff, pytest (310), `npm run lint`/`build`/`test` (26), `check:nav` | grün |
| Semgrep | `semgrep scan --config p/default --config p/secrets --metrics=off --severity ERROR .` | 0 Funde (ERROR) |
| Gitleaks | `gitleaks git --redact .` | 0 Funde |
| pip-audit | Lockfile ohne dev (neu: pyjwt[crypto], cryptography) | 0 Funde |
| npm audit | `npm audit --omit=dev` | 0 Funde |
| /security-review | gegen 3820600 (40 Dateien) | 0 Funde |

/security-review im Detail (Schwerpunkt Auth): `api/auth.py` – JWT nur RS256, Pflicht `exp`/`aud`/`iss`, Schlüssel nur aus der
JWKS der konfigurierten Team-Domain (Slug per Regex validiert, kein Redirect-Folgen → kein SSRF), unbekannte `kid` → 401,
Fehler loggen nur die Fehlerart; `mode: jwt` ohne .env-Werte = Startfehler (fail closed); kein anonymer Fallback.
`api/account.py` – jede Abfrage über `user_id` der Identität, Identität nie aus Client-Eingaben, alle SQL-Statements
parametrisiert, Pydantic strict + `extra=forbid`, Größenlimits, `application/json` Pflicht (Formular-CSRF damit nicht möglich),
Origin-/Sec-Fetch-Site-Prüfung. Migration 0003: Kaskaden, CHECK auf normalisierte E-Mail. Service Worker: `/api/me*` nie gecacht.
Hinweis (kein Fund): Im Header-Modus ist die Identität nur so vertrauenswürdig wie die Firewall (8420 nur von cloudflared);
der JWT-Modus (`CF_ACCESS_TEAM_DOMAIN` + `CF_ACCESS_AUD`) schließt das und wird empfohlen.

## Nachtrag Deploy Nr. 5 (2026-11-21): Änderungen seit d395038 (Profil-Hinweise „notices“)

Ruff, pytest (317), `npm run lint`/`build`/`test` (28), `check:nav` grün; Semgrep (ERROR) 0 Funde; Gitleaks 0; npm audit 0.
Delta klein (16 Dateien, 196 Zeilen): keine XSS-Senken oder SQL in den neuen Zeilen (Hinweistext wird als React-Text gerendert,
nicht als HTML), `notices` stammt ausschließlich aus `config.yaml` (pydantic-validiert), keine Nutzereingabe. Manuelle Durchsicht, kein Fund.
Zusätzlich Live-Smoke-Test der Konto-Endpunkte auf „trading“ nach Deploy Nr. 4 (401 ohne Identität, 403 fremde Herkunft, 422 ungültig,
Kontentrennung, Testkonten danach gelöscht).
