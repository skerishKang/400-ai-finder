"""Lock the legacy direct-requests fallback contracts for the crawler.

Issue #834 (first compatibility PR): before the crawler/mapper are refactored
to route every fetch through the fetch-provider abstraction, this file pins the
*current* behavior of the fallback path that runs when ``fetch_provider=None``.

All HTTP is blocked via monkeypatch. ``URLCrawler()`` and ``HomepageMapper()``
are constructed WITHOUT a ``fetch_provider`` argument, so the original direct
``requests.get`` code path is exercised. No real network, no real provider, no
DNS, no live server, no API/LLM/Firecrawl call is used.

These are mock-only compatibility baseline tests. They must stay green through
the refactor so the new code preserves the documented fallback semantics.

legacy fallback / fetch_provider=None / no network / compatibility baseline
"""

from __future__ import annotations

import pytest


class FakeResponse:
    """Minimal stand-in for a ``requests`` Response used by the fallback path."""

    def __init__(
        self,
        *,
        status_code=200,
        url="https://example.test/final",
        content_type="text/html; charset=utf-8",
        text="",
        encoding="utf-8",
        apparent_encoding="utf-8",
    ):
        self.status_code = status_code
        self.url = url
        self.headers = {"Content-Type": content_type}
        self.text = text
        self.encoding = encoding
        self.apparent_encoding = apparent_encoding


# Sample HTML with title, meta description, and internal links so the legacy
# extraction behavior can be asserted deterministically.
_SAMPLE_HTML = """<!DOCTYPE html>
<html>
<head>
  <title>예시 첫 화면</title>
  <meta name="description" content="예시 설명입니다">
</head>
<body>
  <nav>
    <a href="/notice">공지사항</a>
    <a href="/intro">기관소개</a>
    <a href="https://other.test/external">외부</a>
  </nav>
</body>
</html>
"""


# ===========================================================================
# A. URLCrawler legacy fallback (fetch_provider=None -> _analyze_original)
# ===========================================================================
def test_urlcrawler_legacy_200_html(monkeypatch):
    """legacy fallback / fetch_provider=None / no network / compatibility baseline.

    A normal 200 HTML response is fetched exactly once with the configured
    User-Agent and timeout, the redirect final URL is reflected in result["url"],
    and title/description/clean text/internal links are extracted.
    """
    from src.crawler.url_crawler import URLCrawler

    fake = FakeResponse(
        status_code=200,
        url="https://example.test/final",
        content_type="text/html; charset=utf-8",
        text=_SAMPLE_HTML,
    )
    get_mock = None

    def _get(url, headers=None, timeout=None):
        nonlocal get_mock
        get_mock = (url, headers, timeout)
        return fake

    monkeypatch.setattr("src.crawler.url_crawler.requests.get", _get)

    crawler = URLCrawler(timeout=7, user_agent="ContractUA")
    assert crawler.fetch_provider is None
    result = crawler.analyze("https://example.test/start", correlation_id="c1")

    # Exactly one call, with the expected headers and timeout.
    assert get_mock is not None
    _url, headers, timeout = get_mock
    assert headers == {"User-Agent": "ContractUA"}
    assert timeout == 7

    assert result["status_code"] == 200
    assert result["url"] == "https://example.test/final"
    assert result["content_type"] == "text/html; charset=utf-8"
    assert result["title"] == "예시 첫 화면"
    assert result["description"] == "예시 설명입니다"
    assert "공지사항" in result["text"]
    assert result["errors"] == []
    internal = result["links"]["internal"]
    internal_urls = {link["url"] for link in internal}
    assert "https://example.test/notice" in internal_urls
    assert "https://example.test/intro" in internal_urls
    # External link kept separate from internal.
    assert any(link["url"] == "https://other.test/external" for link in result["links"]["external"])


def test_urlcrawler_legacy_404_html(monkeypatch):
    """legacy fallback / fetch_provider=None / no network / compatibility baseline.

    Unlike the provider path (which early-returns on a non-ok result and does not
    analyze HTML), the legacy path still analyzes the HTML body on a 4xx and
    records a distinct error string. This difference is asserted explicitly.
    """
    from src.crawler.url_crawler import URLCrawler

    fake = FakeResponse(
        status_code=404,
        url="https://example.test/notfound",
        content_type="text/html; charset=utf-8",
        text=_SAMPLE_HTML,
    )

    def _get(url, headers=None, timeout=None):
        return fake

    monkeypatch.setattr("src.crawler.url_crawler.requests.get", _get)

    crawler = URLCrawler(timeout=7, user_agent="ContractUA")
    result = crawler.analyze("https://example.test/page", correlation_id="c2")

    # Legacy path records the HTTP error AND still parses the body.
    assert result["errors"] == ["HTTP Error: Status code 404"]
    assert result["status_code"] == 404
    assert result["title"] == "예시 첫 화면"
    assert "공지사항" in result["text"]


def test_urlcrawler_legacy_non_html_200(monkeypatch):
    """legacy fallback / fetch_provider=None / no network / compatibility baseline.

    A 200 with a non-HTML content type is rejected with a content-type error and
    the body text stays empty, but url/status/content_type are still populated.
    """
    from src.crawler.url_crawler import URLCrawler

    fake = FakeResponse(
        status_code=200,
        url="https://example.test/file.pdf",
        content_type="application/pdf",
        text="%PDF-1.4 binary contents",
    )

    def _get(url, headers=None, timeout=None):
        return fake

    monkeypatch.setattr("src.crawler.url_crawler.requests.get", _get)

    crawler = URLCrawler(timeout=7, user_agent="ContractUA")
    result = crawler.analyze("https://example.test/file.pdf", correlation_id="c3")

    assert result["errors"] == ["Response content type is not HTML: application/pdf"]
    assert result["text"] == ""
    assert result["url"] == "https://example.test/file.pdf"
    assert result["status_code"] == 200
    assert result["content_type"] == "application/pdf"


def test_urlcrawler_legacy_timeout(monkeypatch):
    """legacy fallback / fetch_provider=None / no network / compatibility baseline."""
    from src.crawler.url_crawler import URLCrawler
    import requests

    def _get(url, headers=None, timeout=None):
        raise requests.exceptions.Timeout("timed out")

    monkeypatch.setattr("src.crawler.url_crawler.requests.get", _get)

    crawler = URLCrawler(timeout=7, user_agent="ContractUA")
    result = crawler.analyze("https://example.test/slow", correlation_id="c4")

    assert result["errors"] == ["Request timeout after 7 seconds."]


def test_urlcrawler_legacy_request_exception(monkeypatch):
    """legacy fallback / fetch_provider=None / no network / compatibility baseline."""
    from src.crawler.url_crawler import URLCrawler
    import requests

    def _get(url, headers=None, timeout=None):
        raise requests.exceptions.RequestException("boom")

    monkeypatch.setattr("src.crawler.url_crawler.requests.get", _get)

    crawler = URLCrawler(timeout=7, user_agent="ContractUA")
    result = crawler.analyze("https://example.test/err", correlation_id="c5")

    assert result["errors"] == ["Network error: boom"]


# ===========================================================================
# B. HomepageMapper legacy fallback (fetch_provider=None -> original path)
# ===========================================================================
def test_homepagemapper_legacy_200_with_redirect(monkeypatch):
    """legacy fallback / fetch_provider=None / no network / compatibility baseline.

    fetch_content with the original path fetches once with the crawler's
    User-Agent header and timeout, returns the response text, no error, status
    200, and the redirect final URL.
    """
    from src.crawler.homepage_mapper import HomepageMapper

    fake = FakeResponse(
        status_code=200,
        url="https://example.test/final",
        content_type="text/html; charset=utf-8",
        text=_SAMPLE_HTML,
    )
    calls = []

    def _get(url, headers=None, timeout=None):
        calls.append((url, headers, timeout))
        return fake

    monkeypatch.setattr("src.crawler.homepage_mapper.requests.get", _get)

    mapper = HomepageMapper(timeout=7)
    # Default construction keeps fetch_provider unsent -> None (legacy path).
    assert mapper.fetch_provider is None

    content, error, status, final_url = mapper.fetch_content(
        "https://example.test/start", retries=1
    )

    assert len(calls) == 1
    _url, headers, timeout = calls[0]
    assert headers == mapper.crawler.headers
    assert timeout == 7

    assert content == _SAMPLE_HTML
    assert error is None
    assert status == 200
    assert final_url == "https://example.test/final"


def test_homepagemapper_legacy_503_retry(monkeypatch):
    """legacy fallback / fetch_provider=None / no network / compatibility baseline.

    Two 503 responses exhaust retries=1 (2 attempts): content is None, error is
    the HTTP status string, status is None, and the final URL is the original.
    """
    from src.crawler.homepage_mapper import HomepageMapper

    resp503 = FakeResponse(
        status_code=503,
        url="https://example.test/start",
        content_type="text/html; charset=utf-8",
        text="<html><body>503</body></html>",
    )
    calls = []

    def _get(url, headers=None, timeout=None):
        calls.append((url, headers, timeout))
        return resp503

    monkeypatch.setattr("src.crawler.homepage_mapper.requests.get", _get)

    mapper = HomepageMapper(timeout=7)
    assert mapper.fetch_provider is None

    content, error, status, final_url = mapper.fetch_content(
        "https://example.test/start", retries=1
    )

    assert len(calls) == 2  # original attempt + 1 retry
    assert content is None
    assert error == "HTTP Error: 503"
    assert status is None
    assert final_url == "https://example.test/start"


def test_homepagemapper_legacy_timeout_retry(monkeypatch):
    """legacy fallback / fetch_provider=None / no network / compatibility baseline.

    Two timeouts exhaust retries=1 (2 attempts); the recorded error is the
    timeout message built from the crawler timeout.
    """
    from src.crawler.homepage_mapper import HomepageMapper
    import requests

    calls = []

    def _get(url, headers=None, timeout=None):
        calls.append((url, headers, timeout))
        raise requests.exceptions.Timeout("timed out")

    monkeypatch.setattr("src.crawler.homepage_mapper.requests.get", _get)

    mapper = HomepageMapper(timeout=7)
    assert mapper.fetch_provider is None

    content, error, status, final_url = mapper.fetch_content(
        "https://example.test/start", retries=1
    )

    assert len(calls) == 2
    assert content is None
    assert error == "Timeout after 7s"
    assert status is None


def test_homepagemapper_legacy_timeout_then_200(monkeypatch):
    """legacy fallback / fetch_provider=None / no network / compatibility baseline.

    A timeout on the first attempt is recovered on the retry (200), yielding the
    success result after exactly two calls.
    """
    from src.crawler.homepage_mapper import HomepageMapper
    import requests

    ok = FakeResponse(
        status_code=200,
        url="https://example.test/final",
        content_type="text/html; charset=utf-8",
        text=_SAMPLE_HTML,
    )
    calls = []

    def _get(url, headers=None, timeout=None):
        calls.append((url, headers, timeout))
        if len(calls) == 1:
            raise requests.exceptions.Timeout("timed out")
        return ok

    monkeypatch.setattr("src.crawler.homepage_mapper.requests.get", _get)

    mapper = HomepageMapper(timeout=7)
    assert mapper.fetch_provider is None

    content, error, status, final_url = mapper.fetch_content(
        "https://example.test/start", retries=1
    )

    assert len(calls) == 2
    assert content == _SAMPLE_HTML
    assert error is None
    assert status == 200
    assert final_url == "https://example.test/final"
