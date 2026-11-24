# Databricks notebook source
import json
import sys
from pathlib import Path

from pyspark.sql import SparkSession


def main(db):
    cwd = Path.cwd()
    project = cwd.parent if cwd.name == "notebooks" else cwd
    sys.path.insert(0, str(project / "src"))

    from cdc_acceptance import prepare_failure, resume_and_verify

    param = db.widgets.get
    execute = {
        "prepare_failure": prepare_failure,
        "resume_verify": resume_and_verify,
    }[param("phase")]
    result = execute(
        SparkSession.builder.getOrCreate(),
        param("catalog"),
        param("schema"),
        param("mode"),
        param("git_sha"),
        param("job_run_id"),
    )
    db.notebook.exit(json.dumps(result, sort_keys=True))


main(dbutils)  # noqa: F821
