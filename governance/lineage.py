"""Read-only source adapters and strict joins for v2.6 lineage evidence."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any
from urllib.parse import quote, urlparse

import requests

from governance.contracts import DatasetContract
from governance.evidence import LineageRecord


class EvidenceSourceError(ValueError):
    """A required evidence source was unavailable, incomplete, or inconsistent."""

    def __init__(self, source: str, reason: str) -> None:
        super().__init__(f"{source} evidence is invalid: {reason}")
        self.source = source
        self.reason = reason


@dataclass(frozen=True)
class OpenMetadataEvidence:
    """The catalog identity and ownership evidence for one governed dataset."""

    dataset_id: str
    table_fqn: str
    owners: tuple[str, ...]
    tags: tuple[str, ...]


@dataclass(frozen=True)
class IcebergSnapshotEvidence:
    """The immutable Iceberg table state behind one governed dataset."""

    dataset_id: str
    catalog: str
    namespace: str
    table: str
    snapshot_id: str
    bucket: str
    object_path: str


@dataclass(frozen=True)
class DagsterRunEvidence:
    """The successful orchestration context for one governed dataset."""

    dataset_id: str
    run_id: str
    asset_keys: tuple[str, ...]
    started_at: datetime


class OpenMetadataAdapter:
    """Load table metadata through the OpenMetadata REST API without mutation."""

    def __init__(
        self,
        base_url: str,
        service_name: str,
        session: requests.Session | Any | None = None,
        timeout_seconds: float = 10,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.service_name = service_name
        self.session = session or requests.Session()
        self.timeout_seconds = timeout_seconds

    def collect(self, contract: DatasetContract) -> OpenMetadataEvidence:
        expected_fqn = (
            f"{self.service_name}.{contract.physical_location.namespace}."
            f"{contract.physical_location.table}"
        )
        url = f"{self.base_url}/api/v1/tables/name/{quote(expected_fqn, safe='')}"
        try:
            response = self.session.get(
                url, params={"fields": "owners,tags"}, timeout=self.timeout_seconds
            )
            response.raise_for_status()
            payload = response.json()
        except requests.RequestException as exc:
            raise EvidenceSourceError("openmetadata", str(exc)) from exc
        except (TypeError, ValueError) as exc:
            raise EvidenceSourceError("openmetadata", "response is not valid JSON") from exc

        if not isinstance(payload, dict):
            raise EvidenceSourceError("openmetadata", "table response must be an object")
        table_fqn = payload.get("fullyQualifiedName")
        if table_fqn != expected_fqn:
            raise EvidenceSourceError(
                "openmetadata", f"expected table {expected_fqn!r}, received {table_fqn!r}"
            )
        owners = _owner_names(payload.get("owners"))
        if not owners:
            raise EvidenceSourceError("openmetadata", "table has no catalog owner")
        return OpenMetadataEvidence(
            contract.dataset_id, table_fqn, owners, _tag_names(payload.get("tags"))
        )


class IcebergSnapshotAdapter:
    """Load the current snapshot and metadata location from a PyIceberg catalog."""

    def __init__(self, catalog: Any) -> None:
        self.catalog = catalog

    def collect(self, contract: DatasetContract) -> IcebergSnapshotEvidence:
        location = contract.physical_location
        try:
            table = self.catalog.load_table((location.namespace, location.table))
            snapshot = table.current_snapshot()
        except Exception as exc:
            raise EvidenceSourceError(
                "iceberg", f"cannot load {location.namespace}.{location.table}: {exc}"
            ) from exc
        if snapshot is None or getattr(snapshot, "snapshot_id", None) is None:
            raise EvidenceSourceError("iceberg", "table has no current snapshot")
        metadata_location = getattr(table, "metadata_location", None)
        if not isinstance(metadata_location, str) or not metadata_location:
            raise EvidenceSourceError("iceberg", "table has no metadata location")
        bucket, object_path = _parse_s3_location(metadata_location)
        return IcebergSnapshotEvidence(
            dataset_id=contract.dataset_id,
            catalog=location.catalog,
            namespace=location.namespace,
            table=location.table,
            snapshot_id=str(snapshot.snapshot_id),
            bucket=bucket,
            object_path=object_path,
        )


class DagsterRunAdapter:
    """Load a successful Dagster run and its selected asset keys through GraphQL."""

    _QUERY = """
    query LineageEvidenceRun($runId: ID!) {
      runOrError(runId: $runId) {
        __typename
        ... on Run {
          runId
          status
          startTime
          assetSelection { path }
        }
      }
    }
    """

    def __init__(
        self,
        base_url: str,
        session: requests.Session | Any | None = None,
        timeout_seconds: float = 10,
    ) -> None:
        self.url = f"{base_url.rstrip('/')}/graphql"
        self.session = session or requests.Session()
        self.timeout_seconds = timeout_seconds

    def collect(self, contract: DatasetContract, run_id: str) -> DagsterRunEvidence:
        if not run_id:
            raise EvidenceSourceError("dagster", "run_id is required")
        try:
            response = self.session.post(
                self.url,
                json={"query": self._QUERY, "variables": {"runId": run_id}},
                timeout=self.timeout_seconds,
            )
            response.raise_for_status()
            payload = response.json()
        except requests.RequestException as exc:
            raise EvidenceSourceError("dagster", str(exc)) from exc
        except (TypeError, ValueError) as exc:
            raise EvidenceSourceError("dagster", "response is not valid JSON") from exc

        run = _dagster_run_payload(payload)
        if run.get("runId") != run_id:
            raise EvidenceSourceError("dagster", "response does not match requested run")
        if run.get("status") != "SUCCESS":
            raise EvidenceSourceError(
                "dagster", f"run status is {run.get('status')!r}, not 'SUCCESS'"
            )
        asset_keys = _asset_keys(run.get("assetSelection"))
        if contract.dagster_asset_key not in asset_keys:
            raise EvidenceSourceError(
                "dagster", f"run does not select required asset {contract.dagster_asset_key!r}"
            )
        started_at = _timestamp(run.get("startTime"))
        return DagsterRunEvidence(contract.dataset_id, run_id, asset_keys, started_at)


class LineageEvidenceJoiner:
    """Join three evidence sources into one complete record or fail without output."""

    def __init__(
        self,
        product_id: str,
        runtime_version: str,
        environment: str,
        trino_catalog: str = "iceberg",
        object_store_provider: str = "minio",
    ) -> None:
        self.product_id = product_id
        self.runtime_version = runtime_version
        self.environment = environment
        self.trino_catalog = trino_catalog
        self.object_store_provider = object_store_provider

    def join(
        self,
        contract: DatasetContract,
        openmetadata: OpenMetadataEvidence | None,
        iceberg: IcebergSnapshotEvidence | None,
        dagster: DagsterRunEvidence | None,
    ) -> LineageRecord:
        if openmetadata is None:
            raise EvidenceSourceError("openmetadata", "required source is missing")
        if iceberg is None:
            raise EvidenceSourceError("iceberg", "required source is missing")
        if dagster is None:
            raise EvidenceSourceError("dagster", "required source is missing")
        for source, evidence in (
            ("openmetadata", openmetadata),
            ("iceberg", iceberg),
            ("dagster", dagster),
        ):
            if evidence.dataset_id != contract.dataset_id:
                raise EvidenceSourceError(source, "dataset_id does not match the contract")
        location = contract.physical_location
        if (iceberg.catalog, iceberg.namespace, iceberg.table) != (
            location.catalog,
            location.namespace,
            location.table,
        ):
            raise EvidenceSourceError("iceberg", "physical table does not match the contract")
        if contract.dagster_asset_key not in dagster.asset_keys:
            raise EvidenceSourceError("dagster", "asset selection does not match the contract")
        return LineageRecord(
            dataset_id=contract.dataset_id,
            product_id=self.product_id,
            runtime_version=self.runtime_version,
            environment=self.environment,
            dagster_run_id=dagster.run_id,
            asset_key=contract.dagster_asset_key,
            openmetadata_table_fqn=openmetadata.table_fqn,
            trino_catalog=self.trino_catalog,
            trino_schema=location.namespace,
            trino_table=location.table,
            object_store_provider=self.object_store_provider,
            bucket=iceberg.bucket,
            object_path=iceberg.object_path,
            iceberg_snapshot_id=iceberg.snapshot_id,
            evidence_timestamp=dagster.started_at,
        )


def _owner_names(value: object) -> tuple[str, ...]:
    if not isinstance(value, list):
        return ()
    names = []
    for owner in value:
        if isinstance(owner, dict):
            name = owner.get("name") or owner.get("displayName")
            if isinstance(name, str) and name:
                names.append(name)
    return tuple(names)


def _parse_s3_location(location: str) -> tuple[str, str]:
    parsed = urlparse(location)
    if parsed.scheme not in {"s3", "s3a"} or not parsed.netloc or not parsed.path.lstrip("/"):
        raise EvidenceSourceError(
            "iceberg", f"metadata location is not a bucket-relative S3 URI: {location!r}"
        )
    return parsed.netloc, parsed.path.lstrip("/")


def _tag_names(value: object) -> tuple[str, ...]:
    if not isinstance(value, list):
        return ()
    tags = []
    for tag in value:
        if isinstance(tag, dict):
            name = tag.get("tagFQN") or tag.get("name")
            if isinstance(name, str) and name:
                tags.append(name)
    return tuple(tags)


def _dagster_run_payload(payload: object) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise EvidenceSourceError("dagster", "response must be an object")
    errors = payload.get("errors")
    if errors:
        raise EvidenceSourceError("dagster", f"GraphQL returned errors: {errors!r}")
    data = payload.get("data")
    if not isinstance(data, dict) or not isinstance(data.get("runOrError"), dict):
        raise EvidenceSourceError("dagster", "response has no runOrError payload")
    run = data["runOrError"]
    if run.get("__typename") != "Run":
        raise EvidenceSourceError("dagster", f"run lookup returned {run.get('__typename')!r}")
    return run


def _asset_keys(value: object) -> tuple[str, ...]:
    if not isinstance(value, list):
        raise EvidenceSourceError("dagster", "run has no asset selection")
    keys = []
    for asset in value:
        path = asset.get("path") if isinstance(asset, dict) else None
        if (
            not isinstance(path, list)
            or not path
            or not all(isinstance(part, str) for part in path)
        ):
            raise EvidenceSourceError("dagster", "asset selection has an invalid path")
        keys.append("/".join(path))
    if not keys:
        raise EvidenceSourceError("dagster", "run selects no assets")
    return tuple(keys)


def _timestamp(value: object) -> datetime:
    if not isinstance(value, (int, float)):
        raise EvidenceSourceError("dagster", "run has no start timestamp")
    return datetime.fromtimestamp(value, tz=UTC)
