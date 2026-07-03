"""
CitizenActionPlan — closed / immutable contract for bukgu click-navigator action plans.

No live network, no LLM calls, no DOM/UI code.  Pure business-rule validation only.
"""

from __future__ import annotations

import ast
import os
from dataclasses import dataclass

# ---------------------------------------------------------------------------
# Vocabulary allowlists
# ---------------------------------------------------------------------------

_VALID_PLAN_STATUSES: frozenset[str] = frozenset({"guided", "blocked"})

_VALID_ACTION_TYPES: frozenset[str] = frozenset({
    "ASK_CLARIFYING_QUESTION",
    "PRESENT_CHOICES",
    "HIGHLIGHT_ALLOWLISTED_ELEMENT",
    "SCROLL_TO_ALLOWLISTED_ELEMENT",
    "OPEN_ALLOWLISTED_ROUTE",
    "CLICK_ALLOWLISTED_ELEMENT",
    "PREFILL_APPROVED_DRAFT",
    "STOP_FOR_USER_CONFIRMATION",
})

_FORBIDDEN_ACTION_TYPES: frozenset[str] = frozenset({
    "LOGIN",
    "SUBMIT",
    "UPLOAD_FILE",
    "PAY",
    "ENTER_IDENTITY",
})

_VALID_ROUTE_IDS: frozenset[str] = frozenset({
    "home",
    "civil-service",
    "complaint-category",
    "complaint-intake",
    "complaint-review",
    "handoff-stop",
})

_VALID_TARGET_IDS: frozenset[str] = frozenset({
    "nav-civil-service",
    "nav-complaint-category",
    "complaint-category-illegal-parking",
    "complaint-category-public-parking-inconvenience",
    "complaint-category-residential-parking",
    "complaint-category-traffic-or-facility-safety",
    "complaint-category-other-or-unsure",
    "complaint-body",
    "complaint-draft-review",
    "confirm-draft-prefill",
    "handoff-notice",
})

_VALID_CHOICE_IDS: frozenset[str] = frozenset({
    "illegal-parking",
    "public-parking-inconvenience",
    "residential-parking",
    "traffic-or-facility-safety",
    "other-or-unsure",
})

_REASON_CODES: frozenset[str] = frozenset({
    "invalid_action_plan",
    "invalid_action_shape",
    "unknown_action_type",
    "unknown_route_id",
    "unknown_target_id",
    "invalid_choice_id",
    "confirmation_required",
    "sensitive_action_blocked",
    "hard_stop_required",
})

_EXPLANATION_IDS: frozenset[str] = frozenset({
    "ask_clarifying_question",
    "present_category_choices",
    "highlight_element",
    "scroll_to_element",
    "open_route",
    "click_element",
    "prefill_draft",
    "stop_for_confirmation",
})

_MAX_ACTIONS = 12

# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class CitizenAction:
    action_type: str
    route_id: str | None
    target_id: str | None
    explanation_id: str
    requires_user_confirmation: bool
    choice_ids: tuple[str, ...] = ()


@dataclass(frozen=True)
class CitizenActionPlan:
    plan_status: str
    actions: tuple[CitizenAction, ...]
    requires_user_confirmation: bool
    hard_stop_required: bool
    reason_codes: tuple[str, ...]

    def __post_init__(self) -> None:
        # frozen=True gives immutability; post_init is for validation only
        pass


# ---------------------------------------------------------------------------
# Explanation strings (Korean, closed vocabulary)
# ---------------------------------------------------------------------------

_EXPLANATION_KO: dict[str, str] = {
    "ask_clarifying_question": "질문을 통해 내용을 확인하고 있습니다.",
    "present_category_choices": "해당 상황에 맞는 민원 유형을 선택해 주세요.",
    "highlight_element": "화면에서 필요한 항목을 강조하여 보여드리고 있습니다.",
    "scroll_to_element": "필요한 위치로 스크롤하고 있습니다.",
    "open_route": "해당 페이지로 이동합니다.",
    "click_element": "해당 항목을 클릭합니다.",
    "prefill_draft": "입력하신 내용을 바탕으로 작성 중인 민원 초안을 준비했습니다.",
    "stop_for_confirmation": "확인이 필요합니다. 계속 진행하려면 사용자의 확인이 필요합니다.",
}


def action_explanation_ko(action: CitizenAction) -> str:
    """Return the fixed Korean-language explanation for an action."""
    return _EXPLANATION_KO.get(action.explanation_id, "알 수 없는 동작입니다.")


# ---------------------------------------------------------------------------
# Forbidden-import checker (AST scan of this module)
# ---------------------------------------------------------------------------

_FORBIDDEN_IMPORTS: frozenset[str] = frozenset({
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

# Pre-verify on import — raise if any forbidden import found
_this_file = os.path.join(os.path.dirname(__file__), "citizen_action_plan.py")
with open(_this_file, encoding="utf-8") as fh:
    _tree = ast.parse(fh.read(), filename=_this_file)

for node in ast.walk(_tree):
    if isinstance(node, ast.Import):
        for alias in node.names:
            root = alias.name.split(".")[0]
            if root in _FORBIDDEN_IMPORTS:
                raise ImportError(f"forbidden import: {alias.name}")
    elif isinstance(node, ast.ImportFrom):
        if node.module and node.module.split(".")[0] in _FORBIDDEN_IMPORTS:
            raise ImportError(f"forbidden import: {node.module}")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _is_exact_instance(obj: object, cls: type) -> bool:
    """Return True only when obj is exactly cls (not a subclass)."""
    return type(obj) is cls


def _validate_bool(value: object, field: str) -> bool:
    if type(value) is not bool:
        raise ValueError(f"{field} must be bool, got {type(value).__name__}")
    return True


def _validate_tuple_of_str(value: object, field: str) -> tuple[str, ...]:
    if type(value) is not tuple:
        raise ValueError(f"{field} must be tuple, got {type(value).__name__}")
    for item in value:
        if type(item) is not str:
            raise ValueError(f"{field} must contain only str, got {type(item).__name__}")
    return value  # type: ignore[return-value]


def _normalize_reason_codes(codes: object) -> tuple[str, ...]:
    """Normalize to sorted deduped tuple from closed vocabulary only."""
    if not isinstance(codes, (tuple, list, set, frozenset)):
        codes = ()
    seen: set[str] = set()
    result: list[str] = []
    for c in codes:
        if type(c) is str and c in _REASON_CODES and c not in seen:
            seen.add(c)
            result.append(c)
    result.sort()
    return tuple(result)


def _build_blocked_plan(reasons: object = ()) -> CitizenActionPlan:
    """Return a canonical blocked plan with one STOP action."""
    reason_codes = _normalize_reason_codes(reasons)
    stop_action = CitizenAction(
        action_type="STOP_FOR_USER_CONFIRMATION",
        route_id=None,
        target_id=None,
        explanation_id="stop_for_confirmation",
        requires_user_confirmation=True,
        choice_ids=(),
    )
    return CitizenActionPlan(
        plan_status="blocked",
        actions=(stop_action,),
        requires_user_confirmation=True,
        hard_stop_required=True,
        reason_codes=reason_codes,
    )


# ---------------------------------------------------------------------------
# Per-action validation
# ---------------------------------------------------------------------------

def _validate_action(action: object) -> CitizenAction:
    if not _is_exact_instance(action, CitizenAction):
        raise ValueError("action must be exact CitizenAction instance")

    # Validate field types strictly
    atype = action.action_type
    rid = action.route_id
    tid = action.target_id
    eid = action.explanation_id
    ruc = action.requires_user_confirmation
    cids = action.choice_ids

    if type(atype) is not str:
        raise ValueError("action_type must be str")
    if rid is not None and type(rid) is not str:
        raise ValueError("route_id must be str or None")
    if tid is not None and type(tid) is not str:
        raise ValueError("target_id must be str or None")
    if type(eid) is not str:
        raise ValueError("explanation_id must be str")
    _validate_bool(ruc, "requires_user_confirmation")
    _validate_tuple_of_str(cids, "choice_ids")

    # Forbidden action types
    if atype in _FORBIDDEN_ACTION_TYPES:
        raise ValueError(f"forbidden action_type: {atype}")

    # Unknown action type
    if atype not in _VALID_ACTION_TYPES:
        raise ValueError(f"unknown action_type: {atype}")

    # explanation_id must be from closed vocabulary
    if eid not in _EXPLANATION_IDS:
        raise ValueError(f"unknown explanation_id: {eid}")

    # Shape rules by action_type
    if atype == "ASK_CLARIFYING_QUESTION":
        if rid is not None:
            raise ValueError("ASK_CLARIFYING_QUESTION requires route_id=None")
        if tid is not None:
            raise ValueError("ASK_CLARIFYING_QUESTION requires target_id=None")
        if cids:
            raise ValueError("ASK_CLARIFYING_QUESTION requires choice_ids=()")
        if ruc:
            raise ValueError("ASK_CLARIFYING_QUESTION requires requires_user_confirmation=False")

    elif atype == "PRESENT_CHOICES":
        if rid is not None:
            raise ValueError("PRESENT_CHOICES requires route_id=None")
        if tid is not None:
            raise ValueError("PRESENT_CHOICES requires target_id=None")
        if not cids:
            raise ValueError("PRESENT_CHOICES requires non-empty choice_ids")
        for cid in cids:
            if cid not in _VALID_CHOICE_IDS:
                raise ValueError(f"invalid choice_id: {cid}")
        if ruc:
            raise ValueError("PRESENT_CHOICES requires requires_user_confirmation=False")

    elif atype in (
        "HIGHLIGHT_ALLOWLISTED_ELEMENT",
        "SCROLL_TO_ALLOWLISTED_ELEMENT",
        "CLICK_ALLOWLISTED_ELEMENT",
    ):
        if tid is None:
            raise ValueError(f"{atype} requires target_id (allowlist)")
        if tid not in _VALID_TARGET_IDS:
            raise ValueError(f"unknown target_id: {tid}")
        if rid is not None:
            raise ValueError(f"{atype} requires route_id=None")
        if cids:
            raise ValueError(f"{atype} requires choice_ids=()")
        if ruc:
            raise ValueError(f"{atype} requires requires_user_confirmation=False")

    elif atype == "OPEN_ALLOWLISTED_ROUTE":
        if rid is None:
            raise ValueError("OPEN_ALLOWLISTED_ROUTE requires route_id (allowlist)")
        if rid not in _VALID_ROUTE_IDS:
            raise ValueError(f"unknown route_id: {rid}")
        if tid is not None:
            raise ValueError("OPEN_ALLOWLISTED_ROUTE requires target_id=None")
        if cids:
            raise ValueError("OPEN_ALLOWLISTED_ROUTE requires choice_ids=()")
        if ruc:
            raise ValueError("OPEN_ALLOWLISTED_ROUTE requires requires_user_confirmation=False")

    elif atype == "PREFILL_APPROVED_DRAFT":
        if tid != "complaint-body":
            raise ValueError("PREFILL_APPROVED_DRAFT requires target_id='complaint-body'")
        if rid is not None:
            raise ValueError("PREFILL_APPROVED_DRAFT requires route_id=None")
        if cids:
            raise ValueError("PREFILL_APPROVED_DRAFT requires choice_ids=()")
        if not ruc:
            raise ValueError("PREFILL_APPROVED_DRAFT requires requires_user_confirmation=True")

    elif atype == "STOP_FOR_USER_CONFIRMATION":
        if tid is not None:
            raise ValueError("STOP_FOR_USER_CONFIRMATION requires target_id=None")
        if rid is not None and rid != "handoff-stop":
            raise ValueError("STOP_FOR_USER_CONFIRMATION requires route_id=None or 'handoff-stop'")
        if cids:
            raise ValueError("STOP_FOR_USER_CONFIRMATION requires choice_ids=()")
        if not ruc:
            raise ValueError("STOP_FOR_USER_CONFIRMATION requires requires_user_confirmation=True")

    return action


# ---------------------------------------------------------------------------
# Plan-level validation
# ---------------------------------------------------------------------------

def _validate_guided_plan(plan: CitizenActionPlan) -> CitizenActionPlan:
    actions = plan.actions

    if not actions:
        raise ValueError("guided plan must have at least one action")

    if len(actions) > _MAX_ACTIONS:
        raise ValueError(f"too many actions ({len(actions)}), max is {_MAX_ACTIONS}")

    for a in actions:
        _validate_action(a)

    # Last action must be STOP
    last = actions[-1]
    if last.action_type != "STOP_FOR_USER_CONFIRMATION":
        raise ValueError("last action must be STOP_FOR_USER_CONFIRMATION")

    # No action after STOP
    for i, a in enumerate(actions[:-1]):
        if a.action_type == "STOP_FOR_USER_CONFIRMATION":
            raise ValueError(f"action at index {i} is STOP; no actions allowed after STOP")

    # PREFILL_APPROVED_DRAFT must be immediately followed by STOP
    for i, a in enumerate(actions):
        if a.action_type == "PREFILL_APPROVED_DRAFT":
            if i != len(actions) - 2:
                raise ValueError("PREFILL_APPROVED_DRAFT must be second-to-last (followed by STOP)")
            if actions[i + 1].action_type != "STOP_FOR_USER_CONFIRMATION":
                raise ValueError("action after PREFILL_APPROVED_DRAFT must be STOP")

    # hard_stop_required must be True
    if not plan.hard_stop_required:
        raise ValueError("hard_stop_required must be True for guided plan")

    # reason_codes must be empty
    if plan.reason_codes:
        raise ValueError("reason_codes must be empty for guided plan")

    # requires_user_confirmation must match presence of any confirmation-required action
    any_confirming = any(a.requires_user_confirmation for a in actions)
    if plan.requires_user_confirmation != any_confirming:
        raise ValueError(
            "requires_user_confirmation mismatch: "
            f"plan={plan.requires_user_confirmation}, any_confirming={any_confirming}"
        )

    # strict bool fields
    _validate_bool(plan.requires_user_confirmation, "plan.requires_user_confirmation")
    _validate_bool(plan.hard_stop_required, "plan.hard_stop_required")

    return plan


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def build_citizen_action_plan(actions: object) -> CitizenActionPlan:
    """
    Build a guided CitizenActionPlan from an iterable of CitizenAction objects.

    Raises ValueError (converted to blocked plan) on any validation failure.
    """
    if not isinstance(actions, (list, tuple)):
        return _build_blocked_plan(["invalid_action_plan"])

    # Type-coercion failures: list of dicts, subclasses, etc.
    typed_actions: list[CitizenAction] = []
    for i, item in enumerate(actions):
        if not _is_exact_instance(item, CitizenAction):
            return _build_blocked_plan(["invalid_action_shape"])
        typed_actions.append(item)

    try:
        plan = CitizenActionPlan(
            plan_status="guided",
            actions=tuple(typed_actions),
            requires_user_confirmation=any(a.requires_user_confirmation for a in typed_actions),
            hard_stop_required=True,
            reason_codes=(),
        )
        return _validate_guided_plan(plan)
    except (ValueError, TypeError) as exc:
        # Map specific failures to reason codes
        msg = str(exc)
        if "action_type" in msg or "unknown_action_type" in msg:
            reason = "unknown_action_type"
        elif "route_id" in msg or "unknown route_id" in msg:
            reason = "unknown_route_id"
        elif "target_id" in msg or "unknown target_id" in msg:
            reason = "unknown_target_id"
        elif "choice_id" in msg or "invalid choice_id" in msg:
            reason = "invalid_choice_id"
        elif "requires_user_confirmation" in msg or "confirmation" in msg:
            reason = "confirmation_required"
        elif "forbidden" in msg:
            reason = "sensitive_action_blocked"
        elif "STOP" in msg or "hard_stop" in msg or "too many" in msg:
            reason = "hard_stop_required"
        else:
            reason = "invalid_action_plan"
        return _build_blocked_plan([reason])


def validate_citizen_action_plan(candidate: object) -> CitizenActionPlan:
    """
    Validate a candidate (possibly forged/malformed) object as a CitizenActionPlan.

    Returns a guided plan if valid, otherwise a blocked plan with reason codes.
    """
    # Must be exact CitizenActionPlan
    if not _is_exact_instance(candidate, CitizenActionPlan):
        return _build_blocked_plan(["invalid_action_plan"])

    plan = candidate

    # Strict field types
    if type(plan.plan_status) is not str:
        return _build_blocked_plan(["invalid_action_plan"])
    if not _is_exact_instance(plan.actions, tuple):
        return _build_blocked_plan(["invalid_action_shape"])
    _validate_bool(plan.requires_user_confirmation, "plan.requires_user_confirmation")
    _validate_bool(plan.hard_stop_required, "plan.hard_stop_required")
    if not _is_exact_instance(plan.reason_codes, tuple):
        return _build_blocked_plan(["invalid_action_shape"])

    if plan.plan_status == "blocked":
        # Blocked plans: canonical form
        if plan.actions != ():
            return _build_blocked_plan(plan.reason_codes if plan.reason_codes else ["invalid_action_plan"])
        return _build_blocked_plan(plan.reason_codes if plan.reason_codes else ["invalid_action_plan"])

    if plan.plan_status == "guided":
        try:
            return _validate_guided_plan(plan)
        except (ValueError, TypeError) as exc:
            msg = str(exc)
            if "action_type" in msg or "unknown_action_type" in msg:
                reason = "unknown_action_type"
            elif "route_id" in msg or "unknown route_id" in msg:
                reason = "unknown_route_id"
            elif "target_id" in msg or "unknown target_id" in msg:
                reason = "unknown_target_id"
            elif "choice_id" in msg or "invalid choice_id" in msg:
                reason = "invalid_choice_id"
            elif "requires_user_confirmation" in msg or "confirmation" in msg:
                reason = "confirmation_required"
            elif "forbidden" in msg:
                reason = "sensitive_action_blocked"
            elif "STOP" in msg or "hard_stop" in msg or "too many" in msg:
                reason = "hard_stop_required"
            else:
                reason = "invalid_action_plan"
            return _build_blocked_plan([reason])

    # Unknown status
    return _build_blocked_plan(["invalid_action_plan"])