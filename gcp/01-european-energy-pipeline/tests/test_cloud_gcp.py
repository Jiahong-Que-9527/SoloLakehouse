"""GCP adapter contract tests.

Regression (2026-11-20, first cloud run): the real BigQuery client's
load_table_from_file requires a seekable stream and fails on raw bytes with
`AttributeError: 'bytes' object has no attribute 'tell'`. The fake below
mirrors that contract on purpose, so the adapter cannot regress to passing
bytes.
"""

import io
import sys
import types

import pyarrow as pa
import pyarrow.parquet as pq

from energy_pipeline.cloud_gcp import GcpWarehouse


class _DoneJob:
    def result(self):
        return self


class FakeBigQueryClient:
    """Mirrors the slice of the real client that GcpWarehouse uses."""

    def __init__(self):
        self.loaded = []  # (stream, destination, job_config)
        self.queries = []
        self.dropped = []
        self.inserted = {}

    def load_table_from_file(self, stream, destination, job_config=None):
        # The real client probes the position before initiating the upload.
        if stream.tell() != 0:
            raise ValueError("stream must start at position 0")
        payload = stream.read()
        if stream.tell() != len(payload):
            raise ValueError("stream must be fully read from position 0")
        self.loaded.append((payload, destination, job_config))
        return _DoneJob()

    def query(self, sql):
        self.queries.append(sql)
        return _DoneJob()

    def delete_table(self, table, not_found_ok=False):
        self.dropped.append(table)

    def insert_rows_json(self, table, rows):
        self.inserted.setdefault(table, []).extend(rows)
        return []


def _install_fake_bigquery(monkeypatch, client):
    """Make `from google.cloud import bigquery` resolve to fakes, whatever is installed."""
    google = types.ModuleType("google")
    cloud = types.ModuleType("google.cloud")
    bigquery = types.ModuleType("google.cloud.bigquery")
    bigquery.LoadJobConfig = dict
    bigquery.SourceFormat = types.SimpleNamespace(PARQUET="PARQUET")
    bigquery.WriteDisposition = types.SimpleNamespace(WRITE_TRUNCATE="WRITE_TRUNCATE")
    bigquery.Client = lambda: client
    google.cloud = cloud
    monkeypatch.setitem(sys.modules, "google", google)
    monkeypatch.setitem(sys.modules, "google.cloud", cloud)
    monkeypatch.setitem(sys.modules, "google.cloud.bigquery", bigquery)


def _rows():
    return pa.table(
        {
            "interval_start": pa.array([0], type=pa.timestamp("us")),
            "interval_end": pa.array([1], type=pa.timestamp("us")),
            "area": ["DE"],
            "metric": ["load"],
            "value": [42.5],
            "unit": ["MW"],
            "source": ["smard"],
            "release_id": ["release-1"],
            "ingested_at": pa.array([2], type=pa.timestamp("us")),
        }
    )


def test_merge_observations_streams_parquet_and_merges(monkeypatch):
    client = FakeBigQueryClient()
    _install_fake_bigquery(monkeypatch, client)
    warehouse = GcpWarehouse()

    count = warehouse.merge_observations(
        "proj", "energy", "metric_observation", _rows(), "release-1", "now"
    )

    assert count == 1
    ((payload, destination, job_config),) = client.loaded
    assert destination == "proj.energy.metric_observation_staging_release-1"
    assert job_config == {"source_format": "PARQUET", "write_disposition": "WRITE_TRUNCATE"}
    assert pq.read_table(io.BytesIO(payload)).num_rows == 1
    assert len(client.queries) == 1 and "MERGE" in client.queries[0]
    assert client.dropped == ["proj.energy.metric_observation_staging_release-1"]
