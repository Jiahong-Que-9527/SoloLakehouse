# Implementation plan: E01 · Ingestion and raw layer

**Status:** planned. [Brief](../README.md) · [Design](design.md) · [Delivery plan](../../docs/delivery-plan.md)

## First delivery

Deliver `reference-warehouse/` as an installable Python 3.12 `uv` package with locked German open-data fixtures, a deterministic commerce + mock roaming API generator, and a resumable `charging-commerce ingest` CLI verified offline with `pytest` and `ruff`.

## Files and modules to create or update

- `Data-engineering/reference-warehouse/pyproject.toml` & `uv.lock`
- `Data-engineering/reference-warehouse/fixtures/` (`bnetza_hesse_slice.csv`, `smard_prices_slice.csv`, `ecb_fx_slice.csv`, `manifest.json`)
- `Data-engineering/reference-warehouse/src/charging_commerce/__init__.py`
- `Data-engineering/reference-warehouse/src/charging_commerce/open_data.py`
- `Data-engineering/reference-warehouse/src/charging_commerce/generator.py`
- `Data-engineering/reference-warehouse/src/charging_commerce/ingestion.py`
- `Data-engineering/reference-warehouse/src/charging_commerce/cli.py`
- `Data-engineering/reference-warehouse/tests/test_ingestion.py`
- `.gitignore` (ignore `*.duckdb`, local runtime state under `Data-engineering/reference-warehouse/data/`, while allowing `fixtures/*.csv`)
- `Data-engineering/01-ingestion-raw-layer/evidence/e01-acceptance.md`

## Implementation sequence

1. **Package & fixture lock:** Initialize `pyproject.toml` (`requires-python = ">=3.12,<3.13"`, `duckdb`, `pyarrow`, `pytest`, `ruff`), download or extract the locked BNetzA Hesse/Frankfurt (`CC BY 4.0`), SMARD, and ECB slices into `fixtures/`, and compute `fixtures/manifest.json` SHA-256 digests.
2. **Deterministic generator (`generator.py`):** Implement seeded generation of `raw_tariff_plans` (`t0/t1/t2`), `raw_stations_bnetza` (`t0/t1/t2` upgrades anchored to real BNetzA IDs), `raw_charging_sessions` (dups, 48h late arrivals, negative-kWh dirty rows, refunds, DST edge cases), and a local HTTP/in-process mock paginated roaming API (`429` retry + schema drift).
3. **Contract validation & quarantine (`ingestion.py`):** Validate incoming payloads against [data-contract.md](../../docs/data-contract.md), attach `_batch_id`/`_ingested_at`/`_source_name`/`_source_hash`, and route invalid rows to `raw_quarantine` with deterministic `quarantine_id` and `reject_reason`.
4. **Resumable CLI (`cli.py`):** Implement `charging-commerce generate`, `charging-commerce ingest`, and `charging-commerce refresh-open-data --live` (opt-in only), with cursor checkpointing and batch-hash collision guards.
5. **Tests & acceptance record:** Write `tests/test_ingestion.py` covering manifest checksums, repeat-run idempotence, mid-pagination crash + resume parity, schema-drift quarantine, and batch-collision refusal; record outputs in `evidence/e01-acceptance.md`.

## Verification commands and negative drills

```bash
cd Data-engineering/reference-warehouse
uv sync --locked --python 3.12
uv run --locked ruff check .
uv run --locked ruff format --check .
uv run --locked pytest tests/test_ingestion.py -v
```

**Negative drills to verify in tests & CLI:**
- Inject a mid-pagination failure on page 2, resume, and verify exact row parity against a clean run.
- Submit a modified payload under an existing `--batch-id` and verify non-zero collision failure.
- Submit a drifted roaming JSON record and negative-kWh session and verify landing in `raw_quarantine`.

## Acceptance evidence

Record in `01-ingestion-raw-layer/evidence/e01-acceptance.md`: git commit SHA, `uv.lock` SHA-256, `fixtures/manifest.json` checksums, row counts per Raw table and `raw_quarantine` by `reject_reason`, and exact outputs of the crash-resume and collision drills.
