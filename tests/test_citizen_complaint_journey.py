"""
Tests for citizen-complaint-journey — Stage #849 Phase A.

Pure reducer/API validation.
Uses only `node -e` with `require()` (UMD module) — no jsdom, no VM sandbox,
no fake DOM, no temporary .js runner files.
"""

import json
import subprocess


_JOURNEY_MODULE = "./src/web/static/citizen-complaint-journey.js"

_COMMON_PREFIX = (
    "var J = require('" + _JOURNEY_MODULE + "');\n"
)


def _run_js(script):
    """Run a JS snippet against the loaded module and return parsed JSON."""
    full = _COMMON_PREFIX + script
    result = subprocess.run(
        ["node", "-e", full],
        capture_output=True,
        text=True,
        timeout=30,
    )
    if result.returncode != 0:
        raise RuntimeError(
            "Node script failed:\nSTDERR: " + result.stderr
            + "\nSTDOUT: " + result.stdout
        )
    out = result.stdout.strip()

    # Some scripts print separate JSON lines; pick the last meaningful line
    lines = [ln for ln in out.split("\n") if ln.strip()]
    if not lines:
        return None
    return json.loads(lines[-1])


def _raw_stdout(script):
    """Run JS and return raw stdout text (for non-JSON checks)."""
    full = _COMMON_PREFIX + script
    result = subprocess.run(
        ["node", "-e", full],
        capture_output=True,
        text=True,
        timeout=30,
    )
    if result.returncode != 0:
        raise RuntimeError(
            "Node script failed:\nSTDERR: " + result.stderr
            + "\nSTDOUT: " + result.stdout
        )
    return result.stdout


# =========================================================================
# Tests
# =========================================================================


class TestInitialState:
    """createInitialState returns a clean state."""

    def test_returns_object(self):
        result = _run_js("console.log(JSON.stringify(J.createInitialState()));")
        assert isinstance(result, dict)

    def test_category_id_is_null(self):
        result = _run_js("console.log(JSON.stringify(J.createInitialState()));")
        assert result["category_id"] is None

    def test_facts_all_null(self):
        result = _run_js("console.log(JSON.stringify(J.createInitialState()));")
        assert result["facts"]["location"] is None
        assert result["facts"]["timing_or_recurrence"] is None
        assert result["facts"]["observed_situation"] is None
        assert result["facts"]["requested_remedy"] is None

    def test_draft_and_approved_initial(self):
        result = _run_js("console.log(JSON.stringify(J.createInitialState()));")
        assert result["draft"] is None
        assert result["approved"] is False


class TestGetClarification:
    """getClarification returns the right level of targeting."""

    def test_empty_state_returns_category_clarification(self):
        js = (
            "var s = J.createInitialState();\n"
            + "console.log(JSON.stringify(J.getClarification(s)));\n"
        )
        result = _run_js(js)
        assert result["type"] == "category"

    def test_category_selected_returns_fact_clarification(self):
        js = (
            "var s = J.createInitialState();\n"
            + "s = J.reduce(s, { type: 'SELECT_CATEGORY', category_id: 'illegal-parking' });\n"
            + "console.log(JSON.stringify(J.getClarification(s)));\n"
        )
        result = _run_js(js)
        assert result["type"] == "facts"
        assert "location" in result["missing"]

    def test_partial_facts_shows_only_missing(self):
        js = (
            "var s = J.createInitialState();\n"
            + "s = J.reduce(s, { type: 'SELECT_CATEGORY', category_id: 'illegal-parking' });\n"
            + "s = J.reduce(s, { type: 'SELECT_FACT', field_id: 'location', choice_id: 'roadside' });\n"
            + "s = J.reduce(s, { type: 'SELECT_FACT', field_id: 'timing_or_recurrence', choice_id: 'recent-once' });\n"
            + "console.log(JSON.stringify(J.getClarification(s)));\n"
        )
        result = _run_js(js)
        assert result["type"] == "facts"
        assert "location" not in result["missing"]
        assert "timing_or_recurrence" not in result["missing"]
        assert "observed_situation" in result["missing"]
        assert "requested_remedy" in result["missing"]

    def test_complete_state_returns_null(self):
        js = (
            "var s = J.createInitialState();\n"
            + "s = J.reduce(s, { type: 'SELECT_CATEGORY', category_id: 'illegal-parking' });\n"
            + "s = J.reduce(s, { type: 'SELECT_FACT', field_id: 'location', choice_id: 'roadside' });\n"
            + "s = J.reduce(s, { type: 'SELECT_FACT', field_id: 'timing_or_recurrence', choice_id: 'recent-once' });\n"
            + "s = J.reduce(s, { type: 'SELECT_FACT', field_id: 'observed_situation', choice_id: 'vehicle-blocking-passage' });\n"
            + "s = J.reduce(s, { type: 'SELECT_FACT', field_id: 'requested_remedy', choice_id: 'request-site-check' });\n"
            + "s = J.reduce(s, { type: 'BUILD_DRAFT' });\n"
            + "console.log(JSON.stringify(J.getClarification(s)));\n"
        )
        result = _run_js(js)
        assert result is None


class TestCategoryIds:
    """Exactly five hyphen canonical category IDs are exposed."""

    def test_getClosedChoices_has_five_categories(self):
        js = (
            "var c = J.getClosedChoices();\n"
            + "console.log(JSON.stringify(c.categories.map(function(x) { return x.id; })));\n"
        )
        result = _run_js(js)
        assert len(result) == 5

    def test_all_category_ids_are_hyphen_format(self):
        js = (
            "var c = J.getClosedChoices();\n"
            + "console.log(JSON.stringify(c.categories.map(function(x) { return x.id; })));\n"
        )
        result = _run_js(js)
        for cid in result:
            assert "-" in cid, f"Category ID '{cid}' is not hyphen format"

    def test_known_category_ids(self):
        js = (
            "var c = J.getClosedChoices();\n"
            + "console.log(JSON.stringify(c.categories.map(function(x) { return x.id; })));\n"
        )
        result = _run_js(js)
        expected = {
            "illegal-parking",
            "public-parking-inconvenience",
            "residential-parking",
            "traffic-or-facility-safety",
            "other-or-unsure",
        }
        assert set(result) == expected


class TestSelectCategory:
    """SELECT_CATEGORY event sets the category and resets facts."""

    def test_valid_category_is_accepted(self):
        js = (
            "var s = J.createInitialState();\n"
            + "s = J.reduce(s, { type: 'SELECT_CATEGORY', category_id: 'residential-parking' });\n"
            + "console.log(JSON.stringify(s.category_id));\n"
        )
        result = _run_js(js)
        assert result == "residential-parking"

    def test_selecting_category_resets_facts(self):
        js = (
            "var s = J.createInitialState();\n"
            + "s = J.reduce(s, { type: 'SELECT_CATEGORY', category_id: 'illegal-parking' });\n"
            + "s = J.reduce(s, { type: 'SELECT_FACT', field_id: 'location', choice_id: 'roadside' });\n"
            + "// Now select a different category — facts should reset\n"
            + "s = J.reduce(s, { type: 'SELECT_CATEGORY', category_id: 'residential-parking' });\n"
            + "console.log(JSON.stringify(s.facts));\n"
        )
        result = _run_js(js)
        assert result["location"] is None

    def test_invalid_category_not_accepted(self):
        js = (
            "var s = J.createInitialState();\n"
            + "s = J.reduce(s, { type: 'SELECT_CATEGORY', category_id: 'invalid-category' });\n"
            + "console.log(JSON.stringify(s.category_id));\n"
        )
        result = _run_js(js)
        assert result is None

    def test_unknown_event_keys_rejected(self):
        js = (
            "var s = J.createInitialState();\n"
            + "s = J.reduce(s, { type: 'SELECT_CATEGORY', category_id: 'illegal-parking', extra: 'x' });\n"
            + "console.log(JSON.stringify(s.category_id));\n"
        )
        result = _run_js(js)
        assert result is None


class TestSelectFact:
    """SELECT_FACT event sets a single fact choice."""

    def test_valid_fact_accepted(self):
        js = (
            "var s = J.createInitialState();\n"
            + "s = J.reduce(s, { type: 'SELECT_CATEGORY', category_id: 'illegal-parking' });\n"
            + "s = J.reduce(s, { type: 'SELECT_FACT', field_id: 'location', choice_id: 'roadside' });\n"
            + "console.log(JSON.stringify(s.facts.location));\n"
        )
        result = _run_js(js)
        assert result == "roadside"

    def test_unknown_field_id_rejected(self):
        js = (
            "var s = J.createInitialState();\n"
            + "s = J.reduce(s, { type: 'SELECT_CATEGORY', category_id: 'illegal-parking' });\n"
            + "s = J.reduce(s, { type: 'SELECT_FACT', field_id: 'nonexistent-field', choice_id: 'roadside' });\n"
            + "console.log(JSON.stringify(s.facts.location));\n"
        )
        result = _run_js(js)
        assert result is None

    def test_unknown_choice_id_rejected(self):
        js = (
            "var s = J.createInitialState();\n"
            + "s = J.reduce(s, { type: 'SELECT_CATEGORY', category_id: 'illegal-parking' });\n"
            + "s = J.reduce(s, { type: 'SELECT_FACT', field_id: 'location', choice_id: 'made-up-place' });\n"
            + "console.log(JSON.stringify(s.facts.location));\n"
        )
        result = _run_js(js)
        assert result is None

    def test_extra_keys_on_select_fact_rejected(self):
        js = (
            "var s = J.createInitialState();\n"
            + "s = J.reduce(s, { type: 'SELECT_CATEGORY', category_id: 'illegal-parking' });\n"
            + "s = J.reduce(s, { type: 'SELECT_FACT', field_id: 'location', choice_id: 'roadside', malicious: true });\n"
            + "console.log(JSON.stringify(s.facts.location));\n"
        )
        result = _run_js(js)
        assert result is None

    def test_free_text_payload_not_accepted(self):
        """A free-text-like SELECT_FACT with raw text as choice_id is rejected."""
        js = (
            "var s = J.createInitialState();\n"
            + "s = J.reduce(s, { type: 'SELECT_CATEGORY', category_id: 'illegal-parking' });\n"
            + "s = J.reduce(s, { type: 'SELECT_FACT', field_id: 'location', choice_id: '서울시 강남구 역삼동 123-45' });\n"
            + "console.log(JSON.stringify(s.facts.location));\n"
        )
        result = _run_js(js)
        assert result is None


class TestBuildDraft:
    """BUILD_DRAFT generates a neutral Korean draft when all facts are present."""

    def _complete(self):
        """Return state with all facts selected for illegal-parking."""
        return (
            "var s = J.createInitialState();\n"
            + "s = J.reduce(s, { type: 'SELECT_CATEGORY', category_id: 'illegal-parking' });\n"
            + "s = J.reduce(s, { type: 'SELECT_FACT', field_id: 'location', choice_id: 'roadside' });\n"
            + "s = J.reduce(s, { type: 'SELECT_FACT', field_id: 'timing_or_recurrence', choice_id: 'recent-once' });\n"
            + "s = J.reduce(s, { type: 'SELECT_FACT', field_id: 'observed_situation', choice_id: 'vehicle-blocking-passage' });\n"
            + "s = J.reduce(s, { type: 'SELECT_FACT', field_id: 'requested_remedy', choice_id: 'request-site-check' });\n"
        )

    def test_build_draft_with_complete_facts(self):
        js = self._complete() + (
            "s = J.reduce(s, { type: 'BUILD_DRAFT' });\n"
            + "console.log(JSON.stringify(s.draft));\n"
        )
        result = _run_js(js)
        assert isinstance(result, str)
        assert len(result) > 0

    def test_draft_contains_selected_category_and_facts_only(self):
        js = self._complete() + (
            "s = J.reduce(s, { type: 'BUILD_DRAFT' });\n"
            + "console.log(JSON.stringify(J.getReviewDraft(s)));\n"
        )
        result = _run_js(js)
        assert "불법주정차" in result  # selected category
        assert "일반 도로변" in result  # selected fact
        assert "최근 1회" in result     # selected fact
        assert "차량 통행 방해" in result  # selected fact
        assert "현장 확인 요청" in result  # selected fact
        # Should NOT contain unselected categories
        assert "공용주차장" not in result

    def test_draft_is_neutral_no_legal_conclusion(self):
        js = self._complete() + (
            "s = J.reduce(s, { type: 'BUILD_DRAFT' });\n"
            + "console.log(JSON.stringify(J.getReviewDraft(s)));\n"
        )
        result = _run_js(js)
        forbidden = [
            "처벌", "벌금", "고발", "단속", "적발",
            "조치하겠", "약속", "처리해 드리",
        ]
        for word in forbidden:
            assert word not in result, f"Draft contains forbidden word: {word}"

    def test_draft_contains_review_marker(self):
        js = self._complete() + (
            "s = J.reduce(s, { type: 'BUILD_DRAFT' });\n"
            + "console.log(JSON.stringify(J.getReviewDraft(s)));\n"
        )
        result = _run_js(js)
        assert "검토용 초안" in result

    def test_no_draft_when_facts_missing(self):
        js = (
            "var s = J.createInitialState();\n"
            + "s = J.reduce(s, { type: 'SELECT_CATEGORY', category_id: 'illegal-parking' });\n"
            + "s = J.reduce(s, { type: 'SELECT_FACT', field_id: 'location', choice_id: 'roadside' });\n"
            + "s = J.reduce(s, { type: 'BUILD_DRAFT' });\n"
            + "console.log(JSON.stringify(s.draft));\n"
        )
        result = _run_js(js)
        assert result is None

    def test_no_fabricated_facts_in_draft(self):
        """Draft does not fabricate Korean facts for missing choices."""
        js = (
            "var s = J.createInitialState();\n"
            + "s = J.reduce(s, { type: 'SELECT_CATEGORY', category_id: 'illegal-parking' });\n"
            + "s = J.reduce(s, { type: 'SELECT_FACT', field_id: 'location', choice_id: 'roadside' });\n"
            + "// Only one fact — BUILD_DRAFT should not fabricate\n"
            + "s = J.reduce(s, { type: 'BUILD_DRAFT' });\n"
            + "console.log(JSON.stringify({ draft: s.draft, hasFacts: s.draft !== null }));\n"
        )
        result = _run_js(js)
        assert result["draft"] is None, "Draft must be null when facts missing"

    def test_draft_not_accepted_as_submission(self):
        """Draft clearly says it is a review draft, not a submission."""
        js = self._complete() + (
            "s = J.reduce(s, { type: 'BUILD_DRAFT' });\n"
            + "console.log(JSON.stringify(J.getReviewDraft(s)));\n"
        )
        result = _run_js(js)
        assert "제출 전 확인" in result


class TestApprovalGate:
    """APPROVE_DRAFT gates the prefill payload."""

    def _complete(self):
        return (
            "var s = J.createInitialState();\n"
            + "s = J.reduce(s, { type: 'SELECT_CATEGORY', category_id: 'illegal-parking' });\n"
            + "s = J.reduce(s, { type: 'SELECT_FACT', field_id: 'location', choice_id: 'roadside' });\n"
            + "s = J.reduce(s, { type: 'SELECT_FACT', field_id: 'timing_or_recurrence', choice_id: 'recent-once' });\n"
            + "s = J.reduce(s, { type: 'SELECT_FACT', field_id: 'observed_situation', choice_id: 'vehicle-blocking-passage' });\n"
            + "s = J.reduce(s, { type: 'SELECT_FACT', field_id: 'requested_remedy', choice_id: 'request-site-check' });\n"
            + "s = J.reduce(s, { type: 'BUILD_DRAFT' });\n"
        )

    def test_before_approval_prefill_is_null(self):
        js = self._complete() + (
            "console.log(JSON.stringify(J.getApprovedPrefill(s)));\n"
        )
        result = _run_js(js)
        assert result is None

    def test_after_approval_prefill_has_target_and_text(self):
        js = self._complete() + (
            "s = J.reduce(s, { type: 'APPROVE_DRAFT' });\n"
            + "console.log(JSON.stringify(J.getApprovedPrefill(s)));\n"
        )
        result = _run_js(js)
        assert result["target_id"] == "complaint-body"
        assert isinstance(result["draft_text"], str)
        assert len(result["draft_text"]) > 0

    def test_approval_before_draft_does_nothing(self):
        """No draft text exists yet, so approval does nothing."""
        js = (
            "var s = J.createInitialState();\n"
            + "s = J.reduce(s, { type: 'SELECT_CATEGORY', category_id: 'illegal-parking' });\n"
            + "s = J.reduce(s, { type: 'APPROVE_DRAFT' });\n"
            + "console.log(JSON.stringify(J.getApprovedPrefill(s)));\n"
        )
        result = _run_js(js)
        assert result is None

    def test_approval_extra_keys_rejected(self):
        js = self._complete() + (
            "s = J.reduce(s, { type: 'APPROVE_DRAFT', extra: 'x' });\n"
            + "console.log(JSON.stringify(J.getApprovedPrefill(s)));\n"
        )
        result = _run_js(js)
        assert result is None


class TestRejectDraft:
    """REJECT_DRAFT clears draft and approval."""

    def _approved(self):
        return (
            "var s = J.createInitialState();\n"
            + "s = J.reduce(s, { type: 'SELECT_CATEGORY', category_id: 'illegal-parking' });\n"
            + "s = J.reduce(s, { type: 'SELECT_FACT', field_id: 'location', choice_id: 'roadside' });\n"
            + "s = J.reduce(s, { type: 'SELECT_FACT', field_id: 'timing_or_recurrence', choice_id: 'recent-once' });\n"
            + "s = J.reduce(s, { type: 'SELECT_FACT', field_id: 'observed_situation', choice_id: 'vehicle-blocking-passage' });\n"
            + "s = J.reduce(s, { type: 'SELECT_FACT', field_id: 'requested_remedy', choice_id: 'request-site-check' });\n"
            + "s = J.reduce(s, { type: 'BUILD_DRAFT' });\n"
            + "s = J.reduce(s, { type: 'APPROVE_DRAFT' });\n"
        )

    def test_reject_clears_draft(self):
        js = self._approved() + (
            "s = J.reduce(s, { type: 'REJECT_DRAFT' });\n"
            + "console.log(JSON.stringify(s.draft));\n"
        )
        result = _run_js(js)
        assert result is None

    def test_reject_clears_approval(self):
        js = self._approved() + (
            "s = J.reduce(s, { type: 'REJECT_DRAFT' });\n"
            + "console.log(JSON.stringify(J.getApprovedPrefill(s)));\n"
        )
        result = _run_js(js)
        assert result is None

    def test_reject_preserves_category_and_facts(self):
        js = self._approved() + (
            "s = J.reduce(s, { type: 'REJECT_DRAFT' });\n"
            + "console.log(JSON.stringify({ cat: s.category_id, loc: s.facts.location }));\n"
        )
        result = _run_js(js)
        assert result["cat"] == "illegal-parking"
        assert result["loc"] == "roadside"

    def test_reject_extra_keys_rejected(self):
        js = self._approved() + (
            "s = J.reduce(s, { type: 'REJECT_DRAFT', extra: true });\n"
            + "console.log(JSON.stringify(s.draft));\n"
        )
        result = _run_js(js)
        # With extra key, reject should be ignored, so draft remains
        assert result is not None


class TestClearAll:
    """CLEAR_ALL resets to initial state."""

    def _after_approval(self):
        return (
            "var s = J.createInitialState();\n"
            + "s = J.reduce(s, { type: 'SELECT_CATEGORY', category_id: 'illegal-parking' });\n"
            + "s = J.reduce(s, { type: 'SELECT_FACT', field_id: 'location', choice_id: 'roadside' });\n"
            + "s = J.reduce(s, { type: 'SELECT_FACT', field_id: 'timing_or_recurrence', choice_id: 'recent-once' });\n"
            + "s = J.reduce(s, { type: 'SELECT_FACT', field_id: 'observed_situation', choice_id: 'vehicle-blocking-passage' });\n"
            + "s = J.reduce(s, { type: 'SELECT_FACT', field_id: 'requested_remedy', choice_id: 'request-site-check' });\n"
            + "s = J.reduce(s, { type: 'BUILD_DRAFT' });\n"
            + "s = J.reduce(s, { type: 'APPROVE_DRAFT' });\n"
            + "s = J.reduce(s, { type: 'CLEAR_ALL' });\n"
        )

    def test_clear_resets_category(self):
        js = self._after_approval() + (
            "console.log(JSON.stringify(s.category_id));\n"
        )
        result = _run_js(js)
        assert result is None

    def test_clear_resets_facts(self):
        js = self._after_approval() + (
            "console.log(JSON.stringify(s.facts));\n"
        )
        result = _run_js(js)
        for val in result.values():
            assert val is None

    def test_clear_resets_draft(self):
        js = self._after_approval() + (
            "console.log(JSON.stringify(s.draft));\n"
        )
        result = _run_js(js)
        assert result is None

    def test_clear_resets_approval(self):
        js = self._after_approval() + (
            "console.log(JSON.stringify(J.getApprovedPrefill(s)));\n"
        )
        result = _run_js(js)
        assert result is None

    def test_clear_extra_keys_rejected(self):
        js = (
            "var s = J.createInitialState();\n"
            + "s = J.reduce(s, { type: 'CLEAR_ALL', extra: 'x' });\n"
            + "console.log(JSON.stringify(s));\n"
        )
        result = _run_js(js)
        # With extra key, CLEAR_ALL should be ignored.
        # Since initial state has category_id null, reduce returns state unchanged.
        assert _is_initial_result(result)

    def test_clear_from_initial_state(self):
        js = (
            "var s = J.createInitialState();\n"
            + "s = J.reduce(s, { type: 'CLEAR_ALL' });\n"
            + "console.log(JSON.stringify(s));\n"
        )
        result = _run_js(js)
        assert _is_initial_result(result)


def _is_initial_result(r):
    return (
        r["category_id"] is None
        and r["facts"]["location"] is None
        and r["facts"]["timing_or_recurrence"] is None
        and r["facts"]["observed_situation"] is None
        and r["facts"]["requested_remedy"] is None
        and r["draft"] is None
        and r["approved"] is False
    )


class TestFactChangeInvalidation:
    """Changing a fact after BUILD_DRAFT invalidates draft and approval."""

    def test_fact_change_clears_draft(self):
        js = (
            "var s = J.createInitialState();\n"
            + "s = J.reduce(s, { type: 'SELECT_CATEGORY', category_id: 'illegal-parking' });\n"
            + "s = J.reduce(s, { type: 'SELECT_FACT', field_id: 'location', choice_id: 'roadside' });\n"
            + "s = J.reduce(s, { type: 'SELECT_FACT', field_id: 'timing_or_recurrence', choice_id: 'recent-once' });\n"
            + "s = J.reduce(s, { type: 'SELECT_FACT', field_id: 'observed_situation', choice_id: 'vehicle-blocking-passage' });\n"
            + "s = J.reduce(s, { type: 'SELECT_FACT', field_id: 'requested_remedy', choice_id: 'request-site-check' });\n"
            + "s = J.reduce(s, { type: 'BUILD_DRAFT' });\n"
            + "// Change a fact\n"
            + "s = J.reduce(s, { type: 'SELECT_FACT', field_id: 'location', choice_id: 'public-parking-area' });\n"
            + "console.log(JSON.stringify(s.draft));\n"
        )
        result = _run_js(js)
        assert result is None

    def test_fact_change_clears_approval(self):
        js = (
            "var s = J.createInitialState();\n"
            + "s = J.reduce(s, { type: 'SELECT_CATEGORY', category_id: 'illegal-parking' });\n"
            + "s = J.reduce(s, { type: 'SELECT_FACT', field_id: 'location', choice_id: 'roadside' });\n"
            + "s = J.reduce(s, { type: 'SELECT_FACT', field_id: 'timing_or_recurrence', choice_id: 'recent-once' });\n"
            + "s = J.reduce(s, { type: 'SELECT_FACT', field_id: 'observed_situation', choice_id: 'vehicle-blocking-passage' });\n"
            + "s = J.reduce(s, { type: 'SELECT_FACT', field_id: 'requested_remedy', choice_id: 'request-site-check' });\n"
            + "s = J.reduce(s, { type: 'BUILD_DRAFT' });\n"
            + "s = J.reduce(s, { type: 'APPROVE_DRAFT' });\n"
            + "// Change a fact — approval should be lost\n"
            + "s = J.reduce(s, { type: 'SELECT_FACT', field_id: 'location', choice_id: 'public-parking-area' });\n"
            + "console.log(JSON.stringify(J.getApprovedPrefill(s)));\n"
        )
        result = _run_js(js)
        assert result is None


class TestUnknownEvents:
    """Unknown or malformed events are safely ignored."""

    def test_unknown_event_type(self):
        js = (
            "var s = J.createInitialState();\n"
            + "var s2 = J.reduce(s, { type: 'UNKNOWN_EVENT' });\n"
            + "console.log(JSON.stringify(s === s2));\n"
        )
        result = _run_js(js)
        assert result is True

    def test_missing_event_type(self):
        js = (
            "var s = J.createInitialState();\n"
            + "var s2 = J.reduce(s, { something: true });\n"
            + "console.log(JSON.stringify(s === s2));\n"
        )
        result = _run_js(js)
        assert result is True

    def test_non_object_event(self):
        js = (
            "var s = J.createInitialState();\n"
            + "var s2 = J.reduce(s, null);\n"
            + "console.log(JSON.stringify(s === s2));\n"
        )
        result = _run_js(js)
        assert result is True

    def test_non_string_event_type(self):
        js = (
            "var s = J.createInitialState();\n"
            + "var s2 = J.reduce(s, { type: 123 });\n"
            + "console.log(JSON.stringify(s === s2));\n"
        )
        result = _run_js(js)
        assert result is True

    def test_select_category_with_extra_keys(self):
        js = (
            "var s = J.createInitialState();\n"
            + "s = J.reduce(s, { type: 'SELECT_CATEGORY', category_id: 'illegal-parking', noop: true });\n"
            + "console.log(JSON.stringify(s.category_id));\n"
        )
        result = _run_js(js)
        assert result is None


class TestNoLiveCapability:
    """Source contains no fetch/network/persistence/crawler capability."""

    def test_no_network_keywords(self):
        with open("src/web/static/citizen-complaint-journey.js", encoding="utf-8") as f:
            src = f.read()
        forbidden = [
            "fetch(", "XMLHttpRequest", "WebSocket",
            "navigator.sendBeacon", "EventSource",
            "Firecrawl", "crawler",
            "localStorage", "sessionStorage",
            "indexedDB",
        ]
        for word in forbidden:
            assert word not in src, f"Source contains forbidden keyword: {word}"

    def test_no_planner_executor_require(self):
        """Reducer does not require planner/executor/canvas/shell files."""
        with open("src/web/static/citizen-complaint-journey.js", encoding="utf-8") as f:
            src = f.read()
        forbidden_paths = [
            "citizen-action-executor",
            "citizen-action-demo-canvas",
            "citizen-action-demo-map",
            "citizen-copilot-shell",
            "citizen_action_plan",
        ]
        for path in forbidden_paths:
            assert path not in src, f"Source references forbidden path: {path}"

    def test_no_sensitive_key_names(self):
        """Reducer does not store sensitive PII key names in state."""
        js = (
            "var s = J.createInitialState();\n"
            + "console.log(JSON.stringify(Object.keys(s)));\n"
            + "console.log(JSON.stringify(Object.keys(s.facts)));\n"
        )
        out = _raw_stdout(js)
        state_keys = json.loads(out.split("\n")[0].strip())
        fact_keys = json.loads(out.split("\n")[1].strip())
        all_keys = state_keys + fact_keys
        sensitive = [
            "phone", "email", "address", "ssn",
            "account", "plate", "license", "password",
            "credit", "upload", "signature", "payment",
        ]
        for key in all_keys:
            key_lower = key.lower()
            for word in sensitive:
                assert word not in key_lower, \
                    f"State key '{key}' contains sensitive word: {word}"


class TestGetClosedChoices:
    """getClosedChoices returns the full vocabulary."""

    def test_has_four_fact_fields(self):
        js = (
            "var c = J.getClosedChoices();\n"
            + "console.log(JSON.stringify(Object.keys(c.facts)));\n"
        )
        result = _run_js(js)
        assert len(result) == 4

    def test_each_fact_field_has_choices(self):
        js = (
            "var c = J.getClosedChoices();\n"
            + "var counts = {};\n"
            + "for (var k in c.facts) { counts[k] = c.facts[k].length; }\n"
            + "console.log(JSON.stringify(counts));\n"
        )
        result = _run_js(js)
        for field_id, count in result.items():
            assert count >= 2, f"Field {field_id} has only {count} choices"

    def test_known_field_ids(self):
        js = (
            "var c = J.getClosedChoices();\n"
            + "console.log(JSON.stringify(Object.keys(c.facts)));\n"
        )
        result = _run_js(js)
        expected = {
            "location",
            "timing_or_recurrence",
            "observed_situation",
            "requested_remedy",
        }
        assert set(result) == expected


class TestGetReviewDraft:
    """getReviewDraft returns current draft or null."""

    def test_no_draft_returns_null(self):
        js = (
            "var s = J.createInitialState();\n"
            + "console.log(JSON.stringify(J.getReviewDraft(s)));\n"
        )
        result = _run_js(js)
        assert result is None

    def test_after_build_returns_draft(self):
        js = (
            "var s = J.createInitialState();\n"
            + "s = J.reduce(s, { type: 'SELECT_CATEGORY', category_id: 'illegal-parking' });\n"
            + "s = J.reduce(s, { type: 'SELECT_FACT', field_id: 'location', choice_id: 'roadside' });\n"
            + "s = J.reduce(s, { type: 'SELECT_FACT', field_id: 'timing_or_recurrence', choice_id: 'recent-once' });\n"
            + "s = J.reduce(s, { type: 'SELECT_FACT', field_id: 'observed_situation', choice_id: 'vehicle-blocking-passage' });\n"
            + "s = J.reduce(s, { type: 'SELECT_FACT', field_id: 'requested_remedy', choice_id: 'request-site-check' });\n"
            + "s = J.reduce(s, { type: 'BUILD_DRAFT' });\n"
            + "console.log(JSON.stringify(J.getReviewDraft(s)));\n"
        )
        result = _run_js(js)
        assert isinstance(result, str)
        assert len(result) > 0

    def test_after_reject_returns_null(self):
        js = (
            "var s = J.createInitialState();\n"
            + "s = J.reduce(s, { type: 'SELECT_CATEGORY', category_id: 'illegal-parking' });\n"
            + "s = J.reduce(s, { type: 'SELECT_FACT', field_id: 'location', choice_id: 'roadside' });\n"
            + "s = J.reduce(s, { type: 'SELECT_FACT', field_id: 'timing_or_recurrence', choice_id: 'recent-once' });\n"
            + "s = J.reduce(s, { type: 'SELECT_FACT', field_id: 'observed_situation', choice_id: 'vehicle-blocking-passage' });\n"
            + "s = J.reduce(s, { type: 'SELECT_FACT', field_id: 'requested_remedy', choice_id: 'request-site-check' });\n"
            + "s = J.reduce(s, { type: 'BUILD_DRAFT' });\n"
            + "s = J.reduce(s, { type: 'REJECT_DRAFT' });\n"
            + "console.log(JSON.stringify(J.getReviewDraft(s)));\n"
        )
        result = _run_js(js)
        assert result is None


class TestCategoryChange:
    """Changing category resets facts, draft, and approval."""

    def test_switch_category_resets_facts(self):
        js = (
            "var s = J.createInitialState();\n"
            + "s = J.reduce(s, { type: 'SELECT_CATEGORY', category_id: 'illegal-parking' });\n"
            + "s = J.reduce(s, { type: 'SELECT_FACT', field_id: 'location', choice_id: 'roadside' });\n"
            + "s = J.reduce(s, { type: 'SELECT_CATEGORY', category_id: 'traffic-or-facility-safety' });\n"
            + "console.log(JSON.stringify({ cat: s.category_id, loc: s.facts.location }));\n"
        )
        result = _run_js(js)
        assert result["cat"] == "traffic-or-facility-safety"
        assert result["loc"] is None

    def test_switch_category_clears_draft_and_approval(self):
        js = (
            "var s = J.createInitialState();\n"
            + "s = J.reduce(s, { type: 'SELECT_CATEGORY', category_id: 'illegal-parking' });\n"
            + "s = J.reduce(s, { type: 'SELECT_FACT', field_id: 'location', choice_id: 'roadside' });\n"
            + "s = J.reduce(s, { type: 'SELECT_FACT', field_id: 'timing_or_recurrence', choice_id: 'recent-once' });\n"
            + "s = J.reduce(s, { type: 'SELECT_FACT', field_id: 'observed_situation', choice_id: 'vehicle-blocking-passage' });\n"
            + "s = J.reduce(s, { type: 'SELECT_FACT', field_id: 'requested_remedy', choice_id: 'request-site-check' });\n"
            + "s = J.reduce(s, { type: 'BUILD_DRAFT' });\n"
            + "s = J.reduce(s, { type: 'APPROVE_DRAFT' });\n"
            + "s = J.reduce(s, { type: 'SELECT_CATEGORY', category_id: 'traffic-or-facility-safety' });\n"
            + "console.log(JSON.stringify({ draft: s.draft, approved: s.approved }));\n"
        )
        result = _run_js(js)
        assert result["draft"] is None
        assert result["approved"] is False
