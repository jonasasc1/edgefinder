#!/usr/bin/env bash
# Kopiert die systemd-Units aus dem Checkout nach /etc/systemd/system und aktiviert die Timer.
# Läuft auf „trading“ als root (sudo); wird von install.sh und deploy.sh aufgerufen.
#   sync-units.sh [--no-start]   --no-start: Units aktivieren, aber nichts starten
set -euo pipefail

SRC="${EDGEFINDER_APP_DIR:-/opt/edgefinder}/deploy/systemd"
DST=/etc/systemd/system
START=--now
[[ "${1:-}" == "--no-start" ]] && START=""

[[ $EUID -eq 0 ]] || { echo "Muss als root laufen (sudo)." >&2; exit 1; }
[[ -d "$SRC" ]] || { echo "Nicht gefunden: $SRC" >&2; exit 1; }

changed=0
for file in "$SRC"/edgefinder*; do
    name=$(basename "$file")
    if ! cmp -s "$file" "$DST/$name"; then
        install -m 0644 -o root -g root "$file" "$DST/$name"
        echo "Unit aktualisiert: $name"
        changed=1
    fi
done
# Veraltete edgefinder-Units (z. B. Quelle in config.yaml deaktiviert) entfernen
for old in "$DST"/edgefinder*.timer "$DST"/edgefinder*.service; do
    [[ -e "$old" ]] || continue
    name=$(basename "$old")
    if [[ ! -e "$SRC/$name" ]]; then
        systemctl disable --now "$name" 2>/dev/null || true
        rm -f "$old"
        echo "Unit entfernt: $name"
        changed=1
    fi
done
((changed)) && systemctl daemon-reload

systemctl enable edgefinder.service >/dev/null
for timer in "$SRC"/edgefinder*.timer; do
    # shellcheck disable=SC2086
    systemctl enable $START "$(basename "$timer")" >/dev/null
done
echo "Units synchronisiert (geändert: $changed)."
