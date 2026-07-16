"""Result schema and fail-closed error taxonomy for official-source freshness.

Aligned with repository structured-result conventions (dataclasses, closed
vocab failure codes, public-safe messages). Failures never invent civic facts.

Product answers must come from retrieval — never hard-coded civic names.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field, replace
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable, Final, Mapping
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


class FactKind(str, Enum):
    """Closed fact vocabulary for current-information retrieval."""

    CURRENT_MAYOR = "current_mayor"
    JURISDICTION_NAME = "jurisdiction_name"
    REGIONAL_EXECUTIVE = "regional_executive"
    DISTRICT_EXECUTIVE = "district_executive"
    AGENCY_NAME = "agency_name"
    ADMINISTRATIVE_STATUS = "administrative_status"
    OFFICE_HOURS = "office_hours"
    CONTACT_INFORMATION = "contact_information"
    FEE = "fee"
    APPLICATION_PERIOD = "application_period"
    CURRENT_NOTICE = "current_notice"
    CURRENT_POLICY = "current_policy"
    CURRENT_LAW = "current_law"
    CURRENT_EVENT = "current_event"
    GENERAL_CURRENT_INFORMATION = "general_current_information"


class FreshnessStatus(str, Enum):
    FRESH = "fresh"
    STALE = "stale"
    UNKNOWN = "unknown"
    INVALID = "invalid"
    VERIFIED_CURRENT = "verified_current"
    VERIFIED_AS_OF = "verified_as_of"


class TemporalMode(str, Enum):
    CURRENT = "current"
    HISTORICAL = "historical"


class TemporalPrecision(str, Enum):
    DATE = "date"
    YEAR = "year"
    UNSPECIFIED = "unspecified"


class QueryRoute(str, Enum):
    DETERMINISTIC_JOURNEY = "deterministic_journey"
    OFFICIAL_FRESHNESS_SEARCH = "official_freshness_search"
    GENERAL_WEB_SEARCH = "general_web_search"
    SAFE_UNSUPPORTED = "safe_unsupported"


class SourceType(str, Enum):
    OFFICIAL = "official"
    GENERAL_WEB = "general_web"
    NONE = "none"
    JOURNEY = "journey"


class SearchScope(str, Enum):
    OFFICIAL_ONLY = "official_only"
    OFFICIAL_THEN_GENERAL = "official_then_general"
    GENERAL_ONLY = "general_only"
    NONE = "none"


class ErrorCode(str, Enum):
    """Closed fail-closed taxonomy (public contract)."""

    UNSUPPORTED_QUESTION = "unsupported_question"
    INVALID_REQUEST = "invalid_request"
    INVALID_TIMEZONE = "invalid_timezone"
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
    RETRIEVAL_FAILED = "retrieval_failed"
    NO_VERIFIED_SOURCE = "no_verified_source"
    SOURCE_CONFLICT_UNRESOLVED = "source_conflict_unresolved"
    FACT_KIND_MISMATCH = "fact_kind_mismatch"
    SOURCE_TYPE_MISMATCH = "source_type_mismatch"
    TEMPORAL_SCOPE_MISMATCH = "temporal_scope_mismatch"
    INVALID_SOURCE_METADATA = "invalid_source_metadata"
    INTERNAL_ERROR = "internal_error"


ERROR_CODES: Final[frozenset[str]] = frozenset(code.value for code in ErrorCode)

EXTRACTOR_ID: Final[str] = "official_source.stdlib_html_parser.v1"
PIPELINE_ID: Final[str] = "official_source.current_information.v2"

DEFAULT_TIMEZONE: Final[str] = "Asia/Seoul"

_PUBLIC_MESSAGES: Final[dict[ErrorCode, str]] = {
    ErrorCode.UNSUPPORTED_QUESTION: "지원하지 않는 시급성 사실 질문입니다.",
    ErrorCode.INVALID_REQUEST: "요청이 올바르지 않습니다.",
    ErrorCode.INVALID_TIMEZONE: "유효하지 않은 시간대입니다.",
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
    ErrorCode.RETRIEVAL_FAILED: "최신 정보 검색에 실패하여 사실을 확정할 수 없습니다.",
    ErrorCode.NO_VERIFIED_SOURCE: "검증된 출처가 없어 현재 사실을 확정할 수 없습니다.",
    ErrorCode.SOURCE_CONFLICT_UNRESOLVED: "출처 간 충돌을 안전하게 해소하지 못했습니다.",
    ErrorCode.FACT_KIND_MISMATCH: "요청한 사실 종류와 검색 결과가 일치하지 않습니다.",
    ErrorCode.SOURCE_TYPE_MISMATCH: "출처 유형이 제공자 정책과 일치하지 않습니다.",
    ErrorCode.TEMPORAL_SCOPE_MISMATCH: "현재/과거 검색 범위가 일치하지 않습니다.",
    ErrorCode.INVALID_SOURCE_METADATA: "출처 메타데이터가 올바르지 않습니다.",
    ErrorCode.INTERNAL_ERROR: "내부 처리 오류로 사실을 확정할 수 없습니다.",
}


def public_message_for(code: ErrorCode | None) -> str:
    if code is None:
        return ""
    return _PUBLIC_MESSAGES.get(code, _PUBLIC_MESSAGES[ErrorCode.INTERNAL_ERROR])


Clock = Callable[[], datetime]


def format_utc_z(dt: datetime) -> str:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def format_local_iso(dt: datetime) -> str:
    """Format aware datetime with numeric UTC offset (e.g. +09:00)."""
    if dt.tzinfo is None:
        raise ValueError("datetime must be timezone-aware")
    # %z → +0900; normalize to +09:00
    raw = dt.strftime("%Y-%m-%dT%H:%M:%S%z")
    if len(raw) >= 5 and (raw[-5] in "+-" or raw[-5] == " "):
        return raw[:-2] + ":" + raw[-2:]
    return raw


@dataclass(frozen=True)
class RetrievalPolicy:
    prefer_official: bool = True
    allow_general_web: bool = True
    require_source_for_current_facts: bool = True
    max_age_seconds: int = 7 * 24 * 60 * 60
    search_scope: SearchScope = SearchScope.OFFICIAL_THEN_GENERAL

    def to_dict(self) -> dict[str, Any]:
        return {
            "prefer_official": self.prefer_official,
            "allow_general_web": self.allow_general_web,
            "require_source_for_current_facts": self.require_source_for_current_facts,
            "max_age_seconds": self.max_age_seconds,
            "search_scope": self.search_scope.value,
        }


@dataclass(frozen=True)
class RequestContext:
    """Per-request time and retrieval context (server clock + IANA timezone)."""

    request_started_at_utc: str
    request_started_at_local: str
    timezone: str = DEFAULT_TIMEZONE
    current_information_required: bool = False
    retrieval_policy: RetrievalPolicy = field(default_factory=RetrievalPolicy)
    historical_reference: bool = False
    temporal_mode: TemporalMode = TemporalMode.CURRENT
    as_of_date: str | None = None
    as_of_year: int | None = None
    temporal_precision: TemporalPrecision = TemporalPrecision.UNSPECIFIED

    def to_dict(self) -> dict[str, Any]:
        return {
            "request_started_at_utc": self.request_started_at_utc,
            "request_started_at_local": self.request_started_at_local,
            "timezone": self.timezone,
            "current_information_required": self.current_information_required,
            "retrieval_policy": self.retrieval_policy.to_dict(),
            "historical_reference": self.historical_reference,
            "temporal_mode": self.temporal_mode.value,
            "as_of_date": self.as_of_date,
            "as_of_year": self.as_of_year,
            "temporal_precision": self.temporal_precision.value,
        }


class InvalidTimezoneError(ValueError):
    """Raised when an IANA timezone name cannot be resolved."""


def build_request_context(
    *,
    clock: Clock | None = None,
    evaluated_at: str | None = None,
    timezone_name: str = DEFAULT_TIMEZONE,
    current_information_required: bool = False,
    retrieval_policy: RetrievalPolicy | None = None,
    historical_reference: bool = False,
    temporal_mode: TemporalMode = TemporalMode.CURRENT,
    as_of_date: str | None = None,
    as_of_year: int | None = None,
    temporal_precision: TemporalPrecision = TemporalPrecision.UNSPECIFIED,
) -> RequestContext:
    """Build RequestContext from injected clock or ISO UTC string + ZoneInfo."""
    try:
        zone = ZoneInfo(timezone_name)
    except (ZoneInfoNotFoundError, KeyError, ValueError) as exc:
        raise InvalidTimezoneError(f"invalid timezone: {timezone_name!r}") from exc

    if evaluated_at:
        raw = evaluated_at.strip()
        if raw.endswith("Z"):
            raw = raw[:-1] + "+00:00"
        started = datetime.fromisoformat(raw)
        if started.tzinfo is None:
            started = started.replace(tzinfo=timezone.utc)
        started = started.astimezone(timezone.utc)
    elif clock is not None:
        started = clock()
        if started.tzinfo is None:
            started = started.replace(tzinfo=timezone.utc)
        started = started.astimezone(timezone.utc)
    else:
        started = datetime.now(timezone.utc)

    local = started.astimezone(zone)
    return RequestContext(
        request_started_at_utc=format_utc_z(started),
        request_started_at_local=format_local_iso(local),
        timezone=timezone_name,
        current_information_required=current_information_required,
        retrieval_policy=retrieval_policy or RetrievalPolicy(),
        historical_reference=historical_reference,
        temporal_mode=temporal_mode,
        as_of_date=as_of_date,
        as_of_year=as_of_year,
        temporal_precision=temporal_precision,
    )


@dataclass(frozen=True)
class OfficialSourceRequest:
    question: str
    fact_kind: FactKind | None = None
    target_url: str | None = None
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
    url: str
    title: str
    retrieved_at: str
    final_url: str | None = None
    content_type: str | None = None
    source_type: SourceType = SourceType.OFFICIAL

    def to_dict(self) -> dict[str, Any]:
        return {
            "url": self.url,
            "title": self.title,
            "retrieved_at": self.retrieved_at,
            "final_url": self.final_url,
            "content_type": self.content_type,
            "source_type": self.source_type.value,
        }


@dataclass(frozen=True)
class FactValue:
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
            "success": self.ok,
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


@dataclass(frozen=True)
class CurrentInformationSource:
    """Structured provenance for one retrieved source."""

    url: str
    title: str
    source_type: SourceType
    retrieved_at: str
    provider_name: str
    rank: int = 0
    snippet: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "url": self.url,
            "title": self.title,
            "source_type": self.source_type.value,
            "retrieved_at": self.retrieved_at,
            "provider_name": self.provider_name,
            "rank": self.rank,
            "snippet": self.snippet,
        }


@dataclass(frozen=True)
class CurrentInformationAnswer:
    """Public envelope for current/historical information answers."""

    ok: bool
    answer: str
    query_type: str
    fact_kind: FactKind | None = None
    current_as_of: str | None = None
    retrieved_at: str | None = None
    freshness_status: FreshnessStatus = FreshnessStatus.UNKNOWN
    source_url: str | None = None
    source_title: str | None = None
    source_type: SourceType = SourceType.NONE
    search_scope: SearchScope = SearchScope.NONE
    sources: tuple[CurrentInformationSource, ...] = field(default_factory=tuple)
    warnings: tuple[str, ...] = field(default_factory=tuple)
    failure_code: ErrorCode | None = None
    route: QueryRoute | None = None
    journey_action: str | None = None
    journey_preserved: bool = False
    enrichment_fact_kind: FactKind | None = None
    enrichment_value: str | None = None
    value: str | None = None
    temporal_mode: TemporalMode = TemporalMode.CURRENT
    as_of_date: str | None = None
    as_of_year: int | None = None
    temporal_precision: TemporalPrecision = TemporalPrecision.UNSPECIFIED
    request_context: dict[str, Any] | None = None
    schema_version: str = "2.1.0"
    pipeline_id: str = PIPELINE_ID

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "pipeline_id": self.pipeline_id,
            "ok": self.ok,
            "answer": self.answer,
            "query_type": self.query_type,
            "fact_kind": self.fact_kind.value if self.fact_kind else None,
            "current_as_of": self.current_as_of,
            "retrieved_at": self.retrieved_at,
            "freshness_status": self.freshness_status.value,
            "source_url": self.source_url,
            "source_title": self.source_title,
            "source_type": self.source_type.value,
            "search_scope": self.search_scope.value,
            "sources": [s.to_dict() for s in self.sources],
            "warnings": list(self.warnings),
            "failure_code": self.failure_code.value if self.failure_code else None,
            "route": self.route.value if self.route else None,
            "journey_action": self.journey_action,
            "journey_preserved": self.journey_preserved,
            "enrichment_fact_kind": (
                self.enrichment_fact_kind.value if self.enrichment_fact_kind else None
            ),
            "enrichment_value": self.enrichment_value,
            "value": self.value,
            "temporal_mode": self.temporal_mode.value,
            "as_of_date": self.as_of_date,
            "as_of_year": self.as_of_year,
            "temporal_precision": self.temporal_precision.value,
            "request_context": self.request_context,
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


def failed_current_answer(
    *,
    failure_code: ErrorCode,
    query_type: str,
    route: QueryRoute,
    fact_kind: FactKind | None = None,
    answer: str | None = None,
    warnings: tuple[str, ...] = (),
    search_scope: SearchScope = SearchScope.NONE,
    journey_action: str | None = None,
    journey_preserved: bool = False,
    temporal_mode: TemporalMode = TemporalMode.CURRENT,
    as_of_date: str | None = None,
    as_of_year: int | None = None,
    temporal_precision: TemporalPrecision = TemporalPrecision.UNSPECIFIED,
    request_context: dict[str, Any] | None = None,
) -> CurrentInformationAnswer:
    return CurrentInformationAnswer(
        ok=False,
        answer=answer or public_message_for(failure_code),
        query_type=query_type,
        fact_kind=fact_kind,
        current_as_of=None,
        retrieved_at=None,
        freshness_status=FreshnessStatus.UNKNOWN,
        source_url=None,
        source_title=None,
        source_type=SourceType.NONE,
        search_scope=search_scope,
        sources=(),
        warnings=warnings,
        failure_code=failure_code,
        route=route,
        journey_action=journey_action,
        journey_preserved=journey_preserved,
        enrichment_fact_kind=None,
        enrichment_value=None,
        value=None,
        temporal_mode=temporal_mode,
        as_of_date=as_of_date,
        as_of_year=as_of_year,
        temporal_precision=temporal_precision,
        request_context=request_context,
    )


__all__ = [
    "DEFAULT_TIMEZONE",
    "ERROR_CODES",
    "EXTRACTOR_ID",
    "PIPELINE_ID",
    "Clock",
    "CurrentInformationAnswer",
    "CurrentInformationSource",
    "ErrorCode",
    "FactKind",
    "FactValue",
    "FreshnessStatus",
    "InvalidTimezoneError",
    "OfficialSourceRequest",
    "OfficialSourceResult",
    "QueryRoute",
    "RequestContext",
    "RetrievalPolicy",
    "SearchScope",
    "SourceMetadata",
    "SourceType",
    "TemporalMode",
    "TemporalPrecision",
    "asdict",
    "build_request_context",
    "failed_current_answer",
    "format_local_iso",
    "format_utc_z",
    "public_message_for",
    "replace",
    "successful",
    "unsuccessful",
]
