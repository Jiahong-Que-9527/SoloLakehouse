#!/usr/bin/env python3
"""Merge `.env.shared` and `.env.secrets` into a single `.env` file."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

from governance.env_merge import merge_env_files  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--shared", type=Path, default=Path(".env.shared"))
    parser.add_argument("--secrets", type=Path, default=Path(".env.secrets"))
    parser.add_argument("--output", type=Path, default=Path(".env"))
    args = parser.parse_args()

    for path in (args.shared, args.secrets):
        if not path.exists():
            print(f"Missing required env file: {path}", file=sys.stderr)
            return 1

    args.output.write_text(
        merge_env_files(args.shared, args.secrets),
        encoding="utf-8",
    )
    print(f"Wrote {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
