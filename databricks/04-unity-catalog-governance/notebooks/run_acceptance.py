# Databricks notebook source
"""Run the D04 governance exercise on isolated Unity Catalog schemas."""

import json
import re

from pyspark.errors import PySparkException

RELEASES = ("initial", "invalid", "corrected")


class InvalidCandidate(ValueError):
    pass


def schemas_for(namespace, environment):
    if not re.fullmatch(r"ecb_d04_[a-z0-9_]{1,50}", namespace):
        raise ValueError("Expected a dedicated ecb_d04_* namespace")
    if environment not in {"dev", "prod"}:
        raise ValueError("Expected dev or prod")
    return {
        layer: f"workspace.{namespace}_{environment}_{layer}"
        for layer in ("bronze", "silver", "gold", "consumer")
    }


def setup(spark, schemas):
    for name in schemas.values():
        spark.sql(f"CREATE SCHEMA {name}")

    bronze, silver, gold, consumer = (
        schemas[layer] for layer in ("bronze", "silver", "gold", "consumer")
    )
    fields = """
        release_id STRING NOT NULL, source_batch STRING NOT NULL,
        series_key STRING NOT NULL, observation_date DATE NOT NULL,
        observation_value DECIMAL(12, 4), account_token STRING, counterparty STRING
    """
    for table in (f"{bronze}.observations", f"{silver}.observations", f"{gold}.observations"):
        spark.sql(f"CREATE TABLE IF NOT EXISTS {table} ({fields}) USING DELTA")
    spark.sql(f"""
        CREATE TABLE IF NOT EXISTS {consumer}.release_evidence (
            release_id STRING NOT NULL, source_batch STRING NOT NULL,
            bronze_version BIGINT NOT NULL, gold_version BIGINT NOT NULL,
            job_run_id STRING NOT NULL, published_at TIMESTAMP NOT NULL
        ) USING DELTA
    """)
    spark.sql(f"""
        CREATE TABLE IF NOT EXISTS {consumer}.current_release (
            pointer STRING NOT NULL, release_id STRING NOT NULL
        ) USING DELTA
    """)
    spark.sql(f"""
        CREATE TABLE IF NOT EXISTS {consumer}.grant_change (
            actor STRING NOT NULL, principal STRING NOT NULL,
            object_name STRING NOT NULL, action STRING NOT NULL,
            git_sha STRING NOT NULL, changed_at TIMESTAMP NOT NULL
        ) USING DELTA
    """)
    views = {
        "fx_indicator_current": (
            "g.release_id, g.series_key, g.observation_date, g.observation_value"
        ),
        "transaction_risk_detail": (
            "g.release_id, g.series_key, g.observation_date, g.observation_value, "
            "g.account_token, g.counterparty"
        ),
        "forecast_feature": (
            "g.release_id, g.series_key, g.observation_date, g.observation_value AS fx_rate"
        ),
    }
    for view, columns in views.items():
        spark.sql(f"""
            CREATE VIEW IF NOT EXISTS {consumer}.{view} AS
            SELECT {columns}
            FROM {gold}.observations g
            JOIN {consumer}.current_release r ON g.release_id = r.release_id
            WHERE r.pointer = 'active'
        """)


def table_version(spark, table):
    return spark.sql(f"DESCRIBE HISTORY {table} LIMIT 1").first()["version"]


def stage(spark, schemas, release_id):
    if release_id not in RELEASES:
        raise ValueError("Unknown fixture release")
    bronze = f"{schemas['bronze']}.observations"
    silver = f"{schemas['silver']}.observations"
    approved_value = {"initial": "1.0750", "invalid": "1.0800", "corrected": "1.0825"}[release_id]
    rows = f"""
        ('{release_id}', 'batch-{release_id}', 'EXR.D.USD.EUR.SP00.A',
         DATE '2025-01-02', {approved_value}, 'synthetic-001', 'fixture-counterparty')
    """
    if release_id == "invalid":
        rows = f"{rows}, {rows}"
    already_staged = spark.sql(
        f"SELECT 1 FROM {bronze} WHERE release_id = :release_id LIMIT 1",
        args={"release_id": release_id},
    ).first()
    if not already_staged:
        spark.sql(f"INSERT INTO {bronze} VALUES {rows}")
    if not spark.sql(
        f"SELECT 1 FROM {silver} WHERE release_id = :release_id LIMIT 1",
        args={"release_id": release_id},
    ).first():
        spark.sql(
            f"""
            INSERT INTO {silver} SELECT * FROM {bronze}
            WHERE release_id = :release_id
        """,
            args={"release_id": release_id},
        )


def publish(spark, schemas, release_id, job_run_id):
    if release_id not in RELEASES:
        raise ValueError("Unknown fixture release")
    bronze = f"{schemas['bronze']}.observations"
    silver = f"{schemas['silver']}.observations"
    gold = f"{schemas['gold']}.observations"
    consumer = schemas["consumer"]
    args = {"release_id": release_id}
    quality = spark.sql(
        f"""
        SELECT COUNT(*) AS row_count, COUNT(observation_value) AS non_null_count,
               COUNT(DISTINCT series_key, observation_date) AS distinct_key_count
        FROM {silver} WHERE release_id = :release_id
    """,
        args=args,
    ).first()
    if not (quality.row_count == quality.non_null_count == quality.distinct_key_count > 0):
        raise InvalidCandidate(f"Quality check failed for {release_id}: {quality.asDict()}")

    spark.sql(
        f"""
        MERGE INTO {gold} target
        USING (SELECT * FROM {silver} WHERE release_id = :release_id) source
        ON target.release_id = source.release_id AND target.series_key = source.series_key
           AND target.observation_date = source.observation_date
        WHEN NOT MATCHED THEN INSERT *
    """,
        args=args,
    )
    version_args = {
        **args,
        "bronze_version": table_version(spark, bronze),
        "gold_version": table_version(spark, gold),
        "job_run_id": job_run_id,
    }
    spark.sql(
        f"""
        MERGE INTO {consumer}.release_evidence target
        USING (
            SELECT DISTINCT release_id, source_batch FROM {bronze}
            WHERE release_id = :release_id
        ) source
        ON target.release_id = source.release_id
        WHEN NOT MATCHED THEN INSERT (
            release_id, source_batch, bronze_version, gold_version, job_run_id, published_at
        ) VALUES (
            source.release_id, source.source_batch, :bronze_version, :gold_version,
            :job_run_id, current_timestamp()
        )
    """,
        args=version_args,
    )
    spark.sql(
        f"""
        MERGE INTO {consumer}.current_release target
        USING (SELECT 'active' AS pointer, :release_id AS release_id) source
        ON target.pointer = source.pointer
        WHEN MATCHED AND target.release_id <> source.release_id THEN UPDATE SET *
        WHEN NOT MATCHED THEN INSERT *
    """,
        args=args,
    )


def inspect_view(spark, schema, view):
    frame = spark.sql(f"SELECT * FROM {schema}.{view}")
    return {
        "columns": frame.columns,
        "rows": [row.asDict() for row in frame.collect()],
    }


def probe_system_table(spark, table, query_filter=""):
    try:
        rows = spark.sql(f"SELECT * FROM {table} {query_filter} LIMIT 1").collect()
    except PySparkException as error:
        return {
            "status": "not_available",
            "error_class": error.getCondition(),
        }
    return {"status": "visible", "matching_row": bool(rows)}


def record_grant_change(spark, consumer, git_sha):
    actor = spark.sql("SELECT current_user() AS principal").first().principal
    principal = "`" + actor.replace("`", "``") + "`"
    view = f"{consumer}.fx_indicator_current"

    def explicit_select():
        grants = spark.sql(f"SHOW GRANTS {principal} ON TABLE {view}").collect()
        for row in grants:
            grant = {key.casefold(): value for key, value in row.asDict().items()}
            if grant["actiontype"] == "SELECT" and grant["objectkey"] == view:
                return True
        return False

    before = explicit_select()
    if before:
        raise AssertionError("The temporary SELECT grant already exists")
    spark.sql(f"GRANT SELECT ON TABLE {view} TO {principal}")
    try:
        granted = explicit_select()
    finally:
        spark.sql(f"REVOKE SELECT ON TABLE {view} FROM {principal}")
    after = explicit_select()
    if not granted or after:
        raise AssertionError("The temporary explicit SELECT grant was not restored")
    spark.sql(
        f"""
        INSERT INTO {consumer}.grant_change
        VALUES (:actor, :actor, :object_name, 'REVOKE SELECT', :git_sha, current_timestamp())
        """,
        args={"actor": actor, "object_name": view, "git_sha": git_sha},
    )
    evidence = (
        spark.sql(f"""
        SELECT object_name, action, git_sha, changed_at
        FROM {consumer}.grant_change
    """)
        .first()
        .asDict()
    )
    return {
        "principal": "owner of the demonstration view",
        "explicit_select": {"before": before, "granted": granted, "after": after},
        "owner_read_after_revoke": bool(
            inspect_view(spark, consumer, "fx_indicator_current")["rows"]
        ),
        "ledger_entry": evidence,
    }


def run(spark, namespace, job_run_id, git_sha):
    if not re.fullmatch(r"ecb_d04_[a-z0-9_]{1,32}", namespace):
        raise ValueError("Expected a dedicated ecb_d04_* namespace")
    if not re.fullmatch(r"[0-9]{1,18}", job_run_id):
        raise ValueError("Expected a numeric Databricks job run ID")
    if not re.fullmatch(r"[a-f0-9]{40}", git_sha):
        raise ValueError("Expected a full Git commit SHA")
    namespace = f"{namespace}_{job_run_id}"
    prod = schemas_for(namespace, "prod")
    dev = schemas_for(namespace, "dev")
    setup(spark, dev)
    setup(spark, prod)

    stage(spark, prod, "initial")
    publish(spark, prod, "initial", job_run_id)
    before = inspect_view(spark, prod["consumer"], "fx_indicator_current")

    stage(spark, dev, "invalid")
    try:
        publish(spark, dev, "invalid", job_run_id)
    except InvalidCandidate as error:
        dev_rejection = str(error)
    else:
        raise AssertionError("Invalid development candidate published")

    stage(spark, prod, "invalid")
    try:
        publish(spark, prod, "invalid", job_run_id)
    except InvalidCandidate as error:
        rejection = str(error)
    else:
        raise AssertionError("Invalid production candidate published")
    after = inspect_view(spark, prod["consumer"], "fx_indicator_current")
    if before != after or [row["release_id"] for row in after["rows"]] != ["initial"]:
        raise AssertionError("The rejected candidate changed the approved release")
    if spark.sql(f"SELECT * FROM {dev['consumer']}.current_release").collect():
        raise AssertionError("The development pointer changed")

    stage(spark, prod, "corrected")
    publish(spark, prod, "corrected", job_run_id)
    views = {
        view: inspect_view(spark, prod["consumer"], view)
        for view in ("fx_indicator_current", "transaction_risk_detail", "forecast_feature")
    }
    if any([row["release_id"] for row in view["rows"]] != ["corrected"] for view in views.values()):
        raise AssertionError("A consumer view did not move to the corrected release")
    public_columns = set(views["fx_indicator_current"]["columns"])
    feature_columns = set(views["forecast_feature"]["columns"])
    risk_columns = set(views["transaction_risk_detail"]["columns"])
    restricted = {"account_token", "counterparty"}
    if restricted & (public_columns | feature_columns) or not restricted <= risk_columns:
        raise AssertionError("Controlled view projection changed")

    trace = (
        spark.sql(f"""
        SELECT * FROM {prod["consumer"]}.release_evidence WHERE release_id = 'corrected'
    """)
        .first()
        .asDict()
    )
    trace["versioned_observations"] = {}
    for layer in ("bronze", "gold"):
        version = trace[f"{layer}_version"]
        trace["versioned_observations"][layer] = (
            spark.sql(f"""
            SELECT series_key, observation_date, observation_value, source_batch
            FROM {prod[layer]}.observations VERSION AS OF {version}
            WHERE release_id = 'corrected'
        """)
            .first()
            .asDict()
        )
    if trace["versioned_observations"]["bronze"] != trace["versioned_observations"]["gold"]:
        raise AssertionError("The versioned source observation differs from Gold")

    return {
        "job_run_id": job_run_id,
        "schemas": {"dev": dev, "prod": prod},
        "execution_identity": "workspace user running the job",
        "quality": {"before": before, "after": after, "prod": rejection, "dev": dev_rejection},
        "views": views,
        "trace": trace,
        "grant_change": record_grant_change(spark, prod["consumer"], git_sha),
        "lineage_system_table": probe_system_table(
            spark,
            "system.access.table_lineage",
            f"WHERE target_table_full_name = '{prod['gold']}.observations'",
        ),
        "audit_system_table": probe_system_table(spark, "system.access.audit"),
    }


if "dbutils" in globals():
    dbutils = globals()["dbutils"]
    spark = globals()["spark"]
    dbutils.widgets.text("namespace", "")
    dbutils.widgets.text("job_run_id", "")
    dbutils.widgets.text("git_sha", "")
    dbutils.notebook.exit(
        json.dumps(
            run(
                spark,
                dbutils.widgets.get("namespace"),
                dbutils.widgets.get("job_run_id"),
                dbutils.widgets.get("git_sha"),
            ),
            default=str,
            sort_keys=True,
        )
    )
