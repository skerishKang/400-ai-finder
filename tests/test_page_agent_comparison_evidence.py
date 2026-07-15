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
    "warnings",
    "reproducibility_signature",
    "errors",
    "console_error_messages",
    "console_error_details",
    "request_failed_details",
    "http_error_responses",
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
    "## 알려진 Parity Gap",
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

    def test_base_sha_is_locked_provenance(self):
        data = _read_json(_EXPECTATIONS_PATH)
        base_sha = data["base_sha"]

        assert isinstance(base_sha, str)
        assert re.fullmatch(r"[0-9a-f]{40}", base_sha)
        assert base_sha == "5ad20ad027f993cb522a49c90f39523211e6c5cd"


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
            assert isinstance(run["http_error_responses"], list)

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

    def test_each_run_has_pass_criteria_results(self):
        """Every run must have populated pass_criteria_results from DOM evidence."""
        runs = self.data["primary_runs"]
        for i, run in enumerate(runs):
            cr = run.get("pass_criteria_results", [])
            assert len(cr) > 0, (
                f"Run {i} ({run['mode']}/{run['scenario_id']}): pass_criteria_results is empty"
            )
            for c in cr:
                assert "criterion" in c, f"Run {i} pass_criteria_result missing 'criterion': {c}"
                assert "passed" in c, f"Run {i} pass_criteria_result missing 'passed': {c}"
                assert isinstance(c["passed"], bool), (
                    f"Run {i} pass_criteria_result 'passed' must be bool: {c}"
                )

    def test_pass_criteria_count_matches_parity_contract(self):
        """Each scenario should have the same number of pass criteria as parity-contract.json."""
        parity = _read_json(_PARITY_PATH)
        runs = self.data["primary_runs"]
        by_scenario = {}
        for r in runs:
            by_scenario.setdefault(r["scenario_id"], []).append(r)
        for sid, group in by_scenario.items():
            parity_scenario = next(s for s in parity["scenarios"] if s["id"] == sid)
            expected_count = len(parity_scenario.get("pass_criteria", []))
            first_run = group[0]
            actual_count = len(first_run.get("pass_criteria_results", []))
            assert actual_count == expected_count, (
                f"{sid}: expected {expected_count} pass criteria, got {actual_count}"
            )

    def test_deterministic_action_step_count_matches_sequence(self):
        """Deterministic mode should have action_step_count matching sequence excluding trivials."""
        runs = self.data["primary_runs"]
        det_runs = [r for r in runs if r["mode"] == "deterministic"]
        for r in det_runs:
            seq = r.get("action_sequence", [])
            if len(seq) > 0:
                non_trivial = [s for s in seq if s not in ("message", "", "noop")]
                assert r["action_step_count"] == len(non_trivial), (
                    f"deterministic/{r['scenario_id']}/{r['attempt']}: action_step_count={r['action_step_count']} "
                    f"!= non_trivial count={len(non_trivial)}"
                )

    def test_deterministic_total_engine_step_count_matches_action_sequence(self):
        """Deterministic total_engine_step_count should equal action_sequence length."""
        runs = self.data["primary_runs"]
        det_runs = [r for r in runs if r["mode"] == "deterministic"]
        for r in det_runs:
            seq = r.get("action_sequence", [])
            if len(seq) > 0:
                assert r["total_engine_step_count"] == len(seq), (
                    f"deterministic/{r['scenario_id']}/{r['attempt']}: "
                    f"total_engine_step_count={r['total_engine_step_count']} "
                    f"!= len(action_sequence)={len(seq)}"
                )

    def test_page_agent_action_step_count_matches_diagnostics(self):
        """Page Agent action_step_count should equal non-terminal action count."""
        runs = self.data["primary_runs"]
        pa_runs = [r for r in runs if r["mode"] == "page_agent"]
        for r in pa_runs:
            seq = r.get("action_sequence", [])
            if len(seq) > 0:
                non_terminal = [a for a in seq if a not in ("done", "stop")]
                assert r["action_step_count"] == len(non_terminal), (
                    f"page_agent/{r['scenario_id']}/{r['attempt']}: "
                    f"action_step_count={r['action_step_count']} "
                    f"!= non-terminal count={len(non_terminal)}"
                )

    def test_each_run_records_wrong_route_actions(self):
        """Each run must have wrong_route_action_count computed."""
        runs = self.data["primary_runs"]
        for i, run in enumerate(runs):
            assert isinstance(run["wrong_route_action_count"], (int, float)), (
                f"Run {i}: wrong_route_action_count must be numeric"
            )

    def test_aggregate_wrong_route_actions_matches_runs(self):
        """Aggregate total_wrong_route_actions should sum from individual runs."""
        runs = self.data["primary_runs"]
        aggregate = self.data["aggregate"]
        for mode_name in ("deterministic", "page_agent"):
            mode_runs = [r for r in runs if r["mode"] == mode_name]
            expected_total = sum(r.get("wrong_route_action_count", 0) for r in mode_runs)
            actual_total = aggregate["by_mode"][mode_name]["total_wrong_route_actions"]
            assert actual_total == expected_total, (
                f"{mode_name}: aggregate total_wrong_route_actions={actual_total} "
                f"!= sum of runs={expected_total}"
            )

    def test_aggregate_median_metrics_from_runs(self):
        """Aggregate medians should be computed for all and success."""
        runs = self.data["primary_runs"]
        aggregate = self.data["aggregate"]
        for mode_name in ("deterministic", "page_agent"):
            mode_runs = [r for r in runs if r["mode"] == mode_name]
            success_runs = [r for r in mode_runs if r["success"]]

            def compute_median(values):
                if not values: return 0
                s = sorted(values)
                n = len(s)
                return s[n // 2] if n % 2 else (s[n // 2 - 1] + s[n // 2]) / 2

            expected_action_all = compute_median([r["action_step_count"] for r in mode_runs])
            expected_action_success = compute_median([r["action_step_count"] for r in success_runs])
            expected_elapsed_all = compute_median([r["elapsed_ms"] for r in mode_runs])
            expected_elapsed_success = compute_median([r["elapsed_ms"] for r in success_runs])

            agg = aggregate["by_mode"][mode_name]
            assert agg["median_action_step_count_all"] == expected_action_all
            assert agg["median_action_step_count_success"] == expected_action_success
            assert agg["median_elapsed_ms_all"] == expected_elapsed_all
            assert agg["median_elapsed_ms_success"] == expected_elapsed_success

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
            assert "median_elapsed_ms_all" in m
            assert "median_elapsed_ms_success" in m
            assert "median_action_step_count_all" in m
            assert "median_action_step_count_success" in m
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

    def test_report_owner_is_computer_2(self):
        if not os.path.isfile(_REPORT_PATH):
            pytest.skip("report not yet generated")
        text = _read(_REPORT_PATH)
        m = re.search(r"Owner\*\*?:\s*([^\n]+)", text)
        assert m is not None, "Report must declare an Owner"
        assert "Computer 2" in m.group(1), (
            f"Report owner must be 'Computer 2' per #1109 CTO assignment, got: {m.group(1)!r}"
        )

    def test_report_base_sha_matches_fixture_provenance(self):
        if not os.path.isfile(_REPORT_PATH):
            pytest.skip("report not yet generated")

        text = _read(_REPORT_PATH)
        match = re.search(r"Base SHA\*\*?:\s*`?([0-9a-f]{40})`?", text)

        assert match is not None, "Report must declare a 40-hex Base SHA"

        report_sha = match.group(1)
        expectations = _read_json(_EXPECTATIONS_PATH)
        fixture_sha = expectations["base_sha"]

        assert re.fullmatch(r"[0-9a-f]{40}", report_sha)
        assert report_sha == fixture_sha, (
            f"Report Base SHA {report_sha} "
            f"!= fixture provenance SHA {fixture_sha}"
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

    def test_harness_policy_description_locked(self):
        """Step 5 policy: primary scenario failures are comparison outcomes;
        only integrity/safety/boundary/stall/cardinality/artifact-validation
        violations may cause a non-zero exit. The corrected description must be
        present and the old misleading description must be gone."""
        harness_path = os.path.join(_REPO_ROOT, "scripts", "run_page_agent_comparison.mjs")
        if not os.path.isfile(harness_path):
            pytest.skip("harness script not yet created")
        text = _read(harness_path)
        assert "Primary scenario failures are recorded as comparison outcomes" in text, (
            "Harness description must state primary scenario failures are comparison outcomes"
        )
        assert "harness integrity, safety," in text and "artifact-validation violations" in text, (
            "Harness description must list integrity/safety/boundary/stall/cardinality/"
            "artifact-validation as the only non-zero-exit triggers"
        )
        assert "Non-zero exit on any run failure" not in text, (
            "Obsolete description 'Non-zero exit on any run failure' must be removed"
        )


# ---------------------------------------------------------------------------
# Exact parity: report numbers must match evidence aggregate
# ---------------------------------------------------------------------------


class TestReportEvidenceParity:
    """Contract: every number in the report that corresponds to an evidence
    aggregate field must exactly match the JSON value."""

    @pytest.fixture(autouse=True)
    def load(self):
        if not os.path.isfile(_EVIDENCE_PATH):
            pytest.skip("evidence not yet generated")
        if not os.path.isfile(_REPORT_PATH):
            pytest.skip("report not yet generated")
        self.data = _read_json(_EVIDENCE_PATH)
        self.report = _read(_REPORT_PATH)

    def _extract_number(self, pattern):
        """Find first number matching a regex pattern in the report."""
        m = re.search(pattern, self.report)
        if m is None:
            return None
        # strip commas and convert
        raw = m.group(1).replace(",", "")
        try:
            return int(raw)
        except ValueError:
            try:
                return float(raw)
            except ValueError:
                return None

    def test_total_runs_matches(self):
        agg = self.data["aggregate"]
        expected = agg["total_runs"]
        assert expected == 30, f"total_runs should be 30, got {expected}"
        # Verify report also says 30
        n = self._extract_number(r"총 실행.*?\|.*?(\d+)")
        if n is not None:
            assert n == 15, f"Report table should show 15 per mode (30 total)"

    def test_deterministic_totals_match(self):
        agg = self.data["aggregate"]["by_mode"]["deterministic"]
        runs = self.data["primary_runs"]
        det_runs = [r for r in runs if r["mode"] == "deterministic"]
        assert agg["total"] == len(det_runs), (
            f"aggregate.by_mode.deterministic.total={agg['total']} != actual det runs {len(det_runs)}"
        )
        succ = sum(1 for r in det_runs if r["success"])
        assert agg["successful"] == succ, (
            f"aggregate.by_mode.deterministic.successful={agg['successful']} != {succ}"
        )
        fail = len(det_runs) - succ
        assert agg["failed"] == fail, (
            f"aggregate.by_mode.deterministic.failed={agg['failed']} != {fail}"
        )

    def test_page_agent_totals_match(self):
        agg = self.data["aggregate"]["by_mode"]["page_agent"]
        runs = self.data["primary_runs"]
        pa_runs = [r for r in runs if r["mode"] == "page_agent"]
        assert agg["total"] == len(pa_runs), (
            f"aggregate.by_mode.page_agent.total={agg['total']} != actual pa runs {len(pa_runs)}"
        )
        succ = sum(1 for r in pa_runs if r["success"])
        assert agg["successful"] == succ
        fail = len(pa_runs) - succ
        assert agg["failed"] == fail

    def test_success_rate_matches(self):
        agg = self.data["aggregate"]
        runs = self.data["primary_runs"]
        succ = sum(1 for r in runs if r["success"])
        expected_rate = succ / len(runs) if runs else 0
        assert abs(agg["success_rate"] - expected_rate) < 1e-9, (
            f"success_rate mismatch: {agg['success_rate']} != {expected_rate}"
        )

    def test_wrong_route_totals_match(self):
        runs = self.data["primary_runs"]
        agg = self.data["aggregate"]["by_mode"]
        for mode_name in ("deterministic", "page_agent"):
            mode_runs = [r for r in runs if r["mode"] == mode_name]
            expected = sum(r["wrong_route_action_count"] for r in mode_runs)
            actual = agg[mode_name]["total_wrong_route_actions"]
            assert actual == expected, (
                f"{mode_name} wrong_route total mismatch: {actual} != {expected}"
            )

    def test_console_error_total_matches(self):
        """Sum of all console errors across runs must be 0 in final evidence."""
        runs = self.data["primary_runs"]
        total = sum(r["console_error_count"] for r in runs)
        assert total == 0, (
            f"Expected 0 total console errors in final evidence, got {total}"
        )

    def test_page_error_total_matches(self):
        runs = self.data["primary_runs"]
        total = sum(r["page_error_count"] for r in runs)
        assert total == 0, f"Expected 0 total page errors, got {total}"

    def test_http_error_total_matches(self):
        runs = self.data["primary_runs"]
        total = sum(len(r["http_error_responses"]) for r in runs)
        assert total == 0, f"Expected 0 http errors, got {total}"

    def test_request_failure_total_matches(self):
        runs = self.data["primary_runs"]
        total = sum(r["request_failure_count"] for r in runs)
        assert total == 0, f"Expected 0 request failures, got {total}"

    def test_external_request_total_matches(self):
        runs = self.data["primary_runs"]
        total = sum(r["external_request_count"] for r in runs)
        assert total == 0, f"Expected 0 external requests, got {total}"

    def test_no_submit_all_runs_match(self):
        runs = self.data["primary_runs"]
        for run in runs:
            assert run["no_submit_preserved"] is True, (
                f"{run['mode']}/{run['scenario_id']}/attempt={run['attempt']}: no_submit_preserved is False"
            )

    def test_cancellation_both_modes_success(self):
        probes = self.data["boundary_probes"]
        det_cancel = [p for p in probes if p.get("probe") == "cancellation" and p.get("mode") == "deterministic"]
        pa_cancel = [p for p in probes if p.get("probe") == "cancellation" and p.get("mode") == "page_agent"]
        assert any(p.get("success") is True for p in det_cancel), (
            "Deterministic cancellation probe must have success=True"
        )
        assert any(p.get("success") is True for p in pa_cancel), (
            "Page Agent cancellation probe must have success=True"
        )

    def test_median_action_step_count_computed_from_runs(self):
        """Verify the aggregate medians match actual run data."""
        runs = self.data["primary_runs"]
        agg = self.data["aggregate"]["by_mode"]

        def compute_median(values):
            if not values:
                return 0
            s = sorted(values)
            n = len(s)
            return s[n // 2] if n % 2 else (s[n // 2 - 1] + s[n // 2]) / 2

        for mode_name in ("deterministic", "page_agent"):
            mode_runs = [r for r in runs if r["mode"] == mode_name]
            success_runs = [r for r in mode_runs if r["success"]]
            expected_all = compute_median([r["action_step_count"] for r in mode_runs])
            expected_success = compute_median([r["action_step_count"] for r in success_runs])
            assert agg[mode_name]["median_action_step_count_all"] == expected_all, (
                f"{mode_name} median_action_step_count_all mismatch"
            )
            assert agg[mode_name]["median_action_step_count_success"] == expected_success, (
                f"{mode_name} median_action_step_count_success mismatch"
            )


# ---------------------------------------------------------------------------
# Report must reflect the current passing 30-run evidence (not stale failures)
# ---------------------------------------------------------------------------


class TestReportEvidenceConsistency:
    """Markdown report must agree with the refreshed JSON evidence aggregates.

    Asserts success totals, per-mode 15/15, zero wrong routes, Stage 5 blocked
    wording, mock-adapter limitation, and absence of a winner declaration.
    Does not hard-code volatile elapsed milliseconds.
    """

    STALE_FAILURE_PHRASES = (
        "deterministic 12/15",
        "Page Agent 3/15",
        "Page Agent 4/5 scenario",
        "official-content route failures",
        "mayor deterministic route failure",
        "det 80% vs pa 20%",
        "det 80.0% vs pa 20.0%",
        "80.0% | 20.0%",
        "성공 | 12 | 3",
        "실패 | 3 | 12",
        "30 / 15 / 15",
        "성공률 | 50.0%",
        "Total wrong route actions | 3 | 12",
        "Total wrong route actions | 15 (deterministic 3 + page_agent 12)",
        "page_agent | 0/3 | official-content",
        "mayor_proposal_writing | deterministic | 0/3 | home",
        "4/5 scenarios 0/3",
        "12/15 wrong route",
        "3/15 wrong route",
    )

    @pytest.fixture(autouse=True)
    def load(self):
        if not os.path.isfile(_EVIDENCE_PATH):
            pytest.skip("evidence not yet generated")
        if not os.path.isfile(_REPORT_PATH):
            pytest.skip("report not yet generated")
        self.data = _read_json(_EVIDENCE_PATH)
        self.report = _read(_REPORT_PATH)
        self.agg = self.data["aggregate"]
        self.by_mode = self.agg["by_mode"]

    def test_evidence_is_full_pass(self):
        assert self.agg["total_runs"] == 30
        assert self.agg["successful"] == 30
        assert self.agg["failed"] == 0
        assert abs(self.agg["success_rate"] - 1.0) < 1e-9
        assert self.by_mode["deterministic"]["successful"] == 15
        assert self.by_mode["deterministic"]["failed"] == 0
        assert self.by_mode["page_agent"]["successful"] == 15
        assert self.by_mode["page_agent"]["failed"] == 0
        assert self.by_mode["deterministic"]["total_wrong_route_actions"] == 0
        assert self.by_mode["page_agent"]["total_wrong_route_actions"] == 0
        assert self.agg.get("reproducibility") is True

    def test_report_contains_overall_30_30_0(self):
        assert "30 / 30 / 0" in self.report, (
            "Report must state overall total/success/fail as 30 / 30 / 0"
        )
        assert re.search(r"성공률\s*\|\s*100%", self.report) or "100%" in self.report

    def test_report_contains_mode_15_of_15(self):
        text = self.report
        assert re.search(r"deterministic\s+15/15", text, re.IGNORECASE) or (
            "deterministic" in text and "15/15" in text
        )
        assert re.search(r"Page Agent:\s*15/15", text) or (
            "Page Agent" in text and "15/15" in text
        )
        # Mode aggregate table rows: success 15 / fail 0 for both modes
        assert re.search(
            r"\|\s*성공\s*\|\s*15\s*\|\s*15\s*\|",
            text,
        ), "Report mode table must show success 15 | 15"
        assert re.search(
            r"\|\s*실패\s*\|\s*0\s*\|\s*0\s*\|",
            text,
        ), "Report mode table must show failed 0 | 0"

    def test_report_wrong_route_zero(self):
        text = self.report
        assert re.search(
            r"Total wrong route actions\s*\|\s*0\s*\|\s*0\s*\|",
            text,
        ), "Mode table must show Total wrong route actions | 0 | 0"
        assert "deterministic 0 + page_agent 0" in text
        assert re.search(r"wrong route\s*0", text, re.IGNORECASE)

    def test_report_stage5_blocked_not_executed(self):
        assert "## Stage 5 Live-Provider Validation" in self.report
        assert "BLOCKED / NOT EXECUTED" in self.report
        assert "No live provider/API call was performed." in self.report
        assert "offline/mock parity evidence only" in self.report

    def test_report_mentions_mock_adapter_limitation(self):
        text = self.report.lower()
        assert "mock adapter" in text or "resident mock adapter" in text
        assert "실제 llm이 아니라" in text or "not a real llm" in text or "not a live llm" in text

    def test_report_no_winner_declaration(self):
        text = self.report
        assert "위너 선언 없음" in text or "no winner" in text.lower()
        for pattern in FORBIDDEN_WINNER_PATTERNS:
            matches = re.findall(pattern, text, re.IGNORECASE)
            assert not matches, f"Forbidden winner pattern in report: {matches}"
        # Explicit non-claim of superiority from success-rate comparison
        assert "한 모드의 우수성" in text or "우수하다고 결론 내리지" in text

    def test_stale_failure_phrases_absent(self):
        text = self.report
        for phrase in self.STALE_FAILURE_PHRASES:
            assert phrase not in text, f"Stale failure phrase still present: {phrase!r}"

    def test_report_safety_zeros_align_with_evidence(self):
        runs = self.data["primary_runs"]
        assert sum(r["external_request_count"] for r in runs) == 0
        assert sum(r["request_failure_count"] for r in runs) == 0
        assert sum(r["console_error_count"] for r in runs) == 0
        assert sum(r["page_error_count"] for r in runs) == 0
        assert all(r["no_submit_preserved"] is True for r in runs)
        text = self.report
        assert "External request (합계) | 0" in text or "외부 요청" in text
        assert "Request failure (합계) | 0" in text or "request failure" in text.lower()
        assert "Console error (합계) | 0" in text
        assert "Page error (합계) | 0" in text
        assert "No-submit 위반 | 0" in text or "no-submit 위반" in text.lower()

    def test_report_reproducibility_true(self):
        assert self.agg.get("reproducibility") is True
        assert re.search(r"[Rr]eproducibility\s*\|\s*true", self.report) or (
            "reproducibility: true" in self.report.lower()
        )

    def test_report_keeps_valid_limitations(self):
        text = self.report
        assert "streetlight_report" in text
        assert "elapsed" in text.lower()
        assert "action step" in text.lower() or "action-step" in text.lower()
        assert "Chrome" in text or "chrome" in text
        assert "static" in text.lower() or "정적" in text
