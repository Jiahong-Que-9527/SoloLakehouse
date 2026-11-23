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

## Cloud Run deployment and recovery

Start the live pilot after reviewing a measured phase 04 availability audit.
Use an approved project, region and runtime service account. Keep the
approved model artifact and manifest in the versioned release store per
ADR-005. Publish the prepared image to a private repository and use its
remote `@sha256:...` reference as `IMAGE_URI`. The local image ID identifies
the rehearsal. The registry digest identifies the artifact Cloud Run pulls.

For the manual GitHub workflow, commit the reviewed aggregate audit to
`04-aviation-lakehouse/evidence/availability-measured.json`. Configure
`GCP_PROJECT_ID`, `GCP_WIF_PROVIDER`, `FRAPORT_ARTIFACT_REPOSITORY`,
`FRAPORT_RUN_DEPLOY_SA`, `FRAPORT_RUN_RUNTIME_SA` and `FRAPORT_RUN_INVOKER_SA`.
The deploy identity needs permission to deploy and act as the runtime
identity and to mint an ID token for the invoker. Give the invoker permission
on the service. The verification identity also needs Cloud Logging read
access. The workflow uses WIF credentials and GitHub's `gcp-test` environment.
The packaged runtime loads its model from the image filesystem.

Supply the private Artifact Registry URI ending in
`/eddf-taxi-in@sha256:<digest>` to the workflow. Use `initial` for the first
private service or `candidate` for an existing service. The workflow confirms
the mode against the current service list and uploads the verified revision,
model lineage and request IDs as an artifact. A failed run leaves an
unverified revision for inspection. For candidate mode, normal traffic stays
on the existing revision while the probe runs.

The initial service is private. A later revision can be prepared with
`--no-traffic --tag candidate`, then tested through its tagged URL. Capture
the existing serving revision before changing traffic. Use the settings
below for the small verification workload.

```bash
gcloud run deploy "$SERVICE" --project "$PROJECT" --region "$REGION" \
  --image "$IMAGE_URI" --service-account "$RUNTIME_SERVICE_ACCOUNT" \
  --no-allow-unauthenticated --port 8080 --cpu 1 --memory 1Gi \
  --concurrency 4 --min-instances 0 --max-instances 1 \
  --startup-probe='httpGet.path=/health,httpGet.port=8080,periodSeconds=5,timeoutSeconds=3,failureThreshold=12'
```

From an identity with invocation permission, probe `/health`, `/v1/model`
and `/v1/predict` with an ID token and the fixed synthetic request in the
[local instructions](README.md#run-locally). Verify the manifest and model
hashes, normalized timestamp, and exact prediction before shifting traffic.
Check Cloud Run request status and latency for the revision. Use the
application's release ID and request IDs to correlate logs and predictions.
Record the image digest, revision, model pin and observed cloud usage.

To record the authenticated check from a local operator session, run:

```bash
python3 cloud_acceptance.py --project "$PROJECT" --region "$REGION" \
  --service "$SERVICE" --revision "$REVISION" --image "$IMAGE_URI" \
  --invoker "$INVOKER_SERVICE_ACCOUNT" --output "$out/cloud-acceptance.json"
```

Pass `--tag candidate` to inspect a zero-traffic revision. The probe uses the
base service URL as its token audience and sends the request to the tagged
URL. It checks anonymous denial, exact release lineage and score, Prometheus
identity and latency series, and both request IDs in the revision's Cloud
Logging records. For the active endpoint it checks that the expected revision
has 100% of the traffic. Inspect Cloud Monitoring request counts, errors and
latency for that revision during the pilot and record those observations.

For a subsequent release, move traffic to the verified revision by name.
If the live check fails, restore the recorded previous revision and repeat
the authenticated probe to confirm the previous lineage and score.

```bash
gcloud run services update-traffic "$SERVICE" --project "$PROJECT" --region "$REGION" \
  --to-revisions "$PREVIOUS_REVISION=100"
```

Run `cloud_acceptance.py` for the restored revision and its image digest,
without `--tag`. Provide `--evidence` with the previous release's verified
probe results if its model changed. Preserve the rollout and restoration
records together.

Cloud references: [container deployment](https://docs.cloud.google.com/run/docs/deploying)
· [token audience](https://docs.cloud.google.com/run/docs/authenticating/service-to-service)
· [traffic migration and rollback](https://docs.cloud.google.com/run/docs/rollouts-rollbacks-traffic-migration)
· [Cloud Run monitoring](https://docs.cloud.google.com/run/docs/monitoring).
