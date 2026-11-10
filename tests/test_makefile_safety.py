# Regression checks: legacy convenience targets must not destroy state.
from __future__ import annotations

import os
import shutil
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MAKE = shutil.which("make")


@unittest.skipUnless(MAKE, "make is required for Makefile behavior checks")
class TestMakefileSafety(unittest.TestCase):
    def run_target(self, target: str | None) -> subprocess.CompletedProcess[str]:
        env = dict(os.environ, PATH="/nonexistent-slh-command-safety", GIT_COMMIT="test")
        command = [str(MAKE), "--no-print-directory"]
        if target is not None:
            command.append(target)
        return subprocess.run(command, cwd=ROOT, env=env, text=True, capture_output=True)

    def test_destructive_convenience_targets_fail_without_external_commands(self) -> None:
        for target in ("clean", "reset-mlflow-db", "purge-legacy-docker-volumes"):
            with self.subTest(target=target):
                result = self.run_target(target)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("Disabled", result.stderr)
                self.assertNotIn("not found", result.stderr)
                self.assertNotIn("No such file", result.stderr)

    def test_default_target_is_help_without_external_commands(self) -> None:
        result = self.run_target(None)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("docs-check", result.stdout)
        self.assertIn("No cluster is deployed", result.stdout)
