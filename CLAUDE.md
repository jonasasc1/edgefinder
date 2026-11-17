# edgefinder

Kostenloses Makro-, Sentiment- und Fundamental-Dashboard (Vorbild: A1 Trading EdgeFinder).
Privates Projekt von Jonas. Sprache der Oberfläche: Deutsch (Fachbegriffe wie COT englisch).

> Dieses Dokument wird nach jeder Etappe aktualisiert. Aktueller Stand und nächster Schritt
> stehen direkt hier unten, offene Punkte am Ende.

## Stand und nächster Schritt

**Stand (2026-11-17):** Etappe a und b sind abgeschlossen und auf `origin/main` (Remote per SSH,
Host-Alias `github-edgefinder`). Tests (88), ruff sind grün. Die Fetcher für CFTC, FRED (mit
ALFRED-Vintages), Eurostat, EZB und yfinance (Kurse + Earnings) laufen live; ein erster Lauf
hat die lokale DB (`data/`, nicht im Repo) befüllt. Auf „trading“ wurde noch nichts verändert.

**Nächster Schritt: Etappe c** – Fetcher für Myfxbook, AAII, SEC EDGAR (Fundamentaldaten,
Form 4) und FINRA (Short Interest). Vorher die Punkte unter „Offen“ (Etappe c, noch ungeprüft)
live testen und Abweichungen melden. Neue Fetcher folgen dem Muster aus `fetchers/base.py`
(siehe „Fetcher-Konventionen“).

### Etappenplan

| Etappe | Inhalt | Status |
|---|---|---|
| a | Erreichbarkeit „trading“, Gerüst, Config, DB-Schema, CLAUDE.md, README, Repo | fertig |
| b | Fetcher: CFTC, FRED/Eurostat/ECB, yfinance | fertig (Datenlücken siehe „Offen“) |
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
  fetchers/     ✓  base.py (HTTP, Retry/Backoff, Rate-Limit, Rohdaten-Ablage, Lauf-Protokoll),
                   macro.py (gemeinsam für FRED/Eurostat/EZB), cftc.py, fred.py,
                   eurostat.py (Eurostat + EZB), prices.py (yfinance: Kurse, Earnings)
                   geplant: myfxbook.py aaii.py edgar.py finra.py
  scoring/         factors/ (ein Modul je Faktor), engine.py, labels.py
  api/          ✓  FastAPI-App (bisher /api/health + SPA-Auslieferung), Router, Schemas
  notify/       ✓  Notifier-Schnittstelle (noch ohne Kanal)
  backtest/        Auswertung Score-Historie gegen Kursentwicklung
  cli.py        ✓  `edgefinder check-config | migrate | serve | fetch <quelle>` (später: score, backtest)
backend/tests/     pytest; fixtures/ = aufgezeichnete API-Antworten (ohne Keys), support.py = Hilfen
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

### Fetcher-Konventionen
- Aufruf: `uv run edgefinder fetch <cftc|fred|eurostat|ecb|prices|all>`. Jede Quelle läuft mit
  eigener DB-Verbindung und eigenem `fetch_runs`-Eintrag; `all` macht bei Ausfall einer Quelle
  mit den übrigen weiter. Exit-Code 1, wenn ein Lauf nicht `success` war (systemd zeigt es an).
  Der CLI-Name ist der Schlüssel in `config.sources`; `enabled: false` überspringt die Quelle.
- Neuer Fetcher: Unterklasse von `Fetcher`, `source = "<name>"`, `fetch()` gibt die Zeilenzahl zurück.
  Fehler je Einheit (Serie, Symbol, Kontrakt) in `with self.unit("name"):` fangen → Lauf wird
  `partial`; nichts gespeichert + Fehler → `error`. Je Einheit eine Transaktion (`transaction()`).
  HTTP nur über `self.http.get()` (Rate-Limit, Retry, Backoff), Bibliotheken mit eigenem HTTP
  (yfinance) über `call_with_retry`. Rohantwort immer mit `self.save_raw()` ablegen.
- Secrets stehen teils in URLs (FRED `api_key`): Fehlermeldungen enthalten nur Pfad und Status,
  `self.scrub()` schwärzt Werte, die Logger `httpx`/`httpcore` bleiben auf WARNING (sie würden
  sonst URLs samt Key auf INFO loggen). Nie URLs mit Query loggen.
- Makro-Serien in `config.yaml`: FRED = Serien-ID, EZB = `Dataflow/Schlüssel`, Eurostat =
  `Datensatz?Filter` (je Dimension ein Wert; Eurostat-HICP seit 2026 im Datensatz
  `prc_hicp_minr` mit `coicop18`, der alte `prc_hicp_manr` ist bei 2025-12 eingefroren).
  `macro_observations.series_id` = dieser String. Zeiträume stehen auf dem Periodenbeginn
  (Quartal 2026-Q3 → 2026-07-01). Wachstumsraten, die die Quelle schon als Vorjahres-%
  liefert, haben `transform: level`.
- FRED/ALFRED: je Serie ein Abruf des aktuellen Stands (`vintage_date = ''`) und einer aller
  Vorabstände (`vintage_date` = `realtime_start`). Tägliche Marktdaten (DGS2, DGS10) sprengen
  das ALFRED-Limit von 2000 Vintage-Daten (HTTP 400) und werden nur mit aktuellem Stand
  gespeichert (nicht revidiert). Eurostat/EZB liefern nur den aktuellen Stand.
- CFTC: ein Abruf für alle Kontrakte (Legacy – Futures Only, `6dca-aqww`, 6 Jahre); ein
  konfigurierter Kontrakt ohne Daten oder mit letzter Meldung > 45 Tage gibt `partial`.
- Kurse: Tagesdaten ab `history_years`, danach nur ab letztem Kurs minus 10 Tage (Korrekturen).
  Der Eintrag des laufenden Tages ist bis zum Handelsschluss ein Zwischenstand und wird beim
  nächsten Lauf überschrieben. Earnings liegen unter `ticker` (z. B. `BRK-B`), noch nicht
  gemeldete Termine haben `eps_actual = NULL`.

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
- **Makro-Lücken (Stand 2026-11-17, live geprüft):** Es gibt keine aktuelle Gratis-Serie in
  FRED/Eurostat/EZB für: Inflation (CPI/Kern) von UK, JP, AU, CA, NZ (die OECD-CPI-Reihen auf
  FRED enden 2021–2025, Eurostat liefert für UK keine Werte mehr); Industrieproduktion CH, AU,
  NZ; Einzelhandel AU, NZ; BIP NZ. Folge: Teilscore „macro“ dieser Währungen hat keine
  Inflationskomponente (Gewichte werden renormiert). Zu klären: Ergänzung durch nationale
  Quellen (ONS, StatCan, ABS, Stats NZ, e-Stat) – wäre ein neuer Fetcher je Land.
- **Leitzinsen:** Offizielle Leitzins-Serien gibt es nur für USA (FEDFUNDS) und EZ (EZB-Einlagesatz).
  Für UK (SONIA), JP, CH, AU, CA (Tagesgeldsätze) und NZ (3M-Interbank) stehen Proxys in der
  Konfiguration (im Label vermerkt). 2-Jahres-Renditen gibt es nur für USA und EZ.
- **Euroraum-Zusammensetzung:** Eurostat-Reihen nutzen `geo=EA21` (Euroraum mit Bulgarien seit
  2026), HICP `geo=EA`. Ändert sich die Mitgliederzahl, muss `config.yaml` angepasst werden.
- **Rohdaten wachsen:** `data/raw` bekommt je Lauf neue Dateien (FRED mit Vintages ≈ 20 MB je
  Lauf). Aufräumregel (z. B. nur die letzten 30 Tage behalten) fehlt noch – vor Etappe g klären.
- **yfinance** ist eine inoffizielle Schnittstelle (kann ohne Vorwarnung brechen); Forex-Volumen
  ist immer 0. Mini-Zeitverzug und Zwischenstände des Tages sind möglich.
- **Etappe b/h:** Für den Backtest die Vintages aus `macro_observations` nutzen
  (`vintage_date <= Stichtag`, je Beobachtung der jüngste Stand); Zeilen mit `''` nur dort, wo
  keine Vintages existieren (tägliche Marktdaten, Eurostat, EZB, CFTC kennt keine Revisionen).
- **Etappe c, noch ungeprüft:** AAII hat einen Bot-Schutz (Abruf evtl. blockiert); FINRA evtl.
  nur mit Account; Myfxbook deckt Indizes, Öl und Kupfer voraussichtlich nicht ab. Ergebnis an
  Jonas melden.
- Bekannte Lücke: kein COT für den DAX (Eurex) → Teilscore entfällt, Gewichte werden renormiert.
  Nikkei: COT jetzt über den Yen-Kontrakt 240743 (der USD-Kontrakt 240741 meldet seit 2026-03-03 nicht mehr).
- **Etappe f:** `npm audit` erneut prüfen. Stand heute: 1 Meldung „moderate“ in `minimatch`,
  nur über ESLint/typescript-eslint (Dev), nicht im Build; Fix würde ESLint auf 9 zurücksetzen.
- **Etappe e:** Im Skill `jonas-design` ist der Abschnitt „Marke“ noch offen.
- Testwarnung: Starlette empfiehlt `httpx2` statt `httpx` für den TestClient; vor einem
  Wechsel Herkunft des Pakets prüfen.
- `.claude/settings.local.json` ist lokal und nicht im Repo (in `.gitignore`).
