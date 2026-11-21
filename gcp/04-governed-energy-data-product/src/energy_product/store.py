"""Product store port and role policy (design sections 5 and 1).

The store owns four kinds of surfaces per product: immutable version
tables, the authorised `_current` view, the release ledger and the
quarantine. The role policy below is the local specification of the IAM
grants the Terraform must create; the cloud adapter relies on real IAM
and the access tests prove the mapping, not the mechanism.
"""

from dataclasses import dataclass, replace
from datetime import datetime
from enum import StrEnum


class AccessDenied(PermissionError):
    """The role may not touch this surface; mirrors a live IAM denial."""


class Role(StrEnum):
    PRODUCER = "producer"
    ANALYST = "analyst"
    AUDITOR = "auditor"


class Surface(StrEnum):
    SOURCE = "source"  # the input release rows (G01 dataset)
    CURRENT_VIEW = "current_view"  # the authorised `_current` view
    QUARANTINE = "quarantine"  # failed-gate rows and reasons
    RELEASE_LEDGER = "release_ledger"  # release rows and manifests


#: The exact grant mapping the cloud IAM must implement (design section 1:
#: the analyst can query the published view and cannot query the source or
#: quarantine; the auditor can read the release record and cannot edit).
ROLE_POLICY: dict[Role, frozenset[Surface]] = {
    Role.PRODUCER: frozenset(Surface),
    Role.ANALYST: frozenset({Surface.CURRENT_VIEW}),
    Role.AUDITOR: frozenset({Surface.RELEASE_LEDGER}),
}


@dataclass(frozen=True)
class ReleaseRow:
    product: str
    release_id: str
    input_release_id: str
    contract_version: str
    status: str  # passed | blocked | withdrawn
    output_table: str
    git_sha: str | None
    approver: str
    checksum: str
    published_at: datetime
    manifest: dict


class ProductStore:
    """Port implemented by the in-memory fake and the BigQuery adapter."""

    def read_as(self, role: Role, surface: Surface, query):
        if surface not in ROLE_POLICY[role]:
            raise AccessDenied(f"role {role.value} may not read {surface.value}")
        return query()


class InMemoryProductStore(ProductStore):
    """In-memory fake of the BigQuery publication path.

    ``fail_view_switch`` simulates a crash after the version table is
    written but before the view switch; the retry path in the publisher
    must adopt the existing table (checksum-verified) and complete.
    """

    def __init__(self, *, fail_view_switch: int = 0) -> None:
        self._tables: dict[str, list[dict]] = {}
        self._checksums: dict[str, str] = {}
        self._current: dict[str, str | None] = {}
        self._empty_view_schema: dict[str, str] = {}
        self._releases: dict[tuple[str, str], ReleaseRow] = {}
        self._quarantine: list[dict] = []
        self._manifests: list[dict] = []
        self._fail_view_switch = fail_view_switch

    # --- read surfaces ------------------------------------------------------

    def version_rows(self, product: str, release_id: str) -> list[dict]:
        return list(self._tables.get(self._table(product, release_id), []))

    def current_release_id(self, product: str) -> str | None:
        return self._current.get(product)

    def current_rows(self, product: str) -> list[dict]:
        release_id = self.current_release_id(product)
        if release_id is None:
            return []
        return self.version_rows(product, release_id)

    def empty_view_schema_table(self, product: str) -> str | None:
        return self._empty_view_schema.get(product)

    def release_row(self, product: str, release_id: str) -> ReleaseRow | None:
        return self._releases.get((product, release_id))

    def releases(self, product: str) -> tuple[ReleaseRow, ...]:
        return tuple(
            row
            for (product_key, _), row in sorted(self._releases.items())
            if product_key == product
        )

    def quarantine(self, product: str) -> tuple[dict, ...]:
        return tuple(row for row in self._quarantine if row["product"] == product)

    def manifests(self, product: str) -> tuple[dict, ...]:
        return tuple(manifest for manifest in self._manifests if manifest["product"] == product)

    # --- publication primitives ---------------------------------------------

    def _table(self, product: str, release_id: str) -> str:
        return f"{product}_v{release_id}"

    def recorded_checksum(self, product: str, release_id: str) -> str | None:
        return self._checksums.get(self._table(product, release_id))

    def write_version_table(
        self, product: str, release_id: str, rows: list[dict], checksum: str
    ) -> None:
        table = self._table(product, release_id)
        if table in self._tables:
            raise RuntimeError(f"version table {table} already exists")
        self._tables[table] = [dict(row) for row in rows]
        self._checksums[table] = checksum

    def point_current_view(self, product: str, release_id: str | None) -> None:
        if self._fail_view_switch > 0:
            self._fail_view_switch -= 1
            raise RuntimeError("simulated failure between version table and view switch")
        self._current[product] = release_id

    def empty_current_view(self, product: str, schema_table: str) -> None:
        """An authorised view with the schema of `schema_table` and no rows."""
        self._current[product] = None
        self._empty_view_schema[product] = schema_table

    def insert_release_row(self, row: ReleaseRow) -> None:
        key = (row.product, row.release_id)
        if key in self._releases:
            raise RuntimeError(f"release row {key} already exists")
        self._releases[key] = row

    def mark_release_status(self, product: str, release_id: str, status: str) -> None:
        existing = self._releases[(product, release_id)]
        self._releases[(product, release_id)] = replace(existing, status=status)

    def insert_quarantine_rows(self, rows: list[dict]) -> None:
        self._quarantine.extend(rows)

    def record_manifest(self, manifest: dict) -> None:
        key = (manifest["product"], manifest["release_id"])
        if any((m["product"], m["release_id"]) == key for m in self._manifests):
            return  # idempotent: a retry after a crash must not duplicate it
        self._manifests.append(manifest)
