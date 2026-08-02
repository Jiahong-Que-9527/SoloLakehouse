"""Tests for v2.9 Block C operational evidence."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from governance.operations import (
    OperationalEvidenceManifest,
    build_operational_evidence_record,
    evaluate_service_slos,
)


def test_evaluate_service_slos_marks_missing_service() -> None:
    results = evaluate_service_slos([("MinIO", "PASS", "ok")])
    trino = next(item for item in results if item.service_name == "Trino")
    assert trino.status == "missing"


def test_build_operational_evidence_record_requires_passing_slos() -> None:
    slo_results = evaluate_service_slos(
        [
            ("MinIO", "PASS", "ok"),
            ("PostgreSQL", "PASS", "ok"),
            ("Hive Metastore", "PASS", "ok"),
            ("Trino", "FAIL", "down"),
            ("MLflow", "PASS", "ok"),
            ("Dagster", "PASS", "ok"),
            ("OpenMetadata", "PASS", "ok"),
            ("Superset", "PASS", "ok"),
        ]
    )
    with pytest.raises(ValueError, match="SLO evaluation failed"):
        build_operational_evidence_record(
            product_id="sololakehouse",
            runtime_version="slh-v2.6.1",
            environment="local",
            slo_results=slo_results,
        )


def test_operational_manifest_binds_record_digest() -> None:
    slo_results = evaluate_service_slos(
        [
            ("MinIO", "PASS", "ok"),
            ("PostgreSQL", "PASS", "ok"),
            ("Hive Metastore", "PASS", "ok"),
            ("Trino", "PASS", "ok"),
            ("MLflow", "PASS", "ok"),
            ("Dagster", "PASS", "ok"),
            ("OpenMetadata", "PASS", "ok"),
            ("Superset", "PASS", "ok"),
        ]
    )
    record = build_operational_evidence_record(
        product_id="sololakehouse",
        runtime_version="slh-v2.6.1",
        environment="local",
        slo_results=slo_results,
        generated_at=datetime(2026, 8, 2, 12, 0, tzinfo=UTC),
    )
    manifest = OperationalEvidenceManifest.from_record(record)
    assert manifest.record_sha256 == record.sha256()
    assert len(record.runbooks) >= 4
