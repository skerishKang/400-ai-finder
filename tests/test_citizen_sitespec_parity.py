"""#1225-D3 — citizen SiteSpec display identity projection parity contract.

Pure stdlib + pytest only. No network, no provider, no Firecrawl.

The browser citizen UI must reference the current institution using the
canonical SiteSpec display identity:

* ko   -> ``북구청``        (``display.default_label``)
* en   -> ``Gwangju Buk-gu`` (``display.locale_labels.en``)
* vi/th/id -> ``Gwangju Buk-gu`` (approved English label fallback; no
  invented translations exist for these locales)

The checked-in browser projection ``src/web/static/citizen-sitespec-metadata.js``
must stay in exact parity with ``configs/sites/bukgu_gwangju.sitespec.json``.
If the SiteSpec changes without updating the projection (or the citizen-i18n
strings that consume it), this test fails CI.

Brand copy (``BUKGU AI CIVIC NAVIGATOR``) is a product/brand token and is
intentionally preserved; it is never used as the institution identity.
"""

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STATIC = ROOT / "src" / "web" / "static"

SITESPEC_PATH = ROOT / "configs" / "sites" / "bukgu_gwangju.sitespec.json"
PROJECTION_PATH = STATIC / "citizen-sitespec-metadata.js"
I18N_PATH = STATIC / "citizen-i18n.js"
HTML_PATH = STATIC / "citizen-action-demo.html"

CANONICAL_ID = "bukgu_gwangju"
SCHEMA_VERSION = "1.0.0"
DEFAULT_LABEL = "북구청"
EN_LABEL = "Gwangju Buk-gu"
SUPPORTED = ("ko", "en", "vi", "th", "id")


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _load_sitespec() -> dict:
    with open(SITESPEC_PATH, "r", encoding="utf-8") as fh:
        return json.load(fh)


def _extract_section(text: str, start_marker: str, end_marker: str) -> str:
    start = text.index(start_marker) + len(start_marker)
    end = text.index(end_marker, start)
    return text[start:end]


def _value_in(section: str, key: str) -> str | None:
    m = re.search(r"\b" + re.escape(key) + r'\s*:\s*"([^"]*)"', section)
    return m.group(1) if m else None


def _projection_values() -> dict:
    js = _read(PROJECTION_PATH)
    metadata = _extract_section(
        js, "window.CitizenSiteSpecMetadata = Object.freeze({", "});"
    )
    labels = _extract_section(js, "locale_labels: Object.freeze({", "names:")
    names_section = _extract_section(js, "names: Object.freeze({", "\n    }),")
    return {
        "site_id": _value_in(metadata, "site_id"),
        "schema_version": _value_in(metadata, "schema_version"),
        "default_label": _value_in(js, "default_label"),
        "locale_ko": _value_in(labels, "ko"),
        "locale_en": _value_in(labels, "en"),
        "name_ko": _value_in(names_section, "ko"),
        "name_en": _value_in(names_section, "en"),
        "name_vi": _value_in(names_section, "vi"),
        "name_th": _value_in(names_section, "th"),
        "name_id": _value_in(names_section, "id"),
    }


# ---------------------------------------------------------------------------
# A. SiteSpec ↔ browser projection exact parity
# ---------------------------------------------------------------------------


def test_projection_identity_parity():
    spec = _load_sitespec()
    proj = _projection_values()
    assert proj["site_id"] == spec["site_id"] == CANONICAL_ID
    assert proj["schema_version"] == spec["schema_version"] == SCHEMA_VERSION


def test_projection_display_default_label_parity():
    spec = _load_sitespec()
    proj = _projection_values()
    assert proj["default_label"] == spec["display"]["default_label"] == DEFAULT_LABEL


def test_projection_locale_labels_parity():
    spec = _load_sitespec()
    proj = _projection_values()
    spec_labels = spec["display"]["locale_labels"]
    # The projection must mirror the exact SiteSpec locale label set.
    assert set(spec_labels) == {"ko", "en"}
    assert proj["locale_ko"] == spec_labels["ko"] == DEFAULT_LABEL
    assert proj["locale_en"] == spec_labels["en"] == EN_LABEL


def test_projection_derived_names_parity():
    proj = _projection_values()
    # ko uses display.default_label; en uses display.locale_labels.en.
    assert proj["name_ko"] == DEFAULT_LABEL
    assert proj["name_en"] == EN_LABEL


def test_no_invented_vi_th_id_institution_translation():
    """vi/th/id have no SiteSpec locale institution label; the projection
    must deterministically use the approved English label — never a newly
    invented local translation."""
    spec = _load_sitespec()
    en_label = spec["display"]["locale_labels"]["en"]
    assert en_label == EN_LABEL
    proj = _projection_values()
    for loc in ("vi", "th", "id"):
        assert proj[f"name_{loc}"] == en_label, (
            f"name_{loc} must fall back to the approved English label"
        )
    # No locale-specific label exists for vi/th/id in the SiteSpec.
    assert "vi" not in spec["display"]["locale_labels"]
    assert "th" not in spec["display"]["locale_labels"]
    assert "id" not in spec["display"]["locale_labels"]


# ---------------------------------------------------------------------------
# B. citizen-i18n consumes the projected identity
# ---------------------------------------------------------------------------


def test_i18n_uses_projected_institution_name():
    """Official-identity UI strings carry the {institution} token and are
    substituted synchronously from the SiteSpec projection (#1378). The
    tokenized form replaces the former hardcoded 'Gwangju Buk-gu' literals;
    substitution is byte-identical for the Buk-gu projection (en label
    'Gwangju Buk-gu'). The stale 'Bukgu-gu' form remains forbidden."""
    i18n = _read(I18N_PATH)
    expected_tokenized_en_strings = [
        "After your first question, I will show the route together with the {institution} guide screen.",
        "Please complete the official submission directly through {institution}'s official channels.",
        "I have your question. The {institution} guide screen is now open on the left.",
        "The {institution} guide screen stays open on the left.",
        "Guiding you along the route on the {institution} screen.",
        "{institution} official snapshot",
    ]
    for s in expected_tokenized_en_strings:
        assert s in i18n, f"missing tokenized institution string: {s!r}"
    # Substitution contract: t() must run values through the SiteSpec
    # identity projection.
    assert "_withInstitution" in i18n
    assert "getInstitutionName(locale)" in i18n


def test_i18n_has_no_stale_bukgu_gu_institution_references():
    i18n = _read(I18N_PATH)
    stale = [
        "The Bukgu-gu guide screen",
        "Bukgu-gu's official channels",
        "Bukgu-gu official snapshot",
        "on the Bukgu-gu screen",
        "the Bukgu-gu website",
        "the Bukgu-gu civil office",
        "Bukgu-gu offices and welfare centers",
        "to the Bukgu-gu site",
        "the Bukgu-gu menu",
        "through Bukgu-gu's official channels",
    ]
    for s in stale:
        assert s not in i18n, f"stale institution reference remains: {s!r}"


def test_i18n_brand_copy_preserved():
    """BUKGU AI CIVIC NAVIGATOR is a brand token, not the institution
    identity. It is preserved exactly once per non-Korean locale."""
    i18n = _read(I18N_PATH)
    assert i18n.count("BUKGU AI CIVIC NAVIGATOR") == 4
    # Brand token never appears as the standalone institution identity in
    # the official-identity keys (it stays inside the chat.welcome brand line).
    assert "BUKGU AI CIVIC NAVIGATOR guide screen" not in i18n


def test_i18n_menu_name_exception_preserved():
    """The '북구소개' website-menu-name translation (th) legitimately keeps
    the menu's own name 'Bukgu-gu' — it is a navigation label, not the
    current institution identity."""
    i18n = _read(I18N_PATH)
    assert "ก่อนอื่น เปิดเมนูแนะนำ Bukgu-gu" in i18n


def test_i18n_exposes_get_institution_name():
    i18n = _read(I18N_PATH)
    assert "function getInstitutionName(" in i18n
    assert "SITE_METADATA" in i18n
    assert "getInstitutionName: getInstitutionName" in i18n
    # Synchronous/offline: the projection is read at load time.
    assert "window.CitizenSiteSpecMetadata" in i18n
    assert "fetch(" not in i18n
    assert "XMLHttpRequest" not in i18n


def test_historical_alias_not_current_identity():
    """The historical jurisdiction alias 광주광역시 북구 and the canonical
    jurisdiction name must not appear as the current institution identity in
    the citizen UI. The UI references the SiteSpec display labels only."""
    i18n = _read(I18N_PATH)
    assert "광주광역시 북구" not in i18n
    assert "전남광주통합특별시" not in i18n


# ---------------------------------------------------------------------------
# C. Script load ordering (projection before citizen-i18n)
# ---------------------------------------------------------------------------


def test_projection_script_loads_before_i18n():
    html = _read(HTML_PATH)
    assert "citizen-sitespec-metadata.js" in html
    assert html.index("citizen-sitespec-metadata.js") < html.index("citizen-i18n.js")


# ---------------------------------------------------------------------------
# D. Locale policy surface for all five locales
# ---------------------------------------------------------------------------


def test_institution_name_policy_for_all_locales():
    proj = _projection_values()
    policy = {
        "ko": DEFAULT_LABEL,
        "en": EN_LABEL,
        "vi": EN_LABEL,
        "th": EN_LABEL,
        "id": EN_LABEL,
    }
    for loc in SUPPORTED:
        assert proj[f"name_{loc}"] == policy[loc], loc
