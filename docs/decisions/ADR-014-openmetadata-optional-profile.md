# ADR-014: OpenMetadata as optional compose profile

**Status:** Accepted  
**Date:** 2026-03

**Amendment (v2.5 baseline, 2026-04):** OpenMetadata (and Superset) are merged into the **default** `Makefile` `COMPOSE_STACK`, so `make up` starts them without a Compose profile or `make up-openmetadata`. The sections below record the original “optional overlay” intent; operator commands in the **Decision** bullet list are **obsolete** for current main.

## Context

v3 planning explicitly avoids **forcing** a unified enterprise catalog (see [roadmap](../roadmap.md)). Teams still want a **reference** deployment of a data catalog UI that can ingest metadata from Trino.

## Decision

Ship **OpenMetadata 1.5.x** (Collate images) as an **optional** Docker Compose overlay:

- File: `docker/docker-compose.openmetadata.yml` (merged with the main compose file)
- Profile: `openmetadata` (does not start with default `make up`)
- Target command: `make up-openmetadata`
- Configuration: `docker/openmetadata/openmetadata.env` (derived from upstream defaults; `DB_HOST` / `ELASTICSEARCH_HOST` point at `om-mysql` / `om-elasticsearch`)
- Pipeline service client **disabled** in env (`PIPELINE_SERVICE_CLIENT_ENABLED=false`) so Airflow is not required for the baseline demo

## Rationale

- Keeps default stack lighter for laptops and CI
- Demonstrates catalog + discovery next to Trino and Iceberg
- Preserves v3 scope guardrails: optional catalog, not a migration mandate

## Consequences

- Operators add a Trino connection in the OpenMetadata UI (host `trino`, port `8080`, catalogs `hive` / `iceberg`)
- **Current main:** `scripts/verify-setup.py` always runs OpenMetadata (and Superset) checks as part of `make verify` (no env-gated skip).

## Related

- [ADR-012](ADR-012-v3-data-governance-catalog-strategy.md)
