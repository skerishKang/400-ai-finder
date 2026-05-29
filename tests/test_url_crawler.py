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
