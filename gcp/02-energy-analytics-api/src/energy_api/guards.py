"""Request validation and query guards (plan Task 1.3).

One entry point, one precedence: parameters, then range, then span.
Release existence is deliberately NOT checked here — an unpublished
metric is a route-level 404, and the span guard must outrank it there
(review focus #3).
"""

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

_AREA = "DE"


@dataclass(frozen=True)
class QueryGuard:
    """Design §4 initial values."""

    max_span_days: int = 31
    timeout_seconds: int = 15
    max_bytes_billed: int = 1_000_000_000


class ValidationError(Exception):
    """A request that never reaches the data layer; carries the error code."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


def _parse_utc(value: str, field: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value)
    except (TypeError, ValueError) as exc:
        message = f"{field} must be an ISO-8601 timestamp"
        raise ValidationError(code="invalid_parameters", message=message) from exc
    if parsed.tzinfo is None:
        message = f"{field} must carry a UTC offset"
        raise ValidationError(code="invalid_parameters", message=message)
    return parsed.astimezone(UTC)


def validate_request(
    area: str,
    metric: str,
    from_s: str,
    to_s: str,
    guard: QueryGuard,
) -> tuple[str, str, datetime, datetime]:
    """Validate one metrics/summary request; returns normalised fields."""
    if area != _AREA:
        message = f"area must be '{_AREA}' in v1"
        raise ValidationError(code="invalid_parameters", message=message)
    if not metric:
        message = "metric is required"
        raise ValidationError(code="invalid_parameters", message=message)

    start = _parse_utc(from_s, "from")
    end = _parse_utc(to_s, "to")

    if start >= end:
        message = "from must be earlier than to"
        raise ValidationError(code="invalid_range", message=message)

    if end - start > timedelta(days=guard.max_span_days):
        message = f"span exceeds {guard.max_span_days} days"
        raise ValidationError(code="query_rejected", message=message)

    return area, metric, start, end
