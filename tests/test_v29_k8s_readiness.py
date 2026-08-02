"""Tests for v2.9 Block F Kubernetes readiness evidence."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from governance.k8s_readiness import (
    K8sReadinessManifest,
    build_k8s_readiness_record,
    evaluate_k8s_readiness,
)


def test_build_k8s_readiness_record_passes_on_repository() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    record = build_k8s_readiness_record(
        product_id="sololakehouse",
        runtime_version="slh-v2.6.1",
        environment="local",
        repository_root=repo_root,
        generated_at=datetime(2026, 8, 2, 12, 0, tzinfo=UTC),
    )
    manifest = K8sReadinessManifest.from_record(record)
    assert manifest.record_sha256 == record.sha256()
    deferred = [check for check in record.checks if check.status == "deferred"]
    assert deferred


def test_build_k8s_readiness_record_fails_when_promotion_module_missing(tmp_path: Path) -> None:
    (tmp_path / "Makefile").write_text("demo:\n\ttrue\n", encoding="utf-8")
    (tmp_path / "docker").mkdir()
    (tmp_path / "docker" / "docker-compose.yml").write_text("services: {}\n", encoding="utf-8")
    with pytest.raises(ValueError, match="K8s readiness checks missing"):
        build_k8s_readiness_record(
            product_id="sololakehouse",
            runtime_version="slh-v2.6.1",
            environment="local",
            repository_root=tmp_path,
        )


def test_evaluate_k8s_readiness_marks_helm_as_deferred() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    record = evaluate_k8s_readiness(
        product_id="sololakehouse",
        runtime_version="slh-v2.6.1",
        environment="local",
        repository_root=repo_root,
    )
    helm = next(check for check in record.checks if check.check_id == "infra.helm_charts")
    assert helm.status == "deferred"
