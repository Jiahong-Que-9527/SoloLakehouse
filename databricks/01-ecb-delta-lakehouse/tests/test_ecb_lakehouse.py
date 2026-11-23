"""Unit and contract tests for D01 ECB Delta Lakehouse (zero local JVM required)."""

from __future__ import annotations

import ast
import json
from decimal import Decimal
from pathlib import Path

import pytest

from ecb_lakehouse.contracts import ContractError, sha256_file
from ecb_lakehouse.transforms import (
    build_gold_daily,
    build_gold_monthly_summary,
    load_bronze_csv,
    normalize_silver,
    run_local_rehearsal,
)

PROJECT_ROOT = Path(__file__).resolve().parents[1]
FIXTURES_DIR = PROJECT_ROOT / "fixtures"


def test_fixture_manifest_checksums_match_disk() -> None:
    manifest = json.loads((FIXTURES_DIR / "manifest.json").read_text(encoding="utf-8"))
    for entry in manifest["files"]:
        path = FIXTURES_DIR / entry["filename"]
        assert path.is_file()
        assert sha256_file(path) == entry["sha256"]
        row_count = len(path.read_text(encoding="utf-8").strip().splitlines()) - 1
        assert row_count == entry["row_count"]


def test_csv_header_contract_rejects_mismatched_columns(tmp_path: Path) -> None:
    bad_csv = tmp_path / "bad_header.csv"
    bad_csv.write_text(
        "series_key,obs_date,value,unit,title\nEXR.D.USD.EUR.SP00.A,2025-01-02,1.03,USD_PER_EUR,x\n",
        encoding="utf-8",
    )
    with pytest.raises(ContractError, match="expected header"):
        load_bronze_csv(bad_csv, "batch-bad", "2026-11-23T00:00:00Z")


def test_silver_normalization_rejects_malformed_and_conflicting_rows() -> None:
    expected = json.loads((FIXTURES_DIR / "expected_results.json").read_text(encoding="utf-8"))
    fx_bronze = load_bronze_csv(
        FIXTURES_DIR / "ecb_fx_2025q1.csv", "batch-2025q1-init", "2026-11-23T00:00:00Z"
    )
    rate_bronze = load_bronze_csv(
        FIXTURES_DIR / "ecb_policy_rates_2025q1.csv", "batch-2025q1-init", "2026-11-23T00:00:00Z"
    )

    fx_norm = normalize_silver(fx_bronze, "daily")
    rate_norm = normalize_silver(rate_bronze, "irregular")

    counts = expected["initial_silver_counts"]
    assert len(fx_norm.rows) == counts["fx_rows"]
    assert len(fx_norm.rejects) == counts["fx_rejects"]
    assert fx_norm.duplicate_rows_dropped == counts["fx_duplicate_drops"]
    assert len(rate_norm.rows) == counts["policy_rate_rows"]
    assert len(rate_norm.rejects) == counts["policy_rate_rejects"]
    assert rate_norm.duplicate_rows_dropped == counts["policy_rate_duplicate_drops"]

    fx_dates = {row.observation_date.isoformat() for row in fx_norm.rows}
    assert expected["missing_calendar_date_absent_from_silver"] not in fx_dates
    assert expected["conflicting_duplicate_date"] not in fx_dates

    reasons = [r.reject_reason for r in fx_norm.rejects]
    assert reasons.count("conflicting_duplicate_in_batch") == 2
    assert "null_series_key" in reasons
    assert "invalid_observation_date" in reasons
    assert "non_numeric_value" in reasons


def test_gold_daily_and_monthly_match_expected_results() -> None:
    expected = json.loads((FIXTURES_DIR / "expected_results.json").read_text(encoding="utf-8"))
    fx_norm = normalize_silver(
        load_bronze_csv(
            FIXTURES_DIR / "ecb_fx_2025q1.csv", "batch-2025q1-init", "2026-11-23T00:00:00Z"
        ),
        "daily",
    )
    rate_norm = normalize_silver(
        load_bronze_csv(
            FIXTURES_DIR / "ecb_policy_rates_2025q1.csv",
            "batch-2025q1-init",
            "2026-11-23T00:00:00Z",
        ),
        "irregular",
    )

    gold_rows = build_gold_daily(fx_norm.rows, rate_norm.rows, silver_version=1, release_id="v1")
    gold_by_date = {row.observation_date.isoformat(): row for row in gold_rows}

    for check in expected["checked_gold_rows"]:
        actual = gold_by_date[check["observation_date"]]
        assert actual.usd_per_eur == Decimal(check["usd_per_eur"])
        assert actual.policy_rate == Decimal(check["policy_rate"])
        assert actual.policy_rate_status == check["policy_rate_status"]
        assert actual.policy_rate_source_date.isoformat() == check["policy_rate_source_date"]
        assert actual.silver_version == 1

    monthly = build_gold_monthly_summary(gold_rows)
    assert [
        {
            "month_utc": row.month_utc,
            "last_fx_date": row.last_fx_date.isoformat(),
            "last_usd_per_eur": str(row.last_usd_per_eur),
            "avg_usd_per_eur": str(row.avg_usd_per_eur),
            "last_policy_rate": str(row.last_policy_rate),
            "observation_days": row.observation_days,
        }
        for row in monthly
    ] == expected["monthly_summary_initial"]


def test_local_rehearsal_merge_time_travel_and_replay_idempotency() -> None:
    expected = json.loads((FIXTURES_DIR / "expected_results.json").read_text(encoding="utf-8"))
    result = run_local_rehearsal(FIXTURES_DIR, git_sha="test-sha")

    initial = result["initial"]
    assert initial["fx_inserted"] == 10
    assert initial["rate_inserted"] == 3
    assert initial["fx_replay_changed"] is False
    assert initial["rate_replay_changed"] is False
    assert initial["monthly_summary"] == expected["monthly_summary_initial"]
    assert initial["release_record"]["git_sha"] == "test-sha"
    assert initial["release_record"]["reject_count"] == 5

    rev = result["revision"]
    rev_check = expected["revision_check"]
    assert rev["version_after"] == rev["version_before"] + 1
    assert rev["merge_inserted"] == 0
    assert rev["merge_updated"] == 1
    assert rev["merge_unchanged"] == 1
    assert rev["revision_replay_changed"] is False

    assert rev["before_2025_02_05"]["value"] == rev_check["before_value"]
    assert rev["before_2025_02_05"]["source_batch_id"] == rev_check["before_batch"]
    assert rev["after_2025_02_05"]["value"] == rev_check["after_value"]
    assert rev["after_2025_02_05"]["source_batch_id"] == rev_check["after_batch"]
    assert rev["after_2025_02_06"]["source_batch_id"] == rev_check["untouched_batch"]

    feb_after = next(m for m in rev["monthly_summary"] if m["month_utc"] == "2025-02")
    assert feb_after["avg_usd_per_eur"] == rev_check["feb_avg_after"]
    assert rev["release_record"]["silver_fx_version"] == rev["version_after"]


def test_databricks_runner_bundle_and_notebook_parse_cleanly() -> None:
    runner_src = (PROJECT_ROOT / "src" / "ecb_lakehouse" / "databricks_runner.py").read_text(
        encoding="utf-8"
    )
    notebook_src = (PROJECT_ROOT / "notebooks" / "run_d01_free_edition.py").read_text(
        encoding="utf-8"
    )
    ast.parse(runner_src)
    ast.parse(notebook_src)

    bundle_text = (PROJECT_ROOT / "databricks.yml").read_text(encoding="utf-8")
    for required_key in ("bundle:", "variables:", "resources:", "jobs:", "targets:", "dev:"):
        assert required_key in bundle_text
