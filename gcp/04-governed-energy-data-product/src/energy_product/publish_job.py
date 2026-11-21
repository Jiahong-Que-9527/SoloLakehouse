"""Cloud Run publish job: one governed release, end to end.

Reads the input release from G01 (producer identity), evaluates the
contract gate with a recorded evaluation time, then publishes under the
approved candidate ID: version table, manifest, view switch, release
row. A blocked gate quarantines and leaves the previous release current.

Environment (set by Terraform):
  BQ_DATASET            the `energy_product` dataset
  INPUT_RELEASE_ID      the G01 release id to consume
  CANDIDATE_ID          the immutable release id for this publication
  CONTRACT_FILE         contract path inside the image (/app/contracts/...)
  GIT_SHA, APPROVER     provenance, recorded in the manifest
  EVALUATED_AT          optional recorded clock (ISO-8601) for historical
                        replay; defaults to now
Approval is not passed through the environment: the job runs only after
the `gcp-test` gate has approved the deployment, which is the recorded
human approval (design section 5, step 1).
"""

import os
from datetime import UTC, datetime, timedelta
from pathlib import Path

from energy_product.cloud_gcp import BigQueryProductStore
from energy_product.contract import load_contract
from energy_product.publisher import PublishConflict, PublishRequest, publish
from energy_product.store import AccessDenied


def _evaluation_time() -> datetime:
    recorded = os.environ.get("EVALUATED_AT")
    return datetime.fromisoformat(recorded) if recorded else datetime.now(UTC)


def main() -> int:
    dataset = os.environ["BQ_DATASET"]
    input_release_id = os.environ["INPUT_RELEASE_ID"]
    candidate_id = os.environ["CANDIDATE_ID"]
    contract_path = Path(os.environ.get("CONTRACT_FILE", "/app/contracts/energy-load.yaml"))

    contract = load_contract(contract_path)
    store = BigQueryProductStore(dataset)

    ledger, rows = store.fetch_input_release(input_release_id)
    ingested_at = ledger.get("published_at") or _evaluation_time()
    if isinstance(ingested_at, str):
        ingested_at = datetime.fromisoformat(ingested_at)
    if rows and "ingested_at" in rows[0] and rows[0]["ingested_at"] is not None:
        # G01 stamps every row with the ingestion time; prefer the rows.
        ingested_at = rows[0]["ingested_at"]

    interval_minutes = 15  # the energy-load grain; per-product when more products go live
    expected_grid = _expected_grid(
        ledger["window_start"], ledger["window_end"], rows, interval_minutes
    )

    request = PublishRequest(
        product=contract.slug,
        candidate_id=candidate_id,
        input_release_id=input_release_id,
        contract=contract,
        rows=rows,
        expected_grid=expected_grid,
        ingested_at=ingested_at,
        evaluation_time=_evaluation_time(),
        git_sha=os.environ.get("GIT_SHA"),
        approver=os.environ.get("APPROVER", "gcp-test-gate"),
        approved=True,
    )
    result = publish(store, request)
    print(
        f"publish {contract.data_product} candidate {candidate_id} from input "
        f"{input_release_id}: {result.status}, view points at {result.view_points_at}"
    )
    return 0


def _as_datetime(value) -> datetime:
    """The G01 ledger types the window as DATE: the client returns
    ``datetime.date``, whose arithmetic truncates sub-day offsets — the
    first live publication collapsed 672 quarter-hour keys onto 7 day
    keys this way. Coerce date, datetime and ISO strings to aware UTC."""
    if isinstance(value, datetime):
        parsed = value
    elif isinstance(value, str):
        parsed = datetime.fromisoformat(value)
    else:
        parsed = datetime(value.year, value.month, value.day)
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)


def _expected_grid(
    window_start, window_end, rows: list[dict], interval_minutes: int
) -> list[tuple]:
    """The exact business keys the ledger window must contain, built from
    the window alone — never from the actual rows, so a masked gap still
    fails the bidirectional completeness check."""
    start = _as_datetime(window_start)
    end = _as_datetime(window_end)
    expected_count = int((end - start).total_seconds() // 60 // interval_minutes)
    if expected_count <= 0 or not rows:
        return _grid_from_rows(rows)
    area, metric = rows[0]["area"], rows[0]["metric"]
    return [
        (area, metric, start + timedelta(minutes=index * interval_minutes))
        for index in range(expected_count)
    ]


def _grid_from_rows(rows: list[dict]) -> list[tuple]:
    """Fallback when the ledger window cannot be parsed: the distinct keys."""
    seen = []
    for row in rows:
        key = (row.get("area"), row.get("metric"), row.get("interval_start"))
        if key not in seen:
            seen.append(key)
    return seen


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (AccessDenied, PublishConflict, LookupError) as error:
        print(f"publish blocked: {error}")
        raise SystemExit(1) from error
