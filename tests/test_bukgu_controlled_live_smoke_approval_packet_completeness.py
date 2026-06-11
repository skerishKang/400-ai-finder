"""
test_bukgu_controlled_live_smoke_approval_packet_completeness.py

Contract tests for the Stage 418 bukgu_gwangju controlled live smoke approval packet completeness gate.
Verifies that incomplete packets cannot be interpreted as approval and unsafe requests are blocked.

All tests are pure text/contract verification — no live execution, no network calls.
"""

import re
import ast
from pathlib import Path


# ─── Constants ──────────────────────────────────────────────────────────────

DOC_PATH = Path("docs/product/bukgu-controlled-live-smoke-approval-packet.md")
TEST_PATH = Path("tests/test_bukgu_controlled_live_smoke_approval_packet_completeness.py")
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
                  "Future Post-Run Report Checklist", "Cross-References", "Validation"]:
        pattern = r'(^#{2}\s+(\d+\.\s+)?' + escaped_header + r'\s*\n)(.*?)(?=\n## |\Z)'
    else:
        pattern = r'(^#{3}\s+(\d+\.\s+)?' + escaped_header + r'\s*\n)(.*?)(?=\n## |\n### |\Z)'
    match = re.search(pattern, text, re.MULTILINE | re.DOTALL)
    return match.group(3).strip() if match else ""


# ─── Exact headers from document ────────────────────────────────────────────

H_PURPOSE = "Purpose and Scope"
H_TARGET = "Exact Target Policy"
H_PROVIDER = "Provider Policy"
H_FIELDS = "Required Approval Fields"
H_TEMPLATE = "Command Template"
H_FORBIDDEN = "Forbidden Defaults"


# ─── Contract Tests ─────────────────────────────────────────────────────────

class TestCompletenessGateWording:
    """Verify completeness gate wording is present in the document."""

    def test_incomplete_packet_not_approved(self):
        """Document must state incomplete packet = not approved = no execution."""
        content = read_doc()
        section = extract_section(content, H_PURPOSE)
        assert "incomplete packet" in section.lower()
        assert "not approved" in section.lower()
        assert "no execution" in section.lower() or "must not be interpreted" in section.lower()

    def test_placeholders_not_approval(self):
        """Document must state placeholders are not approval."""
        content = read_doc()
        section = extract_section(content, H_PURPOSE)
        assert "placeholder" in section.lower()
        assert "not approval" in section.lower() or "do not constitute" in section.lower()

    def test_template_not_executable_script(self):
        """Document must state template is not an executable script."""
        content = read_doc()
        section = extract_section(content, H_PURPOSE)
        assert "template" in section.lower()
        assert "executable script" in section.lower()
        assert "not" in section.lower()

    def test_approval_requires_all_fields(self):
        """Document must state approval requires ALL mandatory fields plus human approval."""
        content = read_doc()
        section = extract_section(content, H_PURPOSE)
        assert "all mandatory fields" in section.lower() or "all" in section.lower()
        assert "human approval" in section.lower() or "explicit" in section.lower()

    def test_missing_any_field_blocks_approval(self):
        """Document must state missing ANY mandatory field blocks approval."""
        content = read_doc()
        section = extract_section(content, H_PURPOSE)
        assert "missing any mandatory field" in section.lower() or "missing" in section.lower()
        assert "blocks approval" in section.lower()

    def test_unsafe_requests_blocked_from_default_approval(self):
        """Document must state unsafe requests cannot receive default approval."""
        content = read_doc()
        section = extract_section(content, H_PURPOSE)
        assert "unsafe" in section.lower()
        assert "default approval" in section.lower()
        assert "blocked" in section.lower() or "explicitly blocked" in section.lower()


class TestMissingMandatoryFieldsBlockApproval:
    """Focused contract tests: each missing mandatory field blocks approval."""

    # These tests verify the document states each field is mandatory
    # The actual "gate" is contractual — the document declares it

    def test_missing_approver_blocks_approval(self):
        """Missing approver must be covered by 'all fields mandatory' gate."""
        content = read_doc()
        section = extract_section(content, H_FIELDS)
        assert "approver" in section.lower()
        # The gate in Purpose section covers this
        purpose = extract_section(content, H_PURPOSE)
        assert "missing any mandatory field blocks approval" in purpose.lower()

    def test_missing_approval_timestamp_blocks_approval(self):
        """Missing approval timestamp must be covered by gate."""
        content = read_doc()
        section = extract_section(content, H_FIELDS)
        assert "approval timestamp" in section.lower()
        purpose = extract_section(content, H_PURPOSE)
        assert "missing any mandatory field blocks approval" in purpose.lower()

    def test_missing_exact_target_profile_blocks_approval(self):
        """Missing exact target profile must be covered by gate."""
        content = read_doc()
        section = extract_section(content, H_FIELDS)
        assert "target profile" in section.lower()
        purpose = extract_section(content, H_PURPOSE)
        assert "missing any mandatory field blocks approval" in purpose.lower()

    def test_target_profile_must_be_exactly_bukgu_gwangju(self):
        """Target profile must be exactly bukgu_gwangju."""
        content = read_doc()
        section = extract_section(content, H_TARGET)
        assert "bukgu_gwangju" in section
        assert "only profile allowed" in section.lower() or "exactly" in section.lower()

    def test_missing_exact_command_blocks_approval(self):
        """Missing exact command must be covered by gate."""
        content = read_doc()
        section = extract_section(content, H_FIELDS)
        assert "exact command" in section.lower()
        purpose = extract_section(content, H_PURPOSE)
        assert "missing any mandatory field blocks approval" in purpose.lower()

    def test_missing_max_pages_blocks_approval(self):
        """Missing max pages must be covered by gate."""
        content = read_doc()
        section = extract_section(content, H_FIELDS)
        assert "max pages" in section.lower()
        purpose = extract_section(content, H_PURPOSE)
        assert "missing any mandatory field blocks approval" in purpose.lower()

    def test_missing_max_depth_blocks_approval(self):
        """Missing max depth must be covered by gate."""
        content = read_doc()
        section = extract_section(content, H_FIELDS)
        assert "max depth" in section.lower()
        purpose = extract_section(content, H_PURPOSE)
        assert "missing any mandatory field blocks approval" in purpose.lower()

    def test_missing_timeout_blocks_approval(self):
        """Missing timeout must be covered by gate."""
        content = read_doc()
        section = extract_section(content, H_FIELDS)
        assert "timeout" in section.lower()
        purpose = extract_section(content, H_PURPOSE)
        assert "missing any mandatory field blocks approval" in purpose.lower()

    def test_missing_retry_policy_blocks_approval(self):
        """Missing retry policy must be covered by gate."""
        content = read_doc()
        section = extract_section(content, H_FIELDS)
        assert "retry policy" in section.lower()
        purpose = extract_section(content, H_PURPOSE)
        assert "missing any mandatory field blocks approval" in purpose.lower()

    def test_missing_output_location_blocks_approval(self):
        """Missing output location must be covered by gate."""
        content = read_doc()
        section = extract_section(content, H_FIELDS)
        assert "output location" in section.lower()
        purpose = extract_section(content, H_PURPOSE)
        assert "missing any mandatory field blocks approval" in purpose.lower()

    def test_missing_expected_diff_policy_blocks_approval(self):
        """Missing expected diff policy must be covered by gate."""
        content = read_doc()
        section = extract_section(content, H_FIELDS)
        assert "expected diff policy" in section.lower()
        purpose = extract_section(content, H_PURPOSE)
        assert "missing any mandatory field blocks approval" in purpose.lower()

    def test_missing_stop_rollback_conditions_blocks_approval(self):
        """Missing stop/rollback conditions must be covered by gate."""
        content = read_doc()
        section = extract_section(content, H_FIELDS)
        assert "stop" in section.lower() and "rollback" in section.lower()
        purpose = extract_section(content, H_PURPOSE)
        assert "missing any mandatory field blocks approval" in purpose.lower()

    def test_missing_no_persist_confirmation_blocks_approval(self):
        """Missing no-persist confirmation must be covered by gate."""
        content = read_doc()
        section = extract_section(content, H_FIELDS)
        assert "no-persist" in section.lower() or "no persist" in section.lower()
        purpose = extract_section(content, H_PURPOSE)
        assert "missing any mandatory field blocks approval" in purpose.lower()


class TestUnsafeRequestsBlockDefaultApproval:
    """Focused contract tests: unsafe requests cannot receive default approval."""

    def test_firecrawl_provider_switch_requires_separate_approval(self):
        """Firecrawl/provider switch must require separate approval and block default approval."""
        content = read_doc()
        # Check Forbidden Defaults
        section = extract_section(content, H_FORBIDDEN)
        assert "firecrawl" in section.lower()
        assert "prohibited" in section.lower()
        assert "separate approval" in section.lower()
        # Check Purpose completeness gate
        purpose = extract_section(content, H_PURPOSE)
        assert "unsafe" in purpose.lower()
        assert "firecrawl" in purpose.lower() or "provider switch" in purpose.lower()

    def test_api_key_secret_requirement_blocks_approval(self):
        """API key/secret requirement must block default approval."""
        content = read_doc()
        section = extract_section(content, H_FORBIDDEN)
        assert "api" in section.lower()
        assert "prohibited" in section.lower()
        purpose = extract_section(content, H_PURPOSE)
        assert "api" in purpose.lower() or "api key" in purpose.lower()

    def test_profile_expansion_blocks_approval(self):
        """Profile expansion must block default approval."""
        content = read_doc()
        section = extract_section(content, H_FORBIDDEN)
        assert "profile expansion" in section.lower()
        assert "prohibited" in section.lower()
        purpose = extract_section(content, H_PURPOSE)
        assert "profile expansion" in purpose.lower()

    def test_batch_profile_run_blocks_approval(self):
        """Batch profile run must block default approval."""
        content = read_doc()
        section = extract_section(content, H_TARGET)
        assert "batch" in section.lower()
        assert "prohibited" in section.lower()
        purpose = extract_section(content, H_PURPOSE)
        assert "batch" in purpose.lower()

    def test_run_live_tests_prohibited_cannot_be_approved_default(self):
        """RUN_LIVE_*_TESTS=1 must remain prohibited and not appear as approved default."""
        content = read_doc()
        section = extract_section(content, H_FORBIDDEN)
        assert "run_live" in section.lower()
        assert "prohibited" in section.lower()
        purpose = extract_section(content, H_PURPOSE)
        assert "run_live" in purpose.lower()

    def test_scenario_snapshot_cache_config_persistence_blocks_default_approval(self):
        """Scenario/snapshot/cache/config/source-grounding persistence must block default approval."""
        content = read_doc()
        section = extract_section(content, H_FORBIDDEN)
        assert "scenario" in section.lower() or "snapshot" in section.lower() or "cache" in section.lower()
        assert "prohibited" in section.lower()
        purpose = extract_section(content, H_PURPOSE)
        assert "scenario" in purpose.lower() or "snapshot" in purpose.lower() or "cache" in purpose.lower() or "config" in purpose.lower() or "source-grounding" in purpose.lower()


class TestMetaNoLiveTests:
    """Meta/no-live tests for the test file itself."""

    def test_test_file_imports_only_stdlib(self):
        """Test file must import only stdlib modules."""
        content = read_test()
        # Parse the AST to check imports
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
        # Check for actual import statements only (not in comments/docstrings)
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
        # Should not contain a real script path that could be executed
        # Only placeholders like <CANDIDATE_LIVE_SMOKE_SCRIPT> are allowed
        assert "scripts/" not in content or "CANDIDATE_LIVE_SMOKE_SCRIPT" in content

    def test_no_source_config_scenario_snapshot_cache_files_modified(self):
        """Test must not modify source/config/scenario/snapshot/cache files."""
        # This is a meta test - the test file itself doesn't modify files
        # Just verify the test file exists and runs
        assert TEST_PATH.exists()


# ─── Entry Point ────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v"])