"""Mock search providers: official-first, then general web (no live network).

Importing and constructing providers performs no I/O. Live network is not
authorized in this module — callers must inject mock hits for tests.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Mapping

from .models import FactKind, SourceType


@dataclass(frozen=True)
class SearchHit:
    """One retrieval hit. Values must come from provider configuration — never
    invented by the model layer.
    """

    fact_kind: FactKind
    value: str
    source_url: str
    source_title: str
    source_type: SourceType
    retrieved_at: str
    snippet: str = ""
    rank: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "fact_kind": self.fact_kind.value,
            "value": self.value,
            "source_url": self.source_url,
            "source_title": self.source_title,
            "source_type": self.source_type.value,
            "retrieved_at": self.retrieved_at,
            "snippet": self.snippet,
            "rank": self.rank,
        }


@dataclass(frozen=True)
class ProviderSearchResult:
    ok: bool
    hits: tuple[SearchHit, ...] = ()
    error: str = ""
    provider_name: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "hits": [h.to_dict() for h in self.hits],
            "error": self.error,
            "provider_name": self.provider_name,
        }


class CurrentInfoSearchProvider(ABC):
    @property
    @abstractmethod
    def name(self) -> str: ...

    @property
    @abstractmethod
    def source_type(self) -> SourceType: ...

    @abstractmethod
    def search(
        self,
        question: str,
        *,
        fact_kind: FactKind | None,
        evaluated_at: str,
    ) -> ProviderSearchResult: ...


class MockOfficialSearchProvider(CurrentInfoSearchProvider):
    """In-memory official search. Missing keys fail closed — no invented hits."""

    def __init__(
        self,
        hits_by_kind: Mapping[FactKind, SearchHit] | None = None,
        *,
        fail_kinds: frozenset[FactKind] | None = None,
    ) -> None:
        self._hits = dict(hits_by_kind or {})
        self._fail_kinds = fail_kinds or frozenset()
        self._call_log: list[str] = []

    @property
    def name(self) -> str:
        return "mock_official_search"

    @property
    def source_type(self) -> SourceType:
        return SourceType.OFFICIAL

    @property
    def call_log(self) -> tuple[str, ...]:
        return tuple(self._call_log)

    def set_hit(self, kind: FactKind, hit: SearchHit) -> None:
        self._hits[kind] = hit

    def search(
        self,
        question: str,
        *,
        fact_kind: FactKind | None,
        evaluated_at: str,
    ) -> ProviderSearchResult:
        self._call_log.append(f"{fact_kind}:{question}")
        if fact_kind is None:
            return ProviderSearchResult(
                ok=False, error="missing_fact_kind", provider_name=self.name
            )
        if fact_kind in self._fail_kinds:
            return ProviderSearchResult(
                ok=False, error="mock_official_forced_failure", provider_name=self.name
            )
        hit = self._hits.get(fact_kind)
        if hit is None:
            return ProviderSearchResult(
                ok=False, error="mock_official_no_hit", provider_name=self.name
            )
        return ProviderSearchResult(ok=True, hits=(hit,), provider_name=self.name)


class MockGeneralWebSearchProvider(CurrentInfoSearchProvider):
    """In-memory general web search (second priority after official)."""

    def __init__(
        self,
        hits_by_kind: Mapping[FactKind, SearchHit] | None = None,
        *,
        fail_kinds: frozenset[FactKind] | None = None,
    ) -> None:
        self._hits = dict(hits_by_kind or {})
        self._fail_kinds = fail_kinds or frozenset()
        self._call_log: list[str] = []

    @property
    def name(self) -> str:
        return "mock_general_web_search"

    @property
    def source_type(self) -> SourceType:
        return SourceType.GENERAL_WEB

    @property
    def call_log(self) -> tuple[str, ...]:
        return tuple(self._call_log)

    def set_hit(self, kind: FactKind, hit: SearchHit) -> None:
        self._hits[kind] = hit

    def search(
        self,
        question: str,
        *,
        fact_kind: FactKind | None,
        evaluated_at: str,
    ) -> ProviderSearchResult:
        self._call_log.append(f"{fact_kind}:{question}")
        if fact_kind is None:
            return ProviderSearchResult(
                ok=False, error="missing_fact_kind", provider_name=self.name
            )
        if fact_kind in self._fail_kinds:
            return ProviderSearchResult(
                ok=False, error="mock_general_forced_failure", provider_name=self.name
            )
        hit = self._hits.get(fact_kind)
        if hit is None:
            return ProviderSearchResult(
                ok=False, error="mock_general_no_hit", provider_name=self.name
            )
        return ProviderSearchResult(ok=True, hits=(hit,), provider_name=self.name)


@dataclass
class OfficialFirstSearchOrchestrator:
    """Try official provider first; only then general web. No model memory."""

    official: CurrentInfoSearchProvider
    general: CurrentInfoSearchProvider | None = None
    allow_general: bool = True

    def search(
        self,
        question: str,
        *,
        fact_kind: FactKind | None,
        evaluated_at: str,
    ) -> tuple[ProviderSearchResult, SourceType]:
        official_result = self.official.search(
            question, fact_kind=fact_kind, evaluated_at=evaluated_at
        )
        if official_result.ok and official_result.hits:
            return official_result, SourceType.OFFICIAL

        if self.allow_general and self.general is not None:
            general_result = self.general.search(
                question, fact_kind=fact_kind, evaluated_at=evaluated_at
            )
            if general_result.ok and general_result.hits:
                return general_result, SourceType.GENERAL_WEB
            return general_result, SourceType.NONE

        return official_result, SourceType.NONE

    def resolve_conflict(
        self,
        official_hit: SearchHit | None,
        general_hit: SearchHit | None,
    ) -> SearchHit | None:
        """Official wins on conflict; never invent a third value."""
        if official_hit is not None:
            return official_hit
        return general_hit


__all__ = [
    "CurrentInfoSearchProvider",
    "MockGeneralWebSearchProvider",
    "MockOfficialSearchProvider",
    "OfficialFirstSearchOrchestrator",
    "ProviderSearchResult",
    "SearchHit",
]
