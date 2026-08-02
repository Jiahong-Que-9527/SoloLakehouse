#!/usr/bin/env python3
"""Generate the v2.7 sovereignty component-origin report."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

from governance.sovereignty import (  # noqa: E402
    build_sovereignty_report,
    render_sovereignty_markdown,
)
from runtime_identity import get_runtime_identity  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--format",
        choices=("markdown", "json"),
        default="markdown",
        help="Output format (default: markdown).",
    )
    args = parser.parse_args()

    identity = get_runtime_identity()
    report = build_sovereignty_report(
        product_id=identity.product_id,
        runtime_version=identity.runtime_version,
        environment=identity.environment,
        repository_root=REPOSITORY_ROOT,
    )
    if args.format == "json":
        sys.stdout.write(json.dumps(report.model_dump(mode="json"), sort_keys=True, indent=2))
    else:
        sys.stdout.write(render_sovereignty_markdown(report))
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
