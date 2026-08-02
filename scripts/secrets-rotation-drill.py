#!/usr/bin/env python3
"""Record a manual secrets rotation drill for v2.9 Block D."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

from governance.secrets_discipline import (  # noqa: E402
    SecretsRotationDrillManifest,
    SecretsRotationDrillRecord,
)
from runtime_identity import get_runtime_identity  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--keys",
        required=True,
        help="Comma-separated secret keys rotated in the drill.",
    )
    parser.add_argument(
        "--verification-command",
        default="make verify",
        help="Command used to verify the platform after rotation.",
    )
    parser.add_argument(
        "--notes",
        default="",
        help="Optional operator notes for the drill record.",
    )
    args = parser.parse_args()

    rotated_keys = tuple(key.strip() for key in args.keys.split(",") if key.strip())
    if not rotated_keys:
        print("At least one rotated key is required.", file=sys.stderr)
        return 1

    identity = get_runtime_identity()
    record = SecretsRotationDrillRecord(
        product_id=identity.product_id,
        runtime_version=identity.runtime_version,
        environment=identity.environment,
        rotated_keys=rotated_keys,
        verification_command=args.verification_command,
        notes=args.notes,
        generated_at=datetime.now(tz=UTC),
    )
    manifest = SecretsRotationDrillManifest.from_record(record)
    sys.stdout.write(json.dumps(manifest.model_dump(mode="json"), sort_keys=True, indent=2))
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
