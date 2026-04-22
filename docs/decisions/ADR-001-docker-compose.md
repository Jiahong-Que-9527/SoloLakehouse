# ADR-001: Why v1 Uses Docker Compose (Single Node) Instead of Kubernetes

**Status:** Accepted
**Date:** 2024-01

## Context

SoloLakehouse v1 needs a deployment strategy. Two primary candidates were evaluated:
1. Docker Compose — single-node, all services on one machine
2. Kubernetes — container orchestration, supports multi-node scaling

## Decision

v1 uses Docker Compose with a single-node topology.

## Rationale

**1. Data volume does not require distributed compute.**
v1 processes ~2,500 rows of daily financial data (ECB rates + DAX prices). This fits comfortably in memory on a single laptop. Distributing this workload across multiple nodes would add complexity with zero performance benefit.

**2. "One command to start" is a product requirement.**
A critical success criterion for SoloLakehouse v1 is that a recruiter or engineer can clone the repo and have a running platform within 5 minutes. `docker compose up -d` achieves this. Kubernetes requires `kubectl`, `helm`, a local cluster (Minikube/Kind), and significantly more configuration.

**3. Single-node constraints improve architectural discipline.**
When you can't solve problems by adding more machines, you are forced to make better design decisions about data modelling, query efficiency, and schema design. This is a feature, not a limitation.

**4. Kubernetes introduces infrastructure complexity that distracts from Lakehouse logic.**
Kubernetes requires: Ingress controllers, PersistentVolumeClaims, Helm charts or Kustomize, and careful resource limit tuning. In v1, the goal is to demonstrate Lakehouse architecture. Infrastructure management is v3's focus.

## Upgrade Path

v3 will migrate to Kubernetes. The migration is appropriate when:
- Data volumes exceed single-node memory (Trino distributed execution becomes necessary)
- High availability is required (SLA guarantees, no single point of failure)
- Multi-tenant isolation is needed (separate namespaces per team)
- CI/CD automation requires a stable cluster API

The Docker Compose architecture is intentionally designed to map cleanly to Kubernetes: each `docker-compose.yml` service becomes a Kubernetes Deployment, each durable data path becomes a `PersistentVolumeClaim` (or equivalent hostPath/local volume for dev), and the shared network maps to a Kubernetes Service mesh. (The reference stack uses **bind mounts** under `docker/data/` rather than Compose named volumes.)

## Rejected Alternative: Direct Kubernetes from v1

**Rejected.** Starting with Kubernetes in v1 would be over-engineering. The operational overhead would dominate the project, leaving less time to build the Lakehouse pipeline logic that is the actual differentiator.
