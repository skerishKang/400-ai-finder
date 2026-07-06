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
