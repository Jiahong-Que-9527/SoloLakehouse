"""Contract-level tests: availability table and the issue-time rule."""

from __future__ import annotations

from datetime import date

from charging_forecast.contract import (
    AVAILABILITY_TABLE,
    TABLE_GRAIN,
    TABLE_SCHEMAS,
    issue_time_utc,
    render_contract,
)
from conftest import TINY_CONFIG


def test_unreadable_families_are_flagged():
    assert AVAILABILITY_TABLE["weather_realized"]["readable_at_issue"] is False
    assert AVAILABILITY_TABLE["same_day_demand"]["readable_at_issue"] is False
    for family in (
        "calendar",
        "station_attributes",
        "demand_lags",
        "weather_forecasts",
        "tariff_events",
    ):
        assert AVAILABILITY_TABLE[family]["readable_at_issue"] is True, family


def test_issue_time_is_0600_berlin():
    assert issue_time_utc(date(2025, 1, 15)).utcoffset().total_seconds() == 0
    assert issue_time_utc(date(2025, 1, 15)).hour == 5  # CET -> 05:00Z
    assert issue_time_utc(date(2025, 7, 15)).hour == 4  # CEST -> 04:00Z
    assert issue_time_utc(date(2026, 10, 24)).hour == 4  # last full CEST day
    assert issue_time_utc(date(2026, 10, 25)).hour == 5  # transition day: 06:00 is CET


def test_every_table_has_schema_and_grain():
    for name in TABLE_SCHEMAS:
        assert name in TABLE_GRAIN, name
        grain = TABLE_GRAIN[name]
        columns = [c for c, _ in TABLE_SCHEMAS[name]]
        assert set(grain) <= set(columns), name


def test_render_contract_contains_gates_and_availability():
    doc = render_contract(TINY_CONFIG)
    assert doc["data_product"] == "charging-network-demand"
    assert doc["quality_gates"]["demand_max_fraction_of_capacity"] == 1.0
    assert doc["contract"]["availability_table"] == AVAILABILITY_TABLE
    assert doc["release"]["approval_required"] is True
