# Architecture & Production-Readiness Review — 2026-08-11

## Scope and method

A read-only, external-style review conducted against `main` on 2026-08-11, in
four phases: repository reconnaissance, architecture & production-readiness
review, platform-owner-style prioritization, and execution planning. No code
was changed as part of the review itself. Findings below feed
[Block `K`](../TASKS.md#block-k--reliability-data-correctness-and-recovery-hardening)
in `TASKS.md`, which is the authoritative task list — this document is the
supporting rationale and evidence trail.

## Headline finding

Every long-running core Compose service — `postgres`, `minio`,
`hive-metastore`, `trino`, `dagster-webserver`, `dagster-daemon`, `om-mysql`,
`om-elasticsearch`, `om-migrate`, `superset` — has no `restart:` policy across
any of the four Compose files (`docker/docker-compose.yml`,
`docker-compose.openmetadata.yml`, `docker-compose.superset.yml`,
`docker-compose.polaris.yml`). Docker's default is `"no"`: a container crash
(OOM kill, transient fault) or a host reboot does not self-heal and requires a
manual `make up`. At review time, `docker ps -a` on the runtime host showed
all 14 SLH containers `Exited` — this is the most likely mechanical
explanation, not evidence of an unrelated failure. Only `mlflow`,
`openmetadata-server`, and `ingestion` (Airflow) carry
`restart: unless-stopped`. See `K1`.

## Residual gap in Block `R`

`R1` ("Fix `RUNTIME_VERSION` in `runtime_identity.py` and `.env.example`") is
marked done and did fix those two files. It did not touch
`docker/docker-compose.yml`, whose `RUNTIME_VERSION: ${RUNTIME_VERSION:-slh-v2.5.1}`
default still disagrees with `runtime_identity.py`'s
`DEFAULT_RUNTIME_VERSION = "slh-v2.6.1"`. Any deployment that does not set
`RUNTIME_VERSION` explicitly in `.env` — which is the common case, since
nothing prompts an operator to set it — gets a version stamp on every
governance evidence manifest that depends on which code path resolves the
value first. `runtime_identity.py`'s own comment already names the
consequence: a stale value "silently misattributes audit artifacts to the
wrong runtime." This is directly relevant to Block `G`'s evidence-correctness
acceptance bar, which is why `K2` is recommended before or alongside the
external-validation push rather than after it. See `K2`.

## Data-plane note: Bronze re-ingestion pattern

`ingestion/collectors/ecb_collector.py` fetches the full ECB series
(`startPeriod=1999-01-01`) on every ingestion cycle, and
`BronzeWriter.write()` (`ingestion/bronze_writer.py`) appends it via
`iceberg_io.append_table`. The only guard against same-day duplication is
`_already_ingested_today()`, a non-atomic check-then-act — it does not guard
against every-day accumulation, which is the actual growth pattern here.
`transformations/ecb_bronze_to_silver.py` and `dax_bronze_to_silver.py`
correctly `drop_duplicates(subset=["observation_date"], keep="last")`, so
**Silver and Gold output stay correct** — this is a storage/ops cost, not a
data-correctness incident, and should not be read as one.

Recommended fix (`K3`) is to switch `BronzeWriter.write()` from
`append_table` to `overwrite_table`, *not* to switch to incremental fetch.
The full-history refetch is what lets Bronze catch upstream historical
restatements (central banks do occasionally revise published series) —
incremental fetch would quietly give that property up. `overwrite` keeps the
revalidation behavior while removing the unbounded-growth cost. The Bronze
`rejected_records` side table should stay on `append` (it is meant to
accumulate history, unlike the primary tables).

## Findings summary

Severity below is the platform-owner-prioritization pass, not the raw
architecture-review pass — several items were deliberately re-graded down
after asking "does this matter at the platform's actual current scale and
data value," not just "is this a deviation from a textbook pattern."

| ID | Finding | Priority | Block K task |
|---|---|---|---|
| No restart policy on 10 core services | P0 | `K1` |
| `RUNTIME_VERSION` default mismatch (residual `R1` gap) | P0 | `K2` |
| Bronze full-refetch + `append` → unbounded growth | P1 | `K3` |
| `_already_ingested_today()` TOCTOU race, no Dagster run concurrency limit | P2 | `K4` |
| No disk-capacity observability anywhere | P1 | `K5` |
| No Silver/Gold freshness sensor (Bronze has one, asymmetric) | P1 | `K6` |
| No push-based alerting of any kind | P1 | `K7` |
| No runtime guard against deploying with known weak example passwords | P1 | `K8` |
| Cross-system backup (Postgres/MinIO/OpenMetadata) has no quiesce coordination | P1 | `K9` |
| 2026-05-17 restore drill found OpenMetadata MySQL restore fails; never formally closed | P1 | `K10` |
| Security boundary (loopback + SSH tunnel, no internal TLS/auth) is real but implicit | P2 | `K11` |
| No ADR for the `K1` self-healing level once chosen | P2 | `K12` |
| No ADR for the `K3` Bronze write-semantics decision once made | P2 | `K13` |
| No ADR for the backup consistency model once `K9`/`K10` land | P2 | `K14` |
| `hive-metastore` Dockerfile downloads a JDBC driver with no checksum pin | P2 | `K15` |
| No Iceberg snapshot expiry / Dagster run-history retention | P2 | `K16` |
| `iceberg_schemas.py` schema param is a no-op for already-existing tables | P2 | `K17` |
| `ParquetIOManager` registered but never wired to any asset (dead code); stale `docker/.env` | P3 | `K18` |
| No cross-run statistical drift detection ("in-range but wrong" data) | P3 (deferred, not in Block K) | — |

The last row (statistical drift detection) was considered and explicitly
**not** added to Block `K`: it reads as a generic lakehouse best-practice
reflex rather than a risk grounded in this platform's actual data
characteristics (a central-bank policy rate and a static bundled CSV are both
low-noise, low-drift sources in practice). Revisit only if an actual
in-range-but-wrong data incident occurs.

## What the review confirmed is already solid — do not disturb

- Iceberg's atomic commit semantics (`append`/`overwrite` are single-commit)
  — no partial-write corruption path was found anywhere in the pipeline.
- The three-source lineage join
  (`governance/lineage.py::LineageEvidenceJoiner`) requiring the Dagster
  run's materialized `iceberg_snapshot_id` to equal Iceberg's live current
  snapshot — the strongest correctness check in the evidence plane, and the
  reason Block `J`'s `J4` (causal snapshot binding) is worth keeping exactly
  as built.
- The Bronze `rejected_records` side-table pattern — one bad record does not
  block the rest of a batch.
- Loopback-only port binding, applied consistently across all four Compose
  files (main, OpenMetadata, Superset, Polaris), including the
  `openmetadata-server` comment explicitly telling operators to use an SSH
  tunnel rather than exposing the admin UI.
- The `compose-demo` CI job, which actually brings up the full stack and runs
  a real Dagster job rather than stopping at unit tests — stronger CI signal
  than most projects this size carry.
- The dual-layer retry on the ECB collector (3 attempts + 2s backoff at the
  collector level, plus a 3-retry `RetryPolicy` at the Dagster asset level) —
  a proportionate, already-correct response to "network interruption," one of
  the more likely real failure modes.

## Explicit non-goals for Block K

Kubernetes, Kafka, Service Mesh, Vault, multi-region/HA, GitOps, complex
RBAC, custom operators, a full Prometheus/Grafana stack. These match this
repository's own ADR-007 (K8s), ADR-009 (managed secrets), and ADR-015
(Prometheus/Grafana) deferrals to v3.0 — Block `K` does not argue for
accelerating any of them, since none solve a problem this review found actual
evidence for at the platform's current single-operator, single-host scale.

## One pattern worth a deliberate pause

ADR-017, ADR-018, ADR-021, ADR-022, and ADR-023 — and the modules they
document (`governance/k8s_readiness.py`, `sovereignty.py`,
`interoperability.py`, `promotion.py`, `secrets_discipline.py`) — were all
authored on **2026-08-02**, nine days before this review. Each is a static,
self-referential evidence generator: it checks its own preconditions and
produces a SHA-256-signed report, without external verification or runtime
enforcement (`policy_hooks.py`'s `enforcement_mode` is hard-coded
`"metadata_only"`). That is a legitimate, proportionate governance pattern at
this scale on its own — the review is not recommending removal of any of
these five modules, several of which (`contracts.py`, `quality.py`) are
genuinely load-bearing in the write path. The concentration of five
similarly-shaped modules landing in a single day is worth naming explicitly,
though: before adding a sixth module in the same shape, it is worth checking
that a specific failure scenario is driving it, rather than a general sense
that `governance/` should keep growing.

## Reference

Full findings with file:line evidence citations, Mermaid architecture and
dependency-graph diagrams, the six-workstream breakdown, and the five-week
execution schedule behind Block `K` were produced during the reviewing
session and are kept in the owner's personal planning notes (not part of this
repository). This document carries the subset that is operationally binding
here — what is in Block `K`, why, and what was deliberately left out.
