"""Kommandozeile: `edgefinder <befehl>`. Einstiegspunkt für systemd-Units und Deploy."""

from __future__ import annotations

import argparse
import logging
import sys
from collections import Counter
from datetime import UTC, date, datetime

from edgefinder.config import Config, load_config, load_secrets
from edgefinder.db import connect, migrate
from edgefinder.fetchers import FETCHERS

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


def _cmd_fetch(config: Config, args: argparse.Namespace) -> int:
    """Holt eine oder alle Quellen. Jede Quelle läuft für sich (eigene Verbindung, eigener Lauf)."""
    names = list(FETCHERS) if args.source == "all" else [args.source]
    secrets = load_secrets()
    migrate_conn = connect(config.storage.database)
    try:
        migrate(migrate_conn)
    finally:
        migrate_conn.close()
    failed = False
    for name in names:
        if not config.sources[name].enabled:
            log.info("%s: in config.yaml deaktiviert, übersprungen", name)
            continue
        conn = connect(config.storage.database)
        try:
            result = FETCHERS[name](config, secrets, conn).run()
        finally:
            conn.close()
        log.info(
            "%s: %s, %d Zeilen, %d Requests (Lauf %d)",
            name,
            result.status,
            result.items,
            result.requests,
            result.run_id,
        )
        for error in result.errors:
            log.error("%s: %s", name, error)
        failed |= result.status != "success"
    return 1 if failed else 0


def _cmd_score(config: Config, args: argparse.Namespace) -> int:
    """Scores berechnen: ein Stichtag (Standard heute) oder Zeitraum (--from/--to, Backtest)."""
    from edgefinder.scoring.engine import ScoreEngine

    if args.asset:
        unknown = sorted(set(args.asset) - set(config.assets_by_id))
        if unknown:
            log.error("Unbekannte Asset-ID(s): %s", ", ".join(unknown))
            return 2
    if (args.date_from or args.date_to) and args.as_of:
        log.error("--as-of und --from/--to schließen sich aus")
        return 2
    migrate_conn = connect(config.storage.database)
    try:
        migrate(migrate_conn)
    finally:
        migrate_conn.close()
    conn = connect(config.storage.database)
    try:
        engine = ScoreEngine(config, conn)
        if args.date_from or args.date_to:
            start = args.date_from or args.date_to
            end = args.date_to or datetime.now(UTC).date()
            if start > end:
                log.error("--from liegt nach --to")
                return 2
            count = engine.run_range(start, end, args.asset)
            log.info("%d Scores für %s bis %s berechnet", count, start, end)
        else:
            day = args.as_of or datetime.now(UTC).date()
            results = engine.run_day(day, args.asset)
            for result in results:
                log.debug(
                    "%s %s: %+.2f %s (Abdeckung %.0f %%)",
                    result.asset_id,
                    result.profile,
                    result.score,
                    result.label,
                    result.coverage * 100,
                )
            log.info("%d Scores für %s berechnet", len(results), day)
            if not results:
                return 1
    finally:
        conn.close()
    return 0


def _cmd_cleanup(config: Config, args: argparse.Namespace) -> int:
    """Rohdaten älter als `storage.raw_retention_days` löschen (Dateien + raw_files-Einträge)."""
    from edgefinder.cleanup import cleanup_raw

    days = args.days or config.storage.raw_retention_days
    migrate_conn = connect(config.storage.database)
    try:
        migrate(migrate_conn)
    finally:
        migrate_conn.close()
    conn = connect(config.storage.database)
    try:
        result = cleanup_raw(conn, config.storage.raw_dir, days, dry_run=args.dry_run)
    finally:
        conn.close()
    log.info(
        "Aufräumen%s: %d Dateien (%.1f MB) älter als %d Tage, %d Einträge, %d fehlende Dateien",
        " (Probelauf)" if args.dry_run else "",
        result.files,
        result.bytes / 1e6,
        days,
        result.rows,
        result.missing,
    )
    return 0


def _iso_date(value: str) -> date:
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(f"ungültiges Datum '{value}' (YYYY-MM-DD)") from exc


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
    fetch = commands.add_parser("fetch", help="Daten einer Quelle holen")
    fetch.add_argument("source", choices=[*FETCHERS, "all"], help="Quelle oder „all“")
    fetch.set_defaults(func=_cmd_fetch)
    score = commands.add_parser("score", help="Scores berechnen und speichern")
    score.add_argument("--as-of", type=_iso_date, help="Stichtag YYYY-MM-DD (Standard: heute)")
    score.add_argument("--from", dest="date_from", type=_iso_date, help="Zeitraum ab (Werktage)")
    score.add_argument(
        "--to", dest="date_to", type=_iso_date, help="Zeitraum bis (Standard: heute)"
    )
    score.add_argument("--asset", action="append", help="nur dieses Asset (mehrfach möglich)")
    score.set_defaults(func=_cmd_score)
    cleanup = commands.add_parser("cleanup", help="alte Rohdaten (data/raw) löschen")
    cleanup.add_argument("--days", type=int, help="überschreibt storage.raw_retention_days")
    cleanup.add_argument("--dry-run", action="store_true", help="nur zählen, nichts löschen")
    cleanup.set_defaults(func=_cmd_cleanup)
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
    for noisy in ("httpx", "httpcore"):  # loggen URLs samt Query (API-Keys), auch bei -v
        logging.getLogger(noisy).setLevel(logging.WARNING)
    try:
        config = load_config()
    except (OSError, ValueError) as exc:
        log.error("Konfiguration ungültig: %s", exc)
        return 2
    return args.func(config, args)


if __name__ == "__main__":
    sys.exit(main())
