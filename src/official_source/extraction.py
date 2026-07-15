"""HTML/content extraction for narrowly scoped official civic facts.

Uses the stdlib HTML parser only. No network, no browser, no third-party
scraper. Extraction is fail-closed: missing or ambiguous facts raise typed
errors consumed by the service layer.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from html.parser import HTMLParser

from .models import FactKind
from .normalize import normalize_fact_value, normalize_whitespace


class ExtractionError(Exception):
    """Base extraction failure (mapped to fail-closed error codes)."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


class MalformedHtmlError(ExtractionError):
    def __init__(self, message: str = "malformed HTML") -> None:
        super().__init__("malformed_html", message)


class FactAbsentError(ExtractionError):
    def __init__(self, message: str = "expected fact absent") -> None:
        super().__init__("fact_absent", message)


class AmbiguousValueError(ExtractionError):
    def __init__(self, message: str = "ambiguous multiple values") -> None:
        super().__init__("ambiguous_value", message)


@dataclass(frozen=True)
class ExtractionResult:
    kind: FactKind
    raw_values: tuple[str, ...]
    title: str


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
        self.saw_html_tag = False
        self.parse_error: str | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        tag_l = tag.lower()
        if tag_l in {"html", "body", "div", "span", "p", "h1", "h2", "meta"}:
            self.saw_html_tag = True
        attr_map = {k.lower(): (v or "") for k, v in attrs}
        if tag_l == "title":
            self._in_title = True
            self._title_buf = []
        if tag_l == "meta":
            # og:site_name / application-name as jurisdiction candidates when marker matches.
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
            # Close one capture level for common containers.
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

    def error(self, message: str) -> None:  # pragma: no cover - py<3.10 API
        self.parse_error = message


_UNBALANCED_TAG_RE = re.compile(r"<[^>]*$")


def _assert_minimally_well_formed(html: str) -> None:
    if not isinstance(html, str) or not html.strip():
        raise MalformedHtmlError("empty HTML document")
    # Extremely broken fragments: unclosed angle bracket, null bytes, or no tags.
    if "\x00" in html:
        raise MalformedHtmlError("HTML contains null bytes")
    if _UNBALANCED_TAG_RE.search(html.rstrip()):
        raise MalformedHtmlError("unbalanced HTML tag fragment")
    if "<" not in html or ">" not in html:
        raise MalformedHtmlError("HTML contains no tags")
    # Require a basic document shell so truncated fragments fail closed.
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
    except Exception as exc:  # noqa: BLE001 — map any parser crash to malformed
        raise MalformedHtmlError(f"HTML parse failed: {exc}") from exc

    if parser.parse_error:
        raise MalformedHtmlError(parser.parse_error)

    title = normalize_whitespace(" ".join(parser.title_parts))
    values = tuple(dict.fromkeys(parser.captured))  # de-dupe, preserve order

    # Fallback heuristics only when marker values are empty (still fail-closed
    # if nothing found — never invent).
    if not values:
        values = _heuristic_candidates(html, fact_kind)

    return ExtractionResult(kind=fact_kind, raw_values=values, title=title)


def _heuristic_candidates(html: str, fact_kind: FactKind) -> tuple[str, ...]:
    text = re.sub(r"<script[\s\S]*?</script>", " ", html, flags=re.I)
    text = re.sub(r"<style[\s\S]*?</style>", " ", text, flags=re.I)
    text = re.sub(r"<[^>]+>", " ", text)
    text = normalize_whitespace(text)

    if fact_kind is FactKind.CURRENT_MAYOR:
        # Require an explicit separator so prose like "구청장 정보가" does not match.
        # e.g. "구청장 : 문인" / "구청장:문인"
        matches = re.findall(
            r"구청장\s*[:：]\s*([가-힣]{2,4})",
            text,
        )
        # Blocklist common non-name collocations that can appear near "구청장".
        blocked = {"정보", "소개", "인사", "공약", "프로필", "약력", "사진"}
        cleaned = [m for m in matches if m not in blocked]
        return tuple(dict.fromkeys(cleaned))

    if fact_kind is FactKind.JURISDICTION_NAME:
        matches = re.findall(
            r"(광주광역시\s*북구(?:청)?)",
            text,
        )
        return tuple(dict.fromkeys(matches))

    return ()


def resolve_single_fact(
    html: str,
    *,
    fact_kind: FactKind,
    fact_marker: str,
):
    """Extract and normalize exactly one fact value (fail-closed otherwise)."""
    extracted = extract_fact_candidates(
        html, fact_kind=fact_kind, fact_marker=fact_marker
    )
    if not extracted.raw_values:
        raise FactAbsentError(
            f"no {fact_kind.value} value found in official HTML"
        )

    normalized = []
    for raw in extracted.raw_values:
        fact = normalize_fact_value(fact_kind, raw)
        if fact is not None:
            normalized.append(fact)

    # Unique by normalized value.
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
    return fact, extracted.title


__all__ = [
    "AmbiguousValueError",
    "ExtractionError",
    "ExtractionResult",
    "FactAbsentError",
    "MalformedHtmlError",
    "extract_fact_candidates",
    "resolve_single_fact",
]
