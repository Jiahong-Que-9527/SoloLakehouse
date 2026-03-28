from __future__ import annotations

import datetime as dt
from io import BytesIO
from types import SimpleNamespace
from unittest.mock import MagicMock

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
import pytest

from ingestion.collectors.dax_collector import DAXCollector
from ingestion.collectors.ecb_collector import ECBCollector
from ingestion.exceptions import CollectorUnavailableError
from ml import evaluate
from ml.train_ecb_dax_model import _make_model, train
from transformations.quality_report import run_silver_quality_report


def make_gold_training_frame(rows: int = 12) -> pd.DataFrame:
    dates = pd.date_range("2024-01-01", periods=rows, freq="B")
    return pd.DataFrame(
        {
            "event_date": dates.date,
            "rate_change_bps": [25.0 if i % 2 == 0 else -25.0 for i in range(rows)],
            "rate_level_pct": [3.0 + i * 0.1 for i in range(rows)],
            "is_rate_hike": [i % 2 == 0 for i in range(rows)],
            "is_rate_cut": [i % 2 == 1 for i in range(rows)],
            "dax_volatility_pre_5d": [1.0 + i * 0.05 for i in range(rows)],
            "dax_pre_close": [15000.0 + i * 10 for i in range(rows)],
            "dax_return_1d": [1.0 if i % 2 == 0 else -1.0 for i in range(rows)],
        }
    )


class FakeResponse:
    def __init__(self, payload: bytes):
        self._payload = payload
        self.closed = False
        self.released = False

    def read(self) -> bytes:
        return self._payload

    def close(self) -> None:
        self.closed = True

    def release_conn(self) -> None:
        self.released = True


class TestECBCollector:
    def test_parse_payload_extracts_records(self) -> None:
        collector = ECBCollector(minio_client=MagicMock())
        payload = {
            "structure": {
                "dimensions": {
                    "observation": [
                        {
                            "values": [
                                {"id": "2024-01-01"},
                                {"id": "2024-01-02"},
                            ]
                        }
                    ]
                }
            },
            "dataSets": [
                {
                    "series": {
                        "0:0:0:0:0": {
                            "observations": {"0": [4.0], "1": [4.25]}
                        }
                    }
                }
            ],
        }

        records = collector._parse_payload(payload)

        assert records == [
            {"observation_date": "2024-01-01", "rate_pct": 4.0},
            {"observation_date": "2024-01-02", "rate_pct": 4.25},
        ]

    def test_fetch_data_retries_then_succeeds(self, monkeypatch) -> None:
        collector = ECBCollector(minio_client=MagicMock())
        calls = {"count": 0}

        class DummyResponse:
            def raise_for_status(self) -> None:
                return None

            def json(self) -> dict[str, object]:
                return {"ok": True}

        def fake_get(*args, **kwargs):
            calls["count"] += 1
            if calls["count"] < 3:
                raise RuntimeError("temporary")
            return DummyResponse()

        monkeypatch.setattr("ingestion.collectors.ecb_collector.requests.get", fake_get)
        monkeypatch.setattr("ingestion.collectors.ecb_collector.time.sleep", lambda *_: None)
        monkeypatch.setattr(collector, "_parse_payload", lambda payload: [{"payload": payload}])

        records = collector._fetch_data()

        assert calls["count"] == 3
        assert records == [{"payload": {"ok": True}}]

    def test_fetch_data_raises_after_retries(self, monkeypatch) -> None:
        collector = ECBCollector(minio_client=MagicMock())

        monkeypatch.setattr(
            "ingestion.collectors.ecb_collector.requests.get",
            lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("down")),
        )
        monkeypatch.setattr("ingestion.collectors.ecb_collector.time.sleep", lambda *_: None)

        with pytest.raises(CollectorUnavailableError):
            collector._fetch_data()

    def test_validate_records_splits_valid_and_rejected(self) -> None:
        collector = ECBCollector(minio_client=MagicMock())
        tomorrow = (dt.date.today() + dt.timedelta(days=1)).isoformat()

        valid, rejected = collector._validate_records(
            [
                {"observation_date": "2024-01-01", "rate_pct": 4.0},
                {"observation_date": tomorrow, "rate_pct": 99.0},
            ]
        )

        assert len(valid) == 1
        assert len(rejected) == 1
        assert "rejection_reason" in rejected[0]

    def test_already_ingested_today_detects_latest_partition(self) -> None:
        today = dt.date.today().isoformat()
        minio = MagicMock()
        minio.list_objects.return_value = [
            SimpleNamespace(object_name="bronze/ecb_rates/ingestion_date=2024-01-01/a.parquet"),
            SimpleNamespace(object_name=f"bronze/ecb_rates/ingestion_date={today}/b.parquet"),
        ]
        collector = ECBCollector(minio_client=minio)

        assert collector._already_ingested_today() is True

    def test_collect_returns_skip_when_partition_exists(self, monkeypatch) -> None:
        collector = ECBCollector(minio_client=MagicMock(), force=False)
        monkeypatch.setattr(collector, "_already_ingested_today", lambda: True)

        result = collector.collect()

        assert result == {"status": "skipped", "reason": "already_ingested_today"}

    def test_collect_writes_valid_and_rejected_records(self, monkeypatch) -> None:
        collector = ECBCollector(minio_client=MagicMock(), force=True)
        monkeypatch.setattr(
            collector,
            "_fetch_data",
            lambda: [
                {"observation_date": "2024-01-01", "rate_pct": 4.0},
                {"observation_date": "3024-01-01", "rate_pct": 4.0},
            ],
        )
        monkeypatch.setattr(
            "ingestion.collectors.ecb_collector.run_ecb_bronze_checks",
            lambda df: None,
        )
        collector.bronze_writer = MagicMock()
        collector.bronze_writer.write.return_value = (
            "bronze/ecb_rates/ingestion_date=2024-01-01/x.parquet"
        )
        collector.bronze_writer.write_rejected.return_value = "bronze/rejected/source=ECB/x.parquet"

        result = collector.collect()

        assert result["status"] == "ok"
        assert result["valid_count"] == 1
        assert result["rejected_count"] == 1
        collector.bronze_writer.write.assert_called_once()
        collector.bronze_writer.write_rejected.assert_called_once()


class TestDAXCollector:
    def test_fetch_data_renames_expected_columns(self, tmp_path) -> None:
        csv_path = tmp_path / "dax.csv"
        csv_path.write_text(
            "date,open,high,low,close,volume\n2024-01-02,100,101,99,100.5,12345\n",
            encoding="utf-8",
        )
        collector = DAXCollector(minio_client=MagicMock(), csv_path=str(csv_path))

        records = collector._fetch_data()

        assert records == [
            {
                "observation_date": "2024-01-02",
                "open_price": 100,
                "high_price": 101,
                "low_price": 99,
                "close_price": 100.5,
                "volume": 12345,
            }
        ]

    def test_validate_records_splits_valid_and_rejected(self) -> None:
        collector = DAXCollector(minio_client=MagicMock())

        valid, rejected = collector._validate_records(
            [
                {
                    "observation_date": "2024-01-02",
                    "open_price": 100,
                    "high_price": 101,
                    "low_price": 99,
                    "close_price": 100.5,
                    "volume": 1000,
                },
                {
                    "observation_date": "2024-01-03",
                    "open_price": 100,
                    "high_price": 98,
                    "low_price": 99,
                    "close_price": 100.5,
                    "volume": 1000,
                },
            ]
        )

        assert len(valid) == 1
        assert len(rejected) == 1

    def test_collect_returns_skip_when_already_ingested(self, monkeypatch) -> None:
        collector = DAXCollector(minio_client=MagicMock(), force=False)
        monkeypatch.setattr(collector, "_already_ingested_today", lambda: True)

        result = collector.collect()

        assert result == {"status": "skipped", "reason": "already_ingested_today"}

    def test_collect_success_path(self, monkeypatch) -> None:
        collector = DAXCollector(minio_client=MagicMock(), force=True)
        monkeypatch.setattr(
            collector,
            "_fetch_data",
            lambda: [
                {
                    "observation_date": "2024-01-02",
                    "open_price": 100,
                    "high_price": 101,
                    "low_price": 99,
                    "close_price": 100.5,
                    "volume": 1000,
                }
            ],
        )
        monkeypatch.setattr(
            "ingestion.collectors.dax_collector.run_dax_bronze_checks",
            lambda df: None,
        )
        collector.bronze_writer = MagicMock()
        collector.bronze_writer.write.return_value = (
            "bronze/dax_daily/ingestion_date=2024-01-02/x.parquet"
        )
        collector.bronze_writer.write_rejected.return_value = None

        result = collector.collect()

        assert result == {
            "status": "ok",
            "valid_count": 1,
            "rejected_count": 0,
            "path": "bronze/dax_daily/ingestion_date=2024-01-02/x.parquet",
            "rejected_path": None,
        }


class TestQualityReport:
    def test_quality_report_detects_dates_nulls_and_duplicates(self) -> None:
        df = pd.DataFrame(
            {
                "event_date": ["2024-01-01", "2024-01-01", None],
                "metric": [1.0, 1.0, None],
            }
        )

        result = run_silver_quality_report(df, "gold_layer")

        assert result["layer"] == "gold_layer"
        assert result["row_count"] == 3
        assert result["duplicate_count"] == 1
        assert result["null_counts"] == {"event_date": 1, "metric": 1}
        assert result["date_range"] == {"min": "2024-01-01", "max": "2024-01-01"}


class DummyClassifier:
    def __init__(self, *args, **kwargs):
        self.was_fit = False

    def fit(self, x, y) -> "DummyClassifier":
        self.was_fit = True
        return self

    def predict(self, x):
        return [1 if i % 2 == 0 else 0 for i in range(len(x))]


class TestTraining:
    def test_make_model_selects_supported_backends(self, monkeypatch) -> None:
        monkeypatch.setattr("ml.train_ecb_dax_model.XGBClassifier", DummyClassifier)
        monkeypatch.setattr("ml.train_ecb_dax_model.LGBMClassifier", DummyClassifier)

        assert isinstance(_make_model("xgboost", {}), DummyClassifier)
        assert isinstance(_make_model("lightgbm", {}), DummyClassifier)

        with pytest.raises(ValueError):
            _make_model("unknown", {})

    def test_train_returns_metrics_and_model(self, monkeypatch) -> None:
        monkeypatch.setattr(
            "ml.train_ecb_dax_model._make_model",
            lambda model_type, params: DummyClassifier(),
        )

        model, metrics = train(
            make_gold_training_frame(),
            model_type="xgboost",
            params={"max_depth": 3},
        )

        assert isinstance(model, DummyClassifier)
        assert metrics["n_splits"] == 5
        assert metrics["model_type"] == "xgboost"
        assert metrics["params"] == {"max_depth": 3}
        assert 0.0 <= metrics["accuracy"] <= 1.0

    def test_train_requires_enough_rows(self) -> None:
        with pytest.raises(ValueError):
            train(make_gold_training_frame(rows=5))


class TestEvaluate:
    def test_run_experiment_set_returns_best_run_id(self, monkeypatch) -> None:
        df = make_gold_training_frame()
        buffer = BytesIO()
        pq.write_table(pa.Table.from_pandas(df, preserve_index=False), buffer, compression="snappy")
        payload = buffer.getvalue()

        minio = MagicMock()
        minio.get_object.return_value = FakeResponse(payload)

        train_calls: list[tuple[str, int, int]] = []

        def fake_train(df, model_type, params):
            train_calls.append((model_type, params["n_estimators"], params["max_depth"]))
            accuracy = 0.5 + (0.1 if model_type == "lightgbm" else 0.0) + params["max_depth"] / 100
            return DummyClassifier(), {
                "accuracy": accuracy,
                "precision": 0.7,
                "recall": 0.6,
                "f1": 0.65,
            }

        run_ids = [f"run-{i}" for i in range(12)]

        class DummyRun:
            def __init__(self, run_id: str):
                self.info = SimpleNamespace(run_id=run_id)

            def __enter__(self) -> "DummyRun":
                return self

            def __exit__(self, exc_type, exc, tb) -> bool:
                return False

        monkeypatch.setattr(evaluate, "train", fake_train)
        monkeypatch.setattr(evaluate.mlflow, "set_tracking_uri", lambda uri: None)
        monkeypatch.setattr(evaluate.mlflow, "set_experiment", lambda name: None)
        monkeypatch.setattr(evaluate.mlflow, "start_run", lambda: DummyRun(run_ids.pop(0)))
        monkeypatch.setattr(evaluate.mlflow, "log_param", lambda *args, **kwargs: None)
        monkeypatch.setattr(evaluate.mlflow, "log_metrics", lambda *args, **kwargs: None)
        monkeypatch.setattr(evaluate.mlflow, "log_artifact", lambda *args, **kwargs: None)
        monkeypatch.delenv("TRINO_URL", raising=False)

        best_run_id = evaluate.run_experiment_set(minio, "http://localhost:5000")

        assert best_run_id == "run-7"
        assert len(train_calls) == 12
