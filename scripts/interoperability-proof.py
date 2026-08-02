#!/usr/bin/env python3
"""Generate a catalog interoperability proof for v2.7 Block I4."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

from governance.interoperability import (  # noqa: E402
    CatalogBackendBinding,
    build_catalog_interoperability_proof,
    count_rest_namespaces,
)
from ingestion.catalog_boundary import load_catalog_settings  # noqa: E402
from runtime_identity import get_runtime_identity  # noqa: E402


def _binding_from_settings(settings: object) -> CatalogBackendBinding:
    from ingestion.catalog_boundary import CatalogConnectionSettings

    if not isinstance(settings, CatalogConnectionSettings):
        raise TypeError("settings must be CatalogConnectionSettings")
    if settings.backend == "hive":
        connection_uri = settings.hive_metastore_uri
    else:
        if settings.rest_uri is None:
            raise ValueError("REST settings require rest_uri")
        connection_uri = settings.rest_uri
    return CatalogBackendBinding(
        backend=settings.backend,
        catalog_name=settings.catalog_name,
        connection_uri=connection_uri,
        warehouse_uri=settings.warehouse_uri,
        s3_endpoint=settings.s3_endpoint,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--live-rest",
        action="store_true",
        help=(
            "Connect to a live REST catalog and record namespace count "
            "(requires Polaris bootstrap)."
        ),
    )
    args = parser.parse_args()

    identity = get_runtime_identity()
    base_env = dict(os.environ)
    hive_settings = load_catalog_settings({**base_env, "ICEBERG_CATALOG_BACKEND": "hive"})
    rest_env = {**base_env, "ICEBERG_CATALOG_BACKEND": "rest"}
    if not rest_env.get("ICEBERG_REST_URI"):
        rest_env["ICEBERG_REST_URI"] = "http://localhost:8181/api/catalog"
    rest_settings = load_catalog_settings(rest_env)

    live_count: int | None = None
    if args.live_rest:
        from ingestion.catalog_boundary import build_catalog

        catalog = build_catalog(rest_settings)
        live_count = count_rest_namespaces(catalog)

    proof = build_catalog_interoperability_proof(
        product_id=identity.product_id,
        runtime_version=identity.runtime_version,
        environment=identity.environment,
        hive_binding=_binding_from_settings(hive_settings),
        rest_binding=_binding_from_settings(rest_settings),
        live_rest_namespace_count=live_count,
    )
    sys.stdout.write(json.dumps(proof.model_dump(mode="json"), sort_keys=True, indent=2))
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
