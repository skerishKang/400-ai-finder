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
