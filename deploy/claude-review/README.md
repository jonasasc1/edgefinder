# Claude-Prüfagent (Etappe q): Anleitung für Jonas

Kurz: Ein abgeschotteter, headless Claude-Code-Agent auf „trading“ prüft Daten, Bilanz und Logs und macht **nur Vorschläge**.
Technik und Grenzen: `CLAUDE.md`, Abschnitt „Claude-Prüfagent (Etappe q)“. Vorgabe: Läufe starten nur auf Zuruf an den Hauptagenten;
`claude.enabled` bleibt `false`, bis du es freigibst.

## 1. Installation freigeben (einmalig, durch den Hauptagenten nach deiner Freigabe)
1. Zuerst Snapshot/Backup des Containers „trading“ (CT 122) anlegen.
2. App-Version mit Etappe q deployen (`deploy.sh`), damit die Units `edgefinder-adminjobs`/`-cleanup` die neuen Schreibrechte haben.
3. Auf trading als `claude`: `deploy/claude-review/install.sh --dry-run` ansehen, dann `deploy/claude-review/install.sh`
   (zeigt vorher die Änderungen und fragt nach). Optional `--apply-firewall` (60-s-Rollback, im Terminal bestätigen).

## 2. Login (du, manuell – der Hauptagent sieht nie Zugangsdaten)
Das Skript gibt am Ende die Schritte aus: `sudo -u claude-review -H env … claude` auf trading starten, Anmeldung per Abo wählen,
die angezeigte URL auf deinem Rechner im Browser öffnen, den Code ins Terminal einfügen, `/status` prüfen, `/exit`.
Zugangsdaten bleiben in `/var/lib/claude-review/.claude/` (700/600). Geht der Login nicht: `sudo tail /var/log/tinyproxy/tinyproxy.log`,
fehlenden Host vorübergehend in `/etc/tinyproxy/claude-allow.filter` ergänzen und `sudo systemctl reload tinyproxy`.

## 3. Aktivieren und benutzen
`config.yaml`: `claude.enabled: true`, deployen. Admin-Seite → „Claude-Analyse starten“ (Tageslimit 3, Abkühlzeit 30 Min.).
Ergebnis, Vorschläge und Protokoll erscheinen dort; Download der `analysis.md`.

## 4. Protokoll lesen (Hauptagent oder du)
`sudo journalctl -t claude-review --since today`; Dateien unter `/var/lib/claude-review/runs/<id>/` (`output/analysis.md`, `audit.jsonl`,
`transcript.jsonl`, `status.json`).

## 4a. Sicherheit der Paketübergabe (Befund 2026-11-23, behoben)
`prepare.py` läuft als root. Früher arbeitete es in einem Verzeichnis, das dem Web-Benutzer gehört, und rief `chown`/`chmod` auf Pfaden auf
(TOCTOU: Austausch durch einen Symlink → root ändert beliebige Dateien). Jetzt: `runs/` gehört root (0755); der Webprozess schreibt das
Paket nur nach `staging/<id>/` (edgefinder-eigen); `prepare.py` kopiert es als root per Deskriptoren (keine Symlinks, nur reguläre
Dateien, geprüfte Namen, Größen-/Anzahl-Limit) nach `runs/<id>/input` (root:claude-review, nur lesbar) und nutzt `fchown`/`fchmod`.
`install.sh` setzt die Rechte (erneut ausführen, falls schon installiert: `runs/` muss root gehören, sonst bricht `prepare.py` ab).
Alte Läufe räumt `prepare.py` auf (Aufbewahrung aus der Anforderung), das Zwischenlager der `cleanup`-Lauf.

## 5. Notaus
- Läufe verhindern: `claude.enabled: false` deployen, oder `sudo systemctl disable --now claude-review.path`.
- Netz kappen: `sudo systemctl disable --now tinyproxy`.
- Benutzer sperren: `sudo usermod -L -s /usr/sbin/nologin claude-review` und `sudo rm -rf /var/lib/claude-review/.claude` (Login entfernen).
- Abo-Zugriff widerrufen: im Claude-Konto die Sitzung/den Zugriff beenden.
