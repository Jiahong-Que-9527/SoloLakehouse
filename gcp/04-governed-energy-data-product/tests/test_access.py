"""Role policy: the local specification of the IAM grants the cloud must
create (design section 1; acceptance 2). The access tests prove the
mapping — the live IAM proof happens against the deployed resources."""

import pytest

from conftest import GOOD_CANDIDATE, load_contracts
from energy_product.fixture import candidate_rows, expected_grid
from energy_product.publisher import publish
from energy_product.store import (
    AccessDenied,
    InMemoryProductStore,
    Role,
    Surface,
)

CONTRACT, _, _ = load_contracts()
GRID = expected_grid()


def make_store_with_release():
    store = InMemoryProductStore()
    from datetime import UTC, datetime

    from energy_product.publisher import PublishRequest

    publish(
        store,
        PublishRequest(
            product=CONTRACT.slug,
            candidate_id=GOOD_CANDIDATE,
            input_release_id="input-week-672",
            contract=CONTRACT,
            rows=candidate_rows(GRID),
            expected_grid=GRID,
            ingested_at=datetime(2026, 6, 15, 1, 0, tzinfo=UTC),
            evaluation_time=datetime(2026, 6, 15, 2, 0, tzinfo=UTC),
            git_sha="abc1234",
            approver="owner",
            approved=True,
        ),
    )
    return store


def test_analyst_reads_the_published_view_and_is_denied_source_and_quarantine():
    store = make_store_with_release()
    rows = store.read_as(
        Role.ANALYST, Surface.CURRENT_VIEW, lambda: store.current_rows("energy_load")
    )
    assert len(rows) == len(GRID)
    with pytest.raises(AccessDenied, match="analyst may not read source"):
        store.read_as(Role.ANALYST, Surface.SOURCE, lambda: [])
    with pytest.raises(AccessDenied, match="analyst may not read quarantine"):
        store.read_as(Role.ANALYST, Surface.QUARANTINE, lambda: [])


def test_auditor_reads_the_release_ledger_and_cannot_read_observations():
    store = make_store_with_release()
    releases = store.read_as(
        Role.AUDITOR, Surface.RELEASE_LEDGER, lambda: store.releases("energy_load")
    )
    assert [row.release_id for row in releases] == [GOOD_CANDIDATE]
    with pytest.raises(AccessDenied, match="auditor may not read current_view"):
        store.read_as(Role.AUDITOR, Surface.CURRENT_VIEW, lambda: [])


def test_producer_reads_everything_but_the_policy_has_no_write_surfaces_for_readers():
    store = make_store_with_release()
    assert store.read_as(Role.PRODUCER, Surface.SOURCE, lambda: ["x"]) == ["x"]
    assert store.read_as(Role.PRODUCER, Surface.QUARANTINE, lambda: ["x"]) == ["x"]
    # The analyst's grant set is exactly the published view.
    assert Role.ANALYST in {
        role
        for role, surfaces in {r: s for r, s in _policy_items()}.items()
        if surfaces == frozenset({Surface.CURRENT_VIEW})
    }


def _policy_items():
    from energy_product.store import ROLE_POLICY

    return ROLE_POLICY.items()
