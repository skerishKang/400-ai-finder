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
    # Priority order: document > apply > notice > board > contact > menu > unknown
    
    # 1. Document
    assert classify_url("https://example.com/downloads/report.pdf", "My Report") == "document"
    assert classify_url("https://example.com/file-show", "양식 다운로드") == "document"
    
    # 2. Apply
    assert classify_url("https://example.com/register", "Join Us") == "apply"
    assert classify_url("https://example.com/program", "신청서 작성") == "apply"
    
    # 3. Notice
    assert classify_url("https://example.com/announcements", "News") == "notice"
    assert classify_url("https://example.com/notice-list", "새로운 알림") == "notice"
    
    # 4. Board
    assert classify_url("https://example.com/bbs/free-board", "Talk") == "board"
    assert classify_url("https://example.com/article/1", "게시물") == "board"
    
    # 5. Contact
    assert classify_url("https://example.com/support", "Get Help") == "contact"
    assert classify_url("https://example.com/contact-us", "고객 상담") == "contact"
    
    # 6. Menu (is_navigation=True)
    assert classify_url("https://example.com/about-us", "회사소개", is_navigation=True) == "menu"
    
    # 7. Unknown
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
