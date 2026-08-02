"""Shared runtime health check access for v2.9 operational evidence."""

from __future__ import annotations

import importlib.util
from pathlib import Path
from typing import Any

StatusTuple = tuple[str, str, str]
_REPO_ROOT = Path(__file__).resolve().parents[1]
_VERIFY_SETUP_PATH = _REPO_ROOT / "scripts" / "verify-setup.py"


def load_verify_setup_module() -> Any:
    spec = importlib.util.spec_from_file_location("verify_setup", _VERIFY_SETUP_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load {_VERIFY_SETUP_PATH}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def run_verification_checks() -> tuple[list[StatusTuple], list[str]]:
    """Run verify-setup health checks without requiring a subprocess."""
    module = load_verify_setup_module()
    module.load_dotenv_if_present()
    return module.run_verification_checks()
