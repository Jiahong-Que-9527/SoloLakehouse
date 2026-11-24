"""Rehearse the phase 03 Geometry v2 ingestion contract in local DuckDB."""

import fcntl
import importlib.util
import sys
from pathlib import Path

import duckdb

PHASE_03 = Path(__file__).resolve().parent.parent / "03-airport-analytics" / "ingest_release.py"
spec = importlib.util.spec_from_file_location("frankfurt_airport_phase03_ingest", PHASE_03)
phase03 = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = phase03
spec.loader.exec_module(phase03)


def geometry_counts(connection, table: str, release_id: str) -> dict:
    counts = connection.execute(f"""
        SELECT count(*), count(*) FILTER (WHERE status = 'labeled' AND taxi_in_s IS NOT NULL),
               count(*) - count(DISTINCT (day_utc, flight_key))
        FROM {table} WHERE release_id = ?
    """, [release_id]).fetchone()
    return dict(zip(("rows", "labeled_rows", "duplicate_keys"), counts, strict=True))


def ingest_local(directory: Path, handoff: dict, database: Path) -> dict:
    release_id = handoff["release_id"]
    manifest_hash = handoff["manifest_sha256"]
    if phase03.digest(directory / "manifest.json") != manifest_hash:
        raise ValueError("Gold manifest no longer matches the verified handoff")
    verdict = phase03.verify_release(directory)
    if not verdict.ok:
        raise ValueError(f"phase 03 blocked the release: {verdict.reason}")
    table = phase03.target_table(verdict.manifest, phase03.GEOMETRY_TABLE)
    if verdict.manifest["release_id"] != release_id:
        raise ValueError("phase 03 received a different release ID")
    parquet = directory / "data/part-0001.parquet"
    expected = {"rows": handoff["rows"], "labeled_rows": handoff["coverage_status_counts"]["labeled"],
                "duplicate_keys": 0}
    database.parent.mkdir(parents=True, exist_ok=True)
    with database.with_suffix(".lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        with duckdb.connect(str(database), config={"threads": 2}) as connection:
            connection.execute("BEGIN TRANSACTION")
            connection.execute("""CREATE TABLE IF NOT EXISTS ingest_ledger (
                release_id VARCHAR PRIMARY KEY, manifest_sha256 VARCHAR NOT NULL, row_count BIGINT NOT NULL
            )""")
            ledger = connection.execute("""SELECT manifest_sha256, row_count FROM ingest_ledger
                                            WHERE release_id = ?""", [release_id]).fetchone()
            if ledger is None:
                connection.execute("CREATE TEMP TABLE release_stage AS SELECT *, ?::VARCHAR AS release_id FROM read_parquet(?)",
                                   [release_id, str(parquet)])
                if (phase03.digest(parquet) != verdict.manifest["files"]["data/part-0001.parquet"]["sha256"]
                        or phase03.digest(directory / "manifest.json") != manifest_hash
                        or geometry_counts(connection, "release_stage", release_id) != expected):
                    raise ValueError("staged release failed checksum or count reconciliation")
                connection.execute(f"CREATE TABLE IF NOT EXISTS {table} AS SELECT * FROM release_stage WHERE false")
                connection.execute(f"INSERT INTO {table} BY NAME SELECT * FROM release_stage")
                connection.execute("INSERT INTO ingest_ledger VALUES (?, ?, ?)", [release_id, manifest_hash, expected["rows"]])
            elif ledger != (manifest_hash, expected["rows"]):
                raise ValueError("this release ID is already pinned to a different manifest or row count")
            counts = geometry_counts(connection, table, release_id)
            if counts != expected:
                raise ValueError("local analytics table failed count or duplicate-key reconciliation")
            connection.execute("COMMIT")
    return {"backend": "duckdb_local", "table": table, "release_id": release_id,
            "manifest_sha256": manifest_hash, "status": "already_ingested" if ledger else "ingested",
            "rows_added": 0 if ledger else counts["rows"], "geometry_counts": counts}
