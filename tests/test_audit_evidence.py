from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import pytest

from governance.audit import AuditEvidenceWriter
from governance.evidence import EvidenceManifest, LineageRecord
from governance.lineage import EvidenceSourceError


def _manifest() -> EvidenceManifest:
    return EvidenceManifest.from_record(
        LineageRecord(
            dataset_id="fin.ecb_dax_features_gold",
            product_id="sololakehouse",
            runtime_version="slh-v2.6",
            environment="local",
            dagster_run_id="run-123",
            asset_key="gold_features",
            openmetadata_table_fqn="finlakehouse-trino.gold.ecb_dax_features",
            trino_catalog="iceberg",
            trino_schema="gold",
            trino_table="ecb_dax_features",
            object_store_provider="minio",
            bucket="sololakehouse",
            object_path="warehouse/gold/ecb_dax_features/metadata/v1.metadata.json",
            iceberg_snapshot_id="1001",
            evidence_timestamp=datetime(2026, 7, 30, tzinfo=UTC),
        )
    )


class _Client:
    def __init__(self, error: Exception | None = None) -> None:
        self.error = error
        self.kwargs: dict[str, Any] | None = None

    def put_object(self, **kwargs: Any) -> None:
        if self.error:
            raise self.error
        self.kwargs = kwargs


def test_audit_writer_writes_canonical_manifest_at_stable_path() -> None:
    client = _Client()
    path = AuditEvidenceWriter(client, "sololakehouse-audit").write_manifest(_manifest())

    assert path == "lineage/fin.ecb_dax_features_gold/2026-07-30/run-123/manifest.json"
    assert client.kwargs is not None
    assert client.kwargs["Bucket"] == "sololakehouse-audit"
    assert b'"record_sha256"' in client.kwargs["Body"]


def test_audit_writer_fails_loudly_when_object_store_rejects_write() -> None:
    with pytest.raises(EvidenceSourceError, match="cannot write"):
        AuditEvidenceWriter(_Client(RuntimeError("denied")), "audit").write_manifest(_manifest())
