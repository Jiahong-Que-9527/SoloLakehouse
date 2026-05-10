# SoloLakehouse v2.5 Demo Script

This is the fixed recording script for a 20-30 minute v2.5 walkthrough.

The goal is not to show every feature. The goal is to prove, in one take, that a fresh clone can start the stack, move real financial-market data through Bronze, Silver, and Gold, query it through Trino, and inspect orchestration and lineage surfaces.

## Preconditions

- Use a fresh clone on Linux, macOS, or WSL2.
- Confirm Docker has at least 4 CPU cores, 8 GB RAM, and 10 GB free disk.
- Keep one terminal at the repository root.
- Use browser tabs for:
  - Health dashboard: `http://127.0.0.1:8090/health`
  - Dagster: `http://localhost:3000`
  - Trino: `http://localhost:8080`
  - MinIO Console: `http://localhost:9001`
  - MLflow: `http://localhost:5000`
  - OpenMetadata: `http://localhost:8585`

## Timing

| Time | Segment | Action | Evidence |
|---:|---|---|---|
| 00:00-02:00 | Opening | State what SoloLakehouse is and why it exists. | README one-sentence What / Why / How. |
| 02:00-06:00 | Cold start | Run `git clone`, `cd SoloLakehouse`, then `make setup`. | Setup performs env creation, dependency install, image pull, Compose start, and health wait. |
| 06:00-08:00 | Health surface | Run `make health` and open `http://127.0.0.1:8090/health`. | Every service shows PASS or a clear failing service. |
| 08:00-13:00 | Data flow | Run `make demo`. | Dagster executes the demo data-flow job, then Trino row-count checks pass for Hive Gold and Iceberg Gold. |
| 13:00-17:00 | Three-layer view | Open MinIO and show Bronze, Silver, and Gold object paths. | Bronze/Silver Parquet and Gold feature paths are visible. |
| 17:00-21:00 | Query and compliance angle | Show the Gold SQL checks and explain why auditable row counts matter. | `hive.gold.ecb_dax_features` and `iceberg.gold.ecb_dax_features_iceberg` return rows. |
| 21:00-25:00 | Orchestration | Open Dagster and show the latest successful `demo_data_flow_job` run. | Asset graph and recent run status are visible. |
| 25:00-28:00 | Metadata and ML | Open OpenMetadata and MLflow. | Catalog UI and experiment tracking surface are reachable. |
| 28:00-30:00 | Close | Summarize v2.5 boundary and point to v2.6 roadmap. | v2.5 is a frozen baseline, not a feature backlog. |

## Commands

```bash
git clone https://github.com/Jiahong-Que-9527/SoloLakehouse.git
cd SoloLakehouse
make setup
make verify
make health
make demo
```

For a step-by-step explanation of `make demo`, including the equivalent manual commands and pass/fail criteria for each stage, see [docs/make-demo-guide.md](docs/make-demo-guide.md).

## Demo Data Rule

ECB data must come from the ECB collector path. DAX data must come from the project DAX ingestion path configured for the v2.5 demo. If a live provider is unavailable, the recording must explicitly say which source failed and whether the checked-in sample CSV was used as a fallback.

Do not describe fallback data as live data.

## Fallback Branches

| Failure | Pivot | Recovery command |
|---|---|---|
| Docker daemon is not running | Show README prerequisites and pause the demo. | Start Docker, then rerun `make setup`. |
| OpenMetadata or Superset is slow | Continue with `make verify`, Dagster, Trino, and MinIO; return to the UI later. | Wait 2-5 minutes, then rerun `make verify`. |
| Pipeline fails before Gold | Open Dagster run details and show the failed asset. | `make verify`, then `make demo`. |
| Trino query fails | Show `RUNBOOK.md` Trino debugging path. | `make verify`, inspect `docker logs slh-trino`. |
| MLflow Host header or artifact issue | Show that the demo does not hide failures. | Rebuild MLflow with `make up`, then rerun `make verify`. |

## Pass Criteria

- `make setup` exits 0.
- `make verify` exits 0.
- `make demo` exits 0.
- Health dashboard shows all services as PASS.
- Dagster shows a successful `demo_data_flow_job`.
- Trino returns row counts greater than zero for both Gold tables.
