# 06 · Model Serving Integration

**Runtime:** Local Docker for M1–M2. Cloud Run is planned for M3 after the
phase 04 observation-availability check.

Serve the taxi-in model from project 05 through an API. This is the aviation
path of [GCP milestone G05](../../gcp/README.md). This subproject owns the
Frankfurt model contract, version pinning and rollback.

## Scope

- Adopt the Aviation ML Serving request and response contract for the
  `EDDF` model.
- Load a specific model version. Every response reports the model version.
- Validate requests, and return clear errors for invalid input.
- Add structured logs and basic metrics: latency, error rate and request
  volume.
- Define rollback to a previous model release manifest (ADR-005).

## Milestones

- **M1.** Local HTTP contract tests cover request validation, UTC conversion,
  deterministic responses and startup checks for the model pin.
- **M2.** Local Docker serves the pinned model release with its manifest and
  artifact checksums in the prediction lineage.
- **M3.** Deploy to Cloud Run through CI/CD and verify predictions against
  a fixed test set.
- **M4.** Local Prometheus metrics and a pinned-release rollback drill.
  [Monitoring and rollback runbook](runbook.md)

## Acceptance

- The same request and model version give the same prediction.
- Responses can be traced to a model artifact and source commit.
- The rollback procedure is tested.

## Depends on

Project 05 model artifact and the project 04 feature contract. Validate that
serving inputs can be produced at the same observable cutoff used for
training. Contract tests use synthetic requests.

## Outputs

A deployed endpoint, test evidence and a runbook.

## Local API contract

`GET /health` checks that the process started with a verified model.
`GET /v1/model` returns the model release ID, registry version, training
source commit, manifest SHA-256 and model artifact SHA-256. `POST /v1/predict`
accepts one EDDF arrival with point-in-time features from the caller.

`prediction_at` requires an RFC 3339 timestamp with a UTC offset. The service
normalizes it to UTC and derives the model's `prediction_hour_utc` feature.
All six feature keys are required. `null` represents an unavailable approach
speed, altitude, vertical rate or ground speed. Distance and approach age
require finite numeric values. The caller supplies features available at the
prediction cutoff described by [phase 04](../04-aviation-lakehouse/README.md).

A success response includes `airport_icao`, the UTC `prediction_at`,
`predicted_taxi_in_seconds` and the `model` lineage returned by `/v1/model`.
Invalid bodies return HTTP 400 with `code`, `message` and `request_id`.
The service returns `X-Request-Id` for correlation and logs the route, status,
latency and release ID without logging request features.
`GET /metrics` exposes prediction request counts by status class, a latency
histogram and the pinned model identity in Prometheus format.

## Run locally

From this directory, run `uv run --locked python -m unittest -v` for the
synthetic checks. To use the local M4 artifact, set `release_dir` to its
directory and derive the expected checksum from the Git-tracked manifest.
The manifest and model are externally supplied inputs to the image.

```bash
release_dir=/home/bill/slh-data/full-20241101-20261031-geometry-v2/model-releases/geometry-v2-2024-11-m4/release
manifest=../05-taxi-in-prediction/releases/fraport-taxi-in-f3b6b1ebf360fce8.json
pin=$(sha256sum "$manifest" | cut -d ' ' -f 1)
docker build --build-arg "SOURCE_COMMIT=$(git rev-parse HEAD)" -t eddf-taxi-in-serving .
docker run --rm --user "$(id -u):$(id -g)" -p 127.0.0.1:8080:8080 \
  --mount "type=bind,src=$release_dir,dst=/release,readonly" \
  -e "MODEL_MANIFEST_SHA256=$pin" eddf-taxi-in-serving
```

```bash
curl -fsS http://127.0.0.1:8080/v1/model
curl -fsS http://127.0.0.1:8080/v1/predict -H 'Content-Type: application/json' -d '{
  "airport_icao": "EDDF",
  "prediction_at": "2025-04-15T15:30:05+02:00",
  "features": {
    "approach_speed_mps": 70,
    "approach_altitude_m": 150,
    "approach_vertical_rate_mps": -2,
    "approach_distance_m": 1200,
    "ground_speed_mps": 35,
    "approach_age_s": 9
  }
}'
```

The service checks the pinned manifest first, then checks the model bytes
before deserializing them. Use a trusted manifest pin from version control.

## M1–M2 verification

Four synthetic contract tests passed. A network-isolated Docker container
running as UID 10001 loaded release `fraport-taxi-in-f3b6b1ebf360fce8` (MLflow
version 1). Fourteen distinct rows from the four M5 months, including missing
optional features, produced the exact offline scores over HTTP. Repeated
requests returned the same prediction and new request IDs. The smoke check
also verified health, lineage, HTTP 400 on invalid input and startup refusal
under a different manifest pin.

- Service code `09cc2103fe95bf10875297c0f622f3ce67262e07`
- Local Docker image ID `sha256:0f2ad73ef39a6638a3c6ad7a283cfe290f13dc2944c279121d89f72650693b2e`

The smoke inputs use M5 replay features with simulated observation delay.
The archive audit found no measured receipt column in 731 daily Silver
partitions. M3 is pending a measured EDDF input sample and review of its
trigger replay. [Phase 04 availability audit](../04-aviation-lakehouse/README.md#measured-availability-audit)

## Full archive HTTP replay

The replay prepares one request for every row in the four M5 feature
partitions. It verifies the frozen model and the recorded input checksums,
then compares each HTTP response with the offline prediction, UTC timestamp
and pinned model lineage. It also recomputes MAE on the same proxy labels.
All traffic in this check goes to the isolated local service.

From this directory, prepare the fixture with the phase 05 locked environment:

```bash
data_root=/home/bill/slh-data/full-20241101-20261031-geometry-v2
out=$(mktemp -d /tmp/fraport-archive-http.XXXXXX)
OMP_NUM_THREADS=2 OPENBLAS_NUM_THREADS=2 uv run --project ../05-taxi-in-prediction --locked \
  python archive_replay.py prepare \
  --release ../05-taxi-in-prediction/releases/fraport-taxi-in-f3b6b1ebf360fce8.json \
  --evaluation ../05-taxi-in-prediction/reports/seasonal-evaluation.json \
  --model "$data_root/model-releases/geometry-v2-2024-11-m4/release/model.pkl" \
  --features "$data_root/features" --output "$out/fixture.jsonl"
```

With the isolated service running on loopback as in the local startup
instructions, run:

```bash
python3 archive_replay.py verify --fixture "$out/fixture.jsonl" \
  --output "$out/archive-evidence.json"
```

Keep the replay fixture outside Git. It contains individual observations
and proxy labels. The summary contains only aggregate counts and provenance.
The archived feature partitions retain the five-second simulated availability
used in M5. The production availability check still needs measured receipts.

The network-isolated Docker run matched all **65,981 predictions** exactly.
The service recorded 65,981 successful requests and zero 4xx or 5xx responses.
The **51,319** usable proxy labels reproduced the offline MAE of **171.2871 s**.
The replay container was removed after verification.
[Full archive evidence](evidence/archive-http-replay.json)
