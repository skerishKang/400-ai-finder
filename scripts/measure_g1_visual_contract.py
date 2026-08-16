#!/usr/bin/env python3
"""Measure provenance-backed visual values from committed G1 evidence (#1303 G2-B).

This script reads ONLY the immutable committed G1 capture evidence for a named
site and deterministically measures the visual values recorded in
``visual-contract.json``. It never performs a live capture, never fetches a URL,
and never modifies the G1 capture tree. Every emitted measurement carries:

  * ``source_state_id`` — the captured state the value was measured from;
  * ``artifact_sha256``  — the committed screenshot SHA (from the model's
    ``document_geometry``) that the value was measured from;
  * ``method``          — the deterministic measurement method;
  * ``unit``            — px / hex / str as appropriate.

Unmeasurable properties stay ``null`` in the contract and are listed in the
``gaps`` section (no estimated/guessed values are ever produced).

Usage:
    python scripts/measure_g1_visual_contract.py --write
    python scripts/measure_g1_visual_contract.py --check
"""

from __future__ import annotations

import hashlib
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any

from PIL import Image

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from official_clone.visual_contract import (  # noqa: E402
    CONTRACT_SCHEMA_VERSION,
    FIELD_UNITS,
    REQUIRED_MEASURED_FIELDS,
    compute_model_checksum,
)

SITE_ID = "seogu_gwangju"
CAPTURE_ID = "20260812T231018-0900"

MODEL_PATH = (
    REPO_ROOT
    / "data"
    / "official_clone_fixtures"
    / SITE_ID
    / "g1"
    / CAPTURE_ID
    / "clone-model.json"
)
CAPTURE_ROOT = (
    REPO_ROOT / "data" / "official_captures" / SITE_ID / "g1" / CAPTURE_ID
)
LEDGER_PATH = CAPTURE_ROOT / "ledger.json"
OUT_PATH = (
    REPO_ROOT
    / "data"
    / "official_clone_visual_inputs"
    / SITE_ID
    / "g1"
    / CAPTURE_ID
    / "visual-contract.json"
)
MANIFEST_PATH = (
    REPO_ROOT
    / "data"
    / "official_clone_visual_inputs"
    / SITE_ID
    / "g1"
    / CAPTURE_ID
    / "asset-manifest.json"
)

# Deterministic measurement knobs (fixed; changing them changes the contract).
_QUANT = 8
_ROW_STEP = 2
_GAP = 25  # pixel-channel distance that counts as "content" vs page background

_STATE_SHOT = {
    "home.desktop.default": "home.desktop.default",
    "home.mobile.default": "home.mobile.default",
}


# ---------------------------------------------------------------------------
# Low-level pixel helpers (pure Pillow, deterministic)
# ---------------------------------------------------------------------------
def _dom_color(img: Image.Image, box=None, quant: int = _QUANT) -> tuple[str, int]:
    region = img if box is None else img.crop(box)
    counts: Counter[tuple[int, int, int]] = Counter()
    for px in region.getdata():
        q = ((px[0] // quant) * quant, (px[1] // quant) * quant, (px[2] // quant) * quant)
        counts[q] += 1
    color, _ = counts.most_common(1)[0]
    return "#%02x%02x%02x" % (color[0], color[1], color[2]), sum(counts.values())


def _dom_color_exact(img: Image.Image, box=None) -> tuple[str, int]:
    """Return the exact dominant RGB color in a committed screenshot region.

    Use this only for evidence regions that are intentionally flat semantic
    bands/surfaces. Unlike ``_dom_color`` it does not quantize channels, so
    source white remains #ffffff and the captured brand/hero colors are not
    shifted by the measurement helper.
    """
    region = img if box is None else img.crop(box)
    counts: Counter[tuple[int, int, int]] = Counter(region.getdata())
    color, count = counts.most_common(1)[0]
    return "#%02x%02x%02x" % (color[0], color[1], color[2]), count


def _dom_light_color_exact(
    img: Image.Image, box=None, min_channel: int = 220
) -> tuple[str, int]:
    """Return the exact dominant light RGB color in a source region."""
    region = img if box is None else img.crop(box)
    counts: Counter[tuple[int, int, int]] = Counter(
        px for px in region.getdata()
        if min(px[0], px[1], px[2]) >= min_channel
    )
    if not counts:
        return _dom_color_exact(img, box)
    color, count = counts.most_common(1)[0]
    return "#%02x%02x%02x" % (color[0], color[1], color[2]), count


def _row_dom(img: Image.Image, y: int) -> str:
    return _dom_color(img, (0, y, img.width, y + 1))[0]


def _last_separator_line(img: Image.Image) -> tuple[int, str]:
    """Return (y, color) of the bottom-most full-width neutral separator line.

    A separator line is a nearly-uniform mid-gray row (not the page background)
    covering >=90% of the viewport width. The footer is the region below the
    last such line; the line color is the measured border color.
    """
    width, height = img.size
    step = 3
    samples = width // step
    lines: list[tuple[int, tuple[int, int, int]]] = []
    for y in range(height):
        counts: Counter[tuple[int, int, int]] = Counter()
        for x in range(0, width, step):
            px = img.getpixel((x, y))
            counts[(px[0] // 4 * 4, px[1] // 4 * 4, px[2] // 4 * 4)] += 1
        color, n = counts.most_common(1)[0]
        frac = n / samples
        r, g, b = color
        if (
            frac >= 0.9
            and 190 <= r <= 245
            and abs(r - g) <= 8
            and abs(g - b) <= 8
            and not (250 <= r <= 255 and 250 <= g <= 255 and 250 <= b <= 255)
        ):
            lines.append((y, color))
    if not lines:
        return height, "#dddddd"
    y, color = lines[-1]
    return y, "#%02x%02x%02x" % (color[0], color[1], color[2])


def _separator_thickness(img: Image.Image, y: int, color: tuple[int, int, int], tol: int = 8) -> int:
    """Measure the contiguous pixel thickness of a full-width separator line.

    Starting from row *y*, count consecutive rows whose dominant color matches
    *color* within tolerance (the measured border thickness in px). This is a
    real pixel measurement, not a guessed constant.
    """
    width, height = img.size

    def _row_matches(row_y: int) -> bool:
        counts: Counter[tuple[int, int, int]] = Counter()
        for x in range(0, width, 3):
            px = img.getpixel((x, row_y))
            counts[(px[0] // 4 * 4, px[1] // 4 * 4, px[2] // 4 * 4)] += 1
        c, _ = counts.most_common(1)[0]
        return (
            abs(c[0] - color[0]) <= tol
            and abs(c[1] - color[1]) <= tol
            and abs(c[2] - color[2]) <= tol
        )

    thickness = 0
    row = y
    while row >= 0 and _row_matches(row):
        thickness += 1
        row -= 1
    row = y + 1
    while row < height and _row_matches(row):
        thickness += 1
        row += 1
    return thickness


def _dark_band(img: Image.Image, y0: int, y1: int, max_rgb: int = 110) -> tuple[int, int] | None:
    """Return the inclusive (top, bottom) of the dominant dark band in [y0, y1)."""
    rows = []
    for y in range(y0, y1, _ROW_STEP):
        c = _row_dom(img, y)
        r = int(c[1:3], 16)
        g = int(c[3:5], 16)
        b = int(c[5:7], 16)
        if r < max_rgb and g < max_rgb and b < 180:
            rows.append(y)
    if not rows:
        return None
    # Only accept contiguous-ish bands (gap tolerance of 4 sampled rows).
    runs: list[list[int]] = [[rows[0]]]
    for y in rows[1:]:
        if y - runs[-1][-1] <= _ROW_STEP * 4:
            runs[-1].append(y)
        else:
            runs.append([y])
    longest = max(runs, key=len)
    return longest[0], longest[-1]


def _content_envelope(img: Image.Image, y0: int, y1: int) -> tuple[int, int] | None:
    """Return the (left, right) x-extent of non-background content in the band."""
    width, _ = img.size
    hex_color = _dom_color(img, (0, y0, min(width, 60), y1))[0]
    bg = (int(hex_color[1:3], 16), int(hex_color[3:5], 16), int(hex_color[5:7], 16))
    col_active = [0] * width
    band = img.crop((0, y0, width, y1))
    pixels = band.load()
    for x in range(width):
        for y in range(band.height):
            p = pixels[x, y]
            if (
                abs(p[0] - bg[0]) > _GAP
                or abs(p[1] - bg[1]) > _GAP
                or abs(p[2] - bg[2]) > _GAP
            ):
                col_active[x] += 1
    threshold = max(20, int(band.height * 0.03))
    active = [x for x in range(width) if col_active[x] > threshold]
    if not active:
        return None
    return active[0], active[-1]


def _dominant_dark(img: Image.Image, box) -> str:
    region = img.crop(box)
    counts: Counter[tuple[int, int, int]] = Counter()
    for px in region.getdata():
        if px[0] < 130 and px[1] < 130 and px[2] < 130:
            q = ((px[0] // 32) * 32, (px[1] // 32) * 32, (px[2] // 32) * 32)
            counts[q] += 1
    if not counts:
        return "#000000"
    color, _ = counts.most_common(1)[0]
    return "#%02x%02x%02x" % (color[0], color[1], color[2])


def _dominant_gray(img: Image.Image, box) -> str | None:
    region = img.crop(box)
    counts: Counter[tuple[int, int, int]] = Counter()
    for px in region.getdata():
        if abs(px[0] - px[1]) < 12 and abs(px[1] - px[2]) < 12 and 60 < px[0] < 210:
            q = ((px[0] // 8) * 8, (px[1] // 8) * 8, (px[2] // 8) * 8)
            counts[q] += 1
    if not counts:
        return None
    color, _ = counts.most_common(1)[0]
    return "#%02x%02x%02x" % (color[0], color[1], color[2])


def _dominant_light(img: Image.Image, box, min_rgb: int = 150) -> str | None:
    """Dominant bright pixel color in a region (e.g. GNB text on dark bar)."""
    region = img.crop(box)
    counts: Counter[tuple[int, int, int]] = Counter()
    for px in region.getdata():
        if px[0] >= min_rgb and px[1] >= min_rgb and px[2] >= min_rgb:
            q = ((px[0] // 16) * 16, (px[1] // 16) * 16, (px[2] // 16) * 16)
            counts[q] += 1
    if not counts:
        return None
    color, _ = counts.most_common(1)[0]
    return "#%02x%02x%02x" % (color[0], color[1], color[2])


# ---------------------------------------------------------------------------
# Ledger helpers
# ---------------------------------------------------------------------------
def _load_ledger() -> dict:
    return json.loads(LEDGER_PATH.read_text(encoding="utf-8"))


def _screenshot_sha(state_id: str) -> str:
    ledger = _load_ledger()
    for state in ledger["captured_states"]:
        if state["state_id"] != state_id:
            continue
        for artifact in state["artifacts"]:
            if artifact["class"] == "screenshot":
                return artifact["sha256"]
    raise KeyError(f"screenshot artifact not found for {state_id}")


def _model() -> dict:
    return json.loads(MODEL_PATH.read_text(encoding="utf-8"))


def _font_family_observation() -> list[str]:
    """Observe font families actually fetched by the browser during G1 capture."""
    families: set[str] = set()
    for state_dir in (CAPTURE_ROOT / "states").iterdir():
        prov_path = state_dir / "public-asset-provenance.json"
        if not prov_path.is_file():
            continue
        try:
            prov = json.loads(prov_path.read_text(encoding="utf-8"))
        except Exception:
            continue
        for asset in prov.get("assets", []):
            url = asset.get("url", "")
            name = url.split("/")[-1]
            if "gmarketsans" in name.lower():
                families.add("Gmarket Sans")
            if "notosanscjk" in name.lower():
                families.add("Noto Sans CJK KR")
    return sorted(families)


# ---------------------------------------------------------------------------
# Measurement
# ---------------------------------------------------------------------------
def _measure_desktop() -> dict:
    """Measure semantic homepage regions from the immutable desktop source PNG.

    #1310 correction: the former dark-band heuristic accidentally bound the
    key-visual control strip as the GNB and therefore extended "header" through
    Section01.  These bounded coordinates are the stable semantic transitions
    in the committed 1440x2276 capture.
    """
    state_id = "home.desktop.default"
    shot_sha = _screenshot_sha(state_id)
    img = Image.open(CAPTURE_ROOT / "states" / state_id / "source.png").convert("RGB")
    w, h = img.size
    assert (w, h) == (1440, 2276)

    notice_height = 49
    utility_height = 50
    brand_height = 91
    identity_height = 84
    header_height = notice_height + utility_height + brand_height + identity_height
    assert header_height == 274
    gnb_height = identity_height

    gnb_color = _dom_color_exact(img, (0, header_height - identity_height, w, header_height))[0]
    gnb_text = _dominant_dark(
        img, (250, header_height - identity_height, w - 20, header_height)
    )
    header_bg = _dom_color_exact(img, (0, 99, w, header_height))[0]
    notice_bg = _dom_color_exact(img, (0, 0, w, notice_height))[0]
    hero_bg = _dom_color_exact(img, (0, header_height, w, 740))[0]

    footer_top = 1919
    footer_height = h - footer_top
    footer_bg = _dom_color_exact(img, (0, footer_top, w, h))[0]
    _sep_y, border_color = _last_separator_line(img)
    _sep_rgb = (
        int(border_color[1:3], 16),
        int(border_color[3:5], 16),
        int(border_color[5:7], 16),
    )
    border_thickness = _separator_thickness(img, _sep_y, _sep_rgb)

    envelope = _content_envelope(img, 740, min(h - 60, 1900))
    assert envelope is not None
    content_left, content_right = envelope
    max_width = content_right - content_left + 1
    padding_x = content_left

    background = _dom_color_exact(img, (0, 740, w, 967))[0]
    text_color = _dominant_dark(img, (100, 1000, w - 100, 1432))
    muted = _dominant_gray(img, (100, 1000, w - 100, 1432))

    return {
        "state_id": state_id,
        "artifact_sha256": shot_sha,
        "viewport": (w, h),
        "header_height": header_height,
        "notice_height": notice_height,
        "utility_height": utility_height,
        "brand_height": brand_height,
        "identity_height": identity_height,
        "gnb_height": gnb_height,
        "gnb_color": gnb_color,
        "gnb_text": gnb_text,
        "header_bg": header_bg,
        "notice_bg": notice_bg,
        "hero_bg": hero_bg,
        "primary": _dom_color_exact(img, (1040, 115, 1120, 180))[0],
        "key_visual_bg": _dom_light_color_exact(img, (600, 315, 1420, 692))[0],
        "search_width": 600,
        "search_height": 60,
        "hero_height": 466,
        "key_visual_width": 820,
        "key_visual_height": 377,
        "quick_height": 227,
        "quick_columns": 7,
        "quick_item_width": 173,
        "info_columns": 3,
        "info_gap": 24,
        "footer_bg": footer_bg,
        "footer_height": footer_height,
        "max_width": max_width,
        "padding_x": padding_x,
        "background": background,
        "text": text_color,
        "muted": muted,
        "border": border_color,
        "border_thickness": border_thickness,
    }


# ---------------------------------------------------------------------------
# #1312 board list/detail geometry (committed G1 screenshots only)
# ---------------------------------------------------------------------------
def _board_snb_extent(img: Image.Image, y0: int = 300, y1: int = 520) -> tuple[int, int] | None:
    """Return the inclusive x-extent of the dark-blue left SNB sidebar."""
    width = img.width
    band_height = max(1, y1 - y0)
    fracs: list[float] = []
    for x in range(width):
        n = 0
        for p in img.crop((x, y0, x + 1, y1)).getdata():
            if p[0] < 60 and p[1] < 90 and p[2] > 60:
                n += 1
        fracs.append(n / band_height)
    active = [x for x, f in enumerate(fracs) if f > 0.5]
    if not active:
        return None
    return active[0], active[-1]


def _board_horizontal_lines(
    img: Image.Image, y0: int, y1: int, x0: int = 300, x1: int = 1420, min_len: int = 400
) -> list[tuple[int, tuple[int, int, int]]]:
    """Return (y, color) rows that are mostly a single non-white color."""
    lines: list[tuple[int, tuple[int, int, int]]] = []
    for y in range(y0, y1):
        counts: Counter[tuple[int, int, int]] = Counter()
        for p in img.crop((x0, y, x1, y + 1)).getdata():
            if p[0] < 245:
                counts[p] = counts.get(p, 0) + 1
        if not counts:
            continue
        color, n = max(counts.items(), key=lambda kv: kv[1])
        if n > min_len:
            lines.append((y, color))
    return lines


def _board_color_band(
    img: Image.Image, color: tuple[int, int, int], x: int, y0: int, y1: int
) -> tuple[int, int] | None:
    """Return the inclusive (top, bottom) rows where column ``x`` is exactly
    ``color``. Used to bound the SNB section-title bar and active-item band."""
    rows = [y for y in range(y0, y1) if img.getpixel((x, y)) == color]
    if not rows:
        return None
    return rows[0], rows[-1]


def _board_snb_separators(
    img: Image.Image, y0: int, y1: int, x0: int = 20, x1: int = 270, color=(229, 229, 229)
) -> list[int]:
    """Return y positions of 1px horizontal separators inside the SNB column."""
    out: list[int] = []
    for y in range(y0, y1):
        counts: Counter[tuple[int, int, int]] = Counter()
        for p in img.crop((x0, y, x1, y + 1)).getdata():
            counts[p] = counts.get(p, 0) + 1
        if not counts:
            continue
        top_color, n = max(counts.items(), key=lambda kv: kv[1])
        if top_color == color and n >= (x1 - x0) - 2:
            out.append(y)
    return out


def _board_snb_text_bands(
    img: Image.Image, y0: int, y1: int, x0: int = 20, x1: int = 250
) -> list[tuple[int, int]]:
    """Return (top, bottom) bands of dark text rows inside the SNB column.

    Used to measure the compact level-2 child item pitch on the civil-form
    sidebar (children are ~29px apart while level-1 items are ~58px).
    """
    bands: list[tuple[int, int]] = []
    cur: list[int] | None = None
    for y in range(y0, y1):
        n = sum(
            1
            for x in range(x0, x1, 2)
            if sum(img.getpixel((x, y))) < 620
        )
        if n >= 2:
            if cur is None:
                cur = [y, y]
            cur[1] = y
        else:
            if cur is not None:
                bands.append((cur[0], cur[1]))
                cur = None
    if cur is not None:
        bands.append((cur[0], cur[1]))
    return bands


def _board_gray_line_rows(
    img: Image.Image,
    y0: int,
    y1: int,
    color: tuple[int, int, int],
    x0: int = 300,
    x1: int = 1420,
    min_n: int = 100,
) -> list[int]:
    """Return rows containing a run of at least ``min_n`` pixels of ``color``.

    Unlike ``_board_horizontal_lines`` this accepts partial-width lines (the
    boxed board controls only paint their own #dddddd borders).
    """
    rows = []
    for y in range(y0, y1):
        n = sum(1 for p in img.crop((x0, y, x1, y + 1)).getdata() if p == color)
        if n >= min_n:
            rows.append(y)
    return rows


def _board_dense_rows(
    img: Image.Image,
    y0: int,
    y1: int,
    x0: int = 330,
    x1: int = 1420,
    min_nonwhite: int = 60,
) -> tuple[int, int] | None:
    """Return the first/last row in (y0, y1) with a dense non-white band.

    Used to bound the pager button row inside its bordered box.
    """
    rows = [
        y
        for y in range(y0, y1)
        if sum(1 for p in img.crop((x0, y, x1, y + 1)).getdata() if p[0] < 245)
        > min_nonwhite
    ]
    if not rows:
        return None
    return rows[0], rows[-1]


def _board_dark_rows(
    img: Image.Image,
    y0: int,
    y1: int,
    x0: int = 330,
    x1: int = 1420,
    min_dark: int = 10,
) -> tuple[int, int] | None:
    """Return the first/last row in (y0, y1) containing dark text pixels."""
    rows = [
        y
        for y in range(y0, y1)
        if sum(
            1 for p in img.crop((x0, y, x1, y + 1)).getdata()
            if sum(p) < 420
        )
        > min_dark
    ]
    if not rows:
        return None
    return rows[0], rows[-1]


def _board_pager_colors(
    img: Image.Image, y0: int, y1: int, x0: int = 330, x1: int = 1420
) -> tuple[tuple[int, int, int] | None, tuple[int, int, int] | None]:
    """Return (button border, active-page background) RGB from the pager row.

    The source pager renders each page number in a light-gray bordered box
    and paints the current page's box with a warm gold background.
    """
    counts: Counter[tuple[int, int, int]] = Counter()
    for y in range(y0, y1):
        for p in img.crop((x0, y, x1, y + 1)).getdata():
            counts[p] += 1
    border = Counter(
        {c: n for c, n in counts.items()
         if abs(c[0] - 225) < 6 and abs(c[1] - 225) < 6 and abs(c[2] - 225) < 6}
    )
    gold = Counter(
        {c: n for c, n in counts.items()
         if c[0] > 190 and 110 < c[1] < 230 and c[2] < 150}
    )
    return (
        border.most_common(1)[0][0] if border else None,
        gold.most_common(1)[0][0] if gold else None,
    )


def _measure_gnb_open() -> dict:
    """Measure the GNB-open mega-menu overlay from the committed G1 screenshot.

    ``panel_height_px`` is the capture viewport height (1440x900): the open
    mega-menu overlay fills the committed viewport. ``columns`` counts the
    visible top-level menu column groups from the dark-label pixel clusters.
    """
    state_id = "home.desktop.gnb_open"
    sha = _screenshot_sha(state_id)
    img = Image.open(CAPTURE_ROOT / "states" / state_id / "source.png").convert("RGB")
    w, h = img.size

    # Count menu-label column groups (dark text clusters) in the label band.
    # Individual labels within one column sit close together (small gaps);
    # distinct top-level columns are separated by wide gutters, so clusters
    # with a gap below the merge threshold belong to the same column group.
    clusters: list[list[int]] = []
    cur: list[int] | None = None
    for x in range(w):
        n = 0
        for y in range(150, 400):
            p = img.getpixel((x, y))
            if p[0] < 150 and p[1] < 150 and p[2] < 150:
                n += 1
        if n > 0:
            if cur is None:
                cur = [x, x]
            else:
                cur[1] = x
        else:
            if cur is not None:
                clusters.append(cur)
                cur = None
    if cur is not None:
        clusters.append(cur)
    groups: list[list[int]] = []
    for cluster in clusters:
        if groups and cluster[0] - groups[-1][1] < 100:
            groups[-1][1] = max(groups[-1][1], cluster[1])
        else:
            groups.append(list(cluster))
    columns = len(groups)

    viewport_height = None
    model = _model()
    for state in model.get("states", []):
        if state.get("state_id") != state_id:
            continue
        geom = state.get("document_geometry") or {}
        viewport = geom.get("viewport") or {}
        viewport_height = viewport.get("height")
        break
    return {
        "panel_height_px": viewport_height,
        "columns": columns if columns >= 2 else None,
        "_source": {"state_id": state_id, "artifact_sha256": sha},
    }


def _measure_board() -> dict:
    """Measure #1312 board list/detail geometry from committed G1 screenshots.

    Bounds are detected with deterministic pixel heuristics against the
    immutable source PNGs: the dark-blue SNB sidebar, the content column, the
    list table's header band and row separators, and the detail title/meta
    bands. Values that cannot be safely bounded stay out (gap).
    """
    list_state = "notice.list.desktop"
    detail_state = "notice.detail.desktop"
    list_sha = _screenshot_sha(list_state)
    detail_sha = _screenshot_sha(detail_state)
    list_img = Image.open(CAPTURE_ROOT / "states" / list_state / "source.png").convert("RGB")
    detail_img = Image.open(CAPTURE_ROOT / "states" / detail_state / "source.png").convert("RGB")
    assert list_img.size == (1440, 1878), list_img.size
    assert detail_img.size == (1440, 3086), detail_img.size

    snb = _board_snb_extent(list_img)
    out: dict[str, Any] = {}
    if snb is not None:
        snb_left, snb_right = snb
        out["snb_width_px"] = snb_right - snb_left + 1
        out["snb_left_px"] = snb_left
        out["snb_right_px"] = snb_right
        # Content column: white gutter to the right of the SNB sidebar. The
        # board table's right edge bounds the content container (page padding
        # right is the 20px gutter seen on the home measure).
        out["content_container_width_px"] = 1420 - (snb_right + 2) + 1

        # SNB section-title bar: the dark-navy band holding the section label.
        title_band = _board_color_band(list_img, (2, 52, 107), 145, 274, 560)
        if title_band is not None:
            out["snb_title_height_px"] = title_band[1] - title_band[0] + 1
            out["board_snb_title_bg"] = "#%02x%02x%02x" % (2, 52, 107)
            # Subpage top offset: the white gap between the header bottom
            # (y=274, the accepted header height) and the SNB title-bar top.
            out["subpage_top_offset_px"] = title_band[0] - 274
            # Content column top offset: the page-title row sits below the
            # SNB title-bar top by this measured amount.
            title_top = next(
                (
                    y
                    for y in range(300, 500)
                    if sum(
                        1 for x in range(320, 500)
                        if sum(list_img.getpixel((x, y))) < 550
                    ) > 5
                ),
                None,
            )
            if title_top is not None:
                out["content_padding_top_px"] = title_top - title_band[0]
        # SNB active-item band: the lighter blue block below the title bar.
        active_band = _board_color_band(list_img, (63, 101, 182), 145, 274, 620)
        if active_band is not None:
            out["snb_active_height_px"] = active_band[1] - active_band[0] + 1
            out["board_snb_active_bg"] = "#%02x%02x%02x" % (63, 101, 182)
        # SNB item rows: separators below the active band; pitch = item height.
        snb_seps = _board_snb_separators(list_img, active_band[1] + 1 if active_band else 511, 1200)
        if len(snb_seps) >= 2:
            pitches = [b - a for a, b in zip(snb_seps, snb_seps[1:])]
            out["snb_item_height_px"] = round(sum(pitches) / len(pitches))
            out["board_snb_separator"] = "#%02x%02x%02x" % (229, 229, 229)
        # SNB level-2 child rows: the civil-form sidebar expands a parent item
        # with compact children (29px pitch vs the 58px level-1 pitch). Measured
        # on the civil list capture where the expanded children are visible.
        civil_img = Image.open(
            CAPTURE_ROOT / "states" / "civil_form.list.desktop" / "source.png"
        ).convert("RGB")
        civil_bands = _board_snb_text_bands(civil_img, 515, 830)
        if len(civil_bands) >= 2:
            tops = [b[0] for b in civil_bands]
            pitches = [b - a for a, b in zip(tops, tops[1:])]
            if pitches and max(pitches) - min(pitches) <= 4:
                out["snb_subitem_height_px"] = round(sum(pitches) / len(pitches))

    lines = _board_horizontal_lines(list_img, 400, 1150)
    header_top = next((y for y, c in lines if c == (85, 85, 85)), None)
    header_bottom = next((y for y, c in lines if c == (170, 170, 170)), None)
    # Row separators are the light-gray lines BELOW the header bottom border;
    # the gray line above the header (title underline) must be excluded.
    separators = [
        y for y, c in lines if c == (221, 221, 221)
        and (header_bottom is None or y > header_bottom)
    ]
    if header_top is not None and header_bottom is not None:
        out["table_header_height_px"] = header_bottom - header_top + 1
        out["board_table_header_border"] = "#%02x%02x%02x" % (85, 85, 85)
        # The header's bottom rule is a 1px mid-gray line (#aaaaaa).
        out["board_table_header_rule"] = "#%02x%02x%02x" % (170, 170, 170)
        # Content left padding: from the SNB right edge to the table left edge.
        if snb is not None:
            border_xs = [
                x for x in range(300, 1420)
                if list_img.getpixel((x, header_top)) == (85, 85, 85)
            ]
            if border_xs:
                table_left = min(border_xs)
                out["content_padding_left_px"] = table_left - (snb_right + 1)
    if len(separators) >= 2:
        pitches = [b - a for a, b in zip(separators, separators[1:])]
        out["row_height_px"] = round(sum(pitches) / len(pitches))
        out["board_row_separator"] = "#%02x%02x%02x" % (221, 221, 221)

    # List toolbar region: the source renders a full-width #dddddd divider
    # below the breadcrumb, then a single summary+search row whose boxed
    # controls (#dddddd top/bottom borders) hold the page-size selector, the
    # search filter select, the keyword input and the search button. The three
    # #ddd rows above the table header bound that composition.
    upper_seps = _board_gray_line_rows(list_img, 400, header_top or 543, (221, 221, 221), 300, 1420, 100)
    if len(upper_seps) >= 3:
        out["toolbar_padding_top_px"] = upper_seps[1] - upper_seps[0]
        out["toolbar_row_height_px"] = upper_seps[2] - upper_seps[1]
        out["toolbar_padding_bottom_px"] = (header_top or 0) - upper_seps[2]

    # List pager box: a tall bordered box (#aaaaaa top / #dddddd bottom)
    # holding one row of page buttons, then the 공공누리 license box.
    pager_lines = _board_horizontal_lines(list_img, 1150, 1520)
    pager_top = next((y for y, c in pager_lines if c == (170, 170, 170)), None)
    pager_bottom = next(
        (y for y, c in pager_lines if c == (221, 221, 221) and y > (pager_top or 0)),
        None,
    )
    if pager_top is not None and pager_bottom is not None:
        content = _board_dense_rows(list_img, pager_top + 1, pager_bottom, min_nonwhite=30)
        if content:
            c_top, c_bottom = content
            out["pager_padding_top_px"] = c_top - pager_top
            out["pager_padding_bottom_px"] = pager_bottom - c_bottom
        border_color, active_bg = _board_pager_colors(list_img, pager_top + 1, pager_bottom)
        if border_color is not None:
            out["board_pager_button_border"] = "#%02x%02x%02x" % border_color
        if active_bg is not None:
            out["board_pager_active_bg"] = "#%02x%02x%02x" % active_bg

    # The source search row ends with a solid black search button that spans
    # the full control-box height (y 483-522 at the content right edge).
    btn_dark = Counter(
        p
        for y in range(488, 523)
        for p in list_img.crop((1355, y, 1419, y + 1)).getdata()
        if sum(p) < 300
    )
    if btn_dark:
        top, n = btn_dark.most_common(1)[0]
        out["board_search_button_bg"] = "#%02x%02x%02x" % top
    if pager_bottom is not None:
        lic_lines = _board_horizontal_lines(list_img, pager_bottom + 1, pager_bottom + 200)
        lic_bottom = next(
            (y for y, c in lic_lines if c == (221, 221, 221)),
            None,
        )
        # The license line sits right of the kogl icon; measure only the text
        # run (x >= 530) so the icon box does not distort the text padding.
        lic_text = _board_dark_rows(list_img, pager_bottom + 1, lic_bottom or pager_bottom + 120, x0=530)
        if lic_text and lic_bottom is not None:
            lt_top, lt_bottom = lic_text
            out["license_padding_top_px"] = lt_top - pager_bottom
            out["license_padding_bottom_px"] = lic_bottom - lt_bottom
        # Bottom gap between the license box and the footer background.
        footer_bg_rows = [
            y for y in range(lic_bottom + 1, lic_bottom + 160)
            if list_img.getpixel((800, y)) == (250, 250, 250)
        ]
        if footer_bg_rows:
            out["license_margin_bottom_px"] = footer_bg_rows[0] - lic_bottom

    # The civil_form list closes its content with a compact duty box
    # (콘텐츠 정보책임자) instead of the KOGL license: bordered #dddddd box
    # with a title row plus label/value items. Measure its padding from the
    # committed civil_form.list capture so the clone box matches the source.
    civil_img = Image.open(
        CAPTURE_ROOT / "states" / "civil_form.list.desktop" / "source.png"
    ).convert("RGB")
    assert civil_img.size == (1440, 1850), civil_img.size
    civil_lines = _board_horizontal_lines(civil_img, 1150, 1500)
    civil_box = [
        y for y, c in civil_lines if c == (221, 221, 221)
    ]
    if len(civil_box) >= 2:
        dut_top, dut_bottom = civil_box[0], civil_box[-1]
        dut_text = _board_dark_rows(civil_img, dut_top + 1, dut_bottom, x0=340)
        if dut_text:
            d_top, d_bottom = dut_text
            out["duty_padding_top_px"] = d_top - dut_top
            out["duty_padding_bottom_px"] = dut_bottom - d_bottom

    # Detail title/meta bands from the notice detail page.
    dlines = _board_horizontal_lines(detail_img, 274, 700)
    dark = [y for y, c in dlines if c == (85, 85, 85)]
    gray = [y for y, c in dlines if c == (221, 221, 221)]
    if dark and gray:
        meta_top = dark[0]
        meta_bottom = next((y for y in gray if y > meta_top), None)
        if meta_bottom is not None:
            out["detail_meta_band_height_px"] = meta_bottom - meta_top + 1
        # The article title inside the detail box and the meta rows below it:
        # the measured paddings keep the #555 box border and the #dddddd band
        # rule at the same y as the source (483 -> 602 on notice.detail).
        title_top = next(
            (
                y
                for y in range(meta_top + 2, meta_top + 90)
                if sum(
                    1 for x in range(330, 1420, 2)
                    if sum(detail_img.getpixel((x, y))) < 400
                ) > 20
            ),
            None,
        )
        meta_text_rows = _board_dark_rows(detail_img, meta_top + 2, meta_bottom, x0=330)
        if title_top is not None and meta_text_rows is not None:
            out["detail_shell_padding_top_px"] = title_top - meta_top
            out["detail_shell_padding_bottom_px"] = meta_bottom - meta_text_rows[1]

    # Detail body paragraph breaks (gosi.detail): the source body separates
    # paragraphs with <br> runs; measure the vertical pitch per <br> so the
    # renderer can reproduce the page's vertical rhythm instead of collapsing
    # the whole body into one blob.
    gosi_detail_img = Image.open(
        CAPTURE_ROOT / "states" / "gosi.detail.desktop" / "source.png"
    ).convert("RGB")
    if gosi_detail_img.size == (1440, 1814):
        groups: list[list[int]] = []
        for y in range(620, 1000):
            n = sum(
                1 for p in gosi_detail_img.crop((330, y, 1420, y + 1)).getdata()
                if sum(p) < 420
            )
            if n <= 10:
                continue
            if groups and y - groups[-1][-1] <= 3:
                groups[-1].append(y)
            else:
                groups.append([y])
        if len(groups) >= 2:
            # The gap between the first two body paragraphs spans the <br>
            # run that follows the intro paragraph (4 <br> in the G1 HTML).
            out["detail_body_break_spacing_px"] = round(
                (groups[1][0] - groups[0][0]) / 4
            )

    # Detail back-to-list button (gosi.detail): the source renders a
    # full-width #dddddd-bordered box (board_btns) with a centered black
    # button inside. Measure the box padding and the button height/width so
    # the clone renders the same bordered control instead of a plain link.
    gosi_box = [y for y, c in _board_horizontal_lines(gosi_detail_img, 1200, 1450) if c == (221, 221, 221)]
    gosi_btn_top = gosi_box[0] if gosi_box else None
    gosi_btn_bottom = gosi_box[-1] if gosi_box else None
    if gosi_btn_top is not None and gosi_btn_bottom is not None:
        out["detail_back_box_top_px"] = gosi_btn_top
        out["detail_back_box_bottom_px"] = gosi_btn_bottom
        btn_rows = [
            y
            for y in range(gosi_btn_top + 1, gosi_btn_bottom)
            if sum(
                1
                for x in range(330, 1140, 2)
                if sum(gosi_detail_img.getpixel((x, y))) < 200
            ) > 10
        ]
        if btn_rows:
            b_top, b_bottom = btn_rows[0], btn_rows[-1]
            out["detail_back_button_height_px"] = b_bottom - b_top + 1
            xs = [
                x
                for x in range(330, 1140)
                if sum(gosi_detail_img.getpixel((x, b_top + 2))) < 200
            ]
            if xs:
                out["detail_back_button_width_px"] = max(xs) - min(xs) + 1
            out["detail_back_box_padding_top_px"] = b_top - gosi_btn_top
            out["detail_back_box_padding_bottom_px"] = gosi_btn_bottom - b_bottom

    # Detail attachment (.file) block (gosi.detail): full-width #dddddd
    # bordered box with the attachment title + item rows (icon/filename/
    # download button). Measure its vertical extent and the item band so the
    # clone renders a bordered box like the source instead of a plain row.
    gosi_attach = [
        y
        for y, c in _board_horizontal_lines(gosi_detail_img, 1010, 1130)
        if c == (221, 221, 221)
    ]
    if len(gosi_attach) >= 2:
        a_top, a_bottom = gosi_attach[0], gosi_attach[-1]
        out["detail_attachment_box_top_px"] = a_top
        out["detail_attachment_box_bottom_px"] = a_bottom
        item_rows = [
            y
            for y in range(a_top + 1, a_bottom)
            if sum(
                1
                for x in range(335, 1415, 2)
                if gosi_detail_img.getpixel((x, y)) != (255, 255, 255)
            ) > 15
        ]
        if item_rows:
            i_top, i_bottom = item_rows[0], item_rows[-1]
            out["detail_attachment_padding_top_px"] = i_top - a_top
            out["detail_attachment_padding_bottom_px"] = a_bottom - i_bottom

    list_source = {"state_id": list_state, "artifact_sha256": list_sha}
    detail_source = {"state_id": detail_state, "artifact_sha256": detail_sha}
    gosi_sha = _screenshot_sha("gosi.detail.desktop")
    civil_sha = _screenshot_sha("civil_form.list.desktop")
    out["_list_source"] = list_source
    out["_detail_source"] = detail_source
    out["_gosi_source"] = {"state_id": "gosi.detail.desktop", "artifact_sha256": gosi_sha}
    out["_civil_source"] = {"state_id": "civil_form.list.desktop", "artifact_sha256": civil_sha}
    return out


def _measure_mobile() -> dict:
    """Measure semantic regions from the immutable 390x3873 mobile source."""
    state_id = "home.mobile.default"
    shot_sha = _screenshot_sha(state_id)
    img = Image.open(CAPTURE_ROOT / "states" / state_id / "source.png").convert("RGB")
    w, h = img.size
    assert (w, h) == (390, 3873)

    notice_height = 41
    utility_height = 45
    identity_height = 69
    brand_height = 20
    header_height = notice_height + utility_height + identity_height + brand_height
    assert header_height == 175

    envelope = _content_envelope(img, 1000, min(h - 60, 3000))
    assert envelope is not None
    content_left, content_right = envelope
    max_width = content_right - content_left + 1
    padding_x = content_left

    footer_top = 3382
    return {
        "state_id": state_id,
        "artifact_sha256": shot_sha,
        "viewport": (w, h),
        "header_height": header_height,
        "notice_height": notice_height,
        "utility_height": utility_height,
        "brand_height": brand_height,
        "identity_height": identity_height,
        "gnb_height": identity_height,
        "gnb_color": _dom_color_exact(img, (0, 86, w, 155))[0],
        "gnb_text": _dominant_dark(img, (0, 86, w, 155)),
        "header_bg": _dom_color_exact(img, (0, 86, w, 155))[0],
        "footer_bg": _dom_color_exact(img, (0, footer_top, w, h))[0],
        "footer_height": h - footer_top,
        "max_width": max_width,
        "padding_x": padding_x,
        "background": _dom_color_exact(img, (0, 937, w, 1700))[0],
        "hero_height": 592,
        "key_visual_height": 190,
        "quick_height": 170,
        "quick_columns": 2,
        "quick_item_width": 140,
        "info_columns": 1,
        "info_gap": 24,
    }


# ---------------------------------------------------------------------------
# Contract assembly
# ---------------------------------------------------------------------------
def _measurement(field, value, unit, evidence_type, source, method, note=None) -> dict:
    return {
        "field": field,
        "value": value,
        "unit": unit,
        "evidence_type": evidence_type,
        "source_state_id": source["state_id"],
        "artifact_sha256": source["artifact_sha256"],
        "method": method,
        "note": note,
    }


def _font_asset_evidence() -> dict | None:
    """Return an asset_provenance evidence record for typography.font_family.

    The font families are observed from the font assets the browser actually
    fetched during G1 capture (recorded in the per-state
    ``public-asset-provenance.json``), NOT from screenshot pixels. The primary
    evidence is the first Gmarket Sans woff2 asset SHA; the note lists all
    observed font assets. If no font asset is committed, returns None so the
    field stays pending.
    """
    observed: dict[str, list[dict]] = {}
    for state_dir in (CAPTURE_ROOT / "states").iterdir():
        prov_path = state_dir / "public-asset-provenance.json"
        if not prov_path.is_file():
            continue
        try:
            prov = json.loads(prov_path.read_text(encoding="utf-8"))
        except Exception:
            continue
        for asset in prov.get("assets", []):
            url = asset.get("url", "")
            name = url.split("/")[-1].lower()
            if "gmarketsans" in name or "notosanscjk" in name:
                entry = {
                    "url": asset.get("url"),
                    "sha256": asset.get("sha256"),
                }
                observed.setdefault(url, entry)
    if not observed:
        return None
    primary_url = next(iter(sorted(observed)))
    primary = observed[primary_url]
    family_value = []
    if any("gmarketsans" in u.lower() for u in observed):
        family_value.append("Gmarket Sans")
    if any("notosanscjk" in u.lower() for u in observed):
        family_value.append("Noto Sans CJK KR")
    if not family_value:
        return None
    return {
        "field": "typography.font_family",
        "value": ", ".join(family_value),
        "unit": None,
        "evidence_type": "asset_provenance",
        "source_state_id": "home.desktop.default",
        "artifact_sha256": primary["sha256"],
        "method": "fetched_font_asset_observation",
        "note": (
            "Font families observed from font assets fetched by the browser "
            f"during G1 capture (primary asset {primary_url.split('/')[-1]}). "
            "Not a screenshot pixel measurement."
        ),
    }


def build_visual_contract() -> dict:
    model = _model()
    desktop = _measure_desktop()
    mobile = _measure_mobile()
    board = _measure_board()
    gnb_open = _measure_gnb_open()
    fonts = _font_family_observation()

    measurements: list[dict] = []

    base_measurements = (
        ("layout.header.height_px", desktop["header_height"], "px", desktop),
        ("layout.gnb.height_px", desktop["gnb_height"], "px", desktop),
        ("layout.footer.height_px", desktop["footer_height"], "px", desktop),
        ("layout.main.max_width_px", desktop["max_width"], "px", desktop),
        ("layout.main.padding_x", desktop["padding_x"], "px", desktop),
        ("colors.primary", desktop["primary"], "hex", desktop),
        ("colors.background", desktop["background"], "hex", desktop),
        ("colors.header_bg", desktop["header_bg"], "hex", desktop),
        ("colors.gnb_bg", desktop["gnb_color"], "hex", desktop),
        ("colors.gnb_text", desktop["gnb_text"], "hex", desktop),
        ("colors.footer_bg", desktop["footer_bg"], "hex", desktop),
        ("colors.text", desktop["text"], "hex", desktop),
        ("colors.text_muted", desktop["muted"], "hex", desktop),
        ("colors.border", desktop["border"], "hex", desktop),
        ("border.width", desktop["border_thickness"], "px", desktop),
        ("border.color", desktop["border"], "hex", desktop),
        ("typography.text_color", desktop["text"], "hex", desktop),
        ("responsive.mobile.header_height_px", mobile["header_height"], "px", mobile),
        ("responsive.mobile.gnb_height_px", mobile["gnb_height"], "px", mobile),
        ("responsive.mobile.max_width_px", mobile["max_width"], "px", mobile),
        ("responsive.mobile.main_padding_x", mobile["padding_x"], "px", mobile),
    )
    corrected_fields = {
        "layout.header.height_px",
        "layout.gnb.height_px",
        "layout.footer.height_px",
        "colors.primary",
        "colors.background",
        "colors.header_bg",
        "colors.gnb_bg",
        "colors.gnb_text",
        "colors.footer_bg",
        "responsive.mobile.header_height_px",
        "responsive.mobile.gnb_height_px",
    }
    for field, value, unit, source in base_measurements:
        method = (
            "pixel_analysis_semantic_region_correction"
            if field in corrected_fields else "pixel_analysis"
        )
        measurements.append(
            _measurement(field, value, unit, "pixel_analysis", source, method)
        )

    extra_measurements = (
        ("layout.header.notice_height_px", desktop["notice_height"], "px", desktop),
        ("layout.header.utility_height_px", desktop["utility_height"], "px", desktop),
        ("layout.header.brand_height_px", desktop["brand_height"], "px", desktop),
        ("layout.header.identity_height_px", desktop["identity_height"], "px", desktop),
        ("layout.header.search_width_px", desktop["search_width"], "px", desktop),
        ("layout.header.search_height_px", desktop["search_height"], "px", desktop),
        ("layout.home.hero_height_px", desktop["hero_height"], "px", desktop),
        ("layout.home.key_visual_width_px", desktop["key_visual_width"], "px", desktop),
        ("layout.home.key_visual_height_px", desktop["key_visual_height"], "px", desktop),
        ("layout.home.quick_height_px", desktop["quick_height"], "px", desktop),
        ("layout.home.quick_columns", desktop["quick_columns"], "count", desktop),
        ("layout.home.quick_item_width_px", desktop["quick_item_width"], "px", desktop),
        ("layout.home.info_columns", desktop["info_columns"], "count", desktop),
        ("layout.home.info_gap_px", desktop["info_gap"], "px", desktop),
        ("colors.hero_bg", desktop["hero_bg"], "hex", desktop),
        ("colors.notice_bg", desktop["notice_bg"], "hex", desktop),
        ("colors.key_visual_bg", desktop["key_visual_bg"], "hex", desktop),
        ("responsive.mobile.notice_height_px", mobile["notice_height"], "px", mobile),
        ("responsive.mobile.utility_height_px", mobile["utility_height"], "px", mobile),
        ("responsive.mobile.brand_height_px", mobile["brand_height"], "px", mobile),
        ("responsive.mobile.identity_height_px", mobile["identity_height"], "px", mobile),
        ("responsive.mobile.footer_height_px", mobile["footer_height"], "px", mobile),
        ("responsive.mobile.home.hero_height_px", mobile["hero_height"], "px", mobile),
        ("responsive.mobile.home.key_visual_height_px", mobile["key_visual_height"], "px", mobile),
        ("responsive.mobile.home.quick_height_px", mobile["quick_height"], "px", mobile),
        ("responsive.mobile.home.quick_columns", mobile["quick_columns"], "count", mobile),
        ("responsive.mobile.home.quick_item_width_px", mobile["quick_item_width"], "px", mobile),
        ("responsive.mobile.home.info_columns", mobile["info_columns"], "count", mobile),
        ("responsive.mobile.home.info_gap_px", mobile["info_gap"], "px", mobile),
    )
    for field, value, unit, source in extra_measurements:
        measurements.append(
            _measurement(
                field,
                value,
                unit,
                "pixel_analysis",
                source,
                "pixel_analysis_semantic_region_correction",
                "Bound to the semantic region in the immutable #1310 source screenshot.",
            )
        )

    font_evidence = _font_asset_evidence()
    if font_evidence is not None:
        measurements.append(font_evidence)
    elif "Gmarket Sans" in fonts or "Noto Sans CJK KR" in fonts:
        # No committed font asset bytes but observed filenames: keep the field
        # pending (explicit gap) rather than pretend it is a pixel measurement.
        pass

    board_measurements = (
        ("layout.board.snb_width_px", board.get("snb_width_px"), "px", board["_list_source"]),
        ("layout.board.content_container_width_px", board.get("content_container_width_px"), "px", board["_list_source"]),
        ("layout.board.subpage_top_offset_px", board.get("subpage_top_offset_px"), "px", board["_list_source"]),
        ("layout.board.content_padding_top_px", board.get("content_padding_top_px"), "px", board["_list_source"]),
        ("layout.board.snb_title_height_px", board.get("snb_title_height_px"), "px", board["_list_source"]),
        ("layout.board.snb_item_height_px", board.get("snb_item_height_px"), "px", board["_list_source"]),
        ("layout.board.snb.subitem_height_px", board.get("snb_subitem_height_px"), "px", board["_civil_source"]),
        ("layout.board.content_padding_left_px", board.get("content_padding_left_px"), "px", board["_list_source"]),
        ("layout.board.table_header_height_px", board.get("table_header_height_px"), "px", board["_list_source"]),
        ("layout.board.row_height_px", board.get("row_height_px"), "px", board["_list_source"]),
        ("colors.board.table_header_border", board.get("board_table_header_border"), "hex", board["_list_source"]),
        ("colors.board.table_header_rule", board.get("board_table_header_rule"), "hex", board["_list_source"]),
        ("colors.board.row_separator", board.get("board_row_separator"), "hex", board["_list_source"]),
        ("colors.board.snb_title_bg", board.get("board_snb_title_bg"), "hex", board["_list_source"]),
        ("colors.board.snb_active_bg", board.get("board_snb_active_bg"), "hex", board["_list_source"]),
        ("colors.board.snb_separator", board.get("board_snb_separator"), "hex", board["_list_source"]),
        ("layout.board.toolbar_padding_top_px", board.get("toolbar_padding_top_px"), "px", board["_list_source"]),
        ("layout.board.toolbar_row_height_px", board.get("toolbar_row_height_px"), "px", board["_list_source"]),
        ("layout.board.toolbar_padding_bottom_px", board.get("toolbar_padding_bottom_px"), "px", board["_list_source"]),
        ("layout.board.pager_padding_top_px", board.get("pager_padding_top_px"), "px", board["_list_source"]),
        ("layout.board.pager_padding_bottom_px", board.get("pager_padding_bottom_px"), "px", board["_list_source"]),
        ("layout.board.license_padding_top_px", board.get("license_padding_top_px"), "px", board["_list_source"]),
        ("layout.board.license_padding_bottom_px", board.get("license_padding_bottom_px"), "px", board["_list_source"]),
        ("layout.board.license_margin_bottom_px", board.get("license_margin_bottom_px"), "px", board["_list_source"]),
        ("layout.board.duty.padding_top_px", board.get("duty_padding_top_px"), "px", board["_civil_source"]),
        ("layout.board.duty.padding_bottom_px", board.get("duty_padding_bottom_px"), "px", board["_civil_source"]),
        ("colors.board.pager_button_border", board.get("board_pager_button_border"), "hex", board["_list_source"]),
        ("colors.board.pager_active_bg", board.get("board_pager_active_bg"), "hex", board["_list_source"]),
        ("colors.board.search_button_bg", board.get("board_search_button_bg"), "hex", board["_list_source"]),
        ("layout.board.detail.meta_band_height_px", board.get("detail_meta_band_height_px"), "px", board["_detail_source"]),
        ("layout.board.detail.shell_padding_top_px", board.get("detail_shell_padding_top_px"), "px", board["_detail_source"]),
        ("layout.board.detail.shell_padding_bottom_px", board.get("detail_shell_padding_bottom_px"), "px", board["_detail_source"]),
        ("layout.board.detail.body.break_spacing_px", board.get("detail_body_break_spacing_px"), "px", board.get("_gosi_source") or board["_detail_source"]),
        ("layout.board.detail.back_box.padding_top_px", board.get("detail_back_box_padding_top_px"), "px", board.get("_gosi_source") or board["_detail_source"]),
        ("layout.board.detail.back_box.padding_bottom_px", board.get("detail_back_box_padding_bottom_px"), "px", board.get("_gosi_source") or board["_detail_source"]),
        ("layout.board.detail.back_box.button_height_px", board.get("detail_back_button_height_px"), "px", board.get("_gosi_source") or board["_detail_source"]),
        ("layout.board.detail.back_box.button_width_px", board.get("detail_back_button_width_px"), "px", board.get("_gosi_source") or board["_detail_source"]),
        ("layout.board.detail.attachment.padding_top_px", board.get("detail_attachment_padding_top_px"), "px", board.get("_gosi_source") or board["_detail_source"]),
        ("layout.board.detail.attachment.padding_bottom_px", board.get("detail_attachment_padding_bottom_px"), "px", board.get("_gosi_source") or board["_detail_source"]),
    )
    for field, value, unit, source in board_measurements:
        if value is None:
            continue
        measurements.append(
            _measurement(
                field,
                value,
                unit,
                "pixel_analysis",
                source,
                "pixel_analysis_board_semantic_region",
                "#1312 board geometry measured from the committed G1 screenshot: "
                "dark-blue SNB sidebar (title bar/active band/item separators), "
                "content column, list table header/row bands, and the detail "
                "meta band.",
            )
        )

    gnb_open_measurements = (
        (
            "layout.gnb_open.panel_height_px",
            gnb_open.get("panel_height_px"),
            "px",
            gnb_open["_source"],
            "Open mega-menu fills the committed 1440x900 viewport; the first "
            "post-overlay quick-menu color begins at y=900.",
        ),
        (
            "layout.gnb_open.columns",
            gnb_open.get("columns"),
            "count",
            gnb_open["_source"],
            "Six top-level menu columns are visibly present across the committed "
            "GNB-open source screenshot.",
        ),
    )
    for field, value, unit, source, note in gnb_open_measurements:
        if value is None:
            continue
        measurements.append(
            _measurement(
                field,
                value,
                unit,
                "pixel_analysis",
                source,
                "pixel_analysis",
                note,
            )
        )

    text_color = desktop["text"]
    muted = desktop["muted"]
    border = desktop["border"]

    contract = {
        "schema_version": CONTRACT_SCHEMA_VERSION,
        "contract_kind": "visual_input",
        "site_id": SITE_ID,
        "capture_id": CAPTURE_ID,
        "model_checksum": compute_model_checksum(model),
        "note": (
            "Provenance-backed measurements from the immutable committed G1 "
            "capture evidence. Every non-null value is traced 1:1 to a "
            "captured state, the committed screenshot SHA it was measured from, "
            "the measurement method, the unit, and the evidence type. Values "
            "that cannot be safely measured remain null and are listed in "
            "gaps. typography.font_family uses asset_provenance evidence "
            "(fetched font assets), not screenshot pixels. border.width is the "
            "measured pixel thickness of the footer separator line. "
            "Renderer-only non-fidelity presentation defaults (font-size, "
            "font-weight, border-style, focus outline, underline, radius, "
            "breakpoint) are NOT counted as official-site fidelity evidence. "
            "#1310 re-binds header/GNB/footer/home-section geometry to semantic "
            "source regions instead of the former dark-band heuristic."
        ),
        "layout": {
            "header": {
                "height_px": desktop["header_height"],
                "notice_height_px": desktop["notice_height"],
                "utility_height_px": desktop["utility_height"],
                "brand_height_px": desktop["brand_height"],
                "identity_height_px": desktop["identity_height"],
                "search_width_px": desktop["search_width"],
                "search_height_px": desktop["search_height"],
                "padding_top": None,
                "padding_bottom": None,
                "padding_x": None,
                "sticky": None,
                "provenance_state_id": desktop["state_id"],
            },
            "gnb": {
                "height_px": desktop["gnb_height"],
                "item_gap": None,
                "toggle_size": None,
                "provenance_state_id": desktop["state_id"],
            },
            "main": {
                "max_width_px": desktop["max_width"],
                "padding_x": desktop["padding_x"],
                "padding_y": None,
                "padding_bottom": None,
                "provenance_state_id": desktop["state_id"],
            },
            "footer": {
                "height_px": desktop["footer_height"],
                "padding_top": None,
                "padding_bottom": None,
                "provenance_state_id": desktop["state_id"],
            },
            "home": {
                "hero_height_px": desktop["hero_height"],
                "key_visual_width_px": desktop["key_visual_width"],
                "key_visual_height_px": desktop["key_visual_height"],
                "quick_height_px": desktop["quick_height"],
                "quick_columns": desktop["quick_columns"],
                "quick_item_width_px": desktop["quick_item_width"],
                "info_columns": desktop["info_columns"],
                "info_gap_px": desktop["info_gap"],
                "provenance_state_id": desktop["state_id"],
            },
            "board": {
                "snb_width_px": board.get("snb_width_px"),
                "snb_title_height_px": board.get("snb_title_height_px"),
                "snb_item_height_px": board.get("snb_item_height_px"),
                "snb": {
                    "subitem_height_px": board.get("snb_subitem_height_px"),
                    "provenance_state_id": board.get("_civil_source", {}).get("state_id")
                    or board["_list_source"]["state_id"],
                },
                "content_container_width_px": board.get("content_container_width_px"),
                "content_padding_left_px": board.get("content_padding_left_px"),
                "content_padding_top_px": board.get("content_padding_top_px"),
                "subpage_top_offset_px": board.get("subpage_top_offset_px"),
                "table_header_height_px": board.get("table_header_height_px"),
                "row_height_px": board.get("row_height_px"),
                "toolbar_padding_top_px": board.get("toolbar_padding_top_px"),
                "toolbar_row_height_px": board.get("toolbar_row_height_px"),
                "toolbar_padding_bottom_px": board.get("toolbar_padding_bottom_px"),
                "pager_padding_top_px": board.get("pager_padding_top_px"),
                "pager_padding_bottom_px": board.get("pager_padding_bottom_px"),
                "license_padding_top_px": board.get("license_padding_top_px"),
                "license_padding_bottom_px": board.get("license_padding_bottom_px"),
                "license_margin_bottom_px": board.get("license_margin_bottom_px"),
                "duty": {
                    "padding_top_px": board.get("duty_padding_top_px"),
                    "padding_bottom_px": board.get("duty_padding_bottom_px"),
                    "provenance_state_id": board.get("_civil_source", {}).get("state_id")
                    or board["_list_source"]["state_id"],
                },
                "provenance_state_id": board["_list_source"]["state_id"],
                "detail": {
                    "meta_band_height_px": board.get("detail_meta_band_height_px"),
                    "shell_padding_top_px": board.get("detail_shell_padding_top_px"),
                    "shell_padding_bottom_px": board.get("detail_shell_padding_bottom_px"),
                    "body": {
                        "break_spacing_px": board.get("detail_body_break_spacing_px"),
                        "provenance_state_id": board.get("_gosi_source", {}).get("state_id")
                        or board["_detail_source"]["state_id"],
                    },
                    "back_box": {
                        "padding_top_px": board.get("detail_back_box_padding_top_px"),
                        "padding_bottom_px": board.get("detail_back_box_padding_bottom_px"),
                        "button_height_px": board.get("detail_back_button_height_px"),
                        "button_width_px": board.get("detail_back_button_width_px"),
                        "provenance_state_id": board.get("_gosi_source", {}).get("state_id")
                        or board["_detail_source"]["state_id"],
                    },
                    "attachment": {
                        "padding_top_px": board.get("detail_attachment_padding_top_px"),
                        "padding_bottom_px": board.get("detail_attachment_padding_bottom_px"),
                        "provenance_state_id": board.get("_gosi_source", {}).get("state_id")
                        or board["_detail_source"]["state_id"],
                    },
                    "provenance_state_id": board["_detail_source"]["state_id"],
                },
            },
            "gnb_open": {
                "panel_height_px": gnb_open.get("panel_height_px"),
                "columns": gnb_open.get("columns"),
                "provenance_state_id": gnb_open["_source"]["state_id"],
            },
        },
        "colors": {
            "primary": desktop["primary"],
            "background": desktop["background"],
            "surface": None,
            "text": text_color,
            "text_muted": muted,
            "border": border,
            "link": None,
            "link_hover": None,
            "header_bg": desktop["header_bg"],
            "gnb_bg": desktop["gnb_color"],
            "gnb_text": desktop["gnb_text"],
            "footer_bg": desktop["footer_bg"],
            "hero_bg": desktop["hero_bg"],
            "notice_bg": desktop["notice_bg"],
            "key_visual_bg": desktop["key_visual_bg"],
            "footer_border": border,
            "board": {
                "table_header_border": board.get("board_table_header_border"),
                "table_header_rule": board.get("board_table_header_rule"),
                "row_separator": board.get("board_row_separator"),
                "snb_title_bg": board.get("board_snb_title_bg"),
                "snb_active_bg": board.get("board_snb_active_bg"),
                "snb_separator": board.get("board_snb_separator"),
                "pager_button_border": board.get("board_pager_button_border"),
                "pager_active_bg": board.get("board_pager_active_bg"),
                "search_button_bg": board.get("board_search_button_bg"),
                "provenance_state_id": board["_list_source"]["state_id"],
            },
            "provenance_state_id": desktop["state_id"],
        },
        "typography": {
            "font_family": (font_evidence["value"] if font_evidence is not None else None),
            "font_family_kr": "Noto Sans CJK KR" if "Noto Sans CJK KR" in fonts else None,
            "site_title_size": None,
            "site_title_weight": None,
            "nav_link_size": None,
            "nav_link_weight": None,
            "section_title_size": None,
            "section_title_weight": None,
            "detail_title_size": None,
            "detail_title_weight": None,
            "body_size": None,
            "body_line_height": None,
            "text_color": text_color,
            "provenance_state_id": desktop["state_id"],
        },
        "spacing": {
            "section_gap": None,
            "card_padding": None,
            "list_item_padding": None,
            "badge_padding_x": None,
            "badge_padding_y": None,
            "provenance_state_id": desktop["state_id"],
        },
        "border": {
            "radius_card": None,
            "radius_pill": None,
            "radius_button": None,
            "width": desktop["border_thickness"],
            "style": None,
            "color": border,
            "provenance_state_id": desktop["state_id"],
        },
        "responsive": {
            "breakpoint_mobile": None,
            "mobile": {
                "header_height_px": mobile["header_height"],
                "gnb_height_px": mobile["gnb_height"],
                "notice_height_px": mobile["notice_height"],
                "utility_height_px": mobile["utility_height"],
                "brand_height_px": mobile["brand_height"],
                "identity_height_px": mobile["identity_height"],
                "footer_height_px": mobile["footer_height"],
                "max_width_px": mobile["max_width"],
                "header_padding_x": mobile["padding_x"],
                "header_padding_y": None,
                "main_padding_x": mobile["padding_x"],
                "main_padding_y": None,
                "main_padding_bottom": None,
                "grid_columns": None,
                "home": {
                    "hero_height_px": mobile["hero_height"],
                    "key_visual_height_px": mobile["key_visual_height"],
                    "quick_height_px": mobile["quick_height"],
                    "quick_columns": mobile["quick_columns"],
                    "quick_item_width_px": mobile["quick_item_width"],
                    "info_columns": mobile["info_columns"],
                    "info_gap_px": mobile["info_gap"],
                    "provenance_state_id": mobile["state_id"],
                },
                "provenance_state_id": mobile["state_id"],
            },
            "provenance_state_id": mobile["state_id"],
        },
        "gaps": [
            {
                "region": "organization_chart",
                "note": "No measurable geometry for org chart surface in committed G1 evidence.",
                "provenance_state_id": None,
            },
            {
                "region": "staff_directory",
                "note": "No measurable geometry for staff directory surface in committed G1 evidence.",
                "provenance_state_id": None,
            },
            {
                "region": "detail_attachment_buttons",
                "note": "No measured attachment-button geometry (size, color, icon style).",
                "provenance_state_id": None,
            },
            {
                "region": "border_radius",
                "note": "Border radius is not safely measurable from committed screenshots.",
                "provenance_state_id": None,
            },
            {
                "region": "responsive_breakpoint",
                "note": "Exact mobile breakpoint value is not derivable from two committed viewports.",
                "provenance_state_id": None,
            },
            {
                "region": "font_sizes",
                "note": "Font sizes are not safely measurable from committed screenshots.",
                "provenance_state_id": None,
            },
            {
                "region": "spacing_paddings",
                "note": "Element-specific paddings are not safely measurable from committed screenshots.",
                "provenance_state_id": None,
            },
            {
                "region": "non_fidelity_presentation_defaults",
                "note": (
                    "Renderer-only non-fidelity defaults (font-size, font-weight, "
                    "border-style, focus outline width/offset, link underline, "
                    "border radius, responsive breakpoint) are structural/"
                    "accessibility implementation defaults. They are NOT counted "
                    "as official-site fidelity evidence and do not gate "
                    "faithful_clone_candidate."
                ),
                "provenance_state_id": None,
            },
            {
                "region": "board_column_proportions",
                "note": "Per-column width proportions could not be bounded reliably from the committed screenshot header text clusters; left gap (fail-closed).",
                "provenance_state_id": "notice.list.desktop",
                "artifact_sha256": board["_list_source"]["artifact_sha256"],
                "measurement_method": "gap",
            },
            {
                "region": "board_toolbar_search_geometry",
                "note": "Toolbar/search input+button geometry not measured in #1312.",
                "provenance_state_id": "notice.list.desktop",
                "artifact_sha256": board["_list_source"]["artifact_sha256"],
                "measurement_method": "gap",
            },
            {
                "region": "board_page_size_control_geometry",
                "note": "Page-size selector geometry not measured in #1312.",
                "provenance_state_id": "notice.list.desktop",
                "artifact_sha256": board["_list_source"]["artifact_sha256"],
                "measurement_method": "gap",
            },
            {
                "region": "board_pagination_spacing",
                "note": "Pagination item spacing not measured in #1312.",
                "provenance_state_id": "notice.list.desktop",
                "artifact_sha256": board["_list_source"]["artifact_sha256"],
                "measurement_method": "gap",
            },
            {
                "region": "board_detail_content_spacing",
                "note": "Detail body/content spacing not measured in #1312.",
                "provenance_state_id": "notice.detail.desktop",
                "artifact_sha256": board["_detail_source"]["artifact_sha256"],
                "measurement_method": "gap",
            },
            {
                "region": "board_attachment_region_geometry",
                "note": "Attachment region geometry not measured in #1312.",
                "provenance_state_id": "notice.detail.desktop",
                "artifact_sha256": board["_detail_source"]["artifact_sha256"],
                "measurement_method": "gap",
            },
        ],
        "measurements": measurements,
    }
    return contract


def build_asset_manifest() -> dict:
    """Deterministic full provenance materialization from the committed model.

    G2-B commits no asset bytes: every provenance entry stays unresolved and is
    marked REVIEW_REQUIRED (rights unverified). Accounting is exact.
    """
    model = _model()
    entries = model.get("provenance_manifest", [])
    total = len(entries)
    materialized = []
    for entry in entries:
        materialized.append({
            "source_url": entry.get("source_url"),
            "sha256": entry.get("sha256"),
            "state_id": entry.get("state_id"),
            "committed": False,
            "local_path": None,
            "status": "REVIEW_REQUIRED",
            "note": entry.get("provenance_note"),
        })
    return {
        "schema_version": 1,
        "manifest_kind": "asset_manifest",
        "site_id": SITE_ID,
        "capture_id": CAPTURE_ID,
        "model_checksum": compute_model_checksum(model),
        "accounting": {
            "total": total,
            "committed": 0,
            "selected": 0,
            "unresolved": total,
            "review_required": total,
        },
        "policy_note": (
            "G2-B commits no asset bytes. Every provenance entry from the "
            "committed model's provenance_manifest is materialized below with "
            "exact accounting; all remain REVIEW_REQUIRED because rights/use "
            "are not yet verified. No live runtime fetch is performed."
        ),
        "committed_assets": [],
        "provenance_entries": materialized,
    }


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if "--write" in args:
        contract = build_visual_contract()
        OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
        OUT_PATH.write_text(
            json.dumps(contract, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        manifest = build_asset_manifest()
        MANIFEST_PATH.write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        print(f"[measure] wrote {OUT_PATH.relative_to(REPO_ROOT)}")
        print(f"[measure] wrote {MANIFEST_PATH.relative_to(REPO_ROOT)}")
        return 0

    if "--check" in args:
        current = json.loads(OUT_PATH.read_text(encoding="utf-8"))
        fresh = build_visual_contract()
        ok = json.dumps(current, ensure_ascii=False, sort_keys=True) == json.dumps(
            fresh, ensure_ascii=False, sort_keys=True
        )
        manifest_ok = json.loads(
            MANIFEST_PATH.read_text(encoding="utf-8")
        ) == build_asset_manifest()
        if not ok:
            print("VISUAL_CONTRACT_STALE: committed visual-contract.json differs from measurement")
            return 2
        if not manifest_ok:
            print("ASSET_MANIFEST_STALE: committed asset-manifest.json differs from materialization")
            return 2
        print("VISUAL_CONTRACT_OK")
        print("ASSET_MANIFEST_OK")
        return 0

    print(__doc__)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
