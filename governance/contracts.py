"""Dataset contract registry models and loaders."""

from __future__ import annotations

from pathlib import Path

import yaml  # type: ignore[import-untyped]
from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    ValidationError,
    field_validator,
    model_validator,
)

CONTRACTS_DIRECTORY = Path(__file__).with_name("datasets")


class QualityRules(BaseModel):
    """Rules that must hold before a governed table is written."""

    model_config = ConfigDict(extra="forbid")

    required_columns: list[str] = Field(min_length=1)
    non_null_columns: list[str] = Field(default_factory=list)
    min_row_count: int = Field(ge=0)
    date_column: str | None = None
    max_gap_days: int | None = Field(default=None, ge=1)
    forbid_future_dates: bool = False

    @model_validator(mode="after")
    def validate_date_rules(self) -> "QualityRules":
        if self.max_gap_days is not None and self.date_column is None:
            raise ValueError("max_gap_days requires date_column")
        if self.forbid_future_dates and self.date_column is None:
            raise ValueError("forbid_future_dates requires date_column")
        return self


class PhysicalLocation(BaseModel):
    """Current physical mapping for a governed dataset."""

    model_config = ConfigDict(extra="forbid")

    catalog: str
    namespace: str
    table: str


class DatasetContract(BaseModel):
    """The minimum governance contract required for a v2.6 dataset."""

    model_config = ConfigDict(extra="forbid")

    dataset_id: str = Field(pattern=r"^[a-z][a-z0-9_]*\.[a-z][a-z0-9_]*$")
    owner: str = Field(min_length=1)
    business_purpose: str = Field(min_length=1)
    refresh_sla: str = Field(min_length=1)
    quality_class: str = Field(min_length=1)
    consumers: list[str] = Field(min_length=1)
    retention: str = Field(min_length=1)
    classification: str = Field(min_length=1)
    source_of_truth: str = Field(min_length=1)
    approved_consumer_class: list[str] = Field(min_length=1)
    access_policy_hint: str = Field(min_length=1)
    layer: str = Field(pattern=r"^(bronze|silver|gold)$")
    physical_location: PhysicalLocation
    dagster_asset_key: str = Field(min_length=1)
    upstream_dataset_ids: list[str] = Field(default_factory=list)
    quality_rules: QualityRules

    @field_validator("consumers", "approved_consumer_class", "upstream_dataset_ids")
    @classmethod
    def unique_values(cls, values: list[str]) -> list[str]:
        if len(values) != len(set(values)):
            raise ValueError("list values must be unique")
        return values

    @model_validator(mode="after")
    def validate_lineage_shape(self) -> "DatasetContract":
        if self.layer == "bronze" and self.upstream_dataset_ids:
            raise ValueError("bronze datasets cannot declare upstream_dataset_ids")
        if self.layer in {"silver", "gold"} and not self.upstream_dataset_ids:
            raise ValueError("silver and gold datasets require upstream_dataset_ids")
        return self


def contract_path(dataset_id: str, directory: Path = CONTRACTS_DIRECTORY) -> Path:
    """Return the canonical YAML path for a dataset contract."""
    return directory / f"{dataset_id}.yaml"


def load_contract(path: Path) -> DatasetContract:
    """Load and validate one YAML contract, with a useful empty-file error."""
    payload = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"Contract {path} must contain a YAML mapping")
    try:
        return DatasetContract.model_validate(payload)
    except ValidationError as exc:
        raise ValueError(f"Invalid contract {path}: {exc}") from exc


def load_contracts(directory: Path = CONTRACTS_DIRECTORY) -> dict[str, DatasetContract]:
    """Load every contract and reject duplicate logical dataset identifiers."""
    if not directory.is_dir():
        raise ValueError(f"Contract directory does not exist: {directory}")

    contracts: dict[str, DatasetContract] = {}
    for path in sorted(directory.glob("*.yaml")):
        contract = load_contract(path)
        if contract.dataset_id in contracts:
            raise ValueError(f"Duplicate dataset_id: {contract.dataset_id}")
        contracts[contract.dataset_id] = contract
    if not contracts:
        raise ValueError(f"No YAML contracts found in {directory}")
    return contracts


def contract_for_asset_key(
    asset_key: str,
    contracts: dict[str, DatasetContract] | None = None,
) -> DatasetContract | None:
    """Return the governed contract for one Dagster asset key, if any."""
    registry = contracts or load_contracts()
    for contract in registry.values():
        if contract.dagster_asset_key == asset_key:
            return contract
    return None


def governed_pipeline_asset_keys(
    contracts: dict[str, DatasetContract] | None = None,
) -> tuple[str, ...]:
    """Return Dagster asset keys for every governed dataset contract."""
    registry = contracts or load_contracts()
    return tuple(sorted(contract.dagster_asset_key for contract in registry.values()))
