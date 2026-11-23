# Design: E01 · Ingestion and raw layer

**E01 · Design specification (planned).** [Brief](../README.md) · [Implementation plan](implementation.md)

Build the deterministic hybrid data foundation (`BNetzA` public charging stations `CC BY 4.0`, `SMARD` wholesale prices, `ECB` daily FX, seeded EV charging sessions, and a mock paginated roaming REST API) plus a resumable Python ingestion CLI writing append-only Raw tables and routing malformed/drifted payloads to `raw_quarantine`.

## 1. Decisions

| Topic | Decision |
|---|---|
| Python & tooling | Python `>=3.12,<3.13` managed by `uv`, `pytest`, `ruff`, `duckdb`, `pyarrow` |
| Open-data handling | Locked regional slices + SHA-256 `fixtures/manifest.json` for offline CI; opt-in `--live` refresh script |
| BNetzA scope | Hesse / Frankfurt regional slice (`CC BY 4.0`) + `t0/t1/t2` snapshots for E04 SCD2 |
| Commerce generator | Deterministic PCG64 seed anchored to real `BNetzA` `station_id` values |
| Injected faults | Duplicate events, 48h late settlements, negative-kWh dirty rows, CET/CEST DST transitions, API `429` retry, mid-page crash, schema drift |
| Idempotency & resume | Page/file checkpoint state + `_batch_id` / `_source_hash` guard; repeat runs add 0 rows |
| Quarantine | Malformed/drifted records go to `raw_quarantine` with `reject_reason`; Raw tables stay clean |

## 2. Scope boundary

In scope: locked fixtures + attribution, seeded commerce + roaming API generator, resumable `ingest` CLI, Raw DuckDB/Parquet writer, `raw_quarantine`, and offline unit/resume/quarantine tests.

Out of scope: dbt models (`E02`), dbt testing/contracts (`E03`), BigQuery upload (`E06`), and Airflow scheduling (`E07`).

## 3. Architecture

```text
Locked fixtures (BNetzA/SMARD/ECB) + Seeded generator (sessions/tariffs/roaming API)
        |
        v  charging-commerce ingest --batch-id ... --state-dir ...
  [Schema & Type Gate]
        |-- valid ---------> Raw tables (raw_stations_bnetza, raw_smard_prices,
        |                    raw_ecb_fx_rates, raw_charging_sessions,
        |                    raw_roaming_settlements, raw_tariff_plans)
        '-- malformed/drift -> raw_quarantine (quarantine_id, reject_reason, raw_payload_json)
```

## 4. Contracts and configuration

- Exact column schemas and `reject_reason` enum values are frozen in [data-contract.md](../../docs/data-contract.md).
- `fixtures/manifest.json` records `source_url`, `license`, `retrieval_date`, `sha256`, and `row_count` for every locked open-data file.
- Every Raw table appends `_batch_id`, `_ingested_at`, `_source_name`, `_source_hash`.

## 5. Behaviour and edge cases

1. Repeating `ingest` with the same `--batch-id` and identical `_source_hash` is a verified no-op (`rows_added == 0`).
2. Repeating the same `--batch-id` with a different `_source_hash` raises a batch-collision error rather than silently overwriting.
3. Stopping `ingest` mid-pagination after page 2 of 5 saves cursor state; resuming collects pages 3–5 and produces exact row parity with an uninterrupted run.
4. Schema drift (missing required column or unexpected field type) routes affected records to `raw_quarantine` without corrupting valid records or crashing the entire batch unless the drift rate exceeds the configured abort threshold.

## 6. Delivery and cost

100% local execution in Python 3.12 + DuckDB/Parquet (`€0`). Raw output databases and checkpoint files stay outside Git (ignored via `.gitignore`).

## 7. Acceptance criteria

1. Deterministic generator + locked fixtures pass checksum and schema verification offline.
2. Crash-resume and repeat-run tests verify zero duplicate rows and exact parity.
3. Schema-drift and negative-kWh dirty rows land in `raw_quarantine` with expected `reject_reason`, and raw gross + quarantine totals reconcile to the seeded expectation.

## 8. Handoff

`E02` reads the DuckDB Raw tables produced by `charging-commerce ingest` as `dbt` `sources` (`loaded_at_field: _ingested_at`).
