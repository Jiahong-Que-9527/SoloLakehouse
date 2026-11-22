# M06 · Batch scoring and online serving

<!-- [魏征·2026-11-21] Initialize stage planning. -->

**Status:** accepted (2026-11-22) · [Roadmap](../README.md) · [Acceptance record](evidence/m06-acceptance.md)

Deliver predictions two ways: a scheduled batch score with versioned output, and an HTTP API serving the pinned model with contract tests and shadow comparison.

## Deliverables

- The `serving` package: a batch scoring job that writes the predictions table (model_version, issue time, target windows) idempotently per issue time.
- A FastAPI service (mirroring the [G02 application shape](../../gcp/02-energy-analytics-api/README.md)) that loads the pinned release, reports its model version in every response, validates requests and enforces a latency budget.
- Contract tests over synthetic requests, including invalid-input behavior, mirroring the G02 test shapes.
- The shadow-comparison report format: candidate and pinned score the same requests side by side, offline.

## Acceptance

1. The same request with the same model version returns the same prediction; responses trace to the model release manifest and commit.
2. Rerunning batch scoring for an already-scored issue time replaces nothing silently: idempotence is verified with row counts and checksums.
3. A bounded load check records p95 latency and error behavior, mirroring the G02 guard discipline.

A Cloud Run deployment of this service is a separate variant requiring the owner's cost-gate approval; no acceptance here depends on it.
