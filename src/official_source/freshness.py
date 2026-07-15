"""Freshness metadata: retrieved-at timestamps and fresh/stale assessment.

Deterministic tests must inject ``evaluated_at`` (or a clock callable) and
must not depend on the real wall clock.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Callable, Final

from .models import FreshnessStatus
from .policy import DEFAULT_CLOCK_SKEW_SECONDS, DEFAULT_MAX_AGE_SECONDS

Clock = Callable[[], datetime]


class InvalidTimestampError(ValueError):
    """Raised when a retrieved-at / evaluated-at timestamp cannot be used."""


def parse_utc_timestamp(value: str) -> datetime:
    """Parse an ISO-8601 UTC timestamp into an aware datetime.

    Accepts ``...Z`` and ``...+00:00`` (optional fractional seconds).
    Rejects naive timestamps, empty strings, and non-UTC offsets.
    """
    if not isinstance(value, str) or not value.strip():
        raise InvalidTimestampError("timestamp must be a non-empty string")
    raw = value.strip()
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
    retrieved_at: str | None,
    max_age_seconds: int = DEFAULT_MAX_AGE_SECONDS,
    evaluated_at: str | None = None,
    clock: Clock | None = None,
    clock_skew_seconds: int = DEFAULT_CLOCK_SKEW_SECONDS,
) -> FreshnessAssessment:
    """Compare retrieval time to an evaluation clock and max age.

    * Missing ``retrieved_at`` → status ``unknown`` (caller may fail closed).
    * Unparseable / naive / beyond skew future → raises ``InvalidTimestampError``
      (caller maps to ``invalid`` freshness + ``invalid_timestamp`` failure).
    """
    if not isinstance(max_age_seconds, int) or isinstance(max_age_seconds, bool):
        raise InvalidTimestampError("max_age_seconds must be an int")
    if max_age_seconds < 0:
        raise InvalidTimestampError("max_age_seconds must be >= 0")
    if not isinstance(clock_skew_seconds, int) or clock_skew_seconds < 0:
        raise InvalidTimestampError("clock_skew_seconds must be an int >= 0")

    if evaluated_at:
        evaluated = parse_utc_timestamp(evaluated_at)
        evaluated_label = format_utc_timestamp(evaluated)
    elif clock is not None:
        evaluated = clock()
        if evaluated.tzinfo is None:
            raise InvalidTimestampError("clock must return timezone-aware datetime")
        evaluated = evaluated.astimezone(timezone.utc)
        evaluated_label = format_utc_timestamp(evaluated)
    else:
        # Production fallback only — tests must inject evaluated_at/clock.
        evaluated = datetime.now(timezone.utc)
        evaluated_label = format_utc_timestamp(evaluated)

    if retrieved_at is None or (isinstance(retrieved_at, str) and not retrieved_at.strip()):
        return FreshnessAssessment(
            status=FreshnessStatus.UNKNOWN,
            age_seconds=None,
            max_age_seconds=max_age_seconds,
            retrieved_at="",
            evaluated_at=evaluated_label,
        )

    retrieved = parse_utc_timestamp(retrieved_at)
    age = (evaluated - retrieved).total_seconds()
    if age < -float(clock_skew_seconds):
        raise InvalidTimestampError(
            "retrieved_at is in the future beyond allowed clock skew"
        )
    if age < 0:
        age = 0.0

    status = FreshnessStatus.FRESH if age <= max_age_seconds else FreshnessStatus.STALE
    return FreshnessAssessment(
        status=status,
        age_seconds=age,
        max_age_seconds=max_age_seconds,
        retrieved_at=format_utc_timestamp(retrieved),
        evaluated_at=evaluated_label,
    )


__all__ = [
    "Clock",
    "DEFAULT_MAX_AGE_SECONDS",
    "FreshnessAssessment",
    "InvalidTimestampError",
    "assess_freshness",
    "format_utc_timestamp",
    "parse_utc_timestamp",
]
