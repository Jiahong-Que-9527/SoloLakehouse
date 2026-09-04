from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest

from ingestion.iceberg_io import get_catalog, scan_table


@pytest.mark.integration
def test_pipeline_smoke() -> None:
    fixture = Path("tests/fixtures/alpha_vantage_ewg_daily.json")
    if not fixture.exists():
        pytest.skip("EWG CI fixture not found")

    env = os.environ.copy()
    env.setdefault("DAX_FIXTURE_PATH", str(fixture))
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

    gold_df = scan_table(get_catalog(), "gold", "ecb_german_equity_proxy_features")

    assert len(gold_df) > 0
