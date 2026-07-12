"""
Stage #851 deterministic acceptance matrix.
This suite composes existing local-only contracts.
Detailed executor runtime behavior remains covered by the Stage #848 executor tests.
No browser, server, provider, network, crawler, or external site is executed.
"""

import json
import subprocess
from pathlib import Path

import pytest

from src.agent.citizen_action_plan import (
    CitizenAction,
    build_citizen_action_plan,
    action_explanation_ko,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
STATIC = REPO_ROOT / "src" / "web" / "static"

_ACTION_TYPE_MAP = {
    "ASK_CLARIFYING_QUESTION": "ask_clarifying_question",
    "PRESENT_CHOICES": "present_category_choices",
    "HIGHLIGHT_ALLOWLISTED_ELEMENT": "highlight_element",
    "SCROLL_TO_ALLOWLISTED_ELEMENT": "scroll_to_element",
    "OPEN_ALLOWLISTED_ROUTE": "open_route",
    "CLICK_ALLOWLISTED_ELEMENT": "click_element",
    "PREFILL_APPROVED_DRAFT": "prefill_draft",
    "STOP_FOR_USER_CONFIRMATION": "stop_for_confirmation",
}

_CANONICAL = (
    "illegal-parking", "public-parking-inconvenience", "residential-parking",
    "traffic-or-facility-safety", "other-or-unsure",
)


def _make(action_type, route_id=None, target_id=None, explanation_id=None,
          requires_user_confirmation=False, choice_ids=()):
    return CitizenAction(
        action_type=action_type,
        route_id=route_id,
        target_id=target_id,
        explanation_id=explanation_id or _ACTION_TYPE_MAP.get(action_type, "highlight_element"),
        requires_user_confirmation=requires_user_confirmation,
        choice_ids=choice_ids,
    )


def _stop():
    return _make("STOP_FOR_USER_CONFIRMATION", requires_user_confirmation=True)


def _prefill():
    return _make("PREFILL_APPROVED_DRAFT", target_id="complaint-body",
                 requires_user_confirmation=True)


_JOURNEY_MODULE = "./src/web/static/citizen-complaint-journey.js"
_JOURNEY_PREFIX = "var J = require('" + _JOURNEY_MODULE + "');\n"


def _run_js(script: str):
    full = _JOURNEY_PREFIX + script
    result = subprocess.run(["node", "-e", full], capture_output=True,
                            text=True, timeout=30, cwd=REPO_ROOT)
    if result.returncode != 0:
        raise RuntimeError("Node script failed:\nSTDERR: " + result.stderr)
    lines = [ln for ln in result.stdout.strip().split("\n") if ln.strip()]
    return json.loads(lines[-1]) if lines else None


# =========================================================================
# Scenario 1 — generic complaint request → clarify → local guided trace
# =========================================================================


class TestGenericComplaintGuidedTrace:
    """Scenario 1: full guided plan from clarifying question through to STOP."""

    def test_plan_is_guided_with_korean_explanations(self):
        """Build guided plan; verify guided, hard_stop, last=STOP, all Korean."""
        actions = [
            _make("ASK_CLARIFYING_QUESTION"),
            _make("PRESENT_CHOICES", choice_ids=_CANONICAL),
            _make("OPEN_ALLOWLISTED_ROUTE", route_id="civil-service"),
            _make("HIGHLIGHT_ALLOWLISTED_ELEMENT", target_id="nav-complaint-category"),
            _make("SCROLL_TO_ALLOWLISTED_ELEMENT", target_id="nav-complaint-category"),
            _make("CLICK_ALLOWLISTED_ELEMENT", target_id="nav-complaint-category"),
            _stop(),
        ]
        plan = build_citizen_action_plan(actions)
        assert plan.plan_status == "guided"
        assert plan.hard_stop_required is True
        assert plan.actions[-1].action_type == "STOP_FOR_USER_CONFIRMATION"
        for act in plan.actions:
            exp = action_explanation_ko(act)
            assert len(exp) > 0
            assert "알 수 없는 동작" not in exp

    def test_journey_has_category_clarification_and_canonical_five(self):
        """Initial getClarification()=category; getClosedChoices()=five IDs."""
        result = _run_js(
            "var s = J.createInitialState();\n"
            "console.log(JSON.stringify(J.getClarification(s)));\n"
        )
        assert result["type"] == "category"
        result2 = _run_js(
            "var c = J.getClosedChoices();\n"
            "console.log(JSON.stringify(c.categories.map(function(x){return x.id;})));\n"
        )
        assert len(result2) == 5 and set(result2) == set(_CANONICAL)

    def test_executor_source_has_required_symbols(self):
        """Executor source has action-trace, EXPLANATIONS, OPEN_ROUTE, HIGHLIGHT, SCROLL, CLICK."""
        src = (STATIC / "citizen-action-executor.js").read_text(encoding="utf-8")
        for kw in ("action-trace", "EXPLANATIONS", "OPEN_ROUTE", "HIGHLIGHT", "SCROLL", "CLICK"):
            assert kw in src


# =========================================================================
# Scenario 2 — supported facts → neutral draft → explicit approval →
#              complaint-body only
# =========================================================================


class TestFactDraftAndConfirmedPrefill:
    """Scenario 2: journey reducer selections, neutral draft, prefill payload."""

    _COMPLETE = (
        "var s = J.createInitialState();\n"
        "s = J.reduce(s,{type:'SELECT_CATEGORY',category_id:'illegal-parking'});\n"
        "s = J.reduce(s,{type:'SELECT_FACT',field_id:'location',choice_id:'roadside'});\n"
        "s = J.reduce(s,{type:'SELECT_FACT',field_id:'timing_or_recurrence',choice_id:'recent-once'});\n"
        "s = J.reduce(s,{type:'SELECT_FACT',field_id:'observed_situation',choice_id:'vehicle-blocking-passage'});\n"
        "s = J.reduce(s,{type:'SELECT_FACT',field_id:'requested_remedy',choice_id:'request-site-check'});\n"
        "s = J.reduce(s,{type:'BUILD_DRAFT'});\n"
    )

    def test_clarification_category_to_facts_to_null(self):
        """Clarification: category → facts → null after complete."""
        r = _run_js("var s=J.createInitialState();console.log(JSON.stringify(J.getClarification(s).type));")
        assert r == "category"
        r = _run_js(
            "var s=J.createInitialState();"
            "s=J.reduce(s,{type:'SELECT_CATEGORY',category_id:'illegal-parking'});"
            "console.log(JSON.stringify(J.getClarification(s).type));"
        )
        assert r == "facts"
        r = _run_js(self._COMPLETE + "console.log(JSON.stringify(J.getClarification(s)));")
        assert r is None

    def test_draft_contains_five_sections_and_no_forbidden_phrases(self):
        """Draft has 유형/위치/시간/상황/요청; no submission/legal phrases."""
        r = _run_js(self._COMPLETE + "console.log(JSON.stringify(J.getReviewDraft(s)));")
        for label in ("유형:", "위치:", "시간:", "상황:", "요청:"):
            assert label in r
        for phrase in ("제출 완료", "접수 완료", "처리 완료", "법적 판단", "기관 약속"):
            assert phrase not in r

    def test_prefill_null_before_approval_target_complaint_body_after(self):
        """prefill null pre-approval; after APPROVE_DRAFT target=complaint-body & matches draft."""
        r = _run_js(self._COMPLETE + "console.log(JSON.stringify(J.getApprovedPrefill(s)));")
        assert r is None
        js = (
            self._COMPLETE
            + "var d=J.getReviewDraft(s);"
            + "s=J.reduce(s,{type:'APPROVE_DRAFT'});"
            + "var p=J.getApprovedPrefill(s);"
            + "console.log(JSON.stringify({target:p.target_id, match:p.draft_text===d}));"
        )
        r2 = _run_js(js)
        assert r2["target"] == "complaint-body" and r2["match"] is True

    def test_prefill_penultimate_action_before_stop(self):
        """Action plan: PREFILL is penultimate, target complaint-body, confirmation=True."""
        plan = build_citizen_action_plan([
            _make("OPEN_ALLOWLISTED_ROUTE", route_id="complaint-review"),
            _make("HIGHLIGHT_ALLOWLISTED_ELEMENT", target_id="complaint-body"),
            _make("SCROLL_TO_ALLOWLISTED_ELEMENT", target_id="complaint-body"),
            _prefill(), _stop(),
        ])
        assert plan.plan_status == "guided" and len(plan.actions) == 5
        prefill_action = plan.actions[-2]
        assert prefill_action.action_type == "PREFILL_APPROVED_DRAFT"
        assert prefill_action.requires_user_confirmation is True
        assert prefill_action.target_id == "complaint-body"
        assert plan.requires_user_confirmation is True


# =========================================================================
# Scenario 3 — incomplete / ambiguous case remains safe
# =========================================================================


class TestIncompleteOrAmbiguousCase:
    """Scenario 3: partial selections, invalid events, unsupported routes."""

    def test_one_fact_selected_shows_three_missing(self):
        """One fact → missing=3; invalid category/fact events are no-op."""
        r = _run_js(
            "var s=J.createInitialState();"
            "s=J.reduce(s,{type:'SELECT_CATEGORY',category_id:'illegal-parking'});"
            "s=J.reduce(s,{type:'SELECT_FACT',field_id:'location',choice_id:'roadside'});"
            "console.log(JSON.stringify(J.getClarification(s)));"
        )
        assert r["type"] == "facts" and len(r["missing"]) == 3
        r2 = _run_js(
            "var s=J.createInitialState();"
            "var s2=J.reduce(s,{type:'SELECT_CATEGORY',category_id:'invalid-xyz'});"
            "console.log(JSON.stringify(s===s2));"
        )
        assert r2 is True
        r3 = _run_js(
            "var s=J.createInitialState();"
            "s=J.reduce(s,{type:'SELECT_CATEGORY',category_id:'illegal-parking'});"
            "var b4=s.facts.location;"
            "s=J.reduce(s,{type:'SELECT_FACT',field_id:'location',choice_id:'made-up-place'});"
            "console.log(JSON.stringify(s.facts.location===b4));"
        )
        assert r3 is True

    def test_unknown_route_plan_is_blocked_with_single_stop(self):
        """Unsupported route → blocked plan, hard_stop, single STOP with null ids."""
        plan = build_citizen_action_plan([
            _make("OPEN_ALLOWLISTED_ROUTE", route_id="nonexistent-route"), _stop(),
        ])
        assert plan.plan_status == "blocked"
        assert plan.hard_stop_required is True
        assert len(plan.actions) == 1
        assert plan.actions[0].action_type == "STOP_FOR_USER_CONFIRMATION"
        assert plan.actions[0].route_id is None
        assert plan.actions[0].target_id is None


# =========================================================================
# Scenario 4 — forged sensitive actions are blocked
# =========================================================================


class TestSensitiveActionHardStop:
    """Scenario 4: forged LOGIN/SUBMIT/UPLOAD_FILE/ENTER_IDENTITY/PAY blocked."""

    FORBIDDEN = ["LOGIN", "SUBMIT", "UPLOAD_FILE", "ENTER_IDENTITY", "PAY"]

    @pytest.mark.parametrize("forged_type", FORBIDDEN)
    def test_forged_action_blocked_and_absent(self, forged_type):
        """Each forged type → blocked plan, STOP only, forged type not in result."""
        plan = build_citizen_action_plan([
            _make(forged_type, route_id="home"), _stop(),
        ])
        assert plan.plan_status == "blocked"
        assert plan.hard_stop_required is True
        assert len(plan.actions) == 1
        assert plan.actions[0].action_type == "STOP_FOR_USER_CONFIRMATION"
        assert plan.actions[0].route_id is None and plan.actions[0].target_id is None
        assert forged_type not in [a.action_type for a in plan.actions]


# =========================================================================
# Scenario 5 — left/right dock + compact presentation contract
# =========================================================================


class TestPresentationLayout:
    """Scenario 5: static source read contract for dock/compact/form."""

    def test_html_dock_and_compact_toggle(self):
        """HTML has dock='right', choices='left right', aria-controls/expanded."""
        html = (STATIC / "citizen-action-demo.html").read_text(encoding="utf-8")
        assert 'data-copilot-dock="right"' in html
        assert 'data-copilot-dock-choices="left right"' in html
        assert 'aria-controls="copilot-rail"' in html
        assert "aria-expanded=" in html

    def test_js_has_dock_toggle_expression(self):
        """Shell JS has right→left→right toggle."""
        js = (STATIC / "citizen-copilot-shell.js").read_text(encoding="utf-8")
        assert '_currentDock === "right" ? "left" : "right"' in js
        assert "_toggleDock" in js

    def test_css_has_compact_media_query_and_translateY(self):
        """CSS has @media (max-width: 767px) and translateY."""
        css = (STATIC / "citizen-copilot-shell.css").read_text(encoding="utf-8")
        assert "@media (max-width: 767px)" in css
        assert "translateY" in css

    def test_html_no_form_or_submit(self):
        """HTML must not contain <form> or type='submit'."""
        html = (STATIC / "citizen-action-demo.html").read_text(encoding="utf-8")
        assert "<form" not in html
        assert 'type="submit"' not in html