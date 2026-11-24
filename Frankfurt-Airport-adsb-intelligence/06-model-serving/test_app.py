import hashlib
import json
import pickle
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from httpx import ASGITransport, AsyncClient
from prometheus_client.parser import text_string_to_metric_families

from app import FEATURES, create_app, load_model


class FakeEstimator:
    def predict(self, matrix):
        return [240.0 + matrix[0, -1]]


class ServingTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.release = Path(temporary.name)
        self.artifact = self.release / "model.pkl"
        self.artifact.write_bytes(pickle.dumps({"feature_columns": list(FEATURES), "estimator": FakeEstimator()}))
        self.manifest = {
            "schema_version": "frankfurt-airport-model-release-v1", "model_release_id": "frankfurt-airport-taxi-in-" + "a" * 16,
            "source_commit": "b" * 40, "feature_columns": list(FEATURES),
            "artifact": {"path": "model.pkl", "sha256": hashlib.sha256(self.artifact.read_bytes()).hexdigest()},
            "registry": {"model_name": "frankfurt-airport-taxi-in", "model_uri": "models:/frankfurt-airport-taxi-in/1", "version": 1},
        }
        self.digest = self.write_manifest()
        app = create_app(load_model(self.release, self.digest))
        self.client = AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver")
        self.addAsyncCleanup(self.client.aclose)
        self.body = {"airport_icao": "EDDF", "prediction_at": "2025-10-26T02:30:00+02:00", "features": {
            "approach_speed_mps": 70, "approach_altitude_m": None, "approach_vertical_rate_mps": -2.0,
            "approach_distance_m": 1200, "ground_speed_mps": 30, "approach_age_s": 9,
        }}

    def write_manifest(self):
        data = json.dumps(self.manifest).encode()
        (self.release / "manifest.json").write_bytes(data)
        return hashlib.sha256(data).hexdigest()

    async def test_repeat_prediction_carries_the_pinned_lineage_and_utc_hour(self):
        first = await self.client.post("/v1/predict", json=self.body)
        second = await self.client.post("/v1/predict", json={**self.body, "prediction_at": "2025-10-26T00:30:00Z"})
        self.assertEqual(first.status_code, 200)
        self.assertEqual(first.json(), second.json())
        self.assertNotEqual(first.headers["X-Request-Id"], second.headers["X-Request-Id"])
        self.assertEqual(first.json()["prediction_at"], "2025-10-26T00:30:00Z")
        self.assertEqual(first.json()["predicted_taxi_in_seconds"], 240)
        self.assertEqual(first.json()["model"], (await self.client.get("/v1/model")).json())
        self.assertEqual(first.json()["model"]["manifest_sha256"], self.digest)
        self.assertEqual((await self.client.get("/health")).json(), {"status": "ok"})

    async def test_malformed_and_unsupported_requests_return_a_contract_error(self):
        for patch in ({"airport_icao": "EDDM"}, {"prediction_at": "2025-10-26T00:30:00"},
                      {"prediction_at": "2025-10-26T00:30:00+00:99"}, {"prediction_at": 1000},
                      {"features": {**self.body["features"], "ground_speed_mps": True}},
                      {"features": {**self.body["features"], "prediction_hour_utc": 12}},
                      {"features": {"approach_distance_m": 1200}}):
            with self.subTest(patch=patch):
                self.assert_contract_error(await self.client.post("/v1/predict", json={**self.body, **patch}))
        self.assert_contract_error(await self.client.post("/v1/predict", content="{"))
        non_finite = json.dumps({**self.body, "features": {**self.body["features"], "ground_speed_mps": float("inf")}})
        self.assert_contract_error(await self.client.post("/v1/predict", content=non_finite,
                                                         headers={"Content-Type": "application/json"}))

    def assert_contract_error(self, response):
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["code"], "invalid_parameters")
        self.assertEqual(response.json()["request_id"], response.headers["X-Request-Id"])

    def test_manifest_and_artifact_pins_are_verified(self):
        with self.assertRaisesRegex(ValueError, "manifest does not match"):
            load_model(self.release, "0" * 64)
        self.artifact.write_bytes(b"invalid pickle bytes")
        with self.assertRaisesRegex(ValueError, "artifact does not match"):
            load_model(self.release, self.digest)

    def test_incompatible_feature_order_fails_at_startup(self):
        self.manifest["feature_columns"].reverse()
        with self.assertRaisesRegex(ValueError, "serving contract"):
            load_model(self.release, self.write_manifest())

    async def test_metrics_count_success_validation_error_and_model_error(self):
        self.assertEqual((await self.client.post("/v1/predict", json=self.body)).status_code, 200)
        self.assertEqual((await self.client.post("/v1/predict", json={})).status_code, 400)
        with patch.object(FakeEstimator, "predict", return_value=[float("nan")]):
            with self.assertLogs("uvicorn.error", level="ERROR"):
                self.assertEqual((await self.client.post("/v1/predict", json=self.body)).status_code, 500)
        await self.client.get("/health")
        await self.client.get("/v1/model")
        for _ in range(2):
            response = await self.client.get("/metrics")
            self.assertEqual(response.status_code, 200)
            self.assertIn("text/plain", response.headers["Content-Type"])
            samples = {(sample.name, tuple(sorted(sample.labels.items()))): sample.value
                       for family in text_string_to_metric_families(response.text) for sample in family.samples}
            for status_class in ("2xx", "4xx", "5xx"):
                self.assertEqual(samples["eddf_prediction_requests_total", (("status_class", status_class),)], 1)
            self.assertEqual(samples["eddf_prediction_request_duration_seconds_count", ()], 3)
            self.assertGreaterEqual(samples["eddf_prediction_request_duration_seconds_sum", ()], 0)
            labels = (("model_release_id", self.manifest["model_release_id"]), ("model_version", "1"))
            self.assertEqual(samples["eddf_serving_model_info", labels], 1)


if __name__ == "__main__":
    unittest.main()
