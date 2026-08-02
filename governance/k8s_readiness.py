"""Kubernetes migration readiness evidence for v2.9 Block F."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

K8S_READINESS_SCHEMA_VERSION = "v1"
ReadinessStatus = Literal["ready", "deferred", "missing"]


class K8sReadinessCheck(BaseModel):
    """One v3 migration prerequisite evaluated on the v2.5 runtime."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    check_id: str = Field(min_length=1)
    description: str = Field(min_length=1)
    status: ReadinessStatus
    detail: str = Field(min_length=1)


class K8sReadinessRecord(BaseModel):
    """Machine-readable readiness gate before v3 runtime migration."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = K8S_READINESS_SCHEMA_VERSION
    product_id: str = Field(min_length=1)
    runtime_version: str = Field(min_length=1)
    environment: str = Field(min_length=1)
    checks: tuple[K8sReadinessCheck, ...] = Field(min_length=1)
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


class K8sReadinessManifest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = K8S_READINESS_SCHEMA_VERSION
    record: K8sReadinessRecord
    record_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    generated_at: datetime

    @field_validator("generated_at")
    @classmethod
    def require_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("generated_at must include a timezone")
        return value.astimezone(UTC)

    @model_validator(mode="after")
    def validate_record_digest(self) -> K8sReadinessManifest:
        if self.record_sha256 != self.record.sha256():
            raise ValueError("record_sha256 does not match record")
        return self

    @classmethod
    def from_record(
        cls,
        record: K8sReadinessRecord,
        generated_at: datetime | None = None,
    ) -> K8sReadinessManifest:
        return cls(
            record=record,
            record_sha256=record.sha256(),
            generated_at=generated_at or datetime.now(tz=UTC),
        )


def _status_for_path(path: Path, *, deferred: bool = False) -> ReadinessStatus:
    if path.exists():
        return "ready"
    return "deferred" if deferred else "missing"


def _status_for_make_target(makefile_text: str, target: str) -> ReadinessStatus:
    return "ready" if f"{target}:" in makefile_text else "missing"


def evaluate_k8s_readiness(
    *,
    product_id: str,
    runtime_version: str,
    environment: str,
    repository_root: Path,
    generated_at: datetime | None = None,
) -> K8sReadinessRecord:
    """Evaluate v2.9 evidence prerequisites required before v3 migration."""
    makefile = (repository_root / "Makefile").read_text(encoding="utf-8")
    checks: list[K8sReadinessCheck] = [
        K8sReadinessCheck(
            check_id="runtime.compose_baseline",
            description="Protected v2.5 Compose baseline remains present",
            status=_status_for_path(repository_root / "docker" / "docker-compose.yml"),
            detail="docker/docker-compose.yml",
        ),
        K8sReadinessCheck(
            check_id="governance.contracts",
            description="Governed dataset contracts exist",
            status=_status_for_path(repository_root / "governance" / "datasets"),
            detail="governance/datasets/",
        ),
        K8sReadinessCheck(
            check_id="governance.promotion_evidence",
            description="Promotion evidence module and CLI exist",
            status=(
                "ready"
                if (
                    (repository_root / "governance" / "promotion.py").exists()
                    and _status_for_make_target(makefile, "promotion-evidence") == "ready"
                )
                else "missing"
            ),
            detail="governance/promotion.py + make promotion-evidence",
        ),
        K8sReadinessCheck(
            check_id="governance.operational_evidence",
            description="Operational SLO evidence module and CLI exist",
            status=(
                "ready"
                if (
                    (repository_root / "governance" / "operations.py").exists()
                    and _status_for_make_target(makefile, "operational-evidence") == "ready"
                )
                else "missing"
            ),
            detail="governance/operations.py + make operational-evidence",
        ),
        K8sReadinessCheck(
            check_id="governance.secrets_discipline",
            description="Secrets discipline module and CLI exist",
            status=(
                "ready"
                if (
                    (repository_root / "governance" / "secrets_discipline.py").exists()
                    and _status_for_make_target(makefile, "secrets-discipline") == "ready"
                )
                else "missing"
            ),
            detail="governance/secrets_discipline.py + make secrets-discipline",
        ),
        K8sReadinessCheck(
            check_id="docs.exit_playbook",
            description="Catalog/runtime exit playbook is documented",
            status=_status_for_path(repository_root / "docs" / "exit-playbook.md"),
            detail="docs/exit-playbook.md",
        ),
        K8sReadinessCheck(
            check_id="adr.v3_runtime_migration",
            description="v3 runtime migration ADR is recorded",
            status=_status_for_path(
                repository_root / "docs" / "decisions" / "ADR-007-v3-k8s-helm-terraform.md"
            ),
            detail="docs/decisions/ADR-007-v3-k8s-helm-terraform.md",
        ),
        K8sReadinessCheck(
            check_id="infra.helm_charts",
            description="Helm charts for v3 migration",
            status=_status_for_path(repository_root / "helm", deferred=True),
            detail="helm/ (expected in v3.0, not v2.9)",
        ),
        K8sReadinessCheck(
            check_id="infra.terraform",
            description="Terraform baseline for v3 migration",
            status=_status_for_path(repository_root / "terraform", deferred=True),
            detail="terraform/ (expected in v3.0, not v2.9)",
        ),
    ]
    return K8sReadinessRecord(
        product_id=product_id,
        runtime_version=runtime_version,
        environment=environment,
        checks=tuple(checks),
        generated_at=generated_at or datetime.now(tz=UTC),
    )


def build_k8s_readiness_record(
    *,
    product_id: str,
    runtime_version: str,
    environment: str,
    repository_root: Path,
    generated_at: datetime | None = None,
) -> K8sReadinessRecord:
    """Build readiness evidence and fail when any non-deferred check is missing."""
    record = evaluate_k8s_readiness(
        product_id=product_id,
        runtime_version=runtime_version,
        environment=environment,
        repository_root=repository_root,
        generated_at=generated_at,
    )
    missing = [
        check.check_id
        for check in record.checks
        if check.status == "missing"
    ]
    if missing:
        raise ValueError(f"K8s readiness checks missing: {', '.join(missing)}")
    return record
