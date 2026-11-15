# European Energy Pipeline

<!-- [Codex · 2026-11-13] Initial project directory. -->
<!-- [Codex · 2026-11-13] Project brief. -->
<!-- [房玄龄·2026-11-15] Define independent platform projects and planned acceptance. -->

**G01 · Planned** · [Google Cloud roadmap](../README.md) · [Design](docs/design.md)

Deliver a repeatable batch pipeline for German electricity-market data. Start with one week of SMARD actual total load and publish a queryable BigQuery table.

## Technical scope

Python, Cloud Storage, BigQuery, Cloud Run Jobs, Terraform and GitHub Actions.

## Input and output

- **Input.** The fixed SMARD exports in [fixtures](fixtures/README.md): one week of German actual total load, plus the 2026-10-25 local-time change. Quarter-hour energy in MWh, Europe/Berlin.
- **Output.** A normalized metric table and a versioned release record with the source window, input checksum, code revision and quality results. G02 and G04 can consume that release.

## Acceptance

1. Test interval boundaries, missing intervals and duplicate keys. Include a fixture around a local-time change.
2. Deploy the job through GitHub Actions using Terraform and a federated deployment identity. Set up a scheduled run in a test environment.
3. Run the same window twice. Compare observation keys, row counts and a reference query. Record the run IDs, validation results and observed cost.

[SMARD data documentation](https://www.smard.de/home/ueber-smard) · [Cloud Run Jobs](https://docs.cloud.google.com/run/docs/execute/jobs)
