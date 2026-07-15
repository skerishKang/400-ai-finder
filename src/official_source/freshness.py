"""Freshness metadata: retrieved-at timestamps and fresh/stale assessment."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Final

from .models import FreshnessStatus

_ISO_Z_RE_SUFFIX: Final[str] = "Z"


class InvalidTimestampError(ValueError):
    """Raised when a retrieved-at / evaluated-at timestamp cannot be parsed."""


def parse_utc_timestamp(value: str) -> datetime:
    """Parse an ISO-8601 UTC timestamp into an aware datetime.

    Accepts:
      * ``2026-07-15T06:37:53Z``
      * ``2026-07-15T06:37:53+00:00``
      * ``2026-07-15T06:37:53.848Z``

    Rejects naive timestamps, empty strings, and non-UTC offsets.
    """
    if not isinstance(value, str) or not value.strip():
        raise InvalidTimestampError("timestamp must be a non-empty string")
    raw = value.strip()
    # Normalize trailing Z to +00:00 for fromisoformat.
    if raw.endswith("Z"):
        raw = raw[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(raw)
    except ValueError as exc:
        raise InvalidTimestampError(f"invalid ISO-8601 timestamp: {value!r}") from exc
    if dt.tzinfo is None:
        raise InvalidTimestampError("timestamp must be timezone-aware UTC")
    offset = dt.utcoffset()
    if offset is None or offset.total_seconds() != 0:
        raise InvalidTimestampError("timestamp must be UTC (offset +00:00)")
    return dt.astimezone(timezone.utc)


def format_utc_timestamp(dt: datetime) -> str:
    if dt.tzinfo is None:
        raise InvalidTimestampError("datetime must be timezone-aware")
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


@dataclass(frozen=True)
class FreshnessAssessment:
    status: FreshnessStatus
    age_seconds: float | None
    max_age_seconds: int
    retrieved_at: str
    evaluated_at: str

    def to_dict(self) -> dict[str, object]:
        return {
            "status": self.status.value,
            "age_seconds": self.age_seconds,
            "max_age_seconds": self.max_age_seconds,
            "retrieved_at": self.retrieved_at,
            "evaluated_at": self.evaluated_at,
        }


def assess_freshness(
    *,
    retrieved_at: str,
    max_age_seconds: int,
    evaluated_at: str | None = None,
) -> FreshnessAssessment:
    """Compare retrieval time to evaluation clock and max age.

    Raises ``InvalidTimestampError`` for unusable timestamps.
    """
    if not isinstance(max_age_seconds, int) or isinstance(max_age_seconds, bool):
        raise InvalidTimestampError("max_age_seconds must be an int")
    if max_age_seconds < 0:
        raise InvalidTimestampError("max_age_seconds must be >= 0")

    retrieved = parse_utc_timestamp(retrieved_at)
    if evaluated_at is None or evaluated_at == "":
        evaluated = datetime.now(timezone.utc)
        evaluated_label = format_utc_timestamp(evaluated)
    else:
        evaluated = parse_utc_timestamp(evaluated_at)
        evaluated_label = format_utc_timestamp(evaluated)

    age = (evaluated - retrieved).total_seconds()
    if age < 0:
        # Future retrieval clock is treated as invalid metadata.
        raise InvalidTimestampError("retrieved_at is in the future relative to evaluated_at")

    status = FreshnessStatus.FRESH if age <= max_age_seconds else FreshnessStatus.STALE
    return FreshnessAssessment(
        status=status,
        age_seconds=age,
        max_age_seconds=max_age_seconds,
        retrieved_at=format_utc_timestamp(retrieved),
        evaluated_at=evaluated_label,
    )


__all__ = [
    "FreshnessAssessment",
    "InvalidTimestampError",
    "assess_freshness",
    "format_utc_timestamp",
    "parse_utc_timestamp",
]
