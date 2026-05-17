"""Small local operator portal for the SoloLakehouse v2.5 stack."""

from __future__ import annotations

import argparse
import html
import importlib.util
import json
import os
import sys
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from runtime_identity import RuntimeIdentity, get_runtime_identity  # noqa: E402
from storage_config import get_storage_config  # noqa: E402

StatusTuple = tuple[str, str, str]
DOC_LINKS = [
    {
        "label": "Make Demo Guide",
        "route": "/docs/make-demo-guide.md",
        "path": REPO_ROOT / "docs" / "make-demo-guide.md",
    },
    {
        "label": "Demo Runbook",
        "route": "/docs/DEMO_RUNBOOK.md",
        "path": REPO_ROOT / "docs" / "DEMO_RUNBOOK.md",
    },
    {
        "label": "Demo Runbook EN",
        "route": "/docs/DEMO_RUNBOOK_EN.md",
        "path": REPO_ROOT / "docs" / "DEMO_RUNBOOK_EN.md",
    },
]
DOC_ROUTES = {item["route"]: item["path"] for item in DOC_LINKS}

DEMO_FLOW = [
    {
        "label": "Verify",
        "command": "make verify",
        "detail": "Run service, credential, and bucket health checks.",
    },
    {
        "label": "Dagster",
        "command": "demo_data_flow_job",
        "detail": "Execute the demo orchestration job.",
    },
    {
        "label": "Medallion",
        "command": "Bronze -> Silver -> Gold",
        "detail": "Build raw, cleaned, and feature data assets.",
    },
    {
        "label": "Trino",
        "command": "Hive Gold + Iceberg Gold counts",
        "detail": "Confirm both published Gold surfaces are queryable.",
    },
    {
        "label": "MLflow",
        "command": "make pipeline",
        "detail": "Optional experiment and artifact coverage path.",
    },
]


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


def resolve_service_links() -> list[dict[str, str]]:
    return [
        {
            "label": "Object Store",
            "url": _env_url(
                "OBJECT_STORE_CONSOLE_URL",
                _env("MINIO_CONSOLE_URL", "http://localhost:9001"),
            ),
            "detail": "S3-compatible object store console",
        },
        {
            "label": "Trino",
            "url": _env_url("TRINO_URL", "http://localhost:8080"),
            "detail": "SQL engine and query UI",
        },
        {
            "label": "MLflow",
            "url": _env_url("MLFLOW_TRACKING_URI", "http://localhost:5000"),
            "detail": "Experiments, metrics, and artifacts",
        },
        {
            "label": "Dagster",
            "url": _env_url("DAGSTER_URL", "http://localhost:3000"),
            "detail": "Jobs, runs, schedules, and assets",
        },
        {
            "label": "OpenMetadata",
            "url": _env_url("OPENMETADATA_URL", "http://localhost:8585"),
            "detail": "Catalog, ownership, and lineage metadata",
        },
        {
            "label": "Superset",
            "url": _env_url("SUPERSET_URL", "http://localhost:8088"),
            "detail": "Dashboards and data exploration",
        },
        {
            "label": "Health JSON",
            "url": "/health.json",
            "detail": "Machine-readable portal status",
        },
    ]


def demo_readiness(statuses: list[StatusTuple]) -> dict[str, Any]:
    blocking = [service for service, status, _ in statuses if status != "PASS"]
    ready = not blocking
    return {
        "ready": ready,
        "status": "READY" if ready else "BLOCKED",
        "summary": (
            "Stack health checks are passing; make demo can run."
            if ready
            else "Fix failing health checks before running make demo."
        ),
        "blocking_services": blocking,
        "command": "make demo",
    }


def status_payload() -> dict[str, Any]:
    statuses = collect_statuses()
    identity = get_runtime_identity()
    storage = get_storage_config()
    return {
        "status": "PASS" if all(status == "PASS" for _, status, _ in statuses) else "FAIL",
        "entity": identity.as_dict(),
        "storage": storage.as_dict(),
        "links": resolve_service_links(),
        "docs": [
            {"label": item["label"], "url": item["route"]}
            for item in DOC_LINKS
            if item["path"].exists()
        ],
        "demo": {
            "readiness": demo_readiness(statuses),
            "flow": DEMO_FLOW,
        },
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


def _env(name: str, default: str) -> str:
    value = os.environ.get(name)
    if value is None:
        return default
    cleaned = value.strip().strip("\"'")
    return cleaned or default


def _env_url(name: str, default: str) -> str:
    value = _env(name, default)
    if value.startswith("/") or "://" in value:
        return value.rstrip("/") if value != "/" else value
    return f"http://{value.rstrip('/')}"


def _css_class(value: str) -> str:
    return html.escape(value.lower().replace(" ", "-"))


def render_html(payload: dict[str, Any]) -> str:
    identity = RuntimeIdentity(**payload["entity"])
    display_name = html.escape(identity.display_name)
    identity_summary = html.escape(_identity_summary(identity))
    storage = payload["storage"]
    readiness = payload["demo"]["readiness"]
    readiness_class = _css_class(readiness["status"])
    rows = "\n".join(
        f"<tr><td>{html.escape(item['service'])}</td>"
        f"<td class='{_css_class(item['status'])}'>{html.escape(item['status'])}</td>"
        f"<td>{html.escape(item['detail'])}</td></tr>"
        for item in payload["services"]
    )
    service_links = "\n".join(
        f"<a class='tile' href='{html.escape(item['url'], quote=True)}'>"
        f"<strong>{html.escape(item['label'])}</strong>"
        f"<span>{html.escape(item['detail'])}</span>"
        "</a>"
        for item in payload["links"]
    )
    docs = "\n".join(
        f"<a href='{html.escape(item['url'], quote=True)}'>{html.escape(item['label'])}</a>"
        for item in payload["docs"]
    )
    flow = "\n".join(
        f"<li><span>{html.escape(step['label'])}</span>"
        f"<code>{html.escape(step['command'])}</code>"
        f"<small>{html.escape(step['detail'])}</small></li>"
        for step in payload["demo"]["flow"]
    )
    blocked = ", ".join(readiness["blocking_services"])
    blocked_detail = (
        f"<p class='muted'>Blocking services: {html.escape(blocked)}</p>" if blocked else ""
    )
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{display_name} Portal</title>
  <style>
    :root {{
      color-scheme: light;
      --ink: #172026;
      --muted: #586069;
      --line: #d8dee4;
      --soft: #f6f8fa;
      --pass: #116329;
      --fail: #a40e26;
      --ready: #0f766e;
      --accent: #3454d1;
    }}
    body {{
      font-family: system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      margin: 0;
      color: var(--ink);
      background: #ffffff;
    }}
    main {{
      width: min(1120px, calc(100% - 32px));
      margin: 0 auto;
      padding: 28px 0 40px;
    }}
    header {{
      border-bottom: 1px solid var(--line);
      padding-bottom: 20px;
      margin-bottom: 24px;
    }}
    h1, h2, p {{ margin-top: 0; }}
    h1 {{ margin-bottom: 6px; font-size: 34px; line-height: 1.15; }}
    h2 {{ font-size: 20px; margin-bottom: 12px; }}
    section {{ margin-top: 28px; }}
    .summary {{ margin: 0; font-size: 17px; color: var(--muted); }}
    .identity-grid, .link-grid {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(190px, 1fr));
      gap: 10px;
    }}
    .metric, .tile {{
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 12px;
      background: #fff;
    }}
    .metric span, .tile span, small {{
      display: block;
      color: var(--muted);
      font-size: 13px;
      margin-top: 4px;
    }}
    .tile {{
      color: var(--ink);
      text-decoration: none;
    }}
    .tile:hover {{ border-color: var(--accent); }}
    .readiness {{
      border-left: 4px solid var(--ready);
      background: var(--soft);
      padding: 14px 16px;
      margin-bottom: 16px;
    }}
    .readiness.blocked {{ border-left-color: var(--fail); }}
    table {{ border-collapse: collapse; width: 100%; }}
    th, td {{ border-bottom: 1px solid var(--line); padding: 10px 12px; text-align: left; }}
    th {{ background: var(--soft); }}
    .pass, .ready {{ color: var(--pass); font-weight: 700; }}
    .fail, .timeout, .blocked {{ color: var(--fail); font-weight: 700; }}
    code {{ background: var(--soft); padding: 2px 5px; border-radius: 4px; }}
    ol {{ padding-left: 22px; }}
    li {{ margin-bottom: 12px; }}
    li span {{ font-weight: 700; margin-right: 8px; }}
    .docs a {{ margin-right: 16px; white-space: nowrap; }}
    .muted {{ color: var(--muted); margin-bottom: 0; }}
    @media (max-width: 720px) {{
      main {{ width: min(100% - 20px, 1120px); padding-top: 18px; }}
      h1 {{ font-size: 28px; }}
      table {{ font-size: 14px; }}
      th, td {{ padding: 8px; }}
    }}
  </style>
</head>
<body>
  <main>
    <header>
      <h1>{display_name} Portal</h1>
      <p class="summary">Runtime: <code>{identity_summary}</code></p>
    </header>

    <section>
      <h2>Entity</h2>
      <div class="identity-grid">
        <div class="metric">
          <strong>{html.escape(identity.product_id)}</strong>
          <span>Product ID</span>
        </div>
        <div class="metric">
          <strong>{html.escape(identity.domain)}</strong>
          <span>Domain</span>
        </div>
        <div class="metric">
          <strong>{html.escape(identity.environment)}</strong>
          <span>Environment</span>
        </div>
        <div class="metric">
          <strong>{html.escape(identity.runtime_version)}</strong>
          <span>Runtime Version</span>
        </div>
        <div class="metric">
          <strong>{html.escape(storage['data_bucket'])}</strong>
          <span>Data Bucket</span>
        </div>
        <div class="metric">
          <strong>{html.escape(storage['warehouse_uri'])}</strong>
          <span>Warehouse URI</span>
        </div>
      </div>
    </section>

    <section>
      <h2>Demo Readiness</h2>
      <div class="readiness {readiness_class}">
        <strong class="{readiness_class}">{html.escape(readiness['status'])}</strong>
        <p class="muted">
          {html.escape(readiness['summary'])}
          Command: <code>{html.escape(readiness['command'])}</code>
        </p>
        {blocked_detail}
      </div>
      <ol>{flow}</ol>
    </section>

    <section>
      <h2>Services</h2>
      <div class="link-grid">{service_links}</div>
    </section>

    <section>
      <h2>Health</h2>
      <p class="summary">
        Overall status:
        <span class="{_css_class(payload['status'])}">
          {html.escape(payload['status'])}
        </span>
      </p>
      <table>
        <thead><tr><th>Service</th><th>Status</th><th>Detail</th></tr></thead>
        <tbody>{rows}</tbody>
      </table>
    </section>

    <section class="docs">
      <h2>Docs</h2>
      {docs}
    </section>
  </main>
</body>
</html>
"""


class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        if self.path in DOC_ROUTES:
            self._serve_doc(DOC_ROUTES[self.path])
            return

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

    def _serve_doc(self, path: Path) -> None:
        if not path.exists():
            self.send_error(HTTPStatus.NOT_FOUND)
            return

        body = path.read_bytes()
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", "text/markdown; charset=utf-8")
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
    print(f"{identity.display_name} portal: http://{args.host}:{args.port}/health")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
