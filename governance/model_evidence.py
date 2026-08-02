"""Model evaluation evidence and audit paths for v2.8 E4."""

from __future__ import annotations

import hashlib
import json
import os
import re
from datetime import UTC, date, datetime
from typing import Any, Mapping

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from governance.lineage import EvidenceSourceError
from governance.ml_lineage import MLLineageTuple

MODEL_EVIDENCE_SCHEMA_VERSION = "v1"
_DATASET_ID_PATTERN = re.compile(r"^[a-z][a-z0-9_]*\.[a-z][a-z0-9_]*$")


class ModelEvaluationEvidence(BaseModel):
    """Traceability bundle for one governed MLflow run."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = MODEL_EVIDENCE_SCHEMA_VERSION
    dataset_id: str = Field(pattern=r"^[a-z][a-z0-9_]*\.[a-z][a-z0-9_]*$")
    mlflow_run_id: str = Field(min_length=1)
    ml_lineage: MLLineageTuple
    policy_hook_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    evaluation_metrics: dict[str, float]
    model_card_markdown: str = Field(min_length=1)
    generated_at: datetime

    @field_validator("evaluation_metrics")
    @classmethod
    def validate_metrics(cls, values: dict[str, float]) -> dict[str, float]:
        if not values:
            raise ValueError("evaluation_metrics must not be empty")
        return values

    @field_validator("generated_at")
    @classmethod
    def require_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("generated_at must include a timezone")
        return value.astimezone(UTC)

    def canonical_json_bytes(self) -> bytes:
        payload = self.model_dump(mode="json")
        return json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")

    def sha256(self) -> str:
        return hashlib.sha256(self.canonical_json_bytes()).hexdigest()


class ModelEvaluationManifest(BaseModel):
    """SHA-256-bound wrapper for one model evaluation evidence record."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = MODEL_EVIDENCE_SCHEMA_VERSION
    evidence: ModelEvaluationEvidence
    evidence_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    generated_at: datetime

    @field_validator("generated_at")
    @classmethod
    def require_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("generated_at must include a timezone")
        return value.astimezone(UTC)

    @model_validator(mode="after")
    def validate_evidence_digest(self) -> "ModelEvaluationManifest":
        if self.evidence_sha256 != self.evidence.sha256():
            raise ValueError("evidence_sha256 does not match evidence")
        return self

    @classmethod
    def from_evidence(
        cls,
        evidence: ModelEvaluationEvidence,
        generated_at: datetime | None = None,
    ) -> "ModelEvaluationManifest":
        stamp = generated_at or evidence.generated_at
        return cls(
            evidence=evidence,
            evidence_sha256=evidence.sha256(),
            generated_at=stamp,
        )


def model_evidence_object_path(
    dataset_id: str,
    evidence_date: date,
    dagster_run_id: str,
    mlflow_run_id: str,
) -> str:
    """Return the stable audit-bucket object path for one model evidence manifest."""
    if not _DATASET_ID_PATTERN.fullmatch(dataset_id):
        raise ValueError("dataset_id is not valid")
    if not dagster_run_id or "/" in dagster_run_id or "\\" in dagster_run_id:
        raise ValueError("dagster_run_id cannot contain path separators")
    if not mlflow_run_id or "/" in mlflow_run_id or "\\" in mlflow_run_id:
        raise ValueError("mlflow_run_id cannot contain path separators")
    return (
        f"lineage/{dataset_id}/{evidence_date.isoformat()}/{dagster_run_id}/"
        f"model-evidence/{mlflow_run_id}.json"
    )


def write_model_evaluation_manifest(
    manifest: ModelEvaluationManifest,
    *,
    environ: Mapping[str, str] | None = None,
    s3_client: Any | None = None,
) -> str:
    """Write one model evaluation manifest to the audit bucket."""
    from governance.emission import build_audit_s3_client
    from storage_config import get_storage_config

    env = os.environ if environ is None else environ
    storage = get_storage_config(env)
    client = s3_client or build_audit_s3_client(env)
    object_path = model_evidence_object_path(
        manifest.evidence.dataset_id,
        manifest.evidence.generated_at.date(),
        manifest.evidence.ml_lineage.dagster_run_id,
        manifest.evidence.mlflow_run_id,
    )
    try:
        client.put_object(
            Bucket=storage.audit_bucket,
            Key=object_path,
            Body=manifest.model_dump_json(indent=2).encode("utf-8"),
            ContentType="application/json",
        )
    except Exception as exc:
        raise EvidenceSourceError(
            "audit", f"cannot write {storage.audit_bucket}/{object_path}: {exc}"
        ) from exc
    return object_path
