#!/usr/bin/env bash
# E08 acceptance drill — fully local (€0):
#   RUN A: fresh warehouse -> freshness + build -> audit-dbt (PASS, exit 0)
#   DRILL: corrupt ecb _ingested_at (+71h) -> re-freshness -> audit-dbt
#          records a BREACH row + alert JSON, exits 2
#   IDEMPOTENCY: re-running audit-dbt on the same artifacts adds zero rows
# Output: e08-drill-log.txt
set -u
EVIDENCE="$(cd "$(dirname "$0")" && pwd)"
REPO="$(cd "$EVIDENCE/../../reference-warehouse" && pwd)"
DB="$REPO/data/warehouse.duckdb"
DRILL="/tmp/slh-e08-drill"
LOG="$EVIDENCE/e08-drill-log.txt"

log() { printf '%s\n' "$*" | tee -a "$LOG"; }

: > "$LOG"
rm -rf "$DRILL"
mkdir -p "$DRILL"
rm -rf "$REPO/data/state" "$REPO/data/generated"
rm -f "$DB"
cd "$REPO"

log '=== versions'
uv run --locked dbt --version 2>/dev/null | sed -n '1,2p' >> "$LOG"

log '=== build a fresh offline warehouse (generate -> ingest x5)'
uv run --locked charging-commerce generate --out-dir data/generated > /dev/null
for src in bnetza tariffs sessions smard ecb; do
    uv run --locked charging-commerce ingest "$src" \
        --batch-id "e08-drill-$src" --db "$DB" >> "$LOG" || exit 1
done

run_dbt() { uv run --locked dbt "$@" --project-dir dbt_project --profiles-dir dbt_project --target duckdb; }

log '=== RUN A: dbt deps + source freshness + dbt build'
run_dbt deps > /dev/null 2>&1 || { log 'DEPS FAILED'; exit 1; }
export CHARGING_COMMERCE_DUCKDB="$DB"
run_dbt source freshness --exclude source:raw.raw_roaming_settlements > /dev/null 2>&1 \
    || { log 'FRESHNESS FAILED'; exit 1; }
run_dbt run --select stg_bnetza_stations stg_tariff_plans > /dev/null 2>&1
run_dbt snapshot --vars 'snapshot_asof: 2025-09-15' > /dev/null 2>&1
run_dbt snapshot --vars 'snapshot_asof: 2026-01-15' > /dev/null 2>&1
run_dbt snapshot --vars 'snapshot_asof: 2026-05-15' > /dev/null 2>&1
# Full `dbt run` before `dbt build`: the golden unit test's mocked `this`
# reads mart.fct_charging_sessions, which must exist (E07 DAG ordering).
run_dbt run > /dev/null 2>&1
run_dbt build > /dev/null 2>&1 || { log 'BUILD FAILED'; exit 1; }

log '=== RUN A: audit-dbt (expect exit 0, no alerts)'
set +e
uv run --locked charging-commerce audit-dbt \
    --run-results dbt_project/target/run_results.json \
    --sources dbt_project/target/sources.json --db "$DB" 2>&1 | tee -a "$LOG"
echo "RUN A exit code: ${PIPESTATUS[0]}" >> "$LOG"
set -e

ops_snapshot() {
    uv run --locked python - "$DB" >> "$LOG" <<'PY'
import sys
import duckdb
con = duckdb.connect(sys.argv[1], read_only=True)
n = con.execute("select count(*) from ops.ops_dbt_run_audit").fetchone()[0]
f = con.execute("select count(*) from ops.ops_freshness_slo").fetchone()[0]
b = con.execute("select count(*) from ops.ops_freshness_slo where slo_status='BREACH'").fetchone()[0]
w = con.execute("select count(*) from ops.ops_freshness_slo where slo_status='WARN'").fetchone()[0]
slow = con.execute(
    "select node_name, round(execution_time_s, 1) from ops.ops_dbt_run_audit"
    " order by execution_time_s desc limit 3"
).fetchall()
con.close()
print(f"ops_dbt_run_audit rows: {n} | ops_freshness_slo rows: {f} "
      f"(BREACH={b} WARN={w})")
print(f"slowest nodes: {slow}")
PY
}
log '=== ops tables after RUN A'
ops_snapshot

log '=== DRILL: inject +71h staleness into raw_ecb_fx_rates._ingested_at'
uv run --locked python - "$DB" <<'PY'
import sys
import duckdb
con = duckdb.connect(sys.argv[1])
con.execute(
    "update raw.raw_ecb_fx_rates set _ingested_at ="
    " _ingested_at - interval 71 hour"
)
n = con.execute("select count(*) from raw.raw_ecb_fx_rates").fetchone()[0]
con.close()
print(f"backdated _ingested_at on {n} raw fx rows")
PY
run_dbt source freshness --exclude source:raw.raw_roaming_settlements >> "$LOG" 2>&1 || true

log '=== DRILL: audit-dbt (expect BREACH alert + exit 2)'
set +e
uv run --locked charging-commerce audit-dbt \
    --run-results dbt_project/target/run_results.json \
    --sources dbt_project/target/sources.json --db "$DB" 2>&1 | tee -a "$LOG"
echo "DRILL exit code: ${PIPESTATUS[0]}" >> "$LOG"
set -e

log '=== ops tables after DRILL (BREACH row recorded)'
ops_snapshot

log '=== IDEMPOTENCY: re-run audit-dbt on the same artifacts'
set +e
uv run --locked charging-commerce audit-dbt \
    --run-results dbt_project/target/run_results.json \
    --sources dbt_project/target/sources.json --db "$DB" > /dev/null 2>&1
echo "re-audit exit code: $?" >> "$LOG"
set -e
ops_snapshot

log '=== DONE'
