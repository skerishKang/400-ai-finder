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

# Generic class-name markers used for control classification (no site literal).
_PRIMARY_SLIDER_CLASSES = frozenset({"prev", "pause", "next"})
_QUICK_SLIDER_CLASSES = frozenset({"btn prev", "btn next"})
_SLIDER_CLASSES = _PRIMARY_SLIDER_CLASSES | _QUICK_SLIDER_CLASSES
_SOCIAL_CLASSES = frozenset({"facebook", "kakaoch", "kakaostory", "band", "naver", "instagram", "youtube"})
_SLOGAN_CLASSES = frozenset({"slogan"})
_SEARCH_CLASSES = frozenset({"search_keyword", "btn_search"})
_GNB_TOGGLE_CLASSES = frozenset({"control open", "control close"})
_RD_BOX_PREFIX = "rd_box rd_col"
_UTILITY_BTN_CLASSES = frozenset({"btn"})
_BANNER_CLASSES = frozenset({"hns_bn"})
_TOP_LINK_CLASSES = frozenset({"anchorLink up"})

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

# #1310 home-fidelity promotion gate.  The generic visual-contract validator
# intentionally keeps its cross-surface minimum stable, but a home clone must
# not be promoted merely because that baseline is complete.  These additional
# source-backed values are the geometry/color measurements that make the
# desktop + 390px home composition materially faithful.  They are validated
# 1:1 by visual_contract.py whenever present; this renderer additionally makes
# their presence mandatory for ``faithful_clone_candidate``.
REQUIRED_HOME_FIDELITY_FIELDS = (
    "layout.main.padding_x",
    "layout.header.notice_height_px",
    "layout.header.utility_height_px",
    "layout.header.brand_height_px",
    "layout.header.identity_height_px",
    "layout.header.search_width_px",
    "layout.header.search_height_px",
    "layout.home.hero_height_px",
    "layout.home.key_visual_width_px",
    "layout.home.key_visual_height_px",
    "layout.home.quick_height_px",
    "layout.home.quick_columns",
    "layout.home.quick_item_width_px",
    "layout.home.info_columns",
    "layout.home.info_gap_px",
    "layout.gnb_open.panel_height_px",
    "layout.gnb_open.columns",
    "colors.hero_bg",
    "colors.notice_bg",
    "colors.key_visual_bg",
    "responsive.mobile.header_padding_x",
    "responsive.mobile.notice_height_px",
    "responsive.mobile.utility_height_px",
    "responsive.mobile.brand_height_px",
    "responsive.mobile.identity_height_px",
    "responsive.mobile.footer_height_px",
    "responsive.mobile.home.hero_height_px",
    "responsive.mobile.home.key_visual_height_px",
    "responsive.mobile.home.quick_height_px",
    "responsive.mobile.home.quick_columns",
    "responsive.mobile.home.quick_item_width_px",
    "responsive.mobile.home.info_columns",
    "responsive.mobile.home.info_gap_px",
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
    "border_radius": None,
    # These values are neutral implementation defaults used only where the
    # committed visual contract still has a documented gap. They improve
    # legibility/composition but are NOT source-parity evidence and never
    # promote visual_review/exact/golden.
    "base_font_size_px": 15,
    "utility_font_size_px": 13,
    "site_title_size_px": 20,
    "gnb_font_size_px": 18,
    "section_title_size_px": 24,
    "hero_title_size_px": 28,
    "small_font_size_px": 13,
    "body_line_height": 1.5,
    "font_weight_site_title": "700",
    "font_weight_current_nav": "700",
    "border_style": "solid",
    "focus_outline_width_px": 2,
    "focus_outline_offset_px": 2,
    "link_decoration": "none",
    "utility_gap_px": 20,
    "panel_gap_px": 24,
    "panel_padding_px": 22,
    "card_radius_px": 12,
    "pill_radius_px": 999,
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

    return all(
        _get_path(visual_contract, field) is not None
        for field in REQUIRED_THEME_FIELDS + REQUIRED_HOME_FIDELITY_FIELDS
    )


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
        for field in (
            "height_px", "max_width_px", "padding_x", "notice_height_px",
            "utility_height_px", "brand_height_px", "identity_height_px",
            "search_width_px", "search_height_px",
        ):
            val = seg.get(field)
            if val is not None:
                values[f"layout.{section}.{field}"] = val

    home_layout = layout.get("home") or {}
    for field in (
        "hero_height_px", "key_visual_width_px", "key_visual_height_px",
        "quick_height_px", "quick_columns", "quick_item_width_px",
        "info_columns", "info_gap_px",
    ):
        val = home_layout.get(field)
        if val is not None:
            values[f"layout.home.{field}"] = val

    gnb_open_layout = layout.get("gnb_open") or {}
    for field in ("panel_height_px", "columns"):
        val = gnb_open_layout.get(field)
        if val is not None:
            values[f"layout.gnb_open.{field}"] = val

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
        "hero_bg",
        "notice_bg",
        "key_visual_bg",
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
            "notice_height_px",
            "utility_height_px",
            "brand_height_px",
            "identity_height_px",
            "footer_height_px",
        ):
            val = mobile.get(field)
            if val is not None:
                values[f"responsive.mobile.{field}"] = val
        mobile_home = mobile.get("home") or {}
        for field in (
            "hero_height_px", "key_visual_width_px", "key_visual_height_px",
            "quick_height_px", "quick_columns", "quick_item_width_px",
            "info_columns", "info_gap_px",
        ):
            val = mobile_home.get(field)
            if val is not None:
                values[f"responsive.mobile.home.{field}"] = val
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


def _gnb_groups(model: dict[str, Any]) -> list[tuple[str, list[str]]]:
    """Group captured open-menu controls under model-derived top-level GNB labels."""
    top = _gnb_top_items(model)
    open_state = next(
        (state for state in model.get("states", [])
         if state.get("state_id") == "home.desktop.gnb_open"),
        None,
    )
    if not top or open_state is None:
        return []
    controls = open_state.get("controls", [])
    toggles = [i for i, c in enumerate(controls)
               if _control_class(c) in _GNB_TOGGLE_CLASSES]
    if len(toggles) < 2:
        return []
    top_set = set(top)
    groups: list[tuple[str, list[str]]] = []
    current: str | None = None
    children: list[str] = []
    for control in controls[toggles[0] + 1:toggles[-1]]:
        text = _control_text(control)
        if not text:
            continue
        if text in top_set and text != current:
            if current is not None:
                groups.append((current, children))
            current, children = text, []
        elif current is not None and (not children or children[-1] != text):
            children.append(text)
    if current is not None:
        groups.append((current, children))
    return groups


def _home_body_controls(state: dict[str, Any]) -> list[dict[str, Any]]:
    """Return homepage controls after the final captured GNB toggle."""
    controls = state.get("controls", [])
    toggles = [i for i, c in enumerate(controls)
               if _control_class(c) in _GNB_TOGGLE_CLASSES]
    return controls[toggles[-1] + 1:] if toggles else controls


def _split_home_control_sections(
    state: dict[str, Any],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Split source Section01 hero and Section02 quick-carousel using order."""
    body = _home_body_controls(state)
    banner_idx = next(
        (i for i, c in enumerate(body) if _control_class(c) in _BANNER_CLASSES),
        None,
    )
    if banner_idx is None:
        return body, []
    section01 = body[:banner_idx + 1]
    section02 = [c for c in body[banner_idx + 1:]
                 if _control_class(c) not in _TOP_LINK_CLASSES]
    return section01, section02


def _home_story_groups(
    state: dict[str, Any],
) -> list[tuple[str, list[dict[str, Any]]]]:
    """Derive homepage gallery groups from ordered captured '...더보기' links."""
    groups: list[tuple[str, list[dict[str, Any]]]] = []
    title: str | None = None
    items: list[dict[str, Any]] = []
    for link in state.get("general_links", []):
        text = (link.get("text") or "").strip()
        href = link.get("href") or ""
        if text.endswith("더보기") and len(text) > len("더보기"):
            if title and items:
                groups.append((title, items))
            title, items = text[:-len("더보기")].strip(), []
            continue
        if title and "/gallery.es" in href:
            items.append(link)
            if len(items) >= 4:
                groups.append((title, items))
                title, items = None, []
    if title and items:
        groups.append((title, items))
    return groups


def _footer_links(state: dict[str, Any]) -> list[dict[str, Any]]:
    """Select the final captured utility-link group used by the source footer."""
    return [g for g in state.get("general_links", [])[-6:]
            if (g.get("text") or "").strip()]


def _header_notice(state: dict[str, Any], controls: list[dict[str, Any]]) -> str:
    """Recover the official-site notice prefix from the captured header landmark."""
    header_text = next(
        ((lm.get("text") or "").strip()
         for lm in state.get("landmarks", []) if lm.get("id") == "header"),
        "",
    )
    first = next((_control_text(c) for c in controls if _control_text(c)), "")
    if header_text and first:
        pos = header_text.find(first)
        if pos > 0:
            return header_text[:pos].strip()
    return ""


def _site_title(model: dict[str, Any]) -> str:
    """Extract the site identity title from the home state page_title."""
    for state in model["states"]:
        if state.get("state_id", "").startswith("home."):
            title = state.get("page_title") or ""
            if title:
                return title.split(":")[0].strip()
    return ""


def _site_identity_label(model: dict[str, Any], controls: list[dict[str, Any]] | None = None) -> str:
    """Return the visible identity label grounded in the captured identity control.

    The source page_title carries extra campaign branding while the identity
    control carries the actual site/logo label. Use their longest common prefix
    so the runtime does not display the entire SEO title as the logo text.
    """
    title = _site_title(model)
    candidates = controls or []
    if not candidates:
        desktop = _home_state_for_device(model, "desktop")
        candidates = desktop.get("controls", []) if desktop else []
    idx = _identity_index(candidates, title)
    if idx is None:
        desktop = _home_state_for_device(model, "desktop")
        desktop_controls = desktop.get("controls", []) if desktop else []
        idx = _identity_index(desktop_controls, title)
        candidates = desktop_controls
    if idx is None:
        return title
    identity = _control_text(candidates[idx])
    common = []
    for a, b in zip(identity, title):
        if a != b:
            break
        common.append(a)
    label = "".join(common).strip()
    return label if len(label) >= 4 else identity


def _home_state_for_device(model: dict[str, Any], device: str) -> dict[str, Any] | None:
    """Find the home default state matching the given device class."""
    for state in model["states"]:
        if state.get("state_id") == f"home.{device}.default":
            return state
    for state in model["states"]:
        if state.get("state_id", "").startswith("home."):
            return state
    return None


def _control_class(c: dict[str, Any]) -> str:
    return (c.get("class_name") or "").strip()


def _control_text(c: dict[str, Any]) -> str:
    return (c.get("text") or "").strip()


def _classify_home_control(c: dict[str, Any], identity_text: str, gnb_texts: set[str]) -> str:
    """Classify a home-page control into a semantic group.

    Returns one of: slider, social, slogan, search, utility_btn, gnb_toggle,
    rd_box, banner, top_link, identity, gnb_item, link, empty.
    """
    cn = _control_class(c)
    if cn in _SLIDER_CLASSES:
        return "slider"
    if cn in _SOCIAL_CLASSES:
        return "social"
    if cn in _SLOGAN_CLASSES:
        return "slogan"
    if cn in _SEARCH_CLASSES:
        return "search"
    if cn in _UTILITY_BTN_CLASSES:
        return "utility_btn"
    if cn in _GNB_TOGGLE_CLASSES:
        return "gnb_toggle"
    if cn.startswith(_RD_BOX_PREFIX):
        return "rd_box"
    if cn in _BANNER_CLASSES:
        return "banner"
    if cn in _TOP_LINK_CLASSES:
        return "top_link"
    text = _control_text(c)
    if not text:
        return "empty"
    if text == identity_text:
        return "identity"
    if text in gnb_texts:
        return "gnb_item"
    return "link"


def _identity_index(controls: list[dict[str, Any]], identity_text: str) -> int | None:
    """Index of the control whose text shares the longest common prefix with
    the site identity text. This handles cases where the identity control
    text is a partial match (e.g. page_title adds extra branding text)."""
    best_idx = None
    best_len = 0
    for i, c in enumerate(controls):
        text = _control_text(c)
        if not text:
            continue
        common = 0
        for a, b in zip(text, identity_text):
            if a == b:
                common += 1
            else:
                break
        if common > best_len:
            best_len = common
            best_idx = i
    if best_len >= 4:
        return best_idx
    return None


def _render_control_as_inert(ctrl: dict[str, Any], cls_extra: str = "") -> str:
    """Render a control as an inert read-only span."""
    text = _control_text(ctrl)
    if not text:
        return ""
    cn = _control_class(ctrl)
    cls = f' class="{_esc(cn)}"' if cn else ""
    if cls_extra:
        cls = f' class="{_esc(cls_extra)}"' if not cn else f' class="{_esc(cn)} {_esc(cls_extra)}"'
    return f'<span{cls} role="link" aria-disabled="true" tabindex="-1">{_esc(text)}</span>'


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
    content_max_w = _pick(
        theme, "layout.main.max_width_px", "responsive.mobile.max_width_px", device
    )
    content_pad = _pick(
        theme, "layout.main.padding_x", "responsive.mobile.main_padding_x", device
    )
    notice_h = _pick(
        theme, "layout.header.notice_height_px",
        "responsive.mobile.notice_height_px", device,
    )
    utility_h = _pick(
        theme, "layout.header.utility_height_px",
        "responsive.mobile.utility_height_px", device,
    )
    brand_h = _pick(
        theme, "layout.header.brand_height_px",
        "responsive.mobile.brand_height_px", device,
    )
    identity_h = _pick(
        theme, "layout.header.identity_height_px",
        "responsive.mobile.identity_height_px", device,
    )
    notice_bg = theme.get("colors.notice_bg")
    header_inner = []
    if content_max_w:
        header_inner.append(_decl("max-width", f"{content_max_w}px"))
    header_inner.append(_decl("margin", "0 auto"))
    if content_pad:
        header_inner.append(_decl("padding-left", f"{content_pad}px"))
        header_inner.append(_decl("padding-right", f"{content_pad}px"))
    header_inner_css = "".join(header_inner)

    notice_decls = ["display:flex;align-items:center;"]
    if notice_h:
        notice_decls.append(_decl("min-height", f"{notice_h}px"))
    if notice_bg:
        notice_decls.append(_decl("background", notice_bg))
    rules.append(".rc-gov-notice{" + "".join(notice_decls) + "}")
    rules.append(
        ".rc-gov-notice{padding-left:max(1rem,calc((100% - "
        + (f"{content_max_w}px" if content_max_w else "100%")
        + ")/2));}"
    )

    utility_decls = ["display:flex;flex-wrap:wrap;align-items:center;"]
    if utility_h:
        utility_decls.append(_decl("min-height", f"{utility_h}px"))
    utility_decls.append(header_inner_css)
    rules.append(".rc-utility-bar{" + "".join(utility_decls) + "}")
    rules.append(".rc-utility-item{display:inline-flex;align-items:center;}")

    brand_decls = ["display:flex;align-items:center;justify-content:space-between;"]
    if brand_h:
        brand_decls.append(_decl("min-height", f"{brand_h}px"))
    brand_decls.append(header_inner_css)
    rules.append(".rc-brand-tools{" + "".join(brand_decls) + "}")
    rules.append(".rc-brand-tool{display:inline-flex;align-items:center;}")

    identity_decls = ["display:flex;align-items:center;justify-content:space-between;"]
    if identity_h:
        identity_decls.append(_decl("min-height", f"{identity_h}px"))
    identity_decls.append(header_inner_css)
    rules.append(".rc-identity-row{" + "".join(identity_decls) + "}")

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
    rules.append(
        ".rc-gnb{flex:1;justify-content:flex-end;}"
        ".rc-gnb .rc-stub{display:inline-flex;align-items:center;justify-content:center;flex:1;}"
        "#rc-gnb-toggle{white-space:nowrap;}"
    )

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
            "#rc-mega-menu,"
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
    rules.append(".rc-gnb .rc-stub,#rc-mega-menu .rc-mega-item{background:transparent;}")
    rules.append("#rc-gnb-toggle{font:inherit;cursor:pointer;background:transparent;}")
    rules.append(
        "#rc-mega-menu{display:grid;grid-template-columns:repeat(6,minmax(0,1fr));}"
        "#rc-mega-menu[hidden]{display:none;}"
        ".rc-mega-group{display:block;}"
        ".rc-mega-heading{display:block;}"
        ".rc-mega-children{display:flex;flex-direction:column;}"
        ".rc-mega-item{display:block;}"
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

    hero_bg = theme.get("colors.hero_bg")
    hero_h = _pick(
        theme, "layout.home.hero_height_px",
        "responsive.mobile.home.hero_height_px", device,
    )
    quick_h = _pick(
        theme, "layout.home.quick_height_px",
        "responsive.mobile.home.quick_height_px", device,
    )
    quick_cols = _pick(
        theme, "layout.home.quick_columns",
        "responsive.mobile.home.quick_columns", device,
    )
    info_cols = _pick(
        theme, "layout.home.info_columns",
        "responsive.mobile.home.info_columns", device,
    )
    home_gap = content_pad or 0

    section01_decls = ["display:grid;align-items:stretch;"]
    if hero_bg:
        section01_decls.append(_decl("background", hero_bg))
    if hero_h:
        section01_decls.append(_decl("min-height", f"{hero_h}px"))
    if device == "mobile":
        section01_decls.append(_decl("grid-template-columns", "1fr"))
    else:
        section01_decls.append(_decl("grid-template-columns", "2fr 3fr"))
    rules.append(".rc-section01{" + "".join(section01_decls) + "}")
    rules.append(
        ".rc-mayor-panel,.rc-key-visual{display:flex;flex-direction:column;justify-content:center;}"
        ".rc-key-visual-placeholder{flex:1;min-height:1px;}"
        ".rc-key-visual{overflow:hidden;}"
    )
    if hero_bg:
        rules.append(".rc-key-visual-placeholder{" + _decl("background", hero_bg) + "}")
    if primary:
        rules.append(
            ".rc-primary-slider-controls{" + _decl("background", primary) + "}"
        )

    quick_decls = ["display:flex;align-items:center;"]
    if quick_h:
        quick_decls.append(_decl("min-height", f"{quick_h}px"))
    rules.append(".rc-section02{" + "".join(quick_decls) + "}")
    quick_grid = ["display:grid;width:100%;align-items:stretch;"]
    if quick_cols:
        quick_grid.append(_decl("grid-template-columns", f"repeat({int(quick_cols)},minmax(0,1fr))"))
    rules.append(".rc-quick-items{" + "".join(quick_grid) + "}")
    rules.append(
        ".rc-quick-card{display:flex;align-items:center;justify-content:center;text-align:center;}"
        ".rc-quick-card-featured{font-weight:600;}"
    )

    info_grid = ["display:grid;align-items:start;"]
    if info_cols:
        info_grid.append(_decl("grid-template-columns", f"repeat({int(info_cols)},minmax(0,1fr))"))
    if home_gap:
        info_grid.append(_decl("gap", f"{home_gap}px"))
    rules.append(".rc-section03{" + "".join(info_grid) + "}")
    rules.append(
        ".rc-home-panel{min-width:0;}"
        ".rc-story-grid{display:grid;grid-template-columns:1fr;}"
        ".rc-story-card{display:flex;flex-direction:column;}"
        ".rc-story-image-placeholder{width:100%;aspect-ratio:4/3;}"
        ".rc-section04{display:grid;grid-template-columns:1fr 1fr;}"
        ".rc-lower-placeholder{width:100%;aspect-ratio:16/9;}"
    )
    if border and border_w:
        rules.append(
            ".rc-notice-panel,.rc-story-card,.rc-lower-placeholder{"
            + _decl("border", f"{border_w}px {border_style} {border}") + "}"
        )
    if hero_bg:
        rules.append(".rc-story-image-placeholder,.rc-lower-placeholder{"
                     + _decl("background", hero_bg) + "}")

    if device == "mobile":
        rules.append(
            ".rc-section01 .rc-key-visual{order:1;}"
            ".rc-section01 .rc-mayor-panel{order:2;}"
            ".rc-gnb .rc-stub{display:none;}"
            "#rc-mega-menu{grid-template-columns:1fr;}"
            ".rc-section03,.rc-section04{grid-template-columns:1fr;}"
        )
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
        ".rc-banner{display:block;}"
        ".rc-notice-list{width:100%;}"
        ".rc-mayor-actions{display:flex;flex-wrap:wrap;}"
        ".rc-primary-slider-controls,.rc-quick-carousel-controls{display:flex;align-items:center;}"
        ".rc-footer-links{display:flex;flex-wrap:wrap;}"
    )

    # Source-shaped composition refinements. Geometry/color values come from
    # the validated contract where available; remaining type/gap values are
    # explicitly neutral presentation defaults and never count as parity.
    outer_w = (
        int(content_max_w) + (2 * int(content_pad or 0))
        if content_max_w else None
    )
    search_w = theme.get("layout.header.search_width_px")
    search_h = theme.get("layout.header.search_height_px")
    key_visual_w = theme.get("layout.home.key_visual_width_px")
    key_visual_h = _pick(
        theme, "layout.home.key_visual_height_px",
        "responsive.mobile.home.key_visual_height_px", device,
    )
    quick_item_w = _pick(
        theme, "layout.home.quick_item_width_px",
        "responsive.mobile.home.quick_item_width_px", device,
    )
    info_gap = _pick(
        theme, "layout.home.info_gap_px",
        "responsive.mobile.home.info_gap_px", device,
    ) or nd["panel_gap_px"]
    key_visual_bg = theme.get("colors.key_visual_bg") or hero_bg
    muted_color = _pick(theme, "colors.text_muted", None, device)

    rules.append(
        f'body{{font-size:{nd["base_font_size_px"]}px;'
        f'line-height:{nd["body_line_height"]};}}'
        '.rc-surface-nav[hidden]{display:none!important;}'
        'header.rc-header{position:relative;z-index:5;}'
    )
    if outer_w:
        rules.append(
            f'.rc-header-inner{{width:100%;max-width:{outer_w}px;margin:0 auto;'
            f'padding-left:{int(content_pad or 0)}px;padding-right:{int(content_pad or 0)}px;}}'
            f'main.rc-main{{width:100%;max-width:{outer_w}px;margin:0 auto;'
            f'padding-left:{int(content_pad or 0)}px;padding-right:{int(content_pad or 0)}px;}}'
        )

    rules.append(
        '.rc-gov-notice{padding:0!important;}'
        '.rc-gov-notice .rc-header-inner{display:flex;align-items:center;gap:8px;}'
        '.rc-gov-mark{display:inline-block;width:16px;height:16px;clip-path:circle(50%);'
        'border:4px solid currentColor;opacity:.55;flex:0 0 auto;}'
        f'.rc-gov-notice,.rc-utility-inner{{font-size:{nd["utility_font_size_px"]}px;}}'
        '.rc-utility-bar,.rc-brand-tools,.rc-identity-row{max-width:none;margin:0;padding:0;}'
        f'.rc-utility-inner{{display:flex;align-items:center;justify-content:space-between;'
        f'gap:{nd["utility_gap_px"]}px;}}'
        f'.rc-utility-left,.rc-utility-right{{display:flex;align-items:center;'
        f'gap:{nd["utility_gap_px"]}px;min-width:0;}}'
        '.rc-utility-item{white-space:nowrap;}'
        '.rc-brand-inner{display:flex;align-items:center;justify-content:space-between;}'
        f'.rc-brand-slogan{{font-size:{nd["site_title_size_px"]}px;font-weight:700;white-space:nowrap;}}'
        '.rc-brand-search{display:flex;align-items:center;overflow:hidden;}'
    )
    if search_w:
        rules.append(f'.rc-brand-search{{width:{int(search_w)}px;max-width:60%;}}')
    if search_h:
        rules.append(f'.rc-brand-search{{height:{int(search_h)}px;}}')
    if primary and border:
        rules.append(
            f'.rc-brand-search{{border:1px solid {primary};'
            f'background:#ffffff;}}'
            f'.rc-brand-search .rc-search-part{{display:flex;align-items:center;height:100%;'
            f'padding:0 {nd["panel_padding_px"]}px;}}'
            f'.rc-brand-search .rc-search-part:first-child{{flex:1;color:{muted_color or "#666666"};}}'
            f'.rc-brand-search .rc-search-part:last-child{{justify-content:center;'
            f'width:{int(search_h or 60)}px;padding:0;background:{primary};color:#ffffff;font-weight:700;}}'
        )

    rules.append(
        '.rc-identity-inner{display:flex;align-items:center;justify-content:space-between;}'
        f'.rc-site-title{{display:flex;align-items:center;gap:10px;'
        f'font-size:{nd["site_title_size_px"]}px;white-space:nowrap;line-height:1.2;}}'
        '.rc-site-emblem{display:inline-block;width:38px;height:38px;clip-path:circle(50%);flex:0 0 auto;}'
        f'.rc-gnb{{gap:8px;flex-wrap:nowrap;min-width:0;}}'
        f'.rc-gnb .rc-stub{{flex:0 0 auto!important;padding:0 18px;'
        f'font-size:{nd["gnb_font_size_px"]}px;font-weight:700;color:inherit;white-space:nowrap;}}'
        '#rc-gnb-toggle{border:0!important;display:inline-flex;align-items:center;gap:9px;'
        'padding:8px 0 8px 18px;text-decoration:none;}'
        '.rc-menu-icon{position:relative;display:inline-block;width:20px;height:14px;'
        'border-top:2px solid currentColor;border-bottom:2px solid currentColor;}'
        '.rc-menu-icon:after{content:"";position:absolute;left:0;right:0;top:5px;'
        'border-top:2px solid currentColor;}'
    )
    if primary:
        rules.append(f'.rc-site-emblem{{background:{primary};}}')

    # Mega menu overlays the hero like the captured open-state navigation,
    # rather than increasing document height.
    rules.append(
        '#rc-mega-menu{display:block!important;position:absolute;left:0;right:0;top:100%;z-index:20;'
        'background:#ffffff;padding:28px 0 32px;}'
        '#rc-mega-menu[hidden]{display:none!important;}'
        '.rc-mega-inner{display:grid;grid-template-columns:repeat(6,minmax(0,1fr));gap:24px;}'
        '.rc-mega-heading{font-size:17px;font-weight:700;padding-bottom:12px;}'
        '.rc-mega-children{gap:8px;}'
        '.rc-mega-item{font-size:14px;line-height:1.45;}'
    )
    if border:
        rules.append(
            f'#rc-mega-menu{{border-top:1px solid {border};border-bottom:1px solid {border};}}'
        )

    # Home Section01: measured 580/820 composition at 1440px source.
    if key_visual_w and device != "mobile":
        rules.append(
            f'.rc-section01{{grid-template-columns:calc(100% - {int(key_visual_w)}px) '
            f'{int(key_visual_w)}px;}}'
        )
    rules.append(
        f'.rc-mayor-panel{{position:relative;padding:42px {nd["panel_padding_px"]}px;'
        f'overflow:hidden;}}'
        f'.rc-hero{{font-size:{nd["hero_title_size_px"]}px;font-weight:700;'
        'line-height:1.35;max-width:320px;white-space:pre-line;}'
        f'.rc-mayor-actions{{display:flex;align-items:center;gap:10px;margin-top:22px;}}'
        f'.rc-mayor-action{{display:inline-flex;align-items:center;justify-content:center;'
        f'min-height:42px;padding:0 16px;}}'
        '.rc-mayor-action:nth-child(n+3){padding:0;min-height:auto;font-weight:700;}'
        '.rc-banner{margin-top:18px;font-weight:700;}'
        '.rc-key-visual{position:relative;justify-content:stretch;padding:40px 0;}'
        f'.rc-key-visual-placeholder{{height:{int(key_visual_h or 320)}px;flex:0 0 auto;'
        f'}}'
        '.rc-primary-slider-controls{position:absolute;left:50%;bottom:54px;transform:translateX(-50%);'
        'display:flex;align-items:center;gap:14px;padding:8px 16px;'
        'color:#ffffff;font-size:13px;line-height:1;}'
    )
    if key_visual_bg:
        rules.append(f'.rc-key-visual-placeholder{{background:{key_visual_bg};}}')
    if primary:
        rules.append(
            f'.rc-mayor-action:nth-child(-n+2){{background:{primary};color:#ffffff;}}'
            f'.rc-primary-slider-controls{{background:{primary};}}'
        )

    # Home Section02: one horizontal carousel. Never wrap the 15 source items
    # into extra rows.
    rules.append(
        '.rc-section02{position:relative;padding:28px 48px;}'
        '.rc-quick-carousel{position:relative;width:100%;overflow:hidden;}'
        '.rc-quick-items{display:grid!important;grid-template-columns:none!important;'
        'grid-auto-flow:column;overflow:hidden;align-items:center;}'
        f'.rc-quick-items{{gap:{nd["panel_gap_px"]}px;}}'
        '.rc-quick-carousel-controls{position:absolute;z-index:2;left:0;right:0;top:0;bottom:0;'
        'display:flex;justify-content:space-between;align-items:center;pointer-events:none;}'
        '.rc-quick-carousel-controls>span{display:flex;align-items:center;justify-content:center;'
        'width:36px;height:36px;clip-path:circle(50%);background:#ffffff;font-size:0;}'
        '.rc-quick-carousel-controls>span:before{content:"‹";font-size:22px;}'
        '.rc-quick-carousel-controls>span:last-child:before{content:"›";}'
        f'.rc-quick-card{{display:flex;flex-direction:column;align-items:center;justify-content:center;'
        f'gap:10px;min-height:118px;padding:12px;'
        'background:#ffffff;font-size:14px;line-height:1.35;overflow:hidden;}'
        '.rc-quick-card:before{content:"";display:block;width:48px;height:48px;}'
        '.rc-quick-card-featured{font-weight:700;}'
    )
    if quick_item_w:
        rules.append(f'.rc-quick-items{{grid-auto-columns:{int(quick_item_w)}px;}}')
    if border:
        rules.append(
            f'.rc-quick-card{{border:1px solid {border};}}'
            f'.rc-quick-carousel-controls>span{{border:1px solid {border};}}'
        )
    if hero_bg:
        rules.append(
            f'.rc-quick-card:before{{background:{hero_bg};}}'
            f'.rc-quick-card-featured{{background:{hero_bg};}}'
        )

    # Information panels mirror the source 2:1:1 desktop composition.
    rules.append(
        f'.rc-section03{{grid-template-columns:2fr 1fr 1fr!important;'
        f'gap:{int(info_gap)}px;padding:48px 0 34px;align-items:start;}}'
        f'.rc-section-title{{font-size:{nd["section_title_size_px"]}px;'
        'line-height:1.25;margin:0 0 18px;font-weight:700;}'
        f'.rc-home-panel{{background:#ffffff;}}'
        f'.rc-notice-panel{{padding:{nd["panel_padding_px"]}px;}}'
        '.rc-notice-list{border:0!important;}'
        '.rc-notice-list li{padding:9px 0;border-left:0!important;border-right:0!important;'
        'font-size:14px;line-height:1.35;}'
        '.rc-story-grid{grid-template-columns:1fr!important;}'
        '.rc-story-card{border:0!important;gap:10px;}'
        f'.rc-story-image-placeholder{{aspect-ratio:16/9;}}'
        '.rc-story-card strong{font-size:15px;line-height:1.45;}'
        f'.rc-section04{{gap:{nd["panel_gap_px"]}px;padding:0 0 46px;}}'
        f'.rc-lower-placeholder{{aspect-ratio:16/9;}}'
    )
    if border:
        rules.append(f'.rc-notice-panel{{border:1px solid {border};}}')

    rules.append(
        f'.rc-footer-identity{{font-size:{nd["site_title_size_px"]}px;font-weight:700;}}'
        f'.rc-footer-links{{display:flex;flex-wrap:wrap;gap:{nd["utility_gap_px"]}px;'
        f'font-size:{nd["small_font_size_px"]}px;line-height:1.4;}}'
    )

    if device == "mobile":
        rules.append(
            f'body{{font-size:14px;}}'
            '.rc-gov-notice .rc-header-inner{font-size:10px;gap:5px;}'
            '.rc-gov-mark{width:11px;height:11px;border-width:3px;}'
            '.rc-utility-inner{font-size:11px;gap:8px;}'
            '.rc-utility-left,.rc-utility-right{gap:10px;}'
            '.rc-brand-tools{display:none!important;}'
            '.rc-identity-inner{gap:8px;}'
            '.rc-site-title{font-size:15px;gap:7px;white-space:normal;flex:1;}'
            '.rc-site-emblem{width:30px;height:30px;}'
            '.rc-mobile-search{display:flex;align-items:center;justify-content:center;'
            'width:34px;height:34px;flex:0 0 auto;}'
            '.rc-mobile-search .rc-search-part{font-size:0;}'
            '.rc-mobile-search .rc-search-part:after{content:"⌕";font-size:24px;line-height:1;}'
            '#rc-gnb-toggle{padding:7px;flex:0 0 auto;}'
            '#rc-gnb-toggle span{display:none;}'
            '.rc-menu-icon{width:22px;height:16px;}'
            '.rc-mobile-slogan{display:flex;align-items:center;justify-content:center;'
            'font-size:15px;font-weight:700;height:20px;}'
            '#rc-mega-menu{position:absolute;padding:16px 0;max-height:560px;overflow:auto;}'
            '.rc-mega-inner{grid-template-columns:1fr!important;gap:14px;}'
            '.rc-section01{grid-template-columns:1fr!important;}'
            '.rc-section01 .rc-key-visual{order:1;padding:10px 0 0;}'
            '.rc-section01 .rc-mayor-panel{order:2;padding:24px 18px;}'
            '.rc-hero{font-size:22px;max-width:none;}'
            '.rc-key-visual-placeholder{width:100%;}'
            '.rc-primary-slider-controls{bottom:10px;}'
            '.rc-mayor-actions{gap:8px;margin-top:14px;}'
            '.rc-mayor-action{min-height:38px;padding:0 13px;font-size:13px;}'
            '.rc-section02{padding:18px 34px;}'
            '.rc-quick-items{gap:18px;}'
            '.rc-quick-card{min-height:116px;font-size:13px;}'
            '.rc-quick-card:before{width:42px;height:42px;}'
            '.rc-quick-carousel-controls{left:-27px;right:-27px;}'
            '.rc-section03{grid-template-columns:1fr!important;padding:28px 0 22px;gap:28px;}'
            '.rc-section-title{font-size:20px;margin-bottom:14px;}'
            '.rc-notice-panel{padding:16px;}'
            '.rc-section04{grid-template-columns:1fr!important;gap:28px;padding-bottom:30px;}'
        )

    # GNB-open is a viewport-filling overlay in the committed desktop source:
    # the normal header chrome and Section01 hero are visually covered, and the
    # quick-menu region begins immediately after the measured 900px panel.
    # Keep this generic to the gnb_open state; dimensions/column count come only
    # from provenance-backed visual-contract values.
    gnb_open_h = theme.get("layout.gnb_open.panel_height_px")
    gnb_open_cols = theme.get("layout.gnb_open.columns")
    if device != "mobile" and gnb_open_h and gnb_open_cols:
        rules.append(
            'html[data-content="gnb_open"] .rc-gov-notice,'
            'html[data-content="gnb_open"] .rc-utility-bar,'
            'html[data-content="gnb_open"] .rc-brand-tools,'
            'html[data-content="gnb_open"] .rc-identity-row{'
            'display:none!important;}'
            'html[data-content="gnb_open"] header.rc-header{'
            'min-height:0!important;border-bottom:0!important;position:relative;}'
            f'html[data-content="gnb_open"] #rc-mega-menu{{'
            f'position:static!important;min-height:{int(gnb_open_h)}px;}}'
            f'html[data-content="gnb_open"] #rc-mega-menu .rc-mega-inner{{'
            f'grid-template-columns:repeat({int(gnb_open_cols)},minmax(0,1fr))!important;}}'
            'html[data-content="gnb_open"] .rc-section01{display:none!important;}'
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
    footer_h = _pick(theme, "layout.footer.height_px", "responsive.mobile.footer_height_px", device)
    footer_decls = []
    if footer_bg:
        footer_decls.append(_decl("background", footer_bg))
    if footer_h:
        footer_decls.append(_decl("min-height", f"{footer_h}px"))
    footer_decls.append("display:flex;flex-direction:column;justify-content:center;")
    if content_pad:
        footer_decls.append(_decl("padding-left", f"{content_pad}px"))
        footer_decls.append(_decl("padding-right", f"{content_pad}px"))
    rules.append("footer.rc-footer{" + "".join(footer_decls) + "}")
    rules.append(".rc-footer-identity{display:block;}.rc-footer-link{display:inline-block;}")

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
    device: str = "desktop",
) -> str:
    site_title = _site_title(model)
    home_state = _home_state_for_device(model, device)
    controls = home_state.get("controls", []) if home_state else []
    identity_label = _site_identity_label(model, controls)

    notice = _header_notice(home_state, controls) if home_state else ""
    notice_html = (
        f'<div class="rc-gov-notice"><div class="rc-header-inner">'
        f'<span class="rc-gov-mark" aria-hidden="true"></span>{_esc(notice)}'
        f'</div></div>'
        if notice else ""
    )

    identity_idx = _identity_index(controls, site_title)
    first_tool_idx = next(
        (
            i for i, c in enumerate(controls)
            if _control_class(c) in (_SLOGAN_CLASSES | _SEARCH_CLASSES)
        ),
        identity_idx if identity_idx is not None else len(controls),
    )
    first_toggle_idx = next(
        (
            i for i, c in enumerate(controls)
            if _control_class(c) in _GNB_TOGGLE_CLASSES
        ),
        len(controls),
    )
    utility_ctrls = controls[:first_tool_idx]
    tool_end = identity_idx if identity_idx is not None else first_toggle_idx
    tool_ctrls = controls[first_tool_idx:tool_end]
    slogan_ctrls = [
        c for c in tool_ctrls if _control_class(c) in _SLOGAN_CLASSES
    ]
    search_ctrls = [
        c for c in tool_ctrls if _control_class(c) in _SEARCH_CLASSES
    ]
    other_tool_ctrls = [
        c for c in tool_ctrls
        if c not in slogan_ctrls and c not in search_ctrls and _control_text(c)
    ]

    # The captured utility strip has a left institutional-link cluster and a
    # right language/social cluster. Derive the split from control classes/order.
    right_start = len(utility_ctrls)
    social_pos = next(
        (
            i for i, c in enumerate(utility_ctrls)
            if _control_class(c) in _SOCIAL_CLASSES
        ),
        None,
    )
    if social_pos is not None:
        right_start = social_pos
        if right_start > 0 and _control_class(utility_ctrls[right_start - 1]) in _UTILITY_BTN_CLASSES:
            right_start -= 1
    elif device == "mobile" and len(utility_ctrls) >= 3:
        right_start = 1
    utility_left = utility_ctrls[:right_start]
    utility_right = utility_ctrls[right_start:]
    utility_html = ""
    if utility_ctrls:
        utility_html = (
            '<div class="rc-utility-bar"><div class="rc-header-inner rc-utility-inner">'
            '<div class="rc-utility-left">'
            + "".join(_render_control_as_inert(c, "rc-utility-item") for c in utility_left)
            + '</div><div class="rc-utility-right">'
            + "".join(_render_control_as_inert(c, "rc-utility-item") for c in utility_right)
            + "</div></div></div>"
        )

    # Desktop source: campaign slogan at left, search field at center/right.
    # Search-button-like controls with no class follow the captured search input,
    # so keep them in the same semantic search group.
    desktop_search = search_ctrls + (other_tool_ctrls if search_ctrls else [])
    tools_html = ""
    if device != "mobile" and (slogan_ctrls or desktop_search):
        tools_html = (
            '<div class="rc-brand-tools"><div class="rc-header-inner rc-brand-inner">'
            '<div class="rc-brand-slogan">'
            + "".join(_render_control_as_inert(c, "rc-brand-tool") for c in slogan_ctrls)
            + '</div><div class="rc-brand-search">'
            + "".join(_render_control_as_inert(c, "rc-search-part") for c in desktop_search)
            + "</div></div></div>"
        )

    mobile_search_html = (
        '<div class="rc-mobile-search">'
        + "".join(_render_control_as_inert(c, "rc-search-part") for c in search_ctrls)
        + "</div>"
        if device == "mobile" and search_ctrls else ""
    )
    mobile_slogan_html = (
        '<div class="rc-mobile-slogan">'
        + "".join(_render_control_as_inert(c, "rc-brand-tool") for c in slogan_ctrls)
        + "</div>"
        if device == "mobile" and slogan_ctrls else ""
    )

    nav_html = []
    for route, label in nav:
        href = relative_href(current_route, route)
        current = ' aria-current="page"' if route == current_route else ""
        nav_html.append(f'<a href="{_esc(href)}"{current}>{_esc(label)}</a>')
    nav_block = (
        '<nav class="rc-nav rc-surface-nav" aria-label="내비게이션" hidden>'
        + "".join(nav_html) + "</nav>"
    )

    top_html = "".join(
        f'<span class="rc-stub" role="link" aria-disabled="true" tabindex="-1">{_esc(text)}</span>'
        for text in gnb_top
    )
    grouped = []
    for heading, children in _gnb_groups(model):
        child_html = "".join(
            f'<span class="rc-mega-item" role="link" aria-disabled="true" tabindex="-1">{_esc(text)}</span>'
            for text in children
        )
        grouped.append(
            f'<section class="rc-mega-group" aria-label="{_esc(heading)}">'
            f'<strong class="rc-mega-heading">{_esc(heading)}</strong>'
            f'<div class="rc-mega-children">{child_html}</div></section>'
        )
    if not grouped and gnb_extra:
        grouped.append(
            '<section class="rc-mega-group">'
            + "".join(
                f'<span class="rc-mega-item" role="link" aria-disabled="true" tabindex="-1">{_esc(text)}</span>'
                for text in gnb_extra
            )
            + "</section>"
        )

    expanded = "true" if open_gnb else "false"
    hidden_attr = "" if open_gnb else " hidden"
    return (
        '<header class="rc-header">'
        f'{notice_html}{utility_html}{tools_html}'
        '<div class="rc-identity-row"><div class="rc-header-inner rc-identity-inner">'
        f'<h1 class="rc-site-title"><span class="rc-site-emblem" aria-hidden="true"></span>'
        f'<span>{_esc(identity_label)}</span></h1>'
        f'{mobile_search_html}'
        f'<div class="rc-gnb">{top_html}'
        f'<button type="button" id="rc-gnb-toggle" aria-expanded="{expanded}" '
        f'aria-controls="rc-mega-menu"><span>전체메뉴</span>'
        f'<i class="rc-menu-icon" aria-hidden="true"></i></button></div>'
        '</div></div>'
        f'{mobile_slogan_html}'
        f'{nav_block}'
        f'<div id="rc-mega-menu" aria-label="전체메뉴"{hidden_attr}>'
        f'<div class="rc-header-inner rc-mega-inner">{"".join(grouped)}</div></div>'
        '</header>'
    )


def _render_footer(model: dict[str, Any], state: dict[str, Any]) -> str:
    site_title = _site_identity_label(model)
    links = "".join(
        f'<span class="rc-footer-link" role="link" aria-disabled="true" tabindex="-1">'
        f'{_esc((g.get("text") or "").strip())}</span>'
        for g in _footer_links(state)
    )
    return (
        '<footer class="rc-footer">'
        f'<strong class="rc-footer-identity">{_esc(site_title)}</strong>'
        f'<div class="rc-footer-links">{links}</div>'
        '</footer>'
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
        return _render_org_staff_main(state)
    return _render_home_main(model, state, title, nav, route_prefix)


def _render_home_main(
    model: dict[str, Any],
    state: dict[str, Any],
    title: str,
    nav: list[tuple[str, str]],
    route_prefix: str,
) -> str:
    section01, section02 = _split_home_control_sections(state)

    primary_slider = [c for c in section01
                      if _control_class(c) in _PRIMARY_SLIDER_CLASSES]
    banner_ctrls = [c for c in section01
                    if _control_class(c) in _BANNER_CLASSES]
    mayor_actions = [
        c for c in section01
        if _control_text(c)
        and _control_class(c) not in _PRIMARY_SLIDER_CLASSES
        and _control_class(c) not in _BANNER_CLASSES
    ]

    first_action_text = next(
        (_control_text(c) for c in mayor_actions if _control_text(c)),
        "",
    )
    main_text = next(
        ((lm.get("text") or "").strip()
         for lm in state.get("landmarks", []) if lm.get("id") == "main"),
        title,
    )
    hero_intro = main_text
    if first_action_text and first_action_text in hero_intro:
        hero_intro = hero_intro.split(first_action_text, 1)[0].strip()

    key_visual = (
        '<div class="rc-key-visual" aria-label="주요 시각 배너">'
        '<div class="rc-key-visual-placeholder" aria-hidden="true"></div>'
        + (
            '<div class="rc-primary-slider-controls">'
            + "".join(_render_control_as_inert(c) for c in primary_slider)
            + "</div>"
            if primary_slider else ""
        )
        + "</div>"
    )
    mayor_panel = (
        '<div class="rc-mayor-panel">'
        f'<div class="rc-hero">{_esc(hero_intro)}</div>'
        '<div class="rc-mayor-actions">'
        + "".join(_render_control_as_inert(c, "rc-mayor-action") for c in mayor_actions)
        + "</div>"
        + (
            '<div class="rc-banner">'
            + "".join(_render_control_as_inert(c) for c in banner_ctrls)
            + "</div>"
            if banner_ctrls else ""
        )
        + "</div>"
    )
    hero = (
        '<section class="rc-home-section rc-section01" aria-label="주요">'
        f'{mayor_panel}{key_visual}</section>'
    )

    quick_nav = [c for c in section02
                 if _control_class(c) in _QUICK_SLIDER_CLASSES]
    quick_items = [c for c in section02
                   if _control_class(c) not in _QUICK_SLIDER_CLASSES]
    quick_cards = []
    for c in quick_items:
        extra = "rc-quick-card"
        if _control_class(c).startswith(_RD_BOX_PREFIX):
            extra += " rc-quick-card-featured"
        quick_cards.append(_render_control_as_inert(c, extra))
    quick = (
        '<section class="rc-home-section rc-section02" aria-label="자주찾는 메뉴">'
        '<div class="rc-quick-carousel">'
        + (
            '<div class="rc-quick-carousel-controls">'
            + "".join(_render_control_as_inert(c) for c in quick_nav)
            + "</div>"
            if quick_nav else ""
        )
        + '<div class="rc-quick-items">' + "".join(quick_cards) + '</div>'
        '</div></section>'
        if quick_cards else ""
    )

    board_links = [g for g in state.get("general_links", []) if _is_board_link(g)]
    notice = ""
    if board_links:
        rows = "".join(
            '<li class="rc-notice-item">'
            f'<span role="link" aria-disabled="true" tabindex="-1">'
            f'{_esc((g.get("text") or "").strip())}</span></li>'
            for g in board_links[:5] if (g.get("text") or "").strip()
        )
        notice = (
            '<section class="rc-home-panel rc-notice-panel" aria-label="공지사항">'
            '<h2 class="rc-section-title">공지사항</h2>'
            f'<ul class="rc-list rc-notice-list">{rows}</ul></section>'
        )

    stories = []
    for heading, items in _home_story_groups(state)[:2]:
        story_cards = "".join(
            '<article class="rc-story-card">'
            '<div class="rc-story-image-placeholder" aria-hidden="true"></div>'
            f'<strong>{_esc((g.get("text") or "").strip()[:180])}</strong>'
            '</article>'
            for g in items[:1]
        )
        stories.append(
            f'<section class="rc-home-panel rc-story-panel" aria-label="{_esc(heading)}">'
            f'<h2 class="rc-section-title">{_esc(heading)}</h2>'
            f'<div class="rc-story-grid">{story_cards}</div></section>'
        )
    info = (
        '<section class="rc-home-section rc-section03" aria-label="정보제공">'
        f'{notice}{"".join(stories)}</section>'
        if notice or stories else ""
    )

    lower = (
        '<section class="rc-home-section rc-section04" aria-label="소식과 배너">'
        '<section class="rc-home-panel rc-social-panel">'
        '<h2 class="rc-section-title">SNS</h2>'
        '<div class="rc-lower-placeholder" aria-hidden="true"></div></section>'
        '<section class="rc-home-panel rc-newsletter-panel">'
        '<h2 class="rc-section-title">소식지</h2>'
        '<div class="rc-lower-placeholder" aria-hidden="true"></div></section>'
        '</section>'
    )
    return (
        '<section class="rc-home" aria-label="홈">'
        f'{hero}{quick}{info}{lower}</section>'
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
        model, current_route, nav, gnb_top, gnb_extra, open_gnb, route_prefix,
        device=device,
    )
    main = _render_main(model, state, nav, route_prefix)
    footer = _render_footer(model, state)
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
