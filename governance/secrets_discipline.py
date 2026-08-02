"""Secrets discipline evidence for v2.9 Block D."""

from __future__ import annotations

import hashlib
import json
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

SECRETS_SCHEMA_VERSION = "v1"
CheckStatus = Literal["pass", "fail", "warn"]

_SECRET_KEY_NAMES: frozenset[str] = frozenset(
    {
        "MINIO_ROOT_PASSWORD",
        "POSTGRES_PASSWORD",
        "S3_SECRET_KEY",
        "AWS_SECRET_ACCESS_KEY",
        "SUPERSET_SECRET_KEY",
        "SUPERSET_ADMIN_PASSWORD",
        "OPENMETADATA_AUTH_TOKEN",
        "ICEBERG_REST_CREDENTIAL",
    }
)
_TRACKED_SECRET_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"OPENMETADATA_AUTH_TOKEN\s*=\s*['\"][^'\"]{8,}['\"]"),
    re.compile(r"AWS_SECRET_ACCESS_KEY\s*=\s*['\"][^'\"]{8,}['\"]"),
    re.compile(r"password\s*=\s*['\"][^'\"]{8,}['\"]", re.IGNORECASE),
)
_SCAN_GLOBS = (
    "ingestion/**/*.py",
    "transformations/**/*.py",
    "ml/**/*.py",
    "governance/**/*.py",
    "scripts/**/*.py",
    "dagster/**/*.py",
)


class SecretsDisciplineCheck(BaseModel):
    """One secrets/access discipline check."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    check_id: str = Field(min_length=1)
    description: str = Field(min_length=1)
    status: CheckStatus
    detail: str = Field(min_length=1)


class SecretsDisciplineRecord(BaseModel):
    """Machine-readable secrets discipline evidence."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = SECRETS_SCHEMA_VERSION
    product_id: str = Field(min_length=1)
    runtime_version: str = Field(min_length=1)
    environment: str = Field(min_length=1)
    checks: tuple[SecretsDisciplineCheck, ...] = Field(min_length=1)
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


class SecretsDisciplineManifest(BaseModel):
    """SHA-256-bound wrapper for secrets discipline evidence."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = SECRETS_SCHEMA_VERSION
    record: SecretsDisciplineRecord
    record_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    generated_at: datetime

    @field_validator("generated_at")
    @classmethod
    def require_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("generated_at must include a timezone")
        return value.astimezone(UTC)

    @model_validator(mode="after")
    def validate_record_digest(self) -> SecretsDisciplineManifest:
        if self.record_sha256 != self.record.sha256():
            raise ValueError("record_sha256 does not match record")
        return self

    @classmethod
    def from_record(
        cls,
        record: SecretsDisciplineRecord,
        generated_at: datetime | None = None,
    ) -> SecretsDisciplineManifest:
        return cls(
            record=record,
            record_sha256=record.sha256(),
            generated_at=generated_at or datetime.now(tz=UTC),
        )


class SecretsRotationDrillRecord(BaseModel):
    """Recorded manual rotation drill for local secrets discipline."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = SECRETS_SCHEMA_VERSION
    product_id: str = Field(min_length=1)
    runtime_version: str = Field(min_length=1)
    environment: str = Field(min_length=1)
    rotated_keys: tuple[str, ...] = Field(min_length=1)
    verification_command: str = Field(min_length=1)
    notes: str = ""
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


class SecretsRotationDrillManifest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = SECRETS_SCHEMA_VERSION
    record: SecretsRotationDrillRecord
    record_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    generated_at: datetime

    @field_validator("generated_at")
    @classmethod
    def require_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("generated_at must include a timezone")
        return value.astimezone(UTC)

    @model_validator(mode="after")
    def validate_record_digest(self) -> SecretsRotationDrillManifest:
        if self.record_sha256 != self.record.sha256():
            raise ValueError("record_sha256 does not match record")
        return self

    @classmethod
    def from_record(
        cls,
        record: SecretsRotationDrillRecord,
        generated_at: datetime | None = None,
    ) -> SecretsRotationDrillManifest:
        return cls(
            record=record,
            record_sha256=record.sha256(),
            generated_at=generated_at or datetime.now(tz=UTC),
        )


def _parse_env_keys(path: Path) -> set[str]:
    keys: set[str] = set()
    if not path.exists():
        return keys
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        keys.add(line.split("=", 1)[0].strip())
    return keys


def _gitignore_contains(path: Path, needle: str) -> bool:
    if not path.exists():
        return False
    return any(line.strip() == needle for line in path.read_text(encoding="utf-8").splitlines())


def scan_tracked_python_for_embedded_secrets(repository_root: Path) -> list[str]:
    """Return file paths that appear to embed secret literals."""
    violations: list[str] = []
    for pattern in _SCAN_GLOBS:
        for file_path in sorted(repository_root.glob(pattern)):
            if not file_path.is_file():
                continue
            text = file_path.read_text(encoding="utf-8")
            for regex in _TRACKED_SECRET_PATTERNS:
                if regex.search(text):
                    violations.append(str(file_path.relative_to(repository_root)))
                    break
    return violations


def evaluate_secrets_discipline(
    *,
    product_id: str,
    runtime_version: str,
    environment: str,
    repository_root: Path,
    generated_at: datetime | None = None,
) -> SecretsDisciplineRecord:
    """Run repository secrets/access discipline checks."""
    checks: list[SecretsDisciplineCheck] = []

    shared_example = repository_root / ".env.shared.example"
    secrets_example = repository_root / ".env.secrets.example"
    checks.append(
        SecretsDisciplineCheck(
            check_id="env.shared_example_present",
            description="Shared env template exists for non-secret configuration",
            status="pass" if shared_example.exists() else "fail",
            detail=str(shared_example),
        )
    )
    checks.append(
        SecretsDisciplineCheck(
            check_id="env.secrets_example_present",
            description="Secrets env template exists for local-only credentials",
            status="pass" if secrets_example.exists() else "fail",
            detail=str(secrets_example),
        )
    )

    shared_keys = _parse_env_keys(shared_example)
    secret_keys = _parse_env_keys(secrets_example)
    leaked = sorted(shared_keys & _SECRET_KEY_NAMES)
    checks.append(
        SecretsDisciplineCheck(
            check_id="env.shared_has_no_secret_keys",
            description="Shared env template excludes secret key names",
            status="pass" if not leaked else "fail",
            detail="none" if not leaked else f"secret keys in shared template: {', '.join(leaked)}",
        )
    )
    missing_secret_templates = sorted(_SECRET_KEY_NAMES - secret_keys)
    checks.append(
        SecretsDisciplineCheck(
            check_id="env.secrets_documents_required_keys",
            description="Secrets env template documents required secret keys",
            status="pass" if not missing_secret_templates else "fail",
            detail=(
                "all required keys present"
                if not missing_secret_templates
                else f"missing: {', '.join(missing_secret_templates)}"
            ),
        )
    )

    gitignore = repository_root / ".gitignore"
    for ignored in (".env", ".env.shared", ".env.secrets"):
        check_id = f"gitignore.{ignored.removeprefix('.').replace('.', '_')}"
        checks.append(
            SecretsDisciplineCheck(
                check_id=check_id,
                description=f"{ignored} is gitignored",
                status="pass" if _gitignore_contains(gitignore, ignored) else "fail",
                detail=str(gitignore),
            )
        )

    embedded = scan_tracked_python_for_embedded_secrets(repository_root)
    checks.append(
        SecretsDisciplineCheck(
            check_id="python.no_embedded_secret_literals",
            description="Python sources do not embed obvious secret literals",
            status="pass" if not embedded else "fail",
            detail="none" if not embedded else ", ".join(embedded),
        )
    )

    if environment in {"production", "prod"} and secret_keys:
        weak = [key for key in secret_keys if key in _SECRET_KEY_NAMES]
        checks.append(
            SecretsDisciplineCheck(
                check_id="access.production_secret_placeholders",
                description="Production environments must not rely on example secret values",
                status="warn",
                detail=(
                    "manual verification required for "
                    + ", ".join(sorted(weak))
                ),
            )
        )

    return SecretsDisciplineRecord(
        product_id=product_id,
        runtime_version=runtime_version,
        environment=environment,
        checks=tuple(checks),
        generated_at=generated_at or datetime.now(tz=UTC),
    )


def build_secrets_discipline_record(
    *,
    product_id: str,
    runtime_version: str,
    environment: str,
    repository_root: Path,
    generated_at: datetime | None = None,
) -> SecretsDisciplineRecord:
    """Build secrets discipline evidence and fail on any failed check."""
    record = evaluate_secrets_discipline(
        product_id=product_id,
        runtime_version=runtime_version,
        environment=environment,
        repository_root=repository_root,
        generated_at=generated_at,
    )
    failing = [check.check_id for check in record.checks if check.status == "fail"]
    if failing:
        raise ValueError(f"Secrets discipline checks failed: {', '.join(failing)}")
    return record
