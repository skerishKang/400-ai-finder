"""Official-source / current-information retrieval (#1150).

Mock/offline by default. No live network on import or construction.

Truthfulness / scope:

* ``data-official-fact`` markers are deterministic mock-fixture scaffolding
* the current branch does not prove parsing against the live official mayor page
* no live official-page validation was executed
* this package is not live-ready and not production-ready
* real answer-time official-site retrieval remains deferred until approved
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
    CurrentInformationSource,
    ErrorCode,
    FactKind,
    FactValue,
    FreshnessStatus,
    InvalidTimezoneError,
    OfficialSourceRequest,
    OfficialSourceResult,
    QueryRoute,
    RequestContext,
    RetrievalPolicy,
    SearchScope,
    SourceMetadata,
    SourceType,
    TemporalMode,
    TemporalPrecision,
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
    CurrentInfoSearchRequest,
    MockGeneralWebSearchProvider,
    MockOfficialSearchProvider,
    OfficialFirstSearchOrchestrator,
    SearchHit,
    SearchHitKey,
    make_search_key,
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
    "CurrentInfoSearchRequest",
    "CurrentInformationAnswer",
    "CurrentInformationPipeline",
    "CurrentInformationSource",
    "ErrorCode",
    "FactKind",
    "FactValue",
    "FreshnessAssessment",
    "FreshnessStatus",
    "InvalidTimezoneError",
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
    "SearchHitKey",
    "SearchScope",
    "SourceMetadata",
    "SourceType",
    "TemporalMode",
    "TemporalPrecision",
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
    "make_search_key",
    "resolve_aliases",
    "route_question",
]
