"""Tests for environment-driven runtime identity resolution."""

from __future__ import annotations

from runtime_identity import get_runtime_identity, get_trino_user


def test_default_identity_preserves_sololakehouse_baseline() -> None:
    identity = get_runtime_identity({})

    assert identity.product_id == "sololakehouse"
    assert identity.display_name == "SoloLakehouse"
    assert identity.domain == "financial_markets"
    assert identity.environment == "local"
    assert identity.runtime_version == "slh-v2.5.1"
    assert identity.compose_project_name == "sololakehouse"
    assert identity.trino_user == "sololakehouse"


def test_entity_identity_derives_safe_defaults_from_product_id() -> None:
    identity = get_runtime_identity({"PRODUCT_ID": "aviation-lakehouse"})

    assert identity.product_id == "aviation-lakehouse"
    assert identity.display_name == "Aviation Lakehouse"
    assert identity.compose_project_name == "aviation-lakehouse"
    assert identity.trino_user == "aviation_lakehouse"


def test_explicit_identity_values_override_derived_defaults() -> None:
    identity = get_runtime_identity(
        {
            "PRODUCT_ID": "finlakehouse",
            "PRODUCT_DISPLAY_NAME": "FinLakehouse",
            "PRODUCT_DOMAIN": "financial_markets",
            "ENVIRONMENT": "prod",
            "RUNTIME_VERSION": "slh-v2.5.1",
            "COMPOSE_PROJECT_NAME": "finlakehouse",
            "TRINO_USER": "finlakehouse_user",
        }
    )

    assert identity.product_id == "finlakehouse"
    assert identity.display_name == "FinLakehouse"
    assert identity.domain == "financial_markets"
    assert identity.environment == "prod"
    assert identity.runtime_version == "slh-v2.5.1"
    assert identity.compose_project_name == "finlakehouse"
    assert identity.trino_user == "finlakehouse_user"


def test_quoted_env_values_are_normalized() -> None:
    identity = get_runtime_identity(
        {
            "PRODUCT_ID": "aviation-lakehouse",
            "PRODUCT_DISPLAY_NAME": '"Aviation Lakehouse"',
            "TRINO_USER": "'aviation_lakehouse'",
        }
    )

    assert identity.display_name == "Aviation Lakehouse"
    assert identity.trino_user == "aviation_lakehouse"


def test_get_trino_user_uses_runtime_identity() -> None:
    assert get_trino_user({"PRODUCT_ID": "aviation-lakehouse"}) == "aviation_lakehouse"
