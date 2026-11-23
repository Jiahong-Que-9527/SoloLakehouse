# Reference Warehouse

Single executable code tree for `Data-engineering/` (`E01–E08`). See [architecture.md](../docs/architecture.md), [delivery-plan.md](../docs/delivery-plan.md), [data-contract.md](../docs/data-contract.md), and [evidence-guide.md](../docs/evidence-guide.md) before modifying files here.

## Planned layout

```text
reference-warehouse/
├── pyproject.toml        # Python 3.12 + dbt-core + dbt-duckdb + dbt-bigquery + sqlfluff
├── uv.lock
├── .sqlfluff
├── fixtures/             # Locked BNetzA (CC BY 4.0), SMARD, and ECB slices + manifest.json
├── src/charging_commerce/
│   ├── __init__.py
│   ├── open_data.py      # Locked fixture loader & optional --live refresh (E01)
│   ├── generator.py      # Seeded EV charging + mock paginated roaming API (E01)
│   ├── ingestion.py      # Resumable raw ingestion + raw_quarantine routing (E01)
│   ├── observability.py  # run_results.json & sources.json audit parser (E08)
│   └── cli.py            # CLI entrypoint
├── dbt_project/          # Cross-warehouse dbt models, snapshots, macros, tests (E02-E06)
├── airflow/              # Isolated Airflow uv env + DAGs + optional Compose (E07)
├── template/             # Extracted starter template + 2nd onboarded workload (E08)
└── tests/                # Offline pytest suite
```

## Standard checks (once E01 lands)

```bash
cd Data-engineering/reference-warehouse
uv sync --locked --python 3.12
uv run --locked ruff check .
uv run --locked ruff format --check .
uv run --locked pytest
```

From `E02` onward, SQL and dbt checks run in the same offline loop (`sqlfluff lint dbt_project/models` and `dbt build --target duckdb`). Cloud BigQuery checks (`--target bq` in `E06`) stay strictly inside the Free Tier and obey the [GCP cost gate](../../AGENTS.md).

Attribution for public German charging-station fixtures: **Bundesnetzagentur.de — Ladesäulenregister**, licensed under **CC BY 4.0**.
