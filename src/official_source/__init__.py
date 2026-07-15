"""Official-source freshness retrieval — Phase 1 backend boundary (#1150).

Layers (dependency direction):

* classification  — question → supported fact kind or unsupported
* policy          — official origin allowlist + freshness thresholds
* transport       — fetch interface + mock provider (no live network)
* extraction      — HTML/content parsing for expected facts
* normalize       — fact value normalization
* freshness       — retrieved-at / fresh·stale·unknown·invalid
* service         — orchestration returning a fail-closed payload

Phase 1 supports only current Buk-gu mayor and jurisdiction/organization name.
No live official-page, Firecrawl, paid provider, or external API call is
performed on import, construction, unit tests, or default service use.
"""

from __future__ import annotations

from .classification import ClassificationResult, classify_question
from .freshness import FreshnessAssessment, assess_freshness
from .models import (
    ERROR_CODES,
    EXTRACTOR_ID,
    ErrorCode,
    FactKind,
    FactValue,
    FreshnessStatus,
    OfficialSourceRequest,
    OfficialSourceResult,
    SourceMetadata,
)
from .policy import (
    DEFAULT_MAX_AGE_SECONDS,
    OfficialSourcePolicy,
    assess_url_allowlist,
    get_policy_for_fact,
    is_url_allowlisted,
)
from .service import OfficialSourceFreshnessService
from .transport import (
    MockOfficialSourceTransport,
    OfficialSourceTransport,
    TransportResponse,
)

__all__ = [
    "DEFAULT_MAX_AGE_SECONDS",
    "ERROR_CODES",
    "EXTRACTOR_ID",
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
    "assess_url_allowlist",
    "classify_question",
    "get_policy_for_fact",
    "is_url_allowlisted",
]
