import json
import logging

import pytest
from bs4 import BeautifulSoup
from src.crawler.url_crawler import URLCrawler

def test_title_extraction():
    crawler = URLCrawler()
    html = "<html><head><title> Test Title </title></head><body></body></html>"
    soup = BeautifulSoup(html, 'html.parser')
    assert soup.title.get_text().strip() == "Test Title"

def test_meta_description_extraction():
    # Test name='description'
    html1 = '<html><head><meta name="description" content="This is description"></head></html>'
    soup1 = BeautifulSoup(html1, 'html.parser')
    desc_tag1 = soup1.find('meta', attrs={'name': lambda x: x and x.lower() == 'description'})
    assert desc_tag1.get('content').strip() == "This is description"

    # Test og:description fallback
    html2 = '<html><head><meta property="og:description" content="This is og description"></head></html>'
    soup2 = BeautifulSoup(html2, 'html.parser')
    og_desc_tag = soup2.find('meta', attrs={'property': 'og:description'})
    assert og_desc_tag.get('content').strip() == "This is og description"

def test_clean_text_and_script_style_removal():
    crawler = URLCrawler()
    html = """
    <html>
      <head>
        <style>body { color: red; }</style>
        <script>console.log("hello");</script>
      </head>
      <body>
        <noscript>Turn on Javascript</noscript>
        <div>Hello World</div>
        <p>This is  a test paragraph.  </p>
      </body>
    </html>
    """
    soup = BeautifulSoup(html, 'html.parser')
    clean_text = crawler.clean_text(soup)
    
    # style, script, noscript이 제거되어야 함
    assert "body { color: red; }" not in clean_text
    assert "console.log" not in clean_text
    assert "Turn on Javascript" not in clean_text
    
    # 텍스트 추출 및 정리 확인
    assert "Hello World" in clean_text
    assert "This is  a test paragraph." in clean_text

def test_link_classification_and_normalization():
    crawler = URLCrawler()
    base_url = "https://example.com/subpage/index.html"
    
    html = """
    <html>
      <body>
        <!-- Internal Link -->
        <a href="/internal-path">Internal Link</a>
        <!-- External Link -->
        <a href="https://other.com/path">External Link</a>
        <!-- Attachment -->
        <a href="../docs/manual.pdf">PDF Manual</a>
        <a href="https://example.com/files/report.HWP">HWP Document</a>
        <!-- Duplicate Link with different text -->
        <a href="/internal-path">New Internal Text</a>
        <!-- Special Links to ignore -->
        <a href="javascript:void(0)">JS Link</a>
        <a href="#">Anchor Only</a>
      </body>
    </html>
    """
    soup = BeautifulSoup(html, 'html.parser')
    links = crawler.extract_links(soup, base_url)
    
    # Check Internal
    assert len(links["internal"]) == 1  # /internal-path 하나만 (중복제거)
    assert links["internal"][0]["url"] == "https://example.com/internal-path"
    
    # Check External
    assert len(links["external"]) == 1
    assert links["external"][0]["url"] == "https://other.com/path"

    # Check Attachments
    assert len(links["attachments"]) == 2
    urls = [item["url"] for item in links["attachments"]]
    assert "https://example.com/docs/manual.pdf" in urls
    assert "https://example.com/files/report.HWP" in urls
    
    types = [item["type"] for item in links["attachments"]]
    assert "pdf" in types
    assert "hwp" in types


# ======================================================================
# FetchProvider injection tests
# ======================================================================

def test_crawler_with_mock_fetch_provider():
    """URLCrawler with fetch_provider='mock' uses MockFetchProvider."""
    from src.fetch import MockFetchProvider
    crawler = URLCrawler(fetch_provider="mock")
    assert crawler.fetch_provider is not None
    assert crawler.fetch_provider.name == "mock"
    # analyze() should return a valid result (mock returns HTML)
    result = crawler.analyze("https://bukgu.gwangju.kr/", max_chars=500)
    assert result["status_code"] == 200
    assert len(result["errors"]) == 0


def test_crawler_with_none_fetch_provider_uses_original():
    """URLCrawler with fetch_provider=None keeps original behavior."""
    crawler = URLCrawler()
    assert crawler.fetch_provider is None
    # Should use original path — test with BeautifulSoup directly
    from bs4 import BeautifulSoup
    html = "<html><head><title>Original</title></head><body>Hello</body></html>"
    soup = BeautifulSoup(html, 'html.parser')
    clean_text = crawler.clean_text(soup)
    assert "Hello" in clean_text


def test_crawler_fetch_provider_name_string():
    """URLCrawler accepts provider name string for fetch_provider."""
    crawler = URLCrawler(fetch_provider="mock")
    assert crawler.fetch_provider is not None
    assert crawler.fetch_provider.name == "mock"


def test_crawler_fetch_provider_instance():
    """URLCrawler accepts a FetchProvider instance."""
    from src.fetch import MockFetchProvider
    provider = MockFetchProvider()
    crawler = URLCrawler(fetch_provider=provider)
    assert crawler.fetch_provider is provider


def test_crawler_fetch_provider_error_returns_error_result():
    """When fetch_provider returns ok=False, analyze() returns errors."""
    from src.fetch import MockFetchProvider

    class FailingProvider(MockFetchProvider):
        def fetch(self, url, **kwargs):
            from src.fetch.base import FetchResult
            from datetime import datetime, timezone
            return FetchResult(
                url=url, ok=False, provider="mock_fail",
                fetched_at=datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                error="Simulated failure",
            )

    crawler = URLCrawler(fetch_provider=FailingProvider())
    result = crawler.analyze("https://example.com/")
    assert len(result["errors"]) > 0
    assert "Simulated failure" in result["errors"][0]


# ======================================================================
# Stage 390: Path filtering wiring and default-allow tests
# ======================================================================

def test_default_no_filters_preserves_internal_links():
    # A. default no filters preserves internal links
    base_url = "https://example.com"
    html = """
    <html>
      <body>
        <a href="/allowed1">Allowed 1</a>
        <a href="/allowed2">Allowed 2</a>
        <a href="/denied?print=1">Print URL</a>
      </body>
    </html>
    """
    soup = BeautifulSoup(html, 'html.parser')

    # Case 1: None
    crawler_none = URLCrawler(crawl_filters=None)
    links_none = crawler_none.extract_links(soup, base_url)
    assert len(links_none["internal"]) == 3

    # Case 2: {}
    crawler_empty = URLCrawler(crawl_filters={})
    links_empty = crawler_empty.extract_links(soup, base_url)
    assert len(links_empty["internal"]) == 3


def test_explicit_deny_removes_matching_internal_links():
    # B. explicit deny removes matching internal links
    base_url = "https://example.com"
    html = """
    <html>
      <body>
        <a href="/allowed1">Allowed 1</a>
        <a href="/denied?print=1">Print URL</a>
        <a href="/denied?utm_source=facebook">Tracking URL</a>
      </body>
    </html>
    """
    soup = BeautifulSoup(html, 'html.parser')

    crawler = URLCrawler(crawl_filters={
        "deny_patterns": ["print=", "utm_source="]
    })
    links = crawler.extract_links(soup, base_url)
    assert len(links["internal"]) == 1
    assert links["internal"][0]["url"] == "https://example.com/allowed1"


def test_protected_overrides_deny():
    # C. protected overrides deny
    base_url = "https://bukgu.gwangju.kr"
    html = """
    <html>
      <body>
        <a href="/menu.es?mid=a10103000000">Protected Menu</a>
        <a href="/menu.es?print=1">Denied Print Menu</a>
      </body>
    </html>
    """
    soup = BeautifulSoup(html, 'html.parser')

    crawler = URLCrawler(crawl_filters={
        "deny_patterns": ["menu.es"],
        "protected_patterns": ["mid="]
    })
    links = crawler.extract_links(soup, base_url)
    assert len(links["internal"]) == 1
    assert links["internal"][0]["url"] == "https://bukgu.gwangju.kr/menu.es?mid=a10103000000"


def test_allow_overrides_deny():
    # D. allow overrides deny
    base_url = "https://example.com"
    html = """
    <html>
      <body>
        <a href="/board/notice/view?id=123">Allowed view</a>
        <a href="/board/notice/delete?id=123">Denied delete</a>
      </body>
    </html>
    """
    soup = BeautifulSoup(html, 'html.parser')

    crawler = URLCrawler(crawl_filters={
        "allow_patterns": ["notice/view"],
        "deny_patterns": ["notice"]
    })
    links = crawler.extract_links(soup, base_url)
    assert len(links["internal"]) == 1
    assert links["internal"][0]["url"] == "https://example.com/board/notice/view?id=123"


def test_municipal_structural_urls_allowed_by_unrelated_deny():
    # E. municipal structural URLs allowed by unrelated deny
    base_url = "https://bukgu.gwangju.kr"
    html = """
    <html>
      <body>
        <a href="/menu.es?mid=a101">Menu ES mid</a>
        <a href="/some/path?menuId=a101">Menu ID</a>
        <a href="/board.es?seq=999">Board ES seq</a>
        <a href="/content?contentId=123">Content ID</a>
        <a href="/print-page?print=1">Unrelated Denied Page</a>
      </body>
    </html>
    """
    soup = BeautifulSoup(html, 'html.parser')

    crawler = URLCrawler(crawl_filters={
        "deny_patterns": ["print="]
    })
    links = crawler.extract_links(soup, base_url)
    assert len(links["internal"]) == 4
    urls = [item["url"] for item in links["internal"]]
    assert "https://bukgu.gwangju.kr/menu.es?mid=a101" in urls
    assert "https://bukgu.gwangju.kr/some/path?menuId=a101" in urls
    assert "https://bukgu.gwangju.kr/board.es?seq=999" in urls
    assert "https://bukgu.gwangju.kr/content?contentId=123" in urls


def test_external_links_unaffected():
    # F. external links unaffected
    base_url = "https://example.com"
    html = """
    <html>
      <body>
        <a href="https://external-site.com/denied?print=1">External Denied URL</a>
        <a href="/internal/denied?print=1">Internal Denied URL</a>
      </body>
    </html>
    """
    soup = BeautifulSoup(html, 'html.parser')

    crawler = URLCrawler(crawl_filters={
        "deny_patterns": ["print="]
    })
    links = crawler.extract_links(soup, base_url)
    assert len(links["internal"]) == 0
    assert len(links["external"]) == 1
    assert links["external"][0]["url"] == "https://external-site.com/denied?print=1"


def test_no_runtime_behavior_change_for_default_constructor():
    # G. no runtime behavior change for default constructor
    crawler = URLCrawler()
    assert crawler.crawl_filters is None


# ======================================================================
# Stage 391: Safe SiteProfile-to-URLCrawler mapping path and contracts
# ======================================================================

def test_homepage_mapper_mapping_path_from_synthetic_profile():
    from src.crawler.homepage_mapper import HomepageMapper
    from src.site_profiles.site_profile import SiteProfile

    # 1. Create a synthetic profile containing crawl filters
    profile_data = {
        "site_id": "synthetic_gov",
        "name": "Synthetic Gov",
        "base_url": "https://synthetic.gov.kr/",
        "crawl_filters": {
            "allow_patterns": ["/allowed/"],
            "deny_patterns": ["print="],
            "protected_patterns": ["mid="]
        }
    }
    profile = SiteProfile(profile_data)

    # 2. Instantiate HomepageMapper with the profile's crawl filters
    mapper = HomepageMapper(crawl_filters=profile.crawl_filters)

    # 3. Assert the crawl filters dictionary is successfully mapped and passed to URLCrawler
    assert mapper.crawler.crawl_filters == {
        "allow_patterns": ["/allowed/"],
        "deny_patterns": ["print="],
        "protected_patterns": ["mid="]
    }


def test_existing_profiles_without_crawl_filters_preserve_default_behavior():
    from src.crawler.homepage_mapper import HomepageMapper
    from src.site_profiles.site_profile import SiteProfile

    # Profile without crawl_filters (empty or omitted)
    profile_data = {
        "site_id": "existing_legacy_gov",
        "name": "Legacy Gov",
        "base_url": "https://legacy.gov.kr/"
    }
    profile = SiteProfile(profile_data)

    # Instantiate with the profile's crawl filters (which defaults to empty dict from SiteProfile property)
    mapper = HomepageMapper(crawl_filters=profile.crawl_filters)
    assert mapper.crawler.crawl_filters == {}

    # Verify that it allows all internal URLs
    html = """
    <html>
      <body>
        <a href="/menu.es?mid=1">Menu</a>
        <a href="/page?print=1">Print</a>
        <a href="/normal">Normal</a>
      </body>
    </html>
    """
    soup = BeautifulSoup(html, 'html.parser')
    links = mapper.crawler.extract_links(soup, "https://legacy.gov.kr/")
    assert len(links["internal"]) == 3


def test_mock_static_html_crawl_safety():
    from src.crawler.homepage_mapper import HomepageMapper
    from src.site_profiles.site_profile import SiteProfile

    # Synthetic profile
    profile_data = {
        "site_id": "safety_gov",
        "name": "Safety Gov",
        "base_url": "https://safety.gov.kr/",
        "crawl_filters": {
            "deny_patterns": ["print="],
            "protected_patterns": ["mid="]
        }
    }
    profile = SiteProfile(profile_data)
    mapper = HomepageMapper(crawl_filters=profile.crawl_filters)

    html = """
    <html>
      <body>
        <a href="/menu.es?mid=a101">Menu ES mid</a>
        <a href="/page?print=1">Print Page</a>
        <a href="/normal">Normal Page</a>
      </body>
    </html>
    """
    soup = BeautifulSoup(html, 'html.parser')
    links = mapper.crawler.extract_links(soup, "https://safety.gov.kr/")

    urls = [link["url"] for link in links["internal"]]
    # /menu.es?mid=a101 -> survives (protected)
    assert "https://safety.gov.kr/menu.es?mid=a101" in urls
    # /page?print=1 -> removed (deny)
    assert "https://safety.gov.kr/page?print=1" not in urls
    # /normal -> survives (allow)
    assert "https://safety.gov.kr/normal" in urls


def test_non_html_provider_fallback_path_contract_none_filters():
    from src.crawler.url_crawler import URLCrawler
    from src.fetch.base import FetchProvider, FetchResult
    from datetime import datetime, timezone

    # Mock provider returning flat links (without HTML)
    class FlatLinksProvider(FetchProvider):
        @property
        def name(self) -> str:
            return "flat_mock"

        def fetch(self, url, **kwargs):
            return FetchResult(
                url=url,
                ok=True,
                provider="flat_mock",
                fetched_at=datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                status_code=200,
                content_type="application/json",
                markdown="Mock Content",
                links=[
                    {"text": "Internal Menu", "url": "https://example.com/menu.es?mid=123"},
                    {"text": "Internal Print", "url": "https://example.com/page?print=1"},
                    {"text": "External Link", "url": "https://external.com/page"},
                    {"text": "Attachment", "url": "https://example.com/doc.pdf"}
                ]
            )

    # Case A: crawl_filters = None (default-allow behavior)
    crawler_none = URLCrawler(fetch_provider=FlatLinksProvider(), crawl_filters=None)
    result_none = crawler_none.analyze("https://example.com/")
    links_none = result_none["links"]

    # All internal links should be preserved
    assert len(links_none["internal"]) == 2
    internal_urls_none = [link["url"] for link in links_none["internal"]]
    assert "https://example.com/menu.es?mid=123" in internal_urls_none
    assert "https://example.com/page?print=1" in internal_urls_none

    # External and attachments must remain unaffected
    assert len(links_none["external"]) == 1
    assert links_none["external"][0]["url"] == "https://external.com/page"
    assert len(links_none["attachments"]) == 1
    assert links_none["attachments"][0]["url"] == "https://example.com/doc.pdf"


def test_non_html_provider_fallback_path_contract_explicit_deny():
    from src.crawler.url_crawler import URLCrawler
    from src.fetch.base import FetchProvider, FetchResult
    from datetime import datetime, timezone

    class FlatLinksProvider(FetchProvider):
        @property
        def name(self) -> str:
            return "flat_mock"

        def fetch(self, url, **kwargs):
            return FetchResult(
                url=url,
                ok=True,
                provider="flat_mock",
                fetched_at=datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                status_code=200,
                content_type="application/json",
                markdown="Mock Content",
                links=[
                    {"text": "Internal Menu", "url": "https://example.com/menu.es?mid=123"},
                    {"text": "Internal Print", "url": "https://example.com/page?print=1"},
                    {"text": "External Link", "url": "https://external.com/page?print=1"},
                    {"text": "Attachment", "url": "https://example.com/doc.pdf?print=1"}
                ]
            )

    # Case B: crawl_filters with explicit deny_patterns = ["print="]
    crawler_deny = URLCrawler(
        fetch_provider=FlatLinksProvider(),
        crawl_filters={"deny_patterns": ["print="]}
    )
    result_deny = crawler_deny.analyze("https://example.com/")
    links_deny = result_deny["links"]

    # Internal Print should be removed (only Internal Menu survives)
    assert len(links_deny["internal"]) == 1
    assert links_deny["internal"][0]["url"] == "https://example.com/menu.es?mid=123"

    # External and attachments must NOT be affected by the crawl filter
    assert len(links_deny["external"]) == 1
    assert links_deny["external"][0]["url"] == "https://external.com/page?print=1"
    assert len(links_deny["attachments"]) == 1
    assert links_deny["attachments"][0]["url"] == "https://example.com/doc.pdf?print=1"


def _extract_pipeline_records(caplog: pytest.LogCaptureFixture) -> list[dict[str, object]]:
    records = []
    for line in caplog.messages:
        if line.startswith("pipeline_event="):
            records.append(json.loads(line.split("=", 1)[1]))
    return records


def test_url_crawler_logs_terminal_success_event_for_provider(caplog):
    from datetime import datetime, timezone

    from src.fetch import MockFetchProvider
    from src.fetch.base import FetchResult

    class SuccessProvider(MockFetchProvider):
        def fetch(self, url, **kwargs):
            return FetchResult(
                url=url,
                ok=True,
                provider="mock_success",
                fetched_at=datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                status_code=200,
                content_type="text/html",
                html="<html><head><title>Title</title></head><body><a href='/inner'>go</a></body></html>",
            )

    crawler = URLCrawler(fetch_provider=SuccessProvider())

    with caplog.at_level(logging.INFO, logger="src.crawler.url_crawler"):
        result = crawler.analyze("https://example.com", correlation_id="corr-895")

    records = _extract_pipeline_records(caplog)
    assert result["errors"] == []
    assert [record["event"] for record in records] == ["pipeline_stage_end"]
    assert records[0]["stage"] == "url_crawler"
    assert records[0]["ok"] is True
    assert records[0]["correlation_id"] == "corr-895"
    assert isinstance(records[0]["duration_ms"], int)


def test_url_crawler_logs_terminal_fail_event_for_provider_result_error(caplog):
    from datetime import datetime, timezone

    from src.fetch import MockFetchProvider
    from src.fetch.base import FetchResult

    class FailingProvider(MockFetchProvider):
        def fetch(self, url, **kwargs):
            return FetchResult(
                url=url,
                ok=False,
                provider="mock_fail",
                fetched_at=datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                error="Bearer secret token https://secret.example.com/fail",
            )

    crawler = URLCrawler(fetch_provider=FailingProvider())

    with caplog.at_level(logging.INFO, logger="src.crawler.url_crawler"):
        result = crawler.analyze("https://example.com", correlation_id="corr-fail")

    records = _extract_pipeline_records(caplog)
    assert result["errors"]
    assert [record["event"] for record in records] == ["pipeline_stage_fail"]
    assert records[0]["stage"] == "url_crawler"
    assert records[0]["ok"] is False
    assert records[0]["correlation_id"] == "corr-fail"
    assert records[0]["failure_code"] == "url_crawler_result_error"
    assert isinstance(records[0]["duration_ms"], int)


def test_url_crawler_preserves_empty_correlation_id(caplog):
    from datetime import datetime, timezone

    from src.fetch import MockFetchProvider
    from src.fetch.base import FetchResult

    class SuccessProvider(MockFetchProvider):
        def fetch(self, url, **kwargs):
            return FetchResult(
                url=url,
                ok=True,
                provider="mock_success",
                fetched_at=datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                status_code=200,
                content_type="text/html",
                html="<html><body>Hello</body></html>",
            )

    crawler = URLCrawler(fetch_provider=SuccessProvider())

    with caplog.at_level(logging.INFO, logger="src.crawler.url_crawler"):
        crawler.analyze("https://example.com", correlation_id="")

    records = _extract_pipeline_records(caplog)
    assert records
    assert {record["correlation_id"] for record in records} == {""}


def test_url_crawler_without_correlation_id_logs_nothing(caplog):
    from datetime import datetime, timezone

    from src.fetch import MockFetchProvider
    from src.fetch.base import FetchResult

    class SuccessProvider(MockFetchProvider):
        def fetch(self, url, **kwargs):
            return FetchResult(
                url=url,
                ok=True,
                provider="mock_success",
                fetched_at=datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                status_code=200,
                content_type="text/html",
                html="<html><body>Hello</body></html>",
            )

    crawler = URLCrawler(fetch_provider=SuccessProvider())

    with caplog.at_level(logging.INFO, logger="src.crawler.url_crawler"):
        crawler.analyze("https://example.com")

    assert "pipeline_event=" not in "\n".join(caplog.messages)


def test_url_crawler_event_redacts_raw_failure_contents(caplog):
    from datetime import datetime, timezone

    from src.fetch import MockFetchProvider
    from src.fetch.base import FetchResult

    class FailingProvider(MockFetchProvider):
        def fetch(self, url, **kwargs):
            return FetchResult(
                url="https://secret.example.com/private?token=abc123",
                ok=False,
                provider="mock_fail",
                fetched_at=datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                error="Bearer sk-secret token leaked from https://secret.example.com/private?token=abc123",
            )

    crawler = URLCrawler(fetch_provider=FailingProvider())

    with caplog.at_level(logging.INFO, logger="src.crawler.url_crawler"):
        crawler.analyze("https://example.com", correlation_id="corr-redact")

    records = _extract_pipeline_records(caplog)
    assert [record["event"] for record in records] == ["pipeline_stage_fail"]
    allowed_keys = {
        "event",
        "correlation_id",
        "stage",
        "ok",
        "duration_ms",
        "failure_code",
    }
    joined_logs = "\n".join(caplog.messages)
    for record in records:
        assert set(record).issubset(allowed_keys)
    assert "Bearer" not in joined_logs
    assert "token" not in joined_logs
    assert "https://secret.example.com/private?token=abc123" not in joined_logs


def test_url_crawler_requests_provider_without_fetch_config_preserves_fetch_kwargs():
    from datetime import datetime, timezone

    from src.fetch import FetchResult, RequestsFetchProvider

    class SpyRequestsProvider(RequestsFetchProvider):
        def __init__(self):
            super().__init__(timeout=99)
            self.calls = []

        def fetch(self, url, **kwargs):
            self.calls.append((url, dict(kwargs)))
            return FetchResult(
                url=url,
                ok=True,
                provider="requests",
                fetched_at=datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                status_code=200,
                content_type="text/html",
                html="<html><head><title>T</title></head><body>Hello</body></html>",
            )

    provider = SpyRequestsProvider()
    crawler = URLCrawler(fetch_provider=provider, timeout=7)

    result = crawler.analyze("https://example.com")

    assert result["status_code"] == 200
    assert result["errors"] == []
    assert provider.calls == [("https://example.com", {"timeout": 7})]


def test_url_crawler_threads_fetch_config_to_requests_provider_without_timeout_kwarg():
    from datetime import datetime, timezone

    from src.fetch import FetchConfig, FetchResult, RequestsFetchProvider

    class SpyRequestsProvider(RequestsFetchProvider):
        def __init__(self):
            super().__init__(timeout=99)
            self.calls = []

        def fetch(self, url, **kwargs):
            self.calls.append((url, dict(kwargs)))
            return FetchResult(
                url=url,
                ok=True,
                provider="requests",
                fetched_at=datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                status_code=200,
                content_type="text/html",
                html="<html><head><title>T</title></head><body>Hello</body></html>",
            )

    provider = SpyRequestsProvider()
    config = FetchConfig(timeout=12.5, max_retries=1, retry_backoff=0.0, retry_on_status=(503,))
    crawler = URLCrawler(fetch_provider=provider, timeout=7, fetch_config=config)

    result = crawler.analyze("https://example.com")

    assert result["status_code"] == 200
    assert result["errors"] == []
    assert len(provider.calls) == 1
    assert provider.calls[0][0] == "https://example.com"
    assert provider.calls[0][1]["config"] is config
    assert "timeout" not in provider.calls[0][1]


def test_url_crawler_does_not_pass_fetch_config_to_mock_or_custom_provider():
    from datetime import datetime, timezone

    from src.fetch import FetchConfig, FetchResult, MockFetchProvider
    from src.fetch.base import FetchProvider

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
                html="<html><head><title>Custom</title></head><body>Body</body></html>",
            )

    config = FetchConfig(timeout=9.5, max_retries=2, retry_backoff=0.1, retry_on_status=(503,))

    mock_provider = SpyMockProvider()
    mock_crawler = URLCrawler(fetch_provider=mock_provider, timeout=5, fetch_config=config)
    mock_result = mock_crawler.analyze("https://example.com")

    custom_provider = CustomProvider()
    custom_crawler = URLCrawler(fetch_provider=custom_provider, timeout=6, fetch_config=config)
    custom_result = custom_crawler.analyze("https://example.com")

    assert mock_result["status_code"] == 200
    assert custom_result["status_code"] == 200
    assert mock_provider.calls == [("https://example.com", {"timeout": 5})]
    assert custom_provider.calls == [("https://example.com", {"timeout": 6})]


def test_url_crawler_fetch_config_preserves_failure_result_schema():
    from datetime import datetime, timezone

    from src.fetch import FetchConfig, FetchResult, RequestsFetchProvider

    class FailingRequestsProvider(RequestsFetchProvider):
        def __init__(self):
            super().__init__(timeout=99)

        def fetch(self, url, **kwargs):
            return FetchResult(
                url=url,
                ok=False,
                provider="requests",
                fetched_at=datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                error="Configured failure",
            )

    crawler = URLCrawler(
        fetch_provider=FailingRequestsProvider(),
        fetch_config=FetchConfig(timeout=8.0, max_retries=1, retry_backoff=0.0, retry_on_status=(503,)),
    )

    result = crawler.analyze("https://example.com")

    assert set(result.keys()) == {
        "url",
        "status_code",
        "content_type",
        "title",
        "description",
        "text",
        "links",
        "stats",
        "errors",
    }
    assert result["errors"] == ["Configured failure"]
    assert result["status_code"] == ""
    assert result["links"] == {"internal": [], "external": [], "attachments": []}


# ======================================================================
# Stage 1: Lock crawler direct-fallback contracts (#834-stage1)
# ======================================================================

def test_url_crawler_direct_fallback_success(monkeypatch):
    class FakeResult:
        ok = True
        url = "https://example.com/final-url"
        status_code = 200
        content_type = "text/html; charset=utf-8"
        html = """
        <html>
            <head>
                <title>Success Title</title>
                <meta name="description" content="Success Description">
            </head>
            <body>
                <a href="/internal">Internal Link</a>
                <a href="https://external.com">External Link</a>
                <a href="/doc.pdf">Attachment Link</a>
            </body>
        </html>
        """
        text = html
        error = ""

    called_kwargs = {}
    def mock_fetch(self, url, **kwargs):
        called_kwargs["url"] = url
        called_kwargs["headers"] = kwargs.get("headers")
        called_kwargs["timeout"] = kwargs.get("timeout")
        called_kwargs["compatibility_mode"] = kwargs.get("compatibility_mode")
        called_kwargs["legacy_transport"] = kwargs.get("legacy_transport")
        return FakeResult()

    import unittest.mock
    monkeypatch.setattr(
        "src.crawler.url_crawler.RequestsFetchProvider.fetch", mock_fetch
    )

    crawler = URLCrawler(fetch_provider=None)
    result = crawler.analyze("https://example.com/start-url")

    # Routed through the legacy requests transport with the expected flags.
    assert called_kwargs["url"] == "https://example.com/start-url"
    assert called_kwargs["headers"] == crawler.headers
    assert called_kwargs["timeout"] == crawler.timeout
    assert called_kwargs["compatibility_mode"] is True
    assert called_kwargs["legacy_transport"] is True

    assert result["url"] == "https://example.com/final-url"
    assert result["status_code"] == 200
    assert "text/html" in result["content_type"]
    assert result["title"] == "Success Title"
    assert result["description"] == "Success Description"
    assert "Internal Link" in result["text"]
    assert len(result["links"]["internal"]) == 1
    assert result["links"]["internal"][0]["url"] == "https://example.com/internal"
    assert len(result["links"]["external"]) == 1
    assert result["links"]["external"][0]["url"] == "https://external.com"
    assert len(result["links"]["attachments"]) == 1
    assert result["links"]["attachments"][0]["url"] == "https://example.com/doc.pdf"
    assert result["errors"] == []

    assert set(result) == {
        "url",
        "status_code",
        "content_type",
        "title",
        "description",
        "text",
        "links",
        "stats",
        "errors",
    }
    assert set(result["links"]) == {"internal", "external", "attachments"}
    assert set(result["stats"]) == {
        "text_length",
        "internal_link_count",
        "external_link_count",
        "attachment_count",
    }
    assert result["stats"] == {
        "text_length": len(result["text"]),
        "internal_link_count": 1,
        "external_link_count": 1,
        "attachment_count": 1,
    }


def test_url_crawler_direct_fallback_timeout(monkeypatch):
    class FakeResult:
        ok = False
        url = "https://example.com/start-url"
        status_code = None
        content_type = ""
        html = ""
        text = ""
        error = "Request timed out after 7s"

    def mock_fetch(self, url, **kwargs):
        return FakeResult()

    import unittest.mock
    monkeypatch.setattr(
        "src.crawler.url_crawler.RequestsFetchProvider.fetch", mock_fetch
    )

    crawler = URLCrawler(fetch_provider=None)
    result = crawler.analyze("https://example.com/start-url")

    assert result["errors"] == [f"Request timeout after {crawler.timeout} seconds."]
    assert result["status_code"] is None
    assert result["text"] == ""
    assert result["links"] == {"internal": [], "external": [], "attachments": []}
    assert result["stats"] == {
        "text_length": 0,
        "internal_link_count": 0,
        "external_link_count": 0,
        "attachment_count": 0,
    }


def test_url_crawler_direct_fallback_request_exception(monkeypatch):
    class FakeResult:
        ok = False
        url = "https://example.com/start-url"
        status_code = None
        content_type = ""
        html = ""
        text = ""
        error = "Network error: offline"

    def mock_fetch(self, url, **kwargs):
        return FakeResult()

    import unittest.mock
    monkeypatch.setattr(
        "src.crawler.url_crawler.RequestsFetchProvider.fetch", mock_fetch
    )

    crawler = URLCrawler(fetch_provider=None)
    result = crawler.analyze("https://example.com/start-url")

    assert result["errors"] == ["Network error: offline"]


def test_url_crawler_direct_fallback_http_error_html(monkeypatch):
    class FakeResult:
        ok = False
        url = "https://example.com/error-url"
        status_code = 500
        content_type = "text/html"
        html = "<html><head><title>Error Page</title></head><body>Internal Server Error</body></html>"
        text = html
        error = "HTTP 500"

    def mock_fetch(self, url, **kwargs):
        return FakeResult()

    import unittest.mock
    monkeypatch.setattr(
        "src.crawler.url_crawler.RequestsFetchProvider.fetch", mock_fetch
    )

    crawler = URLCrawler(fetch_provider=None)
    result = crawler.analyze("https://example.com/start-url")

    assert "HTTP Error: Status code 500" in result["errors"]
    assert result["title"] == "Error Page"
    assert "Internal Server Error" in result["text"]


def test_url_crawler_direct_fallback_non_html(monkeypatch):
    """legacy transport / no network.

    A non-HTML 200 still surfaces the same crawler contract after routing
    through the legacy requests transport (single request, body not parsed).
    """
    from src.fetch.requests_provider import req_lib, RequestsFetchProvider

    class FakeResponse:
        status_code = 200
        url = "https://example.com/document.pdf"
        headers = {"Content-Type": "application/pdf"}
        encoding = "utf-8"
        apparent_encoding = "utf-8"
        text = "%PDF-1.4..."

    def mock_get(url, headers=None, timeout=None):
        return FakeResponse()

    monkeypatch.setattr(req_lib, "get", mock_get)

    called_kwargs = {}
    real_fetch = RequestsFetchProvider.fetch

    def spy_fetch(self, url, **kwargs):
        called_kwargs.update(kwargs)
        return real_fetch(self, url, **kwargs)

    monkeypatch.setattr(RequestsFetchProvider, "fetch", spy_fetch)

    crawler = URLCrawler(fetch_provider=None)
    result = crawler.analyze("https://example.com/start-url")

    assert called_kwargs.get("compatibility_mode") is True
    assert called_kwargs.get("legacy_transport") is True
    assert called_kwargs.get("headers") == crawler.headers
    assert called_kwargs.get("timeout") == crawler.timeout

    assert result["errors"] == ["Response content type is not HTML: application/pdf"]
    assert result["title"] == ""
    assert result["text"] == ""
    assert result["links"] == {"internal": [], "external": [], "attachments": []}
    assert result["stats"] == {
        "text_length": 0,
        "internal_link_count": 0,
        "external_link_count": 0,
        "attachment_count": 0,
    }


# ------------------------------------------------------------------
# #949: Lock the crawler attachment-extension taxonomy.
# URLCrawler.attachment_extensions is exactly 5 values; doc/xls/ppt/pptx/zip are
# NOT extracted as attachments (they remain internal links). Link text/URLs here
# carry no document keyword so the classifier does not intervene.
# ------------------------------------------------------------------
def test_url_crawler_attachment_extensions_exact_set():
    """#949 / no network. Default crawler attachment set is exactly 5 values."""
    crawler = URLCrawler()
    assert crawler.attachment_extensions == {"pdf", "hwp", "hwpx", "docx", "xlsx"}


def test_url_crawler_extract_links_attachments_narrow_set():
    """#949 / no network. The 5 narrow extensions are attachments; doc/xls/
    ppt/pptx/zip remain internal links (no document keyword in any href/text)."""
    crawler = URLCrawler()
    html = """
    <html>
      <body>
        <a href="https://example.com/assets/sample.pdf">파일</a>
        <a href="https://example.com/assets/sample.hwp">파일</a>
        <a href="https://example.com/assets/sample.hwpx">파일</a>
        <a href="https://example.com/assets/sample.docx">파일</a>
        <a href="https://example.com/assets/sample.xlsx">파일</a>
        <a href="https://example.com/assets/sample.doc">문서</a>
        <a href="https://example.com/assets/sample.xls">문서</a>
        <a href="https://example.com/assets/sample.ppt">문서</a>
        <a href="https://example.com/assets/sample.pptx">문서</a>
        <a href="https://example.com/assets/sample.zip">문서</a>
      </body>
    </html>
    """
    soup = BeautifulSoup(html, "html.parser")
    links = crawler.extract_links(soup, "https://example.com")

    att_urls = {a["url"] for a in links["attachments"]}
    internal_urls = {a["url"] for a in links["internal"]}

    for ext in ("pdf", "hwp", "hwpx", "docx", "xlsx"):
        assert f"https://example.com/assets/sample.{ext}" in att_urls
    assert len(links["attachments"]) == 5

    for ext in ("doc", "xls", "ppt", "pptx", "zip"):
        assert f"https://example.com/assets/sample.{ext}" in internal_urls
