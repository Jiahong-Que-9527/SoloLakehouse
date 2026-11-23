# 06 · Model Serving Integration

**Runtime:** Cloud Run.

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

- **M1.** Synthetic request and response contract tests pass locally.
- **M2.** Container runs the chosen model version locally.
- **M3.** Deploy to Cloud Run through CI/CD and verify predictions against
  a fixed test set.
- **M4.** Monitoring, a rollback exercise and a short runbook.

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
