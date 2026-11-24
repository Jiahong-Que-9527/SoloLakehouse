#!/usr/bin/env bash
# 02 M4 full-dataset driver: per-day Silver -> monthly Gold -> releases.
#
#   ./full_run.sh silver   # 730 calendar days, 2 workers, restartable
#   ./full_run.sh gold     # 24 monthly merges + gold runs, restartable
#   GEOMETRY_DIR=/path/to/snapshot ./full_run.sh gold
#   GEOMETRY_DIR=/path/to/snapshot APPROVER="..." ./full_run.sh release
#
# Every run writes its own log; failed days are listed at the end and the
# phase can simply be re-run (existing outputs are skipped).
set -u
PHASE="${1:?usage: full_run.sh silver|gold|release}"
PARENT="${PARENT:-/home/bill/slh-data/full-20241101-20261031}"
BRONZE="${BRONZE:-/home/bill/slh-data/aviation}"
DIR02="$(cd "$(dirname "$0")" && pwd)"
WORKERS="${WORKERS:-2}"
START="${START:-2024-11-01}"
END="${END:-2026-10-31}"
GEOMETRY_DIR="${GEOMETRY_DIR:-}"
gold_directory="$PARENT/gold"
release_directory="$PARENT/releases"
contract="contracts/ground_ops.yaml"
release_prefix="radius-v1"
gold_log_prefix="gold"
geometry_args=()
if [ -n "$GEOMETRY_DIR" ]; then
  gold_directory="$PARENT/gold-geometry-v2"
  release_directory="$PARENT/releases-geometry-v2"
  contract="contracts/ground_ops_geometry.yaml"
  release_prefix="geometry-v2"
  gold_log_prefix="gold-geometry-v2"
  geometry_args=(--geometry-dir "$GEOMETRY_DIR")
fi

days() {
  python3 - "$1" "$2" <<'EOF'
import sys
from datetime import date, timedelta
d, end = date.fromisoformat(sys.argv[1]), date.fromisoformat(sys.argv[2])
while d <= end:
    print(d.isoformat())
    d += timedelta(days=1)
EOF
}

months() {
  python3 - "$1" "$2" <<'EOF'
import sys
from datetime import date, timedelta
d, end = date.fromisoformat(sys.argv[1]), date.fromisoformat(sys.argv[2])
seen = set()
while d <= end:
    seen.add(f"{d.year:04d}-{d.month:02d}")
    d += timedelta(days=1)
print("\n".join(sorted(seen)))
EOF
}

month_days() {
  python3 - "$1" <<'EOF'
import calendar
import sys
year, mon = int(sys.argv[1][:4]), int(sys.argv[1][5:7])
for d in range(1, calendar.monthrange(year, mon)[1] + 1):
    print(f"{year:04d}-{mon:02d}-{d:02d}")
EOF
}

run_one_silver() {
  local d="$1"
  local out="$PARENT/silver/$d"
  # A day counts as done only when its manifest exists: silver_v2 creates
  # the output directory first and writes run_manifest.json last, so a
  # directory without a manifest is an interrupted run and must be redone.
  if [ -f "$out/run_manifest.json" ]; then echo "skip $d"; return 0; fi
  rm -rf "$out"
  if (cd "$DIR02" && uv run --locked python silver_v2.py \
        --bronze-root "$BRONZE" --date "$d" --output "$out" \
        > "$PARENT/logs/silver-$d.log" 2>&1); then
    echo "ok $d"
  else
    echo "FAIL $d (see logs/silver-$d.log)"
    return 1
  fi
}

case "$PHASE" in
  silver)
    mkdir -p "$PARENT/silver" "$PARENT/logs"
    export PARENT BRONZE DIR02
    export -f run_one_silver
    set -o pipefail
    days "$START" "$END" | xargs -P "$WORKERS" -I{} bash -c 'run_one_silver {}' || exit 1
    echo "=== silver phase done"
    ;;
  gold)
    mkdir -p "$PARENT/silver-monthly" "$gold_directory" "$PARENT/logs"
    failed=0
    selected_months=$(months "$START" "$END") || exit 1
    while IFS= read -r m; do
      [ -n "$m" ] || continue
      exec 8>"$PARENT/logs/.gold-$m.lock" || exit 1
      flock -x 8 || exit 1
      ms="$PARENT/silver-monthly/$m"; og="$gold_directory/$m"
      if [ -f "$og/run_manifest.json" ]; then echo "skip gold $m"; continue; fi
      rm -rf "$og"
      if [ ! -f "$ms/run_manifest.json" ]; then
        echo "merge $m"
        rm -rf "$ms"
        (cd "$DIR02" && uv run --locked python merge_silver_month.py \
           --daily-root "$PARENT/silver" --month "$m" --output "$ms") \
           > "$PARENT/logs/merge-$m.log" 2>&1 || { echo "FAIL merge $m"; failed=1; continue; }
      fi
      available_days=$(python3 -c 'import json, sys; print(len(json.load(open(sys.argv[1]))["dates_utc"]))' \
           "$ms/run_manifest.json") || { echo "FAIL read $ms/run_manifest.json"; failed=1; continue; }
      if [ "$available_days" = 0 ]; then
        echo "skip gold $m: no complete Silver days (see $ms/run_manifest.json)"
        continue
      fi
      echo "gold $m"
      (cd "$DIR02" && uv run --locked python gold_ground_ops.py \
         --silver-root "$ms" --daily-root "$PARENT/silver" --date-list <(month_days "$m") \
         "${geometry_args[@]}" --output "$og") \
         > "$PARENT/logs/$gold_log_prefix-$m.log" 2>&1 || { echo "FAIL gold $m"; failed=1; continue; }
      echo "ok gold $m"
    done <<< "$selected_months"
    echo "=== gold phase done"
    exit "$failed"
    ;;
  release)
    : "${APPROVER:?set APPROVER to the local release reviewer}"
    mkdir -p "$release_directory" "$PARENT/logs" || exit 1
    failed=0
    selected_months=$(months "$START" "$END") || exit 1
    while IFS= read -r m; do
      [ -n "$m" ] || continue
      release_id="$release_prefix-$m"
      exec 8>"$PARENT/logs/.release-$release_id.lock" || exit 1
      flock -x 8 || exit 1
      output="$release_directory/$release_id"
      if [ -f "$output/_SUCCESS" ]; then
        echo "skip release $release_id: already packaged"
        continue
      fi
      if [ -e "$output" ]; then
        echo "blocked release $release_id: see $output/validation.json"
        failed=1
        continue
      fi
      if [ ! -f "$gold_directory/$m/run_manifest.json" ]; then
        echo "skip release $release_id: no completed Gold"
        continue
      fi
      staging=$(mktemp -d "$release_directory/.stage-$m.XXXXXX") || exit 1
      (cd "$DIR02" && uv run --locked python release_gate.py \
         --gold-root "$gold_directory/$m" --contract "$contract" \
         --output "$staging/release" --release-id "$release_id" \
         --approver "$APPROVER" --notes "${RELEASE_NOTES:-}") \
         > "$PARENT/logs/release-$release_id.log" 2>&1 || failed=1
      if [ -f "$staging/release/_SUCCESS" ] ||
         { [ -f "$staging/release/validation.json" ] &&
           python3 -c 'import json, sys; sys.exit(json.load(open(sys.argv[1]))["status"] != "blocked")' \
             "$staging/release/validation.json"; }; then
        mv -T --no-clobber "$staging/release" "$output" || failed=1
      fi
      rm -rf "$staging"
      if [ -f "$output/_SUCCESS" ]; then
        echo "ok release $release_id"
      else
        echo "FAIL release $release_id (see logs/release-$release_id.log)"
        failed=1
      fi
    done <<< "$selected_months"
    echo "=== release phase done"
    exit "$failed"
    ;;
  *) echo "unknown phase: $PHASE (use silver|gold|release)"; exit 2 ;;
esac
