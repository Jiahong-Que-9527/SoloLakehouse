#!/usr/bin/env python3
"""Record rollback drill evidence for v2.9 Block B."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

from governance.contracts import load_contracts  # noqa: E402
from governance.promotion import (  # noqa: E402
    PromotionGateResult,
    RollbackDrillManifest,
    RollbackDrillRecord,
    default_rollback_commands,
    gates_from_service_checks,
    resolve_git_commit,
    resolve_rollback_target_tag,
    resolve_tag_commit,
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


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--allow-unhealthy-runtime",
        action="store_true",
        help="Record drill output even when runtime checks fail (does not claim readiness).",
    )
    args = parser.parse_args()

    identity = get_runtime_identity()
    service_results, missing_env = run_verification_checks()
    rollback_tag = resolve_rollback_target_tag()
    rollback_commit = resolve_tag_commit(rollback_tag)
    current_commit = resolve_git_commit()

    gates = list(gates_from_service_checks(service_results))
    gates.append(_contract_gate())
    if missing_env:
        gates.append(
            PromotionGateResult(
                gate_id="runtime.required_env",
                description="Required runtime environment variables are present",
                status="fail",
                detail=f"Missing: {', '.join(missing_env)}",
            )
        )

    runtime_checks_passed = all(gate.status == "pass" for gate in gates)
    if not runtime_checks_passed and not args.allow_unhealthy_runtime:
        failing = ", ".join(gate.gate_id for gate in gates if gate.status != "pass")
        print(f"Rollback drill blocked: failing gates: {failing}", file=sys.stderr)
        return 1

    record = RollbackDrillRecord(
        product_id=identity.product_id,
        runtime_version=identity.runtime_version,
        environment=identity.environment,
        current_git_commit=current_commit,
        rollback_target_tag=rollback_tag,
        rollback_target_commit=rollback_commit,
        runtime_checks_passed=runtime_checks_passed,
        gates=tuple(gates),
        rollback_commands=default_rollback_commands(rollback_tag),
        generated_at=datetime.now(tz=UTC),
    )
    manifest = RollbackDrillManifest.from_record(record)
    sys.stdout.write(json.dumps(manifest.model_dump(mode="json"), sort_keys=True, indent=2))
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
