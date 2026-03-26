from __future__ import annotations

import datetime as dt
from unittest.mock import MagicMock

import pandas as pd

from ingestion.bronze_writer import BronzeWriter


class TestBronzeWriter:
    def test_write_calls_put_object_with_expected_path(self) -> None:
        minio = MagicMock()
        writer = BronzeWriter(minio, bucket="sololakehouse")
        df = pd.DataFrame({"a": [1, 2], "b": [3, 4]})

        path = writer.write(df, source="ecb_rates")

        assert path.startswith("bronze/ecb_rates/ingestion_date=")
        minio.put_object.assert_called_once()
        called_bucket = minio.put_object.call_args.args[0]
        called_path = minio.put_object.call_args.args[1]
        assert called_bucket == "sololakehouse"
        assert called_path == path

    def test_write_uses_today_partition(self) -> None:
        minio = MagicMock()
        writer = BronzeWriter(minio)
        df = pd.DataFrame({"a": [1]})

        path = writer.write(df, source="dax_daily")

        today = dt.date.today().isoformat()
        assert f"ingestion_date={today}" in path

    def test_write_rejected_writes_to_rejected_path(self) -> None:
        minio = MagicMock()
        writer = BronzeWriter(minio)
        records = [{"bad": "record", "rejection_reason": "invalid schema"}]

        path = writer.write_rejected(records, source="ECB")

        assert path is not None
        assert path.startswith("bronze/rejected/source=ECB/")
        minio.put_object.assert_called_once()

    def test_write_rejected_returns_none_for_empty_input(self) -> None:
        minio = MagicMock()
        writer = BronzeWriter(minio)

        path = writer.write_rejected([], source="DAX")

        assert path is None
        minio.put_object.assert_not_called()
