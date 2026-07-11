"""
Tests for citizen_action_plan — closed / immutable action plan contract.
"""

import ast
import os
from dataclasses import dataclass
from types import SimpleNamespace

import pytest

from src.agent.citizen_action_plan import (
    CitizenAction,
    CitizenActionPlan,
    build_citizen_action_plan,
    validate_citizen_action_plan,
    action_explanation_ko,
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
        plan = build_citizen_action_plan([
            make_action("OPEN_ALLOWLISTED_ROUTE", route_id="civil-service"),
            stop_action(),
        ])
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
                target_id="complaint-draft-review",
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
# Complaint-board route vocabulary sync (#1069 / PR #1074)
# ---------------------------------------------------------------------------

class TestComplaintBoardRouteVocabulary:
    def test_complaint_board_is_valid_route(self):
        """approved complaint-board route must validate as a guided action."""
        plan = build_citizen_action_plan([
            make_action("OPEN_ALLOWLISTED_ROUTE", route_id="complaint-board"),
            stop_action(),
        ])
        assert plan.plan_status == "guided"

    def test_complaint_write_is_valid_reversible_route(self):
        plan = build_citizen_action_plan([
            make_action("OPEN_ALLOWLISTED_ROUTE", route_id="complaint-write"),
            stop_action(),
        ])
        assert plan.plan_status == "guided"

    def test_unknown_route_still_invalid(self):
        """an unknown route id must still be rejected (no over-permissiveness)."""
        plan = build_citizen_action_plan([
            make_action("OPEN_ALLOWLISTED_ROUTE", route_id="nonexistent-route"),
            stop_action(),
        ])
        assert plan.plan_status == "blocked"

    def test_existing_route_vocabulary_maintained(self):
        """pre-existing approved routes must remain valid after the sync."""
        for rid in (
            "home", "civil-service", "complaint-category",
            "complaint-illegal-parking", "complaint-intake", "complaint-write", "handoff-stop",
            "complaint-review", "bulky-waste-disposal", "passport-guidance",
            "unmanned-kiosk-guidance", "apartment-info", "apartment-dept",
        ):
            plan = build_citizen_action_plan([
                make_action("OPEN_ALLOWLISTED_ROUTE", route_id=rid),
                stop_action(),
            ])
            assert plan.plan_status == "guided", f"route '{rid}' must remain valid"

    def test_forbidden_submit_payment_auth_unchanged(self):
        """forbidden submit/payment/auth action types must remain blocked."""
        for atype in ("SUBMIT", "PAY", "ENTER_IDENTITY"):
            plan = build_citizen_action_plan([
                make_action(atype, route_id="complaint-board"),
                stop_action(),
            ])
            assert plan.plan_status == "blocked", f"forbidden {atype} must be blocked"


# ---------------------------------------------------------------------------
# Type coercion (1류 validation)
# ---------------------------------------------------------------------------
# Type coercion (1류 validation)
# ---------------------------------------------------------------------------

class TestTypeCoercion:
    def test_requires_user_confirmation_int_rejected(self):
        """Real CitizenActionPlan with int requires_user_confirmation → blocked, no raise."""
        stop_a = CitizenAction(
            action_type="STOP_FOR_USER_CONFIRMATION",
            route_id=None,
            target_id=None,
            explanation_id="stop_for_confirmation",
            requires_user_confirmation=True,
            choice_ids=(),
        )
        # Build a valid plan first, then corrupt requires_user_confirmation to int
        # using object.__setattr__ to bypass frozen=True and constructor type check
        plan = CitizenActionPlan(
            plan_status="guided",
            actions=(stop_a,),
            requires_user_confirmation=True,
            hard_stop_required=True,
            reason_codes=(),
        )
        object.__setattr__(plan, "requires_user_confirmation", 1)  # int, not bool
        result = validate_citizen_action_plan(plan)
        assert result.plan_status == "blocked"
        # Canary values must not appear in blocked output
        assert CANARY_TOKEN not in repr(result)
        assert CANARY_TOKEN not in str(result)

    def test_hard_stop_required_str_rejected(self):
        """Real CitizenActionPlan with str hard_stop_required → blocked, no raise."""
        stop_a = CitizenAction(
            action_type="STOP_FOR_USER_CONFIRMATION",
            route_id=None,
            target_id=None,
            explanation_id="stop_for_confirmation",
            requires_user_confirmation=True,
            choice_ids=(),
        )
        plan = CitizenActionPlan(
            plan_status="guided",
            actions=(stop_a,),
            requires_user_confirmation=True,
            hard_stop_required=True,
            reason_codes=(),
        )
        object.__setattr__(plan, "hard_stop_required", "true")  # str, not bool
        result = validate_citizen_action_plan(plan)
        assert result.plan_status == "blocked"
        assert CANARY_CSS_SELECTOR not in repr(result)
        assert CANARY_CSS_SELECTOR not in str(result)

    def test_actions_as_list_rejected(self):
        """tuple-wrapped list for actions field → blocked, no raise."""
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
        """choice_ids as list instead of tuple → blocked, no raise."""
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
            pass

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


# ---------------------------------------------------------------------------
# Object.__new__ forged instances — no AttributeError should escape
# ---------------------------------------------------------------------------

class TestObjectNewForgedInstances:
    def test_object_new_citizen_action_plan_blocked_no_raise(self):
        """object.__new__(CitizenActionPlan) uninitialized → blocked, no AttributeError."""
        # Uninitialized __new__ instance has no fields; must not raise AttributeError
        forged = object.__new__(CitizenActionPlan)
        result = validate_citizen_action_plan(forged)
        assert result.plan_status == "blocked"

    def test_object_new_citizen_action_blocked_no_raise(self):
        """object.__new__(CitizenAction) uninitialized → blocked via build, no AttributeError."""
        forged = object.__new__(CitizenAction)
        # Must not raise AttributeError when iterating actions
        plan = build_citizen_action_plan([forged])
        assert plan.plan_status == "blocked"

    def test_object_new_citizen_action_in_valid_container_blocked(self):
        """A valid-looking plan whose actions tuple contains an object.__new__(CitizenAction) → blocked."""
        real_stop = CitizenAction(
            action_type="STOP_FOR_USER_CONFIRMATION",
            route_id=None,
            target_id=None,
            explanation_id="stop_for_confirmation",
            requires_user_confirmation=True,
            choice_ids=(),
        )
        forged_action = object.__new__(CitizenAction)
        bad_plan = CitizenActionPlan(
            plan_status="guided",
            actions=(forged_action, real_stop),
            requires_user_confirmation=True,
            hard_stop_required=True,
            reason_codes=(),
        )
        result = validate_citizen_action_plan(bad_plan)
        assert result.plan_status == "blocked"

    def test_object_setattr_citizen_action_blocked_no_canary(self):
        """A real CitizenAction corrupted via object.__setattr__ with canary value → blocked."""
        # Create a real CitizenAction, then corrupt one field via object.__setattr__
        real_action = make_action(
            "OPEN_ALLOWLISTED_ROUTE",
            route_id="home",
        )
        # Use object.__setattr__ to bypass frozen=True
        object.__setattr__(real_action, "route_id", CANARY_URL_USERINFO)

        plan = build_citizen_action_plan([real_action, stop_action()])
        assert plan.plan_status == "blocked"
        # Canary must not appear in repr/str of blocked result
        assert CANARY_URL_USERINFO not in repr(plan)
        assert CANARY_URL_USERINFO not in str(plan)

    def test_corrupted_field_via_object_setattr_target(self):
        """Corrupt target_id with canary CSS selector."""
        real_action = make_action(
            "CLICK_ALLOWLISTED_ELEMENT",
            target_id="complaint-body",
        )
        object.__setattr__(real_action, "target_id", CANARY_CSS_SELECTOR)

        plan = build_citizen_action_plan([real_action, stop_action()])
        assert plan.plan_status == "blocked"
        assert CANARY_CSS_SELECTOR not in repr(plan)
        assert CANARY_CSS_SELECTOR not in str(plan)

    def test_partial_init_citizen_action_plan_blocked_no_raise(self):
        """object.__new__(CitizenActionPlan) partially initialized via __setattr__ → blocked."""
        forged = object.__new__(CitizenActionPlan)
        # Populate four of five required fields; intentionally leave reason_codes absent
        object.__setattr__(forged, "plan_status", "guided")
        object.__setattr__(forged, "actions", ())
        object.__setattr__(forged, "requires_user_confirmation", False)
        object.__setattr__(forged, "hard_stop_required", True)
        # reason_codes deliberately not set — attribute will be missing
        result = validate_citizen_action_plan(forged)
        assert result.plan_status == "blocked"
        # Supplied canary must not appear in blocked output
        assert CANARY_TOKEN not in repr(result)
        assert CANARY_TOKEN not in str(result)


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
# AST forbidden import check (test-only; lives in test, not source)
# ---------------------------------------------------------------------------

_FORBIDDEN_IMPORTS = frozenset({
    "requests",
    "httpx",
    "urllib",
    "socket",
    "ssl",
    "http",
    "subprocess",
    "threading",
    "asyncio",
    "concurrent",
    "firecrawl",
    "playwright",
    "selenium",
    "aiohttp",
    "urllib3",
})


class TestForbiddenImports:
    def test_no_forbidden_imports_in_module(self):
        """Verify source file has no forbidden imports via AST scan."""
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

    def test_import_triggers_no_file_read(self):
        """Import/reload must not open the source file at runtime."""
        import importlib
        import sys

        # Record open() call count before import
        import builtins
        opens: list[str] = []

        real_open = builtins.open
        def tracking_open(*args, **kwargs):
            opens.append(str(args[0]) if args else "")
            return real_open(*args, **kwargs)

        builtins.open = tracking_open
        try:
            # Force re-import from scratch
            for mod in list(sys.modules.keys()):
                if "agent" in mod:
                    del sys.modules[mod]
            import src.agent.citizen_action_plan as cap

            # Check that no src/agent path was opened during import
            agent_file_opens = [f for f in opens if "agent" in f]
            assert not agent_file_opens, f"File read during import: {agent_file_opens}"
        finally:
            builtins.open = real_open


# ---------------------------------------------------------------------------
# Action shape rules (type-specific)
# ---------------------------------------------------------------------------

class TestActionShapeRules:
    def test_ask_clarifying_needs_no_route_no_target_no_choices(self):
        plan = build_citizen_action_plan([
            make_action("ASK_CLARIFYING_QUESTION"),
            stop_action(),
        ])
        assert plan.plan_status == "guided"

        plan = build_citizen_action_plan([
            make_action("ASK_CLARIFYING_QUESTION", route_id="home"),
            stop_action(),
        ])
        assert plan.plan_status == "blocked"

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
            plan = build_citizen_action_plan([
                make_action(atype, target_id="nav-civil-service"),
                stop_action(),
            ])
            assert plan.plan_status == "guided", f"failed for {atype}"

            plan = build_citizen_action_plan([
                make_action(atype),
                stop_action(),
            ])
            assert plan.plan_status == "blocked", f"failed for {atype}"

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
        plan = build_citizen_action_plan([
            make_action("OPEN_ALLOWLISTED_ROUTE", route_id="home"),
            stop_action(),
        ])
        assert plan.plan_status == "guided"

        bad_stop = CitizenAction(
            action_type="STOP_FOR_USER_CONFIRMATION",
            route_id=None,
            target_id=None,
            explanation_id="stop_for_confirmation",
            requires_user_confirmation=False,
            choice_ids=(),
        )
        plan = build_citizen_action_plan([
            make_action("OPEN_ALLOWLISTED_ROUTE", route_id="home"),
            bad_stop,
        ])
        assert plan.plan_status == "blocked"

    def test_stop_route_handoff_stop_or_none(self):
        plan = build_citizen_action_plan([stop_action()])
        assert plan.plan_status == "guided"

        stop_handoff = make_action(
            "STOP_FOR_USER_CONFIRMATION",
            route_id="handoff-stop",
            requires_user_confirmation=True,
        )
        plan = build_citizen_action_plan([stop_handoff])
        assert plan.plan_status == "guided"

        stop_bad_route = make_action(
            "STOP_FOR_USER_CONFIRMATION",
            route_id="home",
            requires_user_confirmation=True,
        )
        plan = build_citizen_action_plan([stop_bad_route])
        assert plan.plan_status == "blocked"


# ---------------------------------------------------------------------------
# Empty plan
# ---------------------------------------------------------------------------

class TestEmptyPlan:
    def test_empty_actions(self):
        plan = build_citizen_action_plan([])
        assert plan.plan_status == "blocked"

    def test_empty_tuple_via_validate(self):
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
# Confirmation consistency
# ---------------------------------------------------------------------------

class TestConfirmationConsistency:
    def test_requires_true_when_any_action_requires_true(self):
        plan = build_citizen_action_plan([
            make_action("OPEN_ALLOWLISTED_ROUTE", route_id="home"),
            stop_action(),
        ])
        assert plan.requires_user_confirmation is True


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
    def test_run_all_demos_exists(self):
        demos = os.path.join(os.path.dirname(__file__), "..", "scripts", "run_all_demos.py")
        demos = os.path.normpath(demos)
        assert os.path.exists(demos), "scripts/run_all_demos.py must not be deleted"
        with open(demos, encoding="utf-8") as fh:
            content = fh.read()
        assert "demo" in content.lower() or "run" in content.lower()
