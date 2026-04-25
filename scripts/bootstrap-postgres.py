"""Ensure required PostgreSQL databases exist for local SoloLakehouse runtime."""

from __future__ import annotations

import os
import secrets
import subprocess
import sys
from pathlib import Path

import psycopg2
from psycopg2 import sql

REPO_ROOT = Path(__file__).resolve().parent.parent
REQUIRED_DATABASES = ("hive_metastore", "mlflow", "dagster_storage", "superset_metadata")


def _postgres_tcp_endpoint() -> tuple[str, int]:
    """Host-side TCP endpoint for the published Postgres port (Compose maps PG_PORT)."""
    host = os.environ.get("POSTGRES_HOST", "localhost")
    port_s = os.environ.get("PG_PORT") or os.environ.get("POSTGRES_PORT", "5432")
    return host, int(port_s)


def _dollar_quote_string(value: str) -> str:
    """Return a PostgreSQL dollar-quoted literal safe for passwords with quotes or $."""
    for _ in range(32):
        tag = f"slh_{secrets.token_hex(8)}"
        open_close = f"${tag}$"
        if open_close not in value:
            return f"{open_close}{value}{open_close}"
    raise RuntimeError("could not dollar-quote password safely")


def load_dotenv_if_present() -> None:
    env_path = REPO_ROOT / ".env"
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


def required_databases() -> tuple[str, ...]:
    extra = tuple(
        database.strip()
        for database in os.environ.get("EXTRA_POSTGRES_DATABASES", "").split(",")
        if database.strip()
    )
    return REQUIRED_DATABASES + extra


def verify_tcp_password(*, user: str, password: str) -> bool:
    host, port = _postgres_tcp_endpoint()
    try:
        conn = psycopg2.connect(
            host=host,
            port=port,
            user=user,
            password=password,
            dbname="postgres",
            connect_timeout=5,
        )
        conn.close()
        return True
    except psycopg2.OperationalError:
        return False


def align_role_password_via_docker(*, user: str, password: str) -> None:
    """Apply ALTER USER using trusted in-container psql (avoids quoting issues)."""
    literal = _dollar_quote_string(password)
    safe_user = user.replace('"', '""')
    stmt = f'ALTER USER "{safe_user}" PASSWORD {literal};'
    subprocess.run(
        [
            "docker",
            "exec",
            "slh-postgres",
            "psql",
            "-U",
            user,
            "-d",
            "postgres",
            "-v",
            "ON_ERROR_STOP=1",
            "-c",
            stmt,
        ],
        check=True,
        capture_output=True,
        text=True,
    )


def main() -> int:
    load_dotenv_if_present()

    user = os.environ.get("POSTGRES_USER", "postgres")
    password = os.environ.get("POSTGRES_PASSWORD", "postgres")

    created = ensure_databases_via_docker(user)
    if created is None:
        created = ensure_databases_via_tcp(user=user, password=password)
    elif not verify_tcp_password(user=user, password=password):
        # docker exec uses a local socket (often trust); TCP clients (Hive, MLflow) need SCRAM.
        # If the data directory was initialized with a different password than .env, fix it here.
        print(
            "PostgreSQL accepts local docker exec connections but TCP auth with .env failed; "
            "syncing role password to POSTGRES_PASSWORD from .env.",
            file=sys.stderr,
        )
        try:
            align_role_password_via_docker(user=user, password=password)
        except subprocess.CalledProcessError as exc:
            print(exc.stderr or exc.stdout or str(exc), file=sys.stderr)
            print(
                "Could not align Postgres password. If you changed POSTGRES_PASSWORD after the "
                "first volume init, run `make clean` (destructive) or set the password manually "
                "(see docs/USER_GUIDE.md section 10).",
                file=sys.stderr,
            )
            return 1
        if not verify_tcp_password(user=user, password=password):
            print(
                "TCP authentication still fails after password sync; check POSTGRES_HOST/PG_PORT.",
                file=sys.stderr,
            )
            return 1
        print(
            "PostgreSQL role password aligned with .env for TCP clients (Hive Metastore).",
            flush=True,
        )

    if created:
        print(f"Created databases: {', '.join(created)}")
    else:
        print("All required PostgreSQL databases already exist.")
    return 0


def ensure_databases_via_docker(user: str) -> list[str] | None:
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
                "SELECT datname FROM pg_database;",
            ],
            check=True,
            capture_output=True,
            text=True,
        )
    except (FileNotFoundError, subprocess.CalledProcessError):
        return None

    existing = {line.strip() for line in result.stdout.splitlines() if line.strip()}
    created: list[str] = []
    for database in required_databases():
        if database in existing:
            continue
        subprocess.run(
            [
                "docker",
                "exec",
                "slh-postgres",
                "psql",
                "-U",
                user,
                "-d",
                "postgres",
                "-c",
                f"CREATE DATABASE {database};",
            ],
            check=True,
            capture_output=True,
            text=True,
        )
        created.append(database)
    return created


def ensure_databases_via_tcp(*, user: str, password: str) -> list[str]:
    host, port = _postgres_tcp_endpoint()
    conn = psycopg2.connect(
        host=host,
        port=port,
        user=user,
        password=password,
        dbname="postgres",
        connect_timeout=5,
    )
    conn.autocommit = True

    created: list[str] = []
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT datname FROM pg_database WHERE datname = ANY(%s)",
                (list(required_databases()),),
            )
            existing = {row[0] for row in cur.fetchall()}
            for database in required_databases():
                if database in existing:
                    continue
                cur.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(database)))
                created.append(database)
    finally:
        conn.close()
    return created


if __name__ == "__main__":
    sys.exit(main())
