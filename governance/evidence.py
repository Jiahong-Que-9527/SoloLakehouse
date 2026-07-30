"""Stable, machine-validated lineage evidence types for v2.6."""

from __future__ import annotations

import hashlib
import json
import re
from datetime import UTC, date, datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

LINEAGE_SCHEMA_VERSION = "v1"
_DATASET_ID_PATTERN = r"^[a-z][a-z0-9_]*\.[a-z][a-z0-9_]*$"


class LineageRecord(BaseModel):
    """One joined governance, Iceberg, and Dagster lineage evidence record."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    dataset_id: str = Field(pattern=_DATASET_ID_PATTERN)
    product_id: str = Field(min_length=1)
    runtime_version: str = Field(min_length=1)
    environment: str = Field(min_length=1)
    dagster_run_id: str = Field(min_length=1)
    asset_key: str = Field(min_length=1)
    trino_catalog: str = Field(min_length=1)
    trino_schema: str = Field(min_length=1)
    trino_table: str = Field(min_length=1)
    object_store_provider: str = Field(min_length=1)
    bucket: str = Field(min_length=1)
    object_path: str = Field(min_length=1)
    iceberg_snapshot_id: str | None = None
    evidence_timestamp: datetime

    @field_validator("object_path")
    @classmethod
    def validate_object_path(cls, value: str) -> str:
        if value.startswith("/") or ".." in value.split("/"):
            raise ValueError("object_path must be a relative path without traversal")
        return value

    @field_validator("dagster_run_id")
    @classmethod
    def validate_dagster_run_id(cls, value: str) -> str:
        if "/" in value or "\\" in value:
            raise ValueError("dagster_run_id cannot contain path separators")
        return value

    @field_validator("evidence_timestamp")
    @classmethod
    def require_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("evidence_timestamp must include a timezone")
        return value.astimezone(UTC)

    def canonical_json_bytes(self) -> bytes:
        """Return a deterministic representation suitable for hashing and signing."""
        payload = self.model_dump(mode="json")
        return json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")

    def sha256(self) -> str:
        """Return the SHA-256 digest of the canonical record representation."""
        return hashlib.sha256(self.canonical_json_bytes()).hexdigest()


class EvidenceManifest(BaseModel):
    """Metadata for a future immutable lineage-evidence bundle."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = LINEAGE_SCHEMA_VERSION
    record: LineageRecord
    record_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    generated_at: datetime

    @field_validator("generated_at")
    @classmethod
    def require_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("generated_at must include a timezone")
        return value.astimezone(UTC)

    @model_validator(mode="after")
    def validate_record_digest(self) -> "EvidenceManifest":
        if self.record_sha256 != self.record.sha256():
            raise ValueError("record_sha256 does not match record")
        return self

    @classmethod
    def from_record(
        cls, record: LineageRecord, generated_at: datetime | None = None
    ) -> "EvidenceManifest":
        """Create a manifest whose digest is bound to exactly one lineage record."""
        return cls(
            record=record,
            record_sha256=record.sha256(),
            generated_at=generated_at or datetime.now(UTC),
        )


def audit_prefix(dataset_id: str, evidence_date: date, dagster_run_id: str) -> str:
    """Return the stable, bucket-relative evidence bundle directory."""
    if not re.fullmatch(_DATASET_ID_PATTERN, dataset_id):
        raise ValueError("dataset_id is not valid")
    if not dagster_run_id or "/" in dagster_run_id or "\\" in dagster_run_id:
        raise ValueError("dagster_run_id cannot contain path separators")
    return f"lineage/{dataset_id}/{evidence_date.isoformat()}/{dagster_run_id}"


def manifest_object_path(record: LineageRecord) -> str:
    """Return the canonical audit-bucket object path for a record manifest."""
    prefix = audit_prefix(
        record.dataset_id, record.evidence_timestamp.date(), record.dagster_run_id
    )
    return f"{prefix}/manifest.json"
