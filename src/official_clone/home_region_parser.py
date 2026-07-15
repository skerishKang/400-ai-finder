"""Deterministic offline home-region segmentation from committed raw HTML.

Network-free. Wall-clock-free. Uses only stdlib html.parser.HTMLParser.

Fragment identity rule (canonical subtree serialization, not browser outerHTML):
  For each element node, emit UTF-8 lines in preorder:
    E|<tag>|<id or ->|<space-joined classes>|<k=v pairs sorted by key>
    T|<normalized whitespace text of this node only>
  Child nodes follow immediately. Closing markers are not emitted.
  fragment_sha256 = SHA-256 of the joined serialization with "\\n" separators
  and a trailing newline.

Visibility / variant:
  - local_variant: markers on the node alone
  - effective_variant / visibility / variant: ancestor-aware with precedence
    hidden > template > mobile > desktop
  - Token matching only (no substring false-positives like automobile)
"""

from __future__ import annotations

import hashlib
import re
from html.parser import HTMLParser
from typing import Any
from urllib.parse import urljoin, urlsplit


APPROVED_HOST = "bukgu.gwangju.kr"
APPROVED_SCHEME = "https"
APPROVED_PORT = 443
BASE_URL = "https://bukgu.gwangju.kr/"
VOID_TAGS = frozenset(
    {
        "area",
        "base",
        "br",
        "col",
        "embed",
        "hr",
        "img",
        "input",
        "link",
        "meta",
        "param",
        "source",
        "track",
        "wbr",
    }
)

# Exact class tokens (not substrings of larger tokens).
_MOBILE_CLASS_TOKENS = frozenset({"mobile", "mbl"})
_HIDDEN_CLASS_TOKENS = frozenset({"hidden", "hide"})
_TEMPLATE_CLASS_TOKENS = frozenset({"template"})
_MOBILE_ID_EXACT = frozenset({"mobile", "mbl"})
_TEMPLATE_ID_MARKERS = ("mw_temp",)  # documented id family substrings


class HomeRegionParseError(ValueError):
    """Controlled parse failure for home region segmentation."""


def _norm_ws(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip()


def _classes(attrs: dict[str, str]) -> list[str]:
    return [c for c in (attrs.get("class") or "").split() if c]


def _attr_map(attrs: list[tuple[str, str | None]]) -> dict[str, str]:
    out: dict[str, str] = {}
    for k, v in attrs:
        out[k] = v if v is not None else ""
    return out


def effective_port(scheme: str, port: int | None) -> int | None:
    """Canonical effective port for origin comparison."""
    if port is not None:
        return port
    s = (scheme or "").lower()
    if s == "https":
        return 443
    if s == "http":
        return 80
    return None


def is_same_origin_url(url: object) -> bool | None:
    """Exact same-origin vs https://bukgu.gwangju.kr:443.

    Returns:
      True  — same origin (including absolute https host:443 and relative /path, path, #frag)
      False — different origin or non-navigable scheme
      None  — empty/missing URL (field contract: unknown)

    Never raises ValueError for malformed ports/URLs.
    """
    if url is None:
        return None
    if not isinstance(url, str):
        return False
    if url == "":
        return None

    # Fragment-only references resolve against the page origin.
    if url.startswith("#"):
        return True

    # Non-HTTP navigational schemes are never same-origin page resources.
    lower = url.lower()
    if lower.startswith(("javascript:", "mailto:", "tel:", "data:")):
        return False

    # Scheme-relative must still parse as absolute with host.
    if url.startswith("//"):
        try:
            parts = urlsplit("https:" + url)
        except Exception:
            return False
        return _parts_are_approved_origin(parts)

    # Absolute path on this origin.
    if url.startswith("/"):
        return True

    # Absolute URL with scheme.
    if "://" in url:
        try:
            parts = urlsplit(url)
        except Exception:
            return False
        return _parts_are_approved_origin(parts)

    # Relative path/query without leading slash (e.g. menu.es?mid=a101).
    # Reject empty-looking or scheme-like garbage.
    if re.match(r"^[a-zA-Z][a-zA-Z0-9+.-]*:", url):
        # Unknown scheme
        return False
    return True


def _parts_are_approved_origin(parts: Any) -> bool:
    try:
        port = parts.port
    except ValueError:
        return False
    scheme = (parts.scheme or "").lower()
    if scheme != APPROVED_SCHEME:
        return False
    if parts.username is not None or parts.password is not None:
        return False
    host = (parts.hostname or "").lower()
    if host != APPROVED_HOST:
        return False
    if not parts.netloc:
        return False
    if effective_port(scheme, port) != APPROVED_PORT:
        return False
    return True


def resolve_url(href: str | None) -> str | None:
    if href is None or href == "":
        return href
    if href.startswith(("javascript:", "mailto:", "tel:", "data:")):
        return href
    if href.startswith("#"):
        return href
    return urljoin(BASE_URL, href)


class _Node:
    __slots__ = (
        "tag",
        "attrs",
        "children",
        "text_parts",
        "parent",
        "source_order",
        "start_index",
        "end_index",
    )

    def __init__(
        self,
        tag: str,
        attrs: dict[str, str],
        parent: _Node | None,
        source_order: int,
        start_index: int,
    ) -> None:
        self.tag = tag
        self.attrs = attrs
        self.children: list[_Node] = []
        self.text_parts: list[str] = []
        self.parent = parent
        self.source_order = source_order
        self.start_index = start_index
        self.end_index = start_index


class _DomBuilder(HTMLParser):
    def __init__(self, raw: str) -> None:
        super().__init__(convert_charrefs=True)
        self.raw = raw
        self.root = _Node("[document]", {}, None, -1, 0)
        self.stack: list[_Node] = [self.root]
        self.order = 0
        self._line_starts = self._compute_line_starts(raw)

    @staticmethod
    def _compute_line_starts(raw: str) -> list[int]:
        starts = [0]
        for i, ch in enumerate(raw):
            if ch == "\n":
                starts.append(i + 1)
        return starts

    def _abs_index(self) -> int:
        line, col = self.getpos()
        # HTMLParser lines are 1-based
        if line - 1 < len(self._line_starts):
            return self._line_starts[line - 1] + col
        return col

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        ad = _attr_map(attrs)
        node = _Node(tag.lower(), ad, self.stack[-1], self.order, self._abs_index())
        self.order += 1
        self.stack[-1].children.append(node)
        if tag.lower() not in VOID_TAGS:
            self.stack.append(node)
        else:
            node.end_index = self._abs_index()

    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self.handle_starttag(tag, attrs)

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        for i in range(len(self.stack) - 1, 0, -1):
            if self.stack[i].tag == tag:
                self.stack[i].end_index = self._abs_index()
                self.stack = self.stack[:i]
                return

    def handle_data(self, data: str) -> None:
        if self.stack:
            self.stack[-1].text_parts.append(data)


def parse_dom(raw_html: str) -> _Node:
    if not isinstance(raw_html, str) or not raw_html.strip():
        raise HomeRegionParseError("raw HTML is empty")
    if "<html" not in raw_html.lower():
        raise HomeRegionParseError("raw HTML missing html root marker")
    builder = _DomBuilder(raw_html)
    try:
        builder.feed(raw_html)
        builder.close()
    except HomeRegionParseError:
        raise
    except Exception as exc:  # pragma: no cover - defensive
        raise HomeRegionParseError(f"HTML parse failed: {exc}") from exc
    # Ensure document closed
    builder.root.end_index = len(raw_html)
    return builder.root


def walk(node: _Node) -> list[_Node]:
    out = [node]
    for child in node.children:
        # Script/style subtrees are not structural content for regions.
        if child.tag in ("script", "style"):
            continue
        out.extend(walk(child))
    return out


def node_text(node: _Node) -> str:
    if node.tag in ("script", "style"):
        return ""
    parts = ["".join(node.text_parts)]
    for child in node.children:
        if child.tag in ("script", "style"):
            continue
        parts.append(node_text(child))
    return _norm_ws("".join(parts))


def own_text(node: _Node) -> str:
    return _norm_ws("".join(node.text_parts))


def ancestor_path(node: _Node) -> list[str]:
    tags: list[str] = []
    cur: _Node | None = node
    while cur is not None and cur.tag != "[document]":
        tags.append(cur.tag)
        cur = cur.parent
    return list(reversed(tags))


def _local_variant_flags(node: _Node) -> set[str]:
    """Return local variant markers present on this node alone."""
    flags: set[str] = set()
    classes = {c.lower() for c in _classes(node.attrs)}
    style = (node.attrs.get("style") or "").lower().replace(" ", "")
    nid = (node.attrs.get("id") or "").lower()
    aria_hidden = (node.attrs.get("aria-hidden") or "").lower()

    # hidden
    if "hidden" in node.attrs:  # boolean HTML attribute present
        flags.add("hidden")
    if aria_hidden == "true":
        flags.add("hidden")
    if "display:none" in style or "visibility:hidden" in style:
        flags.add("hidden")
    if classes & _HIDDEN_CLASS_TOKENS:
        flags.add("hidden")
    # Collapsed site/language/menu panel: class "close" with site/language context.
    if "close" in classes and (
        "site" in classes
        or "language" in classes
        or "language" in nid
        or "menu" in classes
        or "gnb" in classes
    ):
        flags.add("hidden")

    # template
    if classes & _TEMPLATE_CLASS_TOKENS:
        flags.add("template")
    if any(marker in nid for marker in _TEMPLATE_ID_MARKERS):
        flags.add("template")
    if "template" in nid.split("-") or "template" in nid.split("_"):
        flags.add("template")

    # mobile — exact class tokens only
    if classes & _MOBILE_CLASS_TOKENS:
        flags.add("mobile")
    if nid in _MOBILE_ID_EXACT:
        flags.add("mobile")
    # id tokens split by -/_
    id_tokens = set(re.split(r"[-_]+", nid)) if nid else set()
    if id_tokens & _MOBILE_CLASS_TOKENS:
        flags.add("mobile")

    return flags


def _pick_variant(flags: set[str]) -> str:
    """Precedence: hidden > template > mobile > desktop."""
    if "hidden" in flags:
        return "hidden"
    if "template" in flags:
        return "template"
    if "mobile" in flags:
        return "mobile"
    return "desktop"


def infer_variant(node: _Node) -> str:
    """Local-only variant (node itself). Kept for compatibility."""
    return _pick_variant(_local_variant_flags(node))


def infer_effective_variant(node: _Node) -> str:
    """Ancestor-aware variant with precedence hidden > template > mobile > desktop."""
    flags: set[str] = set()
    cur: _Node | None = node
    while cur is not None and cur.tag != "[document]":
        flags |= _local_variant_flags(cur)
        cur = cur.parent
    return _pick_variant(flags)


def visibility_fields(node: _Node) -> dict[str, str]:
    local = infer_variant(node)
    effective = infer_effective_variant(node)
    return {
        "local_variant": local,
        "effective_variant": effective,
        # Renderer-facing fields use effective ancestor-aware state.
        "variant": effective,
        "visibility": effective,
    }


def serialize_subtree(node: _Node) -> str:
    """Canonical subtree serialization for fragment_sha256."""
    lines: list[str] = []

    def rec(n: _Node) -> None:
        if n.tag == "[document]":
            for c in n.children:
                rec(c)
            return
        nid = n.attrs.get("id") or "-"
        classes = " ".join(_classes(n.attrs))
        pairs = []
        for k in sorted(n.attrs.keys()):
            if k in ("id", "class"):
                continue
            pairs.append(f"{k}={n.attrs[k]}")
        lines.append(f"E|{n.tag}|{nid}|{classes}|{'&'.join(pairs)}")
        t = own_text(n)
        if t:
            lines.append(f"T|{t}")
        for c in n.children:
            rec(c)

    rec(node)
    return "\n".join(lines) + ("\n" if lines else "")


def fragment_sha256(node: _Node) -> str:
    payload = serialize_subtree(node).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def find_by_id(root: _Node, element_id: str) -> list[_Node]:
    return [n for n in walk(root) if n.attrs.get("id") == element_id]


def find_by_exact_class(root: _Node, class_name: str) -> list[_Node]:
    return [n for n in walk(root) if n.attrs.get("class") == class_name]


def find_by_class_token(root: _Node, token: str) -> list[_Node]:
    return [n for n in walk(root) if token in _classes(n.attrs)]


def _unique_or_error(nodes: list[_Node], label: str) -> _Node:
    if not nodes:
        raise HomeRegionParseError(f"{label}: no candidates")
    if len(nodes) > 1:
        raise HomeRegionParseError(
            f"{label}: multiple candidates without deterministic boundary ({len(nodes)})"
        )
    return nodes[0]


def _source_evidence(node: _Node, *, occurrence_count: int, variant: str | None = None) -> dict[str, Any]:
    local = infer_variant(node)
    effective = variant or infer_effective_variant(node)
    return {
        "tag": node.tag,
        "id": node.attrs.get("id") or None,
        "classes": _classes(node.attrs),
        "ancestor_path": ancestor_path(node),
        "source_order": node.source_order,
        "occurrence_count": occurrence_count,
        "local_variant": local,
        "effective_variant": effective,
        "variant": effective,
        "fragment_sha256": fragment_sha256(node),
        "hash_rule": "canonical_subtree_serialization_v1",
    }


def _anchor_primary_text(anchor: _Node) -> str:
    """Prefer exact title/label subtree text over flattened date+title mashups."""
    for n in walk(anchor):
        classes = _classes(n.attrs)
        if n.tag in ("strong", "span") and ("title" in classes or "label" in classes):
            # Drop accessibility-only "new" blind markers from title nodes.
            parts: list[str] = []
            for child in n.children:
                if child.tag == "span" and "blind" in _classes(child.attrs):
                    continue
                if child.tag == "i" and "new" in _classes(child.attrs):
                    continue
                parts.append(node_text(child) if child.children or child.text_parts else own_text(child))
            own = own_text(n)
            text = _norm_ws(" ".join([own] + [p for p in parts if p]))
            if text:
                return text
    return node_text(anchor)


def _link_items(node: _Node, *, item_prefix: str) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    order = 0
    for n in walk(node):
        if n.tag != "a":
            continue
        href = n.attrs.get("href")
        text = _anchor_primary_text(n)
        order += 1
        # Optional date sibling/descendant preserved separately when present.
        date_text = ""
        for d in walk(n):
            if d.tag == "span" and "date" in _classes(d.attrs):
                date_text = node_text(d)
                break
        item = {
            "item_id": f"{item_prefix}-{order:04d}",
            "order": order,
            "text": text,
            "date_text": date_text or None,
            "href": href,
            "resolved_url": resolve_url(href),
            "same_origin": is_same_origin_url(href if href else None),
            "dom_order": n.source_order,
            "title_attr": n.attrs.get("title") or "",
            "target": n.attrs.get("target") or "",
        }
        item.update(visibility_fields(n))
        items.append(item)
    return items


def _image_items(node: _Node, *, item_prefix: str, start_order: int = 0) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    order = start_order
    for n in walk(node):
        if n.tag != "img":
            continue
        order += 1
        src = n.attrs.get("src")
        item = {
            "item_id": f"{item_prefix}-img-{order:04d}",
            "order": order,
            "text": n.attrs.get("alt") or "",
            "href": None,
            "asset_url": src,
            "resolved_url": resolve_url(src),
            "same_origin": is_same_origin_url(src),
            "dom_order": n.source_order,
        }
        item.update(visibility_fields(n))
        items.append(item)
    return items


def segment_home_regions(raw_html: str) -> dict[str, Any]:
    """Return segmentation map for the six target regions (+ meta)."""
    root = parse_dom(raw_html)
    regions: dict[str, dict[str, Any]] = {}

    # ── utility_navigation: unique div.slidelist (top utilities) ──
    slides = find_by_exact_class(root, "slidelist")
    if len(slides) == 1:
        node = slides[0]
        groups = []
        for child in node.children:
            if child.tag == "div" and "group" in _classes(child.attrs):
                groups.append(
                    {
                        "group_classes": _classes(child.attrs),
                        "text": node_text(child),
                        "links": _link_items(child, item_prefix=f"util-{'-'.join(_classes(child.attrs))}"),
                    }
                )
        items = _link_items(node, item_prefix="utility")
        # Also record sitemap-btn if unique under header
        sitemap = find_by_exact_class(root, "sitemap-btn")
        extra_items = []
        if len(sitemap) == 1:
            extra_items = _link_items(sitemap[0], item_prefix="utility-sitemap")
            for it in extra_items:
                it["group"] = "sitemap-btn"
        combined = items + extra_items
        for i, it in enumerate(combined, start=1):
            it["order"] = i
            it["item_id"] = f"utility-{i:04d}"
        regions["utility_navigation"] = {
            "region_id": "utility_navigation",
            "status": "fixture-ready-renderer-not-wired",
            "reason": None,
            "candidate_count": 1,
            "source_evidence": _source_evidence(node, occurrence_count=1),
            "secondary_evidence": (
                [_source_evidence(sitemap[0], occurrence_count=1)] if len(sitemap) == 1 else []
            ),
            "items": combined,
            "groups": groups,
            "item_count": len(combined),
            "variant_counts": _count_variants(combined),
        }
    else:
        regions["utility_navigation"] = _unresolved(
            "utility_navigation",
            reason="multiple or zero slidelist candidates without deterministic boundary",
            candidate_count=len(slides),
        )

    # ── main_banner: unique div.visual ──
    visuals = [n for n in find_by_class_token(root, "visual") if n.tag == "div"]
    # Prefer exact class token-only visual container (not nested)
    visuals = [n for n in visuals if "visual" in _classes(n.attrs)]
    # Filter to top-level visual under contents01 if multiple
    if len(visuals) == 1:
        node = visuals[0]
        link_items = _link_items(node, item_prefix="banner")
        img_items = _image_items(node, item_prefix="banner", start_order=len(link_items))
        # controls text
        controls = []
        for n in walk(node):
            if "control" in " ".join(_classes(n.attrs)):
                controls.append(
                    {
                        "text": node_text(n),
                        "classes": _classes(n.attrs),
                        "dom_order": n.source_order,
                    }
                )
        regions["main_banner"] = {
            "region_id": "main_banner",
            "status": "fixture-ready-renderer-not-wired",
            "reason": None,
            "candidate_count": 1,
            "source_evidence": _source_evidence(node, occurrence_count=1),
            "items": link_items + img_items,
            "controls": controls,
            "item_count": len(link_items) + len(img_items),
            "variant_counts": _count_variants(link_items + img_items),
        }
    else:
        regions["main_banner"] = _unresolved(
            "main_banner",
            reason="multiple source candidates without deterministic boundary"
            if len(visuals) > 1
            else "no deterministic visual banner boundary",
            candidate_count=len(visuals),
        )

    # ── resident_service_shortcuts: #favorites.most-menu ──
    favorites = find_by_id(root, "favorites")
    if len(favorites) == 1 and "most-menu" in _classes(favorites[0].attrs):
        node = favorites[0]
        items = _link_items(node, item_prefix="shortcut")
        regions["resident_service_shortcuts"] = {
            "region_id": "resident_service_shortcuts",
            "status": "fixture-ready-renderer-not-wired",
            "reason": None,
            "candidate_count": 1,
            "source_evidence": _source_evidence(node, occurrence_count=1),
            "items": items,
            "item_count": len(items),
            "variant_counts": _count_variants(items),
        }
    else:
        regions["resident_service_shortcuts"] = _unresolved(
            "resident_service_shortcuts",
            reason="favorites/most-menu boundary not uniquely present",
            candidate_count=len(favorites),
        )

    # ── notice_news: unique div.board under contents02 ──
    boards = find_by_exact_class(root, "board")
    if len(boards) == 1:
        node = boards[0]
        # Articles may nest under intermediate wrappers; collect in DOM order.
        articles = [n for n in walk(node) if n.tag == "article"]
        groups = []
        items: list[dict[str, Any]] = []
        for idx, art in enumerate(articles, start=1):
            label = ""
            for n in walk(art):
                if n.tag == "strong" and "label" in _classes(n.attrs):
                    label = node_text(n)
                    break
            art_links = _link_items(art, item_prefix=f"notice-g{idx}")
            for it in art_links:
                it["group"] = label
                it["group_order"] = idx
            groups.append(
                {
                    "order": idx,
                    "label": label,
                    "classes": _classes(art.attrs),
                    "item_count": len(art_links),
                    "dom_order": art.source_order,
                }
            )
            items.extend(art_links)
        regions["notice_news"] = {
            "region_id": "notice_news",
            "status": "fixture-ready-renderer-not-wired",
            "reason": None,
            "candidate_count": 1,
            "source_evidence": _source_evidence(node, occurrence_count=1),
            "groups": groups,
            "items": items,
            "item_count": len(items),
            "variant_counts": _count_variants(items),
        }
    else:
        regions["notice_news"] = _unresolved(
            "notice_news",
            reason="multiple or zero board candidates without deterministic boundary",
            candidate_count=len(boards),
        )

    # ── related_site_controls: unique class token family-site ──
    families = find_by_class_token(root, "family-site")
    if len(families) == 1:
        node = families[0]
        heading = ""
        for n in walk(node):
            if n.tag in ("h2", "h3"):
                heading = node_text(n)
                break
        items = _link_items(node, item_prefix="related")
        regions["related_site_controls"] = {
            "region_id": "related_site_controls",
            "status": "fixture-ready-renderer-not-wired",
            "reason": None,
            "candidate_count": 1,
            "source_evidence": _source_evidence(node, occurrence_count=1),
            "heading": heading,
            "items": items,
            "item_count": len(items),
            "variant_counts": _count_variants(items),
        }
    else:
        regions["related_site_controls"] = _unresolved(
            "related_site_controls",
            reason="multiple or zero family-site candidates without deterministic boundary",
            candidate_count=len(families),
        )

    # ── footer_identity_contact: unique div.address + sibling p.copyright ──
    addresses = find_by_exact_class(root, "address")
    copyrights = find_by_exact_class(root, "copyright")
    if len(addresses) == 1:
        addr = addresses[0]
        items: list[dict[str, Any]] = []
        # address block text + tel links
        addr_item = {
            "item_id": "footer-identity-0001",
            "order": 1,
            "text": node_text(addr),
            "href": None,
            "resolved_url": None,
            "same_origin": None,
            "dom_order": addr.source_order,
            "kind": "address_block",
        }
        addr_item.update(visibility_fields(addr))
        items.append(addr_item)
        for it in _link_items(addr, item_prefix="footer-identity-tel"):
            it["kind"] = "contact_link"
            items.append(it)
        secondary = []
        if len(copyrights) == 1:
            cp = copyrights[0]
            secondary.append(_source_evidence(cp, occurrence_count=1))
            cp_item = {
                "item_id": "footer-identity-copyright",
                "order": len(items) + 1,
                "text": node_text(cp),
                "href": None,
                "resolved_url": None,
                "same_origin": None,
                "dom_order": cp.source_order,
                "kind": "copyright",
            }
            cp_item.update(visibility_fields(cp))
            items.append(cp_item)
        # foot-link legal links if unique
        foot_links = find_by_exact_class(root, "foot-link")
        if len(foot_links) == 1:
            secondary.append(_source_evidence(foot_links[0], occurrence_count=1))
            for it in _link_items(foot_links[0], item_prefix="footer-identity-legal"):
                it["kind"] = "legal_link"
                items.append(it)
        # renumber order
        for i, it in enumerate(items, start=1):
            it["order"] = i
        regions["footer_identity_contact"] = {
            "region_id": "footer_identity_contact",
            "status": "fixture-ready-renderer-not-wired",
            "reason": None,
            "candidate_count": 1,
            "source_evidence": _source_evidence(addr, occurrence_count=1),
            "secondary_evidence": secondary,
            "items": items,
            "item_count": len(items),
            "variant_counts": _count_variants(items),
        }
    else:
        regions["footer_identity_contact"] = _unresolved(
            "footer_identity_contact",
            reason="footer identity/contact boundary not unique",
            candidate_count=len(addresses),
        )

    # Normalize item order / ids within each region for stable consumers.
    for region in regions.values():
        items = list(region.get("items") or [])
        prefix = region.get("region_id") or "item"
        for i, it in enumerate(items, start=1):
            it["order"] = i
            if not str(it.get("item_id") or "").startswith(prefix):
                it["item_id"] = f"{prefix}-{i:04d}"
            else:
                # Keep kind suffix if already region-prefixed; still enforce unique order.
                it["item_id"] = f"{prefix}-{i:04d}"
        region["items"] = items
        region["item_count"] = len(items)

    # Integrity: every item text/href must appear in raw when non-empty
    _assert_items_in_source(raw_html, regions)

    ready = sum(
        1 for r in regions.values() if r.get("status") == "fixture-ready-renderer-not-wired"
    )
    unresolved = sum(1 for r in regions.values() if r.get("status") == "unresolved")
    return {
        "parser_id": "src/official_clone/home_region_parser.py",
        "parser_version": "1.0.0",
        "hash_rule": "canonical_subtree_serialization_v1",
        "regions": regions,
        "counts": {
            "target_regions": len(regions),
            "fixture_ready": ready,
            "unresolved": unresolved,
        },
    }


def _count_variants(items: list[dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {
        "desktop": 0,
        "mobile": 0,
        "hidden": 0,
        "template": 0,
        "unknown": 0,
    }
    for it in items:
        v = (
            it.get("effective_variant")
            or it.get("variant")
            or it.get("visibility")
            or "unknown"
        )
        if v not in counts:
            counts[v] = 0
        counts[v] += 1
    return counts


def _unresolved(region_id: str, *, reason: str, candidate_count: int) -> dict[str, Any]:
    return {
        "region_id": region_id,
        "status": "unresolved",
        "reason": reason,
        "candidate_count": candidate_count,
        "source_evidence": {
            "status": "unresolved",
            "reason": reason,
            "candidate_count": candidate_count,
        },
        "items": [],
        "item_count": 0,
        "variant_counts": {
            "desktop": 0,
            "mobile": 0,
            "hidden": 0,
            "template": 0,
            "unknown": 0,
        },
    }


def _plain_text_from_html(raw_html: str) -> str:
    """Tag-stripped source text for fidelity checks across <br> etc."""
    import html as html_lib

    plain = re.sub(r"(?is)<script[^>]*>.*?</script>", " ", raw_html)
    plain = re.sub(r"(?is)<style[^>]*>.*?</style>", " ", plain)
    plain = re.sub(r"(?i)<br\s*/?>", "\n", plain)
    plain = re.sub(r"<[^>]+>", " ", plain)
    # Match HTMLParser(convert_charrefs=True) text extraction.
    plain = html_lib.unescape(plain)
    return plain


def _text_present_in_source(text: str, raw_html: str) -> bool:
    if not text:
        return True
    if text in raw_html:
        return True
    plain = _plain_text_from_html(raw_html)
    if text in plain:
        return True
    # Labels joined across inline tags / br without requiring identical spacing.
    compact_text = re.sub(r"\s+", "", text)
    compact_plain = re.sub(r"\s+", "", plain)
    return bool(compact_text) and compact_text in compact_plain


def _attr_value_present_in_source(value: str, raw_html: str) -> bool:
    """Href/src may appear raw or HTML-escaped (&amp; etc.)."""
    import html as html_lib

    if not value:
        return True
    if value in raw_html:
        return True
    # Common attribute escaping in committed capture HTML.
    escaped = (
        value.replace("&", "&amp;")
        .replace('"', "&quot;")
        .replace("'", "&#39;")
        .replace("<", "&lt;")
    )
    if escaped in raw_html:
        return True
    # Unescape raw and search.
    if value in html_lib.unescape(raw_html):
        return True
    return False


def _assert_items_in_source(raw_html: str, regions: dict[str, dict[str, Any]]) -> None:
    for region in regions.values():
        if region.get("status") == "unresolved":
            continue
        for item in region.get("items") or []:
            text = item.get("text") or ""
            href = item.get("href")
            asset_url = item.get("asset_url")
            if text and not _text_present_in_source(text, raw_html):
                raise HomeRegionParseError(
                    f"item text not found in raw HTML: {text[:80]!r}"
                )
            if href and not _attr_value_present_in_source(str(href), raw_html):
                raise HomeRegionParseError(
                    f"item href not found in raw HTML: {href!r}"
                )
            if asset_url and not _attr_value_present_in_source(str(asset_url), raw_html):
                raise HomeRegionParseError(
                    f"item asset_url not found in raw HTML: {asset_url!r}"
                )
