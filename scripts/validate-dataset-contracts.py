#!/usr/bin/env python3
"""Validate every SoloLakehouse dataset contract."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

from governance.contracts import load_contracts  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--directory",
        type=Path,
        default=REPOSITORY_ROOT / "governance" / "datasets",
        help="directory containing contract YAML files",
    )
    args = parser.parse_args()
    try:
        contracts = load_contracts(args.directory)
    except (OSError, ValueError) as exc:
        print(f"Contract validation failed: {exc}", file=sys.stderr)
        return 1
    print(f"Validated {len(contracts)} dataset contract(s).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
