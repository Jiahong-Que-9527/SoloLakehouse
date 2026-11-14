"""Write one hour of state vectors as sorted ZSTD Parquet."""

from __future__ import annotations

from pathlib import Path

import pyarrow as pa
import pyarrow.compute as pc
import pyarrow.parquet as pq

ROW_GROUP_SIZE = 100_000
COMPRESSION_LEVEL = 9


def table_from_rows(rows: list[tuple], schema: pa.Schema) -> pa.Table:
    if not rows:
        return schema.empty_table()
    columns = list(zip(*rows, strict=True))
    arrays = [pa.array(values, type=field.type) for values, field in zip(columns, schema, strict=True)]
    return pa.Table.from_arrays(arrays, schema=schema)


def write_hour_table(table: pa.Table, path: Path) -> None:
    """Sort by `icao24, time` and write. The caller publishes the file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    indices = pc.sort_indices(
        table,
        sort_keys=[("icao24", "ascending"), ("time", "ascending")],
        null_placement="at_end",
    )
    ordered = table.take(indices)
    pq.write_table(
        ordered,
        path,
        compression="zstd",
        compression_level=COMPRESSION_LEVEL,
        row_group_size=ROW_GROUP_SIZE,
        use_dictionary=True,
        write_statistics=True,
    )
