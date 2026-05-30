from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest

from ingestion.iceberg_io import get_catalog, scan_table


@pytest.mark.integration
def test_pipeline_smoke() -> None:
    sample_csv = Path("data/sample/dax_daily_sample.csv")
    if not sample_csv.exists():
        pytest.skip("Sample DAX CSV not found yet")

    env = os.environ.copy()
    result = subprocess.run(
        [
            "docker",
            "compose",
            "-f",
            "docker/docker-compose.yml",
            "-f",
            "docker/docker-compose.openmetadata.yml",
            "-f",
            "docker/docker-compose.superset.yml",
            "exec",
            "-T",
            "dagster-webserver",
            "dagster",
            "job",
            "execute",
            "-f",
            "/app/dagster/definitions.py",
            "-j",
            "full_pipeline_job",
        ],
        check=False,
        capture_output=True,
        text=True,
        env=env,
    )
    docker_perm_denied = "permission denied while trying to connect to the docker API"
    if result.returncode != 0 and docker_perm_denied in result.stderr:
        pytest.skip("Docker daemon unreachable for integration tests")
    assert result.returncode == 0, result.stdout + result.stderr

    gold_df = scan_table(get_catalog(), "gold", "ecb_dax_features")

    assert len(gold_df) > 0
