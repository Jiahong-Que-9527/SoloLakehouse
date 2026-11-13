# Finance

<!-- [Codex · 2026-11-13] Finance reference entry point. -->

Finance is SoloLakehouse's public reference workload. It ingests ECB policy
rates and exchange rates and uses Alpha Vantage EWG as a German-equity proxy.
The reference processes these inputs through Bronze, Silver, and Gold Iceberg
tables, with Dagster orchestration and Trino queries.

<!-- [Codex · 2026-11-13] Finance roadmap navigation. -->

The [Finance roadmap](roadmap.md) defines the Local, GCP and Databricks
learning and delivery milestones.

## Sources of truth

- **Inputs and transformations.** [Collectors](../../ingestion/collectors) own
  source ingestion. [ECB Silver](src/ecb_bronze_to_silver.py) owns the rate
  conversion. Other [transformations](../../transformations) remain at the
  repository root. [Dagster definitions](../../dagster/definitions.py) and
  [assets](../../dagster/assets.py) wire that logic into the reference runtime.
- **Dataset contracts.** The maintained YAML files are in
  [`governance/datasets/`](../../governance/datasets). Start with the
  [ECB Silver contract](../../governance/datasets/fin.ecb_rates_silver.yaml) and
  the [EUR market Gold contract](../../governance/datasets/fin.eur_market_daily_gold.yaml).
- **Verification.** The [test suite](../../tests) includes
  [contract tests](../../tests/test_governance_contracts.py),
  [ECB Silver tests](tests/test_ecb_bronze_to_silver.py),
  [other transformation tests](../../tests/test_transformations.py), and
  [Dagster asset tests](../../tests/test_dagster_assets.py). The
  [PR workflow](../../.github/workflows/test.yml) defines automated checks.

## Reproduce the local reference

Start with the [Compose quick start](../../docs/quickstart.md) and the
[demo guide](../../DEMO.md). The documented sequence is `make setup`,
`make verify`, then `make demo`. The demo runs the Dagster data flow and
checks Gold results through Trino. The manually triggered
[Compose Demo workflow](../../.github/workflows/compose-demo.yml) shows how
the reference run uses committed [EWG fixtures](../../data/fixtures).

A clean-clone MinIO client image-pull issue remains open. Check the
[object storage decision](../../docs/design/v3/storage-and-recovery.md#object-storage-decision)
and the [operator runbook](../../RUNBOOK.md) before attempting a fresh run.
Record the commit, job result, and Gold query result when validating the demo.

## Environment status

- **Local Compose:** Existing reference code and
  [Compose definition](../../docker/docker-compose.yml). Fresh runtime
  acceptance remains open.
- **Local K3s:** [V3 design and preparation](../../docs/design/v3/README.md).
  Provisioning, Flux delivery, and Finance migration await their own
  acceptance stages.
- **GCP and Databricks:** Deferred experiment candidates. The repository
  currently has no Finance implementation or deployment workflow for either
  environment. See the [roadmap](../../docs/roadmap.md) for scope.

Return to the [project index](../README.md) for the other workload and the
repository-wide planning sources.
