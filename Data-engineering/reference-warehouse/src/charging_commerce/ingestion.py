"""Resumable, contract-validating ingestion into append-only DuckDB raw tables (E01).

Every payload record is validated against the frozen schemas of
``docs/data-contract.md`` (v1.2) before it may enter a Raw table; rejected
records land in ``raw_quarantine`` with a deterministic ``reject_reason``.
Batch state files make repeat runs no-ops, refuse hash collisions, and allow
mid-pagination crash/resume with exact row parity.
"""

from __future__ import annotations

import csv
import hashlib
import json
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import UTC, date, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path

import duckdb

REJECT_MISSING_COLUMN = "missing_required_column"
REJECT_SCHEMA_DRIFT = "unexpected_schema_drift"
REJECT_INVALID_TYPE = "invalid_type"
REJECT_NEGATIVE_ENERGY = "negative_energy_kwh"
REJECT_BAD_TIMESTAMP_ORDER = "invalid_timestamp_order"
REJECT_NULL_PK = "null_primary_key"


class BatchCollisionError(RuntimeError):
    """Raised when a known batch-id is replayed with a different payload hash."""


class SimulatedIngestCrash(RuntimeError):
    """Injected failure used by the mid-pagination crash/resume drill."""


@dataclass(frozen=True)
class Column:
    name: str
    kind: str  # varchar | timestamp | date | int | decimal(p,s)
    nullable: bool = False
    pk: bool = False


@dataclass(frozen=True)
class TableSpec:
    table: str
    source_name: str
    columns: tuple[Column, ...]
    rules: tuple[str, ...] = ()  # business rules applied after type parsing


_TIMESTAMP_KEYS = {"session_started_at": "session_ended_at"}  # start must be <= end


def _spec(
    table: str, source_name: str, columns: list[Column], rules: tuple[str, ...] = ()
) -> TableSpec:
    return TableSpec(table=table, source_name=source_name, columns=tuple(columns), rules=rules)


RAW_SCHEMAS: dict[str, TableSpec] = {
    "raw_stations_bnetza": _spec(
        "raw_stations_bnetza",
        "bnetza_open_data",
        [
            Column("station_id", "varchar", pk=True),
            Column("snapshot_date", "date", pk=True),
            Column("operator_name", "varchar"),
            Column("postal_code", "varchar", nullable=True),
            Column("city", "varchar", nullable=True),
            Column("federal_state", "varchar"),
            Column("latitude", "decimal(9,6)", nullable=True),
            Column("longitude", "decimal(9,6)", nullable=True),
            Column("nominal_power_kw", "decimal(10,2)"),
            Column("connector_count", "int"),
            Column("commissioned_date", "date", nullable=True),
        ],
    ),
    "raw_smard_prices": _spec(
        "raw_smard_prices",
        "smard_api",
        [
            Column("timestamp_utc", "timestamp", pk=True),
            Column("market_zone", "varchar", pk=True),
            Column("wholesale_eur_mwh", "decimal(10,4)"),
            Column("grid_load_mwh", "decimal(12,2)", nullable=True),
        ],
    ),
    "raw_ecb_fx_rates": _spec(
        "raw_ecb_fx_rates",
        "ecb_portal",
        [
            Column("currency_pair", "varchar", pk=True),
            Column("observation_date", "date", pk=True),
            Column("rate", "decimal(12,6)"),
        ],
    ),
    "raw_tariff_plans": _spec(
        "raw_tariff_plans",
        "charging_sim",
        [
            Column("tariff_id", "varchar", pk=True),
            Column("snapshot_date", "date", pk=True),
            Column("price_per_kwh_eur", "decimal(10,4)"),
            Column("roaming_surcharge_eur", "decimal(10,2)"),
            Column("plan_tier", "varchar"),
        ],
    ),
    "raw_charging_sessions": _spec(
        "raw_charging_sessions",
        "charging_sim",
        [
            Column("session_id", "varchar", pk=True),
            Column("event_seq", "int", pk=True),
            Column("station_id", "varchar"),
            Column("tariff_id", "varchar"),
            Column("country_code", "varchar"),
            Column("currency_code", "varchar"),
            Column("session_started_at", "timestamp"),
            Column("session_ended_at", "timestamp"),
            Column("settled_at", "timestamp"),
            Column("energy_kwh", "decimal(12,4)"),
            Column("gross_amount_local", "decimal(12,2)"),
            Column("event_type", "varchar"),
        ],
        rules=("negative_energy", "timestamp_order"),
    ),
    "raw_roaming_settlements": _spec(
        "raw_roaming_settlements",
        "roaming_api",
        [
            Column("settlement_id", "varchar", pk=True),
            Column("session_id", "varchar"),
            Column("roaming_partner", "varchar"),
            Column("roaming_fee_local", "decimal(12,2)"),
            Column("currency_code", "varchar"),
            Column("settled_at", "timestamp"),
        ],
    ),
}

QUARANTINE_COLUMNS = (
    Column("quarantine_id", "varchar"),
    Column("_batch_id", "varchar"),
    Column("_source_name", "varchar"),
    Column("raw_payload_json", "varchar"),
    Column("reject_reason", "varchar"),
    Column("quarantined_at", "timestamp"),
)

LINEAGE_COLUMNS = ("_batch_id", "_ingested_at", "_source_name", "_source_hash")
LINEAGE_TYPES = ("VARCHAR", "TIMESTAMP", "VARCHAR", "VARCHAR")

# Ingest source key -> payload filename (generated payloads or locked fixtures).
SOURCE_PAYLOADS = {
    "bnetza": "stations_snapshots.jsonl",
    "tariffs": "tariffs_snapshots.jsonl",
    "sessions": "charging_sessions.jsonl",
    "smard": "smard_prices_slice.csv",
    "ecb": "ecb_fx_slice.csv",
}
GENERATED_SOURCES = frozenset(("bnetza", "tariffs", "sessions"))
SOURCE_TABLES = {
    "bnetza": "raw_stations_bnetza",
    "tariffs": "raw_tariff_plans",
    "sessions": "raw_charging_sessions",
    "smard": "raw_smard_prices",
    "ecb": "raw_ecb_fx_rates",
    "roaming": "raw_roaming_settlements",
}


def _sql_type(kind: str) -> str:
    if kind == "varchar":
        return "VARCHAR"
    if kind == "timestamp":
        return "TIMESTAMP"
    if kind == "date":
        return "DATE"
    if kind == "int":
        return "INTEGER"
    if kind.startswith("decimal"):
        return kind.upper()
    raise ValueError(kind)


def ensure_schema(conn: duckdb.DuckDBPyConnection) -> None:
    conn.execute("CREATE SCHEMA IF NOT EXISTS raw")
    lineage_ddl = ", ".join(
        f"{name} {kind}" for name, kind in zip(LINEAGE_COLUMNS, LINEAGE_TYPES, strict=True)
    )
    for spec in RAW_SCHEMAS.values():
        cols = ", ".join(f"{c.name} {_sql_type(c.kind)}" for c in spec.columns)
        conn.execute(f"CREATE TABLE IF NOT EXISTS raw.{spec.table} ({cols}, {lineage_ddl})")
    cols = ", ".join(f"{c.name} {_sql_type(c.kind)}" for c in QUARANTINE_COLUMNS)
    conn.execute(f"CREATE TABLE IF NOT EXISTS raw.raw_quarantine ({cols})")


# --------------------------------------------------------------------------
# Validation
# --------------------------------------------------------------------------


def _parse_value(kind: str, raw):
    if kind == "varchar":
        return str(raw)
    if kind == "timestamp":
        text = str(raw).strip()
        if text.endswith("Z"):
            text = text[:-1] + "+00:00"
        moment = datetime.fromisoformat(text)
        if moment.tzinfo is not None:
            moment = moment.astimezone(UTC).replace(tzinfo=None)
        return moment
    if kind == "date":
        return date.fromisoformat(str(raw).strip())
    if kind == "int":
        return int(str(raw).strip())
    if kind.startswith("decimal"):
        return Decimal(str(raw).strip())
    raise ValueError(kind)


def validate_record(spec: TableSpec, record: dict) -> tuple[dict | None, str | None]:
    """Validate one payload record against the contract.

    Returns ``(typed_values, None)`` when valid, or ``(None, reject_reason)``
    when the record must be quarantined.
    """
    names = {c.name for c in spec.columns}
    pk_absent = [c.name for c in spec.columns if c.pk and c.name not in record]
    if pk_absent:
        return None, REJECT_MISSING_COLUMN
    pk_null = [c.name for c in spec.columns if c.pk and record[c.name] in (None, "")]
    if pk_null:
        return None, REJECT_NULL_PK
    missing = [c.name for c in spec.columns if c.name not in record or record[c.name] in (None, "")]
    if any(c.name in missing for c in spec.columns if not c.nullable):
        return None, REJECT_MISSING_COLUMN
    unexpected = [k for k in record if k not in names]
    if unexpected:
        return None, REJECT_SCHEMA_DRIFT

    typed: dict[str, object] = {}
    for column in spec.columns:
        if column.name in missing:  # nullable column absent/empty
            typed[column.name] = None
            continue
        try:
            typed[column.name] = _parse_value(column.kind, record[column.name])
        except (ValueError, InvalidOperation, ArithmeticError):
            return None, REJECT_INVALID_TYPE

    if "negative_energy" in spec.rules and typed["energy_kwh"] < 0:
        return None, REJECT_NEGATIVE_ENERGY
    if "timestamp_order" in spec.rules:
        start_key, end_key = next(iter(_TIMESTAMP_KEYS.items()))
        if typed[end_key] < typed[start_key]:
            return None, REJECT_BAD_TIMESTAMP_ORDER
    return typed, None


# --------------------------------------------------------------------------
# Batch state (idempotency, collision guard, resume checkpoints)
# --------------------------------------------------------------------------


def _state_path(state_dir: Path, batch_id: str) -> Path:
    return state_dir / f"{batch_id}.json"


def _load_state(state_dir: Path, batch_id: str) -> dict | None:
    path = _state_path(state_dir, batch_id)
    return json.loads(path.read_text()) if path.is_file() else None


def _save_state(state_dir: Path, state: dict) -> None:
    state_dir.mkdir(parents=True, exist_ok=True)
    path = _state_path(state_dir, state["batch_id"])
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(state, indent=2) + "\n")
    tmp.replace(path)


@dataclass
class IngestResult:
    batch_id: str
    rows_added: int
    quarantined: int
    skipped: bool = False
    pages_done: int = 0


# --------------------------------------------------------------------------
# DuckDB plumbing
# --------------------------------------------------------------------------


def _connect(db_path: Path) -> duckdb.DuckDBPyConnection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = duckdb.connect(str(db_path))
    ensure_schema(conn)
    return conn


def _arrow_type(kind: str):
    import pyarrow as pa

    if kind == "varchar":
        return pa.string()
    if kind == "timestamp":
        return pa.timestamp("us")
    if kind == "date":
        return pa.date32()
    if kind == "int":
        return pa.int32()
    if kind.startswith("decimal"):
        precision, scale = (int(part) for part in kind[8:-1].split(","))
        return pa.decimal128(precision, scale)
    raise ValueError(kind)


def _decimal_scale(kind: str) -> int:
    return int(kind.removeprefix("decimal(").rstrip(")").split(",")[1])


def _insert_valid(conn, spec: TableSpec, rows: list[dict], lineage: dict) -> int:
    """Columnar insert: stage the batch as an Arrow table, then INSERT .. SELECT.

    DuckDB's row-wise ``executemany`` costs ~1 ms/row; the Arrow path inserts
    tens of thousands of rows in well under a second.
    """
    if not rows:
        return 0
    from decimal import Decimal as _Decimal

    import pyarrow as pa

    names: list[str] = []
    arrays: list = []
    for column in spec.columns:
        values = [row[column.name] for row in rows]
        if column.kind.startswith("decimal"):
            scale = _decimal_scale(column.kind)
            values = [
                value.quantize(_Decimal(1).scaleb(-scale)) if value is not None else None
                for value in values
            ]
        names.append(column.name)
        arrays.append(pa.array(values, type=_arrow_type(column.kind)))
    lineage_types = (pa.string(), pa.timestamp("us"), pa.string(), pa.string())
    for name, arrow_type in zip(LINEAGE_COLUMNS, lineage_types, strict=True):
        names.append(name)
        arrays.append(pa.array([lineage[name]] * len(rows), type=arrow_type))

    table = pa.Table.from_arrays(arrays, names=names)
    conn.register("_staging_batch", table)
    try:
        cols = ", ".join(table.column_names)
        conn.execute(f"INSERT INTO raw.{spec.table} ({cols}) SELECT {cols} FROM _staging_batch")
    finally:
        conn.unregister("_staging_batch")
    return len(rows)


def _insert_quarantined(
    conn, batch_id: str, source_name: str, quarantined: list[tuple[str, str]], ingested_at
) -> int:
    if not quarantined:
        return 0
    cols = [c.name for c in QUARANTINE_COLUMNS]
    placeholders = ", ".join("?" for _ in cols)
    params = [
        [
            hashlib.sha256(f"{batch_id}|{source_name}|{payload}".encode()).hexdigest(),
            batch_id,
            source_name,
            payload,
            reason,
            ingested_at,
        ]
        for payload, reason in quarantined
    ]
    conn.executemany(
        f"INSERT INTO raw.raw_quarantine ({', '.join(cols)}) VALUES ({placeholders})", params
    )
    return len(quarantined)


def _persist(
    conn, spec: TableSpec, records: list[dict], lineage: dict, batch_id: str, ingested_at
) -> tuple[int, int]:
    valid: list[dict] = []
    quarantined: list[tuple[str, str]] = []
    for record in records:
        typed, reason = validate_record(spec, record)
        if reason is None:
            valid.append(typed)
        else:
            quarantined.append((json.dumps(record, sort_keys=True), reason))
    conn.execute("BEGIN")
    try:
        rows_added = _insert_valid(conn, spec, valid, lineage)
        rows_quarantined = _insert_quarantined(
            conn, batch_id, spec.source_name, quarantined, ingested_at
        )
        conn.execute("COMMIT")
    except Exception:
        conn.execute("ROLLBACK")
        raise
    return rows_added, rows_quarantined


# --------------------------------------------------------------------------
# File ingestion
# --------------------------------------------------------------------------


def ingest_file(
    source_key: str,
    payload_path: Path,
    batch_id: str,
    db_path: Path,
    state_dir: Path,
) -> IngestResult:
    """Ingest a CSV or JSONL payload into its raw table (idempotent per batch)."""
    spec = RAW_SCHEMAS[SOURCE_TABLES[source_key]]
    payload_hash = hashlib.sha256(payload_path.read_bytes()).hexdigest()
    state = _load_state(state_dir, batch_id)
    if state and state.get("status") == "completed":
        if state.get("payload_hash") != payload_hash:
            raise BatchCollisionError(
                f"batch {batch_id!r} already ingested with a different payload hash"
            )
        return IngestResult(batch_id, 0, 0, skipped=True)

    suffix = payload_path.suffix.lower()
    records: list[dict]
    if suffix == ".jsonl":
        records = [
            json.loads(line) for line in payload_path.read_text().splitlines() if line.strip()
        ]
        header_drift = _jsonl_header_drift(spec, records)
    elif suffix == ".csv":
        with payload_path.open(newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            header_drift = _csv_header_drift(spec, reader.fieldnames or [])
            records = [dict(row) for row in reader]
    else:
        raise ValueError(f"unsupported payload format: {suffix}")

    ingested_at = datetime.now(UTC).replace(tzinfo=None)
    lineage = {
        "_batch_id": batch_id,
        "_ingested_at": ingested_at,
        "_source_name": spec.source_name,
        "_source_hash": payload_hash,
    }
    conn = _connect(db_path)
    try:
        if header_drift:
            # File-level schema drift: no record can be trusted; quarantine all rows.
            payloads = [(json.dumps(record, sort_keys=True), header_drift[1]) for record in records]
            conn.execute("BEGIN")
            _insert_quarantined(conn, batch_id, spec.source_name, payloads, ingested_at)
            conn.execute("COMMIT")
            rows_added, quarantined = 0, len(payloads)
        else:
            rows_added, quarantined = _persist(conn, spec, records, lineage, batch_id, ingested_at)
    finally:
        conn.close()

    _save_state(
        state_dir,
        {
            "batch_id": batch_id,
            "source_key": source_key,
            "payload_hash": payload_hash,
            "rows_added": rows_added,
            "quarantined": quarantined,
            "status": "completed",
        },
    )
    return IngestResult(batch_id, rows_added, quarantined)


def _csv_header_drift(spec: TableSpec, fieldnames: list[str]) -> tuple[str, str] | None:
    names = {c.name for c in spec.columns}
    missing = [c.name for c in spec.columns if c.name not in fieldnames]
    if missing:
        return json.dumps({"missing_columns": missing}), REJECT_MISSING_COLUMN
    extra = [name for name in fieldnames if name not in names]
    if extra:
        return json.dumps({"unexpected_columns": extra}), REJECT_SCHEMA_DRIFT
    return None


def _jsonl_header_drift(spec: TableSpec, records: list[dict]) -> tuple[str, str] | None:
    return None  # per-record key checks in validate_record cover JSONL drift


# --------------------------------------------------------------------------
# Roaming API ingestion (paginated, resumable, 429-tolerant)
# --------------------------------------------------------------------------


def _fetch_page(base_url: str, cursor: int, max_attempts: int, backoff_s: float) -> bytes:
    url = f"{base_url}/v1/settlements?cursor={cursor}"
    for attempt in range(1, max_attempts + 1):
        try:
            with urllib.request.urlopen(url, timeout=30) as resp:  # noqa: S310 - test-local mock API
                return resp.read()
        except urllib.error.HTTPError as exc:
            if exc.code == 429 and attempt < max_attempts:
                time.sleep(backoff_s * attempt)
                continue
            raise
    raise RuntimeError("unreachable")


def ingest_roaming(
    base_url: str,
    batch_id: str,
    db_path: Path,
    state_dir: Path,
    *,
    fail_after_pages: int | None = None,
    max_attempts: int = 3,
    backoff_s: float = 0.05,
) -> IngestResult:
    """Ingest roaming settlements from the paginated mock API with resume support.

    A checkpoint is persisted atomically after every committed page, so a crash
    (or the injected ``fail_after_pages`` drill) resumes exactly where it
    stopped, producing row parity with an uninterrupted run.
    """
    spec = RAW_SCHEMAS["raw_roaming_settlements"]
    state = _load_state(state_dir, batch_id) or {
        "batch_id": batch_id,
        "source_key": "roaming",
        "status": "open",
        "cursor": 0,
        "pages_done": 0,
        "page_hashes": [],
        "rows_added": 0,
        "quarantined": 0,
    }
    if state.get("status") == "completed":
        return IngestResult(batch_id, 0, 0, skipped=True, pages_done=state["pages_done"])

    cursor, pages_done = state["cursor"], state["pages_done"]
    page_hashes: list[str] = list(state["page_hashes"])
    conn = _connect(db_path)
    try:
        while True:
            body = _fetch_page(base_url, cursor, max_attempts, backoff_s)
            page_hash = hashlib.sha256(body).hexdigest()
            page = json.loads(body)
            records = page["settlements"]
            ingested_at = datetime.now(UTC).replace(tzinfo=None)
            lineage = {
                "_batch_id": batch_id,
                "_ingested_at": ingested_at,
                "_source_name": spec.source_name,
                "_source_hash": page_hash,
            }
            rows_added, quarantined = _persist(conn, spec, records, lineage, batch_id, ingested_at)
            state["rows_added"] += rows_added
            state["quarantined"] += quarantined
            page_hashes.append(page_hash)
            pages_done += 1
            next_cursor = page["next_cursor"]
            state.update(
                {
                    "cursor": next_cursor or 0,
                    "pages_done": pages_done,
                    "page_hashes": page_hashes,
                    "finished": next_cursor is None,
                }
            )
            _save_state(state_dir, state)
            if (
                fail_after_pages is not None
                and pages_done >= fail_after_pages
                and next_cursor is not None
            ):
                raise SimulatedIngestCrash(
                    f"injected crash after {pages_done} pages of batch {batch_id!r} "
                    "(checkpoint persisted)"
                )
            if next_cursor is None:
                break
            cursor = next_cursor
    finally:
        conn.close()

    payload_hash = hashlib.sha256("".join(page_hashes).encode()).hexdigest()
    state.update({"status": "completed", "payload_hash": payload_hash, "finished": True})
    _save_state(state_dir, state)
    return IngestResult(batch_id, state["rows_added"], state["quarantined"], pages_done=pages_done)


# --------------------------------------------------------------------------
# Raw-level reconciliation (E01 acceptance)
# --------------------------------------------------------------------------


def raw_counts(db_path: Path) -> dict[str, int]:
    conn = _connect(db_path)
    try:
        tables = [*RAW_SCHEMAS, "raw_quarantine"]
        return {t: conn.execute(f"SELECT COUNT(*) FROM raw.{t}").fetchone()[0] for t in tables}
    finally:
        conn.close()


def quarantine_by_reason(db_path: Path) -> dict[str, int]:
    conn = _connect(db_path)
    try:
        rows = conn.execute(
            "SELECT reject_reason, COUNT(*) FROM raw.raw_quarantine GROUP BY reject_reason"
        ).fetchall()
        return {reason: count for reason, count in rows}
    finally:
        conn.close()


def raw_conservation(db_path: Path) -> dict[str, str]:
    """Latest-event-per-session gross sums by currency (contract §3.1, raw side).

    Sessions whose surviving raw rows were all quarantined contribute nothing;
    byte-identical duplicates collapse via the max-``event_seq``-per-session rule.
    """
    conn = _connect(db_path)
    try:
        quarantined_sessions = {
            row[0]
            for row in conn.execute(
                "SELECT json_extract_string(raw_payload_json, '$.session_id')"
                " FROM raw.raw_quarantine WHERE _source_name = 'charging_sim'"
            ).fetchall()
            if row[0] is not None
        }
        rows = conn.execute(
            """
            SELECT currency_code, gross_amount_local, event_seq, session_id
            FROM raw.raw_charging_sessions
            """
        ).fetchall()
    finally:
        conn.close()

    latest: dict[str, tuple[int, str, str]] = {}  # session_id -> (event_seq, currency, gross)
    for currency, gross, event_seq, session_id in rows:
        if session_id in quarantined_sessions:
            continue
        if session_id not in latest or event_seq > latest[session_id][0]:
            latest[session_id] = (event_seq, currency, gross)

    totals: dict[str, Decimal] = {}
    for _, currency, gross in latest.values():
        totals[currency] = totals.get(currency, Decimal("0")) + gross
    return {currency: f"{total:.2f}" for currency, total in sorted(totals.items())}
