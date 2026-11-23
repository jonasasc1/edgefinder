#!/usr/bin/python3 -I
# ruff: noqa: E501, SIM105
"""Läuft als root (`ExecStartPre=+`) vor dem Prüfagenten (Etappe q).

Nimmt die älteste gültige Anforderung aus der Inbox, prüft alles streng, übernimmt das vom Web-Benutzer
(edgefinder) in `staging/<id>/input` gebaute Eingabepaket als root nach `runs/<id>/input`, ergänzt den
geschwärzten journald-Auszug, legt `output/` und die Protokolldateien für den Benutzer claude-review an
und schreibt die Lauf-ID nach /run/claude-review/current. Ohne Anforderung: Exit 0, nichts zu tun.
Eingaben sind nur Zahlen aus validierten Dateinamen; es gibt keine Shell.

Sicherheit (Befund /security-review 2026-11-23, TOCTOU edgefinder → root): Alles, was aus einem für
edgefinder oder claude-review schreibbaren Ort kommt, wird ausschließlich über Verzeichnis-Deskriptoren
(`dir_fd=`, `O_NOFOLLOW`) geöffnet und über Datei-Deskriptoren (`fchown`/`fchmod`) geändert – nie über
Pfade. `runs/` gehört root; das Lauf-Verzeichnis legt root an. Das Paket wird kopiert (nur reguläre Dateien
und Verzeichnisse, keine Symlinks, geprüfte Namen, Größen-/Anzahl-Limit), danach gehört es root und ist für
den Agenten nur lesbar.
"""

from __future__ import annotations

import grp
import json
import os
import pwd
import re
import shutil
import stat
import subprocess
import sys
import time
from pathlib import Path
from typing import NamedTuple

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "hooks"))
from scrub import scrub

BASE = Path(os.environ.get("CLAUDE_REVIEW_BASE", "/var/lib/claude-review"))
RUNTIME = Path(os.environ.get("CLAUDE_REVIEW_RUNTIME", "/run/claude-review"))
APP_USER, AGENT_USER = "edgefinder", "claude-review"
NAME_RE = re.compile(r"^([1-9][0-9]{0,8})\.json$")
JOURNAL_MAX = 1_500_000
TEST = (
    "CLAUDE_REVIEW_BASE" in os.environ
)  # nur Tests: Benutzer = aktueller Benutzer (kein root nötig)
# Harte Obergrenzen; die Werte der Anforderung (aus claude.*) dürfen sie nie überschreiten
HARD_MAX_BYTES = 50 * 1024 * 1024
HARD_MAX_FILES = 20_000
MAX_DEPTH = 16
CHUNK = 65536
FILE_NAME_RE = re.compile(r"^[A-Za-z0-9._+@=~,()\[\] -]{1,128}$")
STAMP_RE = re.compile(r"^[0-9T:+.Z-]{10,40}$")
DIR_FLAGS = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | os.O_CLOEXEC


class AlreadyDone(Exception):
    """Lauf-Verzeichnis existiert schon (Anforderung doppelt/bereits bearbeitet): nichts anfassen."""


class Rejected(Exception):
    """Anforderung oder Paket ungültig: verwerfen (kein Systemfehler)."""


class Ids(NamedTuple):
    root: int
    app: int
    agent_uid: int
    agent_gid: int


def resolve_ids() -> Ids:
    if TEST:
        return Ids(os.getuid(), os.getuid(), os.getuid(), os.getgid())
    return Ids(
        0,
        pwd.getpwnam(APP_USER).pw_uid,
        pwd.getpwnam(AGENT_USER).pw_uid,
        grp.getgrnam(AGENT_USER).gr_gid,
    )


UNITS = ["-u", "edgefinder.service", "-u", "edgefinder-*"]


def log(message: str) -> None:
    print(f"prepare: {message}", flush=True)


def open_dir(name: str | Path, dir_fd: int | None = None, owners: set[int] | None = None) -> int:
    """Verzeichnis ohne Symlink-Folgen öffnen; Typ und (optional) Besitzer am Deskriptor prüfen."""
    fd = os.open(name, DIR_FLAGS, dir_fd=dir_fd)
    try:
        info = os.fstat(fd)
        if not stat.S_ISDIR(info.st_mode):
            raise Rejected(f"{name}: kein Verzeichnis")
        if owners is not None and info.st_uid not in owners:
            raise Rejected(f"{name}: unerwarteter Besitzer {info.st_uid}")
    except BaseException:
        os.close(fd)
        raise
    return fd


def pick_request(inbox: Path | int) -> tuple[int, Path] | None:
    """Kleinste gültig benannte Anforderung (`inbox` als Pfad oder Verzeichnis-Deskriptor)."""
    found = []
    try:
        entries = list(os.scandir(inbox))
    except OSError:
        return None
    for entry in entries:
        match = NAME_RE.match(entry.name)
        if match and entry.is_file(follow_symlinks=False):
            found.append((int(match.group(1)), Path(entry.name)))
    if isinstance(inbox, int):
        return min(found) if found else None
    return min((n, Path(inbox) / name) for n, name in found) if found else None


def read_request(path: Path, run_id: int, dir_fd: int | None = None) -> dict | None:
    """Anforderung lesen (mit `dir_fd`: `path` ist der Dateiname darin); nur reguläre Datei, kein Symlink."""
    try:
        fd = os.open(
            path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK | os.O_CLOEXEC, dir_fd=dir_fd
        )
        with os.fdopen(fd, "rb") as handle:
            info = os.fstat(handle.fileno())
            if not stat.S_ISREG(info.st_mode) or info.st_size > 4096:
                return None
            data = json.loads(handle.read(4097).decode("utf-8"))
    except (OSError, ValueError):
        return None
    if not isinstance(data, dict) or data.get("id") != run_id:
        return None
    ranges = {"max_turns": (1, 200), "runtime_max_seconds": (60, 7200), "journal_hours": (1, 168)}
    optional = {
        "max_package_bytes": (1, HARD_MAX_BYTES),
        "max_package_files": (1, HARD_MAX_FILES),
        "retention_days": (1, 3650),
    }
    for key, (low, high) in {**ranges, **optional}.items():
        value = data.get(key)
        if key in optional and value is None:
            continue
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


def create(dir_fd: int, name: str, content: bytes, uid: int, gid: int, mode: int) -> None:
    """Datei relativ zu `dir_fd` neu anlegen (`O_EXCL|O_NOFOLLOW`); Besitzer/Modus am Deskriptor setzen."""
    fd = os.open(
        name,
        os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW | os.O_CLOEXEC,
        0o600,
        dir_fd=dir_fd,
    )
    with os.fdopen(fd, "wb") as handle:
        os.fchown(handle.fileno(), uid, gid)
        os.fchmod(handle.fileno(), mode)
        handle.write(content)


def make_dir(parent_fd: int, name: str, uid: int, gid: int, mode: int) -> int:
    """Verzeichnis anlegen (schlägt bei Vorhandensein fehl), per Deskriptor öffnen, Besitzer/Modus setzen."""
    os.mkdir(name, 0o700, dir_fd=parent_fd)
    fd = open_dir(name, parent_fd)
    try:
        os.fchown(fd, uid, gid)
        os.fchmod(fd, mode)
    except BaseException:
        os.close(fd)
        raise
    return fd


class Budget:
    def __init__(self, max_bytes: int, max_files: int) -> None:
        self.max_bytes, self.max_files = max_bytes, max_files
        self.bytes = self.files = 0

    def add_file(self) -> None:
        self.files += 1
        if self.files > self.max_files:
            raise Rejected(f"mehr als {self.max_files} Dateien im Paket")

    def add_bytes(self, count: int) -> None:
        self.bytes += count
        if self.bytes > self.max_bytes:
            raise Rejected(f"Paket größer als {self.max_bytes} Bytes")


def copy_file(src_dir: int, dst_dir: int, name: str, ids: Ids, budget: Budget) -> None:
    fd = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK | os.O_CLOEXEC, dir_fd=src_dir)
    with os.fdopen(fd, "rb") as src:
        info = os.fstat(src.fileno())
        if not stat.S_ISREG(info.st_mode):
            raise Rejected(f"{name}: keine reguläre Datei")
        if info.st_size > budget.max_bytes - budget.bytes:
            raise Rejected(f"{name}: Paket zu groß")
        out = os.open(
            name,
            os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW | os.O_CLOEXEC,
            0o600,
            dir_fd=dst_dir,
        )
        with os.fdopen(out, "wb") as dst:
            os.fchown(dst.fileno(), ids.root, ids.agent_gid)
            os.fchmod(dst.fileno(), 0o640)
            while chunk := src.read(CHUNK):  # zählt tatsächlich gelesene Bytes (Datei kann wachsen)
                budget.add_bytes(len(chunk))
                dst.write(chunk)


def copy_tree(src_dir: int, dst_dir: int, ids: Ids, budget: Budget, depth: int = 0) -> None:
    """Paket aus dem edgefinder-eigenen Verzeichnis nach root kopieren: nur Dateien/Verzeichnisse, keine Symlinks."""
    if depth > MAX_DEPTH:
        raise Rejected("Verzeichnisse zu tief verschachtelt")
    for entry in sorted(os.scandir(src_dir), key=lambda e: e.name):
        name = entry.name
        if name in (".", "..") or not FILE_NAME_RE.fullmatch(name):
            raise Rejected(f"unzulässiger Dateiname {name!r}")
        budget.add_file()
        mode = os.stat(name, dir_fd=src_dir, follow_symlinks=False).st_mode
        if stat.S_ISDIR(mode):
            sub_src = open_dir(name, src_dir)
            try:
                sub_dst = make_dir(dst_dir, name, ids.root, ids.agent_gid, 0o750)
                try:
                    copy_tree(sub_src, sub_dst, ids, budget, depth + 1)
                finally:
                    os.close(sub_dst)
            finally:
                os.close(sub_src)
        elif stat.S_ISREG(mode):
            copy_file(src_dir, dst_dir, name, ids, budget)
        else:
            raise Rejected(f"{name}: Symlink oder Sonderdatei im Paket")


def prune_runs(runs_fd: int, keep_days: int, skip: int) -> None:
    """Alte Läufe löschen (`runs/` gehört root; der Web-Benutzer kann dort nicht mehr löschen)."""
    cutoff = time.time() - keep_days * 86400
    for entry in os.scandir(runs_fd):
        if (
            not entry.name.isdigit()
            or int(entry.name) == skip
            or not entry.is_dir(follow_symlinks=False)
        ):
            continue
        try:
            fd = open_dir(entry.name, runs_fd)
            try:
                try:
                    mtime = os.stat("request.json", dir_fd=fd, follow_symlinks=False).st_mtime
                except OSError:
                    mtime = os.fstat(fd).st_mtime
            finally:
                os.close(fd)
            if mtime < cutoff:
                shutil.rmtree(entry.name, dir_fd=runs_fd)  # fd-basiert, folgt keinen Symlinks
                log(f"Lauf {entry.name} aufgeräumt (älter als {keep_days} Tage)")
        except (OSError, Rejected) as exc:
            log(f"Aufräumen von {entry.name} übersprungen: {type(exc).__name__}")


def discard(inbox_fd: int, name: str) -> None:
    try:
        os.unlink(name, dir_fd=inbox_fd)
    except OSError:
        pass


def build_run(runs_fd: int, staging_fd: int, run_id: int, request: dict, ids: Ids) -> dict:
    """Lauf-Verzeichnis als root anlegen, Paket übernehmen, Protokolldateien anlegen; liefert request.json."""
    name = str(run_id)
    try:  # Symlink statt Verzeichnis (ELOOP), fehlend oder falscher Besitzer: Paket unbrauchbar
        stage_fd = open_dir(name, staging_fd, {ids.app})
        try:
            src_input = open_dir("input", stage_fd, {ids.app})
        finally:
            os.close(stage_fd)
    except OSError as exc:
        raise Rejected(f"Paketverzeichnis staging/{name}/input unzulässig: {exc.strerror}") from exc
    try:
        started = time.strftime("%Y-%m-%dT%H:%M:%S+00:00", time.gmtime())
        try:
            run_fd = make_dir(runs_fd, name, ids.root, ids.agent_gid, 0o755)
        except FileExistsError as exc:
            raise AlreadyDone(name) from exc
        try:
            budget = Budget(
                request.get("max_package_bytes", HARD_MAX_BYTES),
                request.get("max_package_files", HARD_MAX_FILES),
            )
            dst_input = make_dir(run_fd, "input", ids.root, ids.agent_gid, 0o750)
            try:
                copy_tree(src_input, dst_input, ids, budget)
                journal = journal_text(request["journal_hours"]).encode()
                create(dst_input, "journal.txt", journal, ids.root, ids.agent_gid, 0o640)
            except FileExistsError as exc:  # z. B. ein mitgeliefertes journal.txt
                raise Rejected("Dateiname im Paket kollidiert mit einer Dienstdatei") from exc
            finally:
                os.close(dst_input)
            out_fd = make_dir(run_fd, "output", ids.agent_uid, ids.agent_gid, 0o755)
            os.close(out_fd)
            status = {"state": "running", "started_at": started}
            create(
                run_fd,
                "status.json",
                json.dumps(status).encode(),
                ids.agent_uid,
                ids.agent_gid,
                0o644,
            )
            for fname in ("audit.jsonl", "transcript.jsonl", "claude.stderr"):
                create(run_fd, fname, b"", ids.agent_uid, ids.agent_gid, 0o644)
            created = request.get("created_at")
            clean = {
                "id": run_id,
                "created_at": created
                if isinstance(created, str) and STAMP_RE.fullmatch(created)
                else started,
                "max_turns": request["max_turns"],
                "runtime_max_seconds": request["runtime_max_seconds"],
                "journal_hours": request["journal_hours"],
                "package_bytes": budget.bytes,
            }
            create(run_fd, "request.json", json.dumps(clean).encode(), ids.root, ids.root, 0o644)
        except BaseException:
            os.close(run_fd)
            raise
        os.close(run_fd)
        return clean
    finally:
        os.close(src_input)


def main() -> int:
    ids = resolve_ids()
    try:
        base_fd = open_dir(BASE)
    except (OSError, Rejected):
        log("keine Anforderung")
        return 0
    try:
        try:
            inbox_fd = open_dir("inbox", base_fd, {ids.app})
        except OSError:
            log("keine Anforderung")
            return 0
        except Rejected as exc:
            log(f"inbox unzulässig: {exc}")
            return 1
        picked = pick_request(inbox_fd)
        if picked is None:
            log("keine Anforderung")
            return 0
        run_id, request_name = picked
        request = read_request(request_name, run_id, inbox_fd)
        if request is None:
            log(f"Anforderung {run_id} verworfen (ungültig)")
            discard(inbox_fd, request_name.name)
            return 0
        try:
            runs_fd = open_dir("runs", base_fd, {ids.root})
            staging_fd = open_dir("staging", base_fd, {ids.app})
        except (OSError, Rejected) as exc:
            log(f"runs/ oder staging/ fehlt oder hat falschen Besitzer (install.sh erneut): {exc}")
            return 1
        try:
            RUNTIME.mkdir(parents=True, exist_ok=True)
            runtime_fd = open_dir(RUNTIME)
            try:
                return run_prepare(
                    inbox_fd,
                    request_name.name,
                    runs_fd,
                    staging_fd,
                    runtime_fd,
                    run_id,
                    request,
                    ids,
                )
            finally:
                os.close(runtime_fd)
        finally:
            os.close(runs_fd)
            os.close(staging_fd)
    finally:
        os.close(base_fd)


def run_prepare(
    inbox_fd: int,
    request_name: str,
    runs_fd: int,
    staging_fd: int,
    runtime_fd: int,
    run_id: int,
    request: dict,
    ids: Ids,
) -> int:
    try:
        build_run(runs_fd, staging_fd, run_id, request, ids)
    except AlreadyDone:
        log(f"Anforderung {run_id} verworfen (Lauf existiert schon)")
        discard(inbox_fd, request_name)
        return 0
    except Rejected as exc:
        log(f"Anforderung {run_id} verworfen: {exc}")
        shutil.rmtree(str(run_id), dir_fd=runs_fd, ignore_errors=True)
        discard(inbox_fd, request_name)
        return 0
    except (OSError, KeyError) as exc:
        log(f"Vorbereitung von {run_id} fehlgeschlagen: {type(exc).__name__}: {exc}")
        shutil.rmtree(str(run_id), dir_fd=runs_fd, ignore_errors=True)
        discard(inbox_fd, request_name)
        return 1
    try:
        try:
            os.unlink("current", dir_fd=runtime_fd)
        except FileNotFoundError:
            pass
        create(runtime_fd, "current", f"{run_id}\n".encode(), ids.root, ids.root, 0o644)
    except OSError as exc:
        log(f"current für {run_id} nicht schreibbar: {type(exc).__name__}: {exc}")
        discard(inbox_fd, request_name)
        return 1
    discard(inbox_fd, request_name)
    prune_runs(runs_fd, request.get("retention_days", 90), run_id)
    log(f"Lauf {run_id} vorbereitet")
    return 0


if __name__ == "__main__":
    sys.exit(main())
