"""SQLite index and the append-only ledger. Neither is the commit marker."""

from __future__ import annotations

import json
import os
import sqlite3
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS hours (
    hour INTEGER PRIMARY KEY,
    status TEXT NOT NULL,
    attempts INTEGER NOT NULL,
    rows INTEGER,
    bytes INTEGER,
    sha256 TEXT,
    relative_path TEXT,
    error_class TEXT,
    run_id TEXT,
    updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS runs (
    run_id TEXT PRIMARY KEY,
    started_at TEXT NOT NULL,
    tool_version TEXT,
    git_commit TEXT
);
"""


def connect(path: Path) -> sqlite3.Connection:
    path.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(path)
    db.execute("PRAGMA journal_mode=WAL")
    db.executescript(SCHEMA)
    return db


def record_hour(db: sqlite3.Connection, manifest: dict, *, error_class: str | None = None) -> None:
    db.execute(
        """
        INSERT INTO hours (
            hour, status, attempts, rows, bytes, sha256, relative_path,
            error_class, run_id, updated_at
        ) VALUES (?, ?, 1, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(hour) DO UPDATE SET
            status = excluded.status,
            attempts = hours.attempts + 1,
            rows = excluded.rows,
            bytes = excluded.bytes,
            sha256 = excluded.sha256,
            relative_path = excluded.relative_path,
            error_class = excluded.error_class,
            run_id = excluded.run_id,
            updated_at = excluded.updated_at
        """,
        (
            manifest["hour"],
            manifest["status"],
            manifest.get("rows"),
            manifest.get("bytes"),
            manifest.get("sha256"),
            manifest.get("path"),
            error_class,
            manifest.get("run_id"),
            manifest["collected_at"],
        ),
    )
    db.commit()


def record_run(
    db: sqlite3.Connection, run_id: str, started_at: str, tool_version: str, git_commit: str
) -> None:
    db.execute(
        """
        INSERT INTO runs (run_id, started_at, tool_version, git_commit)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(run_id) DO NOTHING
        """,
        (run_id, started_at, tool_version, git_commit),
    )
    db.commit()


def append_event(root: Path, event: dict) -> None:
    path = root / "metadata" / "ledger" / "events.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a") as stream:
        stream.write(json.dumps(event, sort_keys=True) + "\n")
        stream.flush()
        os.fsync(stream.fileno())
