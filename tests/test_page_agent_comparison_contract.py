"""Offline contract tests for the #1109 Stage 1 Page Agent comparison track.

These tests lock:

  * the resident-facing Page Agent demo route (``examples/page-agent/resident/``);
  * product labeling at the root gateway (primary ``Page Agent형 AI 북구청``
    card, demoted developer lab);
  * route isolation between the Page Agent group and the MVP/mobile/admin
    surfaces;
  * the shared parity scenario contract (``parity-contract.json``);
  * the no-submit boundary.

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

# Resident demo route (primary Page Agent product card).
RESIDENT_ROUTE = "examples/page-agent/resident/"
# Developer lab route (demoted, remains exactly one root link).
DEV_LAB_ROUTE = "examples/page-agent/"

# Page Agent runtime/content signatures that must NEVER leak into the MVP,
# mobile, admin, or root landing surfaces.
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

_SCRIPT_SRC_RE = re.compile(r"<script[^>]+src=[\"']https?://", re.IGNORECASE)
_LINK_HREF_RE = re.compile(r"<link[^>]+href=[\"']https?://", re.IGNORECASE)
_FETCH_HTTP_RE = re.compile(r"fetch\(\s*[\"']https?://", re.IGNORECASE)
_CSS_URL_HTTP_RE = re.compile(r"url\(\s*[\"']?https?://", re.IGNORECASE)


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
# Product labeling at the root gateway
# ---------------------------------------------------------------------------


class TestRootProductLabeling:
    def test_static_landing_primary_page_agent_card(self):
        mod = _load_build_module()
        index = mod.build_index_html([], is_live=False)
        # Primary resident card present and links to the resident route.
        assert "Page Agent형 AI 북구청" in index
        assert index.count(f'href="{RESIDENT_ROUTE}"') == 1
        # No external/forced-tab on the primary card.
        block = index[index.index(f'<a class="card" href="{RESIDENT_ROUTE}"'):]
        block = block[: block.index("</a>")]
        assert 'target="_blank"' not in block

    def test_live_landing_primary_page_agent_card(self):
        mod = _load_build_module()
        index = mod.build_index_html([], is_live=True)
        assert "Page Agent형 AI 북구청" in index
        assert index.count(f'href="{RESIDENT_ROUTE}"') == 1

    def test_developer_lab_demoted_not_primary(self):
        mod = _load_build_module()
        for is_live in (False, True):
            index = mod.build_index_html([], is_live=is_live)
            # Demoted developer lab label + exactly one root link to the lab.
            assert "Page Agent 개발자 실험실" in index
            assert index.count(f'href="{DEV_LAB_ROUTE}"') == 1
            # The old primary product label is gone.
            assert "Page Agent 실험실" not in index

    def test_mvp_mobile_admin_cards_preserved(self):
        mod = _load_build_module()
        index = mod.build_index_html([], is_live=False)
        # MVP card stays relative-path, no query string.
        assert 'href="mvp/"' in index
        assert "시민 행정 도우미" in index
        assert "mvp=1" not in index
        assert 'href="mobile.html"' in index
        assert 'href="admin.html"' in index

    def test_landing_has_no_external_calls(self):
        mod = _load_build_module()
        for is_live in (False, True):
            index = mod.build_index_html([], is_live=is_live)
            _assert_no_external_auto_calls(index, f"landing(is_live={is_live})")

    def test_landing_has_no_page_agent_runtime_leak(self):
        mod = _load_build_module()
        for is_live in (False, True):
            index = mod.build_index_html([], is_live=is_live)
            _assert_no_runtime_signatures(index, f"landing(is_live={is_live})")


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

    def test_resident_index_labeled_and_isolated(self):
        html = _read(_RESIDENT_INDEX)
        assert "Page Agent형 AI 북구청" in html
        assert "comparison" in html.lower() or "비교" in html
        # No Page Agent vendor runtime / mock model / lab JS in the stub.
        _assert_no_runtime_signatures(html, "resident/index.html")
        _assert_no_external_auto_calls(html, "resident/index.html")

    def test_resident_index_links_back_to_root_lab_mvp(self):
        html = _read(_RESIDENT_INDEX)
        # Links use same-origin relative paths only (no http://).
        assert "../../index.html" in html
        assert "../" in html
        assert "../../mvp/" in html
        _assert_no_external_auto_calls(html, "resident/index.html")


# ---------------------------------------------------------------------------
# Build output contracts (in-process, offline)
# ---------------------------------------------------------------------------


class TestBuildOutputContracts:
    def test_build_copies_resident_route(self, build_dir):
        resident = os.path.join(build_dir, "examples", "page-agent", "resident", "index.html")
        assert os.path.isfile(resident), "resident route not copied into build output"

    def test_build_landing_has_primary_and_demoted_cards(self, build_dir):
        index = _read(os.path.join(build_dir, "index.html"))
        assert index.count(f'href="{RESIDENT_ROUTE}"') == 1
        assert index.count(f'href="{DEV_LAB_ROUTE}"') == 1
        assert "Page Agent형 AI 북구청" in index
        assert "Page Agent 개발자 실험실" in index
        assert "Page Agent 실험실" not in index

    @pytest.mark.parametrize(
        "route",
        ["index.html", os.path.join("mvp", "index.html"), "mobile.html", "admin.html"],
    )
    def test_protected_routes_free_of_page_agent_runtime(self, build_dir, route):
        path = os.path.join(build_dir, route)
        if os.path.isfile(path):
            _assert_no_runtime_signatures(_read(path), route)

    @pytest.mark.parametrize(
        "route",
        ["index.html", os.path.join("mvp", "index.html"), "mobile.html", "admin.html"],
    )
    def test_protected_routes_free_of_external_calls(self, build_dir, route):
        path = os.path.join(build_dir, route)
        if os.path.isfile(path):
            _assert_no_external_auto_calls(_read(path), route)

    def test_live_build_landing_labeling(self, live_build_dir):
        index = _read(os.path.join(live_build_dir, "index.html"))
        assert index.count(f'href="{RESIDENT_ROUTE}"') == 1
        assert index.count(f'href="{DEV_LAB_ROUTE}"') == 1
        assert "Page Agent형 AI 북구청" in index
