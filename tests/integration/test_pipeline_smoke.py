from __future__ import annotations

import os
import subprocess
import sys
from io import BytesIO
from pathlib import Path

import pandas as pd
import pytest


@pytest.mark.integration
def test_pipeline_smoke(minio_client) -> None:
    sample_csv = Path("data/sample/dax_daily_sample.csv")
    if not sample_csv.exists():
        pytest.skip("Sample DAX CSV not found yet")

    env = os.environ.copy()
    result = subprocess.run(
        [sys.executable, "scripts/run-pipeline.py"],
        check=False,
        capture_output=True,
        text=True,
        env=env,
    )
    assert result.returncode == 0, result.stdout + result.stderr

    gold_path = "gold/rate_impact_features/ecb_dax_features.parquet"
    response = minio_client.get_object("sololakehouse", gold_path)
    try:
        gold_df = pd.read_parquet(BytesIO(response.read()))
    finally:
        response.close()
        response.release_conn()

    assert len(gold_df) > 0
