# ADR-0002 · SCD Type 2 history via `dbt snapshot` (not hand-rolled macros)

<!-- [ZCode·2026-11-23] Promote the scaffold's rationale into a formal ADR. -->

**Status:** Accepted (2026-11-23, before E04) · Supersedes: none

## Context

`dim_stations` and `dim_tariffs` need full attribute history: stations get power upgrades (`50 kW → 150 kW`) and tariffs change prices, while `fct_charging_sessions` must join to the attribute version valid at `session_started_at` so historical revenue never shifts retroactively (data-contract §3.6, golden example §4).

## Decision

Use **`dbt snapshot`** with `strategy='check'` on the tracked columns (stations: `nominal_power_kw`, `connector_count`, `operator_name`; tariffs: `price_per_kwh_eur`, `roaming_surcharge_eur`, `plan_tier`) to maintain `dim_stations_scd2` / `dim_tariffs_scd2`, and resolve current state via views filtered to `dbt_valid_to IS NULL` (data-contract §2).

## Consequences

- Snapshot metadata columns (`dbt_valid_from`, `dbt_valid_to`, `dbt_scd_id`) are part of the mart surface and must be declared in contracts/tests.
- Point-in-time interval joins live in one place (the fact models) and are covered by native `unit_tests` (E03) and the SCD2 non-overlap acceptance check (E04).
- Snapshot runs must execute before fact builds in orchestration (E07 DAG order: `dbt_snapshot → dbt_build_marts`).

## Alternatives considered

| Alternative | Why rejected |
|---|---|
| Hand-rolled SCD2 macros (`lag()`-based models) | Re-implements dbt built-ins, more SQL to port across DuckDB/BigQuery, and hides change-tracking semantics that interviewers expect to see implemented with `dbt snapshot`. |
| Full history re-derived per run (no state) | Costs a full recompute per run and makes "only new snapshots change" unverifiable — conflicts with the incremental/FinOps story of E04/E06. |
| Store history only in raw (`t0/t1/t2` grain) | Pushes interval logic into every consumer; raw stays append-only, marts must own modeling. |
