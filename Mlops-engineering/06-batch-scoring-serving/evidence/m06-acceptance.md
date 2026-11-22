# M06 · Acceptance evidence

All runs on WSL2 Ubuntu, 2026-11-22. Source commit `ae217c6` (the working
tree's HEAD; artifacts generated before the stage commit, per the M04/M05
convention). Runtime: Python 3.13, FastAPI 0.165.0, uvicorn 0.54.0, httpx
0.28.1 (TestClient), scikit-learn 1.9.1, MLflow 3.18.0 (local sqlite). The pinned
release is `model-v001` (manifest `c31adfd530a70d2e…`, MLflow version 1);
the shadow candidate is `model-v002` (MAE 6.377663, registered but not
pinned). Data release `dataset-v001`; feature release
`feat-v1-dataset-v001`. Decisions resolved in the
[delivery plan](../../docs/delivery-plan.md) (M06 entry, 2026-11-22).

## A1 · Same request, same model version, same prediction — traced

- Contract tests: `test_same_request_same_version_same_prediction` (two
  identical POST /v1/predict bodies return identical payloads) over the
  app factory with an injected fake port.
- Real pinned release: the served prediction rows equal the batch scoring
  rows — both paths call the same `_predict_day` scoring core, and the
  batch output is checksum-stable (A2). Every response carries
  `model_release_id`, `mlflow_model_version` and `git_sha` from the pinned
  manifest, so any served number traces to
  `releases/models/model-v001/manifest.json` and commit `ae217c6`.
- Live probes against the real `serve` process (127.0.0.1:8017): GET /health,
  GET /v1/model, POST /v1/predict for all 40 stations (960 rows) and a
  single-station request (24 rows, station filter honored).

## A2 · Batch scoring idempotence — row counts and checksums

- `score-batch --issue-date 2026-12-30` with the pinned model: `960`
  rows (40 stations × 24 target hours of 2026-12-31 UTC), manifest at
  `releases/scores/model-v001/2026-12-30/manifest.json` (committed) with the
  Parquet SHA-256, target window `2026-12-31T00:00:00Z` …
  `2026-12-31T23:00:00Z` and the full model/feature lineage per row.
- Rerun over the same issue time: every step reused, `SCORE-MANIFEST-BYTES-IDENTICAL`
  and `SCORE-PARQUET-BYTES-IDENTICAL` — nothing replaced silently, verified
  by byte comparison, not claimed.
- Collision guard: a tampered score manifest (row count 1) makes the rerun
  fail with `score collision … cut a new model release` and leaves the
  scored release untouched (unit test).
- The scorer refuses a features directory whose `feature_release_id` does
  not carry the pinned feature-contract major (`feat-v1-…`) — unit test
  forges `feat-v9-…` and scores nothing.

## A3 · Shadow comparison (candidate vs pinned, offline)

`shadow-compare --candidate model-v002 --issue-days 2026-12-28,2026-12-29,2026-12-30`
scored the same request set (3 issue days × 40 stations × 24 hours) with
both models side by side:

| issue day | pinned MAE (model-v001) | candidate MAE (model-v002) | mean \|Δ\| | max \|Δ\| | rows |
|---|---|---|---|---|---|
| 2026-12-28 | 5.882313 | 5.921335 | 0.218437 | 2.141553 | 960 |
| 2026-12-29 | 6.278594 | 6.333327 | 0.240148 | 2.651272 | 960 |
| 2026-12-30 | 5.965350 | 6.023234 | 0.247982 | 3.035146 | 960 |
| **overall** | — | — | **0.235522** | **3.035146** | 2,880 |

The candidate trails the pin on every issue day — no promotion case.

- The report records both model identities (release ID, MLflow version,
  manifest SHA-256) and the request-set hash, per
  [the decision](../../docs/delivery-plan.md) (M06 entry).
- Saved at `data/reports/shadow-model-v002-vs-model-v001.json`.

## A4 · Bounded load check — p95 latency and error behavior

`test_bounded_load_check_records_p95_and_error_behavior` drives 52 requests
through the real port (40 valid all-station predictions, 12 invalid:
out-of-range date, malformed date, unknown station) and records:
`n=52, p95=26.3 ms, max=266.1 ms, status counts={'200': 40, '400': 12}`.

- p95 latency `26.3` ms (budget: 2000 ms in CI; the G02 guard discipline —
  parameters, then range, then scoreability — bounds every request).
- Error behavior: all 12 invalid requests answered `400 invalid_parameters` /
  `invalid_range` with the unified `{"code", "message", "request_id"}`
  body; no request reached the model unchecked.
- Contract tests over the fake port cover the error codes exactly:
  `invalid_parameters` (malformed date, unknown station, over-budget
  station list, malformed body), `invalid_range` (outside the materialized
  issue range), `issue_not_scoreable` (422, in-range day with no
  materialized rows).

## Tests and lint

- Full suite: 66 passed (`pytest`, 445.6 s), `ruff check` and
  `ruff format --check` clean.
- New in M06 (`tests/test_serving.py`, 15 tests): pinned-release loading
  and tamper refusal, no-pin refusal, batch idempotence with stable
  checksums, per-row lineage, score collision, foreign feature-release
  refusal, the shadow report, the HTTP contract (health, model lineage,
  predict with lineage and X-Request-Id, station filter, determinism, all
  error codes, malformed body), the no-pin construction refusal, and the
  bounded load check.
- CI: unchanged jobs (test + image) — the training image now also carries
  the serving CLI (`serve`, `score-batch`, `shadow-compare`).
