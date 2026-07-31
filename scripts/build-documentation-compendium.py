#!/usr/bin/env python3
"""Assemble all project documentation into a single markdown compendium."""

from __future__ import annotations

import re
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "docs" / "DOCUMENTATION_COMPENDIUM.md"

# Ordered sections: (title, relative paths from repo root)
SECTIONS: list[tuple[str, list[str]]] = [
    (
        "1. Getting Started and Project Overview",
        [
            "README.md",
            "docs/README.md",
            "docs/ONBOARDING_READING_ORDER.md",
            "CLAUDE.md",
            "AGENTS.md",
            "docs/roadmap.md",
            "docs/ASSESSMENT_LAKEHOUSE_DAX_ECB.md",
            "CHANGELOG.md",
        ],
    ),
    (
        "2. Quickstart and Deployment",
        [
            "docs/quickstart.md",
            "DEMO.md",
            "docs/make-demo-guide.md",
            "docs/DEMO_RUNBOOK_EN.md",
            "RUNBOOK.md",
            "docs/deployment.md",
            "docs/finlakehouse-deployment-guide.md",
        ],
    ),
    (
        "3. User Guides and Dagster",
        [
            "docs/DAGSTER_GUIDE.md",
            "docs/USER_GUIDE_EN.md",
        ],
    ),
    (
        "4. Architecture and Data Model",
        [
            "docs/architecture.md",
            "docs/medallion-model.md",
            "docs/fin-ecb-dax-features-data-contract.md",
            "docs/entity-template-readiness.md",
            "docs/product-entity-contract.md",
            "docs/dataset-governance-naming.md",
            "docs/object-store-abstraction.md",
            "docs/runtime-state-layout.md",
            "docs/entity-backup-restore-runbook.md",
            "docs/restore-drills/TEMPLATE-iceberg-restore-drill.md",
            "docs/restore-drills/2026-05-17-entity-template-restore-drill.md",
            "docker/openmetadata/README.md",
            "docs/img/README.md",
        ],
    ),
    (
        "5. Architecture Decision Records (ADR)",
        [
            "docs/decisions/README.md",
            "docs/decisions/ADR-001-docker-compose.md",
            "docs/decisions/ADR-002-trino-vs-duckdb.md",
            "docs/decisions/ADR-003-parquet-vs-delta.md",
            "docs/decisions/ADR-004-financial-dataset.md",
            "docs/decisions/ADR-005-v1-scope.md",
            "docs/decisions/ADR-006-v2-dagster-orchestration.md",
            "docs/decisions/ADR-007-v3-k8s-helm-terraform.md",
            "docs/decisions/ADR-008-v3-environment-promotion.md",
            "docs/decisions/ADR-009-v3-secrets-and-access-governance.md",
            "docs/decisions/ADR-010-v3-observability-and-slo.md",
            "docs/decisions/ADR-011-v3-ml-productization-boundary.md",
            "docs/decisions/ADR-012-v3-data-governance-catalog-strategy.md",
            "docs/decisions/ADR-013-iceberg-gold-trino.md",
            "docs/decisions/ADR-014-openmetadata-optional-profile.md",
            "docs/decisions/ADR-015-v3-observability-tooling.md",
            "docs/decisions/ADR-016-compute-engine-migration.md",
            "docs/decisions/ADR-017-iceberg-rest-catalog-option.md",
            "docs/decisions/ADR-018-ml-lineage-five-tuple.md",
            "docs/decisions/ADR-019-minio-seaweedfs-deferral.md",
            "docs/decisions/ADR-020-iceberg-all-layers.md",
        ],
    ),
    (
        "6. Compliance and Governance",
        [
            "docs/compliance/README.md",
            "docs/compliance/dora.md",
            "docs/compliance/bafin-bait.md",
            "docs/compliance/mifid-ii.md",
            "docs/v3-governance-navigation.md",
            "docs/governance-v3-matrix.md",
            "docs/governance-v3-runbook.md",
            "docs/v3-spec.md",
        ],
    ),
    (
        "7. Tasks, Backlog, and Planning",
        [
            "TASKS.md",
            "task.md",
            "docs/project-state-overview-2026-05-05.md",
        ],
    ),
    (
        "8. Version History and Evolution",
        [
            "docs/history/README.md",
            "docs/history/timeline.md",
            "docs/history/architecture-evolution.md",
            "docs/history/legacy-overview.md",
            "docs/history/planning-template.md",
            "docs/history/v2-planning.md",
            "docs/history/v2.5-planning.md",
            "docs/history/v3-planning.md",
        ],
    ),
    (
        "9. Release, Quality, and Contributing",
        [
            "docs/v2.5-acceptance-criteria.md",
            "docs/contributing.md",
            "CONTRIBUTING.md",
            "docs/git-workflow.md",
            "docs/agent-prompts.md",
            ".github/RELEASE_NOTES_v2.5.0.md",
        ],
    ),
]

EXCLUDE_DIR_NAMES = {
    "graphify-out",
    ".agents",
    ".git",
    "docker/data",
    "node_modules",
    "__pycache__",
    ".pytest_cache",
    ".venv",
    ".cursor",
    "site-packages",
}


def slug(text: str) -> str:
    text = text.lower()
    text = re.sub(r"[^\w\s/-]", "", text)
    text = re.sub(r"[/\\]+", "-", text)
    text = re.sub(r"[\s_]+", "-", text.strip())
    text = re.sub(r"-+", "-", text).strip("-")
    return text or "section"


def should_include(rel: str) -> bool:
    parts = Path(rel).parts
    if any(part in EXCLUDE_DIR_NAMES for part in parts):
        return False
    if rel.startswith(".github/ISSUE_TEMPLATE/"):
        return False
    if rel in {".github/pull_request_template.md"}:
        return False
    if rel == OUTPUT.relative_to(ROOT).as_posix():
        return False
    return True


def read_file(rel_path: str) -> str | None:
    path = ROOT / rel_path
    if not path.is_file():
        return None
    return path.read_text(encoding="utf-8").rstrip() + "\n"


def collect_remaining_paths(listed: set[str]) -> list[str]:
    remaining: list[str] = []
    for path in sorted(ROOT.rglob("*.md")):
        rel = path.relative_to(ROOT).as_posix()
        if rel in listed or not should_include(rel):
            continue
        remaining.append(rel)
    return remaining


def main() -> None:
    listed: set[str] = set()
    for _, paths in SECTIONS:
        listed.update(paths)

    appendix = collect_remaining_paths(listed)

    lines: list[str] = [
        "# SoloLakehouse Documentation Compendium",
        "",
        f"> Generated automatically on {date.today().isoformat()}."
        f" It aggregates every Markdown document in the repository for offline reading."
        f" Each section keeps its original source path; to change content, edit the"
        f" source file and re-run "
        f"`python scripts/build-documentation-compendium.py`。",
        "",
        "## Table of Contents",
        "",
    ]

    section_anchors: list[tuple[str, str]] = []
    doc_entries: list[tuple[str, str, str]] = []  # section, rel_path, anchor

    for section_title, paths in SECTIONS:
        sec_anchor = slug(section_title)
        section_anchors.append((section_title, sec_anchor))
        lines.append(f"- [{section_title}](#{sec_anchor})")
        for rel in paths:
            doc_anchor = slug(rel)
            doc_entries.append((section_title, rel, doc_anchor))
            status = "\u2713" if read_file(rel) else "(missing)"
            lines.append(f"  - [{rel}](#{doc_anchor}) {status}")

    if appendix:
        lines.append("- [Appendix: Other Documents](#appendix-other-docs)")
        for rel in appendix:
            doc_anchor = slug(rel)
            doc_entries.append(("Appendix: Other Documents", rel, doc_anchor))
            lines.append(f"  - [{rel}](#{doc_anchor})")

    lines.extend(["", "---", ""])

    current_section = ""
    for section_title, rel, doc_anchor in doc_entries:
        if section_title != current_section:
            current_section = section_title
            if section_title == "Appendix: Other Documents":
                sec_anchor = "appendix-other-docs"
            else:
                sec_anchor = slug(section_title)
            lines.extend(
                [
                    f"## {section_title} {{#{sec_anchor}}}",
                    "",
                ]
            )

        content = read_file(rel)
        lines.extend(
            [
                f"### `{rel}` {{#{doc_anchor}}}",
                "",
            ]
        )
        if content is None:
            lines.extend(["*(source file not found, skipped)*", "", "---", ""])
            continue
        lines.append(content)
        if not content.endswith("\n\n"):
            lines.append("")
        lines.extend(["---", ""])

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text("\n".join(lines), encoding="utf-8")

    line_count = len(lines)
    included = sum(1 for _, rel, _ in doc_entries if read_file(rel) is not None)
    missing = len(doc_entries) - included
    print(f"Wrote {OUTPUT}")
    print(f"Sections: {len(SECTIONS)}, documents: {included} included, {missing} missing")
    print(f"Output lines: {line_count}")


if __name__ == "__main__":
    main()
