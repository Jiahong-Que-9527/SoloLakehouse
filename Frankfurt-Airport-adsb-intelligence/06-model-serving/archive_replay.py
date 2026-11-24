"""Prepare and replay the full pinned M5 archive through an isolated HTTP service."""

import argparse
import hashlib
import json
import math
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from http.client import HTTPConnection
from pathlib import Path
from threading import local
from urllib.parse import urlsplit
from urllib.request import urlopen
from zoneinfo import ZoneInfo


def digest(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def prepare(args):
    import pickle

    import numpy as np
    import pyarrow.parquet as pq

    release = json.loads(args.release.read_bytes())
    evaluation = json.loads(args.evaluation.read_bytes())
    artifact = args.model.read_bytes()
    model_hash = hashlib.sha256(artifact).hexdigest()
    if (model_hash != release["artifact"]["sha256"] or model_hash != evaluation["model_sha256"]
            or digest(args.release) != evaluation["model_release_manifest_sha256"]):
        raise ValueError("model or manifest does not match the frozen M5 evidence")
    columns = release["feature_columns"]
    # Deserialize the checksum-verified model from the trusted local M4 release.
    bundle = pickle.loads(artifact)
    if bundle["feature_columns"] != columns:
        raise ValueError("model feature order differs from the release")
    header = {"lineage": {"model_release_id": release["model_release_id"], "model_version": release["registry"]["version"],
                          "source_commit": release["source_commit"], "manifest_sha256": digest(args.release),
                          "artifact_sha256": model_hash}, "evaluation_sha256": digest(args.evaluation),
              "predictions": evaluation["overall"]["predictions"], "labels": evaluation["overall"]["evaluated_labels"],
              "mae": evaluation["overall"]["candidate_metrics_seconds"]["mae"], "availability": evaluation["availability"]}
    with args.output.open("x", encoding="utf-8") as stream:
        stream.write(json.dumps(header, sort_keys=True) + "\n")
        for month, pinned in sorted(evaluation["datasets"].items()):
            directory = args.features / pinned["feature_dataset_id"]
            parquet = directory / "training.parquet"
            if (digest(directory / "manifest.json") != pinned["feature_manifest_sha256"]
                    or digest(parquet) != pinned["training_parquet_sha256"]):
                raise ValueError(f"pinned M5 features changed for {month}")
            table = pq.read_table(parquet, columns=[*columns, "prediction_at", "taxi_in_s"])
            matrix = np.column_stack([table[name].to_numpy() for name in columns]).astype(np.float64)
            scores = bundle["estimator"].predict(matrix)
            for row, score in zip(table.to_pylist(), scores, strict=True):
                timestamp = datetime.fromtimestamp(row["prediction_at"], UTC)
                if row["prediction_hour_utc"] != timestamp.hour:
                    raise ValueError("archived UTC hour does not match prediction_at")
                case = {"month": month, "body": {"airport_icao": "EDDF",
                         "prediction_at": timestamp.astimezone(ZoneInfo("Europe/Berlin")).isoformat(),
                         "features": {name: row[name] for name in columns if name != "prediction_hour_utc"}},
                        "utc": timestamp.isoformat().replace("+00:00", "Z"),
                        "actual": row["taxi_in_s"], "expected": float(score)}
                stream.write(json.dumps(case, sort_keys=True, allow_nan=False) + "\n")


def verify(args):
    address = urlsplit(args.url)
    if address.scheme != "http" or address.hostname not in ("127.0.0.1", "localhost", "::1") or address.path:
        raise ValueError("archive replay expects the isolated service at a loopback HTTP URL")
    connections = local()

    def get(path):
        with urlopen(args.url + path, timeout=10) as response:
            return json.load(response)

    with args.fixture.open(encoding="utf-8") as stream:
        header = json.loads(next(stream))
        cases = [json.loads(line) for line in stream]
    if get("/health") != {"status": "ok"} or get("/v1/model") != header["lineage"]:
        raise ValueError("service is not serving the pinned M4 release")

    def score(case):
        if not hasattr(connections, "http"):
            connections.http = HTTPConnection(address.hostname, address.port or 80, timeout=15)
        connections.http.request("POST", "/v1/predict", body=json.dumps(case["body"]),
                                 headers={"Content-Type": "application/json"})
        with connections.http.getresponse() as response:
            result = json.load(response)
            if response.status != 200 or not response.headers.get("X-Request-Id") or result != {
                "airport_icao": "EDDF", "prediction_at": case["utc"], "model": header["lineage"],
                "predicted_taxi_in_seconds": case["expected"],
            }:
                raise ValueError(f"prediction, UTC timestamp or lineage differs in {case['month']}")
        return result["predicted_taxi_in_seconds"]

    months = {}
    errors = []
    with ThreadPoolExecutor(max_workers=4) as pool:
        # Submit bounded groups so a service failure stops further requests promptly.
        for offset in range(0, len(cases), 256):
            batch = cases[offset:offset + 256]
            for case, prediction in zip(batch, pool.map(score, batch), strict=True):
                counts = months.setdefault(case["month"], {"predictions": 0, "evaluated_labels": 0})
                counts["predictions"] += 1
                if case["actual"] is not None:
                    counts["evaluated_labels"] += 1
                    errors.append(abs(prediction - case["actual"]))
    if len(cases) != header["predictions"] or len(errors) != header["labels"]:
        raise ValueError("replay counts differ from M5 evidence")
    mae = math.fsum(errors) / len(errors)
    if not math.isclose(mae, header["mae"], rel_tol=0, abs_tol=1e-10):
        raise ValueError("HTTP MAE differs from the frozen offline report")
    report = {"lineage": header["lineage"], "evaluation_sha256": header["evaluation_sha256"],
              "availability": header["availability"], "by_month": months,
              "exact_matches": len(cases), "evaluated_labels": len(errors), "mae_seconds": mae}
    with args.output.open("x", encoding="utf-8") as stream:
        json.dump(report, stream, indent=2, sort_keys=True)
        stream.write("\n")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(required=True)
    build = commands.add_parser("prepare")
    build.set_defaults(run=prepare)
    for name in ("release", "evaluation", "model", "features", "output"):
        build.add_argument(f"--{name}", required=True, type=Path)
    replay = commands.add_parser("verify")
    replay.set_defaults(run=verify)
    replay.add_argument("--url", default="http://127.0.0.1:8080")
    replay.add_argument("--fixture", required=True, type=Path)
    replay.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    args.run(args)


if __name__ == "__main__":
    main()
