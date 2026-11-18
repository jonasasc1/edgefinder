#!/usr/bin/env bash
# Ersteinrichtung von „trading“ (Debian 13) für edgefinder.
#
# Läuft auf trading als User `claude` (sudo wird intern benutzt), idempotent: ein zweiter Lauf
# ändert nichts, was schon stimmt. Zuerst IMMER `--dry-run` ansehen.
#
#   deploy/install.sh --dry-run            zeigt nur, was getan würde (ändert nichts)
#   deploy/install.sh                      richtet alles ein, außer der Firewall
#   deploy/install.sh --apply-firewall     zusätzlich nftables-Regeln aktivieren (Lockout-Risiko!)
#
# Voraussetzung: das Verzeichnis deploy/ liegt auf trading (z. B. `scp -r deploy trading:~/`),
# weil der App-Checkout erst in Abschnitt 6 entsteht. Keine Secrets in diesem Skript: die echte
# .env legt Jonas selbst an, das Skript prüft nur Existenz und Rechte.
set -euo pipefail

# --- Festlegungen (müssen zu deploy/systemd/*.service und config.yaml passen) -------------------
APP_USER=edgefinder
APP_DIR=/opt/edgefinder
STATE_DIR=/var/lib/edgefinder          # Daten (data/), Cache, Deploy-Key; einziger schreibbarer Pfad
REPO_URL=git@github.com:jonasasc1/edgefinder.git
BRANCH=main
UV_VERSION=0.13.4
UV_SHA256=2b428396f12572d4429cf210ca234dd599a33b3af0958a4d5ed569d63e3f344f   # x86_64-unknown-linux-gnu
UV_URL=https://github.com/astral-sh/uv/releases/download/${UV_VERSION}/uv-x86_64-unknown-linux-gnu.tar.gz
NODE_VERSION=22.23.5                   # LTS „Jod“; vite 8 braucht Node >= 20.19 bzw. 22.12
NODE_SHA256=cdeb8670a0c81f51b4dc4ac61919f9b1ad917b304bf8221eb939570663d240f8   # linux-x64.tar.xz
NODE_URL=https://nodejs.org/dist/v${NODE_VERSION}/node-v${NODE_VERSION}-linux-x64.tar.xz
# Host-Key von github.com (offiziell veröffentlicht, docs.github.com „SSH key fingerprints“)
GITHUB_HOSTKEY='github.com ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIOMqqnkVzrm0SdG6UOoqKLsabgH5C9okWi0dh2l9GKJl'
GITHUB_FPR='SHA256:+DiY3wvvV6TuJJhbpZisF/zLDA0zPMSvHdkr4UvCOqU'
FW_PORT=8420
SSH_DIR=$STATE_DIR/.ssh
DEPLOY_KEY=$SSH_DIR/deploy_key
# ------------------------------------------------------------------------------------------------
# Warum Node aus dem offiziellen Tarball (nodejs.org, gepinnt + SHA-256) statt apt/NodeSource?
#  - Debian 13 liefert nodejs 20.x (nahe an der vite-Untergrenze, kurz vor EOL).
#  - Das NodeSource-Repo hieße: Fremd-Repo + Signaturschlüssel + `curl | bash`-Setup-Skript.
#  - Der Tarball ist reproduzierbar, belegt nach dem Build keine Dienste und ist per Prüfsumme
#    abgesichert. Node wird nur für den Frontend-Build gebraucht, nicht im Betrieb.

DRY=0
APPLY_FW=0
SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)

usage() { sed -n '2,12p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'; }
for arg in "$@"; do
    case "$arg" in
        --dry-run) DRY=1 ;;
        --apply-firewall) APPLY_FW=1 ;;
        -h|--help) usage; exit 0 ;;
        *) echo "Unbekannte Option: $arg" >&2; usage >&2; exit 2 ;;
    esac
done

SUDO=""
[[ $EUID -eq 0 ]] || SUDO="sudo"

section() { printf '\n== %s ==\n' "$*"; }
info() { printf '   %s\n' "$*"; }
die() { printf 'FEHLER: %s\n' "$*" >&2; exit 1; }

# Führt einen Befehl aus (oder zeigt ihn im Dry-Run nur an).
run() {
    if ((DRY)); then printf '   [dry-run] %s\n' "$(printf '%q ' "$@")"; else "$@"; fi
}
as_app() { $SUDO -u "$APP_USER" "$@"; }
# Lesende Prüfungen laufen auch im Dry-Run (ändern nichts).
git_ssh() { echo "ssh -i $DEPLOY_KEY -o IdentitiesOnly=yes -o UserKnownHostsFile=$SSH_DIR/known_hosts -o StrictHostKeyChecking=yes"; }

# --- 1. Voraussetzungen ----------------------------------------------------------------------
section "1. Voraussetzungen prüfen"
[[ "$(uname -m)" == x86_64 ]] || die "Nur x86_64 vorgesehen (uv-/Node-Prüfsummen sind dafür gepinnt)."
if [[ -r /etc/os-release ]] && ! grep -q '^VERSION_ID="13"' /etc/os-release; then
    info "WARNUNG: kein Debian 13 – Paketnamen/Python-Version prüfen."
fi
if ((!DRY)); then
    $SUDO -n true 2>/dev/null || die "sudo ohne Passwort nötig (User claude)."
fi
info "ok (Dry-Run: $DRY)"

# --- 2. apt-Pakete ---------------------------------------------------------------------------
section "2. apt-Pakete"
PKGS=(git python3 curl ca-certificates openssh-client xz-utils util-linux sqlite3)
missing=()
for pkg in "${PKGS[@]}"; do
    dpkg -s "$pkg" >/dev/null 2>&1 || missing+=("$pkg")
done
if ((${#missing[@]})); then
    info "fehlend: ${missing[*]}"
    run $SUDO apt-get update
    run $SUDO apt-get install -y --no-install-recommends "${missing[@]}"
else
    info "alle vorhanden: ${PKGS[*]}"
fi
if command -v python3.13 >/dev/null 2>&1; then
    info "Python: $(python3.13 --version)"
else
    ((DRY)) && info "python3.13 (noch) nicht gefunden – nach apt prüfen" || die "python3.13 fehlt (pyproject verlangt 3.13; uv lädt nichts herunter)."
fi

# --- 3. uv und Node (Tarball, Prüfsumme) ------------------------------------------------------
section "3. uv ${UV_VERSION} und Node ${NODE_VERSION}"
tmp=""
cleanup() { [[ -n "$tmp" ]] && rm -rf "$tmp"; return 0; }
trap cleanup EXIT
if [[ "$(uv --version 2>/dev/null || true)" == "uv ${UV_VERSION}"* ]]; then
    info "uv ${UV_VERSION} bereits installiert"
else
    info "uv nach /usr/local/bin (SHA-256 ${UV_SHA256:0:16}…)"
    if ((!DRY)); then
        tmp=$(mktemp -d)
        curl -fsSL --proto '=https' -o "$tmp/uv.tar.gz" "$UV_URL"
        echo "$UV_SHA256  $tmp/uv.tar.gz" | sha256sum -c - >/dev/null || die "uv: Prüfsumme stimmt nicht"
        tar -xzf "$tmp/uv.tar.gz" -C "$tmp"
        $SUDO install -m 0755 "$tmp"/uv-*/uv "$tmp"/uv-*/uvx /usr/local/bin/
    else
        info "[dry-run] herunterladen: $UV_URL, Prüfsumme, installieren nach /usr/local/bin/{uv,uvx}"
    fi
fi
NODE_HOME=/opt/node-v${NODE_VERSION}
if [[ "$(node --version 2>/dev/null || true)" == "v${NODE_VERSION}" ]]; then
    info "Node v${NODE_VERSION} bereits installiert"
else
    info "Node nach ${NODE_HOME} (SHA-256 ${NODE_SHA256:0:16}…), Links in /usr/local/bin"
    if ((!DRY)); then
        tmp=$(mktemp -d)
        curl -fsSL --proto '=https' -o "$tmp/node.tar.xz" "$NODE_URL"
        echo "$NODE_SHA256  $tmp/node.tar.xz" | sha256sum -c - >/dev/null || die "Node: Prüfsumme stimmt nicht"
        $SUDO mkdir -p "$NODE_HOME"
        $SUDO tar -xJf "$tmp/node.tar.xz" -C "$NODE_HOME" --strip-components=1
        for bin in node npm npx; do $SUDO ln -sfn "$NODE_HOME/bin/$bin" "/usr/local/bin/$bin"; done
    else
        info "[dry-run] herunterladen: $NODE_URL, Prüfsumme, entpacken, Links node/npm/npx"
    fi
fi

# --- 4. System-User ---------------------------------------------------------------------------
section "4. System-User ${APP_USER}"
if id "$APP_USER" >/dev/null 2>&1; then
    info "User existiert bereits ($(getent passwd "$APP_USER" | cut -d: -f6,7))"
else
    run $SUDO useradd --system --user-group --home-dir "$APP_DIR" --no-create-home \
        --shell /usr/sbin/nologin --comment "edgefinder (Dienstkonto)" "$APP_USER"
    info "Kein Passwort gesetzt (Systemkonto, gesperrt), Shell nologin."
fi

# --- 5. Verzeichnisse -------------------------------------------------------------------------
section "5. Verzeichnisse"
# App-Code: ${APP_DIR}. Daten: ${STATE_DIR}/data (DB, raw/); config.yaml verwendet den
# relativen Pfad data/…, daher ein Link ${APP_DIR}/data -> ${STATE_DIR}/data (Abschnitt 6).
for spec in "$APP_DIR:0750" "$STATE_DIR:0750" "$STATE_DIR/data:0750" "$STATE_DIR/data/raw:0750" \
    "$STATE_DIR/cache:0750" "$SSH_DIR:0700"; do
    dir=${spec%%:*}; mode=${spec##*:}
    if [[ -d "$dir" ]] && [[ "$(stat -c '%U %a' "$dir")" == "$APP_USER ${mode#0}" ]]; then
        info "ok: $dir"
    else
        run $SUDO install -d -m "$mode" -o "$APP_USER" -g "$APP_USER" "$dir"
    fi
done

# --- 6. Deploy-Key und Repo-Klon --------------------------------------------------------------
section "6. Deploy-Key (read-only) und Klon"
known_ok=0
if $SUDO test -f "$SSH_DIR/known_hosts" 2>/dev/null; then
    ssh-keygen -lf <(echo "$GITHUB_HOSTKEY") | grep -q "$GITHUB_FPR" || die "Pinned Host-Key passt nicht zur Prüfsumme"
    $SUDO grep -qF "$GITHUB_HOSTKEY" "$SSH_DIR/known_hosts" && known_ok=1
fi
if ((known_ok)); then
    info "known_hosts enthält den GitHub-Host-Key"
else
    info "GitHub-Host-Key (${GITHUB_FPR}) in $SSH_DIR/known_hosts eintragen"
    if ((!DRY)); then
        ssh-keygen -lf <(echo "$GITHUB_HOSTKEY") | grep -q "$GITHUB_FPR" || die "Host-Key ≠ Fingerprint"
        echo "$GITHUB_HOSTKEY" | as_app tee -a "$SSH_DIR/known_hosts" >/dev/null
    fi
fi
if $SUDO test -f "$DEPLOY_KEY" 2>/dev/null; then
    info "Deploy-Key vorhanden: $DEPLOY_KEY"
else
    info "ed25519-Schlüssel ohne Passphrase erzeugen ($DEPLOY_KEY)"
    run as_app ssh-keygen -t ed25519 -N '' -C "edgefinder-deploy@trading" -f "$DEPLOY_KEY"
fi
if ((!DRY)); then
    if ! as_app env GIT_SSH_COMMAND="$(git_ssh)" git ls-remote "$REPO_URL" HEAD >/dev/null 2>&1; then
        echo
        echo "GitHub lehnt den Schlüssel noch ab. Bitte als READ-ONLY Deploy-Key eintragen:"
        echo "  https://github.com/jonasasc1/edgefinder/settings/keys  (Add deploy key, 'Allow write access' AUS)"
        echo
        $SUDO cat "$DEPLOY_KEY.pub"
        echo
        echo "Danach install.sh erneut starten (Exit-Code 3 = wartet auf Deploy-Key)."
        exit 3
    fi
    info "GitHub-Zugriff mit Deploy-Key ok"
fi
if $SUDO test -d "$APP_DIR/.git" 2>/dev/null; then
    info "Checkout vorhanden: $APP_DIR"
else
    if [[ -n "$($SUDO ls -A "$APP_DIR" 2>/dev/null || true)" ]]; then
        # Nicht leer (z. B. schon angelegte .env oder ~/.local des Users): einchecken statt klonen.
        # `checkout` bricht ab, statt vorhandene Dateien zu überschreiben; .env bleibt unangetastet.
        info "$APP_DIR enthält schon Dateien – Checkout an Ort und Stelle (nichts wird überschrieben)"
        run as_app git -C "$APP_DIR" init -q -b "$BRANCH"
        run as_app git -C "$APP_DIR" remote add origin "$REPO_URL"
        run as_app git -C "$APP_DIR" config core.sshCommand "$(git_ssh)"
        run as_app git -C "$APP_DIR" fetch -q origin "$BRANCH"
        run as_app git -C "$APP_DIR" checkout -q -B "$BRANCH" "origin/$BRANCH"
        run as_app git -C "$APP_DIR" branch -q --set-upstream-to="origin/$BRANCH" "$BRANCH"
    else
        run as_app env GIT_SSH_COMMAND="$(git_ssh)" git clone --branch "$BRANCH" "$REPO_URL" "$APP_DIR"
        run as_app git -C "$APP_DIR" config core.sshCommand "$(git_ssh)"
    fi
fi
if [[ -L "$APP_DIR/data" ]]; then
    info "Link ok: $APP_DIR/data -> $(readlink "$APP_DIR/data")"
elif [[ -e "$APP_DIR/data" ]]; then
    die "$APP_DIR/data existiert und ist kein Link – bitte manuell prüfen."
else
    run as_app ln -s "$STATE_DIR/data" "$APP_DIR/data"
fi
# Der Link ist für Git „untracked“; ältere Stände ignorierten nur `data/`. Lokal ausschließen, damit deploy.sh nicht abbricht.
if $SUDO test -d "$APP_DIR/.git" 2>/dev/null; then
    run as_app sh -c "grep -qx data \"$APP_DIR/.git/info/exclude\" || echo data >> \"$APP_DIR/.git/info/exclude\""
fi

# --- 7. .env (nur prüfen!) --------------------------------------------------------------------
section "7. .env prüfen (Inhalt wird nie gelesen)"
ENV_FILE=$APP_DIR/.env
if $SUDO test -f "$ENV_FILE" 2>/dev/null; then
    perms=$($SUDO stat -c '%U %a' "$ENV_FILE")
    if [[ "$perms" == "$APP_USER 600" ]]; then
        info "ok: $ENV_FILE ($perms)"
    else
        info "WARNUNG: $ENV_FILE hat '$perms', erwartet '$APP_USER 600'. Korrektur:"
        info "  sudo chown $APP_USER:$APP_USER $ENV_FILE && sudo chmod 600 $ENV_FILE"
    fi
else
    info "FEHLT: $ENV_FILE – bitte selbst anlegen (Vorlage: $APP_DIR/.env.example):"
    info "  sudo -u $APP_USER install -m 600 /dev/null $ENV_FILE && sudo -u $APP_USER nano $ENV_FILE"
fi

# --- 8. systemd-Units und Timer ---------------------------------------------------------------
section "8. systemd-Units und Timer (aus $APP_DIR/deploy/systemd)"
info "Units werden aktiviert, aber nicht gestartet (erst nach dem ersten deploy.sh)."
if $SUDO test -d "$APP_DIR/deploy/systemd" 2>/dev/null; then
    run $SUDO env EDGEFINDER_APP_DIR="$APP_DIR" bash "$APP_DIR/deploy/sync-units.sh" --no-start
else
    info "Checkout fehlt (Dry-Run?) – Schritt wird nach dem Klon ausgeführt."
fi
# sudoers: nicht nötig – `claude` behält vollen sudo (Entscheidung Jonas, 2026-11-12).
# Postfix (Empfehlung, hier bewusst NICHT geändert): falls trading keine Mails senden muss,
#   `sudo systemctl disable --now postfix` bzw. nur an 127.0.0.1 lauschen lassen (inet_interfaces).

# --- 9. Firewall (nftables) -------------------------------------------------------------------
section "9. Firewall (nftables)"
FW_SRC=$SCRIPT_DIR/nftables.conf
[[ -f "$FW_SRC" ]] || die "nftables.conf nicht gefunden: $FW_SRC"
cfg_port=$(sed -n 's/^  port: *\([0-9][0-9]*\).*/\1/p' "$APP_DIR/config.yaml" 2>/dev/null | head -1 || true)
if [[ -n "${cfg_port:-}" && "$cfg_port" != "$FW_PORT" ]]; then
    die "server.port in config.yaml ($cfg_port) ≠ Port in nftables.conf ($FW_PORT)"
fi
info "Regeln aus $FW_SRC (8420 nur von 10.10.20.20, SSH nur von 10.10.20.90, Rest eingehend drop):"
sed 's/^/     | /' "$FW_SRC"
info "Hinweis: Die Proxmox-Firewall auf CT-Ebene (CT 122) gilt unabhängig; beide Regelwerke müssen passen."
if ((!APPLY_FW)); then
    info "Nicht aktiviert. Aktivieren mit: deploy/install.sh --apply-firewall"
else
    [[ -t 0 ]] || die "--apply-firewall braucht ein Terminal (Bestätigung gegen Lockout)."
    run $SUDO apt-get install -y --no-install-recommends nftables
    if ((DRY)); then
        info "[dry-run] nft -c -f $FW_SRC; laden; 60-s-Rollback-Timer; Bestätigung; dauerhaft in /etc/nftables.d/"
    else
        $SUDO nft -c -f "$FW_SRC" || die "Syntaxcheck fehlgeschlagen – nichts geändert."
        info "Syntax ok. Rollback: Tabelle entfernen mit 'sudo nft delete table inet edgefinder_fw'."
        $SUDO systemd-run --unit=edgefinder-fw-rollback --on-active=60 \
            /usr/sbin/nft delete table inet edgefinder_fw >/dev/null
        $SUDO nft -f "$FW_SRC"
        info "Regeln AKTIV. Prüfe jetzt in einer zweiten SSH-Sitzung, dass der Login von 10.10.20.90 geht."
        if read -r -t 60 -p "   SSH ok? Mit 'ja' bestätigen (60 s, sonst automatischer Rollback): " answer \
            && [[ "$answer" == ja ]]; then
            $SUDO systemctl stop edgefinder-fw-rollback.timer
            $SUDO install -d -m 0755 /etc/nftables.d
            $SUDO install -m 0644 "$FW_SRC" /etc/nftables.d/edgefinder.nft
            if ! $SUDO grep -qF '/etc/nftables.d/*.nft' /etc/nftables.conf 2>/dev/null; then
                $SUDO cp -a /etc/nftables.conf /etc/nftables.conf.bak-edgefinder 2>/dev/null || true
                echo 'include "/etc/nftables.d/*.nft"' | $SUDO tee -a /etc/nftables.conf >/dev/null
            fi
            $SUDO systemctl enable nftables.service >/dev/null
            info "Firewall bestätigt und dauerhaft (Backup: /etc/nftables.conf.bak-edgefinder)."
        else
            echo; info "Keine Bestätigung – der Rollback-Timer entfernt die Regeln in Kürze."
            exit 4
        fi
    fi
fi

# --- Ende -------------------------------------------------------------------------------------
section "Fertig"
info "Nächste Schritte: (1) .env anlegen (Abschnitt 7), (2) auf der Agent-VM: deploy/deploy.sh"
((DRY)) && info "Das war ein Dry-Run: nichts wurde verändert."
exit 0
