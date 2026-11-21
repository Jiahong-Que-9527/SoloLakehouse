# SoloLakehouse

SoloLakehouse is a personal portfolio of independent **Data and AI platform engineering** projects. It covers the full path a data product travels: reliable ingestion from imperfect sources, validated and versioned datasets, delivery on managed cloud services, and the DevOps practice that ships, observes and recovers all of it. Each project owns its inputs, environment and acceptance checks, and records the evidence behind every claim.

![Aviation intelligence airport illustration](docs/images/aviation-intelligence-airport-illustration.png)

## Projects

| Project | Question it answers | What is built | Evidence / status |
|---|---|---|---|
| [**Fraport ADS-B Intelligence**](Fraport-adsb-intelligence/README.md) | Can **incomplete aircraft observations** around Frankfurt Airport support **reproducible analysis**? | Local OpenSky collector with **checksummed manifests** and **resumable runs**; **DuckDB** Silver and Gold layers; versioned releases through a **Release Gate** that blocks failing data | **34 monthly batches** accepted and backed up; **109.6M rows** in October 2026 alone; interrupted hour recollected with an **identical SHA-256** |
| [**DevOps Engineering**](Devops-engineering/README.md) | How does a service travel from a **source change** to a **verified deployment**, and recover from a bad release? | **Seven stages:** reproducible dev, containers, **CI** with supply-chain checks, **digest rollback**, **Kubernetes GitOps** drills, incident recovery, reusable template | **D03–D07 accepted** with recorded drills; template **onboarded a second service** |
| [**Google Cloud**](gcp/README.md) | How are **data products** delivered and governed on managed cloud services? | Scheduled **Cloud Run** batch job to **Cloud Storage and BigQuery**; authenticated **API** over an authorized view; **Pub/Sub** event processing with dedup and replay; governed release with contracts | **G01–G04 verified live** with zero destroys; two annual exports reproduced the **same checksum**; the first **governed release** survived a live block–withdraw–republish drill |
| [**ML Engineering**](Mlops-engineering/README.md) | Can one ML system be **closed end to end**, from features to **drift-triggered retraining**? | **Point-in-time features**, rolling backtests, **MLflow** lineage, release gate, batch and online serving, drift monitoring, **Dagster** | **Planned**; M01 is next |
| [**Databricks**](databricks/README.md) | How does a **governed lakehouse** product run on Databricks? | **Delta** tables, scheduled jobs, **CDC** with corrections, **Unity Catalog**, MLflow forecasting, workspace provisioning | **Six design briefs**; no application code yet |

## Delivery progress

![Delivery progress](docs/images/progress.svg)

The earlier self-hosted lakehouse (Compose, Dagster, Iceberg, Trino) is preserved in a [pinned snapshot](https://github.com/Jiahong-Que-9527/SoloLakehouse/tree/741e6da82cdc2cad207aa6ee707b8fb157b0174a); a fixture reproduction is a later milestone.

## Capabilities and target roles

| Project | What it shows | Target roles |
|---|---|---|
| Fraport ADS-B Intelligence | **Resumable bulk ingestion**, **manifest commits**, data quality semantics, **DuckDB** Silver and Gold modelling, **data contracts** and **release gates** | **Data Engineer** · **Data Platform Engineer** |
| DevOps Engineering | **Docker**, **GitHub Actions**, image **supply-chain checks**, **digest-based rollback**, **k3d and Helm GitOps**, **observability**, incident drills, service templates | **DevOps Engineer** · **Platform Engineer** · **SRE** |
| Google Cloud | **Cloud Run**, **BigQuery**, **Pub/Sub**, **Terraform**, **Workload Identity Federation**, authorized views, **idempotent event processing**, governed data products | **Cloud Data Engineer** · **Backend Engineer (data)** |
| ML Engineering *(planned)* | **Point-in-time features**, evaluation, **model registry**, **drift monitoring**, orchestration | **MLOps Engineer** · **ML Engineer** |
| Databricks *(planned)* | **Delta**, **Jobs**, **CDC**, **Unity Catalog**, workspace provisioning | **Lakehouse Engineer** |

A capability counts as demonstrated only where the repository holds code, tests and recorded evidence.

## Run the checks

With Python 3.12+ and [uv](https://docs.astral.sh/uv/). Tests use synthetic data and need no cloud account or live source.

```bash
cd Fraport-adsb-intelligence/01-opensky-acquisition   # or gcp/01-european-energy-pipeline
uv sync --locked && uv run --locked pytest
```

Raw datasets, credentials and runtime state stay outside Git; the repository holds code, contracts, designs and evidence summaries.

[Engineering roadmap](docs/roadmap.md) · [Aviation plan](Fraport-adsb-intelligence/docs/project-plan.md) · [Project template](project-template/README.md)
