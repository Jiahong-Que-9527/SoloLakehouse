"""Select project directories affected by a GitHub push or pull request."""

from __future__ import annotations

import json
import os
import re
import subprocess
from pathlib import Path

PLATFORMS = ("gcp", "databricks", "local")
PROJECT_NAME = re.compile(r"[a-z0-9][a-z0-9-]*")


def git(*args: str) -> bytes:
    return subprocess.check_output(["git", *args], stderr=subprocess.DEVNULL)


def changed_paths(event: str, payload: dict) -> list[str]:
    if event == "pull_request":
        pull_request = payload["pull_request"]
        base = pull_request["base"]["sha"]
        head = pull_request["head"]["sha"]
        compare_to_ancestor = True
    elif event == "push":
        base = payload["before"]
        head = payload["after"]
        compare_to_ancestor = base == "0" * 40
        if compare_to_ancestor:
            default = payload["repository"]["default_branch"]
            base = git("rev-parse", "--verify", f"refs/remotes/origin/{default}").decode().strip()
    else:
        raise ValueError(f"Unsupported event: {event}")

    if any(not re.fullmatch(r"[0-9a-f]{40}", commit) for commit in (base, head)):
        raise ValueError("Invalid commit ID")
    if compare_to_ancestor:
        ancestors = git("merge-base", "--all", base, head).decode().splitlines()
        if len(ancestors) != 1:
            raise ValueError("No unique merge base")
        base = ancestors[0]

    # A rename is reported as deletion and addition, including both project paths.
    diff = git("diff", "--name-only", "--no-renames", "-z", base, head, "--")
    return [os.fsdecode(path) for path in diff.split(b"\0") if path]


def project_paths() -> set[str]:
    return {
        path.as_posix()
        for platform in PLATFORMS
        if not Path(platform).is_symlink()
        for path in Path(platform).glob("*")
        if path.is_dir() and not path.is_symlink() and PROJECT_NAME.fullmatch(path.name)
    }


def select(paths: list[str], projects: set[str]) -> list[str]:
    if any(path.startswith((".github/workflows/", ".github/scripts/")) for path in paths):
        return sorted(projects)
    changed = {"/".join(path.split("/")[:2]) for path in paths}
    return sorted(changed & projects)


def main() -> None:
    projects = project_paths()
    try:
        event = os.environ["GITHUB_EVENT_NAME"]
        payload = json.loads(Path(os.environ["GITHUB_EVENT_PATH"]).read_text(encoding="utf-8"))
        selected = select(changed_paths(event, payload), projects)
    except (KeyError, OSError, ValueError, subprocess.CalledProcessError):
        print("Could not resolve the change range. Checking every project.")
        selected = sorted(projects)

    print(f"Selected projects: {json.dumps(selected)}")
    with Path(os.environ["GITHUB_OUTPUT"]).open("a", encoding="utf-8") as output:
        print(f"projects={json.dumps(selected)}", file=output)


if __name__ == "__main__":
    main()
