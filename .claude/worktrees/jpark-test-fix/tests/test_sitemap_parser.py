import pytest
from src.crawler.sitemap_parser import SitemapParser

def test_urlset_parsing():
    parser = SitemapParser()
    xml_content = """<?xml version="1.0" encoding="UTF-8"?>
    <urlset>
      <url>
        <loc>https://example.com/page1</loc>
        <lastmod>2026-05-01</lastmod>
        <changefreq>daily</changefreq>
        <priority>0.8</priority>
      </url>
      <url>
        <loc>https://example.com/page2</loc>
      </url>
    </urlset>
    """
    res = parser.parse(xml_content)
    assert res["error"] is None
    assert len(res["urls"]) == 2
    assert res["urls"][0]["url"] == "https://example.com/page1"
    assert res["urls"][0]["lastmod"] == "2026-05-01"
    assert res["urls"][0]["changefreq"] == "daily"
    assert res["urls"][0]["priority"] == "0.8"
    assert res["urls"][1]["url"] == "https://example.com/page2"
    assert res["urls"][1]["lastmod"] == ""

def test_sitemapindex_parsing():
    parser = SitemapParser()
    xml_content = """<?xml version="1.0" encoding="UTF-8"?>
    <sitemapindex>
      <sitemap>
        <loc>https://example.com/sitemap1.xml</loc>
        <lastmod>2026-05-01T12:00:00Z</lastmod>
      </sitemap>
      <sitemap>
        <loc>https://example.com/sitemap2.xml</loc>
      </sitemap>
    </sitemapindex>
    """
    res = parser.parse(xml_content)
    assert res["error"] is None
    assert len(res["sitemaps"]) == 2
    assert "https://example.com/sitemap1.xml" in res["sitemaps"]
    assert "https://example.com/sitemap2.xml" in res["sitemaps"]

def test_namespaced_sitemap_parsing():
    parser = SitemapParser()
    # XML with default namespace and xhtml namespace
    xml_content = """<?xml version="1.0" encoding="UTF-8"?>
    <urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9" xmlns:xhtml="http://www.w3.org/1999/xhtml">
      <url>
        <loc>https://example.com/page1</loc>
        <xhtml:link rel="alternate" hreflang="en" href="https://example.com/en/page1" />
        <lastmod>2026-05-01</lastmod>
      </url>
    </urlset>
    """
    res = parser.parse(xml_content)
    assert res["error"] is None
    assert len(res["urls"]) == 1
    assert res["urls"][0]["url"] == "https://example.com/page1"
    assert res["urls"][0]["lastmod"] == "2026-05-01"

def test_invalid_xml_handling():
    parser = SitemapParser()
    # Malformed XML
    xml_content = "This is not XML <urlset><url><loc>hello"
    res = parser.parse(xml_content)
    assert res["error"] is not None
    assert len(res["urls"]) == 0
    assert len(res["sitemaps"]) == 0

    # Empty XML
    res_empty = parser.parse("")
    assert res_empty["error"] == "Empty XML content"
