# Architecture Evolution and Planning Choices

This file explains major architecture choices over time and why they changed.

## v1 Foundation Choices (implemented)

1) Docker Compose first, Kubernetes later  
- Selected: Docker Compose  
- Why: low setup friction and faster local iteration.

2) Trino + Hive Metastore query model  
- Selected: Trino over embedded query-only engines  
- Why: better demonstration of metadata-driven lakehouse patterns.

3) Parquet-first medallion flow  
- Selected: Parquet append-only conventions for Bronze/Silver/Gold  
- Why: lower operational complexity for a reference implementation.

## v2 Orchestration Choices (implemented, historical)

1) Orchestrator selection  
- Candidates: Dagster, Prefect, Airflow, script+cron  
- Selected: Dagster.

2) Runtime convergence decision  
- Historical state: v2 initially kept dual runtime paths for migration.  
- Current state: dual paths retired; orchestration is Dagster-only in active runtime.

## v2.5 Baseline Choices (implemented, historical)

1) Iceberg for Gold  
- Selected: Trino-managed Iceberg Gold table while preserving Python Parquet staging.
- Superseded by ADR-020 (all-layer Iceberg) — see v2.5.x section below.

2) Metadata and BI stack posture  
- Selected: OpenMetadata + Superset as required platform components in default runtime.

3) Single runtime entrypoint  
- Selected: `make pipeline` (Dagster `full_pipeline_job`) as only execution path.

## v2.5.x Full-stack Iceberg Migration (2026-05-29)

1) Iceberg for all medallion layers  
- Selected: pyiceberg `HiveCatalog` writes for Bronze (append), Silver (overwrite), Gold (overwrite).  
- Rejected: continue Parquet-only for Bronze/Silver — leaves them invisible to Trino/OpenMetadata.  
- Rejected: Trino INSERT INTO for Bronze/Silver — would require materialising DataFrames into a Hive external table first, re-introducing the staging problem.  
- Key consequence: `BronzeWriter`, both collectors, and all three transformation `run()` functions now depend on pyiceberg rather than MinIO SDK. The `minio_client` parameter was removed from collectors.  
- ADR-020 records this decision.

## Post-v2.5 Entity Template Choices (Phase 1 complete, 2026-05-18)

Phase 1 of the entity-template preparation is closed. Evidence and exit
criteria are recorded in `docs/entity-template-readiness.md`. Phase 2+
(FinLakehouse / Aviation Lakehouse as long-running entities) is documented in
`task.md` but **deferred indefinitely** as roadmap decision D2 — not the active
repository backlog.

1) Product entity contract before product split (implemented)
- Selected: define a required entity contract before launching FinLakehouse or
  Aviation Lakehouse as long-running runtimes
  (`docs/product-entity-contract.md`).
- Why: stable product identity, dataset namespace, storage locations, metadata
  labels, runtime roots, and upgrade policy need to be explicit before data
  assets become long-lived.
- Alternative rejected: copy the v2.5 runtime first and rename values later.
  That would mix product identity changes with storage/runtime migration risk.

2) Runtime identity parameterization (implemented)
- Selected: drive `PRODUCT_ID`, `PRODUCT_DISPLAY_NAME`, `RUNTIME_VERSION`,
  `COMPOSE_PROJECT_NAME`, and `TRINO_USER` from environment via
  `runtime_identity.py` and `.env.example`, with `tests/test_runtime_identity.py`
  as the regression gate.
- Why: deploy-time configuration must isolate entity identity and storage
  without forking the template for bucket names or product labels. Domain
  pipeline localization still requires code changes in the entity clone.
- Alternative rejected: hardcode `sololakehouse` and grep-replace per entity.

3) Storage location parameterization (implemented)
- Selected: drive `DATA_BUCKET`, `AUDIT_BUCKET`, `MLFLOW_ARTIFACT_BUCKET`,
  `MLFLOW_ARTIFACT_ROOT`, and `WAREHOUSE_URI` from environment via
  `storage_config.py`, with `tests/test_storage_config.py` as the regression
  gate.
- Why: each entity needs its own data/audit/MLflow buckets without rebuilding
  images.
- Compatibility: `BUCKET_NAME` retained as a v2.5 alias when `DATA_BUCKET` is
  unset.

4) MinIO retained for the first split (implemented, ADR-019)
- Selected: keep MinIO as the initial S3-compatible provider while naming the
  object-store boundary generically in product-level configuration.
- Why: entity split, object-store replacement, and v2.6 governance evidence are
  separate risk surfaces and should be validated independently.
- Boundary: product-level configuration uses `OBJECT_STORE_*`, bucket, and
  warehouse names; existing `S3_*`, `AWS_*`, `MLFLOW_S3_ENDPOINT_URL`, and
  `MINIO_*` names remain compatibility/runtime settings until code
  parameterization replaces them safely. See
  `docs/object-store-abstraction.md`.

5) Logical dataset IDs as governance join keys (implemented)
- Selected: use stable `fin.*` and `aviation.*` dataset IDs that map to current
  object-store paths, Trino tables, OpenMetadata entities, and Dagster assets
  (`docs/dataset-governance-naming.md`).
- Why: v2.6 lineage evidence and future storage migrations need a stable key
  that is not tied to MinIO bucket names, warehouse URIs, or catalog table
  names.
- Alternative rejected: use physical paths or Trino table names as governance
  identities. Those names are expected to change during entity split and
  side-by-side migration.

6) Entity-owned runtime roots (documented)
- Selected: keep repository-local `docker/data/` for the local reference runtime
  while recommending `/opt/<product_id>/{app,data,backup,logs,.env}` for
  continuously operated product entities (`docs/runtime-state-layout.md`).
- Why: the reference path stays easy to run, while product entities get clear
  ownership for code, bind-mounted runtime data, backups, logs, and `.env`.
- Alternative rejected: share one checkout and one `docker/data/` tree across
  entities. That would blur backup, restore, rollback, and incident boundaries.

7) Backup/restore as a hard prerequisite to long-running entities (implemented)
- Selected: define minimum backup set (object-store buckets + Postgres logical
  dumps + OpenMetadata re-ingest strategy + `.env` + release metadata) and
  require one passing disposable restore drill before launching a 24/7 entity
  (`docs/entity-backup-restore-runbook.md` +
  `docs/restore-drills/2026-05-17-entity-template-restore-drill.md`).
- Why: an entity that cannot be rebuilt from backup is not actually independent.
- Alternative rejected: defer drills until "after we have something to back
  up". Same failure mode as the 2026-05-09 snapshot's missing acceptance gate.

8) Lightweight portal as shared operator/demo entrypoint (implemented)
- Selected: a stdlib-only HTTP portal driven by `runtime_identity` +
  `storage_config` + `verify-setup.py` output, surfaced via `make health`.
- Why: every entity should answer "am I healthy / what is the next demo step"
  from one URL.
- Boundary: not a database-backed app platform, not a replacement for
  Dagster/Superset/OpenMetadata/MLflow.

## v3 Decision Frame (planned)

- Multi-environment deployment architecture
- Promotion and rollback governance
- Secrets/access model and auditability
- SLO/alerting and incident readiness

## v2.8 E1 ML Lineage Choice (2026-08-02)

1) Five-way ML evidence binding (implemented on PR #51, pending merge)
- Selected: bind each MLflow run to `iceberg_snapshot_id`, `dagster_run_id`,
  `feature_version`, `code_commit`, and `data_contract_hash`, plus a canonical
  SHA-256 digest.
- Selected: train through PyIceberg pinned to the tuple's snapshot ID.
- Rejected: an unversioned Trino read after recording the current snapshot;
  concurrent Gold rewrites could otherwise make the evidence describe data that
  the experiment did not consume.
- Rejected: stamping `git rev-parse HEAD` without a clean-build check; a Docker
  image can contain dirty source while claiming the clean commit.
- Compatibility: no service is added and the v2.5 runtime remains unchanged.
- ADR-018 records the tuple; ADR-021 defines the metadata-first policy boundary.

## v2.8 E2 AI-Governance Contract Choice (2026-08-02)

- Selected: require a declarative `ai_governance` section on every governed
  dataset contract, covering allowed AI use, risk tier, intended and prohibited
  uses, human oversight, and model-lineage requirements.
- Selected: keep Bronze and Silver datasets outside the model-training boundary;
  allow the Gold feature dataset only for model training and evaluation, with
  human oversight and lineage required.
- Rejected: implicit policy inferred from layer, owner, or free-text purpose;
  it cannot be validated or safely reused by future agents.
- Deferred: Trino enforcement, RBAC changes, and a chat application. ADR-021
  keeps those operational controls outside this metadata-and-evidence release.

## Release-gate sequencing decision (2026-08-02)

- Selected: continue internal development through **v2.8, v2.7, and v2.9**;
  perform independent external validation and begin operational rollout only
  after v2.9 completes.
- Why: the integrated candidate gives validators one stable governance and
  operations surface, without pausing development between evidence categories.
- Retained controls: local CI, contract validation, `make verify`, and
  `make demo` remain required during every version; this decision defers only
  the independent external gate and operational rollout.
- No ADR: this changes release sequencing, not the v2.5 runtime architecture
  or a technical boundary.

## Legacy Record

Historical migration and compatibility details remain documented for reference only:
- `docs/history/legacy-overview.md`
