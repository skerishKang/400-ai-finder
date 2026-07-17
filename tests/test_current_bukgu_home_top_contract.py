"""#1170: home top contracts — fixture-driven home replaces #868 synthetic top."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STATIC = ROOT / "src" / "web" / "static"
JS = (STATIC / "citizen-action-demo-canvas.js").read_text(encoding="utf-8")
CSS = (STATIC / "citizen-action-demo-canvas.css").read_text(encoding="utf-8")
FIXTURE_JS = (STATIC / "bukgu-home-clone-fixture.js").read_text(encoding="utf-8")
HTML = (STATIC / "citizen-action-demo.html").read_text(encoding="utf-8")


def _approved_home_block() -> str:
    start = JS.index("  function _renderApprovedHome(")
    end = JS.index("  // CLONE_APPROVED_HOME_RENDERER_END", start)
    return JS[start:end]


def _home_dispatch_block() -> str:
    start = JS.index("  function _renderHome(")
    candidates = [
        "\n  // -----------------------------------------------------------------------\n  // _renderCivilService",
        "\n  function _renderCivilService",
    ]
    end = len(JS)
    for c in candidates:
        idx = JS.find(c, start + 50)
        if idx != -1 and idx < end:
            end = idx
    return JS[start:end]


def test_resident_default_home_uses_approved_designed_composition():
    """#1197/#1198: gate selects approved design; fixture remains opt-in."""
    dispatch = _home_dispatch_block()
    assert "_resolveHomeRendererSelection" in dispatch
    assert "_renderApprovedHome" in dispatch
    assert "approved_default" in dispatch
    home = _approved_home_block()
    assert "home-mayor-card.png" in home
    assert "home-alert-banner.png" in home
    assert "bg-home-quick-link" in home
    assert "bukgu_home.png" not in home
    assert "function _renderHomeFixtureProjection" in JS
    assert "data-home-fixture-sha256" in JS
    assert "data-home-region-id" in JS
    assert "__BUKGU_HOME_CLONE_FIXTURE__" in JS


def test_fixture_projection_function_still_available():
    assert "function _renderHomeFixtureProjection" in JS
    assert "home-fixture" in JS
    assert "home-projection" in JS


def test_projection_script_loads_before_canvas():
    assert "bukgu-home-clone-fixture.js" in HTML
    assert HTML.index("bukgu-home-clone-fixture.js") < HTML.index(
        "citizen-action-demo-canvas.js"
    )


def test_projection_contains_canonical_regions_and_sha():
    assert "81b27b98fadc091ca852079f89ea93da45b93f250372835b8b352726b2faeaed" in FIXTURE_JS
    for rid in [
        "utility_navigation",
        "main_banner",
        "resident_service_shortcuts",
        "notice_news",
        "related_site_controls",
        "footer_identity_contact",
    ]:
        assert rid in FIXTURE_JS


def test_fixture_css_is_scoped_to_home_root():
    assert ".bg-page--home .bg-home-fixture-root" in CSS
    assert ".bg-page--home .bg-home-fixture-region" in CSS
    assert ".bg-page--home .bg-home-fixture-item--hidden" in CSS
    assert "body {" not in CSS[CSS.index(".bg-home-fixture-root") : CSS.index(".bg-home-fixture-root") + 400]


def test_page_agent_home_targets_have_exact_mapping_evidence():
    for target in [
        "nav-civil-service",
        "nav-complaint-board",
        "nav-apartment-dept",
        "nav-passport-guidance",
        "nav-bulky-waste-disposal",
        "mayor-office-open",
    ]:
        assert target in FIXTURE_JS
        assert target in JS
