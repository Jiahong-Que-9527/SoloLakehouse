#!/usr/bin/env python3
"""Ensure a Superset dataset + line chart for eur_market_daily (L7 tile).

Creates or updates a Trino Iceberg dataset and a dual-metric line chart for
``eur_usd`` and ``ewg_close_eur`` when SUPERSET_ADMIN_USERNAME and
SUPERSET_ADMIN_PASSWORD are set. Exits 0 with a skip message when credentials
are absent so local/CI trees without Superset stay green.
"""

from __future__ import annotations

import json
import os
import sys
from typing import Any
from urllib.parse import urljoin

import requests

REPOSITORY_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPOSITORY_ROOT not in sys.path:
    sys.path.insert(0, REPOSITORY_ROOT)


DATASET_TABLE = "eur_market_daily"
DATASET_SCHEMA = "gold"
CHART_NAME = "EUR market daily — EUR/USD & EWG-in-EUR"
DATASET_NAME = "eur_market_daily"


def _load_dotenv() -> None:
    env_path = os.path.join(REPOSITORY_ROOT, ".env")
    if not os.path.exists(env_path):
        return
    for raw_line in open(env_path, encoding="utf-8"):
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        if key and key not in os.environ:
            os.environ[key] = value


def _require_admin() -> tuple[str, str] | None:
    username = os.environ.get("SUPERSET_ADMIN_USERNAME", "").strip()
    password = os.environ.get("SUPERSET_ADMIN_PASSWORD", "").strip()
    if not username or not password:
        return None
    return username, password


class SupersetClient:
    def __init__(self, base_url: str, username: str, password: str):
        self.base_url = base_url.rstrip("/") + "/"
        self.session = requests.Session()
        self.username = username
        self.password = password
        self._csrf: str | None = None

    def _url(self, path: str) -> str:
        return urljoin(self.base_url, path.lstrip("/"))

    def login(self) -> None:
        response = self.session.post(
            self._url("/api/v1/security/login"),
            json={
                "username": self.username,
                "password": self.password,
                "provider": "db",
                "refresh": True,
            },
            timeout=30,
        )
        response.raise_for_status()
        token = response.json()["access_token"]
        self.session.headers.update({"Authorization": f"Bearer {token}"})
        csrf = self.session.get(self._url("/api/v1/security/csrf_token/"), timeout=30)
        csrf.raise_for_status()
        self._csrf = csrf.json()["result"]
        self.session.headers.update({"X-CSRFToken": self._csrf})
        # Superset often expects the CSRF cookie to round-trip on mutating calls.
        self.session.headers.update({"Referer": self.base_url})

    def _get(self, path: str, **params: Any) -> dict[str, Any]:
        response = self.session.get(self._url(path), params=params, timeout=30)
        response.raise_for_status()
        return response.json()

    def _post(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        response = self.session.post(self._url(path), json=payload, timeout=30)
        response.raise_for_status()
        return response.json()

    def _put(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        response = self.session.put(self._url(path), json=payload, timeout=30)
        response.raise_for_status()
        return response.json()

    def find_database_id(self, preferred_names: list[str]) -> int:
        payload = self._get("/api/v1/database/", q=json.dumps({"page": 0, "page_size": 100}))
        by_name = {row["database_name"]: row["id"] for row in payload.get("result", [])}
        for name in preferred_names:
            if name in by_name:
                return int(by_name[name])
        if by_name:
            # Fall back to the first configured database rather than failing hard.
            return int(next(iter(by_name.values())))
        raise RuntimeError("No Superset database connections found")

    def ensure_dataset(self, database_id: int) -> int:
        q = {
            "filters": [
                {"col": "table_name", "opr": "eq", "value": DATASET_TABLE},
                {"col": "schema", "opr": "eq", "value": DATASET_SCHEMA},
            ],
            "page": 0,
            "page_size": 10,
        }
        existing = self._get("/api/v1/dataset/", q=json.dumps(q)).get("result", [])
        if existing:
            dataset_id = int(existing[0]["id"])
            self.session.put(
                self._url(f"/api/v1/dataset/{dataset_id}/refresh"),
                timeout=30,
            ).raise_for_status()
            return dataset_id

        created = self._post(
            "/api/v1/dataset/",
            {
                "database": database_id,
                "schema": DATASET_SCHEMA,
                "table_name": DATASET_TABLE,
            },
        )
        return int(created["id"])

    def ensure_chart(self, dataset_id: int) -> int:
        q = {
            "filters": [{"col": "slice_name", "opr": "eq", "value": CHART_NAME}],
            "page": 0,
            "page_size": 10,
        }
        existing = self._get("/api/v1/chart/", q=json.dumps(q)).get("result", [])
        params = {
            "viz_type": "echarts_timeseries_line",
            "datasource": f"{dataset_id}__table",
            "granularity_sqla": "observation_date",
            "time_range": "No filter",
            "metrics": [
                {
                    "expressionType": "SIMPLE",
                    "column": {"column_name": "eur_usd"},
                    "aggregate": "AVG",
                    "label": "eur_usd",
                },
                {
                    "expressionType": "SIMPLE",
                    "column": {"column_name": "ewg_close_eur"},
                    "aggregate": "AVG",
                    "label": "ewg_close_eur",
                },
            ],
            "groupby": [],
            "x_axis": "observation_date",
        }
        payload = {
            "slice_name": CHART_NAME,
            "viz_type": "echarts_timeseries_line",
            "datasource_id": dataset_id,
            "datasource_type": "table",
            "params": json.dumps(params),
        }
        if existing:
            chart_id = int(existing[0]["id"])
            self._put(f"/api/v1/chart/{chart_id}", payload)
            return chart_id
        created = self._post("/api/v1/chart/", payload)
        return int(created["id"])


def main() -> int:
    _load_dotenv()
    admin = _require_admin()
    if admin is None:
        print("Skipping Superset EUR market tile: SUPERSET_ADMIN_* not set.")
        return 0

    base_url = os.environ.get("SUPERSET_URL", "http://localhost:8088").rstrip("/")
    username, password = admin
    client = SupersetClient(base_url, username, password)
    client.login()

    preferred = [
        os.environ.get("SUPERSET_TRINO_ICEBERG_DB_NAME", "trino_iceberg_gold"),
        "trino_iceberg_gold",
        "finlakehouse_trino_iceberg",
    ]
    database_id = client.find_database_id(preferred)
    dataset_id = client.ensure_dataset(database_id)
    chart_id = client.ensure_chart(dataset_id)
    print(
        json.dumps(
            {
                "status": "ok",
                "database_id": database_id,
                "dataset_id": dataset_id,
                "dataset_name": DATASET_NAME,
                "chart_id": chart_id,
                "chart_name": CHART_NAME,
                "superset_url": base_url,
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
