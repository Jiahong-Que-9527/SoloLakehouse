# SoloLakehouse Assessment: Soundness as a Lakehouse and End-to-End Viability of the DAX/ECB Pipeline

> **Assessment goal**: judge whether SoloLakehouse is a *sound lakehouse reference implementation*, and whether the ECB (main refinancing rate) + DAX (German equity index) sources can run **completely** through Bronze → Silver → Gold → ML. Where the implementation is incomplete or non-idiomatic, propose concrete remedies.
>
> **Assessment date**: 2026-04-17
> **Baseline assessed**: `main` (v2.5 single-track runtime)
> **Scope**: architectural soundness / end-to-end executability / data and modelling soundness / operability

> ## Status update — 2026-07-31
>
> This report was written against the **pre-ADR-020** codebase, when Bronze and
> Silver were Parquet files and the Iceberg Gold table was rebuilt through Trino
> `DROP TABLE + CTAS`. Several findings have since been resolved. Read the
> report with this table applied:
>
> | Finding | Status today |
> |---|---|
> | **P2** — Iceberg Gold loses snapshot history (`DROP + CTAS`) | **Resolved** by ADR-020. All three layers are now written natively through pyiceberg (`append_table` / `overwrite_table`); the Trino write path was removed. Snapshots are retained. |
> | **P5** — Silver/Gold have no versioning | **Resolved** by ADR-020 — Iceberg snapshots provide this. |
> | **P4** — Asset check density too low | **Partly addressed** in v2.6: `governance/datasets/*.yaml` contracts declare `quality_rules`, enforced by `governance/quality.py` and `make validate-contracts`. Freshness and schema checks per the recommendation below are still open. |
> | **P1** — DAX is a static committed CSV | **Still open.** |
> | **P3** — Idempotency keyed on date, not content fingerprint | **Still open.** |
> | **P6** — Rejected records have no governance loop | **Still open.** |
> | **P7** — ECB source uses only the MRO rate | **Still open.** |
> | **P8** — No SLO/alerting | **Still open**, scoped to v2.9. |
> | **§7** — dbt/Spark compute migration | **Still proposed** (ADR-016); not scheduled into any version. |

---

## 1. Conclusion (TL;DR)

| Dimension | Verdict | Notes |
|------|------|------|
| Is this a *sound lakehouse project*? | **Yes** (reference-grade, not production-grade) | It has every characteristic lakehouse layer: object storage, open table format, unified metadata, separated compute, orchestration, ML, catalog, and BI. |
| Can ECB+DAX run end to end **in one pass**? | **Yes, but "complete" needs a caveat** | `make setup` + `make demo` runs `bronze → silver → gold` and verifies Gold through Trino; `make pipeline` additionally runs the MLflow stage. However the DAX data stops at 2024-12-31, comes from a local static CSV rather than a live/incremental source, and its values diverge noticeably from the real DAX index. |
| Is this a *production-ready lakehouse*? | **No** | v2.5 is explicitly a reference/demo baseline. Production readiness is scoped to v3.0 (K8s/Helm/Terraform + environment promotion + secrets governance + SLO). Today it is "feature-complete and well-engineered, but without runtime guarantees". |

One-line positioning: **a single-node lakehouse reference implementation with unusually good engineering discipline — solid for teaching and demonstration; but genuinely trustworthy end-to-end operation still requires fixing the DAX source, quality gates, Silver partitioning, and operational observability.**

---

## 2. Architectural soundness

### 2.1 Are the core lakehouse elements present?

The defining marks of a lakehouse are **open table format + object storage + separated compute + unified metadata + medallion layering**. This project maps as follows:

| Lakehouse element | Implementation here | Soundness |
|--------------|-----------|--------|
| Object storage | MinIO (S3-compatible) | Sound — open S3 semantics |
| Open table format | Apache Iceberg across all layers via pyiceberg *(ADR-020; was Gold-only at assessment time)* | Sound |
| Unified metadata | Apache Hive Metastore (shared by the Hive and Iceberg catalogs) | Sound for a single node |
| Separated compute | Trino for queries + Python/pandas for transformations, orchestrated by Dagster | Sound, though Silver transformations running in pandas rather than Trino is a reference-implementation trade-off |
| Medallion layering | Bronze/Silver/Gold cleanly separated, each with its own namespace | Sound |
| Orchestration | Dagster (asset-aware, with schedule / sensor / asset check) | **Strong** — assets, checks, sensors, and schedules are all present |
| ML tracking | MLflow (PostgreSQL + MinIO artifact store) | Sound |
| Data catalog | OpenMetadata | Sound |
| BI / query UI | Superset (on Trino) | Sound |
| Validation layer | Pydantic v2 + custom Bronze quality checks | Sound — fail-fast is explicit |

> Conclusion: **the architecture is a sound lakehouse reference implementation.** The five-layer model (Sources → Ingestion → Medallion → Query → ML) plus three platform services (orchestration / catalog / BI) are all present, and the format decisions are recorded in `ADR-003` / `ADR-013` / `ADR-020`.

### 2.2 Where it looks like a lakehouse without fully delivering one

These are places where the **concept is right but the implementation is simplified**. Not fatal, but they affect any maturity judgement.

1. **Bronze is genuinely partitioned; Silver and Gold are not.**
   - Bronze appends immutably, day-partitioned on `_ingestion_timestamp` — correct medallion behaviour.
   - Silver and Gold are fully overwritten on every run. Iceberg snapshots preserve history, but there is no partitioning strategy and no incremental semantics.

2. **Silver transformations happen inside a pandas process, not in Trino SQL.**
   - Reasonable for a reference implementation, but it is the bottleneck once data volume grows.
   - Readers should understand this is a deliberate simplification, not how a lakehouse must work.

3. **`rate_change_bps` is recomputed over full history at the Silver layer, with no watermark or incrementality contract.**
   - Every Silver run merges all Bronze data and recomputes from scratch. Wasteful but idempotent, so acceptable at this scale; it becomes a problem as volume grows.

### 2.3 Engineering discipline

This is noticeably better than a typical personal demo project:

- complete ADR record (001–020) with decisions traceable
- clear code structure; `CLAUDE.md` (agent guide) is highly readable
- tests split into `tests/` (mocked, no Docker) and `tests/integration/`
- `ruff` + `mypy` wired into CI
- `requirements.txt` separated from `requirements-dagster.txt`
- `scripts/verify-setup.py` for health checks
- Dagster schedules, sensors, and asset checks present
- medallion documentation, roadmap, and release checklists maintained

These weigh materially in favour of the project's soundness.

---

## 3. Assessment of "ECB + DAX runs end to end"

### 3.1 What genuinely runs today

Taking `make setup` + `make demo` as the acceptance path, the following chain is **actually executable**:

1. `ecb_bronze` — `ECBCollector` pulls the MRO rate from `https://data-api.ecb.europa.eu/service/data/FM/D.U2.EUR.4F.KR.MRR_RT.LEV`, validates it, and appends to `iceberg.bronze.ecb_rates`.
2. `dax_bronze` — `DAXCollector` reads `data/sample/dax_daily_sample.csv` (6,522 rows, 2000-01-03 to 2024-12-31), validates it, and appends to `iceberg.bronze.dax_daily`.
3. `ecb_silver` / `dax_silver` — scan all Bronze data, apply type conversion, forward-fill, weekend filtering, and derived fields, then overwrite the Silver tables.
4. `gold_features` — builds event-study features anchored on ECB rate-change events (5-day pre-window volatility, 5-day post-window cumulative return, etc.) and overwrites `iceberg.gold.ecb_dax_features`.
5. `scripts/verify-demo.py` — verifies through Trino that the Gold table has data.
6. `gold_features_min_rows_check` — asserts Gold has at least 10 rows.

For the full pipeline including MLflow, `make pipeline` additionally runs:

7. `ml_experiment` — reads Gold from Trino (or via pyiceberg when Trino is unavailable), runs an XGBoost + LightGBM 3×2 grid with `TimeSeriesSplit(5)` CV, logs everything to MLflow, and returns the best `run_id`.

Given a healthy Docker stack, a reachable ECB API, and no same-day duplicate-run skip, the demo path does produce a queryable Gold table **in one pass**, and the full pipeline produces a best model run.

### 3.2 Where "end to end" deserves a discount

None of these break the pipeline, but each weakens the claim that it runs end to end convincingly.

#### (P1) DAX is not a live source — it is a static CSV

- `DAXCollector._fetch_data` reads `data/sample/dax_daily_sample.csv` directly.
- The CSV stops at **2024-12-31**. ECB rate changes continued after that, but with DAX data frozen, **every post-2024 ECB event is dropped in `build_gold_features` because its `post_window` has fewer than 5 rows**.
- The CSV values also diverge from real DAX history (its 2024-12-31 close is `10128.23`; the actual DAX closed that year above 19,000). This is a **synthetic test series** and is not labelled as such in the documentation.
- Result: the project presents two data sources, but DAX is effectively synthetic — which does not match the "public real data" narrative in `ADR-004`.

#### (P3) Idempotency boundaries are fragile

- `DAXCollector._already_ingested_today()` skips when today's data has already been ingested. That is reasonable for CSV replay, but it only checks whether an ingestion exists for today — it does **not** fingerprint the CSV contents. Replacing `data/sample/dax_daily_sample.csv` after a same-day run causes the new data to be silently skipped.
- The same applies to the ECB collector.

#### (P4) Asset check density is too low

- There is one check: `gold_features` row count ≥ 10.
- No freshness check (is the maximum `event_date` within a rolling window of today?).
- No schema or null-rate check.
- *(Partly addressed in v2.6 — see the status banner.)*

#### (P6) Rejected records have no governance loop

- `BronzeWriter.write_rejected` writes rejected records aside.
- But there is no metric, no alert, and no presence in the OpenMetadata governance view. A rising rejection rate would go unnoticed.

#### (P7) The ECB series chosen is too coarse for event granularity

- `ECBCollector.ENDPOINT` fetches only `MRR_RT.LEV` (the MRO rate level).
- The ECB's primary policy rate in the modern regime is the **Deposit Facility Rate (DFR)**; since 2022 the MRO has not been the main policy instrument.
- This makes the Gold event definition (`rate_change_bps != 0`) fire infrequently in recent years, which is **unhelpful for ML sample size**.
- It does not stop the pipeline, but it limits how meaningful the resulting model can be.

#### (P8) Operational visibility (SLO/alerting) is out of scope for v2.5

Acknowledged by the project itself (`TASKS.md` Block C, `ADR-010`). Listed only under the production-readiness dimension.

---

## 4. Recommendations

Ordered by impact on end-to-end credibility. Each maps directly to a `P#` above.

### P1. Make DAX a genuinely dynamic source (necessary)

**Option 1 (minimal)**: have the DAX collector prefer a public source and fall back to the CSV.

```python
def _fetch_live(self) -> list[dict[str, Any]] | None:
    """Best-effort pull of DAX daily OHLCV from a free public source.

    Returns None when the live source is unreachable so the caller can
    fall back to the committed sample CSV without failing the pipeline.
    """
    try:
        import yfinance as yf  # optional dependency
    except ImportError:
        return None
    try:
        frame = yf.download("^GDAXI", period="max", progress=False, auto_adjust=False)
    except Exception:
        return None
    if frame is None or frame.empty:
        return None
    frame = frame.reset_index().rename(
        columns={
            "Date": "observation_date",
            "Open": "open_price",
            "High": "high_price",
            "Low": "low_price",
            "Close": "close_price",
            "Volume": "volume",
        }
    )
    return frame.to_dict(orient="records")
```

Then in `collect()`: `raw = self._fetch_live() or self._fetch_data()`, with `yfinance` added as an optional dependency.

**Option 2 (heavier but more robust)**: use a historical CSV URL from an exchange or market-data provider as the primary source, keeping the committed CSV as an airgapped fallback.

**In either case, state clearly in `README` and `ADR-004`** that the committed CSV is an offline/CI fallback and is not a real DAX price series.

### P3. Key idempotency on a content fingerprint, not the date (recommended)

Record a `sha256` of the ingested content in `BronzeWriter`, and change the duplicate check to "today's data exists **and** the fingerprint matches":

- same day + identical content → skip (current behaviour)
- same day + different content → ingest, and record the change
- replacing the CSV then becomes immediately detectable

### P4. Complete the asset checks into a minimum viable data contract (necessary)

At least these four, registered in `dagster/assets.py`:

1. `gold_features_freshness_check` — distance between `max(event_date)` and today is within a threshold (e.g. 180 days)
2. `silver_ecb_monotonic_check` — Silver ECB `observation_date` has no gaps and is strictly increasing
3. `silver_dax_gap_check` — Silver DAX business-day gaps ≤ N days (e.g. 5, to allow long holidays)
4. `gold_features_schema_check` — column names and types match the declared Gold schema exactly

Thresholds should not be magic numbers; put them in `PipelineConfigResource` or the dataset contracts.

*(v2.6 note: `governance/datasets/*.yaml` now expresses `required_columns`, `non_null_columns`, `min_row_count`, `max_gap_days`, and `forbid_future_dates`. The freshness and schema checks above are the remaining gap.)*

### P6. Bring rejected records into the governance loop (recommended)

- After Bronze completes, if `rejected_count > 0`, emit a Dagster metadata field and a structlog metric `bronze.rejected.ratio`.
- Register the rejected-records location as a table in OpenMetadata so the catalog shows rejected data, not only successful data.
- Add an integration test that injects a deliberately bad record and asserts it lands in the rejected path.

### P7. Extend the ECB source to multiple rates (strongly recommended)

Extend `ECBCollector.ENDPOINT` from a single MRO series to at least three:

- MRO (`MRR_RT.LEV`) — main refinancing operations
- DFR (`DFR.LEV`) — deposit facility rate, the effective policy rate since 2022
- MLF (`MLF.LEV`) — marginal lending facility

And let `silver_to_gold_features.build_gold_features` derive events from any chosen rate series via a parameter. This would substantially enrich the 2022–2025 event set, directly improving Gold row count and the statistical meaningfulness of the ML stage.

### P8. A minimal operability patch (optional; v3 scope, but one step is worth pulling forward)

Without waiting for v3, two small things are possible:

1. Write `pipeline.step.duration_ms` into an Iceberg operations table so Superset can chart per-step duration directly.
2. Move the `gold_features_min_rows_check` threshold out of hard-coded `10` into config, and add a short Trino CLI verification list to the README (latest `event_date` and row counts for ECB/DAX/Gold, plus the current Iceberg snapshot count).

---

## 5. If you only do three things

To raise end-to-end credibility most efficiently, in order:

1. **P1 — connect a real DAX source**, and document the committed CSV as an airgapped fallback only.
2. **P7 — extend ECB to MRO/DFR/MLF**, which directly improves Gold row count and ML significance.
3. **P4 — add the freshness, schema, and monotonic checks** on top of the v2.6 contract quality rules.

With those done, the project can reasonably claim genuinely trustworthy end-to-end operation for ECB + DAX.

---

## 6. Suggested wording for the project's current positioning

A precise formulation, consistent with the roadmap and ADRs, and unlikely to be misread as production readiness:

> v2.5 is a **reference-grade runnable lakehouse** with medallion separation, an open table format across all layers, unified metadata, orchestrated assets with basic data-quality gating, and tracked ML experimentation. It is **not yet production-grade**: multi-environment deployment, secrets/access governance, SLO-driven observability, and a non-synthetic DAX source are tracked as later work.

---

## 7. Compute-layer evolution (dbt / PySpark / redefining Trino's role)

> This section answers a follow-up question: "could the transformation layer be replaced by dbt or PySpark, leaving Trino to serve queries only?"
> The full decision record is **[ADR-016: Compute engine migration](decisions/ADR-016-compute-engine-migration.md)**; this is the reader-facing summary.
>
> **Status**: proposed, not scheduled into any version. Note that ADR-020 has since removed the Trino write path entirely — Trino is already query-only, which satisfies the original constraint without adopting Spark.

### 7.1 Clarifying the concepts

- **dbt is not a compute engine.** It is a SQL transformation framework that must bind to a backend (`dbt-trino` / `dbt-spark` / `dbt-duckdb`).
- **PySpark is a real compute engine**, able to read and write Parquet and Iceberg on MinIO directly.
- So "switch to dbt or PySpark" is really three candidates:
  - **A: `dbt-trino`** → Trino does both compute and serving, which **fails** the "Trino serves queries only" constraint.
  - **B: `PySpark` + Iceberg** → Spark computes, Trino serves (satisfies the constraint).
  - **C: `dbt-spark` + Iceberg** → Spark computes, dbt orchestrates SQL-first, Trino serves (satisfies the constraint, with better SQL-ification, lineage, and testing).

### 7.2 Recommended path: two stages toward option C

**Stage 1 — introduce Spark + Iceberg writes; Trino becomes read-only**

- Add a single-node Spark (master + one worker with the Iceberg runtime jar, sharing the existing Hive Metastore).
- Rewrite `silver_to_gold_features` in PySpark, upserting Gold with `MERGE INTO` keyed on `event_date`.
- Remove the Trino write path.
- `ml/evaluate.py`, Superset, and OpenMetadata need no changes — they still read `iceberg.gold.*` through Trino.

**Stage 2 — adopt `dbt-spark` for Silver/Gold SQL-ification and testing**

- Create a dbt project using the `dbt-spark` adapter.
- Rewrite the Silver transformations and the PySpark Gold job as dbt models (`incremental` + `unique_key`).
- Use `dagster-dbt` so each dbt model maps to a Dagster asset, preserving the asset graph shape.
- Use dbt's built-in `not_null` / `unique` / `accepted_values` plus custom freshness tests, which also closes **P4**.
- Enable OpenMetadata dbt manifest ingestion so Silver/Gold lineage and test results appear in the catalog.

### 7.3 Why Bronze stays in Python

A collector's job is talking to an external source, validating with Pydantic, and writing rejected records. That is not SQL-shaped work and should not be absorbed into dbt or Spark. Keeping `ingestion/collectors/*.py` as-is keeps the boundary between the outside world and the lakehouse clear and single-sourced.

### 7.4 Cost and risk snapshot

| Dimension | Today | After stage 1 | After stage 2 |
|------|------|----------|----------|
| Docker image size | small | notably larger (+Spark) | larger still (+dbt / Spark Thrift) |
| Cold-start time | seconds | tens of seconds (JVM) | tens of seconds |
| Trino's role | **query-only** *(already true since ADR-020)* | query-only | query-only |
| Iceberg snapshots | retained *(since ADR-020)* | retained (MERGE) | retained |
| Asset check / test density | low–medium | medium (still hand-written) | high (dbt test + Dagster check) |
| OpenMetadata lineage | Trino scan | Trino scan | Trino scan + dbt manifest |
| Rollback difficulty | — | low | low |

### 7.5 Relationship to the roadmap

ADR-020 already achieved the original motivation for stage 1 — Trino no longer writes, and Iceberg snapshots are retained — at far lower cost than introducing Spark. The remaining argument for this migration is SQL-ification and test density (stage 2), which should be weighed against the roadmap's explicit rule that adopting Spark/dbt is not a proxy for platform maturity. It is not scheduled.

---

## Appendix A: files covered by this assessment

- `README.md`, `Makefile`, `docker/docker-compose.yml`
- `dagster/assets.py`, `dagster/definitions.py`
- `ingestion/collectors/ecb_collector.py`, `ingestion/collectors/dax_collector.py`
- `ingestion/schema/ecb_schema.py`, `ingestion/trino_sql.py`
- `transformations/ecb_bronze_to_silver.py`, `transformations/dax_bronze_to_silver.py`, `transformations/silver_to_gold_features.py`
- `ml/train_ecb_dax_model.py`, `ml/evaluate.py`
- `data/sample/dax_daily_sample.csv` (2000-01-03 – 2024-12-31, 6,522 rows)
- `docs/architecture.md`, `docs/roadmap.md`, `TASKS.md`

## Appendix B: mapping to the backlog

| Recommendation | Backlog location |
|------------|----------------|
| P1 (real DAX source) | Not yet covered — proposed as a `source_of_truth` item under Block A |
| P3 (content-fingerprint idempotency) | Block A quality rules |
| P4 (asset check coverage) | Block A — partly delivered in v2.6 |
| P6 (rejected-record governance) | Block A |
| P7 (multi-rate ECB) | Block A — `business_purpose` of the dataset governance baseline |
| P8 (operational metrics) | Block C, lightweight precursor |
| §7 (compute migration) | Spans Block A / Block F — see [ADR-016](decisions/ADR-016-compute-engine-migration.md) |
