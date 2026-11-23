# E01 acceptance evidence · Ingestion and raw layer

**Run date (UTC):** 2026-11-23T16:38Z · **Branch:** `feat/data-engineering-e01` (base `main` @ `f342272`, E01 code uncommitted at capture time) · **Outcome: PASS**

## Environment

| Item | Value |
|---|---|
| Python (project venv) | 3.12.13 (`.venv`, `requires-python = ">=3.12,<3.13"`) |
| uv | 0.13.9 |
| duckdb | 2.0.1 |
| pyarrow | 26.0.1 |
| pytest | 9.2.0 |
| ruff | 0.17.6 |
| `uv.lock` SHA-256 | `0c0b80b883bc2fed89a95ce7d1985285848e1d03f288b186d0151f54b8dc5b0d` |
| `fixtures/manifest.json` SHA-256 | `8b49e92b72056f1cf192efd1f22667c43869cb06207d09c1c1b65aabb557f2c9` |

## Locked fixtures (retrieved 2026-11-23, manifest-checked)

| Fixture | Rows | SHA-256 (first 16) | Source |
|---|---|---|---|
| `bnetza_hesse_slice.csv` | 3,233 | `2c1d6eaf1aff319e` | BNetzA Ladesäulenregister `2026-11-12`, CC BY 4.0; slice = Hessen ∩ {Frankfurt am Main, Wiesbaden, Groß-Gerau, Main-Kinzig-Kreis} |
| `smard_prices_slice.csv` | 21,313 | `2be4657c8e8bbd6e` | BNetzA SMARD DE-LU day-ahead prices, 15-min, 2025-10-01..2026-05-11 (via energy-charts API, same license); `grid_load_mwh` empty column (endpoint has no load series) |
| `ecb_fx_slice.csv` | 507 | `9e5f9969e6c4d24d` | ECB Data Portal `EUR/CHF`, `EUR/PLN`, `EUR/USD` daily reference rates (ECB base notation) |

`charging-commerce verify-fixtures` → all checksums + row counts match `manifest.json`.

## Commands (after final edit)

```bash
uv sync --locked --python 3.12
uv run --locked ruff check .            # All checks passed!
uv run --locked ruff format --check .   # clean
uv run --locked pytest -q               # 13 passed in 7.43s
uv run charging-commerce verify-fixtures
uv run charging-commerce generate --out-dir data/generated
uv run charging-commerce ingest {bnetza,tariffs,sessions,smard,ecb} --batch-id <default batch ids>
uv run charging-commerce report
```

## Positive checks — observed row counts

| Batch | Source | rows_added | quarantined |
|---|---|---|---|
| `bnetza-snapshots-0001` | stations `t0/t1/t2` snapshots | 9,699 | 0 |
| `tariffs-t0t1t2-0001` | tariffs `t0/t1/t2` | 18 | 0 |
| `charging-sim-window-0001` | charging session events | 12,728 | 40 |
| `smard-2025-10-2026-05-0001` | SMARD prices | 21,313 | 0 |
| `ecb-2025-09-2026-05-0001` | ECB FX | 507 | 0 |

Generated payload totals: 12,768 session events (12,000 base + 40 DST-boundary + duplicates/late-adjustments/refunds), 3,603 roaming settlements, 9,699 station snapshot rows, 18 tariff snapshot rows.

## Revenue conservation reconciliation (raw side, contract §3.1)

Latest-event-per-session gross sums by currency, quarantined sessions excluded, byte-identical duplicates collapsed:

| Currency | Expected (generation report) | Observed (`charging-commerce report`) | Δ |
|---|---|---|---|
| EUR | 296,732.09 | 296,732.09 | 0.00 |
| CHF | 66,620.52 | 66,620.52 | 0.00 |
| PLN | 172,503.85 | 172,503.85 | 0.00 |

Quarantined rows accounted separately (never inside the sum): `negative_energy_kwh` 25, `invalid_timestamp_order` 15 — both match the seeded expectation exactly.

## Negative drills

| Drill | Command (test) | Observed |
|---|---|---|
| Repeat-run idempotence | `test_repeat_run_is_noop`, `test_roaming_repeat_run_is_noop` | second run `skipped`, `rows_added=0`; raw + quarantine counts unchanged |
| Batch-collision refusal | `test_batch_collision_refused` | `BatchCollisionError` raised for same batch-id with different payload hash |
| Mid-pagination crash + resume | `test_roaming_ingest_with_rate_limit_and_resume_parity` | crash after page 2 with checkpoint persisted (`status=open`); resume completes; settlement rows identical to clean run (settlement_id/session_id/fee compared, 0 diffs) |
| 429 rate-limit retry | same test | mock API rate-limits page index 2 once; client retries and completes all 73 pages |
| Schema-drift quarantine | `test_negative_kwh_and_drift_route_to_quarantine` | 5/5 dirty rows quarantined with exact reasons: `negative_energy_kwh`, `invalid_timestamp_order`, `unexpected_schema_drift`, `null_primary_key`, `invalid_type`; 0 valid rows corrupted |
| DST boundary coverage | `test_dst_boundary_sessions_present` | 40 sessions span the 2025-10-25→26 and 2026-03-28→29 CET/CEST transition nights (UTC) |
| Generator determinism | `test_generator_deterministic` | two `generate` runs → byte-identical SHA-256 for all four payload files |

## Skipped checks and why

- **Roaming ingest via CLI:** requires the in-process mock API server; covered by the test suite (`MockRoamingServer` + `ingest_roaming`). The CLI `ingest roaming --api-url` path shares the same code path.
- **`refresh-open-data --live`:** explicit operator action by design; fixtures are locked and were built once during this stage (checksums above). Not re-run as part of acceptance.
- **`raw_roaming_settlements` in the CLI report run:** intentionally 0 — the CLI smoke run ingests file sources only; roaming counts and the 4 expected roaming quarantine rows are proven in the test suite. The report labels these `MISMATCH` until a roaming batch is ingested; this is disclosed rather than hidden.

## Deviations from design docs (recorded)

1. **RNG:** design says "PCG64 seed"; implementation uses the stdlib `random.Random` (MT19937) seeded generator — deterministic and dependency-free. Determinism, not the RNG family, is the requirement; design wording to be aligned in E02's doc pass.
2. **Fixture slice naming:** implementation plan named `bnetza_hesse_slice.csv` for a "Hesse/Frankfurt" slice; the frozen slice is the Rhein-Main subset of Hessen (4 Kreise, 3,233 stations) to fit the ≤10,000 snapshot-row budget (3,233 × 3 = 9,699).
3. **Data source for SMARD:** direct `smard.de` endpoints rejected non-browser clients and returned 404s during fixture build; prices were retrieved via the Fraunhofer `api.energy-charts.info` feed, which redistributes the same BNetzA SMARD data under CC BY 4.0. Provenance recorded verbatim in `fixtures/manifest.json`.
