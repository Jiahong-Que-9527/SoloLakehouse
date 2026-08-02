# SoloLakehouse Timeline

This document records version evolution in release order.

## v1.0.0 (2026-03-26) - Delivered (historical)

Theme:
- Runnable baseline lakehouse core.

What landed:
- MinIO, PostgreSQL, Hive Metastore, Trino, MLflow baseline.
- End-to-end medallion data flow and ML experiment logging.

## v2.0.0 (2026-03-28) - Delivered (historical)

Theme:
- Dagster orchestration introduction.

What landed:
- Software-defined assets and `full_pipeline_job`.
- Schedule, sensor, and asset check governance primitives.

## v2.5.0 (2026-03-28) - Delivered

Theme:
- Single-track runtime standardization and platform completeness.

What landed:
- Iceberg Gold path via Trino.
- OpenMetadata integrated in default stack.
- Superset integrated in default stack.
- Legacy parallel runtime paths removed from code.

Decision gate to v3:
- Harden infrastructure/governance without reintroducing parallel runtime entrypoints.

## v2.5.1 (2026-05-10) - Current baseline (frozen)

Theme:
- v2.5 freeze hardening — close the acceptance gate so v2.6 work can begin.

What landed:
- `make demo` acceptance entrypoint (`demo_data_flow_job` + Trino Hive/Iceberg
  Gold row-count assertions).
- Root `DEMO.md` + `RUNBOOK.md` + cold-clone hardware/OS matrix in README.
- GitHub Actions `compose-demo` gate runs `make setup` + `make demo` from a
  clean CI runner.
- `docs/v2.5-acceptance-criteria.md` checklist closed (cold clone, demo
  readiness, documentation completeness, stability boundary).
- ADR-019 records the MinIO → SeaweedFS deferral that locks v2.5 freeze scope.

Decision gate to v2.6 / Phase 1 of entity split:
- Treat v2.5.1 as the frozen template baseline; new work goes to v2.6 or the
  entity-template preparation track.

## v2.6.0 (2026-07-31) - Delivered

Theme:
- Computational governance and evidence plane on the protected v2.5 runtime.

What landed:
- Machine-validated dataset contracts and governed quality checks for the
  reference Gold dataset.
- Typed three-source lineage evidence that joins OpenMetadata metadata,
  Iceberg snapshots, and a successful Dagster materialization.
- `make lineage-evidence` writes a canonical SHA-256-bound manifest to the
  stable audit-bucket layout.
- A real local release drill recorded a successfully ingested Trino table,
  assigned owner, current Iceberg snapshot, successful Dagster run, and audit
  manifest.

Known limits:
- The release does not claim Object Lock/WORM enforcement, automated catalog
  ingestion, production RBAC, token lifecycle management, or regulatory
  compliance. See `docs/v2.6-release-readiness.md`.

Not delivered, moved to v2.6.1 (recorded 2026-07-31):
- Automatic evidence emission after a successful materialization (planned at
  1 day; evidence generation is still a manual CLI with a hand-copied run ID).
- MinIO Object Lock on the audit bucket (planned as `E4` at 2 days).
- Neither was rescheduled at the time; both are now Block `J` (`J1`, `J2`).

Release status:
- **Tagged and published `2026-07-31`** (PR #44).
- The published tag carries a defect: `RUNTIME_VERSION` defaulted to
  `slh-v2.5.1`, so evidence manifests generated from `v2.6.0` record the wrong
  runtime version. Disclosed in the release notes and in the CHANGELOG; fixed
  on `main` and shipping in `v2.6.1` (Block `R`).

Decision gate to v2.6.1:
- Ship the version-stamp fix, then make the evidence plane operational — automatic emission,
  write-once audit storage, coverage for all governed datasets, and a causal
  (not merely name-consistent) snapshot↔run binding — before adding a new
  evidence category.

## v2.6.1 (2026-07-31) - Delivered

Theme:
- Correct the released version stamp; unify the agent entry points; make the
  published repository English-only.

What landed:
- `RUNTIME_VERSION` now matches the released version. `v2.6.0` defaulted to
  `slh-v2.5.1`, so every evidence manifest it produced misattributed itself to
  the previous runtime. The drill was re-run and the manifest read back from the
  audit bucket to confirm `runtime_version=slh-v2.6.1`
  (run `3d2ccfad-047e-47a9-9dff-c3285a473f94`, snapshot `8854746967558235959`,
  `record_sha256=10dc3f911b…`).
- `docs/roadmap.md` and `TASKS.md` established as the sole planning authorities;
  four conflicting representations reduced to two.
- Decisions D1/D2/D3 recorded; external validation added to release readiness.
- `AGENTS.md` rewritten as the shared agent contract; `.cursor/rules/` added
  (Cursor previously had no project entry point); `make check-agent-docs` wired
  into CI so entry-point drift fails the build.
- Published repository is English-only.

Release status:
- **Tagged and published `2026-07-31`** as `v2.6.1` (`6bd138a`).
- Block `J` shipped later on `main` (`e534c73`, PR #49). See timeline entry below.

Historical decision gate to Block `J` acceptance:
- External validation against baseline `e534c73`, then a post-Block-`J` tag.
  This was superseded on 2026-08-02 by the continuous-development Owner
  Decision recorded below.

## v2.6.1 Block J - Implementation Complete; External Validation Deferred (2026-08-01, updated 2026-08-02)

Theme:
- Operationalize the evidence plane delivered in v2.6.

Implementation completed (`main` @ `e534c73`, PR #49, `2026-08-01`):
- Block `R` — version stamp corrected; tag `v2.6.1` published (`6bd138a`).
- Block `J` — automatic evidence emission, Object Lock, five-dataset coverage,
  causal snapshot↔run binding, CI coverage for `governance/` and `dagster/`.
- Block `G` — external validation gate (`docs/external-validation/`) and G4
  D1 ordering record.

Deferred for the integrated post-v2.9 gate:
- External validator sign-off retains the Block `J` protocol in
  `docs/external-validation/v2.6.1-external-validation.md`.
- Operational rollout and the signed post-v2.9 release tag follow that
  integrated sign-off.

Maintainer rehearsal (`2026-08-01`): `make verify` + `make demo` PASS; automatic
five-dataset emission confirmed (run `dfe42975…`). Does not satisfy G3.

Owner Decision (2026-08-02):
- Development proceeds continuously in the order **v2.8, v2.7, v2.9**.
- Independent external validation and operational rollout begin only after
  v2.9 completes; they do not block implementation or internal validation.

## v2.9 — Operational and Promotion Evidence (2026-08-02) - Delivered

Theme:
- Repeatable operations, rollback readiness, and promotion discipline on the
  existing v2.5 runtime.

What landed on `main` @ `71c2c89`:
- Block `B`/`C` (PR #57) — promotion chain evidence, rollback drill manifests,
  SLO evaluation from verify-setup checks, incident runbook bindings.
- Block `D`/`F` (PR #59) — `.env.shared`/`.env.secrets` split, secrets discipline
  and rotation drill evidence, K8s migration readiness gate (no Helm/Terraform).
- ADR-022 and ADR-023; 167 unit tests on `main`.

Decision gate to integrated external validation:
- Recruit at least one external validator for the v2.6.1–v2.9 candidate per
  `docs/external-validation/v2.6.1-external-validation.md`. Do not start v3.0
  or operational rollout until that gate completes.

## v2.8 E1 - ML Lineage Five-Tuple (2026-08-02) - Implemented; PR #51 Pending

Theme:
- Bind every governed MLflow experiment to the exact data snapshot, Dagster
  run, feature definition, source revision, and dataset contract in force.

What landed on PR #51:
- `MLLineageTuple` with five required fields and a canonical SHA-256 digest.
- MLflow `slh.*` tags and Dagster `ml_experiment` metadata carrying the tuple.
- Snapshot-pinned PyIceberg training reads, so the evidence snapshot is the data
  consumed by training rather than a contemporaneous table head.
- A dirty-input guard before Dagster image builds, preventing `HEAD` from being
  stamped when copied application code differs from that commit.
- ADR-018 finalized; ADR-021 records metadata-first policy hooks and defers
  query-time enforcement.

Decision gate to E2:
- Merge PR #51 only after its CI and review fixes pass. E2 then extends dataset
  contracts with AI-governance fields and constraints.

## v2.8 E2 - AI-Governance Contract Boundaries (2026-08-02) - Implemented Locally

What changed:
- Every governed dataset contract now declares an `ai_governance` boundary:
  whether AI use is allowed, risk tier, intended and prohibited uses, human
  oversight, and whether ML lineage is required.
- Bronze and Silver datasets explicitly prohibit model training; the Gold
  feature dataset permits model training and evaluation only, with human
  oversight and the E1 lineage tuple required.
- Contract validation rejects missing metadata and contradictory declarations.

Decision gate to E3:
- Surface the approved contract metadata through agent-ready policy hooks only;
  do not add a chat application or query-time enforcement.

## v2.6.1 Block J - Planned (next) — superseded

_Superseded by the 2026-08-02 Owner Decision (continuous development through
v2.9; external validation deferred to the integrated post-v2.9 gate). The
section below is retained for history only._

Theme:
- Operationalize the evidence plane delivered in v2.6.

Why this version exists:
- v2.6 shipped roughly 80% of its plan. The missing 20% is exactly what
  separates *demonstrable* from *operational*, and it was never rescheduled.
  Adding a second evidence category on top of a manually-triggered,
  single-dataset, overwritable evidence plane would compound that gap.

Planned scope:
- Block `R` — correct the released version stamp, re-drill, and publish v2.6.1.
- Block `J` — automatic emission, Object Lock, full dataset coverage, causal
  snapshot↔run binding, CI coverage gate extended to `governance/` and `dagster/`.
- Block `G` — external validation gate; record the v2.7/v2.8 ordering decision.

Decision gate to v2.7 / v2.8:
- The ordering of v2.7 (catalog openness) and v2.8 (AI/ML governance) is
  **undecided** and is to be resolved with external input rather than by
  internal planning. See `docs/roadmap.md`, decision D1.

## Post-v2.5 entity-template preparation - Phase 1 complete (2026-05-18)

Theme:
- Turn the frozen v2.5 reference runtime into a repeatable product-entity
  template, so FinLakehouse and Aviation Lakehouse can be split out without
  changing application code.

Delivered scope (evidence in `docs/entity-template-readiness.md`):
- Product entity contract defines identity, storage, runtime, metadata,
  backup, and side-by-side upgrade fields
  (`docs/product-entity-contract.md`).
- Runtime identity parameterized via `runtime_identity.py` + `.env.example`
  (`PRODUCT_ID`, `PRODUCT_DISPLAY_NAME`, `RUNTIME_VERSION`, `TRINO_USER`, etc.).
- Storage locations parameterized via `storage_config.py`
  (`DATA_BUCKET`, `AUDIT_BUCKET`, `MLFLOW_ARTIFACT_BUCKET`, `WAREHOUSE_URI`).
- MinIO retained as current S3-compatible provider, decoupled from product
  identity (`docs/object-store-abstraction.md` + ADR-019).
- Stable logical dataset IDs (`fin.*`, `aviation.*`) defined and mapped to
  physical assets (`docs/dataset-governance-naming.md`).
- Entity-owned runtime root layout `/opt/<product_id>/{app,data,backup,logs}`
  documented (`docs/runtime-state-layout.md`).
- Backup/restore runbook + one passing disposable restore drill
  (`docs/entity-backup-restore-runbook.md` +
  `docs/restore-drills/2026-05-17-entity-template-restore-drill.md`).
- Lightweight SLH portal as shared operator/demo entrypoint
  (`scripts/health-server.py` + `make health`).

Next decision gate (Phase 2):
- Split out FinLakehouse on a dedicated VPS using the prepared template,
  keeping MinIO; do not combine with object-store replacement or v2.6
  governance evidence work.

## v2.5.x — Full-stack Iceberg migration (2026-05-29)

Theme:
- Elevate Bronze and Silver to first-class Iceberg tables; remove the Parquet + Hive-staging write path.

What landed:
- `ingestion/iceberg_schemas.py` — canonical Iceberg schema + partition spec for all six tables.
- `ingestion/iceberg_io.py` — thin pyiceberg I/O layer (`append_table`, `overwrite_table`, `scan_table`, `get_catalog`).
- `BronzeWriter` rewritten to use `iceberg_io.append_table`; `ECBCollector`/`DAXCollector` use `Catalog` instead of `minio_client`.
- All three transformation `run()` functions read and write Iceberg tables (not MinIO Parquet).
- `trino_sql.py` stripped to just `execute_trino_sql`; Hive staging and CTAS flow removed.
- `IcebergCatalogResource` added to Dagster; all assets and sensors use it.
- `ml/evaluate.py` updated: Trino reads `iceberg.gold.ecb_dax_features` (renamed from `_iceberg` suffix); pyiceberg fallback replaces MinIO Parquet fallback.
- `scripts/init-iceberg-namespaces.py` bootstraps all namespaces and tables; wired into `make up`.
- `HIVE_METASTORE_URI` env var added to `.env` (host) and docker-compose (container override).
- All 69 unit tests pass; tests now mock `iceberg_io.scan_table` / `overwrite_table` instead of MinIO `put_object`.
- ADR-020 records the decision.

Decision gate:
- Full E2E verification via `make clean && make up && make pipeline` against live Hive Metastore + MinIO.

## v3.0.0 - Planned

Theme:
- Production infrastructure and governance hardening.

Focus:
- Multi-environment deployment model.
- Promotion controls, rollback strategy, secrets governance.
- SLO-driven observability and incident workflows.

## v4.0.0 - Planned

Theme:
- Self-serve usability and operational clarity.
