# Databricks notebook source
"""Create and inspect disposable schemas for the single-identity smoke run."""

import json
import re

from pyspark.sql import SparkSession


def main(db):
    spark = SparkSession.builder.getOrCreate()
    args = db.widgets.get
    stack = args("stack_id")
    if not re.fullmatch(r"slh-d06smoke[0-9]{14}-dev", stack):
        raise ValueError("Use an isolated D06 smoke stack")

    prefix = stack.replace("-", "_")
    schemas = {layer: f"workspace.{prefix}_{layer}" for layer in ("bronze", "silver", "gold")}
    phase = args("phase")
    if phase == "prepare":
        for schema in schemas.values():
            spark.sql(f"CREATE SCHEMA {schema}")
        result = {"schemas": schemas, "stack_id": stack}
    elif phase == "inspect":
        result = {
            "rows": {
                layer: [row.asDict() for row in spark.table(f"{schema}.fixture").collect()]
                for layer, schema in schemas.items()
            },
            "stack_id": stack,
        }
    else:
        raise ValueError("Unknown D06 smoke setup phase")
    db.notebook.exit(json.dumps(result, sort_keys=True))


main(dbutils)  # noqa: F821
