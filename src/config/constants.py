"""Named config constants for 400-ai-finder.

These constants are meaning-separated on purpose. Each block below covers a
single, distinct profile/source concern, and they must NOT be consolidated
into shared umbrella symbols.

Issue #951 (parent #833): document-extension taxonomy constants.
  The three views of "document extensions" are intentionally distinct:

  1. ``PROFILE_DOCUMENT_EXTENSIONS`` — the profile-default document formats a
     site supports. Ordered (tuple) because some callers rely on a stable
     ordering, and it is broader than the crawler/classifier views (includes
     doc/xls/ppt/pptx/zip). 10 values.
  2. ``CRAWLER_ATTACHMENT_EXTENSIONS`` — extensions the crawler extracts as
     attachments. 5 values. Set-like behavior, so a frozenset.
  3. ``CLASSIFIER_DOCUMENT_EXTENSIONS`` — extensions the URL classifier treats
     as documents by extension alone (no keyword). 5 values. Frozenset.

  The 5-value crawler/classifier sets currently contain the same members, but
  their names and purposes are separate and must not be unified into one
  constant. The broader ``doc/xls/ppt/pptx/zip`` extensions are profile-only
  and must never enter the crawler/classifier views.

Issue #957 (parent #833): profile-default board/crawl patterns.
  These are SiteProfile-scoped profile defaults ONLY. They are kept apart from
  classifier labels, mapper keys, demo category lists, and demo crawl limits —
  no cross-semantic consolidation.

  * ``PROFILE_DEFAULT_BOARD_PATTERNS`` — ordered (tuple) profile board-pattern
    defaults. 6 values.
  * ``PROFILE_DEFAULT_CRAWL_RULES`` — profile crawl-rule defaults. A mapping
    copied by ``SiteProfile.crawl_rules`` so the public ``DEFAULT_CRAWL_RULES``
    stays a fresh dict per read.
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

# 4. Profile-default board-pattern defaults (ordered; 6). SiteProfile-scoped.
PROFILE_DEFAULT_BOARD_PATTERNS: tuple[str, ...] = (
    "board",
    "bbs",
    "list",
    "view",
    "article",
    "notice",
)

# 5. Profile-default crawl-rule defaults. SiteProfile-scoped mapping.
PROFILE_DEFAULT_CRAWL_RULES: dict[str, object] = {
    "max_depth": 3,
    "max_pages": 200,
    "include_documents": True,
    "respect_robots": True,
}
