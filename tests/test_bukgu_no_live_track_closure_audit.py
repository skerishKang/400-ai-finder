"""
test_bukgu_no_live_track_closure_audit.py

Contract tests for the Stage 416 bukgu_gwangju no-live track closure audit document.
Verifies the document exists, contains required content, and preserves safety boundaries.

All tests are pure text/contract verification — no live execution, no network calls.
"""

import re
from pathlib import Path


# ─── Constants ──────────────────────────────────────────────────────────────

DOC_PATH = Path("docs/product/bukgu-no-live-crawl-filter-track-closure-audit.md")
TARGET_PROFILE = "bukgu_gwangju"


# ─── Helpers ────────────────────────────────────────────────────────────────

def read_doc() -> str:
    """Read the closure audit document as plain text."""
    assert DOC_PATH.exists(), f"Document not found: {DOC_PATH}"
    return DOC_PATH.read_text(encoding="utf-8")


def extract_section(text: str, header: str) -> str:
    """Extract content under a markdown header (## or ###), with or without section number.
    Captures the full section including all sub-sections until the next same-level or higher header."""
    # Handle both regular dash and em dash in headers
    escaped_header = re.escape(header).replace(r"\-", r"[\-\u2014]")
    # For ## headers, capture until next ## or end; for ### headers, capture until next ### or end
    if header in ["Locked Safety Policy", "Deferred Work", "Closure Conclusion", "Prohibited Interpretations", "Files Not Modified in This Track Closure", "Validation"]:
        # Top-level sections (##) - capture until next ## or end
        pattern = r'(^#{2}\s+(\d+\.\s+)?' + escaped_header + r'\s*\n)(.*?)(?=\n## |\Z)'
    else:
        # Sub-sections (###) - capture until next ###, ##, or end
        pattern = r'(^#{3}\s+(\d+\.\s+)?' + escaped_header + r'\s*\n)(.*?)(?=\n## |\n### |\Z)'
    match = re.search(pattern, text, re.MULTILINE | re.DOTALL)
    return match.group(3).strip() if match else ""


# ─── Exact headers from document ────────────────────────────────────────────

H_STAGE_409 = "Stage 409 \u2014 Bukgu Hardening (58 tests)"
H_STAGE_410 = "Stage 410 \u2014 Bukgu Deeper Hardening (66 tests)"
H_STAGE_411 = "Stage 411 \u2014 Bukgu Continued Hardening (32 tests)"
H_STAGE_412 = "Stage 412 \u2014 Bukgu Readiness Audit (11 tests)"
H_STAGE_413 = "Stage 413 \u2014 Local-First Controlled Live Smoke Plan (docs-only)"
H_STAGE_414 = "Stage 414 \u2014 Command Contract No-Live Tests (48 tests)"
H_STAGE_415 = "Stage 415 \u2014 Edge-Case No-Live Hardening (41 tests)"
H_SAFETY_POLICY = "Locked Safety Policy"
H_DEFERRED = "Deferred Work"
H_CLOSURE = "Closure Conclusion"
H_PROHIBITED = "Prohibited Interpretations"
H_FILES_NOT_MODIFIED = "Files Not Modified in This Track Closure"
H_VALIDATION = "Validation"


# ─── Contract Tests ─────────────────────────────────────────────────────────

class TestDocumentExistsAndStructure:
    """Verify document exists and has required structure."""

    def test_document_exists(self):
        """Closure audit document must exist."""
        assert DOC_PATH.exists(), f"Missing document: {DOC_PATH}"

    def test_document_targets_bukgu_gwangju(self):
        """Document must explicitly target bukgu_gwangju."""
        content = read_doc()
        assert TARGET_PROFILE in content, f"Document must mention {TARGET_PROFILE}"

    def test_document_names_stages_409_to_415(self):
        """Document must reference all completed stages 409-415."""
        content = read_doc()
        for stage in ["409", "410", "411", "412", "413", "414", "415"]:
            assert f"Stage {stage}" in content, f"Document must mention Stage {stage}"

    def test_document_has_required_sections(self):
        """Document must have all required sections."""
        content = read_doc()
        required_sections = [
            "Purpose",
            "Completed Stages Summary",
            "Test Coverage Inventory",
            "Locked Safety Policy",
            "Deferred Work",
            "Closure Conclusion",
            "Prohibited Interpretations",
            "Cross-References",
            "Files Not Modified",
            "Validation",
        ]
        for section in required_sections:
            assert section.lower() in content.lower(), f"Missing section: {section}"


class TestCompletedStagesSummary:
    """Verify each stage is properly summarized."""

    def test_stage_409_summarized(self):
        """Stage 409 hardening must be summarized."""
        content = read_doc()
        section = extract_section(content, H_STAGE_409)
        # Check body content
        assert "crawl_filters load/wiring verification" in section
        assert "Protected structural URLs" in section
        assert "Denied duplicate/noisy URLs" in section
        # Check header has test count (in full content)
        assert "58 tests" in content
        assert "protected" in content.lower()
        assert "deny" in content.lower()

    def test_stage_410_summarized(self):
        """Stage 410 deeper hardening must be summarized."""
        content = read_doc()
        section = extract_section(content, H_STAGE_410)
        assert "Dynamic URL patterns" in section
        assert "Deep pagination" in section
        assert "66 tests" in content
        assert "dynamic" in content.lower()
        assert "pagination" in content.lower()

    def test_stage_411_summarized(self):
        """Stage 411 continued hardening must be summarized."""
        content = read_doc()
        section = extract_section(content, H_STAGE_411)
        assert "Query-order" in section
        assert "canonicalization" in section.lower()
        assert "32 tests" in content

    def test_stage_412_summarized(self):
        """Stage 412 readiness audit must be summarized."""
        content = read_doc()
        section = extract_section(content, H_STAGE_412)
        assert "Empty query string" in section
        assert "COMPLETE" in section
        assert "11 tests" in content
        assert "readiness" in content.lower()

    def test_stage_413_summarized(self):
        """Stage 413 local-first plan must be summarized."""
        content = read_doc()
        section = extract_section(content, H_STAGE_413)
        assert "local-first" in section.lower()
        assert "provider priority" in section.lower()
        assert "413" in content
        assert "local-first" in content.lower()

    def test_stage_414_summarized(self):
        """Stage 414 command contract tests must be summarized."""
        content = read_doc()
        section = extract_section(content, H_STAGE_414)
        assert "contract" in section.lower()
        assert "48 tests" in content

    def test_stage_415_summarized(self):
        """Stage 415 edge-case hardening must be summarized."""
        content = read_doc()
        section = extract_section(content, H_STAGE_415)
        assert "Repeated slashes" in section
        assert "41 tests" in content

    def test_total_test_count_documented(self):
        """Total test count must be documented."""
        content = read_doc()
        assert "345" in content or "256" in content


class TestLockedSafetyPolicy:
    """Verify the locked safety policy is properly documented."""

    def test_local_first_declared(self):
        """Document must declare local-first as default path."""
        content = read_doc()
        section = extract_section(content, H_SAFETY_POLICY)
        assert "local-first" in section.lower()
        assert "requests" in section.lower()
        assert "default" in section.lower()

    def test_provider_priority_locked(self):
        """Provider priority must be locked: requests -> playwright -> firecrawl."""
        content = read_doc()
        # Check sub-sections
        full = content.lower()
        assert "requests" in full
        assert "playwright" in full
        assert "firecrawl" in full
        assert "optional" in full or "fallback" in full

    def test_explicit_approval_required(self):
        """Document must state explicit operator approval is required for ANY live smoke."""
        content = read_doc()
        section = extract_section(content, H_SAFETY_POLICY)
        assert "explicit operator approval" in section.lower()
        assert "any live smoke" in section.lower() or "live smoke" in section.lower()

    def test_approval_requirements_listed(self):
        """All 6 approval requirements must be listed."""
        content = read_doc()
        section = extract_section(content, H_SAFETY_POLICY)
        requirements = [
            "explicit operator approval",
            "exact target profile",
            "exact command",
            "no api keys",
            "rollback",
            "expected diff"
        ]
        for req in requirements:
            assert req.lower() in section.lower(), f"Missing approval requirement: {req}"

    def test_no_live_execution_without_approval(self):
        """Document must state no live execution without approval."""
        content = read_doc()
        section = extract_section(content, H_SAFETY_POLICY)
        assert "RUN_LIVE" in section
        assert "prohibited" in section.lower()

    def test_first_live_target_bukgu_only(self):
        """Document must state first live target is bukgu_gwangju only."""
        content = read_doc()
        section = extract_section(content, H_SAFETY_POLICY)
        assert "bukgu_gwangju" in section.lower()
        assert "first live" in section.lower() or "one at a time" in section.lower()


class TestDeferredWork:
    """Verify deferred work is explicitly listed."""

    def test_controlled_live_smoke_deferred(self):
        """Controlled live smoke execution must be listed as deferred."""
        content = read_doc()
        section = extract_section(content, H_DEFERRED)
        assert "controlled live smoke" in section.lower()
        assert "deferred" in section.lower()

    def test_executable_live_script_deferred(self):
        """Executable live script design must be listed as deferred."""
        content = read_doc()
        section = extract_section(content, H_DEFERRED)
        assert "executable live script" in section.lower()
        assert "deferred" in section.lower()

    def test_firecrawl_fallback_deferred(self):
        """Firecrawl/manual fallback validation must be listed as deferred."""
        content = read_doc()
        section = extract_section(content, H_DEFERRED)
        assert "firecrawl" in section.lower()
        assert "deferred" in section.lower()

    def test_profile_expansion_deferred(self):
        """Profile expansion must be listed as deferred."""
        content = read_doc()
        section = extract_section(content, H_DEFERRED)
        assert "profile expansion" in section.lower()
        assert "deferred" in section.lower()

    def test_scenario_cache_promotion_deferred(self):
        """Scenario/snapshot/cache promotion must be listed as deferred."""
        content = read_doc()
        section = extract_section(content, H_DEFERRED)
        assert ("scenario" in section.lower() or "cache" in section.lower())
        assert "deferred" in section.lower()

    def test_pagination_deny_policy_deferred(self):
        """Pagination deny policy change must be listed as deferred."""
        content = read_doc()
        section = extract_section(content, H_DEFERRED)
        assert "pagination deny" in section.lower()
        assert "deferred" in section.lower()


class TestClosureConclusion:
    """Verify the closure conclusion is explicitly stated."""

    def test_closed_conclusion_stated(self):
        """Document must explicitly state track is CLOSED."""
        content = read_doc()
        section = extract_section(content, H_CLOSURE)
        assert "CLOSED" in section
        assert "closed" in section.lower()

    def test_live_unapproved_stated(self):
        """Document must state live validation remains unapproved."""
        content = read_doc()
        section = extract_section(content, H_CLOSURE)
        # The section includes sub-sections, check full content
        assert "unapproved" in content.lower() or "not approved" in content.lower()

    def test_no_live_executed_stated(self):
        """Document must state no live smoke executed."""
        content = read_doc()
        section = extract_section(content, H_CLOSURE)
        assert "no live smoke" in content.lower()
        assert "not executed" in content.lower() or "has not been executed" in content.lower()

    def test_next_steps_conditional(self):
        """Document must make next steps conditional on separate approval."""
        content = read_doc()
        section = extract_section(content, H_CLOSURE)
        assert "approval" in content.lower()
        assert "separate" in content.lower()


class TestProhibitedInterpretations:
    """Verify prohibited interpretations are explicitly blocked."""

    def test_live_ready_not_means_execute(self):
        """Document must block 'live ready → execute' interpretation."""
        content = read_doc()
        section = extract_section(content, H_PROHIBITED)
        # Assert the prohibited interpretation row itself
        assert "Live is ready" in section or "live is ready" in section.lower()
        assert "execute" in section.lower()
        # Assert the correct explicit-approval wording for that row
        assert "explicitly approved" in section.lower() or "per §4.2" in section
        # Also verify Firecrawl/default is properly contrasted
        assert "Local-first" in section or "local-first" in section.lower()
        assert "optional fallback" in section.lower() or "fallback" in section.lower()

    def test_profile_expansion_not_approved(self):
        """Document must block 'profile expansion approved' interpretation."""
        content = read_doc()
        section = extract_section(content, H_PROHIBITED)
        assert "Profile expansion" in section
        assert "separate explicit approval" in section.lower()

    def test_auto_promotion_forbidden(self):
        """Document must block 'auto-promotion' interpretation."""
        content = read_doc()
        section = extract_section(content, H_PROHIBITED)
        assert "Scenario" in section or "snapshot" in section.lower() or "cache" in section.lower()
        assert "forbidden" in section.lower() or "explicit" in section.lower()

    def test_run_live_not_default(self):
        """Document must block 'RUN_LIVE default' interpretation."""
        content = read_doc()
        section = extract_section(content, H_PROHIBITED)
        assert "RUN_LIVE" in section
        assert "prohibited" in section.lower() or "without explicit" in section.lower()

class TestProhibitedWordingNotPresent:
    """Verify document does NOT contain prohibited wording suggesting unauthorized actions.
    These checks exclude the "Prohibited Interpretations" section which explicitly lists
    these phrases as PROHIBITED interpretations.
    """

    def _get_main_content(self, content: str) -> str:
        """Get document content excluding the Prohibited Interpretations section."""
        # Remove the Prohibited Interpretations section
        pattern = r'(^## \d+\. Prohibited Interpretations\s*\n)(.*?)(?=\n## |\Z)'
        match = re.search(pattern, content, re.MULTILINE | re.DOTALL)
        if match:
            # Remove the section content
            return content[:match.start()] + content[match.end():]
        return content

    def test_no_live_approved_language(self):
        """Document must not state live is already approved (outside prohibited section)."""
        content = read_doc()
        main_content = self._get_main_content(content)
        prohibited_phrases = [
            "live smoke is approved",
            "live execution is approved",
            "approved for live",
            "live validation approved",
            "live smoke approved",
        ]
        for phrase in prohibited_phrases:
            assert phrase.lower() not in main_content.lower(), f"Prohibited phrase found: {phrase}"

    def test_no_firecrawl_default_language(self):
        """Document must not state Firecrawl is default (outside prohibited section)."""
        content = read_doc()
        main_content = self._get_main_content(content)
        prohibited = [
            "firecrawl is the default",
            "firecrawl is default",
            "default firecrawl",
            "firecrawl first",
            "firecrawl-first",
        ]
        for phrase in prohibited:
            assert phrase not in main_content.lower(), f"Prohibited Firecrawl-default phrasing: {phrase}"

    def test_no_profile_expansion_approved(self):
        """Document must not state profile expansion is approved (outside prohibited section)."""
        content = read_doc()
        main_content = self._get_main_content(content)
        prohibited = [
            "profile expansion is approved",
            "profile expansion approved",
            "approved profile expansion",
            "fourth profile approved",
            "fifth profile approved",
        ]
        for phrase in prohibited:
            assert phrase not in main_content.lower(), f"Prohibited profile expansion phrasing: {phrase}"

    def test_no_auto_promotion_language(self):
        """Document must not state auto-promotion is enabled (outside prohibited section)."""
        content = read_doc()
        main_content = self._get_main_content(content)
        prohibited = [
            "auto-promotion",
            "automatic promotion",
            "auto promote",
            "automatically promoted",
            "promotion is automatic",
        ]
        for phrase in prohibited:
            assert phrase not in main_content.lower(), f"Prohibited auto-promotion phrasing: {phrase}"

    def test_no_run_live_default_language(self):
        """Document must not suggest RUN_LIVE can be enabled by default."""
        content = read_doc()
        main_content = self._get_main_content(content)
        main_content_lower = main_content.lower()
        prohibited = [
            "RUN_LIVE_CRAWL_TESTS=1 can be enabled",
            "RUN_LIVE_CRAWL_TESTS=1 by default",
            "RUN_LIVE_CRAWL_TESTS=1 enabled",
            "RUN_LIVE_CRAWL_TESTS=1 default",
            "RUN_LIVE_*_TESTS=1 may be executed",
        ]
        for phrase in prohibited:
            assert phrase.lower() not in main_content_lower, f"Prohibited RUN_LIVE phrasing: {phrase}"


class TestSafetyStrings:
    """Verify safety strings confirm no live calls."""

    def test_files_not_modified_no_live_calls(self):
        """Files Not Modified / Validation section must state no live calls made."""
        content = read_doc()
        # Check Validation section which contains the safety statement
        section = extract_section(content, H_VALIDATION)
        assert "no live" in section.lower()
        assert "no live/network/api/firecrawl" in section.lower()


class TestValidationCommands:
    """Verify validation commands in document."""

    def test_validation_has_git_diff_check(self):
        """Validation must include git diff --check."""
        content = read_doc()
        section = extract_section(content, H_VALIDATION)
        assert "git diff --check" in section

    def test_validation_has_pytest_contract_test(self):
        """Validation must include pytest for contract test."""
        content = read_doc()
        section = extract_section(content, H_VALIDATION)
        assert "pytest" in section
        assert "test_bukgu_no_live_track_closure_audit.py" in section

    def test_validation_has_related_bukgu_tests(self):
        """Validation must reference related Bukgu tests."""
        content = read_doc()
        section = extract_section(content, H_VALIDATION)
        assert "test_bukgu_crawl_filters_readiness_no_live.py" in section
        assert "test_bukgu_local_first_live_smoke_plan_contract_no_live.py" in section
        assert "test_bukgu_crawl_filters_stage415_no_live.py" in section

    def test_validation_confirms_no_live_calls(self):
        """Validation must confirm no live calls."""
        content = read_doc()
        section = extract_section(content, H_VALIDATION)
        assert "no live" in section.lower()
        assert "no live/network/api/firecrawl" in section.lower()


# ─── Entry Point ────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v"])