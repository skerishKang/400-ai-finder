import pytest
import json
from src.indexer.document_indexer import make_canonical_url, DocumentIndexer

def test_canonical_url_generation():
    assert make_canonical_url("HTTPS://Example.com/Path/") == "https://example.com/Path"
    assert make_canonical_url("http://example.com/") == "http://example.com/"  # root slash preserved
    assert make_canonical_url("https://example.com/path#fragment") == "https://example.com/path"
    assert make_canonical_url("https://example.com/search?q=query") == "https://example.com/search?q=query"
    assert make_canonical_url("") == ""

def test_sitemap_navigation_merge():
    indexer = DocumentIndexer()
    homepage_map = {
        "base_url": "https://example.com",
        "sitemap": {
            "urls": [
                {
                    "url": "https://example.com/notice/",
                    "lastmod": "2026-01-01",
                    "category": "notice"
                }
            ]
        },
        "homepage": {
            "navigation_links": [
                {
                    "text": "공지사항",
                    "url": "https://example.com/notice",
                    "category": "menu"
                }
            ]
        }
    }
    
    docs = indexer.build_index(homepage_map)
    assert len(docs) == 1
    doc = docs[0]
    assert doc["canonical_url"] == "https://example.com/notice"
    assert doc["source_types"] == ["navigation", "sitemap"]
    assert doc["metadata"]["discovered_from"] == ["navigation", "sitemap"]
    assert doc["metadata"]["lastmod"] == "2026-01-01"
    assert doc["category"] == "notice"
    assert doc["title"] == "공지사항"

def test_attachment_record_generation():
    indexer = DocumentIndexer()
    homepage_map = {
        "base_url": "https://example.com",
        "homepage": {
            "attachment_links": [
                {
                    "text": "신청 양식",
                    "url": "https://example.com/files/form.pdf",
                    "type": "pdf"
                }
            ]
        }
    }
    
    docs = indexer.build_index(homepage_map)
    assert len(docs) == 1
    doc = docs[0]
    assert doc["content_type"] == "attachment"
    assert doc["category"] == "document"
    assert doc["metadata"]["file_type"] == "pdf"
    assert doc["title"] == "신청 양식"

def test_title_priority_logic():
    indexer = DocumentIndexer()
    # 1. path segment only
    map_1 = {
        "sitemap": {"urls": [{"url": "https://example.com/page-name"}]}
    }
    assert indexer.build_index(map_1)[0]["title"] == "page-name"

    # 2. attachment text > path segment
    map_2 = {
        "homepage": {
            "attachment_links": [{"text": "Att Text", "url": "https://example.com/form.pdf", "type": "pdf"}]
        }
    }
    assert indexer.build_index(map_2)[0]["title"] == "Att Text"

    # 3. navigation text > attachment text
    map_3 = {
        "homepage": {
            "navigation_links": [{"text": "Nav Text", "url": "https://example.com/form.pdf"}],
            "attachment_links": [{"text": "Att Text", "url": "https://example.com/form.pdf", "type": "pdf"}]
        }
    }
    assert indexer.build_index(map_3)[0]["title"] == "Nav Text"

def test_category_priority_logic():
    indexer = DocumentIndexer()
    map_data = {
        "sitemap": {
            "urls": [
                {"url": "https://example.com/apply-notice", "category": "notice"},
                {"url": "https://example.com/apply-notice", "category": "apply"}
            ]
        }
    }
    docs = indexer.build_index(map_data)
    assert docs[0]["category"] == "apply"

def test_deterministic_id_and_sorting():
    indexer = DocumentIndexer()
    homepage_map = {
        "sitemap": {
            "urls": [
                {"url": "https://example.com/zebra"},
                {"url": "https://example.com/apple"}
            ]
        }
    }
    
    docs = indexer.build_index(homepage_map)
    assert len(docs) == 2
    assert docs[0]["canonical_url"] == "https://example.com/apple"
    assert docs[0]["id"] == "doc-000001"
    
    assert docs[1]["canonical_url"] == "https://example.com/zebra"
    assert docs[1]["id"] == "doc-000002"
