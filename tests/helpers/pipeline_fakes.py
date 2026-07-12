"""Shared pipeline test fixtures (test-only helper data).

These fake return values are imported by several pipeline test modules
(``test_pipeline_runner``, ``test_municipal_crawl_filters_config_contract``,
``test_pipeline_observability``, ...). They are intentionally kept in an
explicit repository-local helper module rather than inside a ``test_*.py``
module so that test files import a clear helper boundary (never another
test module) and so the import resolves to this repository even when a
third-party top-level ``tests`` package is installed.
"""

FAKE_HOMEPAGE_MAP = {
    "start_url": "https://example.com",
    "base_url": "https://example.com",
    "sitemap": {"candidates": [], "found": [], "url_count": 0, "urls": [], "errors": []},
    "homepage": {
        "title": "Example",
        "description": "Example site",
        "navigation_links": [
            {"text": "신청 안내", "url": "https://example.com/apply", "category": "apply"},
        ],
        "attachment_links": [],
        "errors": [],
    },
    "categories": {
        "menu": [], "notice": [], "board": [], "document": [],
        "apply": ["https://example.com/apply"], "contact": [], "unknown": [],
    },
    "stats": {
        "sitemap_url_count": 0, "navigation_link_count": 1, "attachment_count": 0,
        "category_counts": {
            "menu": 0, "notice": 0, "board": 0, "document": 0,
            "apply": 1, "contact": 0, "unknown": 0,
        },
    },
    "errors": [],
}

FAKE_DOCS = [
    {
        "id": "doc-000001",
        "url": "https://example.com/apply",
        "canonical_url": "https://example.com/apply",
        "title": "신청 안내",
        "category": "apply",
        "source_types": ["navigation"],
        "content_type": "page",
        "text": "",
        "summary": "",
        "metadata": {
            "base_url": "https://example.com",
            "lastmod": "", "changefreq": "", "priority": "",
            "link_texts": ["신청 안내"],
            "file_type": "",
            "discovered_from": ["navigation"],
        },
    },
]

FAKE_ENRICHED_DOCS = [
    {
        **FAKE_DOCS[0],
        "text": "중소기업 지원사업 신청 방법 안내",
        "metadata": {
            **FAKE_DOCS[0]["metadata"],
            "fetched_at": "2026-05-29T12:00:00Z",
            "http_status": 200,
            "response_content_type": "text/html",
            "fetch_status": "fetched",
            "fetch_error": "",
            "description": "지원사업 신청 안내",
        },
    },
]

FAKE_SEARCH_RESULTS = [
    {
        "rank": 1,
        "id": "doc-000001",
        "title": "신청 안내",
        "url": "https://example.com/apply",
        "canonical_url": "https://example.com/apply",
        "category": "apply",
        "content_type": "page",
        "score": 10.0,
        "matched_terms": ["신청"],
        "matched_fields": ["title"],
        "snippet": "중소기업 지원사업 신청 방법 안내",
        "metadata": {
            "source_types": ["navigation"],
            "fetch_status": "fetched",
            "description": "지원사업 신청 안내",
        },
    },
]

FAKE_ANSWER_RESULT = {
    "query": "신청서 제출서류",
    "provider": "mock",
    "model": "mock-model",
    "ok": True,
    "answer_markdown": "## 답변\n\n신청 안내 페이지를 확인하세요.\n\n## 관련 자료\n\n- [신청 안내](https://example.com/apply)\n\n## 다음에 할 일\n\n1. 안내 페이지 확인\n\n## 확인 필요 사항\n\n없음",
    "sources": [
        {
            "rank": 1,
            "id": "doc-000001",
            "title": "신청 안내",
            "url": "https://example.com/apply",
            "category": "apply",
            "content_type": "page",
            "score": 10.0,
            "matched_terms": ["신청"],
            "matched_fields": ["title"],
            "snippet": "중소기업 지원사업 신청 방법 안내",
            "description": "지원사업 신청 안내",
            "fetch_status": "fetched",
            "source_types": ["navigation"],
        }
    ],
    "warnings": [],
    "error": "",
}

__all__ = [
    "FAKE_HOMEPAGE_MAP",
    "FAKE_DOCS",
    "FAKE_ENRICHED_DOCS",
    "FAKE_SEARCH_RESULTS",
    "FAKE_ANSWER_RESULT",
]
