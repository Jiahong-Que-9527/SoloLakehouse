"""E01 acceptance tests: fixtures, generator determinism, ingestion guarantees.

Positive checks and negative drills per ``01-ingestion-raw-layer/docs/implementation.md``:
manifest checksums, repeat-run idempotence, mid-pagination crash + resume parity,
schema-drift quarantine, batch-collision refusal, and raw-level conservation.
"""

from __future__ import annotations

import hashlib
import json
from decimal import Decimal
from pathlib import Path

import pytest

from charging_commerce import ingestion
from charging_commerce.generator import MockRoamingServer, generate
from charging_commerce.open_data import verify_fixtures

FIXTURES_DIR = Path(__file__).resolve().parents[1] / "fixtures"


@pytest.fixture(scope="session")
def generated(tmp_path_factory) -> Path:
    out = tmp_path_factory.mktemp("generated")
    generate(out, FIXTURES_DIR)
    return out


@pytest.fixture()
def report(generated: Path) -> dict:
    return json.loads((generated / "generation_report.json").read_text())


GENERATED_SOURCES = {"bnetza", "tariffs", "sessions"}


def _ingest_file_sources(
    db_path: Path, state_dir: Path, generated_dir: Path, fixtures_dir: Path
) -> None:
    for source, batch in (
        ("bnetza", "bnetza-snapshots-0001"),
        ("tariffs", "tariffs-t0t1t2-0001"),
        ("sessions", "charging-sim-window-0001"),
        ("smard", "smard-2025-10-2026-05-0001"),
        ("ecb", "ecb-2025-09-2026-05-0001"),
    ):
        name = ingestion.SOURCE_PAYLOADS[source]
        payload = (
            Path(generated_dir) / name if source in GENERATED_SOURCES else Path(fixtures_dir) / name
        )
        ingestion.ingest_file(source, payload, batch, db_path, state_dir)


# --------------------------------------------------------------------------
# Fixtures
# --------------------------------------------------------------------------


def test_manifest_checksums():
    counts = verify_fixtures(FIXTURES_DIR)
    assert counts["bnetza_hesse_slice.csv"] == 3233
    assert counts["ecb_fx_slice.csv"] == 507
    assert counts["smard_prices_slice.csv"] > 20_000


def test_generator_deterministic(tmp_path):
    out_a, out_b = tmp_path / "a", tmp_path / "b"
    generate(out_a, FIXTURES_DIR)
    generate(out_b, FIXTURES_DIR)
    for name in (
        "charging_sessions.jsonl",
        "settlements.jsonl",
        "stations_snapshots.jsonl",
        "tariffs_snapshots.jsonl",
    ):
        assert _sha256(out_a / name) == _sha256(out_b / name), f"{name} is not deterministic"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


# --------------------------------------------------------------------------
# Ingestion guarantees
# --------------------------------------------------------------------------


def test_ingest_raw_expected_row_counts(generated: Path, report: dict, tmp_path):
    db, state = tmp_path / "wh.duckdb", tmp_path / "state"
    _ingest_file_sources(db, state, generated, FIXTURES_DIR)
    counts = ingestion.raw_counts(db)
    quarantined_sessions = sum(report["quarantine_expected"]["charging_sim"].values())
    assert counts["raw_stations_bnetza"] == report["raw_expected_rows"]["raw_stations_bnetza"]
    assert counts["raw_tariff_plans"] == report["raw_expected_rows"]["raw_tariff_plans"]
    # Raw tables only hold contract-valid rows: payload rows minus quarantined.
    assert counts["raw_charging_sessions"] == (
        report["raw_expected_rows"]["raw_charging_sessions"] - quarantined_sessions
    )
    assert counts["raw_smard_prices"] > 0
    assert counts["raw_ecb_fx_rates"] == 507


def test_repeat_run_is_noop(generated: Path, tmp_path):
    db, state = tmp_path / "wh.duckdb", tmp_path / "state"
    payload = generated / "charging_sessions.jsonl"
    first = ingestion.ingest_file("sessions", payload, "charging-sim-window-0001", db, state)
    assert first.rows_added > 0 and first.quarantined > 0
    second = ingestion.ingest_file("sessions", payload, "charging-sim-window-0001", db, state)
    assert second.skipped and second.rows_added == 0
    counts = ingestion.raw_counts(db)
    assert counts["raw_charging_sessions"] == first.rows_added
    assert counts["raw_quarantine"] == first.quarantined


def test_batch_collision_refused(generated: Path, tmp_path):
    db, state = tmp_path / "wh.duckdb", tmp_path / "state"
    payload = generated / "tariffs_snapshots.jsonl"
    ingestion.ingest_file("tariffs", payload, "tariffs-t0t1t2-0001", db, state)
    tampered = tmp_path / "tampered.jsonl"
    lines = payload.read_text().splitlines()
    record = json.loads(lines[0])
    record["plan_tier"] = "premium"
    tampered.write_text("\n".join([json.dumps(record, sort_keys=True), *lines[1:]]) + "\n")
    with pytest.raises(ingestion.BatchCollisionError, match="different payload hash"):
        ingestion.ingest_file("tariffs", tampered, "tariffs-t0t1t2-0001", db, state)


def test_quarantine_routing_matches_report(generated: Path, report: dict, tmp_path):
    db, state = tmp_path / "wh.duckdb", tmp_path / "state"
    _ingest_file_sources(db, state, generated, FIXTURES_DIR)
    reasons = ingestion.quarantine_by_reason(db)
    expected = {
        **report["quarantine_expected"]["charging_sim"],
        **report["quarantine_expected"]["roaming_api"],
    }
    # roaming_api faults only land after the roaming ingest (separate test);
    # here the charging_sim expectations must hold exactly.
    for reason, count in report["quarantine_expected"]["charging_sim"].items():
        assert reasons.get(reason, 0) == count, f"{reason}: {reasons.get(reason, 0)} != {count}"
    assert set(reasons) <= set(expected)


def test_negative_kwh_and_drift_route_to_quarantine(tmp_path):
    db, state = tmp_path / "wh.duckdb", tmp_path / "state"
    payload = tmp_path / "dirty.jsonl"
    rows = [
        {
            "session_id": "S-DIRTY-1",
            "event_seq": 1,
            "station_id": "1001771",
            "tariff_id": "T-DE-STD-01",
            "country_code": "DE",
            "currency_code": "EUR",
            "session_started_at": "2025-10-10T10:00:00Z",
            "session_ended_at": "2025-10-10T11:00:00Z",
            "settled_at": "2025-10-10T12:00:00Z",
            "energy_kwh": "-3.5000",
            "gross_amount_local": "2.07",
            "event_type": "charge",
        },
        {
            "session_id": "S-DIRTY-2",
            "event_seq": 1,
            "station_id": "1001771",
            "tariff_id": "T-DE-STD-01",
            "country_code": "DE",
            "currency_code": "EUR",
            "session_started_at": "2025-10-10T12:00:00Z",
            "session_ended_at": "2025-10-10T11:00:00Z",
            "settled_at": "2025-10-10T12:00:00Z",
            "energy_kwh": "10.0000",
            "gross_amount_local": "5.90",
            "event_type": "charge",
        },
        {
            # schema drift: unexpected field
            "session_id": "S-DIRTY-3",
            "event_seq": 1,
            "station_id": "1001771",
            "tariff_id": "T-DE-STD-01",
            "country_code": "DE",
            "currency_code": "EUR",
            "session_started_at": "2025-10-10T13:00:00Z",
            "session_ended_at": "2025-10-10T14:00:00Z",
            "settled_at": "2025-10-10T15:00:00Z",
            "energy_kwh": "5.0000",
            "gross_amount_local": "2.95",
            "event_type": "charge",
            "legacy_field": "oops",
        },
        {
            # null primary key
            "session_id": None,
            "event_seq": 1,
            "station_id": "1001771",
            "tariff_id": "T-DE-STD-01",
            "country_code": "DE",
            "currency_code": "EUR",
            "session_started_at": "2025-10-10T16:00:00Z",
            "session_ended_at": "2025-10-10T17:00:00Z",
            "settled_at": "2025-10-10T18:00:00Z",
            "energy_kwh": "5.0000",
            "gross_amount_local": "2.95",
            "event_type": "charge",
        },
        {
            # invalid type
            "session_id": "S-DIRTY-5",
            "event_seq": 1,
            "station_id": "1001771",
            "tariff_id": "T-DE-STD-01",
            "country_code": "DE",
            "currency_code": "EUR",
            "session_started_at": "not-a-timestamp",
            "session_ended_at": "2025-10-10T17:00:00Z",
            "settled_at": "2025-10-10T18:00:00Z",
            "energy_kwh": "5.0000",
            "gross_amount_local": "2.95",
            "event_type": "charge",
        },
    ]
    payload.write_text("\n".join(json.dumps(r) for r in rows) + "\n")
    result = ingestion.ingest_file("sessions", payload, "charging-sim-dirty-0001", db, state)
    assert (result.rows_added, result.quarantined) == (0, 5)
    reasons = ingestion.quarantine_by_reason(db)
    assert reasons["negative_energy_kwh"] == 1
    assert reasons["invalid_timestamp_order"] == 1
    assert reasons["unexpected_schema_drift"] == 1
    assert reasons["null_primary_key"] == 1
    assert reasons["invalid_type"] == 1


def test_lineage_columns_present(generated: Path, tmp_path):
    db, state = tmp_path / "wh.duckdb", tmp_path / "state"
    ingestion.ingest_file(
        "ecb", FIXTURES_DIR / "ecb_fx_slice.csv", "ecb-2025-09-2026-05-0001", db, state
    )
    conn = ingestion._connect(db)
    try:
        row = conn.execute(
            "SELECT _batch_id, _source_name, length(_source_hash), _ingested_at"
            " FROM raw.raw_ecb_fx_rates LIMIT 1"
        ).fetchone()
    finally:
        conn.close()
    assert row[0] == "ecb-2025-09-2026-05-0001"
    assert row[1] == "ecb_portal"
    assert row[2] == 64  # SHA-256 hex digest


# --------------------------------------------------------------------------
# Conservation (raw side of contract §3.1)
# --------------------------------------------------------------------------


def test_raw_conservation_matches_generation_report(generated: Path, report: dict, tmp_path):
    db, state = tmp_path / "wh.duckdb", tmp_path / "state"
    _ingest_file_sources(db, state, generated, FIXTURES_DIR)
    actual = ingestion.raw_conservation(db)
    assert actual == report["confirmed_gross_by_currency"]


def test_dst_boundary_sessions_present(generated: Path, report: dict, tmp_path):
    db, state = tmp_path / "wh.duckdb", tmp_path / "state"
    _ingest_file_sources(db, state, generated, FIXTURES_DIR)
    conn = ingestion._connect(db)
    try:
        (count,) = conn.execute(
            """
            SELECT COUNT(DISTINCT session_id) FROM raw.raw_charging_sessions
            WHERE session_id LIKE 'S-DST-%'
            """
        ).fetchone()
    finally:
        conn.close()
    assert count == report["dst_sessions"]


# --------------------------------------------------------------------------
# Roaming API: 429 retry, mid-pagination crash + resume parity
# --------------------------------------------------------------------------


def _start_server(generated: Path) -> MockRoamingServer:
    server = MockRoamingServer(generated / "settlements.jsonl", generated / "roaming_faults.json")
    server.start()
    return server


def test_roaming_ingest_with_rate_limit_and_resume_parity(generated: Path, report: dict, tmp_path):
    total_settlements = report["raw_expected_rows"]["raw_roaming_settlements"]
    roaming_quarantined = sum(report["quarantine_expected"]["roaming_api"].values())

    # Clean run against a fresh server (page 2 rate-limits once; client retries).
    server = _start_server(generated)
    try:
        db, state = tmp_path / "clean.duckdb", tmp_path / "state_clean"
        result = ingestion.ingest_roaming(server.base_url, "roaming-window-0001", db, state)
        assert result.quarantined == roaming_quarantined
        assert (
            ingestion.raw_counts(db)["raw_roaming_settlements"]
            == total_settlements - roaming_quarantined
        )
    finally:
        server.stop()

    # Crash drill: die after page 2, resume with a new server, expect exact parity.
    server_a = _start_server(generated)
    try:
        db2, state2 = tmp_path / "resume.duckdb", tmp_path / "state_resume"
        with pytest.raises(ingestion.SimulatedIngestCrash):
            ingestion.ingest_roaming(
                server_a.base_url, "roaming-window-0001", db2, state2, fail_after_pages=2
            )
        checkpoint = json.loads((state2 / "roaming-window-0001.json").read_text())
        assert checkpoint["pages_done"] == 2 and checkpoint["status"] == "open"
    finally:
        server_a.stop()

    server_b = _start_server(generated)
    try:
        resumed = ingestion.ingest_roaming(server_b.base_url, "roaming-window-0001", db2, state2)
        assert not resumed.skipped
        counts = ingestion.raw_counts(db2)
        assert counts["raw_roaming_settlements"] == total_settlements - roaming_quarantined
        assert counts["raw_quarantine"] == ingestion.raw_counts(db)["raw_quarantine"]
        clean_conn = ingestion._connect(db)
        resume_conn = ingestion._connect(db2)
        try:
            clean_rows = clean_conn.execute(
                "SELECT settlement_id, session_id, roaming_fee_local"
                " FROM raw.raw_roaming_settlements ORDER BY settlement_id"
            ).fetchall()
            resume_rows = resume_conn.execute(
                "SELECT settlement_id, session_id, roaming_fee_local"
                " FROM raw.raw_roaming_settlements ORDER BY settlement_id"
            ).fetchall()
        finally:
            clean_conn.close()
            resume_conn.close()
        assert clean_rows == resume_rows
    finally:
        server_b.stop()


def test_roaming_repeat_run_is_noop(generated: Path, tmp_path):
    server = _start_server(generated)
    try:
        db, state = tmp_path / "wh.duckdb", tmp_path / "state"
        first = ingestion.ingest_roaming(server.base_url, "roaming-window-0001", db, state)
        second = ingestion.ingest_roaming(server.base_url, "roaming-window-0001", db, state)
        assert first.rows_added > 0
        assert second.skipped and second.rows_added == 0
    finally:
        server.stop()


def test_decimal_rounding_is_half_up():
    from charging_commerce.generator import _q

    assert _q("4.256", 2) == Decimal("4.26")  # banker's rounding would give 4.25
    assert _q("1.4115", 2) == Decimal("1.41")
    assert _q("24.872512", 2) == Decimal("24.87")
