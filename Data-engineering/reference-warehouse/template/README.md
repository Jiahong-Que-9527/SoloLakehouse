# DE Platform Template (extracted from the charging-commerce warehouse)

A minimal, guardrail-complete starter for onboarding a **new data domain**
into this repository. It carries the conventions the primary warehouse
earned across E01–E07 — offline-first `uv` + pytest, SQLFluff-clean SQL,
dbt tests with an enforced mart contract, and a DuckDB-first profile —
while keeping the domain's contract fully independent of
`charging_commerce`.

## Layout

```text
template/
├── README.md                  <- you are here; the onboarding checklist
├── pyproject.toml             <- ruff + pytest baseline (same rules as primary)
├── .sqlfluff                  <- lint config (duckdb dialect, 100 cols)
└── dbt_project/
    ├── dbt_project.yml        <- project skeleton (rename `de_starter`)
    ├── profiles.yml           <- duckdb target via env var (no secrets)
    ├── seeds/                 <- raw drop zone (CSV; swap for your ingest later)
    ├── models/staging/        <- typed 1:1 view over the seed + tests
    ├── models/marts/          <- star-schema fact/dim with enforced contract
    ├── tests/generic/         <- reusable singular/generic test patterns
    └── macros/                <- cross-database helper pattern
```

## Onboarding checklist (measured in E08 evidence)

1. Copy `template/dbt_project/` to your new domain's directory
   (convention: `reference-warehouse/examples/<domain>_mart/dbt_project/`).
2. Rename the project: `dbt_project.yml` `name:` / `profile:` → your domain.
3. Point `models/staging/*.sql` at your raw inputs — a `seeds/*.csv` drop
   works from minute one; swap in an ingest pipeline when the domain earns one.
4. Write the mart with `contract: {enforced: true}` and describe every
   column (the template's `models/marts/schema.yml` shows the shape).
5. Add the domain's tests: `unique`, `not_null`, `non_negative`, and one
   singular reconciliation test mirroring `tests/singular/` in the primary.
6. Verify offline, in this order (all from `reference-warehouse/`):

   ```bash
   uv run --locked ruff check <your-dir>
   uv run --locked sqlfluff lint <your-dir>/dbt_project/models \
       --config template/.sqlfluff   # adjust project_dir inside first
   uv run --locked dbt build --project-dir <your-dir>/dbt_project \
       --profiles-dir <your-dir>/dbt_project --target duckdb
   ```

7. Wire the domain into CI by adding a workflow step that mirrors
   `.github/workflows/data-engineering.yml` for your directory.

## What the template deliberately does NOT include

- Any `charging_commerce` model, macro, or schema — domains stay isolated.
- Cloud targets: add a `bq` profile only when the domain has a funded
  BigQuery home (E06 pattern: `maximum_bytes_billed` guard is mandatory).
- Ingestion state machinery: E01's `data/state` batch-id protocol is a
  primary-warehouse concern until your domain needs resumability.
