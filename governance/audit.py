"""Audit-bucket writer for validated lineage evidence manifests."""

from __future__ import annotations

from typing import Any

from governance.evidence import EvidenceManifest, manifest_object_path
from governance.lineage import EvidenceSourceError


class AuditEvidenceWriter:
    """Write canonical manifest bytes to the configured audit bucket."""

    def __init__(self, client: Any, bucket: str) -> None:
        self.client = client
        self.bucket = bucket

    def write_manifest(self, manifest: EvidenceManifest) -> str:
        object_path = manifest_object_path(manifest.record)
        try:
            self.client.put_object(
                Bucket=self.bucket,
                Key=object_path,
                Body=manifest.model_dump_json(indent=2).encode("utf-8"),
                ContentType="application/json",
            )
        except Exception as exc:
            raise EvidenceSourceError(
                "audit", f"cannot write {self.bucket}/{object_path}: {exc}"
            ) from exc
        return object_path
