#!/usr/bin/env bash
# Expose SoloLakehouse UIs on the tailnet via Tailscale Serve (HTTPS).
#
# Prerequisites:
#   1. Tailscale installed and this node joined to your tailnet.
#   2. Serve enabled for this node in the Tailscale admin console (one-time).
#   3. Docker stack running (`make up` / `make verify`).
#
# Usage:
#   ./scripts/tailscale-serve-ui.sh up      # register all UI proxies (background)
#   ./scripts/tailscale-serve-ui.sh down    # tailscale serve reset
#   ./scripts/tailscale-serve-ui.sh status
#   ./scripts/tailscale-serve-ui.sh urls    # print bookmarkable HTTPS URLs

set -euo pipefail

TS_CMD=(tailscale)
if ! tailscale serve status >/dev/null 2>&1; then
  if command -v sudo >/dev/null 2>&1; then
    TS_CMD=(sudo tailscale)
  fi
fi

# tailnet_https_port:local_loopback_port:label
SERVICES=(
  "443:3000:Dagster"
  "8080:8080:Trino"
  "8088:8088:Superset"
  "8585:8585:OpenMetadata"
  "5000:5000:MLflow"
  "9001:9001:MinIO Console"
)

dns_name() {
  tailscale status --json 2>/dev/null \
    | python3 -c "import json,sys; print(json.load(sys.stdin)['Self']['DNSName'].rstrip('.'))" \
    || true
}

print_urls() {
  local host
  host="$(dns_name)"
  if [[ -z "${host}" ]]; then
    echo "Could not resolve Tailscale DNS name. Run: tailscale status"
    return 1
  fi
  echo "FinLakehouse UI URLs (tailnet only, HTTPS):"
  echo ""
  for entry in "${SERVICES[@]}"; do
    IFS=: read -r https_port local_port label <<<"${entry}"
    if [[ "${https_port}" == "443" ]]; then
      printf "  %-16s https://%s/\n" "${label}" "${host}"
    else
      printf "  %-16s https://%s:%s/\n" "${label}" "${host}" "${https_port}"
    fi
  done
  echo ""
  echo "Health (when running): make health  ->  http://127.0.0.1:8090/health (not served by default)"
}

serve_up() {
  local entry https_port local_port label output
  for entry in "${SERVICES[@]}"; do
    IFS=: read -r https_port local_port label <<<"${entry}"
    echo "==> ${label}: tailnet :${https_port} -> 127.0.0.1:${local_port}"
    if ! output="$(
      timeout 15 "${TS_CMD[@]}" serve --yes --bg --https="${https_port}" "http://127.0.0.1:${local_port}" 2>&1
    )"; then
      if grep -q "Serve is not enabled" <<<"${output}"; then
        echo ""
        echo "${output}"
        echo ""
        echo "Enable Serve for this node in the Tailscale admin console, then rerun:"
        echo "  make serve-ui-up"
        exit 1
      fi
      echo "${output}"
      exit 1
    fi
    if grep -q "Serve is not enabled" <<<"${output}"; then
      echo ""
      echo "${output}"
      echo ""
      echo "Enable Serve for this node in the Tailscale admin console, then rerun:"
      echo "  make serve-ui-up"
      exit 1
    fi
  done
  echo ""
  "${TS_CMD[@]}" serve status
  echo ""
  print_urls
}

serve_down() {
  "${TS_CMD[@]}" serve reset
  echo "Tailscale Serve configuration cleared."
}

serve_status() {
  "${TS_CMD[@]}" serve status
  echo ""
  print_urls || true
}

case "${1:-}" in
  up) serve_up ;;
  down) serve_down ;;
  status) serve_status ;;
  urls) print_urls ;;
  *)
    echo "Usage: $0 {up|down|status|urls}" >&2
    exit 2
    ;;
esac
