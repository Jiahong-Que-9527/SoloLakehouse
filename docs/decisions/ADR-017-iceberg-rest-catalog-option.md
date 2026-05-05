# ADR-017: Iceberg REST Catalog Option

**Status:** Placeholder
**Target version:** v2.7
**Related work:** E15, Block I4

## Context

SoloLakehouse currently uses Hive Metastore as the catalog backend for Iceberg Gold tables. v2.7 needs a documented comparison between Hive Metastore, Iceberg REST Catalog, and AWS Glue so the project can demonstrate catalog portability without replacing the default local stack.

## Decision To Make

Decide whether v2.7 should add an optional Iceberg REST Catalog compose profile, and document when a customer should stay with Hive Metastore versus switch to REST Catalog or a managed catalog such as AWS Glue.

## Evidence Required

- Same Gold Iceberg table readable through the current Hive Metastore path.
- Same or equivalent table readable through the optional REST Catalog path.
- Documented behavior differences for schema evolution, auth, metadata location, and engine compatibility.
- Clear statement that REST Catalog is optional and does not enter the default `make up` stack.

## Alternatives To Compare

- Hive Metastore as the default local/reference catalog.
- Iceberg REST Catalog as the open, engine-neutral upgrade path.
- AWS Glue or equivalent managed catalog for cloud deployments where customer policy allows managed services.

## Follow-Up

Replace this placeholder with a full ADR when v2.7 E15 implementation starts.
