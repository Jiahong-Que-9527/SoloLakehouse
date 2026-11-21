#!/usr/bin/env bash
# 02 M4 full-dataset driver: per-day Silver -> monthly merge -> monthly Gold.
#
#   ./full_run.sh silver   # 727 daily runs, 2 workers, restartable
#   ./full_run.sh gold     # 24 monthly merges + gold runs, restartable
#
# Every run writes its own log; failed days are listed at the end and the
# phase can simply be re-run (existing outputs are skipped).
set -u
PHASE="${1:?usage: full_run.sh silver|gold}"
PARENT="${PARENT:-/home/bill/slh-data/full-20241101-20261031}"
BRONZE="${BRONZE:-/home/bill/slh-data/aviation}"
DIR02="$(cd "$(dirname "$0")" && pwd)"
WORKERS="${WORKERS:-2}"
START="${START:-2024-11-01}"
END="${END:-2026-10-31}"

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
from datetime import date
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
  fi
}

case "$PHASE" in
  silver)
    mkdir -p "$PARENT/silver" "$PARENT/logs"
    export PARENT BRONZE DIR02
    export -f run_one_silver
    days "$START" "$END" | xargs -P "$WORKERS" -I{} bash -c 'run_one_silver {}'
    echo "=== failed days:"
    grep -l . "$PARENT"/logs/silver-*.log 2>/dev/null | while read -r log; do
      d=$(basename "$log" .log); d=${d#silver-}
      [ -d "$PARENT/silver/$d" ] || echo "$d"
    done
    echo "=== silver phase done"
    ;;
  gold)
    mkdir -p "$PARENT/silver-monthly" "$PARENT/gold" "$PARENT/logs"
    for m in $(months "$START" "$END"); do
      ms="$PARENT/silver-monthly/$m"; og="$PARENT/gold/$m"
      if [ -f "$og/run_manifest.json" ]; then echo "skip gold $m"; continue; fi
      rm -rf "$og"
      if [ ! -f "$ms/observations.parquet" ]; then
        echo "merge $m"
        rm -rf "$ms"
        (cd "$DIR02" && uv run --locked python merge_silver_month.py \
           --daily-root "$PARENT/silver" --month "$m" --output "$ms") \
           > "$PARENT/logs/merge-$m.log" 2>&1 || { echo "FAIL merge $m"; continue; }
      fi
      echo "gold $m"
      (cd "$DIR02" && uv run --locked python gold_ground_ops.py \
         --silver-root "$ms" --date-list <(month_days "$m") \
         --output "$og") \
         > "$PARENT/logs/gold-$m.log" 2>&1 || { echo "FAIL gold $m"; continue; }
      echo "ok gold $m"
    done
    echo "=== gold phase done"
    ;;
  *) echo "unknown phase: $PHASE (use silver|gold)"; exit 2 ;;
esac
