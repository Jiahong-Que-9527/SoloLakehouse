from __future__ import annotations

import uuid

import pandas as pd
import pytest

from ingestion.bronze_writer import BronzeWriter
from ingestion.iceberg_io import scan_table


@pytest.mark.integration
def test_bronze_writer_roundtrip(iceberg_catalog) -> None:
    writer = BronzeWriter(catalog=iceberg_catalog)
    source_id = f"integration-{uuid.uuid4().hex[:8]}"
    before = scan_table(iceberg_catalog, "bronze", "ecb_rates")
    df = pd.DataFrame(
        {
            "observation_date": ["2024-01-01"],
            "rate_pct": [4.5],
            "_ingestion_timestamp": [pd.Timestamp.utcnow()],
            "_source": [source_id],
        }
    )

    path = writer.write(df, source="ecb_rates")
    loaded = scan_table(iceberg_catalog, "bronze", "ecb_rates")
    inserted = loaded[loaded["_source"] == source_id]

    assert path == "iceberg:bronze.ecb_rates"
    assert len(inserted) == len(df)
    assert len(loaded) >= len(before) + len(df)


@pytest.mark.integration
def test_bronze_writer_rejected_records(iceberg_catalog) -> None:
    writer = BronzeWriter(catalog=iceberg_catalog)
    source = f"ECB_{uuid.uuid4().hex[:8]}"
    rejected = [{"foo": "bar", "rejection_reason": "invalid schema"}]

    path = writer.write_rejected(rejected, source=source)
    assert path is not None
    assert path == f"iceberg:bronze.rejected_records[source={source}]"

    loaded = scan_table(iceberg_catalog, "bronze", "rejected_records")
    inserted = loaded[loaded["source"] == source]

    assert "rejection_reason" in inserted.columns
    assert len(inserted) == 1
