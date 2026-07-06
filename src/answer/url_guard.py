"""Answer output URL guard — canonicalize and allowlist-check provider URLs.

Pure, standard-library-only. No fetching, no provider calls, no mutations.
"""

from __future__ import annotations

import re
from typing import Any
from urllib.parse import urlparse, urlunparse


def canonicalize_url(url: str) -> str | None:
    """Canonicalize an absolute HTTP/HTTPS URL for exact-comparison allowlisting.

    Returns the canonicalized URL string, or *None* if the URL is rejected
    (unsupported scheme, credentials, missing host, malformed authority,
    relative path, or dot-segment path).

    Contract per issue #841:
    - accept absolute http/https URLs only;
    - lowercase scheme and hostname;
    - remove explicit default port (:80 for http, :443 for https);
      retain non-default ports;
    - discard fragments for comparison;
    - preserve query strings exactly (including order and encoding);
    - preserve percent-encoded path bytes and slash structure;
    - reject literal dot-segment paths rather than decoding or resolving them;
    - reject credentials, missing hosts, malformed authorities, relative URLs,
      and unsupported schemes;
    - compare the fully canonicalized URL for equality only.
    """
    if not url:
        return None

    # Reject credentials or malformed authority symbols directly in raw URL representation
    # before urlparse resolves or corrects them.
    if "@" in url:
        return None

    try:
        parsed = urlparse(url)
        # Access parsed.port early inside try/except block because it can raise ValueError
        # for malformed ports (e.g. non-integer or out of range).
        port = parsed.port
    except Exception:
        return None

    netloc = parsed.netloc
    # Reject netloc with trailing colon (e.g. example.com:), missing host, or malformed characters.
    if netloc.endswith(":") or not netloc:
        return None

    scheme = parsed.scheme.lower()
    if scheme not in ("http", "https"):
        return None

    hostname = parsed.hostname
    if not hostname:
        return None

    # Reject credentials in the authority.
    if parsed.username or parsed.password:
        return None

    # Reject dot-segment paths ("/../", "/./", or path ending with "/..", "/.")
    path = parsed.path
    if "/../" in path or "/./" in path or path.endswith("/..") or path.endswith("/."):
        return None

    netloc_lower = netloc.lower()

    # Remove explicit default port.
    if port is not None:
        default_port = 80 if scheme == "http" else 443
        if port == default_port:
            # Rebuild netloc without the port.
            netloc_lower = hostname.lower()
            # Preserve any non-default userinfo (already rejected above,
            # but defensive).
    elif netloc != hostname.lower():
        # netloc may contain userinfo or other malformation without a port;
        # hostname already validated, but if netloc diverges without port it
        # likely has credentials we missed or is malformed.
        # Re-derive from hostname only.
        netloc_lower = hostname.lower()

    # Preserve params (rare in practice but contract says keep structure).
    params = parsed.params
    # Preserve query exactly.
    query = parsed.query
    # Discard fragment.
    fragment = ""

    return urlunparse((scheme, netloc_lower, path, params, query, fragment))


# ------------------------------------------------------------------
# URL extraction from Markdown output
# ------------------------------------------------------------------

# Bare HTTP(S) URL: standalone http/https URL not inside Markdown link syntax.
_BARE_URL_RE = re.compile(
    r'(?:^|[\s(\[{"\'‘“])'  # preceded by whitespace/open-bracket/quote
    r'(https?://[^\s)\]>"\'’”\\]+)'  # the URL itself
    r'(?:[\s)\]>"\'’”\\]|$)',  # terminated by whitespace/close-bracket/quote/end
    re.IGNORECASE,
)

# Markdown inline link destination: [text](destination)
_MARKDOWN_LINK_RE = re.compile(
    r'\[([^\]]*)\]\(([^)]+)\)',
)

# Markdown autolink: <URL> (URI scheme followed by colon, no whitespace, e.g. <https://...> or <mailto:...>)
# Matches scheme starting with letter followed by letters/digits/+/./- then a colon, and no spaces inside <...>
_AUTOLINK_RE = re.compile(
    r'<([a-zA-Z][a-zA-Z0-9+.-]*:[^\s>]+)>',
)


def extract_urls_from_markdown(markdown: str) -> list[dict[str, str]]:
    """Extract candidate URLs from provider Markdown output.

    Returns a list of dicts, each with:
      - ``url``: the raw URL string as it appeared in the text
      - ``kind``: one of ``"bare"``, ``"markdown_link"``, ``"autolink"``

    Relative links, non-HTTP(S) destinations, and empty destinations are
    identified but not returned as candidate URLs — they are untrusted
    by definition and will cause guard failure if present as link destinations.
    """
    candidates: list[dict[str, str]] = []
    untrusted: list[dict[str, str]] = []

    # Track spans occupied by markdown link destinations so autolinks and
    # bare URLs inside them are not double-counted.
    link_spans: list[tuple[int, int]] = []

    # Markdown inline links
    for m in _MARKDOWN_LINK_RE.finditer(markdown):
        destination = m.group(2).strip()
        # Strip optional angle-bracket wrappers: [text](<url>)
        if destination.startswith("<") and destination.endswith(">"):
            destination = destination[1:-1].strip()
        if not destination:
            continue
        link_spans.append((m.start(2), m.end(2)))
        try:
            parsed = urlparse(destination)
            scheme = parsed.scheme
        except Exception:
            scheme = ""
        if scheme in ("http", "https"):
            candidates.append({"url": destination, "kind": "markdown_link"})
        else:
            untrusted.append({"url": destination, "kind": "markdown_link"})

    # Autolinks — skip those inside a markdown link destination span.
    for m in _AUTOLINK_RE.finditer(markdown):
        if any(s <= m.start() < e for s, e in link_spans):
            continue
        url = m.group(1).strip()
        if not url:
            continue
        try:
            parsed = urlparse(url)
            scheme = parsed.scheme.lower()
        except Exception:
            scheme = ""
        if scheme in ("http", "https"):
            candidates.append({"url": url, "kind": "autolink"})
        else:
            untrusted.append({"url": url, "kind": "autolink"})

    # Bare URLs — skip those inside a markdown link destination span.
    for m in _BARE_URL_RE.finditer(markdown):
        if any(s <= m.start(1) < e for s, e in link_spans):
            continue
        url = m.group(1)
        candidates.append({"url": url, "kind": "bare"})

    return candidates + untrusted


def assess_url_allowlist(
    answer_markdown: str,
    sources: list[dict],
) -> dict[str, Any]:
    """Assess whether all URLs in the provider output are allowlisted.

    Build an allowlist from source ``url`` and ``canonical_url`` fields.
    Canonicalize each allowlist entry and each candidate output URL.
    Allow only an exact canonical match.

    Returns a dict with:
      - ``passed``: bool — True if every output URL is allowlisted
      - ``blocked_urls``: list of raw URLs that failed allowlist
      - ``allowlist``: list of canonical source URLs used for checking
    """
    # Build allowlist from source URLs.
    allowlist_raw: list[str] = []
    for src in sources:
        for key in ("url", "canonical_url"):
            val = src.get(key, "")
            if val:
                allowlist_raw.append(val)

    # Canonicalize allowlist.
    allowlist_canonical: set[str] = set()
    for raw in allowlist_raw:
        canon = canonicalize_url(raw)
        if canon is not None:
            allowlist_canonical.add(canon)

    # Extract candidate URLs from answer.
    candidates = extract_urls_from_markdown(answer_markdown)

    # Check each candidate.
    blocked: list[str] = []
    for cand in candidates:
        raw_url = cand["url"]
        canon = canonicalize_url(raw_url)
        if canon is None:
            # Unsupported/relative/non-HTTP — always blocked.
            blocked.append(raw_url)
        elif canon not in allowlist_canonical:
            blocked.append(raw_url)

    return {
        "passed": len(blocked) == 0,
        "blocked_urls": blocked,
        "allowlist": sorted(allowlist_canonical),
    }
