# ADR-002: Why Trino Instead of DuckDB as the Query Engine

**Status:** Accepted
**Date:** 2024-01

## Context

v1 needs a SQL engine that can query Parquet files stored in MinIO. Three candidates were evaluated: Trino, DuckDB, and Spark SQL.

## Decision

v1 uses Trino.

## Rationale

**1. Trino demonstrates the standard Lakehouse query architecture.**
The pattern of `Query Engine ↔ Metadata Catalog ↔ Object Storage` is the industry standard for modern Lakehouses (Databricks, AWS EMR, Azure Synapse all follow this pattern). By implementing Trino + Hive Metastore + MinIO, v1 demonstrates understanding of this three-layer decoupling. DuckDB, being embedded, does not expose this architecture.

**2. Trino has higher signal value in Frankfurt FinTech hiring.**
When a recruiter or hiring manager at Deutsche Bank, DWS, or ING sees "Trino" in a portfolio, they associate it with large-scale data platform work. DuckDB, while excellent, is more commonly associated with analytical/data science workflows. SoloLakehouse targets the Platform Engineer market, not the Data Analyst market.

**3. Trino is horizontally scalable; the v1 single-node deployment does not lock us in.**
Adding Trino worker nodes in v3 (Kubernetes) requires minimal configuration changes — just add more worker pods. Replacing DuckDB with a distributed engine would require a fundamentally different architecture.

**4. The Hive Metastore integration itself is a demonstration of platform engineering skill.**
Configuring Trino to use a Hive catalog (metastore.uri, s3.endpoint, path-style-access, auth settings) is non-trivial work that demonstrates hands-on experience with data platform infrastructure.

## DuckDB's Advantages (Acknowledged but Not Adopted)

DuckDB has genuine strengths that are not being dismissed:
- **Faster on single-node, small datasets** — for v1's 2,500 rows, DuckDB would be measurably faster than Trino
- **Zero-infrastructure deployment** — DuckDB is a Python library, no separate service needed
- **Excellent for ad-hoc analytics** — DuckDB's WASM, Parquet native support, and Python integration are best-in-class

If the goal were to build the fastest analytical tool for a data scientist, DuckDB would be the right choice. But SoloLakehouse's goal is to demonstrate platform architecture competence, and Trino better serves that goal.

## Spark SQL

Spark SQL was rejected because full Spark requires significant memory overhead even in local mode. On a single Docker Compose node with limited RAM, running a Spark JVM alongside MinIO, PostgreSQL, Hive Metastore, and MLflow would create resource contention. Spark is a candidate for v2/v3 as a batch processing engine for large-scale transformations.
