"""HTML/content extraction for narrowly scoped official civic facts.

Stdlib HTML parser only. Fail-closed: missing, ambiguous, placeholder, or
wrong page identity never invents a civic fact.

Phase-1 truthfulness:

* ``data-official-fact`` markers are deterministic mock-fixture scaffolding
* the current branch does not prove parsing against the live official mayor page
* no live official-page validation was executed
* live official DOM parsing is not yet verified
* actual official DOM selectors/extraction require a separately approved
  validation/integration phase
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from html.parser import HTMLParser

from .models import EXTRACTOR_ID, FactKind
from .normalize import normalize_fact_value, normalize_whitespace


class ExtractionError(Exception):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


class MalformedHtmlError(ExtractionError):
    def __init__(self, message: str = "malformed HTML") -> None:
        super().__init__("malformed_content", message)


class FactAbsentError(ExtractionError):
    def __init__(self, message: str = "expected fact absent") -> None:
        super().__init__("fact_not_found", message)


class AmbiguousValueError(ExtractionError):
    def __init__(self, message: str = "ambiguous multiple values") -> None:
        super().__init__("ambiguous_fact", message)


class SourceIdentityMismatchError(ExtractionError):
    def __init__(self, message: str = "source identity mismatch") -> None:
        super().__init__("source_identity_mismatch", message)


@dataclass(frozen=True)
class ExtractionResult:
    kind: FactKind
    raw_values: tuple[str, ...]
    title: str
    extractor_id: str = EXTRACTOR_ID


class _OfficialFactParser(HTMLParser):
    """Collect text for ``data-official-fact`` markers and title."""

    def __init__(self, marker: str) -> None:
        super().__init__(convert_charrefs=True)
        self.marker = marker
        self.title_parts: list[str] = []
        self.captured: list[str] = []
        self._capture_depth = 0
        self._buffer: list[str] = []
        self._in_title = False
        self._title_buf: list[str] = []
        self.parse_error: str | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        tag_l = tag.lower()
        attr_map = {k.lower(): (v or "") for k, v in attrs}
        if tag_l == "title":
            self._in_title = True
            self._title_buf = []
        if tag_l == "meta":
            prop = attr_map.get("property", "") or attr_map.get("name", "")
            content = attr_map.get("content", "")
            if self.marker == "jurisdiction_name" and prop in {
                "og:site_name",
                "application-name",
            }:
                if content.strip():
                    self.captured.append(content.strip())
        if attr_map.get("data-official-fact") == self.marker:
            self._capture_depth += 1
            if self._capture_depth == 1:
                self._buffer = []

    def handle_endtag(self, tag: str) -> None:
        tag_l = tag.lower()
        if tag_l == "title" and self._in_title:
            self._in_title = False
            self.title_parts.append("".join(self._title_buf))
        if self._capture_depth > 0 and tag_l in {
            "span",
            "p",
            "div",
            "strong",
            "em",
            "h1",
            "h2",
            "h3",
            "td",
            "li",
            "a",
        }:
            self._capture_depth -= 1
            if self._capture_depth == 0 and self._buffer:
                text = normalize_whitespace("".join(self._buffer))
                if text:
                    self.captured.append(text)
                self._buffer = []

    def handle_data(self, data: str) -> None:
        if self._in_title:
            self._title_buf.append(data)
        if self._capture_depth > 0:
            self._buffer.append(data)

    def error(self, message: str) -> None:  # pragma: no cover
        self.parse_error = message


_UNBALANCED_TAG_RE = re.compile(r"<[^>]*$")


def _assert_minimally_well_formed(html: str) -> None:
    if not isinstance(html, str) or not html.strip():
        raise MalformedHtmlError("empty HTML document")
    if "\x00" in html:
        raise MalformedHtmlError("HTML contains null bytes")
    if _UNBALANCED_TAG_RE.search(html.rstrip()):
        raise MalformedHtmlError("unbalanced HTML tag fragment")
    if "<" not in html or ">" not in html:
        raise MalformedHtmlError("HTML contains no tags")
    lowered = html.lower()
    if "<html" in lowered and "</html>" not in lowered:
        raise MalformedHtmlError("truncated HTML document (missing </html>)")
    if "<body" in lowered and "</body>" not in lowered:
        raise MalformedHtmlError("truncated HTML document (missing </body>)")


def extract_fact_candidates(
    html: str,
    *,
    fact_kind: FactKind,
    fact_marker: str,
) -> ExtractionResult:
    """Extract candidate raw values for ``fact_kind`` from official HTML."""
    _assert_minimally_well_formed(html)

    parser = _OfficialFactParser(marker=fact_marker)
    try:
        parser.feed(html)
        parser.close()
    except Exception as exc:  # noqa: BLE001
        raise MalformedHtmlError(f"HTML parse failed: {exc}") from exc

    if parser.parse_error:
        raise MalformedHtmlError(parser.parse_error)

    title = normalize_whitespace(" ".join(parser.title_parts))
    values = tuple(dict.fromkeys(parser.captured))
    return ExtractionResult(kind=fact_kind, raw_values=values, title=title)


def assert_page_identity(title: str, expected_tokens: tuple[str, ...]) -> None:
    """Require expected identity tokens in the page title (fail-closed)."""
    if not expected_tokens:
        return
    haystack = title or ""
    for token in expected_tokens:
        if token not in haystack:
            raise SourceIdentityMismatchError(
                f"page title missing expected identity token {token!r}"
            )


def resolve_single_fact(
    html: str,
    *,
    fact_kind: FactKind,
    fact_marker: str,
    expected_title_tokens: tuple[str, ...] = (),
):
    """Extract and normalize exactly one fact value (fail-closed otherwise)."""
    extracted = extract_fact_candidates(
        html, fact_kind=fact_kind, fact_marker=fact_marker
    )
    assert_page_identity(extracted.title, expected_title_tokens)

    if not extracted.raw_values:
        raise FactAbsentError(f"no {fact_kind.value} value found in official HTML")

    normalized = []
    for raw in extracted.raw_values:
        fact = normalize_fact_value(fact_kind, raw)
        if fact is not None:
            normalized.append(fact)

    unique: dict[str, object] = {}
    for fact in normalized:
        unique[fact.value] = fact

    if not unique:
        raise FactAbsentError(
            f"no normalizable {fact_kind.value} value in official HTML"
        )
    if len(unique) > 1:
        raise AmbiguousValueError(
            f"multiple distinct {fact_kind.value} values: {sorted(unique)}"
        )

    fact = next(iter(unique.values()))
    return fact, extracted.title, extracted.extractor_id


__all__ = [
    "AmbiguousValueError",
    "ExtractionError",
    "ExtractionResult",
    "FactAbsentError",
    "MalformedHtmlError",
    "SourceIdentityMismatchError",
    "assert_page_identity",
    "extract_fact_candidates",
    "resolve_single_fact",
]
