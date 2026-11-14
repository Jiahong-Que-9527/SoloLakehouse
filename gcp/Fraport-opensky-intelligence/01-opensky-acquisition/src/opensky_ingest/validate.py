"""Re-read checks for one staged hour. Duplicates are counted, not removed."""

from __future__ import annotations

from dataclasses import dataclass

import pyarrow as pa
import pyarrow.compute as pc

from .config import BBox
from .errors import SourceError


@dataclass(frozen=True)
class HourStats:
    rows: int
    aircraft: int
    ground_rows: int
    stale_or_unknown_rows: int
    duplicate_key_rows: int
    nulls: dict[str, int]
    min_time: int | None
    max_time: int | None


def _as_int(value) -> int:
    return 0 if value is None else int(value)


def validate_hour_table(
    table: pa.Table, *, schema: pa.Schema, hour_epoch: int, bbox: BBox
) -> HourStats:
    """Check the contract. Raise SourceError('VALIDATION') on any violation."""
    if not table.schema.equals(schema, check_metadata=False):
        raise SourceError("VALIDATION", "schema does not match the contract")

    indices = pc.sort_indices(
        table,
        sort_keys=[("icao24", "ascending", "at_end"), ("time", "ascending", "at_end")],
    )
    expected = pa.array(range(table.num_rows), type=pa.int64())
    if table.num_rows and not pc.all(pc.equal(indices, expected)).as_py():
        raise SourceError("VALIDATION", "rows are not sorted by icao24, time")

    lat_ok = pc.and_(
        pc.greater_equal(table.column("lat"), bbox.south),
        pc.less_equal(table.column("lat"), bbox.north),
    )
    lon_ok = pc.and_(
        pc.greater_equal(table.column("lon"), bbox.west),
        pc.less_equal(table.column("lon"), bbox.east),
    )
    time_ok = pc.and_(
        pc.greater_equal(table.column("time"), hour_epoch),
        pc.less(table.column("time"), hour_epoch + 3600),
    )
    hour_ok = pc.equal(table.column("hour"), hour_epoch)
    inside = pc.and_(pc.and_(lat_ok, lon_ok), pc.and_(time_ok, hour_ok))
    bad = pc.sum(pc.if_else(pc.fill_null(inside, False), 0, 1)).as_py()
    if _as_int(bad):
        raise SourceError("VALIDATION", "a row is outside the box or the hour window")

    grouped = table.group_by(["icao24", "time"]).aggregate([([], "count_all")])
    extras = pc.sum(pc.subtract(grouped.column("count_all"), 1)).as_py()
    stale = pc.or_(
        pc.is_null(table.column("lastcontact")),
        pc.greater(
            pc.subtract(pc.cast(table.column("time"), pa.float64()), table.column("lastcontact")),
            15,
        ),
    )
    times = table.column("time")
    return HourStats(
        rows=table.num_rows,
        aircraft=_as_int(pc.count_distinct(table.column("icao24")).as_py()),
        ground_rows=_as_int(
            pc.sum(pc.if_else(pc.fill_null(table.column("onground"), False), 1, 0)).as_py()
        ),
        stale_or_unknown_rows=_as_int(pc.sum(pc.if_else(pc.fill_null(stale, False), 1, 0)).as_py()),
        duplicate_key_rows=_as_int(extras),
        nulls={name: table.column(name).null_count for name in table.column_names},
        min_time=None if times.null_count == table.num_rows else int(pc.min(times).as_py()),
        max_time=None if times.null_count == table.num_rows else int(pc.max(times).as_py()),
    )
