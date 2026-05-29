"""End-to-end demo verification for the v2.5 freeze path."""

from __future__ import annotations

import os
import sys
import urllib.parse
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import trino  # noqa: E402

from runtime_identity import get_trino_user  # noqa: E402

DEMO_QUERIES = {
    "Iceberg Gold": "SELECT count(*) AS total_rows FROM iceberg.gold.ecb_dax_features",
}


def load_dotenv_if_present() -> None:
    env_path = Path(__file__).resolve().parent.parent / ".env"
    if not env_path.exists():
        return

    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        if key and key not in os.environ:
            os.environ[key] = value


def execute_count(trino_url: str, sql: str) -> int:
    parsed = urllib.parse.urlparse(trino_url)
    conn = trino.dbapi.connect(
        host=parsed.hostname or "localhost",
        port=parsed.port or 8080,
        user=get_trino_user(),
        http_scheme=parsed.scheme or "http",
    )
    try:
        cur = conn.cursor()
        cur.execute(sql)
        row = cur.fetchone()
        if row is None:
            raise ValueError("Trino returned no rows")
        return int(row[0])
    finally:
        conn.close()


def main() -> int:
    load_dotenv_if_present()
    trino_url = os.environ.get("TRINO_URL", "http://localhost:8080")

    failures: list[str] = []
    print("Demo check      Rows  Status")
    print("--------------- ----- ------")
    for label, sql in DEMO_QUERIES.items():
        try:
            rows = execute_count(trino_url, sql)
            status = "PASS" if rows > 0 else "FAIL"
            print(f"{label:<15} {rows:<5} {status}")
            if rows <= 0:
                failures.append(f"{label} returned zero rows")
        except Exception as exc:
            print(f"{label:<15} {'-':<5} FAIL")
            failures.append(f"{label}: {exc}")

    if failures:
        print("")
        print("Failures:")
        for failure in failures:
            print(f"- {failure}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
