"""Catalog interoperability evidence for v2.7 Block I."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

INTEROPERABILITY_SCHEMA_VERSION = "v1"


class CatalogBackendBinding(BaseModel):
    """One catalog backend configuration bound to a shared warehouse layout."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    backend: Literal["hive", "rest"]
    catalog_name: str = Field(min_length=1)
    connection_uri: str = Field(min_length=1)
    warehouse_uri: str = Field(min_length=1)
    s3_endpoint: str = Field(min_length=1)


class CatalogInteroperabilityProof(BaseModel):
    """Minimal proof that Hive and REST backends share one warehouse binding."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: str = INTEROPERABILITY_SCHEMA_VERSION
    product_id: str = Field(min_length=1)
    runtime_version: str = Field(min_length=1)
    environment: str = Field(min_length=1)
    shared_warehouse_uri: str = Field(min_length=1)
    shared_s3_endpoint: str = Field(min_length=1)
    backends: tuple[CatalogBackendBinding, ...] = Field(min_length=2)
    live_rest_namespace_count: int | None = None
    generated_at: datetime
    proof_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")

    @field_validator("generated_at")
    @classmethod
    def require_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("generated_at must include a timezone")
        return value.astimezone(UTC)

    @field_validator("backends")
    @classmethod
    def require_hive_and_rest(
        cls, value: tuple[CatalogBackendBinding, ...]
    ) -> tuple[CatalogBackendBinding, ...]:
        backends = {binding.backend for binding in value}
        if backends != {"hive", "rest"}:
            raise ValueError("backends must include exactly one hive and one rest binding")
        return value

    def canonical_json_bytes(self) -> bytes:
        payload = self.model_dump(mode="json")
        payload.pop("proof_sha256")
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
    def from_payload(cls, payload: dict[str, object]) -> CatalogInteroperabilityProof:
        digest = cls.compute_digest(payload)
        return cls(**payload, proof_sha256=digest)  # type: ignore[arg-type]


def build_catalog_interoperability_proof(
    *,
    product_id: str,
    runtime_version: str,
    environment: str,
    hive_binding: CatalogBackendBinding,
    rest_binding: CatalogBackendBinding,
    live_rest_namespace_count: int | None = None,
    generated_at: datetime | None = None,
) -> CatalogInteroperabilityProof:
    """Build a SHA-256-bound interoperability proof from two backend bindings."""
    if hive_binding.backend != "hive" or rest_binding.backend != "rest":
        raise ValueError("hive_binding and rest_binding must use the expected backends")
    if hive_binding.warehouse_uri != rest_binding.warehouse_uri:
        raise ValueError("Hive and REST bindings must share the same warehouse_uri")
    if hive_binding.s3_endpoint != rest_binding.s3_endpoint:
        raise ValueError("Hive and REST bindings must share the same s3_endpoint")

    timestamp = generated_at or datetime.now(tz=UTC)
    digest = CatalogInteroperabilityProof.compute_digest(
        {
            "schema_version": INTEROPERABILITY_SCHEMA_VERSION,
            "product_id": product_id,
            "runtime_version": runtime_version,
            "environment": environment,
            "shared_warehouse_uri": hive_binding.warehouse_uri,
            "shared_s3_endpoint": hive_binding.s3_endpoint,
            "backends": (
                hive_binding.model_dump(mode="json"),
                rest_binding.model_dump(mode="json"),
            ),
            "live_rest_namespace_count": live_rest_namespace_count,
            "generated_at": timestamp.isoformat(),
        }
    )
    return CatalogInteroperabilityProof(
        product_id=product_id,
        runtime_version=runtime_version,
        environment=environment,
        shared_warehouse_uri=hive_binding.warehouse_uri,
        shared_s3_endpoint=hive_binding.s3_endpoint,
        backends=(hive_binding, rest_binding),
        live_rest_namespace_count=live_rest_namespace_count,
        generated_at=timestamp,
        proof_sha256=digest,
    )


def count_rest_namespaces(catalog: object) -> int:
    """Return namespace count from a live REST catalog (raises on failure)."""
    namespaces = catalog.list_namespaces()  # type: ignore[attr-defined]
    return len(list(namespaces))
