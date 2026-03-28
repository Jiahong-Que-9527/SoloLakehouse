"""Linear pipeline orchestrator for SoloLakehouse."""

from __future__ import annotations

import argparse
import os
import sys
import time
from pathlib import Path
from typing import Any, Callable

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import structlog  # noqa: E402
from minio import Minio  # noqa: E402

from ingestion.collectors.dax_collector import DAXCollector  # noqa: E402
from ingestion.collectors.ecb_collector import ECBCollector  # noqa: E402
from ingestion.exceptions import CollectorUnavailableError, StepError  # noqa: E402
from ingestion.trino_sql import register_gold_tables_trino  # noqa: E402
from ml import evaluate  # noqa: E402
from transformations import (  # noqa: E402
    dax_bronze_to_silver,
    ecb_bronze_to_silver,
    silver_to_gold_features,
)

logger = structlog.get_logger()


def emit_step_metric(step: str, duration_ms: int) -> None:
    logger.info("pipeline_metric", metric="pipeline.step.duration_ms", step=step, value=duration_ms)


def load_dotenv_if_present() -> None:
    env_path = REPO_ROOT / ".env"
    if not env_path.exists():
        return

    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()
        if key and key not in os.environ:
            os.environ[key] = value


def minio_base_url() -> str:
    endpoint = os.environ.get("MINIO_ENDPOINT", "localhost:9000")
    if endpoint.startswith("http://") or endpoint.startswith("https://"):
        return endpoint.rstrip("/")
    return f"http://{endpoint}".rstrip("/")


def retry_step(fn: Callable[[], Any], max_attempts: int = 3, delay: float = 5.0) -> Any:
    """Retry fn up to max_attempts times with delay seconds between attempts."""
    last_error: StepError | None = None
    for attempt in range(1, max_attempts + 1):
        try:
            return fn()
        except StepError as exc:
            last_error = exc
            logger.warning(
                "pipeline_step_retry",
                step_number=exc.step_number,
                step_name=exc.step_name,
                attempt=attempt,
                max_attempts=max_attempts,
                error=str(exc.original),
            )
            if attempt < max_attempts:
                time.sleep(delay)

    if last_error is None:
        raise RuntimeError("retry_step exhausted without capturing StepError")
    raise last_error


def run_gold_and_register(clients: dict[str, Any]) -> str:
    gold_path = silver_to_gold_features.run(
        minio_client=clients["minio_client"],
        bucket=clients["bucket"],
    )
    register_gold_tables_trino(
        trino_url=clients["trino_url"],
        bucket=clients["bucket"],
    )
    return gold_path


def run_step(step_number: int, step_name: str, fn: Callable[[], Any]) -> Any:
    """Run one pipeline step and normalize failures as StepError."""
    try:
        return fn()
    except CollectorUnavailableError as exc:
        logger.error(
            "upstream_api_unavailable",
            step_number=step_number,
            step_name=step_name,
            error=str(exc),
        )
        logger.error(
            "pipeline_step_failed",
            step_number=step_number,
            step_name=step_name,
            error=str(exc),
        )
        raise StepError(step_number, step_name, exc) from exc
    except StepError:
        raise
    except Exception as exc:
        logger.error(
            "pipeline_step_failed",
            step_number=step_number,
            step_name=step_name,
            error=str(exc),
        )
        raise StepError(step_number, step_name, exc) from exc


def build_clients() -> dict[str, Any]:
    """Initialize runtime clients from environment variables."""
    endpoint = os.environ.get("MINIO_ENDPOINT", "localhost:9000")
    endpoint = endpoint.replace("http://", "").replace("https://", "").rstrip("/")
    access_key = os.environ.get("S3_ACCESS_KEY", os.environ.get("MINIO_ROOT_USER", "sololakehouse"))
    secret_key = os.environ.get(
        "S3_SECRET_KEY",
        os.environ.get("MINIO_ROOT_PASSWORD", "sololakehouse123"),
    )
    secure = os.environ.get("MINIO_SECURE", "false").lower() == "true"

    minio_client = Minio(
        endpoint,
        access_key=access_key,
        secret_key=secret_key,
        secure=secure,
    )
    return {
        "minio_client": minio_client,
        "bucket": os.environ.get("BUCKET_NAME", "sololakehouse"),
        "mlflow_tracking_uri": os.environ.get("MLFLOW_TRACKING_URI", "http://localhost:5000"),
        "trino_url": os.environ.get("TRINO_URL", "http://localhost:8080"),
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run SoloLakehouse pipeline")
    parser.add_argument(
        "--force",
        action="store_true",
        help="Bypass incremental ingestion checks and force fresh ingestion.",
    )
    return parser.parse_args()


def main() -> int:
    load_dotenv_if_present()
    logger.warning(
        "pipeline_legacy_deprecated",
        message=(
            "This script is deprecated in v2.0. Use "
            "'dagster job execute -f dagster/definitions.py -j full_pipeline_job' "
            "or the Dagster UI instead."
        ),
    )
    os.environ.setdefault(
        "AWS_ACCESS_KEY_ID",
        os.environ.get("S3_ACCESS_KEY", os.environ.get("MINIO_ROOT_USER", "sololakehouse")),
    )
    os.environ.setdefault(
        "AWS_SECRET_ACCESS_KEY",
        os.environ.get(
            "S3_SECRET_KEY",
            os.environ.get("MINIO_ROOT_PASSWORD", "sololakehouse123"),
        ),
    )
    os.environ["MLFLOW_S3_ENDPOINT_URL"] = minio_base_url()

    args = parse_args()
    clients = build_clients()

    steps: list[tuple[int, str, Callable[[], Any], bool]] = [
        (
            1,
            "ECB Ingestion",
            lambda: ECBCollector(
                minio_client=clients["minio_client"],
                bucket=clients["bucket"],
                force=args.force,
            ).collect(),
            True,
        ),
        (
            2,
            "DAX Ingestion",
            lambda: DAXCollector(
                minio_client=clients["minio_client"],
                bucket=clients["bucket"],
                force=args.force,
            ).collect(),
            True,
        ),
        (
            3,
            "ECB Bronze->Silver",
            lambda: ecb_bronze_to_silver.run(
                minio_client=clients["minio_client"],
                bucket=clients["bucket"],
            ),
            False,
        ),
        (
            4,
            "DAX Bronze->Silver",
            lambda: dax_bronze_to_silver.run(
                minio_client=clients["minio_client"],
                bucket=clients["bucket"],
            ),
            False,
        ),
        (
            5,
            "Silver->Gold",
            lambda: run_gold_and_register(clients),
            False,
        ),
        (
            6,
            "ML Experiment",
            lambda: evaluate.run_experiment_set(
                minio_client=clients["minio_client"],
                mlflow_tracking_uri=clients["mlflow_tracking_uri"],
                bucket=clients["bucket"],
                trino_url=clients["trino_url"],
            ),
            False,
        ),
    ]

    statuses: list[dict[str, Any]] = []
    try:
        for step_number, step_name, fn, with_retry in steps:
            logger.info("pipeline_step_started", step_number=step_number, step_name=step_name)
            started = time.perf_counter()
            if with_retry:
                def _run_with_context(
                    sn: int = step_number,
                    sname: str = step_name,
                    sf: Callable[[], Any] = fn,
                ) -> Any:
                    return run_step(sn, sname, sf)

                result = retry_step(
                    _run_with_context,
                    max_attempts=3,
                    delay=5.0,
                )
            else:
                result = run_step(step_number, step_name, fn)

            statuses.append({"step_number": step_number, "step_name": step_name, "status": "ok"})
            duration_ms = int((time.perf_counter() - started) * 1000)
            step_key = step_name.lower().replace(" ", "_").replace("->", "_")
            emit_step_metric(step=step_key, duration_ms=duration_ms)
            logger.info(
                "pipeline_step_complete",
                step_number=step_number,
                step_name=step_name,
                duration_ms=duration_ms,
                result=result,
            )
    except StepError as exc:
        print(f"PIPELINE FAILED at step {exc.step_number} ({exc.step_name})")
        return 1

    logger.info("pipeline_complete", steps=statuses)
    return 0


if __name__ == "__main__":
    sys.exit(main())
