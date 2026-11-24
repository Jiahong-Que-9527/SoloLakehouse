#!/usr/bin/env bash
# E07 local acceptance (design §7): clean run -> injected-failure halt ->
# clear-only-the-failed-task recovery -> bounded-backfill run.
# Everything is local (SQLite metadata in /tmp, DuckDB warehouse in the repo's
# data/) — EUR 0. Full log goes to the evidence dir.
#
# Fixes vs v1: DAG unpaused (new DAGs start paused), python heredocs run
# through the repo venv (duckdb), run-id parsed with regex fallback, run
# state polled from the metadata DB (no CLI DagBag parse per poll).
set -u

REPO=/home/bill/src/SoloLakehouse-e07/Data-engineering/reference-warehouse
EV=/home/bill/src/SoloLakehouse-e07/Data-engineering/07-orchestration-airflow/evidence
AHOME=/tmp/slh-airflow-e07
DB="$REPO/data/warehouse.duckdb"
LOG="$EV/e07-run-log.txt"

export AIRFLOW_HOME="$AHOME"
export AIRFLOW__CORE__DAGS_FOLDER="$REPO/airflow/dags"
export AIRFLOW__CORE__LOAD_EXAMPLES=False
export AIRFLOW__CORE__EXECUTOR=SequentialExecutor
export AIRFLOW__CORE__DAGS_ARE_PAUSED_AT_CREATION=False
export AIRFLOW__SCHEDULER__CATCHUP_BY_DEFAULT=False
export AIRFLOW__WEBSERVER__WEB_SERVER_PORT=8080

mkdir -p "$EV" "$AHOME"
cd "$REPO/airflow" || exit 1

say() { echo "=== $*"; }

runid_of() {
    # --output json may carry deprecation-warning noise around the payload:
    # slice from the first "{" to the last "}", then fall back to a regex
    # that stops at the first quote/comma/whitespace (no trailing junk).
    # NOTE: plain `-c` so python's stdin is the piped trigger output (a
    # heredoc would swallow the pipe).
    python3 -c 'import json, re, sys
data = sys.stdin.read()
try:
    obj = json.loads(data[data.index("{"):data.rindex("}") + 1])
    print(obj.get("dag_run_id", ""))
    sys.exit(0)
except Exception:
    pass
m = re.search(r"((?:manual|scheduled|backfill)__[^\s\",]+)", data)
print(m.group(1) if m else "")'
}

trigger_dag() { # $1 conf-json-or-empty -> echoes the dag run id (retries on
    # SQLite lock contention with the scheduler; stderr is logged, not lost)
    local conf="$1" out rid try
    for try in 1 2 3 4 5; do
        if [ -n "$conf" ]; then
            out=$(uv run --locked airflow dags trigger charging_commerce_daily --conf "$conf" --output json 2>&1)
        else
            out=$(uv run --locked airflow dags trigger charging_commerce_daily --output json 2>&1)
        fi
        rid=$(printf '%s\n' "$out" | runid_of)
        if [ -n "$rid" ]; then
            echo "$rid"
            return 0
        fi
        echo "trigger attempt $try failed:" >&2
        printf '%s\n' "$out" | tail -2 >&2
        sleep 5
    done
    return 1
}

run_state() { # $1 run_id -> state from the metadata DB (fast, no DAG parse).
    # Read-only URI connection: never block or lock the scheduler.
    python3 - "$1" "$AHOME/airflow.db" <<'PY'
import sqlite3, sys
con = sqlite3.connect(f"file:{sys.argv[2]}?mode=ro", uri=True)
row = con.execute("select state from dag_run where run_id = ?", (sys.argv[1],)).fetchone()
con.close()
print(row[0] if row else "missing")
PY
}

wait_run() { # $1 run_id, $2 max minutes
    local st
    for _ in $(seq 1 $(($2 * 6))); do
        sleep 10
        st=$(run_state "$1")
        case "$st" in success | failed) echo "$st"; return ;; esac
    done
    echo timeout
}

dump_states() { # $1 label, $2 run_id (read-only connection)
    python3 - "$1" "$2" "$AHOME/airflow.db" <<'PY'
import sqlite3, sys
label, run_id, db = sys.argv[1], sys.argv[2], sys.argv[3]
con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
rows = con.execute(
    "select task_id, state, try_number, start_date, end_date, duration"
    " from task_instance where run_id = ? order by start_date", (run_id,)
).fetchall()
print(f"--- {label} (run_id={run_id})")
for r in rows:
    print(f"  {r[0]:<28} state={r[1] or 'None':<16} try={r[2]} start={r[3]} end={r[4]} dur={r[5]}")
PY
}

raw_count() {  # repo venv python has duckdb; missing db is not an error here.
    # Subshell cd: same leak protection as duck_exec.
    (
        cd "$REPO" && uv run --locked python - "$DB" <<'PY'
import os, sys
if not os.path.exists(sys.argv[1]):
    print("(no db yet)")
    sys.exit(0)
import duckdb
con = duckdb.connect(sys.argv[1], read_only=True)
print(con.execute("select count(*) from raw.raw_charging_sessions").fetchone()[0])
con.close()
PY
    )
}

duck_exec() {  # $1 sql — repo venv python; subshell so the `cd` cannot leak
    # into the main script's cwd (uv would then resolve the main project
    # env, which has no `airflow` entrypoint -> "Failed to spawn").
    (
        cd "$REPO" && uv run --locked python - "$DB" "$1" <<'PY'
import duckdb, sys
con = duckdb.connect(sys.argv[1])
con.execute(sys.argv[2])
con.close()
PY
    )
}

{
    say "versions"
    uv run --locked airflow version | head -1
    (cd "$REPO" && uv run --locked dbt --version | sed -n '1,2p')

    say "metadata db (disposable AIRFLOW_HOME=$AHOME)"
    rm -rf "$AHOME"
    mkdir -p "$AHOME"
    # Clean warehouse slate too: the E01 state dir (data/state) records
    # batch -> payload hash, and regeneration is not byte-stable, so a
    # stale state dir next to a fresh warehouse would raise a spurious
    # BatchCollisionError. State, payloads and warehouse reset together.
    rm -rf "$REPO/data/state" "$REPO/data/generated"
    rm -f "$DB" "$DB.wal"
    uv run --locked airflow db migrate 2>&1 | tail -1
    # WAL journal mode: the acceptance probes below poll dag_run/task states
    # every few seconds, and in rollback-journal mode a reader blocks the
    # scheduler's writers — observed as tasks failing before their first
    # log line ever appeared (no task log, start=None). WAL makes the
    # readers non-blocking.
    python3 - "$AHOME/airflow.db" <<'PY'
import sqlite3, sys
con = sqlite3.connect(sys.argv[1])
print("journal_mode:", con.execute("PRAGMA journal_mode=WAL").fetchone()[0])
con.close()
PY

    say "start airflow standalone (loopback)"
    # Port guard: a leftover standalone from an earlier run would hold
    # 8080/8793/8794 and race this run's scheduler on the same metadata DB
    # (observed as tasks failing before their first log line). Fail loudly.
    for p in 8080 8793 8794; do
        if ss -ltn 2>/dev/null | grep -q ":$p "; then
            echo "FATAL: port $p is already in use — kill the stale Airflow first"
            exit 1
        fi
    done
    nohup uv run --locked airflow standalone >"$AHOME/standalone.log" 2>&1 &
    echo $! >"$AHOME/standalone.pid"

    ready=no
    for i in $(seq 1 40); do
        sleep 5
        if grep -q "Starting the scheduler" "$AHOME/standalone.log" 2>/dev/null; then ready=yes; break; fi
    done
    echo "standalone ready: $ready (waited ~$((i * 5))s)"
    # New DAGs are paused by default; unpause explicitly (the documented
    # UI action in the runbook).
    uv run --locked airflow dags unpause charging_commerce_daily 2>&1 | tail -1
    uv run --locked airflow dags details charging_commerce_daily 2>/dev/null | grep -iE 'is_paused|dag_id' | head -2
    sleep 10

    say "RUN 1 (clean scheduled-style run)"
    BEFORE_RAW=$(raw_count)
    echo "raw rows before: $BEFORE_RAW"
    RUN1=$(trigger_dag "")
    echo "run_id=$RUN1"
    S1=$(wait_run "$RUN1" 45)
    echo "RUN 1 state: $S1"
    dump_states "RUN 1 task instances" "$RUN1"
    echo "raw rows after RUN 1: $(raw_count)"

    say "RUN 2 (drill: corrupted country_code on one raw session row)"
    BAD_SID=$(cd "$REPO" && uv run --locked python - "$DB" <<'PY'
import duckdb, sys
con = duckdb.connect(sys.argv[1])
sid = con.execute(
    "select session_id from raw.raw_charging_sessions where event_type = 'charge' order by session_id limit 1"
).fetchone()[0]
con.execute("update raw.raw_charging_sessions set country_code = 'XX' where session_id = ?", (sid,))
con.close()
print(sid)
PY
)
    echo "corrupted session_id=$BAD_SID (country_code -> 'XX')"
    RUN2=$(trigger_dag "")
    echo "run_id=$RUN2"
    S2=$(wait_run "$RUN2" 45)
    echo "RUN 2 state: $S2 (expected failed)"
    dump_states "RUN 2 task instances (halted)" "$RUN2"

    say "recovery: fix input, clear ONLY the halted build stage (and its downstream verify; upstream producers are never re-run), let scheduler resume"
    duck_exec "update raw.raw_charging_sessions set country_code = 'DE' where session_id = '$BAD_SID'"
    echo "input restored: country_code back to 'DE' for $BAD_SID; raw rows still $(raw_count)"
    # Airflow clears do not cascade into downstream tasks: verify stays
    # upstream_failed unless it is cleared too, so the operator command is
    # the failed task plus --downstream. --only-failed keeps the blast
    # radius minimal in *all* runs in the date window: succeeded builds
    # (scheduled run, RUN 1) are never touched, and the upstream producers
    # (ingest/freshness/snapshot) keep try=1 everywhere.
    uv run --locked airflow tasks clear charging_commerce_daily \
        -t '^dbt_build_marts$' -s 2026-11-20 -e 2026-12-31 --yes --downstream --only-failed 2>&1 | tail -2
    S2B=$(wait_run "$RUN2" 45)
    echo "RUN 2 state after clear+rerun: $S2B (expected success)"
    dump_states "RUN 2 task instances (recovered)" "$RUN2"

    say "RUN 3 (bounded backfill window via dag_run.conf)"
    RUN3=$(trigger_dag '{"backfill_start": "2025-10-01", "backfill_end": "2025-10-08"}')
    echo "run_id=$RUN3"
    S3=$(wait_run "$RUN3" 45)
    echo "RUN 3 state: $S3"
    dump_states "RUN 3 task instances" "$RUN3"
    echo "raw rows after RUN 3: $(raw_count) (same-ds re-ingest skips, no duplication)"

    say "stop standalone"
    kill "$(cat "$AHOME/standalone.pid")" 2>/dev/null
    sleep 3
    pkill -f "airflow standalone" 2>/dev/null

    say "summary"
    echo "RUN1=$S1 RUN2=$S2 -> $S2B (recovered) RUN3=$S3"
    echo "DONE"
} 2>&1 | tee -a "$LOG"
