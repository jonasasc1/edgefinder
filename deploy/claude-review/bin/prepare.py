#!/usr/bin/python3 -I
# ruff: noqa: PTH101
"""Läuft als root (`ExecStartPre=+`) vor dem Prüfagenten (Etappe q).

Nimmt die älteste gültige Anforderung aus der Inbox, prüft alles streng, ergänzt das Eingabepaket um
den geschwärzten journald-Auszug, legt `output/` und die Protokolldateien für den Benutzer
claude-review an und schreibt die Lauf-ID nach /run/claude-review/current. Ohne Anforderung: Exit 0,
nichts zu tun. Eingaben sind nur Zahlen aus validierten Dateinamen; es gibt keine Shell.
"""

from __future__ import annotations

import grp
import json
import os
import pwd
import re
import stat
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "hooks"))
from scrub import scrub

BASE = Path(os.environ.get("CLAUDE_REVIEW_BASE", "/var/lib/claude-review"))
RUNTIME = Path(os.environ.get("CLAUDE_REVIEW_RUNTIME", "/run/claude-review"))
APP_USER, AGENT_USER = "edgefinder", "claude-review"
NAME_RE = re.compile(r"^([1-9][0-9]{0,8})\.json$")
JOURNAL_MAX = 1_500_000
UNITS = ["-u", "edgefinder.service", "-u", "edgefinder-*"]


def log(message: str) -> None:
    print(f"prepare: {message}", flush=True)


def pick_request(inbox: Path) -> tuple[int, Path] | None:
    found = []
    try:
        entries = list(os.scandir(inbox))
    except OSError:
        return None
    for entry in entries:
        match = NAME_RE.match(entry.name)
        if match and entry.is_file(follow_symlinks=False):
            found.append((int(match.group(1)), Path(entry.path)))
    return min(found) if found else None


def read_request(path: Path, run_id: int) -> dict | None:
    try:
        if path.stat().st_size > 4096:
            return None
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if not isinstance(data, dict) or data.get("id") != run_id:
        return None
    ranges = {"max_turns": (1, 200), "runtime_max_seconds": (60, 7200), "journal_hours": (1, 168)}
    for key, (low, high) in ranges.items():
        value = data.get(key)
        if not isinstance(value, int) or isinstance(value, bool) or not low <= value <= high:
            return None
    return data


def journal_text(hours: int) -> str:
    cmd = [
        "/usr/bin/journalctl",
        *UNITS,
        "--since",
        f"-{int(hours)}h",
        "-o",
        "short-iso",
        "--no-pager",
        "-q",
    ]
    try:
        out = subprocess.run(cmd, capture_output=True, text=True, timeout=60, check=False)  # noqa: S603
        text = out.stdout
    except (OSError, subprocess.SubprocessError) as exc:
        return f"(journalctl nicht verfügbar: {type(exc).__name__})\n"
    text = scrub(text)
    if len(text) > JOURNAL_MAX:
        text = "[… gekürzt, nur das Ende …]\n" + text[-JOURNAL_MAX:]
    return text or "(keine Einträge im Zeitraum)\n"


def create(path: Path, content: bytes, uid: int, gid: int, mode: int) -> None:
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, mode)
    with os.fdopen(fd, "wb") as handle:
        handle.write(content)
    os.chown(path, uid, gid)
    os.chmod(path, mode)


def main() -> int:
    app_uid = pwd.getpwnam(APP_USER).pw_uid
    agent_uid = pwd.getpwnam(AGENT_USER).pw_uid
    agent_gid = grp.getgrnam(AGENT_USER).gr_gid
    inbox = BASE / "inbox"
    picked = pick_request(inbox)
    if picked is None:
        log("keine Anforderung")
        return 0
    run_id, request_file = picked
    base = BASE / "runs" / str(run_id)
    try:
        info = base.lstat()
        valid = (
            stat.S_ISDIR(info.st_mode)
            and info.st_uid == app_uid
            and (base / "input").is_dir()
            and not (base / "input").is_symlink()
            and not (base / "status.json").exists()
            and not (base / "output").exists()
        )
    except OSError:
        valid = False
    request = read_request(request_file, run_id) if valid else None
    if request is None:
        log(f"Anforderung {run_id} verworfen (ungültig oder schon bearbeitet)")
        request_file.unlink(missing_ok=True)
        return 0
    started = time.strftime("%Y-%m-%dT%H:%M:%S+00:00", time.gmtime())
    try:
        create(
            base / "input" / "journal.txt",
            journal_text(request["journal_hours"]).encode(),
            app_uid,
            agent_gid,
            0o640,
        )
        out = base / "output"
        out.mkdir(mode=0o2770)
        os.chown(out, app_uid, agent_gid)
        out.chmod(0o2770)
        status = {"state": "running", "started_at": started}
        create(base / "status.json", json.dumps(status).encode(), agent_uid, agent_gid, 0o644)
        for name in ("audit.jsonl", "transcript.jsonl", "claude.stderr"):
            create(base / name, b"", agent_uid, agent_gid, 0o644)
        RUNTIME.mkdir(parents=True, exist_ok=True)
        create_current = RUNTIME / "current"
        create_current.unlink(missing_ok=True)
        create(create_current, f"{run_id}\n".encode(), 0, 0, 0o644)
    except (OSError, KeyError) as exc:
        log(f"Vorbereitung von {run_id} fehlgeschlagen: {type(exc).__name__}: {exc}")
        request_file.unlink(missing_ok=True)
        return 1
    request_file.unlink(missing_ok=True)
    log(f"Lauf {run_id} vorbereitet")
    return 0


if __name__ == "__main__":
    sys.exit(main())
