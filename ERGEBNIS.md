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
