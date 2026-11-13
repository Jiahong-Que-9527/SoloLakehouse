"""Exercise the project CI routing for changes and missing history."""
from __future__ import annotations

import subprocess
import unittest
from unittest.mock import patch

from scripts.ci_scope import changes, select


class ProjectCiTest(unittest.TestCase):
    def test_project_routing(self) -> None:
        cases = [
            (["projects/finance/runtimes/gcp/job.py"], (True, "none")),
            (["transformations/ecb_bronze_to_silver.py"], (True, "none")),
            (["governance/datasets/fin.ecb_rates_silver.yaml"], (True, "none")),
            (["projects/aviation/roadmap.md", "docs/workloads/aviation.md"], (False, "aviation")),
            (["README.md", "projects/finance/README.md"], (False, "repository")),
            (["requirements.txt"], (True, "repository")),
            ([".github/workflows/test.yml"], (True, "repository")),
            (["projects/unmapped/source.py"], (True, "repository")),
            (["ingestion/bronze_writer.py", "projects/aviation/README.md"], (True, "aviation")),
            ([], (False, "none")),
        ]
        for paths, expected in cases:
            with self.subTest(paths=paths):
                self.assertEqual(select([("M", path) for path in paths]), expected)

    def test_removed_finance_path_checks_links(self) -> None:
        self.assertEqual(select([("D", "ingestion/old.py")]), (True, "repository"))

    @patch("scripts.ci_scope.git")
    def test_existing_push_uses_both_event_endpoints(self, git) -> None:
        before, after = "a" * 40, "b" * 40
        git.return_value = b"D\0ingestion/old.py\0A\0projects/aviation/case.md\0"
        self.assertEqual(
            select(changes("push", {"before": before, "after": after})),
            (True, "repository"),
        )
        git.assert_called_once_with(
            "diff", "--no-renames", "--name-status", "-z", before, after, "--"
        )

    @patch("scripts.ci_scope.git")
    def test_pr_uses_merge_base(self, git) -> None:
        base, head, ancestor = "a" * 40, "b" * 40, "c" * 40
        git.side_effect = [f"{ancestor}\n".encode(), b"M\0README.md\0"]
        payload = {"pull_request": {"base": {"sha": base}, "head": {"sha": head}}}
        self.assertEqual(changes("pull_request", payload), [("M", "README.md")])
        git.assert_any_call("merge-base", "--all", base, head)
        git.assert_any_call("diff", "--no-renames", "--name-status", "-z", ancestor, head, "--")

    @patch("scripts.ci_scope.git")
    def test_new_branch_uses_default_branch_ancestor(self, git) -> None:
        base, head, ancestor = "a" * 40, "b" * 40, "c" * 40
        git.side_effect = [f"{base}\n".encode(), f"{ancestor}\n".encode(), b""]
        payload = {"before": "0" * 40, "after": head, "repository": {"default_branch": "main"}}
        self.assertEqual(changes("push", payload), [])
        git.assert_any_call("rev-parse", "--verify", "refs/remotes/origin/main")
        git.assert_any_call("diff", "--no-renames", "--name-status", "-z", ancestor, head, "--")

    @patch("scripts.ci_scope.git")
    def test_missing_commit_reaches_fallback(self, git) -> None:
        git.side_effect = subprocess.CalledProcessError(128, "git diff")
        with self.assertRaises(subprocess.CalledProcessError):
            changes("push", {"before": "a" * 40, "after": "b" * 40})
