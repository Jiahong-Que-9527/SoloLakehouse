# [房玄龄·2026-11-10] Check code fences, heading anchors and preserved source coverage.
from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path
from types import ModuleType


def load_checker() -> ModuleType:
    path = Path(__file__).resolve().parents[1] / "scripts/check-repo-docs.py"
    spec = importlib.util.spec_from_file_location("repo_docs_check", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


CHECKER = load_checker()


class TestRepositoryDocs(unittest.TestCase):
    def test_fenced_examples_are_not_treated_as_real_links(self) -> None:
        fence = chr(96) * 3
        text = f"[real](README.md)\n{fence}text\n[fake](missing.md)\n{fence}\n"
        self.assertEqual(CHECKER.links_in(text), ["README.md"])

    def test_duplicate_and_formatted_heading_anchors(self) -> None:
        headings = "# Same\n# Same\n## **Source** / identity\n"
        self.assertEqual(
            CHECKER.heading_slugs(headings), {"same", "same-1", "source--identity"}
        )

    def test_html_image_paths_are_checked(self) -> None:
        self.assertEqual(CHECKER.links_in('<img src="docs/img/slh-brand.png">'),
                         ["docs/img/slh-brand.png"])

    def test_archive_and_unfinished_item_integrity(self) -> None:
        self.assertEqual(CHECKER.check_archive()[0], [])
        self.assertEqual(CHECKER.check_retained_work()[0], [])
