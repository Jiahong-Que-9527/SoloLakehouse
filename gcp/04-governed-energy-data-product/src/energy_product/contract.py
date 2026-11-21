"""Data-product contracts (design section 4).

One YAML file per product; thresholds live there, never in code. A live
feed may only tighten or loosen a threshold by changing the contract
version, which makes every gate decision reproducible against the exact
contract text that produced it.
"""

from dataclasses import dataclass
from pathlib import Path

import yaml


class ContractError(ValueError):
    """A contract file is missing, malformed or internally inconsistent."""


@dataclass(frozen=True)
class QualityGates:
    completeness_min: float
    duplicate_business_keys_max: int
    value_min: float
    freshness_hours_max: int


@dataclass(frozen=True)
class DataProductContract:
    data_product: str
    version: str
    schema_version: int
    grain: tuple[str, ...]
    required_columns: tuple[str, ...]
    gates: QualityGates
    approval_required: bool
    record_manifest: bool

    @property
    def slug(self) -> str:
        """Table-safe name: ``energy-load`` -> ``energy_load``."""
        return self.data_product.replace("-", "_")

    @property
    def version_table(self) -> str:
        return f"{self.slug}_v"

    @property
    def current_view(self) -> str:
        return f"{self.slug}_current"


def _require(document: dict, key: str, kind: type, where: str):
    if key not in document:
        raise ContractError(f"{where}: missing key {key!r}")
    value = document[key]
    if not isinstance(value, kind) or isinstance(value, bool) and kind is not bool:
        raise ContractError(f"{where}: {key!r} must be {kind.__name__}")
    return value


def load_contract(path: Path) -> DataProductContract:
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
    if not version:
        raise ContractError("top level: 'version' must not be empty")

    contract = _require(document, "contract", dict, "top level")
    schema_version = _require(contract, "schema_version", int, "contract")
    grain = tuple(_require(contract, "grain", list, "contract"))
    required = tuple(_require(contract, "required_columns", list, "contract"))
    if not grain or not all(isinstance(g, str) for g in grain):
        raise ContractError("contract: 'grain' must be a non-empty list of column names")
    if not required or not all(isinstance(c, str) for c in required):
        raise ContractError("contract: 'required_columns' must be a non-empty list of column names")
    for column in grain:
        if column not in required:
            raise ContractError(f"contract: grain column {column!r} is not a required column")

    gates_doc = _require(document, "quality_gates", dict, "top level")
    completeness_min = _require(gates_doc, "completeness_min", float, "quality_gates")
    duplicate_max = _require(gates_doc, "duplicate_business_keys_max", int, "quality_gates")
    value_min = _require(gates_doc, "value_min", (int, float), "quality_gates")
    freshness_max = _require(gates_doc, "freshness_hours_max", int, "quality_gates")
    if not 0.0 <= completeness_min <= 1.0:
        raise ContractError("quality_gates: completeness_min must be within [0, 1]")
    if duplicate_max < 0 or freshness_max < 0:
        raise ContractError("quality_gates: thresholds must not be negative")

    release = _require(document, "release", dict, "top level")
    approval_required = _require(release, "approval_required", bool, "release")
    record_manifest = _require(release, "record_manifest", bool, "release")

    return DataProductContract(
        data_product=data_product,
        version=version,
        schema_version=schema_version,
        grain=grain,
        required_columns=required,
        gates=QualityGates(
            completeness_min=float(completeness_min),
            duplicate_business_keys_max=duplicate_max,
            value_min=float(value_min),
            freshness_hours_max=freshness_max,
        ),
        approval_required=approval_required,
        record_manifest=record_manifest,
    )
