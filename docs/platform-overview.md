<!-- [房玄龄·2026-11-10] Owner-approved monorepo design and safe repository entrypoints. -->

**Current design route:** the owner selected a single-repository v3 construction plan; hardware is not provisioned. Read the [current design](design/v3/README.md) for future architecture. The retained text below describes its reference/dated operated context, not a newly deployed cluster.

<!-- [房玄龄·2026-11-04] Owner-approved platform positioning; documentation only. -->

# SoloLakehouse: from a personal lakehouse to an operated data platform

## The original question

SoloLakehouse began with a goal: build a lakehouse that one person could understand and operate. That meant following the data from its source through storage, transformation, querying, and model experiments, while keeping the dependencies and resource costs understandable.

Running real workloads made maintenance part of the project. Sources have different calendars and coverage. Jobs can fail while containers stay healthy. A table can be reproducible while its labels remain uncertain. Those experiences shifted attention toward the full responsibility for an output: what produced it, what it means, and how to investigate or recover the workflow.

## Core positioning

**SoloLakehouse is a personally operated data and AI platform built on a lakehouse foundation, with aviation as its primary domain and financial data as a complementary workload.**

The public repository provides the reusable platform foundation and a finance reference implementation. The operated environment reuses those services for separate workloads, including an aviation pipeline maintained in a separate project. [Architecture](architecture.md) distinguishes these implementation boundaries.

The platform is intended to make four responsibilities inspectable:

1. **Data meaning:** sources, versions, quality, missingness, and intended uses are explicit.
2. **Reproduction:** a result can be related to its processing run, table state, features, and experiment artifacts.
3. **Operation:** dependencies, failures, resource limits, and the scope of recovery are documented and checked.
4. **Reuse:** common storage, query, orchestration, and experiment services support different domain workflows.

These are engineering goals; each demonstrated result still needs its own verification record.

## Current workloads

### Aviation: the primary domain

Historical OpenSky observations around Frankfurt Airport are processed into candidate arrival events, taxi-in proxy labels, features, and baseline experiments. This workload brings time and space semantics, observation coverage, uncertain targets, and reproducibility into the same engineering discussion.

The [aviation guide](workloads/aviation.md) records a dated operating snapshot and explains why these outputs are proxies rather than airport ground truth. Aircraft movement data does not establish a shipment, waybill, or live air-cargo transaction workflow.

### Finance: a reference workload and engineering comparison

The public code processes ECB policy rates and FX alongside an EWG equity ETF proxy. Different calendars, source windows, missing prices, freshness checks, and EUR conversion provide useful comparisons for platform methods.

On the operator's 2026-11-04 snapshot, Daily Gold held 6,861 dates, while EWG prices were present on 100 dates. The event-feature job was failing its minimum-row check. Updating Daily Gold and failing the full job can coexist; the snapshot does not establish an uninterrupted complete pipeline or decades of complete joined market data.

## What AI means here

The current platform AI scope is feature preparation, reproducible baseline experiments, evaluation, and model-artifact tracking and reload. Dataset quality and target definitions determine what conclusions those experiments support.

RecordChat is a separate ONE Record knowledge application. It provides complementary work on retrieval, citations, evaluation, release, and recovery, with its own data and lifecycle. No live integration with the lakehouse is claimed here. Supporting further domain AI services is a direction to evaluate, rather than a delivered platform-wide capability.

## Next steps and evidence of progress

The immediate output is a reviewable aviation case covering source and label definitions, architecture, successful processing, quality findings, failure handling, and recovery boundaries. The public workload guide is an entry point; it does not complete that case or make the private aviation pipeline reproducible from a public clone.

Further work should address the most material observed gap, for example source authentication, an independently checked label, recovery, or an independent reproduction. It should state the expected outcome and the evidence needed before changing a pipeline.

A small three-node Proxmox cluster is planned as an infrastructure exploration. Capacity, placement, storage, backup, and recovery choices are unresolved. It is separate from the protected reference Compose runtime and does not by itself deliver high availability or start the Kubernetes migration.

The [2026-11-04 roadmap decision](roadmap.md#d6-personally-operated-platform-and-workload-positioning-decided-2026-11-04) records this scope. Progress is assessed through data fitness, reproducible outputs, checked recovery, and maintainable operation within personal resources.
