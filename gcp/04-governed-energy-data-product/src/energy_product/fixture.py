"""Seeded candidates for the contract and gate tests (sequence step 1).

The good candidate covers a fixed historical week whose every interval is
known; the invalid variants mirror the acceptance cases: a duplicate that
masks a missing interval (row count preserved), a null measure, a stale
input release and a missing required column.
"""

import hashlib
import json
from datetime import UTC, datetime, timedelta

INTERVAL_MINUTES = 15
AREA = "DE"
METRIC = "actual_load_mwh"
UNIT = "MWh"
WEEK_START = datetime(2026, 6, 8, 0, 0, tzinfo=UTC)
EVALUATION_TIME = datetime(2026, 6, 15, 2, 0, tzinfo=UTC)
GOOD_INPUT_RELEASE = "input-week-672"
GOOD_CANDIDATE = "cand-good-0001"


def expected_grid(start: datetime = WEEK_START, hours: int = 24 * 7) -> list[tuple]:
    count = hours * 60 // INTERVAL_MINUTES
    return [
        (AREA, METRIC, start + timedelta(minutes=index * INTERVAL_MINUTES))
        for index in range(count)
    ]


def candidate_rows(
    grid: list[tuple] | None = None, *, release_id: str = GOOD_INPUT_RELEASE
) -> list[dict]:
    step = timedelta(minutes=INTERVAL_MINUTES)
    rows = []
    for index, (area, metric, interval_start) in enumerate(grid or expected_grid()):
        rows.append(
            {
                "interval_start": interval_start,
                "interval_end": interval_start + step,
                "area": area,
                "metric": metric,
                "value": 10000.0 + (index % 96) * 25.0,
                "unit": UNIT,
                "release_id": release_id,
            }
        )
    return rows


def candidate_metadata(*, ingested_at: datetime | None = None) -> dict:
    # The week closes at WEEK_START + 7d; ingestion one hour later is fresh
    # against the recorded evaluation time two hours later.
    return {
        "ingested_at": ingested_at or WEEK_START + timedelta(hours=24 * 7 + 1),
        "evaluation_time": EVALUATION_TIME,
    }


def with_duplicate_masking_missing(rows: list[dict]) -> list[dict]:
    """Duplicate the second key onto a copy of the first row and drop the
    original first row: the row count still matches the grid, one key
    appears twice and the first key is missing."""
    shifted = dict(rows[0])
    shifted["interval_start"] = rows[1]["interval_start"]
    shifted["interval_end"] = rows[1]["interval_end"]
    return [shifted] + rows[1:]


def with_null_value(rows: list[dict]) -> list[dict]:
    damaged = [dict(row) for row in rows]
    damaged[10]["value"] = None
    return damaged


def with_missing_column(rows: list[dict]) -> list[dict]:
    damaged = [{key: value for key, value in row.items() if key != "unit"} for row in rows]
    return damaged


def stale_metadata() -> dict:
    return {
        "ingested_at": EVALUATION_TIME - timedelta(hours=72),
        "evaluation_time": EVALUATION_TIME,
    }


def rows_checksum(rows: list[dict]) -> str:
    """Canonical checksum of a candidate's rows; retry idempotency compares it."""
    payload = json.dumps(
        rows, sort_keys=True, separators=(",", ":"), default=_isoformat, ensure_ascii=False
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _isoformat(value):
    if isinstance(value, datetime):
        return value.isoformat()
    raise TypeError(f"not serialisable: {type(value)}")
