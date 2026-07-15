"""Result schema and fail-closed error taxonomy for official-source freshness.

Aligned with repository structured-result conventions (dataclasses, closed
vocab failure codes, public-safe messages). Failures never invent civic facts.
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
    INVALID = "invalid"


class ErrorCode(str, Enum):
    """Closed fail-closed taxonomy (Phase-1 public contract)."""

    UNSUPPORTED_QUESTION = "unsupported_question"
    INVALID_REQUEST = "invalid_request"
    SOURCE_NOT_ALLOWLISTED = "source_not_allowlisted"
    EXTERNAL_REDIRECT = "external_redirect"
    TRANSPORT_TIMEOUT = "transport_timeout"
    TRANSPORT_ERROR = "transport_error"
    HTTP_ERROR = "http_error"
    INVALID_CONTENT_TYPE = "invalid_content_type"
    EMPTY_CONTENT = "empty_content"
    MALFORMED_CONTENT = "malformed_content"
    SOURCE_IDENTITY_MISMATCH = "source_identity_mismatch"
    FACT_NOT_FOUND = "fact_not_found"
    AMBIGUOUS_FACT = "ambiguous_fact"
    INVALID_TIMESTAMP = "invalid_timestamp"
    STALE_SOURCE = "stale_source"
    INTERNAL_ERROR = "internal_error"


ERROR_CODES: Final[frozenset[str]] = frozenset(code.value for code in ErrorCode)

EXTRACTOR_ID: Final[str] = "official_source.stdlib_html_parser.v1"

# Public-safe messages for each failure code (no secrets / internals).
_PUBLIC_MESSAGES: Final[dict[ErrorCode, str]] = {
    ErrorCode.UNSUPPORTED_QUESTION: "지원하지 않는 시급성 사실 질문입니다.",
    ErrorCode.INVALID_REQUEST: "요청이 올바르지 않습니다.",
    ErrorCode.SOURCE_NOT_ALLOWLISTED: "승인되지 않은 공식 출처입니다.",
    ErrorCode.EXTERNAL_REDIRECT: "외부 출처로 리다이렉트되어 차단되었습니다.",
    ErrorCode.TRANSPORT_TIMEOUT: "공식 출처 조회 시간이 초과되었습니다.",
    ErrorCode.TRANSPORT_ERROR: "공식 출처 조회에 실패했습니다.",
    ErrorCode.HTTP_ERROR: "공식 출처 HTTP 오류가 발생했습니다.",
    ErrorCode.INVALID_CONTENT_TYPE: "공식 출처 콘텐츠 형식이 올바르지 않습니다.",
    ErrorCode.EMPTY_CONTENT: "공식 출처 본문이 비어 있습니다.",
    ErrorCode.MALFORMED_CONTENT: "공식 출처 HTML을 해석할 수 없습니다.",
    ErrorCode.SOURCE_IDENTITY_MISMATCH: "공식 출처 페이지 식별이 일치하지 않습니다.",
    ErrorCode.FACT_NOT_FOUND: "공식 출처에서 해당 사실을 찾지 못했습니다.",
    ErrorCode.AMBIGUOUS_FACT: "공식 출처 사실 값이 모호합니다.",
    ErrorCode.INVALID_TIMESTAMP: "조회 시각 정보가 올바르지 않습니다.",
    ErrorCode.STALE_SOURCE: "공식 출처 조회 결과가 오래되어 사용할 수 없습니다.",
    ErrorCode.INTERNAL_ERROR: "내부 처리 오류로 사실을 확정할 수 없습니다.",
}


def public_message_for(code: ErrorCode | None) -> str:
    if code is None:
        return ""
    return _PUBLIC_MESSAGES.get(code, _PUBLIC_MESSAGES[ErrorCode.INTERNAL_ERROR])


@dataclass(frozen=True)
class OfficialSourceRequest:
    """Retrieval request model (classification + policy target + clock)."""

    question: str
    fact_kind: FactKind | None = None
    target_url: str | None = None
    # Injected evaluation clock (ISO-8601 UTC). Required for deterministic tests.
    evaluated_at: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "question": self.question,
            "fact_kind": self.fact_kind.value if self.fact_kind else None,
            "target_url": self.target_url,
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
    """Structured success/failure payload for official-source freshness.

    Public contract fields (also available via properties / to_dict):
      ok, fact_type, value, source_url, source_title, retrieved_at,
      freshness_status, failure_code, public_safe_message
    """

    ok: bool
    fact_kind: FactKind | None = None
    fact: FactValue | None = None
    source: SourceMetadata | None = None
    freshness_status: FreshnessStatus = FreshnessStatus.UNKNOWN
    max_age_seconds: int | None = None
    age_seconds: float | None = None
    failure_code: ErrorCode | None = None
    public_safe_message: str = ""
    extractor_id: str = EXTRACTOR_ID
    warnings: tuple[str, ...] = field(default_factory=tuple)
    schema_version: str = "1.0.0"

    # Backward-compatible aliases used by earlier Phase-1 commits.
    @property
    def success(self) -> bool:
        return self.ok

    @property
    def error_code(self) -> ErrorCode | None:
        return self.failure_code

    @property
    def error_message(self) -> str:
        return self.public_safe_message

    @property
    def fact_type(self) -> str | None:
        return self.fact_kind.value if self.fact_kind else None

    @property
    def value(self) -> str | None:
        return self.fact.value if self.fact else None

    @property
    def source_url(self) -> str | None:
        return self.source.url if self.source else None

    @property
    def source_title(self) -> str | None:
        return self.source.title if self.source else None

    @property
    def retrieved_at(self) -> str | None:
        return self.source.retrieved_at if self.source else None

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "ok": self.ok,
            "success": self.ok,  # alias
            "fact_type": self.fact_type,
            "fact_kind": self.fact_type,
            "value": self.value,
            "fact": self.fact.to_dict() if self.fact else None,
            "source_url": self.source_url,
            "source_title": self.source_title,
            "retrieved_at": self.retrieved_at,
            "source": self.source.to_dict() if self.source else None,
            "freshness_status": self.freshness_status.value,
            "max_age_seconds": self.max_age_seconds,
            "age_seconds": self.age_seconds,
            "failure_code": self.failure_code.value if self.failure_code else None,
            "error_code": self.failure_code.value if self.failure_code else None,
            "public_safe_message": self.public_safe_message,
            "error_message": self.public_safe_message,
            "extractor_id": self.extractor_id,
            "warnings": list(self.warnings),
        }


def unsuccessful(
    *,
    failure_code: ErrorCode,
    public_safe_message: str | None = None,
    fact_kind: FactKind | None = None,
    source: SourceMetadata | None = None,
    freshness_status: FreshnessStatus = FreshnessStatus.UNKNOWN,
    max_age_seconds: int | None = None,
    age_seconds: float | None = None,
    warnings: tuple[str, ...] = (),
) -> OfficialSourceResult:
    """Construct a fail-closed unsuccessful result (never attaches a fact)."""
    return OfficialSourceResult(
        ok=False,
        fact_kind=fact_kind,
        fact=None,
        source=source,
        freshness_status=freshness_status,
        max_age_seconds=max_age_seconds,
        age_seconds=age_seconds,
        failure_code=failure_code,
        public_safe_message=public_safe_message or public_message_for(failure_code),
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
        ok=True,
        fact_kind=fact.kind,
        fact=fact,
        source=source,
        freshness_status=freshness_status,
        max_age_seconds=max_age_seconds,
        age_seconds=age_seconds,
        failure_code=None,
        public_safe_message="",
        warnings=warnings,
    )


__all__ = [
    "ERROR_CODES",
    "EXTRACTOR_ID",
    "ErrorCode",
    "FactKind",
    "FactValue",
    "FreshnessStatus",
    "OfficialSourceRequest",
    "OfficialSourceResult",
    "SourceMetadata",
    "asdict",
    "public_message_for",
    "successful",
    "unsuccessful",
]
