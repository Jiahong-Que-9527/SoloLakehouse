from __future__ import annotations

import argparse
import importlib.util
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from ingestion.exceptions import CollectorUnavailableError, StepError


def load_pipeline_module():
    script_path = Path(__file__).resolve().parent.parent / "scripts" / "run-pipeline.py"
    spec = importlib.util.spec_from_file_location("run_pipeline_module", script_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class TestPipelineRetry:
    def test_step1_retries_three_times_then_raises(self) -> None:
        module = load_pipeline_module()
        attempts = {"count": 0}

        def fail_with_step_error():
            attempts["count"] += 1
            raise StepError(1, "ECB Ingestion", Exception("boom"))

        with pytest.raises(StepError):
            module.retry_step(fail_with_step_error, max_attempts=3, delay=0)

        assert attempts["count"] == 3

    def test_step3_failure_does_not_retry(self, monkeypatch) -> None:
        module = load_pipeline_module()

        monkeypatch.setattr(module, "parse_args", lambda: argparse.Namespace(force=False))
        monkeypatch.setattr(
            module,
            "build_clients",
            lambda: {
                "minio_client": object(),
                "bucket": "sololakehouse",
                "mlflow_tracking_uri": "http://x",
                "trino_url": "http://localhost:8080",
            },
        )

        module.ECBCollector = MagicMock()
        module.ECBCollector.return_value.collect.return_value = {"status": "ok"}
        module.DAXCollector = MagicMock()
        module.DAXCollector.return_value.collect.return_value = {"status": "ok"}

        module.ecb_bronze_to_silver.run = MagicMock(side_effect=Exception("transform broke"))
        module.dax_bronze_to_silver.run = MagicMock()
        module.run_gold_and_register = MagicMock()
        module.evaluate.run_experiment_set = MagicMock()

        retry_calls = {"count": 0}
        original_retry = module.retry_step

        def counting_retry(fn, max_attempts=3, delay=5.0):
            retry_calls["count"] += 1
            return original_retry(fn, max_attempts=max_attempts, delay=0)

        monkeypatch.setattr(module, "retry_step", counting_retry)

        code = module.main()
        assert code == 1
        assert retry_calls["count"] == 2  # only step1 and step2 are retried
        assert module.ecb_bronze_to_silver.run.call_count == 1

    def test_force_argument_passed_to_collectors(self, monkeypatch) -> None:
        module = load_pipeline_module()
        monkeypatch.setattr(module, "parse_args", lambda: argparse.Namespace(force=True))
        monkeypatch.setattr(
            module,
            "build_clients",
            lambda: {
                "minio_client": object(),
                "bucket": "sololakehouse",
                "mlflow_tracking_uri": "http://x",
                "trino_url": "http://localhost:8080",
            },
        )

        module.ECBCollector = MagicMock()
        module.ECBCollector.return_value.collect.return_value = {"status": "ok"}
        module.DAXCollector = MagicMock()
        module.DAXCollector.return_value.collect.return_value = {"status": "ok"}
        module.ecb_bronze_to_silver.run = MagicMock(return_value="silver/ecb")
        module.dax_bronze_to_silver.run = MagicMock(return_value="silver/dax")
        module.run_gold_and_register = MagicMock(return_value="gold/path")
        module.evaluate.run_experiment_set = MagicMock(return_value="run-id")

        code = module.main()
        assert code == 0
        assert module.ECBCollector.call_args.kwargs["force"] is True
        assert module.DAXCollector.call_args.kwargs["force"] is True

    def test_collector_unavailable_logs_distinct_message(self) -> None:
        module = load_pipeline_module()
        module.logger = MagicMock()

        def fail():
            raise CollectorUnavailableError("upstream down")

        with pytest.raises(StepError):
            module.run_step(1, "ECB Ingestion", fail)

        first_event = module.logger.error.call_args_list[0].args[0]
        assert first_event == "upstream_api_unavailable"
