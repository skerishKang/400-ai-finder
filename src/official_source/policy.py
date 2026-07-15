"""Official Buk-gu source allowlist and per-fact freshness policy.

Phase 1 uses a closed allowlist of official ``bukgu.gwangju.kr`` URLs.
Non-allowlisted hosts and paths are rejected fail-closed before any fact
is returned. This module performs no network I/O.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final
from urllib.parse import parse_qs, urlparse, urlunparse

from .models import FactKind

# Official origin only — never expand to arbitrary web search hosts.
OFFICIAL_ORIGIN: Final[str] = "https://bukgu.gwangju.kr"
OFFICIAL_HOST: Final[str] = "bukgu.gwangju.kr"

# Default max age for "current" civic facts (7 days). Stale beyond this.
DEFAULT_MAX_AGE_SECONDS: Final[int] = 7 * 24 * 60 * 60


@dataclass(frozen=True)
class OfficialSourcePolicy:
    """Per-fact retrieval policy bound to an allowlisted official URL."""

    fact_kind: FactKind
    url: str
    title: str
    max_age_seconds: int = DEFAULT_MAX_AGE_SECONDS
    # Selector hint for extractors (stable fixture/contract marker).
    fact_marker: str = ""

    def to_dict(self) -> dict[str, object]:
        return {
            "fact_kind": self.fact_kind.value,
            "url": self.url,
            "title": self.title,
            "max_age_seconds": self.max_age_seconds,
            "fact_marker": self.fact_marker,
        }


# Narrow Phase-1 allowlist: one official page per supported fact.
_POLICIES: Final[dict[FactKind, OfficialSourcePolicy]] = {
    FactKind.CURRENT_MAYOR: OfficialSourcePolicy(
        fact_kind=FactKind.CURRENT_MAYOR,
        url="https://bukgu.gwangju.kr/menu.es?mid=a10101010100",
        title="구청장 소개",
        max_age_seconds=DEFAULT_MAX_AGE_SECONDS,
        fact_marker="current_mayor",
    ),
    FactKind.JURISDICTION_NAME: OfficialSourcePolicy(
        fact_kind=FactKind.JURISDICTION_NAME,
        url="https://bukgu.gwangju.kr/",
        title="광주광역시 북구청",
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


def canonicalize_official_url(url: str) -> str | None:
    """Return a comparable canonical form, or None if not HTTP(S)."""
    if not isinstance(url, str) or not url.strip():
        return None
    raw = url.strip()
    parsed = urlparse(raw)
    if parsed.scheme not in ("http", "https"):
        return None
    if not parsed.netloc:
        return None
    host = parsed.hostname.lower() if parsed.hostname else ""
    # Drop default ports; keep path; sort query for mid-style pages.
    path = parsed.path or "/"
    if path != "/" and path.endswith("/"):
        path = path.rstrip("/")
    query = ""
    if parsed.query:
        qs = parse_qs(parsed.query, keep_blank_values=True)
        # Prefer mid-based identity for Buk-gu menu pages.
        parts: list[str] = []
        for key in sorted(qs.keys()):
            for value in qs[key]:
                parts.append(f"{key}={value}")
        query = "&".join(parts)
    # Force https for official host comparison.
    scheme = "https" if host == OFFICIAL_HOST else parsed.scheme.lower()
    return urlunparse((scheme, host, path, "", query, ""))


def is_official_host(url: str) -> bool:
    parsed = urlparse(url.strip() if isinstance(url, str) else "")
    host = (parsed.hostname or "").lower()
    return host == OFFICIAL_HOST


def is_url_allowlisted(url: str, fact_kind: FactKind | None = None) -> bool:
    """True iff ``url`` matches the closed official allowlist.

    When ``fact_kind`` is provided, the URL must match that fact's policy URL.
    When omitted, the URL must match any policy URL.
    """
    canon = canonicalize_official_url(url)
    if canon is None:
        return False
    if not is_official_host(canon):
        return False

    if fact_kind is not None:
        policy = get_policy_for_fact(fact_kind)
        return canon == canonicalize_official_url(policy.url)

    allowed = {
        canonicalize_official_url(policy.url)
        for policy in _POLICIES.values()
    }
    return canon in allowed


def allowlisted_urls() -> frozenset[str]:
    urls: set[str] = set()
    for policy in _POLICIES.values():
        canon = canonicalize_official_url(policy.url)
        if canon:
            urls.add(canon)
    return frozenset(urls)


__all__ = [
    "DEFAULT_MAX_AGE_SECONDS",
    "OFFICIAL_HOST",
    "OFFICIAL_ORIGIN",
    "OfficialSourcePolicy",
    "all_policies",
    "allowlisted_urls",
    "canonicalize_official_url",
    "get_policy_for_fact",
    "is_official_host",
    "is_url_allowlisted",
]
