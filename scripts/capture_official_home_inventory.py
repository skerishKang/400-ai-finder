#!/usr/bin/env python3
"""One-shot read-only capture of the official Buk-gu homepage inventory (#1160).

Allowed: public HTTPS GET of official homepage and bounded same-origin asset probes.
Forbidden: Firecrawl, provider APIs, login, form submission, payment, PII.
This script is operator-run for capture only; routine tests must not execute it
against the live network (mocked pure-function paths are unit-tested offline).
"""

from __future__ import annotations

import hashlib
import json
import re
import ssl
import urllib.error
import urllib.parse
import urllib.request
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from html.parser import HTMLParser
from pathlib import Path
from typing import Any, Callable

REQUESTED = "https://bukgu.gwangju.kr/"
APPROVED_HOST = "bukgu.gwangju.kr"
KST = timezone(timedelta(hours=9))
ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "official_captures" / "bukgu_gwangju" / "home"
PROBE_LIMIT = 40
PARTIAL_HASH_LIMIT = 65536
MAX_REDIRECT_HOPS = 10
UA = "400-ai-finder-official-capture/1.0 (read-only inventory; no auth)"
REDACTED_CSRF = "[REDACTED_SESSION_CSRF]"
SANITIZATION_NOTES = [
    "normalize_crlf_and_cr_to_lf",
    "expand_tabs_to_spaces",
    "strip_trailing_whitespace_per_line",
    "redact_session_csrf_meta_and_input_values",
]

REDIRECT_STATUSES = frozenset({301, 302, 303, 307, 308})


class CaptureError(RuntimeError):
    """Raised for invalid redirects or policy violations during capture."""


# ── Origin policy ──────────────────────────────────────────────────


def is_approved_bukgu_https_url(url: str) -> bool:
    """Exact official-origin validation (no startswith host tricks)."""
    if not isinstance(url, str) or not url:
        return False
    try:
        parts = urllib.parse.urlsplit(url)
    except Exception:
        return False
    if parts.scheme.lower() != "https":
        return False
    if parts.username is not None or parts.password is not None:
        return False
    host = (parts.hostname or "").lower()
    if host != APPROVED_HOST:
        return False
    if parts.port not in (None, 443):
        return False
    return True


def origin_of(url: str) -> str | None:
    try:
        p = urllib.parse.urlsplit(url)
        if p.scheme in ("http", "https") and p.hostname:
            port = f":{p.port}" if p.port and p.port not in (80, 443) else ""
            return f"{p.scheme}://{p.hostname.lower()}{port}"
    except Exception:
        return None
    return None


# ── Sanitization (canonical committed bytes) ───────────────────────


def sanitize_public_html(html_text: str) -> str:
    """Deterministic public-safe HTML normalization for committed raw snapshot.

    Ordered operations:
    1. normalize CRLF and CR to LF
    2. expand tabs to spaces
    3. strip trailing whitespace per line
    4. redact session-bound _csrf meta/input values
    5. end with exactly one final LF
    """
    if not isinstance(html_text, str):
        raise TypeError("html_text must be str")
    text = html_text.replace("\r\n", "\n").replace("\r", "\n")
    text = text.expandtabs(4)
    lines = [ln.rstrip(" \t") for ln in text.split("\n")]
    text = "\n".join(lines)
    # meta name="_csrf" content="..."
    text = re.sub(
        r'(<meta\b[^>]*\bname\s*=\s*["_\']?_csrf["\']?[^>]*\bcontent\s*=\s*")[^"]*(")',
        rf"\1{REDACTED_CSRF}\2",
        text,
        flags=re.I,
    )
    text = re.sub(
        r'(<meta\b[^>]*\bcontent\s*=\s*")[^"]*("[^>]*\bname\s*=\s*["_\']?_csrf["\']?)',
        rf"\1{REDACTED_CSRF}\2",
        text,
        flags=re.I,
    )
    # hidden inputs name="_csrf" value="..."
    text = re.sub(
        r'(<input\b[^>]*\bname\s*=\s*["_\']?_csrf["\']?[^>]*\bvalue\s*=\s*")[^"]*(")',
        rf"\1{REDACTED_CSRF}\2",
        text,
        flags=re.I,
    )
    text = re.sub(
        r'(<input\b[^>]*\bvalue\s*=\s*")[^"]*("[^>]*\bname\s*=\s*["_\']?_csrf["\']?)',
        rf"\1{REDACTED_CSRF}\2",
        text,
        flags=re.I,
    )
    text = text.rstrip("\n") + "\n"
    return text


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def metadata_checksum(meta: dict[str, Any]) -> str:
    body = {k: v for k, v in meta.items() if k != "metadata_sha256"}
    payload = json.dumps(body, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode(
        "utf-8"
    )
    return sha256_bytes(payload)


# ── Redirect-aware HTTP ────────────────────────────────────────────


class NoFollowRedirectHandler(urllib.request.HTTPRedirectHandler):
    """Return redirect responses instead of following them automatically."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):  # noqa: ANN001
        return None


def build_capture_opener(context: ssl.SSLContext | None = None) -> urllib.request.OpenerDirector:
    handlers: list[Any] = [NoFollowRedirectHandler()]
    if context is not None:
        handlers.append(urllib.request.HTTPSHandler(context=context))
    else:
        handlers.append(urllib.request.HTTPSHandler())
    handlers.append(urllib.request.HTTPHandler())
    return urllib.request.build_opener(*handlers)


def _validate_redirect_target(location: str, base_url: str) -> str:
    if not location:
        raise CaptureError("redirect response missing Location header")
    resolved = urllib.parse.urljoin(base_url, location)
    if resolved.startswith("//"):
        raise CaptureError("protocol-relative redirect rejected")
    if not is_approved_bukgu_https_url(resolved):
        raise CaptureError(f"redirect target not approved official HTTPS origin: {resolved}")
    return resolved


def fetch_with_redirect_recording(
    start_url: str,
    *,
    opener: urllib.request.OpenerDirector,
    headers: dict[str, str] | None = None,
    timeout: float = 45,
    max_hops: int = MAX_REDIRECT_HOPS,
    read_body: bool = True,
) -> dict[str, Any]:
    """Manually walk redirects; record every hop; return final body when 2xx."""
    if not is_approved_bukgu_https_url(start_url):
        raise CaptureError(f"start URL not approved official HTTPS origin: {start_url}")

    chain: list[dict[str, Any]] = []
    url = start_url
    seen: set[str] = set()
    hdrs = {
        "User-Agent": UA,
        "Accept": "*/*",
        **(headers or {}),
    }

    for _ in range(max_hops + 1):
        if url in seen:
            raise CaptureError(f"redirect loop detected at {url}")
        seen.add(url)
        req = urllib.request.Request(url, method="GET", headers=hdrs)
        try:
            resp = opener.open(req, timeout=timeout)
            status = getattr(resp, "status", None) or resp.getcode()
            resp_headers = {k.lower(): v for k, v in resp.headers.items()}
            loc = resp.headers.get("Location")
            chain.append({"url": url, "status": status, "location": loc})
            if status in REDIRECT_STATUSES:
                url = _validate_redirect_target(loc or "", url)
                continue
            body = resp.read() if read_body else b""
            final_url = resp.geturl() if hasattr(resp, "geturl") else url
            if not is_approved_bukgu_https_url(final_url):
                # geturl may still be start; prefer last chain url
                final_url = url
            return {
                "final_url": final_url,
                "status": status,
                "headers": resp_headers,
                "body": body,
                "redirect_chain": chain,
                "redirected": len(chain) > 1,
            }
        except urllib.error.HTTPError as exc:
            status = exc.code
            resp_headers = {k.lower(): v for k, v in exc.headers.items()} if exc.headers else {}
            loc = exc.headers.get("Location") if exc.headers else None
            chain.append({"url": url, "status": status, "location": loc})
            if status in REDIRECT_STATUSES:
                url = _validate_redirect_target(loc or "", url)
                continue
            body = exc.read() if read_body else b""
            return {
                "final_url": url,
                "status": status,
                "headers": resp_headers,
                "body": body,
                "redirect_chain": chain,
                "redirected": len(chain) > 1,
            }
    raise CaptureError(f"exceeded max redirect hops ({max_hops})")


# ── HTML inventory parser ──────────────────────────────────────────


def _section_label(tag: str, tid: str) -> str:
    if "util" in tid or "top" in tid:
        return "utility"
    if "gnb" in tid or "global" in tid or "main-menu" in tid:
        return "global_nav"
    if tag == "footer" or "footer" in tid:
        return "footer"
    if any(x in tid for x in ("banner", "visual", "slide", "carousel")):
        return "banner"
    if any(x in tid for x in ("quick", "service", "shortcut")):
        return "service_shortcuts"
    if any(x in tid for x in ("notice", "news", "board")):
        return "notices_news"
    if tag == "header":
        return "header"
    if tag == "nav":
        return "nav"
    if tag == "main":
        return "main"
    return tag


class InventoryParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.links: list[dict[str, Any]] = []
        self.assets: list[dict[str, Any]] = []
        self.hierarchy_events: list[dict[str, Any]] = []
        self._section_stack: list[str] = ["document"]
        self._in_a = False
        self._a_attrs: dict[str, str] = {}
        self._a_text: list[str] = []
        self._a_img_alts: list[str] = []
        self._a_depth = 0

    @property
    def current_section(self) -> str:
        return self._section_stack[-1]

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        ad = {k: (v or "") for k, v in attrs}
        tid = f"{ad.get('id', '')} {ad.get('class', '')}".lower()
        if tag in ("header", "nav", "footer", "main", "aside", "section"):
            label = _section_label(tag, tid)
            self._section_stack.append(label)
            self.hierarchy_events.append(
                {
                    "event": "enter",
                    "section": label,
                    "tag": tag,
                    "id": ad.get("id", ""),
                    "class": ad.get("class", ""),
                    "depth": len(self._section_stack) - 1,
                }
            )
        if tag == "a":
            self._in_a = True
            self._a_attrs = ad
            self._a_text = []
            self._a_img_alts = []
            self._a_depth = len(self._section_stack) - 1
        if self._in_a and tag == "img":
            alt = (ad.get("alt") or "").strip()
            if alt:
                self._a_img_alts.append(alt)
        if tag == "link" and ad.get("href"):
            rel = ad.get("rel", "").lower()
            kind = "css" if "stylesheet" in rel else ("favicon" if "icon" in rel else "link")
            self.assets.append(
                {
                    "tag": tag,
                    "type": kind,
                    "source_url": ad["href"],
                    "rel": rel,
                    "section": self.current_section,
                    "ancestor_sections": list(self._section_stack),
                }
            )
        if tag == "script" and ad.get("src"):
            self.assets.append(
                {
                    "tag": tag,
                    "type": "javascript",
                    "source_url": ad["src"],
                    "section": self.current_section,
                    "ancestor_sections": list(self._section_stack),
                }
            )
        if tag == "img" and ad.get("src"):
            self.assets.append(
                {
                    "tag": tag,
                    "type": "image",
                    "source_url": ad["src"],
                    "alt": ad.get("alt", ""),
                    "section": self.current_section,
                    "ancestor_sections": list(self._section_stack),
                }
            )
        if tag in ("source", "video") and ad.get("src"):
            self.assets.append(
                {
                    "tag": tag,
                    "type": "video" if tag == "video" else "media",
                    "source_url": ad["src"],
                    "section": self.current_section,
                    "ancestor_sections": list(self._section_stack),
                }
            )
        if tag == "input" and ad.get("type") == "image" and ad.get("src"):
            self.assets.append(
                {
                    "tag": tag,
                    "type": "image",
                    "source_url": ad["src"],
                    "section": self.current_section,
                    "ancestor_sections": list(self._section_stack),
                }
            )

    def handle_endtag(self, tag: str) -> None:
        if tag == "a" and self._in_a:
            visible = re.sub(r"\s+", " ", "".join(self._a_text)).strip()
            aria = (self._a_attrs.get("aria-label") or "").strip()
            title = (self._a_attrs.get("title") or "").strip()
            img_alt = self._a_img_alts[0] if self._a_img_alts else ""
            if visible:
                label, source, absence = visible, "visible_text", None
            elif aria:
                label, source, absence = aria, "aria-label", None
            elif title:
                label, source, absence = title, "title", None
            elif img_alt:
                label, source, absence = img_alt, "child_image_alt", None
            else:
                label, source, absence = "", "absent", "no_visible_text_aria_title_or_img_alt"
            ancestors = list(self._section_stack)
            self.links.append(
                {
                    "visible_label": label,
                    "label_source": source,
                    "label_absence_reason": absence,
                    "source_url": self._a_attrs.get("href", ""),
                    "title_attr": title,
                    "target": self._a_attrs.get("target", ""),
                    "section": self.current_section,
                    "ancestor_sections": ancestors,
                    "hierarchy_depth": self._a_depth,
                    "link_type": "anchor",
                }
            )
            self._in_a = False
            self._a_attrs = {}
            self._a_text = []
            self._a_img_alts = []
        if tag in ("header", "nav", "footer", "main", "aside", "section") and len(
            self._section_stack
        ) > 1:
            left = self._section_stack.pop()
            self.hierarchy_events.append(
                {
                    "event": "leave",
                    "section": left,
                    "tag": tag,
                    "depth": len(self._section_stack) - 1,
                }
            )

    def handle_data(self, data: str) -> None:
        if self._in_a:
            self._a_text.append(data)


def absolutize(url: str, base: str) -> str:
    if not url or url.startswith(("javascript:", "mailto:", "tel:", "#", "data:")):
        return url
    if url.startswith("//"):
        return "https:" + url
    return urllib.parse.urljoin(base, url)


def build_top_level_hierarchy(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Collapse enter events into ordered top-level official containers."""
    preferred = (
        "utility",
        "header",
        "global_nav",
        "nav",
        "banner",
        "main",
        "service_shortcuts",
        "notices_news",
        "footer",
    )
    seen: set[str] = set()
    out: list[dict[str, Any]] = []
    order = 0
    for ev in events:
        if ev.get("event") != "enter":
            continue
        section = ev.get("section") or ""
        if section in ("document", "section", "aside"):
            continue
        if section not in preferred and section not in (
            "header",
            "nav",
            "footer",
            "main",
            "utility",
            "global_nav",
            "banner",
            "service_shortcuts",
            "notices_news",
        ):
            continue
        key = section
        if key in seen:
            continue
        seen.add(key)
        order += 1
        out.append(
            {
                "order": order,
                "section": section,
                "tag": ev.get("tag"),
                "id": ev.get("id") or "",
                "class": ev.get("class") or "",
            }
        )
    return out


def parse_homepage_inventories(html_text: str, final_url: str) -> dict[str, Any]:
    parser = InventoryParser()
    parser.feed(html_text)
    hierarchy = build_top_level_hierarchy(parser.hierarchy_events)

    nav_items: list[dict[str, Any]] = []
    for i, link in enumerate(parser.links):
        src = link["source_url"]
        abs_u = absolutize(src, final_url)
        same: bool | None
        if abs_u.startswith("http"):
            same = is_approved_bukgu_https_url(abs_u)
        elif abs_u.startswith("#"):
            same = True
        elif abs_u.startswith(("javascript:", "mailto:", "tel:", "data:")):
            same = False
        else:
            same = None
        nav_items.append(
            {
                "order": i + 1,
                "section": link["section"],
                "visible_label": link["visible_label"],
                "label_source": link["label_source"],
                "label_absence_reason": link["label_absence_reason"],
                "ancestor_sections": link["ancestor_sections"],
                "hierarchy_depth": link["hierarchy_depth"],
                "source_url": src,
                "resolved_url": abs_u,
                "same_origin": same,
                "link_type": link["link_type"],
                "title_attr": link["title_attr"],
                "target": link["target"],
                "capture_result": "recorded",
            }
        )

    seen: set[str] = set()
    asset_items: list[dict[str, Any]] = []
    for a in parser.assets:
        src = a["source_url"]
        abs_u = absolutize(src, final_url)
        if abs_u in seen:
            continue
        seen.add(abs_u)
        same = is_approved_bukgu_https_url(abs_u) if abs_u.startswith("http") else None
        asset_items.append(
            {
                "source_url": src,
                "requested_url": abs_u,
                "resolved_url": abs_u,
                "asset_type": a["type"],
                "tag": a["tag"],
                "section": a.get("section"),
                "ancestor_sections": a.get("ancestor_sections"),
                "alt": a.get("alt"),
                "same_origin": same,
                "redirected": False,
                "redirect_chain": [],
                "response_status": None,
                "content_type": None,
                "size_bytes": None,
                "sha256": None,
                "hash_scope": None,
                "hashed_byte_count": None,
                "capture_result": "listed",
                "failure_reason": None,
                "local_copy_recommendation": (
                    "defer_until_exact_integration" if same else "do_not_localize_external"
                ),
                "licensing_note": (
                    "public official portal asset; verify reuse on integration"
                    if same
                    else "external asset; do not copy without review"
                ),
            }
        )

    return {
        "nav_items": nav_items,
        "asset_items": asset_items,
        "hierarchy": hierarchy,
        "hierarchy_events": parser.hierarchy_events,
    }


# ── Asset probing ──────────────────────────────────────────────────


FetchFn = Callable[[str], dict[str, Any]]


def probe_asset_items(
    asset_items: list[dict[str, Any]],
    *,
    fetch_fn: FetchFn,
    probe_limit: int = PROBE_LIMIT,
) -> int:
    """Probe approved same-origin HTTPS assets only; record partial-hash scope."""
    probed = 0
    for item in asset_items:
        req_url = item.get("requested_url") or item.get("resolved_url") or ""
        if not req_url.startswith("http"):
            item["capture_result"] = "skipped_non_http"
            item["failure_reason"] = "non_http_url"
            continue
        if not is_approved_bukgu_https_url(req_url):
            # Record external without fetching
            item["same_origin"] = False
            item["capture_result"] = "listed_external_unfetched"
            item["failure_reason"] = "external_or_unapproved_origin_not_fetched"
            continue
        if probed >= probe_limit:
            item["capture_result"] = "listed_unprobed"
            item["failure_reason"] = "probe_budget_exceeded"
            continue
        try:
            result = fetch_fn(req_url)
            chain = result.get("redirect_chain") or []
            final_url = result.get("final_url") or req_url
            status = result.get("status")
            headers = result.get("headers") or {}
            body = result.get("body") or b""
            item["redirect_chain"] = chain
            item["redirected"] = bool(result.get("redirected")) or len(chain) > 1
            item["resolved_url"] = final_url
            item["response_status"] = status
            item["content_type"] = headers.get("content-type")
            item["same_origin"] = is_approved_bukgu_https_url(final_url)
            if not item["same_origin"]:
                item["capture_result"] = "redirected_off_origin_unhashed"
                item["failure_reason"] = "final_url_not_approved_origin"
                item["sha256"] = None
                item["hash_scope"] = None
                item["hashed_byte_count"] = 0
                probed += 1
                continue
            if status and int(status) >= 400:
                item["capture_result"] = "http_error"
                item["failure_reason"] = f"HTTP {status}"
                probed += 1
                continue
            hashed = body[:PARTIAL_HASH_LIMIT]
            item["hashed_byte_count"] = len(hashed)
            item["hash_scope"] = "first_65536_bytes"
            cl = headers.get("content-length")
            item["size_bytes"] = int(cl) if cl and str(cl).isdigit() else None
            if hashed:
                item["sha256"] = sha256_bytes(hashed)
                item["capture_result"] = "partial_body_hashed"
            else:
                item["sha256"] = None
                item["capture_result"] = "headers_only"
            probed += 1
        except CaptureError as ex:
            item["capture_result"] = "probe_policy_failed"
            item["failure_reason"] = str(ex)[:200]
            probed += 1
        except Exception as ex:  # noqa: BLE001 — inventory records probe failures
            item["capture_result"] = "probe_failed"
            item["failure_reason"] = f"{type(ex).__name__}: {str(ex)[:200]}"
            probed += 1
    return probed


# ── Bundle writer ──────────────────────────────────────────────────


def extract_page_title(html_text: str) -> str:
    title_m = re.search(r"<title[^>]*>(.*?)</title>", html_text, re.I | re.S)
    return re.sub(r"\s+", " ", title_m.group(1)).strip() if title_m else ""


def extract_source_updated_at(html_text: str) -> tuple[str | None, str | None]:
    for pattern in (
        r"최종\s*수정\s*일\s*[:：]?\s*([0-9]{4}[./-][0-9]{1,2}[./-][0-9]{1,2})",
        r"업데이트\s*[:：]?\s*([0-9]{4}[./-][0-9]{1,2}[./-][0-9]{1,2})",
        r"작성일\s*[:：]?\s*([0-9]{4}[./-][0-9]{1,2}[./-][0-9]{1,2})",
    ):
        um = re.search(pattern, html_text)
        if um:
            return um.group(1), None
    return None, "not-shown-on-homepage-html"


def build_capture_notes(
    *,
    requested_url: str,
    final_url: str,
    status: int | None,
    content_type: str,
    enc: str,
    page_title: str,
    captured_at: str,
    source_updated_display: str,
    raw_sha: str,
    meta_sha: str,
    redirect_chain: list[dict[str, Any]],
    nav_count: int,
    sec_counts: dict[str, int],
    hierarchy: list[dict[str, Any]],
    asset_count: int,
    type_counts: dict[str, int],
    same_c: int,
    ext_c: int,
    miss_c: int,
    blank_label_count: int,
    partial_hash_count: int,
) -> str:
    hierarchy_lines = "\n".join(
        f"- {h['order']}. {h['section']} ({h.get('tag') or 'container'})" for h in hierarchy
    ) or "- (none observed)"
    return f"""# Official home-route source inventory (capture-only)

Issue: #1160
Parent: #1080
Status: **capture_only** — not integrated into civic canvas; route remains `capture_required`.

## Source

- Requested URL: `{requested_url}`
- Final resolved URL: `{final_url}`
- HTTP status: `{status}`
- Content-Type: `{content_type}`
- Encoding: `{enc}`
- Official page title: `{page_title}`
- Captured at: `{captured_at}`
- Source-visible update date: `{source_updated_display}`
- Raw SHA-256: `{raw_sha}`
- Metadata SHA-256: `{meta_sha}`

## Redirect chain

```json
{json.dumps(redirect_chain, ensure_ascii=False, indent=2)}
```

## Inventory counts

- Navigation items: {nav_count}
- Blank labels (with explicit absence reason): {blank_label_count}
- Section counts: {dict(sorted(sec_counts.items()))}
- Assets listed: {asset_count}
- Asset type counts: {dict(sorted(type_counts.items()))}
- Same-origin assets: {same_c}
- External assets: {ext_c}
- Missing/failed probes: {miss_c}
- Partial-hash assets: {partial_hash_count}

## Hierarchy (observed order)

{hierarchy_lines}

## Method

Read-only Python `urllib` GET of the public homepage with manual redirect
recording and bounded approved same-origin asset probes.
No Firecrawl, provider API, login, form submission, payment, or PII.

## Sanitization

1. normalize CRLF and CR to LF
2. expand tabs to spaces
3. strip trailing whitespace per line
4. redact all session-bound `_csrf` meta/input values to `{REDACTED_CSRF}`

Checksums and byte lengths are computed from the sanitized committed bytes only.

## Non-integration

This capture does **not**:

- change `home` route rendering
- change manifest status from `capture_required` to `exact`
- localize assets into `src/web/static`
- execute any official-site write action
"""


def write_capture_bundle(
    out_dir: Path,
    *,
    requested_url: str,
    final_url: str,
    status: int | None,
    content_type: str,
    character_encoding: str,
    redirect_chain: list[dict[str, Any]],
    sanitized_html: str,
    captured_at: str,
    capture_finished_at: str,
    nav_items: list[dict[str, Any]],
    asset_items: list[dict[str, Any]],
    hierarchy: list[dict[str, Any]],
    probed_count: int,
    source_updated_at: str | None,
    source_updated_at_absence_reason: str | None,
) -> dict[str, Any]:
    out_dir.mkdir(parents=True, exist_ok=True)
    raw_bytes = sanitized_html.encode("utf-8")
    raw_sha = sha256_bytes(raw_bytes)
    page_title = extract_page_title(sanitized_html)

    (out_dir / "raw-homepage.html").write_bytes(raw_bytes)

    sec_counts: dict[str, int] = defaultdict(int)
    blank_label_count = 0
    for n in nav_items:
        sec_counts[n["section"]] += 1
        if not n.get("visible_label"):
            blank_label_count += 1

    type_counts: dict[str, int] = defaultdict(int)
    same_c = ext_c = miss_c = partial_hash_count = redirected_asset_count = 0
    for a in asset_items:
        type_counts[a["asset_type"]] += 1
        if a.get("same_origin") is True:
            same_c += 1
        elif a.get("same_origin") is False:
            ext_c += 1
        if a.get("capture_result") in (
            "http_error",
            "probe_failed",
            "probe_policy_failed",
            "skipped_non_http",
        ):
            miss_c += 1
        if a.get("capture_result") == "partial_body_hashed":
            partial_hash_count += 1
        if a.get("redirected"):
            redirected_asset_count += 1

    meta: dict[str, Any] = {
        "schema_version": 1,
        "inventory_kind": "official_home_source_inventory",
        "status": "capture_only",
        "route_id": "home",
        "site_id": "bukgu_gwangju",
        "site_name": "전남광주통합특별시 북구",
        "source": {
            "requested_url": requested_url,
            "final_resolved_url": final_url,
            "redirect_chain": redirect_chain,
            "http_status": status,
            "content_type": content_type,
            "character_encoding": character_encoding,
            "official_page_title": page_title,
            "captured_at": captured_at,
            "capture_finished_at": capture_finished_at,
            "source_updated_at": source_updated_at,
            "source_updated_at_absence_reason": source_updated_at_absence_reason,
            "capture_method": "python-urllib read-only HTTP GET inventory capture",
            "capture_tool": "scripts/capture_official_home_inventory.py",
            "raw_content_sha256": raw_sha,
            "raw_byte_length": len(raw_bytes),
            "sanitization_notes": list(SANITIZATION_NOTES),
        },
        "files": {
            "raw_snapshot": "data/official_captures/bukgu_gwangju/home/raw-homepage.html",
            "navigation_inventory": "data/official_captures/bukgu_gwangju/home/navigation-inventory.json",
            "asset_inventory": "data/official_captures/bukgu_gwangju/home/asset-inventory.json",
            "capture_notes": "data/official_captures/bukgu_gwangju/home/CAPTURE-NOTES.md",
        },
        "counts": {
            "navigation_items": len(nav_items),
            "blank_labels": blank_label_count,
            "assets_listed": len(asset_items),
            "assets_probed": probed_count,
            "partial_hash_assets": partial_hash_count,
            "redirected_assets": redirected_asset_count,
            "hierarchy_nodes": len(hierarchy),
        },
        "boundaries": {
            "firecrawl": False,
            "provider_api": False,
            "login": False,
            "form_submission": False,
            "payment": False,
            "pii": False,
            "canvas_integration": False,
            "route_status_change": False,
        },
    }
    meta["metadata_sha256"] = metadata_checksum(meta)
    (out_dir / "capture-metadata.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )

    nav_doc = {
        "schema_version": 1,
        "route_id": "home",
        "source_final_url": final_url,
        "captured_at": captured_at,
        "item_count": len(nav_items),
        "blank_label_count": blank_label_count,
        "section_counts": dict(sorted(sec_counts.items())),
        "hierarchy": hierarchy,
        "items": nav_items,
    }
    (out_dir / "navigation-inventory.json").write_text(
        json.dumps(nav_doc, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )

    asset_doc = {
        "schema_version": 1,
        "route_id": "home",
        "source_final_url": final_url,
        "captured_at": captured_at,
        "item_count": len(asset_items),
        "type_counts": dict(sorted(type_counts.items())),
        "same_origin_count": same_c,
        "external_count": ext_c,
        "missing_or_failed_count": miss_c,
        "partial_hash_count": partial_hash_count,
        "redirected_asset_count": redirected_asset_count,
        "probe_budget": PROBE_LIMIT,
        "partial_hash_limit_bytes": PARTIAL_HASH_LIMIT,
        "items": asset_items,
    }
    (out_dir / "asset-inventory.json").write_text(
        json.dumps(asset_doc, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )

    source_updated_display = (
        source_updated_at if source_updated_at else (source_updated_at_absence_reason or "absent")
    )
    notes = build_capture_notes(
        requested_url=requested_url,
        final_url=final_url,
        status=status,
        content_type=content_type,
        enc=character_encoding,
        page_title=page_title,
        captured_at=captured_at,
        source_updated_display=source_updated_display,
        raw_sha=raw_sha,
        meta_sha=meta["metadata_sha256"],
        redirect_chain=redirect_chain,
        nav_count=len(nav_items),
        sec_counts=dict(sec_counts),
        hierarchy=hierarchy,
        asset_count=len(asset_items),
        type_counts=dict(type_counts),
        same_c=same_c,
        ext_c=ext_c,
        miss_c=miss_c,
        blank_label_count=blank_label_count,
        partial_hash_count=partial_hash_count,
    )
    (out_dir / "CAPTURE-NOTES.md").write_text(notes, encoding="utf-8")
    return meta


def generate_capture_from_homepage_response(
    *,
    out_dir: Path,
    requested_url: str,
    final_url: str,
    status: int,
    content_type: str,
    character_encoding: str,
    redirect_chain: list[dict[str, Any]],
    response_body: bytes,
    captured_at: str,
    capture_finished_at: str,
    asset_fetch_fn: FetchFn | None = None,
    probe_limit: int = PROBE_LIMIT,
) -> dict[str, Any]:
    """Pure generation path used by live capture and offline reproducibility tests."""
    try:
        decoded = response_body.decode(character_encoding, errors="replace")
    except LookupError:
        character_encoding = "utf-8"
        decoded = response_body.decode("utf-8", errors="replace")
    meta_enc = re.search(r"<meta[^>]+charset=[\"']?([\w-]+)", decoded, re.I)
    if meta_enc:
        character_encoding = meta_enc.group(1).lower()
        try:
            decoded = response_body.decode(character_encoding, errors="replace")
        except LookupError:
            character_encoding = "utf-8"
            decoded = response_body.decode("utf-8", errors="replace")

    sanitized = sanitize_public_html(decoded)
    source_updated_at, source_updated_at_absence = extract_source_updated_at(sanitized)
    parsed = parse_homepage_inventories(sanitized, final_url)
    probed = 0
    if asset_fetch_fn is not None:
        probed = probe_asset_items(
            parsed["asset_items"], fetch_fn=asset_fetch_fn, probe_limit=probe_limit
        )
    else:
        for item in parsed["asset_items"]:
            if item.get("same_origin") is False:
                item["capture_result"] = "listed_external_unfetched"
                item["failure_reason"] = "external_or_unapproved_origin_not_fetched"

    return write_capture_bundle(
        out_dir,
        requested_url=requested_url,
        final_url=final_url,
        status=status,
        content_type=content_type,
        character_encoding=character_encoding,
        redirect_chain=redirect_chain,
        sanitized_html=sanitized,
        captured_at=captured_at,
        capture_finished_at=capture_finished_at,
        nav_items=parsed["nav_items"],
        asset_items=parsed["asset_items"],
        hierarchy=parsed["hierarchy"],
        probed_count=probed,
        source_updated_at=source_updated_at,
        source_updated_at_absence_reason=source_updated_at_absence,
    )


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    capture_started = datetime.now(KST)
    ctx = ssl.create_default_context()
    opener = build_capture_opener(ctx)

    home = fetch_with_redirect_recording(
        REQUESTED,
        opener=opener,
        headers={
            "Accept": "text/html,application/xhtml+xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "ko,en;q=0.8",
        },
        timeout=45,
        max_hops=MAX_REDIRECT_HOPS,
        read_body=True,
    )
    if int(home["status"] or 0) != 200:
        raise CaptureError(f"homepage HTTP status not 200: {home['status']}")

    def asset_fetch(url: str) -> dict[str, Any]:
        return fetch_with_redirect_recording(
            url,
            opener=opener,
            headers={"Accept": "*/*"},
            timeout=20,
            max_hops=MAX_REDIRECT_HOPS,
            read_body=True,
        )

    capture_finished = datetime.now(KST)
    meta = generate_capture_from_homepage_response(
        out_dir=OUT,
        requested_url=REQUESTED,
        final_url=home["final_url"],
        status=int(home["status"]),
        content_type=str(home["headers"].get("content-type", "")),
        character_encoding="utf-8",
        redirect_chain=home["redirect_chain"],
        response_body=home["body"],
        captured_at=capture_started.isoformat(timespec="seconds"),
        capture_finished_at=capture_finished.isoformat(timespec="seconds"),
        asset_fetch_fn=asset_fetch,
        probe_limit=PROBE_LIMIT,
    )

    print("CAPTURE_OK")
    print("final_url", meta["source"]["final_resolved_url"])
    print("status", meta["source"]["http_status"])
    print("title", meta["source"]["official_page_title"])
    print("raw_sha", meta["source"]["raw_content_sha256"])
    print("meta_sha", meta["metadata_sha256"])
    print(
        "nav",
        meta["counts"]["navigation_items"],
        "assets",
        meta["counts"]["assets_listed"],
        "probed",
        meta["counts"]["assets_probed"],
    )
    print("out", OUT)


if __name__ == "__main__":
    main()
