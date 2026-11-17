# Design: European Energy Analytics API

**G02 · Design only.** No application code in this directory yet.

Serve the published energy observations over an authenticated HTTP API. The project proves that a BigQuery table can be exposed with a fixed contract, a denied-by-default identity, and guards against unbounded queries.

The project [brief](../README.md) fixes the first consumer.

## 1. Decisions

| Topic | Decision |
|-------|----------|
| Runtime | Cloud Run Service, FastAPI, one stateless revision |
| Access | Not public. Cloud Run invoker IAM is the v1 gate. An OIDC client map is a later addition. |
| Data | A read-only BigQuery view. The service never reads the raw bucket. |
| First metric | `actual_load_mwh` for `DE`, matching the G01 release. Price and generation mix use the same handler when those metrics exist. |
| Missing metric | A metric with no published release returns a stable `404` and `code=metric_not_published`. |
| Query guard | A required time range, a maximum span, a statement timeout, and a maximum bytes billed. A request past a guard is rejected before the query runs, or the query fails closed. |
| Independence | Tests and deploy use a seeded view. A live G01 release is optional. |
| Identity | Runtime service account has `roles/bigquery.dataViewer` on the view and `roles/bigquery.jobUser` on the project. It has no access to raw tables. |

## 2. Boundary

In scope: the HTTP contract, request validation, the query layer, auth, tests, and one deployed revision.

Out of scope: collecting data, changing a release, streaming, and model scoring. Pagination and response caching are specified and are not part of v1 acceptance.

## 3. Architecture

```text
Caller with invoker permission
            |
            v
Cloud Run Service
  auth -> validate params -> guard -> parameterised query -> JSON
            |
            v
BigQuery view energy_api.metric_observation
```

The view exposes the G01 observation columns plus `release_id`. The seed job for this project creates the view from a fixture table when G01 is not in the same project.

## 4. HTTP contract

| Method and path | Behaviour |
|-----------------|-----------|
| `GET /health` | Process up. Does not query BigQuery. |
| `GET /v1/metrics` | Observations for `metric`, `area`, `from`, `to`. |
| `GET /v1/summary` | Row count, min, max, and unit for the same filter. |
| `GET /openapi.json` | Generated OpenAPI document. |

`GET /v1/prices` and `GET /v1/generation-mix` are aliases of `/v1/metrics` with the metric fixed. Until a release for that metric is loaded, they return `metric_not_published`.

Query parameters:

| Name | Rule |
|------|------|
| `area` | Required. v1 allows `DE`. |
| `metric` | Required on `/v1/metrics`. |
| `from`, `to` | Required, ISO-8601 UTC, `from < to`, span at most 31 days. |
| `release_id` | Optional. Default is the latest passed release. |

Response fields for an observation: `interval_start`, `interval_end`, `area`, `metric`, `value`, `unit`, `release_id`.

Errors use one JSON shape: `code`, `message`, `request_id`. Validation errors are HTTP 400. A range with no rows is HTTP 200 and an empty list. A caller without invoker permission is rejected by Cloud Run and never reaches the application.

Initial guard values, held in config: span 31 days, timeout 15 seconds, maximum bytes billed 1 GB. A request that would exceed them returns HTTP 400 with `code=query_rejected`.

## 5. Behaviour

- Every BigQuery query is parameterised. The request path does not concatenate SQL.
- Each request logs `request_id`, route, metric, release id, byte estimate, and status. It does not log the caller's token.
- The service reads the view as the runtime service account. A test identity that can invoke the service still cannot query the raw G01 tables with that same account.
- An empty fixture window and a populated window are both tested.

## 6. Delivery and cost

GitHub Actions runs pytest against a fake query layer, builds the image, and deploys the revision with Terraform. The runtime min instances stay at zero.

The load check is a short fixed-rate run against the deployed test revision, then stop. It is not a soak test. The report records request count, p50, p95, and error rate, plus the revision and request ids.

## 7. Acceptance

1. Tests cover a valid window, an empty window, a reversed range, an unknown metric, a span over the limit, and a call without invoker permission.
2. After deploy, the runtime identity can query the approved view and receives an access denial on the raw table. Record both results.
3. Run the bounded load check. Report rate, latency, error rate, revision, and request ids.

## 8. Handoff

G04 owns who may be granted invoker and who may read the view. This service assumes that grant already exists. G05 does not call this API for training data; it reads a released table.

<!-- [房玄龄·2026-11-17] Document implementation order and acceptance evidence. -->

[Implementation sequence and evidence](implementation.md)
