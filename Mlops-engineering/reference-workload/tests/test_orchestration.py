from datetime import UTC, datetime
from pathlib import Path

import pytest
from dagster import Definitions, build_schedule_context, build_sensor_context

from charging_forecast.contract import sha256_file
from charging_forecast.monitoring import SCHEMA_VERSION, retraining_decision, write_json
from charging_forecast.orchestration import (
    Settings,
    TrainingConfig,
    _identity,
    _require_training_inputs,
    build_definitions,
)


@pytest.fixture()
def settings(tiny_release, tmp_path):
    release, cfg = tiny_release
    releases = tmp_path / "models"
    manifest = releases / "model-test" / "manifest.json"
    write_json(manifest, {"mlflow_model_version": 1, "source_run_id": "run-test"})
    write_json(
        releases / "pinned.json",
        {"model_release_id": "model-test", "manifest_sha256": sha256_file(manifest)},
    )
    return Settings(
        tmp_path,
        dataset_config=Path(cfg["_config_path"]),
        dataset_release=release,
        model_releases=releases,
    )


def test_schedules_use_tick_dates_and_skip_unavailable_release(settings):
    definitions = build_definitions(settings)
    Definitions.validate_loadable(definitions)
    daily = definitions.resolve_schedule_def("batch_scoring_schedule")
    monitor = definitions.resolve_schedule_def("forecast_monitor_schedule")
    monthly = definitions.resolve_schedule_def("monthly_retraining_schedule")
    assert daily.execution_timezone == monitor.execution_timezone == "Europe/Berlin"
    assert daily.cron_schedule == "0 6 * * *"
    assert monthly.cron_schedule == "15 5 1 * *"

    same_day = datetime.fromisoformat("2025-03-19T06:00:00+01:00")
    scoring = daily.evaluate_tick(build_schedule_context(scheduled_execution_time=same_day))
    assert scoring.run_requests[0].run_key == "2025-03-19"
    assert scoring.run_requests[0].run_config["ops"]["batch_forecast"]["config"] == {
        "issue_date": "2025-03-19"
    }

    tick = datetime.fromisoformat("2025-03-21T04:30:00+01:00")
    monitoring = monitor.evaluate_tick(build_schedule_context(scheduled_execution_time=tick))
    assert monitoring.run_requests[0].run_config["ops"]["forecast_monitor"]["config"] == {
        "issue_date": "2025-03-19",
        "as_of": "2025-03-21T03:30:00+00:00",
    }
    outside = daily.evaluate_tick(build_schedule_context(scheduled_execution_time=tick))
    assert not outside.run_requests
    assert "outside" in outside.skip_message

    early = monthly.evaluate_tick(
        build_schedule_context(scheduled_execution_time=datetime(2025, 3, 1, 5, tzinfo=UTC))
    )
    assert not early.run_requests
    assert "newer" in early.skip_message
    eligible = monthly.evaluate_tick(
        build_schedule_context(scheduled_execution_time=datetime(2025, 4, 1, 5, tzinfo=UTC))
    )
    assert eligible.run_requests[0].tags["training_trigger"] == "calendar"
    assert eligible.run_requests[0].run_key == "2025-04"


def test_sensor_deduplicates_matching_decision_and_rejects_invalid_inputs(settings):
    build = build_definitions(settings)
    sensor = build.resolve_sensor_def("retraining_decision_sensor")
    identity = _identity(settings)
    inbox = settings.path(settings.state) / "decisions"
    report = {
        "schema_version": SCHEMA_VERSION,
        "kind": "monitor-window",
        "issue_date": "2025-03-19",
        "as_of": "2025-03-21T02:00:00+00:00",
        "model_release_id": "model-test",
        "model_manifest_sha256": identity["pin_manifest_sha256"],
        "data_manifest_sha256": identity["data_manifest_sha256"],
        "signals": {"residual.mae_kwh": {"breached": True}},
    }
    report["decision"] = retraining_decision(report)
    write_json(inbox / "monitor-a.json", report)
    write_json(inbox / "monitor-b.json", report)
    with (inbox / "monitor-invalid.json").open("w") as handle:
        handle.write("invalid JSON")
    stale = {**report, "data_manifest_sha256": "old-dataset"}
    stale["decision"] = retraining_decision(stale)
    write_json(inbox / "monitor-old.json", stale)
    forged = {
        **report,
        "decision": {**report["decision"], "decision_id": "forged"},
    }
    write_json(inbox / "monitor-forged.json", forged)
    held = {**report, "signals": {"weather.fcst_temperature_c.missing": {"breached": True}}}
    held["decision"] = retraining_decision(held)
    write_json(inbox / "monitor-held.json", held)

    tick = sensor.evaluate_tick(build_sensor_context())
    assert len(tick.run_requests) == 1
    run = tick.run_requests[0]
    assert run.run_key == report["decision"]["decision_id"]
    config = run.run_config["ops"]["candidate_model"]["config"]
    assert config["trigger"] == "monitor"
    assert config["pin_manifest_sha256"] == identity["pin_manifest_sha256"]

    (inbox / "monitor-a.json").unlink()
    (inbox / "monitor-b.json").unlink()
    assert not sensor.evaluate_tick(build_sensor_context()).run_requests


def test_worker_rejects_lookahead_and_a_stale_pin_before_running_cli(settings):
    actual = _identity(settings)
    request = {
        "trigger": "monitor",
        "trigger_id": "abc",
        "as_of": "2025-03-21T23:00:00+00:00",
        "data_manifest_sha256": actual["data_manifest_sha256"],
        "pin_manifest_sha256": actual["pin_manifest_sha256"],
    }
    with pytest.raises(ValueError, match="unavailable"):
        _require_training_inputs(settings, actual, TrainingConfig(**request))
    with pytest.raises(ValueError, match="superseded"):
        _require_training_inputs(
            settings,
            actual,
            TrainingConfig(**{**request, "pin_manifest_sha256": "previous"}),
        )
