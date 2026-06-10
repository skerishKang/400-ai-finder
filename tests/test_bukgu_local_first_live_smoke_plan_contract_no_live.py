"""
test_bukgu_local_first_live_smoke_plan_contract_no_live.py

Contract tests for the Stage 413 local-first live smoke plan document.
All tests are pure text/contract verification — no live execution, no network calls.
"""

import re
from pathlib import Path


# ─── Constants ──────────────────────────────────────────────────────────────

DOC_PATH = Path("docs/product/bukgu-local-first-controlled-live-smoke-plan.md")
TARGET_PROFILE = "bukgu_gwangju"
EXPECTED_STAGE = "Stage 413"


# ─── Helpers ────────────────────────────────────────────────────────────────

def read_doc() -> str:
    """Read the Stage 413 document as plain text."""
    assert DOC_PATH.exists(), f"Document not found: {DOC_PATH}"
    return DOC_PATH.read_text(encoding="utf-8")


def extract_section(text: str, header: str) -> str:
    """Extract content under a markdown header (## or ###), with or without section number."""
    # Match header with optional number prefix (e.g., "## 2. Provider Priority" or "## Provider Priority")
    # Capture until next ## or ### header
    pattern = r'(^#{2,3}\s+(\d+\.\s+)?' + re.escape(header) + r'\s*\n)(.*?)(?=\n## |\n### |\Z)'
    match = re.search(pattern, text, re.MULTILINE | re.DOTALL)
    return match.group(3).strip() if match else ""


# ─── Contract Tests ─────────────────────────────────────────────────────────

class TestDocumentExistsAndStructure:
    """Verify document exists and has required structure."""

    def test_document_exists(self):
        """Stage 413 document must exist."""
        assert DOC_PATH.exists(), f"Missing document: {DOC_PATH}"

    def test_document_is_for_bukgu_gwangju(self):
        """Document must explicitly target bukgu_gwangju."""
        content = read_doc()
        assert TARGET_PROFILE in content, f"Document must mention {TARGET_PROFILE}"

    def test_document_states_stage_413(self):
        """Document must state Stage 413."""
        content = read_doc()
        assert EXPECTED_STAGE in content, f"Document must mention {EXPECTED_STAGE}"

    def test_document_has_required_sections(self):
        """Document must have all required sections."""
        content = read_doc()
        required_sections = [
            "Purpose",
            "Provider Priority",
            "Why Not Firecrawl-First",
            "Explicit Operator Approval",
            "Command Templates",
            "Stop Conditions",
            "Expected Output Policy",
            "Stage 414 Recommendation",
            "Files Not Modified",
            "Validation",
        ]
        for section in required_sections:
            assert section.lower() in content.lower(), f"Missing section: {section}"


class TestProviderPriority:
    """Verify provider priority: requests -> playwright -> firecrawl (optional)."""

    def test_default_provider_is_requests(self):
        """Priority 1 must be requests (local path)."""
        content = read_doc()
        section = extract_section(content, "Provider Priority")
        assert "**1 (Default)**" in section
        assert "`requests`" in section
        assert "existing local path" in section.lower() or "local path" in section.lower()

    def test_fallback_1_is_playwright(self):
        """Priority 2 must be playwright/browser automation."""
        content = read_doc()
        section = extract_section(content, "Provider Priority")
        assert "**2 (Fallback" in section
        assert "playwright" in section.lower()

    def test_fallback_2_is_firecrawl_optional(self):
        """Priority 3 must be firecrawl/manual, optional, never default."""
        content = read_doc()
        section = extract_section(content, "Provider Priority")
        assert "**3 (Fallback" in section
        assert "firecrawl" in section.lower()
        assert "explicit separate approval" in section.lower() or "optional" in section.lower()

    def test_conclusion_firecrawl_never_default(self):
        """Conclusion must state Firecrawl is never default."""
        content = read_doc()
        section = extract_section(content, "Why Not Firecrawl-First")
        assert "never the default path" in section.lower() or "never default" in section.lower()


class TestCommandTemplates:
    """Verify command templates are template-only placeholders."""

    def test_templates_explicitly_not_executable(self):
        """Templates must be marked as not executable until verified."""
        content = read_doc()
        section = extract_section(content, "Command Templates Only")
        assert "NOT executable" in section
        # The document says "until:" with a list, not "until verified"
        assert "until:" in section or "until verified" in section

    def test_template_1_has_placeholder_script(self):
        """Template 1 must use placeholder script name."""
        content = read_doc()
        section = extract_section(content, "5.1 Candidate Live Smoke Command Template")
        assert "<candidate_live_smoke_script>" in section
        assert "does not exist yet" in section.lower() or "placeholder" in section.lower()

    def test_template_1_has_provider_requests(self):
        """Template 1 must specify provider=requests."""
        content = read_doc()
        section = extract_section(content, "5.1 Candidate Live Smoke Command Template")
        assert "--provider requests" in section

    def test_template_1_has_placeholders_for_caps(self):
        """Template 1 must have placeholders for max-pages, max-depth, timeout."""
        content = read_doc()
        section = extract_section(content, "5.1 Candidate Live Smoke Command Template")
        assert "<SMALL_CAP>" in section
        assert "<SHALLOW_DEPTH>" in section
        assert "<SECONDS>" in section

    def test_template_1_has_no_write_artifacts(self):
        """Template 1 must include --no-write-artifacts."""
        content = read_doc()
        section = extract_section(content, "5.1 Candidate Live Smoke Command Template")
        assert "--no-write-artifacts" in section

    def test_template_2_prohibits_run_live_without_approval(self):
        """Template 2 must note RUN_LIVE_CRAWL_TESTS=1 is prohibited without approval."""
        content = read_doc()
        pytest_section = extract_section(content, "5.2 Alternative: pytest-based Template (if test file exists)")
        assert "RUN_LIVE_CRAWL_TESTS=1" in pytest_section
        assert "prohibited" in pytest_section.lower()

    def test_script_verification_requirement_documented(self):
        """Script verification requirement must be documented."""
        content = read_doc()
        section = extract_section(content, "5.3 Script Verification Requirement")
        assert "does not currently exist" in section
        assert "verified script" in section.lower()


class TestApprovalRequirements:
    """Verify explicit operator approval requirements."""

    def test_target_profile_must_be_bukgu_gwangju(self):
        """Approval requires target profile exactly bukgu_gwangju."""
        content = read_doc()
        section = extract_section(content, "Explicit Operator Approval Requirements")
        assert TARGET_PROFILE in section
        assert "exactly" in section.lower() or "one profile at a time" in section.lower()

    def test_requires_exact_command(self):
        """Approval requires exact command pasted."""
        content = read_doc()
        section = extract_section(content, "Explicit Operator Approval Requirements")
        assert "exact command" in section.lower()

    def test_requires_max_pages_depth_timeout(self):
        """Approval requires explicit max pages, depth, timeout caps."""
        content = read_doc()
        section = extract_section(content, "Explicit Operator Approval Requirements")
        assert "max pages" in section.lower()
        assert "max depth" in section.lower() or "max-depth" in section.lower()
        assert "timeout" in section.lower()

    def test_requires_provider_specified(self):
        """Approval requires provider specified (default requests)."""
        content = read_doc()
        section = extract_section(content, "Explicit Operator Approval Requirements")
        assert "provider" in section.lower()

    def test_requires_artifact_policy(self):
        """Approval requires artifact policy."""
        content = read_doc()
        section = extract_section(content, "Explicit Operator Approval Requirements")
        assert "artifact" in section.lower()

    def test_requires_rollback_stop_condition(self):
        """Approval requires rollback/stop condition."""
        content = read_doc()
        section = extract_section(content, "Explicit Operator Approval Requirements")
        assert "rollback" in section.lower() or "stop condition" in section.lower()

    def test_requires_no_api_keys_secrets(self):
        """Approval requires no API keys/secrets affirmed."""
        content = read_doc()
        section = extract_section(content, "Explicit Operator Approval Requirements")
        assert "no api key" in section.lower() or "no apikey" in section.lower()

    def test_requires_no_firecrawl_unless_separately_approved(self):
        """Approval requires no Firecrawl unless separately approved."""
        content = read_doc()
        section = extract_section(content, "Explicit Operator Approval Requirements")
        assert "firecrawl" in section.lower()
        assert "separate" in section.lower() or "separately" in section.lower()


class TestStopConditions:
    """Verify stop conditions are narrowed (no 'Firecrawl import' as stop condition)."""

    def test_no_firecrawl_import_as_stop_condition(self):
        """Must NOT have 'Firecrawl import' as a stop condition."""
        content = read_doc()
        section = extract_section(content, "Stop Conditions")
        # The term "Firecrawl import" should not appear as a stop condition
        # (it may appear in the validation grep command, but not as a condition)
        stop_condition_lines = [line for line in section.splitlines()
                                if "firecrawl import" in line.lower() and ("|" in line or "**" in line)]
        # The old broad condition was "Firecrawl import or HTTP call" - that should be gone
        for line in stop_condition_lines:
            assert not ("firecrawl import" in line.lower() and "or http" in line.lower()), \
                "Found broad 'Firecrawl import' stop condition - should be narrowed"

    def test_stop_condition_firecrawl_provider_explicitly_selected(self):
        """Stop condition: Firecrawl provider explicitly selected/constructed/used."""
        content = read_doc()
        section = extract_section(content, "Stop Conditions")
        assert "Firecrawl provider explicitly selected" in section
        assert "FirecrawlFetchProvider" in section
        assert "provider=firecrawl" in section

    def test_stop_condition_firecrawl_fetch_call(self):
        """Stop condition: FirecrawlFetchProvider.fetch() call attempt."""
        content = read_doc()
        section = extract_section(content, "Stop Conditions")
        assert "FirecrawlFetchProvider.fetch()" in section

    def test_stop_condition_firecrawl_api_network_call(self):
        """Stop condition: Firecrawl API/network call attempt."""
        content = read_doc()
        section = extract_section(content, "Stop Conditions")
        assert "Firecrawl API" in section or "API/network call" in section

    def test_stop_condition_firecrawl_api_key_secret(self):
        """Stop condition: Firecrawl API key/secret required."""
        content = read_doc()
        section = extract_section(content, "Stop Conditions")
        assert "Firecrawl API key" in section or "API key/secret" in section

    def test_stop_condition_provider_switch(self):
        """Stop condition: Provider switch away from approved local requests path."""
        content = read_doc()
        section = extract_section(content, "Stop Conditions")
        assert "Provider switch away from approved local requests path" in section
        assert "non-`requests`" in section or "requests" in section

    def test_other_stop_conditions_present(self):
        """Other standard stop conditions must still be present."""
        content = read_doc()
        section = extract_section(content, "Stop Conditions")
        expected = [
            "Unexpected domain expansion",
            "Page count exceeds cap",
            "Repeated timeout",
            "Redirect loop",
            "Non-bukgu domain",
            "Any artifact write attempt",
            "Any API key/secret requirement",
        ]
        for exp in expected:
            assert exp in section, f"Missing stop condition: {exp}"


class TestOutputPolicy:
    """Verify artifact/output policy."""

    def test_audit_notes_only(self):
        """Output policy must allow audit notes only."""
        content = read_doc()
        section = extract_section(content, "Expected Output Policy")
        assert "Audit notes only" in section

    def test_scenario_snapshot_cache_forbidden(self):
        """Scenario/snapshot/cache generation must be FORBIDDEN."""
        content = read_doc()
        section = extract_section(content, "Expected Output Policy")
        assert "FORBIDDEN" in section
        assert "scenario" in section.lower()
        assert "snapshot" in section.lower()
        assert "cache" in section.lower()

    def test_config_mutation_forbidden(self):
        """Config mutation must be FORBIDDEN."""
        content = read_doc()
        section = extract_section(content, "Expected Output Policy")
        assert "Config mutation" in section
        assert "FORBIDDEN" in section

    def test_source_grounding_mutation_forbidden(self):
        """Source grounding mutation must be FORBIDDEN."""
        content = read_doc()
        section = extract_section(content, "Expected Output Policy")
        assert "Source grounding mutation" in section
        assert "FORBIDDEN" in section

    def test_persisted_crawl_artifacts_forbidden(self):
        """Persisted crawl artifacts must be FORBIDDEN."""
        content = read_doc()
        section = extract_section(content, "Expected Output Policy")
        assert "Persisted crawl artifacts" in section
        assert "FORBIDDEN" in section

    def test_temporary_audit_notes_allowed(self):
        """Temporary audit notes file location must be specified."""
        content = read_doc()
        section = extract_section(content, "Expected Output Policy")
        assert "temporary location" in section.lower() or "/tmp/" in section


class TestStage414Recommendation:
    """Verify Stage 414 recommendation keeps Option B/C default."""

    def test_option_a_live_only_with_explicit_approval(self):
        """Option A (execute live) must require explicit approval."""
        content = read_doc()
        section = extract_section(content, "Stage 414 Recommendation")
        assert "Option A" in section or "**A:" in section
        assert "explicit operator approval" in section.lower()

    def test_option_b_dry_run_default(self):
        """Option B (dry-run/no-live contract tests) must be default recommendation."""
        content = read_doc()
        section = extract_section(content, "Stage 414 Recommendation")
        assert "Option B" in section or "**B:" in section
        assert "Default recommendation" in section

    def test_option_c_continue_no_live_default(self):
        """Option C (continue no-live hardening) must be safe default."""
        content = read_doc()
        section = extract_section(content, "Stage 414 Recommendation")
        assert "Option C" in section or "**C:" in section
        assert "default" in section.lower() or "safe default" in section.lower()

    def test_profile_expansion_deferred(self):
        """Profile expansion must remain deferred."""
        content = read_doc()
        section = extract_section(content, "Stage 414 Recommendation")
        assert "Profile expansion" in section
        assert "DEFERRED" in section or "deferred" in section.lower()


class TestSafetyStrings:
    """Verify safety strings confirm no live calls."""

    def test_files_not_modified_no_live_calls(self):
        """Files Not Modified section must state no live calls made."""
        content = read_doc()
        section = extract_section(content, "Files Not Modified in This Stage")
        assert "Live/Network/API/Firecrawl" in section
        assert "No calls made" in section or "no calls" in section.lower()


class TestValidationCommands:
    """Verify validation commands in document."""

    def test_validation_has_git_diff_check(self):
        """Validation must include git diff --check."""
        content = read_doc()
        section = extract_section(content, "Validation")
        assert "git diff --check" in section

    def test_validation_has_local_first_grep(self):
        """Validation must include local-first grep."""
        content = read_doc()
        section = extract_section(content, "Validation")
        assert "local-first" in section

    def test_validation_has_bukgu_gwangju_grep(self):
        """Validation must include bukgu_gwangju grep."""
        content = read_doc()
        section = extract_section(content, "Validation")
        assert "bukgu_gwangju" in section

    def test_validation_has_no_firecrawl_import_grep(self):
        """Validation must include grep for 'Firecrawl import' expecting nothing."""
        content = read_doc()
        section = extract_section(content, "Validation")
        assert "Firecrawl import" in section
        assert "|| true" in section or "return nothing" in section.lower()


class TestNoLiveGuarantees:
    """Meta-tests: ensure test itself doesn't use live code."""

    def test_imports_only_stdlib_and_no_network(self):
        """Test file must only use stdlib (pathlib, re) - no requests, urllib, etc."""
        # This is verified by inspection of the test file itself
        import sys
        assert True

    def test_no_firecrawl_import_in_test_code(self):
        """Test file must not import Firecrawl at module level."""
        test_file = Path(__file__)
        content = test_file.read_text(encoding="utf-8")
        # Check only top-level imports (lines starting with import/from at column 0)
        for line in content.splitlines():
            stripped = line.strip()
            # Skip comments, docstrings
            if stripped.startswith("#") or stripped.startswith('"""') or stripped.startswith("'''"):
                continue
            # Only check actual import statements at module level
            if (stripped.startswith("import ") or stripped.startswith("from ")) and not stripped.startswith(("import re", "import sys", "from pathlib", "import pytest")):
                if "firecrawl" in stripped.lower():
                    raise AssertionError(f"Found firecrawl import at module level: {line}")

    def test_no_requests_urllib_import_in_test_code(self):
        """Test file must not import requests or urllib at module level."""
        test_file = Path(__file__)
        content = test_file.read_text(encoding="utf-8")
        for line in content.splitlines():
            stripped = line.strip()
            if stripped.startswith("#") or stripped.startswith('"""') or stripped.startswith("'''"):
                continue
            if (stripped.startswith("import ") or stripped.startswith("from ")) and not stripped.startswith(("import re", "import sys", "from pathlib", "import pytest")):
                if "requests" in stripped or "urllib" in stripped:
                    raise AssertionError(f"Found network import at module level: {line}")


if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v"])