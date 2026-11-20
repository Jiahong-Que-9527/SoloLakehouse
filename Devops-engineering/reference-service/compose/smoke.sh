#!/usr/bin/env bash
# Smoke-check an energy-quality-service image against all D01 routes.
# Usage: compose/smoke.sh [IMAGE] [REPORT_FILE]
#   IMAGE       image reference consumed by compose (default energy-quality-service:d02)
#   REPORT_FILE fixture file name under fixtures/ (default report-passed.json)
# Requires docker, docker compose and curl on the host. Honors an existing
# DOCKER_HOST; on this machine export DOCKER_HOST=unix:///run/recordchat-docker.sock.
set -euo pipefail
cd "$(dirname "$0")"

IMAGE="${1:-energy-quality-service:d02}"
REPORT_FILE="${2:-report-passed.json}"
export ENERGY_QUALITY_IMAGE="$IMAGE"
export AUDIT_REPORT_FILE="$REPORT_FILE"
export ENERGY_QUALITY_PORT="${ENERGY_QUALITY_PORT:-8732}"

EXPECTED_ID=$(grep -o '"report_id": *"[^"]*"' "../fixtures/$REPORT_FILE" | head -1 | sed 's/.*: *"//; s/"//')

STARTED=$SECONDS
docker compose up -d --quiet-pull --wait
echo "startup-to-healthy: $((SECONDS - STARTED))s"

BASE="http://127.0.0.1:$ENERGY_QUALITY_PORT"
echo "--live--"
curl --noproxy '*' -s --max-time 5 -w " [%{http_code}]\n" "$BASE/live"
echo "--ready--"
curl --noproxy '*' -s --max-time 5 -w " [%{http_code}]\n" "$BASE/ready"
echo "--quality--"
BODY=$(curl --noproxy '*' -s --max-time 5 -w "\n[%{http_code}]" "$BASE/v1/quality/latest")
echo "$BODY"
GOT_ID=$(echo "$BODY" | grep -o '"report_id":"[^"]*"' | head -1 | sed 's/.*:"//; s/"//')

if [ "$GOT_ID" = "$EXPECTED_ID" ]; then
  echo "identity-check: OK ($GOT_ID)"
else
  echo "identity-check: FAILED (expected $EXPECTED_ID, got ${GOT_ID:-none})"
  docker compose down
  exit 1
fi

docker compose down
