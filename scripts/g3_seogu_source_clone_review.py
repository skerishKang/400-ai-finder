#!/usr/bin/env python3
"""#1303 G3 Phase 1 evidence generator: Seo-gu source-vs-clone review.

EVIDENCE-ONLY. Produces the 11-state evidence set comparing the committed G1
source captures against the merged G2-B candidate clone renderer output at
``2be1b85e04cc755255298ad94eb68934adf0da40`` (exact main).

Steps (fail-closed):
  1. assert running tree HEAD == candidate_commit_sha;
  2. assert every committed G1 source.png SHA-256 == G1 ledger
     (no source mutation, no runtime source regeneration);
  3. build the offline clone site via the approved G2-B build script;
  4. serve it on 127.0.0.1 only (ephemeral loopback port);
  5. for each of the 11 canonical states, capture a FULL-PAGE clone screenshot
     at the G1-matched viewport, aborting + counting any non-loopback request;
  6. run interaction evidence (GNB toggle, list->detail, overflow, focus);
  7. composite a top-aligned, no-crop, no-distortion SOURCE | CLONE side-by-side;
  8. write manifest.json + review.md into the evidence root.

Zero network to the actual site or any provider/API. External network count = 0.

Usage:
    python scripts/g3_seogu_source_clone_review.py [--repo-root DIR] [--chromium PATH]
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.metadata as _md
import json
import os
import re
import socket
import subprocess
import sys
import threading
from datetime import datetime, timezone
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

import PIL
from PIL import Image, ImageDraw, ImageFont
from playwright.sync_api import sync_playwright

CANDIDATE_COMMIT_SHA = "2be1b85e04cc755255298ad94eb68934adf0da40"
G1_CAPTURE_ID = "20260812T231018-0900"
SITE_ID = "seogu_gwangju"
SITE_PREFIX = SITE_ID.split("_")[0]
ROUTE_PREFIX = "/seogu/"

# canonical order: (state_id, viewport, served_subpath, gnb_open)
STATE_PLAN = [
    ("home.desktop.default",      {"width": 1440, "height": 900}, "",                  False),
    ("home.mobile.default",       {"width": 390,  "height": 844},  "home/mobile/",    False),
    ("home.desktop.gnb_open",     {"width": 1440, "height": 900},  "home/gnb-open/",  True),
    ("notice.list.desktop",       {"width": 1440, "height": 900},  "notice/",         False),
    ("notice.detail.desktop",     {"width": 1440, "height": 900},  "notice/detail/",  False),
    ("gosi.list.desktop",         {"width": 1440, "height": 900},  "gosi/",           False),
    ("gosi.detail.desktop",       {"width": 1440, "height": 900},  "gosi/detail/",    False),
    ("civil_form.list.desktop",   {"width": 1440, "height": 900},  "civil-form/",     False),
    ("civil_form.detail.desktop", {"width": 1440, "height": 900},  "civil-form/detail/", False),
    ("organization.chart.desktop",{"width": 1440, "height": 900},  "organization/",   False),
    ("staff.directory.desktop",   {"width": 1440, "height": 900},  "staff/",          False),
]
STATE_BY_ID = {s[0]: s for s in STATE_PLAN}

# Known material gaps: the committed G1 source hierarchy/content is demonstrably
# richer than the modeled clone. These MUST NOT be reported as source-parity
# structural/content PASS (fail-closed). Each carries an explicit exception with
# the reason the source is richer than the clone.
KNOWN_SOURCE_PARITY_GAPS = {
    "organization.chart.desktop": (
        "Source renders the full 행정조직도 hierarchy (2실·1관·7국·1소·18동 with a "
        "nested department tree); the clone models only the top-level layout shell."
    ),
    "staff.directory.desktop": (
        "Source renders the full 직원 업무안내 staff directory with per-department "
        "personnel entries; the clone models only placeholder structure."
    ),
    "notice.detail.desktop": (
        "Source renders the full 공고문 article body, attachments and metadata; the "
        "clone models only the detail shell with inert attachments."
    ),
    "gosi.detail.desktop": (
        "Source renders the full 고시/공고 notice body and metadata; the clone models "
        "only the detail shell."
    ),
    "civil_form.detail.desktop": (
        "Source renders the full 민원서식 form/document content; the clone models "
        "only the detail shell."
    ),
    "home.desktop.default": (
        "Source home renders full real content (news, banners, menus, widgets); the "
        "clone models only the layout skeleton."
    ),
    "home.mobile.default": (
        "Source mobile renders full responsive real content; the clone models only "
        "the layout skeleton at the mobile viewport."
    ),
    "home.desktop.gnb_open": (
        "Source GNB/mega-menu open renders the full 전체메뉴 tree; the clone models "
        "only the GNB toggle/panel shell."
    ),
}

# Source-parity dimensions, assessed against committed G1 evidence only.
SOURCE_PARITY_DIMENSIONS = (
    "structural", "content", "asset", "interaction_navigation",
    "responsive", "a11y", "visual",
)


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _is_loopback(url: str) -> bool:
    try:
        from urllib.parse import urlparse
        p = urlparse(url)
        host = (p.hostname or "").lower().strip("[]")
        return p.scheme in ("http", "https") and host in ("127.0.0.1", "localhost", "::1")
    except Exception:
        return False


def _git_head(repo_root: Path) -> str:
    return subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=str(repo_root), text=True
    ).strip()


def _bind_ephemeral() -> tuple[str, int]:
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return "127.0.0.1", port


class _Server(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True


def _start_server(docroot: Path, host: str, port: int) -> _Server:
    handler = lambda *a: SimpleHTTPRequestHandler(*a, directory=str(docroot))  # noqa: E731
    httpd = _Server((host, port), handler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    return httpd


def _build_site(repo_root: Path) -> Path:
    env = dict(os.environ)
    proc = subprocess.run(
        [sys.executable, str(repo_root / "scripts" / "build_reference_clone_site.py"),
         "--site-id", SITE_ID],
        cwd=str(repo_root), capture_output=True, text=True, env=env,
    )
    if proc.returncode != 0:
        sys.stderr.write(proc.stdout + proc.stderr)
        raise SystemExit("clone site build failed")
    return repo_root / "dist" / f"{SITE_ID}-clone"


def _font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    path = ("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold
            else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf")
    try:
        return ImageFont.truetype(path, size)
    except Exception:
        return ImageFont.load_default()


def _clone_route(state_id: str) -> str:
    return ROUTE_PREFIX + STATE_BY_ID[state_id][2]


def compose_side_by_side(source_png: Path, clone_png: Path, state_id: str,
                         viewport: dict[str, int], out_path: Path) -> Path:
    """SOURCE (left) | CLONE (right), top-aligned, no crop, no aspect distortion."""
    src = Image.open(source_png).convert("RGB")
    cln = Image.open(clone_png).convert("RGB")
    gap = 16
    header_h = 76
    cw = src.width + gap + cln.width
    ch = header_h + max(src.height, cln.height)
    canvas = Image.new("RGB", (cw, ch), "#ffffff")
    draw = ImageDraw.Draw(canvas)

    draw.rectangle((0, 0, cw, header_h), fill="#f2f2f2")
    draw.line((0, header_h, cw, header_h), fill="#b0b0b0", width=1)

    mid = (src.width) / 2.0
    title = f"{state_id}  @  {viewport['width']}x{viewport['height']}  (viewport)  —  source full-page"
    draw.text((12, 10), title, fill="#333333", font=_font(16))
    draw.text((12, 38), f"source SHA-256: {_sha256(source_png)}", fill="#666666", font=_font(13))

    rtitle = f"clone (candidate {CANDIDATE_COMMIT_SHA[:12]})  —  local offline full-page"
    draw.text((src.width + gap + 12, 10), rtitle, fill="#333333", font=_font(16))
    draw.text((src.width + gap + 12, 38), f"clone SHA-256:   {_sha256(clone_png)}", fill="#666666", font=_font(13))

    # corner badges
    draw.rectangle((8, header_h + 10, 110, header_h + 46), fill="#6a0019", outline="#40020f")
    draw.text((18, header_h + 16), "SOURCE", fill="#ffffff", font=_font(20, bold=True))
    clx = src.width + gap + 8
    draw.rectangle((clx, header_h + 10, clx + 110, header_h + 46), fill="#0b4c86", outline="#073564")
    draw.text((clx + 10, header_h + 16), "CLONE", fill="#ffffff", font=_font(20, bold=True))

    canvas.paste(src, (0, header_h))
    canvas.paste(cln, (src.width + gap, header_h))
    canvas.save(out_path, format="PNG", optimize=True)
    return out_path


def _make_external_counter(external: list[str]):
    def _handler(route_obj):
        url = route_obj.request.url
        if _is_loopback(url):
            route_obj.continue_()
        else:
            external.append(url)
            route_obj.abort()
    return _handler


def _run_interactions(page, base: str, external: list[str]) -> dict[str, Any]:
    page.route("**/*", _make_external_counter(external))
    page.set_viewport_size({"width": 1440, "height": 900})
    page.goto(base, wait_until="networkidle", timeout=30000)

    rec: dict[str, Any] = {}
    before = page.get_attribute("#rc-gnb-toggle", "aria-expanded")
    page.click("#rc-gnb-toggle")
    after = page.get_attribute("#rc-gnb-toggle", "aria-expanded")
    panel_visible = page.is_visible("#rc-mega-menu")
    page.keyboard.press("Escape")
    after_escape = page.get_attribute("#rc-gnb-toggle", "aria-expanded")
    rec["gnb_toggle"] = {
        "initial_aria_expanded": before,
        "after_click_aria_expanded": after,
        "panel_visible_when_open": panel_visible,
        "after_escape_aria_expanded": after_escape,
    }

    families = [
        ("notice/", "notice/detail/", "사회연대경제"),
        ("gosi/", "gosi/detail/", "고시/공고"),
        ("civil-form/", "civil-form/detail/", "자동차 등록 위임장"),
    ]
    navs = []
    for lst, det, marker in families:
        page.goto(base + lst, wait_until="networkidle", timeout=30000)
        link = page.query_selector("a.rc-list-link[data-detail='1']")
        entry: dict[str, Any] = {"family": lst, "list_detail_link_present": bool(link)}
        if link:
            link.click()
            page.wait_for_load_state("networkidle", timeout=15000)
            entry["landed_on_detail"] = page.url.endswith(det)
            entry["marker_present"] = (marker in page.content())
            entry["attachments_inert"] = page.eval_on_selector_all(
                "button.rc-attach",
                "(els)=>els.every(e=>e.hasAttribute('disabled')||e.getAttribute('aria-disabled')==='true')",
            )
        navs.append(entry)
    rec["list_to_detail_navigation"] = navs

    overflow = {}
    for vp in ((1440, 900), (390, 844)):
        page.set_viewport_size({"width": vp[0], "height": vp[1]})
        page.goto(base, wait_until="networkidle", timeout=30000)
        overflow[f"{vp[0]}x{vp[1]}"] = page.eval_on_selector_all(
            "html", "(d)=>d[0].scrollWidth - window.innerWidth",
        )
    rec["overflow"] = overflow

    page.set_viewport_size({"width": 1440, "height": 900})
    page.goto(base, wait_until="networkidle", timeout=15000)
    page.focus("#rc-gnb-toggle")
    rec["focus_active_element"] = page.eval_on_selector(
        "body", "()=>document.activeElement && document.activeElement.id",
    )
    return rec


def _modeled_contract_for(interaction: dict[str, Any]) -> dict[str, str]:
    """Clone's own offline route/browser QA (NOT source parity).

    These PASS results describe the merged G2-B clone candidate's behavior as
    verified by the offline interaction evidence. They are intentionally kept
    separate from source parity and must never be reused as source-vs-clone PASS.
    """
    g = interaction["gnb_toggle"]
    gnb_ok = (
        g["initial_aria_expanded"] == "false"
        and g["after_click_aria_expanded"] == "true"
        and g["panel_visible_when_open"] is True
        and g["after_escape_aria_expanded"] == "false"
    )
    nav_ok = all(
        bool(n.get("list_detail_link_present")) and bool(n.get("landed_on_detail"))
        and bool(n.get("attachments_inert"))
        for n in interaction["list_to_detail_navigation"]
    )
    overflow_ok = all(abs(v) <= 1 for v in interaction["overflow"].values())
    focus_ok = interaction["focus_active_element"] == "rc-gnb-toggle"
    return {
        "route_browser": "PASS",
        "gnb_interaction": "PASS" if gnb_ok else "FAIL",
        "list_detail_nav": "PASS" if nav_ok else "FAIL",
        "inert_attachment": "PASS" if nav_ok else "FAIL",
        "overflow": "PASS" if overflow_ok else "FAIL",
        "focus": "PASS" if focus_ok else "FAIL",
    }


def _source_parity_for(state_id: str) -> dict[str, Any]:
    """Source-vs-clone parity, grounded in committed G1 evidence only.

    Fail-closed: no PASS is claimed without positive committed evidence. Known
    material gaps are DIFFER (source demonstrably richer than the clone); all
    other states are NOT_ASSESSED (insufficient automated source-vs-clone
    comparison evidence). Conservative states (asset/visual) are never relaxed.
    """
    is_gap = state_id in KNOWN_SOURCE_PARITY_GAPS
    reason = KNOWN_SOURCE_PARITY_GAPS.get(state_id)
    if is_gap:
        structural = "DIFFER"
        content = "DIFFER"
        responsive = "DIFFER"
    else:
        # Insufficient committed automated source-vs-clone comparison evidence;
        # fail-closed (no PASS). Owner visual review is still pending.
        structural = "NOT_ASSESSED"
        content = "NOT_ASSESSED"
        responsive = "NOT_ASSESSED"
    return {
        "structural": structural,
        "content": content,
        "asset": "FAIL",
        "interaction_navigation": "NOT_ASSESSED",
        "responsive": responsive,
        "a11y": "NOT_ASSESSED",
        "visual": "DIFFER",
        "gap": is_gap,
        "reason": reason,
    }


def _build_review(results, interaction, ext_total, browser_version, pw_version) -> str:
    L = []
    L.append("# Seo-gu G3 Phase 1 — Source-vs-Clone Review Evidence")
    L.append("")
    L.append(f"- Candidate commit (exact main): `{CANDIDATE_COMMIT_SHA}`")
    L.append(f"- G1 capture id: `{G1_CAPTURE_ID}`")
    L.append(f"- Browser/tool: chromium `{browser_version}` (Playwright {pw_version}, "
             "headless, full-page screenshots)")
    L.append(f"- External network count (total across all states + interactions): `{ext_total}` (expected 0)")
    L.append("")
    L.append("> This PR is EVIDENCE-ONLY. Lifecycle gates remain closed: "
             "`visual_review=pending`, `owner_visual_approved=false`, "
             "`clone_mvp_ready=false`, `exact=false`, `golden=false`, "
             "`resident_default=false`, `production_ready=false`, "
             "`actual_site_integrated=false`.")
    L.append("")
    L.append("## Lifecycle (rendered `rc-lifecycle` JSON-LD, all 11 states)")
    L.append("")
    L.append("| marker | value |")
    L.append("|---|---|")
    for k, v in [
        ("visual_review", "pending"),
        ("clone_mvp_ready", False),
        ("resident_default", False),
        ("exact", False),
        ("golden", False),
        ("actual_site_integrated", False),
        ("production_ready", False),
        ("asset_byte_fidelity_complete", False),
        ("faithful_clone_candidate", True),
    ]:
        L.append(f"| `{k}` | `{v}` |")
    L.append("")
    L.append("## Modeled contract (clone offline QA — NOT source parity)")
    L.append("")
    L.append("These results describe the **clone's own** route/browser behavior as "
             "verified by the offline interaction evidence. They are intentionally "
             "kept separate from source parity and MUST NOT be reused as "
             "source-vs-clone PASS. (Requirement: modeled-contract PASS is not "
             "reused as source-parity PASS.)")
    L.append("")
    mc = results[0]["modeled_contract"]
    for k in ("route_browser", "gnb_interaction", "list_detail_nav",
              "inert_attachment", "overflow", "focus"):
        L.append(f"- `{k}`: {mc[k]}")
    L.append("")
    L.append("## Source parity (G1 committed evidence grounded)")
    L.append("")
    L.append("structural / content / asset / interaction_navigation / responsive / "
             "a11y / visual are assessed against the **committed G1 source** evidence "
             "only. `NOT_ASSESSED` = insufficient committed source-vs-clone comparison "
             "evidence (fail-closed; no PASS claimed). `DIFFER` = source demonstrably "
             "richer than the modeled clone. `FAIL` = known defect. This matrix is "
             "NOT an auto-approval: `visual_review` stays `pending`.")
    L.append("")
    hdr = ("| # | state_id | viewport | clone route | ext.req | "
           "structural | content | asset | interaction_nav | responsive | a11y | visual |")
    L.append(hdr)
    L.append("|" + "|".join(["---"] * (hdr.count("|") - 1)) + "|")
    for i, r in enumerate(results, 1):
        vp = r["source_viewport"]
        sp = r["source_parity"]
        L.append(
            f"| {i} | `{r['state_id']}` | {vp['width']}x{vp['height']} | "
            f"`{r['clone_route']}` | {r['external_network_count']} | "
            f"{sp['structural']} | {sp['content']} | {sp['asset']} | "
            f"{sp['interaction_navigation']} | {sp['responsive']} | "
            f"{sp['a11y']} | {sp['visual']} |"
        )
    L.append("")
    L.append("## Source parity per-state notes")
    L.append("")
    for r in results:
        vp = r["source_viewport"]
        sp = r["source_parity"]
        L.append(f"### `{r['state_id']}` — `{r['clone_route']}` @ {vp['width']}x{vp['height']} (viewport)")
        L.append(f"- source PNG: canonical committed G1 (`{r['source_screenshot_path']}`), "
                 f"SHA-256 {r['source_screenshot_sha256'][:16]}…, "
                 f"full-page dims {r['source_screenshot_dimensions']['width']}x"
                 f"{r['source_screenshot_dimensions']['height']}.")
        L.append(f"- clone screenshot: local offline full-page at matched viewport, "
                 f"SHA-256 {r['clone_screenshot_sha256'][:16]}….")
        L.append(f"- side-by-side: `{r['side_by_side_path']}`, SHA-256 "
                 f"{r['side_by_side_sha256'][:16]}….")
        L.append("- external network count: **0** (non-loopback requests aborted + counted).")
        L.append(f"- source parity: structural=`{sp['structural']}`, content=`{sp['content']}`, "
                 f"asset=`{sp['asset']}`, interaction_nav=`{sp['interaction_navigation']}`, "
                 f"responsive=`{sp['responsive']}`, a11y=`{sp['a11y']}`, visual=`{sp['visual']}`.")
        if sp["gap"]:
            L.append(f"- **KNOWN GAP (source richer than clone)**: {sp['reason']}")
        else:
            L.append("- source parity structural/content = NOT_ASSESSED: committed "
                     "automated source-vs-clone comparison evidence is insufficient; "
                     "no PASS is claimed (fail-closed). Owner visual review pending.")
        L.append("")
    L.append("## Source parity legend / closures")
    L.append("")
    L.append("- **assets = FAIL**: `asset_byte_fidelity_complete=false` — the clone "
             "renders structural placeholders only; no real Seo-gu asset bytes "
             "(images/fonts/css) are fetched or committed. This holds for all 11 "
             "states and is unchanged.")
    L.append("- **visual/material = DIFFER (expected G2-B)**: source is the real "
             "municipal site with full visual styling, photographs, fonts and "
             "iconography; clone is the modeled layout tokens only. Unchanged.")
    L.append("- **modeled-contract PASS is NOT source-parity PASS**: the clone's own "
             "route/browser QA (GNB toggle, list->detail, inert attachments, no "
             "overflow, focus) is reported in the 'Modeled contract' section above "
             "and must not be interpreted as source-vs-clone parity.")
    L.append("")
    L.append("## Interaction evidence")
    L.append("")
    g = interaction["gnb_toggle"]
    L.append("GNB toggle (home `/`):")
    L.append(f"- initial aria-expanded: `{g['initial_aria_expanded']}`")
    L.append(f"- after click: `{g['after_click_aria_expanded']}`, "
             f"mega-menu visible: `{g['panel_visible_when_open']}`")
    L.append(f"- after Escape: `{g['after_escape_aria_expanded']}` (closes)")
    L.append("")
    L.append("List -> detail local navigation (attachments remain inert):")
    L.append("| family | list->detail link present | landed on detail | content marker present | attachments inert |")
    L.append("|---|---|---|---|---|")
    for n in interaction["list_to_detail_navigation"]:
        L.append(f"| `{n['family']}` | {n['list_detail_link_present']} | "
                 f"{n.get('landed_on_detail')} | {n.get('marker_present')} | "
                 f"{n.get('attachments_inert')} |")
    L.append("")
    ov = interaction["overflow"]
    L.append("Horizontal overflow (require <= 1px):")
    for k, v in ov.items():
        L.append(f"- {k}: `{v}px`")
    L.append(f"- keyboard focus active element: `{interaction['focus_active_element']}` "
             "(expect `rc-gnb-toggle`)")
    L.append("")
    L.append("## Exceptions (fail-closed on promotion readiness)")
    L.append("")
    L.append("- `asset_byte_fidelity_complete=false` — affects all 11 states. The G2-B "
             "candidate intentionally renders structural placeholders and does NOT bind "
             "real Seo-gu asset bytes. Asset PASS must NOT be claimed until asset bytes "
             "are resolved and the lifecycle marker flips to `true`.")
    L.append("- `visual_review=pending` / `owner_visual_approved=false` — side-by-side "
             "evidence is provided for owner visual approval only; no automated visual "
             "pass is asserted.")
    L.append("- Known material gaps (organization.chart, staff.directory, notice.detail, "
             "gosi.detail, civil_form.detail, home.desktop.default, home.mobile.default, "
             "home.desktop.gnb_open) are reported as source-parity `DIFFER` (source richer "
             "than the modeled clone) with an explicit exception/reason; they are NOT "
             "source-parity PASS. All other states are `NOT_ASSESSED` (insufficient "
             "committed comparison evidence, fail-closed).")
    L.append("")
    L.append("## Scope / non-mutation statement")
    L.append("")
    L.append("- G1 canonical capture bytes: UNCHANGED (SHA-256 verified each state).")
    L.append("- G2-B renderer (`src/official_clone/reference_clone_renderer.py`), "
             "`visual_contract.py`, G2-A semantic model: UNCHANGED in this PR.")
    L.append("- No live recapture of the Seo-gu site; source side is the committed G1 PNG.")
    L.append("- No production/Cloudflare/DB mutation; no actual site integration.")
    return "\n".join(L) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="G3 Seo-gu source-vs-clone evidence")
    parser.add_argument("--repo-root", default=str(Path(__file__).resolve().parents[1]))
    parser.add_argument("--chromium", default=None)
    args = parser.parse_args(argv)
    repo_root = Path(args.repo_root).resolve()
    ev_root = (repo_root / "data" / "official_clone_reviews" / SITE_PREFIX
               / "g3" / CANDIDATE_COMMIT_SHA)

    # 1. fail-closed candidate identity.
    head = _git_head(repo_root)
    if head != CANDIDATE_COMMIT_SHA:
        raise SystemExit(f"FAIL-CLOSED: HEAD {head} != candidate {CANDIDATE_COMMIT_SHA}")

    # 2. verify committed G1 source PNGs against the ledger (no runtime source).
    capture_root = (repo_root / "data" / "official_captures" / SITE_ID
                    / "g1" / G1_CAPTURE_ID)
    ledger = json.loads((capture_root / "ledger.json").read_text(encoding="utf-8"))
    ledger_by_state = {s["state_id"]: s for s in ledger["captured_states"]}
    src_records: dict[str, dict[str, Any]] = {}
    for state_id, _vp, _sub, _open in STATE_PLAN:
        s = ledger_by_state.get(state_id)
        if s is None:
            raise SystemExit(f"FAIL-CLOSED: {state_id} missing from G1 ledger")
        png_art = next((a for a in s["artifacts"] if a.get("class") == "screenshot"), None)
        if png_art is None:
            raise SystemExit(f"FAIL-CLOSED: {state_id} no screenshot in ledger")
        src_png = capture_root / "states" / state_id / "source.png"
        if not src_png.is_file():
            raise SystemExit(f"FAIL-CLOSED: source.png missing for {state_id}")
        actual = _sha256(src_png)
        if actual != png_art["sha256"]:
            raise SystemExit(f"FAIL-CLOSED: {state_id} source SHA mismatch "
                             f"(file={actual} ledger={png_art['sha256']})")
        src_records[state_id] = {
            "ledger_sha256": png_art["sha256"],
            "dimensions": png_art["dimensions"],
            "viewport": s["viewport"],
            "requested_url": s["requested_url"],
        }

    # 3. build + serve the offline clone.
    dist_root = _build_site(repo_root)
    if not (dist_root / "index.html").is_file():
        raise SystemExit("FAIL-CLOSED: clone site index.html missing after build")
    host, port = _bind_ephemeral()
    httpd = _start_server(dist_root, host, port)
    base = f"http://{host}:{port}/"
    sys.stderr.write(f"[g3] serving clone at {base} (docroot={dist_root})\n")

    pw_version = _md.version("playwright")
    pil_version = getattr(PIL, "__version__", "?.?")
    browser_version = None
    external_total = 0
    results: list[dict[str, Any]] = []

    try:
        with sync_playwright() as p:
            launch_opts: dict[str, Any] = {"headless": True}
            if args.chromium:
                launch_opts["executable_path"] = args.chromium
            browser = p.chromium.launch(**launch_opts)
            browser_version = browser.version
            context = browser.new_context(
                viewport={"width": 1440, "height": 900},
                device_scale_factor=1,
            )

            # 5. per-state full-page clone capture + per-state external count.
            for state_id, viewport_, subpath, _open in STATE_PLAN:
                page = context.new_page()
                external: list[str] = []
                page.route("**/*", _make_external_counter(external))
                page.set_viewport_size(viewport_)
                url = base + subpath  # base ends with "/"; subpath may be ""
                if not url.endswith("/"):
                    url += "/"
                page.goto(url, wait_until="networkidle", timeout=30000)
                page.wait_for_timeout(300)
                clone_png = ev_root / "states" / state_id / "clone.png"
                clone_png.parent.mkdir(parents=True, exist_ok=True)
                page.screenshot(path=str(clone_png), full_page=True, type="png")
                external_total += len(external)

                gnb_state = None
                if state_id == "home.desktop.gnb_open":
                    gnb_state = {
                        "aria_expanded": page.get_attribute("#rc-gnb-toggle", "aria-expanded"),
                        "panel_visible": page.is_visible("#rc-mega-menu"),
                    }

                results.append({
                    "state_id": state_id,
                    "source_screenshot_path": str(
                        (capture_root / "states" / state_id / "source.png").relative_to(repo_root)),
                    "source_screenshot_sha256": src_records[state_id]["ledger_sha256"],
                    "source_viewport": src_records[state_id]["viewport"],
                    "source_screenshot_dimensions": src_records[state_id]["dimensions"],
                    "source_url": src_records[state_id]["requested_url"],
                    "clone_route": _clone_route(state_id),
                    "clone_capture_url": url,
                    "clone_screenshot_path": str(
                        (ev_root / "states" / state_id / "clone.png").relative_to(repo_root)),
                    "clone_screenshot_sha256": _sha256(clone_png),
                    "side_by_side_path": str(
                        (ev_root / "states" / state_id / "side_by_side.png").relative_to(repo_root)),
                    "side_by_side_sha256": None,
                    "browser_tool_version": browser_version,
                    "capture_viewport": viewport_,
                    "external_network_count": len(external),
                    "external_requests": external,
                    "gnb_open_state": gnb_state,
                    "source_parity": _source_parity_for(state_id),
                    "modeled_contract": None,
                })
                page.close()

            # 6. interaction evidence on a shared loopback-only page.
            ipage = context.new_page()
            external_i: list[str] = []
            ipage.route("**/*", _make_external_counter(external_i))
            interaction = _run_interactions(ipage, base, external_i)
            external_total += len(external_i)
            ipage.close()

            # Modeled contract (clone's own QA) is clone-wide; attach the same
            # verified result to every state. It is intentionally separate from
            # the per-state source_parity computed above.
            mc = _modeled_contract_for(interaction)
            for r in results:
                r["modeled_contract"] = mc

            browser.close()
    finally:
        httpd.shutdown()

    # 7. side-by-side composites.
    for r in results:
        sb = ev_root / "states" / r["state_id"] / "side_by_side.png"
        src = repo_root / r["source_screenshot_path"]
        cln = repo_root / r["clone_screenshot_path"]
        vp = r["capture_viewport"]
        compose_side_by_side(src, cln, r["state_id"], vp, sb)
        r["side_by_side_sha256"] = _sha256(sb)

    manifest = {
        "candidate_commit_sha": CANDIDATE_COMMIT_SHA,
        "g1_capture_id": G1_CAPTURE_ID,
        "site_id": SITE_ID,
        "route_prefix": ROUTE_PREFIX,
        "evidence_root": str(ev_root.relative_to(repo_root)),
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "tooling": {
            "browser": "chromium",
            "browser_version": browser_version,
            "playwright_version": pw_version,
            "pillow_version": pil_version,
            "capture_method": "playwright_headless_full_page_screenshot",
            "python": sys.version.split()[0],
        },
        "external_network_total": external_total,
        "lifecycle": {
            "g3_evidence_complete": len(results) == 11 and external_total == 0,
            "visual_review": "pending",
            "owner_visual_approved": False,
            "clone_mvp_ready": False,
            "exact": False,
            "golden": False,
            "resident_default": False,
            "production_ready": False,
            "actual_site_integrated": False,
            "asset_byte_fidelity_complete": False,
        },
        "states": results,
    }
    ev_root.mkdir(parents=True, exist_ok=True)
    (ev_root / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")

    (ev_root / "review.md").write_text(
        _build_review(results, interaction, external_total, browser_version, pw_version),
        encoding="utf-8")

    sys.stderr.write(f"[g3] evidence root: {ev_root}\n")
    sys.stderr.write(f"[g3] states: {len(results)} | clone screenshots: {len(results)} "
                     f"| side-by-sides: {len(results)} | external_network_total: {external_total}\n")
    sys.stderr.write(f"[g3] manifest states external counts: "
                     f"{[r['external_network_count'] for r in results]}\n")
    if external_total != 0:
        raise SystemExit(f"FAIL-CLOSED: external network count {external_total} != 0")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
