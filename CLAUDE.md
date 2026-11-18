# edgefinder

Kostenloses Makro-, Sentiment- und Fundamental-Dashboard (Vorbild: A1 Trading EdgeFinder).
Privates Projekt von Jonas. Sprache der Oberfläche: Deutsch (Fachbegriffe wie COT englisch).

> Dieses Dokument wird nach jeder Etappe aktualisiert. Aktueller Stand und nächster Schritt
> stehen direkt hier unten, offene Punkte am Ende.

## Stand und nächster Schritt

**Stand (2026-11-17):** Etappe a–d sind im Code fertig (Tests 200, ruff grün). Live laufen CFTC,
FRED (ALFRED), Eurostat, EZB, yfinance, AAII und FINRA. **Myfxbook und SEC EDGAR sind nur gegen
Fixtures getestet:** In der lokalen `.env` fehlen `MYFXBOOK_EMAIL`/`MYFXBOOK_PASSWORD` und
`CONTACT_EMAIL`. Folge für die Scores: Retail-Sentiment (Forex/Gold/Silber) sowie Fundamentals und
Insider (Aktien) entfallen vorerst (Gewichte werden renormiert, Abdeckung ca. 55–95 %). Der erste
`edgefinder score`-Lauf (86 Scores, 43 Assets × 2 Profile) ist plausibel. Auf „trading“ wurde noch
nichts verändert.

**Etappe e (2026-11-17):** Design-System + Übersicht von Jonas freigegeben.

**Etappe f (2026-11-18): fertig.** Alle Seiten (Asset-Detail, Makro, Änderungen, Favoriten, Status,
Vergleich), Command-Palette, Tastenkürzel, Tooltips/Erklär-Sheets, PWA. Screenshots (hell/dunkel ×
Desktop/iPhone) unter `~/remote/edgefinder-shots/etappe-f/`; axe, Konsole und 320-px-Überlauf sauber.
Neu im Backend: `GET /api/sparklines` (Score-Verlauf aller Assets), `sw.js`/Manifest ohne Cache.
**Etappe h (2026-11-18): fertig** (Nacharbeiten + Backtest, Tests 238). **Etappe g (2026-11-18): vorbereitet, Ausführung wartet auf Jonas' Freigabe.** `deploy/` ist geschrieben und lokal
getestet (bash -n, systemd-Analyse, pytest); auf „trading“ wurde nichts ausgeführt oder geprüft. Ablauf: Jonas prüft
`deploy/install.sh --dry-run` → Ersteinrichtung → `.env` selbst anlegen → `deploy/deploy.sh`. Pflicht-Checks vor Deploy
stehen in `ERGEBNIS.md` (`/security-review` offen). **Nächster Schritt:** Freigabe/Rückfragen aus dem Etappe-g-Bericht;
Tuning-Entscheidungen nach Backtest-Bericht.

**Nächster Schritt:** Jonas trägt die drei fehlenden Werte in die `.env` ein; danach je einmal
`uv run edgefinder fetch myfxbook` und `… edgar` live prüfen (Symbolliste von Myfxbook ansehen,
siehe „Offen“). Dann Etappe e (Design-System, Beispielseite, Screenshots zur Freigabe).

### Etappenplan

| Etappe | Inhalt | Status |
|---|---|---|
| a | Erreichbarkeit „trading“, Gerüst, Config, DB-Schema, CLAUDE.md, README, Repo | fertig |
| b | Fetcher: CFTC, FRED/Eurostat/ECB, yfinance | fertig (Datenlücken siehe „Offen“) |
| c | Fetcher: Myfxbook, AAII, SEC EDGAR, FINRA | fertig (Myfxbook/EDGAR noch ohne Live-Lauf, siehe „Offen“) |
| d | Score-Engine mit beiden Profilen, FastAPI-Endpunkte | fertig |
| e | Design-System und eine Beispielseite | fertig, von Jonas freigegeben |
| f | Restliches Frontend mit allen Seiten und Funktionen | fertig |
| g | Einrichtung „trading“ (install.sh vorher zeigen), systemd, deploy.sh, Cloudflare-Doku | vorbereitet, wartet auf Freigabe |
| h | Backtest (Trefferquote/Rendite nach Score-Bereich, je Profil und Assetklasse) | fertig (Ergebnisse siehe „Offen“, `docs/backtest-report.md`) |

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
                   eurostat.py (Eurostat + EZB), prices.py (yfinance: Kurse, Earnings),
                   myfxbook.py aaii.py edgar.py finra.py
  scoring/      ✓  factors/ (ein Modul je Faktor: cot, retail_sentiment, macro, trend, seasonality,
                   aaii, fundamentals, earnings, short_interest, insider), data.py (DataStore:
                   Daten bis Stichtag, Look-Ahead-Schutz), engine.py (Gewichten, Persistenz), labels.py
  api/          ✓  app.py (FastAPI, /api/health, SPA), routes.py (alle /api-Endpunkte), schemas.py
  notify/       ✓  Notifier-Schnittstelle (noch ohne Kanal)
  backtest/     ✓  analysis.py (Forward-Rendite, Buckets, Kennzahlen, Faktor-IC), stats.py, report.py (Markdown/JSON)
  cleanup.py    ✓  Rohdaten-Aufbewahrung (`edgefinder cleanup`)
  backup.py     ✓  SQLite-Online-Backup mit Rotation (`edgefinder backup`)
  systemd.py    ✓  erzeugt Units/Timer aus config.yaml (`edgefinder gen-systemd [--out DIR] [--check]`)
  cli.py        ✓  `edgefinder check-config | migrate | serve | fetch <quelle> | score | backtest | cleanup | backup | gen-systemd`
backend/tests/     pytest; fixtures/ = aufgezeichnete API-Antworten (ohne Keys), support.py = Hilfen
frontend/          React + TypeScript + Vite, Tailwind mit eigenen Tokens
deploy/            install.sh (Ersteinrichtung trading, --dry-run/--apply-firewall), deploy.sh (läuft auf der
                   Agent-VM, per SSH), sync-units.sh (Units nach /etc/systemd/system), nftables.conf,
                   systemd/ (ERZEUGT aus config.yaml, nicht von Hand ändern; Test prüft Aktualität)
                   Kein sudoers (claude hat vollen sudo). Layout auf trading: Code /opt/edgefinder,
                   Daten /var/lib/edgefinder/data (Link /opt/edgefinder/data), Deploy-Key
                   /var/lib/edgefinder/.ssh, Node 22 (Tarball, gepinnt) und uv (gepinnt) in /usr/local
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
- Zeitpläne stehen als systemd-`OnCalendar` in `config.yaml` (String oder Liste; mehrere Uhrzeiten mit
  verschiedenen Minuten gehen nur als Liste, `07:00,23:15:00` ist ungültig); die Units entstehen daraus mit
  `uv run edgefinder gen-systemd` und liegen eingecheckt in `deploy/systemd/`. Nach jeder Änderung der Zeitpläne
  neu erzeugen (sonst schlägt `test_committed_units_match_config` an). Wartungs-Zeitpläne: `maintenance:`.
- Deploy: nur nach Freigabe; vorher Pflicht-Checks (ERGEBNIS.md). `deploy.sh` rollt einen auf origin/main liegenden
  Commit aus, Rollback `--rollback`. Jobs laufen nacheinander (flock), nice 19, MemoryMax 1G.
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

- Aufruf-Namen jetzt: `cftc|fred|eurostat|ecb|prices|myfxbook|aaii|edgar|finra|ons|statcan|abs|imf|all`.
  `HttpClient` kann auch `post_json()` (FINRA); `Fetcher.get_state/set_state/clear_state` nutzen
  `source_state` (Session, Fristen). Migration `0002_sec_edgar.sql`: `sec_companies` (Ticker → CIK),
  `sec_filings_seen` (ausgewertete Form-4-Einreichungen).
- **Myfxbook:** `login.json` + `get-community-outlook.json`. Alle Symbole des Outlooks landen in
  `retail_sentiment` (Quelle `myfxbook`), auch nicht zugeordnete – so lässt sich nach dem ersten
  Live-Lauf die Symbolliste für Indizes/Öl/Kupfer prüfen. Limit: `daily_request_limit: 80` (Gratis
  100/24 h), gezählt persistent in `request_log` über jeden Versuch inkl. Login und Retries.
  Session in `source_state` (Token nie loggen/in Rohdaten; `scrub` schwärzt ihn), Neu-Login bei
  „Invalid session“ (einmal je Lauf, nie direkt nach frischem Login) und nach 25 Tagen. Nach
  fehlgeschlagenem Login 12 h Pause (Schutz vor Konto-Sperre). Konfigurierte Symbole, die im
  Outlook fehlen → `partial`.
- **AAII:** HTML von `aaii.com/sentimentsurvey` (aktuelle Woche + 4 letzte Wochen; Historie bauen
  wir selbst auf). Erkennt keine Ergebnisse (Bot-Schutz/Layout) → `error`, kein Ersatz.
  Der Standard-UA `edgefinder/0.1` bekam 403 (Imperva); ein ehrlicher beschreibender UA
  (`options.user_agent`, nennt Zweck, kein Browser-Vortäuschen) wird akzeptiert.
- **EDGAR:** UA `edgefinder/0.1 (private research; <CONTACT_EMAIL>)`, 5 Requests/s. Ablauf:
  company_tickers.json (7 Tage) → je Ticker companyfacts (alle 3 Tage, gzip in `raw`, nur Formulare
  10-K/10-Q, Konzepte aus `options.fundamentals_concepts`) → `submissions`, neue Form 4 laden
  (rohes XML), nur Code P/S aus der nicht abgeleiteten Tabelle in `insider_trades`. `submissions`
  „recent“ reicht für ≥ 1 Jahr bzw. 1000 Einreichungen. Form 4/A (Korrekturen) werden nicht
  ausgewertet.
- **FINRA:** `POST api.finra.org/data/group/otcMarket/name/consolidatedShortInterest`, ohne Account
  (live geprüft). Filter: `settlementDate` > Start und `domainFilters` auf `symbolCode`; Symbol =
  Ticker ohne `-`/`.` (BRK-B → BRKB). Erstladung 2 Jahre, danach die letzten 60 Tage (Revisionen).
  Ticker ohne Meldung seit 45 Tagen → `partial`.

- **Nationale Inflation (2026-11-18, live geprüft, `fetchers/inflation.py`):** `ons` = UK-CPI-Jahresrate (CSV-
  Generator der ONS-Webseite, Serie „D7G7/mm23“; die JSON-API api.ons.gov.uk ist seit 2024-11 abgeschaltet),
  `statcan` = Kanada-CPI-Index (WDS, POST, Vektor 41690973), `abs` = Australien-CPI-Index quartalsweise (SDMX-CSV,
  Dataflow `CPI`; der Monatsfluss `CPI_M` endet 2025-09), `imf` = Japan (monatlich) und Neuseeland (Quartal) als
  CPI-Index der IMF-SDMX-API (`api.imf.org`, CSV). **Ersatz:** e-Stat braucht eine appId (Account), Stats NZ einen
  API-Schlüssel und `api.stats.govt.nz` hat ein abgelaufenes Zertifikat, die OECD-API liefert für Japan nur bis
  2021-06. Index-Reihen laufen mit `transform: yoy`. Indikator-Option `publication_lag_days` (nur Serien ohne
  Vintages) überschreibt die Verzögerungsschätzung nach Frequenz (Japan/IMF: 75 Tage).
- **Rohdaten-Aufbewahrung:** `storage.raw_retention_days: 30`. `uv run edgefinder cleanup [--days N] [--dry-run]`
  löscht Dateien und `raw_files`-Einträge, die älter sind (nie außerhalb `raw_dir`, leere Ordner werden entfernt);
  normalisierte Tabellen bleiben. Timer: `edgefinder-cleanup.timer` (wöchentlich, siehe `maintenance:`).

### Score-Engine (Etappe d)
- Aufruf: `uv run edgefinder score [--as-of YYYY-MM-DD] [--asset ID ...] [--from D --to D]`.
  `--from/--to` rechnet jeden Werktag nach (Backtest, Etappe h; Herkunft `backfill`). Ein Eintrag je
  Asset/Profil/Tag in `scores`, Teilscores in `score_components`; erneuter Lauf überschreibt.
  Ohne Kurse bis zum Stichtag oder ohne einen einzigen Faktor gibt es keinen Score.
- Gesamt = 10 × Σ (effektives Gewicht × Teilscore); effektives Gewicht = Gewicht / Summe der
  Gewichte verfügbarer Faktoren; `coverage` = verfügbare / alle Gewichte. Label aus `scoring.labels`.
- **Look-Ahead-Schutz** (`scoring/data.py`): Kurse ≤ Stichtag; COT ab Berichtsdatum + 3 Tage
  (Freitag); Makro mit ALFRED-Vintage ≤ Stichtag, ohne Vintages (Eurostat/EZB/Tageswerte) mit
  geschätzter Verzögerung je Frequenz (täglich 1, wöchentlich 5, monatlich 50, quartalsweise 135
  Tage ab Periodenbeginn); AAII Umfragedatum + 1; Short Interest + 11 Tage; Fundamentals/Form 4 nach
  Einreichungsdatum; Earnings nach Meldedatum. Stichtag ≥ heute = „live“, dann ohne Verzögerung.
  Retail-Sentiment hat keine Historie vor dem ersten Fetch (Backtest: Faktor entfällt dort).
- Formeln (Startwerte, Parameter je Profil in `config.yaml`):
  - **cot:** Non-Commercial Netto / Open Interest; 0,7 × Perzentil des Niveaus + 0,3 × Perzentil der
    `change_weeks`-Veränderung über `percentile_weeks` → [-1,1]. Forex: (Score(Basis) − Score(Quote)) / 2.
  - **retail_sentiment:** konträr, −(Long% − 50)/25 auf [-1,1]; Mittel über `smoothing_days`;
    Messung älter als 7 Tage → entfällt.
  - **macro:** je Indikator z-Wert der `change_months`-Veränderung gegen 10 Jahre, tanh(z/2),
    Richtung laut `higher_is`; Kategorie = Mittel; Gesamt = Mittel der Kategorien. Forex:
    Differenz Basis − Quote je Kategorie plus Zinskategorie (Leitzins, 2J, 10J: tanh(Differenz/2 PP)).
    Index: Wachstum + Arbeitsmarkt der eigenen Volkswirtschaft. Rohstoffe über `macro_driver`
    (`safe_haven`: US-Inflation, Zinsen (Leitzins, Realrendite DFII10, 10J-Rendite, gespiegelt) und Dollar-Stärke (DTWEXBGS, gespiegelt) als eigene Kategorien; `cyclical`: US-Wachstum + Arbeitsmarkt).
    Serien älter als `max_age_days` entfallen.
  - **trend:** Abstand zum langsamen SMA, SMA-Kreuz und ROC, je durch Volatilität × √Horizont
    geteilt, tanh(z/2), Mittel der drei.
  - **seasonality:** Rendite über `forward_days` ab gleichem Kalendertag in den letzten `years`
    Jahren; t-Statistik, tanh(t/3); mindestens 3 Jahre.
  - **aaii:** konträr moderat (max ±0,6): Perzentil von Bullish−Bearish über `history_weeks`; bei
    < `min_weeks` Wochen Historie z-Wert gegen `fallback_mean/std`.
  - **fundamentals:** TTM-Umsatzwachstum (CAGR), operative/Nettomarge (Niveau + Veränderung), KGV im
    Perzentil der eigenen Historie (günstig = bullish); Mittel der verfügbaren Teile.
  - **earnings:** gewichtetes Mittel der Surprise-% der letzten `quarters`, tanh(x/10).
  - **short_interest:** 0,6 × (−tanh(Veränderung/25 %)) + 0,4 × (−Perzentil Days-to-Cover).
  - **insider:** (Käufe − 0,2 × Verkäufe)/(Käufe + 0,2 × Verkäufe) in $, Vertrauen min(1, n/3),
    negative Werte halbiert; keine Transaktion = 0, keine Form-4-Daten geladen = entfällt.
- **Cross-COT (2026-11-18):** Differenz/2 statt Differenz, weil die Differenz zweier Perzentil-Scores bei
  moderaten Positionierungen schon ±1 erreichte (EURUSD sättigte). /2 = Mittel aus Basis und gespiegelter Quote;
  ±1 gibt es nur noch bei komplett gegensätzlichen Extremen. Die Makro-Differenz je Kategorie bleibt unverändert.
- **Texte:** Zahlen in `reason` laufen über `factors.de()` (Komma als Dezimalzeichen, Punkt als Tausendertrenner).
- Forex-Crosses (EURGBP …) und Majors laufen gleich: COT und Makro aus Basis- und Quote-Währung
  (`currencies` in `config.yaml`); der Kurs-/Trend-Faktor nutzt die Kursreihe des Paares.

### Backtest (Etappe h)
- **Backfill:** `uv run edgefinder score --from 2013-01-01 --to 2026-11-13 [--weekday fr|all]` – Standard sind die
  Stichtage des Wochentags `backtest.score_weekday` (Freitag), `--weekday all` = jeder Werktag. Dauer ≈ 4 Min.
  (`nice -n 19 ionice -c3`), ≈ 62 000 Scores, DB ≈ 47 MB. Backfill speichert nur Teilscores/Gewichte
  (`reason` leer, `inputs` `{}`), sonst wären es Hunderte MB; Details gibt es nur für `score --as-of`-Läufe.
- **Auswertung:** `uv run edgefinder backtest [--profile P] [--class K] [--horizon-days N] [--from D --to D]
  [--markdown PFAD]` → `backtest.output_dir` (`data/backtest/backtest.json` + `backtest-report.md`, nicht im Git);
  der eingecheckte Report liegt in `docs/backtest-report.md` (`--markdown docs/backtest-report.md`).
  `GET /api/backtest` liefert das JSON. Keine neue DB-Tabelle (Report ist abgeleitet und schnell neu erzeugt).
- Forward-Rendite: letzter Schlusskurs ≤ Stichtag → `h` Handelstage der Kursreihe später (Horizonte
  `backtest.horizons`: Swing 5/10/20, Langfristig 20/60/120; Kennwert `primary_horizon`). Buckets/Richtung aus
  `scoring.labels`. Kennzahlen: n, n_eff (÷ Überlappung h/5), Trefferquote (Richtung korrekt), Basisrate
  (Anteil steigend), Ø/Median, Spread bullish − bearish, IC (Spearman, gepoolt + Querschnitt je Stichtag),
  IC je Faktor, Stabilität je Jahr, Abdeckung je Jahr. „Alle Klassen“: IC/Spread als n-gewichtetes Klassenmittel.
- Einstieg am Schlusskurs des Stichtags (Signal ist erst nach Handelsschluss bekannt: leicht optimistisch).

### API (Etappe d)
Alle lesend, JSON, unter `/api`; Schemas in `api/schemas.py`, Swagger unter `/api/docs`. Pro Request
eigene Verbindung, wenige Abfragen (kein N+1; Indizes aus Migration 0001 reichen, keine 0003).
`/profiles`, `/assets` (beide Profile + Änderung 1d/7d), `/assets/{id}?date=` (Teilscores mit Begründung,
Eingangswerten, Abdeckung), `/assets/{id}/history?days|from|to`, `/assets/{id}/cot?weeks`,
`/assets/{id}/sentiment` (Retail + AAII), `/assets/{id}/fundamentals?profile` (Aktien: SEC-Werte,
Earnings, Short Interest, Insider; sonst Makrodaten der beteiligten Volkswirtschaften), `/macro`
(Heatmap je Land/Indikator mit Wert, Änderung, Score, Frische), `/changes?since=1d|7d`,
`/status` (letzte erfolgreiche Aktualisierung je Quelle, `stale` aus `stale_after_hours`),
`/sparklines?days&profile` (Score-Verlauf aller Assets in einem Abruf), `/health`.
Favoriten gibt es nur clientseitig (localStorage).

### Frontend
- Design-Tokens (Farben, Abstände, Radien, Typografie, hell/dunkel) als CSS-Variablen, in Tailwind
  eingebunden. Keine Rohwerte in Komponenten.
- Radix nur als ungestylte Primitives. Kein shadcn, keine Templates.
- Grün/Rot nur mit Bedeutung (bullish/bearish). `tabular-nums` für Zahlen.
- `prefers-reduced-motion` respektieren. iPhone-first.
- Gestaltung nach Skill `jonas-design` (+ `frontend-design`).
- **Struktur `frontend/src/`:** `design/tokens.css` (alle Rohwerte, hell+dunkel, inkl. `--c-series-1..4` für
  Mehrfach-Diagramme), `index.css`, `lib/` (api, useApi [Laden/Fehler/Reload], assets [geteilte Asset-Liste],
  favorites [localStorage `ef-favorites`, useSyncExternalStore], glossary [ALLE Erklärtexte, Faktor-/Quellen-/
  Indikatornamen], format, stats, search, score, theme, offline, pwa, useShortcuts, chartColors),
  `components/` (Design-System wie in Etappe e + InfoTip/ExplainSheet, CommandPalette, ShortcutsSheet,
  ui-context, ScoreBar, Table, SectionTitle, ErrorState/NoData, StarButton, Footer, OfflineBanner,
  `charts/TimeChart` = Lightweight Charts mit Panes, Legende, Token-Farben), `pages/` (`overview`, `asset`
  [Detail: Hero, FactorList, PriceScoreChart, CotCard, SentimentCard, FundamentalsCard], `macro` [Heatmap],
  `changes`, `favorites`, `status`, `compare`, `DesignPage`). Routen in `App.tsx`; Asset- und
  Vergleichsseite sind lazy. Neue Seite = Route + ggf. Eintrag in `components/nav.tsx`.
- **Navigation:** Übersicht, Makro, Änderungen, Favoriten, Status (Tab-Bar/Sidebar). Vergleich (`/vergleich?ids=A,B`,
  2–4 Assets) über Detailseite, Favoriten, Palette oder `g v`.
- **Tastenkürzel:** Strg/⌘+K Palette (Assets, Seiten, Darstellung), `/` Suche, `?` Hilfe, `g` dann `o`/`m`/`c`/`f`/`s`/`v`
  Navigation; in Textfeldern und offenen Dialogen inaktiv. Palette: ↑↓, ↵, ⇧↵ = Vergleich.
- **Tooltips/Erklärungen:** `InfoTip term="…"` (Hover = Kurztext, Tippen = Sheet). Texte nur in `lib/glossary.ts`.
- **PWA:** `public/manifest.webmanifest`, Icons in `public/icons` (erzeugt mit `scripts/make-icons.mjs` aus der
  Wortmarke, maskable + apple-touch-icon), `public/sw.js` (App-Shell/Assets Cache-first, Navigation und API
  network-first; API-Fallback nur offline, max. 24 h, Header `x-ef-cached-at` → Offline-Banner), Registrierung nur im
  Produktionsbuild (`lib/pwa.ts`). Push nur vorbereitet (push/notificationclick im SW, nichts abonniert/gesendet).
  `theme-color` folgt der gewählten Darstellung (`lib/theme.tsx`). Backend liefert sw.js/Manifest mit `no-cache`.
- **Tests Frontend:** `npm test` (vitest, nur reine Logik: Favoriten, Formatierung, Sortierung, Suche, Statistik).
- **Token-Konventionen:** Farben als `--c-*` (Modus per `[data-theme="dark"]`, gesetzt von
  `public/theme-init.js` und `lib/theme.tsx`; Wahl in localStorage `ef-theme`). Tailwind-Namen
  (`bg-surface`, `text-ink-2`, `text-bull-ink`, `rounded-card`, `text-largetitle`, `shadow-card`) kommen
  aus `@theme` in tokens.css; Tailwind-Standardfarben/-größen sind abgeschaltet. Keine Hex-Werte,
  keine `[…]`-Arbitrary-Values in Komponenten; fehlt ein Wert, erst Token anlegen. Text auf Flächen:
  `*-ink` (AA-Kontrast), `*-ring` nur für Grafik. Bullish/Bearish: `soft` (Fläche), `ring`, `ring-strong`,
  `solid` + `on-solid` (gefüllte Marke). `ink-3` nur Deko (Kontrast < 4,5).
- **Score-Ring:** 270°-Gauge, Null oben, Bogen wächst von der Nullmarke; Stufe aus dem API-Label
  (`lib/score.ts`). Zahlen/Ring laufen federnd (`useSpringValue`), sofort bei `prefers-reduced-motion`.
- **Screenshots/Prüfung:** `node frontend/scripts/screenshots.mjs [Ordner] [URL]` (Backend mit Build muss
  laufen; Playwright + axe-core aus `~/tools/playwright`, Chromium notfalls per `CHROMIUM_PATH`). Macht
  alle Seiten (Detail je Assetklasse, Makro, Änderungen, Favoriten leer/gefüllt, Status, Vergleich, Palette,
  Hilfe, Erklärung, Fehler-/Leer-/Ladezustände) in hell/dunkel × Desktop 1440×900/iPhone 14 (Service Worker
  geblockt) und prüft Konsole, Überlauf (auch 320 px) und axe-core. Dauert ca. 4 Min.
- Charts: TradingView Lightweight Charts (Attribution als Link im Footer jeder Seite, `components/Footer`).
- Lizenz Inter: OFL, per `@fontsource-variable/inter` selbst gehostet (kein CDN).

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
- **Etappe d, Stand 2026-11-17:** Gewichte, Skalen (tanh-Teiler), Label-Schwellen sind Startwerte,
  Feintuning nach dem Backtest (Etappe h). Aufgefallen: (1) EURUSD-COT-Sättigung ist mit Differenz/2
  behoben (2026-11-18). (2) AAII hat erst 2–3 Wochen
  eigene Historie → Norm-Fallback. (3) Retail-Sentiment/EDGAR-Faktoren fehlen bis zu den Live-Läufen.
  (4) Backtest: für Zeit vor dem ersten Lauf gibt es kein Retail-Sentiment, kaum AAII, Short
  Interest ab 2024-11, Earnings nur soweit yfinance sie liefert.
- **Makro-Lücken (Stand 2026-11-18, live geprüft):** Inflation (CPI) von UK, JP, AU, CA, NZ ist jetzt über
  nationale Quellen/IMF abgedeckt (siehe Fetcher-Konventionen); **Kerninflation** dieser Länder fehlt weiter. Es gibt
  keine aktuelle Gratis-Serie in FRED/Eurostat/EZB für: Industrieproduktion CH, AU,
  NZ; Einzelhandel AU, NZ; BIP NZ. Folge: Teilscore „macro“ dieser Währungen hat keine
  Inflationskomponente (Gewichte werden renormiert). Zu klären: Ergänzung durch nationale
  Quellen (ONS, StatCan, ABS, Stats NZ, e-Stat) – wäre ein neuer Fetcher je Land.
- **Leitzinsen:** Offizielle Leitzins-Serien gibt es nur für USA (FEDFUNDS) und EZ (EZB-Einlagesatz).
  Für UK (SONIA), JP, CH, AU, CA (Tagesgeldsätze) und NZ (3M-Interbank) stehen Proxys in der
  Konfiguration (im Label vermerkt). 2-Jahres-Renditen gibt es nur für USA und EZ.
- **Euroraum-Zusammensetzung:** Eurostat-Reihen nutzen `geo=EA21` (Euroraum mit Bulgarien seit
  2026), HICP `geo=EA`. Ändert sich die Mitgliederzahl, muss `config.yaml` angepasst werden.
- **Backtest-Ergebnis (2026-11-18, 2013–2026, wöchentlich, `docs/backtest-report.md`):** Die Scores haben
  **keinen positiven Vorhersagewert**; Indizes/Aktien zeigen signifikant *negativen* IC (Swing 10 T: Indizes −0,09,
  Aktien −0,05; Langfristig 60 T: Indizes −0,15). Haupttreiber: der Trend-Faktor (Kurzfrist-Umkehr: IC Indizes −0,12,
  Aktien −0,06, Forex −0,03; geprüft: Trend korreliert 0,86–0,92 mit der Vorperformance, also kein Vorzeichenfehler).
  Forex/Rohstoffe: IC ≈ 0. Makro (Indizes langfristig −0,15) fällt negativ auf. COT (Forex) −0,08 (nur 2021–2026
  verfügbar). Sehr hohe Scores (Stark bullish) sind selten (n klein). Tuning-Kandidaten (nicht geändert): Trend-Gewicht
  senken/Vorzeichen für Indizes/Aktien prüfen, Makro-Gewicht Indizes, COT-Interpretation (Trendfolger vs. Konträr).
  CFTC lädt nur 6 Jahre (`history_years: 6`); 15 Jahre würden den COT-Backtest ab 2013 ermöglichen (offen, Jonas fragen).
- **Rohdaten wachsen:** `data/raw` bekommt je Lauf neue Dateien (FRED mit Vintages ≈ 20 MB je
  Lauf). Regel: 30 Tage, `edgefinder cleanup`; Timer `edgefinder-cleanup` ist in `deploy/systemd` vorbereitet.
- **yfinance** ist eine inoffizielle Schnittstelle (kann ohne Vorwarnung brechen); Forex-Volumen
  ist immer 0. Mini-Zeitverzug und Zwischenstände des Tages sind möglich.
- **Etappe b/h:** Für den Backtest die Vintages aus `macro_observations` nutzen
  (`vintage_date <= Stichtag`, je Beobachtung der jüngste Stand); Zeilen mit `''` nur dort, wo
  keine Vintages existieren (tägliche Marktdaten, Eurostat, EZB, CFTC kennt keine Revisionen).
- **Etappe c, Stand 2026-11-17:**
  - Myfxbook: Zugangsdaten fehlen in der `.env` → kein Live-Lauf. Welche Symbole der Outlook für
    Indizes (SPX/NDX/DJI/DAX/Nikkei), Öl und Kupfer führt, ist ungeprüft; `myfxbook:` bleibt dort
    `null` (nicht geraten). Abgedeckt sind vermutlich 14 Forex-Paare, Gold (XAUUSD), Silber
    (XAGUSD). Nach dem ersten Lauf: `SELECT DISTINCT symbol FROM retail_sentiment`.
    Die Myfxbook-Webseite liegt hinter Cloudflare-Challenge (403), die API selbst ist erreichbar.
  - EDGAR: `CONTACT_EMAIL` fehlt in der `.env` → kein Live-Lauf; die Fixtures sind nach der
    dokumentierten Struktur nachgebaut, nicht aufgezeichnet. Erster Live-Lauf lädt ≈ 20 × (Facts +
    Submissions) + einige hundert Form-4-XML (≈ 5 Min.).
  - AAII: läuft, aber nur mit beschreibendem UA (siehe oben). Die Seite zeigt nur 4 Wochen; ein
    Backfill ist nicht möglich (Historie der Seite `sent_results` ist Mitgliedern vorbehalten,
    nicht geprüft). Fällt ein Donnerstag/Freitag-Lauf aus, bleibt eine Lücke bis zu 4 Wochen heilbar.
  - FINRA: läuft ohne Account; Daten ab 2024-11 geladen, Veröffentlichung ca. 7 Handelstage nach
    Stichtag (Stand: letzter Stichtag 2026-10-30).
  - `data/raw` wächst durch EDGAR (gzip) zusätzlich; Aufräumregel weiter offen.
- Bekannte Lücke: kein COT für den DAX (Eurex) → Teilscore entfällt, Gewichte werden renormiert.
  Nikkei: COT jetzt über den Yen-Kontrakt 240743 (der USD-Kontrakt 240741 meldet seit 2026-03-03 nicht mehr).
- **Etappe f:** `npm audit --omit=dev`: 0 Funde (2026-11-18). Mit Dev-Paketen: 1 „moderate“ in `minimatch` (ESLint, nicht im Build).
  Score-Verlauf hat erst 2 Tage Historie (Diagramm blendet ihn unter 5 Punkten aus); `reason`-Texte nutzen jetzt Dezimalkomma; Favoriten nur lokal; Push nur Struktur.
- **Etappe e:** Im Skill `jonas-design` ist der Abschnitt „Marke“ noch offen (Marke hier aus der Vorgabe
  „Apple-native“ abgeleitet). 
- Testwarnung: Starlette empfiehlt `httpx2` statt `httpx` für den TestClient; vor einem
  Wechsel Herkunft des Pakets prüfen.
- `.claude/settings.local.json` ist lokal und nicht im Repo (in `.gitignore`).
