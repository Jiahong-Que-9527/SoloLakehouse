"""Audit-bucket Object Lock configuration and verification helpers."""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import timedelta
from typing import Any

DEFAULT_AUDIT_OBJECT_LOCK_MODE = "GOVERNANCE"
DEFAULT_AUDIT_OBJECT_LOCK_RETENTION = "2555d"


class AuditStorageError(ValueError):
    """The audit bucket is missing or lacks the required Object Lock configuration."""

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


@dataclass(frozen=True)
class AuditObjectLockConfig:
    """Expected Object Lock settings for the entity audit bucket."""

    mode: str
    retention: str

    @classmethod
    def from_environ(cls, environ: Mapping[str, str] | None = None) -> "AuditObjectLockConfig":
        env = os.environ if environ is None else environ
        mode = env.get("AUDIT_OBJECT_LOCK_MODE", DEFAULT_AUDIT_OBJECT_LOCK_MODE).strip().upper()
        retention = env.get(
            "AUDIT_OBJECT_LOCK_RETENTION",
            DEFAULT_AUDIT_OBJECT_LOCK_RETENTION,
        ).strip()
        if mode not in {"GOVERNANCE", "COMPLIANCE"}:
            raise AuditStorageError(
                f"AUDIT_OBJECT_LOCK_MODE must be GOVERNANCE or COMPLIANCE, not {mode!r}"
            )
        if not retention:
            raise AuditStorageError("AUDIT_OBJECT_LOCK_RETENTION must not be empty")
        return cls(mode=mode, retention=retention)


def verify_audit_bucket_object_lock(
    client: Any,
    bucket: str,
    expected: AuditObjectLockConfig | None = None,
) -> AuditObjectLockConfig:
    """Verify that the audit bucket has Object Lock enabled with the expected defaults."""
    config = expected or AuditObjectLockConfig.from_environ()
    try:
        lock_config = client.get_object_lock_config(bucket)
    except Exception as exc:
        raise AuditStorageError(
            f"cannot read Object Lock config for {bucket!r}: {exc}"
        ) from exc

    mode = _lock_mode_name(lock_config)
    duration = _lock_duration(lock_config)
    if mode is None or duration is None:
        raise AuditStorageError(
            f"{bucket!r} does not have Object Lock enabled; recreate it with "
            "`mc mb --with-lock` after `make clean`"
        )

    actual_mode = mode.upper()
    if actual_mode != config.mode:
        raise AuditStorageError(
            f"{bucket!r} Object Lock mode is {actual_mode!r}, expected {config.mode!r}"
        )

    expected_duration = _parse_retention_duration(config.retention)
    if duration != expected_duration:
        raise AuditStorageError(
            f"{bucket!r} default retention is {duration!r}, expected {expected_duration!r}"
        )

    return config


def _lock_mode_name(lock_config: Any) -> str | None:
    mode = getattr(lock_config, "mode", None)
    if mode is None:
        return None
    name = getattr(mode, "name", None)
    if isinstance(name, str):
        return name
    return str(mode)


def _lock_duration(lock_config: Any) -> timedelta | None:
    duration = getattr(lock_config, "duration", None)
    if duration is None:
        return None
    if isinstance(duration, timedelta):
        return duration
    unit = str(getattr(lock_config, "duration_unit", "Days")).lower()
    if not isinstance(duration, int):
        return None
    if unit.startswith("day"):
        return timedelta(days=duration)
    if unit.startswith("year"):
        return timedelta(days=duration * 365)
    return None


def _parse_retention_duration(value: str) -> timedelta:
    if len(value) < 2 or not value[:-1].isdigit():
        raise AuditStorageError(f"invalid retention duration: {value!r}")
    amount = int(value[:-1])
    unit = value[-1].lower()
    if unit == "d":
        return timedelta(days=amount)
    if unit == "y":
        return timedelta(days=amount * 365)
    raise AuditStorageError(f"unsupported retention unit in {value!r}; use days (d) or years (y)")
