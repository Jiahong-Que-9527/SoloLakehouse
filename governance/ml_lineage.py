"""ML lineage five-tuple types and binding helpers for v2.8."""

from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
from typing import Any, Mapping

from pydantic import BaseModel, ConfigDict, Field, field_validator

from governance.contracts import DatasetContract

ML_LINEAGE_SCHEMA_VERSION = "v1"
_GIT_COMMIT_PATTERN = re.compile(r"^[0-9a-f]{7,40}$")
_MLFLOW_TAG_PREFIX = "slh."


class MLLineageError(ValueError):
    """A required ML lineage field is missing or invalid."""

    def __init__(self, field: str, reason: str) -> None:
        super().__init__(f"ML lineage field {field!r} is invalid: {reason}")
        self.field = field
        self.reason = reason


class MLLineageTuple(BaseModel):
    """Governed binding from one MLflow run to data, code, and contract evidence."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    iceberg_snapshot_id: str = Field(min_length=1)
    dagster_run_id: str = Field(min_length=1)
    feature_version: str = Field(min_length=1)
    code_commit: str = Field(min_length=1)
    data_contract_hash: str = Field(pattern=r"^[0-9a-f]{64}$")

    @field_validator("dagster_run_id")
    @classmethod
    def validate_dagster_run_id(cls, value: str) -> str:
        if "/" in value or "\\" in value:
            raise ValueError("dagster_run_id cannot contain path separators")
        return value

    @field_validator("code_commit")
    @classmethod
    def validate_code_commit(cls, value: str) -> str:
        if not _GIT_COMMIT_PATTERN.fullmatch(value):
            raise ValueError("code_commit must be a lowercase git commit hash")
        return value

    def canonical_json_bytes(self) -> bytes:
        payload = self.model_dump(mode="json")
        return json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")

    def sha256(self) -> str:
        return hashlib.sha256(self.canonical_json_bytes()).hexdigest()


def contract_content_sha256(contract: DatasetContract) -> str:
    """Return the SHA-256 digest of a contract's canonical JSON representation."""
    payload = contract.model_dump(mode="json")
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


def resolve_code_commit(environ: Mapping[str, str] | None = None) -> str:
    """Resolve the current git commit from GIT_COMMIT or `git rev-parse HEAD`."""
    env = os.environ if environ is None else environ
    configured = env.get("GIT_COMMIT", "").strip().lower()
    if configured:
        if not _GIT_COMMIT_PATTERN.fullmatch(configured):
            raise MLLineageError("code_commit", "GIT_COMMIT is not a valid git hash")
        return configured

    try:
        completed = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
            timeout=5,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise MLLineageError(
            "code_commit",
            "set GIT_COMMIT or run inside a git checkout with git available",
        ) from exc

    commit = completed.stdout.strip().lower()
    if not _GIT_COMMIT_PATTERN.fullmatch(commit):
        raise MLLineageError("code_commit", "git rev-parse HEAD did not return a valid hash")
    return commit


def build_ml_lineage_tuple(
    *,
    iceberg_snapshot_id: str,
    dagster_run_id: str,
    feature_version: str,
    data_contract_hash: str,
    code_commit: str | None = None,
    environ: Mapping[str, str] | None = None,
) -> MLLineageTuple:
    """Construct and validate the five-tuple, resolving code_commit when omitted."""
    resolved_commit = code_commit or resolve_code_commit(environ)
    for field_name, value in (
        ("iceberg_snapshot_id", iceberg_snapshot_id),
        ("dagster_run_id", dagster_run_id),
        ("feature_version", feature_version),
        ("data_contract_hash", data_contract_hash),
    ):
        if not str(value).strip():
            raise MLLineageError(field_name, "required value is missing")
    try:
        return MLLineageTuple(
            iceberg_snapshot_id=iceberg_snapshot_id,
            dagster_run_id=dagster_run_id,
            feature_version=feature_version,
            code_commit=resolved_commit,
            data_contract_hash=data_contract_hash,
        )
    except ValueError as exc:
        raise MLLineageError("tuple", str(exc)) from exc


def mlflow_tags_for_tuple(lineage: MLLineageTuple) -> dict[str, str]:
    """Return MLflow tags for one validated five-tuple."""
    return {
        f"{_MLFLOW_TAG_PREFIX}ml_lineage_schema": ML_LINEAGE_SCHEMA_VERSION,
        f"{_MLFLOW_TAG_PREFIX}iceberg_snapshot_id": lineage.iceberg_snapshot_id,
        f"{_MLFLOW_TAG_PREFIX}dagster_run_id": lineage.dagster_run_id,
        f"{_MLFLOW_TAG_PREFIX}feature_version": lineage.feature_version,
        f"{_MLFLOW_TAG_PREFIX}code_commit": lineage.code_commit,
        f"{_MLFLOW_TAG_PREFIX}data_contract_hash": lineage.data_contract_hash,
        f"{_MLFLOW_TAG_PREFIX}ml_lineage_sha256": lineage.sha256(),
    }


def bind_mlflow_run(run: Any, lineage: MLLineageTuple) -> None:
    """Attach the five-tuple to one active MLflow run; fail if tagging is unavailable."""
    tags = mlflow_tags_for_tuple(lineage)
    set_tag = getattr(run, "set_tag", None)
    if callable(set_tag):
        for key, value in tags.items():
            set_tag(key, value)
        return

    import mlflow

    for key, value in tags.items():
        mlflow.set_tag(key, value)
