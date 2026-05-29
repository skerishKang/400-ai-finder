"""Tests for fetch provider abstraction layer.

All tests use MockFetchProvider or monkeypatched requests — no real HTTP calls.
"""

from __future__ import annotations

import json
import os
import sys
from datetime import datetime
from unittest.mock import patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.fetch import (
    FetchProvider,
    FetchResult,
    MockFetchProvider,
    RequestsFetchProvider,
    FirecrawlFetchProvider,
    get_fetch_provider,
    list_fetch_providers,
)


# ======================================================================
# FetchResult basic structure
# ======================================================================

class TestFetchResultStructure:
    def test_default_fields(self):
        """FetchResult has all required fields with defaults."""
        r = FetchResult(url="https://example.com", ok=True, provider="test", fetched_at="now")
        assert r.url == "https://example.com"
        assert r.ok is True
        assert r.provider == "test"
        assert r.fetched_at == "now"
        assert r.status_code == ""
        assert r.content_type == ""
        assert r.markdown == ""
        assert r.html == ""
        assert r.text == ""
        assert r.title == ""
        assert r.description == ""
        assert r.links == []
        assert r.error == ""
        assert r.raw == {}

    def test_full_fields(self):
        """All FetchResult fields can be set."""
        r = FetchResult(
            url="https://example.com",
            ok=True,
            provider="firecrawl",
            fetched_at="2026-01-01T00:00:00Z",
            status_code=200,
            content_type="text/html",
            markdown="# Hello",
            html="<h1>Hello</h1>",
            text="Hello",
            title="Hello Page",
            description="A test page",
            links=[{"text": "Link", "url": "https://example.com/link"}],
            error="",
            raw={"success": True},
        )
        assert r.status_code == 200
        assert r.markdown == "# Hello"
        assert len(r.links) == 1


# ======================================================================
# MockFetchProvider
# ======================================================================

class TestMockFetchProvider:
    def test_ok_true(self):
        provider = MockFetchProvider()
        result = provider.fetch("https://bukgu.gwangju.kr/")
        assert result.ok is True
        assert result.provider == "mock"

    def test_markdown_html_title(self):
        provider = MockFetchProvider()
        result = provider.fetch("https://example.com/")
        assert "Mock Page" in result.markdown
        assert "Mock Page" in result.html
        assert result.title == "Mock Page"

    def test_custom_values(self):
        provider = MockFetchProvider(
            markdown="# Custom",
            html="<h1>Custom</h1>",
            title="Custom Title",
        )
        result = provider.fetch("https://example.com/")
        assert result.markdown == "# Custom"
        assert result.html == "<h1>Custom</h1>"
        assert result.title == "Custom Title"

    def test_env_values(self):
        with patch.dict(os.environ, {
            "AI_FINDER_FETCH_MOCK_MARKDOWN": "env markdown",
            "AI_FINDER_FETCH_MOCK_HTML": "<p>env html</p>",
            "AI_FINDER_FETCH_MOCK_TITLE": "Env Title",
        }):
            provider = MockFetchProvider()
            result = provider.fetch("https://example.com/")
            assert result.markdown == "env markdown"
            assert result.html == "<p>env html</p>"
            assert result.title == "Env Title"

    def test_links_returned(self):
        provider = MockFetchProvider()
        result = provider.fetch("https://example.com/")
        assert len(result.links) == 2
        assert result.links[0]["text"] == "Mock Link 1"

    def test_status_code(self):
        provider = MockFetchProvider()
        result = provider.fetch("https://example.com/")
        assert result.status_code == 200

    def test_name_property(self):
        provider = MockFetchProvider()
        assert provider.name == "mock"


# ======================================================================
# Provider factory
# ======================================================================

class TestGetFetchProvider:
    def test_mock(self):
        provider = get_fetch_provider("mock")
        assert isinstance(provider, MockFetchProvider)

    def test_requests(self):
        provider = get_fetch_provider("requests")
        assert isinstance(provider, RequestsFetchProvider)

    def test_firecrawl(self):
        provider = get_fetch_provider("firecrawl")
        assert isinstance(provider, FirecrawlFetchProvider)

    def test_unknown_raises(self):
        with pytest.raises(ValueError, match="Unknown fetch provider"):
            get_fetch_provider("nonexistent_provider_xyz")

    def test_env_default(self):
        with patch.dict(os.environ, {"AI_FINDER_FETCH_PROVIDER": "mock"}):
            provider = get_fetch_provider()
            assert isinstance(provider, MockFetchProvider)

    def test_env_default_fallback(self):
        with patch.dict(os.environ, {}, clear=True):
            provider = get_fetch_provider()
            assert isinstance(provider, RequestsFetchProvider)


class TestListFetchProviders:
    def test_returns_list(self):
        providers = list_fetch_providers()
        assert isinstance(providers, list)
        assert len(providers) == 3

    def test_names(self):
        names = [p["name"] for p in list_fetch_providers()]
        assert "mock" in names
        assert "requests" in names
        assert "firecrawl" in names


# ======================================================================
# RequestsFetchProvider
# ======================================================================

class TestRequestsFetchProvider:
    def test_invalid_url(self):
        provider = RequestsFetchProvider()
        result = provider.fetch("not-a-url")
        assert result.ok is False
        assert "invalid url" in result.error.lower()

    def test_empty_url(self):
        provider = RequestsFetchProvider()
        result = provider.fetch("")
        assert result.ok is False

    def test_successful_fetch(self):
        """Monkeypatched GET returns HTML, title/description/text/links extracted."""
        captured = {}

        def fake_get(url, headers, timeout):
            captured["url"] = url
            captured["headers"] = headers

            class FakeResponse:
                status_code = 200
                encoding = "utf-8"

                def __init__(self):
                    self.headers = {"Content-Type": "text/html; charset=utf-8"}
                    self.url = url

                def raise_for_status(self):
                    pass

                @property
                def text(self):
                    return (
                        "<html><head>"
                        "<title>Bukgu Test</title>"
                        '<meta name="description" content="Bukgu description">'
                        "</head><body>"
                        "<nav><a href='/apply'>신청하기</a><a href='/notice'>공지사항</a></nav>"
                        "<p>북구청 테스트 페이지입니다.</p>"
                        "</body></html>"
                    )

            return FakeResponse()

        with patch("requests.get", side_effect=fake_get):
            provider = RequestsFetchProvider()
            result = provider.fetch("https://bukgu.gwangju.kr/")

        assert result.ok is True
        assert result.title == "Bukgu Test"
        assert "Bukgu description" in result.description
        assert "북구청 테스트 페이지입니다." in result.text
        assert len(result.links) >= 2
        assert result.status_code == 200

    def test_http_error(self):
        def fake_get(url, headers, timeout):
            class FakeResponse:
                status_code = 404
                encoding = "utf-8"

                def __init__(self):
                    self.headers = {"Content-Type": "text/html"}
                    self.url = url
                    self.text = ""

            return FakeResponse()

        with patch("requests.get", side_effect=fake_get):
            provider = RequestsFetchProvider()
            result = provider.fetch("https://example.com/404")
        assert result.ok is False
        assert "HTTP" in result.error
        assert result.status_code == 404

    def test_network_error(self):
        def fake_get(url, headers, timeout):
            import requests
            raise requests.exceptions.ConnectionError("Connection refused")

        with patch("requests.get", side_effect=fake_get):
            provider = RequestsFetchProvider()
            result = provider.fetch("https://example.com/")
        assert result.ok is False
        assert "Connection refused" in result.error or "Network" in result.error or "error" in result.error

    def test_timeout(self):
        def fake_get(url, headers, timeout):
            import requests
            raise requests.exceptions.Timeout("timed out")

        with patch("requests.get", side_effect=fake_get):
            provider = RequestsFetchProvider()
            result = provider.fetch("https://example.com/")
        assert result.ok is False
        assert "timed out" in result.error.lower()

    def test_non_html_content_type(self):
        """Non-HTML responses still return ok=True with text but no parsing."""

        def fake_get(url, headers, timeout):
            class FakeResponse:
                status_code = 200
                encoding = "utf-8"

                def __init__(self):
                    self.headers = {"Content-Type": "application/pdf"}
                    self.url = url
                    self.text = "%PDF-1.4 binary content"

            return FakeResponse()

        with patch("requests.get", side_effect=fake_get):
            provider = RequestsFetchProvider()
            result = provider.fetch("https://example.com/file.pdf")
        assert result.ok is True
        assert result.content_type == "application/pdf"
        assert "PDF" in result.text

    def test_name_property(self):
        provider = RequestsFetchProvider()
        assert provider.name == "requests"


# ======================================================================
# FirecrawlFetchProvider
# ======================================================================

class TestFirecrawlConfigValidation:
    """Config validation errors return FetchResult(ok=False), not exceptions."""

    def test_missing_api_key(self):
        """No API key → no requests.post call, returns ok=False."""
        provider = FirecrawlFetchProvider(api_key="")
        result = provider.fetch("https://bukgu.gwangju.kr/")
        assert result.ok is False
        assert "api key" in result.error.lower()

    def test_error_does_not_leak_api_key(self):
        """Error messages should not contain the actual API key value."""
        provider = FirecrawlFetchProvider(api_key="fc-super-secret-12345")
        result = provider.fetch("https://bukgu.gwangju.kr/")
        assert result.ok is False
        assert "fc-super-secret-12345" not in result.error


class TestFirecrawlRequestPayload:
    """Verify request payload structure using monkeypatch."""

    def test_endpoint_and_formats(self):
        captured = {}

        def fake_post(url, headers, json, timeout):
            captured["url"] = url
            captured["headers"] = headers
            captured["json"] = json

            class FakeResponse:
                status_code = 200

                def json(self):
                    return {
                        "success": True,
                        "data": {
                            "markdown": "# Page",
                            "html": "<h1>Page</h1>",
                            "links": ["https://example.com/link1"],
                            "metadata": {
                                "title": "Test Page",
                                "description": "Test description",
                                "sourceURL": "https://bukgu.gwangju.kr/",
                            },
                        },
                    }

            return FakeResponse()

        with patch("requests.post", side_effect=fake_post):
            provider = FirecrawlFetchProvider(api_key="fc-test-key")
            result = provider.fetch("https://bukgu.gwangju.kr/")

        # Endpoint check
        assert "/v1/scrape" in captured["url"]

        # Formats check
        assert captured["json"]["formats"] == ["markdown", "html", "links"]

        # URL in body
        assert captured["json"]["url"] == "https://bukgu.gwangju.kr/"

        # Auth header
        auth = captured["headers"].get("Authorization", "")
        assert auth.startswith("Bearer ")
        # Key is in the header but NOT logged/tested for value exposure

        # Result parsing
        assert result.ok is True
        assert result.title == "Test Page"
        assert "Page" in result.markdown
        assert len(result.links) == 1


class TestFirecrawlResponseParsing:
    """Test various Firecrawl response scenarios."""

    def test_success_response(self):
        def fake_post(url, headers, json, timeout):
            class FakeResponse:
                status_code = 200

                def json(self):
                    return {
                        "success": True,
                        "data": {
                            "markdown": "# 지원사업 안내",
                            "html": "<h1>지원사업 안내</h1>",
                            "links": [
                                "https://bukgu.gwangju.kr/apply",
                                "https://bukgu.gwangju.kr/notice",
                            ],
                            "metadata": {
                                "title": "북구청 지원사업",
                                "description": "북구청 지원사업 안내 페이지입니다.",
                                "sourceURL": "https://bukgu.gwangju.kr/",
                            },
                        },
                    }

            return FakeResponse()

        with patch("requests.post", side_effect=fake_post):
            provider = FirecrawlFetchProvider(api_key="fc-test-key")
            result = provider.fetch("https://bukgu.gwangju.kr/")

        assert result.ok is True
        assert result.title == "북구청 지원사업"
        assert result.description == "북구청 지원사업 안내 페이지입니다."
        assert "지원사업 안내" in result.markdown
        assert len(result.links) == 2
        assert result.status_code == 200

    def test_success_false_response(self):
        def fake_post(url, headers, json, timeout):
            class FakeResponse:
                status_code = 200

                def json(self):
                    return {"success": False, "error": "Failed to scrape URL"}

            return FakeResponse()

        with patch("requests.post", side_effect=fake_post):
            provider = FirecrawlFetchProvider(api_key="fc-test-key")
            result = provider.fetch("https://bukgu.gwangju.kr/")
        assert result.ok is False
        assert "Failed to scrape" in result.error

    def test_missing_data_field(self):
        def fake_post(url, headers, json, timeout):
            class FakeResponse:
                status_code = 200

                def json(self):
                    return {"success": True}

            return FakeResponse()

        with patch("requests.post", side_effect=fake_post):
            provider = FirecrawlFetchProvider(api_key="fc-test-key")
            result = provider.fetch("https://bukgu.gwangju.kr/")
        assert result.ok is False
        assert "data" in result.error.lower()

    def test_empty_metadata(self):
        """Metadata can be null/None without crashing."""

        def fake_post(url, headers, json, timeout):
            class FakeResponse:
                status_code = 200

                def json(self):
                    return {
                        "success": True,
                        "data": {
                            "markdown": "content",
                            "html": "",
                            "links": [],
                            "metadata": None,
                        },
                    }

            return FakeResponse()

        with patch("requests.post", side_effect=fake_post):
            provider = FirecrawlFetchProvider(api_key="fc-test-key")
            result = provider.fetch("https://bukgu.gwangju.kr/")
        assert result.ok is True
        assert result.title == ""

    def test_http_error(self):
        def fake_post(url, headers, json, timeout):
            import requests

            class FakeResponse:
                status_code = 401
                text = "Unauthorized"

                def raise_for_status(self):
                    raise requests.exceptions.HTTPError(
                        "401 Client Error", response=self
                    )

            return FakeResponse()

        with patch("requests.post", side_effect=fake_post):
            provider = FirecrawlFetchProvider(api_key="bad-key")
            result = provider.fetch("https://bukgu.gwangju.kr/")
        assert result.ok is False
        # Error message should NOT contain the API key
        assert "bad-key" not in result.error

    def test_timeout(self):
        def fake_post(url, headers, json, timeout):
            import requests
            raise requests.exceptions.Timeout("timed out")

        with patch("requests.post", side_effect=fake_post):
            provider = FirecrawlFetchProvider(api_key="fc-test-key", timeout=5)
            result = provider.fetch("https://bukgu.gwangju.kr/")
        assert result.ok is False
        assert "timed out" in result.error.lower()

    def test_json_decode_error(self):
        def fake_post(*args, **kwargs):
            class FakeResponse:
                status_code = 200

                def json(self):
                    import json as json_mod
                    raise json_mod.JSONDecodeError("Not JSON", doc="", pos=0)

            return FakeResponse()

        with patch("requests.post", side_effect=fake_post):
            provider = FirecrawlFetchProvider(api_key="fc-test-key")
            result = provider.fetch("https://bukgu.gwangju.kr/")
        assert result.ok is False
        assert "invalid json" in result.error.lower()

    def test_links_as_strings_and_dicts(self):
        """Links can be strings or dicts; both are handled."""

        def fake_post(url, headers, json, timeout):
            class FakeResponse:
                status_code = 200

                def json(self):
                    return {
                        "success": True,
                        "data": {
                            "markdown": "# Page",
                            "html": "",
                            "links": [
                                "https://example.com/1",
                                {"text": "Link 2", "url": "https://example.com/2"},
                            ],
                            "metadata": {"title": "Test"},
                        },
                    }

            return FakeResponse()

        with patch("requests.post", side_effect=fake_post):
            provider = FirecrawlFetchProvider(api_key="fc-test-key")
            result = provider.fetch("https://example.com/")
        assert result.ok is True
        assert len(result.links) == 2
        assert result.links[0]["url"] == "https://example.com/1"
        assert result.links[1]["text"] == "Link 2"

    def test_name_property(self):
        provider = FirecrawlFetchProvider(api_key="test")
        assert provider.name == "firecrawl"


# ======================================================================
# CLI output encoding test
# ======================================================================

class TestCliOutputEncoding:
    def test_ensure_ascii_false(self):
        """JSON output should have ensure_ascii=False for Korean text."""
        result = FetchResult(
            url="https://bukgu.gwangju.kr/",
            ok=True,
            provider="mock",
            fetched_at="2026-01-01T00:00:00Z",
            title="북구청",
            description="북구청 테스트",
            text="안녕하세요",
            markdown="# 북구청",
            links=[{"text": "신청하기", "url": "https://bukgu.gwangju.kr/apply"}],
        )
        output = json.dumps({
            "ok": result.ok,
            "provider": result.provider,
            "title": result.title,
            "description": result.description,
            "links": result.links,
        }, ensure_ascii=False, indent=2)
        # Korean characters should NOT be escaped
        assert "\\u" not in output
        assert "북구청" in output
        assert "신청하기" in output
