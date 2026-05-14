"""Small local health dashboard for the SoloLakehouse v2.5 stack."""

from __future__ import annotations

import argparse
import html
import importlib.util
import json
import sys
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from runtime_identity import RuntimeIdentity, get_runtime_identity  # noqa: E402

StatusTuple = tuple[str, str, str]


def load_verify_setup_module() -> Any:
    module_path = Path(__file__).resolve().with_name("verify-setup.py")
    spec = importlib.util.spec_from_file_location("verify_setup", module_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot load {module_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


verify_setup = load_verify_setup_module()


def collect_statuses() -> list[StatusTuple]:
    verify_setup.load_dotenv_if_present()
    checks = [
        verify_setup.check_minio,
        verify_setup.check_postgres,
        verify_setup.check_hive_metastore,
        verify_setup.check_trino,
        verify_setup.check_mlflow,
        verify_setup.check_dagster,
        verify_setup.check_dagster_credentials,
        verify_setup.check_openmetadata,
        verify_setup.check_superset,
    ]
    return [check() for check in checks]


def status_payload() -> dict[str, Any]:
    statuses = collect_statuses()
    identity = get_runtime_identity()
    return {
        "status": "PASS" if all(status == "PASS" for _, status, _ in statuses) else "FAIL",
        "entity": identity.as_dict(),
        "services": [
            {"service": service, "status": status, "detail": detail}
            for service, status, detail in statuses
        ],
    }


def _identity_summary(identity: RuntimeIdentity) -> str:
    return (
        f"{identity.display_name} ({identity.product_id}, "
        f"{identity.environment}, {identity.runtime_version})"
    )


def render_html(payload: dict[str, Any]) -> str:
    identity = RuntimeIdentity(**payload["entity"])
    display_name = html.escape(identity.display_name)
    identity_summary = html.escape(_identity_summary(identity))
    rows = "\n".join(
        f"<tr><td>{item['service']}</td><td class='{item['status'].lower()}'>{item['status']}</td>"
        f"<td>{html.escape(item['detail'])}</td></tr>"
        for item in payload["services"]
    )
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{display_name} Health</title>
  <style>
    body {{
      font-family: system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      margin: 32px;
      color: #172026;
    }}
    h1 {{ margin-bottom: 4px; }}
    .summary {{ margin: 0 0 24px; font-size: 18px; }}
    table {{ border-collapse: collapse; min-width: 760px; max-width: 100%; }}
    th, td {{ border-bottom: 1px solid #d8dee4; padding: 10px 12px; text-align: left; }}
    th {{ background: #f6f8fa; }}
    .pass {{ color: #116329; font-weight: 700; }}
    .fail, .timeout {{ color: #a40e26; font-weight: 700; }}
    code {{ background: #f6f8fa; padding: 2px 4px; border-radius: 4px; }}
  </style>
</head>
<body>
  <h1>{display_name} Health</h1>
  <p class="summary">Runtime: <code>{identity_summary}</code></p>
  <p class="summary">
    Overall status: <span class="{payload['status'].lower()}">{payload['status']}</span>
  </p>
  <table>
    <thead><tr><th>Service</th><th>Status</th><th>Detail</th></tr></thead>
    <tbody>{rows}</tbody>
  </table>
  <p>JSON endpoint: <code>/health.json</code></p>
</body>
</html>
"""


class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        if self.path not in {"/", "/health", "/health.json"}:
            self.send_error(HTTPStatus.NOT_FOUND)
            return

        payload = status_payload()
        if self.path == "/health.json":
            body = json.dumps(payload, indent=2).encode("utf-8")
            content_type = "application/json; charset=utf-8"
        else:
            body = render_html(payload).encode("utf-8")
            content_type = "text/html; charset=utf-8"

        response_status = (
            HTTPStatus.OK if payload["status"] == "PASS" else HTTPStatus.SERVICE_UNAVAILABLE
        )
        self.send_response(response_status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format: str, *args: object) -> None:
        return


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8090)
    args = parser.parse_args()

    server = ThreadingHTTPServer((args.host, args.port), HealthHandler)
    identity = get_runtime_identity()
    print(f"{identity.display_name} health dashboard: http://{args.host}:{args.port}/health")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
