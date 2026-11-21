"""The release boundary: publish, block, retry, withdraw (design section 5)."""

from datetime import UTC, datetime

import pytest

from conftest import load_contracts
from energy_product.fixture import (
    GOOD_CANDIDATE,
    GOOD_INPUT_RELEASE,
    candidate_metadata,
    candidate_rows,
    expected_grid,
    stale_metadata,
    with_duplicate_masking_missing,
    with_null_value,
)
from energy_product.publisher import PublishConflict, PublishRequest, publish, withdraw
from energy_product.store import InMemoryProductStore

CONTRACT, _, _ = load_contracts()
GRID = expected_grid()
META = candidate_metadata()


def make_request(candidate_id=GOOD_CANDIDATE, rows=None, approved=True, metadata=None, **overrides):
    values = dict(
        product=CONTRACT.slug,
        candidate_id=candidate_id,
        input_release_id=GOOD_INPUT_RELEASE,
        contract=CONTRACT,
        rows=rows if rows is not None else candidate_rows(GRID),
        expected_grid=GRID,
        ingested_at=(metadata or META)["ingested_at"],
        evaluation_time=(metadata or META)["evaluation_time"],
        git_sha="abc1234",
        approver="owner",
        approved=approved,
    )
    values.update(overrides)
    return PublishRequest(**values)


def test_unapproved_candidate_cannot_publish():
    store = InMemoryProductStore()
    with pytest.raises(PermissionError, match="not approved"):
        publish(store, make_request(approved=False))
    assert store.current_release_id("energy_load") is None
    assert store.releases("energy_load") == ()


def test_publish_good_candidate_passes_and_records_everything():
    store = InMemoryProductStore()
    result = publish(store, make_request())

    assert result.status == "passed"
    assert store.current_release_id("energy_load") == GOOD_CANDIDATE
    assert len(store.current_rows("energy_load")) == len(GRID)
    release = store.release_row("energy_load", GOOD_CANDIDATE)
    assert release.status == "passed"
    assert release.input_release_id == GOOD_INPUT_RELEASE
    assert release.contract_version == "1.0.0"
    assert release.git_sha == "abc1234"
    assert release.approver == "owner"
    assert release.output_table == f"energy_load_v{GOOD_CANDIDATE}"
    (manifest,) = store.manifests("energy_load")
    assert manifest["input_release_id"] == GOOD_INPUT_RELEASE
    assert manifest["git_sha"] == "abc1234"
    assert manifest["contract_version"] == "1.0.0"
    assert manifest["approver"] == "owner"
    assert all(passed for _, passed, _ in manifest["gate"])


def test_blocked_candidate_writes_quarantine_and_keeps_the_previous_release_current():
    store = InMemoryProductStore()
    publish(store, make_request())  # v1 passes and becomes current

    bad_rows = with_duplicate_masking_missing(candidate_rows(GRID))
    result = publish(store, make_request(candidate_id="cand-bad-0002", rows=bad_rows))

    assert result.status == "blocked"
    # The published view is unchanged and the previous release stays queryable.
    assert store.current_release_id("energy_load") == GOOD_CANDIDATE
    assert len(store.current_rows("energy_load")) == len(GRID)
    # The failed gate result is queryable: quarantine rows + blocked release row.
    checks = {row["check"] for row in store.quarantine("energy_load")}
    assert {"grain_uniqueness", "completeness"} <= checks
    blocked = store.release_row("energy_load", "cand-bad-0002")
    assert blocked.status == "blocked"
    assert blocked.checksum


def test_a_null_measure_candidate_is_blocked():
    store = InMemoryProductStore()
    publish(store, make_request())
    result = publish(
        store,
        make_request(candidate_id="cand-null-0003", rows=with_null_value(candidate_rows(GRID))),
    )
    assert result.status == "blocked"
    assert {row["check"] for row in store.quarantine("energy_load")} >= {"value_range"}


def test_a_stale_candidate_is_blocked():
    store = InMemoryProductStore()
    result = publish(store, make_request(candidate_id="cand-stale-0004", metadata=stale_metadata()))
    assert result.status == "blocked"
    assert {row["check"] for row in store.quarantine("energy_load")} >= {"freshness"}


def test_retry_with_the_same_candidate_id_and_content_is_idempotent():
    store = InMemoryProductStore()
    first = publish(store, make_request())
    again = publish(store, make_request())
    assert first.release_id == again.release_id == GOOD_CANDIDATE
    assert len(store.manifests("energy_load")) == 1
    assert len(store.current_rows("energy_load")) == len(GRID)


def test_retry_with_the_same_candidate_id_but_different_content_is_a_conflict():
    store = InMemoryProductStore()
    publish(store, make_request())
    tampered = candidate_rows(GRID)
    tampered[0]["value"] = 42.0
    with pytest.raises(PublishConflict, match="fresh ID"):
        publish(store, make_request(rows=tampered))


def test_crash_between_version_table_and_view_switch_recovers_on_retry():
    store = InMemoryProductStore(fail_view_switch=1)
    with pytest.raises(RuntimeError, match="view switch"):
        publish(store, make_request())
    # The table exists and is recorded; the view still points at nothing.
    assert len(store.version_rows("energy_load", GOOD_CANDIDATE)) == len(GRID)
    assert store.current_release_id("energy_load") is None

    result = publish(store, make_request())  # same candidate ID, same content
    assert result.status == "passed"
    assert store.current_release_id("energy_load") == GOOD_CANDIDATE
    assert len(store.manifests("energy_load")) == 1
    assert len(store.releases("energy_load")) == 1


def test_withdraw_falls_back_to_the_previous_passed_release():
    store = InMemoryProductStore()
    publish(store, make_request())  # cand-good-0001
    publish(
        store, make_request(candidate_id="cand-good-0002", rows=candidate_rows(expected_grid()))
    )
    assert store.current_release_id("energy_load") == "cand-good-0002"

    fallback = withdraw(store, CONTRACT, operator="owner", at=datetime.now(UTC))

    assert fallback == GOOD_CANDIDATE
    assert store.current_release_id("energy_load") == GOOD_CANDIDATE
    assert store.release_row("energy_load", "cand-good-0002").status == "withdrawn"
    assert store.release_row("energy_load", GOOD_CANDIDATE).status == "passed"
    # A republish uses a fresh ID; the withdrawn id is never reused.
    fresh_id = "cand-good-0003"
    publish(store, make_request(candidate_id=fresh_id, rows=candidate_rows(expected_grid())))
    assert store.current_release_id("energy_load") == fresh_id
    assert store.release_row("energy_load", "cand-good-0002").status == "withdrawn"


def test_withdraw_without_a_previous_release_leaves_an_empty_authorised_view():
    store = InMemoryProductStore()
    publish(store, make_request())
    assert store.current_release_id("energy_load") == GOOD_CANDIDATE

    fallback = withdraw(store, CONTRACT, operator="owner", at=datetime.now(UTC))

    assert fallback is None
    assert store.current_release_id("energy_load") is None
    assert store.current_rows("energy_load") == []
    assert store.empty_view_schema_table("energy_load") == f"energy_load_v{GOOD_CANDIDATE}"
    assert store.release_row("energy_load", GOOD_CANDIDATE).status == "withdrawn"
