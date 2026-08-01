"""Generate and persist a complete v2.6 lineage-evidence manifest."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


def load_dotenv_if_present() -> None:
    """Load local Compose-style environment values without evaluating shell syntax."""
    import os

    env_path = REPO_ROOT / ".env"
    if not env_path.exists():
        return
    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        if key and key not in os.environ:
            os.environ[key] = value.strip()


load_dotenv_if_present()

from governance.emission import emit_lineage_evidence  # noqa: E402
from storage_config import get_storage_config  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset-id", required=True)
    parser.add_argument("--dagster-run-id", required=True)
    args = parser.parse_args()
    manifest, object_path = emit_lineage_evidence(args.dataset_id, args.dagster_run_id)
    print(f"wrote s3://{get_storage_config().audit_bucket}/{object_path}")
    print(f"record_sha256={manifest.record_sha256}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
