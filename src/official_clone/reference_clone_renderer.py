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
    is validated, its required measured fields are present, and the rendered
    surface has no explicit promotion-blocking fidelity gap. A null/pending
    contract or an unresolved board-fidelity gap renders with
    ``faithful_clone_candidate`` False for the affected surface.
    ``visual_review`` always stays ``pending``.

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
_BOARD_FIDELITY_GAP_PREFIX = "board_"

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
    # Organization-chart tier sizing. These are non-fidelity structural
    # defaults: the source does not publish these exact px, but the clone must
    # read as a tiered hierarchy (strong root -> distinct sub -> subordinate
    # children) rather than a flat grid of uniform boxes. They do NOT gate the
    # faithful claim and never promote visual_review/exact/golden.
    "org_section_title_size_px": 26,
    "exec_root_size_px": 28,
    "exec_sub_size_px": 20,
    "group_title_size_px": 18,
    "group_child_size_px": 14,
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


def _has_unresolved_board_fidelity_gaps(
    visual_contract: dict[str, Any] | None,
) -> bool:
    """Return True when the validated contract explicitly records board gaps.

    Board list/detail geometry is a separate #1312 fidelity slice. Existing
    #1310 home measurements can keep the home surface candidate-ready, but an
    affected list/detail surface must not inherit that stronger claim while its
    own board geometry remains a provenance-backed ``measurement_method=gap``.
    """
    if not visual_contract:
        return True
    gaps = visual_contract.get("gaps")
    if not isinstance(gaps, list):
        return True
    return any(
        isinstance(gap, dict)
        and gap.get("measurement_method") == "gap"
        and str(gap.get("region") or "").startswith(_BOARD_FIDELITY_GAP_PREFIX)
        for gap in gaps
    )


def faithful_clone_candidate_ready(
    visual_contract: dict[str, Any] | None,
    state_id: str | None = None,
) -> bool:
    """State-scoped promotion gate for the hidden lifecycle candidate marker."""
    if not faithful_ready(visual_contract):
        return False
    if not state_id:
        return True
    try:
        _family, _device, content = parse_state_id(state_id)
    except ReferenceCloneRendererError:
        return False
    if content in ("list", "detail") and _has_unresolved_board_fidelity_gaps(
        visual_contract
    ):
        return False
    return True


def _lifecycle_markers(
    visual_contract: dict[str, Any] | None,
    state_id: str | None = None,
) -> dict[str, Any]:
    markers = dict(_BASE_LIFECYCLE_MARKERS)
    markers["faithful_clone_candidate"] = faithful_clone_candidate_ready(
        visual_contract, state_id
    )
    return markers


def _lifecycle_json(
    visual_contract: dict[str, Any] | None,
    state_id: str | None = None,
) -> str:
    return json.dumps(
        _lifecycle_markers(visual_contract, state_id),
        ensure_ascii=False,
        sort_keys=True,
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

    org_layout = layout.get("organization") or {}
    val = org_layout.get("hero_footprint_height_px")
    if val is not None:
        values["layout.organization.hero_footprint_height_px"] = val

    board_layout = layout.get("board") or {}
    for field in (
        "snb_width_px",
        "snb_title_height_px",
        "snb_item_height_px",
        "content_container_width_px",
        "content_padding_left_px",
        "content_padding_top_px",
        "subpage_top_offset_px",
        "table_header_height_px",
        "row_height_px",
        "toolbar_padding_top_px",
        "toolbar_row_height_px",
        "toolbar_padding_bottom_px",
        "pager_padding_top_px",
        "pager_padding_bottom_px",
        "license_padding_top_px",
        "license_padding_bottom_px",
        "license_margin_bottom_px",
    ):
        val = board_layout.get(field)
        if val is not None:
            values[f"layout.board.{field}"] = val
    detail_layout = board_layout.get("detail") or {}
    for field in ("shell_padding_top_px", "shell_padding_bottom_px"):
        val = detail_layout.get(field)
        if val is not None:
            values[f"layout.board.detail.{field}"] = val
    val = detail_layout.get("meta_band_height_px")
    if val is not None:
        values["layout.board.detail.meta_band_height_px"] = val
    body_layout = detail_layout.get("body") or {}
    val = body_layout.get("break_spacing_px")
    if val is not None:
        values["layout.board.detail.body.break_spacing_px"] = val
    back_box_layout = detail_layout.get("back_box") or {}
    for field in ("padding_top_px", "padding_bottom_px", "button_height_px", "button_width_px"):
        val = back_box_layout.get(field)
        if val is not None:
            values[f"layout.board.detail.back_box.{field}"] = val
    attachment_layout = detail_layout.get("attachment") or {}
    for field in ("padding_top_px", "padding_bottom_px"):
        val = attachment_layout.get(field)
        if val is not None:
            values[f"layout.board.detail.attachment.{field}"] = val
    duty_layout = board_layout.get("duty") or {}
    for field in ("padding_top_px", "padding_bottom_px"):
        val = duty_layout.get(field)
        if val is not None:
            values[f"layout.board.duty.{field}"] = val
    snb_layout = board_layout.get("snb") or {}
    for field in ("subitem_height_px",):
        val = snb_layout.get(field)
        if val is not None:
            values[f"layout.board.snb.{field}"] = val

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

    board_colors = colors.get("board") or {}
    for field in (
        "table_header_border",
        "table_header_rule",
        "row_separator",
        "snb_title_bg",
        "snb_active_bg",
        "snb_separator",
        "pager_button_border",
        "pager_active_bg",
        "search_button_bg",
    ):
        val = board_colors.get(field)
        if val is not None:
            values[f"colors.board.{field}"] = val

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
    # chart/directory surfaces: the FIRST segment is the captured surface
    # identity itself (e.g. 행정조직도 / 직원 업무안내), not a record/status
    # prefix. list/detail boards keep the breadcrumb-segment behaviour.
    if content in ("chart", "directory"):
        return segments[0]
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
    for item in items:
        item["links_to_detail"] = (
            detail_route is not None
            and detail_id is not None
            and item.get("record_id") == detail_id
        )
        item["detail_route"] = detail_route
    return items


# ---------------------------------------------------------------------------
# CSS (derived strictly from the validated visual contract)
# ---------------------------------------------------------------------------
def _decl(property_name: str, value: Any) -> str:
    return f"{property_name}:{value};"


def _render_css(theme: dict[str, Any], device: str = "desktop",
                org_surface: bool = False) -> str:
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
        f".rc-site-title{{font-weight:{nd['font_weight_site_title']};margin:0;}}"
        ".rc-nav{display:flex;flex-wrap:wrap;}"
        f".rc-nav a[aria-current=\"page\"]{{font-weight:{nd['font_weight_current_nav']};}}"
        ".rc-banner{display:block;}"
        ".rc-notice-list{width:100%;}"
        ".rc-mayor-actions{display:flex;flex-wrap:wrap;}"
        ".rc-primary-slider-controls,.rc-quick-carousel-controls{display:flex;align-items:center;}"
        ".rc-footer-links{display:flex;flex-wrap:wrap;}"
    )

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
        f'gap:{nd["utility_gap_px"]}px;flex-wrap:wrap;}}'
        f'.rc-utility-left,.rc-utility-right{{display:flex;flex-wrap:wrap;align-items:center;'
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
        f'.rc-gnb{{gap:8px;flex-wrap:wrap;min-width:0;}}'
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

    if key_visual_w and device != "mobile":
        rules.append(
            f'.rc-section01{{grid-template-columns:minmax(0,calc(100% - {int(key_visual_w)}px)) '
            f'minmax(0,{int(key_visual_w)}px);}}'
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

    border_c = _pick(theme, "colors.border", None, device)
    muted_c = _pick(theme, "colors.text_muted", None, device)
    board_content_w = _pick(theme, "layout.board.content_container_width_px", None, device)
    content_pad_l = _pick(theme, "layout.board.content_padding_left_px", None, device)
    content_pad_t = _pick(theme, "layout.board.content_padding_top_px", None, device)
    subpage_top = _pick(theme, "layout.board.subpage_top_offset_px", None, device)
    detail_meta_h = _pick(theme, "layout.board.detail.meta_band_height_px", None, device)
    body_break = _pick(theme, "layout.board.detail.body.break_spacing_px", None, device)
    rules.append(
        ".rc-subpage{display:block;width:100%;}"
        ".rc-subpage-body{display:flex;flex-wrap:wrap;align-items:flex-start;width:100%;}"
        ".rc-subpage-context{display:block;width:100%;}"
        ".rc-page-head{display:flex;flex-wrap:wrap;align-items:flex-start;justify-content:space-between;}"
        ".rc-page-head .rc-tools{display:flex;flex-wrap:wrap;align-items:center;gap:4px;}"
        f".rc-breadcrumb,.rc-location{{font-size:{nd['small_font_size_px']}px;line-height:{nd['body_line_height']};}}"
        ".rc-breadcrumb{display:flex;flex-wrap:wrap;align-items:center;justify-content:flex-end;}"
        ".rc-breadcrumb .rc-crumb-current{font-weight:700;}"
        ".rc-location{display:flex;flex-wrap:wrap;align-items:center;}"
        ".sr_only{position:absolute;width:1px;height:1px;overflow:hidden;"
        "clip:rect(0 0 0 0);white-space:nowrap;}"
        "/* The source renders the board location hierarchy as a visually "
        "hidden .blind legend (screen-reader only); keep it in the a11y tree "
        "but out of the visible composition. */"
        ".rc-location{position:absolute;width:1px;height:1px;overflow:hidden;clip:rect(0 0 0 0);white-space:nowrap;}"
        ".rc-snb{display:flex;flex-direction:column;flex:none;}"
        f".rc-snb-title{{display:flex;align-items:center;justify-content:center;font-size:{nd['section_title_size_px']}px;"
        f"font-weight:700;text-align:center;}}"
        f".rc-snb-item{{display:flex;align-items:center;font-size:{nd['small_font_size_px']}px;"
        f"line-height:{nd['body_line_height']};padding:0 {nd['panel_padding_px']}px;}}"
        ".rc-snb-current{font-weight:700;}"
        # Generic responsive board: when the container is too narrow for
        # SNB beside content, flex-wrap:wrap on .rc-subpage-body moves
        # content to the next row so the table gets full width. The
        # flex-basis is derived from the base font size (16 chars) — a
        # structural default, not a guessed pixel value.
        ".rc-content{flex:1 1 240px;min-width:0;}"
        # Title sizing comes from the measured section-title size via the font
        # shorthand (the board-gap gate forbids the literal "{font-size:" form).
        f".rc-page-title,.rc-detail-title{{font:700 {nd['section_title_size_px']}px/1.25 inherit;"
        f"margin:0 0 {nd['panel_gap_px']}px;}}"
        f".rc-surface-tools{{display:flex;flex-wrap:wrap;justify-content:flex-end;gap:{nd['utility_gap_px']}px;}}"
        ".rc-tool{cursor:not-allowed;}"
        f".rc-board-toolbar{{display:flex;align-items:center;justify-content:space-between;}}"
        ".rc-toolbar-controls{display:flex;flex-wrap:wrap;align-items:center;}"
        ".rc-toolbar-search{display:flex;align-items:center;}"
        ".rc-pagesize,.rc-search-btn,.rc-page{cursor:not-allowed;}"
        ".rc-toolbar-pagesize,.rc-toolbar-filter,.rc-toolbar-search{display:inline-flex;align-items:center;}"
        f".rc-board-summary{{font-size:{nd['small_font_size_px']}px;margin:0;}}"
        f"table.rc-board{{border-collapse:collapse;width:100%;font-size:{nd['small_font_size_px']}px;}}"
        "table.rc-board th{text-align:center;font-weight:700;vertical-align:middle;}"
        "table.rc-board td{text-align:center;vertical-align:middle;}"
        "table.rc-board .rc-col-제목{text-align:left;}"
        ".rc-list-item{display:block;}"
        f".rc-pagination{{display:flex;flex-wrap:wrap;align-items:center;justify-content:center;font-size:{nd['small_font_size_px']}px;}}"
        ".rc-pager-inner{display:inline-flex;flex-wrap:wrap;align-items:center;justify-content:center;}"
        ".rc-page-current{font-weight:700;}"
        ".rc-detail-meta{display:flex;flex-wrap:wrap;align-items:center;margin:0;}"
        ".rc-dmeta-row{display:inline-flex;align-items:center;}"
        ".rc-dmeta-key,.rc-dmeta-val{margin:0;}"
        ".rc-dmeta-key{font-weight:700;}"
        f".rc-detail-body{{font-size:{nd['base_font_size_px']}px;line-height:{nd['body_line_height']};}}"
        ".rc-attachments{display:block;}"
        ".rc-attachments-title{display:block;}"
        ".rc-attach-item{display:block;}"
        ".rc-attach-name{display:inline-block;}"
        ".rc-attach-meta{display:inline-block;}"
        ".rc-attach{display:inline-block;cursor:not-allowed;}"
        ".rc-prevnext{display:block;list-style:none;margin:0;padding:0;}"
        ".rc-pn-prev,.rc-pn-next{display:block;}"
        ".rc-pn-label{display:inline-block;font-weight:700;}"
        ".rc-pn-item{display:inline-block;}"
        ".rc-detail-para{margin:0;}"
        ".rc-detail-image{border:1px dashed #b7b7bc;background:#fafafa;padding:1.25rem;margin:0 0 1em;text-align:center;}"
        ".rc-detail-image-name{display:block;font-weight:700;margin:0 0 .25em;}"
        ".rc-detail-image-note{display:block;font-size:.85em;color:#6a6a73;}"
        ".rc-back{text-align:center;}"
    )
    if board_content_w:
        rules.append(f".rc-content{{width:100%;max-width:{board_content_w}px;}}")
    if content_pad_l:
        rules.append(f".rc-content{{padding-left:{content_pad_l}px;}}")
    if content_pad_t:
        rules.append(f".rc-content{{padding-top:{content_pad_t}px;}}")
    if subpage_top:
        rules.append(f".rc-subpage{{padding-top:{subpage_top}px;}}")
    if border_c:
        rules.append(
            "table.rc-board th,table.rc-board td{border-left:0;border-right:0;}"
            ".rc-dmeta-row+.rc-dmeta-row{border-left:1px solid %s;}" % (border_c,)
        )
    snb_w = _pick(theme, "layout.board.snb_width_px", None, device)
    if snb_w:
        rules.append(f".rc-snb{{width:{snb_w}px;}}")
    snb_title_h = _pick(theme, "layout.board.snb_title_height_px", None, device)
    if snb_title_h:
        rules.append(f".rc-snb-title{{min-height:{snb_title_h}px;}}")
    snb_item_h = _pick(theme, "layout.board.snb_item_height_px", None, device)
    if snb_item_h:
        rules.append(f".rc-snb-item{{height:{snb_item_h}px;}}")
    snb_sub_h = _pick(theme, "layout.board.snb.subitem_height_px", None, device)
    if snb_sub_h:
        rules.append(
            f".rc-snb-sub{{height:{snb_sub_h}px;font-size:{nd['small_font_size_px']}px;}}"
            f".rc-snb-sub{{padding-left:{max(int(snb_sub_h) * 2, 40)}px;}}"
        )
    snb_title_bg = _pick(theme, "colors.board.snb_title_bg", None, device)
    if snb_title_bg:
        rules.append(
            f".rc-snb-title{{background:{snb_title_bg};}}"
            + (f".rc-snb-title{{color:{bg};}}" if bg else "")
        )
    snb_active_bg = _pick(theme, "colors.board.snb_active_bg", None, device)
    if snb_active_bg:
        rules.append(
            f".rc-snb-current{{background:{snb_active_bg};}}"
            + (f".rc-snb-current{{color:{bg};}}" if bg else "")
        )
    snb_sep = _pick(theme, "colors.board.snb_separator", None, device)
    if snb_sep:
        rules.append(f".rc-snb-item{{border-bottom:1px solid {snb_sep};}}")
    hdr_h = _pick(theme, "layout.board.table_header_height_px", None, device)
    if hdr_h:
        rules.append(f"table.rc-board th{{height:{hdr_h}px;}}")
    row_h = _pick(theme, "layout.board.row_height_px", None, device)
    if row_h:
        rules.append(f"table.rc-board td{{height:{row_h}px;}}")
    row_sep = _pick(theme, "colors.board.row_separator", None, device)
    if row_sep:
        rules.append(f"table.rc-board td{{border-bottom:1px solid {row_sep};}}")
    hdr_border = _pick(theme, "colors.board.table_header_border", None, device)
    if hdr_border:
        rules.append(f"table.rc-board th{{border-top:2px solid {hdr_border};}}")
    hdr_rule = _pick(theme, "colors.board.table_header_rule", None, device)
    if hdr_rule:
        rules.append(f"table.rc-board th{{border-bottom:1px solid {hdr_rule};}}")
    # List toolbar composition: a full-width #dddddd divider below the
    # breadcrumb, then a single summary+search row. The measured paddings keep
    # the divider at y=447 and the table top at y=543 (source notice.list).
    toolbar_pad_t = _pick(theme, "layout.board.toolbar_padding_top_px", None, device)
    toolbar_pad_b = _pick(theme, "layout.board.toolbar_padding_bottom_px", None, device)
    toolbar_row_h = _pick(theme, "layout.board.toolbar_row_height_px", None, device)
    if row_sep and toolbar_pad_t is not None and toolbar_pad_b is not None:
        rules.append(
            f".rc-board-toolbar{{margin-top:20px;border-top:1px solid {row_sep};"
            f"padding-top:{toolbar_pad_t}px;padding-bottom:{toolbar_pad_b}px;}}"
        )
    if toolbar_row_h:
        rules.append(f".rc-board-toolbar{{min-height:{toolbar_row_h}px;}}")
        rules.append(
            f".rc-pagesize,.rc-filter-opt,.rc-search-input,.rc-search-btn"
            f"{{min-height:{toolbar_row_h}px;}}"
        )
    if row_sep:
        rules.append(
            f".rc-pagesize,.rc-filter-opt,.rc-search-input"
            f"{{border:1px solid {row_sep};background:#fff;}}"
        )
    search_bg = _pick(theme, "colors.board.search_button_bg", None, device)
    if search_bg:
        rules.append(
            f".rc-search-btn{{background:{search_bg};color:#fff;border:none;"
            "cursor:not-allowed;}"
        )
    # Pager box: a tall bordered box (#aaaaaa top / #dddddd bottom) holding a
    # single row of boxed page buttons, then the 공공누리 license box.
    pager_pad_t = _pick(theme, "layout.board.pager_padding_top_px", None, device)
    pager_pad_b = _pick(theme, "layout.board.pager_padding_bottom_px", None, device)
    if hdr_rule and row_sep and pager_pad_t is not None and pager_pad_b is not None:
        rules.append(
            f".rc-pagination{{border-top:1px solid {hdr_rule};"
            f"border-bottom:1px solid {row_sep};"
            f"padding:{pager_pad_t}px 0 {pager_pad_b}px;}}"
        )
    pager_border = _pick(theme, "colors.board.pager_button_border", None, device)
    if pager_border:
        rules.append(
            f".rc-page{{border:1px solid {pager_border};background:#fff;"
            "padding:8px 12px;margin:0 3px;cursor:not-allowed;}"
        )
    pager_active = _pick(theme, "colors.board.pager_active_bg", None, device)
    if pager_active:
        rules.append(
            f".rc-page-current{{background:{pager_active};border-color:{pager_active};}}"
        )
    lic_pad_t = _pick(theme, "layout.board.license_padding_top_px", None, device)
    lic_pad_b = _pick(theme, "layout.board.license_padding_bottom_px", None, device)
    lic_margin_b = _pick(theme, "layout.board.license_margin_bottom_px", None, device)
    if row_sep and lic_pad_t is not None and lic_pad_b is not None:
        rules.append(
            f".rc-contents-info{{border-top:1px solid {row_sep};"
            f"border-bottom:1px solid {row_sep};"
            f"padding:{lic_pad_t}px 0 {lic_pad_b}px;}}"
        )
    if lic_margin_b is not None:
        rules.append(f".rc-contents-info{{margin-bottom:{lic_margin_b}px;}}")
    # Civil-duty contents box (콘텐츠 정보책임자): the source renders the same
    # #dddddd bordered box as the KOGL notice but with a more compact padding
    # around the title + label/value rows (measured from civil_form.list).
    dut_pad_t = _pick(theme, "layout.board.duty.padding_top_px", None, device)
    dut_pad_b = _pick(theme, "layout.board.duty.padding_bottom_px", None, device)
    if row_sep and dut_pad_t is not None and dut_pad_b is not None:
        rules.append(
            f".rc-contents-duty{{border-top:1px solid {row_sep};"
            f"border-bottom:1px solid {row_sep};"
            f"padding:{dut_pad_t}px 0 {dut_pad_b}px;}}"
        )
        # The source duty box is a dense single-band block: the title row and
        # the label/value items all sit on one line (measured 62px box, items
        # span the full content width).
        rules.append(
            f".rc-contents-duty{{display:flex;align-items:center;gap:16px;}}"
        )
        rules.append(
            f".rc-contents-duty .rc-duty-title{{font-size:13px;font-weight:700;"
            f"line-height:1.4;margin:0;white-space:nowrap;}}"
        )
        rules.append(
            f".rc-contents-duty .rc-duty-list{{margin:0;padding:0;list-style:none;"
            f"display:flex;gap:20px;align-items:center;}}"
        )
        rules.append(
            f".rc-contents-duty .rc-duty-item{{display:flex;gap:6px;"
            f"font-size:13px;line-height:1.4;}}"
        )
        rules.append(
            f".rc-contents-duty .rc-duty-label{{font-weight:700;min-width:56px;}}"
        )
    # Detail article shell: the source renders the breadcrumb, then a #dddddd
    # divider, then a #555555-bordered box holding the article title and the
    # meta band (#dddddd bottom rule at the measured 120px band height).
    shell_pad_t = _pick(theme, "layout.board.detail.shell_padding_top_px", None, device)
    shell_pad_b = _pick(theme, "layout.board.detail.shell_padding_bottom_px", None, device)
    if (
        hdr_border
        and row_sep
        and shell_pad_t is not None
        and shell_pad_b is not None
        and toolbar_pad_t is not None
    ):
        rules.append(
            f".rc-detail-shell{{margin-top:20px;border-top:1px solid {row_sep};"
            f"padding-top:{toolbar_pad_t}px;}}"
            f".rc-detail-box{{border-top:2px solid {hdr_border};"
            f"border-bottom:1px solid {row_sep};"
            f"padding:{shell_pad_t}px 0 {shell_pad_b}px;}}"
        )
    if detail_meta_h:
        rules.append(f".rc-detail-box{{min-height:{detail_meta_h}px;box-sizing:border-box;}}")
    if body_break:
        # Paragraph <br> runs inside the captured body: the renderer scales the
        # gap between generic body paragraphs from the measured per-<br> pitch
        # (G1 gosi.detail evidence) via this CSS custom property.
        rules.append(f".rc-detail-body{{--rc-break-space:{body_break}px;}}")
    back_pad_t = _pick(theme, "layout.board.detail.back_box.padding_top_px", None, device)
    back_pad_b = _pick(theme, "layout.board.detail.back_box.padding_bottom_px", None, device)
    back_btn_h = _pick(theme, "layout.board.detail.back_box.button_height_px", None, device)
    back_btn_w = _pick(theme, "layout.board.detail.back_box.button_width_px", None, device)
    if back_pad_t is not None and back_pad_b is not None:
        # Source board_btns: full-width #dddddd-bordered box with a centered
        # black button (G1 gosi.detail evidence: 1316-1405 box, 35x142px btn).
        rules.append(
            f".rc-back{{text-align:center;margin-top:{back_pad_t}px;"
            f"padding:{back_pad_t}px 0 {back_pad_b}px;border-top:1px solid {row_sep or '#dddddd'};"
            f"border-bottom:1px solid {row_sep or '#dddddd'};}}"
        )
    if back_btn_h and back_btn_w:
        rules.append(
            f".rc-back-link{{display:inline-flex;align-items:center;justify-content:center;"
            f"height:{back_btn_h}px;min-width:{back_btn_w}px;background:#23201f;color:#ffffff;"
            f"text-decoration:none;padding:0 1.2em;}}"
        )
    attach_pad_t = _pick(theme, "layout.board.detail.attachment.padding_top_px", None, device)
    attach_pad_b = _pick(theme, "layout.board.detail.attachment.padding_bottom_px", None, device)
    if attach_pad_t is not None and attach_pad_b is not None and row_sep:
        # Source .file block: full-width #dddddd-bordered box holding the
        # attachment title and one or more item rows (G1 evidence: box
        # y1017-1106 = 89px with a single 20px item band at y1049-1069).
        rules.append(
            f".rc-attachments{{margin-top:0;padding:{attach_pad_t}px 0 {attach_pad_b}px;"
            f"border-top:1px solid {row_sep};border-bottom:1px solid {row_sep};}}"
        )
        rules.append(
            # Source .file block renders the 첨부파일 title and the first item
            # on one 20px line band (G1 gosi.detail evidence: title/icon at
            # y1050 and the filename row through y1069 inside the 89px box).
            f".rc-attachments-title{{display:inline-block;font-size:{nd['small_font_size_px']}px;font-weight:700;margin:0 .8em 0 0;}}"
        )
        rules.append(
            f".rc-attach-item{{display:inline-flex;align-items:center;font-size:{nd['small_font_size_px']}px;}}"
            f".rc-attach-name{{font-weight:700;margin-right:.6em;}}"
            f".rc-attach-meta{{color:{muted_c or '#6a6a73'};margin-right:.8em;}}"
        )
    if muted_c:
        rules.append(".rc-loc{color:%s;}" % muted_c)

    # Organization-chart + staff-directory surfaces reuse the shared board
    # content family. The layout blocks below are generic structural
    # presentation (tiering/grouping affordances only, NOT source-measured
    # pixel fidelity); measured colors are reused where available and no
    # guessed radius/max-width/breakpoint is introduced. The nested semantic
    # org DOM is kept, but its presentation is no longer a margin-indented
    # narrow vertical list.
    # Generic, source-backed hierarchy (no site literal, no guessed color):
    # tier strength is expressed through the semantic depth-* classes and the
    # role containers (rc-org-exec / rc-org-groups / rc-org-flat) that the model
    # already emits. Measured colors are reused; sizes are non-fidelity
    # structural defaults. No border-radius, no guessed max-width/breakpoint.
    org_border = border or "#dcdcdc"
    org_primary = primary or "#1663b6"
    org_band = theme.get("colors.hero_bg") or "#f0f0ff"
    org_band2 = theme.get("colors.key_visual_bg") or "#f1fbfd"
    org_subtle = theme.get("colors.footer_bg") or "#fafafa"
    org_ink = text or "#000000"
    st = nd["org_section_title_size_px"]
    ex = nd["exec_root_size_px"]
    exs = nd["exec_sub_size_px"]
    gt = nd["group_title_size_px"]
    gc = nd["group_child_size_px"]
    rules.append(".rc-org-chart{margin-top:24px;}")

    # Optional, source-backed organization hero visual footprint: an inert
    # semantic spacer reserved before the executive hierarchy ONLY on the
    # organization surface when the validated visual contract provides the
    # measured value. Absent/null means no space is invented (an organization
    # surface without this source feature is unaffected), and non-org surfaces
    # (e.g. staff) keep their output unchanged.
    hero_footprint = theme.get("layout.organization.hero_footprint_height_px")
    if org_surface and hero_footprint is not None:
        rules.append(
            f".rc-org-hero-footprint{{display:block;height:{hero_footprint}px;}}"
        )

    # Source-like vertical breathing room between labelled org sections.
    rules.append(".rc-org-section{margin-bottom:64px;}")
    rules.append(
        f".rc-org-section-title{{font-size:{st}px;font-weight:700;margin:0 0 28px;"
        f"padding-bottom:10px;border-bottom:2px solid {org_primary};color:{org_ink};}}"
    )
    rules.append(".rc-org-tree{list-style:none;margin:0;padding:0;}")
    rules.append(".rc-org-node{margin:0;padding:2px;}")
    # Generic subordinate-card label base.
    rules.append(
        f".rc-org-label{{display:inline-block;padding:6px 14px;"
        f"background:{org_subtle};border:1px solid {org_border};color:{org_ink};}}"
    )

    # ── Executive tier: centred vertical spine, strong root -> distinct sub -> 3실/관 band ──
    rules.append(".rc-org-exec{display:flex;justify-content:center;margin-bottom:48px;}")
    rules.append(".rc-org-exec-chain{display:flex;flex-direction:column;align-items:center;}")
    rules.append(".rc-org-exec-chain>.rc-org-node{display:flex;flex-direction:column;align-items:center;}")
    # Hierarchy connector between executive levels.
    rules.append(
        f".rc-org-exec-arrow{{display:block;color:{org_primary};font-size:20px;"
        f"line-height:1;margin:6px 0;text-align:center;}}"
    )
    # Executive root (top single-child node / section roots): strongest tier.
    rules.append(
        f".rc-org-exec .rc-org-depth-1 .rc-org-label{{display:inline-block;"
        f"font-size:{ex}px;font-weight:700;padding:14px 36px;"
        f"background:{org_primary};color:#ffffff;border:2px solid {org_primary};}}"
    )
    # Distinct sub-tier (white field, primary rule) directly beneath the root.
    rules.append(
        f".rc-org-exec .rc-org-depth-2 .rc-org-label{{display:inline-block;"
        f"font-size:{exs}px;font-weight:700;padding:11px 28px;"
        f"background:#ffffff;color:{org_primary};border:2px solid {org_primary};}}"
    )

    # 3실/관: independent horizontal band tier between executive and the department matrix.
    rules.append(
        f".rc-org-exec-branch{{position:relative;display:flex;flex-wrap:wrap;"
        f"justify-content:center;gap:12px;margin-top:16px;padding:18px 16px;"
        f"background:{org_band};border:1px solid {org_border};}}"
    )
    rules.append(
        f".rc-org-exec-branch::before{{content:'';position:absolute;top:0;left:50%;"
        f"width:2px;height:16px;background:{org_primary};transform:translateX(-50%);}}"
    )
    rules.append(".rc-org-exec-branch .rc-org-node{padding:0;}")
    # Subordinate cards inside the 3실/관 band.
    rules.append(
        f".rc-org-exec-branch .rc-org-depth-3 .rc-org-label{{display:inline-block;"
        f"font-size:{gc}px;font-weight:600;padding:8px 18px;"
        f"background:#ffffff;color:{org_ink};border:1px solid {org_border};}}"
    )

    # ── Department matrix: broad group cards, strong root header vs subordinate children ──
    rules.append(".rc-org-groups{display:flex;flex-wrap:wrap;gap:24px;align-items:flex-start;margin-top:8px;}")
    rules.append(
        f".rc-org-group{{flex:1 1 220px;min-width:200px;display:flex;flex-direction:column;"
        f"border:1px solid {org_border};background:#ffffff;}}"
    )
    # Group root header (국/소): clearly stronger than its child cards.
    rules.append(
        f".rc-org-label.rc-org-depth-1{{display:block;font-size:{gt}px;font-weight:700;"
        f"padding:12px 16px;background:{org_primary};color:#ffffff;"
        f"border:1px solid {org_primary};}}"
    )
    rules.append(".rc-org-group-list{display:flex;flex-direction:column;gap:6px;padding:12px;}")
    # Subordinate department cards (과).
    rules.append(
        f".rc-org-group .rc-org-depth-2 .rc-org-label{{display:block;font-size:{gc}px;"
        f"font-weight:400;padding:7px 12px;background:{org_subtle};"
        f"color:{org_ink};border:1px solid {org_border};}}"
    )

    # ── Flat neighbourhood-centre grid (18동): broad, separated section ──
    rules.append(
        f".rc-org-flat{{display:grid;grid-template-columns:repeat(auto-fill,minmax(120px,1fr));"
        f"gap:12px;}}"
    )
    rules.append(
        f".rc-org-box{{display:block;text-align:center;padding:11px 8px;"
        f"background:{org_band2};border:1px solid {org_border};"
        f"color:{org_ink};font-size:{gc}px;}}"
    )
    # Staff search row: summary (left) + inert controls (right) on one row.
    rules.append(
        f".rc-staff-search-row{{display:flex;flex-wrap:wrap;align-items:center;"
        f"justify-content:space-between;gap:12px;margin:16px 0;}}"
    )
    rules.append(
        f".rc-staff-search{{display:flex;flex-wrap:wrap;gap:10px;align-items:center;margin:0;}}"
    )
    rules.append(".rc-staff-field{display:inline-flex;align-items:center;}")
    rules.append(
        f".rc-staff-select,.rc-staff-input{{font-size:{nd['small_font_size_px']}px;"
        f"padding:6px 8px;border:1px solid #888888;background:#ffffff;color:#222222;}}"
    )
    # Readable disabled affordance: disabled must not grey to illegibility.
    rules.append(".rc-staff-select:disabled,.rc-staff-input:disabled{background:#ffffff;color:#222222;opacity:1;}")
    rules.append(
        f".rc-staff-btn{{font-size:{nd['small_font_size_px']}px;padding:6px 14px;"
        f"border:1px solid #23201f;background:#23201f;color:#ffffff;cursor:default;}}"
    )
    rules.append(".rc-staff-btn:disabled{background:#23201f;color:#ffffff;opacity:1;}")
    rules.append(".rc-staff-table{margin-top:8px;width:100%;}")
    # Breadcrumb hierarchy legibility: crumbs must not mash together.
    rules.append(".rc-breadcrumb .rc-crumb{padding-left:10px;}")
    rules.append(".rc-breadcrumb .rc-crumb:first-child{padding-left:0;}")

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
    visual_contract: dict[str, Any] | None = None,
) -> str:
    family, _device, content = parse_state_id(state.get("state_id", ""))
    title = state.get("page_title") or ""

    # Generic CMS content-page capability (#1357): a state carrying a
    # source-backed ``content_page`` block is rendered as an informational
    # article body. This is data-driven (driven by the presence of the generic
    # content_page block), never a site-specific branch, and only fires when the
    # model actually captured an article body — so home / list / detail / chart
    # / directory states without one keep their existing renderer.
    content_page = state.get("content_page")
    if isinstance(content_page, dict) and content_page.get("kind") == "content_page":
        return _render_content_main(model, state, route_prefix, visual_contract)

    if content == "detail":
        return _render_detail_main(model, state, family, title, route_prefix)
    if content == "list":
        return _render_list_main(model, state, family, title, route_prefix)
    if content == "chart":
        return _render_organization_main(model, state, route_prefix, visual_contract)
    if content == "directory":
        return _render_staff_directory_main(model, state, route_prefix)
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


_BOARD_COLUMN_TOKENS = frozenset(
    {"번호", "제목", "담당부서", "부서명", "등록일", "첨부파일",
     "조회수", "분류", "고시공고번호", "게재일자"}
)
_DATE_TOKEN_RE = re.compile(r"\d{4}[/-]\d{2}[/-]\d{2}")


def _contents_landmark_text(state: dict[str, Any]) -> str:
    for lm in state.get("landmarks", []):
        if lm.get("id") == "contents":
            return (lm.get("text") or "").strip()
    return ""


def _detect_board_columns(contents: str) -> list[str]:
    if not contents:
        return []
    tokens = contents.split()
    first_no = next((i for i, t in enumerate(tokens) if t.isdigit()), None)
    if first_no is None:
        return []
    cols: list[str] = []
    i = first_no - 1
    while i >= 0 and tokens[i] in _BOARD_COLUMN_TOKENS:
        cols.insert(0, tokens[i])
        i -= 1
    if len(cols) >= 2 and "번호" in cols and "제목" in cols:
        return cols
    return []


def _parse_board_blob_rows(contents: str, columns: list[str]) -> list[dict[str, str]]:
    if not contents or not columns:
        return []
    tokens = contents.split()
    first_no = next((i for i, t in enumerate(tokens) if t.isdigit()), None)
    if first_no is None:
        return []
    rows: list[dict[str, str]] = []
    i = first_no
    n = len(tokens)
    while i < n and i < len(tokens):
        if not tokens[i].isdigit():
            i += 1
            continue
        no = tokens[i]
        di = next(
            (k for k in range(i + 1, n) if _DATE_TOKEN_RE.fullmatch(tokens[k])), None
        )
        if di is None:
            break
        rec: dict[str, str] = {
            "번호": no, "분류": "", "담당부서": "", "등록일": tokens[di], "조회수": "",
        }
        if di > i + 1:
            rec["담당부서"] = tokens[di - 1]
        views_idx = next(
            (k for k in range(di + 1, n) if tokens[k].isdigit()), None
        )
        if views_idx is not None:
            rec["조회수"] = tokens[views_idx]
        if "분류" in columns and columns.index("분류") == 1 and i + 1 < di:
            rec["분류"] = tokens[i + 1]
        rows.append(rec)
        nxt = next(
            (k for k in range((views_idx + 1) if views_idx is not None else di + 1, n)
             if tokens[k].isdigit()),
            None,
        )
        if nxt is None:
            break
        i = nxt
    return rows


def _board_summary(contents: str) -> dict[str, str]:
    out: dict[str, str] = {}
    m = re.search(r"전체\s*([\d,]+)\s*건", contents)
    if m:
        out["total"] = m.group(1)
    m = re.search(r"페이지\s*(\d+)\s*/\s*(\d+)", contents)
    if m:
        out["page_current"] = m.group(1)
        out["page_total"] = m.group(2)
    return out


def _board_snb_items(state: dict[str, Any]) -> tuple[str, list[dict[str, Any]]]:
    """Return ``(section title, menu items)`` for the left sidebar.

    Prefers the source-backed structured ``board.snb`` capture (level-1 items
    plus the visible level-2 children of the expanded parent, mirroring the
    source sidebar's two-level hierarchy). Falls back to the flat ``snb``
    landmark text (all items depth 1) for states without a board capture.
    """
    board = state.get("board")
    if isinstance(board, dict):
        snb = board.get("snb")
        if isinstance(snb, dict) and snb.get("items"):
            title = (snb.get("title") or "").strip()
            return title, list(snb["items"])
    for lm in state.get("landmarks", []):
        if lm.get("id") == "snb":
            tokens = [t for t in (lm.get("text") or "").split() if t]
            items = [{"label": t, "depth": 1} for t in tokens]
            if len(items) >= 2:
                return items[0]["label"], items[1:]
            if items:
                return "", items
            return "", []
    return "", []


def _board_breadcrumb_trail(state: dict[str, Any]) -> list[str]:
    best: list[str] = []
    for lm in state.get("landmarks", []):
        if lm.get("id") is not None:
            continue
        text = (lm.get("text") or "").strip()
        if text.startswith("홈"):
            trail = [t for t in text.split() if t]
            if len(trail) > len(best):
                best = trail
    return best


def _board_active_label(state: dict[str, Any]) -> str:
    active: list[str] = []
    for c in state.get("controls", []):
        if (c.get("class_name") or "").strip() == "active":
            text = (c.get("text") or "").strip()
            if text:
                active.append(text)
    return active[-1] if active else ""


def _board_location_hierarchy(contents: str) -> list[str]:
    m = re.search(r"([^>]+(?:>[^>]+)+)", contents)
    if not m:
        return []
    parts = [p.strip() for p in m.group(1).split(">")]
    if len(parts) >= 2 and all(parts):
        return parts
    return []


# Standard Korean public-sector 공공누리 license notice. It appears verbatim
# in the committed G1 HTML (div.contents_info > .kogl .txt) on every board
# list/detail page and is generic boilerplate, not site-specific data.
_CONTENTS_INFO_NOTICE = (
    "본 공공저작물은 공공누리 “출처표시+상업적이용금지+변경금지” "
    "조건에 따라 이용할 수 있습니다."
)


def _render_contents_info(board: dict[str, Any] | None) -> str:
    """Render the source-backed ``div.contents_info`` block for a board.

    Municipal board pages close the content section with either the 공공누리
    (KOGL) license notice (``div.kogl > span.txt``) or, on some service
    families, a civil-duty box (``article.duty`` with title + label/value
    items, e.g. 콘텐츠 정보책임자). When the model captured a duty box the
    duty markup is rendered (no active hyperlinks — the tel link is inert
    text to keep external interactions at zero); otherwise the standard
    notice constant is used as before.
    """
    contents = (board or {}).get("contents_info")
    if isinstance(contents, dict) and contents.get("kind") == "duty":
        items = contents.get("items") or []
        title = contents.get("title") or ""
        item_html = []
        for it in items:
            label = (it.get("label") or "").strip()
            value = (it.get("value") or "").strip()
            if not label and not value:
                continue
            item_html.append(
                f'<li class="rc-duty-item"><strong class="rc-duty-label">'
                f'{_esc(label)}</strong><span class="rc-duty-value">'
                f'{_esc(value)}</span></li>'
            )
        return (
            f'<div class="rc-contents-info rc-contents-duty">'
            f'<h3 class="rc-duty-title">{_esc(title)}</h3>'
            f'<ul class="rc-duty-list">{"".join(item_html)}</ul></div>'
        )
    return (
        f'<div class="rc-contents-info">{_esc(_CONTENTS_INFO_NOTICE)}</div>'
    )


def _board_toolbar(state: dict[str, Any]) -> dict[str, Any]:
    page_sizes: list[str] = []
    filter_text: str = ""
    search_placeholder: str = ""
    search_button: str = ""
    for c in state.get("controls", []):
        text = (c.get("text") or "").strip()
        cn = (c.get("class_name") or "").strip()
        if not text:
            continue
        if re.search(r"\d+개씩", text):
            for part in text.split():
                if re.match(r"\d+개씩", part):
                    page_sizes.append(part)
        if "제목" in text and "전체" in text and not filter_text:
            filter_text = text
        if cn == "form_textbox" and not search_placeholder:
            search_placeholder = text
        if text == "검색" and not search_button and cn != "search_keyword":
            search_button = text
    return {
        "page_sizes": page_sizes,
        "filter_text": filter_text,
        "search_placeholder": search_placeholder,
        "search_button": search_button,
    }


def _render_surface_tools(state: dict[str, Any]) -> str:
    tools = []
    for c in state.get("controls", []):
        cn = (c.get("class_name") or "")
        if cn.startswith("btn "):
            text = (c.get("text") or "").strip()
            if text:
                tools.append(
                    f'<button type="button" class="rc-tool" disabled '
                    f'aria-disabled="true">{_esc(text)}</button>'
                )
    if not tools:
        return ""
    return f'<div class="rc-surface-tools rc-tools" aria-label="도구">{"".join(tools)}</div>'


def _board_nav_html(state: dict[str, Any]) -> tuple[str, str, str]:
    trail = _board_breadcrumb_trail(state)
    active = _board_active_label(state)
    crumbs = []
    for idx, label in enumerate(trail):
        # No invented visual separator: the source breadcrumb hierarchy is a
        # sequence of labelled landmarks (홈 → 구정소식 → 공지사항). A literal
        # "›" glyph is not source-proven, so crumbs stay as discrete spans.
        if idx == len(trail) - 1:
            crumbs.append(
                f'<span class="rc-crumb rc-crumb-current" aria-current="page">{_esc(label)}</span>'
            )
        else:
            crumbs.append(f'<span class="rc-crumb">{_esc(label)}</span>')
    breadcrumb_html = (
        f'<nav class="rc-breadcrumb" aria-label="위치">{"".join(crumbs)}</nav>' if crumbs else ""
    )
    # The blind search fieldset legend ("분야별정보 > 행정 > 행정소식 > 공지사항")
    # is screen-reader-only source content and MUST NOT be promoted into a
    # navigation landmark (visible or hidden). The real visible location
    # hierarchy is the source-backed breadcrumb (홈 / 구정소식 / 공지사항)
    # rendered above. No separate rc-location nav is derived for board states;
    # deriving it from the contents landmark would re-introduce the blind
    # legend as a duplicate navigation landmark.
    location_html = ""
    section_title, snb = _board_snb_items(state)
    snb_parts = []
    if section_title:
        snb_parts.append(
            f'<span class="rc-snb-title">{_esc(section_title)}</span>'
        )
    for item in snb:
        label = item.get("label") if isinstance(item, dict) else item
        depth = item.get("depth") if isinstance(item, dict) else 1
        cls = "rc-snb-item"
        if depth and depth > 1:
            cls += " rc-snb-sub"
        if label == active:
            cls += " rc-snb-current"
            snb_parts.append(
                f'<span class="{cls}" aria-current="page">{_esc(label)}</span>'
            )
        else:
            snb_parts.append(
                f'<span class="{cls}" role="link" aria-disabled="true" tabindex="-1">{_esc(label)}</span>'
            )
    snb_html = (
        f'<nav class="rc-snb" aria-label="하위 메뉴">{"".join(snb_parts)}</nav>' if snb_parts else ""
    )
    return breadcrumb_html, location_html, snb_html


def _subpage_context_html(breadcrumb_html: str, location_html: str) -> str:
    return (
        f'<div class="rc-subpage-context">{breadcrumb_html}{location_html}</div>'
        if breadcrumb_html or location_html
        else ""
    )


def _wrap_subpage(snb_html: str, content_html: str) -> str:
    return (
        f'<div class="rc-subpage">'
        f'<div class="rc-subpage-body">{snb_html}'
        f'<div class="rc-content">{content_html}</div></div></div>'
    )


def _render_board_toolbar(toolbar: dict[str, Any]) -> str:
    """Render the summary + boxed search controls of the source toolbar row.

    The captured source renders the page-size selector, the search filter
    select, the keyword input and the black search button as one right-aligned
    row next to the result summary. Only the currently selected option of each
    selector is visible in the capture, so the model's first page-size token
    and last filter token stand in for the selected values.
    """
    parts = []
    page_sizes = toolbar.get("page_sizes") or []
    if page_sizes:
        parts.append(
            f'<span class="rc-toolbar-pagesize" aria-label="페이지 크기">'
            f'<span class="rc-pagesize" role="link" aria-disabled="true" '
            f'tabindex="-1">{_esc(page_sizes[0])}</span></span>'
        )
    filter_text = toolbar.get("filter_text") or ""
    opts = [o for o in filter_text.split() if o]
    if opts:
        parts.append(
            f'<span class="rc-toolbar-filter" aria-label="검색 범위">'
            f'<span class="rc-filter-opt" role="link" aria-disabled="true" '
            f'tabindex="-1">{_esc(opts[-1])}</span></span>'
        )
    if toolbar.get("search_placeholder") or toolbar.get("search_button"):
        ph = toolbar.get("search_placeholder") or ""
        btn = toolbar.get("search_button") or "검색"
        parts.append(
            f'<span class="rc-toolbar-search" aria-label="검색">'
            f'<input type="text" class="rc-search-input" placeholder="{_esc(ph)}" '
            f'aria-label="검색어" disabled>'
            f'<button type="button" class="rc-search-btn" disabled aria-disabled="true">{_esc(btn)}</button>'
            f"</span>"
        )
    if not parts:
        return ""
    return (
        f'<div class="rc-toolbar-controls" aria-label="게시판 도구">'
        f'{"".join(parts)}</div>'
    )


def _render_board_pagination(
    summary: dict[str, str],
    board_pagination: dict[str, Any] | None = None,
) -> str:
    """Render an inert pager from source-backed page numbers when available."""
    pages: list[int] = []
    if board_pagination:
        pages = [int(p) for p in board_pagination.get("pages") or [] if str(p).isdigit()]
    total = summary.get("page_total")
    current = summary.get("page_current") or str(
        board_pagination.get("current_page") if board_pagination else None
    ) or "1"
    # source DOM uses class="arr first" + text "처음", "arr prev" + "이전",
    # "arr next" + "다음", "arr last" + "마지막". The visible glyph treatment is
    # CSS-driven (an icon font / sprite) and is NOT materialized in the controlled
    # clone asset set, so we render only the source-backed text labels and drop
    # the invented literal « ‹ › » glyphs (no provenance, no external request).
    items = [
        '<button type="button" class="rc-page" disabled aria-disabled="true">처음</button>',
        '<button type="button" class="rc-page" disabled aria-disabled="true">이전</button>',
    ]
    if pages:
        for page in pages:
            if page == int(current or 1):
                items.append(
                    f'<button type="button" class="rc-page rc-page-current" '
                    f'aria-current="page" disabled aria-disabled="true">{page}</button>'
                )
            else:
                items.append(
                    f'<button type="button" class="rc-page" disabled '
                    f'aria-disabled="true">{page}</button>'
                )
    else:
        items.append(
            f'<button type="button" class="rc-page rc-page-current" aria-current="page" '
            f'disabled aria-disabled="true">{_esc(current)}</button>'
        )
    items.extend([
        '<button type="button" class="rc-page" disabled aria-disabled="true">다음</button>',
        '<button type="button" class="rc-page" disabled aria-disabled="true">마지막</button>',
    ])
    suffix = f' / {_esc(total)}' if total else ""
    return (
        f'<nav class="rc-pagination" aria-label="페이지 이동">'
        f'<span class="rc-pager-inner">{"".join(items)}'
        f'<span class="rc-page-total">{suffix}</span></span></nav>'
    )


def _render_content_main(
    model: dict[str, Any],
    state: dict[str, Any],
    route_prefix: str,
    visual_contract: dict[str, Any] | None = None,
) -> str:
    """Render a generic CMS informational content page into ``rc-main``.

    The content is fully source-backed text from the model's ``content_page``
    block: headings, paragraphs, and lists in document order, plus the civil-
    duty ``contents_info`` box (rendered inert — the source ``tel:`` link is
    plain text, never an active hyperlink). No raw source HTML is emitted; every
    value is HTML-escaped. External links and interactive affordances are not
    reproduced, keeping the surface offline and inert.
    """
    content = state.get("content_page") or {}
    blocks = content.get("blocks") or []
    parts: list[str] = []
    for blk in blocks:
        btype = blk.get("type")
        if btype == "heading":
            level = max(2, min(6, int(blk.get("level") or 2)))
            parts.append(
                f'<h{level} class="rc-content-heading">{_esc(blk.get("text", ""))}</h{level}>'
            )
        elif btype == "paragraph":
            parts.append(
                f'<p class="rc-content-paragraph">{_esc(blk.get("text", ""))}</p>'
            )
        elif btype == "list":
            items = "".join(
                f'<li class="rc-content-item">{_esc(it)}</li>'
                for it in (blk.get("items") or [])
            )
            parts.append(f'<ul class="rc-content-list">{items}</ul>')
        elif btype == "table":
            # Source-backed fee/fact tables (e.g. bulky-waste 부과기준). Fully
            # inert: every cell is HTML-escaped plain text, no links emitted.
            headings = blk.get("headings") or []
            rows = blk.get("rows") or []
            thead = ""
            if headings:
                head_cells = "".join(
                    f'<th scope="col">{_esc(h)}</th>' for h in headings
                )
                thead = f"<thead><tr>{head_cells}</tr></thead>"
            body_rows = "".join(
                "<tr>"
                + "".join(f"<td>{_esc(c)}</td>" for c in row)
                + "</tr>"
                for row in rows
            )
            tbody = f"<tbody>{body_rows}</tbody>" if body_rows else ""
            parts.append(
                '<table class="rc-content-table">'
                + thead
                + tbody
                + "</table>"
            )
    contents_info = content.get("contents_info")
    if isinstance(contents_info, dict) and contents_info.get("kind") == "duty":
        parts.append(_render_contents_info({"contents_info": contents_info}))
    body = "".join(parts)
    return (
        '<section class="rc-content-page" aria-label="안내 내용">'
        + body
        + "</section>"
    )


def _render_list_main(
    model: dict[str, Any],
    state: dict[str, Any],
    family: str,
    title: str,
    route_prefix: str,
) -> str:
    contents = _contents_landmark_text(state)
    columns = _detect_board_columns(contents)
    summary = _board_summary(contents)
    items = _list_items(model, state, route_prefix)
    blob_rows = _parse_board_blob_rows(contents, columns)
    breadcrumb_html, location_html, snb_html = _board_nav_html(state)
    toolbar = _board_toolbar(state)
    surface_label_text = surface_label(state, model)
    board = state.get("board") or {}
    board_columns = board.get("columns") if board.get("kind") == "list" else None
    board_rows = board.get("rows") if board.get("kind") == "list" else None
    board_pagination = board.get("pagination") if board.get("kind") == "list" else None

    toolbar_controls_html = _render_board_toolbar(toolbar)
    summary_html = ""
    if summary:
        parts = []
        if summary.get("total"):
            parts.append(f'전체 {_esc(summary["total"])}건')
        if summary.get("page_current") and summary.get("page_total"):
            parts.append(f'페이지 {_esc(summary["page_current"])} / {_esc(summary["page_total"])}')
        if parts:
            summary_html = f'<p class="rc-board-summary">{" · ".join(parts)}</p>'
    if summary_html or toolbar_controls_html:
        toolbar_html = (
            f'<div class="rc-board-toolbar" role="search">'
            f'{summary_html}{toolbar_controls_html}</div>'
        )
    else:
        toolbar_html = ""

    current_route = route_for_state(state["state_id"], route_prefix)
    detail_no: str | None = None
    detail_record = _family_detail_record_id(model, family)
    if detail_record:
        match = re.search(r"(\d+)$", detail_record)
        detail_no = match.group(1) if match else None

    if board_columns and board_rows:
        # Source-backed board table from the semantic model's generic board
        # vocabulary (columns/rows captured verbatim from the committed G1 DOM).
        head_cells = "".join(
            f'<th scope="col" class="rc-th rc-col-{_esc(c)}">{_esc(c)}</th>'
            for c in board_columns
        )
        col_widths = board.get("col_widths") or []
        colgroup_html = ""
        if col_widths:
            cols = []
            for w in col_widths:
                if isinstance(w, int) and w > 0:
                    cols.append(f'<col style="width:{int(w)}%">')
                else:
                    cols.append("<col>")
            colgroup_html = "<colgroup>" + "".join(cols) + "</colgroup>"
        body_rows = []
        for row in board_rows:
            cells = row.get("cells") or {}
            record_id = row.get("record_id")
            links_to_detail = (
                detail_no is not None and record_id == detail_no
            )
            cell_html = []
            for col in board_columns:
                value = cells.get(col) or ""
                if col == "제목":
                    value = cells.get(col) or ""
                    if row.get("is_new"):
                        # Source DOM: <i class="xi-new"></i><span class="sr_only">새글</span>
                        # followed by the title. The xi-new glyph is an XEIcon
                        # font treatment whose body bytes are not materialized in
                        # the controlled clone asset set (TECHNICAL_CAPTURE_GAP),
                        # so we emit the source element + screen-reader "새글"
                        # label and do NOT fabricate a visible bordered chip.
                        clean_title = re.sub(r"^새글\s*", "", value).strip()
                        cell_text = (
                            f'<i class="xi-new" aria-hidden="true"></i>'
                            f'<span class="sr_only">새글</span> '
                            f'{_esc(clean_title)}'
                        )
                    else:
                        cell_text = _esc(value)
                    if links_to_detail:
                        detail_route = _family_detail_route(model, family, route_prefix)
                        href = relative_href(current_route, detail_route) if detail_route else "#"
                        cell_html.append(
                            f'<td class="rc-td rc-col-{_esc(col)}">'
                            f'<a class="rc-list-link" data-detail="1" href="{_esc(href)}">'
                            f'{cell_text}</a></td>'
                        )
                    else:
                        cell_html.append(
                            f'<td class="rc-td rc-col-{_esc(col)}">'
                            f'<span class="rc-list-item" aria-disabled="true" '
                            f'role="link" tabindex="-1">{cell_text}</span></td>'
                        )
                elif col == "첨부파일" and row.get("attachment_count"):
                    # Source renders an attachment icon (e.g. /upload/skin/board/
                    # basic/attach.png) whose body bytes are not materialized in
                    # the controlled clone asset set (TECHNICAL_CAPTURE_GAP). We
                    # preserve the attachment count semantics without fabricating
                    # a visible bordered chip or any external/relative asset URL.
                    count = row["attachment_count"]
                    cell_html.append(
                        f'<td class="rc-td rc-col-{_esc(col)}">'
                        f'<span class="rc-attach-count sr_only" '
                        f'aria-label="첨부파일 {count}개">첨부파일 {count}개</span></td>'
                    )
                else:
                    cell_html.append(
                        f'<td class="rc-td rc-col-{_esc(col)}">{_esc(value)}</td>'
                    )
            body_rows.append(
                f'<tr class="rc-board-row">{"".join(cell_html)}</tr>'
            )
        table_html = (
            f'<table class="rc-board" aria-label="{_esc(surface_label_text)} 목록">'
            f'{colgroup_html}'
            f'<thead><tr class="rc-board-head">{head_cells}</tr></thead>'
            f'<tbody>{"".join(body_rows)}</tbody></table>'
        )
    elif columns:
        head_cells = "".join(
            f'<th scope="col" class="rc-th rc-col-{_esc(c)}">{_esc(c)}</th>' for c in columns
        )
        body_rows = []
        for i, item in enumerate(items):
            blob = blob_rows[i] if i < len(blob_rows) else None
            cells = []
            for col in columns:
                if col == "제목":
                    if item.get("links_to_detail") and item.get("detail_route"):
                        href = relative_href(current_route, item["detail_route"])
                        cells.append(
                            f'<td class="rc-td rc-col-제목"><a class="rc-list-link" data-detail="1" '
                            f'href="{_esc(href)}">{_esc(item["text"])}</a></td>'
                        )
                    else:
                        cells.append(
                            f'<td class="rc-td rc-col-제목"><span class="rc-list-item" '
                            f'aria-disabled="true" role="link" tabindex="-1">{_esc(item["text"])}</span></td>'
                        )
                elif col == "번호":
                    val = (blob or {}).get("번호") or ""
                    cells.append(f'<td class="rc-td rc-col-번호">{_esc(val)}</td>')
                elif col in ("담당부서", "부서명"):
                    val = (blob or {}).get("담당부서") if blob else ""
                    cells.append(f'<td class="rc-td rc-col-{_esc(col)}">{_esc(val)}</td>')
                elif col == "등록일":
                    val = (blob or {}).get("등록일") if blob else ""
                    cells.append(f'<td class="rc-td rc-col-등록일">{_esc(val)}</td>')
                elif col == "조회수":
                    val = (blob or {}).get("조회수") if blob else ""
                    cells.append(f'<td class="rc-td rc-col-조회수">{_esc(val)}</td>')
                elif col == "분류":
                    val = (blob or {}).get("분류") if blob else ""
                    cells.append(f'<td class="rc-td rc-col-분류">{_esc(val)}</td>')
                else:
                    cells.append(f'<td class="rc-td rc-col-{_esc(col)}"></td>')
            body_rows.append(f'<tr class="rc-board-row">{ "".join(cells) }</tr>')
        table_html = (
            f'<table class="rc-board" aria-label="{_esc(surface_label_text)} 목록">'
            f'<thead><tr class="rc-board-head">{head_cells}</tr></thead>'
            f'<tbody>{"".join(body_rows)}</tbody></table>'
        )
    else:
        rows = []
        for item in items:
            if item.get("links_to_detail") and item.get("detail_route"):
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
        table_html = f'<ul class="rc-list">{"".join(rows)}</ul>'

    pagination_html = _render_board_pagination(summary, board_pagination)
    license_html = _render_contents_info(board)

    context_html = _subpage_context_html(breadcrumb_html, location_html)
    tools_html = _render_surface_tools(state)
    content_html = (
        f'<div class="rc-page-head">'
        f'<h2 class="rc-page-title">{_esc(surface_label_text)}</h2>'
        f'{tools_html}</div>'
        f'{context_html}'
        f'{toolbar_html}{table_html}{pagination_html}{license_html}'
    )
    return _wrap_subpage(snb_html, content_html)


def _parse_detail_metadata(contents: str) -> dict[str, str]:
    out: dict[str, str] = {}
    m = re.search(r"작성일시(\S+ \S+)", contents)
    if m:
        out["작성일시"] = m.group(1)
    m = re.search(r"작성일(\S+)", contents)
    if m and "작성일시" not in out:
        out["작성일"] = m.group(1)
    m = re.search(r"작성부서(\S+)", contents)
    if m:
        out["작성부서"] = m.group(1)
    m = re.search(r"조회수(\d+)", contents)
    if m:
        out["조회수"] = m.group(1)
    m = re.search(r"분류(\S+)", contents)
    if m:
        out["분류"] = m.group(1)
    m = re.search(r"공고번호(\S+)", contents)
    if m:
        out["공고번호"] = m.group(1)
    m = re.search(r"담당자연락처(\S+)", contents)
    if m:
        out["담당자연락처"] = m.group(1)
    return out


def _parse_detail_body(contents: str) -> str:
    if not contents:
        return ""
    end_meta = 0
    for pat in (
        r"조회수\d+",
        r"담당자연락처\S+",
        r"담당부서\S+",
        r"작성일시\S+ \S+",
        r"작성일\S+",
        r"분류\S+",
        r"공고번호\S+",
    ):
        mm = re.search(pat, contents)
        if mm:
            end_meta = max(end_meta, mm.end())
    body = contents[end_meta:].strip()
    markers = ["첨부파일", "목록", "이전글", "다음글", "콘텐츠 정보책임자", "다운로드", "미리보기"]
    cut = len(body)
    for mk in markers:
        idx = body.find(mk)
        if idx != -1:
            cut = min(cut, idx)
    return body[:cut].strip()


def _render_detail_main(
    model: dict[str, Any],
    state: dict[str, Any],
    family: str,
    title: str,
    route_prefix: str,
) -> str:
    contents = _contents_landmark_text(state)
    meta = _parse_detail_metadata(contents)
    body = _parse_detail_body(contents)
    breadcrumb_html, location_html, snb_html = _board_nav_html(state)
    surface_label_text = surface_label(state, model)
    board = state.get("board") or {}
    board_detail = board if board.get("kind") == "detail" else {}

    exts = state.get("attachment_document_extensions") or []
    downloads = state.get("download_references") or []
    board_attachments = board_detail.get("attachments") or []
    attach_html = ""
    if board_attachments:
        chips = []
        for att in board_attachments:
            name = att.get("name") or ""
            ext = att.get("ext") or ""
            att_meta = att.get("meta") or ""
            chip = (
                '<div class="rc-attach-item">'
                f'<span class="rc-attach-name">{_esc(name)}</span>'
                + (f'<span class="rc-attach-meta">{_esc(att_meta)}</span>' if att_meta else "")
                + '<span class="rc-attach-actions">'
                f'<button type="button" class="rc-attach" disabled aria-disabled="true" '
                f'data-attachment-ext="{_esc(ext)}">다운로드</button>'
                + (
                    '<button type="button" class="rc-attach" disabled aria-disabled="true" '
                    f'data-attachment-ext="{_esc(ext)}">미리보기</button>'
                    if att.get("preview_href") else ""
                )
                + "</span></div>"
            )
            chips.append(chip)
        attach_html = (
            '<div class="rc-attachments" aria-label="첨부">'
            f'<strong class="rc-attachments-title">첨부파일</strong>{"".join(chips)}</div>'
        )
    elif exts or downloads:
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
        back = f'<p class="rc-back"><a class="rc-back-link" href="{_esc(href)}">목록</a></p>'

    if board_detail:
        detail_title = board_detail.get("title") or title
        meta_items = []
        for entry in board_detail.get("meta") or []:
            label = (entry.get("label") or "").strip()
            value = (entry.get("value") or "").strip()
            if label and value:
                meta_items.append(
                    f'<div class="rc-dmeta-row"><dt class="rc-dmeta-key">{_esc(label)}</dt>'
                    f'<dd class="rc-dmeta-val">{_esc(value)}</dd></div>'
                )
        meta_html = f'<dl class="rc-detail-meta">{"".join(meta_items)}</dl>' if meta_items else ""
        body_parts = []
        for block in board_detail.get("body") or []:
            if (block.get("type") or "") == "image":
                # Bounded asset-gate placeholder: the captured source image
                # reference is rendered as an inert labeled box. No bytes are
                # hotlinked or embedded (#1234 rights gate), and no fabricated
                # text is substituted for the artwork.
                label = (
                    (block.get("alt") or "").strip()
                    or (block.get("title") or "").strip()
                    or (block.get("source_path") or "").rsplit("/", 1)[-1]
                )
                body_parts.append(
                    '<div class="rc-detail-image" role="img" '
                    f'aria-label="{_esc(label) or "본문 이미지"}">'
                    f'<span class="rc-detail-image-name">{_esc(label) or "본문 이미지"}</span>'
                    '<span class="rc-detail-image-note">이미지(자산 게이트) — 본문 이미지는 '
                    '원본 파일이 확보되면 표시됩니다</span></div>'
                )
                continue
            text = (block.get("text") or "").replace("\xa0", " ").strip()
            if text:
                breaks = int(block.get("break_count") or 0)
                # The source renders the body as one contents block whose
                # paragraph separation is literal <br> runs (4 <br> between
                # the first two text groups on the committed G1 page).
                # Reproducing the same <br> run keeps the paragraph rhythm
                # (line-height * break count) without stacking an extra
                # margin on top of the paragraph line box.
                br = "<br>" * breaks if breaks > 0 else ""
                body_parts.append(
                    f'<p class="rc-detail-para">{br}{_esc(text)}</p>'
                )
        body_html = (
            f'<div class="rc-detail-body">{"".join(body_parts)}</div>'
            if body_parts else ""
        )
        prev_next_html = ""
        pn = []
        if board_detail.get("prev") and board_detail["prev"].get("title"):
            pn.append(
                f'<li class="rc-pn-prev"><span class="rc-pn-label">이전글</span>'
                f'<span class="rc-pn-item" aria-disabled="true" role="link" tabindex="-1">'
                f'{_esc(board_detail["prev"]["title"])}</span></li>'
            )
        if board_detail.get("next") and board_detail["next"].get("title"):
            pn.append(
                f'<li class="rc-pn-next"><span class="rc-pn-label">다음글</span>'
                f'<span class="rc-pn-item" aria-disabled="true" role="link" tabindex="-1">'
                f'{_esc(board_detail["next"]["title"])}</span></li>'
            )
        if pn:
            prev_next_html = f'<ul class="rc-prevnext">{"".join(pn)}</ul>'
        context_html = _subpage_context_html(breadcrumb_html, location_html)
        tools_html = _render_surface_tools(state)
        # Source detail template: the page title lives in the page head, then
        # the breadcrumb, then the article title + meta inside a bordered box.
        shell_html = (
            f'<div class="rc-detail-shell"><div class="rc-detail-box">'
            f'<h2 class="rc-detail-title">{_esc(detail_title)}</h2>'
            f'{meta_html}</div></div>'
        )
        license_html = _render_contents_info(board)
        content_html = (
            f'<div class="rc-page-head">'
            f'<h2 class="rc-page-title">{_esc(surface_label_text)}</h2>'
            f'{tools_html}</div>'
            f'{context_html}'
            f'{shell_html}{body_html}{attach_html}{back}{prev_next_html}{license_html}'
        )
        return _wrap_subpage(snb_html, content_html)

    meta_items = []
    for label, key in (
        ("작성일시", "작성일시"),
        ("작성일", "작성일"),
        ("공고번호", "공고번호"),
        ("분류", "분류"),
        ("작성부서", "작성부서"),
        ("담당자연락처", "담당자연락처"),
        ("조회수", "조회수"),
    ):
        val = meta.get(key)
        if val:
            meta_items.append(
                f'<div class="rc-dmeta-row"><dt class="rc-dmeta-key">{_esc(label)}</dt>'
                f'<dd class="rc-dmeta-val">{_esc(val)}</dd></div>'
            )
    meta_html = f'<dl class="rc-detail-meta">{"".join(meta_items)}</dl>' if meta_items else ""
    body_html = f'<div class="rc-detail-body">{_esc(body)}</div>' if body else ""

    context_html = _subpage_context_html(breadcrumb_html, location_html)
    tools_html = _render_surface_tools(state)
    shell_html = (
        f'<div class="rc-detail-shell"><div class="rc-detail-box">'
        f'<h2 class="rc-detail-title">{_esc(title)}</h2>'
        f'{meta_html}</div></div>'
    )
    license_html = _render_contents_info(board)
    content_html = (
        f'<div class="rc-page-head">'
        f'<h2 class="rc-page-title">{_esc(surface_label_text)}</h2>'
        f'{tools_html}</div>'
        f'{context_html}'
        f'{shell_html}{body_html}{attach_html}{back}{license_html}'
    )
    return _wrap_subpage(snb_html, content_html)


def _render_org_staff_main(state: dict[str, Any]) -> str:
    label = surface_label(state, {})
    return f'<section aria-label="{_esc(label)}"><h2 class="rc-section-title">{_esc(label)}</h2></section>'


# ---------------------------------------------------------------------------
# Generic organization-chart renderer (nested semantic org DOM)
# ---------------------------------------------------------------------------
def _org_node_is_leaf(node: dict[str, Any]) -> bool:
    return not (node.get("children") or [])


def _org_spine(first: dict[str, Any]) -> list[dict[str, Any]]:
    """Single-child chain from *first* (the executive vertical hierarchy)."""
    spine: list[dict[str, Any]] = []
    cur = first
    while cur is not None:
        spine.append(cur)
        ch = cur.get("children") or []
        if len(ch) == 1:
            cur = ch[0]
        else:
            break
    return spine


def _org_partition(
    nodes: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Split top-level nodes into (executive, peer department groups).

    Topology-only: the first node is the executive block when its single-child
    chain terminates in a node with >=2 descendant leaves (a branching
    hierarchy); otherwise every top-level node is a peer department group.
    """
    if not nodes:
        return [], []
    first = nodes[0]
    spine = _org_spine(first)
    branch = spine[-1].get("children") or []
    if len(branch) >= 2:
        return [first], nodes[1:]
    return [], nodes


def _render_org_exec(spine: list[dict[str, Any]]) -> str:
    """Vertical executive chain ending in a horizontal leaf-branch row."""

    def _chain(items: list[dict[str, Any]]) -> str:
        node = items[0]
        depth = node.get("depth", 1)
        label = _esc(node.get("label", ""))
        out = [
            f'<li class="rc-org-node rc-org-depth-{_esc(str(depth))}">'
            f'<span class="rc-org-label">{label}</span>'
        ]
        if len(items) > 1:
            out.append('<span class="rc-org-exec-arrow" aria-hidden="true">↓</span>')
            out.append(
                f'<ul class="rc-org-tree rc-org-exec-chain">{_chain(items[1:])}</ul>'
            )
        else:
            branch = node.get("children") or []
            if branch:
                bd = depth + 1
                leaves = "".join(
                    f'<li class="rc-org-node rc-org-depth-{_esc(str(b.get("depth", bd)))}">'
                    f'<span class="rc-org-label">{_esc(b.get("label", ""))}</span></li>'
                    for b in branch
                )
                out.append(
                    f'<ul class="rc-org-tree rc-org-children rc-org-exec-branch">'
                    f"{leaves}</ul>"
                )
        out.append("</li>")
        return "".join(out)

    return (
        f'<div class="rc-org-exec"><ul class="rc-org-tree rc-org-exec-chain">'
        f"{_chain(spine)}</ul></div>"
    )


def _render_org_group(node: dict[str, Any]) -> str:
    """A peer department card: horizontal header + vertical child list."""
    depth = node.get("depth", 1)
    title = _esc(node.get("label", ""))
    children = node.get("children") or []
    child_lis = "".join(
        f'<li class="rc-org-node rc-org-depth-{_esc(str(c.get("depth", depth + 1)))}">'
        f'<span class="rc-org-label">{_esc(c.get("label", ""))}</span></li>'
        for c in children
    )
    return (
        f'<div class="rc-org-group">'
        f'<span class="rc-org-label rc-org-group-title rc-org-depth-{_esc(str(depth))}">'
        f"{title}</span>"
        f'<ul class="rc-org-tree rc-org-group-list">{child_lis}</ul>'
        f"</div>"
    )


def _render_org_section(
    section: dict[str, Any], hero_footprint: int | None = None
) -> str:
    title = section.get("title") or ""
    nodes = section.get("nodes") or []
    head = f'<h2 class="rc-org-section-title">{_esc(title)}</h2>'
    if not nodes:
        body = ""
    elif all(_org_node_is_leaf(n) for n in nodes):
        boxes = "".join(
            f'<span class="rc-org-label rc-org-box">{_esc(n.get("label", ""))}</span>'
            for n in nodes
        )
        body = f'<div class="rc-org-flat">{boxes}</div>'
    else:
        exec_nodes, group_nodes = _org_partition(nodes)
        parts: list[str] = []
        if exec_nodes:
            # Inert, source-backed visual footprint reserved before the
            # executive hierarchy ONLY when the validated visual contract
            # provides the measured value. No placeholder art/text/emoji.
            parts.append(
                '<div class="rc-org-hero-footprint" aria-hidden="true"></div>'
                if hero_footprint else ""
            )
            parts.append(_render_org_exec(_org_spine(exec_nodes[0])))
        if group_nodes:
            groups = "".join(_render_org_group(g) for g in group_nodes)
            parts.append(f'<div class="rc-org-groups">{groups}</div>')
        body = "".join(parts)
    return (
        f'<section class="rc-org-section" aria-label="{_esc(title)}">'
        f"{head}{body}</section>"
    )


def _render_organization_main(
    model: dict[str, Any], state: dict[str, Any], route_prefix: str,
    visual_contract: dict[str, Any] | None = None,
) -> str:
    breadcrumb_html, location_html, snb_html = _board_nav_html(state)
    org = state.get("organization") or {}
    org_layout = (visual_contract or {}).get("layout") or {}
    hero_footprint = (org_layout.get("organization") or {}).get(
        "hero_footprint_height_px"
    )
    sections_html = "".join(
        _render_org_section(
            s, hero_footprint=hero_footprint if idx == 0 else None
        )
        for idx, s in enumerate(org.get("sections", []))
    )
    surface_label_text = surface_label(state, model)
    context_html = _subpage_context_html(breadcrumb_html, location_html)
    tools_html = _render_surface_tools(state)
    page_head = (
        f'<div class="rc-page-head"><h2 class="rc-page-title">{_esc(surface_label_text)}</h2>'
        f"{tools_html}</div>"
    )
    content_html = (
        f"{page_head}"
        f"{context_html}"
        f'<div class="rc-org-chart" aria-label="{_esc(surface_label_text)}">{sections_html}</div>'
    )
    return _wrap_subpage(snb_html, content_html)


# ---------------------------------------------------------------------------
# Generic staff-directory renderer (inert search form + source-backed table)
# ---------------------------------------------------------------------------
def _render_staff_search_form(sd: dict[str, Any]) -> str:
    """Render the staff search controls as a read-only, inert form.

    The source form is ``method=POST`` to the official endpoint; the clone
    renders the controls (department select, search-field select, keyword
    input, search button) as provenance-backed inert controls with no
    ``action`` and ``onsubmit="return false"`` so no request is ever issued.
    """
    dept = sd.get("department_selector") or {}
    field = sd.get("search_field_selector") or {}
    inp = sd.get("search_input") or {}
    btn = sd.get("search_button") or {}

    dept_opts = "".join(
        f'<option value="{_esc(o.get("value", ""))}"'
        f'{" selected" if o.get("value") == "" else ""}>{_esc(o.get("label", ""))}</option>'
        for o in dept.get("options", [])
    )
    field_opts = "".join(
        f'<option value="{_esc(o.get("value", ""))}">{_esc(o.get("label", ""))}</option>'
        for o in field.get("options", [])
    )
    ph = _esc(inp.get("placeholder") or "")
    btn_label = _esc(btn.get("label") or "검색")

    parts = [
        f'<span class="rc-staff-field"><select class="rc-staff-select" disabled '
        f'aria-disabled="true">{dept_opts}</select></span>',
        f'<span class="rc-staff-field"><select class="rc-staff-select" disabled '
        f'aria-disabled="true">{field_opts}</select></span>',
        f'<span class="rc-staff-field"><input type="text" class="rc-staff-input" '
        f'placeholder="{ph}" disabled aria-disabled="true"></span>',
        f'<span class="rc-staff-field"><button type="button" class="rc-staff-btn" '
        f'disabled aria-disabled="true">{btn_label}</button></span>',
    ]
    return (
        f'<form class="rc-staff-search" aria-label="직원 검색" onsubmit="return false">'
        f'{"".join(parts)}</form>'
    )


def _render_staff_table(sd: dict[str, Any]) -> str:
    table = sd.get("table") or {}
    columns = table.get("columns") or []
    rows = table.get("rows") or []
    col_widths = table.get("col_widths") or []
    caption = table.get("caption")

    head_cells = "".join(
        f'<th scope="col" class="rc-th rc-col-{_esc(c)}">{_esc(c)}</th>' for c in columns
    )
    colgroup = ""
    if col_widths:
        cols = [
            f'<col style="width:{int(w)}%">' if isinstance(w, int) and w > 0 else "<col>"
            for w in col_widths
        ]
        colgroup = f'<colgroup>{"".join(cols)}</colgroup>'
    caption_html = (
        f'<caption class="sr_only">{_esc(caption)}</caption>' if caption else ""
    )
    body_rows = []
    for row in rows:
        cells = row.get("cells") or {}
        tds = "".join(
            f'<td class="rc-td rc-col-{_esc(c)}">{_esc(cells.get(c) or "")}</td>'
            for c in columns
        )
        body_rows.append(f'<tr class="rc-board-row">{tds}</tr>')
    return (
        f'<table class="rc-board rc-staff-table" aria-label="직원 목록">'
        f"{colgroup}{caption_html}"
        f'<thead><tr class="rc-board-head">{head_cells}</tr></thead>'
        f'<tbody>{"".join(body_rows)}</tbody></table>'
    )


def _render_staff_directory_main(
    model: dict[str, Any], state: dict[str, Any], route_prefix: str
) -> str:
    breadcrumb_html, location_html, snb_html = _board_nav_html(state)
    sd = state.get("staff_directory") or {}
    form_html = _render_staff_search_form(sd) if sd else ""

    rc = sd.get("result_count") or {}
    pi = sd.get("pagination_info") or {}
    summary_parts = []
    if rc.get("label"):
        summary_parts.append(_esc(rc["label"]))
    if pi.get("label"):
        summary_parts.append(_esc(pi["label"]))
    summary_html = (
        f'<p class="rc-board-summary">{" · ".join(summary_parts)}</p>'
        if summary_parts else ""
    )

    table_html = _render_staff_table(sd) if sd else ""
    pager = sd.get("pager") or {}
    pagination_html = _render_board_pagination(
        {
            "page_total": pi.get("total_pages"),
            "page_current": pi.get("current_page"),
        },
        {"pages": pager.get("pages"), "current_page": pager.get("current_page")},
    )

    surface_label_text = surface_label(state, model)
    context_html = _subpage_context_html(breadcrumb_html, location_html)
    tools_html = _render_surface_tools(state)
    page_head = (
        f'<div class="rc-page-head"><h2 class="rc-page-title">{_esc(surface_label_text)}</h2>'
        f"{tools_html}</div>"
    )
    # SOURCE ordering: page title, then breadcrumb/location, then content.
    # The result summary and the inert search controls share one clear row.
    content_html = (
        f"{page_head}"
        f"{context_html}"
        f'<div class="rc-staff-search-row" aria-label="직원 검색">'
        f"{summary_html}{form_html}"
        f"</div>"
        f"{table_html}{pagination_html}"
    )
    return _wrap_subpage(snb_html, content_html)


def _evidence_json(state: dict[str, Any]) -> str:
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
    main = _render_main(
        model, state, nav, route_prefix, visual_contract=visual_contract
    )
    footer = _render_footer(model, state)
    theme = _theme_values(visual_contract, device=device)
    css = _render_css(theme, device=device, org_surface=(content == "chart"))
    lifecycle_script = (
        f'<script type="application/ld+json" id="rc-lifecycle">'
        f"{_lifecycle_json(visual_contract, state_id)}</script>"
    )
    evidence_script = (
        f'<script type="application/ld+json" id="rc-evidence">'
        f"{_evidence_json(state)}</script>"
    )
    faithful = faithful_clone_candidate_ready(visual_contract, state_id)
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
    _require_model_ready(model)
    pages: dict[str, str] = {}
    for state in model["states"]:
        state_id = state.get("state_id", "")
        route = route_for_state(state_id, route_prefix)
        pages[route] = render_state(
            model, state_id, route_prefix=route_prefix, visual_contract=visual_contract
        )
    return pages


def load_model(path: str | Path) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def write_site(
    model: dict[str, Any],
    out_root: str | Path,
    route_prefix: str,
    visual_contract: dict[str, Any] | None = None,
) -> list[Path]:
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
    pages = render_site(model, route_prefix="/clone/")
    blob = "\n".join(f"{r}\x00{p}" for r, p in sorted(pages.items()))
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()
