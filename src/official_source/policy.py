"""Official Buk-gu source allowlist and per-fact freshness policy.

Origin is derived from committed official-snapshot metadata
(``data/official_snapshots/bukgu_gwangju/*.json`` → ``https://bukgu.gwangju.kr``).

Phase 1 allowlists exact HTTPS URLs only. No network I/O.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final
from urllib.parse import parse_qs, urlparse, urlunparse

from .models import ErrorCode, FactKind

# Derived from committed official snapshot source URLs.
OFFICIAL_ORIGIN: Final[str] = "https://bukgu.gwangju.kr"
OFFICIAL_HOST: Final[str] = "bukgu.gwangju.kr"
OFFICIAL_SCHEME: Final[str] = "https"

# Explicit freshness threshold (7 days). Not unexplained arithmetic in callers.
DEFAULT_MAX_AGE_SECONDS: Final[int] = 7 * 24 * 60 * 60

# Max HTML body accepted from transport (bytes of UTF-8).
DEFAULT_MAX_BODY_BYTES: Final[int] = 512_000

# Allowed clock skew: retrieved_at may be slightly ahead of evaluated_at.
DEFAULT_CLOCK_SKEW_SECONDS: Final[int] = 60


@dataclass(frozen=True)
class OfficialSourcePolicy:
    """Per-fact retrieval policy bound to an allowlisted official URL."""

    fact_kind: FactKind
    url: str
    title: str
    # Substrings that must appear in page <title> (identity check).
    expected_title_tokens: tuple[str, ...]
    max_age_seconds: int = DEFAULT_MAX_AGE_SECONDS
    fact_marker: str = ""
    max_body_bytes: int = DEFAULT_MAX_BODY_BYTES

    def to_dict(self) -> dict[str, object]:
        return {
            "fact_kind": self.fact_kind.value,
            "url": self.url,
            "title": self.title,
            "expected_title_tokens": list(self.expected_title_tokens),
            "max_age_seconds": self.max_age_seconds,
            "fact_marker": self.fact_marker,
            "max_body_bytes": self.max_body_bytes,
        }


# Narrow Phase-1 allowlist: one official page per supported fact.
# Paths are policy targets under the committed official origin (not live-fetched).
_POLICIES: Final[dict[FactKind, OfficialSourcePolicy]] = {
    FactKind.CURRENT_MAYOR: OfficialSourcePolicy(
        fact_kind=FactKind.CURRENT_MAYOR,
        url="https://bukgu.gwangju.kr/menu.es?mid=a10101010100",
        title="구청장 소개",
        expected_title_tokens=("구청장",),
        max_age_seconds=DEFAULT_MAX_AGE_SECONDS,
        fact_marker="current_mayor",
    ),
    FactKind.JURISDICTION_NAME: OfficialSourcePolicy(
        fact_kind=FactKind.JURISDICTION_NAME,
        url="https://bukgu.gwangju.kr/",
        title="광주광역시 북구청",
        expected_title_tokens=("북구",),
        max_age_seconds=DEFAULT_MAX_AGE_SECONDS,
        fact_marker="jurisdiction_name",
    ),
}


def get_policy_for_fact(fact_kind: FactKind) -> OfficialSourcePolicy:
    try:
        return _POLICIES[fact_kind]
    except KeyError as exc:
        raise KeyError(f"no official-source policy for fact_kind={fact_kind!r}") from exc


def all_policies() -> tuple[OfficialSourcePolicy, ...]:
    return tuple(_POLICIES[kind] for kind in FactKind)


def _reject_reason(url: object) -> str | None:
    """Return a rejection reason code, or None if the URL shape is acceptable."""
    if not isinstance(url, str) or not url.strip():
        return "empty_url"
    raw = url.strip()
    if raw.startswith("//"):
        return "protocol_relative"
    lowered = raw.lower()
    if lowered.startswith("javascript:") or lowered.startswith("data:"):
        return "disallowed_scheme"
    if "\\" in raw:
        return "malformed_authority"

    try:
        parsed = urlparse(raw)
    except Exception:
        return "malformed_url"

    scheme = (parsed.scheme or "").lower()
    if scheme == "http":
        return "http_downgrade"
    if scheme != "https":
        return "disallowed_scheme"
    if not parsed.netloc:
        return "missing_host"
    if parsed.username is not None or parsed.password is not None or "@" in parsed.netloc:
        return "userinfo_present"

    host = (parsed.hostname or "").lower()
    if not host:
        return "missing_host"
    # Exact host match only — reject deceptive suffix/prefix hosts.
    if host != OFFICIAL_HOST:
        return "non_allowlisted_host"
    if host.endswith(f".{OFFICIAL_HOST}") or OFFICIAL_HOST in host and host != OFFICIAL_HOST:
        return "deceptive_host"

    port = parsed.port
    if port is not None and port != 443:
        return "unexpected_port"
    return None


def canonicalize_official_url(url: str) -> str | None:
    """Return a comparable canonical HTTPS form, or None if rejected."""
    if _reject_reason(url) is not None:
        return None
    raw = url.strip()
    parsed = urlparse(raw)
    host = (parsed.hostname or "").lower()
    path = parsed.path or "/"
    if path != "/" and path.endswith("/"):
        path = path.rstrip("/")
    query = ""
    if parsed.query:
        qs = parse_qs(parsed.query, keep_blank_values=True)
        parts: list[str] = []
        for key in sorted(qs.keys()):
            for value in qs[key]:
                parts.append(f"{key}={value}")
        query = "&".join(parts)
    return urlunparse(("https", host, path, "", query, ""))


def is_official_host(url: str) -> bool:
    if _reject_reason(url) is not None:
        return False
    parsed = urlparse(url.strip())
    return (parsed.hostname or "").lower() == OFFICIAL_HOST


def assess_url_allowlist(
    url: str,
    fact_kind: FactKind | None = None,
) -> dict[str, object]:
    """Assess whether ``url`` is on the closed official allowlist."""
    reason = _reject_reason(url)
    if reason is not None:
        code = ErrorCode.SOURCE_NOT_ALLOWLISTED
        if reason == "http_downgrade":
            code = ErrorCode.SOURCE_NOT_ALLOWLISTED
        return {
            "allowed": False,
            "reason": reason,
            "failure_code": code,
            "canonical": None,
        }

    canon = canonicalize_official_url(url)
    if canon is None:
        return {
            "allowed": False,
            "reason": "canonicalize_failed",
            "failure_code": ErrorCode.SOURCE_NOT_ALLOWLISTED,
            "canonical": None,
        }

    if fact_kind is not None:
        policy = get_policy_for_fact(fact_kind)
        policy_canon = canonicalize_official_url(policy.url)
        allowed = canon == policy_canon
    else:
        allowed = canon in allowlisted_urls()

    return {
        "allowed": allowed,
        "reason": "ok" if allowed else "path_not_allowlisted",
        "failure_code": None if allowed else ErrorCode.SOURCE_NOT_ALLOWLISTED,
        "canonical": canon,
    }


def is_url_allowlisted(url: str, fact_kind: FactKind | None = None) -> bool:
    return bool(assess_url_allowlist(url, fact_kind)["allowed"])


def allowlisted_urls() -> frozenset[str]:
    urls: set[str] = set()
    for policy in _POLICIES.values():
        canon = canonicalize_official_url(policy.url)
        if canon:
            urls.add(canon)
    return frozenset(urls)


__all__ = [
    "DEFAULT_CLOCK_SKEW_SECONDS",
    "DEFAULT_MAX_AGE_SECONDS",
    "DEFAULT_MAX_BODY_BYTES",
    "OFFICIAL_HOST",
    "OFFICIAL_ORIGIN",
    "OFFICIAL_SCHEME",
    "OfficialSourcePolicy",
    "all_policies",
    "allowlisted_urls",
    "assess_url_allowlist",
    "canonicalize_official_url",
    "get_policy_for_fact",
    "is_official_host",
    "is_url_allowlisted",
]
