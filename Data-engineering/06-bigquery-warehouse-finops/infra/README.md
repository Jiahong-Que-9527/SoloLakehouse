# E06 infra — BigQuery datasets, Authorized View and analyst IAM

Scope (design §4): datasets `de_raw`, `de_stg`, `de_int`, `de_mart`, `de_consumer`
in `europe-west3`, one Authorized View (`de_consumer.v_daily_revenue` over
`de_mart.fct_daily_revenue_v2`), and an optional analyst read split. **Zero
paid resources, zero destroys** — every dataset carries `prevent_destroy`,
and the [GCP cost gate](../../../AGENTS.md) requires the owner's explicit
approval before any apply.

## Two-phase apply (see views.tf header)

1. **Phase 1 — before the load/build** (datasets exist so dbt can write):

   ```bash
   cp terraform.tfvars.example terraform.tfvars   # set project_id
   terraform init
   terraform plan -target=google_bigquery_dataset.de_raw \
                  -target=google_bigquery_dataset.de_stg \
                  -target=google_bigquery_dataset.de_int \
                  -target=google_bigquery_dataset.de_mart \
                  -target=google_bigquery_dataset.de_consumer
   terraform apply -target=google_bigquery_dataset.de_raw \
                   -target=google_bigquery_dataset.de_stg \
                   -target=google_bigquery_dataset.de_int \
                   -target=google_bigquery_dataset.de_mart \
                   -target=google_bigquery_dataset.de_consumer
   ```

   Expected plan: `5 to add, 0 to change, 0 to destroy`.

2. **Phase 2 — after `dbt build --target bq`** (the view's source table now
   exists): set `analyst_principal`, then full `terraform plan` /
   `terraform apply`. Expected plan: `4 to add, 0 to change, 0 to destroy`
   (view, access grant, 2 IAM bindings).

## Verification

- `terraform plan` on an applied state prints `No changes` (idempotent).
- `gcloud bigquery datasets list --location=europe-west3` shows the five
  datasets; `bq show de_consumer` shows `v_daily_revenue`.
- The acceptance negative drills (partition filter rejection, analyst 403 on
  `de_raw`) are recorded in [../docs/cloud-verification.md](../docs/cloud-verification.md).
