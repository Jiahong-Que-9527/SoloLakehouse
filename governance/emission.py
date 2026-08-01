"""Lineage evidence emission for CLI and Dagster automation."""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from typing import Any

import boto3
from botocore.exceptions import ClientError

from governance.audit import AuditEvidenceWriter
from governance.contracts import DatasetContract, contract_path, load_contract, load_contracts
from governance.evidence import EvidenceManifest, audit_prefix
from governance.lineage import (
    DagsterRunAdapter,
    EvidenceSourceError,
    IcebergSnapshotAdapter,
    LineageEvidenceJoiner,
    OpenMetadataAdapter,
)
from ingestion.iceberg_io import get_catalog
from runtime_identity import get_runtime_identity
from storage_config import get_storage_config


@dataclass(frozen=True)
class LineageEvidenceEmission:
    """One emitted lineage-evidence manifest for a governed dataset."""

    dataset_id: str
    object_path: str
    record_sha256: str


@dataclass(frozen=True)
class PendingLineageEvidenceRunResult:
    """Outcome of automatic lineage-evidence emission for one successful run."""

    skip_reason: str | None
    emissions: tuple[LineageEvidenceEmission, ...]


def evidence_manifest_object_path(
    dataset_id: str,
    dagster_run_id: str,
    run_started_at: datetime,
) -> str:
    """Return the stable audit-bucket object path for one run's manifest."""
    return f"{audit_prefix(dataset_id, run_started_at.date(), dagster_run_id)}/manifest.json"


def audit_manifest_exists(
    dataset_id: str,
    dagster_run_id: str,
    run_started_at: datetime,
    *,
    environ: Mapping[str, str] | None = None,
    s3_client: Any | None = None,
) -> bool:
    """Return whether the audit bucket already holds this run's manifest."""
    env = os.environ if environ is None else environ
    storage = get_storage_config(env)
    client = s3_client or build_audit_s3_client(env)
    object_path = evidence_manifest_object_path(dataset_id, dagster_run_id, run_started_at)
    try:
        client.head_object(Bucket=storage.audit_bucket, Key=object_path)
    except ClientError as exc:
        error_code = exc.response.get("Error", {}).get("Code")
        if error_code in {"404", "NoSuchKey", "NotFound"}:
            return False
        raise EvidenceSourceError(
            "audit", f"cannot check {storage.audit_bucket}/{object_path}: {exc}"
        ) from exc
    return True


def governed_dataset_ids_for_materialized_assets(
    materialized_asset_keys: tuple[str, ...],
    contracts: dict[str, DatasetContract] | None = None,
) -> tuple[str, ...]:
    """Return governed dataset IDs for materialized Dagster asset keys."""
    registry = contracts or load_contracts()
    asset_to_dataset = {
        contract.dagster_asset_key: contract.dataset_id for contract in registry.values()
    }
    return tuple(
        dataset_id
        for asset_key in materialized_asset_keys
        if (dataset_id := asset_to_dataset.get(asset_key)) is not None
    )


def build_audit_s3_client(environ: Mapping[str, str]) -> Any:
    endpoint = environ.get("MINIO_ENDPOINT", "localhost:9000")
    endpoint_url = endpoint if "://" in endpoint else f"http://{endpoint}"
    return boto3.client(
        "s3",
        endpoint_url=endpoint_url,
        aws_access_key_id=environ.get("S3_ACCESS_KEY"),
        aws_secret_access_key=environ.get("S3_SECRET_KEY"),
    )


def _required_env(environ: Mapping[str, str], name: str) -> str:
    value = environ.get(name)
    if not value:
        raise ValueError(f"{name} is required")
    return value


def emit_lineage_evidence(
    dataset_id: str,
    dagster_run_id: str,
    *,
    environ: Mapping[str, str] | None = None,
    s3_client: Any | None = None,
) -> tuple[EvidenceManifest, str]:
    """Collect all required sources and write one complete manifest."""
    env = os.environ if environ is None else environ
    contract = load_contract(contract_path(dataset_id))
    identity = get_runtime_identity(env)
    storage = get_storage_config(env)
    service_name = _required_env(env, "OPENMETADATA_TRINO_SERVICE_NAME")
    auth_token = _required_env(env, "OPENMETADATA_AUTH_TOKEN")
    openmetadata = OpenMetadataAdapter(
        env.get("OPENMETADATA_URL", "http://localhost:8585"),
        service_name,
        auth_token=auth_token,
        trino_catalog=env.get("TRINO_CATALOG", "iceberg"),
    ).collect(contract)
    iceberg = IcebergSnapshotAdapter(
        get_catalog(name=contract.physical_location.catalog)
    ).collect(contract)
    dagster = DagsterRunAdapter(env.get("DAGSTER_URL", "http://localhost:3000")).collect(
        contract, dagster_run_id
    )
    record = LineageEvidenceJoiner(
        identity.product_id,
        identity.runtime_version,
        identity.environment,
        object_store_provider=env.get("OBJECT_STORE_PROVIDER", "minio"),
    ).join(contract, openmetadata, iceberg, dagster)
    manifest = EvidenceManifest.from_record(record)
    client = s3_client or build_audit_s3_client(env)
    object_path = AuditEvidenceWriter(client, storage.audit_bucket).write_manifest(manifest)
    return manifest, object_path


def emit_pending_lineage_evidence_for_run(
    dagster_run_id: str,
    *,
    environ: Mapping[str, str] | None = None,
    s3_client: Any | None = None,
    dagster_adapter: DagsterRunAdapter | None = None,
    contracts: dict[str, DatasetContract] | None = None,
) -> PendingLineageEvidenceRunResult:
    """Emit evidence for pending governed datasets materialized in one successful run."""
    env = os.environ if environ is None else environ
    adapter = dagster_adapter or DagsterRunAdapter(env.get("DAGSTER_URL", "http://localhost:3000"))
    asset_keys, run_started_at = adapter.get_successful_run_materializations(dagster_run_id)
    dataset_ids = governed_dataset_ids_for_materialized_assets(asset_keys, contracts)

    if not dataset_ids:
        return PendingLineageEvidenceRunResult(
            skip_reason=f"run {dagster_run_id} materialized no governed assets",
            emissions=(),
        )

    pending = [
        dataset_id
        for dataset_id in dataset_ids
        if not audit_manifest_exists(
            dataset_id,
            dagster_run_id,
            run_started_at,
            environ=env,
            s3_client=s3_client,
        )
    ]
    if not pending:
        return PendingLineageEvidenceRunResult(
            skip_reason=f"lineage evidence already emitted for run {dagster_run_id}",
            emissions=(),
        )

    emissions: list[LineageEvidenceEmission] = []
    for dataset_id in pending:
        try:
            manifest, object_path = emit_lineage_evidence(
                dataset_id,
                dagster_run_id,
                environ=env,
                s3_client=s3_client,
            )
        except (EvidenceSourceError, ValueError):
            raise
        emissions.append(
            LineageEvidenceEmission(
                dataset_id=dataset_id,
                object_path=object_path,
                record_sha256=manifest.record_sha256,
            )
        )

    return PendingLineageEvidenceRunResult(skip_reason=None, emissions=tuple(emissions))
