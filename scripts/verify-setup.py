"""Service verification script for SoloLakehouse runtime."""

from __future__ import annotations

import os
import socket
import sys
from pathlib import Path

import psycopg2
import requests
from minio import Minio

StatusTuple = tuple[str, str, str]
VALID_STATUSES = {"PASS", "FAIL", "TIMEOUT"}


def load_dotenv_if_present() -> None:
    env_path = Path(__file__).resolve().parent.parent / ".env"
    if not env_path.exists():
        return

    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()
        if key and key not in os.environ:
            os.environ[key] = value


def _minio_base_url(endpoint: str) -> str:
    if endpoint.startswith("http://") or endpoint.startswith("https://"):
        return endpoint.rstrip("/")
    return f"http://{endpoint}".rstrip("/")


def check_minio() -> StatusTuple:
    endpoint = os.environ.get("MINIO_ENDPOINT", "localhost:9000")
    health_url = f"{_minio_base_url(endpoint)}/minio/health/live"
    minio_endpoint = endpoint.replace("http://", "").replace("https://", "").rstrip("/")

    try:
        response = requests.get(health_url, timeout=5)
        if response.status_code != 200:
            return ("MinIO", "FAIL", f"Health endpoint returned HTTP {response.status_code}")

        access_key = os.environ.get(
            "S3_ACCESS_KEY",
            os.environ.get("MINIO_ROOT_USER", "sololakehouse"),
        )
        secret_key = os.environ.get(
            "S3_SECRET_KEY",
            os.environ.get("MINIO_ROOT_PASSWORD", "sololakehouse123"),
        )
        client = Minio(minio_endpoint, access_key=access_key, secret_key=secret_key, secure=False)
        buckets = {bucket.name for bucket in client.list_buckets()}
        required = {"sololakehouse", "mlflow-artifacts"}
        missing = sorted(required - buckets)
        if missing:
            return ("MinIO", "FAIL", f"Missing buckets: {', '.join(missing)}")

        return ("MinIO", "PASS", "Buckets: sololakehouse, mlflow-artifacts")
    except requests.Timeout:
        return ("MinIO", "TIMEOUT", "Timed out after 5s")
    except Exception as exc:
        return ("MinIO", "FAIL", str(exc))


def check_postgres() -> StatusTuple:
    host = os.environ.get("POSTGRES_HOST", "localhost")
    port = int(os.environ.get("POSTGRES_PORT", "5432"))
    user = os.environ.get("POSTGRES_USER", "postgres")
    password = os.environ.get("POSTGRES_PASSWORD", "postgres")

    conn = None
    try:
        conn = psycopg2.connect(
            host=host,
            port=port,
            user=user,
            password=password,
            dbname="postgres",
            connect_timeout=5,
        )
        with conn.cursor() as cur:
            cur.execute(
                "SELECT datname FROM pg_database WHERE datname IN (%s, %s)",
                ("hive_metastore", "mlflow"),
            )
            existing = {row[0] for row in cur.fetchall()}
        required = {"hive_metastore", "mlflow"}
        missing = sorted(required - existing)
        if missing:
            return ("PostgreSQL", "FAIL", f"Missing databases: {', '.join(missing)}")
        return ("PostgreSQL", "PASS", "Databases: hive_metastore, mlflow")
    except psycopg2.OperationalError as exc:
        message = str(exc)
        if "timeout" in message.lower():
            return ("PostgreSQL", "TIMEOUT", "Timed out after 5s")
        return ("PostgreSQL", "FAIL", message.splitlines()[0])
    except Exception as exc:
        return ("PostgreSQL", "FAIL", str(exc))
    finally:
        if conn is not None:
            conn.close()


def check_hive_metastore() -> StatusTuple:
    host = os.environ.get("HIVE_METASTORE_HOST", "localhost")
    port = int(os.environ.get("HIVE_METASTORE_PORT", "9083"))

    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(5)
    try:
        sock.connect((host, port))
        return ("Hive Metastore", "PASS", "TCP port 9083 open")
    except socket.timeout:
        return ("Hive Metastore", "TIMEOUT", "Timed out after 5s")
    except Exception as exc:
        return ("Hive Metastore", "FAIL", str(exc))
    finally:
        sock.close()


def check_trino() -> StatusTuple:
    try:
        response = requests.get("http://localhost:8080/v1/info", timeout=5)
        if response.status_code != 200:
            return ("Trino", "FAIL", f"HTTP {response.status_code}")
        payload = response.json()
        starting = bool(payload.get("starting", True))
        if starting:
            return ("Trino", "FAIL", "Still starting")
        return ("Trino", "PASS", "Running, not starting")
    except requests.Timeout:
        return ("Trino", "TIMEOUT", "Timed out after 5s")
    except Exception as exc:
        return ("Trino", "FAIL", str(exc))


def check_mlflow() -> StatusTuple:
    try:
        response = requests.get("http://localhost:5000/health", timeout=5)
        if response.status_code == 200:
            return ("MLflow", "PASS", "HTTP 200")
        return ("MLflow", "FAIL", f"HTTP {response.status_code}")
    except requests.Timeout:
        return ("MLflow", "TIMEOUT", "Timed out after 5s")
    except Exception as exc:
        return ("MLflow", "FAIL", str(exc))


def validate_required_env_vars() -> list[str]:
    required = [
        "MINIO_ROOT_USER",
        "MINIO_ROOT_PASSWORD",
        "MINIO_ENDPOINT",
        "POSTGRES_USER",
        "POSTGRES_PASSWORD",
        "POSTGRES_HOST",
        "POSTGRES_PORT",
        "S3_ACCESS_KEY",
        "S3_SECRET_KEY",
        "MLFLOW_TRACKING_URI",
    ]
    return [name for name in required if not os.environ.get(name)]


def print_status_table(results: list[StatusTuple]) -> None:
    print("Service          Status  Detail")
    print("---------------- ------- ----------------------------")
    for service, status, detail in results:
        status_display = status if status in VALID_STATUSES else "FAIL"
        print(f"{service:<16} {status_display:<7} {detail}")


def main() -> int:
    load_dotenv_if_present()

    missing_env = validate_required_env_vars()
    if missing_env:
        print(f"Missing required env vars: {', '.join(missing_env)}")

    checks = [
        check_minio,
        check_postgres,
        check_hive_metastore,
        check_trino,
        check_mlflow,
    ]
    results = [check() for check in checks]
    print_status_table(results)

    all_pass = all(status == "PASS" for _, status, _ in results)
    if missing_env:
        return 1
    return 0 if all_pass else 1


if __name__ == "__main__":
    sys.exit(main())
