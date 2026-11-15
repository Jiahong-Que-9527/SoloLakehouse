# Google Cloud project roadmap

<!-- [房玄龄·2026-11-15] Record the platform projects, milestones and acceptance criteria. -->

Use a single German electricity-load dataset to practice batch delivery, API access,
event processing and governance. The aviation project provides a separate workload
for model training and serving. The milestones below are planned.

## Projects

- [European Energy Pipeline](european-energy-pipeline/README.md) owns the batch pipeline,
  the BigQuery data product and its release checks.
- [Energy Data API](energy-data-api/README.md) exposes approved indicators through a
  read-only interface.
- [Energy Event Pipeline](energy-event-pipeline/README.md) uses synthetic corrections
  to test event handling and recovery against an isolated BigQuery target.
- The aviation model delivery path connects [Taxi-in Prediction](../Fraport-adsb-intelligence/05-taxi-in-prediction/README.md)
  and [Model Serving Integration](../Fraport-adsb-intelligence/06-model-serving/README.md).

## Milestones

1. **G01 · Deploy a batch pipeline.** Start with one week of SMARD actual total
   load. Record the source, unit, interval and source time zone. Normalize interval
   keys to UTC and test the local-time transition. Use a Cloud Run Job and retain
   source inputs in Cloud Storage. Publish one queryable BigQuery table. Run the
   same window twice and compare the keys, row count and query result. After
   the first test deployment, reproduce it through GitHub Actions using
   Terraform and a federated deployment identity. Capture the source revision,
   deployment record, job run ID and observed cost.
2. **G02 · Expose a read-only API.** Read a date-bounded metric from an approved
   BigQuery view. Test an allowed request, a denied request and request tracing.
3. **G03 · Process corrections and recover from failures.** Send duplicate,
   out-of-order and failing synthetic messages through Pub/Sub. Check the final
   table and record one dead-letter recovery.
4. **G04 · Publish with governance.** Use versioned schema and quality rules in
   the batch pipeline. Record the release ID, source window, checksum, code
   revision and validation result. Show that an incompatible input stops
   publication, the API identity can only read the approved view, and a query
   result can be traced to its release and source batch. Verify catalog or lineage
   evidence when configured.
5. **G05 · Deliver a versioned aviation model.** Start with the flagship's local
   baseline. Then plan Vertex AI training and model registration, and a Cloud Run
   service that loads a pinned model version. Trace a synthetic prediction back
   to the model, evaluation and training-data release. Exercise rollback to a
   prior model version. Report ADS-B taxi-in proxy-label coverage separately
   from airport-verified labels.
6. **G06 · Reuse deployment configuration.** Once two workloads have been
   deployed, extract repeated Terraform, GitHub Actions and identity setup into
   the [project template](../project-template/README.md). Validate reuse by
   deploying the second workload into its own test environment and recording
   the result and observed cost.

## Project handoffs

The batch pipeline publishes a versioned schema and an approved view. The API
can seed a fixture into its own test environment and use the approved batch
release when testing integration. The event project shares the metric contract
and writes to its own target. A repository fork can validate each project with
its own fixture. Cloud deployment uses the operator's own GCP environment.

OpenSky Data Ingestion is the first public SoloLakehouse delivery. The first
GCP milestone is the bounded G01 run described above.

[SMARD source documentation](https://www.smard.de/home/ueber-smard) ·
[Cloud Run Jobs](https://docs.cloud.google.com/run/docs/execute/jobs) ·
[Identity federation for deployment pipelines](https://docs.cloud.google.com/iam/docs/workload-identity-federation-with-deployment-pipelines)
