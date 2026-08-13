"""Generic, model-driven faithful-clone renderer for #1303 G2-B.

This module is the G2-B faithful-clone *candidate* renderer. It is the ONLY
runtime consumer of the G2-A semantic model document and of the validated
visual contract. It never reads raw capture evidence (committed per-state
source HTML, viewport screenshots, visible-region inventory, capture ledger,
provenance manifest, live reference URLs, or the capture artifact tree). All
semantics are taken from the model dict; all presentation values are taken from
the *validated* visual contract dict produced by
``src/official_clone/visual_contract.py``.

Fail-closed contract:
  * ``load_model`` reads a single ``clone-model.json`` file only.
  * ``render_state`` / ``render_site`` raise if the model's
    ``claim_gates.reference_baseline_ready`` is not ``True``.
  * The renderer is generic: routing, surface labels, and list/detail linking
    are derived from ``state_id`` structure and ``page_title`` text. There is
    NO per-site conditional branch and NO site-specific literal.
  * Presentation (CSS) is derived ONLY from the validated visual contract.
    Every measured value is consumed as-is; no hand-authored color, radius,
    max-width, or breakpoint is ever emitted. Values that are null/gap in the
    contract are omitted from the CSS (fail-closed on that fidelity).
  * ``faithful_clone_candidate`` is True ONLY when the provided visual contract
    is validated and its required measured fields are present. A null/pending
    contract renders a structural-only page with ``faithful_clone_candidate``
    False. ``visual_review`` always stays ``pending``.

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

Resident-visible surface:
  * No developer/debug metadata is shown to residents. Capture identifiers,
    timestamps, HTTP status, state ids, and visual-input-gap messages are
    rendered as hidden machine-readable JSON only (QA evidence), never as
    visible text.
"""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any

# Generic lifecycle markers required by the G2-B contract. These are explicit
# candidate-status flags; they are NOT visual-approval / production claims.
# They are emitted as hidden machine-readable JSON-LD only — no visible badge,
# no footer text, no developer-facing UI. ``faithful_clone_candidate`` is
# recomputed from the validated visual contract at render time.
_BASE_LIFECYCLE_MARKERS = {
    "visual_review": "pending",
    "clone_mvp_ready": False,
    "resident_default": False,
    "exact": False,
    "golden": False,
    "actual_site_integrated": False,
    "production_ready": False,
    "asset_byte_fidelity_complete": False,
}

# Board-record identifier tokens shared across municipal board systems.
_BOARD_ID_TOKENS = ("list_no", "not_ancmt_mgt_no")

# Device classes recognised in a state_id's middle segment.
_DEVICE_CLASSES = ("desktop", "mobile")

# Required measured theme fields: the renderer derives its CSS from exactly
# these dotted paths. A contract is faithful-ready only when every one of them
# is present and non-null. Mobile (390px) geometry is required too: desktop-only
# evidence cannot promote a faithful candidate.
REQUIRED_THEME_FIELDS = (
    "layout.header.height_px",
    "layout.gnb.height_px",
    "layout.main.max_width_px",
    "layout.footer.height_px",
    "colors.primary",
    "colors.background",
    "colors.header_bg",
    "colors.gnb_bg",
    "colors.gnb_text",
    "colors.footer_bg",
    "colors.text",
    "colors.text_muted",
    "colors.border",
    "typography.font_family",
    "typography.text_color",
    "border.width",
    "border.color",
    "responsive.mobile.header_height_px",
    "responsive.mobile.gnb_height_px",
    "responsive.mobile.max_width_px",
    "responsive.mobile.main_padding_x",
)

# Non-fidelity presentation defaults. These are structural/accessibility
# implementation defaults that do NOT represent measured official-site values;
# they are NOT counted as faithful visual evidence and do NOT gate
# faithful_clone_candidate. Values here are either driven by measured contract
# fields (colors, dimensions) or are generic accessibility defaults that any
# readable HTML clone needs regardless of provenance:
#   * font-size: browser default (no measured site font size);
#   * font-weight: 700 site title / 600 current nav (accessibility emphasis);
#   * border-style: solid / dashed (structural separators);
#   * focus outline width/offset: 2px (keyboard accessibility);
#   * link underline: default navigation affordance;
#   * border radius: none (not measured);
#   * responsive breakpoint: none (mobile is a separate route).
NON_FIDELITY_PRESENTATION_DEFAULTS = {
    "font_size": "browser-default",
    "font_weight_site_title": "700",
    "font_weight_current_nav": "600",
    "border_style": "solid",
    "stub_border_style": "dashed",
    "focus_outline_width_px": 2,
    "focus_outline_offset_px": 2,
    "link_decoration": "underline",
    "border_radius": None,
    "responsive_breakpoint": None,
}


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
# Visual contract consumption (validated dict only)
# ---------------------------------------------------------------------------
def _get_path(contract: dict[str, Any] | None, dotted: str) -> Any:
    if not contract:
        return None
    node: Any = contract
    for part in dotted.split("."):
        if not isinstance(node, dict) or part not in node:
            return None
        node = node[part]
    return node


def faithful_ready(visual_contract: dict[str, Any] | None) -> bool:
    """A validated visual contract is faithful-ready iff it was produced by
    ``validate_visual_contract()`` (has a full ``readiness`` section whose
    ``faithful_ready`` is ``True``) and every required measured field is present
    and non-null.

    A raw (unvalidated) contract never carries the ``readiness`` block, so this
    function returns ``False`` for it — the renderer requires the validator gate.
    """
    if not visual_contract:
        return False
    readiness = visual_contract.get("readiness")
    if not isinstance(readiness, dict):
        return False
    if not bool(readiness.get("faithful_ready")):
        return False

    # Verify the readiness dict was produced by the validator: all of its
    # computed fields must be present and the field count must match the
    # renderer's own required field set. This prevents trivial spoofing
    # (e.g. ``{"readiness": {"faithful_ready": True}}``).
    for key in (
        "schema_version",
        "required_measured_count",
        "measured_required_count",
        "missing_required",
        "measured_value_count",
        "gap_count",
    ):
        if key not in readiness:
            return False
    if readiness.get("required_measured_count") != len(REQUIRED_THEME_FIELDS):
        return False

    return all(_get_path(visual_contract, field) is not None for field in REQUIRED_THEME_FIELDS)


def _lifecycle_markers(visual_contract: dict[str, Any] | None) -> dict[str, Any]:
    markers = dict(_BASE_LIFECYCLE_MARKERS)
    markers["faithful_clone_candidate"] = faithful_ready(visual_contract)
    return markers


def _lifecycle_json(visual_contract: dict[str, Any] | None) -> str:
    return json.dumps(
        _lifecycle_markers(visual_contract), ensure_ascii=False, sort_keys=True
    )


def _theme_values(
    contract: dict[str, Any] | None, device: str = "desktop"
) -> dict[str, Any]:
    """Flatten measured contract values into ``dotted.path -> value``.

    Responsive (mobile) values override desktop values for mobile routes only.
    Values that are null/gap are omitted entirely so the CSS builder never
    emits a guessed substitute.
    """
    values: dict[str, Any] = {}
    if not contract:
        return values

    layout = contract.get("layout") or {}
    for section in ("header", "gnb", "main", "footer"):
        seg = layout.get(section) or {}
        for field in ("height_px", "max_width_px", "padding_x"):
            val = seg.get(field)
            if val is not None:
                values[f"layout.{section}.{field}"] = val

    colors = contract.get("colors") or {}
    for field in (
        "primary",
        "background",
        "header_bg",
        "gnb_bg",
        "gnb_text",
        "footer_bg",
        "text",
        "text_muted",
        "border",
    ):
        val = colors.get(field)
        if val is not None:
            values[f"colors.{field}"] = val

    typo = contract.get("typography") or {}
    if typo.get("font_family"):
        values["typography.font_family"] = typo["font_family"]
    if typo.get("text_color"):
        values["typography.text_color"] = typo["text_color"]

    border = contract.get("border") or {}
    if border.get("width") is not None:
        values["border.width"] = border["width"]
    if border.get("color"):
        values["border.color"] = border["color"]

    if device == "mobile":
        mobile = (contract.get("responsive") or {}).get("mobile") or {}
        for field in (
            "main_padding_x",
            "header_padding_x",
            "max_width_px",
            "header_height_px",
            "gnb_height_px",
        ):
            val = mobile.get(field)
            if val is not None:
                values[f"responsive.mobile.{field}"] = val
    return values


def _pick(
    theme: dict[str, Any], desktop_key: str, mobile_key: str | None, device: str
) -> Any:
    if device == "mobile" and mobile_key and mobile_key in theme:
        return theme[mobile_key]
    return theme.get(desktop_key)


def _font_stack(family: str) -> str:
    """Build a CSS font-family stack from the measured family names plus a
    generic system fallback (no @font-face, no network fetch)."""
    names = [n.strip() for n in family.split(",") if n.strip()]
    quoted = ", ".join(json.dumps(n) for n in names)
    if not quoted:
        return "ui-sans-serif, system-ui, sans-serif"
    return f"{quoted}, ui-sans-serif, system-ui, sans-serif"


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


def route_for_state(state_id: str, route_prefix: str) -> str:
    """Deterministically map a ``state_id`` to its clone route (generic).

    *route_prefix* is caller-provided; there is no hardcoded default.
    """
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


def _family_detail_route(model: dict[str, Any], family: str, route_prefix: str) -> str | None:
    for state in model["states"]:
        fam, _dev, content = parse_state_id(state.get("state_id", ""))
        if fam == family and content == "detail":
            return route_for_state(state["state_id"], route_prefix)
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


def _list_items(
    model: dict[str, Any], state: dict[str, Any], route_prefix: str
) -> list[dict[str, Any]]:
    """Board items for a list surface, with local detail-link targeting."""
    family, _dev, _content = parse_state_id(state.get("state_id", ""))
    detail_route = _family_detail_route(model, family, route_prefix)
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
# CSS (derived strictly from the validated visual contract)
# ---------------------------------------------------------------------------
def _decl(property_name: str, value: Any) -> str:
    return f"{property_name}:{value};"


def _render_css(theme: dict[str, Any], device: str = "desktop") -> str:
    """Build CSS from measured contract values only.

    Every fidelity declaration is derived from a measured value; gaps are
    omitted (fail-closed). No guessed color, radius, max-width, or breakpoint
    exists. Remaining presentation values come from the documented
    ``NON_FIDELITY_PRESENTATION_DEFAULTS`` (accessibility/structural defaults
    that are NOT faithful visual evidence).
    """
    nd = NON_FIDELITY_PRESENTATION_DEFAULTS
    rules: list[str] = ["*{box-sizing:border-box;}", "html,body{margin:0;padding:0;}"]

    body_decls = []
    bg = _pick(theme, "colors.background", None, device)
    if bg:
        body_decls.append(_decl("background", bg))
    text = _pick(theme, "colors.text", None, device)
    if text:
        body_decls.append(_decl("color", text))
    family = theme.get("typography.font_family")
    if family:
        body_decls.append(_decl("font-family", _font_stack(family)))
    rules.append("body{" + "".join(body_decls) + "}")
    # Link underline is a documented accessibility default (non-fidelity).
    rules.append(f"a{{color:inherit;text-decoration:{nd['link_decoration']};}}")

    border = _pick(theme, "colors.border", None, device)
    border_w = theme.get("border.width")
    border_style = nd["border_style"]

    header_bg = _pick(theme, "colors.header_bg", None, device)
    header_h = _pick(theme, "layout.header.height_px", "responsive.mobile.header_height_px", device)
    header_decls = []
    if header_bg:
        header_decls.append(_decl("background", header_bg))
    if border and border_w:
        header_decls.append(_decl("border-bottom", f"{border_w}px {border_style} {border}"))
    if header_h:
        header_decls.append(_decl("min-height", f"{header_h}px"))
    rules.append("header.rc-header{" + "".join(header_decls) + "}")
    rules.append(".rc-topbar{display:flex;flex-wrap:wrap;align-items:center;}")

    gnb_bg = _pick(theme, "colors.gnb_bg", None, device)
    gnb_text = _pick(theme, "colors.gnb_text", None, device)
    gnb_h = _pick(theme, "layout.gnb.height_px", "responsive.mobile.gnb_height_px", device)
    gnb_decls = ["display:flex;flex-wrap:wrap;align-items:center;"]
    if gnb_bg:
        gnb_decls.append(_decl("background", gnb_bg))
    if gnb_text:
        gnb_decls.append(_decl("color", gnb_text))
    if gnb_h:
        gnb_decls.append(_decl("min-height", f"{gnb_h}px"))
    rules.append(".rc-gnb{" + "".join(gnb_decls) + "}")

    primary = _pick(theme, "colors.primary", None, device)
    if primary:
        # Focus outline is a documented keyboard-accessibility default
        # (non-fidelity); the outline color uses the measured primary color.
        rules.append(
            "#rc-gnb-toggle:focus-visible,"
            ".rc-nav a:focus-visible,"
            "a.rc-list-link:focus-visible{"
            + _decl("outline", f"{nd['focus_outline_width_px']}px solid {primary}")
            + _decl("outline-offset", f"{nd['focus_outline_offset_px']}px")
            + "}"
        )
    if border and border_w:
        rules.append(
            "#rc-gnb-toggle,"
            ".rc-nav a,"
            ".rc-gnb .rc-stub,"
            "#rc-mega-menu,"
            "#rc-mega-menu .rc-mega-item,"
            ".rc-surface-card,"
            "ul.rc-list,"
            "ul.rc-list li,"
            ".rc-badge-pill,"
            ".rc-attach,"
            "footer.rc-footer{"
            + _decl("border", f"{border_w}px {border_style} {border}")
            + "}"
        )
        rules.append(
            "ul.rc-list li:last-child{"
            + _decl("border-bottom", "none")
            + "}"
        )
    if border and border_w:
        rules.append(
            ".rc-gnb .rc-stub,"
            "#rc-mega-menu .rc-mega-item{"
            + _decl("border-style", nd["stub_border_style"])
            + "}"
        )
    rules.append(".rc-gnb .rc-stub,#rc-mega-menu .rc-mega-item{background:transparent;}")
    rules.append("#rc-gnb-toggle{font:inherit;cursor:pointer;background:transparent;}")
    rules.append(
        "#rc-mega-menu{display:flex;flex-wrap:wrap;}"
        "#rc-mega-menu[hidden]{display:none;}"
    )

    max_w = _pick(theme, "layout.main.max_width_px", "responsive.mobile.max_width_px", device)
    pad_x = _pick(theme, "layout.main.padding_x", "responsive.mobile.main_padding_x", device)
    main_decls = ["margin:0 auto;"]
    if max_w:
        main_decls.append(_decl("max-width", f"{max_w}px"))
    if pad_x:
        main_decls.append(_decl("padding-left", f"{pad_x}px"))
        main_decls.append(_decl("padding-right", f"{pad_x}px"))
    rules.append("main.rc-main{" + "".join(main_decls) + "}")
    rules.append(
        ".rc-surface-grid{display:flex;flex-wrap:wrap;}"
        ".rc-surface-card{display:block;}"
        "ul.rc-list{list-style:none;margin:0;padding:0;}"
        "ul.rc-list li{display:flex;flex-wrap:wrap;align-items:center;}"
        ".rc-attachments{display:flex;flex-wrap:wrap;}"
        ".rc-attach{font:inherit;cursor:not-allowed;}"
        ".rc-badges{display:flex;flex-wrap:wrap;}"
        # Site-title / current-nav weight are documented accessibility defaults
        # (non-fidelity).
        f".rc-site-title{{font-weight:{nd['font_weight_site_title']};margin:0;}}"
        ".rc-nav{display:flex;flex-wrap:wrap;}"
        f".rc-nav a[aria-current=\"page\"]{{font-weight:{nd['font_weight_current_nav']};}}"
    )

    muted = _pick(theme, "colors.text_muted", None, device)
    if muted:
        rules.append(
            ".rc-gnb .rc-stub,"
            "#rc-mega-menu .rc-mega-item,"
            ".rc-list-item,"
            ".rc-badge-pill,"
            ".rc-attach,"
            "footer.rc-footer{"
            + _decl("color", muted)
            + "}"
        )

    footer_bg = _pick(theme, "colors.footer_bg", None, device)
    footer_h = _pick(theme, "layout.footer.height_px", None, device)
    footer_decls = []
    if footer_bg:
        footer_decls.append(_decl("background", footer_bg))
    if footer_h:
        footer_decls.append(_decl("min-height", f"{footer_h}px"))
    rules.append("footer.rc-footer{" + "".join(footer_decls) + "}")

    return "\n".join(rules)


def _render_js() -> str:
    return """
(function () {
  "use strict";
  var btn = document.getElementById("rc-gnb-toggle");
  var panel = document.getElementById("rc-mega-menu");
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
    site_title = ""
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
    nav_block = f'<nav class="rc-nav" aria-label="내비게이션">{"".join(nav_html)}</nav>'

    gnb_top_html = "".join(
        f'<span class="rc-stub" role="link" aria-disabled="true" tabindex="-1">{_esc(t)}</span>'
        for t in gnb_top
    )
    gnb_extra_html = "".join(
        f'<span class="rc-mega-item" role="link" aria-disabled="true" tabindex="-1">{_esc(t)}</span>'
        for t in gnb_extra
    )
    expanded = "true" if open_gnb else "false"
    hidden_attr = "" if open_gnb else ' hidden'
    gnb_block = (
        f'<div class="rc-gnb">'
        f"{gnb_top_html}"
        f'<button type="button" id="rc-gnb-toggle" aria-expanded="{expanded}" '
        f'aria-controls="rc-mega-menu">전체메뉴</button>'
        f"</div>"
        f'<div id="rc-mega-menu" aria-label="전체메뉴"{hidden_attr}>{gnb_extra_html}</div>'
    )

    return (
        f'<header class="rc-header">'
        f'<div class="rc-topbar">'
        f'<h1 class="rc-site-title">{_esc(site_title)}</h1>'
        f"</div>"
        f"{nav_block}"
        f"{gnb_block}"
        f"</header>"
    )


def _render_footer() -> str:
    # No site/capture identifiers are shown to residents. The footer is a plain
    # themed band; capture lifecycle stays in hidden machine-readable metadata.
    return '<footer class="rc-footer"></footer>'


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
        return _render_org_staff_main(state)
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
            f'<a class="rc-surface-card" href="{_esc(href)}">'
            f"<h3>{_esc(label)}</h3></a>"
        )
    card_grid = (
        f'<div class="rc-surface-grid">{"".join(cards)}</div>' if cards else ""
    )
    return (
        f'<section aria-label="홈">'
        f'<h2 class="rc-section-title">{_esc("홈")}</h2>'
        f'<div class="rc-hero">{_esc(hero_text[:4000])}</div>'
        f"{card_grid}"
        f"</section>"
    )


def _render_list_main(
    model: dict[str, Any],
    state: dict[str, Any],
    family: str,
    title: str,
    route_prefix: str,
) -> str:
    items = _list_items(model, state, route_prefix)
    current_route = route_for_state(state["state_id"], route_prefix)
    rows = []
    for item in items:
        if item["links_to_detail"] and item["detail_route"]:
            href = relative_href(current_route, item["detail_route"])
            rows.append(
                f'<li><a class="rc-list-link" data-detail="1" href="{_esc(href)}">'
                f'{_esc(item["text"])}</a></li>'
            )
        else:
            rows.append(
                f'<li><span class="rc-list-item" aria-disabled="true" role="link" tabindex="-1">'
                f'{_esc(item["text"])}</span></li>'
            )
    return (
        f'<section aria-label="목록">'
        f'<h2 class="rc-section-title">{_esc(surface_label(state, model))} · 목록</h2>'
        f'<ul class="rc-list">{"".join(rows)}</ul>'
        f"</section>"
    )


def _render_detail_main(
    model: dict[str, Any],
    state: dict[str, Any],
    family: str,
    title: str,
    route_prefix: str,
) -> str:
    # list_no is an internal URL/record identifier that is NOT proven to be
    # resident-visible captured content; it is kept only in hidden
    # machine-readable evidence (see _evidence_json), never shown to residents.
    exts = state.get("attachment_document_extensions") or []
    downloads = state.get("download_references") or []
    attach_html = ""
    if exts or downloads:
        chips = []
        for ext in exts:
            chips.append(
                f'<button type="button" class="rc-attach" disabled aria-disabled="true" '
                f'data-attachment-ext="{_esc(ext)}">다운로드 (.{_esc(ext)})</button>'
                f'<button type="button" class="rc-attach" disabled aria-disabled="true" '
                f'data-attachment-ext="{_esc(ext)}">미리보기</button>'
            )
        attach_html = (
            '<div class="rc-attachments" aria-label="첨부">'
            f'{"".join(chips)}</div>'
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
        f'<h2 class="rc-detail-title">{_esc(title)}</h2>'
        f"{attach_html}"
        f"{back}"
        f"</section>"
    )


def _render_org_staff_main(state: dict[str, Any]) -> str:
    """Org/staff surfaces render their captured section label only.

    No fake UI is built from metadata counts and no visual-input-gap wording is
    shown to residents; the gap is recorded in the visual contract and hidden
    machine-readable metadata.
    """
    label = surface_label(state, {})
    return f'<section aria-label="{_esc(label)}"><h2 class="rc-section-title">{_esc(label)}</h2></section>'


def _evidence_json(state: dict[str, Any]) -> str:
    """Hidden machine-readable state evidence for QA (never resident-visible)."""
    viewport = state.get("viewport") or {}
    evidence = {
        "state_id": state.get("state_id"),
        "device_class": state.get("device_class"),
        "captured_at": state.get("captured_at"),
        "source_updated_at": state.get("source_updated_at"),
        "final_http_status": state.get("final_http_status"),
        "viewport_width": viewport.get("width") if isinstance(viewport, dict) else None,
        "list_no": state.get("list_no"),
    }
    return json.dumps(evidence, ensure_ascii=False, sort_keys=True)


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
    visual_contract: dict[str, Any] | None,
) -> str:
    state_id = state.get("state_id", "")
    _family, device, content = parse_state_id(state_id)
    title = state.get("page_title") or state_id
    header = _render_header(
        model, current_route, nav, gnb_top, gnb_extra, open_gnb, route_prefix
    )
    main = _render_main(model, state, nav, route_prefix)
    footer = _render_footer()
    theme = _theme_values(visual_contract, device=device)
    css = _render_css(theme, device=device)
    lifecycle_script = (
        f'<script type="application/ld+json" id="rc-lifecycle">'
        f"{_lifecycle_json(visual_contract)}</script>"
    )
    evidence_script = (
        f'<script type="application/ld+json" id="rc-evidence">'
        f"{_evidence_json(state)}</script>"
    )
    faithful = faithful_ready(visual_contract)
    return (
        "<!DOCTYPE html>"
        f'<html lang="ko" data-clone-candidate="{str(faithful).lower()}" '
        f'data-state-id="{_esc(state_id)}" '
        f'data-route="{_esc(current_route)}" data-content="{_esc(content)}">'
        "<head>"
        '<meta charset="UTF-8">'
        '<meta name="viewport" content="width=device-width, initial-scale=1.0">'
        f"<title>{_esc(title)}</title>"
        f"<style>{css}</style>"
        f"{lifecycle_script}"
        f"{evidence_script}"
        "</head>"
        "<body>"
        f"{header}"
        f'<main class="rc-main">{main}</main>'
        f"{footer}"
        f"<script>{_render_js()}</script>"
        "</body></html>"
    )


def render_state(
    model: dict[str, Any],
    state_id: str,
    route_prefix: str,
    visual_contract: dict[str, Any] | None = None,
    open_gnb: bool = False,
) -> str:
    """Render a single model state into a complete HTML document.

    *route_prefix* is required — there is no hardcoded default. The visual
    contract is re-validated at entry (see ``validate_visual_contract``);
    a ``None`` contract renders structurally with ``faithful_clone_candidate``
    False.
    """
    _require_model_ready(model)
    if visual_contract is not None:
        from official_clone.visual_contract import validate_visual_contract

        visual_contract = validate_visual_contract(visual_contract, model)
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
        model,
        state,
        current_route,
        nav,
        gnb_top,
        gnb_extra,
        open_gnb,
        route_prefix,
        visual_contract,
    )


def render_site(
    model: dict[str, Any],
    route_prefix: str,
    visual_contract: dict[str, Any] | None = None,
) -> dict[str, str]:
    """Render every model state to its deterministic route (11 states -> 11 files).

    *route_prefix* is required — there is no hardcoded default.
    """
    _require_model_ready(model)
    pages: dict[str, str] = {}
    for state in model["states"]:
        state_id = state.get("state_id", "")
        route = route_for_state(state_id, route_prefix)
        pages[route] = render_state(
            model, state_id, route_prefix=route_prefix, visual_contract=visual_contract
        )
    return pages


# ---------------------------------------------------------------------------
# Model loading + filesystem writing
# ---------------------------------------------------------------------------
def load_model(path: str | Path) -> dict[str, Any]:
    """Load a single ``clone-model.json`` (the ONLY file read by the renderer)."""
    return json.loads(Path(path).read_text(encoding="utf-8"))


def write_site(
    model: dict[str, Any],
    out_root: str | Path,
    route_prefix: str,
    visual_contract: dict[str, Any] | None = None,
) -> list[Path]:
    """Render every state and write deterministic route files under *out_root*.

    *route_prefix* is required — there is no hardcoded default.
    *out_root* is the directory that becomes the route namespace root.
    """
    pages = render_site(model, route_prefix=route_prefix, visual_contract=visual_contract)
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
    # Use a default prefix for checksum computation (caller must provide same).
    pages = render_site(model, route_prefix="/clone/")
    blob = "\n".join(f"{r}\x00{p}" for r, p in sorted(pages.items()))
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()
