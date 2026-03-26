from __future__ import annotations

import pandas as pd
import pytest

from ingestion.bronze_writer import BronzeWriter
from tests.integration.conftest import read_parquet_from_minio


@pytest.mark.integration
def test_bronze_writer_roundtrip(minio_client, test_bucket) -> None:
    writer = BronzeWriter(minio_client=minio_client, bucket=test_bucket)
    df = pd.DataFrame({"observation_date": ["2024-01-01"], "rate_pct": [4.5]})

    path = writer.write(df, source="ecb_rates")
    loaded = read_parquet_from_minio(minio_client, test_bucket, path)

    assert len(loaded) == len(df)


@pytest.mark.integration
def test_bronze_writer_rejected_records(minio_client, test_bucket) -> None:
    writer = BronzeWriter(minio_client=minio_client, bucket=test_bucket)
    rejected = [{"foo": "bar", "rejection_reason": "invalid schema"}]

    path = writer.write_rejected(rejected, source="ECB")
    assert path is not None
    assert "bronze/rejected/source=ECB/" in path

    loaded = read_parquet_from_minio(minio_client, test_bucket, path)
    assert "rejection_reason" in loaded.columns
