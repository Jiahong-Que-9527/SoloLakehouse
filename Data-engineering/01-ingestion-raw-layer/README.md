# E01 · Ingestion and raw layer

**Status:** implemented (acceptance evidence recorded, pending owner review) · [Roadmap](../README.md) · [Design](docs/design.md) · [Implementation plan](docs/implementation.md) · [Delivery plan](../docs/delivery-plan.md) · [Data contract](../docs/data-contract.md) · [Evidence](evidence/e01-acceptance.md)

Build the deterministic hybrid data foundation (locked German open-data slices + seeded charging/roaming commerce generator) and the resumable Python ingestion CLI that writes append-only Raw batches with lineage metadata and schema-drift quarantine.

## Deliverables

- Locked open-data fixtures (`BNetzA` Hesse/Rhein-Main station slice with `CC BY 4.0` attribution, `SMARD` price slice, `ECB` FX rates) with SHA-256 `manifest.json` + opt-in `--live` refresh helper — see `reference-warehouse/fixtures/`.
- Seeded generator producing `charging_sessions`, `tariff_plans`, station `t0/t1/t2` snapshots, and an in-process mock paginated `roaming_settlements` REST server/client with injected duplicates, 48h late arrivals, refunds, DST-boundary sessions, rate-limit retries, and schema drift — `reference-warehouse/src/charging_commerce/generator.py`.
- Resumable ingestion CLI writing append-only Raw DuckDB tables with `_batch_id`, `_ingested_at`, `_source_name`, `_source_hash`, routing malformed payloads to `raw_quarantine` — `reference-warehouse/src/charging_commerce/{ingestion,cli}.py`.

## Quick verification (offline, no cloud account)

```bash
cd Data-engineering/reference-warehouse
uv sync --locked --python 3.12
uv run --locked ruff check . && uv run --locked ruff format --check .
uv run --locked pytest -q            # 13 tests incl. crash/resume + collision drills
uv run charging-commerce verify-fixtures
uv run charging-commerce generate --out-dir data/generated
uv run charging-commerce ingest bnetza  --batch-id bnetza-snapshots-0001
uv run charging-commerce ingest tariffs --batch-id tariffs-t0t1t2-0001
uv run charging-commerce ingest sessions --batch-id charging-sim-window-0001
uv run charging-commerce ingest smard   --batch-id smard-2025-10-2026-05-0001
uv run charging-commerce ingest ecb     --batch-id ecb-2025-09-2026-05-0001
uv run charging-commerce report
```

## Acceptance

1. Re-running `ingest` on the same batch or resuming after an injected mid-pagination crash produces zero duplicate rows and exact row parity (verified in `test_repeat_run_is_noop` and `test_roaming_ingest_with_rate_limit_and_resume_parity`).
2. Deliberate schema drift (missing required field, unexpected field, wrong type, null key, negative kWh, inverted timestamps) is quarantined to `raw_quarantine` with the exact `reject_reason` (verified in `test_negative_kwh_and_drift_route_to_quarantine`).
3. All unit, crash-resume, and quarantine tests pass offline via `uv run --locked pytest` and `ruff check .` (13 passed, lint clean — see [evidence](evidence/e01-acceptance.md)).

## Scope notes

- The roaming source ingests from the in-process mock API (`MockRoamingServer`), exercised by the test suite; the CLI `ingest roaming` path expects `--api-url`.
- `refresh-open-data --live` re-downloads sources and rebuilds the fixture slice; it is an explicit operator action and was **not** run as part of acceptance (fixtures are locked).
