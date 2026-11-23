import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from cloud_acceptance import HERE, app_probe, logs_for, target_url
from deploy_cloud_run import deploy, deployment_args

EVIDENCE = HERE / "evidence/cloud-run-image-rehearsal.json"
MODEL = json.loads(EVIDENCE.read_bytes())["probe"]


class CloudAcceptanceTests(unittest.TestCase):
    def test_candidate_uses_tag_url_with_the_base_audience_and_no_service_traffic(self):
        status = {"url": "https://eddf.run.app", "traffic": [
            {"tag": "candidate", "url": "https://candidate---eddf.run.app", "revisionName": "eddf-candidate"},
            {"revisionName": "eddf-known-good", "percent": 100},
        ]}
        self.assertEqual(target_url(status, "eddf-candidate", "candidate"),
                         ("https://eddf.run.app", "https://candidate---eddf.run.app"))
        self.assertEqual(target_url(status, "eddf-known-good", None), ("https://eddf.run.app",) * 2)
        status["traffic"][0]["percent"] = 10
        with self.assertRaisesRegex(ValueError, "zero service traffic"):
            target_url(status, "eddf-candidate", "candidate")
        status["url"] = "https://eddf.run.app.example.com"
        with self.assertRaisesRegex(ValueError, "direct HTTPS"):
            target_url(status, "eddf-known-good", None)

    def test_acceptance_checks_private_probe_lineage_http_and_metric(self):
        release = MODEL["model"]
        gauge = (f'eddf_serving_model_info{{model_release_id="{release["model_release_id"]}",'
                 'model_version="1"} 1.0\neddf_prediction_request_duration_seconds_count 2.0\n')
        responses = [(403, None, "Forbidden"), (200, None, '{"status":"ok"}'),
                     (200, None, json.dumps(release)), (200, "a" * 32, json.dumps(MODEL)),
                     (200, "b" * 32, json.dumps(MODEL)), (200, None, gauge)]
        with patch("cloud_acceptance.request", side_effect=responses) as http:
            ids = app_probe("https://eddf.run.app", "token", MODEL)
            self.assertEqual(ids, ["a" * 32, "b" * 32])
            self.assertEqual(http.call_args_list[0].args, ("https://eddf.run.app", "/health"))
        with patch("cloud_acceptance.request", return_value=(200, None, "public")):
            with self.assertRaisesRegex(ValueError, "anonymous"):
                app_probe("https://eddf.run.app", "token", MODEL)

    def test_logs_match_request_ids_and_release_from_json_or_uvicorn_text(self):
        ids = ["a" * 32, "b" * 32]
        records = [{"request_id": item, "model_release_id": "model", "route": "/v1/predict",
                    "latency_ms": 3.5, "status": 200} for item in ids]
        output = json.dumps([{"jsonPayload": records[0]}, {"textPayload": "INFO: " + json.dumps(records[1])}])
        with patch("cloud_acceptance.gcloud", return_value=output) as client:
            self.assertEqual([r["request_id"] for r in logs_for("test", "eddf-r1", ids, "model")], ids)
            self.assertIn('resource.labels.revision_name="eddf-r1"', client.call_args.args[2])

    def test_deploy_refuses_archive_evidence_and_unknown_images_before_cloud(self):
        with tempfile.TemporaryDirectory() as temp:
            audit = Path(temp) / "audit.json"
            audit.write_text('{"status":"blocked"}')
            with patch("deploy_cloud_run.gcloud") as cloud:
                with self.assertRaisesRegex(ValueError, "measured"):
                    deploy(SimpleNamespace(audit=audit))
                cloud.assert_not_called()
        args = SimpleNamespace(project="slh-gcp-test", repository="aviation-serving", suffix="r1", mode="candidate",
                               runtime="fraport-runtime@slh-gcp-test.iam.gserviceaccount.com",
                               invoker="fraport-invoker@slh-gcp-test.iam.gserviceaccount.com",
                               image="europe-west3-docker.pkg.dev/slh-gcp-test/aviation-serving/eddf-taxi-in@sha256:" + "a" * 64)
        command = deployment_args(args)
        self.assertIn("--no-traffic", command)
        self.assertIn("--no-allow-unauthenticated", command)
        self.assertIn("--max-instances=1", command)
        args.image = args.image.split("@")[0] + ":latest"
        with self.assertRaisesRegex(ValueError, "digest"):
            deployment_args(args)

    def test_measured_candidate_deploy_checks_existing_service_and_verifies_revision(self):
        with tempfile.TemporaryDirectory() as temp:
            audit = Path(temp) / "audit.json"
            audit.write_text(json.dumps({"schema_version": "fraport-availability-audit-v1", "status": "measured",
                                         "observed_partitions": [{}], "arrival_triggers": {"observed": 3},
                                         "observation_delays": {"invalid_timestamps_including_context": 0}}))
            args = SimpleNamespace(project="slh-gcp-test", repository="aviation-serving", suffix="r1", mode="candidate",
                                   runtime="fraport-runtime@slh-gcp-test.iam.gserviceaccount.com",
                                   invoker="fraport-invoker@slh-gcp-test.iam.gserviceaccount.com", audit=audit,
                                   evidence=EVIDENCE, image="europe-west3-docker.pkg.dev/slh-gcp-test/aviation-serving/eddf-taxi-in@sha256:" + "a" * 64)
            with patch("deploy_cloud_run.gcloud", side_effect=["eddf-taxi-in", ""]) as cloud, \
                 patch("deploy_cloud_run.verify", return_value={"traffic_percent": 0}) as verify_cloud:
                self.assertEqual(deploy(args)["traffic_percent"], 0)
                self.assertIn("--no-traffic", cloud.call_args.args)
                self.assertEqual(verify_cloud.call_args.args[0].revision, "eddf-taxi-in-r1")
                self.assertEqual(verify_cloud.call_args.args[0].tag, "candidate")
            with patch("deploy_cloud_run.gcloud", return_value="energy-api") as cloud:
                with self.assertRaisesRegex(ValueError, "mode"):
                    deploy(args)
                cloud.assert_called_once()
