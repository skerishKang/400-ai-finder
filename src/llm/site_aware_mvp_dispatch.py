"""Shared site-aware MVP runtime identity + fail-closed dispatch seam (#1331, Slice A).

This module is the SINGLE ownership point that maps a site identity to an MVP
runtime status. The Python web handler (``src.web.mobile_demo``) and the
Cloudflare Function (``functions/api/mvp/site_runtime.js``) MUST agree on these
semantics. The status vocabulary is mirrored 1:1 between the two runtimes.

Status contract
---------------
- ``CONFIGURED``               : a working resident runtime exists (Buk-gu today).
                                The existing Buk-gu router/quest/action logic may
                                execute unchanged.
- ``RECOGNIZED_UNCONFIGURED`` : the site identity is acknowledged by the
                                platform but its MVP runtime is NOT configured
                                for this slice (e.g. Seo-gu). It MUST NOT
                                execute any Buk-gu (or any) quest/action
                                behavior in this slice.
- ``UNKNOWN``                 : fail closed. Never falls back to Buk-gu.

Backward compatibility
----------------------
An omitted / empty / ``None`` site identity resolves to the default resident
runtime (Buk-gu) so legacy callers that never carried a site identity keep their
Buk-gu behavior. A malformed (non-empty, wrong-shape) identity fails closed
rather than silently defaulting to Buk-gu.

This is intentionally the ONLY place that enumerates site runtime identity. Do
not scatter ``if site_id == "seogu_gwangju"`` branches through the shared
runtime; branch on the resolved ``SiteRuntimeStatus`` instead.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum
from typing import Literal

# Status vocabulary — mirrors functions/api/mvp/site_runtime.js exactly.
SITE_RUNTIME_CONFIGURED = "configured"
SITE_RUNTIME_RECOGNIZED_UNCONFIGURED = "recognized_unconfigured"
SITE_RUNTIME_UNKNOWN = "unknown"


class SiteRuntimeStatus(str, Enum):
    """Resolved MVP runtime status for a site identity."""

    CONFIGURED = SITE_RUNTIME_CONFIGURED
    RECOGNIZED_UNCONFIGURED = SITE_RUNTIME_RECOGNIZED_UNCONFIGURED
    UNKNOWN = SITE_RUNTIME_UNKNOWN


# Canonical recognized site registry for the MVP dispatch seam.
#
# "Recognized" does NOT imply a configured runtime. This is the ONLY place that
# enumerates site runtime identity; shared code must not hard-code site id
# strings. Slice A configures Buk-gu and acknowledges Seo-gu (recognized but not
# yet configured). Any other site id is UNKNOWN (fail closed).
SUPPORTED_SITE_RUNTIMES: dict[str, SiteRuntimeStatus] = {
    "bukgu_gwangju": SiteRuntimeStatus.CONFIGURED,
    "seogu_gwangju": SiteRuntimeStatus.RECOGNIZED_UNCONFIGURED,
}

DEFAULT_SITE_ID = "bukgu_gwangju"

# Closed site-dispatch failure codes. These are distinct from the provider/model
# failure_code vocabulary in ``src.llm.openai_compatible_provider`` on purpose:
# they describe site-identity dispatch outcomes, not provider failures.
SITE_FAILURE_UNKNOWN = "unknown_site"
SITE_FAILURE_UNCONFIGURED = "site_unconfigured_for_slice"

# Site id shape: lowercase letters/digits/underscore, 3..64 chars. This matches
# the Cloudflare request-safety validation so Python and Cloudflare agree on
# what a well-formed site id looks like.
SITE_ID_PATTERN = r"^[a-z0-9_]{3,64}$"
_SITE_ID_RE = re.compile(SITE_ID_PATTERN)


class SiteIdentityError(ValueError):
    """Raised for unrecognized / fail-closed site identity.

    Callers that want to enforce a hard failure may catch this. The resolver
    itself returns ``UNKNOWN`` rather than raising, so handlers can decide their
    own fail-closed envelope.
    """


@dataclass(frozen=True)
class SiteRuntimeResolution:
    """Resolution result for a site identity."""

    site_id: str
    status: SiteRuntimeStatus


def is_valid_site_id_format(site_id: object) -> bool:
    """Return True when ``site_id`` is a well-formed site id string."""
    return isinstance(site_id, str) and bool(_SITE_ID_RE.match(site_id))


def resolve_site_runtime(site_id: object) -> SiteRuntimeResolution:
    """Resolve a site identity to its MVP runtime status.

    Rules (Python and Cloudflare MUST agree):
      - omitted / empty / non-string -> default resident runtime (Buk-gu)
      - well-formed but unrecognized  -> UNKNOWN (fail closed, never Buk-gu)
      - malformed (non-empty, bad shape) -> UNKNOWN (fail closed)
      - recognized, not configured    -> RECOGNIZED_UNCONFIGURED (no execution)
      - configured                     -> CONFIGURED (Buk-gu runtime may run)
    """
    if site_id is None or not isinstance(site_id, str) or not site_id.strip():
        resolved = DEFAULT_SITE_ID
    else:
        resolved = site_id.strip()

    # Malformed identity fails closed instead of defaulting to Buk-gu. This keeps
    # the fail-closed guarantee even if a caller passes a garbage non-empty id.
    if not is_valid_site_id_format(resolved):
        return SiteRuntimeResolution(
            site_id=resolved, status=SiteRuntimeStatus.UNKNOWN
        )

    status = SUPPORTED_SITE_RUNTIMES.get(resolved)
    if status is None:
        return SiteRuntimeResolution(
            site_id=resolved, status=SiteRuntimeStatus.UNKNOWN
        )
    return SiteRuntimeResolution(site_id=resolved, status=status)


# Re-export the literal string form for callers that prefer string comparisons
# (mirrors the JS constants and avoids Enum import churn at call sites).
SiteRuntimeStatusLiteral = Literal[
    SITE_RUNTIME_CONFIGURED,
    SITE_RUNTIME_RECOGNIZED_UNCONFIGURED,
    SITE_RUNTIME_UNKNOWN,
]

__all__ = [
    "SITE_RUNTIME_CONFIGURED",
    "SITE_RUNTIME_RECOGNIZED_UNCONFIGURED",
    "SITE_RUNTIME_UNKNOWN",
    "SiteRuntimeStatus",
    "SUPPORTED_SITE_RUNTIMES",
    "DEFAULT_SITE_ID",
    "SITE_FAILURE_UNKNOWN",
    "SITE_FAILURE_UNCONFIGURED",
    "SITE_ID_PATTERN",
    "SiteIdentityError",
    "SiteRuntimeResolution",
    "is_valid_site_id_format",
    "resolve_site_runtime",
]
