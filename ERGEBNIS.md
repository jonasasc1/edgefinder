# ERGEBNIS – Pflicht-Checks vor Deploy (Etappe g, Stand 2026-11-18)

Kein Deploy erfolgt. Alle Checks lokal auf der Agent-VM (nice/ionice).

| # | Befehl | Kurzfazit | Funde |
|---|---|---|---|
| 1 | `semgrep scan --config p/default --config p/secrets --metrics=off --error .` (`--config auto` geht mit `--metrics=off` nicht: „Cannot create auto config when metrics are off“) | 9 Funde, alle als False Positive bewertet (siehe unten) – **offen bis Jonas entscheidet** | ERROR 9 (kein High/Critical-Äquivalent bestätigt), Warning 0 |
| 2 | `gitleaks git --redact .` (10 Commits) | 1 Fund, False Positive (Testwert) | 1 (generic-api-key) |
| 3a | `pip-audit -r <uv export --frozen --no-dev>` (Lockfile, 112 Zeilen) | keine bekannten Schwachstellen | 0 |
| 3b | `npm audit --omit=dev` (frontend) | keine Schwachstellen | 0 |
| 4 | `/security-review` | **offen, wird von Claude-Hauptsession ausgeführt** | – |

## Semgrep-Details (alle ERROR, Bewertung: False Positive)
- `backend/edgefinder/api/routes.py:58` und `backend/edgefinder/backtest/analysis.py:116-118` (sqlalchemy-execute-raw-query): SQL wird aus festen Fragmenten zusammengesetzt, alle Werte laufen als `?`-Parameter; keine Nutzereingabe im SQL-Text.
- `backend/edgefinder/db/connection.py:24` (formatted-sql-query, 2 Treffer): `PRAGMA busy_timeout = {BUSY_TIMEOUT_MS}` mit Konstante (int), PRAGMA lässt keine Parameter zu.
- `frontend/scripts/make-icons.mjs:60`, `frontend/scripts/screenshots.mjs:136,146,155,168` (Playwright goto/evaluate/setContent): lokale Dev-Skripte (Screenshots/Icons), nie auf „trading“ im Betrieb, URLs/Quellen fest.
- Neuer Code dieser Etappe (backup.py, systemd.py, deploy/*.sh) ohne Funde.

## Gitleaks-Detail
- `backend/tests/test_myfxbook.py:16` (Commit 5e9436b): Dummy-Zugangsdaten im Test („Reine Testwerte“). Vorschlag: `.gitleaksignore` mit dem Fingerprint oder Rename; nicht ohne Rückmeldung geändert.

## Nicht geprüft
- `shellcheck` und `nft` sind auf der Agent-VM nicht installiert: `install.sh`, `deploy.sh`, `sync-units.sh` nur mit `bash -n` und Dry-Run/Stub geprüft, `nftables.conf` nicht per `nft -c`.
