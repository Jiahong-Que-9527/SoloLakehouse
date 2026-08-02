"""Promotion and rollback evidence for v2.9 Block B."""

from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
from datetime import UTC, datetime
from typing import Literal, Mapping

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

PROMOTION_SCHEMA_VERSION = "v1"
PromotionStage = Literal["dev", "staging", "production"]
PromotionGateStatus = Literal["pass", "fail", "skip"]
_GIT_COMMIT_PATTERN = re.compile(r"^[0-9a-f]{40}$")
_PROMOTION_CHAIN: dict[PromotionStage, PromotionStage | None] = {
    "dev": "staging",
    "staging": "production",
    "production": None,
}


class PromotionGateResult(BaseModel):
    """One promotion gate evaluation."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    gate_id: str = Field(min_length=1)
    description: str = Field(min_length=1)
    status: PromotionGateStatus
    detail: str = Field(min_length=1)


class PromotionEvidenceRecord(BaseModel):
    """Machine-readable promotion gate evidence for one stage transition."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = PROMOTION_SCHEMA_VERSION
    product_id: str = Field(min_length=1)
    runtime_version: str = Field(min_length=1)
    environment: str = Field(min_length=1)
    source_stage: PromotionStage
    target_stage: PromotionStage
    git_commit: str = Field(pattern=r"^[0-9a-f]{40}$")
    rollback_target_tag: str = Field(min_length=1)
    gates: tuple[PromotionGateResult, ...] = Field(min_length=1)
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


class PromotionEvidenceManifest(BaseModel):
    """SHA-256-bound wrapper for a promotion evidence record."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = PROMOTION_SCHEMA_VERSION
    record: PromotionEvidenceRecord
    record_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    generated_at: datetime

    @field_validator("generated_at")
    @classmethod
    def require_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("generated_at must include a timezone")
        return value.astimezone(UTC)

    @model_validator(mode="after")
    def validate_record_digest(self) -> PromotionEvidenceManifest:
        if self.record_sha256 != self.record.sha256():
            raise ValueError("record_sha256 does not match record")
        return self

    @classmethod
    def from_record(
        cls,
        record: PromotionEvidenceRecord,
        generated_at: datetime | None = None,
    ) -> PromotionEvidenceManifest:
        return cls(
            record=record,
            record_sha256=record.sha256(),
            generated_at=generated_at or datetime.now(tz=UTC),
        )


class RollbackDrillRecord(BaseModel):
    """Rollback readiness evidence from a drill against a known-good tag."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = PROMOTION_SCHEMA_VERSION
    product_id: str = Field(min_length=1)
    runtime_version: str = Field(min_length=1)
    environment: str = Field(min_length=1)
    current_git_commit: str = Field(pattern=r"^[0-9a-f]{40}$")
    rollback_target_tag: str = Field(min_length=1)
    rollback_target_commit: str = Field(pattern=r"^[0-9a-f]{40}$")
    runtime_checks_passed: bool
    gates: tuple[PromotionGateResult, ...] = Field(min_length=1)
    rollback_commands: tuple[str, ...] = Field(min_length=1)
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


class RollbackDrillManifest(BaseModel):
    """SHA-256-bound wrapper for rollback drill evidence."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = PROMOTION_SCHEMA_VERSION
    record: RollbackDrillRecord
    record_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    generated_at: datetime

    @field_validator("generated_at")
    @classmethod
    def require_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("generated_at must include a timezone")
        return value.astimezone(UTC)

    @model_validator(mode="after")
    def validate_record_digest(self) -> RollbackDrillManifest:
        if self.record_sha256 != self.record.sha256():
            raise ValueError("record_sha256 does not match record")
        return self

    @classmethod
    def from_record(
        cls,
        record: RollbackDrillRecord,
        generated_at: datetime | None = None,
    ) -> RollbackDrillManifest:
        return cls(
            record=record,
            record_sha256=record.sha256(),
            generated_at=generated_at or datetime.now(tz=UTC),
        )


def resolve_promotion_stage(environ: Mapping[str, str] | None = None) -> PromotionStage:
    """Resolve the current promotion stage from PROMOTION_STAGE or ENVIRONMENT."""
    env = os.environ if environ is None else environ
    explicit = env.get("PROMOTION_STAGE", "").strip().lower()
    if explicit:
        if explicit not in _PROMOTION_CHAIN:
            raise ValueError(
                "PROMOTION_STAGE must be one of "
                f"{sorted(_PROMOTION_CHAIN)!r}, received {explicit!r}"
            )
        return explicit  # type: ignore[return-value]

    environment = env.get("ENVIRONMENT", "local").strip().lower()
    if environment in {"production", "prod"}:
        return "production"
    if environment == "staging":
        return "staging"
    return "dev"


def next_promotion_stage(source: PromotionStage) -> PromotionStage | None:
    """Return the next stage in the dev -> staging -> production chain."""
    return _PROMOTION_CHAIN[source]


def validate_promotion_transition(source: PromotionStage, target: PromotionStage) -> None:
    """Fail loudly when a stage transition violates the dev -> staging -> production chain."""
    expected_target = _PROMOTION_CHAIN[source]
    if expected_target != target:
        raise ValueError(
            f"Invalid promotion transition {source!r} -> {target!r}; "
            f"expected next stage is {expected_target!r}"
        )


def resolve_git_commit(environ: Mapping[str, str] | None = None) -> str:
    """Resolve the current git commit from GIT_COMMIT or `git rev-parse HEAD`."""
    env = os.environ if environ is None else environ
    configured = env.get("GIT_COMMIT", "").strip().lower()
    if configured:
        if not _GIT_COMMIT_PATTERN.fullmatch(configured):
            raise ValueError("GIT_COMMIT is not a valid git hash")
        return configured
    completed = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        check=True,
        capture_output=True,
        text=True,
        timeout=5,
    )
    commit = completed.stdout.strip().lower()
    if not _GIT_COMMIT_PATTERN.fullmatch(commit):
        raise ValueError("git rev-parse HEAD did not return a valid commit hash")
    return commit


def resolve_rollback_target_tag(environ: Mapping[str, str] | None = None) -> str:
    """Return the configured rollback tag required for promotion evidence."""
    env = os.environ if environ is None else environ
    tag = env.get("ROLLBACK_TARGET_TAG", "").strip()
    if not tag:
        raise ValueError("ROLLBACK_TARGET_TAG is required for promotion/rollback evidence")
    return tag


def resolve_tag_commit(tag: str) -> str:
    """Resolve a git tag to a commit hash."""
    completed = subprocess.run(
        ["git", "rev-parse", tag],
        check=True,
        capture_output=True,
        text=True,
        timeout=5,
    )
    commit = completed.stdout.strip().lower()
    if not _GIT_COMMIT_PATTERN.fullmatch(commit):
        raise ValueError(f"tag {tag!r} did not resolve to a valid commit hash")
    return commit


def gates_from_service_checks(
    service_results: list[tuple[str, str, str]],
) -> tuple[PromotionGateResult, ...]:
    """Convert verify-setup tuples into promotion gate results."""
    gates: list[PromotionGateResult] = []
    for service, status, detail in service_results:
        gates.append(
            PromotionGateResult(
                gate_id=f"runtime.{service.lower().replace(' ', '_')}",
                description=f"Runtime health check for {service}",
                status="pass" if status == "PASS" else "fail",
                detail=detail,
            )
        )
    return tuple(gates)


def default_rollback_commands(rollback_target_tag: str) -> tuple[str, ...]:
    """Return the reference rollback command sequence for the v2.5 runtime."""
    return (
        f"git checkout {rollback_target_tag}",
        "make down",
        "make up",
        "make verify",
        "make demo",
    )


def build_promotion_evidence_record(
    *,
    product_id: str,
    runtime_version: str,
    environment: str,
    source_stage: PromotionStage,
    target_stage: PromotionStage,
    git_commit: str,
    rollback_target_tag: str,
    gates: tuple[PromotionGateResult, ...],
    generated_at: datetime | None = None,
) -> PromotionEvidenceRecord:
    """Build one promotion evidence record after gate evaluation."""
    validate_promotion_transition(source_stage, target_stage)
    if any(gate.status == "fail" for gate in gates):
        failing = ", ".join(gate.gate_id for gate in gates if gate.status == "fail")
        raise ValueError(f"Promotion gates failed: {failing}")
    return PromotionEvidenceRecord(
        product_id=product_id,
        runtime_version=runtime_version,
        environment=environment,
        source_stage=source_stage,
        target_stage=target_stage,
        git_commit=git_commit,
        rollback_target_tag=rollback_target_tag,
        gates=gates,
        generated_at=generated_at or datetime.now(tz=UTC),
    )
