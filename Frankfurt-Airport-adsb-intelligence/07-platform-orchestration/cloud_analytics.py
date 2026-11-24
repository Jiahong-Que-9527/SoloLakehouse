"""Reconcile an existing BigQuery release using one capped SELECT per run."""

import json
import re
import subprocess
from uuid import uuid4

from local_analytics import phase03

LOCATION = "europe-west3"
MAX_BYTES_BILLED = 100 * 1024 * 1024


def bq_json(command: list[str], sql: str | None = None):
    result = subprocess.run(command, input=sql, text=True, capture_output=True, check=False, timeout=120)
    if result.returncode:
        raise RuntimeError(f"BigQuery read failed: {(result.stderr or result.stdout).strip()}")
    return json.loads(result.stdout)


def reconcile_existing_release(project: str, handoff: dict) -> dict:
    if not re.fullmatch(r"[a-z][a-z0-9-]{4,28}[a-z0-9]", project):
        raise ValueError("FRANKFURT_AIRPORT_BQ_PROJECT must be a Google Cloud project ID")
    release_id = handoff["release_id"]
    expected = {"rows": handoff["rows"], "labeled_rows": handoff["coverage_status_counts"]["labeled"],
                "duplicate_keys": 0}
    dataset = f"{project}.aviation"
    sql = f"""
        WITH ledger AS (
          SELECT ARRAY_AGG(STRUCT(data_product, manifest_sha256, row_count)) AS entries
          FROM `{dataset}.ingest_ledger`
          WHERE release_id = @release_id AND status = 'ingested'
        ), geometry AS (
          SELECT COUNT(*) AS total_rows,
                 COUNTIF(status = 'labeled' AND taxi_in_s IS NOT NULL) AS labeled_rows,
                 COUNT(*) - COUNT(DISTINCT TO_JSON_STRING(STRUCT(day_utc, flight_key))) AS duplicate_keys
          FROM `{dataset}.{phase03.GEOMETRY_TABLE}`
          WHERE release_id = @release_id
        )
        SELECT ledger.entries, geometry.* FROM ledger CROSS JOIN geometry
    """
    command = ["bq", "--quiet", "--format=json", f"--project_id={project}", f"--location={LOCATION}"]
    job_id = f"frankfurt_airport_reconcile_{uuid4().hex}"
    rows = bq_json([*command, f"--job_id={job_id}", "query", "--use_legacy_sql=false",
                    f"--maximum_bytes_billed={MAX_BYTES_BILLED}", f"--parameter=release_id:STRING:{release_id}"], sql)
    if len(rows) != 1:
        raise ValueError(f"unexpected query result for {release_id} (job {job_id})")
    row, = rows
    entries = row["entries"] or []
    if len(entries) != 1:
        raise ValueError(f"expected one ingested ledger entry for {release_id}, got {len(entries)} (job {job_id})")
    entry, = entries
    if (entry["data_product"] != "ground-ops" or entry["manifest_sha256"] != handoff["manifest_sha256"]
            or int(entry["row_count"]) != expected["rows"]):
        raise ValueError(f"ledger identity or manifest disagrees for {release_id} (job {job_id})")
    counts = {"rows": int(row["total_rows"]), "labeled_rows": int(row["labeled_rows"]),
              "duplicate_keys": int(row["duplicate_keys"])}
    if counts != expected:
        raise ValueError(f"BigQuery table counts disagree for {release_id}: {counts} (job {job_id})")
    job = bq_json([*command, "show", "--job", f"{project}:{job_id}"])
    stats = job["statistics"]["query"]
    billed = int(stats["totalBytesBilled"])
    if stats["statementType"] != "SELECT" or not 0 <= billed <= MAX_BYTES_BILLED:
        raise ValueError(f"unexpected query type or billing for job {job_id}")
    return {"backend": "bigquery_read_only", "status": "already_ingested", "release_id": release_id,
            "manifest_sha256": handoff["manifest_sha256"], "rows_added": 0, "geometry_counts": counts,
            "job_id": job_id, "bytes_billed": billed, "max_bytes_billed": MAX_BYTES_BILLED,
            "cache_hit": stats["cacheHit"], "project": project, "location": LOCATION}
