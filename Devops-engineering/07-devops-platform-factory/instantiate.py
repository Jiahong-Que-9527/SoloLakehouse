#!/usr/bin/env python3
"""Instantiate the D07 service template into a new service directory.

Usage: python3 instantiate.py <replacements.json> <target-service-dir>

Layout mapping:
  template/service/**            -> <target>/**            (service skeleton at the root)
  template/chart/**              -> <target>/chart/**       (delivery chart inside the service)
  template/workflow.yml          -> .github/workflows/<WORKFLOW_FILE>  (repo-level)
  template/ONBOARDING.md         -> not copied; it documents the template itself
"""

import json
import sys
from pathlib import Path

TEMPLATE = Path(__file__).resolve().parent / "template"


def main() -> int:
    replacements = json.loads(Path(sys.argv[1]).read_text())
    target = Path(sys.argv[2]).resolve()
    repo_root = target.parent.parent

    def fill(text: str) -> str:
        for key, value in replacements.items():
            text = text.replace(f"__{key}__", value)
        return text

    copied = 0
    for path in TEMPLATE.rglob("*"):
        if path.is_dir():
            continue
        relative = path.relative_to(TEMPLATE)
        parts = relative.parts
        if parts[0] == "service":
            destination = target / Path(*parts[1:])
        elif parts[0] == "chart":
            destination = target / "chart" / Path(*parts[1:])
        elif relative == Path("workflow.yml"):
            destination = (
                repo_root / ".github/workflows" / replacements["WORKFLOW_FILE"]
            )
        else:
            continue
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(fill(path.read_text()))
        copied += 1
    print(f"instantiated {copied} files into {target}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
