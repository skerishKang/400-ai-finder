import json
import logging
from unittest.mock import patch

import pytest
from src.crawler.homepage_mapper import (
    get_base_url,
    parse_robots_txt,
    classify_url,
    HomepageMapper
)

def test_base_url_calculation():
    assert get_base_url("https://example.com/sub/page.html") == "https://example.com"
    assert get_base_url("http://sub.example.com:8080/path?query=1") == "http://sub.example.com:8080"
    assert get_base_url("invalid-url") == ""

def test_robots_txt_sitemap_parsing():
    content = """
    User-agent: *
    Disallow: /admin/
    Sitemap: https://example.com/sitemap.xml
    sitemap: https://example.com/sitemap_index.xml
    """
    sitemaps = parse_robots_txt(content)
    assert len(sitemaps) == 2
    assert "https://example.com/sitemap.xml" in sitemaps
    assert "https://example.com/sitemap_index.xml" in sitemaps

def test_category_classification_rules():
    # Priority order: document > apply > notice > board > contact > location > menu > unknown
    
    # 1. Document
    assert classify_url("https://example.com/downloads/report.pdf", "My Report") == "document"
    assert classify_url("https://example.com/file-show", "양식 다운로드") == "document"
    
    # 2. Apply
    assert classify_url("https://example.com/register", "Join Us") == "apply"
    assert classify_url("https://example.com/program", "신청서 작성") == "apply"
    
    # 3. Notice
    assert classify_url("https://example.com/announcements", "News") == "notice"
    assert classify_url("https://example.com/notice-list", "새로운 알림") == "notice"
    assert classify_url("https://example.com/board", "고시공고") == "notice"
    assert classify_url("https://example.com/notice/board", "입법예고") == "notice"
    assert classify_url("https://example.com/recruit", "채용공고") == "notice"
    assert classify_url("https://example.com/board/list", "공고") == "notice"
    
    # 4. Board
    assert classify_url("https://example.com/bbs/free-board", "Talk") == "board"
    assert classify_url("https://example.com/article/1", "게시물") == "board"
    
    # 5. Contact
    assert classify_url("https://example.com/support", "Get Help") == "contact"
    assert classify_url("https://example.com/contact-us", "고객 상담") == "contact"
    assert classify_url("https://example.com/org", "조직도") == "contact"
    assert classify_url("https://example.com/staff-search", "직원검색") == "contact"
    assert classify_url("https://example.com/dept-info", "부서안내") == "contact"
    assert classify_url("https://example.com/phone", "전화번호") == "contact"
    assert classify_url("https://example.com/manager", "담당자") == "contact"
    assert classify_url("https://example.com/job", "담당업무") == "contact"
    
    # 6. Location
    assert classify_url("https://example.com/office-guide", "청사안내") == "location"
    assert classify_url("https://example.com/office-location", "청사") == "location"
    assert classify_url("https://example.com/map", "오시는길") == "location"
    assert classify_url("https://example.com/direction", "오시는 길") == "location"
    assert classify_url("https://example.com/way-to-come", "찾아오시는길") == "location"
    assert classify_url("https://example.com/parking", "주차") == "location"
    assert classify_url("https://example.com/parking-lot", "주차안내") == "location"
    assert classify_url("https://example.com/address", "위치") == "location"
    assert classify_url("https://example.com/parking-info", "parking") == "location"

    # 7. Menu (is_navigation=True)
    assert classify_url("https://example.com/about-us", "회사소개", is_navigation=True) == "menu"
    
    # 8. Unknown
    assert classify_url("https://example.com/about-us", "회사소개", is_navigation=False) == "unknown"

def test_homepage_menu_links_extraction_and_normalization():
    mapper = HomepageMapper()
    html = """
    <html>
      <body>
        <nav>
          <a href="/about">회사 소개</a>
          <a href="https://example.com/notices">공지사항</a>
          <a href="../downloads/manual.pdf">PDF 매뉴얼</a>
          <!-- duplicate -->
          <a href="/about">회사 소개 중복</a>
        </nav>
        <div id="header-menu">
          <a href="/support">고객센터</a>
        </div>
        <div>
          <!-- Outside nav/header/menu areas, should be ignored -->
          <a href="/hidden-page">숨겨진 페이지</a>
        </div>
      </body>
    </html>
    """
    
    nav_links, att_links = mapper.extract_menu_links(html, "https://example.com")
    
    # Check duplicate filter and relative -> absolute path conversion
    assert len(nav_links) == 3
    urls = [link["url"] for link in nav_links]
    assert "https://example.com/about" in urls
    assert "https://example.com/notices" in urls
    assert "https://example.com/support" in urls
    assert "https://example.com/hidden-page" not in urls
    
    # Categories test
    categories = {link["url"]: link["category"] for link in nav_links}
    assert categories["https://example.com/about"] == "menu"
    assert categories["https://example.com/notices"] == "notice"
    assert categories["https://example.com/support"] == "contact"

    # Attachment checks
    assert len(att_links) == 1
    assert att_links[0]["url"] == "https://example.com/downloads/manual.pdf"
    assert att_links[0]["type"] == "pdf"


# ======================================================================
# FetchProvider injection tests
# ======================================================================

def test_mapper_fetch_provider_mock():
    """HomepageMapper with fetch_provider='mock' creates URLCrawler with mock provider."""
    from src.fetch import MockFetchProvider
    mapper = HomepageMapper(fetch_provider="mock")
    assert mapper.fetch_provider is not None
    assert mapper.fetch_provider.name == "mock"
    # URLCrawler inside mapper should also have the mock provider
    assert mapper.crawler.fetch_provider is not None
    assert mapper.crawler.fetch_provider.name == "mock"


def test_mapper_fetch_provider_instance():
    """HomepageMapper accepts a FetchProvider instance directly."""
    from src.fetch import MockFetchProvider
    provider = MockFetchProvider()
    mapper = HomepageMapper(fetch_provider=provider)
    assert mapper.fetch_provider is provider


def test_mapper_fetch_provider_none():
    """HomepageMapper with fetch_provider=None keeps original behavior."""
    mapper = HomepageMapper()
    assert mapper.fetch_provider is None
    # URLCrawler should also have no fetch_provider
    assert mapper.crawler.fetch_provider is None


def test_mapper_fetch_content_with_mock_provider():
    """fetch_content() with mock provider returns HTML and no error."""
    mapper = HomepageMapper(fetch_provider="mock")
    content, error, status, final_url = mapper.fetch_content("https://bukgu.gwangju.kr/")
    assert error is None
    assert status == 200
    assert "Mock Page" in content or "mock" in content.lower()


def test_mapper_fetch_content_with_mock_provider_error():
    """fetch_content() propagates provider errors correctly."""
    from src.fetch import MockFetchProvider
    from src.fetch.base import FetchResult
    from datetime import datetime, timezone

    class FailingProvider(MockFetchProvider):
        def fetch(self, url, **kwargs):
            return FetchResult(
                url=url, ok=False, provider="mock_fail",
                fetched_at=datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                error="Fetch error in mapper",
            )

    mapper = HomepageMapper(fetch_provider=FailingProvider())
    content, error, status, final_url = mapper.fetch_content("https://example.com/")
    assert content is None
    assert error is not None
    assert "Fetch error" in error


def test_mapper_fetch_config_propagates_to_inner_url_crawler():
    from src.fetch import FetchConfig

    config = FetchConfig(timeout=9.5, max_retries=2, retry_backoff=0.0, retry_on_status=(503,))
    mapper = HomepageMapper(fetch_config=config)

    assert mapper.fetch_config is config
    assert mapper.crawler.fetch_config is config


def test_mapper_fetch_content_without_fetch_config_preserves_outer_retry_and_timeout_kwarg():
    from src.fetch import FetchResult, RequestsFetchProvider
    from datetime import datetime, timezone

    class FailingRequestsProvider(RequestsFetchProvider):
        def __init__(self):
            super().__init__(timeout=99)
            self.calls = []

        def fetch(self, url, **kwargs):
            self.calls.append((url, dict(kwargs)))
            return FetchResult(
                url=url,
                ok=False,
                provider="requests",
                fetched_at=datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                error="provider failure",
            )

    provider = FailingRequestsProvider()
    mapper = HomepageMapper(fetch_provider=provider, timeout=7)

    content, error, status, final_url = mapper.fetch_content("https://example.com", retries=2)

    assert content is None
    assert error == "provider failure"
    assert status is None
    assert final_url == "https://example.com"
    assert provider.calls == [
        ("https://example.com", {"timeout": 7}),
        ("https://example.com", {"timeout": 7}),
        ("https://example.com", {"timeout": 7}),
    ]


def test_mapper_fetch_content_threads_fetch_config_to_requests_provider_once_without_timeout_kwarg():
    from src.fetch import FetchConfig, FetchResult, RequestsFetchProvider
    from datetime import datetime, timezone

    class SpyRequestsProvider(RequestsFetchProvider):
        def __init__(self):
            super().__init__(timeout=99)
            self.calls = []

        def fetch(self, url, **kwargs):
            self.calls.append((url, dict(kwargs)))
            return FetchResult(
                url="https://example.com/final",
                ok=True,
                provider="requests",
                fetched_at=datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                status_code=200,
                content_type="text/html",
                html="<html><body>Configured success</body></html>",
            )

    provider = SpyRequestsProvider()
    config = FetchConfig(timeout=12.5, max_retries=1, retry_backoff=0.0, retry_on_status=(503,))
    mapper = HomepageMapper(fetch_provider=provider, timeout=7, fetch_config=config)

    content, error, status, final_url = mapper.fetch_content("https://example.com", retries=5)

    assert content == "<html><body>Configured success</body></html>"
    assert error is None
    assert status == 200
    assert final_url == "https://example.com/final"
    assert len(provider.calls) == 1
    assert provider.calls[0][0] == "https://example.com"
    assert provider.calls[0][1]["config"] is config
    assert "timeout" not in provider.calls[0][1]


def test_mapper_fetch_content_with_fetch_config_preserves_failure_tuple_shape():
    from src.fetch import FetchConfig, FetchResult, RequestsFetchProvider
    from datetime import datetime, timezone

    class FailingRequestsProvider(RequestsFetchProvider):
        def __init__(self):
            super().__init__(timeout=99)
            self.calls = []

        def fetch(self, url, **kwargs):
            self.calls.append((url, dict(kwargs)))
            return FetchResult(
                url="https://example.com/ignored",
                ok=False,
                provider="requests",
                fetched_at=datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                error="configured failure",
            )

    provider = FailingRequestsProvider()
    config = FetchConfig(timeout=8.0, max_retries=3, retry_backoff=0.0, retry_on_status=(503,))
    mapper = HomepageMapper(fetch_provider=provider, fetch_config=config)

    content, error, status, final_url = mapper.fetch_content("https://example.com", retries=5)

    assert content is None
    assert error == "configured failure"
    assert status is None
    assert final_url == "https://example.com"
    assert len(provider.calls) == 1
    assert provider.calls[0][1] == {"config": config}


def test_mapper_fetch_content_with_fetch_config_returns_exception_string_without_retry():
    from src.fetch import FetchConfig, RequestsFetchProvider

    class RaisingRequestsProvider(RequestsFetchProvider):
        def __init__(self):
            super().__init__(timeout=99)
            self.calls = []

        def fetch(self, url, **kwargs):
            self.calls.append((url, dict(kwargs)))
            raise RuntimeError("provider boom")

    provider = RaisingRequestsProvider()
    config = FetchConfig(timeout=8.0, max_retries=1, retry_backoff=0.0, retry_on_status=(503,))
    mapper = HomepageMapper(fetch_provider=provider, fetch_config=config)

    content, error, status, final_url = mapper.fetch_content("https://example.com", retries=5)

    assert content is None
    assert error == "provider boom"
    assert status is None
    assert final_url == "https://example.com"
    assert len(provider.calls) == 1


def test_mapper_fetch_content_with_fetch_config_does_not_pass_config_to_mock_or_custom_provider():
    from src.fetch import FetchConfig, FetchResult, MockFetchProvider
    from src.fetch.base import FetchProvider
    from datetime import datetime, timezone

    class SpyMockProvider(MockFetchProvider):
        def __init__(self):
            super().__init__()
            self.calls = []

        def fetch(self, url, **kwargs):
            self.calls.append((url, dict(kwargs)))
            return super().fetch(url, **kwargs)

    class CustomProvider(FetchProvider):
        def __init__(self):
            self.calls = []

        @property
        def name(self) -> str:
            return "custom"

        def fetch(self, url, **kwargs):
            self.calls.append((url, dict(kwargs)))
            return FetchResult(
                url=url,
                ok=True,
                provider=self.name,
                fetched_at=datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                status_code=200,
                content_type="text/html",
                html="<html><body>custom</body></html>",
            )

    config = FetchConfig(timeout=10.0, max_retries=2, retry_backoff=0.0, retry_on_status=(503,))

    mock_provider = SpyMockProvider()
    mock_mapper = HomepageMapper(fetch_provider=mock_provider, timeout=5, fetch_config=config)
    mock_result = mock_mapper.fetch_content("https://example.com", retries=1)

    custom_provider = CustomProvider()
    custom_mapper = HomepageMapper(fetch_provider=custom_provider, timeout=6, fetch_config=config)
    custom_result = custom_mapper.fetch_content("https://example.com", retries=1)

    assert mock_result[1] is None
    assert custom_result[1] is None
    assert mock_provider.calls == [("https://example.com", {"timeout": 5})]
    assert custom_provider.calls == [("https://example.com", {"timeout": 6})]


def _extract_pipeline_records(caplog: pytest.LogCaptureFixture) -> list[dict[str, object]]:
    records = []
    for line in caplog.messages:
        if line.startswith("pipeline_event="):
            records.append(json.loads(line.split("=", 1)[1]))
    return records


def test_homepage_mapper_logs_terminal_success_event(caplog):
    mapper = HomepageMapper()

    def fake_fetch_content(url, retries=1):
        if url.endswith("/robots.txt"):
            return "", None, 200, url
        return (
            "<html><head><title>Home</title></head>"
            "<body><nav><a href=\"/apply\">신청</a></nav></body></html>",
            None,
            200,
            url,
        )

    with patch.object(mapper, "fetch_content", side_effect=fake_fetch_content), \
         patch.object(mapper.sitemap_parser, "parse", return_value={"error": "", "sitemaps": [], "urls": []}), \
         caplog.at_level(logging.INFO, logger="src.crawler.homepage_mapper"):
        result = mapper.build_map("https://example.com", correlation_id="corr-123")

    records = _extract_pipeline_records(caplog)
    assert result["homepage"]["title"] == "Home"
    assert [record["event"] for record in records] == ["pipeline_stage_end"]
    assert records[0]["stage"] == "homepage_mapper"
    assert records[0]["ok"] is True
    assert records[0]["correlation_id"] == "corr-123"
    assert isinstance(records[0]["duration_ms"], int)


def test_homepage_mapper_preserves_empty_correlation_id(caplog):
    mapper = HomepageMapper()

    def fake_fetch_content(url, retries=1):
        if url.endswith("/robots.txt"):
            return "", None, 200, url
        return "<html><body></body></html>", None, 200, url

    with patch.object(mapper, "fetch_content", side_effect=fake_fetch_content), \
         patch.object(mapper.sitemap_parser, "parse", return_value={"error": "", "sitemaps": [], "urls": []}), \
         caplog.at_level(logging.INFO, logger="src.crawler.homepage_mapper"):
        mapper.build_map("https://example.com", correlation_id="")

    records = _extract_pipeline_records(caplog)
    assert records
    assert {record["correlation_id"] for record in records} == {""}


def test_homepage_mapper_without_correlation_id_logs_nothing(caplog):
    mapper = HomepageMapper()

    def fake_fetch_content(url, retries=1):
        if url.endswith("/robots.txt"):
            return "", None, 200, url
        return "<html><body></body></html>", None, 200, url

    with patch.object(mapper, "fetch_content", side_effect=fake_fetch_content), \
         patch.object(mapper.sitemap_parser, "parse", return_value={"error": "", "sitemaps": [], "urls": []}), \
         caplog.at_level(logging.INFO, logger="src.crawler.homepage_mapper"):
        mapper.build_map("https://example.com")

    assert "pipeline_event=" not in "\n".join(caplog.messages)


def test_homepage_mapper_logs_static_failure_and_reraises(caplog):
    mapper = HomepageMapper()

    with patch.object(
        mapper,
        "fetch_content",
        side_effect=RuntimeError("secret token failed for https://example.com"),
    ):
        with caplog.at_level(logging.INFO, logger="src.crawler.homepage_mapper"):
            with pytest.raises(RuntimeError, match="secret token failed"):
                mapper.build_map("https://example.com", correlation_id="corr-err")

    records = _extract_pipeline_records(caplog)
    assert [record["event"] for record in records] == ["pipeline_stage_fail"]
    assert records[0]["stage"] == "homepage_mapper"
    assert records[0]["ok"] is False
    assert records[0]["failure_code"] == "homepage_mapper_exception"
    joined_logs = "\n".join(caplog.messages)
    assert "https://example.com" not in joined_logs
    assert "secret" not in joined_logs
    assert "token" not in joined_logs
    assert "RuntimeError" not in joined_logs


# ======================================================================
# Stage 1: Lock homepage mapper direct-fallback contracts (#834-stage1)
# ======================================================================

def test_homepage_mapper_direct_fallback_success(monkeypatch):
    class FakeResponse:
        status_code = 200
        url = "https://example.com/final"
        headers = {"Content-Type": "text/html; charset=utf-8"}
        text = "Hello World"
        encoding = "ISO-8859-1"
        apparent_encoding = "utf-8"

    captured = {}
    def mock_get(url, **kwargs):
        captured["url"] = url
        captured["headers"] = kwargs.get("headers")
        captured["timeout"] = kwargs.get("timeout")
        return FakeResponse()

    import requests
    monkeypatch.setattr(requests, "get", mock_get)

    mapper = HomepageMapper(fetch_provider=None)
    content, err, status, final_url = mapper.fetch_content("https://example.com/start")

    # Routed through legacy requests transport: caller headers verbatim and the
    # scalar timeout (not a split tuple) forwarded to requests.get.
    assert captured["url"] == "https://example.com/start"
    assert captured["headers"] == mapper.crawler.headers
    assert captured["timeout"] == mapper.crawler.timeout
    assert content == "Hello World"
    assert err is None
    assert status == 200
    assert final_url == "https://example.com/final"


def test_homepage_mapper_direct_fallback_http_error_retry(monkeypatch):
    class FakeResponse:
        status_code = 503
        url = "https://example.com/start"
        headers = {"Content-Type": "text/html; charset=utf-8"}
        text = "<html><body>unavailable</body></html>"
        encoding = "utf-8"
        apparent_encoding = "utf-8"

    call_count = 0
    def mock_get(url, **kwargs):
        nonlocal call_count
        call_count += 1
        return FakeResponse()

    import requests
    monkeypatch.setattr(requests, "get", mock_get)

    mapper = HomepageMapper(fetch_provider=None)
    content, err, status, final_url = mapper.fetch_content("https://example.com/start", retries=1)

    assert call_count == 2
    assert content is None
    assert err == "HTTP Error: 503"
    assert status is None
    assert final_url == "https://example.com/start"


def test_homepage_mapper_direct_fallback_timeout_retry(monkeypatch):
    call_count = 0
    import requests
    def mock_get(url, **kwargs):
        nonlocal call_count
        call_count += 1
        raise requests.exceptions.Timeout("Timed out")

    monkeypatch.setattr(requests, "get", mock_get)

    mapper = HomepageMapper(fetch_provider=None)
    content, err, status, final_url = mapper.fetch_content("https://example.com/start", retries=1)

    assert call_count == 2
    assert content is None
    assert err == f"Timeout after {mapper.crawler.timeout}s"
    assert status is None
    assert final_url == "https://example.com/start"


def test_homepage_mapper_direct_fallback_generic_exception(monkeypatch):
    import requests
    def mock_get(url, **kwargs):
        raise RuntimeError("fallback boom")

    monkeypatch.setattr(requests, "get", mock_get)

    mapper = HomepageMapper(fetch_provider=None)
    content, err, status, final_url = mapper.fetch_content("https://example.com/start", retries=0)

    assert content is None
    assert err == "fallback boom"
    assert status is None
    assert final_url == "https://example.com/start"


def test_homepage_mapper_direct_fallback_timeout_then_success(monkeypatch):
    """legacy fallback / fetch_provider=None / no network / compatibility baseline."""

    from src.crawler.homepage_mapper import HomepageMapper
    import requests

    class FakeResponse:
        status_code = 200
        url = "https://example.com/final"
        headers = {"Content-Type": "text/html; charset=utf-8"}
        text = "Recovered content"
        encoding = "utf-8"
        apparent_encoding = "utf-8"

    calls = []
    def mock_get(url, **kwargs):
        calls.append((url, kwargs))
        if len(calls) == 1:
            raise requests.exceptions.Timeout("timed out")
        return FakeResponse()

    monkeypatch.setattr(requests, "get", mock_get)

    mapper = HomepageMapper(timeout=7, fetch_provider=None)
    content, err, status, final_url = mapper.fetch_content(
        "https://example.com/start",
        retries=1,
    )

    assert len(calls) == 2
    assert content == "Recovered content"
    assert err is None
    assert status == 200
    assert final_url == "https://example.com/final"


# ------------------------------------------------------------------
# #949: Lock that extract_menu_links follows classify_url behavior.
# Inside a nav area a .pdf is a document attachment; .doc/.zip are NOT
# extension-only documents in the classifier, so they stay on the nav/menu
# side (no document keyword anywhere in href/text). HomepageMapper keeps no
# separate extension list — it defers to classify_url.
# ------------------------------------------------------------------
def test_extract_menu_links_follows_classifier_taxonomy():
    """#949 / no network. pdf -> attachment; doc/zip -> nav/menu (not doc)."""
    mapper = HomepageMapper()
    html = """
    <html>
      <body>
        <nav>
          <a href="https://example.com/assets/sample.pdf">파일</a>
          <a href="https://example.com/assets/sample.doc">문서</a>
          <a href="https://example.com/assets/sample.zip">압축</a>
        </nav>
      </body>
    </html>
    """
    nav_links, att_links = mapper.extract_menu_links(html, "https://example.com")

    att_urls = {a["url"] for a in att_links}
    nav_urls = {n["url"] for n in nav_links}

    assert "https://example.com/assets/sample.pdf" in att_urls
    assert att_urls == {"https://example.com/assets/sample.pdf"}

    assert "https://example.com/assets/sample.doc" in nav_urls
    assert "https://example.com/assets/sample.zip" in nav_urls
    # doc/zip are classified as menu (navigation) by the shared classifier.
    categories = {n["url"]: n["category"] for n in nav_links}
    assert categories["https://example.com/assets/sample.doc"] == "menu"
    assert categories["https://example.com/assets/sample.zip"] == "menu"


# ======================================================================
# #1294: acquisition-scope containment (HomepageMapper)
# All tests offline/deterministic — fake fetch_content / fake sitemap
# parser, no network, no provider/API calls.
# ======================================================================

def _scope_policy(allowed):
    from src.site_profiles.site_profile import SiteAcquisitionPolicy, SiteProfile
    profile = SiteProfile({
        "site_id": "synthetic",
        "name": "Synthetic",
        "base_url": "https://%s/" % allowed[0],
        "allowed_domains": list(allowed),
    })
    return SiteAcquisitionPolicy(profile)


def _homepage_html():
    return (
        "<html><head><title>Home</title></head><body>"
        "<nav><a href=\"/apply\">신청</a>"
        "<a href=\"https://evil.example/page\">evil</a></nav>"
        "</body></html>"
    )


def test_mapper_requested_start_url_outside_scope_fails_closed():
    policy = _scope_policy(["bukgu.gwangju.kr"])
    mapper = HomepageMapper(acquisition_policy=policy)
    fetched = []

    def fake_fetch_content(url, retries=1):
        fetched.append(url)
        return "", None, 200, url

    with patch.object(mapper, "fetch_content", side_effect=fake_fetch_content), \
         patch.object(mapper.sitemap_parser, "parse",
                      return_value={"error": "", "sitemaps": [], "urls": []}):
        result = mapper.build_map("https://evil.example/")

    assert fetched == []
    assert result["errors"]
    assert "outside the acquisition scope" in result["errors"][0]


def test_mapper_homepage_requested_allowed_final_allowed_passes():
    policy = _scope_policy(["bukgu.gwangju.kr"])
    mapper = HomepageMapper(acquisition_policy=policy)

    def fake_fetch_content(url, retries=1):
        if url.endswith("/robots.txt"):
            return "", None, 200, url
        return _homepage_html(), None, 200, url

    with patch.object(mapper, "fetch_content", side_effect=fake_fetch_content), \
         patch.object(mapper.sitemap_parser, "parse",
                      return_value={"error": "", "sitemaps": [], "urls": []}):
        result = mapper.build_map("https://bukgu.gwangju.kr/")

    assert result["homepage"]["title"] == "Home"
    # evil nav link is dropped; /apply stays.
    nav_urls = [l["url"] for l in result["homepage"]["navigation_links"]]
    assert nav_urls == ["https://bukgu.gwangju.kr/apply"]


def test_mapper_homepage_final_external_fails_closed():
    policy = _scope_policy(["bukgu.gwangju.kr"])
    mapper = HomepageMapper(acquisition_policy=policy)

    def fake_fetch_content(url, retries=1):
        if url.endswith("/robots.txt"):
            return "", None, 200, url
        # requested allowed, but effective/final URL leaves the scope
        return _homepage_html(), None, 200, "https://evil.example/"

    with patch.object(mapper, "fetch_content", side_effect=fake_fetch_content), \
         patch.object(mapper.sitemap_parser, "parse",
                      return_value={"error": "", "sitemaps": [], "urls": []}):
        result = mapper.build_map("https://bukgu.gwangju.kr/")

    assert result["homepage"]["title"] == ""
    assert result["homepage"]["navigation_links"] == []
    assert any("outside the acquisition scope" in e for e in result["homepage"]["errors"])


def test_mapper_navigation_scope_filtering():
    policy = _scope_policy(["bukgu.gwangju.kr", "alias.gwangju.kr"])
    mapper = HomepageMapper(acquisition_policy=policy)
    html = (
        "<html><body><nav>"
        "<a href=\"https://bukgu.gwangju.kr/notice\">notice</a>"
        "<a href=\"https://alias.gwangju.kr/alias\">alias</a>"
        "<a href=\"https://evil.example/page\">evil</a>"
        "<a href=\"https://foo.bukgu.gwangju.kr/sub\">subdomain</a>"
        "<a href=\"https://www.bukgu.gwangju.kr/www\">www</a>"
        "</nav></body></html>"
    )
    nav_links, _ = mapper.extract_menu_links(
        html, "https://bukgu.gwangju.kr/", acquisition_policy=policy
    )
    urls = [l["url"] for l in nav_links]
    assert "https://bukgu.gwangju.kr/notice" in urls
    assert "https://alias.gwangju.kr/alias" in urls
    assert "https://evil.example/page" not in urls
    assert "https://foo.bukgu.gwangju.kr/sub" not in urls
    assert "https://www.bukgu.gwangju.kr/www" not in urls


def test_mapper_external_navigation_never_reaches_indexer():
    from src.indexer.document_indexer import DocumentIndexer

    policy = _scope_policy(["bukgu.gwangju.kr"])
    mapper = HomepageMapper(acquisition_policy=policy)

    def fake_fetch_content(url, retries=1):
        if url.endswith("/robots.txt"):
            return "", None, 200, url
        return _homepage_html(), None, 200, url

    with patch.object(mapper, "fetch_content", side_effect=fake_fetch_content), \
         patch.object(mapper.sitemap_parser, "parse",
                      return_value={"error": "", "sitemaps": [], "urls": []}):
        result = mapper.build_map("https://bukgu.gwangju.kr/")

    docs = DocumentIndexer().build_index(result)
    assert all("evil.example" not in (d.get("url") or "") for d in docs)
    assert any("https://bukgu.gwangju.kr/apply" == d.get("url") for d in docs)


def test_mapper_robots_sitemap_directive_external_not_followed():
    policy = _scope_policy(["bukgu.gwangju.kr"])
    mapper = HomepageMapper(acquisition_policy=policy)
    fetched = []

    def fake_fetch_content(url, retries=1):
        fetched.append(url)
        if url.endswith("/robots.txt"):
            return "Sitemap: https://evil.example/sitemap.xml", None, 200, url
        if url.endswith(".xml"):
            return "<urlset/>", None, 200, url
        return _homepage_html(), None, 200, url

    with patch.object(mapper, "fetch_content", side_effect=fake_fetch_content), \
         patch.object(mapper.sitemap_parser, "parse",
                      return_value={"error": "", "sitemaps": [], "urls": []}):
        mapper.build_map("https://bukgu.gwangju.kr/")

    assert "https://evil.example/sitemap.xml" not in fetched
    assert "https://bukgu.gwangju.kr/sitemap.xml" in fetched


def test_mapper_robots_final_external_rejected():
    policy = _scope_policy(["bukgu.gwangju.kr"])
    mapper = HomepageMapper(acquisition_policy=policy)

    def fake_fetch_content(url, retries=1):
        if url.endswith("/robots.txt"):
            # robots effective URL left the scope
            return "Sitemap: https://bukgu.gwangju.kr/sitemap.xml", None, 200, "https://evil.example/robots.txt"
        return "", None, 200, url

    with patch.object(mapper, "fetch_content", side_effect=fake_fetch_content), \
         patch.object(mapper.sitemap_parser, "parse",
                      return_value={"error": "", "sitemaps": [], "urls": []}):
        result = mapper.build_map("https://bukgu.gwangju.kr/")

    assert any("robots" in e and "outside the acquisition scope" in e
               for e in result["sitemap"]["errors"])


def test_mapper_sitemap_containment_nested_and_loc():
    policy = _scope_policy(["bukgu.gwangju.kr", "alias.gwangju.kr"])
    mapper = HomepageMapper(acquisition_policy=policy)
    fetched = []

    def fake_fetch_content(url, retries=1):
        fetched.append(url)
        if url.endswith("/robots.txt"):
            return "Sitemap: https://bukgu.gwangju.kr/sitemap.xml", None, 200, url
        if url.endswith("/sitemap_index.xml"):
            return "<sitemapindex/>", None, 200, url
        if url.endswith("/sitemap.xml"):
            return "<MAIN/>", None, 200, url
        if url.endswith("/nested.xml"):
            return "<NESTED/>", None, 200, url
        return "", None, 200, url

    def fake_parse(xml):
        if "sitemapindex" in xml:
            return {"error": "", "sitemaps": [], "urls": []}
        if "NESTED" in xml:
            return {"error": "", "sitemaps": [], "urls": [
                {"url": "https://bukgu.gwangju.kr/nested-page"},
            ]}
        return {"error": "", "sitemaps": [
            "https://bukgu.gwangju.kr/nested.xml",
            "https://evil.example/evil-nested.xml",
        ], "urls": [
            {"url": "https://bukgu.gwangju.kr/notice"},
            {"url": "https://evil.example/external-loc"},
            {"url": "https://alias.gwangju.kr/alias-page"},
        ]}

    with patch.object(mapper, "fetch_content", side_effect=fake_fetch_content), \
         patch.object(mapper.sitemap_parser, "parse", side_effect=fake_parse):
        result = mapper.build_map("https://bukgu.gwangju.kr/")

    # external nested sitemap never fetched
    assert "https://evil.example/evil-nested.xml" not in fetched
    # allowed nested sitemap fetched
    assert "https://bukgu.gwangju.kr/nested.xml" in fetched

    urls = [u["url"] for u in result["sitemap"]["urls"]]
    assert "https://bukgu.gwangju.kr/notice" in urls
    assert "https://alias.gwangju.kr/alias-page" in urls
    assert "https://bukgu.gwangju.kr/nested-page" in urls
    assert "https://evil.example/external-loc" not in urls


def test_mapper_default_sitemap_candidate_scope_rejected():
    """D7: default/fallback sitemap candidates must be scope-checked when
    the acquisition policy is set.  A base_url whose default sitemap path
    is on a non-allowed domain must be excluded from the candidate list.
    """
    policy = _scope_policy(["bukgu.gwangju.kr"])
    mapper = HomepageMapper(acquisition_policy=policy)

    def fake_fetch_content(url, retries=1):
        if url.endswith("/robots.txt"):
            return "", None, 200, url
        if url.endswith(".xml"):
            return "<urlset/>", None, 200, url
        return _homepage_html(), None, 200, url

    with patch.object(mapper, "fetch_content", side_effect=fake_fetch_content), \
         patch.object(mapper.sitemap_parser, "parse",
                      return_value={"error": "", "sitemaps": [], "urls": []}):
        result = mapper.build_map("https://bukgu.gwangju.kr/")

    candidates = result["sitemap"]["candidates"]
    assert all("bukgu.gwangju.kr" in c for c in candidates)
    assert len(result["sitemap"]["urls"]) == 0  # sitemap body not parsed when candidates are on different host


def test_mapper_default_sitemap_candidate_external_base_url_rejected():
    """D7: when base_url itself is not an allowed domain, the default
    sitemap candidates are still added but the policy check at line 335-339
    filters them out.  This ensures the policy is always applied.
    """
    policy = _scope_policy(["different.allowed.kr"])
    mapper = HomepageMapper(acquisition_policy=policy)
    fetched = []

    def fake_fetch_content(url, retries=1):
        fetched.append(url)
        return "", None, 200, url

    with patch.object(mapper, "fetch_content", side_effect=fake_fetch_content), \
         patch.object(mapper.sitemap_parser, "parse",
                      return_value={"error": "", "sitemaps": [], "urls": []}):
        mapper.build_map("https://external-host.kr/")

    # robots.txt is still fetched (it's always fetched), but sitemap candidates
    # are filtered by policy before being fetched.
    assert "https://external-host.kr/sitemap.xml" not in fetched
    assert "https://external-host.kr/sitemap_index.xml" not in fetched


def test_mapper_robots_final_external_body_not_trusted():
    """D3: when the robots effective/final URL is outside the scope, the
    body content is never parsed for Sitemap directives.  Even if the body
    contains a valid in-scope sitemap URL that is NOT among the default
    candidates, it must be discarded.
    """
    policy = _scope_policy(["bukgu.gwangju.kr"])
    mapper = HomepageMapper(acquisition_policy=policy)

    # The body contains a sitemap directive that would be a NEW candidate
    # (not one of the defaults).  The final URL leaves the scope, so the
    # directive must be discarded — the default candidates are the only
    # entries present.
    robots_body = "Sitemap: https://bukgu.gwangju.kr/sitemap_extra.xml"

    def fake_fetch_content(url, retries=1):
        if url.endswith("/robots.txt"):
            return robots_body, None, 200, "https://evil.example/robots.txt"
        return "", None, 200, url

    with patch.object(mapper, "fetch_content", side_effect=fake_fetch_content), \
         patch.object(mapper.sitemap_parser, "parse",
                      return_value={"error": "", "sitemaps": [], "urls": []}):
        result = mapper.build_map("https://bukgu.gwangju.kr/")

    # Default candidates are always present (sitemap.xml, sitemap_index.xml).
    # The extra sitemap from the external robots body must NOT be added.
    default_candidates = [
        "https://bukgu.gwangju.kr/sitemap.xml",
        "https://bukgu.gwangju.kr/sitemap_index.xml",
    ]
    candidates = result["sitemap"]["candidates"]
    assert len(candidates) == len(default_candidates)
    assert candidates == default_candidates
    assert any("robots" in e and "outside the acquisition scope" in e
               for e in result["sitemap"]["errors"])


def test_mapper_external_homepage_final_body_title_nav_description_zeroed():
    """C2: when the final/effective homepage URL leaves the scope, the
    external response body/title/nav/description must all be zero — the
    external host's content is never trusted as active-site data.
    """
    policy = _scope_policy(["bukgu.gwangju.kr"])
    mapper = HomepageMapper(acquisition_policy=policy)
    external_homepage = (
        "<html><head>"
        "<title>External Title</title>"
        '<meta name="description" content="External desc">'
        "</head><body>"
        "<nav><a href=\"/page\">External Nav</a></nav>"
        "</body></html>"
    )

    def fake_fetch_content(url, retries=1):
        if url.endswith("/robots.txt"):
            return "", None, 200, url
        # The effective/final URL leaves the scope
        return external_homepage, None, 200, "https://evil.example/"

    with patch.object(mapper, "fetch_content", side_effect=fake_fetch_content), \
         patch.object(mapper.sitemap_parser, "parse",
                      return_value={"error": "", "sitemaps": [], "urls": []}):
        result = mapper.build_map("https://bukgu.gwangju.kr/")

    assert result["homepage"]["title"] == ""
    assert result["homepage"]["description"] == ""
    assert result["homepage"]["navigation_links"] == []
    assert result["homepage"]["attachment_links"] == []
    assert any("outside the acquisition scope" in e for e in result["homepage"]["errors"])


def test_mapper_explicit_allowed_alias_nav_preserved():
    """C5: an explicitly configured allowed alias in navigation links is
    preserved (exact host match from allowed_domains).
    """
    policy = _scope_policy(["bukgu.gwangju.kr", "alias.gwangju.kr"])
    mapper = HomepageMapper(acquisition_policy=policy)
    html = (
        "<html><body><nav>"
        "<a href=\"https://alias.gwangju.kr/alias-page\">Alias Link</a>"
        "<a href=\"https://www.alias.gwangju.kr/www-alias\">www alias</a>"
        "</nav></body></html>"
    )
    nav_links, _ = mapper.extract_menu_links(
        html, "https://bukgu.gwangju.kr/", acquisition_policy=policy
    )
    urls = [l["url"] for l in nav_links]
    assert "https://alias.gwangju.kr/alias-page" in urls
    # www.alias.gwangju.kr is NOT the same as alias.gwangju.kr — the exact
    # host match rejects it unless explicitly configured.
    assert "https://www.alias.gwangju.kr/www-alias" not in urls


def test_mapper_explicit_allowed_alias_sitemap_allowed():
    """D6: an explicitly configured alias host in a sitemap <loc> entry
    is retained (exact host match from allowed_domains).
    """
    policy = _scope_policy(["bukgu.gwangju.kr", "alias.gwangju.kr"])
    mapper = HomepageMapper(acquisition_policy=policy)

    def fake_fetch_content(url, retries=1):
        if url.endswith("/robots.txt"):
            return "Sitemap: https://bukgu.gwangju.kr/sitemap.xml", None, 200, url
        if url.endswith(".xml"):
            return "<urlset/>", None, 200, url
        return _homepage_html(), None, 200, url

    def fake_parse(xml):
        return {"error": "", "sitemaps": [], "urls": [
            {"url": "https://alias.gwangju.kr/alias-page"},
            {"url": "https://bukgu.gwangju.kr/notice"},
            {"url": "https://evil.example/external-loc"},
        ]}

    with patch.object(mapper, "fetch_content", side_effect=fake_fetch_content), \
         patch.object(mapper.sitemap_parser, "parse", side_effect=fake_parse):
        result = mapper.build_map("https://bukgu.gwangju.kr/")

    urls = [u["url"] for u in result["sitemap"]["urls"]]
    assert "https://alias.gwangju.kr/alias-page" in urls
    assert "https://bukgu.gwangju.kr/notice" in urls
    assert "https://evil.example/external-loc" not in urls


def test_mapper_external_attachment_excluded():
    """C6: an external PDF/document URL inside a nav element is excluded from
    attachment_links at extraction time — it never enters the active-site
    pipeline as a document record.  Bounded diagnostic appears in rejected_urls
    without leaking any response body, credential, or attacker data."""
    policy = _scope_policy(["bukgu.gwangju.kr"])
    mapper = HomepageMapper(acquisition_policy=policy)
    html = (
        "<html><body><nav>"
        '<a href="https://bukgu.gwangju.kr/form.pdf">Internal Form</a>'
        '<a href="https://evil.example/evil.pdf">Evil PDF</a>'
        '<a href="https://alien.example/doc.hwp">Alien HWP</a>'
        "</nav></body></html>"
    )
    nav_links, att_links = mapper.extract_menu_links(
        html, "https://bukgu.gwangju.kr/", acquisition_policy=policy
    )
    att_urls = {a["url"] for a in att_links}
    assert "https://bukgu.gwangju.kr/form.pdf" in att_urls
    assert "https://evil.example/evil.pdf" not in att_urls
    assert "https://alien.example/doc.hwp" not in att_urls


def test_mapper_external_attachment_never_reaches_indexer():
    """C6: external PDF URLs excluded from attachment_links can never reach
    DocumentIndexer — the indexer only receives what the mapper produces."""
    from src.indexer.document_indexer import DocumentIndexer

    policy = _scope_policy(["bukgu.gwangju.kr"])
    mapper = HomepageMapper(acquisition_policy=policy)
    html = (
        "<html><body><nav>"
        '<a href="https://bukgu.gwangju.kr/form.pdf">Internal Form</a>'
        '<a href="https://evil.example/evil.pdf">Evil PDF</a>'
        "</nav></body></html>"
    )

    def fake_fetch_content(url, retries=1):
        if url.endswith("/robots.txt"):
            return "", None, 200, url
        return html, None, 200, url

    with patch.object(mapper, "fetch_content", side_effect=fake_fetch_content), \
         patch.object(mapper.sitemap_parser, "parse",
                      return_value={"error": "", "sitemaps": [], "urls": []}):
        result = mapper.build_map("https://bukgu.gwangju.kr/")

    assert result["stats"]["attachment_count"] == 1  # only internal
    att_urls = {a["url"] for a in result["homepage"]["attachment_links"]}
    assert "https://bukgu.gwangju.kr/form.pdf" in att_urls
    assert "https://evil.example/evil.pdf" not in att_urls

    docs = DocumentIndexer().build_index(result)
    doc_urls = [d.get("url") for d in docs]
    assert "https://evil.example/evil.pdf" not in doc_urls
    assert "https://bukgu.gwangju.kr/form.pdf" in doc_urls


def test_mapper_external_attachment_bounded_diagnostic():
    """C6: when a homepage nav/attachment is scope-rejected, a bounded
    deterministic diagnostic appears in rejected_urls.  The diagnostic
    contains only url, reason, and allowed_domains — no response body,
    credential, or unbounded attacker data."""
    policy = _scope_policy(["bukgu.gwangju.kr"])
    mapper = HomepageMapper(acquisition_policy=policy)
    html = (
        "<html><body><nav>"
        '<a href="https://evil.example/evil.pdf">Evil PDF</a>'
        '<a href="https://alien.example/page">Alien Nav</a>'
        "</nav></body></html>"
    )

    def fake_fetch_content(url, retries=1):
        if url.endswith("/robots.txt"):
            return "", None, 200, url
        return html, None, 200, url

    with patch.object(mapper, "fetch_content", side_effect=fake_fetch_content), \
         patch.object(mapper.sitemap_parser, "parse",
                      return_value={"error": "", "sitemaps": [], "urls": []}):
        result = mapper.build_map("https://bukgu.gwangju.kr/")

    rejected = result.get("rejected_urls", [])
    assert len(rejected) >= 2
    for entry in rejected:
        assert "url" in entry
        assert "reason" in entry
        assert entry["reason"] == "homepage_navigation"
        assert "allowed_domains" in entry
        # Bounded diagnostic: no body, no credential, no secret
        assert "body" not in entry
        assert "credential" not in entry
        assert "secret" not in entry
        assert "Authorization" not in str(entry)
    reasons = [e["url"] for e in rejected]
    assert "https://evil.example/evil.pdf" in reasons
    assert "https://alien.example/page" in reasons


def test_mapper_rejected_urls_diagnostics_no_secret_leak():
    """Across multiple rejection types in rejected_urls, no entry contains
    attacker-controlled body content, credentials, or secrets."""
    policy = _scope_policy(["bukgu.gwangju.kr"])
    mapper = HomepageMapper(acquisition_policy=policy)
    html = "<html><body><nav><a href='https://evil.example/page'>Evil</a></nav></body></html>"

    def fake_fetch_content(url, retries=1):
        if url.endswith("/robots.txt"):
            return "Sitemap: https://bukgu.gwangju.kr/sitemap.xml", None, 200, url
        return html, None, 200, url

    def fake_parse(xml):
        return {"error": "", "sitemaps": ["https://evil.example/nested.xml"], "urls": [
            {"url": "https://evil.example/loc"},
        ]}

    with patch.object(mapper, "fetch_content", side_effect=fake_fetch_content), \
         patch.object(mapper.sitemap_parser, "parse", side_effect=fake_parse):
        result = mapper.build_map("https://bukgu.gwangju.kr/")

    rejected = result.get("rejected_urls", [])
    seen_reasons = set()
    for entry in rejected:
        seen_reasons.add(entry["reason"])
        assert isinstance(entry["url"], str)
        assert isinstance(entry["reason"], str)
        assert isinstance(entry["allowed_domains"], list)
        for key in entry:
            assert key in ("url", "reason", "allowed_domains")
            val = entry[key]
            val_str = str(val)
            assert "secret" not in val_str.lower()
            assert "credential" not in val_str.lower()
            assert "Authorization" not in val_str
    assert len(seen_reasons) >= 1


# ======================================================================
# #1293: preserve location discovery evidence through mapper + indexer.
# Offline/static only; no provider, DNS, or external network execution.
# ======================================================================

def test_location_category_priority_is_explicit_and_ordered():
    from src.crawler.url_classifier import CATEGORY_PRIORITY

    ordered = [
        "document",
        "apply",
        "notice",
        "board",
        "contact",
        "location",
        "menu",
        "unknown",
    ]
    assert all(
        CATEGORY_PRIORITY[left] > CATEGORY_PRIORITY[right]
        for left, right in zip(ordered, ordered[1:])
    )


def test_location_navigation_and_sitemap_survive_mapper_stats_and_indexer():
    from src.indexer.document_indexer import DocumentIndexer

    mapper = HomepageMapper()
    homepage_html = (
        "<html><head><title>Home</title></head><body><nav>"
        '<a href="/map">오시는길</a>'
        '<a href="/about">소개</a>'
        "</nav></body></html>"
    )

    def fake_fetch_content(url, retries=1):
        if url.endswith("/robots.txt"):
            return "", None, 200, url
        if url.endswith(".xml"):
            return "<urlset/>", None, 200, url
        return homepage_html, None, 200, url

    parsed_sitemap = {
        "error": "",
        "sitemaps": [],
        "urls": [
            {"url": "https://example.com/parking"},
            {"url": "https://example.com/misc"},
        ],
    }

    with patch.object(mapper, "fetch_content", side_effect=fake_fetch_content), \
         patch.object(mapper.sitemap_parser, "parse", return_value=parsed_sitemap):
        result = mapper.build_map("https://example.com/")

    assert result["categories"]["location"] == [
        "https://example.com/map",
        "https://example.com/parking",
    ]
    assert result["categories"]["menu"] == ["https://example.com/about"]
    assert result["categories"]["unknown"] == ["https://example.com/misc"]
    assert result["stats"]["category_counts"]["location"] == 2
    assert result["stats"]["category_counts"]["menu"] == 1
    assert result["stats"]["category_counts"]["unknown"] == 1

    docs = {doc["url"]: doc for doc in DocumentIndexer().build_index(result)}
    assert docs["https://example.com/map"]["category"] == "location"
    assert docs["https://example.com/parking"]["category"] == "location"
    assert docs["https://example.com/about"]["category"] == "menu"
    assert docs["https://example.com/misc"]["category"] == "unknown"


def test_mapper_unsupported_category_still_degrades_to_unknown():
    mapper = HomepageMapper()
    homepage_html = (
        "<html><head><title>Home</title></head><body><nav>"
        '<a href="/future">Future</a>'
        "</nav></body></html>"
    )

    def fake_fetch_content(url, retries=1):
        if url.endswith("/robots.txt"):
            return "", None, 200, url
        if url.endswith(".xml"):
            return "<urlset/>", None, 200, url
        return homepage_html, None, 200, url

    with patch.object(mapper, "fetch_content", side_effect=fake_fetch_content), \
         patch.object(mapper.sitemap_parser, "parse",
                      return_value={"error": "", "sitemaps": [], "urls": []}), \
         patch("src.crawler.homepage_mapper.classify_url", return_value="future_category"):
        result = mapper.build_map("https://example.com/")

    assert result["categories"]["unknown"] == ["https://example.com/future"]
    assert result["stats"]["category_counts"]["unknown"] == 1
