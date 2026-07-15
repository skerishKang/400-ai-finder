"""Official-source freshness retrieval — Phase 1 backend boundary (#1150).

Isolated domain package for time-sensitive civic facts that must be checked
against allowlisted official Buk-gu public pages.

Layers (intentionally separate):

* classification  — question → supported fact kind or unsupported
* policy          — official source allowlist and freshness thresholds
* transport       — fetch interface + mock provider (no live network)
* extraction      — HTML/content parsing for expected facts
* normalize       — fact value normalization
* freshness       — retrieved-at / fresh-or-stale metadata
* service         — orchestration returning a fail-closed payload

Phase 1 supports only:

* current Buk-gu mayor
* current jurisdiction / organization name

No live official-page, Firecrawl, paid provider, or external API call is
performed on import, construction, unit tests, or default service use.
"""

from __future__ import annotations

from .classification import ClassificationResult, classify_question
from .freshness import FreshnessAssessment, assess_freshness
from .models import (
    ERROR_CODES,
    ErrorCode,
    FactKind,
    FactValue,
    FreshnessStatus,
    OfficialSourceRequest,
    OfficialSourceResult,
    SourceMetadata,
)
from .policy import OfficialSourcePolicy, get_policy_for_fact, is_url_allowlisted
from .service import OfficialSourceFreshnessService
from .transport import (
    MockOfficialSourceTransport,
    OfficialSourceTransport,
    TransportResponse,
)

__all__ = [
    "ERROR_CODES",
    "ClassificationResult",
    "ErrorCode",
    "FactKind",
    "FactValue",
    "FreshnessAssessment",
    "FreshnessStatus",
    "MockOfficialSourceTransport",
    "OfficialSourceFreshnessService",
    "OfficialSourcePolicy",
    "OfficialSourceRequest",
    "OfficialSourceResult",
    "OfficialSourceTransport",
    "SourceMetadata",
    "TransportResponse",
    "assess_freshness",
    "classify_question",
    "get_policy_for_fact",
    "is_url_allowlisted",
]
