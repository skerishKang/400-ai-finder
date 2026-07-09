"""
CitizenActionPlan — closed / immutable contract for bukgu click-navigator action plans.

No live network, no LLM calls, no DOM/UI code.  Pure business-rule validation only.
"""

from __future__ import annotations

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
    "complaint-illegal-parking",
    "complaint-intake",
    "handoff-stop",
    "complaint-review",
    "bulky-waste-disposal",
    "move-in-report-guidance",
    "public-health-center-guidance",
    "apartment-info",
    "apartment-dept",
})

_VALID_TARGET_IDS: frozenset[str] = frozenset({
    "nav-civil-service",
    "nav-complaint-category",
    "complaint-category-illegal-parking",
    "complaint-category-public-parking-inconvenience",
    "complaint-category-residential-parking",
    "complaint-category-traffic-or-facility-safety",
    "complaint-category-other-or-unsure",
    "complaint-illegal-parking-report",
    "complaint-body",
    "complaint-draft-review",
    "confirm-draft-prefill",
    "handoff-notice",
    "bulky-waste-guidance-card",
    "move-in-guidance-card",
    "health-center-guidance-card",
    "apartment-guidance-card",
    "apartment-dept-card",
    "apartment-life-card",
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
# Helpers
# ---------------------------------------------------------------------------

def _is_exact_instance(obj: object, cls: type) -> bool:
    """Return True only when obj is exactly cls (not a subclass)."""
    return type(obj) is cls


def _safe_get_field(obj: object, name: str, default: object) -> object:
    """Get an attribute safely; return default on any AttributeError/TypeError."""
    try:
        return getattr(obj, name, default)
    except (AttributeError, TypeError):
        return default


def _is_true_bool(value: object) -> bool:
    """Return True only if value is exactly True or False."""
    return type(value) is bool


def _is_true_tuple_of_str(value: object) -> bool:
    """Return True only if value is exactly a tuple of only str."""
    if type(value) is not tuple:
        return False
    for item in value:
        if type(item) is not str:
            return False
    return True


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
# Per-action validation (safe — catches all attribute errors internally)
# ---------------------------------------------------------------------------

def _validate_action(action: object) -> CitizenAction | None:
    """
    Validate an action. Returns the validated CitizenAction or None if invalid.
    Never raises; all errors are swallowed and reported via return value.
    """
    if not _is_exact_instance(action, CitizenAction):
        return None

    # Safely extract all fields — any corruption is blocked
    try:
        atype = action.action_type
        rid = action.route_id
        tid = action.target_id
        eid = action.explanation_id
        ruc = action.requires_user_confirmation
        cids = action.choice_ids
    except (AttributeError, TypeError):
        return None

    # Strict field types
    if type(atype) is not str:
        return None
    if rid is not None and type(rid) is not str:
        return None
    if tid is not None and type(tid) is not str:
        return None
    if type(eid) is not str:
        return None
    if not _is_true_bool(ruc):
        return None
    if not _is_true_tuple_of_str(cids):
        return None

    # Forbidden action types
    if atype in _FORBIDDEN_ACTION_TYPES:
        return None

    # Unknown action type
    if atype not in _VALID_ACTION_TYPES:
        return None

    # explanation_id must be from closed vocabulary
    if eid not in _EXPLANATION_IDS:
        return None

    # Shape rules by action_type
    if atype == "ASK_CLARIFYING_QUESTION":
        if rid is not None:
            return None
        if tid is not None:
            return None
        if cids:
            return None
        if ruc:
            return None

    elif atype == "PRESENT_CHOICES":
        if rid is not None:
            return None
        if tid is not None:
            return None
        if not cids:
            return None
        for cid in cids:
            if cid not in _VALID_CHOICE_IDS:
                return None
        if ruc:
            return None

    elif atype in (
        "HIGHLIGHT_ALLOWLISTED_ELEMENT",
        "SCROLL_TO_ALLOWLISTED_ELEMENT",
        "CLICK_ALLOWLISTED_ELEMENT",
    ):
        if tid is None:
            return None
        if tid not in _VALID_TARGET_IDS:
            return None
        if rid is not None:
            return None
        if cids:
            return None
        if ruc:
            return None

    elif atype == "OPEN_ALLOWLISTED_ROUTE":
        if rid is None:
            return None
        if rid not in _VALID_ROUTE_IDS:
            return None
        if tid is not None:
            return None
        if cids:
            return None
        if ruc:
            return None

    elif atype == "PREFILL_APPROVED_DRAFT":
        if tid != "complaint-body":
            return None
        if rid is not None:
            return None
        if cids:
            return None
        if not ruc:
            return None

    elif atype == "STOP_FOR_USER_CONFIRMATION":
        if tid is not None:
            return None
        if rid is not None and rid != "handoff-stop":
            return None
        if cids:
            return None
        if not ruc:
            return None

    return action  # type: ignore[return-value]


# ---------------------------------------------------------------------------
# Plan-level validation (safe — catches all errors internally)
# ---------------------------------------------------------------------------

def _validate_guided_plan(plan: CitizenActionPlan) -> CitizenActionPlan | None:
    """
    Validate a guided plan. Returns the plan if valid, None if invalid.
    Never raises.
    """
    try:
        actions = plan.actions
    except (AttributeError, TypeError):
        return None

    if type(actions) is not tuple:
        return None

    if not actions:
        return None

    if len(actions) > _MAX_ACTIONS:
        return None

    validated_actions: list[CitizenAction] = []
    for a in actions:
        validated = _validate_action(a)
        if validated is None:
            return None
        validated_actions.append(validated)

    # Last action must be STOP
    last = validated_actions[-1]
    if last.action_type != "STOP_FOR_USER_CONFIRMATION":
        return None

    # No action after STOP
    for i, a in enumerate(validated_actions[:-1]):
        if a.action_type == "STOP_FOR_USER_CONFIRMATION":
            return None

    # PREFILL_APPROVED_DRAFT must be immediately followed by STOP
    for i, a in enumerate(validated_actions):
        if a.action_type == "PREFILL_APPROVED_DRAFT":
            if i != len(validated_actions) - 2:
                return None
            if validated_actions[i + 1].action_type != "STOP_FOR_USER_CONFIRMATION":
                return None

    # Safely extract plan bool fields
    try:
        ruc = plan.requires_user_confirmation
        hsr = plan.hard_stop_required
        rc = plan.reason_codes
    except (AttributeError, TypeError):
        return None

    if not _is_true_bool(ruc):
        return None
    if not _is_true_bool(hsr):
        return None
    if not _is_true_tuple_of_str(rc):
        return None

    # hard_stop_required must be True
    if not hsr:
        return None

    # reason_codes must be empty
    if rc:
        return None

    # requires_user_confirmation must match presence of any confirmation-required action
    any_confirming = any(a.requires_user_confirmation for a in validated_actions)
    if ruc != any_confirming:
        return None

    return plan  # type: ignore[return-value]


# ---------------------------------------------------------------------------
# Public API — both functions are total safe boundaries
# ---------------------------------------------------------------------------

def build_citizen_action_plan(actions: object) -> CitizenActionPlan:
    """
    Build a guided CitizenActionPlan from an iterable of CitizenAction objects.

    Always returns a CitizenActionPlan. Returns a blocked plan on any validation
    failure, including malformed/forged/exact-but-corrupted action instances.
    """
    if not isinstance(actions, (list, tuple)):
        return _build_blocked_plan(["invalid_action_plan"])

    validated_actions: list[CitizenAction] = []
    for item in actions:
        # Reject anything that is not an exact CitizenAction instance
        if not _is_exact_instance(item, CitizenAction):
            return _build_blocked_plan(["invalid_action_shape"])
        # _validate_action handles corrupted frozen-dataclass instances safely
        validated = _validate_action(item)
        if validated is None:
            return _build_blocked_plan(["invalid_action_shape"])
        validated_actions.append(validated)

    plan = CitizenActionPlan(
        plan_status="guided",
        actions=tuple(validated_actions),
        requires_user_confirmation=any(a.requires_user_confirmation for a in validated_actions),
        hard_stop_required=True,
        reason_codes=(),
    )

    result = _validate_guided_plan(plan)
    if result is None:
        return _build_blocked_plan(["invalid_action_plan"])
    return result


def validate_citizen_action_plan(candidate: object) -> CitizenActionPlan:
    """
    Validate a candidate (possibly forged/malformed) object as a CitizenActionPlan.

    Always returns a CitizenActionPlan. Never raises. Returns a guided plan if
    the candidate is a valid exact CitizenActionPlan; otherwise returns a
    canonical blocked plan with closed-vocabulary reason codes.
    """
    # Must be exact type — rejects subclasses, SimpleNamespace, dict, etc.
    if not _is_exact_instance(candidate, CitizenActionPlan):
        return _build_blocked_plan(["invalid_action_plan"])

    # Safely extract all fields — uninitialized __new__ instances return sentinel
    _sentinel = object()
    ps = _safe_get_field(candidate, "plan_status", _sentinel)
    acts = _safe_get_field(candidate, "actions", _sentinel)
    ruc = _safe_get_field(candidate, "requires_user_confirmation", _sentinel)
    hsr = _safe_get_field(candidate, "hard_stop_required", _sentinel)
    rc = _safe_get_field(candidate, "reason_codes", _sentinel)

    # If any field was absent (returned sentinel)
    if any(value is _sentinel for value in (ps, acts, ruc, hsr, rc)):
        return _build_blocked_plan(["invalid_action_plan"])

    # Strict field types
    if type(ps) is not str:
        return _build_blocked_plan(["invalid_action_plan"])
    if type(acts) is not tuple:
        return _build_blocked_plan(["invalid_action_shape"])
    if not _is_true_bool(ruc):
        return _build_blocked_plan(["confirmation_required"])
    if not _is_true_bool(hsr):
        return _build_blocked_plan(["hard_stop_required"])
    if not _is_true_tuple_of_str(rc):
        return _build_blocked_plan(["invalid_action_shape"])

    if ps == "blocked":
        return _build_blocked_plan(rc if rc else ["invalid_action_plan"])

    if ps == "guided":
        result = _validate_guided_plan(candidate)
        if result is not None:
            return result
        return _build_blocked_plan(["invalid_action_plan"])

    return _build_blocked_plan(["invalid_action_plan"])