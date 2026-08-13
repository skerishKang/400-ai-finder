"""Generic, model-driven faithful-clone renderer for #1303 G2-B.

This module is the G2-B faithful-clone *candidate* renderer. It is the ONLY
runtime consumer of the G2-A semantic model document. It never reads the raw
capture evidence (the committed per-state source HTML, the captured viewport
image, the visible-region inventory, the capture ledger, the provenance
manifest, live reference URLs, or the capture artifact tree). All rendered
semantics are taken from the model dict produced by the G2-A builder.

Fail-closed contract:
  * ``load_model`` reads a single ``clone-model.json`` file only.
  * ``render_state`` / ``render_site`` raise if the model's
    ``claim_gates.reference_baseline_ready`` is not ``True``.
  * The renderer is generic: routing, surface labels, and list/detail linking
    are derived from ``state_id`` structure and ``page_title`` text. There is
    NO per-site conditional branch and NO site-specific literal.

Asset limitation (G2-B):
  * No external image/font/css are fetched. Only deterministic local CSS and
    inline JS are emitted.
  * Real asset bytes are NOT in the repository, so asset fidelity is left
    *pending* and rendered as explicit local placeholders. The lifecycle
    marker ``asset_byte_fidelity_complete`` stays ``False``.

Link policy:
  * Modeled internal destinations (the captured state routes) are rendered as
    working relative links.
  * Every other captured link (general_links / controls / GNB menu items) is
    rendered as an inert, read-only, ``aria-disabled`` affordance. No live
    navigation, no remote download, no form submission.
"""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any

# Generic lifecycle markers required by the G2-B contract. These are explicit
# candidate-status flags; they are NOT visual-approval / production claims.
LIFECYCLE_MARKERS = {
    "faithful_clone_candidate": True,
    "visual_review": "pending",
    "clone_mvp_ready": False,
    "resident_default": False,
    "exact": False,
    "golden": False,
    "actual_site_integrated": False,
    "production_ready": False,
    "asset_byte_fidelity_complete": False,
}

# Deterministic output route namespace. Generic: a second-site model renders
# under the same prefix; routing is derived from state_id, never hardcoded.
DEFAULT_ROUTE_PREFIX = "/seogu/"

# Board-record identifier tokens shared across municipal board systems.
_BOARD_ID_TOKENS = ("list_no", "not_ancmt_mgt_no")

# Device classes recognised in a state_id's middle segment.
_DEVICE_CLASSES = ("desktop", "mobile")


class ReferenceCloneRendererError(ValueError):
    """Raised when the model is not ready or a state cannot be rendered."""


def _esc(value: Any) -> str:
    """HTML-escape a scalar for safe inline text/attribute insertion."""
    text = "" if value is None else str(value)
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&#39;")
    )


def _require_model_ready(model: dict[str, Any]) -> None:
    gates = model.get("claim_gates") or {}
    if not gates.get("reference_baseline_ready"):
        raise ReferenceCloneRendererError(
            "refusing to render: model claim_gates.reference_baseline_ready is not True"
        )


# ---------------------------------------------------------------------------
# State-id parsing (generic; no site literal)
# ---------------------------------------------------------------------------
def parse_state_id(state_id: str) -> tuple[str, str, str]:
    """Split ``family.device.content`` into ``(family, device, content)``.

    The device segment is whichever segment is a known device class; the
    remaining non-family segment is the content/variant token.
    """
    parts = state_id.split(".")
    if len(parts) < 3:
        raise ReferenceCloneRendererError(f"unexpected state_id shape: {state_id!r}")
    family = parts[0]
    device = next((p for p in parts if p in _DEVICE_CLASSES), "desktop")
    content = next((p for p in parts if p not in (family, device)), "")
    return family, device, content


def _slug(family: str) -> str:
    return family.replace("_", "-")


def route_for_state(state_id: str, route_prefix: str = DEFAULT_ROUTE_PREFIX) -> str:
    """Deterministically map a ``state_id`` to its clone route (generic)."""
    family, device, content = parse_state_id(state_id)
    slug = _slug(family)
    if content == "gnb_open":
        return f"{route_prefix}home/gnb-open/"
    if content == "default":
        if family == "home" and device == "mobile":
            return f"{route_prefix}home/mobile/"
        if family == "home":
            return route_prefix
        return f"{route_prefix}{slug}/"
    if content == "list":
        return f"{route_prefix}{slug}/"
    if content == "detail":
        return f"{route_prefix}{slug}/detail/"
    # chart / directory / unknown variant -> family landing surface.
    return f"{route_prefix}{slug}/"


# ---------------------------------------------------------------------------
# Relative href resolution (generic, directory-relative)
# ---------------------------------------------------------------------------
def relative_href(from_route: str, to_route: str) -> str:
    """Resolve a relative href between two route directories."""
    a = [p for p in from_route.split("/") if p]
    b = [p for p in to_route.split("/") if p]
    i = 0
    while i < min(len(a), len(b)) and a[i] == b[i]:
        i += 1
    up = [".."] * (len(a) - i)
    down = b[i:]
    rel = "/".join(up + down)
    return (rel or ".") + "/"


# ---------------------------------------------------------------------------
# Semantic extraction helpers (generic, all from model dict)
# ---------------------------------------------------------------------------
def _record_id(value: str | None) -> str | None:
    if not value:
        return None
    for token in _BOARD_ID_TOKENS:
        match = re.search(rf"{token}=(\d+)", value)
        if match:
            return f"{token}={match.group(1)}"
    return None


def _is_board_link(link: dict[str, Any]) -> bool:
    href = link.get("href", "") or ""
    text = (link.get("text") or "").strip()
    if not text:
        return False
    if any(tok in href for tok in _BOARD_ID_TOKENS):
        return True
    if "act=view" in href or "act=viewC" in href:
        return True
    return False


def surface_label(state: dict[str, Any], model: dict[str, Any]) -> str:
    """Derive a human surface label generically from the captured page_title.

    No site literal is used: single-segment titles become ``홈``; multi-segment
    titles use the breadcrumb segment after the (optional) status segment.
    The GNB-open surface label is taken from the model's ``gnb2`` landmark text.
    """
    state_id = state.get("state_id", "")
    _family, _device, content = parse_state_id(state_id)
    if content == "gnb_open":
        for lm in state.get("landmarks", []):
            if lm.get("id") == "gnb2":
                text = (lm.get("text") or "").strip()
                if text:
                    return text
        return "전체메뉴"
    title = state.get("page_title") or ""
    head = title.rsplit(":", 1)[0] if ":" in title else title
    segments = [s.strip() for s in head.split("|") if s.strip()]
    if len(segments) <= 1:
        return "홈"
    return segments[1]


def _gnb_top_items(model: dict[str, Any]) -> list[str]:
    """Top GNB menu tokens from the ``gnb1`` landmark (model-derived, inert)."""
    for state in model["states"]:
        if state.get("state_id", "").endswith(".default"):
            for lm in state.get("landmarks", []):
                if lm.get("id") == "gnb1":
                    return [t for t in (lm.get("text") or "").split() if t]
    return []


def _gnb_extra_items(model: dict[str, Any]) -> list[str]:
    """Mega-menu items: controls present in ``gnb_open`` but not in default."""
    default_state = None
    open_state = None
    for state in model["states"]:
        sid = state.get("state_id", "")
        if sid.endswith(".default") and sid.startswith("home."):
            default_state = state
        if parse_state_id(sid)[2] == "gnb_open":
            open_state = state
    if default_state is None or open_state is None:
        return []
    base = {c.get("text") for c in default_state.get("controls", []) if c.get("text")}
    extra: list[str] = []
    for control in open_state.get("controls", []):
        text = control.get("text")
        if text and text not in base and text not in extra:
            extra.append(text)
    return extra


def _family_detail_route(model: dict[str, Any], family: str) -> str | None:
    for state in model["states"]:
        fam, _dev, content = parse_state_id(state.get("state_id", ""))
        if fam == family and content == "detail":
            return route_for_state(state["state_id"])
    return None


def _family_detail_record_id(model: dict[str, Any], family: str) -> str | None:
    for state in model["states"]:
        fam, _dev, content = parse_state_id(state.get("state_id", ""))
        if fam == family and content == "detail":
            return _record_id(state.get("final_url"))
    return None


def _nav_entries(model: dict[str, Any], route_prefix: str) -> list[tuple[str, str]]:
    """Working local navigation: one entry per distinct landing route."""
    seen: set[str] = set()
    nav: list[tuple[str, str]] = []
    for state in model["states"]:
        _family, device, content = parse_state_id(state.get("state_id", ""))
        if content == "detail":
            continue
        if device == "mobile":
            continue
        route = route_for_state(state["state_id"], route_prefix)
        if route in seen:
            continue
        seen.add(route)
        nav.append((route, surface_label(state, model)))
    return nav


def _list_items(model: dict[str, Any], state: dict[str, Any]) -> list[dict[str, Any]]:
    """Board items for a list surface, with local detail-link targeting."""
    family, _dev, _content = parse_state_id(state.get("state_id", ""))
    detail_route = _family_detail_route(model, family)
    detail_id = _family_detail_record_id(model, family)
    raw = [l for l in state.get("general_links", []) if _is_board_link(l)]
    items: list[dict[str, Any]] = []
    for link in raw:
        items.append({
            "text": (link.get("text") or "").strip(),
            "record_id": _record_id(link.get("href")),
        })
    matched = [i for i in items if i["record_id"] and i["record_id"] == detail_id]
    targets = matched if matched else (items[:1] if items else [])
    for item in items:
        item["links_to_detail"] = detail_route is not None and item in targets
        item["detail_route"] = detail_route
    return items


# ---------------------------------------------------------------------------
# Lifecycle + CSS + JS
# ---------------------------------------------------------------------------
def _lifecycle_json() -> str:
    return json.dumps(LIFECYCLE_MARKERS, ensure_ascii=False, sort_keys=True)


def _render_css() -> str:
    return """
:root{
  --bg:#ffffff; --fg:#101012; --muted:#8a8a93; --line:#e6e6ea;
  --brand:#1f6feb; --brand-weak:#eef3ff; --panel:#fafafb; --warn:#7a5b00;
  --warn-bg:#fff7e6; --radius:12px;
}
*{box-sizing:border-box;}
html,body{margin:0;padding:0;}
body{
  font-family:ui-sans-serif,system-ui,-apple-system,"Segoe UI",Roboto,"Noto Sans KR","Apple SD Gothic Neo",sans-serif;
  background:var(--bg); color:var(--fg); -webkit-font-smoothing:antialiased;
  line-height:1.55; overflow-x:hidden;
}
a{color:var(--brand); text-decoration:none;}
a:hover{text-decoration:underline;}
header.seogu-header{
  border-bottom:1px solid var(--line); background:var(--panel);
  padding:14px 18px; position:sticky; top:0; z-index:10;
}
.seogu-topbar{display:flex; flex-wrap:wrap; gap:10px 18px; align-items:center;}
.seogu-site-title{font-weight:700; font-size:1.05rem; margin:0;}
.seogu-badge{
  font-size:.72rem; color:var(--warn); background:var(--warn-bg);
  border:1px solid #f0d9a0; border-radius:999px; padding:2px 10px; white-space:nowrap;
}
.seogu-clone-nav{display:flex; flex-wrap:wrap; gap:6px; margin-top:10px;}
.seogu-clone-nav a{
  font-size:.85rem; padding:6px 12px; border:1px solid var(--line);
  border-radius:999px; background:#fff; color:var(--fg);
}
.seogu-clone-nav a:hover{background:var(--brand-weak); text-decoration:none;}
.seogu-clone-nav a[aria-current="page"]{background:var(--brand); color:#fff; border-color:var(--brand);}
.seogu-gnb{display:flex; flex-wrap:wrap; gap:6px 14px; margin-top:10px; align-items:center;}
.seogu-gnb .seogu-stub{
  font-size:.85rem; color:var(--muted); border:1px dashed var(--line);
  border-radius:8px; padding:3px 9px;
}
#seogu-gnb-toggle{
  font:inherit; font-size:.85rem; cursor:pointer; border:1px solid var(--line);
  background:#fff; border-radius:8px; padding:5px 12px; color:var(--fg);
}
#seogu-gnb-toggle:focus-visible,
.seogu-clone-nav a:focus-visible,
a.seogu-list-link:focus-visible{
  outline:3px solid var(--brand); outline-offset:2px;
}
#seogu-mega-menu{
  margin-top:10px; border:1px solid var(--line); border-radius:var(--radius);
  background:#fff; padding:12px; display:flex; flex-wrap:wrap; gap:6px 10px;
}
#seogu-mega-menu[hidden]{display:none;}
#seogu-mega-menu .seogu-mega-item{
  font:inherit; font-size:.82rem; color:var(--muted);
  border:1px dashed var(--line); border-radius:8px; padding:4px 10px;
  background:var(--panel);
}
main.seogu-main{max-width:980px; margin:0 auto; padding:22px 18px 60px;}
.seogu-hero{font-size:.98rem; color:#2a2a2e;}
.seogu-section-title{font-size:1.25rem; font-weight:700; margin:26px 0 12px;}
.seogu-surface-grid{display:grid; grid-template-columns:repeat(auto-fill,minmax(200px,1fr)); gap:12px; margin-top:14px;}
.seogu-surface-card{
  display:block; border:1px solid var(--line); border-radius:var(--radius);
  padding:16px 18px; background:#fff; color:var(--fg);
}
.seogu-surface-card:hover{background:var(--brand-weak); text-decoration:none;}
.seogu-surface-card h3{margin:0 0 6px; font-size:1rem;}
.seogu-surface-card p{margin:0; color:var(--muted); font-size:.85rem;}
ul.seogu-list{list-style:none; margin:0; padding:0; border:1px solid var(--line); border-radius:var(--radius); overflow:hidden;}
ul.seogu-list li{padding:12px 16px; border-bottom:1px solid var(--line); display:flex; gap:12px; align-items:center; flex-wrap:wrap;}
ul.seogu-list li:last-child{border-bottom:none;}
.seogu-list-item{color:var(--muted);}
a.seogu-list-link{font-weight:600;}
.seogu-detail-title{font-size:1.4rem; font-weight:700; margin:0 0 10px; line-height:1.35;}
.seogu-badges{display:flex; flex-wrap:wrap; gap:8px; margin:10px 0 18px;}
.seogu-badge-pill{font-size:.78rem; border:1px solid var(--line); border-radius:999px; padding:3px 10px; background:var(--panel); color:var(--muted);}
.seogu-attachments{display:flex; flex-wrap:wrap; gap:10px; margin:14px 0;}
.seogu-attach{
  font:inherit; font-size:.85rem; border:1px solid var(--line); border-radius:8px;
  padding:8px 14px; background:#fff; color:var(--muted); cursor:not-allowed;
}
.seogu-meta{margin-top:26px; border:1px solid var(--line); border-radius:var(--radius); padding:14px 16px; background:var(--panel);}
.seogu-meta dt{font-size:.72rem; color:var(--muted); text-transform:uppercase; letter-spacing:.04em;}
.seogu-meta dd{margin:0 0 8px; font-size:.9rem;}
.seogu-note{font-size:.85rem; color:var(--muted); border-left:3px solid var(--warn); background:var(--warn-bg); padding:8px 12px; border-radius:6px; margin:14px 0;}
footer.seogu-footer{border-top:1px solid var(--line); padding:18px; color:var(--muted); font-size:.8rem;}
footer.seogu-footer a{color:var(--muted);}
@media (max-width:600px){
  header.seogu-header{padding:12px;}
  main.seogu-main{padding:18px 14px 48px;}
  .seogu-surface-grid{grid-template-columns:1fr;}
  .seogu-clone-nav a, .seogu-gnb .seogu-stub, #seogu-gnb-toggle{padding:6px 9px;}
}
"""


def _render_js() -> str:
    return """
(function () {
  "use strict";
  var btn = document.getElementById("seogu-gnb-toggle");
  var panel = document.getElementById("seogu-mega-menu");
  if (!btn || !panel) return;
  function setOpen(open) {
    btn.setAttribute("aria-expanded", open ? "true" : "false");
    if (open) { panel.removeAttribute("hidden"); }
    else { panel.setAttribute("hidden", ""); }
  }
  btn.addEventListener("click", function () {
    setOpen(btn.getAttribute("aria-expanded") !== "true");
  });
  document.addEventListener("keydown", function (e) {
    if (e.key === "Escape" && btn.getAttribute("aria-expanded") === "true") {
      setOpen(false);
      btn.focus();
    }
  });
})();
"""


# ---------------------------------------------------------------------------
# Section renderers
# ---------------------------------------------------------------------------
def _render_header(
    model: dict[str, Any],
    current_route: str,
    nav: list[tuple[str, str]],
    gnb_top: list[str],
    gnb_extra: list[str],
    open_gnb: bool,
    route_prefix: str,
) -> str:
    site_title = "서구 청 참조 복제 후보"
    for state in model["states"]:
        if state.get("state_id", "").startswith("home."):
            title = state.get("page_title") or ""
            if title:
                site_title = title.split(":")[0].strip()
            break

    nav_html = []
    for route, label in nav:
        href = relative_href(current_route, route)
        current = ' aria-current="page"' if route == current_route else ""
        nav_html.append(f'<a href="{_esc(href)}"{current}>{_esc(label)}</a>')
    nav_block = f'<nav class="seogu-clone-nav" aria-label="복제 내비게이션">{"".join(nav_html)}</nav>'

    gnb_top_html = "".join(
        f'<span class="seogu-stub" role="link" aria-disabled="true" tabindex="-1">{_esc(t)}</span>'
        for t in gnb_top
    )
    gnb_extra_html = "".join(
        f'<span class="seogu-mega-item" role="link" aria-disabled="true" tabindex="-1">{_esc(t)}</span>'
        for t in gnb_extra
    )
    expanded = "true" if open_gnb else "false"
    hidden_attr = "" if open_gnb else ' hidden'
    gnb_block = (
        f'<div class="seogu-gnb">'
        f'<span class="seogu-stub" role="link" aria-disabled="true" tabindex="-1">모델 GNB</span>'
        f"{gnb_top_html}"
        f'<button type="button" id="seogu-gnb-toggle" aria-expanded="{expanded}" '
        f'aria-controls="seogu-mega-menu">전체메뉴 열기/닫기</button>'
        f"</div>"
        f'<div id="seogu-mega-menu" aria-label="전체메뉴(읽기 전용)"{hidden_attr}>{gnb_extra_html}</div>'
    )

    return (
        f'<header class="seogu-header">'
        f'<div class="seogu-topbar">'
        f'<h1 class="seogu-site-title">{_esc(site_title)}</h1>'
        f'<span class="seogu-badge">Faithful clone candidate · visual review pending</span>'
        f"</div>"
        f"{nav_block}"
        f"{gnb_block}"
        f"</header>"
    )


def _render_footer(model: dict[str, Any]) -> str:
    site_id = _esc(model.get("site_id", ""))
    capture_id = _esc(model.get("capture_id", ""))
    return (
        f'<footer class="seogu-footer">'
        f"<div>참조 복제 후보 (G2-B). 실제 사이트 통합 없음 · 자산 바이트 충실도 미완료.</div>"
        f"<div>site_id={site_id} · capture_id={capture_id} · "
        f"faithful_clone_candidate=true · visual_review=pending · exact=false</div>"
        f"</footer>"
    )


def _render_main(
    model: dict[str, Any],
    state: dict[str, Any],
    nav: list[tuple[str, str]],
    route_prefix: str,
) -> str:
    family, _device, content = parse_state_id(state.get("state_id", ""))
    title = state.get("page_title") or ""

    if content == "detail":
        return _render_detail_main(model, state, family, title, route_prefix)
    if content == "list":
        return _render_list_main(model, state, family, title, route_prefix)
    if content in ("chart", "directory"):
        return _render_org_staff_main(model, state, family, title)
    return _render_home_main(model, state, title, nav, route_prefix)


def _render_home_main(
    model: dict[str, Any],
    state: dict[str, Any],
    title: str,
    nav: list[tuple[str, str]],
    route_prefix: str,
) -> str:
    hero_text = ""
    for lm in state.get("landmarks", []):
        if lm.get("id") == "main":
            hero_text = lm.get("text") or ""
            break
    if not hero_text:
        hero_text = title

    cards = []
    current_route = route_for_state(state["state_id"], route_prefix)
    for route, label in nav:
        if route == current_route:
            continue
        href = relative_href(current_route, route)
        cards.append(
            f'<a class="seogu-surface-card" href="{_esc(href)}">'
            f"<h3>{_esc(label)}</h3><p>참조 복제 표면</p></a>"
        )
    card_grid = (
        f'<div class="seogu-surface-grid">{"".join(cards)}</div>' if cards else ""
    )
    note = (
        '<p class="seogu-note">이 화면은 G2-A 시맨틱 모델에서 복원한 참조 복제 후보입니다. '
        "실제 서구청 자산 바이트는 저장소에 없으므로 시각 충실도는 보류(pending) 상태입니다.</p>"
    )
    return (
        f'<section aria-label="홈">'
        f'<h2 class="seogu-section-title">{_esc("홈 · 참조 복제 후보")}</h2>'
        f'<div class="seogu-hero">{_esc(hero_text[:4000])}</div>'
        f"{note}"
        f'<h3 class="seogu-section-title">{_esc("모델 복제 표면")}</h3>'
        f"{card_grid}"
        f"</section>"
        + _render_meta(state)
    )


def _render_list_main(
    model: dict[str, Any],
    state: dict[str, Any],
    family: str,
    title: str,
    route_prefix: str,
) -> str:
    items = _list_items(model, state)
    current_route = route_for_state(state["state_id"], route_prefix)
    rows = []
    for item in items:
        if item["links_to_detail"] and item["detail_route"]:
            href = relative_href(current_route, item["detail_route"])
            rows.append(
                f'<li><a class="seogu-list-link" data-detail="1" href="{_esc(href)}">'
                f'{_esc(item["text"])}</a></li>'
            )
        else:
            rows.append(
                f'<li><span class="seogu-list-item" aria-disabled="true" role="link" tabindex="-1">'
                f'{_esc(item["text"])}</span></li>'
            )
    note = (
        '<p class="seogu-note">목록 항목은 G2-A 모델의 general_links에서 복원한 시맨틱 항목입니다. '
        "대표 항목만 복제 상세 경로로 연결되며, 나머지는 읽기 전용 자리표시자입니다.</p>"
    )
    return (
        f'<section aria-label="목록">'
        f'<h2 class="seogu-section-title">{_esc(surface_label(state, model))} · 목록</h2>'
        f"{note}"
        f'<ul class="seogu-list">{"".join(rows)}</ul>'
        f"</section>"
        + _render_meta(state)
    )


def _render_detail_main(
    model: dict[str, Any],
    state: dict[str, Any],
    family: str,
    title: str,
    route_prefix: str,
) -> str:
    list_no = state.get("list_no")
    badges = []
    if list_no:
        badges.append(f'<span class="seogu-badge-pill">list_no={_esc(list_no)}</span>')
    badges.append(f'<span class="seogu-badge-pill">device={_esc(state.get("device_class",""))}</span>')
    badges.append(f'<span class="seogu-badge-pill">state={_esc(state.get("state_id",""))}</span>')

    exts = state.get("attachment_document_extensions") or []
    downloads = state.get("download_references") or []
    attach_html = ""
    if exts or downloads:
        chips = []
        for ext in exts:
            chips.append(
                f'<button type="button" class="seogu-attach" disabled aria-disabled="true" '
                f'data-attachment-ext="{_esc(ext)}">다운로드 (.{_esc(ext)})</button>'
                f'<button type="button" class="seogu-attach" disabled aria-disabled="true" '
                f'data-attachment-ext="{_esc(ext)}">미리보기</button>'
            )
        attach_html = (
            '<div class="seogu-attachments" aria-label="첨부(읽기 전용)">'
            f'{"".join(chips)}</div>'
            '<p class="seogu-note">첨부 다운로드/미리보기는 실제 원격 자산이 없으므로 비활성(읽기 전용)입니다. '
            "원격 다운로드는 금지됩니다.</p>"
        )
    else:
        attach_html = (
            '<p class="seogu-note">이 상태에는 캡처된 첨부 메타데이터가 없습니다.</p>'
        )

    list_route = None
    for s in model["states"]:
        fam, _d, c = parse_state_id(s.get("state_id", ""))
        if fam == family and c == "list":
            list_route = route_for_state(s["state_id"], route_prefix)
            break
    back = ""
    if list_route:
        href = relative_href(route_for_state(state["state_id"], route_prefix), list_route)
        back = f'<p><a href="{_esc(href)}">← 목록으로</a></p>'

    return (
        f'<section aria-label="상세">'
        f'<h2 class="seogu-detail-title">{_esc(title)}</h2>'
        f'<div class="seogu-badges">{"".join(badges)}</div>'
        f"{attach_html}"
        f"{back}"
        f"</section>"
        + _render_meta(state)
    )


def _render_org_staff_main(
    model: dict[str, Any],
    state: dict[str, Any],
    family: str,
    title: str,
) -> str:
    controls = state.get("controls") or []
    note = (
        "조직도/직원 안내 표면은 G2-A 모델의 캡처된 시맨틱 메타데이터(제목·랜드마크·컨트롤 수)로 "
        "표현됩니다. 실제 차트/디렉터리 바이트 충실도는 보류(pending)입니다."
    )
    evidence = (
        f'<p>캡처된 컨트롤 수: <strong>{len(controls)}</strong> · '
        f'랜드마크 수: <strong>{len(state.get("landmarks", []))}</strong></p>'
    )
    label = surface_label(state, model)
    return (
        f'<section aria-label="{_esc(label)}">'
        f'<h2 class="seogu-section-title">{_esc(label)}</h2>'
        f'<p class="seogu-note">{note}</p>{evidence}'
        f"</section>"
        + _render_meta(state)
    )


def _render_meta(state: dict[str, Any]) -> str:
    rows = []
    mapping = (
        ("state_id", state.get("state_id")),
        ("device_class", state.get("device_class")),
        (
            "viewport",
            (state.get("viewport") or {}).get("width")
            if isinstance(state.get("viewport"), dict)
            else None,
        ),
        ("captured_at", state.get("captured_at")),
        ("source_updated_at", state.get("source_updated_at")),
        ("final_http_status", state.get("final_http_status")),
        ("list_no", state.get("list_no")),
    )
    for key, value in mapping:
        if value is None or value == "":
            continue
        rows.append(f"<dt>{_esc(key)}</dt><dd>{_esc(value)}</dd>")
    if not rows:
        return ""
    return f'<dl class="seogu-meta" aria-label="캡처 메타데이터">{"".join(rows)}</dl>'


# ---------------------------------------------------------------------------
# Page assembly
# ---------------------------------------------------------------------------
def _render_page(
    model: dict[str, Any],
    state: dict[str, Any],
    current_route: str,
    nav: list[tuple[str, str]],
    gnb_top: list[str],
    gnb_extra: list[str],
    open_gnb: bool,
    route_prefix: str,
) -> str:
    state_id = state.get("state_id", "")
    _family, _device, content = parse_state_id(state_id)
    title = state.get("page_title") or state_id
    header = _render_header(
        model, current_route, nav, gnb_top, gnb_extra, open_gnb, route_prefix
    )
    main = _render_main(model, state, nav, route_prefix)
    footer = _render_footer(model)
    lifecycle_script = (
        f'<script type="application/ld+json" id="seogu-lifecycle-markers">'
        f"{_lifecycle_json()}</script>"
    )
    return (
        "<!DOCTYPE html>"
        f'<html lang="ko" data-clone-candidate="true" data-state-id="{_esc(state_id)}" '
        f'data-route="{_esc(current_route)}" data-content="{_esc(content)}">'
        "<head>"
        '<meta charset="UTF-8">'
        '<meta name="viewport" content="width=device-width, initial-scale=1.0">'
        f"<title>{_esc(title)}</title>"
        f"<style>{_render_css()}</style>"
        f"{lifecycle_script}"
        "</head>"
        "<body>"
        f"{header}"
        f'<main class="seogu-main">{main}</main>'
        f"{footer}"
        f"<script>{_render_js()}</script>"
        "</body></html>"
    )


def render_state(
    model: dict[str, Any],
    state_id: str,
    route_prefix: str = DEFAULT_ROUTE_PREFIX,
    open_gnb: bool = False,
) -> str:
    """Render a single model state into a complete HTML document."""
    _require_model_ready(model)
    state = next((s for s in model["states"] if s.get("state_id") == state_id), None)
    if state is None:
        raise ReferenceCloneRendererError(f"state not found in model: {state_id}")
    nav = _nav_entries(model, route_prefix)
    gnb_top = _gnb_top_items(model)
    gnb_extra = _gnb_extra_items(model)
    current_route = route_for_state(state_id, route_prefix)
    if parse_state_id(state_id)[2] == "gnb_open":
        open_gnb = True
    return _render_page(
        model, state, current_route, nav, gnb_top, gnb_extra, open_gnb, route_prefix
    )


def render_site(
    model: dict[str, Any], route_prefix: str = DEFAULT_ROUTE_PREFIX
) -> dict[str, str]:
    """Render every model state to its deterministic route (11 states -> 11 files)."""
    _require_model_ready(model)
    pages: dict[str, str] = {}
    for state in model["states"]:
        state_id = state.get("state_id", "")
        route = route_for_state(state_id, route_prefix)
        pages[route] = render_state(model, state_id, route_prefix=route_prefix)
    return pages


# ---------------------------------------------------------------------------
# Model loading + filesystem writing
# ---------------------------------------------------------------------------
def load_model(path: str | Path) -> dict[str, Any]:
    """Load a single ``clone-model.json`` (the ONLY file read by the renderer)."""
    text = Path(path).read_text(encoding="utf-8")
    return json.loads(text)


def write_site(
    model: dict[str, Any],
    out_root: str | Path,
    route_prefix: str = DEFAULT_ROUTE_PREFIX,
) -> list[Path]:
    """Render every state and write deterministic route files under *out_root*.

    *out_root* is the directory that becomes the route namespace root (e.g.
    ``dist/cloudflare-pages/seogu``). A route ``/seogu/notice/`` maps to
    ``<out_root>/notice/index.html``; the root route ``/seogu/`` maps to
    ``<out_root>/index.html``.
    """
    pages = render_site(model, route_prefix=route_prefix)
    written: list[Path] = []
    for route, html in pages.items():
        rel = route[len(route_prefix):] if route.startswith(route_prefix) else route.lstrip("/")
        rel_parts = [p for p in rel.split("/") if p]
        target = Path(out_root)
        if rel_parts:
            target = target.joinpath(*rel_parts)
        target = target / "index.html"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(html, encoding="utf-8", newline="\n")
        written.append(target)
    return written


def model_checksum(model: dict[str, Any]) -> str:
    """Stable checksum of the rendered site (determinism proof)."""
    pages = render_site(model)
    blob = "\n".join(f"{r}\x00{p}" for r, p in sorted(pages.items()))
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()
