"""Run the D03 restart and replay acceptance against a new workspace schema."""

from decimal import Decimal

from cdc_delta import FAILURE, DeltaLane
from cdc_fixture import FILES, OBSERVATION, SEED, fixture
from financial_cdc import digest


def offsets(path):
    return sorted(int(entry.name) for entry in path.iterdir() if entry.name.isdecimal())


def checkpoint(lane, mode):
    if mode == "stream":
        path = lane.checkpoints / "apply"
        return {
            "path": str(path),
            "offsets": offsets(path / "offsets"),
            "commits": offsets(path / "commits"),
        }
    path = lane.checkpoints / "batch_apply"
    return {"path": str(path), "commits": sorted(file.name for file in path.glob("*.json"))}


def compact(snapshot):
    state, events, gold, counts = snapshot
    rows = sorted(
        (kind, key, seq, str(amount) if amount is not None else None, deleted)
        for (kind, key), (seq, amount, deleted) in state.items()
    )
    return {
        "counts": counts,
        "state_sha256": digest(rows),
        "gold": {
            key: {"transactions": n, "amount": str(amount)} for key, (n, amount) in gold.items()
        },
        "transactions": {
            key: {
                "sequence": seq,
                "amount": str(amount) if amount is not None else None,
                "deleted": deleted,
            }
            for kind, key, seq, amount, deleted in rows
            if key in {"tx-focus", "tx-withdrawn", OBSERVATION}
        },
        "outcomes": {
            outcome: sum(row[2] == outcome for row in events.values())
            for outcome in ("applied", "duplicate", "ignored", "conflict")
        },
    }


def run_acceptance(spark, catalog, schema, mode):
    if mode not in {"stream", "batch"}:
        raise ValueError("mode must be stream or batch")
    files, oracle = fixture()
    primary = DeltaLane(spark, catalog, schema, "primary")
    if any(primary.input.iterdir()) or primary.spark.table(primary.journal).limit(1).count():
        raise ValueError("use a fresh D03 schema for this acceptance run")
    ingest, apply = (
        (primary.stream_bronze, primary.stream_apply)
        if mode == "stream"
        else (primary.batch_bronze, primary.batch_apply)
    )

    hashes = {FILES[0]: primary.land(FILES[0], files[FILES[0]])}
    first_bronze, first_apply = ingest(), apply()
    first_checkpoint = checkpoint(primary, mode)
    first_snapshot = primary.snapshot()
    assert first_snapshot[0][("transaction", "tx-focus")] == (2, Decimal("12"), False)
    assert first_snapshot[3]["bronze"] == len(files[FILES[0]])

    hashes[FILES[1]] = primary.land(FILES[1], files[FILES[1]])
    second_bronze = ingest()
    assert checkpoint(primary, mode) == first_checkpoint
    crashed = apply(crash=True)
    assert crashed.get("failure") == FAILURE
    failed_checkpoint = checkpoint(primary, mode)
    assert failed_checkpoint["commits"] == first_checkpoint["commits"]
    if mode == "stream":
        assert failed_checkpoint["offsets"][:-1] == first_checkpoint["offsets"]
    failed_snapshot = primary.snapshot()
    failed_versions = primary.versions()
    assert failed_snapshot[0][("transaction", "tx-focus")] == (4, None, True)
    assert compact(failed_snapshot)["outcomes"]["conflict"] == 1

    resumed = apply()
    resumed_checkpoint = checkpoint(primary, mode)
    if mode == "stream":
        assert first_apply["query_id"] == crashed["query_id"] == resumed["query_id"]
        assert first_bronze["query_id"] == second_bronze["query_id"]
        assert first_apply["run_id"] != resumed["run_id"]
        assert resumed["batch_id"] == failed_checkpoint["offsets"][-1]
    assert len(resumed_checkpoint["commits"]) == len(first_checkpoint["commits"]) + 1
    assert primary.snapshot() == failed_snapshot
    assert primary.versions() == failed_versions

    hashes[FILES[2]] = primary.land(FILES[2], files[FILES[2]])
    third_bronze, third_apply = ingest(), apply()
    deleted = primary.snapshot()
    assert deleted[0][("transaction", "tx-focus")] == (4, None, True)
    assert deleted[0][("transaction", "tx-withdrawn")] == (3, None, True)
    assert deleted[0][("observation", OBSERVATION)] == (2, Decimal("1.0425"), False)
    assert deleted[2]["EUR"] == (160, first_snapshot[2]["EUR"][1] - Decimal("32"))
    assert deleted[3]["current"] == 160

    hashes[FILES[3]] = primary.land(FILES[3], files[FILES[3]])
    last_bronze, last_apply = ingest(), apply()
    final_checkpoint = checkpoint(primary, mode)
    final = primary.snapshot()
    expected = {
        key: (seq, Decimal(amount) if amount is not None else None, tombstone)
        for key, (seq, amount, tombstone) in oracle.items()
    }
    expected_amounts = [
        amount
        for (kind, _), (_, amount, tombstone) in expected.items()
        if kind == "transaction" and not tombstone
    ]
    assert final[0] == expected
    assert final[2] == {"EUR": (len(expected_amounts), sum(expected_amounts))}
    assert final[3]["bronze"] == len(final[1]) == sum(map(len, files.values()))
    assert final[3]["rejects"] == 2
    events = compact(final)["outcomes"]
    assert events == {"applied": 184, "duplicate": 2, "ignored": 2, "conflict": 2}, events
    assert final[3]["history"] == len(final[1]) - 2
    assert final[3]["current"] == len(expected_amounts)

    comparisons = {}
    for lane_name, compare_mode in (("uninterrupted", mode), ("replay", "batch")):
        lane = DeltaLane(spark, catalog, schema, lane_name)
        assert {name: lane.land(name, files[name]) for name in FILES} == hashes
        bronze = lane.stream_bronze() if compare_mode == "stream" else lane.batch_bronze()
        applied = lane.stream_apply() if compare_mode == "stream" else lane.batch_apply()
        comparison = lane.snapshot()
        assert comparison[0] == final[0] and comparison[2] == final[2]
        assert comparison[3]["bronze"] == final[3]["bronze"]
        comparisons[lane_name] = {
            "mode": compare_mode,
            "checkpoint": checkpoint(lane, compare_mode),
            "bronze": bronze,
            "apply": applied,
            "versions": lane.versions(),
            "result": compact(comparison),
        }

    return {
        "mode": mode,
        "seed": SEED,
        "schema": f"{catalog}.{schema}",
        "source_files": hashes,
        "versions": primary.versions(),
        "committed_restart": {
            "after_first_commit": first_checkpoint,
            "bronze_first": first_bronze,
            "apply_first": first_apply,
            "bronze_second": second_bronze,
        },
        "pre_ack_fault": {
            "injected": crashed,
            "failed_checkpoint": failed_checkpoint,
            "after_resume": resumed,
            "resumed_checkpoint": resumed_checkpoint,
            "versions_preserved_at_resume": failed_versions,
            "snapshot_preserved_at_resume": compact(failed_snapshot),
        },
        "delete_and_late_change": {
            "snapshot": compact(deleted),
            "bronze": third_bronze,
            "apply": third_apply,
        },
        "final_checkpoint": final_checkpoint,
        "final_bronze": last_bronze,
        "final_apply": last_apply,
        "result": compact(final),
        "comparisons": comparisons,
    }
