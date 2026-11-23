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

## Pflicht-Checks vor Deploy Nr. 6 (2026-11-21, Änderungen seit 4e7ec1d: Score-Eichung „Einordnung“)

| Schritt | Befehl | Ergebnis |
|---|---|---|
| Lint/Tests | ruff, pytest, `npm run lint`/`build`/`test` (36), `check:nav` | grün |
| Semgrep | `semgrep scan --config p/default --config p/secrets --metrics=off --severity ERROR .` | 0 Funde (ERROR) |
| Gitleaks | `gitleaks git --redact .` | 0 Funde |
| pip-audit | keine neuen Abhängigkeiten seit Deploy Nr. 4 (0 Funde) | 0 Funde |
| npm audit | `npm audit --omit=dev` | 0 Funde |
| Manuelle Durchsicht | 30 Dateien (22.548 Zeilen, davon `docs/calibration.json` ≈ 22.000) | kein Fund |

Durchsicht: neue Endpunkte `/api/assets/{id}/calibration` und `/api/calibration/summary`: Asset-ID gegen die Config geprüft (404),
Profil gegen die Config (422), der Dateipfad der Eichung stammt ausschließlich aus `config.yaml` (nicht vom Client), keine SQL-f-Strings,
keine HTML-Senken im Frontend (Texte als React-Text). Die Eichdatei ist statisch und deterministisch.
Inhaltliches Ergebnis der Eichung: kein Bereich „belegt“ (Swing Indizes/Aktien „schwach“, übrige „kein Vorteil“) – siehe `docs/backtest-report.md`.

## Pflicht-Checks vor Deploy Nr. 7 (2026-11-21, Änderungen seit 19a90be: Forward-Test, Live-Bilanz, Wartungszyklus)

| Schritt | Befehl | Ergebnis |
|---|---|---|
| Lint/Tests | ruff, pytest, `gen-systemd --check`, `npm run lint`/`build`/`test` (40), `check:nav` | grün |
| Semgrep | `semgrep scan --config p/default --config p/secrets --metrics=off --severity ERROR .` | 1 Treffer (`backtest/live.py:161`), False Positive, mit `# nosemgrep` + Begründung markiert → 0 Funde |
| Gitleaks | `gitleaks git --redact .` | 0 Funde |
| pip-audit | keine neuen Abhängigkeiten seit Deploy Nr. 4 | 0 Funde |
| npm audit | `npm audit --omit=dev` | 0 Funde |
| Manuelle Durchsicht | 43 Dateien (Migration 0004, `live.py`, `maintenance.py`, API `trackrecord`, Frontend Bilanz) | kein Fund |

Bewertung des Semgrep-Treffers: SQL aus festen Fragmenten, die Werte (`model_version`, `profile`) laufen als `?`-Parameter, das Profil wird vorher
gegen die Config geprüft – kein Injection-Pfad. Durchsicht: neue Endpunkte `/api/trackrecord` und `/api/assets/{id}/trackrecord` validieren Asset und Profil
gegen die Config (404/422), `limit` ist begrenzt (`MAX_LIMIT`), keine Nutzereingabe in SQL oder Dateipfaden; neue CLI-Befehle `evaluate`/`maintain`/`review-report`
laufen nur über systemd-Timer (User `edgefinder`, flock, MemoryMax=1G, ProtectSystem=strict) und schreiben nur unter `/var/lib/edgefinder`;
keine HTML-Senken im Frontend (React-Text).

## Pflicht-Checks vor Deploy Nr. 8 (2026-11-22, Änderungen seit 63f4556: Admin-Bereich)

| Schritt | Befehl | Ergebnis |
|---|---|---|
| Lint/Tests | ruff, pytest (417), `gen-systemd --check` (26 Dateien), `npm run lint`/`build`/`test` (48), `check:nav` | grün |
| Semgrep | `semgrep scan --config p/default --config p/secrets --metrics=off --severity ERROR .` | 0 Funde |
| Gitleaks | `gitleaks git --redact .` | 0 Funde |
| pip-audit | keine neuen Abhängigkeiten | 0 Funde |
| npm audit | `npm audit --omit=dev` | 0 Funde |
| /security-review | gegen 63f4556 (40 Dateien) | 0 Funde |

Durchsicht (Schwerpunkt Autorisierung und Ausführung): `api/admin.py` – `require_admin` prüft bei jedem Aufruf Identität und frische DB-Zeile (401/403 mit gleicher Meldung,
kein Konto wird angelegt), `users.is_admin` ist per API nicht setzbar (nur CLI `admin grant|revoke`, Audit-Eintrag), Berichtsendpunkte lesen feste Dateien (keine Pfadparameter,
fester Dateiname, Größenlimit). `admin_jobs.py` – Allowlist fest im Code und in `config.yaml`, Runner ruft nur Python-Funktionen aus `JOBS` (kein subprocess/Shell, Test prüft den Quelltext),
SQL parametrisiert; der f-String mit `JOB_COLUMNS` setzt eine Modulkonstante ein (kein Client-Wert, `# noqa: S608`). Teil-Index verhindert parallele Aufträge, Abkühlzeit und
Queue-Limit vorhanden. Unit `edgefinder-adminjobs.service`: User edgefinder, gleiche Härtung wie die übrigen Jobs, flock-Jobsperre. CSRF über `api/guard.py` (Origin, Sec-Fetch-Site,
nur JSON, 256 B). Hinweis (kein Fund): Im Header-Modus ist die Admin-Identität nur so vertrauenswürdig wie die Firewall (8420 nur von cloudflared); der JWT-Modus schließt das
und wird für die Admin-Funktion empfohlen. Auswirkung bei Ausnutzung wäre begrenzt (nur die vier Allowlist-Aufträge und Lesezugriff auf Berichte/Konten, keine Codeausführung).

## Pflicht-Checks vor Deploy Nr. 9 (2026-11-23, Änderungen seit eda2224: Claude-Prüfagent Phase 1 [nicht installiert, `enabled: false`], EDGAR-Vorgänger-CIKs/XOM, Sicherheitsfix)

| Schritt | Befehl | Ergebnis |
|---|---|---|
| Lint/Tests | ruff, pytest, `gen-systemd --check`, `bash -n` + `py_compile` aller Deploy-Skripte, `npm run lint`/`build`/`test` (59) | grün |
| Semgrep | `semgrep scan --config p/default --config p/secrets --metrics=off --severity ERROR .` | 0 Funde |
| Gitleaks | `gitleaks git --redact .` | 0 Funde |
| pip-audit | keine neuen Python-Abhängigkeiten (uv.lock unverändert) | 0 Funde |
| npm audit | Frontend `--omit=dev`; Claude-Code-Lockfile `deploy/claude-review/npm` | je 0 Funde |
| /security-review | gegen eda2224 (49 Dateien) | **1 Fund (Medium), behoben und nachgeprüft** |

**Fund (Medium, behoben in b5a662e, ergänzt in 4e3f5e5):** `deploy/claude-review/bin/prepare.py` (läuft als root, `ExecStartPre=+`) arbeitete in `runs/<id>/`, einem dem Web-Benutzer
`edgefinder` gehörenden Verzeichnis, mit pfadbasierten `os.chown`/`os.chmod` nach dem Schreiben. Ein kompromittierter edgefinder-Prozess hätte die Datei im Zeitfenster durch einen Symlink ersetzen
können (TOCTOU) und root ein beliebiges Ziel (z. B. /etc/sudoers) übereignen lassen: Rechteausweitung edgefinder → root. **Behebung:** `runs/` gehört root; der Webprozess baut das Paket in `staging/<id>/`
(edgefinder-eigen); `prepare.py` legt `runs/<id>` als root an und kopiert per `dir_fd` mit `O_NOFOLLOW` (nur reguläre Dateien/Verzeichnisse, Namens-, Größen-, Tiefen- und Anzahl-Limits),
`fchown`/`fchmod` ausschließlich am Deskriptor, Besitzer-/Typprüfung per `fstat`; `input/` gehört danach root:claude-review und ist für edgefinder nicht mehr erreichbar; `BASE` gehört root
(Agenten-Home in `.home`). Quelltext-Test verbietet pfadbasierte `chown`/`chmod` in `prepare.py`. Nachprüfung: kein pfadbasiertes chown/chmod mehr, 28 fd-basierte Operationen.
Der Claude-Prüfagent ist weder installiert noch aktiviert; der Fund war vor Installation behoben.

Weitere Durchsicht ohne Fund: `claude_review.py`/`claude_scrub.py` (Lauf-ID nur validierte Zahl, `O_NOFOLLOW`, feste Pfade, Größenlimits), `run.sh`/`finish.py` (keine Shell-Eingaben),
Hook `audit.py` (deny-by-default), `tinyproxy.conf`/`claude-allow.filter` (CONNECT nur :443, Allowlist, auf Hostnamen verankert), Service-Härtung, Markdown-Renderer
(nur Text-Knoten, kein HTML), EDGAR-Vorgänger-CIK (Konfigurationsvalidierung: positive ints, Ticker in der Watchlist; URL-Bau mit `:010d`-formatierter Zahl).

## Pflicht-Checks vor Deploy Nr. 10 (2026-11-23, Änderungen seit ff3cb00: EdgeFinder-Scorecard – 14 Kernzeilen, Modell-Erwartung, Release-Kalender)

| Schritt | Befehl | Ergebnis |
|---|---|---|
| Lint/Tests | ruff, pytest (536), `gen-systemd --check`, `npm run lint`/`build`/`test` (61), `check:nav` | grün |
| Semgrep | `semgrep scan --config p/default --config p/secrets --metrics=off --severity ERROR .` | 0 Funde |
| Gitleaks | `gitleaks git --redact .` | 0 Funde |
| pip-audit / npm audit | keine Abhängigkeitsänderung (uv.lock, package.json unverändert) | 0 Funde |
| Durchsicht (22 Dateien) | Migration 0006, FRED-Release-Kalender, Transforms `mom`/`sma`, Scorecard, Frontend | kein Fund |

Durchsicht: Neue externe Aufrufe nur an die bestehende FRED-API (`series/release`, `release/dates`), Serien-IDs ausschließlich aus `config.yaml`, Release-ID als Zahl, Parameter über den HTTP-Client
(Key per Parameter, `scrub` greift; Rohdaten enthalten keinen Key), Fehler je Serie → `partial`. SQL durchgehend parametrisiert (`DELETE … WHERE series_id = ? AND release_date >= ?`),
keine f-String-SQL, keine HTML-Senken im Frontend. Die neuen Anzeige-Indikatoren (`display_only`) verändern keinen Score (Test + Vorher/Nachher-Vergleich EURUSD/GOLD/SPX/AAPL identisch).

## Pflicht-Checks vor Deploy Nr. 10, Nachtrag (2026-11-23): Edelmetall-Score nur noch Inflation (Modell 2026-11-23)

| Schritt | Befehl | Ergebnis |
|---|---|---|
| Lint/Tests | ruff check + format, pytest (alle grün), `gen-systemd --check` | grün |
| Semgrep | `semgrep scan --config p/default --config p/secrets --metrics=off --severity ERROR .` | 0 Funde |
| Gitleaks | `gitleaks git --redact .` (55 Commits) | 0 Funde |
| pip-audit / npm audit | keine Abhängigkeitsänderung | 0 Funde |
| /security-review | gesamter Diff dieser Änderung (7 Dateien, nur Löschen von Rechenlogik, Versionsstring, Tests, Doku) | kein Fund |

Änderung auf Jonas' Wunsch: Zinsen, Realrendite, 10J-Rendite und Dollar-Index gehen bei Gold/Silber nicht mehr in den Score ein (nur noch US-Inflation; Zeilen bleiben „nur Info“).
`scoring.model_version` = 2026-11-23, daher Backfill + Eichung nach dem Deploy neu (`maintain`).
