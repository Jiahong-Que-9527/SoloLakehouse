# SoloLakehouse Capability Showcase Guide

How to **explain**, **demonstrate**, and **prove** what this platform can do.

Use this document when preparing a walkthrough, portfolio recording, customer
demo, or internal review. It complements the timed v2.5 script in
[`DEMO.md`](../DEMO.md) and the detailed `make demo` notes in
[`make-demo-guide.md`](make-demo-guide.md).

**Authority reminder:** version status and backlog live in
[`roadmap.md`](roadmap.md) and [`TASKS.md`](../TASKS.md). This guide does not
redefine them.

---

## 1. How to talk about the platform

SoloLakehouse is a **reference implementation** of a lakehouse on one Docker
Compose node: real financial inputs (ECB + EWG), Iceberg medallion tables,
Dagster orchestration, Trino query, OpenMetadata, Superset, MLflow, and a
**governance / evidence plane** that writes SHA-256-bound manifests to an audit
bucket.

### One sentence

> Start the stack, move live market data through Bronze → Silver → Gold, query
> it, orchestrate it daily, and produce auditable evidence that binds a run to
> catalog metadata and an Iceberg snapshot.

### Proof style (use every time)

For each capability, leave three artifacts:

1. **Command or UI action**
2. **Observable result** (exit code, row count, SUCCESS run, green check)
3. **Durable evidence** when it exists (audit object path, hash, run id)

Do **not** claim compliance certification, enterprise WORM, production IAM, or
regulatory readiness without a matching implementation and verification record.
Limitations belong in `CHANGELOG.md` and release-readiness docs.

---

## 2. Capability inventory (quick map)

| # | Capability | What it is | Primary proof surface |
|---|------------|------------|------------------------|
| 1 | Runtime / health | Compose stack is up and checked | `make verify`, health UI |
| 2 | Medallion data path | ECB + EWG → Bronze/Silver/Gold Iceberg | `make demo` / pipeline, Trino, MinIO |
| 3 | Orchestration | Dagster assets, schedule, sensors | Dagster UI |
| 4 | Dataset governance | Machine-validated contracts | YAML + `make validate-contracts` |
| 5 | Lineage evidence | OM + Iceberg + Dagster join | Audit `manifest.json` |
| 6 | Data audit store | Hash-bound manifests in locked bucket | MinIO `sololakehouse-audit` |
| 7 | ML + AI governance | Train/track + five-tuple + model evidence | MLflow + audit model-evidence |
| 8 | Policy hooks | Contract-derived metadata for agents | `make export-policy-hooks` |
| 9 | Catalog / BI consume | OpenMetadata + Superset | OM UI, Superset chart |
| 10 | Openness / sovereignty | Catalog boundary + component origin | `make interoperability-proof`, `make sovereignty-report` |
| 11 | Promotion / rollback | Gate results as evidence | `make promotion-evidence`, `make rollback-drill` |
| 12 | Secrets discipline | Secret-handling checks + rotation drill | `make secrets-discipline` |
| 13 | Ops / SLO evidence | Runtime health → evidence manifest | `make operational-evidence` |
| 14 | Reliability / recovery / alert | Stay up, restore, notify | verify, drills, email sensors, Block `K` |
| 15 | K8s readiness gate | Migration readiness evidence (not K8s yet) | `make k8s-readiness` |

---

## 3. Suggested demo arcs

### A. Core lakehouse (15–20 min) — always start here

Follow [`DEMO.md`](../DEMO.md): setup → verify/health → `make demo` → MinIO
layers → Trino Gold → Dagster run → brief OM/MLflow glance.

### B. Governance & evidence add-on (8–12 min)

1. Open one contract under `governance/datasets/`.
2. Run `make validate-contracts`.
3. Open today’s successful Dagster run; copy `run_id`.
4. In MinIO audit bucket, open
   `lineage/<dataset_id>/<date>/<run_id>/manifest.json`.
5. Align `dagster_run_id`, `iceberg_snapshot_id`, `openmetadata_table_fqn`,
   `record_sha256`.
6. Optional: open matching `model-evidence/*.json` and MLflow tags.

### C. Full “platform story” (25–35 min)

A → B → one consume UI (Superset or OM) → one ops command
(`make operational-evidence` or a restart self-heal) → close with honest
boundaries.

---

## 4. Detailed capability cards

Each card: **intent**, **show**, **say**, **do not say**.

### 4.1 Runtime and health

**Intent:** The reference stack is runnable and observable.

**Show**

```bash
make verify
make health   # or open http://127.0.0.1:8090/health
```

**Say:** “Every core service is health-checked; failures are visible, not
hidden.”

**Do not say:** “This is a production multi-AZ deployment.”

---

### 4.2 Medallion data path (ECB + EWG)

**Intent:** Real inputs land in Iceberg Bronze/Silver/Gold and are queryable.

**Show**

```bash
make demo
# or rely on daily full_pipeline_job SUCCESS
```

- MinIO: `s3://sololakehouse/warehouse/` Bronze / Silver / Gold paths  
- Trino: `SELECT count(*), max(...) FROM iceberg.gold.<table>`

**Say:** “Batch finance path: ECB SDW rates and Alpha Vantage EWG through a
full medallion pipeline.”

**Do not say:** That `data/sample/dax_daily_sample.csv` is a supported market
leg (Owner Decision D4 retired it).

---

### 4.3 Orchestration (Dagster)

**Intent:** Materialization is scheduled, visible, and recoverable from the UI.

**Show**

- UI: http://localhost:3000  
- Asset graph for bronze → silver → gold → `ml_experiment`  
- `daily_pipeline_schedule` (weekdays 06:00 UTC)  
- Sensors: freshness, lineage evidence, success/failure email  

**Say:** “Daily job is the happy path; sensors add freshness and evidence
emission.”

---

### 4.4 Dataset governance (contracts)

**Intent:** Governed datasets have a machine-readable identity and rules.

**Show**

- Files: `governance/datasets/*.yaml`  
  Point at `dataset_id`, owner, layer, physical location, quality /
  freshness fields.
- Command:

```bash
make validate-contracts
```

**Say:** “Governance starts as contracts the platform can validate—not a Word
policy alone.”

**Detail:** Contracts drive quality gates and evidence joins. Adding a dataset
means adding YAML that passes the schema; CI runs the same validation.

---

### 4.5 Lineage evidence

**Intent:** A successful materialization can be joined across three sources.

**Sources joined**

| Source | What must be present |
|--------|----------------------|
| OpenMetadata | Table FQN + catalog owner |
| Iceberg | Current snapshot id + metadata path |
| Dagster | Successful run that materialized the asset |

**Show**

1. Dagster run id for a SUCCESS pipeline.  
2. Audit object:

```text
s3://sololakehouse-audit/lineage/<dataset_id>/<UTC-date>/<dagster_run_id>/manifest.json
```

3. Inside the manifest: matching run id, snapshot id, OM FQN, `record_sha256`.

**Manual / backfill**

```bash
make lineage-evidence \
  DATASET_ID=fin.ecb_german_equity_proxy_features_gold \
  DAGSTER_RUN_ID=<run-id>
```

Happy path: `lineage_evidence_sensor` after SUCCESS (requires usable OM token
and owned tables). Fail loudly—no partial manifest.

**Say:** “Lineage here means a hash-bound join of catalog + table snapshot +
orchestrator run—not only a UI graph.”

**Do not say:** “OpenMetadata screen alone is our audit trail.”

See also [`governance-evidence-layout.md`](governance-evidence-layout.md).

---

### 4.6 Data audit store

**Intent:** Evidence is stored as immutable-oriented audit objects.

**Show**

- Bucket: `sololakehouse-audit` (MinIO console http://localhost:9001)  
- Layout: `lineage/<dataset_id>/<date>/<run_id>/…`  
- Files: `manifest.json`, optional `model-evidence/*.json`  
- `make verify` reports audit-bucket Object Lock configuration  

**Say:** “Audit output is a first-class artifact with digest binding and Object
Lock on the reference MinIO bucket.”

**Do not say:** “Certified WORM” or “regulatory archive.” This is a **local
reference** of write-once audit storage.

---

### 4.7 ML tracking and AI governance

**Intent:** Training is reproducible enough to audit; metrics are secondary.

**Show**

- MLflow http://localhost:5000 — experiment `ecb_dax_impact`  
- Hyperparameter grid (XGBoost / LightGBM) with `TimeSeriesSplit`  
- Best-run tags `slh.*` (snapshot, dagster run, feature version, commit,
  contract hash)  
- Audit `model-evidence/...json` + model card text  

**Say:** “The demo classifier is weak on purpose (sparse event rows). The
product claim is traceable training evidence, not alpha.”

**Do not say:** That accuracy alone proves production ML readiness. Policy
hooks remain **metadata_only**.

---

### 4.8 Policy hooks

**Intent:** Contracts expose consumer / risk hints for downstream agents.

**Show**

```bash
make export-policy-hooks
```

**Say:** “These hooks are derived metadata for governance storytelling and
future enforcement—not an authorization system today (ADR-021).”

---

### 4.9 Catalog and BI consume

**Intent:** Downstream humans can find and chart governed tables.

**Show**

- OpenMetadata http://localhost:8585 — Trino service tables, owners  
- Optional: `make om-ingest-trino` to refresh metadata  
- Superset http://localhost:8088 — one clear chart (e.g. EUR market tile helpers)  

**Say:** “Consume layer sits on the same Iceberg/Trino path as the pipeline.”

Until Gold event volume is larger, keep BI modest (see deferred polish notes in
`TASKS.md`).

---

### 4.10 Openness and sovereignty evidence

**Intent:** Show catalog-boundary and component-origin thinking without adding
engines for vanity.

**Show**

```bash
make interoperability-proof
make sovereignty-report
# FORMAT=json for machine output
```

**Say:** “We produce openness / origin evidence on the current Hive-first
boundary; REST/Polaris is selectable evaluation, not the default stack.”

---

### 4.11 Promotion and rollback evidence

**Intent:** Promotion and rollback are gated results, not tribal knowledge.

**Show**

```bash
make promotion-evidence
make rollback-drill
```

**Say:** “Gates emit SHA-256-bound manifests (ADR-022).”

Escape hatches such as `ALLOW_UNHEALTHY=1` exist only to **document** a known
limitation—never as the default happy path.

---

### 4.12 Secrets discipline

**Intent:** Secret handling is checked mechanically.

**Show**

```bash
make secrets-discipline
make secrets-rotation-drill ROTATED_KEYS=POSTGRES_PASSWORD,S3_SECRET_KEY
```

**Say:** “Config lives in `.env.shared`, secrets in `.env.secrets`, merged by
`make init-env`—not `cp .env.example .env`.”

---

### 4.13 Operational / SLO evidence

**Intent:** Runtime health can be packaged as evidence.

**Show**

```bash
make operational-evidence
```

**Say:** “Operations produce manifests with explicit gates, not only log
lines.”

---

### 4.14 Reliability, recovery, alerting

**Intent:** Prove the system stays up, can be restored, and can notify humans.
Block `K` in `TASKS.md` is the hardening track during Compose operation.

| Theme | What “good” looks like | How to demonstrate |
|-------|------------------------|--------------------|
| Reliability | Services restart; daily pipeline stays green; freshness holds | `docker stop` a core container and watch `restart: unless-stopped`; multi-day Dagster SUCCESS; freshness sensor / checks; `make verify` |
| Recovery | Real backup + restore drill with recorded result | Follow `docs/entity-backup-restore-runbook.md`; complete/record `K9`/`K10` drills; OM path is **re-ingest**, not blind MySQL restore |
| Alerting | Failures reach a human without staring at UI | Pipeline success/failure email sensors; planned daily `make verify` push (`K7`) |

**Say:** “Reliability is consecutive green plus self-heal; recovery is a
recorded restore; alerting is push notification.”

**Do not say:** “We have DR” without a dated restore drill artifact.

---

### 4.15 Kubernetes readiness (gate only)

**Intent:** Show migration readiness evidence without running Kubernetes now.

**Show**

```bash
make k8s-readiness
```

**Say:** “v3.0 is a future runtime migration; this gate records whether we are
allowed to claim readiness.”

---

## 5. Evidence command cheat sheet

| Command | Proves |
|---------|--------|
| `make verify` | Service health (+ audit lock check) |
| `make demo` | Acceptance data flow; Gold queryable |
| `make pipeline` | Full Dagster job path |
| `make validate-contracts` | Contract schema validity |
| `make lineage-evidence DATASET_ID=… DAGSTER_RUN_ID=…` | Three-source lineage manifest |
| `make export-policy-hooks` | Policy metadata export |
| `make interoperability-proof` | Catalog interoperability evidence |
| `make sovereignty-report` | Component-origin report |
| `make promotion-evidence` | Promotion gates |
| `make rollback-drill` | Rollback drill record |
| `make operational-evidence` | SLO / ops evidence |
| `make secrets-discipline` | Secrets handling gates |
| `make secrets-rotation-drill ROTATED_KEYS=…` | Rotation drill record |
| `make k8s-readiness` | K8s migration readiness gate |
| `make om-ingest-trino` | Refresh OM table metadata from Trino |

Every evidence command should **exit non-zero and write nothing** when a
required source is missing. That failure mode is a feature—show it if asked.

---

## 6. UI map

| Surface | URL (local defaults) | Use in demo |
|---------|----------------------|-------------|
| Health | http://127.0.0.1:8090/health | Opening health slide |
| Dagster | http://localhost:3000 | Assets, runs, sensors |
| Trino | http://localhost:8080 | Ad-hoc SQL / UI |
| MinIO | http://localhost:9001 | Warehouse + audit bucket |
| MLflow | http://localhost:5000 | Experiments / tags |
| OpenMetadata | http://localhost:8585 | Catalog owners / FQN |
| Superset | http://localhost:8088 | One business chart |

Loopback-only bindings are intentional for the reference security model.

---

## 7. Sample talk track (≈30 minutes)

| Min | Segment | Proof |
|----:|---------|-------|
| 0–2 | What / why / boundary | README one-liner; “reference, not SaaS” |
| 2–8 | Bring-up & health | `make verify` / health UI |
| 8–14 | Data flow | `make demo` or today’s pipeline; Trino Gold |
| 14–17 | Storage layers | MinIO Bronze/Silver/Gold |
| 17–20 | Orchestration | Dagster asset graph + schedule |
| 20–26 | Governance + lineage + audit | Contract YAML → validate → audit manifest |
| 26–28 | ML governance | MLflow best run + model-evidence (honest metrics) |
| 28–30 | Close | Boundaries: single node, policy metadata-only, K8s later; point to roadmap |

---

## 8. Honest boundaries (say these out loud)

- **Runtime:** Docker Compose single node until an Owner Decision starts v3.0.  
- **Market leg:** Live EWG via Alpha Vantage only—no sample DAX CSV fallback.  
- **Policy hooks:** Metadata, not enforcement.  
- **Audit Object Lock:** Reference MinIO behavior, not a compliance certificate.  
- **ML scores:** Sparse event-study classifier; do not sell accuracy.  
- **Streaming / crypto (L4 Phase 2):** Deferred until Owner Decision.  
- **Block `K`:** Reliability hardening during operation; restore drill must be
  recorded before claiming DR.

---

## 9. Prep checklist before a live demo

- [ ] Stack healthy: `make verify`  
- [ ] Recent SUCCESS `full_pipeline_job` (or run `make demo`)  
- [ ] `OPENMETADATA_AUTH_TOKEN` usable (or admin password refresh path)  
- [ ] OM tables for demo datasets have **owners**  
- [ ] Audit bucket contains at least one fresh `manifest.json`  
- [ ] Browser tabs pre-opened (health, Dagster, MinIO, Trino, OM, MLflow)  
- [ ] One contract YAML and one manifest path bookmarked  
- [ ] Know which Gold table name the current stack uses (event-study vs daily)  

---

## 10. Related documents

| Doc | Role |
|-----|------|
| [`DEMO.md`](../DEMO.md) | Fixed 20–30 min v2.5 recording script |
| [`make-demo-guide.md`](make-demo-guide.md) | `make demo` deep dive |
| [`DEMO_RUNBOOK_EN.md`](DEMO_RUNBOOK_EN.md) | Longer EN runbook + acceptance |
| [`governance-evidence-layout.md`](governance-evidence-layout.md) | Manifest path and Object Lock |
| [`dataset-governance-naming.md`](dataset-governance-naming.md) | `dataset_id` rules |
| [`operational-slo.md`](operational-slo.md) | SLO framing |
| [`promotion-discipline.md`](promotion-discipline.md) | Promotion evidence |
| [`entity-backup-restore-runbook.md`](entity-backup-restore-runbook.md) | Backup/restore |
| [`ASSESSMENT_LAKEHOUSE_DAX_ECB.md`](ASSESSMENT_LAKEHOUSE_DAX_ECB.md) | Honest self-assessment |
| [`TASKS.md`](../TASKS.md) Block `K` | Reliability / recovery / alert backlog |

---

## 11. Closing line for audiences

> SoloLakehouse shows a full open-source lakehouse path on one node—and treats
> governance as **executable evidence**: contracts you validate, lineage you
> hash-bind, audits you can open by run id. What it does not do is pretend that
> evidence alone is a compliance certification or a multi-region production
> fabric.
