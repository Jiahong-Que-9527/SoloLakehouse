#!/usr/bin/env python3
"""Export the governed agent-ready policy hook catalog as canonical JSON."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

from governance.policy_hooks import build_policy_hook_catalog  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--include-digest",
        action="store_true",
        help="Prefix output with catalog_sha256 while keeping hooks sorted canonically.",
    )
    args = parser.parse_args()

    catalog = build_policy_hook_catalog()
    if args.include_digest:
        payload = {"catalog_sha256": catalog.sha256(), **catalog.model_dump(mode="json")}
        sys.stdout.write(json.dumps(payload, sort_keys=True, separators=(",", ":")))
    else:
        sys.stdout.write(catalog.canonical_json_bytes().decode("utf-8"))
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
