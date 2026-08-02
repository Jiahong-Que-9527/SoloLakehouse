# Kubernetes Readiness Gate (v2.9 Block F)

v2.9 records whether the repository has the governance and operational evidence
required before starting the v3 runtime migration (ADR-007).

## Command

```bash
make k8s-readiness
```

The gate checks for:

- protected v2.5 Compose baseline
- governed dataset contracts
- promotion, operational, and secrets evidence modules/CLIs
- exit playbook and v3 runtime ADR

Items explicitly **deferred to v3.0** (Helm/Terraform directories) are recorded
as `deferred`, not failures.

## Limitations

Passing this gate means the **evidence plane is ready for v3 planning**, not
that Kubernetes deployment exists yet.
