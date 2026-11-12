# edgefinder

Kostenloses Makro-, Sentiment- und Fundamental-Dashboard (Vorbild: A1 Trading EdgeFinder).
Privates Projekt von Jonas. Sprache der Oberfläche: Deutsch (Fachbegriffe wie COT englisch).

> Dieses Dokument wird nach jeder Etappe aktualisiert. Aktueller Stand und nächster Schritt
> stehen direkt hier unten, offene Punkte am Ende.

## Stand und nächster Schritt

**Stand (2026-11-12):** Etappe a ist abgeschlossen und lokal committet (2 Commits + dieser
Doku-Commit). Tests (30), ruff und Frontend-Build sind grün. Auf „trading“ wurde noch nichts
verändert.

**Sofort zu erledigen:** `git push -u origin main` – das Repo `jonasasc1/edgefinder`
(privat, Remote `origin` per HTTPS) ist noch leer. Der Push war in der ersten Sitzung
blockiert, weil sie in `/home/agent/remote` gestartet wurde und
`.claude/settings.local.json` (erlaubt `git push`, verbietet `--force`/`-f`) dort nicht griff.

**Nächster Schritt: Etappe b** – erst starten, wenn Jonas bestätigt, dass der FRED-Key in
der lokalen `.env` steht (Datei existiert, chmod 600; nicht ausgeben). Inhalt:
1. `fetchers/base.py`: HTTP-Client mit Retry/Backoff, Rate-Limit je Quelle (`request_log`),
   Rohdaten-Ablage (`raw_files`), Lauf-Protokoll (`fetch_runs`); CLI `edgefinder fetch <quelle>`.
2. CFTC (Socrata, Legacy Futures Only), FRED, Eurostat/ECB, yfinance (Kurse, Earnings).
   Neue Abhängigkeiten (httpx als Laufzeit-Dependency, yfinance, pandas) über `uv add`.
3. Makro-Serien der übrigen Volkswirtschaften in `config.yaml` ergänzen, CFTC-Codes prüfen.
4. Tests mit aufgezeichneten Antworten unter `backend/tests/fixtures/`.
5. Abschluss: Tests grün, ruff sauber, Build ok, Commit, Push, kurze Zusammenfassung an Jonas
   mit Bericht je Quelle (was funktioniert, was nicht).

### Etappenplan

| Etappe | Inhalt | Status |
|---|---|---|
| a | Erreichbarkeit „trading“, Gerüst, Config, DB-Schema, CLAUDE.md, README, Repo | fertig, Push offen |
| b | Fetcher: CFTC, FRED/Eurostat/ECB, yfinance | wartet auf FRED-Key |
| c | Fetcher: Myfxbook, AAII, SEC EDGAR, FINRA | offen |
| d | Score-Engine mit beiden Profilen, FastAPI-Endpunkte | offen |
| e | Design-System und eine Beispielseite – **Screenshots zur Freigabe durch Jonas** | offen |
| f | Restliches Frontend mit allen Seiten und Funktionen | offen |
| g | Einrichtung „trading“ (install.sh vorher zeigen), systemd, deploy.sh, Cloudflare-Doku | offen |
| h | Backtest (Trefferquote/Rendite nach Score-Bereich, je Profil und Assetklasse) | offen |

### Arbeitsweise (von Jonas vorgegeben)
- In Etappen arbeiten; nach jeder Etappe: Tests grün, ruff sauber, Build ok, Commit, kurze
  Zusammenfassung. Keine Etappe gilt als fertig, solange Tests, Lint oder Build fehlschlagen.
- Bei Unklarheit nachfragen statt raten. Quelle funktioniert nicht wie beschrieben → melden.
- `deploy.sh` und Eingriffe auf „trading“ nur nach Freigabe.

### Entscheidungen von Jonas (2026-11-12)
- Port 8420. „trading“ hat 2 GB RAM, der Frontend-Build läuft dort.
- `claude` behält auf „trading“ volles sudo (keine Einschränkung per sudoers).
- Fehlende Teilscores: Gewichte renormieren, Abdeckung sichtbar machen.
- Crosses: EURGBP, EURJPY, GBPJPY, EURCHF, AUDJPY, EURAUD, AUDNZD.
- Gewichte und Label-Schwellen in `config.yaml` sind Startwerte; Feintuning nach dem Backtest.

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
- **Push nach GitHub** steht aus (siehe oben).
- **Etappe b:** Makro-Serien für EZ, DE, UK, JP, CH, AU, CA, NZ ergänzen, nachdem sie gegen
  die Live-Quellen geprüft sind (bisher nur USA in `config.yaml`).
- **Etappe b:** CFTC-Kontraktcodes und Dataset-ID in `config.yaml` stammen aus dem Gedächtnis;
  gegen Live-Daten prüfen.
- **Etappe b/h:** FRED liefert revidierte Werte; für den Backtest Vintages (ALFRED,
  `macro_observations.vintage_date`) nutzen, damit kein Vorgriff auf Revisionen entsteht.
- **Etappe c, noch ungeprüft:** AAII hat einen Bot-Schutz (Abruf evtl. blockiert); FINRA evtl.
  nur mit Account; Myfxbook deckt Indizes, Öl und Kupfer voraussichtlich nicht ab. Ergebnis an
  Jonas melden.
- Bekannte Lücke: kein COT für den DAX (Eurex) → Teilscore entfällt, Gewichte werden renormiert.
- **Etappe f:** `npm audit` erneut prüfen. Stand heute: 1 Meldung „moderate“ in `minimatch`,
  nur über ESLint/typescript-eslint (Dev), nicht im Build; Fix würde ESLint auf 9 zurücksetzen.
- **Etappe e:** Im Skill `jonas-design` ist der Abschnitt „Marke“ noch offen.
- Testwarnung: Starlette empfiehlt `httpx2` statt `httpx` für den TestClient; vor einem
  Wechsel Herkunft des Pakets prüfen.
- `.claude/settings.local.json` ist lokal und nicht im Repo (in `.gitignore`).
