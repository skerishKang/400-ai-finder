import pytest
import json
import re
from unittest.mock import MagicMock
from src.indexer.document_enricher import DocumentEnricher
from src.crawler.url_crawler import URLCrawler

def test_page_fetch_success(monkeypatch):
    mock_analyze = MagicMock(return_value={
        "status_code": 200,
        "content_type": "text/html",
        "title": "Fetched Title",
        "description": "Fetched Meta Description",
        "text": "Fetched main content",
        "errors": []
    })
    monkeypatch.setattr(URLCrawler, "analyze", mock_analyze)

    enricher = DocumentEnricher()
    docs = [{
        "id": "doc-000001",
        "url": "https://example.com/notice",
        "canonical_url": "https://example.com/notice",
        "title": "공지사항",
        "category": "notice",
        "content_type": "page",
        "text": "",
        "summary": "",
        "metadata": {
            "base_url": "https://example.com",
            "link_texts": ["공지사항"]
        }
    }]

    res = enricher.enrich_records(docs)
    assert len(res) == 1
    doc = res[0]
    
    assert doc["title"] == "Fetched Title"
    assert doc["text"] == "Fetched main content"
    assert doc["metadata"]["description"] == "Fetched Meta Description"
    assert doc["metadata"]["fetch_status"] == "fetched"
    assert doc["metadata"]["http_status"] == 200
    assert doc["metadata"]["response_content_type"] == "text/html"
    assert doc["metadata"]["fetch_error"] == ""
    assert doc["metadata"]["base_url"] == "https://example.com"
    assert doc["metadata"]["link_texts"] == ["공지사항"]
    
    assert "fetched_at" in doc["metadata"]
    fetched_at = doc["metadata"]["fetched_at"]
    assert re.match(r'^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$', fetched_at)

def test_page_fetch_error(monkeypatch):
    mock_analyze = MagicMock(return_value={
        "status_code": 404,
        "content_type": "text/html",
        "title": "",
        "description": "",
        "text": "",
        "errors": ["HTTP Error: Status code 404", "Request timeout"]
    })
    monkeypatch.setattr(URLCrawler, "analyze", mock_analyze)

    enricher = DocumentEnricher()
    docs = [
        {
            "id": "doc-000001",
            "url": "https://example.com/notfound",
            "content_type": "page",
            "metadata": {}
        },
        {
            "id": "doc-000002",
            "url": "https://example.com/ok",
            "content_type": "page",
            "metadata": {}
        }
    ]

    res = enricher.enrich_records(docs)
    assert len(res) == 2
    assert res[0]["metadata"]["fetch_status"] == "error"
    assert "HTTP Error: Status code 404" in res[0]["metadata"]["fetch_error"]
    assert "Request timeout" in res[0]["metadata"]["fetch_error"]
    assert res[1]["metadata"]["fetch_status"] == "error"

def test_attachment_skipped():
    enricher = DocumentEnricher()
    docs = [{
        "id": "doc-000002",
        "url": "https://example.com/files/form.pdf",
        "canonical_url": "https://example.com/files/form.pdf",
        "title": "신청서",
        "category": "document",
        "content_type": "attachment",
        "text": "",
        "summary": "",
        "metadata": {
            "base_url": "https://example.com",
            "link_texts": ["신청서"],
            "file_type": "pdf"
        }
    }]
    
    res = enricher.enrich_records(docs)
    assert len(res) == 1
    doc = res[0]
    
    assert doc["metadata"]["fetch_status"] == "skipped"
    assert "attachment fetching is not implemented" in doc["metadata"]["fetch_error"]
    assert doc["metadata"]["file_type"] == "pdf"
    assert doc["metadata"]["link_texts"] == ["신청서"]
    assert doc["metadata"]["fetched_at"] == ""

def test_unknown_content_type_skipped():
    enricher = DocumentEnricher()
    docs = [{
        "id": "doc-000003",
        "url": "https://example.com/unknown",
        "content_type": "video",
        "metadata": {}
    }]
    
    res = enricher.enrich_records(docs)
    assert len(res) == 1
    assert res[0]["metadata"]["fetch_status"] == "skipped"
    assert "unsupported content_type" in res[0]["metadata"]["fetch_error"]

def test_order_preservation(monkeypatch):
    mock_analyze = MagicMock(return_value={
        "status_code": 200,
        "errors": []
    })
    monkeypatch.setattr(URLCrawler, "analyze", mock_analyze)
    
    enricher = DocumentEnricher()
    docs = [
        {"id": "doc-000001", "url": "https://example.com/1", "content_type": "page", "metadata": {}},
        {"id": "doc-000002", "url": "https://example.com/2", "content_type": "page", "metadata": {}},
        {"id": "doc-000003", "url": "https://example.com/3", "content_type": "page", "metadata": {}}
    ]
    
    res = enricher.enrich_records(docs)
    assert len(res) == 3
    assert [d["id"] for d in res] == ["doc-000001", "doc-000002", "doc-000003"]

def test_limit_processing(monkeypatch):
    mock_analyze = MagicMock(return_value={
        "status_code": 200,
        "errors": []
    })
    monkeypatch.setattr(URLCrawler, "analyze", mock_analyze)

    enricher = DocumentEnricher()
    docs = [
        {"id": "doc-000001", "url": "https://example.com/1", "content_type": "page", "metadata": {}},
        {"id": "doc-000002", "url": "https://example.com/file.pdf", "content_type": "attachment", "metadata": {}},
        {"id": "doc-000003", "url": "https://example.com/3", "content_type": "page", "metadata": {}},
        {"id": "doc-000004", "url": "https://example.com/4", "content_type": "page", "metadata": {}}
    ]
    
    res = enricher.enrich_records(docs, limit=1)
    assert len(res) == 4
    
    assert res[0]["metadata"]["fetch_status"] == "fetched"
    assert res[1]["metadata"]["fetch_status"] == "skipped"
    assert res[2]["metadata"]["fetch_status"] == "not_processed"
    assert res[3]["metadata"]["fetch_status"] == "not_processed"
