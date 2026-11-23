"""G06 reference workload: read one fixture object, insert one row.

The batch template's smoke job: it proves the runtime identity can read
its own bucket prefix and write its own dataset — and nothing else. The
fixture carries the stack's name; the inserted row records it plus the
runtime principal (from the metadata server — google.auth reports
"default" on Cloud Run), so the smoke check verifies identity scoping.
"""

import json
import os
import sys
import urllib.request
from datetime import datetime, UTC

from google.cloud import bigquery, storage

BUCKET = os.environ["STACK_BUCKET"]
FIXTURE_OBJECT = os.environ.get("FIXTURE_OBJECT", "fixture/stack.json")
DATASET = os.environ["STACK_DATASET"]

METADATA = "http://metadata.google.internal/computeMetadata/v1/instance/service-accounts/default/email"


def runtime_principal() -> str:
    request = urllib.request.Request(METADATA, headers={"Metadata-Flavor": "Google"})
    return urllib.request.urlopen(request, timeout=10).read().decode().strip()


def main() -> int:
    payload = json.loads(
        storage.Client().bucket(BUCKET).blob(FIXTURE_OBJECT).download_as_text()
    )
    row = {
        "stack_name": payload["stack_name"],
        "runtime_principal": runtime_principal(),
        "inserted_at": datetime.now(UTC).isoformat(),
    }
    table = bigquery.Client().dataset(DATASET).table("smoke_results")
    errors = bigquery.Client().insert_rows_json(table, [row])
    if errors:
        print(f"insert failed: {errors}", file=sys.stderr)
        return 1
    print(f"smoke row inserted for stack {row['stack_name']} by {row['runtime_principal']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
