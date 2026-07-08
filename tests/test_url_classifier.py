import pytest
from src.crawler.url_classifier import classify_url, CATEGORY_PRIORITY
from src.crawler.homepage_mapper import classify_url as legacy_classify_url
from src.indexer.document_indexer import CATEGORY_PRIORITY as legacy_category_priority

def test_url_classifier_re_exports():
    """Verify legacy re-exports preserve reference identity."""
    assert legacy_classify_url is classify_url
    assert legacy_category_priority is CATEGORY_PRIORITY

def test_category_priority_values():
    """Verify CATEGORY_PRIORITY mappings and exact keys are locked."""
    expected = {
        "document": 7,
        "apply": 6,
        "notice": 5,
        "board": 4,
        "contact": 3,
        "menu": 2,
        "unknown": 1,
    }
    assert CATEGORY_PRIORITY == expected

@pytest.mark.parametrize(
    "url,text,is_navigation,expected",
    [
        ("https://example.com/file.pdf", "", False, "document"),
        ("https://example.com/apply-form", "", False, "apply"),
        ("https://example.com/notice-list", "", False, "notice"),
        ("https://example.com/bbs/list", "", False, "board"),
        ("https://example.com/contact-us", "", False, "contact"),
        ("https://example.com/parking-info", "", False, "location"),
        ("https://example.com/home", "", True, "menu"),
        ("https://example.com/home", "", False, "unknown"),
    ]
)
def test_classify_url_cases(url, text, is_navigation, expected):
    """Verify classification matches the specified criteria."""
    assert classify_url(url, text=text, is_navigation=is_navigation) == expected

def test_classify_url_precedence():
    """Verify evaluation order / precedence works as locked."""
    # document > apply
    assert classify_url("https://example.com/file.pdf", text="신청") == "document"
    # apply > notice
    assert classify_url("https://example.com/apply", text="공지") == "apply"
    # notice > board
    assert classify_url("https://example.com/notice", text="게시판") == "notice"
    # board > contact
    assert classify_url("https://example.com/board", text="문의") == "board"
    # contact > location
    assert classify_url("https://example.com/contact", text="청사") == "contact"
    # location > menu (navigation flag)
    assert classify_url("https://example.com/parking", text="", is_navigation=True) == "location"


# ------------------------------------------------------------------
# #949: Lock the classifier document-extension taxonomy.
# The classifier's extension-only document set is exactly 5 values; doc/xls/
# ppt/pptx/zip are profile-default documents but NOT extension-only documents
# in the classifier. Keyword-driven matches are covered separately so the two
# mechanisms are never conflated. URLs here avoid document keywords entirely.
# ------------------------------------------------------------------
@pytest.mark.parametrize(
    "url",
    [
        "https://example.com/assets/sample.pdf",
        "https://example.com/assets/sample.hwp",
        "https://example.com/assets/sample.hwpx",
        "https://example.com/assets/sample.docx",
        "https://example.com/assets/sample.xlsx",
    ],
)
def test_classify_url_extension_only_document(url):
    """#949 / no network. The 5 classifier document extensions classify by
    extension alone (no document keyword in the URL or text)."""
    assert classify_url(url, text="") == "document"


@pytest.mark.parametrize(
    "url",
    [
        "https://example.com/assets/sample.doc",
        "https://example.com/assets/sample.xls",
        "https://example.com/assets/sample.ppt",
        "https://example.com/assets/sample.pptx",
        "https://example.com/assets/sample.zip",
    ],
)
def test_classify_url_extension_only_broad_profile_only(url):
    """#949 / no network. These are profile-default documents but NOT
    classifier extension-only documents — by extension alone they must NOT be
    classified as "document"."""
    assert classify_url(url, text="") != "document"


def test_classify_url_keyword_driven_document():
    """#949 / no network. Keyword-driven document classification is distinct
    from extension classification. Uses a real document keyword but no document
    extension, and must still classify as document."""
    assert classify_url("https://example.com/section/page-1", text="첨부파일 안내") == "document"
    assert classify_url("https://example.com/section/page-2", text="신청서식 다운로드") == "document"
