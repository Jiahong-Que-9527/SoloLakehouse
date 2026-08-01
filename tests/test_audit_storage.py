from __future__ import annotations

from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from governance.audit_storage import (
    AuditObjectLockConfig,
    AuditStorageError,
    verify_audit_bucket_object_lock,
)


def test_audit_object_lock_config_defaults() -> None:
    config = AuditObjectLockConfig.from_environ({})

    assert config.mode == "GOVERNANCE"
    assert config.retention == "2555d"


def test_verify_audit_bucket_object_lock_accepts_matching_defaults() -> None:
    client = MagicMock()
    client.get_object_lock_config.return_value = SimpleNamespace(
        mode="GOVERNANCE",
        duration=2555,
        duration_unit="Days",
    )

    config = verify_audit_bucket_object_lock(client, "sololakehouse-audit")

    assert config.mode == "GOVERNANCE"
    assert config.retention == "2555d"


def test_verify_audit_bucket_object_lock_accepts_timedelta_duration() -> None:
    client = MagicMock()
    client.get_object_lock_config.return_value = SimpleNamespace(
        mode=SimpleNamespace(name="GOVERNANCE"),
        duration=timedelta(days=2555),
    )

    verify_audit_bucket_object_lock(client, "sololakehouse-audit")


def test_verify_audit_bucket_object_lock_rejects_disabled_lock() -> None:
    client = MagicMock()
    client.get_object_lock_config.side_effect = Exception(
        "Object Lock configuration does not exist"
    )

    with pytest.raises(AuditStorageError, match="cannot read Object Lock config"):
        verify_audit_bucket_object_lock(client, "sololakehouse-audit")
