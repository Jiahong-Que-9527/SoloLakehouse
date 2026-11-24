"""Delta delivery journal, Auto Loader source, and bounded checkpoint runners."""

import json
import re
from pathlib import Path
from typing import Any

from financial_cdc import Change, Delivery, digest, reduce_batch

BRONZE_SCHEMA = (
    "source_file STRING, ordinal BIGINT, kind STRING, key STRING, sequence_number BIGINT, "
    "operation STRING, amount STRING, status STRING, currency STRING, event_time STRING"
)
JOURNAL_SCHEMA = (
    "row_id STRING, record_type STRING, source_file STRING, ordinal BIGINT, kind STRING, "
    "key STRING, sequence_number BIGINT, operation STRING, amount DECIMAL(18,6), status STRING, "
    "currency STRING, event_time STRING, fingerprint STRING, outcome STRING, batch_id BIGINT"
)
FAILURE = "D03_INJECTED_AFTER_DELTA_COMMIT_BEFORE_CHECKPOINT"


def _delivery(row):
    data = row.asDict()
    file, ordinal = data.pop("source_file"), data.pop("ordinal")
    from decimal import Decimal

    data["amount"] = None if data["amount"] is None else Decimal(data["amount"])
    return Delivery(file, ordinal, Change(**data))


def _journal_row(delivery, outcome, batch_id, *, state=False):
    change = delivery.change
    row_id = "state_" + digest(change.identity) if state else delivery.id
    return (
        row_id,
        "state" if state else "event",
        delivery.file,
        delivery.ordinal,
        change.kind,
        change.key,
        change.sequence_number,
        change.operation,
        change.amount,
        change.status,
        change.currency,
        change.event_time,
        change.fingerprint,
        outcome,
        batch_id,
    )


def apply_batch(frame, batch_id, journal, crash=False):
    spark = frame.sparkSession
    deliveries = [_delivery(row) for row in frame.collect()]
    if not deliveries:
        return
    highest, seen, recorded = {}, {}, {}
    for row in spark.table(journal).collect():
        identity = (row.kind, row.key)
        version = (*identity, row.sequence_number)
        if row.record_type == "state":
            highest[identity] = row.sequence_number
        else:
            recorded[row.row_id] = (version, row.fingerprint)
            if row.outcome in {"applied", "ignored"}:
                seen[version] = row.fingerprint
    outcomes, updates = reduce_batch(deliveries, highest, seen, recorded)
    rows = [_journal_row(item, outcome, batch_id) for item, outcome in outcomes]
    rows += [_journal_row(item, "applied", batch_id, state=True) for item in updates]
    if not rows:
        return
    spark.createDataFrame(rows, JOURNAL_SCHEMA).createOrReplaceTempView("d03_changes")
    spark.sql(f"""
        MERGE INTO {journal} t USING d03_changes s ON t.row_id = s.row_id
        WHEN MATCHED AND s.record_type = 'state' AND s.sequence_number > t.sequence_number
          THEN UPDATE SET *
        WHEN NOT MATCHED THEN INSERT *
    """)
    if crash:
        raise RuntimeError(FAILURE)


class DeltaLane:
    def __init__(self, spark: Any, catalog: str, schema: str, lane: str):
        if not re.fullmatch(r"[a-zA-Z_][a-zA-Z0-9_]*", catalog):
            raise ValueError("invalid catalog")
        if not re.fullmatch(r"ecb_d03_[a-z0-9_]+", schema):
            raise ValueError("D03 requires a dedicated ecb_d03_* test schema")
        if lane not in {"primary", "uninterrupted", "replay"}:
            raise ValueError("invalid lane")
        self.spark = spark
        self.root = Path(f"/Volumes/{catalog}/{schema}/cdc_events")
        self.input = self.root / "input" / lane
        self.checkpoints = self.root / "checkpoints" / lane
        prefix = f"{catalog}.{schema}.{lane}"
        self.bronze = prefix + "_bronze"
        self.journal = prefix + "_journal"
        self.current = prefix + "_current_transaction"
        self.history = prefix + "_transaction_history"
        self.reject = prefix + "_cdc_reject"
        self.gold = prefix + "_gold_transaction_metrics"
        spark.sql(f"CREATE SCHEMA IF NOT EXISTS {catalog}.{schema}")
        spark.sql(f"CREATE VOLUME IF NOT EXISTS {catalog}.{schema}.cdc_events")
        self.input.mkdir(parents=True, exist_ok=True)
        self.checkpoints.mkdir(parents=True, exist_ok=True)
        spark.sql(f"CREATE TABLE IF NOT EXISTS {self.bronze} ({BRONZE_SCHEMA}) USING DELTA")
        spark.sql(f"CREATE TABLE IF NOT EXISTS {self.journal} ({JOURNAL_SCHEMA}) USING DELTA")
        spark.sql(f"""
            CREATE VIEW IF NOT EXISTS {self.current} AS
            SELECT key AS transaction_id, sequence_number, amount, currency, status
            FROM {self.journal}
            WHERE record_type = 'state' AND kind = 'transaction' AND operation <> 'DELETE'
        """)
        spark.sql(f"""
            CREATE VIEW IF NOT EXISTS {self.history} AS
            SELECT * FROM {self.journal} WHERE record_type = 'event' AND outcome <> 'conflict'
        """)
        spark.sql(f"""
            CREATE VIEW IF NOT EXISTS {self.reject} AS
            SELECT * FROM {self.journal} WHERE record_type = 'event' AND outcome = 'conflict'
        """)
        spark.sql(f"""
            CREATE VIEW IF NOT EXISTS {self.gold} AS
            SELECT currency, COUNT(*) AS transactions, SUM(amount) AS amount
            FROM {self.current} GROUP BY currency
        """)

    def land(self, name, rows):
        path = self.input / name
        contents = "".join(json.dumps(row, sort_keys=True) + "\n" for row in rows)
        try:
            with path.open("x", encoding="utf-8") as stream:
                stream.write(contents)
        except FileExistsError:
            if path.read_text() != contents:
                raise ValueError(f"input file is immutable: {name}") from None
        return digest(contents)

    def _files(self):
        return sorted(self.input.glob("*.json"))

    def stream_bronze(self):
        frame = (
            self.spark.readStream.format("cloudFiles")
            .option("cloudFiles.format", "json")
            .option("cloudFiles.useManagedFileEvents", "false")
            .option("cloudFiles.schemaLocation", str(self.checkpoints / "source_schema"))
            .schema(BRONZE_SCHEMA.partition(", ")[2])
            .load(str(self.input))
            .selectExpr("_metadata.file_name as source_file", "*")
        )
        query = (
            frame.writeStream.option("checkpointLocation", str(self.checkpoints / "bronze"))
            .trigger(availableNow=True)
            .toTable(self.bronze)
        )
        query.awaitTermination()
        return query_details(query)

    def stream_apply(self, crash=False):
        # Spark Connect serializes this callback to a different Python process.
        # Carry the exact reducer modules with the callback.
        import sys

        from pyspark import cloudpickle

        for name in ("financial_cdc", __name__):
            cloudpickle.register_pickle_by_value(sys.modules[name])
        journal = self.journal
        query = (
            self.spark.readStream.table(self.bronze)
            .writeStream.foreachBatch(
                lambda frame, batch_id: apply_batch(frame, batch_id, journal, crash)
            )
            .option("checkpointLocation", str(self.checkpoints / "apply"))
            .trigger(availableNow=True)
            .start()
        )
        try:
            query.awaitTermination()
        except Exception as error:
            if not crash or FAILURE not in str(error):
                raise
            return query_details(query) | {"failure": FAILURE}
        if crash:
            raise AssertionError("the streaming apply did not reach the injected failure")
        return query_details(query)

    def _checkpointed(self, name, process):
        path = self.checkpoints / name
        path.mkdir(exist_ok=True)
        applied = []
        for offset, file in enumerate(self._files()):
            marker = path / file.name
            fingerprint = digest(file.read_text())
            if marker.exists():
                if marker.read_text() != fingerprint:
                    raise ValueError(f"input file is immutable: {file.name}")
                continue
            process(file, offset)
            with marker.open("x", encoding="utf-8") as stream:
                stream.write(fingerprint)
            applied.append(offset)
        return {"checkpoint": str(path), "file_offsets": applied}

    def batch_bronze(self):
        def process(file, _offset):
            source = [
                json.loads(row) | {"source_file": file.name}
                for row in file.read_text().splitlines()
            ]
            self.spark.createDataFrame(source, BRONZE_SCHEMA).createOrReplaceTempView("d03_input")
            self.spark.sql(f"""
                MERGE INTO {self.bronze} t USING d03_input s
                ON t.source_file = s.source_file AND t.ordinal = s.ordinal
                WHEN NOT MATCHED THEN INSERT *
            """)

        return self._checkpointed("batch_bronze", process)

    def batch_apply(self, crash=False):
        from pyspark.sql import functions as f

        def process(file, offset):
            frame = self.spark.table(self.bronze).where(f.col("source_file") == file.name)
            apply_batch(frame, offset, self.journal, crash)

        try:
            result = self._checkpointed("batch_apply", process)
        except RuntimeError as error:
            if not crash or str(error) != FAILURE:
                raise
            return {"checkpoint": str(self.checkpoints / "batch_apply"), "failure": FAILURE}
        if crash:
            raise AssertionError("the batch apply did not reach the injected failure")
        return result

    def versions(self):
        return {
            name: self.spark.sql(f"DESCRIBE HISTORY {table} LIMIT 1").first()["version"]
            for name, table in (("bronze", self.bronze), ("journal", self.journal))
        }

    def snapshot(self):
        from decimal import Decimal

        # Only verification reads the whole small acceptance fixture.
        manifest = self.spark.table(self.journal).orderBy("row_id").collect()
        state, events = {}, {}
        for row in manifest:
            if row.record_type == "state":
                state[(row.kind, row.key)] = (
                    row.sequence_number,
                    row.amount,
                    row.operation == "DELETE",
                )
            else:
                events[row.row_id] = (row.source_file, row.ordinal, row.outcome)
        gold = self.spark.table(self.gold).orderBy("currency").collect()
        metrics = {row.currency: (row.transactions, Decimal(row.amount)) for row in gold}
        counts = {
            name: self.spark.table(table).count()
            for name, table in (
                ("bronze", self.bronze),
                ("rejects", self.reject),
                ("history", self.history),
                ("current", self.current),
            )
        }
        return state, events, metrics, counts


def query_details(query):
    progress = query.lastProgress or {}
    return {
        "query_id": str(query.id),
        "run_id": str(query.runId),
        "batch_id": progress.get("batchId"),
        "input_rows": progress.get("numInputRows"),
        "sources": [
            {k: value for k, value in source.items() if k in {"startOffset", "endOffset"}}
            for source in progress.get("sources", [])
        ],
    }
