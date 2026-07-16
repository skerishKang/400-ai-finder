"""Official-source / current-information retrieval (#1150).

Layers (dependency direction):

* request context — server clock injection (no web clock search)
* classification  — question → fact kind or unsupported
* aliases         — surface forms → entity keys (no permanent fact values)
* routing         — journey vs official vs general vs safe unsupported
* policy          — official origin allowlist + freshness thresholds
* transport       — HTML fetch interface + mock (Phase-1 path)
* search providers — official-first then general web (mock-only default)
* extraction      — HTML/content parsing for Phase-1 facts
* normalize       — fact value normalization
* freshness       — retrieved-at / fresh·stale·unknown·invalid
* service         — Phase-1 HTML orchestration
* pipeline        — expanded current-information answers

No live official-page, Firecrawl, paid provider, or external API call is
performed on import, construction, unit tests, or default service/pipeline use.

Truthfulness:

* ``data-official-fact`` markers are mock-fixture scaffolding only
* civic names in mock fixtures are examples, not product constants
* product answers must come from retrieval hits
* this package is not live-ready until a separately approved live stage
"""

from __future__ import annotations

from .aliases import AliasResolution, alias_table_for_tests, resolve_aliases
from .classification import ClassificationResult, classify_question
from .freshness import FreshnessAssessment, assess_freshness
from .models import (
    DEFAULT_TIMEZONE,
    ERROR_CODES,
    EXTRACTOR_ID,
    PIPELINE_ID,
    CurrentInformationAnswer,
    ErrorCode,
    FactKind,
    FactValue,
    FreshnessStatus,
    OfficialSourceRequest,
    OfficialSourceResult,
    QueryRoute,
    RequestContext,
    RetrievalPolicy,
    SearchScope,
    SourceMetadata,
    SourceType,
    build_request_context,
)
from .pipeline import CurrentInformationPipeline, assert_no_hallucinated_names
from .policy import (
    DEFAULT_MAX_AGE_SECONDS,
    OfficialSourcePolicy,
    assess_url_allowlist,
    get_policy_for_fact,
    is_url_allowlisted,
)
from .routing import RoutingDecision, classify_journey_action, route_question
from .search_providers import (
    MockGeneralWebSearchProvider,
    MockOfficialSearchProvider,
    OfficialFirstSearchOrchestrator,
    SearchHit,
)
from .service import OfficialSourceFreshnessService
from .transport import (
    MockOfficialSourceTransport,
    OfficialSourceTransport,
    TransportResponse,
)

__all__ = [
    "DEFAULT_MAX_AGE_SECONDS",
    "DEFAULT_TIMEZONE",
    "ERROR_CODES",
    "EXTRACTOR_ID",
    "PIPELINE_ID",
    "AliasResolution",
    "ClassificationResult",
    "CurrentInformationAnswer",
    "CurrentInformationPipeline",
    "ErrorCode",
    "FactKind",
    "FactValue",
    "FreshnessAssessment",
    "FreshnessStatus",
    "MockGeneralWebSearchProvider",
    "MockOfficialSearchProvider",
    "MockOfficialSourceTransport",
    "OfficialFirstSearchOrchestrator",
    "OfficialSourceFreshnessService",
    "OfficialSourcePolicy",
    "OfficialSourceRequest",
    "OfficialSourceResult",
    "OfficialSourceTransport",
    "QueryRoute",
    "RequestContext",
    "RetrievalPolicy",
    "RoutingDecision",
    "SearchHit",
    "SearchScope",
    "SourceMetadata",
    "SourceType",
    "TransportResponse",
    "alias_table_for_tests",
    "assert_no_hallucinated_names",
    "assess_freshness",
    "assess_url_allowlist",
    "build_request_context",
    "classify_journey_action",
    "classify_question",
    "get_policy_for_fact",
    "is_url_allowlisted",
    "resolve_aliases",
    "route_question",
]
