"""Named document-extension taxonomy constants for 400-ai-finder.

Issue #951 (parent #833): extract the document-extension taxonomy into
meaning-separated named constants *without* collapsing them into a single
umbrella set. The three views of "document extensions" are intentionally
distinct:

1. ``PROFILE_DOCUMENT_EXTENSIONS`` — the profile-default document formats a site
   supports. Ordered (tuple) because some callers rely on stable ordering, and
   it is broader than the crawler/classifier views (includes doc/xls/ppt/pptx/
   zip). 10 values.
2. ``CRAWLER_ATTACHMENT_EXTENSIONS`` — extensions the crawler extracts as
   attachments. 5 values. Set-like behavior, so a frozenset.
3. ``CLASSIFIER_DOCUMENT_EXTENSIONS`` — extensions the URL classifier treats as
   documents by extension alone (no keyword). 5 values. Frozenset for the same
   reason.

The 5-value crawler/classifier sets currently contain the same members, but
their names and purposes are separate and must not be unified into one
constant. The broader ``doc/xls/ppt/pptx/zip`` extensions are profile-only and
must never enter the crawler/classifier views.
"""

from __future__ import annotations

# 1. Profile-supported document formats (ordered; broader set of 10).
PROFILE_DOCUMENT_EXTENSIONS: tuple[str, ...] = (
    "pdf",
    "hwp",
    "hwpx",
    "doc",
    "docx",
    "xls",
    "xlsx",
    "ppt",
    "pptx",
    "zip",
)

# 2. Crawler attachment-extraction formats (5).
CRAWLER_ATTACHMENT_EXTENSIONS: frozenset[str] = frozenset({
    "pdf",
    "hwp",
    "hwpx",
    "docx",
    "xlsx",
})

# 3. Classifier extension-only document formats (5).
CLASSIFIER_DOCUMENT_EXTENSIONS: frozenset[str] = frozenset({
    "pdf",
    "hwp",
    "hwpx",
    "docx",
    "xlsx",
})
