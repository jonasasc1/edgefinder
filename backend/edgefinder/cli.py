"""Kommandozeile: `edgefinder <befehl>`. Einstiegspunkt für systemd-Units und Deploy."""

from __future__ import annotations

import argparse
import logging
import sys
from collections import Counter

from edgefinder.config import Config, load_config
from edgefinder.db import connect, migrate

log = logging.getLogger("edgefinder")


def _cmd_check_config(config: Config, _args: argparse.Namespace) -> int:
    counts = Counter(asset.asset_class.value for asset in config.assets.all())
    summary = ", ".join(f"{count} {name}" for name, count in sorted(counts.items()))
    print(f"Konfiguration gültig: {summary}; Profile: {', '.join(config.profiles)}")
    return 0


def _cmd_migrate(config: Config, _args: argparse.Namespace) -> int:
    conn = connect(config.storage.database)
    try:
        applied = migrate(conn)
    finally:
        conn.close()
    if applied:
        for migration in applied:
            log.info("Migration %04d_%s angewendet", migration.version, migration.name)
    else:
        log.info("Datenbank ist aktuell")
    return 0


def _cmd_serve(config: Config, args: argparse.Namespace) -> int:
    import uvicorn

    from edgefinder.api.app import create_app

    uvicorn.run(
        create_app(config),
        host=args.host or config.server.host,
        port=args.port or config.server.port,
        log_config=None,  # Logging läuft über unsere Konfiguration nach stderr/journald
        proxy_headers=True,
        forwarded_allow_ips=args.forwarded_allow_ips,
    )
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="edgefinder", description=__doc__)
    parser.add_argument("-v", "--verbose", action="store_true", help="Debug-Ausgaben")
    commands = parser.add_subparsers(dest="command", required=True)

    commands.add_parser("check-config", help="config.yaml prüfen").set_defaults(
        func=_cmd_check_config
    )
    commands.add_parser("migrate", help="ausstehende DB-Migrationen anwenden").set_defaults(
        func=_cmd_migrate
    )
    serve = commands.add_parser("serve", help="API und Frontend ausliefern")
    serve.add_argument("--host", help="überschreibt server.host")
    serve.add_argument("--port", type=int, help="überschreibt server.port")
    serve.add_argument(
        "--forwarded-allow-ips",
        default="127.0.0.1",
        help="Proxys, deren X-Forwarded-*-Header vertraut wird",
    )
    serve.set_defaults(func=_cmd_serve)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    # journald ergänzt Zeitstempel selbst; daher bewusst ohne Zeit im Format.
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(levelname)s %(name)s: %(message)s",
        stream=sys.stderr,
    )
    try:
        config = load_config()
    except (OSError, ValueError) as exc:
        log.error("Konfiguration ungültig: %s", exc)
        return 2
    return args.func(config, args)


if __name__ == "__main__":
    sys.exit(main())
