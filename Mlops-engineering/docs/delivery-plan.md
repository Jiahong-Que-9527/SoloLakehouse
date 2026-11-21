# Delivery plan

<!-- [魏征·2026-11-21] Initialize ML engineering delivery planning. -->

## Intended outcome

Given only a fresh checkout and a seed, an engineer can regenerate the synthetic charging dataset, rebuild point-in-time features, retrain the model to the same metrics, publish a model release manifest, score the next day in batch, serve the pinned model over HTTP, watch drift alerts fire under an injected regime change, retrain through the orchestrator, and onboard a second model from the extracted template. The first portfolio checkpoint is M01–M04 with a reproducible dataset release, a leakage-tested feature pipeline, a committed baseline report and a model that beats the seasonal baseline on held-out folds or documents why it does not.

## Sequence and handoffs

- **Checkpoint 1 · Data and model foundations.** M01 freezes the task contract and ships the seeded generator with dataset validation. M02 turns the availability table into tested code. M03 fixes the backtest protocol and metric suite before any model exists. M04 adds the supervised model with full MLflow lineage. Each stage consumes the previous stage's release ID.
- **Checkpoint 2 · Production pipeline.** M05 wraps the same steps into one idempotent CLI, containers it, registers the model and publishes a release manifest. M06 adds batch scoring and an HTTP service that pins a model version and supports shadow comparison.
- **Checkpoint 3 · Operate, orchestrate and reuse.** M07 wires residual and drift monitors into alerting and drills an injected regime change end to end. M08 hands scheduling and triggered retraining to Dagster, wrapping the same CLI steps. M09 extracts the stable pieces into a template and onboards a second model with it.

## Working loop

Every stage is picked up the same way, so any agent can continue from any point:

1. **Resolve the stage's open decision first.** Find the stage's entry under "Decisions to resolve by phase", agree it with the owner where the decision needs one, and record the resolution and date in that entry before writing code.
2. **Implement under `reference-workload/`.** One Python 3.12 package managed with uv, pytest and Ruff, following the repository's established project conventions. Synthetic inputs only; never regenerate a released dataset with a different seed.
3. **Run the stage's acceptance checks.** Each stage README lists them; failures are recorded, not smoothed over.
4. **Record evidence per the [evidence guide](evidence-guide.md)** and link it from the stage README, then move the stage's status from planned to accepted.
5. **Update this plan.** Constraints discovered during the stage become recorded decisions here, not tribal knowledge.

The project-scoped CI workflow (pytest and Ruff, mirroring the energy project's workflow) is created with M01 and extended with the training-image build at M05.

## Decisions and rationale

- **Synthetic domain, self-contained inputs.** The charging network is generated, not imported. No other project's data or schedule can block this one, injected drift is controllable, and a fresh checkout reproduces everything. A pinned Gold release from another track may be consumed later as an explicitly marked variant.
- **One workload, one source tree.** All packages live under `reference-workload/`. Stage directories hold designs and evidence only, so delivery behavior changes stay observable against a stable code layout.
- **CLI first, Dagster on top.** Every pipeline step is a CLI command with a stable interface (owner decision 2026-11-21). Dagster (M08) wraps the same commands as assets and jobs instead of replacing them; a step must run identically with or without the orchestrator.
- **MLflow per ADR-005.** Tracking and registry run locally; registered versions publish model release manifests (release ID, git SHA, data release ID, metrics, artifact checksum) committed to Git. No design may require Vertex AI.
- **Manifest-based releases.** Dataset releases (M01) and model releases (M05) mirror the Gold release pattern of ADR-003: versioned folder, checksums, manifest, release ID. Rollback always means re-pinning the previous manifest and re-verifying.
- **Local-first serving.** M06 serves over HTTP from WSL. A Cloud Run deployment is a separate variant that requires the owner's cost-gate approval; no planned stage depends on it.
- **Scoped automation.** A dedicated workflow scoped to `Mlops-engineering/**` runs this project's checks and, from M05, builds the training image. The workflow vendors nothing from sibling projects.
- **No LLM scope in v1.** Owner decision 2026-11-21. A bounded LLM summary-and-eval extension may be proposed later as its own stage.

## Decisions to resolve by phase

- **M01** — freeze the availability table (calendar, weather forecasts as of issue and lagged demand: yes; realized weather and same-day demand: no), the station and tariff schema, the regime-injection schedule and the dataset release layout. Record generator runtime and output size.
- **M03** — fix the fold plan (rolling origin, fold count, embargo), the metric set (MAE, RMSE, sMAPE, by hour, station and district) and the paired-comparison method before M04 trains anything.
- **M04** — choose the search tool and budget (seeded Optuna or a fixed grid), the early-stopping policy and the run-tag schema (data_release_id, git_sha, fold plan).
- **M05** — fix the registry layout (experiment and model names, stage tags), the manifest location under this project and the container base-image pin.
- **M06** — fix the scoring table schema (model_version, issue time, target windows), the API contract endpoints and the shadow-comparison report format.
- **M07** — derive drift metrics (PSI/KS per feature family, prediction distribution) and thresholds from the M03 baseline, and decide the Prometheus push path (an ADR recorded in this project).
- **M08** — fix the Dagster deployment shape for WSL (daemon plus asset jobs or ephemeral runs), the schedules and the sensor that executes the M07 retraining policy.
- **M09** — select the second workload (station outage or low-balance classification, or a district-aggregate forecaster) and decide which template inputs are genuinely reusable.

## Operating boundary

This is a personal WSL exercise and runs when the host is available. Cloud deployment stays behind the repository cost gate. Raw generated data, MLflow state and model artifacts stay outside Git; manifests, reports and evidence are committed. The scope excludes LLM components by owner decision.
