# SoloLakehouse

A personal portfolio of independent **Data and AI platform engineering** projects: reliable ingestion, governed data products, cloud delivery, and the DevOps path that ships and recovers them.

![Aviation intelligence airport illustration](docs/images/aviation-intelligence-airport-illustration.png)

## Projects

| Project | What it demonstrates | Highlights |
|---|---|---|
| [**Fraport ADS-B Intelligence**](Fraport-adsb-intelligence/README.md) | Frankfurt Airport flight data, from raw observations to a versioned, released dataset | 32 monthly batches accepted; 109M rows in one month; interrupted runs resume with identical checksums |
| [**DevOps Engineering**](Devops-engineering/README.md) | One service from fresh checkout to CI, release, rollback, Kubernetes GitOps and incident recovery | Seven stages D01–D07; a template that onboarded a second service |
| [**Google Cloud**](gcp/README.md) | Cloud data products on German electricity data, deployed with Terraform and Workload Identity Federation | Batch job, authenticated API and event processing live on free-tier SKUs |
| [**ML Engineering**](Mlops-engineering/README.md) | Point-in-time features, evaluation, model registry, serving and drift monitoring | Planned; M01 is next |
| [**Databricks**](databricks/README.md) | Delta lakehouse, jobs, CDC, Unity Catalog and MLflow on financial time series | Design briefs |

![Delivery progress](docs/images/progress.svg)

## Capabilities and target roles

| Project | Core capabilities | Target roles |
|---|---|---|
| Fraport ADS-B Intelligence | Resumable bulk ingestion, manifest commits, DuckDB Silver/Gold modelling, data contracts, release gate | Data Engineer · Data Platform Engineer |
| DevOps Engineering | Docker, GitHub Actions, supply-chain checks, digest rollback, k3d/Helm GitOps, observability, reusable templates | DevOps Engineer · Platform Engineer · SRE |
| Google Cloud | Cloud Run, BigQuery, Pub/Sub, Terraform, WIF, authorized views, governed data products | Cloud Data Engineer · Backend Engineer (data) |
| ML Engineering *(planned)* | Feature pipelines, MLflow lineage, release gates, drift monitoring, Dagster | MLOps Engineer · ML Engineer |
| Databricks *(planned)* | Delta, Jobs, CDC, Unity Catalog, workspace provisioning | Lakehouse / Databricks Engineer |

Capabilities are listed as demonstrated only where the repository holds code, tests and recorded evidence.

## Run the checks

With Python 3.12+ and [uv](https://docs.astral.sh/uv/) installed. The tests use synthetic data and need no cloud account.

```bash
cd Fraport-adsb-intelligence/01-opensky-acquisition   # or gcp/01-european-energy-pipeline
uv sync --locked && uv run --locked pytest
```

## More

[Engineering roadmap](docs/roadmap.md) · [Aviation plan](Fraport-adsb-intelligence/docs/project-plan.md) · [Local and legacy projects](local/self-hosted-lakehouse/README.md) · [Project template](project-template/README.md)
