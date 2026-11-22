"""Canonical serialisation shared by pin checks and dataset metadata."""

import hashlib
import json
from datetime import datetime


def canonical_checksum(payload) -> str:
    """Stable sha256 over a JSON-canonical form of the payload."""
    encoded = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        default=_isoformat,
        ensure_ascii=False,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _isoformat(value):
    if isinstance(value, datetime):
        return value.isoformat()
    raise TypeError(f"not serialisable: {type(value)}")
