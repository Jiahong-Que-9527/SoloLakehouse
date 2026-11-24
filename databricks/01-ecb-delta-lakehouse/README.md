# ECB Delta Lakehouse

<!-- [房玄龄·2026-11-15] Define the D01 to D04 project brief. -->
<!-- [房玄龄·2026-11-15] Define independent platform projects and planned acceptance. -->

**D01 · Accepted on Databricks Free Edition (2026-11-24)** · [Databricks roadmap](../README.md) · [Playbook](../docs/free-edition-cli-playbook.md) · [Design](docs/design.md) · [Implementation plan](docs/implementation.md)

**Environment:** Databricks Free Edition (Serverless compute + Databricks CLI with PAT auth).

Model ECB reference exchange rates and policy rates in Delta. Begin with a fixed quarter of the daily USD/EUR series, then add one policy-rate series with its
own publication calendar and units.

## Technical scope

PySpark, Delta Lake, SQL and Bronze, Silver and Gold models.

## Input and output

- **Input.** Fixed ECB extracts and small fixtures. Record the source series keys, observation dates, units and source windows.
- **Output.** Bronze source batches, normalized Silver observations keyed by series and date, and a versioned Gold release with derived metrics. D02 can package the transforms and D05 can consume a specific Delta snapshot.

## Acceptance

1. Verify known output rows and metric values, then rerun the same inputs and check key uniqueness.
2. Apply a controlled update with Delta MERGE and inspect the pre-update and post-update versions.
3. Trace a Gold release to the input batch, table version, quality-check result and source commit.

[ECB daily reference exchange-rate series](https://data.ecb.europa.eu/data/datasets/EXR/EXR.D.USD.EUR.SP00.A)

See the [live verification](docs/implementation.md#free-edition-verification) and [recorded Delta evidence](evidence/free-edition-694217175083761.json).

## Local checks (no Java / PySpark needed)

```bash
cd databricks/01-ecb-delta-lakehouse
uv sync --locked
uv run --locked ruff check .
uv run --locked ruff format --check .
uv run --locked pytest
```

## Run on Databricks Free Edition

Method A — **Git Folders in the Free Edition Web UI**:

1. Connect the repository in your Databricks Free Edition workspace (`Workspace -> Repos / Git folders`).
2. Open `databricks/01-ecb-delta-lakehouse/notebooks/run_d01_free_edition.py`.
3. Attach **Serverless** compute, set widget `schema` (e.g., `ecb_d01_dev`), and run all cells.
4. Record the printed JSON output (`silver_fx_version_before_revision`, `silver_fx_version_after_revision`, `time_travel_2025_02_05_before`, `time_travel_2025_02_05_after`, and `release_v1`/`release_v2`) in [implementation.md](docs/implementation.md).

Method B — **Databricks CLI + PAT (Declarative Automation Bundle)**:

> Authenticate with a Personal Access Token (`databricks configure --profile slh-free`), **not** `databricks auth login` (OAuth is unsupported on Free Edition hosts). See [Free Edition & CLI Playbook](../docs/free-edition-cli-playbook.md).

```bash
cd databricks/01-ecb-delta-lakehouse
databricks bundle validate --profile slh-free
databricks bundle deploy -t dev --profile slh-free
databricks bundle run d01_ecb_lakehouse -t dev --profile slh-free
# Capture the JSON evidence returned by dbutils.notebook.exit:
databricks jobs get-run-output <run_id> --profile slh-free
```

<!-- [房玄龄·2026-11-17] Add implementation sequence and acceptance evidence. -->
