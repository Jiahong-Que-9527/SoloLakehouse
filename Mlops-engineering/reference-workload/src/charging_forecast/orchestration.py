"""Local Dagster assets and triggers around the charging-forecast CLI."""

import hashlib
import json
import os
import subprocess
import sys
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import yaml
from dagster import (
    AssetExecutionContext,
    Config,
    Definitions,
    MaterializeResult,
    MetadataValue,
    RetryPolicy,
    RunFailureSensorContext,
    RunRequest,
    ScheduleEvaluationContext,
    SensorEvaluationContext,
    SkipReason,
    asset,
    define_asset_job,
    definitions,
    run_failure_sensor,
    schedule,
    sensor,
)

from .contract import git_commit, load_config, sha256_file
from .eval import valid_issue_range
from .features import feature_release_id
from .monitoring import SCHEMA_VERSION, read_json, retraining_decision, write_json
from .pipeline import read_pin

TIMEZONE = "Europe/Berlin"
RETRY_POLICY = RetryPolicy(max_retries=2, delay=2)


@dataclass(frozen=True)
class Settings:
    workdir: Path
    dataset_config: Path = Path("configs/dataset-v001.yaml")
    dataset_release: Path = Path("data/releases/dataset/v001")
    features: Path = Path("data/features/feat-v1-dataset-v001")
    models: Path = Path("data/models")
    model_releases: Path = Path("releases/models")
    state: Path = Path("data/m08")
    calibration: Path = Path("data/m07/calibration.json")
    pushgateway: str | None = None
    # Pin an explicit clock for a disposable replay; live ticks use wall time.
    replay_clock: str | None = None

    @classmethod
    def from_file(cls, path: Path) -> "Settings":
        values = yaml.safe_load(path.read_text(encoding="utf-8"))
        root = (path.parent / values.pop("workdir")).resolve()
        pushgateway = values.pop("pushgateway", None)
        replay_clock = values.pop("replay_clock", None)
        return cls(
            root,
            pushgateway=pushgateway,
            replay_clock=replay_clock,
            **{key: Path(value) for key, value in values.items()},
        )

    def path(self, path: Path) -> Path:
        return self.workdir / path

    def config(self) -> dict:
        return load_config(self.path(self.dataset_config))


class IssueConfig(Config):
    issue_date: str


class MonitorConfig(IssueConfig):
    as_of: str


class TrainingConfig(Config):
    trigger: str
    trigger_id: str
    as_of: str
    data_manifest_sha256: str
    pin_manifest_sha256: str


def _identity(settings: Settings) -> dict:
    data_path = settings.path(settings.dataset_release) / "manifest.json"
    dataset = read_json(data_path)
    releases = settings.path(settings.model_releases)
    pin = read_pin(releases)
    if pin is None:
        raise ValueError("orchestration requires a pinned model")
    model_path = releases / pin["model_release_id"] / "manifest.json"
    if sha256_file(model_path) != pin["manifest_sha256"]:
        raise ValueError("pinned model manifest checksum changed")
    model = read_json(model_path)
    return {
        "data_release_id": dataset["release_id"],
        "data_manifest_sha256": sha256_file(data_path),
        "pinned_model_release_id": pin["model_release_id"],
        "pin_manifest_sha256": pin["manifest_sha256"],
        "pinned_mlflow_version": model["mlflow_model_version"],
        "pinned_mlflow_run_id": model["source_run_id"],
    }


def _tagged_identity(context: AssetExecutionContext, settings: Settings) -> dict:
    identity = _identity(settings)
    context.instance.add_run_tags(
        context.run_id, {key: str(value) for key, value in identity.items()}
    )
    return identity


def _training_ready(settings: Settings, as_of: datetime) -> bool:
    if as_of.utcoffset() is None:
        raise ValueError("training as_of requires a timezone")
    cfg = settings.config()
    final_hour = datetime.fromisoformat(cfg["window"]["end"])
    available = final_hour + timedelta(hours=1 + int(cfg.get("ingestion_delay_hours", 1)))
    return available <= as_of


def _clock(settings: Settings) -> datetime:
    """Wall time, or the explicit clock a disposable replay pins in settings."""
    if settings.replay_clock is None:
        return datetime.now(UTC)
    moment = datetime.fromisoformat(settings.replay_clock)
    if moment.utcoffset() is None:
        raise ValueError("replay clock requires a timezone")
    return moment


def _issue_request(
    settings: Settings, asset_name: str, issue: date, **config
) -> RunRequest | SkipReason:
    first, last = valid_issue_range(settings.config())
    if not first <= issue <= last:
        return SkipReason(f"issue {issue} is outside the configured dataset range {first}..{last}")
    return RunRequest(
        run_key=str(issue),
        run_config={"ops": {asset_name: {"config": {"issue_date": str(issue), **config}}}},
        tags={"issue_date": str(issue)},
    )


def _training_request(identity: dict, trigger: str, token: str, as_of: datetime) -> RunRequest:
    config = TrainingConfig(
        trigger=trigger,
        trigger_id=token,
        as_of=as_of.isoformat(),
        data_manifest_sha256=identity["data_manifest_sha256"],
        pin_manifest_sha256=identity["pin_manifest_sha256"],
    )
    return RunRequest(
        run_key=token,
        run_config={"ops": {"candidate_model": {"config": config.model_dump()}}},
        tags={"training_trigger": trigger, "trigger_id": token},
    )


def _cli(context: AssetExecutionContext, settings: Settings, command: str, *args, cwd=None) -> None:
    dataset = [
        "--config",
        settings.path(settings.dataset_config),
        "--release",
        settings.path(settings.dataset_release),
        "--features",
        settings.path(settings.features),
    ]
    argv = [sys.executable, "-m", "charging_forecast.cli", command, *map(str, [*dataset, *args])]
    context.log.info(f"Running charging-forecast {command}")
    # Inherit stdout/stderr so Dagster preserves CLI progress and failures.
    subprocess.run(
        argv,
        cwd=cwd or settings.workdir,
        check=True,
        timeout=3600,
        env={**os.environ, "MLFLOW_DISABLE_TELEMETRY": "1"},
    )


@contextmanager
def _lock(state: Path, name: str):
    # On the WSL host, flock releases the lock if the worker exits mid-step.
    import fcntl

    directory = state / "locks"
    directory.mkdir(parents=True, exist_ok=True)
    with (directory / f"{name}.lock").open("a") as handle:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        yield


def _candidate_id(config: TrainingConfig, feature_hash: str, source_commit: str) -> str:
    raw = json.dumps(
        [config.data_manifest_sha256, config.pin_manifest_sha256, feature_hash, source_commit]
    )
    return "model-m08-" + hashlib.sha256(raw.encode()).hexdigest()[:16]


def _decision(report: dict) -> dict:
    if report["kind"] != "monitor-window" or report["schema_version"] != SCHEMA_VERSION:
        raise ValueError("expected an M07 monitor-window report")
    decision = report["decision"]
    reasons = decision["reasons"]
    last_training = reasons.get("calendar", {}).get("last_training")
    expected = retraining_decision(
        report,
        last_training=date.fromisoformat(last_training) if last_training else None,
        manual_reason=reasons.get("manual"),
    )
    if decision != expected:
        raise ValueError("decision contents differ from the M07 policy result")
    return decision


def _require_training_inputs(settings: Settings, identity: dict, config: TrainingConfig) -> str:
    if (
        identity["data_manifest_sha256"] != config.data_manifest_sha256
        or identity["pin_manifest_sha256"] != config.pin_manifest_sha256
    ):
        raise ValueError("training launch references a superseded dataset or pin")
    if not _training_ready(settings, datetime.fromisoformat(config.as_of)):
        raise ValueError("dataset contains labels unavailable at the training decision time")
    release = settings.path(settings.dataset_release)
    marker = read_json(release / "_SUCCESS")
    data_manifest = read_json(release / "manifest.json")
    if (
        marker["release_id"] != identity["data_release_id"]
        or sha256_file(settings.path(settings.dataset_config)) != data_manifest["config_sha256"]
    ):
        raise ValueError("training requires a published dataset matching its config")
    # Use a complete release so M05 will reuse shared features instead of rebuilding them.
    feature_path = settings.path(settings.features) / "manifest.json"
    feature = read_json(feature_path)
    dataset_config = settings.config()
    first, last = valid_issue_range(dataset_config)
    if (
        feature["source_manifest_sha256"] != identity["data_manifest_sha256"]
        or feature["feature_release_id"] != feature_release_id(dataset_config)
        or feature["issue_start"] != str(first)
        or feature["issue_end"] != str(last)
    ):
        raise ValueError("training requires features materialized for the entire dataset")
    return sha256_file(feature_path)


def build_definitions(settings: Settings) -> Definitions:
    state = settings.path(settings.state)
    pin_args = (
        "--models-dir",
        settings.path(settings.models),
        "--releases-dir",
        settings.path(settings.model_releases),
    )
    score_args = (
        "--scores-dir",
        state / "scores",
        "--score-releases-dir",
        state / "score-manifests",
    )

    @asset(retry_policy=RETRY_POLICY)
    def batch_forecast(context: AssetExecutionContext, config: IssueConfig) -> MaterializeResult:
        day = str(date.fromisoformat(config.issue_date))
        context.instance.add_run_tags(context.run_id, {"issue_date": day})
        with _lock(state, f"score-{day}"):
            identity = _tagged_identity(context, settings)
            _cli(context, settings, "score-batch", "--issue-date", day, *pin_args, *score_args)
            path = (
                state
                / "score-manifests"
                / identity["pinned_model_release_id"]
                / day
                / "manifest.json"
            )
            manifest = read_json(path)
            if (
                _identity(settings) != identity
                or manifest["model_release_id"] != identity["pinned_model_release_id"]
            ):
                raise RuntimeError("dataset or pin changed during scoring")
        return MaterializeResult(
            metadata={
                **identity,
                "issue_date": day,
                "cli": "score-batch",
                "manifest": MetadataValue.path(str(path)),
                "manifest_sha256": sha256_file(path),
                "feature_manifest_sha256": manifest["feature_manifest_sha256"],
                "predictions_sha256": manifest["predictions"]["sha256"],
                "rows": manifest["rows"],
            }
        )

    @asset(deps=[batch_forecast], retry_policy=RETRY_POLICY)
    def forecast_monitor(
        context: AssetExecutionContext, config: MonitorConfig
    ) -> MaterializeResult:
        day = str(date.fromisoformat(config.issue_date))
        context.instance.add_run_tags(context.run_id, {"issue_date": day})
        identity = _tagged_identity(context, settings)
        out = state / "decisions" / f"monitor-{day}-{context.run_id}.json"
        args = ["--pushgateway", settings.pushgateway] if settings.pushgateway else []
        # Enqueue the decision only after optional metrics delivery succeeds.
        staging = state / "monitor-reports" / out.name
        _cli(
            context,
            settings,
            "monitor-window",
            "--issue-date",
            day,
            "--as-of",
            config.as_of,
            "--calibration",
            settings.path(settings.calibration),
            "--out",
            staging,
            *pin_args,
            *score_args,
            *args,
        )
        report = read_json(staging)
        if (
            report["model_manifest_sha256"] != identity["pin_manifest_sha256"]
            or report["data_manifest_sha256"] != identity["data_manifest_sha256"]
        ):
            raise RuntimeError("monitor report does not match launch lineage")
        decision = _decision(report)
        write_json(out, report)
        return MaterializeResult(
            metadata={
                **identity,
                "issue_date": day,
                "cli": "monitor-window",
                "decision": decision["action"],
                "decision_id": decision["decision_id"],
                "report": MetadataValue.path(str(out)),
                "score_manifest_sha256": report["score_manifest_sha256"],
            }
        )

    @asset(retry_policy=RETRY_POLICY)
    def candidate_model(
        context: AssetExecutionContext, config: TrainingConfig
    ) -> MaterializeResult:
        releases = state / "candidate-releases"
        tracking_db = state / "mlflow.db"
        with _lock(state, "training"):
            identity = _tagged_identity(context, settings)
            feature_hash = _require_training_inputs(settings, identity, config)
            source_commit = git_commit(settings.path(settings.dataset_release))
            candidate = _candidate_id(config, feature_hash, source_commit)
            _cli(
                context,
                settings,
                "run-pipeline",
                "--model-release-id",
                candidate,
                "--out",
                state / "candidate-reports" / candidate,
                "--models-dir",
                state / "candidate-models",
                "--releases-dir",
                releases,
                "--tracking-uri",
                f"sqlite:///{tracking_db}",
                cwd=state,
            )
            path = releases / candidate / "manifest.json"
            manifest = read_json(path)
            if (
                manifest["data_manifest_sha256"] != identity["data_manifest_sha256"]
                or manifest["feature_manifest_sha256"] != feature_hash
                or manifest["source_commit"] != source_commit
            ):
                raise RuntimeError("candidate manifest references different training inputs")
        return MaterializeResult(
            metadata={
                **identity,
                "cli": "run-pipeline",
                "training_trigger": config.trigger,
                "trigger_id": config.trigger_id,
                "candidate_model_release_id": candidate,
                "mlflow_run_id": manifest["source_run_id"],
                "mlflow_model_version": manifest["mlflow_model_version"],
                "mlflow_tracking_db": MetadataValue.path(str(tracking_db)),
                "feature_manifest_sha256": feature_hash,
                "manifest": MetadataValue.path(str(path)),
                "manifest_sha256": sha256_file(path),
            }
        )

    score_job = define_asset_job("daily_batch_scoring", selection=[batch_forecast])
    monitor_job = define_asset_job("daily_forecast_monitor", selection=[forecast_monitor])
    train_job = define_asset_job("train_candidate", selection=[candidate_model])

    @schedule(job=score_job, cron_schedule="0 6 * * *", execution_timezone=TIMEZONE)
    def batch_scoring_schedule(context: ScheduleEvaluationContext):
        issue = context.scheduled_execution_time.date()
        return _issue_request(settings, "batch_forecast", issue)

    @schedule(job=monitor_job, cron_schedule="30 4 * * *", execution_timezone=TIMEZONE)
    def forecast_monitor_schedule(context: ScheduleEvaluationContext):
        tick = context.scheduled_execution_time
        return _issue_request(
            settings,
            "forecast_monitor",
            tick.date() - timedelta(days=2),
            as_of=tick.astimezone(UTC).isoformat(),
        )

    @schedule(job=train_job, cron_schedule="15 5 1 * *", execution_timezone=TIMEZONE)
    def monthly_retraining_schedule(context: ScheduleEvaluationContext):
        tick = context.scheduled_execution_time
        if not _training_ready(settings, tick):
            return SkipReason("the configured training dataset has labels newer than this tick")
        return _training_request(_identity(settings), "calendar", tick.strftime("%Y-%m"), tick)

    @sensor(job=train_job, minimum_interval_seconds=15)
    def retraining_decision_sensor(context: SensorEvaluationContext):
        paths = sorted((state / "decisions").glob("monitor-*.json"))
        if not paths:
            return SkipReason("no M07 reports in the decision inbox")
        identity = _identity(settings)
        now = _clock(settings)
        requests = {}
        deferred = []
        for path in paths:
            try:
                decision = _decision(read_json(path))
                if (
                    decision["model_manifest_sha256"] != identity["pin_manifest_sha256"]
                    or decision["data_manifest_sha256"] != identity["data_manifest_sha256"]
                ):
                    continue
                as_of = datetime.fromisoformat(decision["as_of"])
                if as_of.utcoffset() is None:
                    raise ValueError("monitor decision as_of requires a timezone")
                if as_of > now:
                    # Live mode waits for wall time; a replay passes it via replay_clock.
                    deferred.append(path.name)
                    continue
                if decision["action"] == "retrain" and _training_ready(settings, now):
                    token = decision["decision_id"]
                    requests[token] = _training_request(identity, "monitor", token, now)
            except (OSError, ValueError, KeyError, TypeError) as exc:
                context.log.warning(f"Rejected report {path.name}: {exc}")
        if requests:
            return list(requests.values())
        reason = "no eligible retraining decision for this dataset and pin"
        if deferred:
            reason += f"; {len(deferred)} deferred until the clock passes their as_of"
        return SkipReason(reason)

    @run_failure_sensor(monitored_jobs=[score_job, monitor_job, train_job])
    def orchestration_failure_sensor(context: RunFailureSensorContext):
        run = context.dagster_run
        event = {
            "run_id": run.run_id,
            "job": run.job_name,
            "issue_date": run.tags.get("issue_date"),
            "training_trigger": run.tags.get("training_trigger"),
            "trigger_id": run.tags.get("trigger_id"),
            "data_release_id": run.tags.get("data_release_id"),
            "pinned_model_release_id": run.tags.get("pinned_model_release_id"),
            "recorded_at": datetime.now(UTC).isoformat(),
            "dagster_run_path": f"/runs/{run.run_id}",
            "message": context.failure_event.message,
        }
        write_json(state / "failures" / f"{run.run_id}.json", event)
        context.log.error(f"Run {run.run_id} failed after retries. Inspect /runs/{run.run_id}")

    return Definitions(
        assets=[batch_forecast, forecast_monitor, candidate_model],
        jobs=[score_job, monitor_job, train_job],
        schedules=[batch_scoring_schedule, forecast_monitor_schedule, monthly_retraining_schedule],
        sensors=[retraining_decision_sensor, orchestration_failure_sensor],
    )


@definitions
def defs():
    config_file = Path(os.environ["CHARGING_FORECAST_ORCHESTRATION_CONFIG"]).resolve()
    return build_definitions(Settings.from_file(config_file))
