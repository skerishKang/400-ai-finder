"""#1145 final-route parity contracts for Page Agent (Phase A).

Locks fail-closed expectations so intermediate routes and text-only hits
cannot be reported as success. Offline only — no network, no live model.
"""

from __future__ import annotations

import json
import os
import re

import pytest

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
_PARITY_SCENARIOS = os.path.join(
    _REPO_ROOT, "src", "web", "examples", "page-agent", "resident", "parity-scenarios.js"
)
_MOCK_MODEL = os.path.join(
    _REPO_ROOT, "src", "web", "examples", "page-agent", "resident", "resident-mock-model.js"
)
_SERVER_SCENARIOS = os.path.join(
    _REPO_ROOT, "functions", "api", "page-agent", "_parity_scenarios.js"
)
_EXPECTATIONS = os.path.join(
    _REPO_ROOT, "tests", "fixtures", "page_agent_comparison_expectations.json"
)
_HARNESS = os.path.join(_REPO_ROOT, "scripts", "run_page_agent_comparison.mjs")

EXPECTED_FINAL_ROUTES = {
    "apartment_contact": "apartment-dept",
    "bulky_waste_menu": "bulky-waste-disposal",
    "passport_procedure": "passport-guidance",
    "complaint_screen": "complaint-write",
    "mayor_proposal_writing": "mayor-complaint-write",
}

FORBIDDEN_EARLY_DONE_TARGETS = {
    "apartment_contact": "nav-civil-service",
    "bulky_waste_menu": "nav-civil-service",
    "passport_procedure": "nav-civil-service",
    "complaint_screen": "nav-civil-service",
}

FORBIDDEN_SUCCESS_ROUTES = {
    "home",
    "civil-service",
    "complaint-category",
    "complaint-board",
    "mayor-office",
    "official-content",
}


def _read(path: str) -> str:
    with open(path, encoding="utf-8") as f:
        return f.read()


def _scenario_blocks(src: str) -> dict[str, str]:
    """Split resident parity-scenarios.js into id → full scenario object text."""
    blocks: dict[str, str] = {}
    # Each scenario object starts at `id: '...'` and ends before the next
    # top-level scenario or the SCENARIOS array close.
    parts = re.split(r"(?=\n\s*\{\s*\n\s*id:\s*')", src)
    for part in parts:
        m = re.search(r"id:\s*'([^']+)'", part)
        if not m:
            continue
        sid = m.group(1)
        if sid in EXPECTED_FINAL_ROUTES:
            blocks[sid] = part
    return blocks


class TestExpectedFinalRoutes:
    def test_expectations_lock_five_final_routes(self):
        data = json.loads(_read(_EXPECTATIONS))
        got = {
            s["id"]: s["page_agent"]["expected_final_route"] for s in data["scenarios"]
        }
        assert got == EXPECTED_FINAL_ROUTES

    def test_resident_parity_route_ids_match(self):
        src = _read(_PARITY_SCENARIOS)
        blocks = _scenario_blocks(src)
        assert set(blocks) == set(EXPECTED_FINAL_ROUTES)
        for sid, route in EXPECTED_FINAL_ROUTES.items():
            assert f"routeId: '{route}'" in blocks[sid], f"{sid} routeId mismatch"

    def test_server_parity_route_ids_match(self):
        src = _read(_SERVER_SCENARIOS)
        for sid, route in EXPECTED_FINAL_ROUTES.items():
            assert sid in src
            # Each scenario object includes routeId near the id block.
            assert f"routeId: '{route}'" in src or f'routeId: "{route}"' in src


class TestNoEarlyDoneOnIntermediateNav:
    def test_resident_nav_targets_are_not_civil_service_only(self):
        src = _read(_PARITY_SCENARIOS)
        blocks = _scenario_blocks(src)
        for sid, forbidden in FORBIDDEN_EARLY_DONE_TARGETS.items():
            block = blocks[sid]
            # First (or only) nav target must not be the intermediate civil-service step alone.
            targets = re.findall(r"target:\s*'([^']+)'", block)
            assert targets, f"{sid} missing navSteps targets"
            assert targets[0] != forbidden, (
                f"{sid} still early-stops at {forbidden}; need final-route targets"
            )

    def test_complaint_requires_two_steps_to_write(self):
        src = _read(_PARITY_SCENARIOS)
        block = _scenario_blocks(src)["complaint_screen"]
        targets = re.findall(r"target:\s*'([^']+)'", block)
        assert targets == ["nav-complaint-board", "complaint-write"]
        assert "routeId: 'complaint-write'" in block


class TestFailClosedSurfaceContracts:
    def test_mock_uses_get_current_route_id(self):
        src = _read(_MOCK_MODEL)
        assert "getCurrentRouteId" in src
        assert "hasRequiredVisibleContent" in src or "requiredVisible" in src
        assert "isForbiddenSuccessRoute" in src or "FORBIDDEN_SUCCESS_ROUTES" in src
        # Must not declare success solely because navSteps finished.
        assert "success: true" in src
        assert "success: false" in src

    def test_parity_declares_required_visible(self):
        src = _read(_PARITY_SCENARIOS)
        blocks = _scenario_blocks(src)
        for sid in EXPECTED_FINAL_ROUTES:
            assert "requiredVisible:" in blocks[sid], f"{sid} missing requiredVisible"

    def test_harness_rejects_text_only_route_success(self):
        src = _read(_HARNESS)
        assert "routeMatchesExact" in src
        assert "FORBIDDEN_SUCCESS_ROUTES" in src
        # Old false-positive helper that accepted content keywords as route pass.
        assert "function routeMatches(expectedRoutes, contentKeywords)" not in src
        assert "getCurrentRouteId" in src
        assert "mockReportedSuccess === true" in src or "mock_success" in src

    def test_forbidden_routes_enumerated(self):
        src = _read(_PARITY_SCENARIOS) + _read(_HARNESS) + _read(_SERVER_SCENARIOS)
        for route in FORBIDDEN_SUCCESS_ROUTES:
            assert route in src, f"forbidden route {route!r} not locked in sources"


class TestExpectationsRequiredVisible:
    @pytest.mark.parametrize("sid", sorted(EXPECTED_FINAL_ROUTES))
    def test_page_agent_required_visible_any(self, sid: str):
        data = json.loads(_read(_EXPECTATIONS))
        scenario = next(s for s in data["scenarios"] if s["id"] == sid)
        pa = scenario["page_agent"]
        assert pa["expected_final_route"] == EXPECTED_FINAL_ROUTES[sid]
        assert isinstance(pa.get("required_visible_any"), list)
        assert pa["required_visible_any"]
        assert isinstance(pa.get("forbidden_intermediate_routes"), list)
        assert pa["forbidden_intermediate_routes"]
