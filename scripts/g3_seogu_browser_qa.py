#!/usr/bin/env python3
"""#1303 G3 browser QA — Python mirror of tests/browser/verify_seogu_reference_clone_e2e.mjs.

Runs the SAME fail-closed assertions the Node e2e harness enforces, against the
locally-served G2-B clone on loopback only. Exit 0 only if every assertion holds.
"""
from __future__ import annotations

import json
import re
import socket
import subprocess
import sys
import threading
import urllib.request
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from playwright.sync_api import sync_playwright

REPO_ROOT = Path(__file__).resolve().parents[1]
CANDIDATE_SHA = "2be1b85e04cc755255298ad94eb68934adf0da40"
SITE_ID = "seogu_gwangju"

REQUIRED_ROUTES = [
    "", "notice/", "notice/detail/", "gosi/", "gosi/detail/",
    "civil-form/", "civil-form/detail/", "organization/", "staff/",
    "home/gnb-open/", "home/mobile/",
]
FAMILIES = [
    ("notice/", "notice/detail/", "사회연대경제"),
    ("gosi/", "gosi/detail/", "고시/공고"),
    ("civil-form/", "civil-form/detail/", "자동차 등록 위임장"),
]
FORBIDDEN_VISIBLE = [
    "site_id=", "capture_id=", "captured_at=", "source_updated_at=",
    "final_http_status=", "visual-input gap", "표면", "rc-meta",
    "<dt>state_id</dt>", "list_no=",
]
FORBIDDEN_CSS = ["#e6e6ea", "#8a8a93", "#1f6feb", "980px", "999px",
                 "border-radius", "max-width:600px", "@media (max-width",
                 "font-size:.85rem", "font-size:1.25rem", "font-size:1.4rem",
                 "padding:14px 18px", "padding:22px 18px 60px"]


def _is_loopback(url: str) -> bool:
    from urllib.parse import urlparse
    p = urlparse(url)
    host = (p.hostname or "").lower().strip("[]")
    return p.scheme in ("http", "https") and host in ("127.0.0.1", "localhost", "::1")


def _build_and_serve():
    subprocess.run(
        [sys.executable, str(REPO_ROOT / "scripts" / "build_reference_clone_site.py"),
         "--site-id", SITE_ID],
        cwd=str(REPO_ROOT), check=True, capture_output=True,
    )
    docroot = REPO_ROOT / "dist" / f"{SITE_ID}-clone"
    s = socket.socket(); s.bind(("127.0.0.1", 0)); port = s.getsockname()[1]; s.close()
    handler = lambda *a: SimpleHTTPRequestHandler(*a, directory=str(docroot))
    httpd = ThreadingHTTPServer(("127.0.0.1", port), handler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    return httpd, f"http://127.0.0.1:{port}/"


def main() -> int:
    head = subprocess.check_output(["git", "rev-parse", "HEAD"],
                                   cwd=str(REPO_ROOT), text=True).strip()
    if head != CANDIDATE_SHA:
        print(f"FAIL-CLOSED: HEAD {head} != candidate {CANDIDATE_SHA}"); return 1
    httpd, base = _build_and_serve()
    failures: list[str] = []
    external: list[str] = []

    def check(cond, msg):
        if not cond:
            failures.append(msg)

    def route_handler(route_obj):
        url = route_obj.request.url
        if _is_loopback(url):
            route_obj.continue_()
        else:
            external.append(url)
            route_obj.abort()

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True, executable_path="/usr/bin/chromium")
            ctx = browser.new_context(viewport={"width": 1440, "height": 900})
            ctx.route("**/*", route_handler)
            page = ctx.new_page()

            # 1) modeled routes serve 200 + text/html
            for route in REQUIRED_ROUTES:
                try:
                    with urllib.request.urlopen(base + route, timeout=10) as r:
                        ct = r.headers.get("content-type", "")
                        check(r.status == 200, f"route not 200: {route}")
                        check("text/html" in ct, f"route not html: {route}")
                except Exception as e:
                    check(False, f"route fetch failed: {route} ({e})")

            # 2) root title + lifecycle + no debug leak
            page.goto(base, wait_until="networkidle", timeout=20000)
            html = page.content()
            title = page.title()
            check("서구청" in title, "root title missing 서구청")
            check("착한도시 서구" in title, "root title missing 착한도시 서구")
            check('id="rc-lifecycle"' in html, "rc-lifecycle missing")
            check('id="rc-evidence"' in html, "rc-evidence missing")

            def _jsonld(tag_id):
                i = html.index(f'id="{tag_id}"')
                end = html.index("</script>", i)
                return json.loads(html[i:end].split(">", 1)[1])

            life = _jsonld("rc-lifecycle")
            check(life.get("faithful_clone_candidate") is True,
                  "faithful_clone_candidate not true")
            check(life.get("asset_byte_fidelity_complete") is False,
                  "asset_byte_fidelity_complete not false")
            check(life.get("visual_review") == "pending", "visual_review not pending")
            check(life.get("clone_mvp_ready") is False, "clone_mvp_ready not false")
            check(life.get("exact") is False, "exact not false")
            check(life.get("golden") is False, "golden not false")
            check(life.get("resident_default") is False, "resident_default not false")
            check(life.get("production_ready") is False, "production_ready not false")
            check(life.get("actual_site_integrated") is False,
                  "actual_site_integrated not false")

            for tok in FORBIDDEN_VISIBLE:
                check(tok not in html, f"resident-visible debug leaked: {tok!r}")
            for tok in FORBIDDEN_CSS:
                check(tok not in html, f"forbidden guessed CSS token: {tok!r}")

            # 3) GNB toggle open/click/close
            btn = page.locator("#rc-gnb-toggle")
            check(btn.get_attribute("aria-expanded") == "false", "GNB not collapsed initially")
            page.click("#rc-gnb-toggle")
            check(btn.get_attribute("aria-expanded") == "true", "GNB did not open on click")
            check(page.is_visible("#rc-mega-menu"), "mega-menu not visible when open")
            page.keyboard.press("Escape")
            check(btn.get_attribute("aria-expanded") == "false", "Escape did not close GNB")

            # 4) list -> detail for all three families
            for lst, det, marker in FAMILIES:
                page.goto(base + lst, wait_until="networkidle", timeout=20000)
                link = page.locator("a.rc-list-link[data-detail='1']")
                check(link.count() >= 1, f"list->detail link missing for {lst}")
                with page.expect_navigation(url=re.compile(".*"), timeout=15000):
                    link.click()
                page.wait_for_load_state("networkidle", timeout=15000)
                check(page.url.endswith(det), f"expected {det}, got {page.url}")
                dhtml = page.content()
                check(marker in dhtml, f"detail for {lst} missing marker {marker}")
                inert = page.eval_on_selector_all(
                    "button.rc-attach",
                    "(els)=>els.every(e=>e.hasAttribute('disabled')||"
                    "e.getAttribute('aria-disabled')==='true')",
                )
                check(inert, f"attachments not inert for {lst}")

            # 5) organization / staff reachable
            for route in ["organization/", "staff/"]:
                with urllib.request.urlopen(base + route, timeout=10) as r:
                    check(r.status == 200, f"{route} not reachable")
                page.goto(base + route, wait_until="networkidle", timeout=20000)
                c = page.content()
                check(("서구소개" in c or "청사안내" in c), f"{route} content missing")

            # 6) .hwpx attachment affordance on notice detail
            page.goto(base + "notice/detail/", wait_until="networkidle", timeout=20000)
            hwpx = page.eval_on_selector_all(
                "button.rc-attach",
                "(els)=>els.some(e=>(e.getAttribute('data-attachment-ext')||'')"
                ".includes('hwpx'))",
            )
            check(hwpx, "notice detail missing .hwpx attachment affordance")

            # 7) responsive overflow
            for vp in ((1440, 900), (390, 844)):
                page.set_viewport_size({"width": vp[0], "height": vp[1]})
                page.goto(base, wait_until="networkidle", timeout=20000)
                ov = page.eval_on_selector_all(
                    "html", "(d)=>d[0].scrollWidth - window.innerWidth")
                check(ov <= 1, f"horizontal overflow at {vp}: {ov}px")

            # 8) keyboard focus
            page.set_viewport_size({"width": 1440, "height": 900})
            page.goto(base, wait_until="networkidle", timeout=15000)
            page.focus("#rc-gnb-toggle")
            active = page.eval_on_selector(
                "body", "()=>document.activeElement && document.activeElement.id")
            check(active == "rc-gnb-toggle", f"focus not on gnb-toggle (got {active})")

            browser.close()
    finally:
        httpd.shutdown()

    # 9) zero external / no seogu.gwangju.kr
    check(len(external) == 0, f"external requests: {external}")
    for url in external:
        check("seogu.gwangju.kr" not in url, f"request to seogu.gwangju.kr: {url}")

    print(f"BROWSER_QA_FAILURES={len(failures)}")
    for f in failures:
        print("  FAIL:", f)
    print(f"EXTERNAL_REQUESTS={len(external)}")
    if failures or external:
        return 1
    print("Seo-gu G2-B browser QA (Python mirror of node e2e) PASSED.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
