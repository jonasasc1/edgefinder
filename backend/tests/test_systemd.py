from __future__ import annotations

import shutil
import sqlite3
import subprocess
from datetime import UTC, datetime
from pathlib import Path

import pytest
from test_cli_fetch import cli_env  # noqa: F401

from edgefinder import cli, systemd
from edgefinder.backup import backup_database
from edgefinder.config import load_config

REPO_ROOT = Path(__file__).resolve().parents[2]


def test_committed_units_match_config() -> None:
    """deploy/systemd/ muss zu config.yaml passen (sonst `edgefinder gen-systemd` ausführen)."""
    config = load_config(REPO_ROOT / "config.yaml")
    files = systemd.generate(config)
    out = REPO_ROOT / "deploy" / "systemd"
    on_disk = {p.name for p in out.glob("edgefinder*")}
    assert on_disk == set(files)
    for name, content in files.items():
        assert (out / name).read_text(encoding="utf-8") == content, name


def test_one_timer_per_enabled_source_with_schedule() -> None:
    config = load_config(REPO_ROOT / "config.yaml")
    files = systemd.generate(config)
    for name, source in config.sources.items():
        timer = files[f"edgefinder-fetch-{name}.timer"]
        schedules = [source.schedule] if isinstance(source.schedule, str) else source.schedule
        for entry in schedules:
            assert f"OnCalendar={entry}\n" in timer
        assert f"Unit=edgefinder-fetch@{name}.service" in timer
        assert "Persistent=true" in timer
    for entry in config.scoring.schedule:
        assert f"OnCalendar={entry}\n" in files["edgefinder-score.timer"]


def test_all_schedules_are_valid_calendar_expressions() -> None:
    exe = shutil.which("systemd-analyze")
    if exe is None:
        pytest.skip("systemd-analyze nicht verfügbar")
    config = load_config(REPO_ROOT / "config.yaml")
    schedules = [config.scoring.schedule, config.maintenance.cleanup_schedule]
    schedules += [config.maintenance.backup_schedule]
    schedules += [source.schedule for source in config.sources.values()]
    for entry in schedules:
        for expression in [entry] if isinstance(entry, str) else entry:
            result = subprocess.run(  # noqa: S603
                [exe, "calendar", expression], capture_output=True, text=True, check=False
            )
            assert result.returncode == 0, f"{expression}: {result.stderr}"


def test_disabled_source_gets_no_timer() -> None:
    config = load_config(REPO_ROOT / "config.yaml")
    config.sources["aaii"] = config.sources["aaii"].model_copy(update={"enabled": False})
    assert "edgefinder-fetch-aaii.timer" not in systemd.generate(config)


def test_myfxbook_schedule_respects_daily_limit() -> None:
    """Läufe/Tag × (Login + Outlook = 2 Requests) bleiben unter dem konfigurierten Limit."""
    config = load_config(REPO_ROOT / "config.yaml")
    source = config.sources["myfxbook"]
    assert source.daily_request_limit is not None and source.daily_request_limit <= 100
    exe = shutil.which("systemd-analyze")
    if exe is None:
        pytest.skip("systemd-analyze nicht verfügbar")
    out = subprocess.run(  # noqa: S603
        [exe, "calendar", "--iterations=30", source.schedule],
        capture_output=True,
        text=True,
        check=True,
    )
    days: dict[str, int] = {}
    for line in out.stdout.splitlines():
        if line.strip().startswith("Iteration #"):
            day = line.split()[3]
            days[day] = days.get(day, 0) + 1
    full_days = sorted(days)[1:-1]  # erster/letzter Tag können angeschnitten sein
    assert full_days
    for day in full_days:
        assert 2 * days[day] <= source.daily_request_limit


def test_server_unit_is_hardened() -> None:
    unit = systemd.generate(load_config(REPO_ROOT / "config.yaml"))["edgefinder.service"]
    for line in (
        "NoNewPrivileges=true",
        "ProtectSystem=strict",
        "PrivateTmp=true",
        "ProtectHome=true",
        "ReadWritePaths=/var/lib/edgefinder",
        "Restart=on-failure",
        "User=edgefinder",
        "MemoryMax=600M",
    ):
        assert line in unit


def test_gen_systemd_command_and_check(cli_env: Path, tmp_path: Path) -> None:  # noqa: F811
    out = tmp_path / "units"
    assert cli.main(["gen-systemd", "--out", str(out)]) == 0
    assert cli.main(["gen-systemd", "--out", str(out), "--check"]) == 0
    (out / "edgefinder-score.timer").write_text("x", encoding="utf-8")
    assert cli.main(["gen-systemd", "--out", str(out), "--check"]) == 1
    (out / "edgefinder-alt.timer").write_text("x", encoding="utf-8")
    assert cli.main(["gen-systemd", "--out", str(out)]) == 0  # entfernt Veraltetes
    assert not (out / "edgefinder-alt.timer").exists()


def test_backup_consistent_and_rotates(tmp_path: Path) -> None:
    db = tmp_path / "e.db"
    conn = sqlite3.connect(db)
    conn.execute("CREATE TABLE t (x)")
    conn.execute("INSERT INTO t VALUES (1)")
    conn.commit()
    conn.close()
    backups = tmp_path / "b"
    for sec in range(3):
        target = backup_database(
            db, backups, keep=2, now=datetime(2026, 1, 1, 3, 0, sec, tzinfo=UTC)
        )
    assert sorted(p.name for p in backups.iterdir()) == [
        "edgefinder-20260101T030001Z.db",
        "edgefinder-20260101T030002Z.db",
    ]
    assert sqlite3.connect(target).execute("SELECT x FROM t").fetchone() == (1,)


def test_backup_command(cli_env: Path) -> None:  # noqa: F811
    assert cli.main(["backup"]) == 1  # keine Datenbank → Fehler, kein Absturz
    assert cli.main(["migrate"]) == 0
    assert cli.main(["backup"]) == 0
