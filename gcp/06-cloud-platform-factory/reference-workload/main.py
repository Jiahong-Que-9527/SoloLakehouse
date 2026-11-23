"""G06 reference workload: read one fixture object, insert one row.

The batch template's smoke job: it proves the runtime identity can read
its own bucket prefix and write its own dataset — and nothing else. The
fixture carries the stack's name; the inserted row records it plus the
runtime principal, so the smoke check verifies identity scoping too.
"""

import json
import os
import sys

from google.cloud import bigquery, storage

BUCKET = os.environ["STACK_BUCKET"]
FIXTURE_OBJECT = os.environ.get("FIXTURE_OBJECT", "fixture/stack.json")
DATASET = os.environ["STACK_DATASET"]


def main() -> int:
    client = storage.Client()
    payload = json.loads(
        client.bucket(BUCKET).blob(FIXTURE_OBJECT).download_as_text()
    )
    stack_name = payload["stack_name"]
    table = bigquery.Client().dataset(DATASET).table("smoke_results")
    row = {
        "stack_name": stack_name,
        "runtime_principal": os.environ.get(" runtime_principal", ""),
    }
    import google.auth

    credentials, _ = google.auth.default()
    row["runtime_principal"] = credentials.service_account_email
    errors = bigquery.Client().insert_rows_json(table, [row])
    if errors:
        print(f"insert failed: {errors}", file=sys.stderr)
        return 1
    print(f"smoke row inserted for stack {stack_name} by {row['runtime_principal']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
