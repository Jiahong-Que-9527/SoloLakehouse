"""Command line entry point."""

from __future__ import annotations

import argparse
import sys
from collections.abc import Callable, Sequence
from typing import Any

from . import __version__, auth
from .config import Config, ConfigError, load_config
from .discover import discover, save_record, summarise
from .errors import (
    EXIT_AUTH_REQUIRED,
    EXIT_ERROR,
    EXIT_OK,
    EXIT_USAGE,
    AuthRequired,
    IngestError,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="opensky-ingest", description="OpenSky acquisition for the EDDF dataset."
    )
    parser.add_argument("--version", action="version", version=__version__)
    parser.add_argument("--config", help="path to the dataset config file")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("login", help="log in to OpenSky in the browser and cache the session")
    sub.add_parser("discover", help="read-only check of tables, schemas and partitions")
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
        _ = cfg.username  # fail early if OPENSKY_USERNAME is not set
        if args.command == "login":
            return cmd_login(cfg, connection_factory)
        if args.command == "discover":
            return cmd_discover(cfg, connection_factory)
    except AuthRequired as exc:
        print(str(exc), file=sys.stderr)
        return EXIT_AUTH_REQUIRED
    except (ConfigError, IngestError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return EXIT_ERROR
    return EXIT_USAGE


if __name__ == "__main__":
    sys.exit(main())
