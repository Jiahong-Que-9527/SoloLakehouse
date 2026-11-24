"""The four retryable D02 tasks, using the D01 ECB contracts and Delta writes."""

import json
import re
from dataclasses import asdict, dataclass
from datetime import UTC, date, datetime
from hashlib import sha256
from time import monotonic
from typing import Any

from ecb_lakehouse.contracts import sha256_file
from ecb_lakehouse.databricks_runner import (
    _append_bronze_if_absent,
    _append_rejects_if_absent,
    _delta_version,
    _ensure_tables,
    _merge_silver_delta,
    _read_silver_rows,
    _validate_identifier,
    _write_gold_daily,
)
from ecb_lakehouse.transforms import (
    BronzeRow,
    SilverRow,
    load_bronze_csv,
    normalize_silver,
)


@dataclass(frozen=True)
class Request:
    start: date
    end: date
    batch: str
    variant: str
    git_sha: str

    @classmethod
    def parse(cls, start, end, batch, variant, git_sha):
        start, end = date.fromisoformat(start), date.fromisoformat(end)
        if not date(2025, 1, 1) <= start <= end <= date(2025, 3, 31):
            raise ValueError("window must be inside 2025-01-01 through 2025-03-31")
        if not re.fullmatch(r"[a-z0-9][a-z0-9_-]{0,47}", batch):
            raise ValueError("invalid source_batch_id")
        if variant not in {"initial", "faulty", "corrected"}:
            raise ValueError("invalid fixture_variant")
        if not re.fullmatch(r"[0-9a-f]{40}", git_sha):
            raise ValueError("git_sha must be a full commit")
        return cls(start, end, batch, variant, git_sha)

    def contains(self, day: date) -> bool:
        return self.start <= day <= self.end


@dataclass(frozen=True)
class Batch:
    request: Request
    source_hashes: dict[str, str]
    rows: dict[str, list[BronzeRow]]
    rate_context: tuple[SilverRow, ...]
    batch_key: str
    release_id: str


def prepare(request, d01_fixtures, d02_fixtures):
    fx_path = {
        "initial": d01_fixtures / "ecb_fx_2025q1.csv",
        "faulty": d02_fixtures / "fx_conflict.csv",
        "corrected": d01_fixtures / "ecb_fx_2025q1_revision.csv",
    }[request.variant]
    paths = {"fx": fx_path, "rate": d01_fixtures / "ecb_policy_rates_2025q1.csv"}
    hashes = {path.name: sha256_file(path) for path in paths.values()}
    identity = [request.batch, str(request.start), str(request.end), hashes]
    key = sha256(json.dumps(identity, sort_keys=True).encode()).hexdigest()[:24]
    release = sha256(f"{key}:{request.git_sha}".encode()).hexdigest()[:24]
    now = datetime.now(UTC).isoformat()
    rows = {}
    for kind, path in paths.items():
        rows[kind] = [
            row for row in load_bronze_csv(path, key, now) if in_window(request, row)
        ]
    rate_context = normalize_silver(
        [
            row
            for row in load_bronze_csv(paths["rate"], key, now)
            if row.observation_date < "2025-01-01"
        ],
        "irregular",
    ).rows
    return Batch(request, hashes, rows, rate_context, key, f"d02-{release}")


def in_window(request, row):
    try:
        day = date.fromisoformat(row.observation_date)
    except ValueError:
        # The full fixture's invalid date is retained in Bronze for rejection evidence.
        return (request.start, request.end) == (date(2025, 1, 1), date(2025, 3, 31))
    return request.contains(day)


def outside_window_digest(request, silver):
    outside = {
        kind: [
            asdict(row) for row in rows if not request.contains(row.observation_date)
        ]
        for kind, rows in silver.items()
    }
    return sha256(json.dumps(outside, sort_keys=True, default=str).encode()).hexdigest()


def validate_quality(batch, silver, report):
    if report["outside_before"] != report["outside_after"]:
        raise ValueError(
            "transform changed Silver records outside the requested window"
        )
    for kind, frequency in (("fx", "daily"), ("rate", "irregular")):
        normalized = normalize_silver(batch.rows[kind], frequency)
        rows = silver[kind]
        keyed = {(row.series_key, row.observation_date): row for row in rows}
        if len(rows) != len(keyed):
            raise ValueError(f"duplicate business key in Silver {kind}")
        reasons = {row.reject_reason for row in normalized.rejects}
        allowed = (
            {
                "invalid_observation_date",
                "non_numeric_value",
                "null_series_key",
                "conflicting_duplicate_in_batch",
            }
            if batch.request.variant == "initial" and kind == "fx"
            else set()
        )
        if unexpected := reasons - allowed:
            raise ValueError(
                f"{kind} quality rejected input: {', '.join(sorted(unexpected))}"
            )
        if kind == "fx" and not normalized.rows:
            raise ValueError("window has no valid FX observations")
        for row in normalized.rows:
            actual = keyed.get((row.series_key, row.observation_date))
            expected = (row.value, row.unit, row.frequency)
            if (
                actual is None
                or (actual.value, actual.unit, actual.frequency) != expected
            ):
                raise ValueError(
                    f"Silver {kind} differs from the fixture at {row.observation_date}"
                )


class Tasks:
    def __init__(
        self, spark: Any, catalog: str, schema: str, run_id: str, batch: Batch
    ):
        self.spark = spark
        self.catalog = _validate_identifier(catalog, "catalog")
        self.schema = _validate_identifier(schema, "schema")
        if not self.schema.startswith("ecb_d02_"):
            raise ValueError("D02 requires a dedicated ecb_d02_* schema")
        if not run_id.isascii() or not run_id.isdecimal():
            raise ValueError("A Databricks job run ID is required")
        self.run_id = run_id
        self.batch = batch
        self.records = self.table("d02_task_events")
        self.ledger = self.table("d02_releases")
        self.tables = _ensure_tables(
            spark, self.catalog, self.schema, reset_tables=False
        )
        self.sql(f"""
            CREATE TABLE IF NOT EXISTS {self.records} (
                run_id STRING, task STRING, status STRING, recorded_at TIMESTAMP,
                duration_ms BIGINT, source_batch_id STRING, batch_key STRING,
                window_start DATE, window_end DATE, git_sha STRING, detail STRING
            ) USING DELTA
        """)
        self.sql(f"""
            CREATE TABLE IF NOT EXISTS {self.ledger} (
                release_id STRING, published_at TIMESTAMP, job_run_id STRING,
                source_batch_id STRING, batch_key STRING, git_sha STRING,
                window_start DATE, window_end DATE, gold_table STRING,
                gold_rows BIGINT, silver_fx_version BIGINT, silver_rate_version BIGINT,
                source_hashes STRING
            ) USING DELTA
        """)

    def table(self, name):
        return f"{self.catalog}.{self.schema}.{name}"

    def sql(self, query, **args):
        return self.spark.sql(query, args=args)

    def event(self, task, status, started, detail):
        request = self.batch.request
        self.sql(
            f"""
            INSERT INTO {self.records}
            VALUES (:run, :task, :status, current_timestamp(), :duration, :batch, :key,
                    :start, :end, :sha, :detail)
            """,
            run=self.run_id,
            task=task,
            status=status,
            duration=int((monotonic() - started) * 1000),
            batch=request.batch,
            key=self.batch.batch_key,
            start=request.start,
            end=request.end,
            sha=request.git_sha,
            detail=json.dumps(detail),
        )

    def recorded(self, task, status):
        rows = self.sql(
            f"""
            SELECT detail FROM {self.records}
            WHERE run_id=:run AND task=:task AND status=:status AND batch_key=:key
            ORDER BY recorded_at DESC LIMIT 1
            """,
            run=self.run_id,
            task=task,
            status=status,
            key=self.batch.batch_key,
        ).collect()
        return json.loads(rows[0]["detail"]) if rows else None

    def published(self):
        rows = self.sql(
            f"SELECT * FROM {self.ledger} WHERE release_id=:rid",
            rid=self.batch.release_id,
        ).collect()
        if len(rows) > 1:
            raise RuntimeError("duplicate release identity")
        return rows[0].asDict() if rows else None

    def current(self):
        rows = self.sql(f"""
            SELECT release_id, gold_table FROM {self.ledger}
            ORDER BY published_at DESC, release_id DESC LIMIT 1
        """).collect()
        return rows[0].asDict() if rows else None

    def counts(self):
        return self.sql(f"SELECT COUNT(*) AS n FROM {self.ledger}").collect()[0]["n"]

    def silver(self):
        return {
            kind: _read_silver_rows(self.spark, self.tables[f"silver_{kind}"])
            for kind in ("fx", "rate")
        }

    def versions(self):
        return {
            kind: _delta_version(self.spark, self.tables[f"silver_{kind}"])
            for kind in ("fx", "rate")
        }

    def ingest(self, retry_once, started):
        result = {}
        for kind, rows in self.batch.rows.items():
            table = self.tables[f"bronze_{kind}"]
            result[kind] = bool(rows) and _append_bronze_if_absent(
                self.spark,
                table,
                rows,
                self.batch.batch_key,
            )
        injected = self.recorded("ingest", "retry_injected")
        if retry_once and injected is None:
            self.event("ingest", "retry_injected", started, {"bronze_appended": result})
            raise RuntimeError("ingest: injected transient failure after Bronze commit")
        return {"bronze_appended": result, "recovered_retry": injected is not None}

    def transform(self):
        if self.published():
            return {"already_published": True}
        before = outside_window_digest(self.batch.request, self.silver())
        reject_count = 0
        for kind, frequency in (("fx", "daily"), ("rate", "irregular")):
            table = self.tables[f"bronze_{kind}"]
            rows = self.sql(
                f"SELECT * FROM {table} WHERE source_batch_id=:key",
                key=self.batch.batch_key,
            ).collect()
            if len(rows) != len(self.batch.rows[kind]):
                raise ValueError(
                    f"Bronze {kind} row count differs from the pinned batch"
                )
            normalized = normalize_silver(
                [BronzeRow(**row.asDict()) for row in rows], frequency
            )
            if normalized.rejects:
                reject_count += len(normalized.rejects)
                _append_rejects_if_absent(
                    self.spark,
                    self.tables["silver_reject"],
                    normalized.rejects,
                    self.batch.batch_key,
                    normalized.rejects[0].source_file,
                )
            if normalized.rows:
                _merge_silver_delta(
                    self.spark,
                    self.tables[f"silver_{kind}"],
                    normalized.rows,
                    "d02_inputs",
                )
        return {
            "outside_before": before,
            "outside_after": outside_window_digest(self.batch.request, self.silver()),
            "reject_count": reject_count,
        }

    def quality(self):
        if self.published():
            return {"already_published": True}
        report = self.recorded("transform", "success")
        if report is None:
            raise ValueError("missing successful transform for this run")
        validate_quality(self.batch, self.silver(), report)
        return report | {"silver_versions": self.versions()}

    def publish(self):
        quality = self.recorded("quality", "success")
        if quality is None:
            raise ValueError("missing successful quality check for this run")
        existing = self.published()
        if existing:
            return {
                "reused": True,
                "current": self.current(),
                "release_count": self.counts(),
            }
        versions = self.versions()
        if versions != quality["silver_versions"]:
            raise ValueError("Silver moved since the quality check")
        release_id = self.batch.release_id
        gold = self.table("gold_" + release_id.removeprefix("d02-"))
        silver = self.silver()
        n = _write_gold_daily(
            self.spark,
            gold,
            silver["fx"],
            [*self.batch.rate_context, *silver["rate"]],
            versions["fx"],
            release_id,
        )
        self.sql(f"""
            CREATE VIEW IF NOT EXISTS {self.table("d02_current_release")} AS
            SELECT * FROM {self.ledger} ORDER BY published_at DESC, release_id DESC LIMIT 1
        """)
        request = self.batch.request
        self.sql(
            f"""
            INSERT INTO {self.ledger}
            VALUES (:rid, current_timestamp(), :run, :batch, :key, :sha, :start, :end,
                    :gold, :rows, :fx, :rate, :hashes)
            """,
            rid=release_id,
            run=self.run_id,
            batch=request.batch,
            key=self.batch.batch_key,
            sha=request.git_sha,
            start=request.start,
            end=request.end,
            gold=gold,
            rows=n,
            fx=versions["fx"],
            rate=versions["rate"],
            hashes=json.dumps(self.batch.source_hashes, sort_keys=True),
        )
        return {
            "reused": False,
            "current": self.current(),
            "release_count": self.counts(),
            "gold_rows": n,
            "silver_versions": versions,
        }

    def run(self, task, retry_once=False):
        started = monotonic()
        methods = {
            "ingest": lambda: self.ingest(retry_once, started),
            "transform": self.transform,
            "quality": self.quality,
            "publish": self.publish,
        }
        try:
            detail = methods[task]()
        except Exception as error:
            self.event(
                task,
                "failed",
                started,
                {
                    "reason": str(error)[:1000],
                    "current": self.current(),
                    "release_count": self.counts(),
                },
            )
            raise
        self.event(task, "success", started, detail)
        return {
            "task": task,
            "run_id": self.run_id,
            "schema": self.schema,
            "source_batch_id": self.batch.request.batch,
            "batch_key": self.batch.batch_key,
            "release_id": self.batch.release_id,
            "git_sha": self.batch.request.git_sha,
            "window": [str(self.batch.request.start), str(self.batch.request.end)],
            "duration_ms": int((monotonic() - started) * 1000),
            **detail,
        }
