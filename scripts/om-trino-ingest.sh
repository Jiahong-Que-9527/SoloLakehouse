#!/usr/bin/env bash
# Run a one-shot OpenMetadata Trino metadata ingestion via the bundled 1.5.6 image.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

if [[ -f .env ]]; then
  set -a
  # shellcheck disable=SC1091
  source .env
  set +a
fi
if [[ -f .env.secrets ]]; then
  set -a
  # shellcheck disable=SC1091
  source .env.secrets
  set +a
fi

export OPENMETADATA_SYNC_ENABLED="${OPENMETADATA_SYNC_ENABLED:-1}"
export OPENMETADATA_INGEST_API_URL="${OPENMETADATA_INGEST_API_URL:-http://openmetadata-server:8585/api}"

python3 - <<'PY'
from governance.openmetadata_ingest import run_trino_metadata_ingest

result = run_trino_metadata_ingest()
status = result.get("status")
if status == "skipped":
    print(f"skip: {result.get('reason')}")
    raise SystemExit(2)
if status != "ok":
    raise SystemExit(f"unexpected status: {status}")
print("ok:", result)
PY
