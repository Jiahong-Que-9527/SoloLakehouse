from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType


def load_health_server() -> ModuleType:
    module_path = Path(__file__).resolve().parent.parent / "scripts" / "health-server.py"
    spec = importlib.util.spec_from_file_location("health_server", module_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_status_payload_contains_portal_sections(monkeypatch) -> None:
    module = load_health_server()
    monkeypatch.setattr(
        module,
        "collect_statuses",
        lambda: [
            ("MinIO", "PASS", "Buckets ready"),
            ("Trino", "PASS", "Running"),
            ("MLflow", "PASS", "HTTP 200"),
        ],
    )
    monkeypatch.setenv("PRODUCT_ID", "finlakehouse")
    monkeypatch.setenv("PRODUCT_DISPLAY_NAME", "FinLakehouse")
    monkeypatch.setenv("PRODUCT_DOMAIN", "financial_markets")
    monkeypatch.setenv("ENVIRONMENT", "prod")
    monkeypatch.setenv("RUNTIME_VERSION", "slh-v2.5.1")
    monkeypatch.setenv("DATA_BUCKET", "finlakehouse-data")
    monkeypatch.setenv("OBJECT_STORE_CONSOLE_URL", "http://object-store.local:9001")

    payload = module.status_payload()

    assert payload["status"] == "PASS"
    assert payload["entity"]["product_id"] == "finlakehouse"
    assert payload["storage"]["data_bucket"] == "finlakehouse-data"
    assert payload["demo"]["readiness"]["status"] == "READY"
    assert payload["demo"]["flow"][0]["command"] == "make verify"
    assert payload["demo"]["readiness"]["command"] == "make demo"
    assert {"label": "Health JSON", "url": "/health.json", "detail": "Machine-readable portal status"} in payload["links"]
    assert any(link["url"] == "http://object-store.local:9001" for link in payload["links"])
    assert any(doc["url"] == "/docs/make-demo-guide.md" for doc in payload["docs"])


def test_demo_readiness_reports_blocking_services() -> None:
    module = load_health_server()

    readiness = module.demo_readiness(
        [
            ("MinIO", "PASS", "Buckets ready"),
            ("Dagster", "FAIL", "HTTP 500"),
            ("Superset", "TIMEOUT", "Timed out"),
        ]
    )

    assert readiness["ready"] is False
    assert readiness["status"] == "BLOCKED"
    assert readiness["blocking_services"] == ["Dagster", "Superset"]


def test_render_html_exposes_links_flow_and_entity_context() -> None:
    module = load_health_server()
    payload = {
        "status": "PASS",
        "entity": {
            "product_id": "aviation-lakehouse",
            "display_name": "Aviation Lakehouse",
            "domain": "aviation_operations",
            "environment": "local",
            "runtime_version": "slh-v2.5.1",
            "compose_project_name": "aviation-lakehouse",
            "trino_user": "aviation_lakehouse",
        },
        "storage": {
            "data_bucket": "aviation-lakehouse-data",
            "audit_bucket": "aviation-lakehouse-audit",
            "mlflow_artifact_bucket": "aviation-lakehouse-mlflow",
            "mlflow_artifact_root": "s3://aviation-lakehouse-mlflow/",
            "warehouse_uri": "s3a://aviation-lakehouse-data/warehouse/",
        },
        "links": [
            {
                "label": "Dagster",
                "url": "http://localhost:3000",
                "detail": "Jobs, runs, schedules, and assets",
            },
            {
                "label": "Health JSON",
                "url": "/health.json",
                "detail": "Machine-readable portal status",
            },
        ],
        "docs": [
            {"label": "Make Demo Guide", "url": "/docs/make-demo-guide.md"},
        ],
        "demo": {
            "readiness": {
                "ready": True,
                "status": "READY",
                "summary": "Stack health checks are passing; make demo can run.",
                "blocking_services": [],
                "command": "make demo",
            },
            "flow": module.DEMO_FLOW,
        },
        "services": [
            {"service": "Dagster", "status": "PASS", "detail": "HTTP 200"},
        ],
    }

    html = module.render_html(payload)

    assert "Aviation Lakehouse Portal" in html
    assert "aviation-lakehouse" in html
    assert "aviation_operations" in html
    assert "s3a://aviation-lakehouse-data/warehouse/" in html
    assert "http://localhost:3000" in html
    assert "/health.json" in html
    assert "make verify" in html
    assert "make demo" in html
    assert "/docs/make-demo-guide.md" in html
