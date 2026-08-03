from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType

import pytest


def _load_check_module() -> ModuleType:
    path = Path(__file__).resolve().parents[1] / "scripts" / "check-agent-docs.py"
    spec = importlib.util.spec_from_file_location("check_agent_docs", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


check_agent_docs = _load_check_module()


class TestVersionProseDetection:
    """Version state asserted in prose drifts as easily as a table row.

    CLAUDE.md carried a stale `Current version: v2.6` claim through four
    delivered versions because the table-shaped check could not see a sentence.
    """

    @pytest.mark.parametrize(
        "line",
        [
            "**Current version: v2.6 — computational governance and evidence plane.**",
            "Current version: v2.9",
            "**Next target: v2.6.1 — deepen the evidence plane**",
            "Released tag: `v2.6.1`",
            "- Active version: v3.0",
            "current release: v2.5",
        ],
    )
    def test_flags_version_state_asserted_in_prose(self, line: str) -> None:
        assert check_agent_docs.VERSION_PROSE.search(line) is not None

    @pytest.mark.parametrize(
        "line",
        [
            "Which version is current: see AGENTS.md.",
            "**Runtime baseline: v2.5 single-track** — do not add platform services.",
            "The v2.5 runtime does not change before v3.0.",
            "See `docs/roadmap.md` for the current version status table.",
            "`RUNTIME_VERSION` tracks the last published tag.",
        ],
    )
    def test_allows_pointers_and_code_level_constraints(self, line: str) -> None:
        assert check_agent_docs.VERSION_PROSE.search(line) is None

    def test_flags_prose_only_at_line_start(self) -> None:
        """A mid-sentence mention is discussion, not an assertion of state."""
        text = "Do not write a Current version: line in a pointer file."
        assert check_agent_docs.VERSION_PROSE.search(text) is None


class TestRepositoryEntryPoints:
    def test_repository_passes_its_own_check(self) -> None:
        assert check_agent_docs.main() == 0

    def test_pointer_files_carry_no_version_state(self) -> None:
        repo_root = check_agent_docs.REPO_ROOT
        pointers = [p for p in check_agent_docs.ENTRY_POINTS if p != check_agent_docs.CONTRACT]
        assert pointers, "expected at least one pointer entry point besides the contract"

        for path_str in pointers:
            text = (repo_root / path_str).read_text(encoding="utf-8")
            assert check_agent_docs.VERSION_PROSE.search(text) is None, (
                f"{path_str} asserts version state in prose"
            )
            assert check_agent_docs.VERSION_TABLE.search(text) is None, (
                f"{path_str} duplicates the version table"
            )
