from __future__ import annotations

import uuid

import pandas as pd
import pytest

from ingestion.bronze_writer import BronzeWriter
from ingestion.iceberg_io import scan_table


@pytest.mark.integration
def test_bronze_writer_overwrite_roundtrip(iceberg_catalog) -> None:
    writer = BronzeWriter(catalog=iceberg_catalog)
    marker_a = f"integration-{uuid.uuid4().hex[:8]}"
    marker_b = f"integration-{uuid.uuid4().hex[:8]}"
    df_a = pd.DataFrame(
        {
            "observation_date": ["2024-01-01"],
            "rate_pct": [4.5],
            "_ingestion_timestamp": [pd.Timestamp.utcnow()],
            "_source": [marker_a],
        }
    )
    df_b = pd.DataFrame(
        {
            "observation_date": ["2024-02-01"],
            "rate_pct": [4.25],
            "_ingestion_timestamp": [pd.Timestamp.utcnow()],
            "_source": [marker_b],
        }
    )

    path = writer.write(df_a, source="ecb_rates")
    loaded_a = scan_table(iceberg_catalog, "bronze", "ecb_rates")
    assert path == "iceberg:bronze.ecb_rates"
    assert marker_a in set(loaded_a["_source"])

    writer.write(df_b, source="ecb_rates")
    loaded_b = scan_table(iceberg_catalog, "bronze", "ecb_rates")

    assert marker_b in set(loaded_b["_source"])
    assert marker_a not in set(loaded_b["_source"])
    assert len(loaded_b) == len(df_b)


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
