from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest
from pydantic import ValidationError

from governance.contracts import contract_path, load_contract
from governance.ml_lineage import (
    MLLineageError,
    MLLineageTuple,
    bind_mlflow_run,
    build_ml_lineage_tuple,
    contract_content_sha256,
    mlflow_tags_for_tuple,
    resolve_code_commit,
)


def _tuple(**overrides: object) -> MLLineageTuple:
    payload: dict[str, object] = {
        "iceberg_snapshot_id": "987654321",
        "dagster_run_id": "dagster-run-1",
        "feature_version": "fin.ecb_german_equity_proxy_features_gold/v1",
        "code_commit": "abc1234",
        "data_contract_hash": "0" * 64,
    }
    payload.update(overrides)
    return MLLineageTuple.model_validate(payload)


def test_build_ml_lineage_tuple_resolves_code_commit_from_env() -> None:
    lineage = build_ml_lineage_tuple(
        iceberg_snapshot_id="111",
        dagster_run_id="run-1",
        feature_version="v1",
        data_contract_hash="f" * 64,
        code_commit="deadbeef",
    )

    assert lineage.code_commit == "deadbeef"
    assert lineage.sha256() == lineage.sha256()


def test_resolve_code_commit_uses_git_commit_env() -> None:
    assert resolve_code_commit({"GIT_COMMIT": "AbCdEf1"}) == "abcdef1"


def test_resolve_code_commit_raises_when_unavailable(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("GIT_COMMIT", raising=False)
    monkeypatch.setattr(
        "governance.ml_lineage.subprocess.run",
        MagicMock(side_effect=FileNotFoundError("git")),
    )

    with pytest.raises(MLLineageError, match="code_commit"):
        resolve_code_commit({})


def test_contract_content_sha256_is_stable() -> None:
    contract = load_contract(contract_path("fin.ecb_german_equity_proxy_features_gold"))
    first = contract_content_sha256(contract)
    second = contract_content_sha256(contract)

    assert first == second
    assert len(first) == 64


def test_mlflow_tags_include_schema_and_digest() -> None:
    lineage = _tuple()
    tags = mlflow_tags_for_tuple(lineage)

    assert tags["slh.ml_lineage_schema"] == "v1"
    assert tags["slh.ml_lineage_sha256"] == lineage.sha256()
    assert tags["slh.iceberg_snapshot_id"] == "987654321"


def test_bind_mlflow_run_uses_run_set_tag_when_available() -> None:
    lineage = _tuple()
    run = MagicMock()

    bind_mlflow_run(run, lineage)

    assert run.set_tag.call_count == len(mlflow_tags_for_tuple(lineage))


def test_makefile_rejects_dirty_dagster_build_inputs() -> None:
    makefile = Path("Makefile").read_text(encoding="utf-8")

    assert "check-git-lineage:" in makefile
    assert "git diff --quiet -- $(LINEAGE_BUILD_INPUTS)" in makefile
    assert "git ls-files --others --exclude-standard -- $(LINEAGE_BUILD_INPUTS)" in makefile
    assert "up: check-git-lineage prepare-data-dirs" in makefile


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("dagster_run_id", "run/1", "cannot contain path separators"),
        ("code_commit", "not-a-sha", "git commit hash"),
        ("data_contract_hash", "short", "String should match pattern"),
    ],
)
def test_ml_lineage_tuple_rejects_invalid_values(
    field: str, value: object, message: str
) -> None:
    with pytest.raises(ValidationError, match=message):
        _tuple(**{field: value})
