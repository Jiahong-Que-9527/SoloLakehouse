# SoloLakehouse

SoloLakehouse is a personal portfolio of independent **Data and AI platform engineering** projects. It covers the full path a data product travels: reliable ingestion from imperfect sources, validated and versioned datasets, delivery on managed cloud services, and the DevOps practice that ships, observes and recovers all of it. Each project owns its inputs, environment and acceptance checks, and records the evidence behind every claim.

![Aviation intelligence airport illustration](docs/images/aviation-intelligence-airport-illustration.png)

## Projects

### [Fraport ADS-B Intelligence](Fraport-adsb-intelligence/README.md)
Can incomplete aircraft observations around Frankfurt Airport support reproducible analysis? A local collector pulls hourly ADS-B state vectors from OpenSky's Trino source, commits Parquet partitions through checksummed manifests and resumes interrupted runs without duplicating data. A DuckDB transformation layer builds a neutral Silver layer and a use-case Gold market, then publishes versioned releases through a Release Gate that blocks failing data.
**Evidence:** 32 monthly batches accepted and backed up; 109.6M state-vector rows in October 2026 alone; an interrupted hour recollected with an identical SHA-256.

### [DevOps Engineering](Devops-engineering/README.md)
How does a service travel from a source change to a verified deployment, and how is it recovered after a bad release? A small data-quality service is taken through seven stages: reproducible development, containers, CI with supply-chain checks, manifest-driven delivery with digest rollback, Kubernetes and GitOps drift drills, monitored incident recovery, and a reusable template.
**Evidence:** D03–D07 accepted with recorded drills; the template onboarded a second service with its own identity.

### [Google Cloud](gcp/README.md)
Data products on German electricity-load data, deployed with Terraform and Workload Identity Federation on free-tier services. G01 publishes versioned windows to Cloud Storage and BigQuery from a scheduled Cloud Run Job. G02 serves them through an authenticated API over an authorized view. G03 folds duplicate, late and conflicting events from Pub/Sub into one current state. G04 adds a governed release with contracts and provenance.
**Evidence:** G01–G03 verified live with zero destroys; two independent annual exports produced the same checksum.

### [ML Engineering](Mlops-engineering/README.md)
Closing the loop of one ML system on a synthetic EV-charging network: point-in-time features with leakage tests, rolling backtests, MLflow lineage, a registered and releasable training pipeline, batch and online serving, drift monitoring and Dagster orchestration. **Status:** planned; M01 is next.

### [Databricks](databricks/README.md)
Six design briefs on financial time series: Delta lakehouse tables, scheduled jobs, CDC with corrections, Unity Catalog governance, forecasting with MLflow, and reusable workspace environments. **Status:** design only, no application code yet.

## Delivery progress

![Delivery progress](docs/images/progress.svg)

The earlier self-hosted lakehouse (Compose, Dagster, Iceberg, Trino) is preserved in a [pinned snapshot](https://github.com/Jiahong-Que-9527/SoloLakehouse/tree/741e6da82cdc2cad207aa6ee707b8fb157b0174a); a fixture reproduction is a later milestone.

## Capabilities and target roles

| Project | What it shows | Target roles |
|---|---|---|
| Fraport ADS-B Intelligence | Resumable bulk ingestion, manifest commits, data quality semantics, DuckDB Silver and Gold modelling, data contracts and release gates | Data Engineer · Data Platform Engineer |
| DevOps Engineering | Docker, GitHub Actions, image supply-chain checks, digest-based rollback, k3d and Helm GitOps, observability, incident drills, service templates | DevOps Engineer · Platform Engineer · SRE |
| Google Cloud | Cloud Run, BigQuery, Pub/Sub, Terraform, Workload Identity Federation, authorized views, idempotent event processing, governed data products | Cloud Data Engineer · Backend Engineer (data) |
| ML Engineering *(planned)* | Point-in-time features, evaluation, model registry, drift monitoring, orchestration | MLOps Engineer · ML Engineer |
| Databricks *(planned)* | Delta, Jobs, CDC, Unity Catalog, workspace provisioning | Lakehouse Engineer |

A capability counts as demonstrated only where the repository holds code, tests and recorded evidence.

## Run the checks

With Python 3.12+ and [uv](https://docs.astral.sh/uv/). Tests use synthetic data and need no cloud account or live source.

```bash
cd Fraport-adsb-intelligence/01-opensky-acquisition   # or gcp/01-european-energy-pipeline
uv sync --locked && uv run --locked pytest
```

Raw datasets, credentials and runtime state stay outside Git; the repository holds code, contracts, designs and evidence summaries.

[Engineering roadmap](docs/roadmap.md) · [Aviation plan](Fraport-adsb-intelligence/docs/project-plan.md) · [Project template](project-template/README.md)
