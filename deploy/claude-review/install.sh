#!/usr/bin/env bash
# Einrichtung des Claude-Prüfagenten (Etappe q) auf „trading“ – OHNE Login, ohne Zugangsdaten.
#
# Läuft auf trading als User `claude` (sudo wird intern benutzt), idempotent. Zuerst IMMER `--dry-run`:
#
#   deploy/claude-review/install.sh --dry-run            zeigt nur, was geändert würde
#   deploy/claude-review/install.sh                      richtet alles ein (fragt vorher nach), keine Firewall
#   deploy/claude-review/install.sh --apply-firewall     zusätzlich nftables-Fragment (60-s-Rollback)
#   deploy/claude-review/install.sh --yes                ohne Rückfrage (nur nach Freigabe durch Jonas)
#
# Voraussetzung: App ist deployt (/opt/edgefinder mit deploy/claude-review/), node/npm 22 und uv sind da
# (install.sh der App), user edgefinder existiert. Danach: Login-Anleitung am Ende (macht Jonas selbst).
set -euo pipefail

APP_USER=edgefinder
AGENT=claude-review
APP_DIR=/opt/edgefinder
STATE=/var/lib/claude-review
PREFIX=/opt/claude-review
CLAUDE_VERSION=2.1.330                # gepinnt; Prüfsummen (sha512) stehen in npm/package-lock.json
SRC=${EDGEFINDER_CLAUDE_SRC:-$APP_DIR/deploy/claude-review}
DRY=0
APPLY_FW=0
YES=0

usage() { sed -n '2,13p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'; }
for arg in "$@"; do
    case "$arg" in
        --dry-run) DRY=1 ;;
        --apply-firewall) APPLY_FW=1 ;;
        --yes) YES=1 ;;
        -h|--help) usage; exit 0 ;;
        *) echo "Unbekannte Option: $arg" >&2; usage >&2; exit 2 ;;
    esac
done

SUDO=""
[[ $EUID -eq 0 ]] || SUDO="sudo"
section() { printf '\n== %s ==\n' "$*"; }
info() { printf '   %s\n' "$*"; }
die() { printf 'FEHLER: %s\n' "$*" >&2; exit 1; }
run() { if ((DRY)); then printf '   [dry-run] %s\n' "$(printf '%q ' "$@")"; else "$@"; fi; }

# --- 0. Plan: was dieses Skript ändert (immer zuerst anzeigen) ---------------------------------
section "0. Was dieses Skript ändert"
cat <<PLAN
   1. Benutzer/Gruppe $AGENT (System, keine Shell, kein sudo, Passwort gesperrt), Home $STATE
   2. Verzeichnisse: $STATE (0751), inbox + staging (edgefinder), runs (root, 0755; Läufe legt prepare.py als root an), .claude (0700)
   3. apt: nur das Paket tinyproxy; /etc/tinyproxy/tinyproxy.conf + claude-allow.filter (Original als .orig)
   4. Claude Code $CLAUDE_VERSION per 'npm ci' (Lockfile mit Integrität) nach $PREFIX/node_modules (root-eigen)
   5. Python-Umgebung $PREFIX/venv (uv sync --frozen --no-install-project) für Tests des Agenten (optional)
   6. $PREFIX/{bin,hooks,PROMPT.md,settings.json} (root-eigen, nur lesbar) und
      /etc/claude-code/managed-settings.json (nicht vom Agenten änderbar)
   7. systemd: claude-review.service/.path nach /etc/systemd/system, path aktiviert (kein Timer, kein Zeitplan)
   8. Optional (--apply-firewall): nftables-Tabelle claude_review_fw (nur Loopback zum Proxy für $AGENT)
   Nicht geändert: /opt/edgefinder, /var/lib/edgefinder, .env, Deploy-Key, edgefinder-Units, Cloudflare, SSH.
   KEIN Login, keine Zugangsdaten: das macht Jonas danach selbst (Anleitung am Ende).
PLAN
if ((!DRY && !YES)); then
    [[ -t 0 ]] || die "Ohne Terminal bitte --yes angeben (nach Freigabe durch Jonas)."
    read -r -p "   Fortfahren? [j/N] " answer
    [[ "$answer" == j || "$answer" == J ]] || { echo "Abgebrochen."; exit 3; }
fi

# --- 1. Voraussetzungen ------------------------------------------------------------------------
section "1. Voraussetzungen"
# Im Dry-Run nur warnen (z. B. auf einer anderen Maschine), sonst abbrechen
need() { if ((DRY)); then info "WARNUNG (Dry-Run): $*"; else die "$*"; fi; }
[[ "$(uname -m)" == x86_64 ]] || die "Nur x86_64 vorgesehen."
((DRY)) || $SUDO -n true 2>/dev/null || die "sudo ohne Passwort nötig."
id "$APP_USER" >/dev/null 2>&1 || need "Benutzer $APP_USER fehlt (zuerst deploy/install.sh der App)."
[[ -d "$SRC" ]] || die "Nicht gefunden: $SRC (App deployen oder EDGEFINDER_CLAUDE_SRC setzen)."
for f in PROMPT.md settings.json hooks/audit.py hooks/scrub.py bin/run.sh bin/prepare.py bin/finish.py \
    tinyproxy.conf claude-allow.filter nftables-claude.conf npm/package.json npm/package-lock.json \
    systemd/claude-review.service systemd/claude-review.path; do
    [[ -f "$SRC/$f" ]] || die "Fehlt im Checkout: $SRC/$f"
done
command -v node >/dev/null && command -v npm >/dev/null || die "node/npm fehlen (Node 22, siehe deploy/install.sh der App)."
node -e 'process.exit(Number(process.versions.node.split(".")[0]) >= 22 ? 0 : 1)' || die "Node >= 22 nötig (Claude Code)."
command -v uv >/dev/null || info "WARNUNG: uv fehlt – Test-Umgebung (Schritt 5) wird übersprungen."
grep -q "\"$CLAUDE_VERSION\"" "$SRC/npm/package.json" || die "Version in npm/package.json ≠ $CLAUDE_VERSION"
info "ok"

# --- 2. Benutzer und Verzeichnisse -------------------------------------------------------------
section "2. Benutzer $AGENT und Verzeichnisse"
if id "$AGENT" >/dev/null 2>&1; then
    info "Benutzer $AGENT existiert"
else
    run $SUDO useradd --system --user-group --home-dir "$STATE" --no-create-home --shell /usr/sbin/nologin \
        --comment "Claude-Pruefagent (nur Analyse)" "$AGENT"
fi
run $SUDO install -d -o "$AGENT" -g "$AGENT" -m 0751 "$STATE"
run $SUDO install -d -o "$AGENT" -g "$AGENT" -m 0700 "$STATE/.claude"
run $SUDO install -d -o "$APP_USER" -g "$APP_USER" -m 2770 "$STATE/inbox"
# Zwischenlager des Webbenutzers: dort baut er das Eingabepaket; prepare.py (root) kopiert es per Deskriptor
# nach runs/<id>/input. Der Agent kommt nicht heran (InaccessiblePaths).
run $SUDO install -d -o "$APP_USER" -g "$APP_USER" -m 0750 "$STATE/staging"
# runs/ gehört root (nicht edgefinder-schreibbar: Schutz gegen TOCTOU, Befund /security-review 2026-11-23);
# lesbar für edgefinder (Anzeige der Ergebnisse) und claude-review.
run $SUDO install -d -o root -g root -m 0755 "$STATE/runs"
run $SUDO chmod 2770 "$STATE/inbox"   # install -d setzt setgid nicht zuverlässig
info "Der Benutzer $AGENT ist in keiner weiteren Gruppe (insbesondere nicht in $APP_USER)."

# --- 3. tinyproxy (Allowlist-Proxy) ------------------------------------------------------------
section "3. tinyproxy (nur HTTPS-CONNECT zu Anthropic, nur 127.0.0.1)"
if ! dpkg -s tinyproxy >/dev/null 2>&1; then
    run $SUDO apt-get update
    run $SUDO apt-get install -y --no-install-recommends tinyproxy
fi
if [[ -f /etc/tinyproxy/tinyproxy.conf && ! -f /etc/tinyproxy/tinyproxy.conf.orig ]]; then
    run $SUDO cp -a /etc/tinyproxy/tinyproxy.conf /etc/tinyproxy/tinyproxy.conf.orig
fi
changed_proxy=0
for pair in "tinyproxy.conf:/etc/tinyproxy/tinyproxy.conf" "claude-allow.filter:/etc/tinyproxy/claude-allow.filter"; do
    src=${pair%%:*}; dst=${pair#*:}
    if ! $SUDO cmp -s "$SRC/$src" "$dst" 2>/dev/null; then
        run $SUDO install -m 0644 -o root -g root "$SRC/$src" "$dst"
        changed_proxy=1
    fi
done
if ((changed_proxy)); then run $SUDO systemctl restart tinyproxy; fi
run $SUDO systemctl enable --now tinyproxy

# --- 4. Claude Code (gepinnt, Integrität per Lockfile) -----------------------------------------
section "4. Claude Code $CLAUDE_VERSION nach $PREFIX (kein curl | bash, Auto-Update aus)"
installed_ver=$($SUDO "$PREFIX/node_modules/.bin/claude" --version 2>/dev/null | head -1 || true)
if [[ "$installed_ver" == "$CLAUDE_VERSION"* ]]; then
    info "bereits installiert: $installed_ver"
elif ((DRY)); then
    info "[dry-run] npm ci (als $(id -un), nicht root) in Staging, Version prüfen, nach $PREFIX/node_modules kopieren"
else
    stage=$(mktemp -d)
    trap 'rm -rf "$stage"' EXIT
    cp "$SRC/npm/package.json" "$SRC/npm/package-lock.json" "$stage/"
    # npm ci prüft die sha512-Integrität aller Pakete laut Lockfile; das Postinstall-Skript von Claude Code
    # (verlinkt die Plattform-Binärdatei) läuft als normaler Benutzer, nicht als root.
    (cd "$stage" && npm ci --no-audit --no-fund --omit=dev)
    got=$(DISABLE_AUTOUPDATER=1 "$stage/node_modules/.bin/claude" --version 2>/dev/null | head -1 || true)
    [[ "$got" == "$CLAUDE_VERSION"* ]] || die "Claude Code meldet '$got' statt $CLAUDE_VERSION – nichts installiert."
    $SUDO install -d -o root -g root -m 0755 "$PREFIX"
    $SUDO rm -rf "$PREFIX/node_modules"
    $SUDO cp -a "$stage/node_modules" "$PREFIX/node_modules"
    $SUDO chown -R root:root "$PREFIX/node_modules"
    $SUDO chmod -R go-w "$PREFIX/node_modules"
    info "installiert: $got"
fi
if ! ((DRY)) && [[ -x "$PREFIX/node_modules/.bin/claude" ]]; then
    help=$(DISABLE_AUTOUPDATER=1 "$PREFIX/node_modules/.bin/claude" --help 2>&1 || true)
    for flag in --output-format --max-turns --settings --strict-mcp-config --disable-slash-commands \
        --no-session-persistence --verbose; do
        grep -q -- "$flag" <<<"$help" || info "WARNUNG: 'claude --help' kennt $flag nicht – bin/run.sh anpassen!"
    done
fi

# --- 5. Python-Umgebung für Tests des Agenten --------------------------------------------------
section "5. Test-Umgebung $PREFIX/venv (optional)"
if [[ -x "$PREFIX/venv/bin/python" ]]; then
    info "vorhanden"
elif ! command -v uv >/dev/null; then
    info "übersprungen (uv fehlt): der Agent analysiert dann ohne Testläufe."
elif ((DRY)); then
    info "[dry-run] UV_PROJECT_ENVIRONMENT=$PREFIX/venv uv sync --frozen --no-install-project (Projekt $APP_DIR)"
else
    $SUDO install -d -o root -g root -m 0755 "$PREFIX"
    # Nur Abhängigkeiten (uv.lock mit Hashes), nicht das Projekt selbst: der Agent testet den Schnappschuss.
    if ! $SUDO env UV_PROJECT_ENVIRONMENT="$PREFIX/venv" UV_CACHE_DIR=/tmp/uv-claude-review \
        uv sync --frozen --no-install-project --project "$APP_DIR"; then
        info "WARNUNG: uv sync fehlgeschlagen – der Agent läuft ohne Testumgebung (Phase 1 ok)."
    fi
    $SUDO rm -rf /tmp/uv-claude-review
fi

# --- 6. Programmdateien, Einstellungen, Hooks ---------------------------------------------------
section "6. Dateien nach $PREFIX und /etc/claude-code (root-eigen, vom Agenten nicht änderbar)"
run $SUDO install -d -o root -g root -m 0755 "$PREFIX/bin" "$PREFIX/hooks" /etc/claude-code
for f in bin/run.sh bin/prepare.py bin/finish.py; do run $SUDO install -m 0755 -o root -g root "$SRC/$f" "$PREFIX/$f"; done
for f in hooks/audit.py hooks/scrub.py; do run $SUDO install -m 0755 -o root -g root "$SRC/$f" "$PREFIX/$f"; done
for f in PROMPT.md settings.json; do run $SUDO install -m 0644 -o root -g root "$SRC/$f" "$PREFIX/$f"; done
run $SUDO install -m 0644 -o root -g root "$SRC/settings.json" /etc/claude-code/managed-settings.json
$SUDO rm -f "$STATE/.claude/settings.json" 2>/dev/null || true   # keine veränderbare Kopie im Home

# --- 7. systemd ---------------------------------------------------------------------------------
section "7. systemd-Units (claude-review.service/.path)"
for u in claude-review.service claude-review.path; do
    if ! $SUDO cmp -s "$SRC/systemd/$u" "/etc/systemd/system/$u" 2>/dev/null; then
        run $SUDO install -m 0644 -o root -g root "$SRC/systemd/$u" "/etc/systemd/system/$u"
    fi
done
run $SUDO systemctl daemon-reload
run $SUDO systemctl enable --now claude-review.path
info "Hinweis: Die edgefinder-Units (adminjobs/cleanup) brauchen die neue Version aus deploy.sh (ReadWritePaths)."

# --- 8. Firewall-Fragment ------------------------------------------------------------------------
section "8. nftables-Fragment (claude_review_fw)"
FW_SRC=$SRC/nftables-claude.conf
sed 's/^/     | /' "$FW_SRC" | sed -n '1,40p'
if ((!APPLY_FW)); then
    info "Nicht aktiviert. Aktivieren mit: $0 --apply-firewall (die systemd-Sperre IPAddressDeny gilt bereits)"
else
    [[ -t 0 ]] || die "--apply-firewall braucht ein Terminal (Bestätigung)."
    if ((DRY)); then
        info "[dry-run] nft -c -f $FW_SRC; laden; 60-s-Rollback-Timer; Bestätigung; dauerhaft in /etc/nftables.d/claude-review.nft"
    else
        command -v nft >/dev/null || run $SUDO apt-get install -y --no-install-recommends nftables
        $SUDO nft -c -f "$FW_SRC" || die "Syntaxcheck fehlgeschlagen – nichts geändert (nft im Container erlaubt? siehe README)."
        $SUDO systemd-run --unit=claude-review-fw-rollback --on-active=60 \
            /usr/sbin/nft delete table inet claude_review_fw >/dev/null
        $SUDO nft -f "$FW_SRC"
        info "Regeln AKTIV. Prüfung: sudo -u $AGENT curl -m 5 -sS https://example.org  → muss scheitern."
        info "SSH/Dienste prüfen (die Regeln betreffen nur den Benutzer $AGENT und tcp/8888 auf Loopback)."
        if read -r -t 60 -p "   Alles ok? Mit 'ja' bestätigen (60 s, sonst Rollback): " answer && [[ "$answer" == ja ]]; then
            $SUDO systemctl stop claude-review-fw-rollback.timer
            $SUDO install -d -m 0755 /etc/nftables.d
            $SUDO install -m 0644 "$FW_SRC" /etc/nftables.d/claude-review.nft
            if ! $SUDO grep -qF '/etc/nftables.d/*.nft' /etc/nftables.conf 2>/dev/null; then
                $SUDO cp -a /etc/nftables.conf /etc/nftables.conf.bak-claude 2>/dev/null || true
                echo 'include "/etc/nftables.d/*.nft"' | $SUDO tee -a /etc/nftables.conf >/dev/null
            fi
            $SUDO systemctl enable nftables.service >/dev/null
            info "Firewall-Fragment bestätigt und dauerhaft."
        else
            echo; info "Keine Bestätigung – der Rollback-Timer entfernt die Regeln in Kürze."
            exit 4
        fi
    fi
fi

# --- 9. Selbsttest (lesend) ----------------------------------------------------------------------
section "9. Selbsttest"
if ((DRY)); then
    info "[dry-run] übersprungen"
else
    code=$($SUDO -u "$AGENT" curl -m 10 -sS -o /dev/null -w '%{http_code}' -x http://127.0.0.1:8888 https://example.org 2>/dev/null || true)
    info "Proxy lehnt Nicht-Anthropic-Ziel ab (erwartet 000/403): $code"
    code=$($SUDO -u "$AGENT" curl -m 10 -sS -o /dev/null -w '%{http_code}' -x http://127.0.0.1:8888 https://api.anthropic.com 2>/dev/null || true)
    info "Proxy erreicht api.anthropic.com (erwartet HTTP-Code, z. B. 404): $code"
fi

# --- Ende: Login-Anleitung ------------------------------------------------------------------------
section "Fertig – Anleitung für Jonas: Abo-Login (einmalig, manuell)"
cat <<LOGIN
   Der Login wird NICHT vom Skript gemacht. Auf trading (Terminal, als User claude):

   1) Anmeldung starten (läuft als $AGENT, nur über den Allowlist-Proxy):
        sudo -u $AGENT -H env HOME=$STATE HTTPS_PROXY=http://127.0.0.1:8888 HTTP_PROXY=http://127.0.0.1:8888 \\
          NO_PROXY=127.0.0.1,localhost DISABLE_AUTOUPDATER=1 CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC=1 \\
          $PREFIX/node_modules/.bin/claude
   2) In der Oberfläche: Anmeldung per Abo (Claude-Konto) wählen. Claude Code zeigt eine URL.
      Diese URL auf DEINEM Rechner im Browser öffnen, anmelden, den angezeigten Code kopieren und im
      Terminal einfügen (Server hat keinen Browser; es werden nur Anthropic-Hosts angesprochen).
   3) Mit /status prüfen: angemeldet; "Setting sources" soll die verwaltete Einstellungsdatei nennen.
      Dann /exit. Die Zugangsdaten bleiben in $STATE/.claude/ (Rechte 700/600) und werden nie kopiert.
   4) Kontrolle: sudo ls -l $STATE/.claude   (Besitzer $AGENT, Dateien 600)
   5) In config.yaml: claude.enabled: true setzen, deployen. Dann Button „Claude-Analyse starten“.

   Funktioniert der Login nicht: Proxy-Log lesen (abgelehnte Hosts):
        sudo tail -n 30 /var/log/tinyproxy/tinyproxy.log
   Fehlt ein Host, ihn vorübergehend in /etc/tinyproxy/claude-allow.filter ergänzen
   (sudo systemctl reload tinyproxy), Login wiederholen, danach Datei aus dem Repo zurückspielen.
LOGIN
((DRY)) && info "Das war ein Dry-Run: nichts wurde verändert."
exit 0
