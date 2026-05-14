# SoloLakehouse Entity Split and Upgrade Migration Tasks

## Purpose

This document describes how to turn the SoloLakehouse v2.5 reference runtime into two independently operated product entities:

- `finlakehouse`
- `aviation-lakehouse`

Both entities are expected to run 24/7 on separate VPS hosts and produce domain-specific data assets. Future SoloLakehouse upgrades, starting with v2.6, should be applied through side-by-side migration: start a fresh target entity on the new version, import or rebuild runtime data from the old entity, validate it, cut over, and keep the old entity available for rollback.

The preferred rule is:

> Split entities first, keep MinIO initially, but prepare the object-store boundary so MinIO can be replaced later without redesigning the product entities.

## Guiding Principles

- Treat SoloLakehouse as the upstream product template, not as a single permanent runtime.
- Treat `finlakehouse` and `aviation-lakehouse` as product instances with their own identity, runtime state, data assets, schedules, evidence, and lifecycle.
- Do not combine entity split, object-store replacement, and v2.6 governance migration into one risky change.
- Keep MinIO for the first entity split, but rename configuration concepts from "MinIO-specific" to "S3-compatible object store".
- Prefer side-by-side upgrades over in-place upgrades.
- Keep old entities read-only during an observation window after cutover.
- Make every migration reversible until the new entity has produced enough validated data assets.

## Phase 1: Preparation Before Splitting Entities

### Goal

Prepare the v2.5 codebase so it can be used as a repeatable entity template. The output of this phase is not yet two new products; it is a cleaner, configurable baseline that can safely create product instances.

### 1. Define the Entity Contract

Create a formal contract for what makes one lakehouse entity complete.

Each entity must define:

| Field | Example: finlakehouse | Example: aviation-lakehouse |
|---|---|---|
| `PRODUCT_ID` | `finlakehouse` | `aviation-lakehouse` |
| Domain | financial markets | aviation operations |
| Runtime host | one dedicated VPS | one dedicated VPS |
| Data bucket | `finlakehouse-data` | `aviation-lakehouse-data` |
| Audit bucket | `finlakehouse-audit` | `aviation-lakehouse-audit` |
| MLflow artifact bucket | `finlakehouse-mlflow` | `aviation-lakehouse-mlflow` |
| Warehouse URI | `s3a://finlakehouse-data/warehouse/` | `s3a://aviation-lakehouse-data/warehouse/` |
| OpenMetadata service name | `finlakehouse-trino` | `aviation-lakehouse-trino` |
| Superset workspace/database labels | `finlakehouse_*` | `aviation_lakehouse_*` |
| Dagster instance | entity-local | entity-local |
| Upgrade strategy | side-by-side | side-by-side |

The entity contract should be documented before any long-running product instance is created.

### 2. Parameterize Runtime Identity

The current v2.5 stack still contains several SoloLakehouse-specific defaults. Before splitting, convert these into environment-driven values.

Required configuration keys:

```bash
PRODUCT_ID=finlakehouse
COMPOSE_PROJECT_NAME=finlakehouse

OBJECT_STORE_PROVIDER=minio
OBJECT_STORE_ENDPOINT=http://minio:9000
OBJECT_STORE_EXTERNAL_ENDPOINT=http://localhost:9000
OBJECT_STORE_ACCESS_KEY=...
OBJECT_STORE_SECRET_KEY=...

DATA_BUCKET=finlakehouse-data
AUDIT_BUCKET=finlakehouse-audit
MLFLOW_ARTIFACT_BUCKET=finlakehouse-mlflow
WAREHOUSE_URI=s3a://finlakehouse-data/warehouse/

TRINO_USER=finlakehouse
TRINO_URL=http://localhost:8080
MLFLOW_TRACKING_URI=http://localhost:5000
OPENMETADATA_URL=http://localhost:8585
SUPERSET_URL=http://localhost:8088
```

Notes:

- Keep MinIO as the initial implementation.
- Avoid names like `MINIO_*` in new application-level code unless the setting is truly MinIO-only.
- Existing lower-level compatibility variables such as `S3_ACCESS_KEY`, `S3_SECRET_KEY`, and `MLFLOW_S3_ENDPOINT_URL` can remain while the stack still uses S3-compatible clients.

### 3. Parameterize Storage Locations

Replace hard-coded storage assumptions with entity-level values.

Configuration that must become entity-aware:

- Main data bucket, currently equivalent to `sololakehouse`.
- MLflow artifact bucket, currently equivalent to `mlflow-artifacts`.
- Hive warehouse URI, currently equivalent to `s3a://sololakehouse/warehouse/`.
- Trino Hive and Iceberg schema locations.
- Future v2.6 audit bucket.
- Superset Trino connection names and URIs.
- OpenMetadata service names.

The target model should be:

```text
entity config -> object store bucket names -> Hive warehouse -> Trino catalogs -> Dagster assets -> governance evidence
```

### 4. Parameterize Runtime State

Because the two entities will run on separate VPS hosts, port and container-name conflicts are less important than they would be on one machine. Still, each entity must own its runtime state clearly.

Each VPS should keep:

```text
/opt/<product_id>/app/       # checked-out code or release artifact
/opt/<product_id>/data/      # runtime bind mounts
/opt/<product_id>/backup/    # local backup staging
/opt/<product_id>/logs/      # optional host-level logs
/opt/<product_id>/.env       # entity-specific configuration
```

The current `docker/data/` model is acceptable for local reference use, but product entities should either:

- keep bind mounts under an entity-specific root, or
- document that the repository checkout itself is the entity runtime root.

### 5. Establish a Lightweight SLH Portal

Before splitting product entities, add a lightweight portal as the unified browser entrypoint for the SoloLakehouse template.

The portal should not become a heavy application platform. Its job is to make the running system legible at a glance and to guide demo execution.

Minimum portal capabilities:

- Show entity identity: `PRODUCT_ID`, runtime version, domain, and environment.
- Link to core UIs: MinIO/object store console, Trino, MLflow, Dagster, OpenMetadata, Superset, and health JSON.
- Display service health summary from the existing verification/health-check surface.
- Display pipeline/demo readiness: whether the stack is healthy enough to run `make demo`.
- Show the demo implementation flow:
  - `make verify`
  - Dagster `demo_data_flow_job`
  - Bronze -> Silver -> Gold data flow
  - Trino Hive Gold and Iceberg Gold row-count checks
  - optional `make pipeline` for MLflow experiment coverage
- Provide links to `docs/make-demo-guide.md`, `docs/DEMO_RUNBOOK.md`, and `docs/DEMO_RUNBOOK_EN.md`.
- Be configurable per entity so FinLakehouse and Aviation Lakehouse can reuse the same portal with different labels, links, and domain context.

Implementation guardrails:

- Keep the portal lightweight and local-first.
- Prefer reusing `scripts/verify-setup.py`, `scripts/verify-demo.py`, and `scripts/health-server.py` outputs instead of inventing a parallel health model.
- Do not introduce a new database for the portal in Phase 1.
- Do not make the portal a replacement for Dagster, Superset, OpenMetadata, or MLflow.
- Treat the portal as an operator/demo entrypoint, not as an end-user data product UI.

The target result is one URL that answers two questions:

```text
Is this lakehouse entity healthy?
What is the exact demo/data-flow path I should follow next?
```

### 6. Prepare Backup and Restore Procedures

Before the first entity runs continuously, define backup and restore for:

- Object store data buckets.
- Object store MLflow artifact bucket.
- Object store audit bucket.
- PostgreSQL databases:
  - Hive Metastore
  - MLflow
  - Dagster
  - Superset
- OpenMetadata MySQL.
- OpenMetadata Elasticsearch, if retained as state rather than rebuilt.
- Entity `.env` and release metadata.

Minimum backup commands or scripts should cover:

```bash
mc mirror <entity-object-store>/<bucket> <backup-root>/<bucket>
pg_dump --format=custom --dbname=hive_metastore
pg_dump --format=custom --dbname=mlflow
pg_dump --format=custom --dbname=dagster_storage
pg_dump --format=custom --dbname=superset_metadata
```

Do not create a long-running entity until at least one restore drill has succeeded on a disposable host or disposable data directory.

### 7. Prepare Dataset Identity and Governance Naming

The entity split should not wait for v2.6, but v2.6 governance should influence naming now.

Define stable dataset IDs before production-like operation starts:

```text
fin.ecb_rates_bronze
fin.dax_daily_bronze
fin.ecb_rates_silver
fin.dax_daily_silver
fin.ecb_dax_features_gold
fin.ecb_dax_features_iceberg

aviation.<source>_bronze
aviation.<cleaned_dataset>_silver
aviation.<feature_dataset>_gold
```

Rules:

- Logical dataset IDs must survive storage changes.
- Physical paths may change during migration.
- Governance contracts should point from logical ID to current physical locations.
- v2.6 lineage evidence should use these stable IDs.

### 8. Decide What Not to Change Yet

Do not replace MinIO before the first entity split.

Reason:

- Entity split changes product identity and runtime ownership.
- Object-store replacement changes the deepest persistence layer.
- v2.6 changes governance evidence and audit behavior.

Combining all three increases migration risk and makes failures difficult to diagnose.

The correct preparation is to make object-store configuration replaceable, while keeping MinIO as the initial provider.

### Phase 1 Exit Criteria

- Entity contract exists.
- Runtime identity is configurable.
- Data, audit, MLflow, and warehouse locations are configurable.
- A lightweight portal exists as the shared operator/demo entrypoint.
- Backup and restore procedure is documented and tested once.
- Dataset ID naming convention exists.
- MinIO is treated as the current S3-compatible provider, not as the product identity.

## Phase 2: Split Out Two Domain Entities

### Goal

Create two independently running product entities from the prepared SoloLakehouse template.

The output of this phase is:

- one running `finlakehouse` VPS,
- one running `aviation-lakehouse` VPS,
- both initially based on the same accepted v2.5 baseline,
- both using MinIO initially,
- both ready for later side-by-side upgrades.

### 1. Create the FinLakehouse Entity

Provision a dedicated VPS.

Recommended host layout:

```text
/opt/finlakehouse/app/
/opt/finlakehouse/data/
/opt/finlakehouse/backup/
/opt/finlakehouse/logs/
/opt/finlakehouse/.env
```

Initial configuration:

```bash
PRODUCT_ID=finlakehouse
COMPOSE_PROJECT_NAME=finlakehouse
DATA_BUCKET=finlakehouse-data
AUDIT_BUCKET=finlakehouse-audit
MLFLOW_ARTIFACT_BUCKET=finlakehouse-mlflow
WAREHOUSE_URI=s3a://finlakehouse-data/warehouse/
TRINO_USER=finlakehouse
```

Initial domain scope:

- ECB rates
- DAX daily data
- existing Bronze -> Silver -> Gold flow
- existing MLflow experiment path
- existing Superset and OpenMetadata integration

FinLakehouse should be the first entity because it is closest to the current v2.5 reference domain.

### 2. Validate FinLakehouse Before Creating Aviation

Run the full local validation path:

```bash
make up
make verify
make demo
make pipeline
make test
```

Operational validation:

- Dagster schedule runs without manual intervention.
- Freshness sensor behavior is acceptable.
- Bronze partitions are created in the entity bucket.
- Silver files are regenerated from Bronze.
- Hive Gold and Iceberg Gold are queryable through Trino.
- MLflow stores metrics and artifacts in the entity artifact bucket.
- OpenMetadata can ingest Trino metadata under an entity-specific service name.
- Superset can query the entity's Trino connection.
- Backups complete and can be restored.

Do not start the aviation entity until FinLakehouse has survived at least one full scheduled cycle.

### 3. Create the Aviation Lakehouse Entity

Provision a second dedicated VPS.

Recommended host layout:

```text
/opt/aviation-lakehouse/app/
/opt/aviation-lakehouse/data/
/opt/aviation-lakehouse/backup/
/opt/aviation-lakehouse/logs/
/opt/aviation-lakehouse/.env
```

Initial configuration:

```bash
PRODUCT_ID=aviation-lakehouse
COMPOSE_PROJECT_NAME=aviation-lakehouse
DATA_BUCKET=aviation-lakehouse-data
AUDIT_BUCKET=aviation-lakehouse-audit
MLFLOW_ARTIFACT_BUCKET=aviation-lakehouse-mlflow
WAREHOUSE_URI=s3a://aviation-lakehouse-data/warehouse/
TRINO_USER=aviation_lakehouse
```

Initial domain scope must be defined separately from FinLakehouse.

Before implementation, decide:

- authoritative aviation source systems,
- ingestion frequency,
- Bronze raw schema,
- Silver cleaned schema,
- Gold assets,
- expected consumers,
- freshness expectations,
- retention expectations,
- whether MLflow is needed immediately or only later.

The aviation entity should not simply rename financial datasets. It needs its own domain contract.

### 4. Keep the Shared Template Clean

After both entities exist, avoid making product-specific changes directly in the shared template unless they are generic platform improvements.

Use this rule:

| Change type | Location |
|---|---|
| Common platform behavior | SoloLakehouse template |
| Fin-specific source, contract, dashboard, model | FinLakehouse entity layer |
| Aviation-specific source, contract, dashboard, model | Aviation entity layer |
| Generic migration tooling | SoloLakehouse template |
| Entity credentials and host config | Entity `.env` / deployment config only |

### Phase 2 Exit Criteria

- `finlakehouse` is running independently on its own VPS.
- `aviation-lakehouse` is running independently on its own VPS.
- Both have unique bucket names, warehouse URIs, artifact locations, metadata service names, and backup paths.
- Both have a known v2.5 release version recorded.
- Both can be rebuilt from code + config + backup.

## Phase 3: Localized Work After Entity Split

### Goal

Turn each copied runtime into a real domain product instead of a generic SoloLakehouse clone.

### 1. FinLakehouse Local Work

FinLakehouse should stabilize the current financial-market path first.

Tasks:

- Rename user-facing labels from SoloLakehouse to FinLakehouse where appropriate.
- Keep dataset IDs under the `fin.*` namespace.
- Review whether ECB and DAX remain the correct first financial sources.
- Add source-level ownership and SLA metadata.
- Make financial dashboards explicitly FinLakehouse dashboards.
- Ensure MLflow experiment names include the product/domain context.
- Define what a daily successful data asset production cycle means.
- Define retention for Bronze, Silver, Gold, audit, and ML artifacts.

Recommended first operating target:

```text
FinLakehouse produces refreshed financial-market Bronze/Silver/Gold data assets every business day, with queryable Gold tables and retained ML experiment artifacts.
```

### 2. Aviation Lakehouse Local Work

Aviation Lakehouse needs more domain design because the current reference implementation is financial.

Tasks:

- Select real or realistic aviation data sources.
- Implement aviation collectors.
- Define Pydantic schemas for raw records.
- Define Bronze layout and rejected-record handling.
- Define Silver transformations.
- Define Gold assets that are meaningful for aviation operations.
- Add quality checks relevant to aviation data.
- Decide whether the first Gold product is analytical, operational, or ML-oriented.
- Build Superset dashboards for aviation consumers.
- Register aviation datasets in OpenMetadata.

Candidate aviation Gold products:

- flight delay features,
- airport route performance,
- aircraft utilization features,
- weather-impact features,
- turnaround-time features,
- cancellation and disruption indicators.

Recommended first operating target:

```text
Aviation Lakehouse produces one reliable Bronze -> Silver -> Gold flow for a single aviation domain question before expanding source coverage.
```

### 3. Entity Operations

Each entity should have its own runbook.

Minimum runbook sections:

- start and stop,
- health check,
- scheduled pipeline behavior,
- manual pipeline trigger,
- backup,
- restore,
- data validation,
- dashboard validation,
- incident notes,
- upgrade procedure,
- rollback procedure.

Minimum daily checks:

- containers healthy,
- latest Dagster run succeeded,
- latest expected Bronze partition exists,
- Silver/Gold row counts are within expected range,
- Trino can query Gold,
- MLflow artifacts are writable if ML is active,
- backup job completed,
- disk usage is below threshold.

### 4. Product Ownership Metadata

Each entity should maintain a small ownership file, for example:

```yaml
product_id: finlakehouse
owner: Jiahong Que
runtime_version: slh-v2.5.x
domain: financial_markets
criticality: medium
upgrade_strategy: side_by_side
object_store_provider: minio
created_at: 2026-xx-xx
```

This metadata later becomes input to governance, audit, and migration reports.

### Phase 3 Exit Criteria

- Each entity has domain-specific datasets and labels.
- Each entity has a runbook.
- Each entity has backup and restore evidence.
- Each entity has a daily operating definition.
- Each entity has a documented owner, runtime version, and storage provider.

## Phase 4: Future Upgrades and Side-by-Side Migration

### Goal

Upgrade `finlakehouse` and `aviation-lakehouse` without risky in-place mutation.

Each upgrade should create a new target runtime beside the old runtime, import or rebuild data, validate output, then cut over.

### 1. Standard Upgrade Pattern

For each entity and each target version:

```text
old entity vN continues running
        |
        v
new entity vN+1 is created beside it
        |
        v
data and metadata are imported or rebuilt
        |
        v
validation gates compare old and new
        |
        v
writes are paused briefly on old
        |
        v
final delta sync
        |
        v
cut over schedules, dashboards, and consumers
        |
        v
old entity remains read-only for rollback
```

### 2. Migration Classification

Before each upgrade, classify every state component.

| Component | Preferred action | Notes |
|---|---|---|
| Bronze object data | copy | Preserve raw data exactly. |
| Rejected records | copy | Important for audit and debugging. |
| Silver object data | copy or rebuild | Rebuild if transformation logic changed. |
| Gold Parquet | rebuild | Prefer deterministic rebuild from Bronze/Silver. |
| Iceberg Gold | rebuild/register | Avoid assuming snapshot continuity across versions. |
| Hive Metastore | recreate/register | Safer than blind DB restore when paths change. |
| Dagster history | export/archive | Do not require old run history inside new scheduler. |
| MLflow metadata | migrate selectively | Preserve important experiments; avoid carrying noise. |
| MLflow artifacts | copy | Keep artifact paths stable or rewrite carefully. |
| OpenMetadata | export/import or re-ingest | Re-ingest is often safer for technical metadata. |
| Superset | export/import | Validate datasets and database connections after import. |
| Audit bucket | copy as immutable archive | v2.6+ evidence must not be overwritten. |

### 3. v2.5 to v2.6 Entity Upgrade

v2.6 adds governance evidence:

- dataset contracts,
- lineage evidence,
- audit bucket,
- WORM/Object Lock behavior,
- OpenMetadata + Iceberg + Dagster lineage join,
- evidence CLI.

Recommended migration approach:

1. Keep the v2.5 entity running.
2. Deploy a fresh v2.6 entity on a new VPS or new runtime root.
3. Copy Bronze and rejected records from v2.5.
4. Copy Silver only if transformation contracts are unchanged; otherwise rebuild Silver.
5. Rebuild Gold and Iceberg Gold in v2.6.
6. Create or update `governance/datasets/*.yaml` for the entity.
7. Re-ingest metadata into OpenMetadata under the v2.6 entity service name.
8. Run the v2.6 lineage evidence command.
9. Validate that audit evidence is generated under the entity audit bucket.
10. Pause old v2.5 writes.
11. Run final object sync.
12. Run v2.6 pipeline and evidence generation again.
13. Cut over schedules and consumers.
14. Keep v2.5 read-only until the observation window ends.

Validation gates:

- `make verify` passes.
- `make test` passes.
- entity pipeline succeeds.
- old and new Bronze object counts match after final sync.
- expected Silver and Gold row counts match or have documented differences.
- Trino can query Hive and Iceberg Gold.
- Superset dashboards load.
- OpenMetadata shows expected datasets.
- lineage evidence exists for critical Gold datasets.
- audit bucket write-once behavior is verified if enabled.

### 4. Object Store Replacement Migration

Do not combine object-store replacement with the initial entity split.

Preferred timing:

- after both entities are stable, and
- after v2.6 evidence flow is understood, or as an explicit v2.7 storage portability workstream.

Target strategy:

```text
old entity with MinIO
        |
        v
new entity with target S3-compatible object store
        |
        v
mirror object data
        |
        v
recreate warehouse/catalog/table metadata
        |
        v
run full pipeline and evidence validation
        |
        v
cut over
```

Object-store migration checklist:

- Confirm target store supports required S3 operations.
- Confirm Trino can read and write through the target endpoint.
- Confirm Hive Metastore warehouse paths point to the target store.
- Confirm MLflow can write artifacts.
- Confirm Dagster assets can read and write objects.
- Confirm large object copy preserves object names and content hashes.
- Confirm audit bucket immutability requirements.
- Rebuild or re-register Iceberg tables rather than relying on old metadata paths.
- Keep old MinIO read-only until the new store passes an observation window.

### 5. Release and Rollback Rules

Every entity upgrade must produce:

- source version,
- target version,
- migration timestamp,
- data copy manifest,
- validation report,
- cutover decision,
- rollback decision,
- old runtime retention period.

Rollback rule:

```text
If target validation fails before cutover, discard target and keep old running.
If target fails after cutover but within observation window, pause target writes and switch consumers back to old read-write or old read-only plus controlled replay.
If target has accepted new writes, rollback requires replaying those writes into the old or replacement target.
```

### 6. Observation Window

Recommended minimum observation windows:

| Change type | Observation window |
|---|---|
| Entity split only | 3-7 days |
| v2.5 -> v2.6 governance upgrade | 7-14 days |
| Object-store replacement | 14 days |
| Major runtime migration, such as Kubernetes | 14-30 days |

During the window:

- old runtime remains available,
- backups are retained,
- new runtime produces daily validation evidence,
- dashboard and query consumers are checked,
- storage growth and failed jobs are monitored.

## Recommended Timeline

### Step A: Finish v2.5 Acceptance

- Freeze the accepted v2.5 baseline.
- Tag the release.
- Record known limitations.
- Do not change object storage yet.

### Step B: Prepare Entity Template

- Parameterize entity identity.
- Parameterize bucket and warehouse names.
- Add audit bucket naming even before v2.6 uses it.
- Add the lightweight portal as the shared operator/demo entrypoint.
- Document backup and restore.
- Define dataset ID naming.

### Step C: Create FinLakehouse

- Deploy on dedicated VPS.
- Keep MinIO.
- Run existing financial domain.
- Stabilize operations.

### Step D: Create Aviation Lakehouse

- Deploy on dedicated VPS.
- Keep MinIO.
- Add aviation-specific data contracts and pipelines.
- Stabilize operations.

### Step E: Upgrade Entities to v2.6

- Use side-by-side migration for FinLakehouse first.
- Apply lessons to Aviation Lakehouse.
- Generate lineage evidence and audit artifacts.

### Step F: Plan Object Store Replacement

- Treat storage replacement as its own migration.
- Use side-by-side storage migration.
- Validate Trino, Hive, Dagster, MLflow, OpenMetadata, Superset, and audit behavior.

## Master Checklist

### Before Entity Split

- [ ] v2.5 accepted and tagged.
- [x] Entity contract written (`docs/product-entity-contract.md`).
- [ ] Runtime identity configurable.
- [ ] Buckets configurable.
- [ ] Warehouse URI configurable.
- [ ] MLflow artifact root configurable.
- [ ] Audit bucket planned.
- [ ] Lightweight portal planned and implemented.
- [x] Dataset ID convention defined (`docs/dataset-governance-naming.md`).
- [ ] Backup procedure written.
- [ ] Restore drill completed.
- [ ] MinIO retained as initial provider.
- [ ] Object-store abstraction prepared.

### FinLakehouse

- [ ] VPS provisioned.
- [ ] Entity `.env` created.
- [ ] Buckets initialized.
- [ ] Stack starts.
- [ ] `make verify` passes.
- [ ] `make demo` passes.
- [ ] `make pipeline` passes.
- [ ] Dagster schedule verified.
- [ ] Trino Gold verified.
- [ ] MLflow artifact write verified.
- [ ] OpenMetadata ingestion verified.
- [ ] Superset connection verified.
- [ ] Backup completed.
- [ ] Restore tested.
- [ ] Runbook written.

### Aviation Lakehouse

- [ ] VPS provisioned.
- [ ] Entity `.env` created.
- [ ] Aviation source selected.
- [ ] Bronze schema defined.
- [ ] Silver schema defined.
- [ ] Gold product defined.
- [ ] Buckets initialized.
- [ ] Stack starts.
- [ ] Pipeline succeeds.
- [ ] Trino Gold verified.
- [ ] OpenMetadata ingestion verified.
- [ ] Superset dashboard verified.
- [ ] Backup completed.
- [ ] Restore tested.
- [ ] Runbook written.

### v2.6 Side-by-Side Upgrade

- [ ] v2.6 target runtime deployed.
- [ ] Old runtime still running.
- [ ] Bronze copied.
- [ ] Rejected records copied.
- [ ] Silver copied or rebuilt.
- [ ] Gold rebuilt.
- [ ] Iceberg Gold rebuilt or re-registered.
- [ ] Dataset contracts created.
- [ ] OpenMetadata re-ingested or imported.
- [ ] Superset imported and validated.
- [ ] Evidence CLI succeeds.
- [ ] Audit bucket validated.
- [ ] Final delta sync completed.
- [ ] Cutover completed.
- [ ] Old runtime retained read-only.
- [ ] Observation window completed.

### Object Store Replacement

- [ ] Target object store selected.
- [ ] Required S3 compatibility verified.
- [ ] Trino read/write verified.
- [ ] Hive warehouse verified.
- [ ] Dagster object access verified.
- [ ] MLflow artifact write verified.
- [ ] Data mirror completed.
- [ ] Table metadata rebuilt.
- [ ] Pipeline succeeds.
- [ ] Evidence generation succeeds.
- [ ] Cutover completed.
- [ ] Old MinIO retained read-only.

## Final Position

The entity split should happen before replacing MinIO, but the entity split must prepare for object-store replacement.

The stable order is:

```text
v2.5 acceptance
  -> parameterize entity template
  -> create FinLakehouse with MinIO
  -> create Aviation Lakehouse with MinIO
  -> localize domain pipelines
  -> upgrade each entity to v2.6 with side-by-side migration
  -> replace MinIO later through a separate side-by-side storage migration
```

This keeps each change understandable, testable, and reversible.
