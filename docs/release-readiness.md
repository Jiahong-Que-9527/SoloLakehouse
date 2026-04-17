# Release Readiness

Checklist for deciding whether the current branch is ready for tagging.

## 1. Demo flow

| Stage | Check |
|-------|-------|
| Startup | `make up` completes |
| Verification | `make verify` passes all required services |
| Pipeline | `make pipeline` succeeds end-to-end |
| Data | Hive and Iceberg Gold queries return rows |
| ML | MLflow has experiment runs |

## 2. Preconditions

- `.env.example` is up to date
- root docs match runtime behavior (`README.md`, `docs/README.md`, `docs/deployment.md`)
- v2.5 single-track wording is consistent
- history docs updated when milestone status changes

## 3. Self-check command set

```bash
cp .env.example .env
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt -r requirements-dagster.txt
make clean
make up
make verify
make pipeline
make test
make lint
make typecheck
```

## 4. Conclusion template

| Question | Expected |
|----------|----------|
| Does the demo run? | Yes |
| Is it ready to tag? | Yes, after clean-environment self-check passes |
