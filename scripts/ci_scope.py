"""Select CI jobs from the full Git change range supplied by GitHub Actions."""
from __future__ import annotations

import json
import os
import re
import subprocess
from pathlib import Path

FINANCE_PATHS = (
    "projects/finance/",
    "ingestion/",
    "transformations/",
    "dagster/",
    "ml/",
    "governance/datasets/fin.",
)
AVIATION_DIR = "projects/aviation/"
AVIATION_CASE = "docs/workloads/aviation.md"
DOC_PATHS = ("docs/", "projects/")
DOC_FILES = {
    "AGENTS.md", "CHANGELOG.md", "CLAUDE.md", "CONTRIBUTING.md",
    "DEMO.md", "GEMINI.md", "README.md", "RUNBOOK.md", "TASKS.md", "task.md",
}


def git(*args: str) -> bytes:
    return subprocess.check_output(["git", *args], stderr=subprocess.DEVNULL)


def changes(event: str, payload: dict) -> list[tuple[str, str]]:
    if event == "pull_request":
        pr = payload["pull_request"]
        head = pr["head"]["sha"]
        base = pr["base"]["sha"]
        use_merge_base = True
    elif event == "push":
        head = payload["after"]
        base = payload["before"]
        use_merge_base = not base.strip("0")
        if use_merge_base:
            default = payload["repository"]["default_branch"]
            base = git("rev-parse", "--verify", f"refs/remotes/origin/{default}").decode().strip()
            if base == head:
                raise ValueError("new default branch has no previous revision")
    else:
        raise ValueError(f"unsupported event: {event}")

    if any(not re.fullmatch(r"[0-9a-f]{40}", sha) for sha in (base, head)):
        raise ValueError("missing or invalid commit")
    if use_merge_base:
        bases = git("merge-base", "--all", base, head).decode().splitlines()
        if len(bases) != 1:
            raise ValueError("ambiguous merge base")
        base = bases[0]

    # Treat renames as deletions and additions, so both paths are classified.
    fields = git("diff", "--no-renames", "--name-status", "-z", base, head, "--").split(b"\0")
    return [
        (status.decode(), os.fsdecode(path))
        for status, path in zip(fields[:-1:2], fields[1:-1:2], strict=True)
    ]


def select(changed: list[tuple[str, str]]) -> tuple[bool, str]:
    finance = False
    docs = False
    aviation = False
    for status, path in changed:
        if path.endswith(".md") and (
            path in DOC_FILES or path.startswith(DOC_PATHS)
        ):
            if path == AVIATION_CASE or path.startswith(AVIATION_DIR):
                aviation = True
            else:
                docs = True
        elif path.startswith(FINANCE_PATHS):
            finance = True
        else:
            # Shared and unclassified paths retain the complete CI coverage.
            return True, "repository"

        # A deleted or renamed path can leave documentation links dangling.
        docs |= status == "D"

    if docs:
        return finance, "repository"
    return finance, "aviation" if aviation else "none"


def main() -> None:
    event = os.environ["GITHUB_EVENT_NAME"]
    try:
        event_path = Path(os.environ["GITHUB_EVENT_PATH"])
        payload = json.loads(event_path.read_text(encoding="utf-8"))
        finance, docs = select(changes(event, payload))
    except (KeyError, OSError, ValueError, subprocess.CalledProcessError) as error:
        print(f"Could not determine the change scope. Running complete CI: {error}")
        finance, docs = True, "repository"

    print(f"CI scope: finance={finance}, documentation={docs}")
    with Path(os.environ["GITHUB_OUTPUT"]).open("a", encoding="utf-8") as output:
        output.write(f"finance={str(finance).lower()}\ndocs={docs}\n")


if __name__ == "__main__":
    main()
