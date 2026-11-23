"""Databricks Free Edition Spark + Delta runner for D01 ECB Delta Lakehouse."""

from __future__ import annotations

import argparse
import json
import re
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from ecb_lakehouse.contracts import sha256_file
from ecb_lakehouse.transforms import (
    BronzeRow,
    RejectRow,
    SilverRow,
    build_gold_daily,
    build_release_record,
    load_bronze_csv,
    normalize_silver,
)

_IDENTIFIER_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def _validate_identifier(name: str, label: str) -> str:
    if not _IDENTIFIER_RE.match(name):
        raise ValueError(f"Invalid SQL identifier for {label}: {name!r}")
    return name


def _table(catalog: str, schema: str, table: str) -> str:
    return f"{catalog}.{schema}.{table}"


def _delta_version(spark: Any, full_table: str) -> int:
    rows = spark.sql(f"DESCRIBE HISTORY {full_table} LIMIT 1").collect()
    return int(rows[0]["version"])


def _append_bronze_if_absent(
    spark: Any,
    full_table: str,
    rows: list[BronzeRow],
    batch_id: str,
) -> bool:
    existing = spark.sql(
        f"SELECT COUNT(*) AS cnt FROM {full_table} WHERE source_batch_id = '{batch_id}'"
    ).collect()[0]["cnt"]
    if int(existing) > 0:
        return False

    from pyspark.sql.types import StringType, StructField, StructType

    schema = StructType(
        [
            StructField("series_key", StringType(), False),
            StructField("observation_date", StringType(), False),
            StructField("value", StringType(), False),
            StructField("unit", StringType(), False),
            StructField("title", StringType(), False),
            StructField("source_file", StringType(), False),
            StructField("source_batch_id", StringType(), False),
            StructField("ingested_at", StringType(), False),
        ]
    )
    df = spark.createDataFrame(
        [
            (
                r.series_key,
                r.observation_date,
                r.value,
                r.unit,
                r.title,
                r.source_file,
                r.source_batch_id,
                r.ingested_at,
            )
            for r in rows
        ],
        schema=schema,
    )
    df.writeTo(full_table).append()
    return True


def _append_rejects_if_absent(
    spark: Any,
    full_table: str,
    rejects: tuple[RejectRow, ...],
    batch_id: str,
    source_file: str,
) -> int:
    if not rejects:
        return 0
    existing = spark.sql(
        f"SELECT COUNT(*) AS cnt FROM {full_table} "
        f"WHERE source_batch_id = '{batch_id}' AND source_file = '{source_file}'"
    ).collect()[0]["cnt"]
    if int(existing) > 0:
        return 0

    from pyspark.sql.types import StringType, StructField, StructType

    schema = StructType(
        [
            StructField("series_key", StringType(), False),
            StructField("observation_date", StringType(), False),
            StructField("value", StringType(), False),
            StructField("unit", StringType(), False),
            StructField("title", StringType(), False),
            StructField("source_file", StringType(), False),
            StructField("source_batch_id", StringType(), False),
            StructField("reject_reason", StringType(), False),
        ]
    )
    df = spark.createDataFrame(
        [
            (
                r.series_key,
                r.observation_date,
                r.value,
                r.unit,
                r.title,
                r.source_file,
                r.source_batch_id,
                r.reject_reason,
            )
            for r in rejects
        ],
        schema=schema,
    )
    df.writeTo(full_table).append()
    return len(rejects)


def _merge_silver_delta(
    spark: Any,
    full_table: str,
    rows: tuple[SilverRow, ...],
    view_name: str,
) -> None:
    from pyspark.sql.types import DateType, DecimalType, StringType, StructField, StructType

    schema = StructType(
        [
            StructField("series_key", StringType(), False),
            StructField("observation_date", DateType(), False),
            StructField("value", DecimalType(18, 6), False),
            StructField("unit", StringType(), False),
            StructField("frequency", StringType(), False),
            StructField("source_batch_id", StringType(), False),
        ]
    )
    df = spark.createDataFrame(
        [
            (
                r.series_key,
                r.observation_date,
                r.value,
                r.unit,
                r.frequency,
                r.source_batch_id,
            )
            for r in rows
        ],
        schema=schema,
    )
    df.createOrReplaceTempView(view_name)
    spark.sql(
        f"""
        MERGE INTO {full_table} AS t
        USING {view_name} AS s
          ON t.series_key = s.series_key AND t.observation_date = s.observation_date
        WHEN MATCHED AND (
          t.value <> s.value OR t.unit <> s.unit OR t.frequency <> s.frequency
        ) THEN UPDATE SET
          t.value = s.value,
          t.unit = s.unit,
          t.frequency = s.frequency,
          t.source_batch_id = s.source_batch_id
        WHEN NOT MATCHED THEN INSERT (
          series_key, observation_date, value, unit, frequency, source_batch_id
        ) VALUES (
          s.series_key, s.observation_date, s.value, s.unit, s.frequency, s.source_batch_id
        )
        """
    )


def _read_silver_rows(spark: Any, full_table: str) -> list[SilverRow]:
    collected = spark.sql(
        f"""
        SELECT series_key, observation_date, value, unit, frequency, source_batch_id
        FROM {full_table}
        ORDER BY series_key, observation_date
        """
    ).collect()
    return [
        SilverRow(
            series_key=row["series_key"],
            observation_date=row["observation_date"],
            value=row["value"],
            unit=row["unit"],
            frequency=row["frequency"],
            source_batch_id=row["source_batch_id"],
        )
        for row in collected
    ]


def _write_gold_daily(
    spark: Any,
    full_table: str,
    fx_rows: list[SilverRow],
    rate_rows: list[SilverRow],
    silver_version: int,
    release_id: str,
) -> int:
    from pyspark.sql.types import (
        DateType,
        DecimalType,
        LongType,
        StringType,
        StructField,
        StructType,
    )

    gold_rows = build_gold_daily(fx_rows, rate_rows, silver_version, release_id)
    schema = StructType(
        [
            StructField("observation_date", DateType(), False),
            StructField("usd_per_eur", DecimalType(18, 6), False),
            StructField("policy_rate", DecimalType(18, 6), False),
            StructField("policy_rate_status", StringType(), False),
            StructField("policy_rate_source_date", DateType(), False),
            StructField("silver_version", LongType(), False),
            StructField("release_id", StringType(), False),
        ]
    )
    df = spark.createDataFrame(
        [
            (
                r.observation_date,
                r.usd_per_eur,
                r.policy_rate,
                r.policy_rate_status,
                r.policy_rate_source_date,
                r.silver_version,
                r.release_id,
            )
            for r in gold_rows
        ],
        schema=schema,
    )
    df.writeTo(full_table).createOrReplace()
    return len(gold_rows)


def _record_release_if_absent(spark: Any, full_table: str, record: dict[str, Any]) -> None:
    release_id = record["release_id"]
    existing = spark.sql(
        f"SELECT COUNT(*) AS cnt FROM {full_table} WHERE release_id = '{release_id}'"
    ).collect()[0]["cnt"]
    if int(existing) > 0:
        return

    from pyspark.sql.types import LongType, StringType, StructField, StructType

    schema = StructType(
        [
            StructField("release_id", StringType(), False),
            StructField("source_batch_id", StringType(), False),
            StructField("source_hashes_json", StringType(), False),
            StructField("git_sha", StringType(), False),
            StructField("silver_fx_table", StringType(), False),
            StructField("silver_fx_version", LongType(), False),
            StructField("silver_rate_table", StringType(), False),
            StructField("silver_rate_version", LongType(), False),
            StructField("gold_table", StringType(), False),
            StructField("gold_row_count", LongType(), False),
            StructField("reject_count", LongType(), False),
            StructField("quality_status", StringType(), False),
        ]
    )
    df = spark.createDataFrame(
        [
            (
                record["release_id"],
                record["source_batch_id"],
                json.dumps(record["source_hashes"], sort_keys=True),
                record["git_sha"],
                record["silver_fx_table"],
                int(record["silver_fx_version"]),
                record["silver_rate_table"],
                int(record["silver_rate_version"]),
                record["gold_table"],
                int(record["gold_row_count"]),
                int(record["reject_count"]),
                record["quality_status"],
            )
        ],
        schema=schema,
    )
    df.writeTo(full_table).append()


def _ensure_tables(spark: Any, catalog: str, schema: str, reset_tables: bool) -> dict[str, str]:
    tables = {
        "bronze_fx": _table(catalog, schema, "bronze_raw_fx_rates"),
        "bronze_rate": _table(catalog, schema, "bronze_raw_ecb_rates"),
        "silver_fx": _table(catalog, schema, "silver_clean_fx_rates"),
        "silver_rate": _table(catalog, schema, "silver_clean_interest_rates"),
        "silver_reject": _table(catalog, schema, "silver_reject"),
        "gold_daily": _table(catalog, schema, "gold_daily_euro_indicators"),
        "gold_monthly": _table(catalog, schema, "gold_monthly_financial_summary"),
        "gold_release": _table(catalog, schema, "gold_release_record"),
    }

    spark.sql(f"CREATE SCHEMA IF NOT EXISTS {catalog}.{schema}")
    if reset_tables:
        spark.sql(f"DROP VIEW IF EXISTS {tables['gold_monthly']}")
        for key in (
            "bronze_fx",
            "bronze_rate",
            "silver_fx",
            "silver_rate",
            "silver_reject",
            "gold_daily",
            "gold_release",
        ):
            spark.sql(f"DROP TABLE IF EXISTS {tables[key]}")

    for bronze_key in ("bronze_fx", "bronze_rate"):
        spark.sql(
            f"""
            CREATE TABLE IF NOT EXISTS {tables[bronze_key]} (
              series_key STRING,
              observation_date STRING,
              value STRING,
              unit STRING,
              title STRING,
              source_file STRING,
              source_batch_id STRING,
              ingested_at STRING
            ) USING DELTA
            """
        )

    for silver_key in ("silver_fx", "silver_rate"):
        spark.sql(
            f"""
            CREATE TABLE IF NOT EXISTS {tables[silver_key]} (
              series_key STRING,
              observation_date DATE,
              value DECIMAL(18, 6),
              unit STRING,
              frequency STRING,
              source_batch_id STRING
            ) USING DELTA
            """
        )

    spark.sql(
        f"""
        CREATE TABLE IF NOT EXISTS {tables["silver_reject"]} (
          series_key STRING,
          observation_date STRING,
          value STRING,
          unit STRING,
          title STRING,
          source_file STRING,
          source_batch_id STRING,
          reject_reason STRING
        ) USING DELTA
        """
    )

    spark.sql(
        f"""
        CREATE TABLE IF NOT EXISTS {tables["gold_release"]} (
          release_id STRING,
          source_batch_id STRING,
          source_hashes_json STRING,
          git_sha STRING,
          silver_fx_table STRING,
          silver_fx_version BIGINT,
          silver_rate_table STRING,
          silver_rate_version BIGINT,
          gold_table STRING,
          gold_row_count BIGINT,
          reject_count BIGINT,
          quality_status STRING
        ) USING DELTA
        """
    )
    return tables


def run_d01_pipeline(
    spark: Any,
    *,
    catalog: str = "workspace",
    schema: str = "ecb_d01_dev",
    fixtures_dir: Path,
    git_sha: str = "manual",
    reset_tables: bool = False,
) -> dict[str, Any]:
    """Run D01 Bronze/Silver/Gold, MERGE revision, and Delta time-travel verification."""
    cat = _validate_identifier(catalog, "catalog")
    sch = _validate_identifier(schema, "schema")
    tables = _ensure_tables(spark, cat, sch, reset_tables=reset_tables)
    ingested_at = datetime.now(UTC).isoformat()

    fx_path = fixtures_dir / "ecb_fx_2025q1.csv"
    rate_path = fixtures_dir / "ecb_policy_rates_2025q1.csv"
    rev_path = fixtures_dir / "ecb_fx_2025q1_revision.csv"

    bronze_fx_init = load_bronze_csv(fx_path, "batch-2025q1-init", ingested_at)
    bronze_rate_init = load_bronze_csv(rate_path, "batch-2025q1-init", ingested_at)
    _append_bronze_if_absent(spark, tables["bronze_fx"], bronze_fx_init, "batch-2025q1-init")
    _append_bronze_if_absent(spark, tables["bronze_rate"], bronze_rate_init, "batch-2025q1-init")

    fx_norm = normalize_silver(bronze_fx_init, "daily")
    rate_norm = normalize_silver(bronze_rate_init, "irregular")
    _append_rejects_if_absent(
        spark, tables["silver_reject"], fx_norm.rejects, "batch-2025q1-init", fx_path.name
    )
    _append_rejects_if_absent(
        spark, tables["silver_reject"], rate_norm.rejects, "batch-2025q1-init", rate_path.name
    )

    _merge_silver_delta(spark, tables["silver_fx"], fx_norm.rows, "tmp_d01_fx_init")
    _merge_silver_delta(spark, tables["silver_rate"], rate_norm.rows, "tmp_d01_rate_init")

    # Replay identical initial batch and confirm Silver row count stays unchanged.
    count_after_init = int(
        spark.sql(f"SELECT COUNT(*) AS cnt FROM {tables['silver_fx']}").collect()[0]["cnt"]
    )
    _merge_silver_delta(spark, tables["silver_fx"], fx_norm.rows, "tmp_d01_fx_init_replay")
    count_after_replay = int(
        spark.sql(f"SELECT COUNT(*) AS cnt FROM {tables['silver_fx']}").collect()[0]["cnt"]
    )

    fx_v1_ver = _delta_version(spark, tables["silver_fx"])
    rate_v1_ver = _delta_version(spark, tables["silver_rate"])
    silver_fx_rows = _read_silver_rows(spark, tables["silver_fx"])
    silver_rate_rows = _read_silver_rows(spark, tables["silver_rate"])

    gold_v1_count = _write_gold_daily(
        spark,
        tables["gold_daily"],
        silver_fx_rows,
        silver_rate_rows,
        fx_v1_ver,
        "d01-2025q1-v1",
    )
    spark.sql(
        f"""
        CREATE OR REPLACE VIEW {tables["gold_monthly"]} AS
        SELECT
          date_format(observation_date, 'yyyy-MM') AS month_utc,
          CAST(MAX(observation_date) AS STRING) AS last_fx_date,
          CAST(MAX_BY(usd_per_eur, observation_date) AS STRING) AS last_usd_per_eur,
          CAST(ROUND(AVG(usd_per_eur), 6) AS STRING) AS avg_usd_per_eur,
          CAST(MAX_BY(policy_rate, observation_date) AS STRING) AS last_policy_rate,
          COUNT(*) AS observation_days
        FROM {tables["gold_daily"]}
        GROUP BY date_format(observation_date, 'yyyy-MM')
        ORDER BY month_utc
        """
    )

    total_rejects_v1 = int(
        spark.sql(f"SELECT COUNT(*) AS cnt FROM {tables['silver_reject']}").collect()[0]["cnt"]
    )
    release_v1 = build_release_record(
        release_id="d01-2025q1-v1",
        source_batch_id="batch-2025q1-init",
        source_hashes={
            fx_path.name: sha256_file(fx_path),
            rate_path.name: sha256_file(rate_path),
        },
        git_sha=git_sha,
        silver_fx_table=tables["silver_fx"],
        silver_fx_version=fx_v1_ver,
        silver_rate_table=tables["silver_rate"],
        silver_rate_version=rate_v1_ver,
        gold_table=tables["gold_daily"],
        gold_row_count=gold_v1_count,
        reject_count=total_rejects_v1,
    )
    _record_release_if_absent(spark, tables["gold_release"], asdict(release_v1))

    # Controlled revision MERGE + Delta Time Travel check
    version_before = _delta_version(spark, tables["silver_fx"])
    bronze_fx_rev = load_bronze_csv(rev_path, "batch-2025q1-rev1", ingested_at)
    _append_bronze_if_absent(spark, tables["bronze_fx"], bronze_fx_rev, "batch-2025q1-rev1")
    rev_norm = normalize_silver(bronze_fx_rev, "daily")
    _merge_silver_delta(spark, tables["silver_fx"], rev_norm.rows, "tmp_d01_fx_rev")
    version_after = _delta_version(spark, tables["silver_fx"])

    # Replay revision batch to confirm logical stability.
    _merge_silver_delta(spark, tables["silver_fx"], rev_norm.rows, "tmp_d01_fx_rev_replay")

    before_row = (
        spark.sql(
            f"""
            SELECT series_key, CAST(observation_date AS STRING) AS observation_date,
                   CAST(value AS STRING) AS value, unit, source_batch_id
            FROM {tables["silver_fx"]} VERSION AS OF {version_before}
            WHERE observation_date = DATE '2025-02-05'
            """
        )
        .collect()[0]
        .asDict()
    )
    after_row = (
        spark.sql(
            f"""
            SELECT series_key, CAST(observation_date AS STRING) AS observation_date,
                   CAST(value AS STRING) AS value, unit, source_batch_id
            FROM {tables["silver_fx"]} VERSION AS OF {version_after}
            WHERE observation_date = DATE '2025-02-05'
            """
        )
        .collect()[0]
        .asDict()
    )
    untouched_row = (
        spark.sql(
            f"""
            SELECT series_key, CAST(observation_date AS STRING) AS observation_date,
                   CAST(value AS STRING) AS value, unit, source_batch_id
            FROM {tables["silver_fx"]}
            WHERE observation_date = DATE '2025-02-06'
            """
        )
        .collect()[0]
        .asDict()
    )

    silver_fx_v2_rows = _read_silver_rows(spark, tables["silver_fx"])
    gold_v2_count = _write_gold_daily(
        spark,
        tables["gold_daily"],
        silver_fx_v2_rows,
        silver_rate_rows,
        version_after,
        "d01-2025q1-v2",
    )
    monthly_rows = [
        row.asDict() for row in spark.sql(f"SELECT * FROM {tables['gold_monthly']}").collect()
    ]

    release_v2 = build_release_record(
        release_id="d01-2025q1-v2",
        source_batch_id="batch-2025q1-rev1",
        source_hashes={
            fx_path.name: sha256_file(fx_path),
            rate_path.name: sha256_file(rate_path),
            rev_path.name: sha256_file(rev_path),
        },
        git_sha=git_sha,
        silver_fx_table=tables["silver_fx"],
        silver_fx_version=version_after,
        silver_rate_table=tables["silver_rate"],
        silver_rate_version=rate_v1_ver,
        gold_table=tables["gold_daily"],
        gold_row_count=gold_v2_count,
        reject_count=total_rejects_v1,
    )
    _record_release_if_absent(spark, tables["gold_release"], asdict(release_v2))

    return {
        "catalog": cat,
        "schema": sch,
        "silver_fx_count_after_init": count_after_init,
        "silver_fx_count_after_replay": count_after_replay,
        "silver_fx_version_before_revision": version_before,
        "silver_fx_version_after_revision": version_after,
        "time_travel_2025_02_05_before": before_row,
        "time_travel_2025_02_05_after": after_row,
        "untouched_2025_02_06": untouched_row,
        "monthly_summary_after_revision": monthly_rows,
        "release_v1": asdict(release_v1),
        "release_v2": asdict(release_v2),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run D01 ECB Delta Lakehouse on Databricks.")
    parser.add_argument("--catalog", default="workspace")
    parser.add_argument("--schema", default="ecb_d01_dev")
    parser.add_argument("--fixtures-dir", default="fixtures")
    parser.add_argument("--git-sha", default="manual")
    parser.add_argument("--reset-tables", action="store_true")
    parser.add_argument("--evidence-out", default="")
    args = parser.parse_args(argv)

    from pyspark.sql import SparkSession

    spark = SparkSession.builder.appName("d01-ecb-delta-lakehouse").getOrCreate()
    evidence = run_d01_pipeline(
        spark,
        catalog=args.catalog,
        schema=args.schema,
        fixtures_dir=Path(args.fixtures_dir),
        git_sha=args.git_sha,
        reset_tables=args.reset_tables,
    )
    rendered = json.dumps(evidence, indent=2, sort_keys=True)
    if args.evidence_out:
        Path(args.evidence_out).write_text(rendered + "\n", encoding="utf-8")
    print(rendered)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
