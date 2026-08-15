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


# ======================================================================
# #1294: Stage-4 acquisition-scope containment (DocumentEnricher)
# Offline/deterministic: crawler.analyze is faked; no network/provider.
# ======================================================================

def _enricher_scope_policy(allowed):
    from src.site_profiles.site_profile import SiteAcquisitionPolicy, SiteProfile
    profile = SiteProfile({
        "site_id": "synthetic",
        "name": "Synthetic",
        "base_url": "https://%s/" % allowed[0],
        "allowed_domains": list(allowed),
    })
    return SiteAcquisitionPolicy(profile)


def _page_doc(url, doc_id="doc-x"):
    return {
        "id": doc_id,
        "url": url,
        "content_type": "page",
        "metadata": {},
    }


def test_enricher_external_record_url_zero_crawler_and_provider_calls(monkeypatch):
    mock_analyze = MagicMock(return_value={"status_code": 200, "errors": []})
    monkeypatch.setattr(URLCrawler, "analyze", mock_analyze)

    policy = _enricher_scope_policy(["bukgu.gwangju.kr"])
    enricher = DocumentEnricher(acquisition_policy=policy)
    docs = [_page_doc("https://evil.example/notice", "doc-000001")]

    res = enricher.enrich_records(docs)

    mock_analyze.assert_not_called()
    assert res[0]["metadata"]["fetch_status"] == "out_of_scope"
    assert "outside the active-site acquisition scope" in res[0]["metadata"]["fetch_error"]
    assert res[0].get("text") in (None, "")


def test_enricher_external_record_url_never_dispatches_network(monkeypatch):
    # Even if analyze were wired to a provider, the scope gate must prevent it.
    import urllib.request

    def _boom(*_a, **_k):
        raise RuntimeError("UNEXPECTED NETWORK CALL")

    monkeypatch.setattr(urllib.request, "urlopen", _boom)

    mock_analyze = MagicMock(return_value={"status_code": 200, "errors": []})
    monkeypatch.setattr(URLCrawler, "analyze", mock_analyze)

    policy = _enricher_scope_policy(["bukgu.gwangju.kr"])
    enricher = DocumentEnricher(acquisition_policy=policy)
    res = enricher.enrich_records([_page_doc("https://evil.example/page")])

    mock_analyze.assert_not_called()
    assert res[0]["metadata"]["fetch_status"] == "out_of_scope"


def test_enricher_allowed_record_url_fetches_offline_fake(monkeypatch):
    mock_analyze = MagicMock(return_value={
        "url": "https://bukgu.gwangju.kr/notice",
        "status_code": 200,
        "content_type": "text/html",
        "title": "Notice",
        "text": "content",
        "errors": [],
    })
    monkeypatch.setattr(URLCrawler, "analyze", mock_analyze)

    policy = _enricher_scope_policy(["bukgu.gwangju.kr"])
    enricher = DocumentEnricher(acquisition_policy=policy)
    res = enricher.enrich_records([_page_doc("https://bukgu.gwangju.kr/notice", "doc-000001")])

    mock_analyze.assert_called_once()
    assert res[0]["metadata"]["fetch_status"] == "fetched"
    assert res[0]["title"] == "Notice"


def test_enricher_allowed_requested_final_external_rejected(monkeypatch):
    # Requested URL is in-scope, but the observable final URL left the scope.
    mock_analyze = MagicMock(return_value={
        "url": "https://evil.example/final",
        "status_code": 200,
        "content_type": "text/html",
        "title": "Evil",
        "text": "external content",
        "errors": [],
    })
    monkeypatch.setattr(URLCrawler, "analyze", mock_analyze)

    policy = _enricher_scope_policy(["bukgu.gwangju.kr"])
    enricher = DocumentEnricher(acquisition_policy=policy)
    res = enricher.enrich_records([_page_doc("https://bukgu.gwangju.kr/notice", "doc-000001")])

    mock_analyze.assert_called_once()
    assert res[0]["metadata"]["fetch_status"] == "out_of_scope"
    assert "Effective fetch URL is outside" in res[0]["metadata"]["fetch_error"]
    # external content is never trusted as enrichment
    assert res[0].get("text") in (None, "")


def test_enricher_allowed_requested_same_final_ok(monkeypatch):
    mock_analyze = MagicMock(return_value={
        "url": "https://bukgu.gwangju.kr/notice",
        "status_code": 200,
        "errors": [],
        "text": "fine",
    })
    monkeypatch.setattr(URLCrawler, "analyze", mock_analyze)

    policy = _enricher_scope_policy(["bukgu.gwangju.kr"])
    enricher = DocumentEnricher(acquisition_policy=policy)
    res = enricher.enrich_records([_page_doc("https://bukgu.gwangju.kr/notice", "doc-000001")])

    assert res[0]["metadata"]["fetch_status"] == "fetched"


# ======================================================================
# #1294 V3: attachment containment regression
# ======================================================================


def test_attachment_out_of_scope_still_skipped_not_rejected():
    """Attachment content_type filter takes priority over acquisition scope:
    an out-of-scope attachment URL is skipped (not scope-rejected) because
    attachments are never dispatched to the crawler/provider."""
    policy = _enricher_scope_policy(["bukgu.gwangju.kr"])
    enricher = DocumentEnricher(acquisition_policy=policy)
    docs = [{
        "id": "doc-x",
        "url": "https://evil.example/files/doc.pdf",
        "content_type": "attachment",
        "metadata": {"file_type": "pdf"},
    }]
    res = enricher.enrich_records(docs)
    assert res[0]["metadata"]["fetch_status"] == "skipped"
    assert "attachment" in res[0]["metadata"]["fetch_error"].lower()


# ======================================================================
# #1294 V3: rejection observability
# ======================================================================


def test_enricher_pre_dispatch_rejection_http_status_and_content_type_empty():
    """Pre-dispatch out-of-scope rejection sets http_status and
    response_content_type to empty strings (no fetch was made)."""
    policy = _enricher_scope_policy(["bukgu.gwangju.kr"])
    enricher = DocumentEnricher(acquisition_policy=policy)
    res = enricher.enrich_records([_page_doc("https://evil.example/notice")])
    assert res[0]["metadata"]["fetch_status"] == "out_of_scope"
    assert res[0]["metadata"]["http_status"] == ""
    assert res[0]["metadata"]["response_content_type"] == ""
    assert res[0]["metadata"]["fetched_at"] == ""


def test_enricher_post_fetch_rejection_preserves_observed_http_and_content_type(monkeypatch):
    """Post-fetch out-of-scope rejection preserves the HTTP status and
    content type observed during the fetch in the metadata."""
    mock_analyze = MagicMock(return_value={
        "url": "https://evil.example/final",
        "status_code": 200,
        "content_type": "text/html",
        "title": "Evil",
        "errors": [],
    })
    monkeypatch.setattr(URLCrawler, "analyze", mock_analyze)

    policy = _enricher_scope_policy(["bukgu.gwangju.kr"])
    enricher = DocumentEnricher(acquisition_policy=policy)
    res = enricher.enrich_records([_page_doc("https://bukgu.gwangju.kr/start")])

    assert res[0]["metadata"]["fetch_status"] == "out_of_scope"
    assert "Effective fetch URL" in res[0]["metadata"]["fetch_error"]
    assert res[0]["metadata"]["http_status"] == 200
    assert res[0]["metadata"]["response_content_type"] == "text/html"
    assert res[0]["metadata"]["fetched_at"] == ""
