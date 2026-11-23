#!/usr/bin/python3 -I
# ruff: noqa: E501, PTH
"""Hilfen für run.sh (als claude-review): Parameter lesen, Transkript schwärzen, Status schreiben.

finish.py params <run-dir>                  gibt `max_turns runtime_max_seconds` aus (validierte Zahlen)
finish.py tee <transcript.jsonl>            stdin → geschwärzt an die Datei (und nach stdout kurz)
finish.py finalize <run-dir> <exit> <start-epoch>   status.json aus Exit-Code und Transkript
"""

from __future__ import annotations

import json
import os
import re
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "hooks"))
from scrub import scrub

RUN_RE = re.compile(r"^/var/lib/claude-review/runs/[1-9][0-9]{0,8}$")


def check_dir(value: str) -> Path:
    base = os.environ.get("CLAUDE_REVIEW_BASE")
    if base:  # nur für Tests
        return Path(value)
    if not RUN_RE.match(value):
        raise SystemExit("ungültiges Lauf-Verzeichnis")
    return Path(value)


def cmd_params(run: Path) -> int:
    data = json.loads((run / "request.json").read_text(encoding="utf-8"))
    turns, runtime = data["max_turns"], data["runtime_max_seconds"]
    if not (
        isinstance(turns, int)
        and 1 <= turns <= 200
        and isinstance(runtime, int)
        and 60 <= runtime <= 7200
    ):
        raise SystemExit("ungültige Parameter")
    print(turns, runtime)
    return 0


def cmd_tee(target: Path) -> int:
    with target.open("a", encoding="utf-8") as handle:
        for line in sys.stdin:
            handle.write(scrub(line.rstrip("\n")) + "\n")
            handle.flush()
    return 0


def _result_line(transcript: Path) -> dict:
    result: dict = {}
    try:
        for line in transcript.read_text(encoding="utf-8", errors="replace").splitlines():
            try:
                item = json.loads(line)
            except ValueError:
                continue
            if isinstance(item, dict) and item.get("type") == "result":
                result = item
    except OSError:
        pass
    return result


def cmd_finalize(run: Path, exit_code: int, start: int) -> int:
    now = int(time.time())
    result = _result_line(run / "transcript.jsonl")
    state = "ok"
    message = None
    if exit_code == 124:
        state, message = "timeout", "Zeitlimit erreicht (RuntimeMaxSec)"
    elif exit_code != 0 or result.get("is_error"):
        state = "error"
        message = scrub(str(result.get("result") or f"claude beendete mit Exit-Code {exit_code}"))[
            :300
        ]
    elif not (run / "output" / "analysis.md").is_file():
        state, message = "error", "Keine analysis.md erzeugt"
    status = {
        "state": state,
        "started_at": time.strftime("%Y-%m-%dT%H:%M:%S+00:00", time.gmtime(start)),
        "finished_at": time.strftime("%Y-%m-%dT%H:%M:%S+00:00", time.gmtime(now)),
        "duration_seconds": now - start,
        "exit_code": exit_code,
    }
    if isinstance(result.get("num_turns"), int):
        status["turns"] = result["num_turns"]
    if isinstance(result.get("total_cost_usd"), int | float):
        status["cost_usd"] = round(
            float(result["total_cost_usd"]), 4
        )  # nur Angabe, Abo-Läufe kosten nichts extra
    if message:
        status["message"] = message
    (run / "status.json").write_text(
        json.dumps(status, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    print(
        f"finish: Lauf {run.name} {state} (Exit {exit_code}, {status['duration_seconds']} s, Turns {status.get('turns', '?')})"
    )
    return 0


def main(argv: list[str]) -> int:
    if len(argv) >= 3 and argv[1] == "params":
        return cmd_params(check_dir(argv[2]))
    if len(argv) == 3 and argv[1] == "tee":
        return cmd_tee(Path(argv[2]))
    if len(argv) == 5 and argv[1] == "finalize" and argv[3].isdigit() and argv[4].isdigit():
        return cmd_finalize(check_dir(argv[2]), int(argv[3]), int(argv[4]))
    print(__doc__, file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv))
