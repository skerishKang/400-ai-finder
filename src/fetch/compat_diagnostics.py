"""Fetch compatibility diagnostic boundary (Stage #800).

This module classifies fetch-related failures into a small, operator-safe
taxonomy so warnings and operator reports can describe *why* a fetch
failed without leaking raw exception text, response bodies, headers,
provider payloads, API keys, or any other sensitive material.

Seven categories are defined — see :class:`FetchCategory` for the
closed set:

* ``timeout``             — request or socket-level deadline exceeded
* ``connection_error``    — DNS / TCP / refused / reset
* ``tls_error``           — TLS handshake / certificate failure
* ``http_error``          — 5xx server-side failure
* ``blocked_or_forbidden`` — 401 / 403 / 429
* ``parse_error``         — JSON / HTML / XML payload malformed
* ``unknown_fetch_error`` — fallback when nothing else fits

The output dataclass :class:`FetchDiagnostic` exposes only four fields:

* ``category``      — one of the :class:`FetchCategory` enum values
* ``short_reason``  — a fixed, sanitized human description (NO raw exc text)
* ``retry_hint``    — one of {"retry", "backoff", "do_not_retry"}
* ``is_transient``  — best-effort hint for retry logic

It is **never** allowed to echo raw exception messages, response bodies,
headers, provider payloads, or API keys. Callers that need raw detail
must keep it in their own (non-operator-facing) logs and never feed it
into this helper.
"""

from __future__ import annotations

import json
import ssl
from dataclasses import dataclass
from enum import Enum
from typing import Any


class FetchCategory(str, Enum):
    """Closed set of operator-safe fetch failure categories."""

    TIMEOUT = "timeout"
    CONNECTION_ERROR = "connection_error"
    TLS_ERROR = "tls_error"
    HTTP_ERROR = "http_error"
    BLOCKED_OR_FORBIDDEN = "blocked_or_forbidden"
    PARSE_ERROR = "parse_error"
    UNKNOWN_FETCH_ERROR = "unknown_fetch_error"


# ---------------------------------------------------------------------------
# Status code → category mapping
# ---------------------------------------------------------------------------

# 5xx codes are treated as http_error (transient server-side failure).
_HTTP_ERROR_CODES: frozenset[int] = frozenset({500, 501, 502, 503, 504, 505})

# 401/403/429 are blocked_or_forbidden. 400/404/405 are NOT classified as
# blocked_or_forbidden (they signal client-side issues, not blocking).
_BLOCKED_OR_FORBIDDEN_CODES: frozenset[int] = frozenset({401, 403, 429})


# ---------------------------------------------------------------------------
# Output shape
# ---------------------------------------------------------------------------

# Fixed short reasons — no template substitution, no raw exception text.
_SHORT_REASONS: dict[FetchCategory, str] = {
    FetchCategory.TIMEOUT: "Request exceeded its deadline.",
    FetchCategory.CONNECTION_ERROR: (
        "Could not establish or maintain a network connection to the host."
    ),
    FetchCategory.TLS_ERROR: (
        "TLS handshake or certificate validation failed."
    ),
    FetchCategory.HTTP_ERROR: "Upstream returned a 5xx server-side error.",
    FetchCategory.BLOCKED_OR_FORBIDDEN: (
        "Upstream refused the request (auth / forbidden / rate-limit)."
    ),
    FetchCategory.PARSE_ERROR: "Response payload could not be parsed.",
    FetchCategory.UNKNOWN_FETCH_ERROR: "Unclassified fetch failure.",
}


# Retry hints — closed vocabulary, used verbatim by callers.
_RETRY_HINTS: dict[FetchCategory, str] = {
    FetchCategory.TIMEOUT: "retry",
    FetchCategory.CONNECTION_ERROR: "retry",
    FetchCategory.TLS_ERROR: "do_not_retry",
    FetchCategory.HTTP_ERROR: "backoff",
    FetchCategory.BLOCKED_OR_FORBIDDEN: "do_not_retry",
    FetchCategory.PARSE_ERROR: "do_not_retry",
    FetchCategory.UNKNOWN_FETCH_ERROR: "do_not_retry",
}


# Best-effort transience flag — used by retry loops.
_IS_TRANSIENT: dict[FetchCategory, bool] = {
    FetchCategory.TIMEOUT: True,
    FetchCategory.CONNECTION_ERROR: True,
    FetchCategory.TLS_ERROR: False,
    FetchCategory.HTTP_ERROR: True,
    FetchCategory.BLOCKED_OR_FORBIDDEN: False,
    FetchCategory.PARSE_ERROR: False,
    FetchCategory.UNKNOWN_FETCH_ERROR: False,
}


@dataclass(frozen=True)
class FetchDiagnostic:
    """Operator-safe diagnostic record for a single fetch failure.

    All four fields are drawn from closed vocabularies. The dataclass is
    ``frozen=True`` so accidental mutation cannot inject raw text into an
    already-classified record.
    """

    category: FetchCategory
    short_reason: str
    retry_hint: str
    is_transient: bool

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable dict for operator reports / logs."""
        return {
            "category": self.category.value,
            "short_reason": self.short_reason,
            "retry_hint": self.retry_hint,
            "is_transient": self.is_transient,
        }


# ---------------------------------------------------------------------------
# Classification — exceptions
# ---------------------------------------------------------------------------

# Lazy import of requests so this module is safe to import in environments
# without the requests library installed (e.g. unit tests that exercise
# the taxonomy only).
def _requests_exc_types() -> dict[str, type[BaseException]]:
    try:
        import requests.exceptions as rex  # type: ignore[import-not-found]
    except ImportError:  # pragma: no cover - requests is a runtime dep
        return {}
    return {
        "Timeout": rex.Timeout,
        "ConnectTimeout": rex.ConnectTimeout,
        "ReadTimeout": rex.ReadTimeout,
        "ConnectionError": rex.ConnectionError,
        "SSLError": rex.SSLError,
        "ChunkedEncodingError": rex.ChunkedEncodingError,
    }


def classify_exception(exc: BaseException) -> FetchDiagnostic:
    """Classify a fetch exception into a :class:`FetchDiagnostic`.

    The ``exc`` argument is **inspected by type only**. Its string form is
    never propagated into the output. Pass a placeholder (``None`` or
    any object) if you only have a class; the helper does not look at
    the message.

    Unknown exception classes fall through to ``unknown_fetch_error``.
    """
    types = _requests_exc_types()
    timeout_cls = types.get("Timeout")
    connect_timeout_cls = types.get("ConnectTimeout")
    read_timeout_cls = types.get("ReadTimeout")
    connection_error_cls = types.get("ConnectionError")
    ssl_error_cls = types.get("SSLError")

    # 1. Timeout — requests' Timeout base class also covers ConnectTimeout
    #    and ReadTimeout, but we list subclasses first for clarity.
    if connect_timeout_cls is not None and isinstance(exc, connect_timeout_cls):
        return _diag(FetchCategory.TIMEOUT)
    if read_timeout_cls is not None and isinstance(exc, read_timeout_cls):
        return _diag(FetchCategory.TIMEOUT)
    if timeout_cls is not None and isinstance(exc, timeout_cls):
        return _diag(FetchCategory.TIMEOUT)
    if isinstance(exc, (TimeoutError, ssl.SSLWantReadError, ssl.SSLWantWriteError)):
        return _diag(FetchCategory.TIMEOUT)

    # 2. TLS / SSL — must come before ConnectionError because some
    #    requests builds wrap SSLError as ConnectionError on certain
    #    transports. We use the explicit SSLError class here.
    if ssl_error_cls is not None and isinstance(exc, ssl_error_cls):
        return _diag(FetchCategory.TLS_ERROR)
    if isinstance(exc, ssl.SSLError):
        return _diag(FetchCategory.TLS_ERROR)

    # 3. Connection error — DNS, refused, reset. We treat builtin socket
    #    errors and requests' ConnectionError uniformly.
    if connection_error_cls is not None and isinstance(exc, connection_error_cls):
        return _diag(FetchCategory.CONNECTION_ERROR)
    if isinstance(
        exc,
        (
            ConnectionError,  # builtin base; OSError alias
            ConnectionRefusedError,
            ConnectionResetError,
            ConnectionAbortedError,
            OSError,  # covers DNS failures (gaierror subclasses OSError)
        ),
    ):
        return _diag(FetchCategory.CONNECTION_ERROR)

    # 4. Parse error — JSON malformed or HTML/BeautifulSoup exception.
    if isinstance(exc, json.JSONDecodeError):
        return _diag(FetchCategory.PARSE_ERROR)
    # BeautifulSoup exceptions live in bs4.FeatureNotFound / bs4.ParserRejectedMarkup;
    # we detect via duck-typing to avoid hard-coupling to bs4 here.
    exc_module = type(exc).__module__
    if exc_module.startswith("bs4") and isinstance(exc, Exception):
        return _diag(FetchCategory.PARSE_ERROR)
    if "ParserCST" in type(exc).__name__ or "ParserRejected" in type(exc).__name__:
        return _diag(FetchCategory.PARSE_ERROR)

    # 5. Fallback.
    return _diag(FetchCategory.UNKNOWN_FETCH_ERROR)


# ---------------------------------------------------------------------------
# Classification — HTTP status codes
# ---------------------------------------------------------------------------


def classify_http_status(status_code: int) -> FetchDiagnostic:
    """Classify an HTTP status code into a :class:`FetchDiagnostic`.

    Codes outside the two closed sets fall through to ``http_error`` so
    callers can still produce a diagnostic for non-2xx responses that
    were not explicitly categorized (e.g. 418, 451).

    Status codes below 400 return ``unknown_fetch_error`` — the helper
    assumes 2xx/3xx outcomes are not failures and would normally be
    handled by the caller without consulting the diagnostic boundary.
    """
    if status_code in _BLOCKED_OR_FORBIDDEN_CODES:
        return _diag(FetchCategory.BLOCKED_OR_FORBIDDEN)
    if status_code in _HTTP_ERROR_CODES:
        return _diag(FetchCategory.HTTP_ERROR)
    if 400 <= status_code < 500:
        # 400, 404, 405, ... — client errors that are not auth/forbidden
        # or rate-limit. They are not transient; treat as http_error so
        # callers can surface them but never retry blindly.
        return _diag(FetchCategory.HTTP_ERROR)
    return _diag(FetchCategory.UNKNOWN_FETCH_ERROR)


# ---------------------------------------------------------------------------
# Operator-facing formatting
# ---------------------------------------------------------------------------

# Maximum length of any operator-facing diagnostic line. Anything longer
# would defeat the "short_reason" contract.
_MAX_OPERATOR_LINE_LEN = 120


def format_operator_safe(diagnostic: FetchDiagnostic) -> str:
    """Render a diagnostic as a single operator-facing line.

    The output is guaranteed to contain only the four fields, joined
    with a colon-separated key=value form. No raw URL, body, header, or
    exception text is included.
    """
    parts = [
        f"category={diagnostic.category.value}",
        f"short_reason={diagnostic.short_reason}",
        f"retry_hint={diagnostic.retry_hint}",
        f"is_transient={str(diagnostic.is_transient).lower()}",
    ]
    line = "; ".join(parts)
    if len(line) > _MAX_OPERATOR_LINE_LEN:
        line = line[: _MAX_OPERATOR_LINE_LEN - 1] + "…"
    return line


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _diag(category: FetchCategory) -> FetchDiagnostic:
    """Build a :class:`FetchDiagnostic` from a fixed category.

    Internal factory used by both classification paths so we never
    assemble a diagnostic by hand and risk leaking partial state.
    """
    return FetchDiagnostic(
        category=category,
        short_reason=_SHORT_REASONS[category],
        retry_hint=_RETRY_HINTS[category],
        is_transient=_IS_TRANSIENT[category],
    )
