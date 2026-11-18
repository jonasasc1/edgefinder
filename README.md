# edgefinder

Kostenloses Makro-, Sentiment- und Fundamental-Dashboard für Forex, Indizes, Rohstoffe und
US-Aktien. Aus COT-Positionierung, Retail-Sentiment, Makrodaten, Trend, Saisonalität und
Fundamentaldaten entsteht je Asset ein nachvollziehbarer Score von −10 bis +10, getrennt nach
den Profilen „Swing“ und „Langfristig“.

**Keine Anlageberatung.** Privates Projekt, ausschließlich kostenlose Datenquellen.

## Stand

| Etappe | Inhalt | Status |
|---|---|---|
| a | Projektgerüst, Konfiguration, DB-Schema, Doku | fertig |
| b | Fetcher: CFTC, FRED/Eurostat/ECB, yfinance | offen |
| c | Fetcher: Myfxbook, AAII, SEC EDGAR, FINRA | offen |
| d | Score-Engine, API-Endpunkte | offen |
| e | Design-System und Beispielseite | fertig |
| f | Restliches Frontend (Seiten, Palette, PWA) | fertig |
| g | Einrichtung „trading“, systemd, Deploy, Cloudflare-Doku | offen |
| h | Backtest | offen |

## Aufbau

```
config.yaml            Assets, Quellen, Zeitpläne, Profile, Gewichtungen
.env.example           Vorlage für Secrets (echte Werte nur in .env)
backend/edgefinder/    Python-Paket: config, db (Migrationen), api, fetchers, scoring, notify, backtest
backend/tests/         pytest (nur aufgezeichnete Daten, keine Live-Calls)
frontend/              React + TypeScript + Vite + Tailwind
deploy/                systemd-Units, install.sh, deploy.sh (Etappe g)
```

Ein Dienst, ein Port (Standard 8420): FastAPI liefert die JSON-API unter `/api/*` und den
Frontend-Build aus. Details zu Architektur und Konventionen stehen in [CLAUDE.md](CLAUDE.md).

## Entwicklung

Voraussetzungen: [uv](https://docs.astral.sh/uv/) (installiert Python 3.13 selbst), Node 24.

```bash
uv sync                                 # Abhängigkeiten laut uv.lock
cp .env.example .env && chmod 600 .env  # Werte eintragen
uv run edgefinder check-config          # config.yaml prüfen
uv run edgefinder migrate               # Datenbank anlegen/aktualisieren
uv run edgefinder serve --host 127.0.0.1

cd frontend
npm ci
npm run dev                             # Vite mit Proxy auf /api
```

Prüfen vor jedem Commit:

```bash
uv run ruff check . && uv run ruff format --check .
uv run pytest
cd frontend && npm run lint && npm run build
```

## Konfiguration

Alles Fachliche steht in `config.yaml` und wird beim Start validiert (unbekannte Schlüssel,
doppelte Asset-IDs, unbekannte Währungen und Gewichte, die sich nicht zu 1 summieren, sind
Fehler):

- `assets`: Forex-Paare, Indizes, Rohstoffe, Aktien-Watchlist. Neues Asset = neue Zeile.
- `sources`: je Quelle Zeitplan (systemd-`OnCalendar`), Rate-Limit und ab wann Daten als
  veraltet gelten.
- `economies`, `currencies`: Makro-Indikatoren je Volkswirtschaft, CFTC-Kontrakte je Währung.
- `profiles`: Gewichte und Zeiträume für „Swing“ und „Langfristig“.
- `scoring.labels`: Schwellen für „Stark bearish“ bis „Stark bullish“.

Fehlt für ein Asset ein Teilscore (z. B. kein COT für den DAX), werden die übrigen Gewichte
renormiert; die Abdeckung wird gespeichert und im Dashboard angezeigt.

Secrets (`.env`, nie im Repo): `FRED_API_KEY`, `CFTC_APP_TOKEN` (optional),
`MYFXBOOK_EMAIL`, `MYFXBOOK_PASSWORD`, `CONTACT_EMAIL`.

## Datenbank

SQLite (WAL) unter `storage.database`. Schemaänderungen ausschließlich über neue Dateien in
`backend/edgefinder/db/migrations/NNNN_name.sql`; angewendete Migrationen sind per Prüfsumme
gegen nachträgliche Änderungen geschützt.

## Betrieb, Deploy, Cloudflare

Folgt in Etappe g (Ersteinrichtung von „trading“, systemd-Units und -Timer, `deploy.sh`,
Firewall, Einstellungen für cloudflared und Cloudflare Access).
