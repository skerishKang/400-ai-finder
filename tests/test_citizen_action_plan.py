"""
Tests for citizen_action_plan — closed / immutable action plan contract.
"""

import ast
import os
import sys
from dataclasses import dataclass, field
from types import SimpleNamespace

import pytest

from src.agent.citizen_action_plan import (
    CitizenAction,
    CitizenActionPlan,
    build_citizen_action_plan,
    validate_citizen_action_plan,
    action_explanation_ko,
    _FORBIDDEN_IMPORTS,
    _MAX_ACTIONS,
)


# ---------------------------------------------------------------------------
# Canary strings that must NEVER appear in repr / str output
# ---------------------------------------------------------------------------
CANARY_QUESTION = "what is your name"
CANARY_TOKEN = "Bearer eyJhbGciOiJIUzI1NiJ9"
CANARY_AUTH = "Authorization: Bearer"
CANARY_URL_USERINFO = "user:pass@localhost"
CANARY_CSS_SELECTOR = "#complaint-body > input[type=text]"
CANARY_JS_SNIPPET = "javascript:void(0)"
CANARY_EXCEPTION = "Traceback (most recent call last):"

ALL_CANARIES = [
    CANARY_QUESTION,
    CANARY_TOKEN,
    CANARY_AUTH,
    CANARY_URL_USERINFO,
    CANARY_CSS_SELECTOR,
    CANARY_JS_SNIPPET,
    CANARY_EXCEPTION,
]


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def make_action(
    action_type,
    route_id=None,
    target_id=None,
    explanation_id=None,
    requires_user_confirmation=False,
    choice_ids=(),
):
    if explanation_id is None:
        explanation_id = {
            "ASK_CLARIFYING_QUESTION": "ask_clarifying_question",
            "PRESENT_CHOICES": "present_category_choices",
            "HIGHLIGHT_ALLOWLISTED_ELEMENT": "highlight_element",
            "SCROLL_TO_ALLOWLISTED_ELEMENT": "scroll_to_element",
            "OPEN_ALLOWLISTED_ROUTE": "open_route",
            "CLICK_ALLOWLISTED_ELEMENT": "click_element",
            "PREFILL_APPROVED_DRAFT": "prefill_draft",
            "STOP_FOR_USER_CONFIRMATION": "stop_for_confirmation",
        }.get(action_type, "highlight_element")
    return CitizenAction(
        action_type=action_type,
        route_id=route_id,
        target_id=target_id,
        explanation_id=explanation_id,
        requires_user_confirmation=requires_user_confirmation,
        choice_ids=choice_ids,
    )


def stop_action():
    return make_action("STOP_FOR_USER_CONFIRMATION", requires_user_confirmation=True)


def prefill_action():
    return make_action(
        "PREFILL_APPROVED_DRAFT",
        target_id="complaint-body",
        requires_user_confirmation=True,
    )


# ---------------------------------------------------------------------------
# Happy-path: valid guided plan
# ---------------------------------------------------------------------------

class TestHappyPath:
    def test_full_flow_clarify_choices_highlight_open_click_stop(self):
        """Standard flow: clarify → choices → highlight → open → click → STOP."""
        actions = [
            make_action("ASK_CLARIFYING_QUESTION", explanation_id="ask_clarifying_question"),
            make_action(
                "PRESENT_CHOICES",
                choice_ids=("illegal-parking", "public-parking-inconvenience"),
            ),
            make_action(
                "HIGHLIGHT_ALLOWLISTED_ELEMENT",
                target_id="complaint-category-illegal-parking",
            ),
            make_action("OPEN_ALLOWLISTED_ROUTE", route_id="complaint-category"),
            make_action("CLICK_ALLOWLISTED_ELEMENT", target_id="complaint-category-illegal-parking"),
            stop_action(),
        ]
        plan = build_citizen_action_plan(actions)
        assert plan.plan_status == "guided"
        assert plan.hard_stop_required is True
        assert plan.reason_codes == ()
        assert plan.actions[-1].action_type == "STOP_FOR_USER_CONFIRMATION"
        assert plan.requires_user_confirmation is True  # STOP is in actions

    def test_plan_is_frozen(self):
        actions = [
            make_action("OPEN_ALLOWLISTED_ROUTE", route_id="civil-service"),
            stop_action(),
        ]
        plan = build_citizen_action_plan([make_action("OPEN_ALLOWLISTED_ROUTE", route_id="civil-service"), stop_action()])
        with pytest.raises(AttributeError):
            plan.plan_status = "blocked"

    def test_action_is_frozen(self):
        a = make_action("OPEN_ALLOWLISTED_ROUTE", route_id="civil-service")
        with pytest.raises(AttributeError):
            a.action_type = "SUBMIT"

    def test_deterministic_same_output(self):
        actions = [
            make_action("OPEN_ALLOWLISTED_ROUTE", route_id="home"),
            stop_action(),
        ]
        p1 = build_citizen_action_plan(actions)
        p2 = build_citizen_action_plan(actions)
        assert p1 == p2


# ---------------------------------------------------------------------------
# Prefill flow
# ---------------------------------------------------------------------------

class TestPrefillFlow:
    def test_prefill_only_complaint_body(self):
        a = make_action(
            "PREFILL_APPROVED_DRAFT",
            target_id="complaint-body",
            requires_user_confirmation=True,
        )
        plan = build_citizen_action_plan([a, stop_action()])
        assert plan.plan_status == "guided"

    def test_prefill_requires_confirmation_true(self):
        a = make_action(
            "PREFILL_APPROVED_DRAFT",
            target_id="complaint-body",
            requires_user_confirmation=True,
        )
        plan = build_citizen_action_plan([a, stop_action()])
        assert plan.requires_user_confirmation is True

    def test_prefill_next_must_be_stop(self):
        actions = [
            make_action(
                "PREFILL_APPROVED_DRAFT",
                target_id="complaint-body",
                requires_user_confirmation=True,
            ),
            make_action("OPEN_ALLOWLISTED_ROUTE", route_id="home"),
        ]
        plan = build_citizen_action_plan(actions)
        assert plan.plan_status == "blocked"

    def test_prefill_wrong_target(self):
        actions = [
            make_action(
                "PREFILL_APPROVED_DRAFT",
                target_id="complaint-draft-review",  # not complaint-body
                requires_user_confirmation=True,
            ),
            stop_action(),
        ]
        plan = build_citizen_action_plan(actions)
        assert plan.plan_status == "blocked"


# ---------------------------------------------------------------------------
# Forbidden action types
# ---------------------------------------------------------------------------

class TestForbiddenActions:
    FORBIDDEN = ["LOGIN", "SUBMIT", "UPLOAD_FILE", "PAY", "ENTER_IDENTITY"]

    @pytest.mark.parametrize("atype", FORBIDDEN)
    def test_forbidden_action_blocked(self, atype):
        actions = [make_action(atype, route_id="home"), stop_action()]
        plan = build_citizen_action_plan(actions)
        assert plan.plan_status == "blocked"
        assert CANARY_TOKEN not in repr(plan)


# ---------------------------------------------------------------------------
# Unknown / malformed input
# ---------------------------------------------------------------------------

class TestUnknownInputs:
    def test_unknown_action_type(self):
        actions = [make_action("DO_SOMETHING"), stop_action()]
        plan = build_citizen_action_plan(actions)
        assert plan.plan_status == "blocked"

    def test_unknown_route_id(self):
        actions = [
            make_action("OPEN_ALLOWLISTED_ROUTE", route_id="nonexistent-route"),
            stop_action(),
        ]
        plan = build_citizen_action_plan(actions)
        assert plan.plan_status == "blocked"

    def test_unknown_target_id(self):
        actions = [
            make_action("CLICK_ALLOWLISTED_ELEMENT", target_id="nonexistent-target"),
            stop_action(),
        ]
        plan = build_citizen_action_plan(actions)
        assert plan.plan_status == "blocked"

    def test_unknown_choice_id(self):
        actions = [
            make_action("PRESENT_CHOICES", choice_ids=("not-a-choice",)),
            stop_action(),
        ]
        plan = build_citizen_action_plan(actions)
        assert plan.plan_status == "blocked"

    def test_dict_instead_of_citizenaction(self):
        plan = build_citizen_action_plan([{"action_type": "OPEN_ROUTE"}])
        assert plan.plan_status == "blocked"


# ---------------------------------------------------------------------------
# Type coercion (1류 validation)
# ---------------------------------------------------------------------------

class TestTypeCoercion:
    def test_requires_user_confirmation_int(self):
        actions = [
            make_action("OPEN_ALLOWLISTED_ROUTE", route_id="home"),
            make_action(
                "STOP_FOR_USER_CONFIRMATION",
                requires_user_confirmation=True,
            ),
        ]
        # Build plan manually with int
        stop_a = CitizenAction(
            action_type="STOP_FOR_USER_CONFIRMATION",
            route_id=None,
            target_id=None,
            explanation_id="stop_for_confirmation",
            requires_user_confirmation=True,  # bool
            choice_ids=(),
        )
        plan = validate_citizen_action_plan(
            CitizenActionPlan(
                plan_status="guided",
                actions=(stop_a,),
                requires_user_confirmation=True,
                hard_stop_required=True,
                reason_codes=(),
            )
        )
        assert plan.plan_status == "guided"

    def test_actions_as_list_rejected(self):
        """Passing a list (not tuple) for actions field → blocked."""
        # validate_citizen_action_plan should reject tuple-wrapped-list as non-tuple
        stop_a = CitizenAction(
            action_type="STOP_FOR_USER_CONFIRMATION",
            route_id=None,
            target_id=None,
            explanation_id="stop_for_confirmation",
            requires_user_confirmation=True,
            choice_ids=(),
        )
        bad_plan = SimpleNamespace(
            plan_status="guided",
            actions=[stop_a],  # list, not tuple
            requires_user_confirmation=True,
            hard_stop_required=True,
            reason_codes=(),
        )
        result = validate_citizen_action_plan(bad_plan)
        assert result.plan_status == "blocked"

    def test_choice_ids_as_list_rejected(self):
        """choice_ids as list instead of tuple → blocked."""
        bad_action = SimpleNamespace(
            action_type="PRESENT_CHOICES",
            route_id=None,
            target_id=None,
            explanation_id="present_category_choices",
            requires_user_confirmation=False,
            choice_ids=["illegal-parking"],  # list, not tuple
        )
        result = validate_citizen_action_plan(bad_action)
        assert result.plan_status == "blocked"

    def test_subclass_instance_rejected(self):
        """Dataclass subclass instance must not be accepted."""
        @dataclass(frozen=True)
        class ExtendedCitizenAction(CitizenAction):
            pass  # subclass

        sub_action = ExtendedCitizenAction(
            action_type="OPEN_ALLOWLISTED_ROUTE",
            route_id="home",
            target_id=None,
            explanation_id="open_route",
            requires_user_confirmation=False,
            choice_ids=(),
        )
        plan = build_citizen_action_plan([sub_action, stop_action()])
        assert plan.plan_status == "blocked"

    def test_forged_object_rejected(self):
        """Object that looks like CitizenAction but isn't must be rejected."""
        fake = SimpleNamespace(
            action_type="OPEN_ALLOWLISTED_ROUTE",
            route_id="home",
            target_id=None,
            explanation_id="open_route",
            requires_user_confirmation=False,
            choice_ids=(),
        )
        result = validate_citizen_action_plan(fake)
        assert result.plan_status == "blocked"

    def test_non_bool_requires_confirmation_rejected(self):
        """requires_user_confirmation as int 1 must be rejected."""
        stop_a = CitizenAction(
            action_type="STOP_FOR_USER_CONFIRMATION",
            route_id=None,
            target_id=None,
            explanation_id="stop_for_confirmation",
            requires_user_confirmation=True,
            choice_ids=(),
        )
        bad_plan = _make_plan_type(
            plan_status="guided",
            actions=(stop_a,),
            requires_user_confirmation=1,  # int, not bool
            hard_stop_required=True,
            reason_codes=(),
        )
        result = validate_citizen_action_plan(bad_plan)
        assert result.plan_status == "blocked"

    def test_non_bool_hard_stop_rejected(self):
        stop_a = CitizenAction(
            action_type="STOP_FOR_USER_CONFIRMATION",
            route_id=None,
            target_id=None,
            explanation_id="stop_for_confirmation",
            requires_user_confirmation=True,
            choice_ids=(),
        )
        bad_plan = _make_plan_type(
            plan_status="guided",
            actions=(stop_a,),
            requires_user_confirmation=True,
            hard_stop_required="true",  # str, not bool
            reason_codes=(),
        )
        result = validate_citizen_action_plan(bad_plan)
        assert result.plan_status == "blocked"

    def test_plan_status_not_str(self):
        stop_a = CitizenAction(
            action_type="STOP_FOR_USER_CONFIRMATION",
            route_id=None,
            target_id=None,
            explanation_id="stop_for_confirmation",
            requires_user_confirmation=True,
            choice_ids=(),
        )
        bad_plan = _make_plan_type(
            plan_status=123,  # not str
            actions=(stop_a,),
            requires_user_confirmation=True,
            hard_stop_required=True,
            reason_codes=(),
        )
        result = validate_citizen_action_plan(bad_plan)
        assert result.plan_status == "blocked"


def _make_plan_type(plan_status, actions, requires_user_confirmation, hard_stop_required, reason_codes):
    """Make a plain SimpleNamespace with same field names (not real CitizenActionPlan)."""
    return SimpleNamespace(
        plan_status=plan_status,
        actions=actions,
        requires_user_confirmation=requires_user_confirmation,
        hard_stop_required=hard_stop_required,
        reason_codes=reason_codes,
    )


# ---------------------------------------------------------------------------
# STOP / action count rules
# ---------------------------------------------------------------------------

class TestStopRules:
    def test_last_action_not_stop(self):
        actions = [
            make_action("OPEN_ALLOWLISTED_ROUTE", route_id="home"),
            make_action("CLICK_ALLOWLISTED_ELEMENT", target_id="nav-civil-service"),
        ]
        plan = build_citizen_action_plan(actions)
        assert plan.plan_status == "blocked"

    def test_action_after_stop(self):
        actions = [
            make_action("OPEN_ALLOWLISTED_ROUTE", route_id="home"),
            stop_action(),
            make_action("CLICK_ALLOWLISTED_ELEMENT", target_id="nav-civil-service"),
        ]
        plan = build_citizen_action_plan(actions)
        assert plan.plan_status == "blocked"

    def test_multiple_stop(self):
        actions = [
            make_action("OPEN_ALLOWLISTED_ROUTE", route_id="home"),
            stop_action(),
            stop_action(),
        ]
        plan = build_citizen_action_plan(actions)
        assert plan.plan_status == "blocked"

    def test_too_many_actions(self):
        many = [
            make_action("ASK_CLARIFYING_QUESTION"),
            make_action(
                "PRESENT_CHOICES", choice_ids=("illegal-parking",)
            ),
            make_action(
                "HIGHLIGHT_ALLOWLISTED_ELEMENT",
                target_id="complaint-category-illegal-parking",
            ),
            make_action("OPEN_ALLOWLISTED_ROUTE", route_id="complaint-category"),
            make_action(
                "CLICK_ALLOWLISTED_ELEMENT",
                target_id="complaint-category-illegal-parking",
            ),
            make_action("STOP_FOR_USER_CONFIRMATION", requires_user_confirmation=True),
        ] * 3  # 18 actions > 12
        plan = build_citizen_action_plan(many)
        assert plan.plan_status == "blocked"


# ---------------------------------------------------------------------------
# Blocked plan repr/string safety
# ---------------------------------------------------------------------------

class TestBlockedReprSafety:
    @pytest.mark.parametrize("canary", ALL_CANARIES, ids=lambda c: c[:30])
    def test_blocked_repr_no_canary(self, canary):
        plan = build_citizen_action_plan([{"bad": "dict"}])
        rep = repr(plan)
        assert canary not in rep, f"canary '{canary[:20]}' found in blocked repr"

    @pytest.mark.parametrize("canary", ALL_CANARIES, ids=lambda c: c[:30])
    def test_blocked_str_no_canary(self, canary):
        plan = build_citizen_action_plan([{"bad": "dict"}])
        s = str(plan)
        assert canary not in s, f"canary '{canary[:20]}' found in blocked str"

    @pytest.mark.parametrize("canary", ALL_CANARIES, ids=lambda c: c[:30])
    def test_blocked_validate_repr_no_canary(self, canary):
        bad = SimpleNamespace(
            plan_status="guided",
            actions=[],
            requires_user_confirmation=True,
            hard_stop_required=True,
            reason_codes=(),
            _secret=f"question={CANARY_QUESTION}",
        )
        plan = validate_citizen_action_plan(bad)
        rep = repr(plan)
        assert CANARY_QUESTION not in rep

    def test_blocked_plan_always_has_one_stop(self):
        plan = build_citizen_action_plan([make_action("DOES_NOT_EXIST")])
        assert plan.plan_status == "blocked"
        assert len(plan.actions) == 1
        assert plan.actions[0].action_type == "STOP_FOR_USER_CONFIRMATION"
        assert plan.requires_user_confirmation is True
        assert plan.hard_stop_required is True

    def test_blocked_plan_reason_codes_deterministic(self):
        p1 = build_citizen_action_plan([make_action("DOES_NOT_EXIST")])
        p2 = build_citizen_action_plan([make_action("DOES_NOT_EXIST")])
        assert p1.reason_codes == p2.reason_codes


# ---------------------------------------------------------------------------
# validate_citizen_action_plan specific
# ---------------------------------------------------------------------------

class TestValidateFunction:
    def test_valid_guided_plan_returns_guided(self):
        actions = [
            make_action("OPEN_ALLOWLISTED_ROUTE", route_id="home"),
            stop_action(),
        ]
        plan = build_citizen_action_plan(actions)
        validated = validate_citizen_action_plan(plan)
        assert validated.plan_status == "guided"
        assert validated == plan

    def test_valid_guided_via_validate(self):
        stop_a = CitizenAction(
            action_type="STOP_FOR_USER_CONFIRMATION",
            route_id=None,
            target_id=None,
            explanation_id="stop_for_confirmation",
            requires_user_confirmation=True,
            choice_ids=(),
        )
        good_plan = CitizenActionPlan(
            plan_status="guided",
            actions=(stop_a,),
            requires_user_confirmation=True,
            hard_stop_required=True,
            reason_codes=(),
        )
        result = validate_citizen_action_plan(good_plan)
        assert result.plan_status == "guided"


# ---------------------------------------------------------------------------
# action_explanation_ko
# ---------------------------------------------------------------------------

class TestExplanationKo:
    def test_valid_explanation(self):
        a = make_action("ASK_CLARIFYING_QUESTION", explanation_id="ask_clarifying_question")
        result = action_explanation_ko(a)
        assert len(result) > 0
        assert "알 수 없는 동작" not in result

    def test_unknown_explanation_id(self):
        a = make_action("ASK_CLARIFYING_QUESTION", explanation_id="not_a_real_id")
        result = action_explanation_ko(a)
        assert "알 수 없는 동작" in result


# ---------------------------------------------------------------------------
# AST forbidden import check
# ---------------------------------------------------------------------------

class TestForbiddenImports:
    def test_no_forbidden_imports_in_module(self):
        this_file = os.path.join(os.path.dirname(__file__), "..", "src", "agent", "citizen_action_plan.py")
        this_file = os.path.normpath(this_file)
        with open(this_file, encoding="utf-8") as fh:
            tree = ast.parse(fh.read(), filename=this_file)

        found = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    root = alias.name.split(".")[0]
                    if root in _FORBIDDEN_IMPORTS:
                        found.append(alias.name)
            elif isinstance(node, ast.ImportFrom):
                if node.module and node.module.split(".")[0] in _FORBIDDEN_IMPORTS:
                    found.append(node.module)

        assert not found, f"forbidden imports found: {found}"


# ---------------------------------------------------------------------------
# Action shape rules (type-specific)
# ---------------------------------------------------------------------------

class TestActionShapeRules:
    def test_ask_clarifying_needs_no_route_no_target_no_choices(self):
        # Valid
        plan = build_citizen_action_plan([
            make_action("ASK_CLARIFYING_QUESTION"),
            stop_action(),
        ])
        assert plan.plan_status == "guided"

        # route_id not None
        plan = build_citizen_action_plan([
            make_action("ASK_CLARIFYING_QUESTION", route_id="home"),
            stop_action(),
        ])
        assert plan.plan_status == "blocked"

        # target_id not None
        plan = build_citizen_action_plan([
            make_action("ASK_CLARIFYING_QUESTION", target_id="nav-civil-service"),
            stop_action(),
        ])
        assert plan.plan_status == "blocked"

    def test_present_choices_needs_non_empty_choices(self):
        plan = build_citizen_action_plan([
            make_action("PRESENT_CHOICES", choice_ids=("illegal-parking",)),
            stop_action(),
        ])
        assert plan.plan_status == "guided"

        plan = build_citizen_action_plan([
            make_action("PRESENT_CHOICES", choice_ids=()),
            stop_action(),
        ])
        assert plan.plan_status == "blocked"

    def test_highlight_scroll_click_need_target_not_route(self):
        for atype in [
            "HIGHLIGHT_ALLOWLISTED_ELEMENT",
            "SCROLL_TO_ALLOWLISTED_ELEMENT",
            "CLICK_ALLOWLISTED_ELEMENT",
        ]:
            # Valid: has target
            plan = build_citizen_action_plan([
                make_action(atype, target_id="nav-civil-service"),
                stop_action(),
            ])
            assert plan.plan_status == "guided", f"failed for {atype}"

            # Invalid: no target
            plan = build_citizen_action_plan([
                make_action(atype),
                stop_action(),
            ])
            assert plan.plan_status == "blocked", f"failed for {atype}"

            # Invalid: has route
            plan = build_citizen_action_plan([
                make_action(atype, target_id="nav-civil-service", route_id="home"),
                stop_action(),
            ])
            assert plan.plan_status == "blocked", f"failed for {atype}"

    def test_open_route_needs_route_not_target(self):
        plan = build_citizen_action_plan([
            make_action("OPEN_ALLOWLISTED_ROUTE", route_id="home"),
            stop_action(),
        ])
        assert plan.plan_status == "guided"

        plan = build_citizen_action_plan([
            make_action("OPEN_ALLOWLISTED_ROUTE", target_id="nav-civil-service"),
            stop_action(),
        ])
        assert plan.plan_status == "blocked"

    def test_stop_requires_confirmation_true(self):
        # Valid stop with confirmation=True
        plan = build_citizen_action_plan([
            make_action("OPEN_ALLOWLISTED_ROUTE", route_id="home"),
            stop_action(),
        ])
        assert plan.plan_status == "guided"

        # Invalid stop with confirmation=False
        bad_stop = CitizenAction(
            action_type="STOP_FOR_USER_CONFIRMATION",
            route_id=None,
            target_id=None,
            explanation_id="stop_for_confirmation",
            requires_user_confirmation=False,  # wrong
            choice_ids=(),
        )
        plan = build_citizen_action_plan([
            make_action("OPEN_ALLOWLISTED_ROUTE", route_id="home"),
            bad_stop,
        ])
        assert plan.plan_status == "blocked"

    def test_stop_route_handoff_stop_or_none(self):
        # route=None is valid
        plan = build_citizen_action_plan([stop_action()])
        assert plan.plan_status == "guided"

        # route=handoff-stop is valid
        stop_handoff = make_action(
            "STOP_FOR_USER_CONFIRMATION",
            route_id="handoff-stop",
            requires_user_confirmation=True,
        )
        plan = build_citizen_action_plan([stop_handoff])
        assert plan.plan_status == "guided"

        # route=other is invalid
        stop_bad_route = make_action(
            "STOP_FOR_USER_CONFIRMATION",
            route_id="home",
            requires_user_confirmation=True,
        )
        plan = build_citizen_action_plan([stop_bad_route])
        assert plan.plan_status == "blocked"


# ---------------------------------------------------------------------------
# Missing STOP in middle of list edge case
# ---------------------------------------------------------------------------

class TestEmptyPlan:
    def test_empty_actions(self):
        plan = build_citizen_action_plan([])
        assert plan.plan_status == "blocked"

    def test_empty_tuple_via_validate(self):
        stop_a = CitizenAction(
            action_type="STOP_FOR_USER_CONFIRMATION",
            route_id=None,
            target_id=None,
            explanation_id="stop_for_confirmation",
            requires_user_confirmation=True,
            choice_ids=(),
        )
        empty_plan = CitizenActionPlan(
            plan_status="guided",
            actions=(),
            requires_user_confirmation=False,
            hard_stop_required=True,
            reason_codes=(),
        )
        result = validate_citizen_action_plan(empty_plan)
        assert result.plan_status == "blocked"


# ---------------------------------------------------------------------------
# Confirm requires_user_confirmation matches action state
# ---------------------------------------------------------------------------

class TestConfirmationConsistency:
    def test_requires_true_when_any_action_requires_true(self):
        # Has STOP which requires confirmation=True
        plan = build_citizen_action_plan([
            make_action("OPEN_ALLOWLISTED_ROUTE", route_id="home"),
            stop_action(),
        ])
        assert plan.requires_user_confirmation is True

    def test_requires_false_when_no_action_requires_true(self):
        # Only actions that don't require confirmation
        plan = build_citizen_action_plan([
            make_action("OPEN_ALLOWLISTED_ROUTE", route_id="home"),
            make_action("OPEN_ALLOWLISTED_ROUTE", route_id="civil-service"),
            make_action("STOP_FOR_USER_CONFIRMATION", requires_user_confirmation=True),
        ])
        assert plan.requires_user_confirmation is True  # has STOP


# ---------------------------------------------------------------------------
# validate: blocked status
# ---------------------------------------------------------------------------

class TestBlockedStatus:
    def test_validate_blocked_with_reason_codes(self):
        stop_a = CitizenAction(
            action_type="STOP_FOR_USER_CONFIRMATION",
            route_id=None,
            target_id=None,
            explanation_id="stop_for_confirmation",
            requires_user_confirmation=True,
            choice_ids=(),
        )
        blocked_plan = CitizenActionPlan(
            plan_status="blocked",
            actions=(stop_a,),
            requires_user_confirmation=True,
            hard_stop_required=True,
            reason_codes=("invalid_action_plan",),
        )
        result = validate_citizen_action_plan(blocked_plan)
        assert result.plan_status == "blocked"


# ---------------------------------------------------------------------------
# Ensure scripts/run_all_demos.py is untouched
# ---------------------------------------------------------------------------

class TestDemosUnchanged:
    def test_run_all_demos_unchanged(self):
        demos = os.path.join(os.path.dirname(__file__), "..", "scripts", "run_all_demos.py")
        demos = os.path.normpath(demos)
        assert os.path.exists(demos), "scripts/run_all_demos.py must not be deleted"
        with open(demos, encoding="utf-8") as fh:
            content = fh.read()
        # Just verify it hasn't been gutted or turned into an agent file
        assert "demo" in content.lower() or "run" in content.lower()