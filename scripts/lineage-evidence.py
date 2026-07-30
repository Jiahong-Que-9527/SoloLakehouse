"""Generate and persist a complete v2.6 lineage-evidence manifest."""

from __future__ import annotations

import argparse
import os
from typing import Any

import boto3

from governance.audit import AuditEvidenceWriter
from governance.contracts import contract_path, load_contract
from governance.evidence import EvidenceManifest
from governance.lineage import (
    DagsterRunAdapter,
    IcebergSnapshotAdapter,
    LineageEvidenceJoiner,
    OpenMetadataAdapter,
)
from ingestion.iceberg_io import get_catalog
from runtime_identity import get_runtime_identity
from storage_config import get_storage_config


def _s3_client() -> Any:
    endpoint = os.environ.get("MINIO_ENDPOINT", "localhost:9000")
    endpoint_url = endpoint if "://" in endpoint else f"http://{endpoint}"
    return boto3.client(
        "s3",
        endpoint_url=endpoint_url,
        aws_access_key_id=os.environ.get("S3_ACCESS_KEY"),
        aws_secret_access_key=os.environ.get("S3_SECRET_KEY"),
    )


def generate(dataset_id: str, dagster_run_id: str) -> tuple[EvidenceManifest, str]:
    """Collect all required sources and write one complete manifest."""
    contract = load_contract(contract_path(dataset_id))
    identity = get_runtime_identity()
    storage = get_storage_config()
    service_name = os.environ.get("OPENMETADATA_TRINO_SERVICE_NAME")
    if not service_name:
        raise ValueError("OPENMETADATA_TRINO_SERVICE_NAME is required")
    openmetadata = OpenMetadataAdapter(
        os.environ.get("OPENMETADATA_URL", "http://localhost:8585"), service_name
    ).collect(contract)
    iceberg = IcebergSnapshotAdapter(get_catalog(name=contract.physical_location.catalog)).collect(
        contract
    )
    dagster = DagsterRunAdapter(os.environ.get("DAGSTER_URL", "http://localhost:3000")).collect(
        contract, dagster_run_id
    )
    record = LineageEvidenceJoiner(
        identity.product_id,
        identity.runtime_version,
        identity.environment,
        object_store_provider=os.environ.get("OBJECT_STORE_PROVIDER", "minio"),
    ).join(contract, openmetadata, iceberg, dagster)
    manifest = EvidenceManifest.from_record(record)
    return manifest, AuditEvidenceWriter(_s3_client(), storage.audit_bucket).write_manifest(
        manifest
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset-id", required=True)
    parser.add_argument("--dagster-run-id", required=True)
    args = parser.parse_args()
    manifest, object_path = generate(args.dataset_id, args.dagster_run_id)
    print(f"wrote s3://{get_storage_config().audit_bucket}/{object_path}")
    print(f"record_sha256={manifest.record_sha256}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
