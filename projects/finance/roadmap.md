# Finance project roadmap

<!-- [Codex · 2026-11-13] Design proposal. -->

Start at the [Finance project page](README.md) for the canonical source and
reproduction path. SoloLakehouse owns the public Finance reference code,
tests, contracts and future environment-specific definitions. The operated
Finance instance and its data have their own operating records. The stages
below are learning and acceptance milestones. The [active queue](../../TASKS.md)
owns implementation status.

## Shared acceptance data

Use a versioned public or synthetic ECB Bronze fixture and the existing
[ECB Silver contract](../../governance/datasets/fin.ecb_rates_silver.yaml).
The [reference conversion](src/ecb_bronze_to_silver.py)
establishes the starting behavior. Record the input checksum, date window,
expected rows, and comparison rules for ordering, nulls and numeric precision.
Cover DFR preference and fallback, duplicate dates, first-row null change and
basis-point rounding. Specify the tie-break for conflicting duplicate dates
before expecting identical output across engines. Test fixed-input semantics
with a fixed reference clock. Exercise live freshness separately. Record cloud
table mappings separately from the canonical contract's local physical location.

## Local

| Stage | Exercise and deliverable | Acceptance |
|---|---|---|
| Beginner | Follow the Compose reference with fixtures. Record the commands, image versions and clean-clone image issue. | Reproduce a fixture run and Trino Gold query, or report the precise blocking step and keep runtime acceptance open. |
| Foundation | Learn PVE networking, OpenTofu and cloud-init through D1.1 and D1.3. Produce a single-guest spec and, in the implementation stage, its static definitions. | Document inputs and run format, provider validation and cloud-init schema checks. H0/H1 own actual host and guest acceptance. |
| Intermediate | Learn Helm, K3s and Flux through D1.4 and H0–H2. Deliver a versioned stateless application and reviewed GitOps configuration. | Trace source SHA to image digest and deployed Git revision. Show functional verification, drift correction and rollback. |
| Advanced | Complete D1.2 storage compatibility independently when its inputs are ready. After H2 and storage selection, migrate a Finance fixture in W0 and cover parity in W1. | Query and reconcile Gold, then restore a matching catalog and object-data recovery point in isolation. Record capability-by-capability parity. |
| Mastery | Execute O0 recovery and capacity exercises with a runbook. | Rehearse host or guest failure and recovery. Publish measured RPO/RTO, workload limits and remaining gaps. |

Use the [existing Local task dependencies](../../TASKS.md#next-bounded-work)
and the [v3 design](../../docs/design/v3/README.md).

## GCP

| Stage | Exercise and deliverable | Acceptance |
|---|---|---|
| Beginner | Learn project, region, billing, IAM and BigQuery. Manually load and query a small fixed fixture in an isolated project or dataset. | Identify the dataset, runtime identity, query result and cost evidence. |
| Foundation | Use Cloud Run Jobs, GCS and BigQuery SQL. Produce one reproducible ECB Bronze-to-Silver job. | Reconcile against the shared fixture and expected Silver rows, with run ID and query results. |
| Intermediate | Define resources in the future `infra/gcp/` area and workload code in `projects/finance/runtimes/gcp/`. Design Terraform validation and deployment via GitHub OIDC/WIF with separate deploy and runtime identities. | Release a recorded image digest to the intended environment from a reviewed SHA. Verify a job execution and its result. |
| Advanced | Design incremental windows, checkpoints, retry and backfill. Exercise partial failure and rollback in isolation. | Rerun the same window without duplicate results, recover failed work and verify the previously accepted version. |
| Mastery | Design a rebuild and restore runbook, measure batch cost and elapsed time, and explain the resource trade-offs. | Rebuild the declared environment and demonstrate verified output recovery with measured time and cost. |

## Databricks

| Stage | Exercise and deliverable | Acceptance |
|---|---|---|
| Beginner | Verify workspace, compute, storage, permissions and quotas. Load a fixed fixture into Delta and query it. | Record workspace capabilities, query output and any feature limitations. |
| Foundation | Use SQL or PySpark and a Job to produce the same Silver rows. | Reconcile with the shared fixture and expected output, with a Job run ID and query result. |
| Intermediate | Define the Job and environment target in a Bundle under the future `projects/finance/runtimes/databricks/` area. Verify the workspace's deployment identity and use workload federation where supported. | Validate, deploy and run the Bundle from a reviewed source SHA and record the deployment target and artifact identity. |
| Advanced | Exercise retries, incremental processing, access isolation and code rollback. | Re-run a failed window without duplicates, restore a prior code version and separately verify isolated data recovery. |
| Mastery | Rebuild the Job from Git, review governance and cost, and evaluate workspace IaC where it has a concrete ownership role. | Reproduce accepted output from recorded versions and compare operational trade-offs with Local and GCP. |

The cloud tracks share the fixture and acceptance rules. Each track also needs
its own account, permissions, budget and isolated target. Cross-environment
comparison follows independently verified results. See the
[project CI/CD design](../../docs/design/project-delivery.md) for trigger rules.
