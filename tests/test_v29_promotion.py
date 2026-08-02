"""Tests for v2.9 Block B promotion and rollback evidence."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from governance.promotion import (
    PromotionEvidenceManifest,
    PromotionGateResult,
    RollbackDrillManifest,
    RollbackDrillRecord,
    build_promotion_evidence_record,
    default_rollback_commands,
    gates_from_service_checks,
    resolve_promotion_stage,
    validate_promotion_transition,
)


def test_resolve_promotion_stage_defaults_local_to_dev() -> None:
    assert resolve_promotion_stage({"ENVIRONMENT": "local"}) == "dev"


def test_validate_promotion_transition_enforces_chain() -> None:
    validate_promotion_transition("dev", "staging")
    with pytest.raises(ValueError, match="Invalid promotion transition"):
        validate_promotion_transition("dev", "production")


def test_build_promotion_evidence_record_fails_on_failed_gate() -> None:
    gates = (
        PromotionGateResult(
            gate_id="runtime.trino",
            description="Runtime health check for Trino",
            status="fail",
            detail="HTTP 500",
        ),
    )
    with pytest.raises(ValueError, match="Promotion gates failed"):
        build_promotion_evidence_record(
            product_id="sololakehouse",
            runtime_version="slh-v2.6.1",
            environment="local",
            source_stage="dev",
            target_stage="staging",
            git_commit="a" * 40,
            rollback_target_tag="v2.6.1",
            gates=gates,
        )


def test_promotion_manifest_binds_record_digest() -> None:
    gates = (
        PromotionGateResult(
            gate_id="runtime.trino",
            description="Runtime health check for Trino",
            status="pass",
            detail="HTTP 200",
        ),
    )
    record = build_promotion_evidence_record(
        product_id="sololakehouse",
        runtime_version="slh-v2.6.1",
        environment="local",
        source_stage="dev",
        target_stage="staging",
        git_commit="b" * 40,
        rollback_target_tag="v2.6.1",
        gates=gates,
        generated_at=datetime(2026, 8, 2, 12, 0, tzinfo=UTC),
    )
    manifest = PromotionEvidenceManifest.from_record(record)
    assert manifest.record_sha256 == record.sha256()


def test_gates_from_service_checks_maps_pass_fail() -> None:
    gates = gates_from_service_checks([("Trino", "PASS", "ok"), ("MLflow", "FAIL", "down")])
    assert gates[0].status == "pass"
    assert gates[1].status == "fail"


def test_rollback_drill_manifest_binds_record_digest() -> None:
    record = RollbackDrillRecord(
        product_id="sololakehouse",
        runtime_version="slh-v2.6.1",
        environment="local",
        current_git_commit="c" * 40,
        rollback_target_tag="v2.6.1",
        rollback_target_commit="d" * 40,
        runtime_checks_passed=True,
        gates=(
            PromotionGateResult(
                gate_id="runtime.trino",
                description="Runtime health check for Trino",
                status="pass",
                detail="HTTP 200",
            ),
        ),
        rollback_commands=default_rollback_commands("v2.6.1"),
        generated_at=datetime(2026, 8, 2, 12, 0, tzinfo=UTC),
    )
    manifest = RollbackDrillManifest.from_record(record)
    assert manifest.record_sha256 == record.sha256()
