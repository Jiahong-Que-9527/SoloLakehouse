# Reference Warehouse

Single executable code tree for `Data-engineering/` (`E01–E08`):

- `src/charging_commerce/` — seeded generator, German open-data loaders (`BNetzA`, `SMARD`, `ECB`), resumable ingestion CLI, and dbt artifact observability parser (`E01`, `E08`).
- `fixtures/` — locked regional `BNetzA Ladesäulenregister` (`CC BY 4.0`), `SMARD`, and `ECB` slices with SHA-256 `manifest.json` for deterministic offline CI.
- `dbt_project/` — cross-warehouse dbt models (`staging`, `intermediate`, `marts`), `snapshots`, `macros`, `tests`, and `profiles.yml` supporting `duckdb` (CI) and `bigquery` (`slh-gcp-test`, `europe-west3`).
- `airflow/` — local standalone Apache Airflow DAGs and optional Compose definition (`E07`, isolated from dbt dependencies).
- `tests/` — Python contract, ingestion resume, quarantine, conservation-parity, and Airflow DAG parse tests.

Attribution for public German charging-station fixtures: **Bundesnetzagentur.de — Ladesäulenregister**, licensed under **CC BY 4.0**.
