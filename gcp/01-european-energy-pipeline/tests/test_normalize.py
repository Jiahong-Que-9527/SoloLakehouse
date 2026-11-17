import csv
import hashlib
import io
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from energy_pipeline.normalize import HEADER, STEP, ZONE, ValidationError, Window, normalize


def encode(rows, header=HEADER):
    stream = io.StringIO(newline="")
    writer = csv.writer(stream, delimiter=";")
    writer.writerow(header)
    writer.writerows(rows)
    return stream.getvalue().encode("utf-8-sig")


def sample_rows(start="2026-06-08", until="2026-06-09"):
    window = Window.from_dates(start, until)
    rows = []
    for index in range(window.expected_rows):
        local = (window.start + index * STEP).astimezone(ZONE).replace(tzinfo=None)
        rows.append(
            [
                local.strftime("%d.%m.%Y %H:%M"),
                (local + STEP).strftime("%d.%m.%Y %H:%M"),
                "10.552,15",
            ]
        )
    return rows


def test_normal_week():
    window = Window.from_dates("2026-06-08", "2026-06-15")
    table = normalize(encode(sample_rows("2026-06-08", "2026-06-15")), window)
    assert table.num_rows == 672
    first = table.to_pylist()[0]
    assert first == {
        "interval_start": datetime(2026, 6, 7, 22, tzinfo=UTC),
        "interval_end": datetime(2026, 6, 7, 22, 15, tzinfo=UTC),
        "area": "DE",
        "metric": "actual_load_mwh",
        "value": 10552.15,
        "unit": "MWh",
        "source": "smard",
    }


@pytest.mark.parametrize("projected_ends", [False, True])
def test_autumn_two_hours_have_distinct_utc_keys(projected_ends):
    rows = sample_rows("2026-10-25", "2026-10-26")
    assert len(rows) == 100
    assert rows[8][0] == rows[12][0] == "25.10.2026 02:00"
    rows[8][2], rows[12][2] = "9.997,16", "10.210,55"
    if projected_ends:
        rows[11][1] = "25.10.2026 02:00"
    table = normalize(encode(rows), Window.from_dates("2026-10-25", "2026-10-26"))
    actual = table.to_pylist()
    assert actual[8]["interval_start"] == datetime(2026, 10, 25, 0, tzinfo=UTC)
    assert actual[12]["interval_start"] == datetime(2026, 10, 25, 1, tzinfo=UTC)
    assert actual[8]["value"] == 9997.16
    assert actual[12]["value"] == 10210.55
    assert len({r["interval_start"] for r in actual}) == 100
    assert all(r["interval_end"] - r["interval_start"] == STEP for r in actual)


@pytest.mark.parametrize("projected_ends", [False, True])
def test_spring_skips_nonexistent_hour(projected_ends):
    rows = sample_rows("2026-03-29", "2026-03-30")
    assert len(rows) == 92
    assert rows[7][0] == "29.03.2026 01:45"
    assert rows[8][0] == "29.03.2026 03:00"
    if projected_ends:
        rows[7][1] = "29.03.2026 03:00"
    actual = normalize(encode(rows), Window.from_dates("2026-03-29", "2026-03-30")).to_pylist()
    assert actual[7]["interval_end"] == actual[8]["interval_start"]


@pytest.mark.parametrize("mutation", ["missing", "duplicate", "replacement", "order", "outside"])
def test_bad_intervals_fail(mutation):
    rows = sample_rows()
    if mutation == "missing":
        rows.pop(18)
    elif mutation == "duplicate":
        rows.insert(18, rows[18])
    elif mutation == "replacement":
        rows[18] = rows[17].copy()  # Correct row count cannot hide a gap plus duplicate.
    elif mutation == "order":
        rows[18], rows[19] = rows[19], rows[18]
    else:
        rows[-1][0] = "09.06.2026 00:00"
    with pytest.raises(ValidationError, match="row count|expected local start"):
        normalize(encode(rows), Window.from_dates("2026-06-08", "2026-06-09"))


@pytest.mark.parametrize("value", ["", "-", "NaN", "Infinity", "10,552.15", "1.23,45"])
def test_null_and_malformed_numbers_fail(value):
    rows = sample_rows()
    rows[16][2] = value
    with pytest.raises(ValidationError, match="line 18: invalid or null MWh"):
        normalize(encode(rows), Window.from_dates("2026-06-08", "2026-06-09"))


@pytest.mark.parametrize("fault", ["end", "timestamp", "columns", "header", "encoding"])
def test_bad_structure_fails(fault):
    rows = sample_rows()
    if fault == "end":
        rows[16][1] = "08.06.2026 05:00"
    elif fault == "timestamp":
        rows[16][0] = "not a date"
    elif fault == "columns":
        rows[16].append("extra")
    raw = encode(rows, HEADER[:2] if fault == "header" else HEADER)
    if fault == "encoding":
        raw = b"\xff" + raw
    with pytest.raises(ValidationError):
        normalize(raw, Window.from_dates("2026-06-08", "2026-06-09"))


@pytest.mark.parametrize(
    "start,until",
    [
        ("2026-06-09", "2026-06-08"),
        ("2026-06-08", "2026-06-08"),
        ("2026-02-30", "2026-03-01"),
        ("20260608", "2026-06-09"),
    ],
)
def test_invalid_window(start, until):
    with pytest.raises(ValidationError):
        Window.from_dates(start, until)


@pytest.mark.parametrize(
    "name,start,until,count,checksum",
    [
        (
            "Realisierter_Stromverbrauch_202606080000_202606150000_Viertelstunde.csv",
            "2026-06-08",
            "2026-06-15",
            672,
            "d08c74c385656bf2eb5d02da208dd31861cf435353cee869f98b8f6665771ee6",
        ),
        (
            "Realisierter_Stromverbrauch_202610250000_202610260000_Viertelstunde.csv",
            "2026-10-25",
            "2026-10-26",
            100,
            "eed51b2a912c41af7d907d8cfd0aec7d6c031ac946c2e1ea0441460ec60d9edb",
        ),
    ],
)
def test_optional_downloaded_fixture(name, start, until, count, checksum):
    fixture = Path(__file__).resolve().parents[1] / "fixtures" / name
    if not fixture.exists():
        pytest.skip("downloaded source files stay outside Git; synthetic tests run in CI")
    raw = fixture.read_bytes()
    assert hashlib.sha256(raw).hexdigest() == checksum
    table = normalize(raw, Window.from_dates(start, until))
    assert table.num_rows == count
    assert all(
        right - left == timedelta(minutes=15)
        for left, right in zip(
            table["interval_start"].to_pylist(),
            table["interval_start"].to_pylist()[1:],
            strict=False,
        )
    )
