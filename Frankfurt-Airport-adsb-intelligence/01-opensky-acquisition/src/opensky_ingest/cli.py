"""Command line entry point."""

from __future__ import annotations

import argparse
import fcntl
import os
import shutil
import sys
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Any

from . import __version__, auth
from .batch import get_batch, validate_batch
from .config import Config, ConfigError, load_config
from .crosscheck import cross_check_hours
from .discover import discover, save_record, summarise
from .errors import (
    EXIT_AUTH_REQUIRED,
    EXIT_ERROR,
    EXIT_OK,
    EXIT_USAGE,
    AuthRequired,
    IngestError,
)
from .fetch import collect_hour
from .flights import collect_flight_range
from .publish import accept_batch, publish_batch
from .reconcile import reconcile_hours
from .report import write_report
from .run import collect_range, parse_duration
from .util import parse_utc_day, parse_utc_hour


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="opensky-ingest", description="OpenSky acquisition for the EDDF dataset."
    )
    parser.add_argument("--version", action="version", version=__version__)
    parser.add_argument("--config", help="path to the dataset config file")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("login", help="log in to OpenSky in the browser and cache the session")
    sub.add_parser("discover", help="read-only check of tables, schemas and partitions")
    collect = sub.add_parser("collect-hour", help="collect one state-vector hour and commit it")
    collect.add_argument("--hour", required=True, help="UTC hour, for example 2026-10-15T12:00:00Z")
    run = sub.add_parser("run", help="collect pending state-vector hours in a UTC range")
    run.add_argument("--from", dest="start", required=True, help="first hour, inclusive")
    run.add_argument("--until", required=True, help="hour at which to stop, exclusive")
    run.add_argument(
        "--max-duration", default="3h", help="stop cleanly after this long, for example 3h"
    )
    flights = sub.add_parser("collect-flights", help="collect pending flight days in a UTC range")
    flights.add_argument("--from", dest="start", required=True, help="first day, inclusive")
    flights.add_argument("--until", required=True, help="day at which to stop, exclusive")
    flights.add_argument(
        "--max-duration", default="3h", help="stop cleanly after this long, for example 3h"
    )
    reconcile = sub.add_parser("reconcile", help="compare committed hours with source aggregates")
    reconcile.add_argument("--from", dest="start", required=True, help="first hour, inclusive")
    reconcile.add_argument("--until", required=True, help="hour at which to stop, exclusive")
    reconcile.add_argument(
        "--max-duration", default="3h", help="stop cleanly after this long, for example 3h"
    )
    check = sub.add_parser("cross-check", help="compare the legacy small box with fin receipts")
    check.add_argument("--from", dest="start", required=True, help="first hour, inclusive")
    check.add_argument("--until", required=True, help="hour at which to stop, exclusive")
    check.add_argument("--receipts", required=True, help="directory of {epoch}.receipt.json files")
    validate = sub.add_parser("validate", help="check one monthly batch against its manifests")
    validate.add_argument("--batch", required=True, help="batch id, for example b01")
    report = sub.add_parser("report", help="write the batch report from the last validation")
    report.add_argument("--batch", required=True, help="batch id, for example b01")
    accept = sub.add_parser("accept", help="record acceptance of a validated batch")
    accept.add_argument("--batch", required=True, help="batch id, for example b01")
    accept.add_argument("--notes", default="", help="required when validation listed anomalies")
    publish = sub.add_parser("publish", help="back up an accepted batch and verify checksums")
    publish.add_argument("--batch", required=True, help="batch id, for example b01")
    return parser


def cmd_login(cfg: Config, factory: Callable[..., Any]) -> int:
    auth.login(cfg, factory)
    return EXIT_OK


def cmd_discover(cfg: Config, factory: Callable[..., Any]) -> int:
    connection = factory(cfg, interactive=False)
    try:
        record = discover(connection, cfg)
    finally:
        close = getattr(connection, "close", None)
        if close:
            close()
    path = save_record(cfg, record)
    for line in summarise(record):
        print(line)
    print(f"Record written to {path}")
    return EXIT_OK if record["window_available"] else EXIT_ERROR


def ensure_free_disk(cfg: Config, minimum: int = 50 * 1024**3) -> None:
    free = shutil.disk_usage(cfg.paths.data_root).free
    if free < minimum:
        raise IngestError("LOW_DISK")


def acquire_lock(root: Path) -> int:
    path = root / "_locks" / "ingest.lock"
    path.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(path, os.O_CREAT | os.O_RDWR, 0o644)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        os.close(fd)
        raise IngestError("CONCURRENT_RUN") from None
    return fd


def cmd_collect_hour(cfg: Config, factory: Callable[..., Any], hour_text: str) -> int:
    try:
        hour = parse_utc_hour(hour_text)
    except ValueError as exc:
        raise ConfigError(str(exc)) from exc
    ensure_free_disk(cfg)
    lock = acquire_lock(cfg.paths.data_root)
    print(hour.strftime("Collecting %Y-%m-%dT%H:%M:%SZ"), flush=True)
    connection = factory(cfg, interactive=False)
    try:
        result = collect_hour(connection, cfg, hour, pause_seconds=0.5, progress=print)
    finally:
        close = getattr(connection, "close", None)
        if close:
            close()
        os.close(lock)
    print(f"outcome: {result['outcome']}")
    print(f"status: {result.get('status')}")
    if result.get("error_class"):
        print(f"error_class: {result['error_class']}")
    print(f"rows: {result.get('rows')}")
    print(f"bytes: {result.get('bytes')}")
    print(f"sha256: {result.get('sha256')}")
    print(f"path: {result.get('path')}")
    print(f"query_id: {result.get('query_id')}")
    print(f"processed_bytes: {result.get('processed_bytes')}")
    print(f"elapsed_seconds: {result.get('elapsed_seconds')}")
    return EXIT_OK if result["outcome"] in {"committed", "skipped"} else EXIT_ERROR


def _print_hour(result: dict[str, Any]) -> None:
    print(
        f"{result.get('window_start')} outcome: {result['outcome']} "
        f"status: {result.get('status')} rows: {result.get('rows')} "
        f"bytes: {result.get('bytes')} elapsed_seconds: {result.get('elapsed_seconds')}"
    )
    if result.get("error_class"):
        print(f"error_class: {result['error_class']}")


def cmd_run(
    cfg: Config,
    factory: Callable[..., Any],
    start_text: str,
    until_text: str,
    max_duration: str,
) -> int:
    try:
        start = parse_utc_hour(start_text)
        until = parse_utc_hour(until_text)
        limit = parse_duration(max_duration)
    except ValueError as exc:
        raise ConfigError(str(exc)) from exc
    ensure_free_disk(cfg)
    lock = acquire_lock(cfg.paths.data_root)
    connection = None
    try:
        connection = factory(cfg, interactive=False)
        summary = collect_range(
            connection,
            cfg,
            start,
            until,
            max_duration=limit,
            pause_seconds=0.5,
            progress=print,
            on_hour=_print_hour,
        )
    finally:
        close = getattr(connection, "close", None)
        if close:
            close()
        os.close(lock)
    print(
        f"run outcome: {summary['outcome']} reason: {summary['reason']} "
        f"committed: {summary['committed']} skipped: {summary['skipped']}"
    )
    if summary["next_hour"]:
        print(f"next_hour: {summary['next_hour']}")
    if summary["error_class"]:
        print(f"error_class: {summary['error_class']}")
    if summary["outcome"] == "finished" or summary["reason"] == "max_duration":
        return EXIT_OK
    return EXIT_ERROR


def cmd_collect_flights(
    cfg: Config,
    factory: Callable[..., Any],
    start_text: str,
    until_text: str,
    max_duration: str,
) -> int:
    try:
        start = parse_utc_day(start_text)
        until = parse_utc_day(until_text)
        limit = parse_duration(max_duration)
    except ValueError as exc:
        raise ConfigError(str(exc)) from exc
    ensure_free_disk(cfg)
    lock = acquire_lock(cfg.paths.data_root)
    connection = None
    try:
        connection = factory(cfg, interactive=False)
        summary = collect_flight_range(
            connection,
            cfg,
            start,
            until,
            max_duration=limit,
            pause_seconds=0.5,
            progress=print,
            on_day=_print_hour,
        )
    finally:
        close = getattr(connection, "close", None)
        if close:
            close()
        os.close(lock)
    print(
        f"flights outcome: {summary['outcome']} reason: {summary['reason']} "
        f"committed: {summary['committed']} skipped: {summary['skipped']}"
    )
    if summary["next_day"]:
        print(f"next_day: {summary['next_day']}")
    if summary["error_class"]:
        print(f"error_class: {summary['error_class']}")
    if summary["outcome"] == "finished" or summary["reason"] == "max_duration":
        return EXIT_OK
    return EXIT_ERROR


def _print_reconcile(item: dict[str, Any]) -> None:
    if item["match"]:
        print(f"{item['hour']} match")
        return
    names = ",".join(item["mismatches"])
    print(f"{item['hour']} mismatch {names}")


def cmd_reconcile(
    cfg: Config,
    factory: Callable[..., Any],
    start_text: str,
    until_text: str,
    max_duration: str,
) -> int:
    try:
        start = parse_utc_hour(start_text)
        until = parse_utc_hour(until_text)
        limit = parse_duration(max_duration)
    except ValueError as exc:
        raise ConfigError(str(exc)) from exc
    lock = acquire_lock(cfg.paths.data_root)
    connection = None
    try:
        connection = factory(cfg, interactive=False)
        summary = reconcile_hours(
            connection,
            cfg,
            start,
            until,
            max_duration=limit,
            pause_seconds=0.5,
            on_hour=_print_reconcile,
        )
    finally:
        close = getattr(connection, "close", None)
        if close:
            close()
        os.close(lock)
    print(
        f"reconcile outcome: {summary['outcome']} checked: {summary['checked']} "
        f"matched: {summary['matched']} mismatched: {summary['mismatched']}"
    )
    if summary["next_hour"]:
        print(f"next_hour: {summary['next_hour']}")
    print(f"report: {summary['path']}")
    return EXIT_OK if summary["outcome"] == "matched" else EXIT_ERROR


def cmd_cross_check(cfg: Config, start_text: str, until_text: str, receipts: str) -> int:
    try:
        start = parse_utc_hour(start_text)
        until = parse_utc_hour(until_text)
    except ValueError as exc:
        raise ConfigError(str(exc)) from exc
    lock = acquire_lock(cfg.paths.data_root)
    try:
        summary = cross_check_hours(cfg, start, until, Path(receipts))
    finally:
        os.close(lock)
    print(
        f"cross-check outcome: {summary['outcome']} checked: {summary['checked']} "
        f"matched: {summary['matched']} mismatched: {summary['mismatched']}"
    )
    print(f"report: {summary['path']}")
    return EXIT_OK if summary["outcome"] == "matched" else EXIT_ERROR


def cmd_validate(cfg: Config, batch_id: str) -> int:
    batch = get_batch(batch_id)
    lock = acquire_lock(cfg.paths.data_root)
    try:
        summary = validate_batch(cfg, batch)
    finally:
        os.close(lock)
    print(
        f"validate outcome: {summary['outcome']} hours: {summary['expected_hours']} "
        f"complete: {summary['complete']} problems: {len(summary['problems'])} "
        f"anomalies: {len(summary['anomalies'])}"
    )
    print(f"manifest: {summary['path']}")
    return EXIT_OK if summary["outcome"] != "failed" else EXIT_ERROR


def cmd_report(cfg: Config, batch_id: str) -> int:
    batch = get_batch(batch_id)
    summary = write_report(cfg, batch)
    print(f"report outcome: {summary['outcome']}")
    print(f"report: {summary['path']}")
    return EXIT_OK


def cmd_accept(cfg: Config, batch_id: str, notes: str) -> int:
    batch = get_batch(batch_id)
    lock = acquire_lock(cfg.paths.data_root)
    try:
        summary = accept_batch(cfg, batch, notes=notes)
    finally:
        os.close(lock)
    print(f"accept outcome: {summary['outcome']} who: {summary['who']}")
    return EXIT_OK


def cmd_publish(cfg: Config, batch_id: str) -> int:
    batch = get_batch(batch_id)
    lock = acquire_lock(cfg.paths.data_root)
    try:
        summary = publish_batch(cfg, batch)
    finally:
        os.close(lock)
    print(
        f"publish outcome: {summary['outcome']} copied: {summary['copied']} "
        f"checked: {summary['checked']}"
    )
    return EXIT_OK if summary["outcome"] == "published" else EXIT_ERROR


def main(
    argv: Sequence[str] | None = None,
    connection_factory: Callable[..., Any] = auth.make_connection,
) -> int:
    parser = build_parser()
    try:
        args = parser.parse_args(argv)
    except SystemExit as exc:
        return int(exc.code) if isinstance(exc.code, int) else EXIT_USAGE
    try:
        cfg = load_config(args.config)
        if args.command == "cross-check":
            return cmd_cross_check(cfg, args.start, args.until, args.receipts)
        if args.command == "validate":
            return cmd_validate(cfg, args.batch)
        if args.command == "report":
            return cmd_report(cfg, args.batch)
        if args.command == "accept":
            return cmd_accept(cfg, args.batch, args.notes)
        if args.command == "publish":
            return cmd_publish(cfg, args.batch)
        _ = cfg.username  # fail early if OPENSKY_USERNAME is not set
        if args.command == "login":
            return cmd_login(cfg, connection_factory)
        if args.command == "discover":
            return cmd_discover(cfg, connection_factory)
        if args.command == "collect-hour":
            return cmd_collect_hour(cfg, connection_factory, args.hour)
        if args.command == "run":
            return cmd_run(cfg, connection_factory, args.start, args.until, args.max_duration)
        if args.command == "collect-flights":
            return cmd_collect_flights(
                cfg, connection_factory, args.start, args.until, args.max_duration
            )
        if args.command == "reconcile":
            return cmd_reconcile(cfg, connection_factory, args.start, args.until, args.max_duration)
    except AuthRequired as exc:
        print(str(exc), file=sys.stderr)
        return EXIT_AUTH_REQUIRED
    except (ConfigError, IngestError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return EXIT_ERROR
    return EXIT_USAGE


if __name__ == "__main__":
    sys.exit(main())
