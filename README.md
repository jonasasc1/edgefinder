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

## Betrieb

Produktion läuft auf dem Container „trading“ (`trading.internal`, 10.10.20.65, Debian 13, 2 GB RAM).
Entwickelt wird nur auf der Agent-VM, auf „trading“ wird eingerichtet und ausgerollt.

| Was | Wo auf „trading“ |
|---|---|
| App-Code (Git-Checkout, Besitzer `edgefinder`) | `/opt/edgefinder` |
| Datenbank, Rohdaten, Sicherungen | `/var/lib/edgefinder/data` (`/opt/edgefinder/data` ist ein Link dorthin, weil `config.yaml` relative Pfade nutzt) |
| Geheimnisse | `/opt/edgefinder/.env` (Besitzer `edgefinder`, `chmod 600`, legt Jonas selbst an) |
| Dienst | `edgefinder.service` (Port 8420, MemoryMax 600 MB) |
| Jobs | `edgefinder-fetch@<quelle>`, `edgefinder-score`, `edgefinder-cleanup`, `edgefinder-backup` mit je eigenem Timer |

### Ersteinrichtung (einmalig)

1. **Snapshot** von CT 122 in Proxmox anlegen.
2. `deploy/` nach „trading“ kopieren: `scp -r deploy claude@trading.internal:~/`.
3. Auf „trading“ erst ansehen, dann ausführen:
   ```
   ~/deploy/install.sh --dry-run      # zeigt nur, was passieren würde
   ~/deploy/install.sh                # richtet ein (ohne Firewall)
   ```
   Das Skript ist idempotent. Es installiert Pakete, uv und Node (gepinnt, mit Prüfsumme), legt den
   User `edgefinder` (ohne Login) und die Verzeichnisse an, erzeugt einen Deploy-Key und klont das Repo.
4. Endet das Skript mit **Exit-Code 3**, zeigt es den öffentlichen Schlüssel: in GitHub unter
   *Settings → Deploy keys* von `jonasasc1/edgefinder` eintragen (**ohne** Schreibrecht), dann erneut starten.
5. `.env` selbst anlegen (Vorlage `/opt/edgefinder/.env.example`, nur Jonas füllt sie):
   `sudo -u edgefinder install -m 600 /dev/null /opt/edgefinder/.env`, dann mit `sudo -u edgefinder nano …` bearbeiten.
6. Erstes Deploy von der Agent-VM: `deploy/deploy.sh` (siehe unten).
7. Optional Firewall: `~/deploy/install.sh --apply-firewall`. Es gibt einen Syntaxcheck und einen
   automatischen Rollback nach 60 s, wenn du nicht in einer **zweiten** SSH-Sitzung geprüft und mit `ja`
   bestätigt hast. Regeln: `deploy/nftables.conf` (8420 nur von 10.10.20.20, SSH nur von 10.10.20.90, sonst
   eingehend drop). Die Proxmox-Firewall auf CT-Ebene ist davon unabhängig und muss dazu passen.
8. Postfix (falls installiert) wird nicht angefasst. Empfehlung: nur lokal lauschen lassen oder
   `sudo systemctl disable --now postfix`, wenn „trading“ keine Mails senden soll.

`claude` behält auf „trading“ vollen sudo (Entscheidung Jonas); ein eingeschränktes sudoers gibt es daher nicht.

### Deploy-Ablauf

Auf der Agent-VM, nach Push auf `origin/main` und grünen Pflicht-Checks (siehe `ERGEBNIS.md`):

```
deploy/deploy.sh            # zeigt den Plan und fragt nach
deploy/deploy.sh --yes      # ohne Rückfrage
```

Schritte: Vorprüfung (`.env` vorhanden, freier Speicher) → `git fetch` und Checkout des Commits (bricht bei
lokalen Änderungen ab) → `uv sync --frozen` → Frontend-Build (`npm ci`, `npm run build`; nur wenn sich
`frontend/` geändert hat, mit `nice`/`ionice` und `--max-old-space-size=1024`) → `check-config`, DB-Sicherung,
`edgefinder migrate` → Units synchronisieren (`daemon-reload`) → `systemctl restart edgefinder` →
Health-Check (`/api/health`, bis 30 s) und Smoke-Test (Startseite, `/api/assets`).
Exit-Codes: 10 Vorprüfung, 11 Code/uv, 12 Frontend, 13 Migration, 14 Neustart/Health, 15 Smoke-Test.

**Speicher:** Der Frontend-Build braucht bis zu ~1 GB. Fehlt Swap, den Build-Fehler `dmesg | grep -i oom`
prüfen; bei Bedarf in Proxmox den CT-Swap erhöhen (Container-Ressourcen, nicht im CT selbst).

### Zeitpläne (systemd-Timer)

Die Zeitpläne stehen in `config.yaml` (`sources.<name>.schedule`, `scoring.schedule`, `maintenance.*`;
`OnCalendar`-Ausdruck oder Liste davon). Die Units entstehen daraus und liegen **im Repo** unter
`deploy/systemd/` (reproduzierbar, im Git sichtbar). Nach jeder Änderung an `config.yaml`:

```
uv run edgefinder gen-systemd           # schreibt deploy/systemd/
uv run edgefinder gen-systemd --check   # Prüfung ohne Schreiben (Test schlägt sonst an)
```

Alle Jobs laufen mit `Nice=19`, `IOSchedulingClass=idle`, `MemoryMax=1G` und über eine gemeinsame Sperrdatei
nacheinander (SQLite, 2 GB RAM). `Persistent=true` holt verpasste Läufe nach einem Ausfall nach,
`RandomizedDelaySec=60` streut die Starts. Myfxbook läuft 6-mal täglich (je Lauf höchstens Login + Outlook =
2 Requests) und zählt zusätzlich selbst gegen `daily_request_limit: 80` (Gratis-Limit 100 pro 24 h).

```
systemctl list-timers 'edgefinder*'     # nächste Läufe
sudo systemctl start edgefinder-fetch@fred.service   # Quelle sofort holen
```

### Logs, Backup, Rollback

- Logs: `journalctl -u edgefinder -f` (Dienst), `journalctl -u 'edgefinder-*' --since today` (Jobs),
  `journalctl -u edgefinder-fetch@myfxbook -n 50`.
- Backup: `edgefinder-backup.timer` schreibt täglich eine geprüfte SQLite-Sicherung (Online-Backup, kein Stopp)
  nach `/var/lib/edgefinder/data/backups` und behält die letzten 14. Vor jeder Migration sichert `deploy.sh`
  zusätzlich. Wiederherstellen: `sudo systemctl stop edgefinder`, Sicherung nach
  `/var/lib/edgefinder/data/edgefinder.db` kopieren (Besitzer `edgefinder`; alte `-wal`/`-shm`-Dateien löschen),
  `sudo systemctl start edgefinder`. Vor größeren Eingriffen zusätzlich einen **Proxmox-Snapshot** machen;
  die Sicherungen liegen im selben CT und ersetzen kein Backup auf einem anderen Host.
- Rollback: `deploy/deploy.sh --rollback` rollt den Stand vor dem letzten Deploy aus; ein bestimmter Stand:
  `deploy/deploy.sh --ref <commit>`. Migrationen werden nicht zurückgedreht (nur additiv); bei Schema-Problemen
  die DB-Sicherung einspielen.

### Fehlersuche

| Symptom | Prüfen |
|---|---|
| Dienst startet nicht | `journalctl -u edgefinder -n 100`; fehlt die `.env` oder gehört sie nicht `edgefinder`? |
| `status=226/NAMESPACE` oder Sandbox-Fehler | Im CT (LXC) können einzelne Härtungsoptionen fehlschlagen: mit `systemctl edit edgefinder` die betroffene Zeile (z. B. `PrivateDevices=`) leeren, Jonas melden |
| Seite leer / 404 auf `/` | `frontend/dist/index.html` fehlt: `deploy/deploy.sh --force-frontend` |
| `/api/assets` leer | Scores fehlen: `sudo systemctl start edgefinder-score.service` |
| Quelle „veraltet“ | `journalctl -u edgefinder-fetch@<quelle>`; Seite „Status“ in der App |
| Von außen nicht erreichbar | Abschnitt „Zugriff von außen“; lokal prüfen: `curl http://127.0.0.1:8420/api/health` |
| Aus dem Heimnetz nicht erreichbar | Firewall (`sudo nft list ruleset`) und Proxmox-CT-Firewall |

## Zugriff von außen (Cloudflare)

Die App selbst hat keine Anmeldung; der Schutz liegt komplett bei Cloudflare Access. **Erst Access einrichten,
dann den Hostnamen veröffentlichen.** Auf der Agent-VM wird an Cloudflare und CT 105 nichts geändert.

1. **Ingress in cloudflared (CT 105, 10.10.20.20):** neuen Hostnamen (z. B. `edgefinder.<deine-domain>`) in der
   Tunnel-Konfiguration bzw. im Zero-Trust-Dashboard (*Networks → Tunnels → Public Hostname*) anlegen, Service
   `http://10.10.20.65:8420`. Besser die **IP** als `http://trading:8420`: ob `trading` auf CT 105 aufgelöst
   wird, hängt von dessen DNS ab (vorher prüfen: `getent hosts trading` auf CT 105). Das DNS-CNAME legt Cloudflare
   beim Anlegen des Hostnamens an. Lauscht der Dienst auf `0.0.0.0:8420` (Standard), ist das ausreichend.
2. **Zero Trust → Access → Applications → Add → Self-hosted:** Domain = der Hostname aus Schritt 1;
   Policy *Allow* mit Regel *Emails* = nur Jonas' E-Mail-Adresse; Login-Methode *One-time PIN*;
   Session-Dauer z. B. 24 h bis 7 Tage (Komfort gegen Sicherheit). Eine zusätzliche *Block*-Standardregel ist nicht
   nötig, Access verweigert alles, was keine Allow-Regel trifft.
3. **Test:** Hostname im Privatfenster öffnen, PIN-Mail abwarten, Startseite und `/api/health` prüfen; ohne Login
   darf nichts außer der Cloudflare-Anmeldeseite erscheinen.
4. **Firewall:** `deploy/nftables.conf` lässt 8420 nur von 10.10.20.20 zu. Die Proxmox-Firewall auf CT-Ebene
   gilt zusätzlich und unabhängig – dort Port 8420 von 10.10.20.20 und SSH von 10.10.20.90 erlauben.
5. **Offene Empfehlung (nicht gebaut):** Die App prüft kein Cloudflare-Access-JWT. Wer das Netz 10.10.20.0/24
   erreicht, könnte die App ohne Access aufrufen. Wie bei Jonas' anderen Apps ließe sich der Header
   `Cf-Access-Jwt-Assertion` gegen die Team-Domain (JWKS) und die Application-AUD prüfen (beides in der `.env`).
   Das bräuchte eine kleine Middleware plus Abhängigkeit (PyJWT) – nur nach Rückfrage umsetzen.
