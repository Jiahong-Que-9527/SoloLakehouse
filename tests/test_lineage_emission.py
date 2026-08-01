from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace
from typing import Any
from unittest.mock import MagicMock

import pytest
from botocore.exceptions import ClientError

from governance.contracts import DatasetContract, load_contracts
from governance.emission import (
    audit_manifest_exists,
    emit_lineage_evidence,
    evidence_manifest_object_path,
    governed_dataset_ids_for_materialized_assets,
)
from governance.evidence import EvidenceManifest, LineageRecord
from governance.lineage import DagsterRunAdapter, EvidenceSourceError


def test_governed_dataset_ids_for_materialized_assets_maps_contract_asset_keys() -> None:
    dataset_ids = governed_dataset_ids_for_materialized_assets(
        ("ecb_bronze", "dax_silver", "ml_experiment"),
        load_contracts(),
    )

    assert dataset_ids == ("fin.ecb_rates_bronze", "fin.dax_daily_silver")


def test_evidence_manifest_object_path_uses_run_start_date() -> None:
    path = evidence_manifest_object_path(
        "fin.ecb_dax_features_gold",
        "run-1",
        datetime(2026, 7, 30, 17, 0, tzinfo=UTC),
    )

    assert path == "lineage/fin.ecb_dax_features_gold/2026-07-30/run-1/manifest.json"


def test_audit_manifest_exists_returns_true_when_head_object_succeeds() -> None:
    client = MagicMock()
    client.head_object.return_value = {}

    assert audit_manifest_exists(
        "fin.ecb_dax_features_gold",
        "run-1",
        datetime(2026, 7, 30, tzinfo=UTC),
        environ={"AUDIT_BUCKET": "sololakehouse-audit"},
        s3_client=client,
    )


def test_audit_manifest_exists_returns_false_when_object_is_missing() -> None:
    client = MagicMock()
    client.head_object.side_effect = ClientError(
        {"Error": {"Code": "404", "Message": "not found"}},
        "HeadObject",
    )

    assert not audit_manifest_exists(
        "fin.ecb_dax_features_gold",
        "run-1",
        datetime(2026, 7, 30, tzinfo=UTC),
        environ={"AUDIT_BUCKET": "sololakehouse-audit"},
        s3_client=client,
    )


def test_dagster_adapter_lists_materialized_asset_keys_for_successful_run() -> None:
    payload = {
        "data": {
            "runOrError": {
                "__typename": "Run",
                "runId": "run-1",
                "status": "SUCCESS",
                "startTime": 1785369600.0,
                "assetMaterializations": [
                    {"assetKey": {"path": ["ecb_bronze"]}},
                    {"assetKey": {"path": ["gold_features"]}},
                ],
            }
        }
    }
    session = MagicMock()
    session.post.return_value = SimpleNamespace(
        raise_for_status=lambda: None,
        json=lambda: payload,
    )

    keys = DagsterRunAdapter("http://dagster:3000", session).list_materialized_asset_keys("run-1")

    assert keys == ("ecb_bronze", "gold_features")


def test_dagster_adapter_rejects_non_successful_run_for_asset_key_listing() -> None:
    payload = {
        "data": {
            "runOrError": {
                "__typename": "Run",
                "runId": "run-1",
                "status": "FAILURE",
                "startTime": 1785369600.0,
                "assetMaterializations": [],
            }
        }
    }
    session = MagicMock()
    session.post.return_value = SimpleNamespace(
        raise_for_status=lambda: None,
        json=lambda: payload,
    )

    with pytest.raises(EvidenceSourceError, match="not 'SUCCESS'"):
        DagsterRunAdapter("http://dagster:3000", session).list_materialized_asset_keys("run-1")


def test_emit_lineage_evidence_writes_manifest_with_injected_dependencies(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    contract = load_contracts()["fin.ecb_dax_features_gold"]
    manifest_record = LineageRecord.model_validate(
        {
            "dataset_id": contract.dataset_id,
            "product_id": "sololakehouse",
            "runtime_version": "slh-v2.6.1",
            "environment": "local",
            "dagster_run_id": "run-1",
            "asset_key": contract.dagster_asset_key,
            "openmetadata_table_fqn": "svc.iceberg.gold.ecb_dax_features",
            "trino_catalog": "iceberg",
            "trino_schema": "gold",
            "trino_table": "ecb_dax_features",
            "object_store_provider": "minio",
            "bucket": "sololakehouse",
            "object_path": "warehouse/gold/ecb_dax_features/metadata/v1.metadata.json",
            "iceberg_snapshot_id": "1001",
            "evidence_timestamp": datetime(2026, 7, 30, tzinfo=UTC),
        }
    )
    expected_manifest = EvidenceManifest.from_record(manifest_record)

    class _OpenMetadataAdapter:
        def __init__(self, *args: object, **kwargs: object) -> None:
            pass

        def collect(self, loaded_contract: DatasetContract) -> object:
            assert loaded_contract.dataset_id == contract.dataset_id
            return object()

    class _IcebergSnapshotAdapter:
        def __init__(self, catalog: Any) -> None:
            self.catalog = catalog

        def collect(self, loaded_contract: DatasetContract) -> object:
            assert loaded_contract.dataset_id == contract.dataset_id
            return object()

    class _DagsterRunAdapter:
        def __init__(self, *args: object, **kwargs: object) -> None:
            pass

        def collect(self, loaded_contract: DatasetContract, run_id: str) -> object:
            assert loaded_contract.dataset_id == contract.dataset_id
            assert run_id == "run-1"
            return object()

    class _Joiner:
        def __init__(self, *args: object, **kwargs: object) -> None:
            pass

        def join(self, *args: object, **kwargs: object) -> LineageRecord:
            return manifest_record

    class _AuditWriter:
        def __init__(self, client: Any, bucket: str) -> None:
            self.client = client
            self.bucket = bucket

        def write_manifest(self, manifest: EvidenceManifest) -> str:
            assert manifest.record_sha256 == expected_manifest.record_sha256
            return "lineage/fin.ecb_dax_features_gold/2026-07-30/run-1/manifest.json"

    monkeypatch.setattr("governance.emission.load_contract", lambda path: contract)
    monkeypatch.setattr("governance.emission.get_runtime_identity", lambda env: SimpleNamespace(
        product_id="sololakehouse",
        runtime_version="slh-v2.6.1",
        environment="local",
    ))
    monkeypatch.setattr("governance.emission.get_storage_config", lambda env: SimpleNamespace(
        audit_bucket="sololakehouse-audit",
    ))
    monkeypatch.setattr("governance.emission.OpenMetadataAdapter", _OpenMetadataAdapter)
    monkeypatch.setattr("governance.emission.IcebergSnapshotAdapter", _IcebergSnapshotAdapter)
    monkeypatch.setattr("governance.emission.DagsterRunAdapter", _DagsterRunAdapter)
    monkeypatch.setattr("governance.emission.LineageEvidenceJoiner", _Joiner)
    monkeypatch.setattr("governance.emission.AuditEvidenceWriter", _AuditWriter)
    monkeypatch.setattr("governance.emission.get_catalog", lambda name: object())

    manifest, object_path = emit_lineage_evidence(
        contract.dataset_id,
        "run-1",
        environ={
            "OPENMETADATA_TRINO_SERVICE_NAME": "svc",
            "OPENMETADATA_AUTH_TOKEN": "token",
        },
        s3_client=object(),
    )

    assert manifest.record_sha256 == expected_manifest.record_sha256
    assert object_path.endswith("/manifest.json")
