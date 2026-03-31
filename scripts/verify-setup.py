"""Service verification script for SoloLakehouse runtime."""

from __future__ import annotations

import os
import socket
import subprocess
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
    user = os.environ.get("POSTGRES_USER", "postgres")
    password = os.environ.get("POSTGRES_PASSWORD", "postgres")
    docker_result = _check_postgres_via_docker(user)
    if docker_result is not None:
        return docker_result

    host = os.environ.get("POSTGRES_HOST", "localhost")
    port = int(os.environ.get("POSTGRES_PORT", "5432"))

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
            required = required_postgres_databases()
            cur.execute(
                "SELECT datname FROM pg_database WHERE datname = ANY(%s)",
                (list(required),),
            )
            existing = {row[0] for row in cur.fetchall()}
        missing = sorted(required - existing)
        if missing:
            return ("PostgreSQL", "FAIL", f"Missing databases: {', '.join(missing)}")
        return ("PostgreSQL", "PASS", f"Databases: {', '.join(sorted(required))}")
    except psycopg2.OperationalError as exc:
        message = str(exc)
        if "timeout" in message.lower():
            return ("PostgreSQL", "TIMEOUT", "Timed out after 5s")
        first_line = message.splitlines()[0] if message.splitlines() else exc.__class__.__name__
        return ("PostgreSQL", "FAIL", first_line)
    except Exception as exc:
        return ("PostgreSQL", "FAIL", str(exc))
    finally:
        if conn is not None:
            conn.close()


def _check_postgres_via_docker(user: str) -> StatusTuple | None:
    try:
        result = subprocess.run(
            [
                "docker",
                "exec",
                "slh-postgres",
                "psql",
                "-U",
                user,
                "-d",
                "postgres",
                "-At",
                "-c",
                _postgres_list_databases_query(include_dagster=True),
            ],
            check=True,
            capture_output=True,
            text=True,
            timeout=5,
        )
    except FileNotFoundError:
        return None
    except subprocess.TimeoutExpired:
        return ("PostgreSQL", "TIMEOUT", "Timed out after 5s")
    except subprocess.CalledProcessError as exc:
        detail = exc.stderr.strip() or exc.stdout.strip() or exc.__class__.__name__
        return ("PostgreSQL", "FAIL", detail.splitlines()[0])

    existing = {line.strip() for line in result.stdout.splitlines() if line.strip()}
    required = required_postgres_databases(include_dagster=True)
    missing = sorted(required - existing)
    if missing:
        return ("PostgreSQL", "FAIL", f"Missing databases: {', '.join(missing)}")
    return ("PostgreSQL", "PASS", f"Databases: {', '.join(sorted(required))}")


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
        if response.status_code != 200:
            return ("MLflow", "FAIL", f"HTTP {response.status_code}")
        # Verify DB migration completed: /health returns 200 even while gunicorn workers
        # are still initializing; the experiments endpoint requires a fully migrated schema.
        api_response = requests.get(
            "http://localhost:5000/api/2.0/mlflow/experiments/search",
            timeout=5,
        )
        if api_response.status_code != 200:
            return (
                "MLflow",
                "FAIL",
                f"/health OK but DB not ready (experiments API HTTP {api_response.status_code})",
            )
        return ("MLflow", "PASS", "HTTP 200, DB initialized")
    except requests.Timeout:
        return ("MLflow", "TIMEOUT", "Timed out after 5s")
    except Exception as exc:
        return ("MLflow", "FAIL", str(exc))


_DAGSTER_REQUIRED_CONTAINER_ENV = {
    "AWS_ACCESS_KEY_ID",
    "AWS_SECRET_ACCESS_KEY",
    "MLFLOW_S3_ENDPOINT_URL",
    "MLFLOW_TRACKING_URI",
}


def check_dagster_credentials() -> StatusTuple:
    """Verify the Dagster daemon container has the S3/MLflow env vars needed for artifact upload.

    The MLflow client inside Dagster uploads artifacts directly to S3 via boto3, so these
    credentials must be present in the container process — not just in the MLflow server.
    """
    try:
        result = subprocess.run(
            ["docker", "exec", "slh-dagster-daemon", "env"],
            check=True,
            capture_output=True,
            text=True,
            timeout=5,
        )
    except FileNotFoundError:
        return ("Dagster S3 creds", "FAIL", "docker CLI not found")
    except subprocess.TimeoutExpired:
        return ("Dagster S3 creds", "TIMEOUT", "Timed out after 5s")
    except subprocess.CalledProcessError as exc:
        detail = (exc.stderr or exc.stdout or "").strip().splitlines()
        return ("Dagster S3 creds", "FAIL", detail[0] if detail else exc.__class__.__name__)

    env_keys = {line.split("=", 1)[0] for line in result.stdout.splitlines() if "=" in line}
    missing = sorted(_DAGSTER_REQUIRED_CONTAINER_ENV - env_keys)
    if missing:
        return ("Dagster S3 creds", "FAIL", f"Missing: {', '.join(missing)}")
    return ("Dagster S3 creds", "PASS", "AWS + MLflow S3 credentials present")


def check_openmetadata() -> StatusTuple:
    """Optional: set OPENMETADATA_CHECK=1 to require OpenMetadata UI (profile openmetadata)."""
    base = os.environ.get("OPENMETADATA_URL", "http://localhost:8585").rstrip("/")
    try:
        response = requests.get(f"{base}/api/v1/system/version", timeout=5)
        if response.status_code == 200:
            return ("OpenMetadata", "PASS", f"API OK ({base})")
        return ("OpenMetadata", "FAIL", f"HTTP {response.status_code}")
    except requests.Timeout:
        return ("OpenMetadata", "TIMEOUT", "Timed out after 5s")
    except Exception as exc:
        return ("OpenMetadata", "FAIL", str(exc))


def check_superset() -> StatusTuple:
    base = os.environ.get("SUPERSET_URL", "http://localhost:8088").rstrip("/")
    try:
        response = requests.get(f"{base}/health", timeout=5)
        if response.status_code == 200:
            return ("Superset", "PASS", f"HTTP 200 ({base}/health)")
        return ("Superset", "FAIL", f"HTTP {response.status_code}")
    except requests.Timeout:
        return ("Superset", "TIMEOUT", "Timed out after 5s")
    except Exception as exc:
        return ("Superset", "FAIL", str(exc))


def check_dagster() -> StatusTuple:
    try:
        response = requests.get("http://localhost:3000/server_info", timeout=5)
        if response.status_code == 200:
            return ("Dagster", "PASS", "HTTP 200 /server_info")
        return ("Dagster", "FAIL", f"HTTP {response.status_code}")
    except requests.Timeout:
        return ("Dagster", "TIMEOUT", "Timed out after 5s")
    except Exception as exc:
        return ("Dagster", "FAIL", str(exc))


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


def _postgres_list_databases_query(*, include_dagster: bool) -> str:
    dbs = sorted(required_postgres_databases(include_dagster=include_dagster))
    in_list = ", ".join(repr(db) for db in dbs)
    return f"SELECT datname FROM pg_database WHERE datname IN ({in_list})"


def required_postgres_databases(*, include_dagster: bool = False) -> set[str]:
    required = {"hive_metastore", "mlflow"}
    if include_dagster:
        required.add("dagster_storage")
    if os.environ.get("SUPERSET_CHECK") == "1":
        required.add(os.environ.get("SUPERSET_DB_NAME", "superset_metadata"))
    return required


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

    checks: list = [
        check_minio,
        check_postgres,
        check_hive_metastore,
        check_trino,
        check_mlflow,
        check_dagster,
        check_dagster_credentials,
    ]
    if os.environ.get("OPENMETADATA_CHECK") == "1":
        checks.append(check_openmetadata)
    if os.environ.get("SUPERSET_CHECK") == "1":
        checks.append(check_superset)
    results = [check() for check in checks]
    print_status_table(results)

    all_pass = all(status == "PASS" for _, status, _ in results)
    if missing_env:
        return 1
    return 0 if all_pass else 1


if __name__ == "__main__":
    sys.exit(main())
