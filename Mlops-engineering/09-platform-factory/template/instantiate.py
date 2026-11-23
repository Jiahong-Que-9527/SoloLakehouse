"""Instantiate the ML delivery template into a new workload directory.

Mirrors the D07 platform-factory pattern: the template carries delivery
assets only; domain contracts stay with each workload. Placeholders are
substituted in file contents and in paths.

Usage:
    python instantiate.py --target ../district-forecast \
        --package district_forecast --workload-id district-forecast \
        --entity district --entity-plural districts

Placeholders (in file bodies and paths):
    {{package}}        Python package name (snake_case)
    {{workload_id}}    kebab-case workload identifier
    {{entity}}         singular entity label used by the fold harness
    {{entity_plural}}  plural entity label
"""

from __future__ import annotations

import argparse
from pathlib import Path

TEMPLATE_DIR = Path(__file__).resolve().parent / "scaffold"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--target", type=Path, required=True, help="New workload directory")
    parser.add_argument("--package", required=True, help="Python package name, snake_case")
    parser.add_argument("--workload-id", required=True, help="kebab-case workload identifier")
    parser.add_argument("--entity", required=True, help="singular entity label")
    parser.add_argument("--entity-plural", required=True, help="plural entity label")
    args = parser.parse_args()

    target = args.target.resolve()
    if target.exists() and any(target.iterdir()):
        raise SystemExit(f"target must be empty or new: {target}")
    values = {
        "{{package}}": args.package,
        "{{workload_id}}": args.workload_id,
        "{{entity}}": args.entity,
        "{{entity_plural}}": args.entity_plural,
    }

    copied = 0
    for path in sorted(TEMPLATE_DIR.rglob("*")):
        relative = path.relative_to(TEMPLATE_DIR)
        rendered_name = relative.as_posix()
        for placeholder, value in values.items():
            rendered_name = rendered_name.replace(placeholder, value)
        if rendered_name.endswith(".tmpl"):
            rendered_name = rendered_name[: -len(".tmpl")]
        out = target / rendered_name
        if path.is_dir():
            out.mkdir(parents=True, exist_ok=True)
            continue
        out.parent.mkdir(parents=True, exist_ok=True)
        text = path.read_text(encoding="utf-8")
        for placeholder, value in values.items():
            text = text.replace(placeholder, value)
        out.write_text(text, encoding="utf-8")
        copied += 1
    print(f"instantiated {args.workload_id}: {copied} files -> {target}")
    print("next: follow template/ONBOARDING.md")


if __name__ == "__main__":
    main()
