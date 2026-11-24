# Databricks notebook source
"""Write a repeatable reference row within one Terraform-managed stack."""

import json
import re

KEY = "d06_reference"


def merge(spark, target, source, args):
    spark.sql(f"""
        CREATE TABLE IF NOT EXISTS {target}
        (fixture_id STRING NOT NULL, fixture_value STRING, stack_id STRING NOT NULL)
        USING DELTA
    """)
    spark.sql(
        f"""
        MERGE INTO {target} target USING ({source}) source
        ON target.fixture_id = source.fixture_id
        WHEN MATCHED THEN UPDATE SET *
        WHEN NOT MATCHED THEN INSERT *
        """,
        args=args,
    )


def run(spark, phase, stack_id, catalog, schemas, fixture_value):
    if not re.fullmatch(r"slh-[a-z][a-z0-9-]{0,22}-(dev|prod)", stack_id):
        raise ValueError("Expected a D06 stack ID")
    if not re.fullmatch(r"[a-z][a-z0-9_]{0,62}", catalog):
        raise ValueError("Expected a simple catalog name")
    expected = {layer: f"{stack_id.replace('-', '_')}_{layer}" for layer in schemas}
    if set(schemas) != {"bronze", "silver", "gold"} or schemas != expected:
        raise ValueError("The supplied schemas do not all belong to this stack")
    tables = {layer: f"{catalog}.{schema}.fixture" for layer, schema in schemas.items()}
    params = {"key": KEY, "stack": stack_id}
    filtered = "WHERE fixture_id = :key AND stack_id = :stack"
    if phase == "land":
        merge(
            spark,
            tables["bronze"],
            "SELECT :key AS fixture_id, :value AS fixture_value, :stack AS stack_id",
            {**params, "value": fixture_value},
        )
    elif phase == "transform":
        merge(spark, tables["silver"], f"SELECT * FROM {tables['bronze']} {filtered}", params)
    elif phase in {"quality", "publish"}:
        rows = spark.sql(f"SELECT * FROM {tables['silver']}").collect()
        if len(rows) != 1 or (rows[0].fixture_id, rows[0].stack_id) != (KEY, stack_id):
            raise ValueError("Silver must contain exactly one reference key for this stack")
        if not (rows[0].fixture_value or "").strip():
            raise ValueError("Silver fixture_value must be non-empty")
        if phase == "publish":
            merge(spark, tables["gold"], f"SELECT * FROM {tables['silver']} {filtered}", params)
            result = spark.sql(f"SELECT * FROM {tables['gold']}").collect()
            if len(result) != 1 or result[0].asDict() != rows[0].asDict():
                raise ValueError("Gold does not match the validated reference row")
            return {
                "gold_table": tables["gold"],
                "row": result[0].asDict(),
                "run_as": spark.sql("SELECT current_user()").first()[0],
            }
    else:
        raise ValueError(f"Unknown task phase {phase}")
    return {"phase": phase, "stack_id": stack_id}


def main(db):
    from pyspark.sql import SparkSession

    get = db.widgets.get
    result = run(
        SparkSession.builder.getOrCreate(),
        get("phase"),
        get("stack_id"),
        get("catalog"),
        {layer: get(f"{layer}_schema") for layer in ("bronze", "silver", "gold")},
        get("fixture_value"),
    )
    db.notebook.exit(json.dumps(result, sort_keys=True))


if "dbutils" in globals():
    main(globals()["dbutils"])
