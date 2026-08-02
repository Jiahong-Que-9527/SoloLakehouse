#!/usr/bin/env python3
"""Generate SLO and incident-readiness evidence for v2.9 Block C."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

from governance.operations import (  # noqa: E402
    DEFAULT_INCIDENT_RUNBOOKS,
    OperationalEvidenceManifest,
    OperationalEvidenceRecord,
    build_operational_evidence_record,
    evaluate_service_slos,
)
from governance.runtime_health import run_verification_checks  # noqa: E402
from runtime_identity import get_runtime_identity  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--allow-slo-failure",
        action="store_true",
        help="Emit evidence JSON even when one or more SLOs fail.",
    )
    args = parser.parse_args()

    identity = get_runtime_identity()
    service_results, missing_env = run_verification_checks()
    if missing_env:
        print(f"Missing required env vars: {', '.join(missing_env)}", file=sys.stderr)
        return 1

    slo_results = evaluate_service_slos(service_results)
    try:
        record = build_operational_evidence_record(
            product_id=identity.product_id,
            runtime_version=identity.runtime_version,
            environment=identity.environment,
            slo_results=slo_results,
        )
    except ValueError as exc:
        if not args.allow_slo_failure:
            print(str(exc), file=sys.stderr)
            return 1
        record = OperationalEvidenceRecord(
            product_id=identity.product_id,
            runtime_version=identity.runtime_version,
            environment=identity.environment,
            slo_results=slo_results,
            runbooks=DEFAULT_INCIDENT_RUNBOOKS,
            generated_at=datetime.now(tz=UTC),
        )

    manifest = OperationalEvidenceManifest.from_record(record)
    sys.stdout.write(json.dumps(manifest.model_dump(mode="json"), sort_keys=True, indent=2))
    sys.stdout.write("\n")
    return 0 if all(result.status == "pass" for result in slo_results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
