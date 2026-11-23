# E01 · Ingestion and raw layer

**Status:** planned · [Roadmap](../README.md) · [Design](docs/design.md) · [Implementation plan](docs/implementation.md) · [Delivery plan](../docs/delivery-plan.md) · [Data contract](../docs/data-contract.md)

Build the deterministic hybrid data foundation (locked German open-data slices + seeded charging/roaming commerce generator) and the resumable Python ingestion CLI that writes append-only Raw batches with lineage metadata and schema-drift quarantine.

## Deliverables

- Locked open-data fixtures (`BNetzA` Hesse/Frankfurt station slice with `CC BY 4.0` attribution, `SMARD` price/load slice, `ECB` FX rates) with SHA-256 `manifest.json` + optional `--live` refresh helper.
- Seeded generator producing `charging_sessions`, `tariff_plans`, and a mock paginated `roaming_settlements` REST server/client with injected duplicates, 48h late arrivals, rate-limit retries, and schema drift.
- Resumable ingestion CLI (`ingest`) writing Raw DuckDB/Parquet partitions with `_batch_id`, `_ingested_at`, `_source_hash`, routing malformed payloads to `raw_quarantine`.

## Acceptance

1. Re-running `ingest` on the same batch or resuming after an injected mid-pagination crash produces zero duplicate rows and identical manifest checksums.
2. Deliberate schema drift (missing required field or wrong type) is quarantined to `raw_quarantine` with `reject_reason` instead of corrupting Raw tables.
3. All unit, crash-resume, and quarantine tests pass offline via `uv run --locked pytest` and `ruff check .`.
