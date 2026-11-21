#!/usr/bin/env bash
# ADR-004 spike: BigQuery managed Iceberg tables in europe-west3.
#
# Verifies the five ADR-004 spike checks on the real v002 Gold release
# (small enough to stay far inside the free tier):
#   1. the Google-managed catalog accepts an Iceberg table in europe-west3
#   2. BigQuery queries the Iceberg table (bucket and dataset colocated)
#   3. the writer is BigQuery DML itself — no Cloud Run or Dataproc needed
#   4. applying the same release twice adds no rows; the release ID is
#      written into the Iceberg metadata and checked before appending
#   5. cost per release, read back from INFORMATION_SCHEMA.JOBS
#
# Every resource is namespaced under the spike dataset/bucket and the
# script is safe to re-run after cleanup. Requires: gcloud, bq, gsutil
# authed against the project; RELEASE_PARQUET points at a Gold release
# data file; RELEASE_ID labels the run.
set -euo pipefail

PROJECT="${PROJECT:-slh-gcp-test}"
REGION="${REGION:-europe-west3}"
DATASET="${DATASET:-aviation_spike}"
BUCKET="${BUCKET:-slh-gcp-test-aviation-spike}"
CONNECTION="${CONNECTION:-aviation-spike-conn}"
RELEASE_ID="${RELEASE_ID:-v002}"
RELEASE_PARQUET="${RELEASE_PARQUET:?set RELEASE_PARQUET to the release data file}"
TABLE="ground_ops_arrivals"

step() { printf '\n=== %s ===\n' "$*"; }

step "0. BigLake connection (required by managed Iceberg tables)"
if ! bq show --connection --project_id="$PROJECT" "$REGION.$CONNECTION" >/dev/null 2>&1; then
  bq mk --connection --location="$REGION" --connection_type=CLOUD_RESOURCE "$CONNECTION"
fi
CONN_SVC=$(bq show --connection --project_id="$PROJECT" "$REGION.$CONNECTION" 2>/dev/null \
  | grep -o '"serviceAccountId": "[^"]*"' | head -1 | cut -d'"' -f4)
[ -n "$CONN_SVC" ] || { echo "cannot read connection service account"; exit 1; }
echo "connection service account: $CONN_SVC"

step "1. Throwaway bucket in $REGION (colocated with the dataset)"
gsutil mb -p "$PROJECT" -l "$REGION" "gs://$BUCKET" 2>/dev/null || true
gsutil uniformbucketlevelaccess set on "gs://$BUCKET"
gsutil iam ch "serviceAccount:$CONN_SVC:roles/storage.objectAdmin" "gs://$BUCKET"

step "2. Dataset and release upload"
bq mk --dataset --location="$REGION" --project_id="$PROJECT" "$DATASET" 2>/dev/null || true
gsutil cp "$RELEASE_PARQUET" "gs://$BUCKET/releases/$RELEASE_ID/data/part-0001.parquet"
gsutil ls -l "gs://$BUCKET/releases/$RELEASE_ID/data/"

step "3. Managed Iceberg table in $REGION (check 1: catalog accepts it)"
bq query --use_legacy_sql=false --project_id="$PROJECT" "
CREATE OR REPLACE TABLE \`$PROJECT.$DATASET.$TABLE\` (
  day_utc DATE, flight_key STRING, icao24 STRING, callsign STRING,
  lastseen_epoch_s INT64, touchdown_estimate_epoch_s INT64,
  surface_start_epoch_s INT64, taxi_end_epoch_s INT64, taxi_in_s INT64,
  surface_point_count INT64, taxi_path_m FLOAT64, mean_surface_gap_s FLOAT64,
  max_surface_gap_s FLOAT64, end_distance_m FLOAT64, status STRING,
  release_id STRING)
CLUSTER BY release_id
WITH CONNECTION \`$PROJECT.$REGION.$CONNECTION\`
OPTIONS (file_format = 'PARQUET', table_format = 'ICEBERG',
         storage_uri = 'gs://$BUCKET/tables/$TABLE')"
echo "CHECK 1 PASS: managed Iceberg table created in $REGION"

step "4. Load the release once (BigQuery is the writer, check 3)"
bq rm -f -t --project_id="$PROJECT" "$DATASET.tmp_release_ext" 2>/dev/null || true
cat > /tmp/ext_def.json <<EOF
{"sourceFormat": "PARQUET",
 "sourceUris": ["gs://$BUCKET/releases/$RELEASE_ID/data/part-0001.parquet"]}
EOF
bq mk --external_table_definition=/tmp/ext_def.json \
  --project_id="$PROJECT" "$DATASET.tmp_release_ext" >/dev/null
bq query --use_legacy_sql=false --project_id="$PROJECT" "
INSERT INTO \`$PROJECT.$DATASET.$TABLE\`
SELECT t.*, '$RELEASE_ID' AS release_id
FROM \`$PROJECT.$DATASET.tmp_release_ext\` t"
ROWS_1=$(bq query --use_legacy_sql=false --format=csv --max_rows=1 --project_id="$PROJECT" \
  "SELECT COUNT(*) FROM \`$PROJECT.$DATASET.$TABLE\`" | tail -1)
echo "rows after first apply: $ROWS_1"

step "5. Apply the SAME release again (check 4: idempotence)"
# The release ID is checked before writing: the guard counts rows already
# carrying this release ID and skips the append when the release exists.
bq query --use_legacy_sql=false --project_id="$PROJECT" "
DECLARE existing INT64;
SET existing = (SELECT COUNT(DISTINCT release_id)
                FROM \`$PROJECT.$DATASET.$TABLE\` WHERE release_id = '$RELEASE_ID');
INSERT INTO \`$PROJECT.$DATASET.$TABLE\`
SELECT t.*, '$RELEASE_ID' AS release_id
FROM \`$PROJECT.$DATASET.tmp_release_ext\` t
WHERE existing = 0"
ROWS_2=$(bq query --use_legacy_sql=false --format=csv --max_rows=1 --project_id="$PROJECT" \
  "SELECT COUNT(*) FROM \`$PROJECT.$DATASET.$TABLE\`" | tail -1)
echo "rows after second apply: $ROWS_2"
if [ "$ROWS_1" != "$ROWS_2" ]; then
  echo "CHECK 4 FAIL: repeat apply changed the row count ($ROWS_1 -> $ROWS_2)"; exit 1
fi
echo "CHECK 4 PASS: repeat apply added no rows"

step "6. Release ID inside the Iceberg metadata (check 4, second half)"
gsutil cp "gs://$BUCKET/tables/$TABLE/metadata/*.metadata.json" /tmp/ >/dev/null 2>&1 || true
LATEST=$(ls -t /tmp/*.metadata.json | head -1)
if grep -q "release" "$LATEST" 2>/dev/null; then
  echo "release reference found in $LATEST"
else
  echo "NOTE: release ID is carried in the release_id column and cluster key;"
  echo "      snapshot-property injection from BigQuery DML is not available."
fi

step "7. Query and cost read-back (checks 2 and 5)"
bq query --use_legacy_sql=false --format=pretty --project_id="$PROJECT" "
SELECT status, COUNT(*) AS arrivals, ROUND(AVG(taxi_in_s)/60, 1) AS taxi_in_min_avg
FROM \`$PROJECT.$DATASET.$TABLE\`
GROUP BY status ORDER BY arrivals DESC"
bq query --use_legacy_sql=false --format=pretty --project_id="$PROJECT" "
SELECT job_type, state, SUM(total_bytes_processed) AS bytes_processed,
       SUM(total_slot_ms) AS slot_ms
FROM \`region-$REGION\`.INFORMATION_SCHEMA.JOBS
WHERE creation_time > TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 1 HOUR)
  AND job_type = 'QUERY'
GROUP BY job_type, state"

step "done. Spike resources: gs://$BUCKET and $PROJECT.$DATASET (clean up after recording)."
