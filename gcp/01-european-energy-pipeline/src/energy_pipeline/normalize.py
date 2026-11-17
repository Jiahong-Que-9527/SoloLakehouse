"""Parse full, chronologically ordered SMARD windows without guessing DST folds."""

import csv
import io
import re
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

import pyarrow as pa

HEADER = ["Datum von", "Datum bis", "Netzlast [MWh] Originalauflösungen"]
ZONE = ZoneInfo("Europe/Berlin")
STEP = timedelta(minutes=15)
NUMBER = re.compile(r"-?(?:\d+|\d{1,3}(?:\.\d{3})+)(?:,\d+)?\Z")
SCHEMA = pa.schema(
    [
        ("interval_start", pa.timestamp("us", tz="UTC")),
        ("interval_end", pa.timestamp("us", tz="UTC")),
        ("area", pa.string()),
        ("metric", pa.string()),
        ("value", pa.float64()),
        ("unit", pa.string()),
        ("source", pa.string()),
    ]
)


class ValidationError(ValueError):
    """An input cannot safely be normalized."""


@dataclass(frozen=True)
class Window:
    start: datetime
    end: datetime

    @classmethod
    def from_dates(cls, start: str, until: str) -> "Window":
        """Dates are local midnights, with an exclusive end."""
        try:
            if not all(re.fullmatch(r"\d{4}-\d{2}-\d{2}", x) for x in (start, until)):
                raise ValueError("expected YYYY-MM-DD dates")
            first, last = date.fromisoformat(start), date.fromisoformat(until)
        except ValueError as exc:
            raise ValidationError(f"invalid window: {exc}") from exc
        if first >= last:
            raise ValidationError("--from must be earlier than --until")
        return cls(
            datetime.combine(first, datetime.min.time(), ZONE).astimezone(UTC),
            datetime.combine(last, datetime.min.time(), ZONE).astimezone(UTC),
        )

    @property
    def expected_rows(self) -> int:
        return (self.end - self.start) // STEP


def normalize(raw: bytes, window: Window) -> pa.Table:
    """Require exactly the declared window, in source order, before writing data.

    Each UTC slot has one expected local start. This disambiguates the two
    autumn hours using full-window order. SMARD's nominal local end may differ
    from the projected UTC end at a clock change; both representations are
    accepted, but the actual output interval is always 15 elapsed minutes.
    """
    try:
        reader = csv.reader(io.StringIO(raw.decode("utf-8-sig")), delimiter=";", strict=True)
        if next(reader, None) != HEADER:
            raise ValidationError(f"expected CSV header: {';'.join(HEADER)}")
        source_rows = list(reader)
    except (UnicodeDecodeError, csv.Error) as exc:
        raise ValidationError(f"invalid UTF-8 CSV: {exc}") from exc
    if len(source_rows) != window.expected_rows:
        raise ValidationError(
            f"row count: expected {window.expected_rows}, got {len(source_rows)}; "
            "check missing/duplicate intervals and the requested window"
        )

    output = []
    for offset, fields in enumerate(source_rows):
        line = offset + 2
        if len(fields) != 3:
            raise ValidationError(f"line {line}: expected 3 columns, got {len(fields)}")
        try:
            local_start, local_end = (
                datetime.strptime(value, "%d.%m.%Y %H:%M") for value in fields[:2]
            )
        except ValueError as exc:
            raise ValidationError(f"line {line}: invalid local timestamp") from exc
        start = window.start + offset * STEP
        end = start + STEP
        expected_start = start.astimezone(ZONE).replace(tzinfo=None)
        if local_start != expected_start:
            raise ValidationError(
                f"line {line}: expected local start {expected_start:%d.%m.%Y %H:%M}, "
                f"got {fields[0]}; missing, duplicate, out-of-order or out-of-window interval"
            )
        expected_ends = {local_start + STEP, end.astimezone(ZONE).replace(tzinfo=None)}
        if local_end not in expected_ends:
            raise ValidationError(f"line {line}: end does not describe a 15-minute interval")
        if not NUMBER.fullmatch(fields[2]):
            raise ValidationError(f"line {line}: invalid or null MWh value {fields[2]!r}")
        number = Decimal(fields[2].replace(".", "").replace(",", "."))
        value = float(number)
        if not (-float("inf") < value < float("inf")):
            raise ValidationError(f"line {line}: MWh value is not finite")
        output.append(
            dict(
                interval_start=start,
                interval_end=end,
                area="DE",
                metric="actual_load_mwh",
                value=value,
                unit="MWh",
                source="smard",
            )
        )
    return pa.Table.from_pylist(output, schema=SCHEMA)
