"""Crawl path filter helper.

Establishes rules for allowing or denying URLs during crawling to protect
crawl budget without modifying crawler traversal behavior.
"""

from __future__ import annotations


def should_crawl_url(url: str, rules: dict | None = None) -> bool:
    """Determine if a URL should be crawled based on filtering rules.

    This is a pure function. It has no side effects, no network or disk I/O,
    and does not mutate any global state.

    Precedence rules:
      1. Empty/invalid URL -> Deny (False)
      2. No rules or empty rules dict -> Allow (True)
      3. Protected pattern matched -> Allow (True)
      4. Allow pattern matched -> Allow (True)
      5. Deny pattern matched -> Deny (False)
      6. Default -> Allow (True)

    Args:
        url: The URL to check.
        rules: Optional dictionary containing 'allow_patterns',
            'deny_patterns', and 'protected_patterns' lists of substrings.

    Returns:
        True if the URL is allowed to be crawled, False otherwise.
    """
    if not url or not isinstance(url, str) or not url.strip():
        return False

    if not rules:
        return True

    url_lower = url.lower()

    protected_patterns = rules.get("protected_patterns")
    allow_patterns = rules.get("allow_patterns")
    deny_patterns = rules.get("deny_patterns")

    # 1. Protected patterns override any deny rules
    if protected_patterns:
        for pattern in protected_patterns:
            if isinstance(pattern, str) and pattern.lower() in url_lower:
                return True

    # 2. Allow patterns override deny rules
    if allow_patterns:
        for pattern in allow_patterns:
            if isinstance(pattern, str) and pattern.lower() in url_lower:
                return True

    # 3. Explicit deny patterns block crawling
    if deny_patterns:
        for pattern in deny_patterns:
            if isinstance(pattern, str) and pattern.lower() in url_lower:
                return False

    # 4. Default fallback is to allow
    return True
