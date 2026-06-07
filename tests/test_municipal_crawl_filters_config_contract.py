import pytest
from unittest.mock import patch
from bs4 import BeautifulSoup
from src.site_profiles.site_profile import SiteProfile
from src.crawler.url_crawler import URLCrawler
from src.crawler.homepage_mapper import HomepageMapper
from src.pipeline.pipeline_runner import PipelineRunner
from tests.test_pipeline_runner import (
    FAKE_HOMEPAGE_MAP,
    FAKE_DOCS,
    FAKE_ENRICHED_DOCS,
    FAKE_SEARCH_RESULTS,
    FAKE_ANSWER_RESULT
)

# Define the candidate config matching Stage 392 guidelines
CANDIDATE_CONFIG = {
    "site_id": "candidate_test",
    "name": "Candidate Test",
    "base_url": "https://candidate.gwangju.kr/",
    "crawl_filters": {
        "allow_patterns": [],
        "deny_patterns": [
            "print=",
            "utm_",
            "utm_source=",
            "utm_medium=",
            "utm_campaign="
        ],
        "protected_patterns": [
            "mid=",
            "menuId=",
            "board.es",
            "seq=",
            "contentId=",
            "articleId="
        ]
    }
}


def test_synthetic_candidate_config_fixture():
    """1. Verify that SiteProfile correctly parses and sanitizes the candidate config fixture."""
    profile = SiteProfile(CANDIDATE_CONFIG)
    filters = profile.crawl_filters
    
    assert filters["allow_patterns"] == []
    assert "print=" in filters["deny_patterns"]
    assert "utm_" in filters["deny_patterns"]
    assert "mid=" in filters["protected_patterns"]
    assert "board.es" in filters["protected_patterns"]


def test_protected_municipal_url_preservation():
    """2. Verify that protected municipal URLs survive under candidate filters."""
    profile = SiteProfile(CANDIDATE_CONFIG)
    crawler = URLCrawler(crawl_filters=profile.crawl_filters)
    
    base_url = "https://candidate.gwangju.kr/"
    html = """
    <html>
      <body>
        <a href="/menu.es?mid=a101">Menu ES mid</a>
        <a href="/some/path?menuId=a101">Menu ID</a>
        <a href="/board.es?seq=999">Board ES seq</a>
        <a href="/content?contentId=123">Content ID</a>
        <a href="/article?articleId=777">Article ID</a>
      </body>
    </html>
    """
    soup = BeautifulSoup(html, 'html.parser')
    links = crawler.extract_links(soup, base_url)
    
    urls = [link["url"] for link in links["internal"]]
    
    # All 5 protected / structural URLs must survive
    assert "https://candidate.gwangju.kr/menu.es?mid=a101" in urls
    assert "https://candidate.gwangju.kr/some/path?menuId=a101" in urls
    assert "https://candidate.gwangju.kr/board.es?seq=999" in urls
    assert "https://candidate.gwangju.kr/content?contentId=123" in urls
    assert "https://candidate.gwangju.kr/article?articleId=777" in urls
    assert len(urls) == 5


def test_deny_duplicate_tracking():
    """3. Verify that duplicate/tracking URLs are denied by candidate filters."""
    profile = SiteProfile(CANDIDATE_CONFIG)
    crawler = URLCrawler(crawl_filters=profile.crawl_filters)
    
    base_url = "https://candidate.gwangju.kr/"
    html = """
    <html>
      <body>
        <a href="/page?print=1">Print Page</a>
        <a href="/page?utm_source=test">UTM Source</a>
        <a href="/page?utm_medium=email">UTM Medium</a>
        <a href="/page?utm_campaign=spring">UTM Campaign</a>
        <a href="/page?utm_content=abc">UTM Content</a>
        <a href="/normal-page">Normal Page</a>
      </body>
    </html>
    """
    soup = BeautifulSoup(html, 'html.parser')
    links = crawler.extract_links(soup, base_url)
    
    urls = [link["url"] for link in links["internal"]]
    
    # Only normal page should survive
    assert urls == ["https://candidate.gwangju.kr/normal-page"]


def test_pagination_deferred():
    """4. Verify that pagination parameters (pageNo, currentPage) are deferred and survive."""
    profile = SiteProfile(CANDIDATE_CONFIG)
    crawler = URLCrawler(crawl_filters=profile.crawl_filters)
    
    base_url = "https://candidate.gwangju.kr/"
    html = """
    <html>
      <body>
        <a href="/board.es?pageNo=2">Page No 2</a>
        <a href="/board.es?currentPage=3">Current Page 3</a>
      </body>
    </html>
    """
    soup = BeautifulSoup(html, 'html.parser')
    links = crawler.extract_links(soup, base_url)
    
    urls = [link["url"] for link in links["internal"]]
    
    # pageNo and currentPage should survive because they are deferred (not in deny_patterns)
    assert "https://candidate.gwangju.kr/board.es?pageNo=2" in urls
    assert "https://candidate.gwangju.kr/board.es?currentPage=3" in urls
    assert len(urls) == 2


def test_forbidden_deny_rule_guard():
    """5. Verify that critical parameters are forbidden in deny_patterns."""
    profile = SiteProfile(CANDIDATE_CONFIG)
    deny_patterns = profile.crawl_filters.get("deny_patterns", [])
    
    forbidden = ["board.es", "mid=", "menuId=", "seq=", "contentId=", "articleId="]
    for pattern in forbidden:
        assert pattern not in deny_patterns, f"Pattern {pattern} is strictly forbidden in deny_patterns"


@patch("src.pipeline.pipeline_runner.AnswerComposer")
@patch("src.pipeline.pipeline_runner.KeywordSearcher")
@patch("src.pipeline.pipeline_runner.DocumentEnricher")
@patch("src.pipeline.pipeline_runner.DocumentIndexer")
@patch("src.pipeline.pipeline_runner.HomepageMapper")
@patch("src.site_profiles.site_profile.SiteProfileLoader")
def test_pipeline_synthetic_profile_fixture(
    MockLoader, MockMapper, MockIndexer, MockEnricher, MockSearcher, MockComposer, tmpdir
):
    """6. Verify synthetic candidate filters are successfully passed to HomepageMapper in pipeline runner."""
    from src.site_profiles.site_profile import SiteProfile
    
    profile = SiteProfile(CANDIDATE_CONFIG)
    MockLoader.return_value.list_ids.return_value = ["candidate_test"]
    MockLoader.return_value.load_by_id.return_value = profile
    
    MockMapper.return_value.build_map.return_value = FAKE_HOMEPAGE_MAP
    MockIndexer.return_value.build_index.return_value = FAKE_DOCS
    MockEnricher.return_value.enrich_records.return_value = FAKE_ENRICHED_DOCS
    MockSearcher.return_value.search.return_value = FAKE_SEARCH_RESULTS
    MockComposer.return_value.compose.return_value = FAKE_ANSWER_RESULT
    
    runner = PipelineRunner(output_dir=str(tmpdir), provider="mock")
    result = runner.run(url="https://candidate.gwangju.kr/", query="test")
    
    # Verify mapping propagation
    MockMapper.assert_called_once()
    call_kwargs = MockMapper.call_args
    assert call_kwargs.kwargs.get("crawl_filters") == profile.crawl_filters
    assert result["ok"] is True
