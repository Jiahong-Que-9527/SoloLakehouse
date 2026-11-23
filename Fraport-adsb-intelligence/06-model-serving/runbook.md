# EDDF serving monitoring and rollback

The local container serves one release for its lifetime. Keep the current
known-good release directory, its pinned manifest SHA-256, the serving image
ID and the expected response for a fixed probe request together. The model
response exposes the loaded release ID, registry version, training commit
and artifact SHA-256.

## Monitor the local service

Use the loopback port from the [local startup instructions](README.md#run-locally).

```bash
curl -fsS http://127.0.0.1:8080/health
curl -fsS http://127.0.0.1:8080/v1/model
curl -fsS http://127.0.0.1:8080/metrics
```

`eddf_prediction_requests_total` counts `POST /v1/predict` responses by status
class. Watch 4xx separately for client contract problems and 5xx for service
errors. `eddf_prediction_request_duration_seconds` is a histogram of request
handling time in the application. Its count is the total number of observed
prediction requests. Health, model metadata and scrapes are outside these
metrics. `eddf_serving_model_info` identifies the release in the process
being scraped. Counters and buckets reset when a container is replaced.

For an error, match the `X-Request-Id` response header to the structured log
and check the release ID before debugging the request or changing the pin.
Use these signals to verify rollbacks locally. Production alert thresholds
and scrape configuration require deployment evidence.

## Verify a release switch and roll back

1. Record `/v1/model` and the expected HTTP response for the fixed request in
   the [API example](README.md#run-locally) with the known-good release. Keep
   its verified artifact, pin and serving image available. Request IDs can
   differ between calls.
2. Start the trial on a separate loopback port. Use the same serving image,
   mount the trial release directory read-only, and set `MODEL_MANIFEST_SHA256`
   to the trial's separately verified digest. Check `/health` and `/v1/model`,
   then send the fixed request. A startup error, wrong lineage or unexpected
   prediction is a reason to restore the known-good pin.
3. Restore by creating a fresh container with the known-good image, release
   directory and digest on the intended loopback port. Stop the affected
   trial instance to release its port if necessary. Repeat the probe and
   compare the prior lineage and prediction exactly. Check that `/metrics`
   identifies the restored release and counts the probe.

If the known-good container stays running on another local port during the
trial, retain it while verifying the restored instance. The local procedure
tests version recovery. A cloud revision traffic switch needs its own drill.

## Local verification

The same non-root image ran three consecutive network-isolated containers.
The known-good version 1 scored the fixed input at **260.686983636 seconds**.
The trial pinned an intentionally different synthetic model and returned
**900 seconds**. Restoring the version 1 manifest reproduced the initial
HTTP response body byte for byte, including the release lineage. The trial
version `99` was a local fixture and has no MLflow registry entry.

For each container, one successful request and one invalid request produced
one 2xx count, one 4xx count and two latency observations. The model metric
identified the active release. The unit test exercised 5xx using a
non-finite model output. All drill containers were removed after verification.

- Service code `11b5d8505d103ae83de5ef632d27f313425b5b29`
- Local image ID `sha256:5cd04b191417ee1e7a22d707ea5207295be5b7d6bb1d7ffb1eedfe0b8f9d4ad8`
