"""Ensure required PostgreSQL databases exist for local SoloLakehouse runtime."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import psycopg2
from psycopg2 import sql

REPO_ROOT = Path(__file__).resolve().parent.parent
REQUIRED_DATABASES = ("hive_metastore", "mlflow", "dagster_storage")


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


def main() -> int:
    load_dotenv_if_present()

    user = os.environ.get("POSTGRES_USER", "postgres")
    password = os.environ.get("POSTGRES_PASSWORD", "postgres")

    created = ensure_databases_via_docker(user)
    if created is None:
        created = ensure_databases_via_tcp(user=user, password=password)

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
    host = os.environ.get("POSTGRES_HOST", "localhost")
    port = int(os.environ.get("POSTGRES_PORT", "5432"))
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
