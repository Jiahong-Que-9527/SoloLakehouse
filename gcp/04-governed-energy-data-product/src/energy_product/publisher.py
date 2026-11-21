"""Publish, retry and withdraw: the release boundary (design section 5).

The flow is ordered so a crash is always recoverable by retrying the same
candidate ID:

1. approval: an unapproved candidate cannot publish at all;
2. checksum: the canonical rows checksum identifies the candidate content;
3. an existing release row with the same ID must carry the same checksum
   (idempotent adopt) — this is what makes the crash between the version
   table and the view switch safe to retry;
4. the gate decides: failure writes quarantine rows and a ``blocked``
   release row, and the `_current` view keeps serving the previous passed
   release; success writes the version table, records the manifest, then
   switches the view and records the ``passed`` release row;
5. withdraw flips the current release's status and repoints the view to
   the previous passed release, or to an empty authorised view.

A republish always uses a fresh ID; manifests are never edited.
"""

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime

from energy_product.contract import DataProductContract
from energy_product.gate import run_gate
from energy_product.store import ReleaseRow


class PublishConflict(RuntimeError):
    """The same candidate ID was reused with different content."""


@dataclass(frozen=True)
class PublishRequest:
    product: str
    candidate_id: str
    input_release_id: str
    contract: DataProductContract
    rows: list[dict]
    expected_grid: list[tuple]
    ingested_at: datetime
    evaluation_time: datetime
    git_sha: str | None = None
    approver: str = "unset"
    approved: bool = False


@dataclass(frozen=True)
class PublishResult:
    release_id: str
    status: str  # passed | blocked
    view_points_at: str | None
    gate_passed: bool


def _checksum(rows: list[dict]) -> str:
    payload = json.dumps(
        rows,
        sort_keys=True,
        separators=(",", ":"),
        default=lambda value: value.isoformat() if hasattr(value, "isoformat") else str(value),
        ensure_ascii=False,
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def publish(store, request: PublishRequest) -> PublishResult:
    contract = request.contract
    if contract.approval_required and not request.approved:
        raise PermissionError(
            f"candidate {request.candidate_id} is not approved; "
            "a protected approver must set approved=true"
        )

    checksum = _checksum(request.rows)
    existing = store.release_row(contract.slug, request.candidate_id)
    if existing is not None:
        if existing.checksum != checksum:
            raise PublishConflict(
                f"candidate {request.candidate_id} already exists with different content; "
                "publish corrected data under a fresh ID"
            )
        # Idempotent adopt: the version table is immutable and verified; the
        # only safe completion left is pointing the view at it.
        store.point_current_view(contract.slug, request.candidate_id)
        return PublishResult(
            request.candidate_id, existing.status, request.candidate_id, existing.status == "passed"
        )

    gate = run_gate(
        contract,
        request.rows,
        request.expected_grid,
        evaluation_time=request.evaluation_time,
        ingested_at=request.ingested_at,
    )
    output_table = f"{contract.version_table}{request.candidate_id}"

    if not gate.passed:
        quarantine_rows = [
            {
                "product": contract.slug,
                "release_id": request.candidate_id,
                "input_release_id": request.input_release_id,
                "check": check.name,
                "detail": check.detail,
                "offending": [list(key) for key in check.offending[:20]],
                "recorded_at": request.evaluation_time,
            }
            for check in gate.failures
        ]
        store.insert_quarantine_rows(quarantine_rows)
        store.insert_release_row(
            ReleaseRow(
                product=contract.slug,
                release_id=request.candidate_id,
                input_release_id=request.input_release_id,
                contract_version=contract.version,
                status="blocked",
                output_table=output_table,
                git_sha=request.git_sha,
                approver=request.approver,
                checksum=checksum,
                published_at=request.evaluation_time,
                manifest={"gate": [(c.name, c.passed, c.detail) for c in gate.checks]},
            )
        )
        return PublishResult(
            request.candidate_id,
            "blocked",
            store.current_release_id(contract.slug),
            False,
        )

    # Passed: version table first (immutable, idempotent by ID), then the
    # manifest, then the view switch, then the release row. A crash between
    # table and switch is recovered by the checksum-verified adopt below.
    recorded = store.recorded_checksum(contract.slug, request.candidate_id)
    if recorded is not None and recorded != checksum:
        raise PublishConflict(
            f"version table for {request.candidate_id} exists with different content"
        )
    if recorded is None:
        store.write_version_table(contract.slug, request.candidate_id, request.rows, checksum)
    manifest = {
        "product": contract.slug,
        "data_product": contract.data_product,
        "contract_version": contract.version,
        "release_id": request.candidate_id,
        "input_release_id": request.input_release_id,
        "output_table": output_table,
        "git_sha": request.git_sha,
        "approver": request.approver,
        "checksum": checksum,
        "row_count": len(request.rows),
        "gate": [(check.name, check.passed, check.detail) for check in gate.checks],
        "published_at": request.evaluation_time.isoformat(),
    }
    if contract.record_manifest:
        store.record_manifest(manifest)
    store.point_current_view(contract.slug, request.candidate_id)
    store.insert_release_row(
        ReleaseRow(
            product=contract.slug,
            release_id=request.candidate_id,
            input_release_id=request.input_release_id,
            contract_version=contract.version,
            status="passed",
            output_table=output_table,
            git_sha=request.git_sha,
            approver=request.approver,
            checksum=checksum,
            published_at=request.evaluation_time,
            manifest=manifest,
        )
    )
    return PublishResult(request.candidate_id, "passed", request.candidate_id, True)


def withdraw(store, contract: DataProductContract, operator: str, at: datetime) -> str | None:
    """Flip the current release to withdrawn; fall back to the previous
    passed release, or to an empty authorised view if none remains."""
    product = contract.slug
    current_id = store.current_release_id(product)
    previous_passed = None
    if current_id is not None:
        store.mark_release_status(product, current_id, "withdrawn")
    for row in store.releases(product):
        if row.release_id != current_id and row.status == "passed":
            previous_passed = row.release_id
    if previous_passed is not None:
        store.point_current_view(product, previous_passed)
        return previous_passed
    schema_table = current_id and f"{contract.version_table}{current_id}"
    if schema_table:
        store.empty_current_view(product, schema_table)
    return None
