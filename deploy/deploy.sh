#!/usr/bin/env bash
# Deploy von edgefinder auf „trading“. Läuft auf der Agent-VM, arbeitet per SSH als `claude`
# (sudo für systemctl und `sudo -u edgefinder` für alle Dateien der App).
#
#   deploy/deploy.sh [--yes] [--ref COMMIT] [--rollback] [--force-frontend] [--host HOST]
#
#   --yes             nicht nachfragen (Standard: Plan anzeigen und bestätigen lassen)
#   --ref COMMIT      diesen Commit ausrollen (Standard: lokaler HEAD, muss auf origin/main liegen)
#   --rollback        den Stand vor dem letzten Deploy wieder ausrollen (merkt sich trading selbst)
#   --force-frontend  Frontend auch bauen, wenn sich frontend/ nicht geändert hat
#   --host HOST       Ziel (Standard: trading.internal)
#
# Exit-Codes: 0 ok · 2 Aufruf · 10 Vorprüfung · 11 Code/Abhängigkeiten · 12 Frontend-Build ·
#             13 Migration/Konfiguration · 14 Neustart/Health-Check · 15 Smoke-Test
#
# Voraussetzung: deploy/install.sh wurde auf trading ausgeführt und die .env existiert.
# Nicht ausführen ohne Freigabe von Jonas (CLAUDE.md: Pflicht-Checks in ERGEBNIS.md zuerst).
set -euo pipefail

APP_USER=edgefinder
APP_DIR=/opt/edgefinder
STATE_DIR=/var/lib/edgefinder
HOST=trading.internal
SSH_USER=claude
PORT=8420
YES=0
REF=""
ROLLBACK=0
FORCE_FE=0

usage() { sed -n '2,15p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'; }
while (($#)); do
    case "$1" in
        --yes) YES=1 ;;
        --ref) REF=${2:?--ref braucht einen Commit}; shift ;;
        --rollback) ROLLBACK=1 ;;
        --force-frontend) FORCE_FE=1 ;;
        --host) HOST=${2:?--host braucht einen Namen}; shift ;;
        -h|--help) usage; exit 0 ;;
        *) echo "Unbekannte Option: $1" >&2; usage >&2; exit 2 ;;
    esac
    shift
done
[[ -z "$REF" || $ROLLBACK -eq 0 ]] || { echo "--ref und --rollback schließen sich aus." >&2; exit 2; }
[[ -z "$REF" || "$REF" =~ ^[0-9a-fA-F]{7,40}$ ]] || { echo "--ref muss ein Commit-Hash sein." >&2; exit 2; }

TARGET=$SSH_USER@$HOST
rsh() { ssh -o BatchMode=yes -o ConnectTimeout=10 "$TARGET" "$@"; }
fail() { local code=$1; shift; printf '\nFEHLER (Exit %s): %s\n' "$code" "$*" >&2
    printf 'Logs:      ssh %s journalctl -u edgefinder -n 100 --no-pager\n' "$TARGET" >&2
    printf 'Rollback:  deploy/deploy.sh --rollback\n' >&2; exit "$code"; }
step() { printf '\n== %s ==\n' "$*"; }

# --- Vorprüfung (lokal) ------------------------------------------------------------------------
cd "$(dirname "${BASH_SOURCE[0]}")/.."
if ((ROLLBACK)); then
    TARGET_SHA="(vorheriger Commit laut $STATE_DIR/previous-commit)"
else
    git fetch --quiet origin || fail 10 "git fetch origin fehlgeschlagen"
    TARGET_SHA=$(git rev-parse --verify "${REF:-HEAD}^{commit}") || fail 10 "Commit unbekannt: ${REF:-HEAD}"
    git merge-base --is-ancestor "$TARGET_SHA" origin/main \
        || fail 10 "Commit $TARGET_SHA ist nicht auf origin/main – erst pushen."
    if [[ -z "$REF" && -n "$(git status --porcelain --untracked-files=no)" ]]; then
        echo "Hinweis: lokal uncommittete Änderungen; ausgerollt wird nur der Commit, nicht sie."
    fi
fi

cat <<PLAN
Deploy-Plan für $TARGET
  1. Vorprüfung: Erreichbarkeit, .env vorhanden (Inhalt wird nicht gelesen), freier Speicher
  2. $APP_DIR: git fetch, bricht bei lokalen Änderungen ab, dann Checkout von
     $TARGET_SHA
  3. uv sync --frozen --no-dev (als $APP_USER, nice/ionice)
  4. Frontend: npm ci + npm run build, nur wenn sich frontend/ geändert hat (--force-frontend erzwingt)
  5. edgefinder check-config, DB-Sicherung, edgefinder migrate
  6. systemd-Units und Timer aus deploy/systemd synchronisieren (daemon-reload)
  7. sudo systemctl restart edgefinder
  8. Health-Check (/api/health, bis 30 s) und Smoke-Test (Startseite, /api/assets)
Tipp: vorher einen Proxmox-Snapshot von CT 122 anlegen.
PLAN
if ((!YES)); then
    read -r -p "Fortfahren? [ja/N] " answer
    [[ "$answer" == ja ]] || { echo "Abgebrochen."; exit 0; }
fi

# --- 1. Vorprüfung (trading) -------------------------------------------------------------------
step "1. Vorprüfung"
rsh true || fail 10 "SSH zu $TARGET nicht möglich"
rsh "sudo -n -u $APP_USER test -f $APP_DIR/.env" \
    || fail 10 "$APP_DIR/.env fehlt – Jonas legt sie an (siehe README, Abschnitt Ersteinrichtung)"
avail=$(rsh "free -m | awk '/^Mem:/{print \$7}'")
swap=$(rsh "free -m | awk '/^Swap:/{print \$2}'")
echo "   frei (available): ${avail} MB, Swap: ${swap} MB"
if ((avail < 700 && swap < 512)); then
    fail 10 "Zu wenig Speicher für den Frontend-Build (2-GB-CT): >= 700 MB frei oder Swap nötig (siehe README)"
fi

# --- 2./3. Code und Abhängigkeiten -------------------------------------------------------------
step "2. Code aktualisieren"
rsh "APP_DIR=$APP_DIR APP_USER=$APP_USER STATE_DIR=$STATE_DIR ROLLBACK=$ROLLBACK TARGET_SHA=${TARGET_SHA@Q} bash -s" <<'REMOTE' \
    || fail 11 "Code-Update fehlgeschlagen (lokale Änderungen oder Netzwerk?)"
set -euo pipefail
app() { sudo -n -u "$APP_USER" "$@"; }
app git -C "$APP_DIR" fetch --quiet origin
if [[ -n "$(app git -C "$APP_DIR" status --porcelain)" ]]; then
    echo "Lokale Änderungen in $APP_DIR – Abbruch:" >&2
    app git -C "$APP_DIR" status --short >&2
    exit 1
fi
old=$(app git -C "$APP_DIR" rev-parse HEAD)
if [[ "$ROLLBACK" == 1 ]]; then
    new=$(app cat "$STATE_DIR/previous-commit")
else
    new=$TARGET_SHA
fi
app git -C "$APP_DIR" cat-file -e "$new^{commit}"
if [[ "$old" != "$new" ]]; then
    app git -C "$APP_DIR" checkout --quiet --detach "$new"
    echo "$old" | app tee "$STATE_DIR/previous-commit" >/dev/null
fi
echo "   $old -> $new"
echo "$old $new" | app tee "$STATE_DIR/.deploy-range" >/dev/null
REMOTE

step "3. Python-Abhängigkeiten (uv sync --frozen)"
rsh "sudo -n -u $APP_USER env HOME=$STATE_DIR UV_CACHE_DIR=$STATE_DIR/cache/uv UV_PYTHON_DOWNLOADS=never \
    nice -n 19 ionice -c3 uv sync --frozen --no-dev --project $APP_DIR" \
    || fail 11 "uv sync fehlgeschlagen"

# --- 4. Frontend ------------------------------------------------------------------------------
step "4. Frontend-Build"
build=$FORCE_FE
changed=$(rsh "APP_DIR=$APP_DIR APP_USER=$APP_USER STATE_DIR=$STATE_DIR bash -s" <<'REMOTE'
set -euo pipefail
read -r old new < <(sudo -n -u "$APP_USER" cat "$STATE_DIR/.deploy-range")
if [[ "$old" == "$new" ]]; then
    echo 0
else
    sudo -n -u "$APP_USER" git -C "$APP_DIR" diff --name-only "$old" "$new" -- frontend | wc -l
fi
REMOTE
)
have_dist=$(rsh "sudo -n -u $APP_USER test -f $APP_DIR/frontend/dist/index.html && echo 1 || echo 0")
if ((changed > 0 || have_dist == 0)); then build=1; fi
if ((build)); then
    echo "   baue Frontend (Änderungen in frontend/: $changed, dist vorhanden: $have_dist)"
    # NODE_OPTIONS begrenzt den Heap (2-GB-CT); Build läuft mit niedriger CPU-/IO-Priorität.
    rsh "sudo -n -u $APP_USER env HOME=$STATE_DIR npm_config_cache=$STATE_DIR/cache/npm \
        NODE_OPTIONS=--max-old-space-size=1024 bash -c 'cd $APP_DIR/frontend && \
        nice -n 19 ionice -c3 npm ci --no-audit --no-fund && nice -n 19 ionice -c3 npm run build'" \
        || fail 12 "Frontend-Build fehlgeschlagen (Speicher? dmesg | grep -i oom; ggf. Swap anlegen)"
else
    echo "   unverändert, übersprungen"
fi

# --- 5. Konfiguration und Migrationen ---------------------------------------------------------
step "5. Konfiguration prüfen, Sicherung, Migrationen"
EF="cd $APP_DIR && .venv/bin/edgefinder"
rsh "sudo -n -u $APP_USER bash -c '$EF check-config'" || fail 13 "check-config fehlgeschlagen"
rsh "sudo -n -u $APP_USER bash -c 'if [ -f $STATE_DIR/data/edgefinder.db ]; then $EF backup; fi'" \
    || fail 13 "DB-Sicherung vor Migration fehlgeschlagen"
rsh "sudo -n -u $APP_USER bash -c '$EF migrate'" || fail 13 "Migration fehlgeschlagen (Sicherung: $STATE_DIR/data/backups)"

# --- 6./7. systemd und Neustart ---------------------------------------------------------------
step "6. systemd-Units synchronisieren"
rsh "sudo -n env EDGEFINDER_APP_DIR=$APP_DIR bash $APP_DIR/deploy/sync-units.sh" || fail 14 "Unit-Sync fehlgeschlagen"
step "7. Neustart"
rsh "sudo -n systemctl restart edgefinder" || fail 14 "systemctl restart fehlgeschlagen"

# --- 8. Health-Check und Smoke-Test -----------------------------------------------------------
step "8. Health-Check (bis 30 s)"
ok=0
for _ in $(seq 1 30); do
    if rsh "curl -fsS --max-time 3 http://127.0.0.1:$PORT/api/health" 2>/dev/null | grep -q '"status":"ok"'; then
        ok=1; break
    fi
    sleep 1
done
((ok)) || fail 14 "/api/health antwortet nicht mit status ok"
echo "   ok"
step "Smoke-Test"
rsh "curl -fsS --max-time 10 http://127.0.0.1:$PORT/ | grep -qi '<div id=\"root\"'" \
    || fail 15 "Startseite lädt nicht (Frontend-Build fehlt? $APP_DIR/frontend/dist)"
echo "   Startseite ok"
count=$(rsh "curl -fsS --max-time 10 http://127.0.0.1:$PORT/api/assets | python3 -c 'import json,sys; print(len(json.load(sys.stdin)))'") \
    || fail 15 "/api/assets liefert keine gültige Antwort"
((count > 0)) || fail 15 "/api/assets ist leer (Scores noch nicht berechnet? sudo systemctl start edgefinder-score)"
echo "   /api/assets: $count Einträge"
printf '\nDeploy erfolgreich: %s\n' "$(rsh "sudo -n -u $APP_USER git -C $APP_DIR rev-parse --short HEAD")"
