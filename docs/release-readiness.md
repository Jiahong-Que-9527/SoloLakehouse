# Release readiness (demo assessment)

Whether the **bundled demo** runs end-to-end and whether a **tagged release** is reasonable to publish.

## 1. Demo flow

| Stage | Check |
|-------|--------|
| Entry | `make pipeline` runs Dagster default path; `make pipeline PIPELINE_MODE=v1` keeps legacy compatibility |
| DAX sample | `data/sample/dax_daily_sample.csv` present; columns match `DAXDailyRecord` |
| Paths | Bronze → Silver → Gold Parquet paths align in both Dagster and legacy execution paths |
| Iceberg | Trino exposes `iceberg` catalog and `iceberg.gold.ecb_dax_features_iceberg` is queryable |
| ML | `run_experiment_set` / evaluate flow matches training scripts |

**External:** ECB SDW API (public, no key); **Docker** for services; **network** for images and ECB.

**Minor:** If `evaluate.py` docstring mentions runs not implemented, it does not block “pipeline completes” as long as the configured runs execute.

## 2. Preconditions for “ready”

- License and `.gitignore` (e.g. `.env` ignored)
- Docs: root `README`, [quickstart.md](quickstart.md), [deployment.md](deployment.md), [architecture.md](architecture.md), ADRs
- `.env.example` and consistent port/env usage
- `make up` → `make verify` → `make pipeline` (v2 default) → `make pipeline PIPELINE_MODE=v1` (compatibility) → `make test` documented and working in a clean environment
- `.venv`-backed `make` commands remain aligned with the installed project dependencies

## 3. Pre-release self-check

```bash
git clone <repository-url>
cd SoloLakehouse
cp .env.example .env
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
make up
make verify
make verify-openmetadata   # optional, when the OpenMetadata profile is enabled
make pipeline
make pipeline PIPELINE_MODE=v1
make test
```

If default ports conflict, set overrides in `.env` and repeat `make up`.

## 4. Conclusion template

| Question | Expected |
|----------|----------|
| Does the demo run? | Yes, with prerequisites met |
| Ready to tag? | After the self-check on a clean machine / CI |

Re-run before each release; environments differ (ports, network, ECB availability).
