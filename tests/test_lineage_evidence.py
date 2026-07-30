from __future__ import annotations

from datetime import UTC, date, datetime

import pytest
from pydantic import ValidationError

from governance.evidence import EvidenceManifest, LineageRecord, audit_prefix, manifest_object_path


def _record(**overrides: object) -> LineageRecord:
    payload: dict[str, object] = {
        "dataset_id": "fin.ecb_dax_features_gold",
        "product_id": "sololakehouse",
        "runtime_version": "slh-v2.6",
        "environment": "local",
        "dagster_run_id": "run-123",
        "asset_key": "gold_features",
        "trino_catalog": "iceberg",
        "trino_schema": "gold",
        "trino_table": "ecb_dax_features",
        "object_store_provider": "minio",
        "bucket": "sololakehouse-audit",
        "object_path": "warehouse/gold/ecb_dax_features/metadata.json",
        "iceberg_snapshot_id": "987654321",
        "evidence_timestamp": datetime(2026, 7, 30, 17, 0, tzinfo=UTC),
    }
    payload.update(overrides)
    return LineageRecord.model_validate(payload)


def test_manifest_binds_a_deterministic_record_digest() -> None:
    record = _record()
    manifest = EvidenceManifest.from_record(
        record, generated_at=datetime(2026, 7, 30, 18, 0, tzinfo=UTC)
    )

    assert manifest.record_sha256 == record.sha256()
    assert manifest.record_sha256 == record.sha256()
    assert manifest.schema_version == "v1"


def test_manifest_path_is_stable_and_bucket_relative() -> None:
    record = _record()

    assert audit_prefix(record.dataset_id, date(2026, 7, 30), record.dagster_run_id) == (
        "lineage/fin.ecb_dax_features_gold/2026-07-30/run-123"
    )
    assert manifest_object_path(record) == (
        "lineage/fin.ecb_dax_features_gold/2026-07-30/run-123/manifest.json"
    )


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("dagster_run_id", "", "String should have at least 1 character"),
        ("evidence_timestamp", datetime(2026, 7, 30, 17, 0), "must include a timezone"),
        ("object_path", "../outside", "relative path without traversal"),
        ("dagster_run_id", "run/123", "cannot contain path separators"),
    ],
)
def test_lineage_record_rejects_missing_or_unsafe_required_evidence(
    field: str, value: object, message: str
) -> None:
    with pytest.raises(ValidationError, match=message):
        _record(**{field: value})


def test_manifest_rejects_a_digest_that_does_not_match_record() -> None:
    with pytest.raises(ValidationError, match="does not match record"):
        EvidenceManifest(
            record=_record(),
            record_sha256="0" * 64,
            generated_at=datetime(2026, 7, 30, 18, 0, tzinfo=UTC),
        )
