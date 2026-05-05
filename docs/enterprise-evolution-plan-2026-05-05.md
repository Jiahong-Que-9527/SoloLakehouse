# SoloLakehouse — Enterprise Evolution Plan

> Date: 2026-05-05
> Companion document: `project-state-overview-2026-05-05.md`
> Purpose: translate "five real enterprise problems" into engineering actions that land in SoloLakehouse, and provide an explicit **compliance requirement ↔ technical capability** mapping.

---

## 0. Overview — five real enterprise problems (the North Star)

| # | Enterprise problem | Value position | Primary audience |
|---|---|---|---|
| **P1** | Regulatory data lineage | Highest value / regulator-mandated | DACH mid-size banks, asset managers, exchanges (DekaBank, Commerzbank, Deutsche Börse class) |
| **P2** | Data sovereignty and vendor-lock-in escape | Geopolitical-budget tier | EU (especially DACH) listed companies, government-linked FIs |
| **P3** | The "poor-man's Databricks" for mid-size FIs | Real market gap | ~200-headcount asset managers, private banks, regional banks |
| **P4** | Cross-cloud / hybrid-cloud unified data layer | Strategic architecture must-have | Any FI executing a multi-cloud strategy |
| **P5** | Compliance foundation for AI/ML engineering | Demand spike in next 18 months | Financial decisioning systems under EU AI Act |

> The five are not parallel. There is **strong dependence** — P1 is the governance bedrock that the other four sit on. The plan is sequenced accordingly.

---

## 1. Master mapping table — compliance requirement ↔ technical capability

This table is the **master index** of this plan. The chapters below expand each row.

> ⚠ **Scope note**: some regulatory citations in this table are **structural mappings** that hold under "if a customer brings in-scope business data into this platform". The project's demo data itself (public ECB rates + DAX index) does **not** directly trigger MiFID II (not trade reporting), Schrems II (not personal data), or ECB internal-model supervision (not capital-risk internal models). Concrete compliance applicability follows the customer's actual data and regulatory jurisdiction.

| Compliance / business requirement | Source (regulation / standard) | Technical capability in SoloLakehouse | Status (2026-05-05) | Target version |
|---|---|---|---|---|
| End-to-end machine-readable lineage | DORA Art.6 (ICT risk framework), Art.8 (ICT systems/protocols/tools identification and business-function mapping), BaFin MaRisk AT 4.3.4 | Lineage graph from joining OpenMetadata + Iceberg snapshot + Dagster asset lineage; one-command JSON evidence pack export | OpenMetadata deployed; Dagster lineage exists internally; the join is missing | **v2.6** (E1/E2) |
| Hour-scale evidence of data-asset impact during incidents | Supporting capability for DORA Art.17 incident-management process + Art.19 / incident-reporting RTS; regulatory reporting windows (classification / initial / intermediate reports) are **not** this platform's audit-evidence response SLA | A `make lineage-evidence DATASET=X DATE=Y` command outputting a signable evidence bundle (schema, sources, transforms, consumers, owner, timestamps); supports customer reporting but does not fulfill the customer's reporting obligation by itself | Does not exist | **v2.6** (E2/E5) |
| Dataset ownership / SLA / quality-class registry | BaFin MaRisk AT 4.3.4; ECB Guide to internal models (2024 update) data-governance section (directly applicable only when customers run regulated internal models on the platform) | `governance/datasets/*.yaml` data contract files, CI-validated, synced with OpenMetadata | Planned in TASKS.md (Block A1); not implemented | **v2.6** (E3) |
| Immutable audit log | MiFID II RTS 24 (at least 5-yr record retention; longer periods depend on customer jurisdiction and internal retention policy), DORA Art.6 | Iceberg snapshots + in-bucket `audit/` + WORM mode (MinIO Object Lock); Dagster run history archived externally | Iceberg snapshots exist by default; WORM and external archive not implemented | **v2.6** (E4) |
| Data sovereignty (no cross-border, no US-cloud SaaS) | EU Data Act, Schrems II (only when processing personal data), DORA Art.28 (ICT third-party dependency management) | Every component runs on EU IDC, private K8s, or on-prem; zero US-SaaS dependencies; "component → origin → license" report generator | Already 100% open-source with zero SaaS; origin report not generated | **v2.7** (E6/E7) |
| Vendor-lock-in escape via Iceberg | EBA Guidelines on outsourcing arrangements (EBA/GL/2019/02), paragraph 70 (exit strategies), DORA Art.28 | Gold uses Iceberg; readable from Trino / Spark / Flink / DuckDB simultaneously; schema/snapshots are migratable as a whole | Gold is already Iceberg; multi-engine compatibility structurally present, not yet demonstrated | v2.5 ✓ → demo in **v2.7** (E8/E15) |
| Low-TCO high-capability (on-prem-first lakehouse) | Commercial, not regulatory | Compose/K8s deploy shape + complete lakehouse + orchestration + ML + governance; first freeze the TCO/customer-evidence pack and K8s readiness, with real multi-node Helm left to v3.0 | Single host stands up; TCO doc and multi-node Helm not provided | **v2.9** (readiness / evidence shape for E10-E13) |
| Cross-cloud data portability | DORA Art.28, EBA Guidelines on outsourcing arrangements (EBA/GL/2019/02), paragraph 70 | Iceberg + S3 protocol + swappable object stores (MinIO / Ceph / AWS S3 / Azure Blob) + Helm values layering | Protocol layer in place; Helm values only have placeholders | **v2.7** (E14-E17; Helm placeholders filled in v3.0) |
| ML decisions are explainable and auditable | EU AI Act Title III (high-risk system obligations apply on 2026-08-02), ECB Guide to internal models (2024 update), PRA SS1/23 (UK customers only) | MLflow run ↔ Gold data version ↔ Iceberg snapshot ↔ Dagster run id binding; auto-generated model card; provides "evidence form" — does **not** auto-validate content | MLflow deployed; run ↔ data-version binding fields not unified | **v2.8** (E18/E19) |
| Decision provenance ("which data produced this prediction") | EU AI Act Art.13 (transparency obligation) | Inference emits `decision_evidence_id`; reverse-lookup yields model_run + data_snapshot + feature_version | Does not exist | v3.1 |
| Controlled, citation-bearing RAG/Copilot for compliance Q&A | EU AI Act + internal model governance | ComplianceRAG built on OpenMetadata + Iceberg + docs; every answer carries citations + data version | Does not exist | v3.1 |
| Secrets and least privilege | DORA Art.9 (ICT security), ISO/IEC 27001 A.9 (access control) | Vault / cloud secret manager injection + service-identity separation + secret-rotation drill | TASKS.md Block D planned; not implemented | **v2.9** (local secrets discipline) + **v3.0** (managed secrets) |
| SLO-driven incident response | DORA Art.11 (incident response and recovery), EBA/GL/2019/04 (ICT and security risk management) | Minimal SLO set (pipeline success rate, Gold freshness, asset-check pass rate, E2E latency) + alerts + runbooks + drill records | TASKS.md Block C planned; not implemented | **v2.9** (SLO emit + dashboard) + **v3.0** (Prometheus / alerting) |
| Environment isolation + promotion gates | DORA Art.6 (ICT risk framework and change control), EBA/GL/2019/04 §31-equivalent (change management) | dev → staging → prod, Helm values layering; promotion checklist + rollback drill evidence | TASKS.md Block B planned; not implemented | **v2.9** (promotion-pack form + Iceberg rollback drill) + **v3.0** (real multi-environment) |

> This table will serve as the **compliance reconciliation sheet** appended to every release checklist.
> The "Target version" column follows v2.5 (delivered) → v2.6 (governance evidence) → v2.7 (openness evidence) → v2.8 (ML compliance evidence) → v2.9 (operational evidence) → v3.0 (K8s + multi-env + managed secrets). See `docs/history/v2.6-planning.md` through `v2.9-planning.md` for details.

---

## 2. P1 — Regulatory data lineage (top priority)

### 2.1 Regulatory context

| Regulation / standard | Key article | What it requires |
|---|---|---|
| **DORA** (in force 2025-01-17) | Art.6 ICT risk framework, Art.8 ICT asset identification / business-function mapping, Art.17 incident-management process | Critical financial data assets must have identifiable and traceable data flows; regulatory incident reporting windows are not the platform audit-evidence response window |
| **BaFin MaRisk AT 4.3.4** | Data quality and consistency | Data governance must hold evidence of "data owner, purpose, quality, processing lineage" |
| **MiFID II RTS 22 / RTS 24** | Trade reporting fields, record retention | Lineage of reporting fields must be verifiable; RTS 24 records are typically retained on an at-least-5-year basis, with concrete retention matched to customer jurisdiction and internal policy |
| **ECB TRIM** | Targeted Review of Internal Models | Lineage of critical model input data must be documented and auditable |

### 2.2 Real pain point in DACH today

> Mid-size banks / asset managers: data scattered across Snowflake, Databricks, on-prem Oracle, **lineage maintained in Excel**. When BaFin shows up, the response is a fire drill.

### 2.3 Half-built parts SoloLakehouse already has

- `OpenMetadata` 1.5.x in default stack (delivered in v2.5) → asset metadata + UI
- `Iceberg` Gold tables ship with native `snapshot_id` / `manifest` / `commit_log` → immutable change history
- `Dagster` asset graph + run history → orchestration-side lineage ("which upstream assets did this run consume")
- `Pydantic` schema + rejected-record landing → ingestion-side evidence
- `structlog` structured event logs

The parts are there. **The glue is not.**

### 2.4 Engineering actions (v2.6)

**E1. Three-source lineage fusion**
- Build `governance/lineage_join.py` that joins, by dataset id:
  - OpenMetadata asset metadata (owner, SLA, quality class)
  - Iceberg snapshot (data version, commit time, change record)
  - Dagster run (orchestration version, upstream assets, executor / trigger)
- Output a unified `LineageRecord` JSON schema
- After every `full_pipeline_job`, write to `audit/lineage/<dataset>/<run_id>.json`

**E2. Evidence-pack export CLI**
- `make lineage-evidence DATASET=ecb_dax_features_iceberg DATE=2026-04-30`
- Output:
  - Dataset snapshot (schema + snapshot_id + row count)
  - Upstream chain back to original source
  - Orchestration context (Dagster run url + timestamp + trigger)
  - Quality evidence (asset-check results, reject counts)
  - Owner / business purpose / SLA / quality class (from data contract)
  - PGP-signable manifest

**E3. Data contract files**
- New `governance/datasets/*.yaml`:
  ```yaml
  dataset_id: ecb_dax_features_iceberg
  data_owner: data-platform@example.eu
  business_purpose: "ECB rate event study features for DAX response model"
  refresh_sla: "T+1 by 06:30 UTC"
  quality_class: "B (model input, non-regulatory-reporting)"
  consumers: ["mlflow:ecb_dax_response_v3", "superset:dashboard:dax_event_study"]
  source_of_truth: "ecb_silver + dax_silver via Dagster gold_features"
  retention: "7 years"
  classification: "internal-confidential"
  ```
- CI validation (schema + required fields)
- Two-way sync with OpenMetadata (daily sync job)

**E4. WORM immutable audit storage**
- Enable MinIO Object Lock on the `audit/` bucket
- Default retention: at least 5 yr for MiFID II RTS 24 scope; longer customer jurisdiction, contract, or internal-policy requirements override via the data contract
- Daily archive of Dagster run history to `audit/dagster-runs/<date>.parquet`

**E5. Drill**
- Stage a fake event: BaFin requests full lineage evidence for `ecb_dax_features_iceberg` as of 2026-04-15, within 24h
- Run `make lineage-evidence`, record time-to-output and artifacts
- Archive the drill report under `docs/governance-v3-runbook.md`

### 2.5 Maps to TASKS.md
- Block A1 (dataset governance baseline)
- Block A2 (quality gate)
- Block H: Lineage Evidence (now added to `TASKS.md`)

---

## 3. P2 — Data sovereignty and vendor-lock-in escape

### 3.1 Regulatory context

| Regulation | Concern |
|---|---|
| **EU Data Act** (applies from 2025-09) | Data sovereignty, interoperability, portability |
| **Schrems II / GDPR** | Constraints on transatlantic data transfer |
| **DORA Art.28** | ICT third-party dependency management; exit strategies |
| **EBA Guidelines on outsourcing arrangements (EBA/GL/2019/02), paragraph 70** | Critical services need executable exit strategies and must be replaceable in a reasonable timeframe |

### 3.2 Key fact

European companies — especially DACH — have escalated dependence on AWS / Azure / Snowflake to **board-level** discussions. This is no longer a technical issue; it is a geopolitical one — and **geopolitical issues carry the largest budgets**.

### 3.3 SoloLakehouse's natural advantages

The repo already satisfies:
- 100% open-source components (MIT / Apache 2.0 / AGPL — commercially usable)
- Zero US-SaaS dependencies
- Every layer is replaceable: MinIO ↔ Ceph ↔ S3, Trino ↔ Spark ↔ Flink, PostgreSQL ↔ any PG-compatible
- Gold is Iceberg (open table format) — **this single fact is what goes into the compliance dossier**

### 3.4 Engineering actions

**E6. Sovereignty evidence generator**
- Implement `scripts/generate-sovereignty-report.py`
- Output `docs/sovereignty-report.md`:
  - Per component → maintainer → HQ country → license → phone-home behaviour
  - Per external dependency → EU-replaceable yes/no
  - Per data resting place → physical location control mechanism

**E7. Vendor replacement matrix**
- In `docs/portability-matrix.md`, list per-layer:
  - Replacement option if the vendor disappears tomorrow
  - Replacement effort estimate (person-days)
  - Data migration path (especially Iceberg → Spark / Flink / DuckDB demos)

**E8. Multi-engine compatibility demo**
- New `examples/multi-engine/` directory
- Same Iceberg Gold table, read by 4 engines:
  - Trino (default)
  - Spark (PySpark)
  - DuckDB
  - Flink (streaming read)
- Each demo is runnable in 5 minutes, with output screenshots
- This is the strongest evidence for Iceberg's "openness"

**E9. Exit playbook**
- `docs/exit-playbook.md`: when a customer migrates off AWS / Snowflake, what does the SoloLakehouse path look like
- Includes: Iceberg metadata re-pointing, Trino catalog switch, Helm values adjustment

### 3.5 Compliance interface

The deliverables must be drop-in usable for the customer's:
- DORA ICT third-party dependency register
- EBA outsourcing exit plan
- Internal IT audit "openness compliance self-assessment"

---

## 4. P3 — The "poor-man's Databricks" for mid-size FIs

### 4.1 Commercial reality

- Databricks for a 200-headcount asset manager: **€500k+/yr**
- Add Snowflake / Fivetran / dbt cloud / data team headcount: **€1.2M+/yr** floor
- SoloLakehouse goal: **1/10 TCO, 80% capability**

### 4.2 Capability comparison

| Capability domain | Databricks | SoloLakehouse v2.5 | Gap |
|---|---|---|---|
| Table format | Delta Lake | Iceberg ✓ | — |
| SQL engine | Photon | Trino ✓ | Performance layer (no Photon-equivalent) |
| Orchestration | Workflows | Dagster ✓ | UX gap |
| ML platform | MLflow (hosted) | MLflow ✓ | Model serving absent (ADR-011 keeps it out of scope) |
| Data catalog | Unity Catalog | OpenMetadata ✓ | Row-level security absent |
| Governance | Unity Catalog policies | Data contracts (to be built) | Full set absent |
| BI | Databricks SQL Dashboards | Superset ✓ | UX gap |
| Collaborative notebooks | Databricks Notebook | — | Absent (fillable with JupyterHub) |
| Multi-user / teams | Workspace | — | Absent (Helm values not in place) |
| Deployment | Multi-cloud SaaS | Compose (v2.5) / Helm (v3.0 planned) | Multi-node deploy path |

### 4.3 Engineering actions (v2.9 freezes evidence/readiness; v3.0 implements the real runtime)

**E10. Multi-node Helm chart**
- Implement `helm/sololakehouse/` chart
- Values layering: `values-dev.yaml`, `values-staging.yaml`, `values-prod.yaml`
- Key services support HA: Trino coordinator/worker, Hive Metastore, PostgreSQL

**E11. Multi-user / RBAC**
- Trino with LDAP / OIDC (achievable on OSS without EE)
- Superset OAuth → role mapping
- OpenMetadata SSO

**E12. JupyterHub integration**
- Optional JupyterHub in default stack (profile-controlled)
- Pre-installed Trino client + MLflow client + iceberg-python
- Per-user namespace isolation

**E13. TCO calculator**
- `tools/tco-calculator/`: user inputs "users, data volume, query concurrency", output:
  - SoloLakehouse on-prem estimate
  - SoloLakehouse on EU IaaS (Hetzner / OVH / IONOS) estimate
  - Databricks reference estimate
- Outputs PDF report (suitable for customer proposals)

**E14. One-shot migration tooling**
- `tools/migrate-from-databricks.py`: scan Delta tables → convert to Iceberg → register in Trino
- `tools/migrate-from-snowflake.py`: UNLOAD → Parquet → Iceberg

### 4.4 Pitch (internal / customer conversation)

> "You are not changing your mental model — you are changing your bill. Databricks taught the industry the Lakehouse design language; SoloLakehouse lets you speak the same language at 1/10 the cost while keeping data sovereignty in-house."

---

## 5. P4 — Cross-cloud / hybrid-cloud unified data layer

### 5.1 Key insight

Iceberg is not "another table format". It is **the lingua franca of enterprise data architecture for the next 5 years**. It makes the following simultaneously possible:
- One dataset readable by Trino, Spark, Flink, DuckDB, Snowflake, BigQuery
- One dataset spread across AWS S3, Azure Blob, GCS, MinIO
- One dataset migratable across engines without schema changes

### 5.2 SoloLakehouse's role

**As a reference implementation (not a product)**, SoloLakehouse demonstrates:
- How an Iceberg table is created (CTAS in `ingestion/trino_sql.py`)
- How Hive Metastore can serve as catalog (with REST catalog as a swap path)
- How multiple engines read the same table (cf. E8)

### 5.3 Engineering actions (overlaps with P2)

**E15. REST catalog alternative demo**
- Fill `docs/decisions/ADR-017-iceberg-rest-catalog-option.md`: Hive Metastore vs Iceberg REST Catalog vs AWS Glue
- Provide a switch demo (compose profile)

**E16. Cross-object-store demo**
- Same Iceberg table — metadata on MinIO, data files distributed across MinIO + simulated S3 (a second MinIO instance posing as S3)
- Demonstrate read across multiple storage backends

**E17. Streaming + batch unification**
- Add a small Flink demo: Flink streaming write into the same Iceberg table
- Show Trino batch read + Flink stream write concurrency safety (Iceberg ACID)

### 5.4 Compliance interface

This rail aligns directly with **DORA Art.28**: customers must be able to swap critical ICT services within reasonable time. The multi-engine demo is the evidence of "swappability".

---

## 6. P5 — Compliance foundation for AI/ML engineering

### 6.1 Regulatory context

| Regulation | Key date | Requirement |
|---|---|---|
| **EU AI Act** | High-risk system obligations apply on 2026-08-02 (some provisions apply earlier / later) | High-risk systems require: risk management, data governance, technical documentation, traceability, human oversight, robustness, cybersecurity |
| **EU AI Act Art.13** | Same high-risk-obligation date | Transparency: users must be able to understand system output |
| **EU AI Act Art.10** | Same high-risk-obligation date | Training datasets must meet quality, relevance, representativeness — and records must be kept |
| **ECB Guide to internal models** | 2024 update | When customers use the platform for regulated internal models, model inputs, assumptions, changes, and validation evidence must be auditable |
| **BaFin** | In force | Algorithmic governance: explainable, auditable, challengeable |

### 6.2 Current state

SoloLakehouse already has:
- MLflow tracking every experiment (params, metrics, artifacts)
- TimeSeriesSplit CV (no leak)
- Training code in git, traceable

But **insufficient**:
- Model run not strongly bound to Gold data version (Iceberg snapshot)
- No automated model-card generation
- No inference-time evidence id
- ComplianceRAG / AuditCopilot / LineageNarrator concepts not realized

### 6.3 Engineering actions

**E18. End-to-end ML lineage binding**
- Fill `docs/decisions/ADR-018-ml-lineage-five-tuple.md` to confirm the ML lineage five-tuple
- In `ml/train_ecb_dax_model.py`, inside `mlflow.start_run()`:
  - Auto-log `iceberg.snapshot_id` (current Gold snapshot)
  - Auto-log `dagster.run_id` (when invoked from an asset)
  - Auto-log `feature_version` (from data contract)
  - Auto-log `code_commit`
- Every model run can now be reverse-resolved to "which data did it consume"

**E19. Auto model card**
- Implement `ml/generate_model_card.py`
- After training, auto-generate a model card aligned with EU AI Act Art.13:
  - Training data source / time range / row count / data contract reference
  - Train / validation / test split methodology
  - Performance metrics (incl. subgroup metrics)
  - Known biases and limitations
  - Intended use and prohibited use
  - Monitoring recommendations
- Store as MLflow artifact + `audit/models/<model_id>/card.md`

**Boundary note: Art.10 evidence form**

v2.8 provides the evidence form needed to document EU AI Act Art.10 inputs: training-data sources, splits, quality checks, representativeness notes, known limitations, and record-retention locations. It does **not** automatically decide whether that content is sufficient, accurate, or compliant in a customer's setting; content validation stays with the customer's data governance, model-risk, and legal process.

**E20. Decision evidence id (v3.1)**
- At inference, every prediction returns `decision_evidence_id`
- The id, in the audit system, resolves to:
  - Which model_run
  - Which data_snapshot that run consumed
  - Which Dagster run produced that snapshot
  - The actual values of the input features
- This is the operational implementation of **EU AI Act Art.13 transparency obligation**

**E21. ComplianceRAG (v3.1, separate subsystem)**
- Sources:
  - OpenMetadata data asset metadata
  - All ADRs + governance docs in repo
  - Iceberg snapshot metadata
  - Dagster run history
- Output: natural-language answers to compliance audit questions, every answer with citations + data version + timestamp
- Examples:
  - "Show me the data sources of model X as of 2026-04-30"
  - "Did asset Y meet its SLA in Q1 2026?"
  - "Who owns dataset Z and what's its quality class?"
- Locally deployable models (Llama 3 family / Mistral / Claude API in a data-resident form)

**E22. AuditCopilot (v3.1, separate subsystem)**
- Proactive RAG: scans runtime events → drafts "if BaFin walks in tomorrow" briefing material
- Weekly auto-generated `audit/weekly-readiness-<date>.md`

**E23. LineageNarrator (v3.1)**
- Auto-translates the lineage graph (from E1) into the regulator's preferred narrative style
- Outputs PDF aligned with BaFin / DORA report templates

### 6.4 Hard boundary (consistent with ADR-011)

- v3.0 still **does not implement model serving** (Triton / vLLM are out of scope)
- E20–E23 belong to v3.1; the precondition is the v3.0 governance bedrock
- The AI layer always sits **on top of** the compliance bedrock — never around it.

---

## 7. Roadmap — six-month milestones

```
2026-Q2 (May–Jun)
└─ M1: P1 governance bedrock MVP
   ├─ Data contract files + CI validation (E3)
   ├─ Three-source lineage fusion + evidence pack CLI (E1, E2)
   ├─ WORM audit storage (E4)
   └─ One drill (E5)

2026-Q3 (Jul–Sep)
└─ M2: P2/P3/P4 sovereignty and portability
   ├─ Sovereignty report generator (E6)
   ├─ Multi-engine demo (E8)
   ├─ Exit playbook (E9)
   ├─ Helm chart + multi-environment values (E10)
   ├─ TCO calculator (E13)
   └─ K8s dev environment running

2026-Q4 (Oct–Dec)
└─ M3: P5 AI/ML compliance bedrock
   ├─ MLflow ↔ Iceberg snapshot binding (E18)
   ├─ Auto model card (E19)
   ├─ SLOs + alerts + runbooks (from TASKS Block C)
   └─ End-to-end drill (incl. simulated regulator)

2027-Q1
└─ M4: AI layer (separate subproject; recommend a separate repo)
   ├─ ComplianceRAG (E21)
   ├─ AuditCopilot (E22)
   └─ LineageNarrator (E23)
```

---

## 8. Mapping to existing TASKS.md

| Plan stage | Corresponding TASKS.md Block | Relationship |
|---|---|---|
| P1 governance bedrock | Block A (governance contracts) + Block C (observability) + Block E (ML governance) + new Block H (Lineage Evidence) | TASKS already plans contracts; this plan adds "lineage evidence" and "WORM audit" |
| P2 data sovereignty | Block I (Sovereignty & Portability Documentation) | Added by this plan and synced into TASKS |
| P3 poor-man's Databricks | Block F (K8s + Helm) + Block G (Terraform) | TASKS already plans deployment path; this plan adds "multi-user, TCO, migration tooling" |
| P4 cross-cloud data layer | Partially covered by Block F | This plan adds "REST catalog, multi-engine demo" |
| P5 AI compliance bedrock | Block E (partial) | TASKS only covers experiment governance; this plan adds "model card, decision evidence, AI subsystems" |

> **Sync status**: `TASKS.md` now contains Block H (Lineage Evidence) and Block I (Sovereignty & Portability Documentation); Block E carries the v2.8 ML lineage five-tuple through ADR-018.

---

## 9. Risks and decision gates

| Risk | Impact | Mitigation |
|---|---|---|
| Compliance narrative outpaces engineering | Pretty docs but nothing runs | Every capability must have an executable `make` entry point; "documented-only" compliance is rejected |
| Scope sprawl, v3.0 slips | Time window lost (DORA already in force; AI Act high-risk system obligations apply on 2026-08-02) | M1 is hard-locked to P1; P2–P5 cannot pull resources before M1 closes |
| ComplianceRAG looks like a toy | Loss of serious customers | Citation tracking + data-version binding mandatory before ship |
| "Poor-man's Databricks" wording offends potential partners | Commercial relationship damage | External wording shifts to "on-prem-first lakehouse for sovereignty-conscious institutions" |
| Single-maintainer overload | Project stalls | Hold ADR-011 boundary strictly; do not expand into serving; the AI layer goes into a separate repo from v3.1 onward |

---

## 10. One-line summary

> **SoloLakehouse already has a small-but-complete open-source Lakehouse core. The next real value is not making it bigger — it is making it the executable answer to DORA / BaFin / MiFID II / AI Act, where every compliance requirement points to a concrete `make` command, a concrete code file, and a concrete evidence artifact in this repo. That is what v3.0 must finish.**

---

## Appendix A — Glossary

| Term | Meaning |
|---|---|
| Data lineage | The complete record of data flow from source to consumer |
| WORM (Write Once Read Many) | A storage mode where written data cannot be modified |
| Data contract | A formal document describing dataset ownership, SLA, quality, consumers |
| Open table format | Iceberg / Delta / Hudi — table formats not locked to a specific engine |
| Data sovereignty | Data location and control align with the host jurisdiction's requirements |
| SLO | Service Level Objective |
| Model card | A standardized doc describing a model's intent, data, performance, limitations |

## Appendix B — Key references

- DORA: Regulation (EU) 2022/2554
- EU AI Act: Regulation (EU) 2024/1689
- BaFin MaRisk: AT 4.3.4 Data governance
- MiFID II RTS 22/24: Trade reporting and record retention
- ECB Guide to internal models (2024 update): data and model-governance expectations for regulated internal models
- EBA Guidelines on Outsourcing Arrangements: GL/2019/02
- EU Data Act: Regulation (EU) 2023/2854
