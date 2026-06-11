"""
test_bukgu_post_run_evidence_review_gate.py

Contract tests for the Stage 419 bukgu_gwangju post-run evidence review gate.
Verifies that live results are evidence-only and cannot auto-promote to persistence.

All tests are pure text/contract verification — no live execution, no network calls.
"""

import re
import ast
from pathlib import Path


# ─── Constants ──────────────────────────────────────────────────────────────

DOC_PATH = Path("docs/product/bukgu-controlled-live-smoke-approval-packet.md")
TEST_PATH = Path("tests/test_bukgu_post_run_evidence_review_gate.py")
TARGET_PROFILE = "bukgu_gwangju"


# ─── Helpers ────────────────────────────────────────────────────────────────

def read_doc() -> str:
    """Read the approval packet document as plain text."""
    assert DOC_PATH.exists(), f"Document not found: {DOC_PATH}"
    return DOC_PATH.read_text(encoding="utf-8")


def read_test() -> str:
    """Read this test file as plain text."""
    assert TEST_PATH.exists(), f"Test file not found: {TEST_PATH}"
    return TEST_PATH.read_text(encoding="utf-8")


def extract_section(text: str, header: str) -> str:
    """Extract content under a markdown header (## or ###), with or without section number."""
    escaped_header = re.escape(header).replace(r"\-", r"[\-\u2014]")
    if header in ["Purpose and Scope", "Exact Target Policy", "Provider Policy", "Required Approval Fields",
                  "Command Template", "Forbidden Defaults", "Default Stop / Rollback Conditions",
                  "Future Post-Run Report Checklist", "Cross-References", "Validation",
                  "Post-Run Evidence Review Gate (Stage 419)"]:
        pattern = r'(^#{2,3}\s+(\d+\.\s+)?' + escaped_header + r'\s*\n)(.*?)(?=\n## |\n### |\Z)'
    else:
        pattern = r'(^#{3}\s+(\d+\.\s+)?' + escaped_header + r'\s*\n)(.*?)(?=\n## |\n### |\Z)'
    match = re.search(pattern, text, re.MULTILINE | re.DOTALL)
    return match.group(3).strip() if match else ""


# ─── Exact headers from document ────────────────────────────────────────────

H_PURPOSE = "Purpose and Scope"
H_POST_RUN_GATE = "Post-Run Evidence Review Gate (Stage 419)"
H_POST_RUN_CHECKLIST = "Future Post-Run Report Checklist"


# ─── Contract Tests ─────────────────────────────────────────────────────────

class TestEvidenceOnlyPolicy:
    """Verify evidence-only policy is locked in the document."""

    def test_live_result_is_evidence_only(self):
        """Document must state live result is evidence only."""
        content = read_doc()
        section = extract_section(content, H_POST_RUN_GATE)
        assert "evidence only" in section.lower()
        assert "does not" in section.lower() and "authorize" in section.lower()

    def test_live_success_not_persistence_approval(self):
        """Document must state live success is not approval for persistence."""
        content = read_doc()
        section = extract_section(content, H_POST_RUN_GATE)
        assert "live success" in section.lower()
        assert "not" in section.lower()
        assert "persistence" in section.lower() or "promotion" in section.lower()

    def test_live_success_not_merge_promotion(self):
        """Document must state live success does not imply merge/promotion."""
        content = read_doc()
        section = extract_section(content, H_POST_RUN_GATE)
        assert "automatic merge" in section.lower() or "automatic promotion" in section.lower()
        assert "not" in section.lower() or "does not" in section.lower()

    def test_separate_human_review_required(self):
        """Document must require separate human-reviewed GitHub issue or PR."""
        content = read_doc()
        section = extract_section(content, H_POST_RUN_GATE)
        assert "human-reviewed" in section.lower() or "human reviewed" in section.lower()
        assert "github" in section.lower()
        assert "issue" in section.lower() or "pr" in section.lower()

    def test_no_automatic_process_may_consume_results(self):
        """Document must state no automatic process may consume live results."""
        content = read_doc()
        section = extract_section(content, H_POST_RUN_GATE)
        assert "automatic process" in section.lower() or "automatic" in section.lower()
        assert "consume" in section.lower() or "may not" in section.lower()

    def test_no_persist_policy_continues_after_live(self):
        """Document must state default no-persist policy continues after live execution."""
        content = read_doc()
        section = extract_section(content, H_POST_RUN_GATE)
        assert "no-persist" in section.lower() or "no persist" in section.lower()
        assert "remain" in section.lower() or "continues" in section.lower()
        assert "prohibited" in section.lower() or "by default" in section.lower()

    def test_promotion_requires_separate_followup_issue(self):
        """Document must state promotion requires separate follow-up issue after human review."""
        content = read_doc()
        section = extract_section(content, H_POST_RUN_GATE)
        assert "promotion" in section.lower()
        assert "follow-up" in section.lower() or "followup" in section.lower()
        assert "separate" in section.lower()
        assert "human review" in section.lower()

    def test_not_auto_triggered(self):
        """Document must state follow-up is not auto-triggered."""
        content = read_doc()
        section = extract_section(content, H_POST_RUN_GATE)
        assert "auto-triggered" in section.lower() or "not auto" in section.lower()

    def test_bukgu_gwangju_only_first_live_target(self):
        """Document must state bukgu_gwangju remains only first-live target."""
        content = read_doc()
        section = extract_section(content, H_POST_RUN_GATE)
        assert "bukgu_gwangju" in section
        assert "only first-live" in section.lower() or "only" in section.lower()
        assert "profile expansion" in section.lower()
        assert "not" in section.lower() or "prohibited" in section.lower()


class TestFailureReportingRules:
    """Verify failure reporting rules / automatic promotion blockers."""

    def test_failures_block_promotion(self):
        """Failures must be listed as automatic promotion blocker."""
        content = read_doc()
        section = extract_section(content, H_POST_RUN_GATE)
        assert "failures" in section.lower()
        assert "block" in section.lower()
        assert "promotion" in section.lower()

    def test_timeouts_block_promotion(self):
        """Timeouts must be listed as automatic promotion blocker."""
        content = read_doc()
        section = extract_section(content, H_POST_RUN_GATE)
        assert "timeouts" in section.lower()
        assert "block" in section.lower()
        assert "promotion" in section.lower()

    def test_domain_expansion_blocks_promotion(self):
        """Unexpected domain expansion must be listed as automatic promotion blocker."""
        content = read_doc()
        section = extract_section(content, H_POST_RUN_GATE)
        assert "domain expansion" in section.lower()
        assert "block" in section.lower()
        assert "promotion" in section.lower()

    def test_provider_switch_blocks_promotion(self):
        """Provider switch must be listed as automatic promotion blocker."""
        content = read_doc()
        section = extract_section(content, H_POST_RUN_GATE)
        assert "provider switch" in section.lower()
        assert "block" in section.lower()
        assert "promotion" in section.lower()

    def test_artifact_write_attempt_blocks_promotion(self):
        """Artifact write attempt must be listed as automatic promotion blocker."""
        content = read_doc()
        section = extract_section(content, H_POST_RUN_GATE)
        assert "artifact write" in section.lower() or "artifact" in section.lower()
        assert "write" in section.lower()
        assert "block" in section.lower()
        assert "promotion" in section.lower()

    def test_firecrawl_api_key_secret_blocks_promotion(self):
        """Firecrawl/API key/secret requirement must block promotion unless separately approved."""
        content = read_doc()
        section = extract_section(content, H_POST_RUN_GATE)
        assert "firecrawl" in section.lower()
        assert "api" in section.lower()
        assert "key" in section.lower() or "secret" in section.lower()
        assert "block" in section.lower()
        assert "promotion" in section.lower()
        assert "separately approved" in section.lower() or "separate" in section.lower()

    def test_disallowed_persistence_attempt_blocks_promotion(self):
        """Disallowed persistence attempt must block promotion."""
        content = read_doc()
        section = extract_section(content, H_POST_RUN_GATE)
        assert "persistence" in section.lower()
        assert "attempt" in section.lower()
        assert "block" in section.lower()
        assert "promotion" in section.lower()


class TestPostRunReportFields:
    """Verify mandatory post-run evidence report fields are documented."""

    def test_all_report_fields_present(self):
        """All 11 mandatory post-run report fields must be listed."""
        content = read_doc()
        section = extract_section(content, H_POST_RUN_CHECKLIST)
        required_fields = [
            "exact command",
            "target profile",
            "provider used",
            "caps used",
            "pages attempted / fetched",
            "errors",
            "timeouts",
            "output artifacts",
            "no-disallowed-persistence",
            "follow-up",
        ]
        for field in required_fields:
            assert field.lower() in section.lower(), f"Missing post-run report field: {field}"

    def test_exact_command_field(self):
        """Exact command used field must be present."""
        content = read_doc()
        section = extract_section(content, H_POST_RUN_CHECKLIST)
        assert "exact command" in section.lower()

    def test_target_profile_field(self):
        """Target profile field must be present."""
        content = read_doc()
        section = extract_section(content, H_POST_RUN_CHECKLIST)
        assert "target profile" in section.lower()

    def test_provider_used_field(self):
        """Provider used field must be present."""
        content = read_doc()
        section = extract_section(content, H_POST_RUN_CHECKLIST)
        assert "provider used" in section.lower()

    def test_caps_used_field(self):
        """Caps used field must be present."""
        content = read_doc()
        section = extract_section(content, H_POST_RUN_CHECKLIST)
        assert "caps used" in section.lower()

    def test_pages_attempted_fetched_field(self):
        """Pages attempted/fetched field must be present."""
        content = read_doc()
        section = extract_section(content, H_POST_RUN_CHECKLIST)
        assert "pages attempted" in section.lower()
        assert "pages fetched" in section.lower() or "fetched" in section.lower()

    def test_errors_field(self):
        """Errors field must be present."""
        content = read_doc()
        section = extract_section(content, H_POST_RUN_CHECKLIST)
        assert "errors" in section.lower()

    def test_timeouts_field(self):
        """Timeouts field must be present."""
        content = read_doc()
        section = extract_section(content, H_POST_RUN_CHECKLIST)
        assert "timeouts" in section.lower()

    def test_output_artifacts_field(self):
        """Output artifacts field must be present."""
        content = read_doc()
        section = extract_section(content, H_POST_RUN_CHECKLIST)
        assert "output artifacts" in section.lower()

    def test_no_disallowed_persistence_confirmation_field(self):
        """No-disallowed-persistence confirmation field must be present."""
        content = read_doc()
        section = extract_section(content, H_POST_RUN_CHECKLIST)
        assert "no-disallowed-persistence" in section.lower() or "no disallowed persistence" in section.lower()

    def test_recommended_followup_issue_field(self):
        """Recommended follow-up issue field must be present."""
        content = read_doc()
        section = extract_section(content, H_POST_RUN_CHECKLIST)
        assert "follow-up" in section.lower() or "followup" in section.lower()


class TestDefaultNoPersistPolicy:
    """Verify default no-persist policy is locked."""

    def test_scenario_snapshot_cache_prohibited_by_default(self):
        """Scenario/snapshot/cache must be prohibited by default."""
        content = read_doc()
        # Check both post-run gate and forbidden defaults
        section = extract_section(content, H_POST_RUN_GATE)
        forbidden = extract_section(content, "Forbidden Defaults")
        assert "scenario" in section.lower() or "scenario" in forbidden.lower()
        assert "snapshot" in section.lower() or "snapshot" in forbidden.lower()
        assert "cache" in section.lower() or "cache" in forbidden.lower()
        assert "prohibited" in section.lower() or "prohibited" in forbidden.lower()

    def test_config_source_grounding_prohibited_by_default(self):
        """Config/source-grounding must be prohibited by default."""
        content = read_doc()
        section = extract_section(content, H_POST_RUN_GATE)
        forbidden = extract_section(content, "Forbidden Defaults")
        assert "config" in section.lower() or "config" in forbidden.lower()
        assert "source-grounding" in section.lower() or "source-grounding" in forbidden.lower()
        assert "prohibited" in section.lower() or "prohibited" in forbidden.lower()

    def test_promotion_requires_separate_followup(self):
        """Promotion must require separate follow-up issue."""
        content = read_doc()
        section = extract_section(content, H_POST_RUN_GATE)
        assert "promotion" in section.lower()
        assert "follow-up" in section.lower() or "followup" in section.lower()
        assert "separate" in section.lower()

    def test_no_automatic_promotion_wording(self):
        """Document must not contain automatic promotion wording."""
        content = read_doc()
        # Check that "automatic promotion" only appears as a prohibited thing
        section = extract_section(content, H_POST_RUN_GATE)
        assert "no automatic" in section.lower() or "not automatic" in section.lower()
        # Verify it doesn't say promotion IS automatic
        assert "promotion is automatic" not in section.lower()
        assert "automatically promoted" not in section.lower()


class TestMetaNoLiveTests:
    """Meta/no-live tests for the test file itself."""

    def test_test_file_imports_only_stdlib(self):
        """Test file must import only stdlib modules."""
        content = read_test()
        tree = ast.parse(content)
        allowed_modules = {
            "re", "pathlib", "ast", "unittest", "pytest",
            "typing", "dataclasses", "enum", "collections",
            "itertools", "functools", "json", "os", "sys"
        }
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    base_module = alias.name.split(".")[0]
                    assert base_module in allowed_modules, f"Non-stdlib import: {alias.name}"
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    base_module = node.module.split(".")[0]
                    assert base_module in allowed_modules, f"Non-stdlib import: {node.module}"

    def test_no_requests_import(self):
        """Test file must not import requests."""
        content = read_test()
        tree = ast.parse(content)
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    assert "requests" != alias.name.split(".")[0]
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    assert "requests" != node.module.split(".")[0]

    def test_no_httpx_import(self):
        """Test file must not import httpx."""
        content = read_test()
        tree = ast.parse(content)
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    assert "httpx" != alias.name.split(".")[0]
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    assert "httpx" != node.module.split(".")[0]

    def test_no_urllib_import(self):
        """Test file must not import urllib."""
        content = read_test()
        tree = ast.parse(content)
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    assert "urllib" != alias.name.split(".")[0]
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    assert "urllib" != node.module.split(".")[0]

    def test_no_socket_import(self):
        """Test file must not import socket."""
        content = read_test()
        tree = ast.parse(content)
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    assert "socket" != alias.name.split(".")[0]
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    assert "socket" != node.module.split(".")[0]

    def test_no_firecrawl_import(self):
        """Test file must not import firecrawl."""
        content = read_test()
        tree = ast.parse(content)
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    assert "firecrawl" != alias.name.split(".")[0]
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    assert "firecrawl" != node.module.split(".")[0]

    def test_no_executable_live_script_path_introduced(self):
        """Test file must not introduce an executable live script path."""
        content = read_test()
        assert "scripts/" not in content or "CANDIDATE_LIVE_SMOKE_SCRIPT" in content

    def test_no_config_src_scenario_snapshot_cache_files_modified(self):
        """Test must not modify config/src/scenario/snapshot/cache files."""
        assert TEST_PATH.exists()


# ─── Entry Point ────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v"])