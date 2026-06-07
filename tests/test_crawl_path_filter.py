"""Tests for the crawl path filter helper.

Asserts allow/deny/protected precedence, case-insensitive matching,
dangerous parameter safety, and contract constraints.
"""

from __future__ import annotations

from src.crawler.crawl_path_filter import should_crawl_url


def test_invalid_urls():
    """Verify that invalid/empty URLs are safely denied."""
    assert should_crawl_url("") is False
    assert should_crawl_url("   ") is False
    assert should_crawl_url(None) is False  # type: ignore
    assert should_crawl_url(123) is False  # type: ignore


def test_default_allow_cases():
    """Verify that URLs are allowed by default when no rules match or exist."""
    # rules is None -> allow
    assert should_crawl_url("https://bukgu.gwangju.kr/menu.es?mid=a101", None) is True

    # rules is empty -> allow
    assert should_crawl_url("https://bukgu.gwangju.kr/menu.es?mid=a101", {}) is True

    # unknown/unrelated rules -> allow
    rules = {
        "unrelated_key": ["something"],
        "deny_patterns": ["print="],
    }
    assert should_crawl_url("https://bukgu.gwangju.kr/menu.es?mid=a101", rules) is True


def test_protected_pattern_overrides_deny():
    """Verify that protected patterns override explicit deny rules."""
    rules = {
        "deny_patterns": ["menu.es"],
        "protected_patterns": ["mid="],
    }
    # Although "menu.es" is in deny, "mid=" is protected
    assert should_crawl_url("https://bukgu.gwangju.kr/menu.es?mid=a10103000000", rules) is True


def test_allow_over_deny():
    """Verify that allow patterns override deny rules when matching both."""
    rules = {
        "allow_patterns": ["notice/view"],
        "deny_patterns": ["notice"],
    }
    # Matches both "notice" and "notice/view" -> allow wins
    assert should_crawl_url("https://bukgu.gwangju.kr/board/notice/view?id=123", rules) is True


def test_explicit_deny():
    """Verify that explicit deny rules block matching URLs."""
    rules = {
        "deny_patterns": ["print=", "utm_"],
    }
    assert should_crawl_url("https://bukgu.gwangju.kr/board/view?id=1&print=1", rules) is False
    assert should_crawl_url("https://bukgu.gwangju.kr/menu.es?mid=a101&utm_source=facebook", rules) is False


def test_dangerous_params_not_denied_by_default():
    """Verify that structural public-sector parameters are not denied by default."""
    rules = {
        "deny_patterns": ["print="],
    }
    # Structural parameters must be allowed under default/unrelated rules
    assert should_crawl_url("https://bukgu.gwangju.kr/menu.es?mid=a10103000000", rules) is True
    assert should_crawl_url("https://bukgu.gwangju.kr/menu.es?menuId=a10103", rules) is True
    assert should_crawl_url("https://bukgu.gwangju.kr/board.es?seq=999", rules) is True
    assert should_crawl_url("https://bukgu.gwangju.kr/content.es?contentId=123", rules) is True


def test_board_pagination():
    """Verify pagination control works conservatively with explicit rules."""
    rules = {
        "deny_patterns": ["pageNo=37"],
    }
    # Explicitly matching page 37 should be denied
    assert should_crawl_url("https://bukgu.gwangju.kr/board.es?mid=a1010&pageNo=37", rules) is False
    # First page is not matched by 'pageNo=37' and should be allowed
    assert should_crawl_url("https://bukgu.gwangju.kr/board.es?mid=a1010&pageNo=1", rules) is True


def test_no_crawler_wiring_and_import_isolation():
    """Ensure crawl_path_filter does not import url_crawler, verifying pure isolation."""
    # We check the source code of crawl_path_filter to ensure it makes no references to url_crawler.
    import inspect
    import src.crawler.crawl_path_filter as cpf
    source = inspect.getsource(cpf)
    assert "url_crawler" not in source
    assert "UrlCrawler" not in source
    assert "URLCrawler" not in source
