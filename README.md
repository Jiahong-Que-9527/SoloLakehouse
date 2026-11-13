<p align="center"><img src="docs/img/slh-brand.png" width="220" alt="SoloLakehouse logo"></p>

<h1 align="center">SoloLakehouse</h1>

<p align="center"><strong>A personally operated data and AI platform, built on a lakehouse foundation</strong></p>

<p align="center">
  <a href="docs/design/v3/README.md">V3 construction plan</a> &middot;
  <a href="docs/architecture.md">Reference architecture</a> &middot;
  <a href="docs/quickstart.md">Compose reference</a> &middot;
  <a href="projects/README.md">Projects</a> &middot;
  <a href="docs/README.md">Documentation</a> &middot;
  <a href="docs/roadmap.md">Roadmap</a> &middot;
  <a href="TASKS.md">Development TODO</a>
</p>

![SoloLakehouse platform overview: finance reference, separate aviation workload, and planned v3 infrastructure](docs/img/sololakehouse-platform-overview.png)

*Conceptual overview of the reference capabilities and v3 direction. The new
cluster and GitOps deployment remain planned; aviation code and datasets are
maintained separately.*

**Current stage — v3 design and repository preparation.** Three Mini PCs have
not been provisioned. The Proxmox/K3s cluster, GitOps deployment, and new
infrastructure directories describe a construction plan. They are not a
deployed platform or a completed migration.

SoloLakehouse started with a practical question: can one person understand a
data platform from ingestion through storage, SQL, model experiments, and
recovery? The repository contains the finance reference implementation and
the contracts, lineage, quality checks, and experiment evidence built around it.
The next step is to make that foundation reproducible and operable through
infrastructure as code and GitOps.

<!-- [Codex · 2026-11-13] Project entry points and source ownership. -->

## Projects and engineering sources

- [Finance](projects/finance/README.md) is the public reference implementation.
  Its project page maps the canonical code and contracts, reproduction steps,
  and environment status.
- [Aviation](docs/workloads/aviation.md) is a separately operated workload.
  SoloLakehouse maintains the public case description. The private pipeline,
  datasets, and detailed operating evidence remain with that workload.

The [project index](projects/README.md) records each project's ownership and
entry points. Git versions code, contracts, architecture decisions, and
deployment definitions. Live data, runtime state, credentials, and backups
are managed in their respective systems. The [roadmap](docs/roadmap.md)
defines scope, and [TASKS.md](TASKS.md) defines execution order.

## Architecture at a glance

```mermaid
%%{init: {"flowchart": {"curve": "basis", "nodeSpacing": 24, "rankSpacing": 32, "htmlLabels": false}}}%%
flowchart TB
    accTitle: SoloLakehouse reference capabilities and planned v3 architecture
    accDescr: Four layers separate code delivery, planned infrastructure, retained data capabilities, and planned operations. Solid elements are reference capabilities; dashed elements are future work.

    subgraph delivery["01  |  Code and delivery"]
        direction LR
        repo["SoloLakehouse monorepo"] --> checks["CI checks"]
        checks -.-> images[("Immutable images")]
        images -.-> release["GitOps configuration PR"]
        release -.-> flux["Flux reconciliation"]
    end

    subgraph foundation["02  |  V3 infrastructure - planned"]
        direction LR
        provision["OpenTofu + cloud-init / Ansible"]
        hostOne["PVE 01 + K3s VM 01"]
        hostTwo["PVE 02 + K3s VM 02"]
        hostThree["PVE 03 + K3s VM 03"]
        cluster["K3s server / worker cluster"]

        provision -.-> hostOne & hostTwo & hostThree
        hostOne & hostTwo & hostThree -.-> cluster
    end

    subgraph capabilities["03  |  Retained SLH capabilities - migration planned"]
        direction LR
        sources["ECB rates + FX + EWG"] --> dagster["Dagster orchestration"]
        quality["Contracts / quality / lineage"] --> dagster
        dagster --> lake[("S3 + Iceberg tables")]
        catalog[("PostgreSQL + Hive catalog")] --> lake
        lake --> trino["Trino SQL"]
        trino --> consumers["OpenMetadata + Superset"]
        dagster --> mlflow["MLflow + model evidence"]
    end

    subgraph operations["04  |  Operations and recovery - planned"]
        direction LR
        telemetry["Metrics / alerts / runbooks"]
        backups[("Independent NAS backups")]
        restore["Consistent catalog + data restore"]
        telemetry ~~~ backups
        backups -.-> restore
    end

    delivery -.->|"Provision and deploy"| foundation
    foundation -.->|"Target runtime"| capabilities
    capabilities -.->|"Observe and protect state"| operations

    classDef existing fill:#e8f3ef,stroke:#527c6c,color:#17392b,stroke-width:1px;
    classDef data fill:#fbf2df,stroke:#ae9158,color:#503d1b,stroke-width:1px;
    classDef planned fill:#edf1fb,stroke:#7488b5,color:#253b60,stroke-width:1px,stroke-dasharray:5 4;
    classDef recovery fill:#fff5e7,stroke:#b78d50,color:#553e1c,stroke-width:1px,stroke-dasharray:5 4;

    class repo,checks,sources,dagster,quality,trino,consumers,mlflow existing;
    class lake,catalog data;
    class images,release,flux,provision,hostOne,hostTwo,hostThree,cluster,telemetry planned;
    class backups,restore recovery;

    style delivery fill:none,stroke:#94a3b8,stroke-width:1px
    style foundation fill:none,stroke:#94a3b8,stroke-width:1px,stroke-dasharray:5 4
    style capabilities fill:none,stroke:#729887,stroke-width:1px
    style operations fill:none,stroke:#b99a68,stroke-width:1px,stroke-dasharray:5 4
```

Solid elements describe retained reference capabilities; dashed elements describe
planned delivery, hosting and recovery. Kubernetes placement is a target design,
not a running deployment. Each planned host carries one server/worker VM; the
S3 implementation and backup procedures still require their scoped validation.
See the [target architecture](docs/design/v3/architecture.md) for responsibilities
and failure-domain boundaries.

## What is here today

| Area | Implemented reference / boundary |
|---|---|
| Data flow | ECB policy rates and FX, plus Alpha Vantage EWG, a German-equity ETF proxy; Bronze/Silver/Gold Iceberg transformations. |
| Runtime path | Docker Compose, Dagster, PostgreSQL, Hive Metastore, MinIO, Trino, MLflow, OpenMetadata, and Superset. Existing paths are retained. |
| Governance | Dataset contracts, quality checks, source/run/snapshot lineage, ML evidence, and operational evidence adapters. Evidence limitations remain explicit. |
| Aviation | The primary operated use case is maintained separately. This public clone contains its [integration guide](docs/workloads/aviation.md), not the private pipeline or datasets. |
| V3 | A documented single-repository target for Proxmox, K3s, Flux, deployment packaging, recovery, and phased validation. No hardware deployment has been performed. |

Aviation uses historical observations and observation-derived taxi-in proxies.
These are not airport-validated labels or a demonstrated air-cargo transaction
loop. Finance remains the public, reproducible engineering reference. Training,
evaluation, and MLflow tracking are in scope; online serving and an operations
agent are later candidates.

## V3: three hosts, one repository, clear ownership

The planned starting hardware is three GMKtec M6 Ultra systems, each with 32GB
RAM and a 1TB SSD. Each PVE host initially carries one 24GiB K3s server VM that
also runs application workloads. An existing NAS is the proposed independent
backup destination. Resource budgets are estimates awaiting measurement.

| Repository area | Responsibility | Current maturity |
|---|---|---|
| [infra/](infra/README.md) | PVE resources, VM lifecycle, state and recovery design | Design only |
| [bootstrap/](bootstrap/README.md) | First boot, K3s installation, upgrades and rebuilds | Design only |
| [deploy/](deploy/README.md) | Reusable SLH deployment packaging and application contracts | Design only |
| [gitops/](gitops/README.md) | Flux entry point, platform components and environment configuration | Design only |
| Existing Python modules | Ingestion, transformation, governance, orchestration and ML | Existing code; preserved |
| [docs/design/v3/](docs/design/v3/README.md) | Construction sequence, decisions, migration and acceptance | Design; checks recorded separately |

The control boundaries are deliberate:

- **OpenTofu + cloud-init/Ansible** establish VMs and K3s from an external
  administration environment.
- **CI** tests code and produces immutable images and, later, versioned charts.
- **Flux** reconciles reviewed deployment configuration.
- **Dagster** schedules and executes data and ML work.

Cluster bootstrap, IaC state, decryption keys, and recovery instructions must
remain usable when the target cluster is unavailable. Git can reconstruct
configuration; recovering databases, catalogs, objects, and model artifacts
requires separate, tested procedures.

Start with the [complete construction plan](docs/design/v3/README.md),
[target architecture](docs/design/v3/architecture.md), and
[storage/recovery design](docs/design/v3/storage-and-recovery.md).
The [roadmap](docs/roadmap.md) owns scope; [TASKS.md](TASKS.md) owns execution order.

## Continue development

**Next: D1.1 construction-input decisions.** The D0 framework is merged;
infrastructure and runtime implementation remain pending. Start with
[development TODO](TASKS.md#start-here-in-the-next-session),
[roadmap](docs/roadmap.md) and [AGENTS](AGENTS.md). TASKS owns the only active
queue, deliverables, dependencies and acceptance. It also records later S3,
VM/bootstrap, GitOps, hardware, migration and operational work. Tool-specific
entrypoints point to these sources rather than duplicate their status.

## Inspect and validate the repository

These commands inspect the repository without starting the runtime:

```bash
make help
make docs-check
make check-agent-docs
```

With the documented Python dependencies installed, the existing checks remain:

```bash
make lint
make typecheck
make validate-contracts
make test
```

These results establish only what each check exercises. A passing Markdown
check does not validate a Helm chart, a VM, a data restore, or cluster HA.

## Use the existing finance reference

The [quick start](docs/quickstart.md), [demo](DEMO.md), and
[runbook](RUNBOOK.md) describe the existing Compose reference path.
It remains the development and regression reference while v3 is constructed.

The previously observed clean-clone MinIO client image-pull problem has not
been resolved or revalidated by this design change. Object-storage supply and
compatibility are explicit [pre-migration work](docs/design/v3/storage-and-recovery.md#object-storage-decision).
Do not infer a successful fresh deployment from retained configuration or
from a separately operated environment.

Routine shutdown uses `make down` and preserves bind-mounted data.
The legacy `clean`, `reset-mlflow-db`, and `purge-legacy-docker-volumes`
targets are disabled: data destruction requires an exact, reviewed recovery
or disposal procedure, not a general cleanup command.

## What completion will mean

V3 acceptance requires more than running Pods:

1. Rebuild the declared environment with its documented bootstrap inputs.
2. Trace a reviewed code change through image digest, GitOps commit, and run.
3. Execute and validate the reference Iceberg/Gold workflow.
4. Recover a consistent catalog and object-data state in isolation.
5. Regress existing governance, MLflow, metadata, and BI capabilities.
6. Record measured resource use, failure behavior, and recovery times.

The [migration and validation plan](docs/design/v3/migration-and-validation.md)
defines the evidence and boundaries for each stage. No delivery date, hardware
availability, production SLA, or whole-platform HA is claimed.

## History and license

The [pre-v3 checkpoint](https://github.com/Jiahong-Que-9527/SoloLakehouse/releases/tag/pre-v3-2026-11-10)
preserves the earlier main baseline. Superseded planning and the original
versions of rewritten entry documents are retained in the
[pre-v3 archive](docs/history/pre-v3/README.md), with source hashes and commit
provenance.

[Project history](docs/history/README.md) · [Platform story](docs/platform-overview.md) · [MIT license](LICENSE)
