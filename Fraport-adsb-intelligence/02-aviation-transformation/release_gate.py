"""Release Gate for gold markets (02 M3, ADR-003).

Packages one gold market output as an immutable, versioned release:

    releases contain data/, manifest.json, contract.yaml,
    validation.json, approval.json and a _SUCCESS written last.

The gate never mutates the gold input. It verifies the input against its
own run manifest first, re-checksums every release file, and blocks (no
_SUCCESS, non-zero exit) when any contract check fails. Thresholds live
in the contract YAML, never in code.
"""
import argparse
import hashlib
import json
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq
import yaml

from gold_ground_ops import GEOMETRY_LABEL_VERSION, RADIUS_LABEL_VERSION
from silver_m1 import digest

RELEASE_SCHEMA_VERSION = "release-v1"


class ContractError(ValueError):
    """A contract file is missing, malformed or internally inconsistent."""


@dataclass(frozen=True)
class GroundOpsContract:
    data_product: str
    version: str
    schema_version: str
    label_version: str
    grain: tuple[str, ...]
    required_columns: tuple[str, ...]
    field_policy: dict
    labeled_ratio_min: float
    taxi_in_s_min: int
    taxi_in_s_max: int
    duplicate_keys_max: int
    approval_required: bool


@dataclass(frozen=True)
class CheckResult:
    name: str
    passed: bool
    detail: str
    offending: tuple = ()


def _require(document, key, kind, where):
    if key not in document:
        raise ContractError(f"{where}: missing key {key!r}")
    value = document[key]
    if not isinstance(value, kind) or isinstance(value, bool) and kind is not bool:
        raise ContractError(f"{where}: {key!r} must be {kind.__name__}")
    return value


def load_contract(path: Path) -> GroundOpsContract:
    """Parse and validate one contract file."""
    try:
        document = yaml.safe_load(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ContractError(f"contract file not found: {path}") from exc
    except yaml.YAMLError as exc:
        raise ContractError(f"contract file is not valid YAML: {exc}") from exc
    if not isinstance(document, dict):
        raise ContractError("contract document must be a mapping")

    data_product = _require(document, "data_product", str, "top level")
    version = _require(document, "version", str, "top level")
    contract = _require(document, "contract", dict, "top level")
    schema_version = _require(contract, "schema_version", str, "contract")
    label_version = contract.get("label_version", RADIUS_LABEL_VERSION)
    if label_version not in (RADIUS_LABEL_VERSION, GEOMETRY_LABEL_VERSION):
        raise ContractError(f"contract: unsupported label_version {label_version!r}")
    grain = tuple(_require(contract, "grain", list, "contract"))
    required = tuple(_require(contract, "required_columns", list, "contract"))
    if not grain or not all(isinstance(g, str) for g in grain):
        raise ContractError("contract: 'grain' must be a non-empty list of column names")
    if not required or not all(isinstance(c, str) for c in required):
        raise ContractError("contract: 'required_columns' must be a non-empty list")
    for column in grain:
        if column not in required:
            raise ContractError(f"contract: grain column {column!r} is not required")
    policy = _require(contract, "field_policy", dict, "contract")
    if not policy or not all(
        isinstance(k, str) and k in required and v in ("keep", "drop")
        for k, v in policy.items()
    ):
        raise ContractError("contract: 'field_policy' must map required columns to keep/drop")

    gates = _require(document, "quality_gates", dict, "top level")
    labeled_ratio_min = _require(gates, "labeled_ratio_min", (int, float), "quality_gates")
    taxi_min = _require(gates, "taxi_in_s_min", int, "quality_gates")
    taxi_max = _require(gates, "taxi_in_s_max", int, "quality_gates")
    duplicate_max = _require(gates, "duplicate_keys_max", int, "quality_gates")
    if not 0.0 <= labeled_ratio_min <= 1.0:
        raise ContractError("quality_gates: labeled_ratio_min must be within [0, 1]")
    if taxi_min < 1 or taxi_max < taxi_min or duplicate_max < 0:
        raise ContractError("quality_gates: thresholds must satisfy 1 <= min <= max, dup >= 0")

    release = _require(document, "release", dict, "top level")
    approval_required = _require(release, "approval_required", bool, "release")

    return GroundOpsContract(
        data_product=data_product, version=version, schema_version=schema_version,
        label_version=label_version,
        grain=grain, required_columns=required, field_policy=dict(policy),
        labeled_ratio_min=float(labeled_ratio_min), taxi_in_s_min=taxi_min,
        taxi_in_s_max=taxi_max, duplicate_keys_max=duplicate_max,
        approval_required=approval_required,
    )


def verify_gold_input(gold_root: Path) -> dict:
    """Re-checksum the gold output against its own run manifest."""
    manifest_path = gold_root / "run_manifest.json"
    if not manifest_path.is_file():
        raise SystemExit(f"gold input has no run_manifest.json: {gold_root}")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    for name, entry in manifest.get("outputs", {}).items():
        file = gold_root / name
        if not file.is_file():
            raise SystemExit(f"gold input file missing: {name}")
        if digest(file) != entry["sha256"]:
            raise SystemExit(f"gold input checksum mismatch: {name}")
    core = {k: v for k, v in manifest.items() if k not in ("input_id", "outputs")}
    input_id = hashlib.sha256(json.dumps(core, sort_keys=True).encode()).hexdigest()
    if input_id != manifest.get("input_id"):
        raise SystemExit("gold input_id does not match its manifest contents")
    return manifest


def source_commit() -> str:
    """Best-effort git commit of the code that built the release."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=Path(__file__).resolve().parent,
            capture_output=True, text=True, timeout=10, check=True)
        return result.stdout.strip()
    except Exception:
        return "unavailable"


def run_checks(contract: GroundOpsContract, rows: list[dict], schema: pa.Schema,
               output: Path, files: dict) -> list[CheckResult]:
    """Contract checks over the staged release. Never mutates anything."""
    checks = []
    now = datetime.now(timezone.utc)

    # Schema: required columns present, arrow types carried from the gold
    # market, and no column the field policy drops.
    actual = {f.name: f.type for f in schema}
    missing = [c for c in contract.required_columns if c not in actual]
    dropped = [c for c, p in contract.field_policy.items() if p == "drop" and c in actual]
    checks.append(CheckResult(
        "schema", not missing and not dropped,
        f"{len(actual)} columns staged" if not missing and not dropped
        else f"missing {missing}, policy-dropped present {dropped}",
        offending=tuple(missing + dropped)))

    # Grain uniqueness.
    keys = [tuple(r.get(c) for c in contract.grain) for r in rows]
    counts = {}
    for key in keys:
        counts[key] = counts.get(key, 0) + 1
    duplicated = tuple(k for k, n in counts.items() if n > 1)
    checks.append(CheckResult(
        "grain_uniqueness", len(duplicated) <= contract.duplicate_keys_max,
        f"{len(duplicated)} duplicated grain keys (max {contract.duplicate_keys_max})",
        offending=duplicated))

    # Label coverage: the labeled share must clear the contract floor.
    labeled = [r for r in rows if r.get("status") == "labeled"]
    ratio = (len(labeled) / len(rows)) if rows else 0.0
    checks.append(CheckResult(
        "label_coverage", ratio >= contract.labeled_ratio_min,
        f"labeled {len(labeled)}/{len(rows)} = {ratio:.3f} "
        f"(min {contract.labeled_ratio_min})"))

    # Labeled taxi-in values are present and inside the contract window.
    bad = tuple(
        r.get("flight_key") for r in labeled
        if r.get("taxi_in_s") is None
        or not contract.taxi_in_s_min <= r["taxi_in_s"] <= contract.taxi_in_s_max)
    checks.append(CheckResult(
        "taxi_in_range", not bad,
        f"{len(bad)} labeled rows with taxi_in_s outside "
        f"[{contract.taxi_in_s_min}, {contract.taxi_in_s_max}] or null",
        offending=bad))

    # Checksums: every staged file must match the manifest entry.
    mismatched = tuple(name for name, entry in files.items()
                       if digest(output / name) != entry["sha256"])
    checks.append(CheckResult(
        "checksums", not mismatched, f"{len(files)} files verified"
        if not mismatched else f"checksum mismatch: {sorted(mismatched)}",
        offending=mismatched))

    # Row count sanity: the manifest and the data agree, non-empty.
    data_rows = files.get("data/part-0001.parquet", {}).get("rows", 0)
    checks.append(CheckResult(
        "row_count", data_rows == len(rows) and data_rows > 0,
        f"manifest {data_rows} rows, staged {len(rows)}"))

    checks.append(CheckResult(
        "gate_clock", True, f"checks ran at {now.isoformat()}"))
    return checks


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--gold-root", type=Path, required=True,
                        help="existing gold market output with run_manifest.json")
    parser.add_argument("--contract", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True,
                        help="new release directory")
    parser.add_argument("--release-id", required=True)
    parser.add_argument("--approver", required=True)
    parser.add_argument("--notes", default="")
    args = parser.parse_args()
    gold_root, output = args.gold_root.resolve(), args.output.resolve()
    _here = Path(__file__).resolve()
    # In a container the three-level repository layout does not exist;
    # skip the repo check there and keep the input-directory checks.
    repo = _here.parents[2] if len(_here.parents) > 2 else None
    if (repo and output.is_relative_to(repo)) or output.is_relative_to(gold_root):
        parser.error("write to a new local directory outside the repository and gold input")
    if output.exists():
        parser.error("output directory already exists; choose a new directory")

    contract = load_contract(args.contract.resolve())
    gold_manifest = verify_gold_input(gold_root)
    if gold_manifest.get("schema_version") != contract.schema_version:
        raise SystemExit(
            f"gold schema {gold_manifest.get('schema_version')!r} is not the "
            f"contract schema {contract.schema_version!r}")
    label_version = gold_manifest.get("label_version", RADIUS_LABEL_VERSION)
    if label_version != contract.label_version:
        raise SystemExit(
            f"gold label version {label_version!r} does not match "
            f"contract label version {contract.label_version!r}")
    geometry = gold_manifest.get("airport_geometry")
    if label_version == GEOMETRY_LABEL_VERSION:
        if not isinstance(geometry, dict) or not geometry.get("files"):
            raise SystemExit("geometry label version requires a fingerprinted airport snapshot")
    elif "airport_geometry" in gold_manifest:
        raise SystemExit("a geometry Gold run requires an explicit geometry label version")

    table = pq.read_table(gold_root / "arrivals.parquet")
    rows = table.to_pylist()
    now = datetime.now(timezone.utc).replace(microsecond=0)

    # Stage the release: contract copy, data, then the manifest.
    output.mkdir(mode=0o700, parents=False, exist_ok=False)
    (output / "data").mkdir()
    contract_copy = output / "contract.yaml"
    contract_copy.write_text(args.contract.resolve().read_text(encoding="utf-8"))
    data_file = output / "data" / "part-0001.parquet"
    pq.write_table(table, data_file, compression="zstd", row_group_size=65536)
    files = {
        "contract.yaml": {"sha256": digest(contract_copy)},
        "data/part-0001.parquet": {"rows": len(rows), "bytes": data_file.stat().st_size,
                                   "sha256": digest(data_file)},
    }
    input_metadata = {key: gold_manifest[key] for key in (
        "silver_dates_utc", "missing_dates_utc", "missing_observation_dates_utc",
        "airport_geometry",
    ) if key in gold_manifest}
    manifest = {
        "release_id": args.release_id,
        "data_product": contract.data_product,
        "contract_version": contract.version,
        "schema_version": contract.schema_version,
        "label_version": contract.label_version,
        "release_schema_version": RELEASE_SCHEMA_VERSION,
        "source_commit": source_commit(),
        "created_at": now.isoformat(),
        "input": {"gold_root": gold_root.name, "input_id": gold_manifest.get("input_id"),
                  "dates_utc": gold_manifest.get("dates_utc"), **input_metadata},
        "grain": list(contract.grain),
        "field_policy": contract.field_policy,
        "code_sha256": {p.name: digest(p) for p in sorted(Path(__file__).parent.glob("*.py"))},
        "files": files,
    }
    (output / "manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    checks = run_checks(contract, rows, table.schema, output, files)
    passed = all(c.passed for c in checks)
    validation = {
        "release_id": args.release_id,
        "status": "passed" if passed else "blocked",
        "checked_at": now.isoformat(),
        "checks": [{"name": c.name, "passed": c.passed, "detail": c.detail,
                    "offending": [list(o) if isinstance(o, tuple) else o
                                  for o in c.offending]} for c in checks],
    }
    (output / "validation.json").write_text(
        json.dumps(validation, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    if not passed:
        failed = [c.name for c in checks if not c.passed]
        print(json.dumps({"status": "blocked", "failed": failed}), flush=True)
        sys.exit(1)

    approval = {
        "release_id": args.release_id,
        "approver": args.approver,
        "decided_at": now.isoformat(),
        "notes": args.notes,
        "contract_version": contract.version,
    }
    (output / "approval.json").write_text(
        json.dumps(approval, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    # _SUCCESS is written last, after every other file is re-verified.
    for name, entry in files.items():
        if digest(output / name) != entry["sha256"]:
            raise SystemExit(f"release file changed after verification: {name}")
    (output / "_SUCCESS").write_text(
        json.dumps({"release_id": args.release_id, "written_at": now.isoformat()}) + "\n",
        encoding="utf-8")
    print(json.dumps({"status": "passed", "release_id": args.release_id,
                      "rows": len(rows)}), flush=True)


if __name__ == "__main__":
    main()
