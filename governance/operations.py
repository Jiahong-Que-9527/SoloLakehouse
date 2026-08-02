"""SLO and incident-readiness evidence for v2.9 Block C."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

OPERATIONS_SCHEMA_VERSION = "v1"
SLOStatus = Literal["pass", "fail", "missing"]


class ServiceSLODefinition(BaseModel):
    """One SLO mapped to a verify-setup service check."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    slo_id: str = Field(min_length=1)
    service_name: str = Field(min_length=1)
    objective: str = Field(min_length=1)


class SLOEvaluationResult(BaseModel):
    """Measured SLO state from runtime health checks."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    slo_id: str = Field(min_length=1)
    service_name: str = Field(min_length=1)
    status: SLOStatus
    detail: str = Field(min_length=1)


class IncidentRunbookBinding(BaseModel):
    """One incident class bound to an in-repo runbook reference."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    incident_class: str = Field(min_length=1)
    runbook_path: str = Field(min_length=1)
    primary_command: str = Field(min_length=1)


class OperationalEvidenceRecord(BaseModel):
    """Combined SLO and incident-readiness evidence for the v2.5 runtime."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = OPERATIONS_SCHEMA_VERSION
    product_id: str = Field(min_length=1)
    runtime_version: str = Field(min_length=1)
    environment: str = Field(min_length=1)
    slo_results: tuple[SLOEvaluationResult, ...] = Field(min_length=1)
    runbooks: tuple[IncidentRunbookBinding, ...] = Field(min_length=1)
    generated_at: datetime

    @field_validator("generated_at")
    @classmethod
    def require_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("generated_at must include a timezone")
        return value.astimezone(UTC)

    def sha256(self) -> str:
        payload = self.model_dump(mode="json")
        canonical = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
        return hashlib.sha256(canonical).hexdigest()


class OperationalEvidenceManifest(BaseModel):
    """SHA-256-bound wrapper for operational evidence."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = OPERATIONS_SCHEMA_VERSION
    record: OperationalEvidenceRecord
    record_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    generated_at: datetime

    @field_validator("generated_at")
    @classmethod
    def require_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("generated_at must include a timezone")
        return value.astimezone(UTC)

    @model_validator(mode="after")
    def validate_record_digest(self) -> OperationalEvidenceManifest:
        if self.record_sha256 != self.record.sha256():
            raise ValueError("record_sha256 does not match record")
        return self

    @classmethod
    def from_record(
        cls,
        record: OperationalEvidenceRecord,
        generated_at: datetime | None = None,
    ) -> OperationalEvidenceManifest:
        return cls(
            record=record,
            record_sha256=record.sha256(),
            generated_at=generated_at or datetime.now(tz=UTC),
        )


DEFAULT_SERVICE_SLOS: tuple[ServiceSLODefinition, ...] = (
    ServiceSLODefinition(
        slo_id="platform.minio.availability",
        service_name="MinIO",
        objective="Object storage health and required buckets are reachable",
    ),
    ServiceSLODefinition(
        slo_id="platform.postgres.availability",
        service_name="PostgreSQL",
        objective="Shared metadata database accepts connections",
    ),
    ServiceSLODefinition(
        slo_id="platform.hive_metastore.availability",
        service_name="Hive Metastore",
        objective="Iceberg catalog thrift endpoint is reachable",
    ),
    ServiceSLODefinition(
        slo_id="platform.trino.availability",
        service_name="Trino",
        objective="SQL coordinator responds to health checks",
    ),
    ServiceSLODefinition(
        slo_id="platform.mlflow.availability",
        service_name="MLflow",
        objective="Experiment tracking server is healthy",
    ),
    ServiceSLODefinition(
        slo_id="platform.dagster.availability",
        service_name="Dagster",
        objective="Orchestrator UI/API responds to health checks",
    ),
    ServiceSLODefinition(
        slo_id="platform.openmetadata.availability",
        service_name="OpenMetadata",
        objective="Metadata server and administrator bootstrap are healthy",
    ),
    ServiceSLODefinition(
        slo_id="platform.superset.availability",
        service_name="Superset",
        objective="BI UI health endpoint responds",
    ),
)

DEFAULT_INCIDENT_RUNBOOKS: tuple[IncidentRunbookBinding, ...] = (
    IncidentRunbookBinding(
        incident_class="pipeline.demo_failure",
        runbook_path="docs/DEMO_RUNBOOK.md",
        primary_command="make demo",
    ),
    IncidentRunbookBinding(
        incident_class="platform.service_unhealthy",
        runbook_path="docs/make-demo-guide.md",
        primary_command="make verify",
    ),
    IncidentRunbookBinding(
        incident_class="governance.lineage_gap",
        runbook_path="docs/v2.6-release-readiness.md",
        primary_command="make lineage-evidence",
    ),
    IncidentRunbookBinding(
        incident_class="catalog.portability",
        runbook_path="docs/exit-playbook.md",
        primary_command="make interoperability-proof",
    ),
)


def evaluate_service_slos(
    service_results: list[tuple[str, str, str]],
    definitions: tuple[ServiceSLODefinition, ...] = DEFAULT_SERVICE_SLOS,
) -> tuple[SLOEvaluationResult, ...]:
    """Evaluate configured SLOs against verify-setup service tuples."""
    by_service = {service: (status, detail) for service, status, detail in service_results}
    evaluations: list[SLOEvaluationResult] = []
    for definition in definitions:
        measured = by_service.get(definition.service_name)
        if measured is None:
            evaluations.append(
                SLOEvaluationResult(
                    slo_id=definition.slo_id,
                    service_name=definition.service_name,
                    status="missing",
                    detail="Service check was not executed",
                )
            )
            continue
        status, detail = measured
        evaluations.append(
            SLOEvaluationResult(
                slo_id=definition.slo_id,
                service_name=definition.service_name,
                status="pass" if status == "PASS" else "fail",
                detail=detail,
            )
        )
    return tuple(evaluations)


def build_operational_evidence_record(
    *,
    product_id: str,
    runtime_version: str,
    environment: str,
    slo_results: tuple[SLOEvaluationResult, ...],
    runbooks: tuple[IncidentRunbookBinding, ...] = DEFAULT_INCIDENT_RUNBOOKS,
    generated_at: datetime | None = None,
) -> OperationalEvidenceRecord:
    """Build operational evidence and fail when any SLO is not passing."""
    failing = [result.slo_id for result in slo_results if result.status != "pass"]
    if failing:
        raise ValueError(f"SLO evaluation failed: {', '.join(failing)}")
    return OperationalEvidenceRecord(
        product_id=product_id,
        runtime_version=runtime_version,
        environment=environment,
        slo_results=slo_results,
        runbooks=runbooks,
        generated_at=generated_at or datetime.now(tz=UTC),
    )
