#!/usr/bin/python3 -I
# ruff: noqa: E501, PTH100, PTH110, PTH119, PTH120
"""Claude-Code-Hook des Prüfagenten: lückenloses Protokoll und zweite Sperrschicht (Etappe q).

Aufruf durch Claude Code (PreToolUse/PostToolUse/Stop), Ereignis als JSON auf stdin. Jeder Aufruf wird
- als JSON-Zeile an `$CLAUDE_REVIEW_RUN_DIR/audit.jsonl` angehängt (Zeit, Ereignis, Werkzeug,
  Eingabe/Ergebnis gekürzt und geschwärzt, Entscheidung) und
- ins journald geschrieben (Kennung `claude-review`; der Benutzer kann Journal-Einträge nicht ändern).
PreToolUse prüft zusätzlich eine feste Positivliste (Werkzeuge, Pfade, Befehle) und antwortet bei
Verstößen mit `permissionDecision: deny`. Das ergänzt die Berechtigungen aus settings.json; die
eigentliche Abschottung leisten Benutzerrechte, systemd-Sandbox und Netzsperre.
Kann das Protokoll nicht geschrieben werden, wird der Werkzeugaufruf abgelehnt (fail closed).
"""

from __future__ import annotations

import json
import logging
import logging.handlers
import os
import re
import shlex
import sys
import time
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from scrub import scrub

MAX_FIELD = 600
MAX_LINE = 4000
APP_DIR = "/opt/claude-review"
READ_TOOLS = {"Read", "Grep", "Glob", "LS"}
WRITE_TOOLS = {"Write", "Edit", "MultiEdit"}
OTHER_ALLOWED = {"Bash", "TodoWrite"}
FORBIDDEN_WORDS = {
    "curl", "wget", "ssh", "scp", "sftp", "nc", "ncat", "netcat", "socat", "telnet", "ftp", "rsync",
    "sudo", "su", "doas", "systemctl", "journalctl", "apt", "apt-get", "dpkg", "pip", "pip3", "uv",
    "npm", "npx", "node", "git", "docker", "kill", "pkill", "chmod", "chown", "rm", "mv", "cp", "ln",
    "tee", "dd", "env", "bash", "sh", "python", "python3", "perl", "ruby", "xargs", "awk", "sed", "find",
}  # fmt: skip
SAFE_ABS = ("/dev/null",)


def run_dir() -> Path | None:
    value = os.environ.get("CLAUDE_REVIEW_RUN_DIR", "")
    return (
        Path(value) if re.fullmatch(r"/var/lib/claude-review/runs/[1-9][0-9]{0,8}", value) else None
    )


def trunc(value: object, limit: int = MAX_FIELD) -> str:
    text = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False, default=str)
    text = scrub(text)
    return text if len(text) <= limit else text[:limit] + f"… [+{len(text) - limit} Zeichen]"


def _inside(path: str, root: Path, cwd: Path) -> bool:
    if path.startswith("~"):
        return False
    try:
        resolved = (
            cwd / path
        ).resolve()  # absolute Pfade überschreiben cwd; Symlinks werden aufgelöst
        resolved.relative_to(root.resolve())
        return True
    except (ValueError, OSError):
        return False


def decide(event: dict, base: Path | None) -> tuple[str, str]:
    """('allow'|'deny', Grund) für einen PreToolUse-Aufruf nach fester Positivliste."""
    tool = str(event.get("tool_name", ""))
    data = event.get("tool_input") or {}
    if base is None:
        return "deny", "kein gültiges Lauf-Verzeichnis (CLAUDE_REVIEW_RUN_DIR)"
    if tool.startswith("mcp__") or (tool not in READ_TOOLS | WRITE_TOOLS | OTHER_ALLOWED):
        return "deny", f"Werkzeug {tool or '?'} nicht erlaubt"
    if tool in READ_TOOLS:
        for key in ("file_path", "path"):
            if key in data and not _inside(str(data[key]), base, base):
                return "deny", "Lesen nur im Lauf-Verzeichnis"
        return "allow", "Lesewerkzeug im Lauf-Verzeichnis"
    if tool in WRITE_TOOLS:
        target = str(data.get("file_path", ""))
        name = Path(target).name
        if not target or not _inside(target, base / "output", base):
            return "deny", "Schreiben nur nach output/"
        if not (name == "analysis.md" or re.fullmatch(r"proposal-[0-9]{1,3}\.diff", name)):
            return "deny", "in output/ sind nur analysis.md und proposal-N.diff erlaubt"
        return "allow", "Schreiben nach output/"
    if tool == "Bash":
        return _decide_bash(str(data.get("command", "")), base)
    return "allow", "ok"


def _decide_bash(command: str, base: Path) -> tuple[str, str]:
    if not command.strip() or len(command) > 2000:
        return "deny", "leerer oder zu langer Befehl"
    if re.search(r"[>`]|\$\(|\$\{|<\(|\n|;|(?<!&)&(?!&)", command):
        return (
            "deny",
            "Umleitung, Substitution, Semikolon, Hintergrund oder mehrere Zeilen nicht erlaubt",
        )
    try:
        tokens = shlex.split(command)
    except ValueError:
        return "deny", "Befehl nicht lesbar"
    segments, current = [], []
    for token in tokens:
        if token in {"|", "&&", "||"}:
            segments.append(current)
            current = []
        else:
            current.append(token)
    segments.append(current)
    for seg in segments:
        if not seg:
            return "deny", "leerer Befehlsteil"
        if os.path.basename(seg[0]) in FORBIDDEN_WORDS and seg[0] != f"{APP_DIR}/venv/bin/python":
            return "deny", f"Befehl {seg[0]} nicht erlaubt"
        if seg[0] == f"{APP_DIR}/venv/bin/python" and seg[1:3] not in (
            ["-m", "pytest"],
            ["-m", "ruff"],
            ["-m", "json.tool"],
        ):
            return "deny", "python nur als -m pytest, -m ruff oder -m json.tool"
        for token in seg:
            if token.startswith("~") or ".." in token.split("/"):
                return "deny", "Pfad mit ~ oder .. nicht erlaubt"
            if (
                token.startswith("/")
                and token not in SAFE_ABS
                and not (_inside(token, base, base) or token.startswith(f"{APP_DIR}/venv/bin/"))
            ):
                return "deny", "absoluter Pfad außerhalb des Lauf-Verzeichnisses"
    return "allow", "Befehl auf Positivliste"


def _syslog() -> logging.Logger | None:
    for address in ("/dev/log", "/run/systemd/journal/dev-log"):
        if os.path.exists(address):
            try:
                handler = logging.handlers.SysLogHandler(address=address)
            except OSError:
                continue
            handler.setFormatter(logging.Formatter("claude-review: %(message)s"))
            logger = logging.getLogger("claude-review-audit")
            logger.setLevel(logging.INFO)
            logger.handlers[:] = [handler]
            logger.propagate = False
            return logger
    return None


def record(event: dict, decision: str, reason: str, base: Path | None) -> dict:
    name = event.get("hook_event_name", "?")
    entry: dict = {
        "t": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "event": name,
        "tool": event.get("tool_name"),
        "session": str(event.get("session_id", ""))[:12],
    }
    if name == "PreToolUse":
        entry["input"] = trunc(event.get("tool_input", {}))
        entry["decision"] = decision
        entry["reason"] = reason
    elif name == "PostToolUse":
        entry["input"] = trunc(event.get("tool_input", {}), 300)
        entry["result"] = trunc(event.get("tool_response", ""))
    elif name == "Stop":
        entry["note"] = "Sitzung beendet"
    line = json.dumps(entry, ensure_ascii=False)
    if len(line) > MAX_LINE:
        entry = {k: (v[:200] if isinstance(v, str) else v) for k, v in entry.items()}
        line = json.dumps(entry, ensure_ascii=False)
    if base is not None:
        fd = os.open(
            base / "audit.jsonl", os.O_WRONLY | os.O_APPEND | os.O_CREAT | os.O_NOFOLLOW, 0o644
        )
        with os.fdopen(fd, "a", encoding="utf-8") as handle:
            handle.write(line + "\n")
    logger = _syslog()
    if logger is not None:
        logger.info(line)
    return entry


def main() -> int:
    try:
        event = json.load(sys.stdin)
        if not isinstance(event, dict):
            raise ValueError("kein Objekt")
    except ValueError:
        print("audit.py: Ereignis nicht lesbar", file=sys.stderr)
        return 0
    base = run_dir()
    decision, reason = ("allow", "")
    if event.get("hook_event_name") == "PreToolUse":
        decision, reason = decide(event, base)
    try:
        record(event, decision, reason, base)
    except OSError as exc:
        if event.get("hook_event_name") == "PreToolUse":
            decision, reason = "deny", f"Protokoll nicht schreibbar ({type(exc).__name__})"
    if event.get("hook_event_name") == "PreToolUse" and decision == "deny":
        print(
            json.dumps(
                {
                    "hookSpecificOutput": {
                        "hookEventName": "PreToolUse",
                        "permissionDecision": "deny",
                        "permissionDecisionReason": f"Prüfagent: {reason}",
                    }
                },
                ensure_ascii=False,
            )
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
