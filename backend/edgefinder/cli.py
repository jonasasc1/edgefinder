"""Kommandozeile: `edgefinder <befehl>`. Einstiegspunkt für systemd-Units und Deploy."""

from __future__ import annotations

import argparse
import logging
import sys
from collections import Counter
from datetime import UTC, date, datetime
from pathlib import Path

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


def _cmd_gen_systemd(config: Config, args: argparse.Namespace) -> int:
    """systemd-Units/-Timer aus config.yaml erzeugen (`--check`: nur auf Abweichung prüfen)."""
    from edgefinder import systemd

    files = systemd.generate(config, systemd.Layout(app_dir=args.app_dir, state_dir=args.state_dir))
    if args.check:
        stale = [
            n
            for n, c in files.items()
            if not (args.out / n).is_file() or (args.out / n).read_text(encoding="utf-8") != c
        ]
        extra = [p.name for p in args.out.glob("edgefinder*.*") if p.name not in files]
        if stale or extra:
            log.error("%s weicht von config.yaml ab: %s", args.out, ", ".join(stale + extra))
            return 1
        log.info("%d Dateien in %s sind aktuell", len(files), args.out)
        return 0
    removed = systemd.write(files, args.out)
    log.info(
        "%d Dateien nach %s geschrieben, %d veraltete entfernt", len(files), args.out, len(removed)
    )
    return 0


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
            weekday = config.backtest.score_weekday if args.weekday is None else args.weekday
            if weekday == ALL_WEEKDAYS:
                weekday = None
            count = engine.run_range(start, end, args.asset, weekday=weekday)
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


def _cmd_backtest(config: Config, args: argparse.Namespace) -> int:
    """Score-Historie gegen spätere Kurse auswerten; schreibt Markdown-Report und JSON."""
    from edgefinder.backtest.analysis import run_backtest
    from edgefinder.backtest.report import write_report

    if args.profile and (unknown := sorted(set(args.profile) - set(config.profiles))):
        log.error("Unbekanntes Profil: %s", ", ".join(unknown))
        return 2
    classes = {a.asset_class.value for a in config.assets.all()}
    if args.asset_class and (unknown := sorted(set(args.asset_class) - classes)):
        log.error(
            "Unbekannte Klasse: %s (erlaubt: %s)", ", ".join(unknown), ", ".join(sorted(classes))
        )
        return 2
    if args.horizon_days is not None and args.horizon_days < 1:
        log.error("--horizon-days muss ≥ 1 sein")
        return 2
    migrate_conn = connect(config.storage.database)
    try:
        migrate(migrate_conn)
    finally:
        migrate_conn.close()
    conn = connect(config.storage.database)
    try:
        result = run_backtest(
            conn,
            config,
            profiles=tuple(args.profile) if args.profile else None,
            classes=tuple(args.asset_class) if args.asset_class else None,
            horizon_days=args.horizon_days,
            since=args.date_from.isoformat() if args.date_from else None,
            until=args.date_to.isoformat() if args.date_to else None,
        )
    finally:
        conn.close()
    if not result["scores"]:
        log.error("Keine Scores im Zeitraum – erst `edgefinder score --from … --to …` ausführen")
        return 1
    paths = write_report(result, config.backtest.output_dir, args.markdown)
    log.info(
        "Backtest: %d Scores, %d Stichtage (%s bis %s) → %s, %s",
        result["scores"],
        result["dates"],
        result["first_date"],
        result["last_date"],
        paths["markdown"],
        paths["json"],
    )
    return 0


def _cmd_calibrate(config: Config, args: argparse.Namespace) -> int:
    """Eichung der Score-Bereiche aus dem Backfill berechnen → `backtest.calibration_file`."""
    from edgefinder.backtest import calibration
    from edgefinder.backtest.report import CLASS_NAME

    migrate_conn = connect(config.storage.database)
    try:
        migrate(migrate_conn)
    finally:
        migrate_conn.close()
    conn = connect(config.storage.database)
    try:
        data = calibration.build_calibration(conn, config)
    finally:
        conn.close()
    if not data["scores"]:
        log.error("Keine Scores – erst `edgefinder score --from … --to …` ausführen")
        return 1
    path = args.out or config.backtest.calibration_file
    calibration.write_calibration(data, path)
    if args.report:
        labels = {k: v.label for k, v in config.profiles.items()}
        section = calibration.render_markdown(data, labels, CLASS_NAME)
        calibration.update_report(args.report, section)
    log.info("Eichung: %d Scores (%s bis %s) → %s", data["scores"], data["first_date"],
             data["data_through"], path)  # fmt: skip
    return 0


def _migrated_conn(config: Config):
    migrate_conn = connect(config.storage.database)
    try:
        migrate(migrate_conn)
    finally:
        migrate_conn.close()
    return connect(config.storage.database)


def _cmd_evaluate(config: Config, _args: argparse.Namespace) -> int:
    """Live-Signale mit abgelaufenem Horizont gegen den realen Kurs auswerten (idempotent)."""
    from edgefinder import maintenance

    conn = _migrated_conn(config)
    try:
        run = maintenance.run_evaluate(conn, config)
    finally:
        conn.close()
    for error in run.errors:
        log.error("evaluate: %s", error)
    return 1 if run.errors else 0


def _cmd_maintain(config: Config, _args: argparse.Namespace) -> int:
    """Wartung: Backfill ergänzen, Eichung neu erzeugen, Drift-Bericht (`<data>/…`)."""
    from edgefinder import maintenance

    conn = _migrated_conn(config)
    try:
        run = maintenance.run_maintain(conn, config)
    finally:
        conn.close()
    for error in run.errors:
        log.error("maintain: %s", error)
    log.info("Wartung: %d neue Backfill-Scores, %d Fehler", run.items, len(run.errors))
    return 1 if run.errors else 0


def _cmd_review_report(config: Config, args: argparse.Namespace) -> int:
    """Markdown-Vorlage für den nächsten Modellpflege-Termin aus Bilanz und Drift schreiben."""
    from edgefinder import maintenance
    from edgefinder.backtest import live

    conn = _migrated_conn(config)
    try:
        report = live.build_trackrecord(conn, config, maintenance.load_current_calibration(config))
    finally:
        conn.close()
    path = args.out or config.data_dir / maintenance.REVIEW_NAME
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(maintenance.render_review(report, config), encoding="utf-8")
    log.info("Review-Vorlage → %s", path)
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


def _cmd_admin(config: Config, args: argparse.Namespace) -> int:
    """Admin-Rolle verwalten (nur lokal auf dem Server) und die Warteschlange abarbeiten."""
    from edgefinder import admin_jobs
    from edgefinder.api.auth import normalize_email

    if args.admin_command == "run":
        done = admin_jobs.run_queue(config)
        log.info("Admin-Aufträge: %d abgearbeitet", done)
        return 0
    conn = _migrated_conn(config)
    try:
        if args.admin_command == "list":
            admins = admin_jobs.list_admins(conn)
            print("\n".join(admins) if admins else "Keine Admins.")
            return 0
        try:
            email = normalize_email(args.email)
            print(
                admin_jobs.set_admin(conn, email, args.admin_command == "grant", force=args.force)
            )
        except ValueError as exc:
            log.error("%s", exc)
            return 2
        except (LookupError, PermissionError) as exc:
            log.error("%s", exc)
            return 1
    finally:
        conn.close()
    return 0


ALL_WEEKDAYS = -1
_WEEKDAYS = {
    "mo": 0,
    "di": 1,
    "mi": 2,
    "do": 3,
    "fr": 4,
    "mon": 0,
    "tue": 1,
    "wed": 2,
    "thu": 3,
    "fri": 4,
}


def _weekday(value: str) -> int:
    key = value.strip().lower()
    if key in ("all", "alle"):
        return ALL_WEEKDAYS
    if key in _WEEKDAYS:
        return _WEEKDAYS[key]
    if key.isdigit() and 0 <= int(key) <= 4:
        return int(key)
    raise argparse.ArgumentTypeError(f"ungültiger Wochentag '{value}' (mo..fr, 0..4 oder all)")


def _iso_date(value: str) -> date:
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(f"ungültiges Datum '{value}' (YYYY-MM-DD)") from exc


def _cmd_serve(config: Config, args: argparse.Namespace) -> int:
    import uvicorn

    from edgefinder.api.app import create_app

    uvicorn.run(
        create_app(config, secrets=load_secrets()),
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
    score.add_argument(
        "--weekday",
        type=_weekday,
        default=None,
        help="Backfill nur an diesem Wochentag (mo..fr oder 0..4); „all“ = jeder Werktag "
        "(Standard: backtest.score_weekday)",
    )
    score.set_defaults(func=_cmd_score)
    backtest = commands.add_parser("backtest", help="Score-Historie gegen Kurse auswerten")
    backtest.add_argument("--profile", action="append", help="nur dieses Profil (mehrfach möglich)")
    backtest.add_argument(
        "--class", dest="asset_class", action="append", help="nur diese Assetklasse (mehrfach)"
    )
    backtest.add_argument(
        "--horizon-days", type=int, help="ein Horizont in Handelstagen statt backtest.horizons"
    )
    backtest.add_argument("--from", dest="date_from", type=_iso_date, help="Stichtage ab")
    backtest.add_argument("--to", dest="date_to", type=_iso_date, help="Stichtage bis")
    backtest.add_argument(
        "--markdown", type=Path, help="Markdown-Report hierhin (Standard: output_dir)"
    )
    backtest.set_defaults(func=_cmd_backtest)
    calibrate = commands.add_parser(
        "calibrate", help="Eichung der Score-Bereiche (docs/calibration.json) aus dem Backfill"
    )
    calibrate.add_argument("--out", type=Path, help="Ziel (Standard: backtest.calibration_file)")
    calibrate.add_argument(
        "--report", type=Path, help="Kalibrierungs-Anhang in diesen Markdown-Report schreiben"
    )
    calibrate.set_defaults(func=_cmd_calibrate)
    commands.add_parser(
        "evaluate", help="Live-Signale nach Ablauf des Horizonts auswerten (Forward-Test)"
    ).set_defaults(func=_cmd_evaluate)
    commands.add_parser(
        "maintain", help="Eichung neu erzeugen: Backfill ergänzen, calibrate, Drift-Bericht"
    ).set_defaults(func=_cmd_maintain)
    review = commands.add_parser("review-report", help="Vorlage für den Modellpflege-Termin")
    review.add_argument("--out", type=Path, help="Ziel (Standard: <data>/review.md)")
    review.set_defaults(func=_cmd_review_report)
    admin = commands.add_parser("admin", help="Admin-Rolle (grant/revoke/list) und Runner (run)")
    admin_cmds = admin.add_subparsers(dest="admin_command", required=True)
    for name, text in (("grant", "Admin-Rolle vergeben"), ("revoke", "Admin-Rolle entziehen")):
        sub = admin_cmds.add_parser(name, help=f"{text} (legt das Konto bei grant an)")
        sub.add_argument("email", help="E-Mail-Adresse des Kontos")
        if name == "revoke":
            sub.add_argument(
                "--force", action="store_true", help="auch den letzten Admin entfernen"
            )
        else:
            sub.set_defaults(force=False)
    admin_cmds.add_parser("list", help="Admins auflisten")
    admin_cmds.add_parser("run", help="wartende Admin-Aufträge abarbeiten (systemd-Dienst)")
    admin.set_defaults(func=_cmd_admin)
    cleanup = commands.add_parser("cleanup", help="alte Rohdaten (data/raw) löschen")
    cleanup.add_argument("--days", type=int, help="überschreibt storage.raw_retention_days")
    cleanup.add_argument("--dry-run", action="store_true", help="nur zählen, nichts löschen")
    cleanup.set_defaults(func=_cmd_cleanup)
    gen = commands.add_parser("gen-systemd", help="systemd-Units/-Timer aus config.yaml erzeugen")
    gen.add_argument("--out", type=Path, default=Path("deploy/systemd"), help="Zielordner")
    gen.add_argument("--app-dir", default="/opt/edgefinder", help="App-Verzeichnis auf dem Server")
    gen.add_argument(
        "--state-dir", default="/var/lib/edgefinder", help="Datenverzeichnis (schreibbar)"
    )
    gen.add_argument("--check", action="store_true", help="nichts schreiben, nur Abweichung melden")
    gen.set_defaults(func=_cmd_gen_systemd)
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
