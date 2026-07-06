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
