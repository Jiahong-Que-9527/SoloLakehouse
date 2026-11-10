# GitOps desired-state design

**Status: design only; hardware not provisioned.**

Own the cluster entrypoint, platform component dependencies and reviewed application/environment releases. Flux owns deployment state; Dagster owns data tasks.

Actual public/encrypted/private configuration boundaries and independent key recovery must be decided before bootstrap. There are no Flux manifests, deployment credentials or automatic prune rules here.

See the [authoritative design](../docs/design/v3/delivery-and-environments.md) and [construction-plan index](../docs/design/v3/README.md).
