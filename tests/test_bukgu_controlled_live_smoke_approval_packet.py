"""
test_bukgu_controlled_live_smoke_approval_packet.py

Contract tests for the Stage 417 bukgu_gwangju controlled live smoke approval packet document.
Verifies the document exists, contains required content, and preserves safety boundaries.

All tests are pure text/contract verification — no live execution, no network calls.
"""

import re
from pathlib import Path


# ─── Constants ──────────────────────────────────────────────────────────────

DOC_PATH = Path("docs/product/bukgu-controlled-live-smoke-approval-packet.md")
TARGET_PROFILE = "bukgu_gwangju"


# ─── Helpers ────────────────────────────────────────────────────────────────

def read_doc() -> str:
    """Read the approval packet document as plain text."""
    assert DOC_PATH.exists(), f"Document not found: {DOC_PATH}"
    return DOC_PATH.read_text(encoding="utf-8")


def extract_section(text: str, header: str) -> str:
    """Extract content under a markdown header (## or ###), with or without section number.
    Captures the full section including all sub-sections until the next same-level or higher header."""
    # Handle both regular dash and em dash in headers
    escaped_header = re.escape(header).replace(r"\-", r"[\-\u2014]")
    # For ## headers, capture until next ## or end; for ### headers, capture until next ###, ##, or end
    if header in ["Purpose and Scope", "Exact Target Policy", "Provider Policy", "Required Approval Fields",
                  "Command Template", "Forbidden Defaults", "Default Stop / Rollback Conditions",
                  "Future Post-Run Report Checklist", "Cross-References", "Validation"]:
        # Top-level sections (##) - capture until next ## or end
        pattern = r'(^#{2}\s+(\d+\.\s+)?' + escaped_header + r'\s*\n)(.*?)(?=\n## |\Z)'
    else:
        # Sub-sections (###) - capture until next ###, ##, or end
        pattern = r'(^#{3}\s+(\d+\.\s+)?' + escaped_header + r'\s*\n)(.*?)(?=\n## |\n### |\Z)'
    match = re.search(pattern, text, re.MULTILINE | re.DOTALL)
    return match.group(3).strip() if match else ""


# ─── Exact headers from document ────────────────────────────────────────────

H_STAGE = "Stage"
H_PURPOSE = "Purpose and Scope"
H_TARGET = "Exact Target Policy"
H_PROVIDER = "Provider Policy"
H_FIELDS = "Required Approval Fields"
H_TEMPLATE = "Command Template"
H_FORBIDDEN = "Forbidden Defaults"
H_STOP = "Default Stop / Rollback Conditions"
H_POST_RUN = "Future Post-Run Report Checklist"
H_CROSS_REF = "Cross-References"
H_VALIDATION = "Validation"


# ─── Contract Tests ─────────────────────────────────────────────────────────

class TestDocumentExistsAndStructure:
    """Verify document exists and has required structure."""

    def test_document_exists(self):
        """Approval packet document must exist."""
        assert DOC_PATH.exists(), f"Missing document: {DOC_PATH}"

    def test_document_targets_bukgu_gwangju(self):
        """Document must explicitly target bukgu_gwangju."""
        content = read_doc()
        assert TARGET_PROFILE in content, f"Document must mention {TARGET_PROFILE}"

    def test_document_states_stage_417(self):
        """Document must state this is Stage 417."""
        content = read_doc()
        assert "Stage 417" in content

    def test_document_declares_approval_preflight_only(self):
        """Document must clearly state it's an approval/preflight packet only."""
        content = read_doc()
        section = extract_section(content, H_PURPOSE)
        assert "approval/preflight packet" in section.lower()
        assert "does not approve" in section.lower() or "does not execute" in section.lower()
        assert "blocked" in section.lower()

    def test_document_has_required_sections(self):
        """Document must have all required sections."""
        content = read_doc()
        required_sections = [
            "Purpose and Scope",
            "Exact Target Policy",
            "Provider Policy",
            "Required Approval Fields",
            "Command Template",
            "Forbidden Defaults",
            "Default Stop / Rollback Conditions",
            "Future Post-Run Report Checklist",
            "Cross-References",
            "Validation",
        ]
        for section in required_sections:
            assert section.lower() in content.lower(), f"Missing section: {section}"


class TestExactTargetPolicy:
    """Verify exact target policy is properly documented."""

    def test_target_profile_bukgu_only(self):
        """Target must be bukgu_gwangju only."""
        content = read_doc()
        section = extract_section(content, H_TARGET)
        assert "bukgu_gwangju" in section.lower()
        assert "only profile allowed" in section.lower() or "only" in section.lower()

    def test_batch_profile_run_prohibited(self):
        """Batch profile run must be prohibited."""
        content = read_doc()
        section = extract_section(content, H_TARGET)
        assert "batch" in section.lower()
        assert "prohibited" in section.lower() or "not permitted" in section.lower()

    def test_profile_expansion_not_permitted(self):
        """Profile expansion must not be permitted in this approval."""
        content = read_doc()
        section = extract_section(content, H_TARGET)
        assert "expansion" in section.lower()
        assert "not permitted" in section.lower() or "separate" in section.lower()


class TestProviderPolicy:
    """Verify provider policy is properly documented."""

    def test_requests_is_default(self):
        """Requests must be documented as default/local-first provider."""
        content = read_doc()
        section = extract_section(content, H_PROVIDER)
        assert "requests" in section.lower()
        assert "default" in section.lower() or "local-first" in section.lower()

    def test_firecrawl_not_default(self):
        """Firecrawl must be documented as not default."""
        content = read_doc()
        section = extract_section(content, H_PROVIDER)
        assert "firecrawl" in section.lower()
        assert "not default" in section.lower() or "separately unapproved" in section.lower()

    def test_firecrawl_fallback_separately_unapproved(self):
        """Firecrawl/manual fallback must be separately unapproved."""
        content = read_doc()
        section = extract_section(content, H_PROVIDER)
        assert "separately unapproved" in section.lower() or "separate approval" in section.lower()

    def test_no_api_keys_allowed(self):
        """No API keys/secrets allowed in this packet."""
        content = read_doc()
        section = extract_section(content, H_PROVIDER)
        assert "api" in section.lower()
        assert "prohibited" in section.lower() or "not allowed" in section.lower()


class TestRequiredApprovalFields:
    """Verify all required approval fields are present."""

    def test_all_12_fields_present(self):
        """All 12 mandatory approval fields must be listed."""
        content = read_doc()
        section = extract_section(content, H_FIELDS)
        required_fields = [
            "approver",
            "approval timestamp",
            "target profile",
            "exact command",
            "max pages",
            "max depth",
            "timeout",
            "retry policy",
            "output location",
            "expected diff policy",
            "stop",
            "rollback",
            "no-persist",
            "confirmation",
        ]
        for field in required_fields:
            assert field.lower() in section.lower(), f"Missing approval field: {field}"

    def test_fields_marked_required(self):
        """Fields should be marked as required."""
        content = read_doc()
        section = extract_section(content, H_FIELDS)
        assert "mandatory" in section.lower() or "required" in section.lower()


class TestCommandTemplate:
    """Verify command template requirements."""

    def test_template_marked_non_executable(self):
        """Template must be clearly marked as non-executable placeholder."""
        content = read_doc()
        section = extract_section(content, H_TEMPLATE)
        assert "non-executable" in section.lower() or "placeholder" in section.lower()
        assert "do not execute" in section.lower() or "not executable" in section.lower()

    def test_no_runnable_script_path(self):
        """Template must not include a runnable verified script path."""
        content = read_doc()
        section = extract_section(content, H_TEMPLATE)
        # The template should have <CANDIDATE_LIVE_SMOKE_SCRIPT> placeholder
        assert "CANDIDATE_LIVE_SMOKE_SCRIPT" in section or "placeholder" in section.lower()

    def test_no_run_live_tests(self):
        """Template must not set RUN_LIVE_*_TESTS=1."""
        content = read_doc()
        section = extract_section(content, H_TEMPLATE)
        assert "RUN_LIVE" in section
        assert "must not" in section.lower() or "prohibited" in section.lower()

    def test_placeholders_for_caps(self):
        """Template must use placeholders for caps, not actual values."""
        content = read_doc()
        section = extract_section(content, H_TEMPLATE)
        placeholders = [
            "MAX_PAGES",
            "MAX_DEPTH",
            "TIMEOUT",
            "RETRY_MAX",
            "BACKOFF",
            "OUTPUT_PATH",
        ]
        for ph in placeholders:
            assert ph in section, f"Missing placeholder: {ph}"

    def test_requests_provider_fixed(self):
        """Template must fix provider to requests."""
        content = read_doc()
        section = extract_section(content, H_TEMPLATE)
        assert "--provider requests" in section

    def test_no_write_artifacts_flag(self):
        """Template must include --no-write-artifacts."""
        content = read_doc()
        section = extract_section(content, H_TEMPLATE)
        assert "--no-write-artifacts" in section

    def test_dry_run_marker(self):
        """Template should include dry-run marker placeholder."""
        content = read_doc()
        section = extract_section(content, H_TEMPLATE)
        assert "dry-run" in section.lower()

    def test_conditional_on_script_verification(self):
        """Approval should be conditional on script verification if no script exists."""
        content = read_doc()
        section = extract_section(content, H_TEMPLATE)
        assert "verified executable script exists" in section.lower() or "conditional" in section.lower()


class TestForbiddenDefaults:
    """Verify forbidden defaults are explicitly listed."""

    def test_run_live_prohibited(self):
        """RUN_LIVE_*_TESTS=1 must be prohibited."""
        content = read_doc()
        section = extract_section(content, H_FORBIDDEN)
        assert "RUN_LIVE" in section
        assert "prohibited" in section.lower()

    def test_api_keys_prohibited(self):
        """API keys/secrets must be prohibited."""
        content = read_doc()
        section = extract_section(content, H_FORBIDDEN)
        assert "api" in section.lower()
        assert "prohibited" in section.lower()

    def test_firecrawl_provider_switch_prohibited(self):
        """Firecrawl/provider switch must be prohibited."""
        content = read_doc()
        section = extract_section(content, H_FORBIDDEN)
        assert "firecrawl" in section.lower()
        assert "prohibited" in section.lower()

    def test_no_persist_mutation_prohibited(self):
        """Scenario/snapshot/cache/config/source-grounding mutation must be prohibited."""
        content = read_doc()
        section = extract_section(content, H_FORBIDDEN)
        assert "scenario" in section.lower() or "snapshot" in section.lower() or "cache" in section.lower()
        assert "prohibited" in section.lower()

    def test_profile_expansion_prohibited(self):
        """Profile expansion must be prohibited."""
        content = read_doc()
        section = extract_section(content, H_FORBIDDEN)
        assert "profile expansion" in section.lower()
        assert "prohibited" in section.lower()

    def test_no_executable_script_creation(self):
        """Executable script creation must be prohibited as part of this packet."""
        content = read_doc()
        section = extract_section(content, H_FORBIDDEN)
        assert "executable" in section.lower()
        assert "prohibited" in section.lower()

    def test_no_live_calls_in_docs_tests(self):
        """Live calls in docs/tests must be prohibited."""
        content = read_doc()
        section = extract_section(content, H_FORBIDDEN)
        assert "live" in section.lower()
        assert "prohibited" in section.lower()


class TestStopRollbackConditions:
    """Verify default stop/rollback conditions are documented."""

    def test_all_stop_conditions_present(self):
        """All 10 default stop conditions must be listed."""
        content = read_doc()
        section = extract_section(content, H_STOP)
        conditions = [
            "unexpected domain expansion",
            "page cap",
            "depth cap",
            "repeated timeout",
            "redirect loop",
            "non-bukgu domain",
            "artifact write",
            "api key",
            "firecrawl",
            "provider switch",
        ]
        for cond in conditions:
            assert cond.lower() in section.lower(), f"Missing stop condition: {cond}"


class TestPostRunReportChecklist:
    """Verify post-run report checklist is present."""

    def test_all_checklist_items_present(self):
        """All 9 post-run report items must be listed."""
        content = read_doc()
        section = extract_section(content, H_POST_RUN)
        items = [
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
        for item in items:
            assert item.lower() in section.lower(), f"Missing post-run item: {item}"


class TestCrossReferences:
    """Verify cross-references to prior stages."""

    def test_stage_413_referenced(self):
        """Must reference Stage 413 local-first plan."""
        content = read_doc()
        section = extract_section(content, H_CROSS_REF)
        assert "413" in section
        assert "local-first" in section.lower()

    def test_stage_416_referenced(self):
        """Must reference Stage 416 closure audit."""
        content = read_doc()
        section = extract_section(content, H_CROSS_REF)
        assert "416" in section
        assert "closure" in section.lower()

    def test_live_smoke_boundary_referenced(self):
        """Must reference controlled live smoke boundary."""
        content = read_doc()
        section = extract_section(content, H_CROSS_REF)
        assert "live smoke boundary" in section.lower() or "controlled-live-smoke-boundary" in section.lower()

    def test_onboarding_boundary_referenced(self):
        """Must reference onboarding boundary for profile expansion."""
        content = read_doc()
        section = extract_section(content, H_CROSS_REF)
        assert "onboarding" in section.lower()


class TestSafetyStrings:
    """Verify safety strings confirm no live calls."""

    def test_validation_confirms_no_live_calls(self):
        """Validation section must confirm no live calls executed."""
        content = read_doc()
        section = extract_section(content, H_VALIDATION)
        assert "no live" in section.lower()
        assert "no live/network/api/firecrawl" in section.lower()

    def test_validation_confirms_no_api_keys(self):
        """Validation must confirm no API keys/secrets."""
        content = read_doc()
        section = extract_section(content, H_VALIDATION)
        assert "no api" in section.lower()

    def test_validation_confirms_no_run_live(self):
        """Validation must confirm no RUN_LIVE_*_TESTS=1."""
        content = read_doc()
        section = extract_section(content, H_VALIDATION)
        assert "run_live" in section.lower()

    def test_validation_confirms_no_config_changes(self):
        """Validation must confirm no config/src/scenario/snapshot/cache changes."""
        content = read_doc()
        section = extract_section(content, H_VALIDATION)
        assert "config" in section.lower()
        assert "scenario" in section.lower()
        assert "snapshot" in section.lower()
        assert "cache" in section.lower()

    def test_validation_confirms_no_executable_script(self):
        """Validation must confirm no executable live smoke script."""
        content = read_doc()
        section = extract_section(content, H_VALIDATION)
        assert "executable" in section.lower()
        assert "live smoke script" in section.lower()

    def test_validation_confirms_no_profile_expansion(self):
        """Validation must confirm no profile expansion."""
        content = read_doc()
        section = extract_section(content, H_VALIDATION)
        assert "profile expansion" in section.lower()


class TestProhibitedWordingNotPresent:
    """Verify document does not contain prohibited wording suggesting unauthorized actions."""

    def _get_main_content(self, content: str) -> str:
        """Get document content excluding sections that list prohibited things as prohibited."""
        # Remove the Post-Run Evidence Review Gate section (Stage 419) which lists
        # prohibited things as prohibited (e.g., "No automatic promotion...")
        # This is a ### sub-section under Purpose and Scope
        pattern = r'(^### Post-Run Evidence Review Gate \(Stage 419\)\s*\n)(.*?)(?=\n## |\n### |\Z)'
        match = re.search(pattern, content, re.MULTILINE | re.DOTALL)
        if match:
            return content[:match.start()] + content[match.end():]
        return content

    def test_no_live_approved_language(self):
        """Document must not state live is already approved."""
        content = read_doc()
        main = self._get_main_content(content)
        prohibited = [
            "live smoke is approved",
            "live execution is approved",
            "approved for live",
            "live validation approved",
            "live smoke approved",
        ]
        for phrase in prohibited:
            assert phrase.lower() not in main.lower(), f"Prohibited phrase found: {phrase}"

    def test_no_firecrawl_default_language(self):
        """Document must not state Firecrawl is default."""
        content = read_doc()
        main = self._get_main_content(content)
        prohibited = [
            "firecrawl is the default",
            "firecrawl is default",
            "default firecrawl",
            "firecrawl first",
            "firecrawl-first",
        ]
        for phrase in prohibited:
            assert phrase.lower() not in main.lower(), f"Prohibited Firecrawl-default phrasing: {phrase}"

    def test_no_profile_expansion_approved(self):
        """Document must not state profile expansion is approved."""
        content = read_doc()
        main = self._get_main_content(content)
        prohibited = [
            "profile expansion is approved",
            "profile expansion approved",
            "approved profile expansion",
            "fourth profile approved",
            "fifth profile approved",
        ]
        for phrase in prohibited:
            assert phrase.lower() not in main.lower(), f"Prohibited profile expansion phrasing: {phrase}"

    def test_no_auto_promotion_language(self):
        """Document must not state auto-promotion is enabled."""
        content = read_doc()
        main = self._get_main_content(content)
        prohibited = [
            "auto-promotion",
            "automatic promotion",
            "auto promote",
            "automatically promoted",
            "promotion is automatic",
        ]
        for phrase in prohibited:
            assert phrase.lower() not in main.lower(), f"Prohibited auto-promotion phrasing: {phrase}"

    def test_no_run_live_default_language(self):
        """Document must not suggest RUN_LIVE can be enabled by default."""
        content = read_doc()
        main = self._get_main_content(content)
        main_lower = main.lower()
        prohibited = [
            "run_live_crawl_tests=1 can be enabled",
            "run_live_crawl_tests=1 by default",
            "run_live_crawl_tests=1 enabled",
            "run_live_crawl_tests=1 default",
            "run_live_*_tests=1 may be executed",
        ]
        for phrase in prohibited:
            assert phrase not in main_lower, f"Prohibited RUN_LIVE phrasing: {phrase}"


# ─── Entry Point ────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v"])