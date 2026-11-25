"""Gold release ingestion for the aviation tables (03 M3, ADR-003/004).

One run ingests one release folder from the landing bucket:

    verify (manifest checksums + validation status)  ->  guard (ledger +
    release_id column)  ->  materialise the managed Iceberg table  ->
    insert with release_id  ->  reconcile row counts  ->  ledger record.

A release that fails verification is recorded as `blocked` and never
reaches a table. Re-ingesting a release that is already recorded as
`ingested` adds no rows (02's release_gate produced the release; ADR-004
fixed the format: BigQuery managed Iceberg tables written by DML).
"""
import argparse
import hashlib
import json
import shutil
import sys
import tempfile
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

TABLE_SCHEMA = [
    ("day_utc", "DATE"), ("flight_key", "STRING"), ("icao24", "STRING"),
    ("callsign", "STRING"), ("lastseen_epoch_s", "INT64"),
    ("touchdown_estimate_epoch_s", "INT64"), ("surface_start_epoch_s", "INT64"),
    ("taxi_end_epoch_s", "INT64"), ("taxi_in_s", "INT64"),
    ("surface_point_count", "INT64"), ("taxi_path_m", "FLOAT64"),
    ("mean_surface_gap_s", "FLOAT64"), ("max_surface_gap_s", "FLOAT64"),
    ("end_distance_m", "FLOAT64"), ("status", "STRING"),
    ("release_id", "STRING"),
]

LEDGER_SCHEMA = [
    ("release_id", "STRING"), ("data_product", "STRING"),
    ("manifest_sha256", "STRING"), ("row_count", "INT64"),
    ("status", "STRING"), ("reason", "STRING"), ("ingested_at", "TIMESTAMP"),
]

DDL_TYPES = {n: t for n, t in TABLE_SCHEMA}
RADIUS_LABEL_VERSION = "taxi-in-radius-v1"
GEOMETRY_LABEL_VERSION = "taxi-in-geometry-v2"
RADIUS_TABLE = "ground_ops_arrivals"
GEOMETRY_TABLE = "ground_ops_arrivals_geometry_v2"


def digest(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


@dataclass
class Verification:
    ok: bool
    reason: str
    manifest: dict = field(default_factory=dict)


def verify_release(local_dir: Path) -> Verification:
    """Checksum every file against the manifest and require a passed gate."""
    manifest_path = local_dir / "manifest.json"
    if not manifest_path.is_file():
        return Verification(False, "no manifest.json in the release")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    for name, entry in manifest.get("files", {}).items():
        file = local_dir / name
        if not file.is_file():
            return Verification(False, f"release file missing: {name}")
        if digest(file) != entry["sha256"]:
            return Verification(False, f"checksum mismatch: {name}")
    validation = local_dir / "validation.json"
    if not validation.is_file():
        return Verification(False, "no validation.json in the release")
    gate = json.loads(validation.read_text(encoding="utf-8"))
    if gate.get("status") != "passed":
        failed = [c["name"] for c in gate.get("checks", []) if not c["passed"]]
        return Verification(False, f"release gate status {gate.get('status')!r}: "
                            f"failed checks {failed}")
    contract = local_dir / "contract.yaml"
    if not contract.is_file() or digest(contract) != manifest["files"].get(
            "contract.yaml", {}).get("sha256"):
        return Verification(False, "contract.yaml missing or not covered by the manifest")
    return Verification(True, "verified", manifest)


class BigQueryOps:
    """The BigQuery calls the ingest needs; subclass or monkeypatch in tests."""

    def __init__(self, project: str, dataset: str, region: str):
        from google.cloud import bigquery
        self.project, self.dataset, self.region = project, dataset, region
        self.client = bigquery.Client(project=project)
        self.max_bytes_billed = None
        self.query_jobs = []

    def sql(self, statement: str) -> list[dict]:
        from google.cloud import bigquery

        config = bigquery.QueryJobConfig(maximum_bytes_billed=self.max_bytes_billed)
        job = self.client.query(statement, job_config=config, location=self.region)
        rows = [dict(row) for row in job.result()]
        self.query_jobs.append({"job_id": job.job_id, "bytes_billed": job.total_bytes_billed})
        return rows

    def qualified(self, table: str) -> str:
        return f"`{self.project}.{self.dataset}.{table}`"

    def ensure_ledger(self) -> None:
        cols = ", ".join(f"{n} {t}" for n, t in LEDGER_SCHEMA)
        self.sql(f"CREATE TABLE IF NOT EXISTS {self.qualified('ingest_ledger')} "
                 f"({cols})")

    def already_ingested(self, release_id: str) -> bool:
        rows = self.sql(f"SELECT COUNT(*) AS n FROM {self.qualified('ingest_ledger')} "
                        f"WHERE release_id = '{release_id}' AND status = 'ingested'")
        return rows[0]["n"] > 0

    def record(self, release_id: str, data_product: str, manifest_sha: str,
               row_count: int, status: str, reason: str) -> None:
        now = datetime.now(timezone.utc).isoformat()
        safe = reason.replace("\\", "\\\\").replace("'", "\\'")
        self.sql("INSERT INTO " + self.qualified("ingest_ledger") +
                 f" VALUES ('{release_id}', '{data_product}', '{manifest_sha}', "
                 f"{row_count}, '{status}', '{safe}', TIMESTAMP '{now}')")

    def ensure_table(self, table: str, gold_bucket: str, connection: str) -> None:
        cols = ", ".join(f"{n} {t}" for n, t in TABLE_SCHEMA)
        self.sql(f"CREATE TABLE IF NOT EXISTS {self.qualified(table)} ({cols}) "
                 f"CLUSTER BY release_id "
                 f"WITH CONNECTION `{self.project}.{self.region}.{connection}` "
                 f"OPTIONS (file_format = 'PARQUET', table_format = 'ICEBERG', "
                 f"storage_uri = 'gs://{gold_bucket}/tables/{table}')")

    def stage_external(self, table: str, landing_uri: str) -> None:
        self.sql(f"CREATE OR REPLACE EXTERNAL TABLE {self.qualified(table)} "
                 f"OPTIONS (format = 'PARQUET', uris = ['{landing_uri}'])")

    def apply_release(self, table: str, external: str, release_id: str,
                      expected_rows: int) -> int:
        """Insert once, guarded by the release_id column (ADR-004 check 4)."""
        self.sql(
            f"INSERT INTO {self.qualified(table)}\n"
            f"SELECT t.*, '{release_id}' AS release_id\n"
            f"FROM {self.qualified(external)} t\n"
            f"WHERE NOT EXISTS (SELECT 1 FROM {self.qualified(table)} "
            f"WHERE release_id = '{release_id}')")
        counted = self.sql(f"SELECT COUNT(*) AS n FROM {self.qualified(table)} "
                           f"WHERE release_id = '{release_id}'")[0]["n"]
        if counted != expected_rows:
            raise RuntimeError(
                f"row reconciliation failed: table has {counted} rows for "
                f"{release_id}, manifest says {expected_rows}")
        return counted

    def geometry_counts(self, release_id: str) -> dict:
        counts = self.sql(f"""
            WITH grain AS (
                SELECT day_utc, flight_key, COUNT(*) AS n,
                       COUNTIF(status = 'labeled') AS labeled
                FROM {self.qualified(GEOMETRY_TABLE)}
                WHERE release_id = '{release_id}'
                GROUP BY day_utc, flight_key
            )
            SELECT COALESCE(SUM(n), 0) AS total_rows,
                   COALESCE(SUM(labeled), 0) AS labeled_rows,
                   COUNTIF(n > 1) AS duplicate_keys
            FROM grain
        """)[0]
        return {"rows": counts["total_rows"], "labeled_rows": counts["labeled_rows"],
                "duplicate_keys": counts["duplicate_keys"]}


def download_release(landing: str, workspace: Path) -> Path:
    """Landing may be a gs:// URI or a local directory (tests, dry runs)."""
    if not landing.startswith("gs://"):
        return Path(landing)
    from google.cloud import storage
    client = storage.Client()
    parts = landing.removeprefix("gs://").split("/", 1)
    bucket_name, prefix = parts[0], parts[1].rstrip("/")
    blobs = client.list_blobs(bucket_name, prefix=f"{prefix}/")
    local_dir = workspace / "release"
    for blob in blobs:
        rel = Path(blob.name).relative_to(prefix)
        target = local_dir / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        blob.download_to_filename(str(target))
    return local_dir


def target_table(manifest: dict, requested: str | None) -> str:
    """Keep geometry and radius labels in separate Iceberg tables."""
    label_version = manifest.get("label_version", RADIUS_LABEL_VERSION)
    if label_version == GEOMETRY_LABEL_VERSION:
        if manifest.get("contract_version") != "2":
            raise ValueError("geometry labels require contract version 2")
        if requested not in (None, GEOMETRY_TABLE):
            raise ValueError(f"{label_version} must use {GEOMETRY_TABLE}")
        return GEOMETRY_TABLE
    if label_version != RADIUS_LABEL_VERSION:
        raise ValueError(f"unsupported label version {label_version!r}")
    if (manifest.get("contract_version") == "2"
            or "airport_geometry" in manifest.get("input", {})):
        raise ValueError("geometry release requires an explicit geometry label version")
    if requested == GEOMETRY_TABLE:
        raise ValueError(f"{GEOMETRY_TABLE} requires {GEOMETRY_LABEL_VERSION}")
    return requested or RADIUS_TABLE


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--landing", required=True,
                        help="gs://bucket/releases/v002 or a local release directory")
    parser.add_argument("--project", required=True)
    parser.add_argument("--dataset", default="aviation")
    parser.add_argument("--region", default="europe-west3")
    parser.add_argument("--gold-bucket", required=True)
    parser.add_argument("--connection", default="aviation-gold-conn")
    parser.add_argument("--table", help="target table, defaults to the label version's table")
    parser.add_argument("--max-bytes-billed", type=int, help="per-query BigQuery billing cap")
    parser.add_argument("--expect-geometry-labels", type=int,
                        help="verify the Geometry v2 row count, label count and grain")
    args = parser.parse_args()
    if args.max_bytes_billed is not None and args.max_bytes_billed <= 0:
        parser.error("--max-bytes-billed must be positive")

    workspace = Path(tempfile.mkdtemp(prefix="aviation-ingest-"))
    try:
        local_dir = download_release(args.landing, workspace)
        verdict = verify_release(local_dir)
        if not verdict.ok:
            print(json.dumps({"status": "blocked", "reason": verdict.reason}))
            sys.exit(1)  # nothing was written to any table
        manifest = verdict.manifest
        try:
            table = target_table(manifest, args.table)
        except ValueError as exc:
            print(json.dumps({"status": "blocked", "reason": str(exc)}))
            sys.exit(1)
        release_id = manifest["release_id"]
        data_product = manifest.get("data_product", "unknown")
        manifest_sha = digest(local_dir / "manifest.json")
        expected_rows = manifest["files"]["data/part-0001.parquet"]["rows"]
        if args.expect_geometry_labels is not None and (
            table != GEOMETRY_TABLE or not 0 <= args.expect_geometry_labels <= expected_rows
        ):
            parser.error("--expect-geometry-labels requires a valid count for a Geometry v2 release")

        ops = BigQueryOps(args.project, args.dataset, args.region)
        ops.max_bytes_billed = args.max_bytes_billed
        ops.ensure_ledger()
        already_ingested = ops.already_ingested(release_id)
        result = {"status": "already_ingested", "release_id": release_id, "rows_added": 0}
        if not already_ingested:
            ops.ensure_table(table, args.gold_bucket, args.connection)
            external = f"tmp_ingest_{table}"
            parquet_uri = f"{args.landing.rstrip('/')}/data/part-0001.parquet"
            ops.stage_external(external, parquet_uri)
            rows = ops.apply_release(table, external, release_id, expected_rows)
            result = {"status": "ingested", "release_id": release_id, "rows": rows}
        if args.expect_geometry_labels is not None:
            actual = ops.geometry_counts(release_id)
            expected = {"rows": expected_rows, "labeled_rows": args.expect_geometry_labels,
                        "duplicate_keys": 0}
            result["geometry_counts"] = actual
            if actual != expected:
                result.update(status="verification_failed", expected_geometry_counts=expected,
                              query_jobs=ops.query_jobs)
                print(json.dumps(result))
                sys.exit(1)
        if not already_ingested:
            ops.record(release_id, data_product, manifest_sha, rows, "ingested", "")
        if args.max_bytes_billed is not None or args.expect_geometry_labels is not None:
            result["query_jobs"] = ops.query_jobs
        print(json.dumps(result))
    finally:
        shutil.rmtree(workspace, ignore_errors=True)


if __name__ == "__main__":
    main()
