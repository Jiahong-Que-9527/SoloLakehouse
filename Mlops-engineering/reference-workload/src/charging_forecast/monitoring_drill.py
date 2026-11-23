"""Replay a tariff shock, check delivered alerts and fit a disposable candidate."""

from __future__ import annotations

import json
import shutil
import subprocess
from contextlib import ExitStack
from datetime import UTC, date, datetime, timedelta
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from threading import Thread
from time import monotonic, sleep
from urllib.request import urlopen

import mlflow
import numpy as np
import yaml

from .contract import build_manifest, git_commit, load_config, sha256_file
from .eval import EMBARGO_DAYS, error_metrics, load_demand, target_hours_us, valid_issue_range
from .features import load_training_features
from .generator import ChargingGenerator
from .monitoring import (
    calibrate,
    evaluate,
    push_metrics,
    retraining_decision,
    write_json,
)
from .pipeline import step_features, step_validate, write_model_artifact
from .serving import PREDICTIONS_NAME, Release, load_pinned_release, score_issue_day
from .training import build_training_data, make_pipeline

GATEWAY = "http://127.0.0.1:19091"
PROMETHEUS = "http://127.0.0.1:19090"
HEALTHY = date(2026, 12, 30)
SHIFTED = date(2026, 11, 15)
HOLDOUT_START = date(2026, 11, 18)
HOLDOUT_END = date(2026, 11, 24)
SHOCK = {
    "date": "2026-10-12",
    "districts": ["D1", "D2", "D3", "D4", "D5", "D6"],
    "surcharge_eur_kwh": 0.45,
    "elasticity": -1.4,
    "ramp_days": 2,
}


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _as_of(day: date) -> datetime:
    return datetime.fromtimestamp(int(target_hours_us(day)[-1]) / 1_000_000, tz=UTC) + timedelta(
        hours=2
    )


def _wait_until(predicate, seconds: float = 30):
    deadline = monotonic() + seconds
    while monotonic() < deadline:
        try:
            result = predicate()
        except OSError:
            result = None
        if result:
            return result
        sleep(0.25)
    raise RuntimeError(f"{predicate.__name__} did not succeed within {seconds:g}s")


def _http_json(url: str) -> dict:
    with urlopen(url, timeout=2) as response:
        return json.load(response)


def _stop(process: subprocess.Popen) -> None:
    process.terminate()
    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait()


def _stack(resources: ExitStack, config: Path, out: Path) -> list[dict]:
    events = []

    class Receiver(BaseHTTPRequestHandler):
        def do_POST(self):
            payload = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            event = {
                "received_at": _now(),
                "status": payload["status"],
                "alerts": [
                    {key: alert[key] for key in ("status", "labels", "startsAt", "endsAt")}
                    for alert in payload["alerts"]
                ],
            }
            with (out / "receiver.jsonl").open("a", encoding="utf-8") as log:
                log.write(json.dumps(event, sort_keys=True) + "\n")
            events.append(event)
            self.send_response(200)
            self.end_headers()

        def log_message(self, *_args):
            pass

    commands = (
        (("pushgateway", "prometheus-pushgateway"), ["--web.listen-address=127.0.0.1:19091"]),
        (
            ("alertmanager", "prometheus-alertmanager"),
            [
                "--web.listen-address=127.0.0.1:19093",
                "--cluster.listen-address=",
                f"--storage.path={out / 'alertmanager'}",
                f"--config.file={config / 'alertmanager.yaml'}",
            ],
        ),
        (
            ("prometheus",),
            [
                "--web.listen-address=127.0.0.1:19090",
                f"--storage.tsdb.path={out / 'prometheus'}",
                f"--config.file={config / 'prometheus.yaml'}",
            ],
        ),
    )
    server = resources.enter_context(HTTPServer(("127.0.0.1", 19876), Receiver))
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    resources.callback(thread.join)
    resources.callback(server.shutdown)
    for aliases, args in commands:
        binary = next((path for name in aliases if (path := shutil.which(name))), None)
        if binary is None:
            raise RuntimeError(f"install {aliases[0]} or add its binary to PATH")
        log = resources.enter_context((out / f"{aliases[0]}.log").open("w", encoding="utf-8"))
        process = subprocess.Popen([binary, *args], stdout=log, stderr=subprocess.STDOUT)
        resources.callback(_stop, process)

    def ready():
        with urlopen(f"{PROMETHEUS}/-/ready", timeout=2) as response:
            return response.status == 200

    _wait_until(ready)
    return events


def _new_dataset(out: Path, config: dict) -> tuple[Path, dict]:
    cfg = {k: v for k, v in config.items() if k != "_config_path"}
    cfg["release_id"] = "dataset-m07-tariff-drill"
    cfg["tariff"] = {**cfg["tariff"], "step": SHOCK}
    cfg_path = out / "tariff-drill.yaml"
    cfg_path.write_text(yaml.safe_dump(cfg, sort_keys=False), encoding="utf-8")
    cfg = load_config(cfg_path)
    release = out / "dataset"
    ChargingGenerator(cfg).generate(release)
    step_validate(release, cfg)
    write_json(release / "manifest.json", build_manifest(release, cfg, git_commit()))
    return release, cfg


def _monitor(
    out: Path,
    pinned: Release,
    release: Path,
    cfg: dict,
    features: Path,
    day: date,
    calibration: dict,
) -> dict:
    score = score_issue_day(
        pinned,
        release,
        cfg,
        features,
        day,
        scores_dir=out / "scores",
        score_releases_dir=out / "score-manifests",
    )
    score_path = out / "scores" / pinned.model_release_id / day.isoformat() / PREDICTIONS_NAME
    report = evaluate(
        pinned,
        release,
        cfg,
        features,
        day,
        calibration,
        score_path,
        score["manifest_path"],
        as_of=_as_of(day),
    )
    report["decision"] = retraining_decision(report)
    write_json(out / f"monitor-{day}.json", report)
    return report


def _fit_candidate(
    out: Path, pinned: Release, release: Path, cfg: dict, features: Path, report: dict
) -> dict:
    as_of = datetime.fromisoformat(report["as_of"])
    last_train = min(
        as_of.date() - timedelta(days=2), HOLDOUT_START - timedelta(days=1 + EMBARGO_DAYS)
    )
    first, _ = valid_issue_range(cfg)
    demand = load_demand(release, cfg)
    training = build_training_data(
        load_training_features(features, first, last_train),
        demand,
        [first + timedelta(days=offset) for offset in range((last_train - first).days + 1)],
    )
    labeled = np.isfinite(training.y)
    params = pinned.manifest["model_config"]
    pipe = make_pipeline(params, max_iter=pinned.manifest["max_iter"], seed=pinned.manifest["seed"])
    pipe.fit(training.X.loc[labeled], training.y[labeled])
    candidate_id = "model-m07-" + report["decision"]["decision_id"][:12]
    artifact, artifact_entry = write_model_artifact(pipe, out / "models", candidate_id)
    trained_at = _now()
    holdout = build_training_data(
        load_training_features(features, HOLDOUT_START, HOLDOUT_END),
        demand,
        [HOLDOUT_START + timedelta(days=i) for i in range((HOLDOUT_END - HOLDOUT_START).days + 1)],
    )
    pinned_metrics = error_metrics(pinned.pipeline.predict(holdout.X), holdout.y)
    candidate_metrics = error_metrics(pipe.predict(holdout.X), holdout.y)

    mlflow.set_tracking_uri(f"sqlite:///{out / 'mlflow.db'}")
    experiment = mlflow.create_experiment(
        "m07-tariff-drift-drill", artifact_location=(out / "mlartifacts").as_uri()
    )
    with mlflow.start_run(experiment_id=experiment, run_name=candidate_id) as run:
        mlflow.log_params({**params, "last_training_issue": str(last_train)})
        mlflow.set_tags(
            {
                "decision_id": report["decision"]["decision_id"],
                "data_manifest_sha256": report["data_manifest_sha256"],
                "feature_manifest_sha256": report["feature_manifest_sha256"],
                "source_commit": git_commit(),
                "pinned_model_release_id": pinned.model_release_id,
                "pinned_model_manifest_sha256": pinned.manifest_sha256,
            }
        )
        mlflow.log_metrics(
            {"pinned_mae_kwh": pinned_metrics["mae"], "candidate_mae_kwh": candidate_metrics["mae"]}
        )
        mlflow.log_artifact(str(artifact))
    candidate = {
        "kind": "drill-candidate",
        "model_release_id": candidate_id,
        "decision_id": report["decision"]["decision_id"],
        "mlflow_run_id": run.info.run_id,
        "data_manifest_sha256": report["data_manifest_sha256"],
        "feature_manifest_sha256": report["feature_manifest_sha256"],
        "pinned_model_manifest_sha256": pinned.manifest_sha256,
        "source_commit": git_commit(),
        "training_issue_end": str(last_train),
        "training_rows": int(labeled.sum()),
        "trained_at": trained_at,
        "artifact": artifact_entry,
        "holdout_issue_start": str(HOLDOUT_START),
        "holdout_issue_end": str(HOLDOUT_END),
        "pinned_metrics": pinned_metrics,
        "candidate_metrics": candidate_metrics,
    }
    write_json(artifact.parent / "manifest.json", candidate)
    if candidate_metrics["mae"] >= pinned_metrics["mae"]:
        raise RuntimeError("candidate did not improve holdout MAE")
    return candidate


def run_drill(
    *,
    out: Path,
    alert_config: Path,
    release: Path,
    cfg: dict,
    features: Path,
    baseline: Path,
    models_dir: Path,
    releases_dir: Path,
) -> dict:
    out = out.resolve()
    out.mkdir(parents=True, exist_ok=False)
    pinned = load_pinned_release(releases_dir=releases_dir, models_dir=models_dir)
    calibration = calibrate(pinned, release, cfg, features, baseline)
    write_json(out / "calibration.json", calibration)
    healthy = _monitor(out, pinned, release, cfg, features, HEALTHY, calibration)
    if healthy["decision"]["action"] != "hold" or any(
        signal["breached"] for signal in healthy["signals"].values()
    ):
        raise RuntimeError("healthy control breached calibrated thresholds")

    injected_at = _now()
    shift_release, shift_cfg = _new_dataset(out, cfg)
    shift_features = out / "features"
    step_features(shift_release, shift_cfg, shift_features)
    shifted = _monitor(out, pinned, shift_release, shift_cfg, shift_features, SHIFTED, calibration)
    observed_at = _now()
    if shifted["decision"]["action"] != "retrain":
        raise RuntimeError("tariff shock did not trigger retraining")

    with ExitStack() as resources:
        events = _stack(resources, alert_config.resolve(), out)
        push_metrics(healthy, GATEWAY)

        def control_scraped():
            data = _http_json(f"{PROMETHEUS}/api/v1/query?query=charging_monitor_breach")
            return len(data["data"]["result"]) == len(healthy["signals"])

        _wait_until(control_scraped)
        healthy_scraped_at = _now()
        sleep(10)
        active = _http_json(f"{PROMETHEUS}/api/v1/alerts")["data"]["alerts"]
        if active or events:
            raise RuntimeError("healthy control fired a Prometheus alert")
        healthy_verified_at = _now()

        shifted_pushed_at = _now()
        push_metrics(shifted, GATEWAY)

        def firing_alert():
            for event in events:
                if event["status"] == "firing" and any(
                    alert["labels"]["alertname"] == "ChargingForecastDrift"
                    for alert in event["alerts"]
                ):
                    return event
            return None

        delivered = _wait_until(firing_alert)
        retraining_started_at = _now()
        candidate = _fit_candidate(out, pinned, shift_release, shift_cfg, shift_features, shifted)

    report = {
        "kind": "tariff-drift-drill",
        "source_commit": git_commit(),
        "shock": SHOCK,
        "source_calibration_sha256": sha256_file(out / "calibration.json"),
        "injected_at": injected_at,
        "observed_at": observed_at,
        "healthy_scraped_at": healthy_scraped_at,
        "healthy_verified_at": healthy_verified_at,
        "healthy": healthy,
        "shifted_pushed_at": shifted_pushed_at,
        "alert_received_at": delivered["received_at"],
        "retraining_started_at": retraining_started_at,
        "shifted": shifted,
        "candidate": candidate,
    }
    write_json(out / "drill.json", report)
    return report
