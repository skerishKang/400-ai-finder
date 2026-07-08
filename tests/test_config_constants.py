"""Lock the named document-extension taxonomy constants (#951).

These constants are meaning-separated (issue parent #833) — they must NOT be
collapsed into a single umbrella set. The three views are distinct:

  * PROFILE_DOCUMENT_EXTENSIONS      -> 10 ordered values (broad)
  * CRAWLER_ATTACHMENT_EXTENSIONS    -> 5 frozenset values
  * CLASSIFIER_DOCUMENT_EXTENSIONS   -> 5 frozenset values

#950 already pinned the resulting observable behavior in tests/test_site_profile,
tests/test_url_classifier, tests/test_url_crawler, tests/test_homepage_mapper.
This module locks the constants themselves and the deliberate asymmetry.

No network / no provider / no crawl — pure constant assertions.
"""

from __future__ import annotations

from src.config.constants import (
    PROFILE_DOCUMENT_EXTENSIONS,
    CRAWLER_ATTACHMENT_EXTENSIONS,
    CLASSIFIER_DOCUMENT_EXTENSIONS,
)

EXPECTED_PROFILE_ORDER = (
    "pdf", "hwp", "hwpx", "doc", "docx",
    "xls", "xlsx", "ppt", "pptx", "zip",
)

EXPECTED_NARROW = frozenset({"pdf", "hwp", "hwpx", "docx", "xlsx"})

# Profile-only formats that must NOT be in the crawler/classifier views.
BROAD_ONLY = {"doc", "xls", "ppt", "pptx", "zip"}


def test_profile_document_extensions_ordered_tuple():
    """Profile view is an ordered 10-value tuple."""
    assert isinstance(PROFILE_DOCUMENT_EXTENSIONS, tuple)
    assert PROFILE_DOCUMENT_EXTENSIONS == EXPECTED_PROFILE_ORDER
    # List equivalence preserves the locked #950 ordering contract.
    assert list(PROFILE_DOCUMENT_EXTENSIONS) == [
        "pdf", "hwp", "hwpx", "doc", "docx",
        "xls", "xlsx", "ppt", "pptx", "zip",
    ]


def test_crawler_attachment_extensions_frozenset():
    """Crawler attachment view is exactly the 5 narrow extensions."""
    assert isinstance(CRAWLER_ATTACHMENT_EXTENSIONS, frozenset)
    assert CRAWLER_ATTACHMENT_EXTENSIONS == EXPECTED_NARROW
    assert len(CRAWLER_ATTACHMENT_EXTENSIONS) == 5


def test_classifier_document_extensions_frozenset():
    """Classifier extension-only view is exactly the 5 narrow extensions."""
    assert isinstance(CLASSIFIER_DOCUMENT_EXTENSIONS, frozenset)
    assert CLASSIFIER_DOCUMENT_EXTENSIONS == EXPECTED_NARROW
    assert len(CLASSIFIER_DOCUMENT_EXTENSIONS) == 5


def test_broad_only_in_profile_but_not_narrow_views():
    """The broad-only formats are profile documents but excluded from the
    crawler/classifier extension views (asymmetric taxonomy)."""
    profile_set = set(PROFILE_DOCUMENT_EXTENSIONS)
    assert BROAD_ONLY.issubset(profile_set)
    assert BROAD_ONLY.isdisjoint(CRAWLER_ATTACHMENT_EXTENSIONS)
    assert BROAD_ONLY.isdisjoint(CLASSIFIER_DOCUMENT_EXTENSIONS)


def test_narrow_views_equal_values_but_distinct_names():
    """#951: the crawler and classifier sets currently hold the same members,
    but they are SEPARATE constants by name and purpose. They must not be
    unified into one symbol. This test documents that intent: equality of
    values is allowed today, but the two names stay distinct.
    """
    assert CRAWLER_ATTACHMENT_EXTENSIONS == CLASSIFIER_DOCUMENT_EXTENSIONS
    # Names/symbols remain distinct identities (not the same object alias).
    assert CRAWLER_ATTACHMENT_EXTENSIONS is not CLASSIFIER_DOCUMENT_EXTENSIONS
