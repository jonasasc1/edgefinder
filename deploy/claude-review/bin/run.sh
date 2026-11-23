#!/usr/bin/env bash
# Startet den Claude-Prüfagenten für die von prepare.py vorbereitete Anforderung (als User claude-review).
# Keine Shell-Eingaben von außen: die Lauf-ID kommt aus /run/claude-review/current und wird als reine Zahl
# validiert; alle Parameter stammen aus validierten Zahlen. Das Transkript wird geschwärzt abgelegt.
set -euo pipefail
umask 0022

BASE=${CLAUDE_REVIEW_BASE:-/var/lib/claude-review}
APP=${CLAUDE_REVIEW_APP:-/opt/claude-review}
CURRENT=${CLAUDE_REVIEW_RUNTIME:-/run/claude-review}/current
PYTHON=/usr/bin/python3

[[ -f "$CURRENT" && ! -L "$CURRENT" ]] || { echo "run: keine vorbereitete Anforderung"; exit 0; }
ID=$(head -c 12 "$CURRENT" | tr -d '\n')
[[ "$ID" =~ ^[1-9][0-9]{0,8}$ ]] || { echo "run: ungültige Lauf-ID" >&2; exit 2; }
RUN="$BASE/runs/$ID"
[[ -d "$RUN" && ! -L "$RUN" && -d "$RUN/input" && -d "$RUN/output" ]] || { echo "run: Lauf-Verzeichnis fehlt" >&2; exit 2; }

FINALIZED=0
on_exit() {
    # Bricht das Skript vor dem normalen Ende ab, trotzdem einen Endstatus schreiben
    if ((!FINALIZED)) && [[ -n "${RUN:-}" ]]; then
        "$PYTHON" -I "$APP/bin/finish.py" finalize "$RUN" 1 "${START:-$(date +%s)}" || true
    fi
}
trap on_exit EXIT

read -r MAX_TURNS RUNTIME < <("$PYTHON" -I "$APP/bin/finish.py" params "$RUN")
START=$(date +%s)
cd "$RUN"

# Umgebung: nur lokaler Proxy, keine Telemetrie, kein Auto-Update, kein Gedächtnis
export HOME="$BASE"
export PATH="$APP/venv/bin:/usr/bin:/bin"
export HTTPS_PROXY=http://127.0.0.1:8888 HTTP_PROXY=http://127.0.0.1:8888 NO_PROXY=127.0.0.1,localhost
export https_proxy=$HTTPS_PROXY http_proxy=$HTTP_PROXY no_proxy=$NO_PROXY
export CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC=1 DISABLE_TELEMETRY=1 DISABLE_ERROR_REPORTING=1
export DISABLE_AUTOUPDATER=1 CLAUDE_CODE_DISABLE_AUTO_MEMORY=1 ENABLE_CLAUDEAI_MCP_SERVERS=false
export CLAUDE_CODE_DISABLE_CLAUDE_MDS=1
export CLAUDE_REVIEW_RUN_DIR="$RUN" PYTHONDONTWRITEBYTECODE=1 PYTHONPATH="$RUN/input/snapshot/backend"

echo "run: Lauf $ID startet (max. $MAX_TURNS Turns, $RUNTIME s)"
set +e
timeout --signal=TERM --kill-after=20 "$((RUNTIME - 60))" \
    "$APP/node_modules/.bin/claude" -p "$(cat "$APP/PROMPT.md")" \
        --output-format stream-json --verbose --max-turns "$MAX_TURNS" \
        --settings "$APP/settings.json" --strict-mcp-config --disable-slash-commands \
        --no-session-persistence </dev/null 2> >("$PYTHON" -I "$APP/bin/finish.py" tee "$RUN/claude.stderr") \
    | "$PYTHON" -I "$APP/bin/finish.py" tee "$RUN/transcript.jsonl"
CODE=${PIPESTATUS[0]}
wait   # Protokoll-Prozess für stderr (Prozess-Substitution) zu Ende schreiben lassen
set -e
FINALIZED=1
"$PYTHON" -I "$APP/bin/finish.py" finalize "$RUN" "$CODE" "$START"
exit 0
