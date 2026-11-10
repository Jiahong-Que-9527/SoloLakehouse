"""Verify that every agent entry point is present, published, and consistent.

This repository is worked on by several AI coding agents, each of which reads a
different file first:

    Claude Code  -> CLAUDE.md
    Cursor       -> .cursor/rules/*.mdc
    Codex        -> AGENTS.md

They must all land on the same target. `AGENTS.md` is the single shared
contract; the other entry points are pointers to it. This check fails the build
when an entry point goes missing, stops pointing at the contract, or starts
duplicating version state that would then drift.

Run via `make check-agent-docs`.
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

CONTRACT = "AGENTS.md"

# Entry points that must exist, be published, and point at the contract.
ENTRY_POINTS = {
    "CLAUDE.md": "Claude Code",
    ".cursor/rules/sololakehouse.mdc": "Cursor",
    "AGENTS.md": "Codex (and any agent following the AGENTS.md convention)",
}

# The contract must answer each of these, or a cold-starting agent cannot orient.
CONTRACT_REQUIREMENTS = {
    "authority chain": r"docs/roadmap\.md",
    "next-PR authority": r"TASKS\.md",
    "protected runtime baseline": r"v2\.5",
    "decision gates": r"\bD1\b.*\bD2\b|\bD2\b.*\bD3\b|Decision gates",
    "validation commands": r"make validate-contracts",
    "language policy": r"[Ee]nglish[- ]only",
}

# Only the contract may carry a version-status table; pointers must not, or the
# three entry points will drift apart.
VERSION_TABLE = re.compile(r"^\|.*\bv2\.6\.1\b.*\|.*\|", re.MULTILINE)

# Version state also drifts in prose, which the table check above cannot see.
# CLAUDE.md carried a stale "Current version: v2.6 / Next target: v2.6.1" for
# four delivered versions because the claim was a sentence, not a table row.
# Pointers must defer to the contract for status rather than assert it.
VERSION_CLAIMS = "Current version|Next target|Released tag|Active version|Current release"
VERSION_PROSE = re.compile(
    rf"^\W*\**\s*({VERSION_CLAIMS})\s*\**\s*:",
    re.MULTILINE | re.IGNORECASE,
)


def _published_files() -> set[str]:
    result = subprocess.run(
        ["git", "-c", "core.quotepath=false", "ls-files"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    return set(result.stdout.split())


def main() -> int:
    failures: list[str] = []
    published = _published_files()

    for path_str, tool in ENTRY_POINTS.items():
        path = REPO_ROOT / path_str
        if not path.is_file():
            failures.append(f"{path_str} is missing — {tool} has no project entry point")
            continue
        if path_str not in published:
            failures.append(
                f"{path_str} exists but is not published — {tool} sees nothing in a fresh clone"
            )
            continue

        text = path.read_text(encoding="utf-8")
        if path_str != CONTRACT:
            if CONTRACT not in text:
                failures.append(f"{path_str} does not point at {CONTRACT} — {tool} may diverge")
            if VERSION_TABLE.search(text):
                failures.append(
                    f"{path_str} duplicates the version table; keep version state in "
                    f"{CONTRACT} only so the entry points cannot drift"
                )
            prose = VERSION_PROSE.search(text)
            if prose:
                claim = prose.group(1)
                failures.append(
                    f"{path_str} asserts version state in prose ({claim!r}); point at "
                    f"{CONTRACT} instead — a sentence drifts as easily as a table"
                )

    contract_path = REPO_ROOT / CONTRACT
    if contract_path.is_file():
        contract_text = contract_path.read_text(encoding="utf-8")
        for requirement, pattern in CONTRACT_REQUIREMENTS.items():
            if not re.search(pattern, contract_text, re.DOTALL):
                failures.append(f"{CONTRACT} no longer states the {requirement}")

    if failures:
        print("Agent entry-point check FAILED:\n", file=sys.stderr)
        for failure in failures:
            print(f"  - {failure}", file=sys.stderr)
        print(
            f"\nSee the 'Multi-agent conventions' section of {CONTRACT}.",
            file=sys.stderr,
        )
        return 1

    print(f"Agent entry points OK: {', '.join(sorted(ENTRY_POINTS))} all resolve to {CONTRACT}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
