# Authorized View + permission split (design §3/§5).

# PHASE NOTE — two-phase apply is intentional:
#   Phase 1 (before the data load):  terraform apply -target=google_bigquery_dataset.* —
#       datasets only (this file minus the view/access resources).
#   Phase 2 (after `dbt build --target bq`): full apply. The view references
#       de_mart.fct_daily_revenue_v2, which only exists after the dbt build;
#       BigQuery validates the view query at CREATE time, so phase 2 is the
#       earliest the Authorized View can be declared. Recorded in
#       docs/cloud-verification.md.

resource "google_bigquery_table" "v_daily_revenue" {
  dataset_id          = google_bigquery_dataset.de_consumer.dataset_id
  table_id            = "v_daily_revenue"
  friendly_name       = "daily revenue (authorized consumer view)"
  description         = "Read-only consumer surface over de_mart.fct_daily_revenue_v2; the only table an analyst may query."
  deletion_protection = false # the view is rebuilt with the dbt revision; the datasets are protected instead

  view {
    query          = <<-SQL
            SELECT
                revenue_date,
                country_code,
                operator_name,
                session_count,
                total_energy_kwh,
                gross_amount_eur,
                roaming_fee_eur,
                net_amount_eur,
                wholesale_cost_eur,
                gross_margin_eur
            FROM de_mart.fct_daily_revenue_v2
        SQL
    use_legacy_sql = false
  }

  depends_on = [google_bigquery_dataset.de_consumer]
}

# Authorize the view in the SOURCE dataset (BigQuery authorized-view pattern):
# queries through the view run with the view owner's access, so the analyst
# never needs de_mart (or de_raw/de_stg/de_int) grants.
resource "google_bigquery_dataset_access" "authorize_v_daily_revenue" {
  dataset_id = google_bigquery_dataset.de_mart.dataset_id

  view {
    project_id = var.project_id
    dataset_id = google_bigquery_dataset.de_consumer.dataset_id
    table_id   = google_bigquery_table.v_daily_revenue.table_id
  }
}

# Analyst identity: read access ONLY on de_consumer; job-user so the analyst can
# run queries at all. No de_raw/de_stg/de_int/de_mart grant exists anywhere in
# this stack — the acceptance drill (403 on de_raw.raw_charging_sessions) proves
# the split. Skipped entirely while analyst_principal is empty (phase 1).
resource "google_bigquery_dataset_iam_member" "analyst_consumer_reader" {
  count      = var.analyst_principal == "" ? 0 : 1
  dataset_id = google_bigquery_dataset.de_consumer.dataset_id
  role       = "roles/bigquery.dataViewer"
  member     = var.analyst_principal
  depends_on = [google_bigquery_table.v_daily_revenue]
}

resource "google_project_iam_member" "analyst_job_user" {
  count   = var.analyst_principal == "" ? 0 : 1
  project = var.project_id
  role    = "roles/bigquery.jobUser"
  member  = var.analyst_principal
}
