"""Resolve the backend location and Terraform working data for one stack."""

import argparse
import json
import re
from pathlib import Path


def stack_paths(stack, state_root):
    team, environment = stack["team"], stack["environment"]
    if not re.fullmatch(r"[a-z][a-z0-9-]{0,22}", team):
        raise ValueError("Invalid D06 team slug")
    if environment not in {"dev", "prod"}:
        raise ValueError("Invalid D06 environment")
    stack_id = f"slh-{team}-{environment}"
    directory = state_root.expanduser().resolve() / stack_id
    return {
        "stack_id": stack_id,
        "state": str(directory / "terraform.tfstate"),
        "data_dir": str(directory / ".terraform"),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("stack_file", type=Path)
    parser.add_argument("--state-root", required=True, type=Path)
    args = parser.parse_args()
    stack = json.loads(args.stack_file.read_text())["stack"]
    print(json.dumps(stack_paths(stack, args.state_root)))


if __name__ == "__main__":
    main()
