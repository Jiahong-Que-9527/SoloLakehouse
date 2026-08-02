#!/usr/bin/env python3
"""Generate promotion gate evidence for v2.9 Block B."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

from governance.contracts import load_contracts  # noqa: E402
from governance.promotion import (  # noqa: E402
    PromotionEvidenceManifest,
    PromotionGateResult,
    PromotionStage,
    build_promotion_evidence_record,
    gates_from_service_checks,
    next_promotion_stage,
    resolve_git_commit,
    resolve_promotion_stage,
    resolve_rollback_target_tag,
    resolve_tag_commit,
    validate_promotion_transition,
)
from governance.runtime_health import run_verification_checks  # noqa: E402
from runtime_identity import get_runtime_identity  # noqa: E402


def _contract_gate() -> PromotionGateResult:
    contracts_dir = REPOSITORY_ROOT / "governance" / "datasets"
    try:
        contracts = load_contracts(contracts_dir)
    except (OSError, ValueError) as exc:
        return PromotionGateResult(
            gate_id="governance.contracts",
            description="Validate governed dataset contracts",
            status="fail",
            detail=str(exc),
        )
    return PromotionGateResult(
        gate_id="governance.contracts",
        description="Validate governed dataset contracts",
        status="pass",
        detail=f"Validated {len(contracts)} dataset contract(s)",
    )


def _rollback_tag_gate(tag: str) -> PromotionGateResult:
    try:
        commit = resolve_tag_commit(tag)
    except (OSError, ValueError) as exc:
        return PromotionGateResult(
            gate_id="release.rollback_target",
            description="Resolve rollback target tag to a git commit",
            status="fail",
            detail=str(exc),
        )
    return PromotionGateResult(
        gate_id="release.rollback_target",
        description="Resolve rollback target tag to a git commit",
        status="pass",
        detail=f"{tag} -> {commit}",
    )


def _resolve_target_stage(
    source_stage: PromotionStage,
    requested: PromotionStage | None,
) -> PromotionStage:
    if requested is not None:
        validate_promotion_transition(source_stage, requested)
        return requested
    expected = next_promotion_stage(source_stage)
    if expected is None:
        raise ValueError(f"Stage {source_stage!r} has no forward promotion target")
    return expected


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--target-stage",
        choices=("staging", "production"),
        help="Promotion target stage (default: next stage after current PROMOTION_STAGE).",
    )
    args = parser.parse_args()

    identity = get_runtime_identity()
    source_stage = resolve_promotion_stage()
    try:
        target_stage = _resolve_target_stage(source_stage, args.target_stage)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    service_results, missing_env = run_verification_checks()
    gates = list(gates_from_service_checks(service_results))
    gates.append(_contract_gate())
    rollback_tag = resolve_rollback_target_tag()
    gates.append(_rollback_tag_gate(rollback_tag))
    if missing_env:
        gates.append(
            PromotionGateResult(
                gate_id="runtime.required_env",
                description="Required runtime environment variables are present",
                status="fail",
                detail=f"Missing: {', '.join(missing_env)}",
            )
        )

    try:
        record = build_promotion_evidence_record(
            product_id=identity.product_id,
            runtime_version=identity.runtime_version,
            environment=identity.environment,
            source_stage=source_stage,
            target_stage=target_stage,
            git_commit=resolve_git_commit(),
            rollback_target_tag=rollback_tag,
            gates=tuple(gates),
        )
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    manifest = PromotionEvidenceManifest.from_record(record)
    sys.stdout.write(json.dumps(manifest.model_dump(mode="json"), sort_keys=True, indent=2))
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
