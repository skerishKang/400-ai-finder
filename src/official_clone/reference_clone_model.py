"""Deterministic, generic reference clone model builder (#1303 G2-A).

Reads a committed G1 named-site reference capture ledger plus its committed
artifact files and produces a renderer-agnostic semantic ``clone-model.json``.

Fail-closed contract:
  * The input capture directory is selected EXPLICITLY (never discovered by
    glob); the ledger must exist at ``<capture_root>/ledger.json``.
  * The builder refuses to produce a model when the G1 evidence is incomplete
    or tampered: plan identity checksum mismatch, artifact paths escaping the
    capture root, missing artifact files, artifact SHA-256 mismatches, or
    invalid visible-region inventories all fail the build.
  * ``reference_baseline_ready`` is DERIVED from that validation, never a
    constant.

The model is a semantic intermediate layer so a later faithful renderer
(G2-B) does not need to read raw G1 artifacts: each state carries its page
title, observed header/nav/main landmarks and controls, asset provenance,
capture exceptions, list numbers, and attachment/download signals — all
derived from the committed G1 evidence. Screenshots are referenced as
evidence but never consumed as runtime source. No network is performed.
"""

from __future__ import annotations

import hashlib
import json
import re
import sys
from html.parser import HTMLParser
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlsplit

SCHEMA_VERSION = 1
MODEL_KIND = "reference_clone_model"
GENERATOR_VERSION = "2.1.0"

# Stage claim gates. reference_baseline_ready is derived at build time;
# the stronger claims are fixed False for G2-A.
FIXED_GATES = {
    "faithful_clone_candidate": False,
    "clone_mvp_ready": False,
    "visual_approval": False,
    "actual_site_integrated": False,
}

BOUNDARIES = {
    "screenshot_used_at_runtime": False,
    "network_at_generation": 0,
    "renderer_wired": False,
    "exact_clone_claimed": False,
}

# Generic document/attachment signal (language- and board-system-agnostic).
_DOC_EXT_RE = re.compile(r"\.([a-z0-9]{1,6})$", re.IGNORECASE)
_DOWNLOAD_HREF_RE = re.compile(r"(download|act=download|boarddownload)", re.IGNORECASE)
_ANCHOR_HREF_RE = re.compile(r"""<a\b[^>]*\bhref\s*=\s*["']([^"']+)["']""", re.IGNORECASE)
_DOC_TOKEN_RE = re.compile(r"\.(hwp[x]?|pdf|zip|docx?|xlsx?|pptx?|csv|txt)", re.IGNORECASE)

SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
SAFE_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")
CAPTURE_PREFIX_RE = re.compile(r"^data/official_captures/([^/]+)/g1/([^/]+)/$")


class ReferenceCloneModelError(ValueError):
    """Raised when the G1 capture evidence is missing, incomplete, or tampered."""


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _require_safe_id(value: str, label: str) -> str:
    if not isinstance(value, str) or not SAFE_ID_RE.fullmatch(value):
        raise ReferenceCloneModelError(f"{label} has unsafe characters: {value!r}")
    return value


def _is_within(parent: Path, child: Path) -> bool:
    try:
        child.resolve().relative_to(parent.resolve())
        return True
    except ValueError:
        return False


def _parse_list_no(final_url: str) -> str | None:
    try:
        values = parse_qs(urlsplit(final_url or "").query).get("list_no")
    except Exception:
        return None
    if values and values[0]:
        return values[0]
    return None


def _extract_download_references(html: str) -> list[dict[str, str]]:
    refs: list[dict[str, str]] = []
    seen: set[str] = set()
    for href in _ANCHOR_HREF_RE.findall(html):
        if not _DOWNLOAD_HREF_RE.search(href):
            continue
        if href in seen:
            continue
        seen.add(href)
        match = _DOC_EXT_RE.search(href.split("?")[0])
        refs.append({"href": href, "ext": match.group(1).lower() if match else ""})
    return refs


def _extract_document_extensions(html: str) -> list[str]:
    return sorted({m.group(1).lower() for m in _DOC_TOKEN_RE.finditer(html)})


# ---------------------------------------------------------------------------
# Generic board vocabulary (list tables, pagers, detail views, attachments)
# ---------------------------------------------------------------------------
# These extractors read the committed G1 ``source.html`` DOM at DESIGN/BUILD
# time only. The renderer (G2-B) never re-opens raw artifacts; it consumes the
# ``state["board"]`` block produced here. The structures parsed are generic
# municipal-board templates (``tstyle_list`` tables, ``board_pager``,
# ``board_view`` articles) with NO site-specific literals.
_BOARD_RECORD_ID_PARAMS = ("list_no", "not_ancmt_mgt_no")
_BOARD_TABLE_CLASS_TOKENS = ("tstyle_list",)
_BOARD_PAGER_CLASS_TOKENS = ("board_pager",)
_BOARD_VIEW_CLASS_TOKENS = ("board_view",)
_BOARD_ATTACHMENT_ALT_RE = re.compile(r"(\d+)\s*개의\s*첨부파일")

# Generic colgroup class-token -> column width percent. Municipal list tables
# express per-column proportions via ``<col class="w8">`` style tokens; a
# ``None`` (flex/auto) column takes the remaining width.
_COLGROUP_WIDTH_BY_CLASS: dict[str, int] = {
    "w8": 8,
    "W8": 8,
    "w10": 10,
    "W10": 10,
    "w12": 12,
    "W12": 12,
    "w15": 15,
    "W15": 15,
    "w20": 20,
    "W20": 20,
}
_COLGROUP_WIDTH_RE = re.compile(r"\s*(\d+(?:\.\d+)?)\s*%")


def _colgroup_width_from_col(attrs) -> int | None:
    """Return the percentage width of a ``<col>`` from its class/width attrs."""
    attrs_dict = dict(attrs)
    cls = (attrs_dict.get("class") or "").strip()
    for token in cls.split():
        if token in _COLGROUP_WIDTH_BY_CLASS:
            return _COLGROUP_WIDTH_BY_CLASS[token]
    width = (attrs_dict.get("width") or "").strip()
    m = _COLGROUP_WIDTH_RE.search(width)
    if m:
        return int(float(m.group(1)))
    return None


def _record_id_from_href(href: str) -> str | None:
    """Extract a board record id from a captured detail link (generic params)."""
    if not href:
        return None
    try:
        query = urlsplit(href).query
    except Exception:
        return None
    values = parse_qs(query)
    for param in _BOARD_RECORD_ID_PARAMS:
        vals = values.get(param)
        if vals and vals[0]:
            return vals[0]
    return None


class _BoardListTableParser(HTMLParser):
    """Collect generic board-list table data (caption/columns/rows/pager)."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.table_found = False
        self.in_table = False
        self.in_colgroup = False
        self.in_caption = False
        self.in_thead = False
        self.in_th = False
        self.in_tbody = False
        self.in_tr = False
        self.in_td = False
        self.in_td_anchor = False
        self._buf: list[str] = []
        self.caption = ""
        self.columns: list[str] = []
        self.col_widths: list[int | None] = []
        self.rows: list[dict[str, Any]] = []
        self._row: dict[str, Any] | None = None
        self._cell_key: str | None = None
        self._cell_href: str = ""
        self._pager_found = False
        self._in_pager = False
        self.pager_pages: list[int] = []
        self.pager_current: int | None = None
        self.pager_links: list[dict[str, str]] = []

    def _cls(self, attrs) -> str:
        for k, v in attrs:
            if k.lower() == "class":
                return v or ""
        return ""

    def _aria_label(self, attrs) -> str | None:
        for k, v in attrs:
            if k.lower() == "aria-label" and v:
                return v.strip()
        return None

    def handle_starttag(self, tag, attrs):
        tag = tag.lower()
        cls = self._cls(attrs)
        if tag == "table" and any(t in cls.split() for t in _BOARD_TABLE_CLASS_TOKENS):
            self.table_found = True
            self.in_table = True
            return
        if not self.in_table:
            if tag == "div" and any(t in cls.split() for t in _BOARD_PAGER_CLASS_TOKENS):
                self._pager_found = True
                self._in_pager = True
                return
            if self._in_pager and tag == "a":
                self._pager_anchor = {
                    "href": next((v for k, v in attrs if k.lower() == "href"), ""),
                    "active": "active" in cls.split(),
                    "text": "",
                }
                self._buf = []
            return
        if tag == "colgroup":
            self.in_colgroup = True
        elif tag == "col" and self.in_colgroup:
            self.col_widths.append(_colgroup_width_from_col(attrs))
        elif tag == "caption":
            self.in_caption = True
            self._buf = []
        elif tag == "thead":
            self.in_thead = True
        elif tag == "tbody":
            self.in_tbody = True
        elif tag == "th":
            self.in_th = True
            self._buf = []
        elif tag == "tr":
            self.in_tr = True
            if self.in_tbody:
                self._row = {"cells": {}, "is_new": False}
        elif tag == "td":
            self.in_td = True
            self._buf = []
            self._cell_key = self._aria_label(attrs)
            self._cell_href = ""
        elif tag == "a" and self.in_td:
            self.in_td_anchor = True
            href = next((v for k, v in attrs if k.lower() == "href"), "")
            self._cell_href = href or ""

    def handle_data(self, data):
        if self.in_caption or self.in_th or self.in_td:
            self._buf.append(data)
        elif (
            getattr(self, "_in_pager", False)
            and isinstance(getattr(self, "_pager_anchor", None), dict)
            and "text" in self._pager_anchor
        ):
            self._pager_anchor["text"] += data

    def handle_endtag(self, tag):
        tag = tag.lower()
        if tag == "table" and self.in_table:
            self.in_table = False
            return
        if not self.in_table:
            if tag == "a" and getattr(self, "_in_pager", False) and hasattr(self, "_pager_anchor"):
                text = self._pager_anchor["text"].strip()
                if text.isdigit():
                    page = int(text)
                    if page not in self.pager_pages:
                        self.pager_pages.append(page)
                    if self._pager_anchor["active"]:
                        self.pager_current = page
                self._pager_anchor = {}
            elif tag == "div" and self._in_pager:
                self._in_pager = False
            return
        if tag == "colgroup":
            self.in_colgroup = False
        elif tag == "caption":
            self.caption = "".join(self._buf).strip()
            self.in_caption = False
        elif tag == "th":
            self.columns.append("".join(self._buf).strip())
            self.in_th = False
        elif tag == "a" and self.in_td_anchor:
            self.in_td_anchor = False
        elif tag == "td":
            text = "".join(self._buf).strip()
            if self._row is not None:
                key = self._cell_key
                if key is None:
                    key = self.columns[len(self._row["cells"])] if len(self._row["cells"]) < len(self.columns) else ""
                self._row["cells"][key] = text
                if key == "제목":
                    rid = _record_id_from_href(self._cell_href)
                    if rid:
                        self._row["record_id"] = rid
                    if "새글" in text:
                        self._row["is_new"] = True
                if key == "첨부파일":
                    m = _BOARD_ATTACHMENT_ALT_RE.search(text)
                    if m:
                        self._row["attachment_count"] = int(m.group(1))
                    elif self._cell_href and _DOWNLOAD_HREF_RE.search(self._cell_href):
                        self._row["attachment_count"] = 1
            self.in_td = False
        elif tag == "tr":
            if self.in_tbody and self._row is not None:
                self.rows.append(self._row)
                self._row = None
            self.in_tr = False


class _BoardDetailParser(HTMLParser):
    """Collect generic board-detail data (title/meta/contents/attachments).

    The parsed structures are generic municipal-board templates; text values
    are taken verbatim from the captured DOM. Direct text inside the contents
    block and the attachment list items is captured as well as wrapped text.
    """

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.article_found = False
        self.in_article = False
        self._buf: list[str] = []
        self.title = ""
        self.meta: list[dict[str, str]] = []
        self.body_blocks: list[dict[str, str]] = []
        self.attachments: list[dict[str, Any]] = []
        self.prev: dict[str, str] | None = None
        self.next: dict[str, str] | None = None
        # context flags
        self._in_title = False
        self._in_meta_list = False
        self._in_meta_li = False
        self._meta_label: str | None = None
        self._in_meta_strong = False
        self._in_contents = False
        self._in_contents_para = False
        self._br_count = 0
        self._in_file = False
        self._in_file_li = False
        self._in_attach_txt = False
        self._in_link_span = False
        self._attach: dict[str, Any] | None = None
        self._attach_name_buf: list[str] = []
        self._in_prevnext = False
        self._prev_li_class = ""
        self._prev_href = ""

    def _cls(self, attrs) -> str:
        for k, v in attrs:
            if k.lower() == "class":
                return v or ""
        return ""

    def _flush_contents_para(self) -> None:
        """Emit the current contents text buffer as one generic paragraph.

        ``break_count`` records how many ``<br>`` runs led into this paragraph
        so the renderer can reproduce the source page's vertical rhythm. The
        counter is only reset when a paragraph is actually emitted, so a run
        of consecutive ``<br>`` (which flush an empty buffer) keeps counting.
        """
        text = "".join(self._buf).strip()
        if text:
            block: dict[str, Any] = {"type": "paragraph", "text": text}
            if self._br_count:
                block["break_count"] = self._br_count
            self.body_blocks.append(block)
            self._br_count = 0
        self._buf = []

    def handle_starttag(self, tag, attrs):
        tag = tag.lower()
        cls = self._cls(attrs)
        if tag == "article" and any(t in cls.split() for t in _BOARD_VIEW_CLASS_TOKENS):
            self.article_found = True
            self.in_article = True
            return
        if not self.in_article:
            if tag == "ul" and "prevnext" in cls.split():
                self._in_prevnext = True
            elif self._in_prevnext and tag == "li":
                self._prev_li_class = cls
                self._buf = []
            elif self._in_prevnext and tag == "a":
                href = next((v for k, v in attrs if k.lower() == "href"), "")
                self._prev_href = href or ""
            return
        if tag == "h2" and "title" in cls.split():
            self._in_title = True
            self._buf = []
        elif tag == "ul" and "info" in cls.split():
            self._in_meta_list = True
        elif tag == "li" and self._in_meta_list:
            self._in_meta_li = True
            self._meta_label = None
            self._buf = []
            self._meta_val: list[str] = []
        elif tag == "strong" and self._in_meta_li:
            self._in_meta_strong = True
            self._buf = []
        elif tag == "div" and "contents" in cls.split():
            self._in_contents = True
            self._buf = []
        elif tag == "p" and self._in_contents:
            self._in_contents_para = True
            self._buf = []
        elif tag == "br" and self._in_contents:
            # Source editor bodies separate paragraphs with <br> runs. Flush the
            # accumulated text as one paragraph (recording how many <br>s led
            # into it) so the rendered vertical rhythm matches the G1 page
            # instead of flattening the whole body into one blob.
            self._flush_contents_para()
            self._br_count += 1
        elif tag == "img" and self._in_contents:
            # Source-backed image reference inside the detail body. The bytes
            # are NOT embedded (rights/asset gate); only the alt/title text and
            # the committed source path are recorded so a renderer can draw a
            # bounded placeholder instead of inventing content.
            alt = next((v for k, v in attrs if k.lower() == "alt"), "") or ""
            title = next((v for k, v in attrs if k.lower() == "title"), "") or ""
            src = next((v for k, v in attrs if k.lower() == "src"), "") or ""
            self.body_blocks.append({
                "type": "image",
                "alt": alt.strip(),
                "title": title.strip(),
                "source_path": src.strip(),
            })
        elif tag == "div" and "file" in cls.split():
            self._in_file = True
        elif tag == "li" and self._in_file:
            self._in_file_li = True
            self._attach = {
                "name": "", "meta": "", "ext": "",
                "download_href": None, "preview_href": None,
            }
            self._buf = []
            self._attach_name_buf = []
        elif tag == "img" and self._in_file_li:
            alt = next((v for k, v in attrs if k.lower() == "alt"), "")
            m = _DOC_EXT_RE.search((alt or "").lower())
            if m and self._attach is not None:
                self._attach["ext"] = m.group(1)
        elif tag == "span" and self._in_file_li:
            if "txt" in cls.split():
                self._in_attach_txt = True
                self._buf = []
            elif "link" in cls.split():
                self._in_link_span = True
        elif tag == "a" and self._in_file_li:
            href = next((v for k, v in attrs if k.lower() == "href"), "")
            self._anchor_text: list[str] = []
            self._anchor_href = href or ""

    def handle_data(self, data):
        if self._in_title or self._in_meta_strong:
            self._buf.append(data)
        elif self._in_meta_li:
            self._meta_val.append(data)
        elif self._in_contents:
            self._buf.append(data)
        elif self._in_attach_txt:
            self._buf.append(data)
        elif self._in_file_li and not self._in_link_span:
            self._attach_name_buf.append(data)
        elif self._in_prevnext:
            self._buf.append(data)
        elif hasattr(self, "_anchor_text"):
            self._anchor_text.append(data)

    def handle_endtag(self, tag):
        tag = tag.lower()
        if tag == "article" and self.in_article:
            self.in_article = False
            return
        if not self.in_article:
            if tag == "ul" and self._in_prevnext:
                self._in_prevnext = False
            elif tag == "li" and self._in_prevnext:
                text = "".join(self._buf).strip()
                for label in ("이전글", "다음글"):
                    if text.startswith(label):
                        text = text[len(label):].strip()
                        break
                href = self._prev_href
                rid = _record_id_from_href(href)
                entry = {"title": text, "record_id": rid} if rid else {"title": text}
                if "prev" in self._prev_li_class:
                    self.prev = entry
                elif "next" in self._prev_li_class:
                    self.next = entry
            return
        if tag == "h2" and self._in_title:
            self.title = "".join(self._buf).strip()
            self._in_title = False
        elif tag == "strong" and self._in_meta_strong:
            self._meta_label = "".join(self._buf).strip()
            self._in_meta_strong = False
        elif tag == "li" and self._in_meta_li:
            value = "".join(self._meta_val).strip()
            if self._meta_label:
                self.meta.append({"label": self._meta_label, "value": value})
            self._in_meta_li = False
        elif tag == "ul" and self._in_meta_list:
            self._in_meta_list = False
        elif tag == "p" and self._in_contents_para:
            self._flush_contents_para()
            self._in_contents_para = False
        elif tag == "div" and self._in_contents:
            self._flush_contents_para()
            self._in_contents = False
        elif tag == "li" and self._in_file_li:
            if self._attach is not None:
                name = "".join(self._attach_name_buf).strip()
                if name and not self._attach.get("name"):
                    self._attach["name"] = name
                if self._attach.get("name") and not self._attach.get("ext"):
                    m = _DOC_TOKEN_RE.search(self._attach["name"])
                    if m:
                        self._attach["ext"] = m.group(1).lower()
                if self._attach.get("name"):
                    self.attachments.append(self._attach)
            self._in_file_li = False
            self._attach = None
        elif tag == "span" and self._in_attach_txt:
            if self._attach is not None:
                self._attach["meta"] = "".join(self._buf).strip()
            self._in_attach_txt = False
        elif tag == "span" and self._in_link_span:
            self._in_link_span = False
        elif tag == "a" and self._in_file_li:
            text = "".join(getattr(self, "_anchor_text", [])).strip()
            href = getattr(self, "_anchor_href", "")
            if self._attach is not None:
                if text == "다운로드" or _DOWNLOAD_HREF_RE.search(href):
                    self._attach["download_href"] = href
                elif text == "미리보기" or "attachPreview" in href:
                    self._attach["preview_href"] = href
            self._anchor_text = []
        elif tag == "div" and self._in_file:
            self._in_file = False


class _BoardDataCollector(HTMLParser):
    """Fully offline pass that merges list/detail/pager extractions."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._list = _BoardListTableParser()
        self._detail = _BoardDetailParser()
        self._current = self._list

    def handle_starttag(self, tag, attrs):
        tag = tag.lower()
        cls = ""
        for k, v in attrs:
            if k.lower() == "class":
                cls = v or ""
                break
        if tag == "table" and any(t in cls.split() for t in _BOARD_TABLE_CLASS_TOKENS):
            self._current = self._list
        elif tag == "article" and any(t in cls.split() for t in _BOARD_VIEW_CLASS_TOKENS):
            self._current = self._detail
        self._current.handle_starttag(tag, attrs)

    def handle_data(self, data):
        self._current.handle_data(data)

    def handle_endtag(self, tag):
        self._current.handle_endtag(tag)

    def handle_entityref(self, name):
        self._current.handle_entityref(name)

    def handle_charref(self, name):
        self._current.handle_charref(name)


class _ContentsInfoParser(HTMLParser):
    """Capture the generic ``div.contents_info`` block from a board page.

    Two source-backed shapes are observed on the committed G1 municipal board
    pages: the 공공누리 (KOGL) license notice (``div.kogl > span.txt``) and the
    civil-service duty box (``article.duty`` with a title plus label/value
    list items, e.g. 콘텐츠 정보책임자). Returns ``None`` when neither shape
    exists in the captured DOM.
    """

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._in_contents = False
        self._in_kogl = False
        self._in_kogl_txt = False
        self._kogl_text: list[str] = []
        self._in_duty = False
        self._in_duty_title = False
        self._in_duty_item = False
        self._in_duty_label = False
        self._in_duty_value = False
        self._duty_title: list[str] = []
        self._duty_label: list[str] = []
        self._duty_value: list[str] = []
        self._duty_items: list[dict[str, str]] = []
        self.result: dict[str, Any] | None = None

    def _cls(self, attrs):
        for k, v in attrs:
            if k.lower() == "class":
                return v or ""
        return ""

    def handle_starttag(self, tag, attrs):
        tag = tag.lower()
        tokens = self._cls(attrs).split()
        if tag == "div" and "contents_info" in tokens:
            self._in_contents = True
            return
        if not self._in_contents:
            return
        if tag == "div" and any(t.startswith("kogl") for t in tokens):
            self._in_kogl = True
        elif tag == "span" and "txt" in tokens and self._in_kogl:
            self._in_kogl_txt = True
        elif tag == "article" and "duty" in tokens:
            self._in_duty = True
        elif self._in_duty:
            if tag == "li":
                self._in_duty_item = True
                self._duty_label = []
                self._duty_value = []
            elif tag == "strong" and "label" in tokens:
                self._in_duty_label = True
            elif tag == "h2" and "title" in tokens:
                self._in_duty_title = True
            elif tag in ("span", "strong") and any(
                t in tokens for t in ("part", "tel", "name", "dept")
            ):
                self._in_duty_value = True

    def handle_data(self, data):
        if not self._in_contents:
            return
        if self._in_duty:
            if self._in_duty_label:
                self._duty_label.append(data)
            elif self._in_duty_value:
                self._duty_value.append(data)
            elif self._in_duty_title:
                self._duty_title.append(data)
        elif self._in_kogl_txt:
            self._kogl_text.append(data)

    def handle_endtag(self, tag):
        tag = tag.lower()
        if tag == "li" and self._in_duty_item:
            label = "".join(self._duty_label).strip()
            value = "".join(self._duty_value).strip()
            if label:
                self._duty_items.append({"label": label, "value": value})
            self._in_duty_item = False
            self._in_duty_label = False
            self._in_duty_value = False
        elif tag == "strong" and self._in_duty_label:
            self._in_duty_label = False
        elif tag == "h2" and self._in_duty_title:
            self._in_duty_title = False
        elif tag == "span" and self._in_kogl_txt:
            self._in_kogl_txt = False
        elif tag == "div" and self._in_kogl:
            self._in_kogl = False
        elif tag == "article" and self._in_duty:
            self._in_duty = False
        elif tag == "div" and self._in_contents and not self._in_duty and not self._in_kogl:
            self._finalize()
            self._in_contents = False

    def _finalize(self) -> None:
        if self._duty_items:
            self.result = {
                "kind": "duty",
                "title": "".join(self._duty_title).strip() or None,
                "items": self._duty_items,
            }
            return
        text = re.sub(r"\s+", " ", "".join(self._kogl_text)).strip()
        if text:
            self.result = {"kind": "kogl", "text": text}


class _SnbStructureParser(HTMLParser):
    """Capture the visible left sidebar menu with depth from ``section#snb``.

    The committed G1 municipal sidebar is a two-level list: ``ul#left_menu_top``
    level-1 items with an optional expanded ``ul`` of level-2 children rendered
    under the active item (``style="display: block;"``). Only the visible
    level-2 children of the expanded parent are part of the rendered sidebar;
    collapsed ``display:none`` sublists are skipped so the captured item order
    matches the visible screenshot row order.
    """

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._in_snb = False
        self._in_title = False
        self._title_parts: list[str] = []
        self._items: list[dict[str, Any]] = []
        self._li_stack: list[dict[str, Any]] = []
        self._in_label_a = False
        self._label_parts: list[str] = []
        self._sub_visible = False
        self._in_li = False
        self.result: dict[str, Any] | None = None

    def _attrs(self, attrs) -> dict[str, str]:
        out: dict[str, str] = {}
        for k, v in attrs:
            out[k.lower()] = (v or "").lower()
        return out

    def handle_starttag(self, tag, attrs):
        tag = tag.lower()
        a = self._attrs(attrs)
        if tag == "section" and a.get("id") == "snb":
            self._in_snb = True
            return
        if not self._in_snb:
            return
        if tag == "h2" and "title" in (a.get("class") or "").split():
            self._in_title = True
        elif tag == "li":
            if self._li_stack:
                # A nested li: level-2 child inside a sublist.
                self._li_stack.append({"depth": 2, "parts": [], "visible": self._sub_visible})
            else:
                self._li_stack.append({"depth": 1, "parts": [], "visible": True})
            self._in_li = True
            self._label_parts = []
        elif tag == "a" and self._li_stack:
            self._in_label_a = True
        elif tag == "ul" and self._li_stack:
            style = a.get("style") or ""
            self._sub_visible = "display: block" in style

    def handle_data(self, data):
        if not self._in_snb:
            return
        if self._in_title:
            self._title_parts.append(data)
        elif self._in_label_a and self._li_stack:
            self._label_parts.append(data)

    def handle_endtag(self, tag):
        tag = tag.lower()
        if tag == "h2" and self._in_title:
            self._in_title = False
        elif tag == "a" and self._in_label_a:
            self._in_label_a = False
            if self._li_stack:
                self._li_stack[-1]["parts"] = self._label_parts
                if self._li_stack[-1].get("depth") == 1 and not self._li_stack[-1].get("emitted"):
                    label = "".join(self._li_stack[-1].get("parts") or []).strip()
                    if label:
                        self._items.append({"label": label, "depth": 1})
                        self._li_stack[-1]["emitted"] = True
        elif tag == "ul":
            self._sub_visible = False
        elif tag == "li" and self._li_stack:
            entry = self._li_stack.pop()
            visible = entry.get("visible", True)
            depth = entry.get("depth", 1)
            label = "".join(entry.get("parts") or []).strip()
            if depth == 2 and visible and label:
                self._items.append({"label": label, "depth": 2})
            self._in_li = False
        elif tag == "section" and self._in_snb:
            self._in_snb = False
            title = "".join(self._title_parts).strip()
            if self._items or title:
                self.result = {"title": title or None, "items": self._items}


def _extract_snb_structure(html: str) -> dict[str, Any] | None:
    """Best-effort generic ``section#snb`` structure extraction."""
    if not html:
        return None
    parser = _SnbStructureParser()
    parser.feed(html)
    return parser.result


def _extract_contents_info(html: str) -> dict[str, Any] | None:
    """Best-effort generic ``div.contents_info`` extraction."""
    if not html:
        return None
    parser = _ContentsInfoParser()
    parser.feed(html)
    return parser.result


def _extract_board(html: str) -> dict[str, Any] | None:
    """Extract the generic board block for a captured state, or ``None``.

    Returns a list-shaped ``{"kind": "list", ...}`` or a detail-shaped
    ``{"kind": "detail", ...}`` block only when the committed G1 DOM actually
    contains the corresponding generic board template. Rows/columns/meta/body
    are source-backed text taken verbatim from the captured HTML.
    """
    if not html:
        return None
    collector = _BoardDataCollector()
    collector.feed(html)
    table = collector._list
    detail = collector._detail
    if table.table_found and table.columns:
        block: dict[str, Any] = {"kind": "list"}
        if table.caption:
            block["caption"] = table.caption
        block["columns"] = table.columns
        # Source-backed per-column width percent (from the colgroup).
        # ``None`` entries mean flex/auto (the title column).
        if table.col_widths:
            block["col_widths"] = table.col_widths
        block["rows"] = table.rows
        if table.pager_pages or table.pager_current is not None:
            block["pagination"] = {
                "pages": table.pager_pages,
                "current_page": table.pager_current,
            }
        contents_info = _extract_contents_info(html)
        if contents_info:
            block["contents_info"] = contents_info
        snb = _extract_snb_structure(html)
        if snb and snb.get("items"):
            block["snb"] = snb
        return block
    if detail.article_found:
        block = {"kind": "detail"}
        if detail.title:
            block["title"] = detail.title
        if detail.meta:
            block["meta"] = detail.meta
        if detail.body_blocks:
            block["body"] = detail.body_blocks
        if detail.attachments:
            block["attachments"] = detail.attachments
        if detail.prev:
            block["prev"] = detail.prev
        if detail.next:
            block["next"] = detail.next
        contents_info = _extract_contents_info(html)
        if contents_info:
            block["contents_info"] = contents_info
        snb = _extract_snb_structure(html)
        if snb and snb.get("items"):
            block["snb"] = snb
        return block
    return None


def _extract_board_pagination(html: str) -> dict[str, Any] | None:
    """Extract pager numbers from a committed G1 list page (best effort)."""
    if not html:
        return None
    collector = _BoardListTableParser()
    collector.feed(html)
    if not collector.pager_pages and collector.pager_current is None:
        return None
    return {
        "pages": collector.pager_pages,
        "current_page": collector.pager_current,
    }


class _AnchorCollector(HTMLParser):
    """Collect (href, text) anchor pairs in document order, fully offline."""

    _SKIP_SCHEMES = ("javascript:", "mailto:", "tel:", "data:")

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._in_anchor = False
        self._text_parts: list[str] = []
        self._attrs: dict[str, str] = {}
        self.anchors: list[tuple[str, str]] = []

    def handle_starttag(self, tag, attrs):
        if tag.lower() != "a":
            return
        self._in_anchor = True
        self._text_parts = []
        self._attrs = {k.lower(): (v or "") for k, v in attrs}

    def handle_data(self, data):
        if self._in_anchor:
            self._text_parts.append(data)

    def handle_endtag(self, tag):
        if tag.lower() != "a" or not self._in_anchor:
            return
        self._in_anchor = False
        href = (self._attrs.get("href") or "").strip()
        text = "".join(self._text_parts).strip()
        self.anchors.append((href, text))


def _extract_general_links(html: str) -> list[dict[str, Any]]:
    """Ordered general anchor observations (text/href/order) for G2-B.

    The semantic model must let a later faithful renderer reconstruct menus and
    navigation links without reopening raw ``source.html``. Fragment-only,
    script, contact, and empty hrefs are skipped; the remaining anchors are
    emitted in document order with an explicit 1-based ``order`` index.
    """
    collector = _AnchorCollector()
    collector.feed(html or "")
    links: list[dict[str, Any]] = []
    for href, text in collector.anchors:
        if not href:
            continue
        low = href.lower()
        if low.startswith(_AnchorCollector._SKIP_SCHEMES):
            continue
        if low == "#" or low.startswith("#"):
            continue
        links.append({"text": text, "href": href, "order": len(links) + 1})
    return links


def _resolve_plan_path(repo_root: Path, plan_path: str | None) -> Path | None:
    if not plan_path:
        return None
    candidate = Path(plan_path)
    if candidate.is_absolute() or any(part == ".." for part in candidate.parts):
        return None
    full = (repo_root / candidate).resolve()
    if not _is_within(repo_root, full):
        return None
    return full


def _resolve_artifact_path(
    capture_root: Path, site_id: str, capture_id: str, artifact_id: str | None
) -> Path | None:
    """Resolve a ledger artifact_id to a file inside the capture root.

    Production artifact ids are repo-relative
    ``data/official_captures/<site>/g1/<capture_id>/states/...``; the capture-
    relative portion is recovered by stripping the declared capture prefix.
    Absolute paths and any ``..`` escape are rejected.
    """
    if not isinstance(artifact_id, str) or not artifact_id:
        return None
    prefix = f"data/official_captures/{site_id}/g1/{capture_id}/"
    rel = artifact_id[len(prefix):] if artifact_id.startswith(prefix) else artifact_id
    rel_path = Path(rel)
    if rel_path.is_absolute() or any(part == ".." for part in rel_path.parts):
        return None
    candidate = (capture_root / rel_path).resolve()
    if not _is_within(capture_root, candidate):
        return None
    return candidate


def _load_plan(repo_root: Path, plan_identity: dict[str, Any] | None) -> tuple[dict[str, Any] | None, str | None]:
    if not isinstance(plan_identity, dict):
        return None, "plan_identity missing"
    plan_path_str = plan_identity.get("path")
    plan_sha = plan_identity.get("sha256")
    if not plan_path_str or not plan_sha:
        return None, "plan_identity.path or sha256 missing"
    plan_path = _resolve_plan_path(repo_root, plan_path_str)
    if plan_path is None:
        return None, "plan path escapes repo root"
    if not plan_path.is_file():
        return None, f"plan file not found: {plan_path_str}"
    if not SHA256_RE.fullmatch(str(plan_sha)):
        return None, "plan_identity.sha256 is not a lowercase 64-hex SHA-256"
    if sha256_file(plan_path) != plan_sha:
        return None, "ledger plan checksum does not match approved plan bytes"
    try:
        plan = json.loads(plan_path.read_text(encoding="utf-8"))
    except Exception as exc:
        return None, f"plan is not valid JSON: {exc}"
    return plan, None


def _inventory_is_valid(value: Any) -> bool:
    if not isinstance(value, dict):
        return False
    if not isinstance(value.get("title"), str) or not value["title"]:
        return False
    for key in ("landmarks", "controls"):
        if not isinstance(value.get(key), list):
            return False
    return True


def _states_duplicate_ids(captured: list[dict[str, Any]]) -> bool:
    ids = [str(s.get("state_id")) for s in captured]
    return len(ids) != len(set(ids))


def _derive_expected_identity(
    capture_root: Path, repo_root: Path
) -> tuple[str | None, str | None]:
    """Derive the expected named-site identity from the canonical capture path.

    A named-site reference capture MUST live at
    ``<repo>/data/official_captures/<site_id>/g1/<capture_id>/``. Deriving the
    expected identity from that path makes the identity gate non-bypassable: a
    normal build can no longer point at an unrelated/arbitrary capture root
    without the ledger ``site_id``/``capture_id`` disagreeing with the path.
    """
    try:
        rel = capture_root.resolve().relative_to(repo_root.resolve()).as_posix()
    except ValueError:
        return None, None
    if not rel.endswith("/"):
        rel += "/"
    match = CAPTURE_PREFIX_RE.fullmatch(rel)
    if not match:
        return None, None
    return match.group(1), match.group(2)


def _expected_site_capture_mismatch(
    ledger: dict[str, Any],
    capture_root_name: str,
    expected_site_id: str | None,
    expected_capture_id: str | None,
) -> str | None:
    if expected_site_id is None or expected_capture_id is None:
        return (
            "capture root is not a canonical named-site capture directory; "
            "site/capture identity cannot be derived from the path"
        )
    ledger_site = str(ledger.get("site_id", ""))
    ledger_capture = capture_root_name
    if ledger_site != expected_site_id:
        return f"expected site_id {expected_site_id!r} but ledger has {ledger_site!r}"
    if ledger_capture != expected_capture_id:
        return f"expected capture_id {expected_capture_id!r} but capture root has {ledger_capture!r}"
    return None


def validate_reference_evidence(
    repo_root: Path,
    capture_root: Path,
    expected_site_id: str | None = None,
    expected_capture_id: str | None = None,
) -> dict[str, Any]:
    """Validate the G1 evidence without building the model.

    Never raises for invalid evidence; returns a report of derived booleans.
    ``reference_baseline_ready`` is the AND of every gate below.
    """
    repo_root = Path(repo_root).resolve()
    capture_root = Path(capture_root).resolve()
    ledger_path = capture_root / "ledger.json"
    if not ledger_path.is_file():
        raise ReferenceCloneModelError(f"ledger not found: {ledger_path}")
    try:
        ledger = json.loads(ledger_path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise ReferenceCloneModelError(f"ledger is not valid JSON: {exc}") from exc

    site_id = _require_safe_id(str(ledger.get("site_id")), "site_id")
    capture_id = _require_safe_id(capture_root.name, "capture_id")
    capture_mode = ledger.get("capture_mode")

    derived_site, derived_capture = _derive_expected_identity(capture_root, repo_root)
    effective_site = expected_site_id if expected_site_id is not None else derived_site
    effective_capture = expected_capture_id if expected_capture_id is not None else derived_capture
    identity_mismatch = _expected_site_capture_mismatch(ledger, capture_root.name, effective_site, effective_capture)

    # 1. Ledger identity (plan checksum + basic ledger fields).
    plan, identity_problem = _load_plan(repo_root, ledger.get("plan_identity"))
    ledger_identity_valid = (
        identity_problem is None
        and identity_mismatch is None
        and bool(site_id)
        and bool(capture_mode)
        and bool(ledger.get("capture_mode"))
        and ledger.get("g1_completion_claim") is True
    )

    # 2. States complete: every captured state succeeded and the captured
    #    state set exactly matches the plan-required set (no duplicates,
    #    no missing, no unknown/additional state IDs).
    captured = ledger.get("captured_states")
    states_complete = False
    if isinstance(captured, list) and captured and ledger_identity_valid:
        by_id = {str(s.get("state_id")): s for s in captured}
        all_success = all(s.get("result_status") == "success" for s in captured)
        no_duplicates = not _states_duplicate_ids(captured)
        required = sorted({
            str(st.get("state_id"))
            for st in (plan or {}).get("states", [])
            if st.get("capture_required")
        })
        captured_sorted = sorted(set(by_id))
        exact_state_set = no_duplicates and bool(required) and captured_sorted == required
        states_complete = all_success and exact_state_set

    # 3-5. Artifact containment, presence, and SHA-256 linkage.
    artifacts_within_capture_root = True
    artifact_files_present = True
    artifact_sha256_match = True
    if isinstance(captured, list):
        for state in captured:
            for artifact in state.get("artifacts", []):
                path = _resolve_artifact_path(capture_root, site_id, capture_id, artifact.get("artifact_id"))
                if path is None:
                    artifacts_within_capture_root = False
                    continue
                if not path.is_file():
                    artifact_files_present = False
                    continue
                if not SHA256_RE.fullmatch(str(artifact.get("sha256") or "")):
                    artifact_sha256_match = False
                    continue
                if sha256_file(path) != artifact["sha256"]:
                    artifact_sha256_match = False

    # 6. Visible-region inventories valid for states carrying html evidence.
    inventories_valid = True
    if isinstance(captured, list):
        for state in captured:
            inventory_artifact = next(
                (a for a in state.get("artifacts", []) if a.get("class") == "visible_region_inventory"),
                None,
            )
            if inventory_artifact is None:
                inventories_valid = False
                continue
            path = _resolve_artifact_path(capture_root, site_id, capture_id, inventory_artifact.get("artifact_id"))
            if path is None or not path.is_file():
                inventories_valid = False
                continue
            try:
                value = json.loads(path.read_text(encoding="utf-8"))
            except Exception:
                inventories_valid = False
                continue
            if not _inventory_is_valid(value):
                inventories_valid = False

    reference_baseline_ready = (
        ledger_identity_valid
        and states_complete
        and artifacts_within_capture_root
        and artifact_files_present
        and artifact_sha256_match
        and inventories_valid
    )
    return {
        "ledger_identity_valid": ledger_identity_valid,
        "states_complete": states_complete,
        "artifacts_within_capture_root": artifacts_within_capture_root,
        "artifact_files_present": artifact_files_present,
        "artifact_sha256_match": artifact_sha256_match,
        "inventories_valid": inventories_valid,
        "reference_baseline_ready": reference_baseline_ready,
        "identity_problem": identity_problem,
        "identity_mismatch": identity_mismatch,
    }


def _load_inventory(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not _inventory_is_valid(value):
        raise ReferenceCloneModelError(f"invalid visible-region inventory: {path}")
    return value


def build_reference_clone_model(
    repo_root: Path,
    capture_root: Path,
    expected_site_id: str | None = None,
    expected_capture_id: str | None = None,
) -> dict[str, Any]:
    """Build the semantic clone model from validated G1 evidence.

    ``capture_root`` must be provided explicitly (never discovered by glob).
    ``expected_site_id`` and ``expected_capture_id``, when provided, are
    compared against the ledger for identity mismatch rejection.
    """
    if capture_root is None:
        raise ReferenceCloneModelError("capture_root is required (glob discovery is forbidden)")
    repo_root = Path(repo_root).resolve()
    capture_root = Path(capture_root).resolve()
    validation = validate_reference_evidence(repo_root, capture_root, expected_site_id, expected_capture_id)
    if not validation["reference_baseline_ready"]:
        problem = validation.get("identity_problem") or validation.get("identity_mismatch") or "G1 evidence is incomplete or tampered"
        raise ReferenceCloneModelError(f"refusing to build: {problem}")

    ledger_path = capture_root / "ledger.json"
    ledger = json.loads(ledger_path.read_text(encoding="utf-8"))
    site_id = _require_safe_id(str(ledger.get("site_id")), "site_id")
    capture_id = _require_safe_id(capture_root.name, "capture_id")
    plan_identity = ledger.get("plan_identity") or {}
    plan, _ = _load_plan(repo_root, plan_identity)
    allowed_hosts: list[str] = list(ledger.get("allowed_hosts") or (plan or {}).get("allowed_hosts") or [])

    claim_gates = dict(FIXED_GATES)
    claim_gates["reference_baseline_ready"] = bool(validation["reference_baseline_ready"])
    claim_gates["reference_semantic_model_ready"] = bool(validation["reference_baseline_ready"])

    # Collect per-state exceptions into a global exception queue.
    exception_queue: list[dict[str, Any]] = []
    provenance_manifest: list[dict[str, Any]] = []

    model: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "model_kind": MODEL_KIND,
        "model_id": f"{site_id}.g1.reference_clone.{capture_id}",
        "site_id": site_id,
        "capture_id": capture_id,
        "capture_mode": ledger.get("capture_mode"),
        "generator_id": "scripts/build_reference_clone_model.py",
        "generator_version": GENERATOR_VERSION,
        "source_identity": {
            "capture_root": str(ledger_path.parent.relative_to(repo_root).as_posix()),
            "ledger_path": str(ledger_path.relative_to(repo_root).as_posix()),
            "ledger_sha256": sha256_file(ledger_path),
            "plan_id": plan_identity.get("plan_id"),
            "plan_path": plan_identity.get("path"),
            "plan_sha256": plan_identity.get("sha256"),
            "allowed_hosts": allowed_hosts,
            "g1_completion_claim": bool(ledger.get("g1_completion_claim")),
        },
        "validation": {
            key: bool(validation[key])
            for key in (
                "ledger_identity_valid",
                "states_complete",
                "artifacts_within_capture_root",
                "artifact_files_present",
                "artifact_sha256_match",
                "inventories_valid",
                "reference_baseline_ready",
            )
        },
        "claim_gates": claim_gates,
        "boundaries": dict(BOUNDARIES),
    }

    states: list[dict[str, Any]] = []
    artifact_count = 0
    for captured in ledger.get("captured_states", []):
        state_id = _require_safe_id(str(captured.get("state_id")), "state_id")
        device_class = "mobile" if "mobile" in state_id.split(".") else "desktop"
        state_name = (captured.get("state") or {}).get("name")

        artifacts = []
        for artifact in captured.get("artifacts", []):
            artifacts.append(
                {
                    "class": artifact.get("class"),
                    "artifact_id": artifact.get("artifact_id"),
                    "sha256": artifact.get("sha256"),
                }
            )
        artifact_count += len(artifacts)

        def _artifact_file(artifact_class: str) -> Path | None:
            artifact = next((a for a in captured.get("artifacts", []) if a.get("class") == artifact_class), None)
            if artifact is None:
                return None
            return _resolve_artifact_path(capture_root, site_id, capture_id, artifact.get("artifact_id"))

        html_path = _artifact_file("html_dom_content")
        download_references: list[dict[str, str]] = []
        document_extensions: list[str] = []
        general_links: list[dict[str, Any]] = []
        if html_path is not None and html_path.is_file():
            html = html_path.read_text(encoding="utf-8", errors="replace")
            download_references = _extract_download_references(html)
            document_extensions = _extract_document_extensions(html)
            general_links = _extract_general_links(html)

        inventory_path = _artifact_file("visible_region_inventory")
        page_title: str | None = None
        landmarks: list[Any] = []
        controls: list[Any] = []
        viewport_geometry: dict[str, Any] | None = None
        if inventory_path is not None and inventory_path.is_file():
            inventory = _load_inventory(inventory_path)
            page_title = inventory.get("title")
            landmarks = inventory.get("landmarks", [])
            controls = inventory.get("controls", [])
            viewport_geometry = inventory.get("viewport")

        # Document/full-page geometry evidence: the capture viewport plus the
        # committed full-page screenshot dimensions (so G2-B need not reopen
        # raw pixels). Absent when the state has no committed screenshot.
        screenshot_artifact = next(
            (a for a in captured.get("artifacts", []) if a.get("class") == "screenshot"),
            None,
        )
        full_page_screenshot = None
        if isinstance(screenshot_artifact, dict) and isinstance(screenshot_artifact.get("dimensions"), dict):
            dims = screenshot_artifact["dimensions"]
            full_page_screenshot = {
                "width": dims.get("width"),
                "height": dims.get("height"),
                "artifact_id": screenshot_artifact.get("artifact_id"),
                "sha256": screenshot_artifact.get("sha256"),
            }
        document_geometry = {
            "viewport": captured.get("viewport"),
            "full_page_screenshot": full_page_screenshot,
        }

        # Collect per-state exceptions and public assets into global queues.
        for exc in captured.get("exceptions", []):
            exception_queue.append({
                "state_id": state_id,
                "code": exc.get("code"),
                "detail": exc.get("detail"),
            })
        for asset in captured.get("public_assets", []):
            provenance_manifest.append({
                "state_id": state_id,
                "source_url": asset.get("source_url"),
                "sha256": asset.get("sha256"),
                "provenance_note": asset.get("provenance_note"),
            })

        # Generic board vocabulary (source-backed rows/columns/meta/body/attachments)
        # extracted at DESIGN time from the committed G1 DOM. Absent for states
        # whose captured HTML contains no generic board template.
        board: dict[str, Any] | None = None
        if html_path is not None and html_path.is_file():
            board = _extract_board(html)

        states.append(
            {
                "state_id": state_id,
                "device_class": device_class,
                "state_name": state_name,
                "captured_at": captured.get("captured_at"),
                "source_updated_at": captured.get("source_updated_at"),
                "final_http_status": captured.get("final_http_status"),
                "viewport": captured.get("viewport"),
                "requested_url": captured.get("requested_url"),
                "final_url": captured.get("final_url"),
                "result_status": captured.get("result_status"),
                "page_title": page_title,
                "landmarks": landmarks,
                "controls": controls,
                "general_links": general_links,
                "viewport_geometry": viewport_geometry,
                "document_geometry": document_geometry,
                "list_no": _parse_list_no(captured.get("final_url") or ""),
                "download_references": download_references,
                "attachment_document_extensions": document_extensions,
                "board": board,
                "public_assets": captured.get("public_assets", []),
                "exceptions": captured.get("exceptions", []),
                "artifacts": artifacts,
            }
        )

    model["state_count"] = len(states)
    model["artifact_count"] = artifact_count
    model["provenance_manifest"] = provenance_manifest
    model["exception_queue"] = exception_queue
    model["states"] = states
    model["model_sha256"] = model_body_checksum(model)
    return model


def stable_dump(model: dict[str, Any]) -> str:
    body = {key: value for key, value in model.items() if key != "model_sha256"}
    return json.dumps(body, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def model_body_checksum(model: dict[str, Any]) -> str:
    return hashlib.sha256(stable_dump(model).encode("utf-8")).hexdigest()


def fixture_path_for(repo_root: Path, capture_root: Path) -> Path:
    ledger = json.loads((capture_root / "ledger.json").read_text(encoding="utf-8"))
    site_id = _require_safe_id(str(ledger.get("site_id")), "site_id")
    capture_id = _require_safe_id(capture_root.name, "capture_id")
    return repo_root / "data" / "official_clone_fixtures" / site_id / "g1" / capture_id / "clone-model.json"


def write_model(
    repo_root: Path,
    capture_root: Path,
    expected_site_id: str | None = None,
    expected_capture_id: str | None = None,
) -> Path:
    fixture_path = fixture_path_for(repo_root, capture_root)
    fixture_path.parent.mkdir(parents=True, exist_ok=True)
    fixture_path.write_text(
        stable_dump(build_reference_clone_model(repo_root, capture_root, expected_site_id, expected_capture_id)),
        encoding="utf-8",
        newline="\n",
    )
    return fixture_path


def check_model(
    repo_root: Path,
    capture_root: Path,
    expected_site_id: str | None = None,
    expected_capture_id: str | None = None,
) -> list[str]:
    fixture_path = fixture_path_for(repo_root, capture_root)
    if not fixture_path.is_file():
        return [f"fixture missing: {fixture_path}"]
    expected = stable_dump(build_reference_clone_model(repo_root, capture_root, expected_site_id, expected_capture_id))
    committed = fixture_path.read_text(encoding="utf-8")
    if committed != expected:
        return ["committed clone-model fixture does not match regenerated model"]
    return []


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if "--capture-root" not in args:
        print("usage: build_reference_clone_model.py --capture-root PATH [--check] [--expected-site-id SITE_ID] [--expected-capture-id CAPTURE_ID]")
        print("  identity (site_id/capture_id) is derived from the canonical capture path when the flags are omitted")
        return 2
    capture_root = Path(args[args.index("--capture-root") + 1])
    repo_root = Path.cwd()

    expected_site_id: str | None = None
    expected_capture_id: str | None = None
    if "--expected-site-id" in args:
        idx = args.index("--expected-site-id")
        expected_site_id = args[idx + 1]
    if "--expected-capture-id" in args:
        idx = args.index("--expected-capture-id")
        expected_capture_id = args[idx + 1]

    try:
        if "--check" in args:
            problems = check_model(repo_root, capture_root, expected_site_id, expected_capture_id)
            for problem in problems:
                print(f"REFERENCE_CLONE_MODEL_CHECK_FAIL: {problem}")
            if problems:
                return 2
            print("REFERENCE_CLONE_MODEL_OK")
            return 0
        fixture_path = write_model(repo_root, capture_root, expected_site_id, expected_capture_id)
        print(f"WROTE {fixture_path}")
        return 0
    except ReferenceCloneModelError as exc:
        print(f"REFERENCE_CLONE_MODEL_ERROR: {exc}")
        return 3


if __name__ == "__main__":
    raise SystemExit(main())
