# edgefinder

Kostenloses Makro-, Sentiment- und Fundamental-Dashboard (Vorbild: A1 Trading EdgeFinder).
Privates Projekt von Jonas. Sprache der Oberfläche: Deutsch (Fachbegriffe wie COT englisch).

> Stand: Etappe a abgeschlossen (Gerüst, Config, DB-Schema). Nächste Etappe: b (Fetcher CFTC,
> FRED/Eurostat/ECB, yfinance). Dieses Dokument wird nach jeder Etappe aktualisiert.

## Umgebungen

| Umgebung | Host | Zweck |
|---|---|---|
| Entwicklung/Test | Agent-VM (10.10.20.90), `~/remote/edgefinder` | entwickeln, testen, Screenshots |
| Produktion | CT „trading“ (`trading.internal`, 10.10.20.65, Debian 13, LXC 122) | nur einrichten, deployen, Logs lesen – dort nie entwickeln |

- Zugriff von außen: Cloudflare Tunnel (cloudflared auf CT 105, 10.10.20.20) → `http://trading:<Port>`,
  geschützt durch Cloudflare Access. An Cloudflare und CT 105 wird von hier nichts geändert.
- Auf „trading“ läuft die App als System-User `edgefinder` (kein Login, keine Shell), dem nur das
  App-Verzeichnis gehört. Der User `claude` behält dort volles sudo (Entscheidung Jonas, 2026-11-12).
- Dienst lauscht auf Port 8420; Firewall: 8420 nur von 10.10.20.20, SSH nur von 10.10.20.90.
- Die echte `.env` auf „trading“ legt Jonas an. **Nie auslesen**, nie ausgeben, nie kopieren.

## Architektur

Ein Dienst, ein Port: FastAPI liefert die JSON-API unter `/api/*` und den gebauten
Frontend-Build (SPA) aus. Daten holen und Scores berechnen laufen getrennt als
systemd-Timer-Jobs (oneshot), nicht im Webprozess.

```
config.yaml ─┐
.env ────────┤
             ▼
 Fetcher (je Quelle ein Modul) ──► SQLite: raw_* (Rohdaten) + normalisierte Tabellen
                                        │
 Score-Engine (Faktoren → Teilscores → Gesamtscore je Profil) ──► scores, score_components
                                        │
 FastAPI (/api) ◄───────────────────────┘ ──► React-SPA (frontend/dist)
```

Struktur (✓ = vorhanden, sonst geplant):

```
backend/edgefinder/
  config.py     ✓  Laden/Validieren von config.yaml (pydantic) und .env
  db/           ✓  Verbindung, Migrations-Runner, migrations/NNNN_name.sql
  fetchers/        base.py (HTTP, Retry/Backoff, Rate-Limit, Rohdaten-Ablage, Lauf-Protokoll)
                   cftc.py fred.py eurostat.py prices.py myfxbook.py aaii.py edgar.py finra.py
  scoring/         factors/ (ein Modul je Faktor), engine.py, labels.py
  api/          ✓  FastAPI-App (bisher /api/health + SPA-Auslieferung), Router, Schemas
  notify/       ✓  Notifier-Schnittstelle (noch ohne Kanal)
  backtest/        Auswertung Score-Historie gegen Kursentwicklung
  cli.py        ✓  `edgefinder check-config | migrate | serve` (später: fetch <quelle>, score, backtest)
backend/tests/     pytest, fixtures/ mit aufgezeichneten Antworten
frontend/          React + TypeScript + Vite, Tailwind mit eigenen Tokens
deploy/            systemd-Units und -Timer, sudoers, nftables, install.sh, deploy.sh
config.yaml        Assets, Gewichtungen, Profile, Zeitpläne
```

## Konventionen

### Backend
- Python 3.13, `uv` mit `uv.lock` (gepinnt). Nie `pip install` direkt.
- Nichts hartcodieren, was in `config.yaml` gehört (Assets, Serien-IDs, Gewichte, Zeiträume, Limits).
- Secrets ausschließlich aus `.env` (in `.gitignore`); `.env.example` enthält nur Platzhalter.
- Fetcher: jeder Lauf schreibt einen Eintrag in `fetch_runs` (Quelle, Start, Ende, Status, Fehler),
  speichert die Rohantwort, nutzt Retry mit Backoff und hält das Rate-Limit der Quelle ein.
  Ein Fehler in einer Quelle bricht keine andere ab (eigene Units, eigene Transaktionen).
- Funktioniert eine Quelle nicht wie beschrieben: an Jonas melden, keinen stillen Ersatz bauen.
- Scores: Teilscore auf [-1, +1], gewichtet zum Gesamtscore [-10, +10]. Fehlt ein Faktor,
  werden die Gewichte renormiert und die Abdeckung mitgespeichert. Jeder Teilscore speichert
  Eingangswerte und eine deutsche Begründung.
- SQLite: WAL, Fremdschlüssel an. Schemaänderungen nur über neue, fortlaufend nummerierte
  Migrationen; bestehende Migrationen nie ändern.
- Zeiten in UTC (ISO 8601) speichern, im Frontend lokal anzeigen.
- `asset_id` in der DB = ID aus `config.yaml`, bewusst ohne Fremdschlüssel (Historie bleibt,
  wenn ein Asset entfernt wird).
- Zeitpläne stehen als systemd-`OnCalendar` in `config.yaml`; die Timer-Units werden daraus
  erzeugt (Etappe g), nicht von Hand gepflegt.
- Tests: pytest, nur aufgezeichnete Beispieldaten, **keine Live-API-Calls**.

### Frontend
- Design-Tokens (Farben, Abstände, Radien, Typografie, hell/dunkel) als CSS-Variablen, in Tailwind
  eingebunden. Keine Rohwerte in Komponenten.
- Radix nur als ungestylte Primitives. Kein shadcn, keine Templates.
- Grün/Rot nur mit Bedeutung (bullish/bearish). `tabular-nums` für Zahlen.
- `prefers-reduced-motion` respektieren. iPhone-first.
- Gestaltung nach Skill `jonas-design` (+ `frontend-design`).

### Git
- Ein sauberer Commit je Etappe (bei Bedarf weitere kleine), klare Message auf Deutsch.
- Rechenintensives (npm install, Builds) mit `nice -n 19 ionice -c3` starten.
- Privates Repo `edgefinder` auf GitHub; „trading“ liest über einen read-only Deploy-Key.

## Prüfen (vor jedem Commit einer Etappe)

```
uv run ruff check . && uv run ruff format --check .
uv run pytest
cd frontend && npm run lint && npm run build     # build enthält den Typecheck (tsc -b)
```

Frontend zusätzlich mit Playwright: Screenshots jeder Seite, hell und dunkel, Desktop und
iPhone-Größe; selbst kritisch prüfen (Abstände, Kontrast, abgeschnittene Texte, Ausrichtung).

## Deploy (nur nach Jonas' Freigabe)

1. Pflicht-Checks, Ergebnisse in `ERGEBNIS.md`: semgrep (`--metrics=off`), gitleaks,
   `pip-audit` und `npm audit --omit=dev`, `/security-review`. Bei Funden nicht deployen.
2. `deploy/deploy.sh`: SSH auf „trading“ → git pull → `uv sync --frozen` → Frontend-Build →
   Migrationen → `systemctl restart` → Health-Check.
3. Smoke-Test: `/api/health` und Startseite laden.

Vor Eingriffen auf „trading“ (Dienste, Firewall, sudoers): erklären, an Snapshot erinnern,
Bestätigung abwarten.

## Offen
- Makro-Serien für EZ, DE, UK, JP, CH, AU, CA, NZ: in Etappe b ergänzen, nachdem sie gegen
  die Live-Quellen geprüft sind (bisher nur USA in `config.yaml`).
- CFTC-Kontraktcodes und Dataset-ID in `config.yaml` in Etappe b gegen Live-Daten prüfen.
- Bekannte Lücken: kein COT für DAX; Myfxbook deckt Indizes, Öl und Kupfer voraussichtlich
  nicht ab → Teilscore entfällt, Gewichte werden renormiert (mit Jonas abgestimmt).
- Testwarnung: Starlette empfiehlt `httpx2` statt `httpx` für den TestClient; vor einem
  Wechsel Herkunft des Pakets prüfen.
