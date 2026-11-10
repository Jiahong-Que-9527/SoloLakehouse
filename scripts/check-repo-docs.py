# [房玄龄·2026-11-10] Validate active documentation, immutable archives and retained-task coverage.
from __future__ import annotations

import hashlib
import html
import json
import re
import subprocess
import sys
from pathlib import Path
from urllib.parse import unquote, urlsplit

ROOT = Path(__file__).resolve().parents[1]
ACTIVE_FILES = (
    "README.md", "AGENTS.md", "CLAUDE.md", "TASKS.md", "CONTRIBUTING.md",
    "docs/README.md", "docs/roadmap.md", "docs/ONBOARDING_READING_ORDER.md",
    "docs/agent-prompts.md", "docs/decisions/ADR-024-v3-gitops-monorepo.md",
    "task.md", "docs/v3-spec.md", "docs/governance-v3-matrix.md",
    "docs/governance-v3-runbook.md", "docs/v3-governance-navigation.md",
    "docs/architecture-review-2026-08-11.md", "docs/history/pre-v3/README.md",
)
ACTIVE_TREES = ("docs/design/v3", "infra", "bootstrap", "deploy", "gitops")
MARKDOWN_LINK = re.compile(r"!?\[[^\]]*\]\(([^)\n]+)\)")
HTML_LINK = re.compile(r"""(?:href|src)\s*=\s*["']([^"']+)["']""", re.IGNORECASE)


def visible_markdown(text: str) -> str:
    lines: list[str] = []
    fence = ""
    for line in text.splitlines():
        stripped = line.lstrip()
        marker = chr(96) * 3 if stripped.startswith(chr(96) * 3) else "~~~"
        if stripped.startswith((chr(96) * 3, "~~~")):
            if not fence:
                fence = marker
            elif marker == fence:
                fence = ""
            continue
        if not fence:
            lines.append(line)
    return "\n".join(lines)


def heading_slugs(text: str) -> set[str]:
    slugs: set[str] = set()
    counts: dict[str, int] = {}
    for line in visible_markdown(text).splitlines():
        match = re.match(r"^#{1,6}\s+(.+?)\s*#*$", line)
        if not match:
            continue
        title = html.unescape(re.sub(r"<[^>]+>", "", match.group(1)))
        title = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", title)
        title = title.replace(chr(96), "").replace("*", "").lower()
        slug = re.sub(r"[^\w\- ]", "", title).replace(" ", "-")
        count = counts.get(slug, 0)
        counts[slug] = count + 1
        slugs.add(f"{slug}-{count}" if count else slug)
    return slugs


def links_in(text: str) -> list[str]:
    visible = visible_markdown(text)
    return MARKDOWN_LINK.findall(visible) + HTML_LINK.findall(visible)


def published_paths() -> set[str]:
    result = subprocess.run(
        ["git", "ls-files", "--cached", "--others", "--exclude-standard"],
        cwd=ROOT, capture_output=True, text=True, check=True,
    )
    return set(result.stdout.splitlines())


def check_links() -> tuple[list[str], int]:
    paths = {ROOT / rel for rel in ACTIVE_FILES}
    for tree in ACTIVE_TREES:
        paths.update((ROOT / tree).rglob("*.md"))
    errors: list[str] = []
    published = published_paths()
    checked = 0
    for source in sorted(paths):
        if not source.is_file():
            errors.append(f"Missing active document: {source.relative_to(ROOT)}")
            continue
        for raw in links_in(source.read_text(encoding="utf-8")):
            target = raw.strip().strip("<>")
            parsed = urlsplit(target)
            if parsed.scheme or target.startswith("//"):
                continue
            dest = (source.parent / unquote(parsed.path)).resolve() if parsed.path else source
            if not dest.is_relative_to(ROOT):
                errors.append(f"{source.relative_to(ROOT)}: target leaves repository: {target}")
                continue
            if not dest.exists():
                errors.append(f"{source.relative_to(ROOT)}: missing target: {target}")
                continue
            relative = dest.relative_to(ROOT).as_posix()
            if dest.is_file() and relative not in published:
                errors.append(f"{source.relative_to(ROOT)}: unpublished local target: {target}")
            if parsed.fragment and dest.is_file() and dest.suffix == ".md":
                anchors = heading_slugs(dest.read_text(encoding="utf-8"))
                if unquote(parsed.fragment) not in anchors:
                    errors.append(f"{source.relative_to(ROOT)}: missing anchor: {target}")
            checked += 1
    return errors, checked


def check_archive() -> tuple[list[str], int]:
    manifest = json.loads((ROOT / "docs/history/pre-v3/manifest.json").read_text(encoding="utf-8"))
    errors: list[str] = []
    for entry in manifest["files"]:
        path = (ROOT / entry["archive_path"]).resolve()
        if not path.is_relative_to(ROOT / "docs/history/pre-v3") or not path.is_file():
            errors.append(f"Missing/out-of-scope archive: {entry['archive_path']}")
        elif hashlib.sha256(path.read_bytes()).hexdigest() != entry["sha256"]:
            errors.append(f"Archived original changed: {entry['archive_path']}")
    return errors, len(manifest["files"])


def check_retained_work() -> tuple[list[str], int]:
    ledger = json.loads((ROOT / "docs/design/v3/retained-work.json").read_text(encoding="utf-8"))
    source = (ROOT / ledger["source_snapshot"]).read_text(encoding="utf-8").splitlines()
    expected = {n: line for n, line in enumerate(source, 1) if re.match(r"^\s*-\s+\[ \]", line)}
    items = ledger["items"]
    actual = {entry["source_line"]: entry["original_first_line"] for entry in items}
    errors = []
    if actual != expected or len(actual) != len(items):
        errors.append(
            "Retained-work ledger does not cover every original unchecked item exactly once."
        )
    if any(not item["classification"].strip() for item in items):
        errors.append("Retained-work item lacks an explicit classification.")
    return errors, len(items)


def main() -> int:
    errors, count = check_links()
    archived, archive_count = check_archive()
    retained, retained_count = check_retained_work()
    errors.extend(archived + retained)
    if errors:
        print("\n".join(errors), file=sys.stderr)
        return 1
    print(f"Active docs OK: {count} local links; {archive_count} unchanged originals; "
          f"{retained_count} prior unchecked items accounted for.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
