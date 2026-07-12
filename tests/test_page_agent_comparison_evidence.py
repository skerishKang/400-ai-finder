"""Offline contract tests for Stage 3 comparison evidence schema and fixtures.

These tests verify:

  * the comparison expectations fixture structure
  * the comparison evidence JSON schema (once generated)
  * scenario coverage (exactly 5 scenario IDs)
  * each mode x scenario has exactly 3 primary runs
  * required metrics exist and have correct types
  * no-submit is preserved on every run
  * external request count is 0 on every run
  * boundary probes exist (unsupported + cancellation)
  * no winner declaration without data
  * no confidential content

All tests are offline static-source checks. No network, no build output,
no browser, no live model.
"""

from __future__ import annotations

import json
import os
import re

import pytest

_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
_FIXTURE_DIR = os.path.join(_REPO_ROOT, "tests", "fixtures")
_EVIDENCE_DIR = os.path.join(_REPO_ROOT, "docs", "artifacts", "1109-stage3-comparison")
_EXPECTATIONS_PATH = os.path.join(_FIXTURE_DIR, "page_agent_comparison_expectations.json")
_EVIDENCE_PATH = os.path.join(_EVIDENCE_DIR, "comparison-evidence.json")
_PARITY_PATH = os.path.join(_REPO_ROOT, "src", "web", "examples", "page-agent", "parity-contract.json")

EXPECTED_SCENARIO_IDS = frozenset({
    "apartment_contact",
    "bulky_waste_menu",
    "passport_procedure",
    "complaint_screen",
    "mayor_proposal_writing",
})

REQUIRED_RUN_FIELDS = frozenset({
    "schema_version",
    "scenario_id",
    "category",
    "mode",
    "attempt",
    "canonical_request",
    "actual_trigger",
    "success",
    "terminal_state",
    "final_route",
    "final_surface",
    "expected_outcome",
    "pass_criteria_results",
    "action_step_count",
    "total_engine_step_count",
    "wrong_route_action_count",
    "action_sequence",
    "elapsed_ms",
    "no_submit_preserved",
    "external_request_count",
    "request_failure_count",
    "console_error_count",
    "page_error_count",
    "warning_count",
    "reproducibility_signature",
    "errors",
})

REQUIRED_EVIDENCE_TOP_KEYS = frozenset({
    "schema_version",
    "track",
    "generated_at",
    "methodology",
    "primary_runs",
    "boundary_probes",
    "aggregate",
})

FORBIDDEN_WINNER_PATTERNS = [
    r"\b(is\s+(faster|better|superior|wins?))\b",
    r"\b(우수|뛰어|낫|승리|더\s+좋)\b",
    r"\b(더\s+빠르)\b",
]

FORBIDDEN_CONFIDENTIAL_PATTERNS = [
    r"\b(의뢰|고객사|비공개|secret|api[_-]?key|token)\b",
]

# Report path
_REPORT_PATH = os.path.join(_REPO_ROOT, "docs", "page-agent-stage3-comparison-report.md")
REQUIRED_REPORT_SECTIONS = [
    "# ",
    "## 목적",
    "## 비교 대상과 동일성 조건",
    "## 실행 환경",
    "## 측정 정의",
    "## Aggregate 결과",
    "## Unsupported / Cancellation 결과",
    "## 재현성",
    "## Safety / No-Submit 검증",
    "## 한계",
    "## Hybrid Boundary 관찰",
    "## 결론",
]


def _read(path: str) -> str:
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def _read_json(path: str) -> dict:
    return json.loads(_read(path))


# ---------------------------------------------------------------------------
# Expectations fixture tests
# ---------------------------------------------------------------------------


class TestExpectationsFixture:
    def test_file_exists(self):
        assert os.path.isfile(_EXPECTATIONS_PATH), "expectations fixture missing"

    def test_valid_json(self):
        data = _read_json(_EXPECTATIONS_PATH)
        assert data["schema_version"] == "1.0.0"
        assert data["track"] == "1109-page-agent-comparison"

    def test_exactly_five_scenarios(self):
        data = _read_json(_EXPECTATIONS_PATH)
        scenarios = data["scenarios"]
        assert len(scenarios) == 5
        ids = frozenset(s["id"] for s in scenarios)
        assert ids == EXPECTED_SCENARIO_IDS

    @pytest.mark.parametrize(
        "sid",
        sorted(EXPECTED_SCENARIO_IDS),
    )
    def test_each_scenario_has_both_modes(self, sid: str):
        data = _read_json(_EXPECTATIONS_PATH)
        scenario = next(s for s in data["scenarios"] if s["id"] == sid)
        assert "deterministic" in scenario, f"{sid} missing deterministic"
        assert "page_agent" in scenario, f"{sid} missing page_agent"
        det = scenario["deterministic"]
        pa = scenario["page_agent"]
        assert "trigger" in det
        assert "trigger" in pa
        assert "expected_final_route" in det
        assert "expected_final_route" in pa

    def test_boundary_section_exists(self):
        data = _read_json(_EXPECTATIONS_PATH)
        assert "boundary" in data
        assert "unsupported" in data["boundary"]
        assert "cancellation" in data["boundary"]

    def test_no_submit_shared_contract_not_duplicated(self):
        """Expectations fixture must NOT duplicate parity-contract pass criteria."""
        data = _read_json(_EXPECTATIONS_PATH)
        for scenario in data["scenarios"]:
            assert "pass_criteria" not in scenario, (
                f"pass_criteria should not be duplicated in expectations for {scenario['id']}"
            )


# ---------------------------------------------------------------------------
# Evidence schema tests (run after harness generates evidence)
# ---------------------------------------------------------------------------


class TestEvidenceExistence:
    def test_evidence_file_exists(self):
        if not os.path.isfile(_EVIDENCE_PATH):
            pytest.skip("evidence file not yet generated; run comparison harness first")
        assert os.path.isfile(_EVIDENCE_PATH)


class TestEvidenceSchema:
    @pytest.fixture(autouse=True)
    def _load_evidence(self):
        if not os.path.isfile(_EVIDENCE_PATH):
            pytest.skip("evidence file not yet generated")
        self.data = _read_json(_EVIDENCE_PATH)

    def test_top_level_keys(self):
        keys = set(self.data.keys())
        assert REQUIRED_EVIDENCE_TOP_KEYS.issubset(keys), (
            f"missing keys: {REQUIRED_EVIDENCE_TOP_KEYS - keys}"
        )

    def test_schema_version(self):
        assert self.data["schema_version"] == "1.0.0"
        assert self.data["track"] == "1109-page-agent-comparison"

    def test_generated_at_present(self):
        assert isinstance(self.data["generated_at"], str)

    def test_methodology(self):
        m = self.data["methodology"]
        assert "description" in m
        assert "modes" in m
        assert isinstance(m["modes"], list) and len(m["modes"]) == 2

    def test_mode_labels(self):
        modes = self.data["methodology"]["modes"]
        labels = set(m["id"] for m in modes)
        assert labels == {"deterministic", "page_agent"}

    def test_primary_runs_count(self):
        runs = self.data["primary_runs"]
        # Expecting 5 scenarios x 2 modes x repetitions
        assert len(runs) == 30, f"Expected 30 primary runs, got {len(runs)}"

    def test_each_run_has_required_fields(self):
        runs = self.data["primary_runs"]
        for i, run in enumerate(runs):
            missing = REQUIRED_RUN_FIELDS - set(run.keys())
            assert not missing, f"Run {i} missing fields: {missing}"

    def test_run_field_types(self):
        runs = self.data["primary_runs"]
        for i, run in enumerate(runs):
            assert isinstance(run["schema_version"], str)
            assert isinstance(run["scenario_id"], str)
            assert isinstance(run["mode"], str)
            assert isinstance(run["attempt"], int)
            assert isinstance(run["success"], bool)
            assert isinstance(run["action_step_count"], int)
            assert isinstance(run["total_engine_step_count"], int)
            assert isinstance(run["wrong_route_action_count"], (int, float))
            assert isinstance(run["action_sequence"], list)
            assert isinstance(run["elapsed_ms"], (int, float))
            assert isinstance(run["no_submit_preserved"], bool)
            assert isinstance(run["external_request_count"], int)
            assert isinstance(run["console_error_count"], int)
            assert isinstance(run["reproducibility_signature"], str)

    def test_exactly_5_scenario_ids(self):
        runs = self.data["primary_runs"]
        ids = frozenset(r["scenario_id"] for r in runs)
        assert ids == EXPECTED_SCENARIO_IDS

    def test_exactly_2_modes(self):
        runs = self.data["primary_runs"]
        modes = frozenset(r["mode"] for r in runs)
        assert modes == {"deterministic", "page_agent"}

    def test_each_mode_scenario_has_3_runs(self):
        runs = self.data["primary_runs"]
        for sid in EXPECTED_SCENARIO_IDS:
            for mode in ("deterministic", "page_agent"):
                subset = [r for r in runs if r["scenario_id"] == sid and r["mode"] == mode]
                assert len(subset) == 3, (
                    f"{mode}/{sid}: expected 3 runs, got {len(subset)}"
                )

    def test_each_run_preserved_no_submit(self):
        runs = self.data["primary_runs"]
        for i, run in enumerate(runs):
            assert run["no_submit_preserved"] is True, (
                f"Run {i} ({run['mode']}/{run['scenario_id']}): no_submit_preserved must be True"
            )

    def test_zero_external_requests(self):
        runs = self.data["primary_runs"]
        for i, run in enumerate(runs):
            assert run["external_request_count"] == 0, (
                f"Run {i} ({run['mode']}/{run['scenario_id']}): external_request_count={run['external_request_count']}"
            )

    def test_attempt_numbers_are_1_2_3(self):
        runs = self.data["primary_runs"]
        for sid in EXPECTED_SCENARIO_IDS:
            for mode in ("deterministic", "page_agent"):
                subset = [r for r in runs if r["scenario_id"] == sid and r["mode"] == mode]
                attempts = sorted(r["attempt"] for r in subset)
                assert attempts == [1, 2, 3], (
                    f"{mode}/{sid}: attempts {attempts} != [1,2,3]"
                )

    def test_boundary_probes_exist(self):
        probes = self.data["boundary_probes"]
        assert isinstance(probes, list)
        assert len(probes) >= 4, f"Expected at least 4 boundary probes, got {len(probes)}"

    def test_boundary_probe_unsupported_both_modes(self):
        probes = self.data["boundary_probes"]
        det = [p for p in probes if p.get("probe") == "unsupported_prompt" and p.get("mode") == "deterministic"]
        pa = [p for p in probes if p.get("probe") == "unsupported_prompt" and p.get("mode") == "page_agent"]
        assert len(det) >= 1, "Missing deterministic unsupported prompt probe"
        assert len(pa) >= 1, "Missing page_agent unsupported prompt probe"

    def test_boundary_unsupported_page_agent_safe(self):
        probes = self.data["boundary_probes"]
        for p in probes:
            if p.get("probe") == "unsupported_prompt" and p.get("mode") == "page_agent":
                assert p.get("safe") is not False, (
                    "Page Agent unsupported probe must be safe"
                )

    def test_boundary_probe_cancellation_both_modes(self):
        probes = self.data["boundary_probes"]
        det = [p for p in probes if p.get("probe") == "cancellation" and p.get("mode") == "deterministic"]
        pa = [p for p in probes if p.get("probe") == "cancellation" and p.get("mode") == "page_agent"]
        assert len(det) >= 1, "Missing deterministic cancellation probe"
        assert len(pa) >= 1, "Missing page_agent cancellation probe"

    def test_aggregate_exists(self):
        a = self.data["aggregate"]
        assert "total_runs" in a
        assert "successful" in a
        assert "failed" in a
        assert "success_rate" in a
        assert "by_mode" in a
        assert "reproducibility" in a

    def test_aggregate_by_mode_has_both(self):
        modes = self.data["aggregate"]["by_mode"]
        assert "deterministic" in modes
        assert "page_agent" in modes

    def test_aggregate_by_mode_fields(self):
        for mode_name in ("deterministic", "page_agent"):
            m = self.data["aggregate"]["by_mode"][mode_name]
            assert "total" in m
            assert "successful" in m
            assert "failed" in m
            assert "median_elapsed_ms" in m
            assert "total_wrong_route_actions" in m

    def test_no_winner_declaration(self):
        """Evidence file must not declare one mode as better/faster/superior."""
        text = json.dumps(self.data, ensure_ascii=False)
        for pattern in FORBIDDEN_WINNER_PATTERNS:
            matches = re.findall(pattern, text, re.IGNORECASE)
            assert not matches, f"Forbidden winner pattern found: {matches} (pattern: {pattern})"

    def test_no_confidential_content(self):
        """Evidence must not contain confidential client/request origin info."""
        text = json.dumps(self.data, ensure_ascii=False)
        for pattern in FORBIDDEN_CONFIDENTIAL_PATTERNS:
            matches = re.findall(pattern, text, re.IGNORECASE)
            assert not matches, f"Forbidden confidential pattern found: {matches}"

    def test_no_provider_live_claim(self):
        text = json.dumps(self.data, ensure_ascii=False).lower()
        assert "live model" not in text
        assert "firecrawl" not in text
        assert "api key" not in text

    def test_reproducibility_signature_matches_run_fields(self):
        runs = self.data["primary_runs"]
        for run in runs:
            sig = run.get("reproducibility_signature", "")
            fields = sig.split("|")
            assert len(fields) >= 5, f"Signature too short: {sig}"

    def test_reproducibility_result_matches_runs(self):
        runs = self.data["primary_runs"]
        details = self.data["aggregate"]["reproducibility_details"]
        for detail in details:
            sid = detail["scenario_id"]
            mode = detail["mode"]
            mode_runs = [r for r in runs if r["scenario_id"] == sid and r["mode"] == mode]
            assert len(mode_runs) == detail["run_count"]


# ---------------------------------------------------------------------------
# Report contract tests
# ---------------------------------------------------------------------------


class TestReportContract:
    def test_report_exists(self):
        if not os.path.isfile(_REPORT_PATH):
            pytest.skip("report not yet generated")
        assert os.path.isfile(_REPORT_PATH)

    def test_required_sections(self):
        if not os.path.isfile(_REPORT_PATH):
            pytest.skip("report not yet generated")
        report = _read(_REPORT_PATH)
        for section in REQUIRED_REPORT_SECTIONS:
            assert section in report, f"Required section '{section}' not found in report"

    def test_report_no_winner_declaration(self):
        if not os.path.isfile(_REPORT_PATH):
            pytest.skip("report not yet generated")
        text = _read(_REPORT_PATH)
        for pattern in FORBIDDEN_WINNER_PATTERNS:
            matches = re.findall(pattern, text, re.IGNORECASE)
            assert not matches, f"Forbidden winner pattern in report: {matches}"

    def test_report_no_confidential_content(self):
        if not os.path.isfile(_REPORT_PATH):
            pytest.skip("report not yet generated")
        text = _read(_REPORT_PATH)
        for pattern in FORBIDDEN_CONFIDENTIAL_PATTERNS:
            matches = re.findall(pattern, text, re.IGNORECASE)
            assert not matches, f"Forbidden confidential pattern in report: {matches}"

    def test_report_no_provider_live_claim(self):
        if not os.path.isfile(_REPORT_PATH):
            pytest.skip("report not yet generated")
        text = _read(_REPORT_PATH).lower()
        assert "live model" not in text
        assert "firecrawl" not in text
        assert "api key" not in text

    def test_report_mentions_deterministic_delays(self):
        if not os.path.isfile(_REPORT_PATH):
            pytest.skip("report not yet generated")
        text = _read(_REPORT_PATH)
        assert "delay" in text.lower() or "intentional" in text.lower(), (
            "Report must mention deterministic intentional delays"
        )

    def test_report_mentions_mock_not_real_llm(self):
        if not os.path.isfile(_REPORT_PATH):
            pytest.skip("report not yet generated")
        text = _read(_REPORT_PATH).lower()
        assert "mock" in text or "deterministic" in text, (
            "Report must acknowledge mock/deterministic nature"
        )


# ---------------------------------------------------------------------------
# Parity contract consistency
# ---------------------------------------------------------------------------


class TestParityContractConsistency:
    def test_parity_contract_and_expectations_have_same_scenarios(self):
        parity = _read_json(_PARITY_PATH)
        expectations = _read_json(_EXPECTATIONS_PATH)
        parity_ids = frozenset(s["id"] for s in parity["scenarios"])
        expect_ids = frozenset(s["id"] for s in expectations["scenarios"])
        assert parity_ids == expect_ids, (
            f"Parity contract IDs ({parity_ids}) != expectations IDs ({expect_ids})"
        )

    def test_no_submit_in_parity_contract_true_for_all(self):
        parity = _read_json(_PARITY_PATH)
        for scenario in parity["scenarios"]:
            assert scenario["no_submit"] is True, (
                f"Scenario {scenario['id']} must have no_submit=true"
            )


# ---------------------------------------------------------------------------
# Forbidden import / no-network checks
# ---------------------------------------------------------------------------


class TestHarnessScriptSafety:
    def test_harness_script_has_no_live_provider_import(self):
        harness_path = os.path.join(_REPO_ROOT, "scripts", "run_page_agent_comparison.mjs")
        if not os.path.isfile(harness_path):
            pytest.skip("harness script not yet created")
        text = _read(harness_path).lower()
        # forbid live API provider imports and dangerous methods;
        # execute_javascript detection in mock diagnostics is allowed
        forbidden = ["openai", "anthropic", "gemini", "firecrawl"]
        for item in forbidden:
            assert item not in text, f"Harness must not reference '{item}'"
