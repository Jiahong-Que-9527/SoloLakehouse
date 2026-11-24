# Databricks notebook source
import json
import sys
from pathlib import Path

from pyspark.sql import SparkSession

cwd = Path.cwd()
project = cwd.parent if cwd.name == "notebooks" else cwd
d01 = project.parent / "01-ecb-delta-lakehouse"
sys.path[:0] = [str(project / "src"), str(d01 / "src")]

from financial_etl import Request, Tasks, prepare  # noqa: E402

param = dbutils.widgets.get  # noqa: F821
request = Request.parse(
    param("window_start"),
    param("window_end"),
    param("source_batch_id"),
    param("fixture_variant"),
    param("git_sha"),
)
batch = prepare(request, d01 / "fixtures", project / "fixtures")
schema = param("schema")
if not schema.startswith(f"ecb_d02_{param('target')}_"):
    raise ValueError("D02 schema must belong to its deployment target")
tasks = Tasks(
    SparkSession.builder.getOrCreate(),
    param("catalog"),
    schema,
    param("job_run_id"),
    batch,
)
result = tasks.run(param("task"), retry_once=param("retry_once") == "true")
dbutils.notebook.exit(json.dumps(result, sort_keys=True))  # noqa: F821
