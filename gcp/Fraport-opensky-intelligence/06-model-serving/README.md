# 06 · Model Serving Integration

**Runtime:** Cloud Run.

Serve the taxi-in model from project 05 through an API. The generic API
contract and versioning work belongs to
[Aviation ML Serving](../../aviation-ml-serving/README.md). This subproject
connects it to the Frankfurt model and its data.

## Scope

- Adopt the Aviation ML Serving request and response contract for the
  `EDDF` model.
- Load a specific model version. Every response reports the model version.
- Validate requests, and return clear errors for invalid input.
- Add structured logs and basic metrics: latency, error rate and request
  volume.
- Define rollback to a previous model version.

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

Project 05 model artifact. Contract tests use synthetic requests.

## Outputs

A deployed endpoint, test evidence and a runbook.
