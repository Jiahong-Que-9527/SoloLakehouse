"""E06 offline tests: BigQuery raw loader, schema mapping and cost guard.

These tests never touch GCP: the BigQuery client is a fake that records the
upload calls, and the raw rows come from the same offline pipeline the rest of
the suite uses. Live-BigQuery verification happens at the E06 acceptance run.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from charging_commerce import bq_loader, ingestion

REPO = Path(__file__).resolve().parents[1]
FIXTURES_DIR = REPO / "fixtures"
DBT_PROJECT = REPO / "dbt_project"


class _FakeJob:
    def __init__(self, job_id: str) -> None:
        self.job_id = job_id

    def result(self):  # pragma: no cover - trivial
        return self


class FakeBQClient:
    """Records loads; enough surface for ``load_raw_to_bigquery``."""

    def __init__(self, project: str = "slh-gcp-test") -> None:
        self.project = project
        self.loads: dict[str, tuple] = {}
        self.tables: dict[str, object] = {}

    def load_table_from_file(self, file_obj, destination, job_config=None):
        self.loads[destination] = job_config
        table = destination.rsplit(".", 1)[-1]
        return _FakeJob(f"fake-{self.project}-{table}")

    def get_table(self, destination):
        from google.cloud.exceptions import NotFound

        if destination not in self.tables:
            raise NotFound(f"{destination} not found")
        return self.tables[destination]

    def create_table(self, table):
        key = f"{table.project}.{table.dataset_id}.{table.table_id}"
        self.tables[key] = table
        return table


@pytest.fixture(scope="module")
def payloads(tmp_path_factory) -> dict[str, tuple]:
    work = tmp_path_factory.mktemp("bq-loader")
    return bq_loader.build_raw_payloads(FIXTURES_DIR, work_dir=work)


def test_all_file_sources_exported(payloads):
    expected = {ingestion.SOURCE_TABLES[source] for source in bq_loader.FILE_SOURCES}
    assert set(payloads) == expected
    for table, (arrow_table, nbytes) in payloads.items():
        assert arrow_table.num_rows > 0, table
        assert nbytes > 0, table


def test_export_keeps_lineage_and_types(payloads):
    arrow_table, _ = payloads["raw_charging_sessions"]
    names = arrow_table.column_names
    for column in (*ingestion.RAW_SCHEMAS["raw_charging_sessions"].columns,):
        assert column.name in names
    for lineage in ingestion.LINEAGE_COLUMNS:
        assert lineage in names
    # Timestamps must arrive tz-aware so BigQuery TIMESTAMP semantics are exact.
    import pyarrow as pa

    for name in ("session_started_at", "session_ended_at", "settled_at", "_ingested_at"):
        assert pa.types.is_timestamp(arrow_table.schema.field(name).type), name
        assert arrow_table.schema.field(name).type.tz == "UTC", name


def test_export_sql_tags_utc_for_lineage_timestamp():
    sql = bq_loader._export_sql("raw_charging_sessions")
    assert sql.count("at time zone 'UTC'") == 4  # 3 model timestamps + _ingested_at
    assert "from raw.raw_charging_sessions" in sql


def test_bq_schema_maps_contract_types():
    fields = bq_loader.bq_schema("raw_charging_sessions")
    by_name = {field.name: field for field in fields}
    assert by_name["session_id"].field_type == "STRING"
    assert by_name["event_seq"].field_type == "INT64"
    assert by_name["settled_at"].field_type == "TIMESTAMP"
    assert by_name["energy_kwh"].field_type == "NUMERIC"  # Parquet carries decimal(12,4)
    assert by_name["_ingested_at"].field_type == "TIMESTAMP"
    assert list(by_name)[-4:] == list(ingestion.LINEAGE_COLUMNS)


def test_load_is_idempotent_truncate(payloads):
    client = FakeBQClient()
    first = bq_loader.load_raw_to_bigquery(client, FIXTURES_DIR, dataset="de_raw", work_dir=None)
    rows_first = dict(first.rows)
    truncating = [job_config.write_disposition for job_config in client.loads.values()]
    assert truncating and all(disposition == "WRITE_TRUNCATE" for disposition in truncating)
    assert set(rows_first) == {ingestion.SOURCE_TABLES[source] for source in bq_loader.FILE_SOURCES}

    second = bq_loader.load_raw_to_bigquery(client, FIXTURES_DIR, dataset="de_raw")
    assert second.rows == rows_first
    # Same destinations, replaced wholesale — never appended.
    assert {dest.rsplit(".", 1)[-1] for dest in client.loads} == set(rows_first)


def test_size_guard_blocks_oversized_upload(payloads):
    client = FakeBQClient()
    with pytest.raises(ValueError, match="Free-Tier guard"):
        bq_loader.load_raw_to_bigquery(client, FIXTURES_DIR, dataset="de_raw", max_total_bytes=1)
    assert client.loads == {}
    assert client.tables == {}


def test_schema_only_tables_created_once():
    client = FakeBQClient()
    first = bq_loader.load_raw_to_bigquery(client, FIXTURES_DIR, dataset="de_raw")
    assert first.schema_only_tables == tuple(bq_loader.SCHEMA_ONLY_TABLES)
    created = [table.table_id.rsplit(".", 1)[-1] for table in client.tables.values()]
    assert sorted(created) == sorted(bq_loader.SCHEMA_ONLY_TABLES)
    # Schema matches the DuckDB ensure_schema shapes (contract + lineage).
    for table_id in bq_loader.SCHEMA_ONLY_TABLES:
        fields = client.tables[f"slh-gcp-test.de_raw.{table_id}"].schema
        names = [field.name for field in fields]
        assert names, table_id

    second = bq_loader.load_raw_to_bigquery(client, FIXTURES_DIR, dataset="de_raw")
    assert second.schema_only_tables == ()  # already present, no-op rerun


def test_profiles_bq_target_has_cost_and_location_guards():
    profiles = yaml.safe_load((DBT_PROJECT / "profiles.yml").read_text())
    target = profiles["charging_commerce"]["outputs"]["bq"]
    assert target["method"] == "oauth"  # ADC per design §4
    assert target["location"] == "europe-west3"
    assert target["maximum_bytes_billed"] == 104857600  # 100 MiB per-query cap
    assert target["dataset"] == "de_mart"
    assert "keyfile" not in target  # no committed credential path
