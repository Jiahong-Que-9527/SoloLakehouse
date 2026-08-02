"""Sovereignty and component-origin evidence for v2.7 Block I."""

from __future__ import annotations

import hashlib
import json
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

import yaml  # type: ignore[import-untyped]
from pydantic import BaseModel, ConfigDict, Field, field_validator

SOVEREIGNTY_SCHEMA_VERSION = "v1"
_IMAGE_REF_PATTERN = re.compile(r"^([^:/]+(?:/[^:/]+)*)(?::([^@]+))?(?:@(.+))?$")
_REQUIREMENTS_LINE = re.compile(
    r"^\s*(?:([A-Za-z0-9_.\-]+)\s*(?:\[(?:[^\]]+)\])?\s*(?:==|>=|<=|~=|!=)\s*([^\s;#]+)|([A-Za-z0-9_.\-]+)\s*(?:\[(?:[^\]]+)\])?)\s*(?:#.*)?$"
)

_BUILT_IMAGE_METADATA: dict[str, dict[str, str]] = {
    "hive-metastore": {
        "maintainer": "SoloLakehouse (local build)",
        "origin_country": "reference implementation",
        "license": "Apache-2.0",
        "phone_home": "false",
        "phone_home_notes": "Local Dockerfile; no vendor telemetry in image build.",
    },
    "mlflow": {
        "maintainer": "SoloLakehouse (local build on MLflow upstream)",
        "origin_country": "US (upstream MLflow project)",
        "license": "Apache-2.0",
        "phone_home": "false",
        "phone_home_notes": "Self-hosted tracking server; telemetry depends on deployment config.",
    },
    "dagster-webserver": {
        "maintainer": "SoloLakehouse (local build on Dagster upstream)",
        "origin_country": "US (upstream Dagster project)",
        "license": "Apache-2.0",
        "phone_home": "false",
        "phone_home_notes": "Self-hosted orchestrator; no SaaS dependency in default stack.",
    },
    "dagster-daemon": {
        "maintainer": "SoloLakehouse (local build on Dagster upstream)",
        "origin_country": "US (upstream Dagster project)",
        "license": "Apache-2.0",
        "phone_home": "false",
        "phone_home_notes": "Self-hosted orchestrator; no SaaS dependency in default stack.",
    },
    "superset": {
        "maintainer": "SoloLakehouse (local build on Apache Superset upstream)",
        "origin_country": "US (Apache Superset project)",
        "license": "Apache-2.0",
        "phone_home": "false",
        "phone_home_notes": "Self-hosted BI; default stack does not enable external analytics.",
    },
}

_KNOWN_IMAGES: dict[str, dict[str, str]] = {
    "minio/minio": {
        "maintainer": "MinIO, Inc.",
        "origin_country": "US",
        "license": "AGPL-3.0",
        "phone_home": "false",
        "phone_home_notes": "Self-hosted object storage in default stack.",
    },
    "minio/mc": {
        "maintainer": "MinIO, Inc.",
        "origin_country": "US",
        "license": "AGPL-3.0",
        "phone_home": "false",
        "phone_home_notes": "Init container only; not a runtime dependency.",
    },
    "postgres": {
        "maintainer": "PostgreSQL Global Development Group (Docker Official Image)",
        "origin_country": "global open-source community",
        "license": "PostgreSQL License",
        "phone_home": "false",
        "phone_home_notes": "Self-hosted metadata store.",
    },
    "trinodb/trino": {
        "maintainer": "Trino Software Foundation",
        "origin_country": "US (foundation); global contributors",
        "license": "Apache-2.0",
        "phone_home": "false",
        "phone_home_notes": "Self-hosted query engine.",
    },
    "docker.getcollate.io/openmetadata/db": {
        "maintainer": "Collate (OpenMetadata)",
        "origin_country": "US",
        "license": "Apache-2.0",
        "phone_home": "false",
        "phone_home_notes": "Self-hosted metadata database image.",
    },
    "docker.getcollate.io/openmetadata/server": {
        "maintainer": "Collate (OpenMetadata)",
        "origin_country": "US",
        "license": "Apache-2.0",
        "phone_home": "false",
        "phone_home_notes": "Self-hosted metadata server.",
    },
    "docker.getcollate.io/openmetadata/ingestion": {
        "maintainer": "Collate (OpenMetadata)",
        "origin_country": "US",
        "license": "Apache-2.0",
        "phone_home": "false",
        "phone_home_notes": "Self-hosted ingestion worker.",
    },
    "docker.elastic.co/elasticsearch/elasticsearch": {
        "maintainer": "Elastic N.V.",
        "origin_country": "Netherlands",
        "license": "Elastic License 2.0 / SSPL (image-specific)",
        "phone_home": "false",
        "phone_home_notes": "Bundled for OpenMetadata search in default stack.",
    },
    "apache/polaris": {
        "maintainer": "Apache Software Foundation",
        "origin_country": "US (ASF); global contributors",
        "license": "Apache-2.0",
        "phone_home": "false",
        "phone_home_notes": "Optional REST catalog profile only; not in default stack.",
    },
}

_KNOWN_PYTHON_PACKAGES: dict[str, dict[str, str]] = {
    "pyiceberg": {
        "maintainer": "Apache Iceberg community",
        "origin_country": "US (Apache Software Foundation)",
        "license": "Apache-2.0",
        "phone_home": "false",
    },
    "dagster": {
        "maintainer": "Dagster Labs",
        "origin_country": "US",
        "license": "Apache-2.0",
        "phone_home": "false",
    },
    "mlflow": {
        "maintainer": "Databricks / MLflow project",
        "origin_country": "US",
        "license": "Apache-2.0",
        "phone_home": "false",
    },
    "trino": {
        "maintainer": "Trino Python client contributors",
        "origin_country": "US (client); Trino server self-hosted",
        "license": "Apache-2.0",
        "phone_home": "false",
    },
    "minio": {
        "maintainer": "MinIO, Inc.",
        "origin_country": "US",
        "license": "Apache-2.0",
        "phone_home": "false",
    },
    "pandas": {
        "maintainer": "NumFOCUS / pandas developers",
        "origin_country": "global open-source community",
        "license": "BSD-3-Clause",
        "phone_home": "false",
    },
    "pydantic": {
        "maintainer": "Pydantic Services Inc.",
        "origin_country": "UK",
        "license": "MIT",
        "phone_home": "false",
    },
    "requests": {
        "maintainer": "Python Software Foundation ecosystem",
        "origin_country": "global open-source community",
        "license": "Apache-2.0",
        "phone_home": "false",
    },
    "boto3": {
        "maintainer": "Amazon Web Services",
        "origin_country": "US",
        "license": "Apache-2.0",
        "phone_home": "false",
    },
    "xgboost": {
        "maintainer": "DMLC / XGBoost contributors",
        "origin_country": "global open-source community",
        "license": "Apache-2.0",
        "phone_home": "false",
    },
    "lightgbm": {
        "maintainer": "Microsoft / LightGBM contributors",
        "origin_country": "US",
        "license": "MIT",
        "phone_home": "false",
    },
    "scikit-learn": {
        "maintainer": "scikit-learn developers",
        "origin_country": "global open-source community",
        "license": "BSD-3-Clause",
        "phone_home": "false",
    },
    "pyarrow": {
        "maintainer": "Apache Arrow community",
        "origin_country": "US (Apache Software Foundation)",
        "license": "Apache-2.0",
        "phone_home": "false",
    },
    "pyyaml": {
        "maintainer": "PyYAML contributors",
        "origin_country": "global open-source community",
        "license": "MIT",
        "phone_home": "false",
    },
    "structlog": {
        "maintainer": "structlog contributors",
        "origin_country": "global open-source community",
        "license": "Apache-2.0 / MIT (dual)",
        "phone_home": "false",
    },
    "pytest": {
        "maintainer": "pytest-dev",
        "origin_country": "global open-source community",
        "license": "MIT",
        "phone_home": "false",
    },
    "pytest-cov": {
        "maintainer": "pytest-dev / coverage.py contributors",
        "origin_country": "global open-source community",
        "license": "MIT",
        "phone_home": "false",
    },
    "ruff": {
        "maintainer": "Astral Software Inc.",
        "origin_country": "US",
        "license": "MIT",
        "phone_home": "false",
    },
    "mypy": {
        "maintainer": "mypy developers",
        "origin_country": "global open-source community",
        "license": "MIT",
        "phone_home": "false",
    },
    "types-requests": {
        "maintainer": "python/typeshed contributors",
        "origin_country": "global open-source community",
        "license": "Apache-2.0",
        "phone_home": "false",
    },
    "psycopg2-binary": {
        "maintainer": "psycopg contributors",
        "origin_country": "global open-source community",
        "license": "LGPL-3.0-or-later (binary bundle)",
        "phone_home": "false",
    },
}

_LIMITATIONS = (
    "Reference evidence only. This report inventories declared default-stack "
    "components and curated maintainer metadata; it is not a compliance "
    "certification, residency guarantee, or legal attestation."
)


class PlatformComponent(BaseModel):
    """One deployable or runtime dependency with origin metadata."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    name: str = Field(min_length=1)
    component_type: Literal["container_image", "python_package"]
    version: str = Field(min_length=1)
    maintainer: str = Field(min_length=1)
    origin_country: str = Field(min_length=1)
    license: str = Field(min_length=1)
    phone_home: bool
    phone_home_notes: str = ""
    source_ref: str = Field(min_length=1)


class SovereigntyReport(BaseModel):
    """Machine-readable sovereignty/portability inventory."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = SOVEREIGNTY_SCHEMA_VERSION
    product_id: str = Field(min_length=1)
    runtime_version: str = Field(min_length=1)
    environment: str = Field(min_length=1)
    generated_at: datetime
    components: tuple[PlatformComponent, ...] = Field(min_length=1)
    limitations: str = _LIMITATIONS
    report_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")

    @field_validator("generated_at")
    @classmethod
    def require_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("generated_at must include a timezone")
        return value.astimezone(UTC)

    def canonical_json_bytes(self) -> bytes:
        payload = self.model_dump(mode="json")
        payload.pop("report_sha256")
        return json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")

    @classmethod
    def compute_digest(cls, payload_without_digest: dict[str, object]) -> str:
        encoded = json.dumps(
            payload_without_digest,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()

    @classmethod
    def from_payload(cls, payload: dict[str, object]) -> SovereigntyReport:
        digest = cls.compute_digest(payload)
        return cls(**payload, report_sha256=digest)  # type: ignore[arg-type]


def _lookup_image_metadata(image_ref: str) -> dict[str, str]:
    match = _IMAGE_REF_PATTERN.match(image_ref)
    if match is None:
        raise ValueError(f"Unrecognized container image reference: {image_ref!r}")
    repository = match.group(1)
    for key, metadata in _KNOWN_IMAGES.items():
        if repository == key or repository.endswith(f"/{key}") or repository.endswith(key):
            return metadata
    raise ValueError(
        f"No sovereignty metadata registered for container image {image_ref!r}. "
        "Add an entry to governance/sovereignty.py before claiming coverage."
    )


def _component_from_image(service_name: str, image_ref: str, source_ref: str) -> PlatformComponent:
    metadata = _lookup_image_metadata(image_ref)
    match = _IMAGE_REF_PATTERN.match(image_ref)
    version = match.group(2) if match and match.group(2) else "unspecified"
    return PlatformComponent(
        name=service_name,
        component_type="container_image",
        version=version,
        maintainer=metadata["maintainer"],
        origin_country=metadata["origin_country"],
        license=metadata["license"],
        phone_home=metadata["phone_home"] == "true",
        phone_home_notes=metadata.get("phone_home_notes", ""),
        source_ref=source_ref,
    )


def _component_from_build(service_name: str, source_ref: str) -> PlatformComponent:
    metadata = _BUILT_IMAGE_METADATA.get(service_name)
    if metadata is None:
        raise ValueError(
            f"No sovereignty metadata registered for built service {service_name!r}."
        )
    return PlatformComponent(
        name=service_name,
        component_type="container_image",
        version="local-build",
        maintainer=metadata["maintainer"],
        origin_country=metadata["origin_country"],
        license=metadata["license"],
        phone_home=metadata["phone_home"] == "true",
        phone_home_notes=metadata.get("phone_home_notes", ""),
        source_ref=source_ref,
    )


def _parse_compose_components(compose_path: Path) -> list[PlatformComponent]:
    raw = yaml.safe_load(compose_path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError(f"Invalid compose file: {compose_path}")
    services = raw.get("services", {})
    if not isinstance(services, dict):
        raise ValueError(f"Compose file {compose_path} has no services mapping")

    components: list[PlatformComponent] = []
    for service_name, service_cfg in sorted(services.items()):
        if not isinstance(service_cfg, dict):
            continue
        source_ref = f"{compose_path}:{service_name}"
        if "image" in service_cfg:
            components.append(
                _component_from_image(service_name, str(service_cfg["image"]), source_ref)
            )
        elif "build" in service_cfg:
            components.append(_component_from_build(str(service_name), source_ref))
    return components


def _parse_requirements_components(requirements_path: Path) -> list[PlatformComponent]:
    components: list[PlatformComponent] = []
    for line in requirements_path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        match = _REQUIREMENTS_LINE.match(stripped)
        if match is None:
            raise ValueError(f"Could not parse requirements line: {stripped!r}")
        name = match.group(1) or match.group(3)
        version = match.group(2) or "unspecified"
        if name is None:
            continue
        normalized = name.lower().replace("_", "-")
        metadata = _KNOWN_PYTHON_PACKAGES.get(normalized)
        if metadata is None:
            raise ValueError(
                f"No sovereignty metadata registered for python package {name!r}. "
                "Add an entry to governance/sovereignty.py before claiming coverage."
            )
        components.append(
            PlatformComponent(
                name=normalized,
                component_type="python_package",
                version=version,
                maintainer=metadata["maintainer"],
                origin_country=metadata["origin_country"],
                license=metadata["license"],
                phone_home=metadata["phone_home"] == "true",
                phone_home_notes=metadata.get("phone_home_notes", ""),
                source_ref=f"{requirements_path}:{normalized}",
            )
        )
    return components


def build_sovereignty_report(
    *,
    product_id: str,
    runtime_version: str,
    environment: str,
    repository_root: Path,
    generated_at: datetime | None = None,
) -> SovereigntyReport:
    """Scan default-stack compose files and Python requirements for origin metadata."""
    compose_files = [
        repository_root / "docker" / "docker-compose.yml",
        repository_root / "docker" / "docker-compose.openmetadata.yml",
        repository_root / "docker" / "docker-compose.superset.yml",
    ]
    components: list[PlatformComponent] = []
    for compose_path in compose_files:
        components.extend(_parse_compose_components(compose_path))
    components.extend(_parse_requirements_components(repository_root / "requirements.txt"))

    timestamp = generated_at or datetime.now(tz=UTC)
    component_tuple = tuple(components)
    digest = SovereigntyReport.compute_digest(
        {
            "schema_version": SOVEREIGNTY_SCHEMA_VERSION,
            "product_id": product_id,
            "runtime_version": runtime_version,
            "environment": environment,
            "generated_at": timestamp.isoformat(),
            "components": [component.model_dump(mode="json") for component in component_tuple],
            "limitations": _LIMITATIONS,
        }
    )
    return SovereigntyReport(
        product_id=product_id,
        runtime_version=runtime_version,
        environment=environment,
        generated_at=timestamp,
        components=component_tuple,
        report_sha256=digest,
    )


def render_sovereignty_markdown(report: SovereigntyReport) -> str:
    """Render a human-readable sovereignty report."""
    lines = [
        "# SoloLakehouse Sovereignty Report",
        "",
        f"- Product: `{report.product_id}`",
        f"- Runtime version: `{report.runtime_version}`",
        f"- Environment: `{report.environment}`",
        f"- Generated at: `{report.generated_at.isoformat()}`",
        f"- Report SHA-256: `{report.report_sha256}`",
        "",
        "## Components",
        "",
        "| Name | Type | Version | Maintainer | Origin | License | Phone-home | Source |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for component in report.components:
        phone_home = "yes" if component.phone_home else "no"
        lines.append(
            "| "
            + " | ".join(
                [
                    component.name,
                    component.component_type,
                    component.version,
                    component.maintainer,
                    component.origin_country,
                    component.license,
                    phone_home,
                    component.source_ref,
                ]
            )
            + " |"
        )
    lines.extend(["", "## Limitations", "", report.limitations, ""])
    return "\n".join(lines)
