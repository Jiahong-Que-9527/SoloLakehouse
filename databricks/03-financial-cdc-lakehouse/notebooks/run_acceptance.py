# Databricks notebook source
import json
import sys
from pathlib import Path

from pyspark.sql import SparkSession


def main(db):
    cwd = Path.cwd()
    project = cwd.parent if cwd.name == "notebooks" else cwd
    sys.path.insert(0, str(project / "src"))

    from cdc_acceptance import run_acceptance

    param = db.widgets.get
    result = run_acceptance(
        SparkSession.builder.getOrCreate(), param("catalog"), param("schema"), param("mode")
    )
    result["git_sha"] = param("git_sha")
    db.notebook.exit(json.dumps(result, sort_keys=True))


main(dbutils)  # noqa: F821
