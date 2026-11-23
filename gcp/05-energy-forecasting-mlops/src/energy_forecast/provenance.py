"""Provenance helpers: the git revision recorded in reports and manifests."""

import subprocess
from pathlib import Path


def git_commit(repo_hint: Path | None = None) -> str:
    """Best-effort HEAD commit; 'unknown' outside a repository."""
    try:
        out = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=repo_hint,
            capture_output=True,
            text=True,
            check=True,
            timeout=10,
        )
        return out.stdout.strip()
    except Exception:
        return "unknown"
