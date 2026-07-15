"""Result schema and fail-closed error taxonomy for official-source freshness.

All unsuccessful paths return a structured ``OfficialSourceResult`` with
``success=False`` and a closed-vocabulary ``error_code``. Callers must never
invent civic facts when the boundary fails closed.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any, Final, Mapping


class FactKind(str, Enum):
    """Narrow Phase-1 fact vocabulary (not arbitrary web search)."""

    CURRENT_MAYOR = "current_mayor"
    JURISDICTION_NAME = "jurisdiction_name"


class FreshnessStatus(str, Enum):
    FRESH = "fresh"
    STALE = "stale"
    UNKNOWN = "unknown"


class ErrorCode(str, Enum):
    """Closed fail-closed taxonomy. Every failure maps to exactly one code."""

    UNSUPPORTED_QUESTION = "unsupported_question"
    NON_ALLOWLISTED_URL = "non_allowlisted_url"
    MISSING_SOURCE = "missing_source"
    TRANSPORT_FAILURE = "transport_failure"
    TRANSPORT_TIMEOUT = "transport_timeout"
    MALFORMED_HTML = "malformed_html"
    FACT_ABSENT = "fact_absent"
    AMBIGUOUS_VALUE = "ambiguous_value"
    STALE_RETRIEVAL = "stale_retrieval"
    INVALID_TIMESTAMP = "invalid_timestamp"
    UNEXPECTED_REDIRECT = "unexpected_redirect"
    EXTERNAL_ORIGIN = "external_origin"
    INTERNAL_ERROR = "internal_error"


ERROR_CODES: Final[frozenset[str]] = frozenset(code.value for code in ErrorCode)


@dataclass(frozen=True)
class OfficialSourceRequest:
    """Retrieval request model (classification output + optional overrides)."""

    question: str
    fact_kind: FactKind | None = None
    # Optional evaluation clock for deterministic tests (ISO-8601 UTC).
    evaluated_at: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "question": self.question,
            "fact_kind": self.fact_kind.value if self.fact_kind else None,
            "evaluated_at": self.evaluated_at,
        }


@dataclass(frozen=True)
class SourceMetadata:
    """Official source URL/title and retrieval timestamp metadata."""

    url: str
    title: str
    retrieved_at: str
    final_url: str | None = None
    content_type: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "url": self.url,
            "title": self.title,
            "retrieved_at": self.retrieved_at,
            "final_url": self.final_url,
            "content_type": self.content_type,
        }


@dataclass(frozen=True)
class FactValue:
    """Normalized civic fact extracted from an official source."""

    kind: FactKind
    value: str
    raw_value: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind.value,
            "value": self.value,
            "raw_value": self.raw_value,
        }


@dataclass(frozen=True)
class OfficialSourceResult:
    """Answer payload for official-source freshness retrieval.

    Successful results always include fact + source + freshness.
    Unsuccessful results never include a guessed ``fact``.
    """

    success: bool
    fact_kind: FactKind | None = None
    fact: FactValue | None = None
    source: SourceMetadata | None = None
    freshness_status: FreshnessStatus = FreshnessStatus.UNKNOWN
    max_age_seconds: int | None = None
    age_seconds: float | None = None
    error_code: ErrorCode | None = None
    error_message: str = ""
    warnings: tuple[str, ...] = field(default_factory=tuple)
    schema_version: str = "1.0.0"

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "success": self.success,
            "fact_kind": self.fact_kind.value if self.fact_kind else None,
            "fact": self.fact.to_dict() if self.fact else None,
            "source": self.source.to_dict() if self.source else None,
            "freshness_status": self.freshness_status.value,
            "max_age_seconds": self.max_age_seconds,
            "age_seconds": self.age_seconds,
            "error_code": self.error_code.value if self.error_code else None,
            "error_message": self.error_message,
            "warnings": list(self.warnings),
        }


def result_from_mapping(data: Mapping[str, Any]) -> OfficialSourceResult:
    """Rebuild a result from a dict (tests / serialization helpers only)."""
    fact_kind_raw = data.get("fact_kind")
    fact_kind = FactKind(fact_kind_raw) if fact_kind_raw else None
    fact_raw = data.get("fact")
    fact = None
    if isinstance(fact_raw, Mapping) and fact_kind is not None:
        fact = FactValue(
            kind=FactKind(fact_raw["kind"]),
            value=str(fact_raw["value"]),
            raw_value=str(fact_raw.get("raw_value", fact_raw["value"])),
        )
    source_raw = data.get("source")
    source = None
    if isinstance(source_raw, Mapping):
        source = SourceMetadata(
            url=str(source_raw["url"]),
            title=str(source_raw.get("title", "")),
            retrieved_at=str(source_raw["retrieved_at"]),
            final_url=source_raw.get("final_url"),
            content_type=source_raw.get("content_type"),
        )
    error_raw = data.get("error_code")
    return OfficialSourceResult(
        success=bool(data.get("success")),
        fact_kind=fact_kind,
        fact=fact,
        source=source,
        freshness_status=FreshnessStatus(data.get("freshness_status", "unknown")),
        max_age_seconds=data.get("max_age_seconds"),
        age_seconds=data.get("age_seconds"),
        error_code=ErrorCode(error_raw) if error_raw else None,
        error_message=str(data.get("error_message", "")),
        warnings=tuple(data.get("warnings") or ()),
        schema_version=str(data.get("schema_version", "1.0.0")),
    )


def unsuccessful(
    *,
    error_code: ErrorCode,
    error_message: str,
    fact_kind: FactKind | None = None,
    source: SourceMetadata | None = None,
    freshness_status: FreshnessStatus = FreshnessStatus.UNKNOWN,
    max_age_seconds: int | None = None,
    age_seconds: float | None = None,
    warnings: tuple[str, ...] = (),
) -> OfficialSourceResult:
    """Construct a fail-closed unsuccessful result (never attaches a fact)."""
    return OfficialSourceResult(
        success=False,
        fact_kind=fact_kind,
        fact=None,
        source=source,
        freshness_status=freshness_status,
        max_age_seconds=max_age_seconds,
        age_seconds=age_seconds,
        error_code=error_code,
        error_message=error_message,
        warnings=warnings,
    )


def successful(
    *,
    fact: FactValue,
    source: SourceMetadata,
    freshness_status: FreshnessStatus,
    max_age_seconds: int,
    age_seconds: float | None,
    warnings: tuple[str, ...] = (),
) -> OfficialSourceResult:
    return OfficialSourceResult(
        success=True,
        fact_kind=fact.kind,
        fact=fact,
        source=source,
        freshness_status=freshness_status,
        max_age_seconds=max_age_seconds,
        age_seconds=age_seconds,
        error_code=None,
        error_message="",
        warnings=warnings,
    )


# Keep asdict available for callers that prefer stdlib dataclasses export.
__all__ = [
    "ERROR_CODES",
    "ErrorCode",
    "FactKind",
    "FactValue",
    "FreshnessStatus",
    "OfficialSourceRequest",
    "OfficialSourceResult",
    "SourceMetadata",
    "asdict",
    "result_from_mapping",
    "successful",
    "unsuccessful",
]
