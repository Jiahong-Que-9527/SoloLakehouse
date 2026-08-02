#!/usr/bin/env python3
"""Generate secrets discipline evidence for v2.9 Block D."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

from governance.secrets_discipline import (  # noqa: E402
    SecretsDisciplineManifest,
    build_secrets_discipline_record,
)
from runtime_identity import get_runtime_identity  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--allow-warn",
        action="store_true",
        help="Emit evidence even when warn-level checks are present.",
    )
    args = parser.parse_args()

    identity = get_runtime_identity()
    try:
        record = build_secrets_discipline_record(
            product_id=identity.product_id,
            runtime_version=identity.runtime_version,
            environment=identity.environment,
            repository_root=REPOSITORY_ROOT,
        )
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    if not args.allow_warn:
        warnings = [check.check_id for check in record.checks if check.status == "warn"]
        if warnings:
            print(
                "Secrets discipline warnings present: "
                + ", ".join(warnings),
                file=sys.stderr,
            )
            return 1

    manifest = SecretsDisciplineManifest.from_record(record)
    sys.stdout.write(json.dumps(manifest.model_dump(mode="json"), sort_keys=True, indent=2))
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
