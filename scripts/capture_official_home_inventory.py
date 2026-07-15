#!/usr/bin/env python3
"""One-shot read-only capture of the official Buk-gu homepage inventory (#1160).

Allowed: public HTTP GET of official homepage and bounded public asset probes.
Forbidden: Firecrawl, provider APIs, login, form submission, payment, PII.
This script is operator-run for capture only; routine tests must not execute it.
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

REQUESTED = "https://bukgu.gwangju.kr/"
KST = timezone(timedelta(hours=9))
ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "official_captures" / "bukgu_gwangju" / "home"
PROBE_LIMIT = 40
UA = "400-ai-finder-official-capture/1.0 (read-only inventory; no auth)"


class InventoryParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.links: list[dict] = []
        self.assets: list[dict] = []
        self.current_section = "document"
        self._section_hints: list[str] = []
        self._in_a = False
        self._a_attrs: dict = {}
        self._a_text: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        ad = {k: (v or "") for k, v in attrs}
        tid = f"{ad.get('id', '')} {ad.get('class', '')}".lower()
        if tag in ("header", "nav", "footer", "main", "aside", "section"):
            label = tag
            if "util" in tid or "top" in tid:
                label = "utility"
            elif "gnb" in tid or "global" in tid or "main-menu" in tid:
                label = "global_nav"
            elif tag == "footer" or "footer" in tid:
                label = "footer"
            elif any(x in tid for x in ("banner", "visual", "slide", "carousel")):
                label = "banner"
            elif any(x in tid for x in ("quick", "service", "shortcut")):
                label = "service_shortcuts"
            elif any(x in tid for x in ("notice", "news", "board")):
                label = "notices_news"
            elif tag == "header":
                label = "header"
            elif tag == "nav":
                label = "nav"
            self.current_section = label
            self._section_hints.append(label)
        if tag == "a":
            self._in_a = True
            self._a_attrs = ad
            self._a_text = []
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
                }
            )
        if tag == "script" and ad.get("src"):
            self.assets.append(
                {
                    "tag": tag,
                    "type": "javascript",
                    "source_url": ad["src"],
                    "section": self.current_section,
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
                }
            )
        if tag in ("source", "video") and ad.get("src"):
            self.assets.append(
                {
                    "tag": tag,
                    "type": "video" if tag == "video" else "media",
                    "source_url": ad["src"],
                    "section": self.current_section,
                }
            )
        if tag == "input" and ad.get("type") == "image" and ad.get("src"):
            self.assets.append(
                {
                    "tag": tag,
                    "type": "image",
                    "source_url": ad["src"],
                    "section": self.current_section,
                }
            )

    def handle_endtag(self, tag: str) -> None:
        if tag == "a" and self._in_a:
            text = re.sub(r"\s+", " ", "".join(self._a_text)).strip()
            self.links.append(
                {
                    "visible_label": text,
                    "source_url": self._a_attrs.get("href", ""),
                    "title_attr": self._a_attrs.get("title", ""),
                    "target": self._a_attrs.get("target", ""),
                    "section": self.current_section,
                    "link_type": "anchor",
                }
            )
            self._in_a = False
            self._a_attrs = {}
            self._a_text = []
        if tag in ("header", "nav", "footer", "main", "aside", "section") and self._section_hints:
            self._section_hints.pop()
            self.current_section = self._section_hints[-1] if self._section_hints else "document"

    def handle_data(self, data: str) -> None:
        if self._in_a:
            self._a_text.append(data)


def origin_of(url: str) -> str | None:
    try:
        p = urllib.parse.urlparse(url)
        if p.scheme in ("http", "https") and p.netloc:
            return f"{p.scheme}://{p.netloc}"
    except Exception:
        return None
    return None


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    capture_started = datetime.now(KST)
    ctx = ssl.create_default_context()

    redirect_chain: list[dict] = []
    url = REQUESTED
    final_url = REQUESTED
    status: int | None = None
    headers: dict[str, str] = {}
    body = b""

    for _ in range(10):
        req = urllib.request.Request(
            url,
            method="GET",
            headers={
                "User-Agent": UA,
                "Accept": "text/html,application/xhtml+xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "ko,en;q=0.8",
            },
        )
        try:
            resp = urllib.request.urlopen(req, context=ctx, timeout=45)
        except urllib.error.HTTPError as exc:
            resp = exc
        status = getattr(resp, "status", None) or resp.getcode()
        headers = {k.lower(): v for k, v in resp.headers.items()}
        loc = resp.headers.get("Location")
        redirect_chain.append({"url": url, "status": status, "location": loc})
        if status in (301, 302, 303, 307, 308) and loc:
            url = urllib.parse.urljoin(url, loc)
            continue
        body = resp.read()
        final_url = resp.geturl() if hasattr(resp, "geturl") else url
        break

    content_type = headers.get("content-type", "")
    enc = "utf-8"
    m = re.search(r"charset=([\w-]+)", content_type, re.I)
    if m:
        enc = m.group(1).lower()
    try:
        html_text = body.decode(enc, errors="replace")
    except LookupError:
        enc = "utf-8"
        html_text = body.decode("utf-8", errors="replace")
    meta_enc = re.search(r"<meta[^>]+charset=[\"']?([\w-]+)", html_text, re.I)
    if meta_enc:
        enc = meta_enc.group(1).lower()
        try:
            html_text = body.decode(enc, errors="replace")
        except LookupError:
            pass

    raw_sha = hashlib.sha256(body).hexdigest()
    title_m = re.search(r"<title[^>]*>(.*?)</title>", html_text, re.I | re.S)
    page_title = re.sub(r"\s+", " ", title_m.group(1)).strip() if title_m else ""

    source_updated_at = None
    source_updated_at_absence = None
    for pattern in (
        r"최종\s*수정\s*일\s*[:：]?\s*([0-9]{4}[./-][0-9]{1,2}[./-][0-9]{1,2})",
        r"업데이트\s*[:：]?\s*([0-9]{4}[./-][0-9]{1,2}[./-][0-9]{1,2})",
        r"작성일\s*[:：]?\s*([0-9]{4}[./-][0-9]{1,2}[./-][0-9]{1,2})",
    ):
        um = re.search(pattern, html_text)
        if um:
            source_updated_at = um.group(1)
            break
    if not source_updated_at:
        source_updated_at_absence = "not-shown-on-homepage-html"

    parser = InventoryParser()
    parser.feed(html_text)
    base_origin = origin_of(final_url) or "https://bukgu.gwangju.kr"

    def absolutize(u: str, base: str = final_url) -> str:
        if not u or u.startswith(("javascript:", "mailto:", "tel:", "#")):
            return u
        return urllib.parse.urljoin(base, u)

    nav_items = []
    for i, link in enumerate(parser.links):
        src = link["source_url"]
        abs_u = absolutize(src)
        o = origin_of(abs_u) if abs_u.startswith("http") else None
        same = None
        if abs_u.startswith("http"):
            same = o == base_origin
        elif abs_u.startswith("#"):
            same = True
        elif abs_u.startswith(("javascript:", "mailto:", "tel:")):
            same = False
        nav_items.append(
            {
                "order": i + 1,
                "section": link["section"],
                "visible_label": link["visible_label"],
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
    asset_items: list[dict] = []
    for a in parser.assets:
        src = a["source_url"]
        abs_u = absolutize(src)
        if abs_u in seen:
            continue
        seen.add(abs_u)
        o = origin_of(abs_u) if abs_u.startswith("http") else None
        same = (o == base_origin) if o else None
        asset_items.append(
            {
                "source_url": src,
                "resolved_url": abs_u,
                "asset_type": a["type"],
                "tag": a["tag"],
                "section": a.get("section"),
                "alt": a.get("alt"),
                "same_origin": same,
                "response_status": None,
                "content_type": None,
                "size_bytes": None,
                "sha256": None,
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

    probed = 0
    for item in asset_items:
        if probed >= PROBE_LIMIT:
            if item["capture_result"] == "listed":
                item["capture_result"] = "listed_unprobed"
                item["failure_reason"] = "probe_budget_exceeded"
            continue
        u = item["resolved_url"]
        if not u or not str(u).startswith("http"):
            item["capture_result"] = "skipped_non_http"
            item["failure_reason"] = "non_http_url"
            continue
        try:
            req = urllib.request.Request(
                u,
                method="GET",
                headers={"User-Agent": UA},
            )
            try:
                r = urllib.request.urlopen(req, context=ctx, timeout=20)
            except urllib.error.HTTPError as e:
                item["response_status"] = e.code
                item["capture_result"] = "http_error"
                item["failure_reason"] = f"HTTP {e.code}"
                probed += 1
                continue
            data = r.read(65536)
            item["response_status"] = r.status
            item["content_type"] = r.headers.get("Content-Type")
            cl = r.headers.get("Content-Length")
            item["size_bytes"] = int(cl) if cl and cl.isdigit() else (len(data) if data else None)
            if data:
                item["sha256"] = hashlib.sha256(data).hexdigest()
                item["capture_result"] = "partial_body_hashed"
            else:
                item["capture_result"] = "headers_only"
            item["resolved_url"] = r.geturl()
            probed += 1
        except Exception as ex:  # noqa: BLE001 — inventory must record probe failures
            item["capture_result"] = "probe_failed"
            item["failure_reason"] = f"{type(ex).__name__}: {str(ex)[:200]}"
            probed += 1

    capture_finished = datetime.now(KST)
    captured_at = capture_started.isoformat(timespec="seconds")

    raw_path = OUT / "raw-homepage.html"
    raw_path.write_bytes(body)

    meta = {
        "schema_version": 1,
        "inventory_kind": "official_home_source_inventory",
        "status": "capture_only",
        "route_id": "home",
        "site_id": "bukgu_gwangju",
        "site_name": "전남광주통합특별시 북구",
        "source": {
            "requested_url": REQUESTED,
            "final_resolved_url": final_url,
            "redirect_chain": redirect_chain,
            "http_status": status,
            "content_type": content_type,
            "character_encoding": enc,
            "official_page_title": page_title,
            "captured_at": captured_at,
            "capture_finished_at": capture_finished.isoformat(timespec="seconds"),
            "source_updated_at": source_updated_at,
            "source_updated_at_absence_reason": source_updated_at_absence,
            "capture_method": "python-urllib read-only HTTP GET inventory capture",
            "capture_tool": "scripts/capture_official_home_inventory.py",
            "raw_content_sha256": raw_sha,
            "raw_byte_length": len(body),
        },
        "files": {
            "raw_snapshot": "data/official_captures/bukgu_gwangju/home/raw-homepage.html",
            "navigation_inventory": "data/official_captures/bukgu_gwangju/home/navigation-inventory.json",
            "asset_inventory": "data/official_captures/bukgu_gwangju/home/asset-inventory.json",
            "capture_notes": "data/official_captures/bukgu_gwangju/home/CAPTURE-NOTES.md",
        },
        "counts": {
            "navigation_items": len(nav_items),
            "assets_listed": len(asset_items),
            "assets_probed": probed,
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
    meta_for_hash = {k: v for k, v in meta.items() if k != "metadata_sha256"}
    meta["metadata_sha256"] = hashlib.sha256(
        json.dumps(meta_for_hash, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode(
            "utf-8"
        )
    ).hexdigest()

    (OUT / "capture-metadata.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )

    sec_counts: dict[str, int] = defaultdict(int)
    for n in nav_items:
        sec_counts[n["section"]] += 1
    nav_doc = {
        "schema_version": 1,
        "route_id": "home",
        "source_final_url": final_url,
        "captured_at": captured_at,
        "item_count": len(nav_items),
        "section_counts": dict(sorted(sec_counts.items())),
        "items": nav_items,
    }
    (OUT / "navigation-inventory.json").write_text(
        json.dumps(nav_doc, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )

    type_counts: dict[str, int] = defaultdict(int)
    same_c = ext_c = miss_c = 0
    for a in asset_items:
        type_counts[a["asset_type"]] += 1
        if a.get("same_origin") is True:
            same_c += 1
        elif a.get("same_origin") is False:
            ext_c += 1
        if a.get("capture_result") in ("http_error", "probe_failed", "skipped_non_http"):
            miss_c += 1

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
        "probe_budget": PROBE_LIMIT,
        "items": asset_items,
    }
    (OUT / "asset-inventory.json").write_text(
        json.dumps(asset_doc, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )

    notes = f"""# Official home-route source inventory (capture-only)

Issue: #1160
Parent: #1080
Status: **capture_only** — not integrated into civic canvas; route remains `capture_required`.

## Source

- Requested URL: `{REQUESTED}`
- Final resolved URL: `{final_url}`
- HTTP status: `{status}`
- Content-Type: `{content_type}`
- Encoding: `{enc}`
- Official page title: `{page_title}`
- Captured at: `{captured_at}`
- Source-visible update date: `{source_updated_at if source_updated_at else source_updated_at_absence}`
- Raw SHA-256: `{raw_sha}`
- Metadata SHA-256: `{meta['metadata_sha256']}`

## Redirect chain

```json
{json.dumps(redirect_chain, ensure_ascii=False, indent=2)}
```

## Inventory counts

- Navigation items: {len(nav_items)}
- Section counts: {dict(sorted(sec_counts.items()))}
- Assets listed: {len(asset_items)}
- Asset type counts: {dict(sorted(type_counts.items()))}
- Same-origin assets: {same_c}
- External assets: {ext_c}
- Missing/failed probes: {miss_c}

## Method

Read-only Python `urllib` GET of the public homepage and bounded public asset probes.
No Firecrawl, provider API, login, form submission, payment, or PII.

## Non-integration

This capture does **not**:

- change `home` route rendering
- change manifest status from `capture_required` to `exact`
- localize assets into `src/web/static`
- execute any official-site write action
"""
    (OUT / "CAPTURE-NOTES.md").write_text(notes, encoding="utf-8")

    print("CAPTURE_OK")
    print("final_url", final_url)
    print("status", status)
    print("title", page_title)
    print("raw_sha", raw_sha)
    print("meta_sha", meta["metadata_sha256"])
    print("nav", len(nav_items), "assets", len(asset_items), "probed", probed)
    print("out", OUT)


if __name__ == "__main__":
    main()
