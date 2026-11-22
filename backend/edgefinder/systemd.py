"""Erzeugt die systemd-Units und -Timer aus `config.yaml` (`edgefinder gen-systemd`).

Der Admin-Runner (`edgefinder-adminjobs.*`) hat eine `.path`-Unit (Trigger-Datei) und einen
Fallback-Timer. Die Zeitpläne (`OnCalendar`) stammen aus `sources.<name>.schedule`,
`scoring.schedule` und
`maintenance.*_schedule`. Die erzeugten Dateien liegen im Repo unter `deploy/systemd/`; ein Test
stellt sicher, dass sie zur `config.yaml` passen (Neu erzeugen: `uv run edgefinder gen-systemd`).
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from edgefinder.admin_jobs import TRIGGER_NAME
from edgefinder.config import Config

HEADER = (
    "# ERZEUGT von `edgefinder gen-systemd` aus config.yaml – nicht von Hand ändern.\n"
    "# Zeitpläne in config.yaml anpassen und die Dateien neu erzeugen.\n"
)
FETCH_SERVICE = "edgefinder-fetch@.service"
# Verzögerung gegen Lastspitzen (z. B. nach Neustart mit Persistent=true)
RANDOM_DELAY = "60"


@dataclass(frozen=True)
class Layout:
    """Pfade auf „trading“ (müssen zu deploy/install.sh passen)."""

    app_dir: str = "/opt/edgefinder"
    state_dir: str = "/var/lib/edgefinder"
    user: str = "edgefinder"

    @property
    def exe(self) -> str:
        return f"{self.app_dir}/.venv/bin/edgefinder"

    @property
    def trigger(self) -> str:
        return f"{self.state_dir}/{TRIGGER_NAME}"

    @property
    def lock(self) -> str:
        return f"{self.state_dir}/.jobs.lock"


def _server_unit(config: Config, layout: Layout) -> str:
    return f"""{HEADER}[Unit]
Description=edgefinder (API und Frontend, Port {config.server.port})
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User={layout.user}
Group={layout.user}
WorkingDirectory={layout.app_dir}
ExecStart={layout.exe} serve
Restart=on-failure
RestartSec=5
# 2 GB RAM auf „trading“: der Webprozess ist klein, Jobs laufen getrennt.
MemoryMax=600M
TasksMax=64
SyslogIdentifier=edgefinder
{_hardening(layout)}
[Install]
WantedBy=multi-user.target
"""


def _hardening(layout: Layout) -> str:
    return f"""NoNewPrivileges=true
ProtectSystem=strict
ReadWritePaths={layout.state_dir}
PrivateTmp=true
PrivateDevices=true
ProtectHome=true
ProtectKernelTunables=true
ProtectKernelModules=true
ProtectControlGroups=true
RestrictSUIDSGID=true
RestrictRealtime=true
LockPersonality=true
RestrictAddressFamilies=AF_UNIX AF_INET AF_INET6
SystemCallArchitectures=native
UMask=0027
"""


def _job_service(description: str, command: str, layout: Layout) -> str:
    """Oneshot-Job: niedrige Priorität, serialisiert über eine Sperrdatei (SQLite, 2 GB RAM)."""
    return f"""{HEADER}[Unit]
Description={description}
After=network-online.target
Wants=network-online.target

[Service]
Type=oneshot
User={layout.user}
Group={layout.user}
WorkingDirectory={layout.app_dir}
ExecStart=/usr/bin/flock -w 7200 {layout.lock} {layout.exe} {command}
Nice=19
IOSchedulingClass=idle
CPUSchedulingPolicy=idle
MemoryMax=1G
TimeoutStartSec=3h
SyslogIdentifier=edgefinder
{_hardening(layout)}"""


def _timer(description: str, schedule: str | list[str], unit: str) -> str:
    calendars = [schedule] if isinstance(schedule, str) else schedule
    on_calendar = "".join(f"OnCalendar={entry}\n" for entry in calendars)
    return f"""{HEADER}[Unit]
Description={description}

[Timer]
{on_calendar}Persistent=true
RandomizedDelaySec={RANDOM_DELAY}
Unit={unit}

[Install]
WantedBy=timers.target
"""


ADMIN_SERVICE = "edgefinder-adminjobs.service"


def _admin_path(layout: Layout) -> str:
    """Startet den Runner, sobald die API die Trigger-Datei berührt hat (sofortige Reaktion)."""
    return f"""{HEADER}[Unit]
Description=edgefinder: Admin-Aufträge sofort abarbeiten (Trigger-Datei)

[Path]
PathChanged={layout.trigger}
Unit={ADMIN_SERVICE}

[Install]
WantedBy=multi-user.target
"""


def _admin_timer() -> str:
    """Sicherheitsnetz, falls die .path-Unit im Container nicht auslöst (leere Queue = billig)."""
    return f"""{HEADER}[Unit]
Description=edgefinder: Admin-Aufträge regelmäßig prüfen (Fallback zur Trigger-Datei)

[Timer]
OnCalendar=*:0/2
AccuracySec=10s
Unit={ADMIN_SERVICE}

[Install]
WantedBy=timers.target
"""


def generate(config: Config, layout: Layout | None = None) -> dict[str, str]:
    """Dateiname → Inhalt aller Units; Quellen mit `enabled: false` bekommen keinen Timer."""
    layout = layout or Layout()
    files: dict[str, str] = {
        "edgefinder.service": _server_unit(config, layout),
        FETCH_SERVICE: _job_service("edgefinder: Quelle %i holen", "fetch %i", layout),
        "edgefinder-score.service": _job_service("edgefinder: Scores berechnen", "score", layout),
        "edgefinder-cleanup.service": _job_service(
            "edgefinder: alte Rohdaten löschen", "cleanup", layout
        ),
        "edgefinder-evaluate.service": _job_service(
            "edgefinder: Live-Signale auswerten", "evaluate", layout
        ),
        "edgefinder-maintain.service": _job_service(
            "edgefinder: Eichung neu erzeugen", "maintain", layout
        ),
        ADMIN_SERVICE: _job_service("edgefinder: Admin-Aufträge abarbeiten", "admin run", layout),
    }
    files["edgefinder-adminjobs.path"] = _admin_path(layout)
    files["edgefinder-adminjobs.timer"] = _admin_timer()
    for name, source in config.sources.items():
        if source.enabled:
            files[f"edgefinder-fetch-{name}.timer"] = _timer(
                f"edgefinder: Quelle {name} holen",
                source.schedule,
                f"edgefinder-fetch@{name}.service",
            )
    files["edgefinder-score.timer"] = _timer(
        "edgefinder: Scores berechnen", config.scoring.schedule, "edgefinder-score.service"
    )
    files["edgefinder-cleanup.timer"] = _timer(
        "edgefinder: Rohdaten aufräumen",
        config.maintenance.cleanup_schedule,
        "edgefinder-cleanup.service",
    )
    files["edgefinder-evaluate.timer"] = _timer(
        "edgefinder: Live-Signale auswerten",
        config.maintenance.evaluate_schedule,
        "edgefinder-evaluate.service",
    )
    files["edgefinder-maintain.timer"] = _timer(
        "edgefinder: Eichung neu erzeugen",
        config.maintenance.maintain_schedule,
        "edgefinder-maintain.service",
    )
    return files


def write(files: dict[str, str], out: Path) -> list[str]:
    """Schreibt die Dateien nach `out` und entfernt dort veraltete edgefinder-Units."""
    out.mkdir(parents=True, exist_ok=True)
    removed = []
    olds = [
        p
        for pattern in ("*.timer", "*.service", "*.path")
        for p in out.glob(f"edgefinder{pattern}")
    ]
    for old in sorted(olds):
        if old.name not in files:
            old.unlink()
            removed.append(old.name)
    for name, content in files.items():
        (out / name).write_text(content, encoding="utf-8")
    return removed
