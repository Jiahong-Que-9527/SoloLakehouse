"""Validate a Geometry v2 release and publish three immutable Delta slices."""

import argparse
import hashlib
import json
import re
from pathlib import Path

import pyarrow as pa
import pyarrow.compute as pc
from release_inputs import EVENT_KEY, check_silver, load_release


LINEAGE = ["release_id", "manifest_sha256", "label_version", "release_created_at_utc"]
GOLD_FIELDS = [*EVENT_KEY, *LINEAGE, "taxi_in_s"]


def canonical(table: pa.Table, schema: pa.Schema) -> pa.Table:
    if set(table.column_names) != set(schema.names):
        raise ValueError("stored slice has unexpected columns")
    return table.select(schema.names).cast(schema).sort_by([(key, "ascending") for key in EVENT_KEY]).combine_chunks()


def fingerprint(table: pa.Table) -> str:
    buffer = pa.BufferOutputStream()
    with pa.ipc.new_stream(buffer, table.schema) as writer:
        writer.write_table(table)
    return hashlib.sha256(buffer.getvalue()).hexdigest()


class LocalDelta:
    def __init__(self, directory: Path):
        from deltalake import DeltaTable, write_deltalake

        self.directory, self.table, self.write = directory, DeltaTable, write_deltalake

    def read(self, name, release_id):
        path = self.directory / name
        if not self.table.is_deltatable(str(path)):
            return None
        return self.table(path).to_pyarrow_table(filters=[("release_id", "=", release_id)])

    def append(self, name, rows):
        self.write(self.directory / name, rows, mode="append")

    def version(self, name):
        return self.table(self.directory / name).version()


class DatabricksDelta:
    def __init__(self, namespace: str):
        from pyspark.sql import SparkSession

        if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*\.[A-Za-z_][A-Za-z0-9_]*", namespace):
            raise ValueError("expected an existing Unity Catalog catalog.schema")
        self.spark = SparkSession.builder.getOrCreate()
        self.namespace = namespace

    def read(self, name, release_id):
        target = f"{self.namespace}.{name}"
        if not self.spark.catalog.tableExists(target):
            return None
        return self.spark.table(target).where(f"release_id = '{release_id}'").toArrow()

    def append(self, name, rows):
        self.spark.createDataFrame(rows).write.format("delta").mode("append").saveAsTable(f"{self.namespace}.{name}")

    def version(self, name):
        return self.spark.sql(f"DESCRIBE HISTORY {self.namespace}.{name} LIMIT 1").first()["version"]


def publish(directory: Path, target) -> dict:
    lineage, source = load_release(directory)
    release_id = lineage["release_id"]
    statuses = check_silver(source, release_id)
    silver = source.append_column("is_labeled", pc.equal(source["status"], "labeled"))
    gold = silver.filter(silver["is_labeled"]).select(GOLD_FIELDS)
    report = {**lineage, "candidates": len(source), "labeled": len(gold),
              "coverage": len(gold) / len(source), "statuses": dict(sorted(statuses.items())), "tables": {}}
    slices = {"aviation_bronze_release": source, "aviation_silver_arrivals": silver,
              "aviation_gold_taxi_in_labels": gold}
    for name, rows in slices.items():
        expected = canonical(rows, rows.schema)
        existing = target.read(name, release_id)
        reused = existing is not None and len(existing) > 0
        if not reused:
            target.append(name, rows)
            existing = target.read(name, release_id)
        if existing is None or not canonical(existing, rows.schema).equals(expected):
            raise ValueError(f"stored Delta slice does not match the immutable release: {name}")
        report["tables"][name] = {"rows": len(rows), "version": target.version(name),
                                  "sha256": fingerprint(expected), "reused": reused}
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("release", type=Path, help="approved monthly release directory or Databricks /Volumes path")
    target = parser.add_mutually_exclusive_group(required=True)
    target.add_argument("--local-delta", type=Path)
    target.add_argument("--unity-catalog", metavar="CATALOG.SCHEMA")
    args = parser.parse_args()
    try:
        if args.local_delta:
            import fcntl

            args.local_delta.mkdir(parents=True, exist_ok=True)
            with (args.local_delta / ".import.lock").open("a") as lock:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
                report = publish(args.release, LocalDelta(args.local_delta))
        else:
            report = publish(args.release, DatabricksDelta(args.unity_catalog))
    except (OSError, KeyError, ValueError) as exc:
        parser.exit(1, f"Aviation lakehouse: {exc}\n")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
