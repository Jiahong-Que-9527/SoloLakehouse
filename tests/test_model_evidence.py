from __future__ import annotations

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from governance.contracts import contract_path, load_contract
from governance.ml_lineage import MLLineageTuple
from governance.model_evidence import (
    ModelEvaluationEvidence,
    ModelEvaluationManifest,
    model_evidence_object_path,
    write_model_evaluation_manifest,
)
from governance.policy_hooks import policy_hook_from_contract
from ml.generate_model_card import build_model_card_markdown, build_model_evaluation_evidence


def _lineage(**overrides: object) -> MLLineageTuple:
    payload: dict[str, object] = {
        "iceberg_snapshot_id": "987654321",
        "dagster_run_id": "dagster-run-1",
        "feature_version": "fin.ecb_german_equity_proxy_features_gold/v1",
        "code_commit": "abc1234",
        "data_contract_hash": "0" * 64,
    }
    payload.update(overrides)
    return MLLineageTuple.model_validate(payload)


def test_model_card_includes_lineage_and_policy_context() -> None:
    contract = load_contract(contract_path("fin.ecb_german_equity_proxy_features_gold"))
    hook = policy_hook_from_contract(contract)
    lineage = _lineage(data_contract_hash=hook.contract_sha256)
    markdown = build_model_card_markdown(
        contract,
        lineage,
        hook,
        "mlflow-run-1",
        {"accuracy": 0.81, "f1": 0.77},
    )

    assert "987654321" in markdown
    assert hook.sha256() in markdown
    assert "Not a regulatory compliance claim" in markdown


def test_model_evaluation_manifest_binds_evidence_digest() -> None:
    contract = load_contract(contract_path("fin.ecb_german_equity_proxy_features_gold"))
    hook = policy_hook_from_contract(contract)
    manifest = build_model_evaluation_evidence(
        contract=contract,
        lineage=_lineage(data_contract_hash=hook.contract_sha256),
        policy_hook=hook,
        mlflow_run_id="mlflow-run-1",
        evaluation_metrics={"accuracy": 0.81, "f1": 0.77},
        generated_at=datetime(2026, 8, 2, 12, 0, tzinfo=UTC),
    )

    assert manifest.evidence_sha256 == manifest.evidence.sha256()
    assert manifest.evidence.dataset_id == "fin.ecb_german_equity_proxy_features_gold"


def test_model_evidence_path_is_stable() -> None:
    assert model_evidence_object_path(
        "fin.ecb_german_equity_proxy_features_gold",
        datetime(2026, 8, 2, tzinfo=UTC).date(),
        "dagster-run-1",
        "mlflow-run-1",
    ) == (
        "lineage/fin.ecb_german_equity_proxy_features_gold/2026-08-02/dagster-run-1/"
        "model-evidence/mlflow-run-1.json"
    )


def test_manifest_rejects_digest_mismatch() -> None:
    evidence = ModelEvaluationEvidence(
        dataset_id="fin.ecb_german_equity_proxy_features_gold",
        mlflow_run_id="mlflow-run-1",
        ml_lineage=_lineage(),
        policy_hook_sha256="1" * 64,
        evaluation_metrics={"accuracy": 0.5},
        model_card_markdown="# card",
        generated_at=datetime(2026, 8, 2, tzinfo=UTC),
    )
    with pytest.raises(ValidationError, match="does not match evidence"):
        ModelEvaluationManifest(
            evidence=evidence,
            evidence_sha256="0" * 64,
            generated_at=datetime(2026, 8, 2, tzinfo=UTC),
        )


def test_write_model_evaluation_manifest_uses_audit_bucket(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, object] = {}

    class _Client:
        def put_object(self, **kwargs: object) -> None:
            captured.update(kwargs)

    monkeypatch.setenv("AUDIT_BUCKET", "sololakehouse-audit")
    monkeypatch.setenv("S3_ACCESS_KEY", "key")
    monkeypatch.setenv("S3_SECRET_KEY", "secret")
    monkeypatch.setattr(
        "governance.emission.build_audit_s3_client",
        lambda _env: _Client(),
    )

    contract = load_contract(contract_path("fin.ecb_german_equity_proxy_features_gold"))
    hook = policy_hook_from_contract(contract)
    manifest = build_model_evaluation_evidence(
        contract=contract,
        lineage=_lineage(data_contract_hash=hook.contract_sha256),
        policy_hook=hook,
        mlflow_run_id="mlflow-run-1",
        evaluation_metrics={"accuracy": 0.81},
        generated_at=datetime(2026, 8, 2, tzinfo=UTC),
    )
    path = write_model_evaluation_manifest(manifest)

    assert captured["Bucket"] == "sololakehouse-audit"
    assert captured["Key"] == path
