"""Mock search providers: official-first, then general web (no live network).

Hits are keyed by structured ``SearchHitKey`` (fact_kind, temporal_mode, as_of).
Historical lookups never fall back to current keys. Hits are integrity-validated
before return.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Mapping

from .freshness import InvalidTimestampError, parse_utc_timestamp
from .models import (
    ErrorCode,
    FactKind,
    SearchScope,
    SourceType,
    TemporalMode,
    TemporalPrecision,
)


@dataclass(frozen=True)
class SearchHitKey:
    """Explicit mock lookup key — no current/historical collision."""

    fact_kind: FactKind
    temporal_mode: TemporalMode
    as_of_key: str | None = None  # None for current; year or date string for historical

    def to_dict(self) -> dict[str, Any]:
        return {
            "fact_kind": self.fact_kind.value,
            "temporal_mode": self.temporal_mode.value,
            "as_of_key": self.as_of_key,
        }


def make_search_key(
    fact_kind: FactKind,
    temporal_mode: TemporalMode,
    *,
    as_of_date: str | None = None,
    as_of_year: int | None = None,
    temporal_precision: TemporalPrecision = TemporalPrecision.UNSPECIFIED,
) -> SearchHitKey:
    if temporal_mode is TemporalMode.CURRENT:
        return SearchHitKey(fact_kind, TemporalMode.CURRENT, None)
    # Historical: prefer explicit date label, else year string, else None sentinel
    if temporal_precision is TemporalPrecision.YEAR and as_of_year is not None:
        as_of = str(as_of_year)
    elif as_of_date is not None:
        as_of = as_of_date
    elif as_of_year is not None:
        as_of = str(as_of_year)
    else:
        as_of = None
    return SearchHitKey(fact_kind, TemporalMode.HISTORICAL, as_of)


@dataclass(frozen=True)
class CurrentInfoSearchRequest:
    """Immutable structured search request passed to providers."""

    question: str
    fact_kind: FactKind
    temporal_mode: TemporalMode
    as_of_date: str | None
    as_of_year: int | None
    temporal_precision: TemporalPrecision
    request_started_at_utc: str
    timezone: str
    search_scope: SearchScope

    def to_dict(self) -> dict[str, Any]:
        return {
            "question": self.question,
            "fact_kind": self.fact_kind.value,
            "temporal_mode": self.temporal_mode.value,
            "as_of_date": self.as_of_date,
            "as_of_year": self.as_of_year,
            "temporal_precision": self.temporal_precision.value,
            "request_started_at_utc": self.request_started_at_utc,
            "timezone": self.timezone,
            "search_scope": self.search_scope.value,
        }

    def hit_key(self) -> SearchHitKey:
        return make_search_key(
            self.fact_kind,
            self.temporal_mode,
            as_of_date=self.as_of_date,
            as_of_year=self.as_of_year,
            temporal_precision=self.temporal_precision,
        )


@dataclass(frozen=True)
class SearchHit:
    fact_kind: FactKind
    value: str
    source_url: str
    source_title: str
    source_type: SourceType
    retrieved_at: str
    temporal_mode: TemporalMode = TemporalMode.CURRENT
    as_of_date: str | None = None
    as_of_year: int | None = None
    temporal_precision: TemporalPrecision = TemporalPrecision.UNSPECIFIED
    snippet: str = ""
    rank: int = 0
    provider_name: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "fact_kind": self.fact_kind.value,
            "value": self.value,
            "source_url": self.source_url,
            "source_title": self.source_title,
            "source_type": self.source_type.value,
            "retrieved_at": self.retrieved_at,
            "temporal_mode": self.temporal_mode.value,
            "as_of_date": self.as_of_date,
            "as_of_year": self.as_of_year,
            "temporal_precision": self.temporal_precision.value,
            "snippet": self.snippet,
            "rank": self.rank,
            "provider_name": self.provider_name,
        }


@dataclass(frozen=True)
class ProviderSearchResult:
    ok: bool
    hits: tuple[SearchHit, ...] = ()
    error: str = ""
    provider_name: str = ""
    failure_code: ErrorCode | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "hits": [h.to_dict() for h in self.hits],
            "error": self.error,
            "provider_name": self.provider_name,
            "failure_code": self.failure_code.value if self.failure_code else None,
        }


def validate_hit_integrity(
    hit: SearchHit,
    request: CurrentInfoSearchRequest,
    *,
    provider_source_type: SourceType,
    provider_name: str,
) -> ErrorCode | None:
    """Return failure code if hit cannot be used as a verified source."""
    if hit.fact_kind is not request.fact_kind:
        return ErrorCode.FACT_KIND_MISMATCH
    if hit.source_type is not provider_source_type:
        return ErrorCode.SOURCE_TYPE_MISMATCH
    if provider_source_type is SourceType.OFFICIAL and hit.source_type is not SourceType.OFFICIAL:
        return ErrorCode.SOURCE_TYPE_MISMATCH
    if (
        provider_source_type is SourceType.GENERAL_WEB
        and hit.source_type is not SourceType.GENERAL_WEB
    ):
        return ErrorCode.SOURCE_TYPE_MISMATCH
    if hit.temporal_mode is not request.temporal_mode:
        return ErrorCode.TEMPORAL_SCOPE_MISMATCH
    if request.temporal_mode is TemporalMode.HISTORICAL:
        # Must not accept current-mode hits
        if hit.temporal_mode is TemporalMode.CURRENT:
            return ErrorCode.TEMPORAL_SCOPE_MISMATCH
        # as-of must match when both sides provide a key
        req_key = request.hit_key().as_of_key
        hit_key = None
        if hit.temporal_precision is TemporalPrecision.YEAR and hit.as_of_year is not None:
            hit_key = str(hit.as_of_year)
        elif hit.as_of_date is not None:
            hit_key = hit.as_of_date
        elif hit.as_of_year is not None:
            hit_key = str(hit.as_of_year)
        if req_key is not None and hit_key is not None and req_key != hit_key:
            return ErrorCode.TEMPORAL_SCOPE_MISMATCH
        if req_key is not None and hit_key is None:
            return ErrorCode.TEMPORAL_SCOPE_MISMATCH
    else:
        if hit.temporal_mode is TemporalMode.HISTORICAL:
            return ErrorCode.TEMPORAL_SCOPE_MISMATCH
    if not (hit.source_url and str(hit.source_url).strip()):
        return ErrorCode.INVALID_SOURCE_METADATA
    if not (hit.source_title and str(hit.source_title).strip()):
        return ErrorCode.INVALID_SOURCE_METADATA
    if not (hit.retrieved_at and str(hit.retrieved_at).strip()):
        return ErrorCode.INVALID_SOURCE_METADATA
    try:
        parse_utc_timestamp(hit.retrieved_at)
    except InvalidTimestampError:
        return ErrorCode.INVALID_TIMESTAMP
    if not (hit.value and str(hit.value).strip()):
        return ErrorCode.FACT_NOT_FOUND
    if hit.source_type in (SourceType.NONE, SourceType.JOURNEY):
        return ErrorCode.INVALID_SOURCE_METADATA
    _ = provider_name  # reserved for logging
    return None


class CurrentInfoSearchProvider(ABC):
    @property
    @abstractmethod
    def name(self) -> str: ...

    @property
    @abstractmethod
    def source_type(self) -> SourceType: ...

    @abstractmethod
    def search(self, request: CurrentInfoSearchRequest) -> ProviderSearchResult: ...


class _MockKeyedProvider(CurrentInfoSearchProvider):
    def __init__(
        self,
        hits: Mapping[SearchHitKey, SearchHit] | None = None,
        *,
        fail_keys: frozenset[SearchHitKey] | None = None,
        expected_source_type: SourceType,
        provider_name: str,
    ) -> None:
        self._hits = dict(hits or {})
        self._fail_keys = fail_keys or frozenset()
        self._expected_source_type = expected_source_type
        self._provider_name = provider_name
        self._call_log: list[dict[str, Any]] = []

    @property
    def name(self) -> str:
        return self._provider_name

    @property
    def source_type(self) -> SourceType:
        return self._expected_source_type

    @property
    def call_log(self) -> tuple[dict[str, Any], ...]:
        return tuple(self._call_log)

    def set_hit(self, key: SearchHitKey, hit: SearchHit) -> None:
        self._hits[key] = hit

    def search(self, request: CurrentInfoSearchRequest) -> ProviderSearchResult:
        key = request.hit_key()
        self._call_log.append(key.to_dict())
        if key in self._fail_keys:
            return ProviderSearchResult(
                ok=False,
                error="mock_forced_failure",
                provider_name=self.name,
                failure_code=ErrorCode.RETRIEVAL_FAILED,
            )
        # Exact key only — no current fallback for historical.
        hit = self._hits.get(key)
        if hit is None:
            return ProviderSearchResult(
                ok=False,
                error="mock_no_hit_for_key",
                provider_name=self.name,
                failure_code=ErrorCode.RETRIEVAL_FAILED,
            )
        # Stamp provider name on a copy-like frozen rebuild if blank
        if not hit.provider_name:
            hit = SearchHit(
                fact_kind=hit.fact_kind,
                value=hit.value,
                source_url=hit.source_url,
                source_title=hit.source_title,
                source_type=hit.source_type,
                retrieved_at=hit.retrieved_at,
                temporal_mode=hit.temporal_mode,
                as_of_date=hit.as_of_date,
                as_of_year=hit.as_of_year,
                temporal_precision=hit.temporal_precision,
                snippet=hit.snippet,
                rank=hit.rank,
                provider_name=self.name,
            )
        code = validate_hit_integrity(
            hit,
            request,
            provider_source_type=self.source_type,
            provider_name=self.name,
        )
        if code is not None:
            return ProviderSearchResult(
                ok=False,
                error=f"integrity:{code.value}",
                provider_name=self.name,
                failure_code=code,
            )
        return ProviderSearchResult(ok=True, hits=(hit,), provider_name=self.name)


class MockOfficialSearchProvider(_MockKeyedProvider):
    def __init__(
        self,
        hits: Mapping[SearchHitKey, SearchHit] | None = None,
        *,
        fail_keys: frozenset[SearchHitKey] | None = None,
    ) -> None:
        super().__init__(
            hits,
            fail_keys=fail_keys,
            expected_source_type=SourceType.OFFICIAL,
            provider_name="mock_official_search",
        )


class MockGeneralWebSearchProvider(_MockKeyedProvider):
    def __init__(
        self,
        hits: Mapping[SearchHitKey, SearchHit] | None = None,
        *,
        fail_keys: frozenset[SearchHitKey] | None = None,
    ) -> None:
        super().__init__(
            hits,
            fail_keys=fail_keys,
            expected_source_type=SourceType.GENERAL_WEB,
            provider_name="mock_general_web_search",
        )


@dataclass
class OfficialFirstSearchOrchestrator:
    official: CurrentInfoSearchProvider
    general: CurrentInfoSearchProvider | None = None
    allow_general: bool = True

    def search(
        self, request: CurrentInfoSearchRequest
    ) -> tuple[ProviderSearchResult, SourceType]:
        official_result = self.official.search(request)
        if official_result.ok and official_result.hits:
            return official_result, SourceType.OFFICIAL

        # Integrity failures on official: do not invent; try general if allowed.
        if self.allow_general and self.general is not None:
            general_result = self.general.search(request)
            if general_result.ok and general_result.hits:
                return general_result, SourceType.GENERAL_WEB
            # Prefer more specific failure code from general if official was mere miss
            if general_result.failure_code and not official_result.ok:
                return general_result, SourceType.NONE
            if official_result.failure_code and official_result.failure_code is not ErrorCode.RETRIEVAL_FAILED:
                return official_result, SourceType.NONE
            return general_result, SourceType.NONE

        return official_result, SourceType.NONE


__all__ = [
    "CurrentInfoSearchProvider",
    "CurrentInfoSearchRequest",
    "MockGeneralWebSearchProvider",
    "MockOfficialSearchProvider",
    "OfficialFirstSearchOrchestrator",
    "ProviderSearchResult",
    "SearchHit",
    "SearchHitKey",
    "make_search_key",
    "validate_hit_integrity",
]
