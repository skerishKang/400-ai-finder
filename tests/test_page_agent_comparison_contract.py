"""Offline contract tests for the #1109 Page Agent comparison track.

These tests lock:

  * the resident-facing Page Agent demo route (``examples/page-agent/resident/``);
  * #1068 product surfaces:
      - ``/`` and ``/mvp/`` = citizen assistant (discovery-free)
      - ``/internal/`` = operator/developer discovery boundary
  * route isolation between the Page Agent group and the MVP/mobile/admin
    surfaces;
  * the shared parity scenario contract (``parity-contract.json``);
  * the no-submit boundary;
  * Stage 2: resident interactive demo assets (mock model, bootstrap, layout).

No network, no live model, no CDN, no provider/Firecrawl/official-site call.
All builds run in-process against a temp output directory (matches the
existing ``test_build_cloudflare_pages.py`` pattern) so the harness stays
offline and hermetic.
"""

from __future__ import annotations

import importlib.util
import json
import os
import re
import tempfile

import pytest

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
_BUILD_MODULE_PATH = os.path.join(_REPO_ROOT, "scripts", "build_cloudflare_pages.py")
_EXAMPLES_DIR = os.path.join(_REPO_ROOT, "src", "web", "examples", "page-agent")
_PARITY_CONTRACT = os.path.join(_EXAMPLES_DIR, "parity-contract.json")
_RESIDENT_INDEX = os.path.join(_EXAMPLES_DIR, "resident", "index.html")

# Resident demo route (primary Page Agent product card on the *internal* index).
# From /internal/ the link is one level up.
INTERNAL_RESIDENT_HREF = "../examples/page-agent/resident/"
# Developer lab route (demoted note link on the internal index).
INTERNAL_DEV_LAB_HREF = "../examples/page-agent/"
# Build-output absolute-from-site-root path still used by artifact presence checks.
RESIDENT_ROUTE = "examples/page-agent/resident/"
DEV_LAB_ROUTE = "examples/page-agent/"

# Page Agent runtime/content signatures that must NEVER leak into the MVP,
# mobile, admin, root landing, or internal discovery surfaces.  The resident
# route IS expected to load some of these (the vendored runtime and its
# resident mock model).
PAGE_AGENT_RUNTIME_SIGNATURES = [
    "./vendor/page-agent.iife.js",
    "./mock-model.js",
    "./page-agent-lab.js",
    "./page-agent-lab.css",
    "new window.PageAgent(",
    "PageAgentLabMockModel",
    "what-is-page-agent",
    "Page Agent 1.12.1",
]

# Discovery signatures that must not appear on the citizen root /mvp entry.
PAGE_AGENT_DISCOVERY_SIGNATURES = [
    "Page Agent형 AI 북구청",
    "Page Agent 개발자 실험실",
    'href="examples/page-agent/"',
    'href="examples/page-agent/resident/"',
    'href="../examples/page-agent/"',
    'href="../examples/page-agent/resident/"',
]

# Stage 2 assets expected in the resident interactive demo directory.
_RESIDENT_MOCK_MODEL = os.path.join(_EXAMPLES_DIR, "resident", "resident-mock-model.js")
_RESIDENT_DEMO_JS = os.path.join(_EXAMPLES_DIR, "resident", "resident-demo.js")
_RESIDENT_DEMO_CSS = os.path.join(_EXAMPLES_DIR, "resident", "resident-demo.css")
# Canonical five-scenario vocabulary owner (Stage 4+ architecture).
_RESIDENT_PARITY_SCENARIOS = os.path.join(
    _EXAMPLES_DIR, "resident", "parity-scenarios.js"
)

_SCRIPT_SRC_RE = re.compile(r"<script[^>]+src=[\"']https?://", re.IGNORECASE)
_LINK_HREF_RE = re.compile(r"<link[^>]+href=[\"']https?://", re.IGNORECASE)
_FETCH_HTTP_RE = re.compile(r"fetch\(\s*[\"']https?://", re.IGNORECASE)
_CSS_URL_HTTP_RE = re.compile(r"url\(\s*[\"']?https?://", re.IGNORECASE)
# Scenario entries in parity-scenarios.js (canonical owner).
_PARITY_SCENARIO_ID_RE = re.compile(r"^\s*id:\s*'([^']+)'", re.MULTILINE)
_PARITY_ROUTE_ID_RE = re.compile(r"routeId:\s*'([^']+)'")


def _load_build_module():
    spec = importlib.util.spec_from_file_location("build_cloudflare_pages", _BUILD_MODULE_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture()
def build_dir():
    mod = _load_build_module()
    with tempfile.TemporaryDirectory() as tmp:
        out = os.path.join(tmp, "out")
        mod.build(out_dir=out)
        yield out


@pytest.fixture()
def live_build_dir():
    mod = _load_build_module()
    with tempfile.TemporaryDirectory() as tmp:
        out = os.path.join(tmp, "cloudflare-pages-live")
        mod.build(out_dir=out, mode="live")
        yield out


def _read(path):
    with open(path, encoding="utf-8") as f:
        return f.read()


def _assert_no_external_auto_calls(text, label):
    assert not _SCRIPT_SRC_RE.search(text), f"external <script src> in {label}"
    assert not _LINK_HREF_RE.search(text), f"external <link href> in {label}"
    assert not _FETCH_HTTP_RE.search(text), f"external fetch() in {label}"
    assert not _CSS_URL_HTTP_RE.search(text), f"external url() in {label}"


def _assert_no_runtime_signatures(text, label):
    for sig in PAGE_AGENT_RUNTIME_SIGNATURES:
        assert sig not in text, f"Page Agent runtime signature {sig!r} leaked into {label}"


# ---------------------------------------------------------------------------
# #1068 product surfaces: citizen root vs internal discovery boundary
# ---------------------------------------------------------------------------


def _assert_no_page_agent_discovery(text, label):
    for sig in PAGE_AGENT_DISCOVERY_SIGNATURES:
        assert sig not in text, f"Page Agent discovery signature {sig!r} in {label}"


class TestRootProductLabeling:
    """#1068: citizen root is not a Page Agent discovery gateway.

    Page Agent product cards live on ``/internal/`` only. ``build_index_html``
    is retained as a deprecated alias of the *internal* artifact index.
    """

    def test_static_citizen_root_has_no_page_agent_discovery(self):
        mod = _load_build_module()
        root = mod.build_mvp_entry_html(is_live=False)
        # Resident root opens the citizen assistant shell.
        assert "citizen-first-use-shell.js" in root
        assert "citizen-action-demo-canvas.js" in root
        # Not an artifact chooser / Page Agent discovery page.
        assert "내부 도구" not in root
        _assert_no_page_agent_discovery(root, "static citizen root")
        _assert_no_runtime_signatures(root, "static citizen root")

    def test_live_citizen_root_has_no_page_agent_discovery(self):
        mod = _load_build_module()
        root = mod.build_mvp_entry_html(is_live=True)
        assert "citizen-first-use-shell.js" in root
        assert "내부 도구" not in root
        _assert_no_page_agent_discovery(root, "live citizen root")
        _assert_no_runtime_signatures(root, "live citizen root")

    def test_static_internal_primary_page_agent_card(self):
        mod = _load_build_module()
        # build_index_html is the internal discovery boundary (#1068).
        internal = mod.build_index_html([], is_live=False)
        assert "내부 도구" in internal
        assert "Page Agent형 AI 북구청" in internal
        assert internal.count(f'href="{INTERNAL_RESIDENT_HREF}"') == 1
        # Primary card, same-document relative, no forced tab.
        block = internal[internal.index(f'<a class="card" href="{INTERNAL_RESIDENT_HREF}"'):]
        block = block[: block.index("</a>")]
        assert 'target="_blank"' not in block

    def test_live_internal_primary_page_agent_card(self):
        mod = _load_build_module()
        internal = mod.build_index_html([], is_live=True)
        assert "Page Agent형 AI 북구청" in internal
        assert internal.count(f'href="{INTERNAL_RESIDENT_HREF}"') == 1

    def test_developer_lab_demoted_on_internal_not_primary(self):
        mod = _load_build_module()
        for is_live in (False, True):
            internal = mod.build_index_html([], is_live=is_live)
            # Demoted developer lab label + exactly one internal link to the lab.
            assert "Page Agent 개발자 실험실" in internal
            assert internal.count(f'href="{INTERNAL_DEV_LAB_HREF}"') == 1
            # The old primary product label is gone.
            assert "Page Agent 실험실" not in internal
            # Developer lab is NOT a primary .card.
            assert f'<a class="card" href="{INTERNAL_DEV_LAB_HREF}"' not in internal

    def test_internal_mvp_mobile_admin_cards_preserved(self):
        mod = _load_build_module()
        internal = mod.build_index_html([], is_live=False)
        # Compatibility MVP card stays relative-path (one level up), no query.
        assert 'href="../mvp/"' in internal
        assert "mvp=1" not in internal
        assert "시민 AI 안내" in internal
        assert 'href="../mobile.html"' in internal
        assert 'href="../admin.html"' in internal

    def test_landing_has_no_external_calls(self):
        mod = _load_build_module()
        for is_live in (False, True):
            root = mod.build_mvp_entry_html(is_live=is_live)
            internal = mod.build_index_html([], is_live=is_live)
            _assert_no_external_auto_calls(root, f"citizen-root(is_live={is_live})")
            _assert_no_external_auto_calls(internal, f"internal(is_live={is_live})")

    def test_landing_has_no_page_agent_runtime_leak(self):
        mod = _load_build_module()
        for is_live in (False, True):
            root = mod.build_mvp_entry_html(is_live=is_live)
            internal = mod.build_index_html([], is_live=is_live)
            _assert_no_runtime_signatures(root, f"citizen-root(is_live={is_live})")
            _assert_no_runtime_signatures(internal, f"internal(is_live={is_live})")


# ---------------------------------------------------------------------------
# Shared parity scenario contract
# ---------------------------------------------------------------------------


class TestParityScenarioContract:
    REQUIRED_SCENARIO_FIELDS = {"id", "resident_request", "category", "target", "pass_criteria", "no_submit"}
    EXPECTED_IDS = [
        "apartment_contact",
        "bulky_waste_menu",
        "passport_procedure",
        "complaint_screen",
        "mayor_proposal_writing",
    ]

    def test_parity_contract_file_exists(self):
        assert os.path.isfile(_PARITY_CONTRACT), "parity-contract.json missing"

    def test_parity_contract_valid_json(self):
        data = json.loads(_read(_PARITY_CONTRACT))
        assert data["track"] == "1109-page-agent-comparison"

    def test_parity_contract_has_both_modes(self):
        data = json.loads(_read(_PARITY_CONTRACT))
        modes = data["modes"]
        assert modes["deterministic"]["route"] == "mvp/"
        assert modes["page_agent"]["route"] == RESIDENT_ROUTE

    def test_parity_contract_five_scenarios(self):
        data = json.loads(_read(_PARITY_CONTRACT))
        scenarios = data["scenarios"]
        assert len(scenarios) == 5
        ids = [s["id"] for s in scenarios]
        assert ids == self.EXPECTED_IDS

    @pytest.mark.parametrize("scenario", json.loads(_read(_PARITY_CONTRACT))["scenarios"])
    def test_each_scenario_has_required_fields(self, scenario):
        missing = self.REQUIRED_SCENARIO_FIELDS - set(scenario.keys())
        assert not missing, f"scenario {scenario.get('id')} missing fields: {missing}"
        assert isinstance(scenario["pass_criteria"], list) and scenario["pass_criteria"]
        assert scenario["no_submit"] is True

    def test_parity_contract_no_submit_boundary(self):
        data = json.loads(_read(_PARITY_CONTRACT))
        forbidden = data["no_submit_boundary"]["forbidden_actions"]
        assert any("submission" in a or "제출" in a for a in forbidden)
        assert any("external" in a or "외부" in a for a in forbidden)
        assert any("JavaScript" in a for a in forbidden)


# ---------------------------------------------------------------------------
# Resident route stub isolation
# ---------------------------------------------------------------------------


class TestResidentRouteStub:
    def test_resident_index_exists(self):
        assert os.path.isfile(_RESIDENT_INDEX), "resident route stub missing"

    def test_resident_index_labeled_and_stage2_ready(self):
        html = _read(_RESIDENT_INDEX)
        assert "Page Agent형 AI 북구청" in html
        # Stage 2: the entry loads the vendored Page Agent runtime.
        assert "./vendor/page-agent.iife.js" in html
        # Stage 2: uses the resident Korean mock model, not the developer lab's.
        assert "resident-mock-model.js" in html
        assert "./mock-model.js" not in html
        assert "page-agent-lab.js" not in html
        assert "page-agent-lab.css" not in html
        # Stage 2: resident-demo.js bootstraps the interactive demo.
        assert "resident-demo.js" in html
        assert "resident-demo.css" in html
        # No external network calls.
        _assert_no_external_auto_calls(html, "resident/index.html")

    def test_resident_index_loads_civic_canvas(self):
        html = _read(_RESIDENT_INDEX)
        assert "citizen-action-demo-canvas.js" in html
        assert "citizen-action-demo-map.js" in html
        assert "bukgu-official-snapshots.js" in html
        assert "citizen-action-demo-canvas.css" in html
        assert 'id="demo-canvas"' in html

    def test_resident_index_has_safety_badges(self):
        """Stage 4+ resident badges: plan-mode label + same-origin + no-submit.

        Scope assertions to the dedicated badge region so incidental body copy
        cannot satisfy the contract. Do not require the legacy internal label
        ``오프라인/mock`` as product-facing copy.
        """
        html = _read(_RESIDENT_INDEX)
        assert "chat-header__badges" in html, "resident safety badge region missing"
        region_start = html.index("chat-header__badges")
        region = html[region_start : region_start + 600]

        # Dedicated plan-mode badge (default local mode user-facing label).
        assert 'id="plan-mode-badge"' in region
        assert "badge--offline" in region
        assert "기본 안내" in region

        # Same-origin and no-submit execution boundaries (user-visible + class).
        assert "badge--sameorigin" in region
        assert "동일 출처" in region
        assert "badge--nosubmit" in region
        assert "제출 불가" in region

    def test_resident_index_has_cancel_button(self):
        html = _read(_RESIDENT_INDEX)
        assert 'id="chat-cancel"' in html or "취소" in html

    def test_resident_index_has_no_external_calls(self):
        html = _read(_RESIDENT_INDEX)
        _assert_no_external_auto_calls(html, "resident/index.html")

    def test_resident_mock_model_exists(self):
        assert os.path.isfile(_RESIDENT_MOCK_MODEL), "resident mock model missing"

    def test_resident_mock_model_covers_all_five_scenarios(self):
        """Canonical five-scenario ownership lives in parity-scenarios.js.

        resident-mock-model.js must consume that owner rather than re-owning
        route vocabulary strings. Do not force route IDs back into the mock.
        """
        assert os.path.isfile(_RESIDENT_PARITY_SCENARIOS), (
            "resident parity-scenarios.js missing"
        )
        parity_src = _read(_RESIDENT_PARITY_SCENARIOS)
        mock_src = _read(_RESIDENT_MOCK_MODEL)
        html = _read(_RESIDENT_INDEX)

        # Load order: canonical vocabulary before mock execution layer.
        assert "parity-scenarios.js" in html
        assert "resident-mock-model.js" in html
        assert html.index("parity-scenarios.js") < html.index("resident-mock-model.js")

        # Canonical owner exports frozen scenario table.
        assert "window.PageAgentParityScenarios" in parity_src
        scenario_ids = _PARITY_SCENARIO_ID_RE.findall(parity_src)
        route_ids = _PARITY_ROUTE_ID_RE.findall(parity_src)
        assert len(scenario_ids) == 5, (
            f"expected exactly 5 parity scenario ids, got {scenario_ids!r}"
        )
        assert len(route_ids) == 5, (
            f"expected exactly 5 parity routeIds, got {route_ids!r}"
        )
        assert len(set(scenario_ids)) == 5, f"duplicate scenario ids: {scenario_ids!r}"
        assert len(set(route_ids)) == 5, f"duplicate routeIds: {route_ids!r}"
        assert all(rid.strip() for rid in route_ids), "blank routeId in parity table"

        # Nav step targets (data-action-target sequences) live on the owner.
        # Direct targets (not nav-civil-service) match canvas data-action-target attrs.
        assert "navSteps" in parity_src
        assert "nav-apartment-dept" in parity_src
        assert "nav-bulky-waste-disposal" in parity_src
        assert "nav-passport-guidance" in parity_src
        assert "nav-complaint-board" in parity_src
        assert "complaint-write" in parity_src
        assert "mayor-office-open" in parity_src
        assert "mayor-message-write" in parity_src

        # Mock is the execution layer over the shared owner (no second map).
        assert "window.PageAgentMockModel" in mock_src
        assert "window.PageAgentLabMockModel" in mock_src
        assert "PageAgentParityScenarios" in mock_src
        assert "parity.SCENARIOS" in mock_src or "parity.SCENARIOS ||" in mock_src

        # No route ID used as direct navigation (contract: click DOM, not route jump).
        assert "navigateToRoute" not in mock_src, (
            "contract violation: navigateToRoute forbidden"
        )
        assert "navigateToRoute" not in parity_src, (
            "contract violation: navigateToRoute forbidden in parity owner"
        )

    def test_resident_mock_model_uses_allowed_actions_only(self):
        src = _read(_RESIDENT_MOCK_MODEL)
        # Contract requires: NO arbitrary model-generated JavaScript execution.
        assert "execute_javascript" not in src, "contract violation: execute_javascript forbidden"
        assert "experimentalScriptExecutionTool" not in src, "contract violation: attribute forbidden"
        # Only allowed DOM actions: click_element_by_index, scroll, done.
        assert "click_element_by_index" in src, "must use click DOM action"
        assert "buildToolResponse" in src
        assert "buildStopResponse" in src
        assert "function respond" in src

    def test_resident_mock_model_exposes_diagnostics_api(self):
        src = _read(_RESIDENT_MOCK_MODEL)
        assert "getDiagnostics" in src
        assert "resetDiagnostics" in src
        assert "callCount" in src
        assert "actionNames" in src
        assert "recordDiag" in src

    def test_resident_demo_js_exists(self):
        assert os.path.isfile(_RESIDENT_DEMO_JS), "resident demo JS missing"

    def test_resident_demo_js_wires_agent(self):
        src = _read(_RESIDENT_DEMO_JS)
        assert "new window.PageAgent(" in src
        assert "customFetch" in src
        assert "agent.execute(" in src
        assert "PageAgentMockModel.respond" in src
        assert "agent.panel.hide()" in src
        # Contract: NO experimental script execution tool.
        assert "experimentalScriptExecutionTool" not in src
        # Uses includeAttributes for data-action-target parsing.
        assert "includeAttributes: [" in src
        # Has cancel button and timeout.
        assert "chat-cancel" in src or "stopAgent" in src
        assert "TIMEOUT_MS" in src or "60000" in src
        # Records action history (not execute_javascript regex extraction).
        assert "click_element_by_index" in src

    def test_resident_demo_css_exists(self):
        assert os.path.isfile(_RESIDENT_DEMO_CSS), "resident demo CSS missing"

    def test_resident_demo_css_mobile_layout(self):
        css = _read(_RESIDENT_DEMO_CSS)
        assert "@media (max-width: 768px)" in css, "must have mobile layout breakpoint"
        assert "flex-direction: column" in css, "mobile must stack vertically"
        assert "chat-cancel" in css or "chat-cancel" in open(_RESIDENT_DEMO_CSS).read()
        # Verify canvas selector is correct (no duplicate class/ID selector).
        assert "#demo-canvas" in css
        assert ".resident-canvas #demo-canvas" not in css, "invalid: canvas is not inside .resident-canvas"


# ---------------------------------------------------------------------------
# Build output contracts (in-process, offline)
# ---------------------------------------------------------------------------


class TestBuildOutputContracts:
    def test_build_copies_resident_route(self, build_dir):
        resident = os.path.join(build_dir, "examples", "page-agent", "resident", "index.html")
        assert os.path.isfile(resident), "resident route not copied into build output"

    def test_build_root_is_citizen_entry_not_discovery(self, build_dir):
        index = _read(os.path.join(build_dir, "index.html"))
        # #1068: built root is the citizen assistant, not Page Agent chooser.
        assert "citizen-first-use-shell.js" in index
        assert "내부 도구" not in index
        _assert_no_page_agent_discovery(index, "build index.html")
        # Internal discovery boundary exists with resident + demoted lab links.
        internal = _read(os.path.join(build_dir, "internal", "index.html"))
        assert internal.count(f'href="{INTERNAL_RESIDENT_HREF}"') == 1
        assert internal.count(f'href="{INTERNAL_DEV_LAB_HREF}"') == 1
        assert "Page Agent형 AI 북구청" in internal
        assert "Page Agent 개발자 실험실" in internal
        assert "Page Agent 실험실" not in internal
        # Direct Page Agent artifact routes still exist.
        assert os.path.isfile(
            os.path.join(build_dir, "examples", "page-agent", "resident", "index.html")
        )
        assert os.path.isfile(
            os.path.join(build_dir, "examples", "page-agent", "index.html")
        )

    @pytest.mark.parametrize(
        "route",
        [
            "index.html",
            os.path.join("mvp", "index.html"),
            "mobile.html",
            "admin.html",
            os.path.join("internal", "index.html"),
        ],
    )
    def test_protected_routes_free_of_page_agent_runtime(self, build_dir, route):
        path = os.path.join(build_dir, route)
        if os.path.isfile(path):
            _assert_no_runtime_signatures(_read(path), route)

    @pytest.mark.parametrize(
        "route",
        [
            "index.html",
            os.path.join("mvp", "index.html"),
            "mobile.html",
            "admin.html",
            os.path.join("internal", "index.html"),
        ],
    )
    def test_protected_routes_free_of_external_calls(self, build_dir, route):
        path = os.path.join(build_dir, route)
        if os.path.isfile(path):
            _assert_no_external_auto_calls(_read(path), route)

    def test_live_build_root_and_internal_labeling(self, live_build_dir):
        index = _read(os.path.join(live_build_dir, "index.html"))
        assert "citizen-first-use-shell.js" in index
        _assert_no_page_agent_discovery(index, "live build index.html")
        internal = _read(os.path.join(live_build_dir, "internal", "index.html"))
        assert internal.count(f'href="{INTERNAL_RESIDENT_HREF}"') == 1
        assert internal.count(f'href="{INTERNAL_DEV_LAB_HREF}"') == 1
        assert "Page Agent형 AI 북구청" in internal

    def test_resident_links_resolve_to_existing_build_output_targets(self, build_dir):
        resident = os.path.join(build_dir, "examples", "page-agent", "resident", "index.html")
        html = _read(resident)
        resident_dir = os.path.dirname(resident)
        for href in re.findall(r'<a[^>]+href="([^"]+)"', html):
            if href.startswith(("http://", "https://", "mailto:", "#")):
                continue
            resolved = os.path.normpath(os.path.join(resident_dir, href))
            assert os.path.exists(resolved), (
                f"href {href!r} resolves to {resolved} which does not exist in build output"
            )
