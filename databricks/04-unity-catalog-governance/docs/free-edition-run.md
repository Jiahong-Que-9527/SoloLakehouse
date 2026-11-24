# Run D04 on Databricks Free Edition

This exercise creates synthetic observations in isolated Unity Catalog schemas. The bundle deploys one unscheduled serverless job. Run it from this project directory with an existing Databricks CLI profile authorized for Workspace and Jobs.

```sh
vars="namespace=ecb_d04_governance,git_sha=$(git rev-parse HEAD)"
databricks bundle validate --strict -p slh-free -t dev --var "$vars"
databricks bundle deploy -p slh-free -t dev --var "$vars"
databricks bundle run d04_governance -p slh-free -t dev --var "$vars"
```

Each new job run creates its own schemas in the `workspace` catalog using the namespace and job run ID. The job first publishes `initial`. It rejects duplicate-key candidates in dev and prod, checks the prod view against its original result, and publishes `corrected`. Use the task's run ID with `databricks jobs get-run-output <task-run-id> -p slh-free -o json` to retrieve the evidence.

The observations form a small D01-shaped synthetic fixture. Its account token and counterparty are synthetic. The job owner exercises a temporary explicit `SELECT` on the new indicator view and then revokes it. The ledger records the actual actor, object, action, commit and timestamp in the workspace. The exported result identifies the actor by role and includes the observed explicit privileges and the owner's post-revoke read.

## Intended access review

| Principal | Intended allow | Intended deny |
|---|---|---|
| Producer | Write in its assigned environment | Dev producer writes to prod |
| Analyst | Read `fx_indicator_current` | Raw observations and restricted fields |
| Risk analyst | Read `transaction_risk_detail` | Raw observations and observation writes |
| ML engineer | Read `forecast_feature` | Raw observations and restricted fields |
| Auditor | Read `release_evidence` and `grant_change` | Observation writes |

The Free Edition job runs as a single workspace user. This matrix documents the policy to exercise when separate role identities are available. The temporary owner grant can verify the DDL and ledger mechanics. An owner's continued read after the revoke is expected under ownership.

## Warehouse verification

Use a separate CLI profile, `slh-d04-sql`, with scope `sql:read:restricted-query`. List warehouses with `databricks warehouses list -p slh-d04-sql`. Use the workspace's 2X-Small warehouse ID to execute the following query with the observed prod consumer schema from the evidence. Replace both placeholders before running.

```sh
databricks api post /api/2.0/sql/statements -p slh-d04-sql --json '{
  "warehouse_id": "<warehouse-id>",
  "statement": "SELECT release_id, series_key, observation_date, fx_rate FROM <prod-consumer-schema>.forecast_feature WHERE release_id = '\''corrected'\''",
  "wait_timeout": "30s"
}'
```

If the response is pending, retrieve the result with `databricks api get /api/2.0/sql/statements/<statement-id> -p slh-d04-sql`. Check the statement status, the projected columns, and the row's release ID.
