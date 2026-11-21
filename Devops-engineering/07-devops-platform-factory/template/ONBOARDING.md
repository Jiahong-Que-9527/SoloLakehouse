# Template: Data-file service with the delivery pipeline

The template carries only the delivery pieces proven in D01–D06. It does
not carry a data contract: every service owns its own parser, routes,
fixtures and tests.

## Inputs (replacements.json)

| Placeholder | Meaning | Example |
|---|---|---|
| `SERVICE_NAME` | Python package/directory/image/workflow-safe name | `freshness-service` |
| `PACKAGE` | Python package name under `src/` | `freshness` |
| `DISPLAY_NAME` | Human-readable service title | `Report Freshness Service` |
| `IMAGE_NAME` | GHCR image name | `freshness-service` |
| `WORKFLOW_TITLE` / `WORKFLOW_FILE` | CI workflow name and filename | `Freshness service` / `freshness-service.yml` |
| `WATCH_PATH` | Repo path that triggers the workflow | `Devops-engineering/freshness-service` |
| `CHART_NAME` | Helm release/chart name | `energy-freshness` |
| `PORT` | Container port | `8000` |
| `INPUT_PATH_ENV` / `INPUT_FILE` | Env var and filename for the read-only input | `FRESHNESS_SNAPSHOT_PATH` / `snapshot-fresh.json` |

## Onboarding steps

1. `python3 instantiate.py replacements.json <target-dir>` fills the
   service skeleton, the scoped CI workflow (`.github/workflows/`) and the
   Helm chart.
2. Copy the prepared application (`src/`, `tests/`, `fixtures/`) into the
   service directory. The service owns its contract; the template owns the
   delivery.
3. `uv lock && uv sync --locked`, then `uv run pytest` and
   `uv run ruff check .` locally before opening the PR.
4. Merge to `main`: CI tests, builds, scans and smokes the image, then
   publishes it to GHCR as `sha-<short-sha>`. Flip the new package to
   public once (same as D03).
5. Pin the published digest in the service's `gitops-values.yaml` and
   deploy: `helm install <chart-name> ./chart -n <namespace>
   --create-namespace -f gitops-values.yaml --wait`. The pod carries
   `prometheus.io/*` annotations, so the shared monitoring stack scrapes
   it without further configuration; alert rules are a manual per-service
   decision.
6. Smoke through `kubectl port-forward` and record the onboarding
   transcript (steps, elapsed time, manual edits).

## Upgrades and teardown

- Template upgrades: bump the template in place; consumers pick up changes
  by re-copying the touched delivery files (Dockerfile, workflow, chart).
  Keep the service contract out of the template so upgrades never touch it.
- Service releases: change the pinned digest in `gitops-values.yaml` and
  re-run `helm upgrade`.
- Teardown: `helm uninstall <chart-name> -n <namespace>`, delete the
  namespace, and record the residuals (GHCR package and its versions, the
  workflow file, the service directory). GHCR package deletion is a manual
  registry action.
