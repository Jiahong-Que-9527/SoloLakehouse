# Databricks notebook source
import json
import sys
from pathlib import Path

from pyspark.sql import SparkSession


def main(db):
    cwd = Path.cwd()
    project = cwd.parent if cwd.name == "notebooks" else cwd
    sys.path.insert(0, str(project / "src"))

    from forecast_workflow import run

    args = db.widgets.get
    result = run(
        SparkSession.builder.getOrCreate(),
        project / "fixtures",
        args("schema"),
        args("git_sha"),
        args("job_run_id"),
        args("phase"),
        args("model_version"),
    )
    db.notebook.exit(json.dumps(result, sort_keys=True, default=str))


main(dbutils)  # noqa: F821
