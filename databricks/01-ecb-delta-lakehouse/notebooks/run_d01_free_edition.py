# Databricks notebook source
# COMMAND ----------
import json
import sys
from pathlib import Path

from pyspark.sql import SparkSession


def _resolve_project_root() -> Path:
    cwd = Path.cwd()
    if (cwd.parent / "src").is_dir():
        return cwd.parent
    if (cwd / "src").is_dir():
        return cwd
    raise RuntimeError(f"Cannot locate D01 project root from cwd={cwd}")


def _main() -> None:
    project_root = _resolve_project_root()
    src_path = str(project_root / "src")
    if src_path not in sys.path:
        sys.path.insert(0, src_path)

    from ecb_lakehouse.databricks_runner import run_d01_pipeline

    dbutils = globals().get("dbutils")
    if dbutils is not None:
        dbutils.widgets.text("catalog", "workspace")
        dbutils.widgets.text("schema", "ecb_d01_dev")
        dbutils.widgets.text("git_sha", "manual")
        dbutils.widgets.dropdown("reset_tables", "true", ["true", "false"])
        catalog = dbutils.widgets.get("catalog")
        schema = dbutils.widgets.get("schema")
        git_sha = dbutils.widgets.get("git_sha")
        reset_tables = dbutils.widgets.get("reset_tables").lower() == "true"
    else:
        catalog = "workspace"
        schema = "ecb_d01_dev"
        git_sha = "manual"
        reset_tables = True

    spark = SparkSession.builder.getOrCreate()
    evidence = run_d01_pipeline(
        spark,
        catalog=catalog,
        schema=schema,
        fixtures_dir=project_root / "fixtures",
        git_sha=git_sha,
        reset_tables=reset_tables,
    )
    rendered = json.dumps(evidence, indent=2, sort_keys=True)
    print(rendered)
    if dbutils is not None:
        dbutils.notebook.exit(rendered)


_main()
