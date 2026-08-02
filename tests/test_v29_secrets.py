"""Tests for v2.9 Block D secrets discipline."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from governance.secrets_discipline import (
    SecretsDisciplineManifest,
    build_secrets_discipline_record,
    evaluate_secrets_discipline,
)


def test_build_secrets_discipline_record_passes_on_repository() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    record = build_secrets_discipline_record(
        product_id="sololakehouse",
        runtime_version="slh-v2.6.1",
        environment="local",
        repository_root=repo_root,
        generated_at=datetime(2026, 8, 2, 12, 0, tzinfo=UTC),
    )
    manifest = SecretsDisciplineManifest.from_record(record)
    assert manifest.record_sha256 == record.sha256()
    assert any(check.check_id == "env.shared_example_present" for check in record.checks)


def test_build_secrets_discipline_record_fails_without_templates(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="Secrets discipline checks failed"):
        build_secrets_discipline_record(
            product_id="sololakehouse",
            runtime_version="slh-v2.6.1",
            environment="local",
            repository_root=tmp_path,
        )


def test_evaluate_secrets_discipline_flags_missing_gitignore_entry(tmp_path: Path) -> None:
    (tmp_path / ".env.shared.example").write_text("PRODUCT_ID=demo\n", encoding="utf-8")
    (tmp_path / ".env.secrets.example").write_text(
        "\n".join(
            [
                "MINIO_ROOT_PASSWORD=x",
                "POSTGRES_PASSWORD=x",
                "S3_SECRET_KEY=x",
                "AWS_SECRET_ACCESS_KEY=x",
                "SUPERSET_SECRET_KEY=x",
                "SUPERSET_ADMIN_PASSWORD=x",
                "OPENMETADATA_AUTH_TOKEN=",
                "ICEBERG_REST_CREDENTIAL=",
            ]
        ),
        encoding="utf-8",
    )
    (tmp_path / ".gitignore").write_text(".env\n", encoding="utf-8")
    record = evaluate_secrets_discipline(
        product_id="sololakehouse",
        runtime_version="slh-v2.6.1",
        environment="local",
        repository_root=tmp_path,
    )
    statuses = {check.check_id: check.status for check in record.checks}
    assert statuses["gitignore.env_secrets"] == "fail"
