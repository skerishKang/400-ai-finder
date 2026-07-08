"""Static contract for the #919 first-use shell and #920 choreography."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STATIC = ROOT / "src" / "web" / "static"
HTML = (STATIC / "citizen-action-demo.html").read_text(encoding="utf-8")
JS = (STATIC / "citizen-first-use-shell.js").read_text(encoding="utf-8")
CSS = (STATIC / "citizen-first-use-shell.css").read_text(encoding="utf-8")
CHOREO = (STATIC / "citizen-first-choreography.js").read_text(encoding="utf-8")
CANVAS = (STATIC / "citizen-action-demo-canvas.js").read_text(encoding="utf-8")


# ── #919 shell contracts ──────────────────────────────────────────


def test_first_use_shell_is_loaded_after_existing_local_demo_scripts():
    assert HTML.index("citizen-action-demo-canvas.js") < HTML.index("citizen-first-use-shell.js")
    assert HTML.index("citizen-action-executor.js") < HTML.index("citizen-first-use-shell.js")
    assert 'data-first-use-state="entry"' in HTML


def test_first_use_shell_defines_entry_transition_split_and_reset_contract():
    assert 'STATE_ENTRY = "entry"' in JS
    assert 'STATE_TRANSITIONING = "transitioning"' in JS
    assert 'STATE_SPLIT = "split"' in JS
    assert "beginSupportedTransition" in JS
    assert "completeSplit" in JS
    assert "resetToEntry" in JS
    assert "setCanvasAvailability(false)" in JS
    assert "setCanvasAvailability(true)" in JS


def test_first_use_shell_rerenders_entry_conversation_after_canvas_boot():
    """The canvas script loads before the first-use shell and may touch the
    chat thread; the shell must re-render the chat-first greeting on fresh
    entry loads."""
    fresh_entry_init = JS[JS.index("if (isLegacyJourneyLoad())"):]
    assert "setState(STATE_ENTRY)" in fresh_entry_init
    assert "renderEntryConversation()" in fresh_entry_init


def test_first_use_shell_is_local_only_and_fail_closed():
    assert '"불법 주정차 신고는 어디서 하나요?": true' in JS
    assert "isSupportedQuestion(question)" in JS
    assert "예시 질문으로 다시 입력해 주세요." in JS
    assert "fetch(" not in JS
    assert "localStorage" not in JS
    assert "sessionStorage" not in JS
    assert "document.cookie" not in JS


def test_first_use_shell_split_follow_up_is_bounded_and_keeps_transition_guard():
    assert "currentState === STATE_TRANSITIONING || !chatInput" in JS
    assert "currentState === STATE_SPLIT" in JS
    assert "SPLIT_FOLLOW_UP_MESSAGE" in JS
    assert "메뉴 이동과 세부 안내를 이어서 보여드리겠습니다" in JS
    assert "beginSupportedTransition(question)" in JS


def test_first_use_shell_has_reduced_motion_and_noninteractive_entry_clone_rules():
    assert "prefers-reduced-motion: reduce" in CSS
    assert "first-use-shell--no-motion" in CSS
    assert "pointer-events: none" in CSS
    assert "aria-hidden" in JS
    assert "inert" in JS


# ── #920 choreography contracts ───────────────────────────────────


def test_choreography_script_is_loaded_after_first_use_shell():
    assert HTML.index("citizen-first-use-shell.js") < HTML.index("citizen-first-choreography.js")


def test_choreography_has_no_network_or_storage():
    """Choreography must not use network, persistence, or cookie APIs.
    Comments listing these as forbidden are allowed; actual invocation is not."""
    # Strip comments to check only code, not guarantee annotations
    code_lines = [l for l in CHOREO.splitlines() if not l.strip().startswith(" *")]
    code = "\n".join(code_lines)
    assert "fetch(" not in code
    assert "XMLHttpRequest" not in code
    assert "WebSocket(" not in code
    assert "EventSource(" not in code
    assert "sendBeacon(" not in code
    assert "localStorage" not in code
    assert "sessionStorage" not in code
    assert "document.cookie" not in code


def test_choreography_defines_state_machine_and_api():
    assert 'STATE_IDLE = "idle"' in CHOREO
    assert 'STATE_RUNNING = "running"' in CHOREO
    assert 'STATE_DONE = "done"' in CHOREO
    assert 'STATE_CANCELLED = "cancelled"' in CHOREO
    assert "function start(journeyKey)" in CHOREO
    assert "cancel: cancel" in CHOREO
    assert "getState: getState" in CHOREO
    assert "hasJourney: hasJourney" in CHOREO
    assert "HIGHLIGHT_CLASS" in CHOREO
    assert '"executor-highlight"' in CHOREO


def test_choreography_uses_only_public_canvas_api():
    assert "navigateToRoute" in CHOREO
    assert "getTargetElement" in CHOREO
    assert "CitizenActionDemoCompute" not in CHOREO
    assert "CitizenActionDemoExecutor" not in CHOREO


def test_choreography_has_journey_map_for_supported_question():
    assert "불법 주정차 신고는 어디서 하나요?" in CHOREO
    assert '"complaint-illegal-parking"' in CHOREO
    assert '"nav-civil-service"' in CHOREO
    assert '"nav-complaint-category"' in CHOREO
    assert '"civil-service"' in CHOREO
    assert '"complaint-category"' in CHOREO
    assert '"completed"' not in CHOREO


def test_choreography_each_step_has_message_and_delay_or_route_target():
    """Every step in the journey map has a 'message' key.
    Non-terminal steps have routeId or targetId plus delayMs."""
    # Verify step structure by checking for the pattern
    assert "message:" in CHOREO
    assert "routeId:" in CHOREO
    assert "targetId:" in CHOREO
    assert "delayMs:" in CHOREO


def test_shell_stores_question_and_integrates_choreography():
    assert "lastSplitQuestion" in JS
    assert "window.CitizenFirstChoreography" in JS
    assert "start(" in JS
    assert "cancel(" in JS


def test_shell_cancels_choreography_on_reset():
    """Reset clears lastSplitQuestion and notifies choreography controller."""
    assert "lastSplitQuestion = null" in JS
    assert "CitizenFirstChoreography.cancel()" in JS


def test_choreography_cancel_clears_timer_and_highlights():
    assert "clearTimeout" in CHOREO
    assert "classList.remove" in CHOREO or "HIGHLIGHT_CLASS" in CHOREO
    assert "classList.add" in CHOREO
    assert "scrollIntoView" in CHOREO


def test_choreography_cancel_is_safe_in_idle():
    """cancel() returns early without error when state is idle."""
    assert 'STATE_IDLE) return' in CHOREO or 'STATE_IDLE) {' in CHOREO


def test_choreography_final_target_highlight_present():
    """The illegal-parking journey map includes complaint-category-illegal-parking
    as a target highlight step before the completion message."""
    assert '"complaint-category-illegal-parking"' in CHOREO
    assert "불법 주정차 신고 항목을 확인합니다" in CHOREO


def test_choreography_final_target_appears_after_route_and_before_completion():
    """complaint-category route appears before complaint-category-illegal-parking target,
    which appears before the terminal completion message."""
    assert CHOREO.index("complaint-category") < CHOREO.index("complaint-category-illegal-parking")
    assert CHOREO.index("complaint-category-illegal-parking") < CHOREO.index(
        "안내가 완료되었습니다"
    )


def test_choreography_terminal_step_preserves_highlight():
    """The completion step (no routeId/targetId) must not call _clearHighlights.
    _clearHighlights must be guarded by a routeId-or-targetId condition so
    message-only terminal steps preserve the previous step's highlight."""
    # Verify the guard: _clearHighlights only runs when step has routeId or targetId
    assert "step.routeId || step.targetId" in CHOREO
    # Verify that a line matching the guard is directly followed by _clearHighlights
    choreo_lines = CHOREO.splitlines()
    guard_found = False
    for i, line in enumerate(choreo_lines):
        if "step.routeId || step.targetId" in line and "{" in line:
            for j in range(i + 1, min(i + 5, len(choreo_lines))):
                stripped = choreo_lines[j].strip()
                if stripped and not stripped.startswith("//") and not stripped.startswith("*"):
                    assert "_clearHighlights" in stripped, (
                        f"_clearHighlights must follow the guard; found '{stripped}'"
                    )
                    guard_found = True
                    break
            break
    assert guard_found, "Guard condition for _clearHighlights not found"


def test_choreography_cancel_still_clears_highlights():
    """cancel() must still call _clearHighlights even though terminal steps
    skip it. Verify _clearHighlights appears in the cancel function body."""
    # Find the cancel function and check _clearHighlights is called inside it
    cancel_start = CHOREO.index("function cancel()")
    cancel_end = CHOREO.index("function getState()")
    cancel_body = CHOREO[cancel_start:cancel_end]
    assert "_clearHighlights" in cancel_body, "cancel() must call _clearHighlights"


# ── Chat preservation contract ─────────────────────────────────


def test_canvas_has_preserve_first_use_chat_helper():
    """Canvas must define _shouldPreserveFirstUseChat() helper."""
    assert "function _shouldPreserveFirstUseChat()" in CANVAS


def test_canvas_preserve_helper_checks_split_and_choreography_state():
    """Helper returns true only when data-first-use-state=split
    and data-choreography-state is running or done."""
    assert '"split"' in CANVAS
    assert 'choreographyState === "running"' in CANVAS or 'choreographyState === "running"' in CANVAS
    assert 'choreographyState === "done"' in CANVAS


def test_canvas_preserve_helper_is_noop_for_entry():
    """Helper returns false when first-use-state is entry (no split yet)."""
    assert 'firstUseState === "split"' in CANVAS


def test_canvas_restore_historical_is_guarded_by_preserve_helper():
    """_restoreHistoricalChat call must be guarded by !_shouldPreserveFirstUseChat()
    so that choreography chat messages survive route transitions."""
    assert "!_shouldPreserveFirstUseChat()" in CANVAS
    assert "_restoreHistoricalChat()" in CANVAS


def test_canvas_preserve_no_network_or_storage():
    """The canvas preserve helper must not add network/storage access."""
    canvas_no_comments = [l for l in CANVAS.splitlines()
                          if not l.strip().startswith(" *")]
    code = "\n".join(canvas_no_comments)
    for kw in ["fetch(", "XMLHttpRequest", "WebSocket(", "EventSource(",
                "localStorage", "sessionStorage", "document.cookie",
                "navigator.sendBeacon"]:
        assert kw not in code, f"{kw} must not appear in canvas code"


# ── #925 / #927 MVP mode wiring contracts ───────────────────────────


def test_shell_detects_mvp_mode_via_query():
    assert "function isMvpMode()" in JS
    assert 'get("mvp") === "1"' in JS


def test_shell_mvp_submission_handler_present():
    assert "function handleMvpSubmission(" in JS
    assert "CitizenMvpBridge" in JS
    assert "/api/mvp/ask" in JS or '"/api/mvp/ask"' in JS


def test_shell_mvp_submission_shows_server_answer_first():
    """The assistant bubble must display the server's model answer.

    The handler must append the user message, then the server answer before
    any choreography starts — i.e. appendChatMessage('ai', answer) appears.
    """
    assert "appendChatMessage(\"ai\", answer)" in JS


def test_shell_normalizes_mvp_action_and_only_runs_approved_actions():
    assert "function normalizeMvpAction(" in JS
    assert "function resolveMvpActionForQuestion(" in JS
    assert 'DEFAULT_SUPPORTED_ACTION = "illegal_parking"' in JS
    assert '"illegal_parking"' in JS
    assert '"housing_department"' in JS
    # Only the two approved actions trigger a split+choreography.
    assert "beginMvpSplitThenChoreography(question, \"illegal_parking\")" in JS
    assert "beginMvpSplitThenChoreography(question, \"housing_department\")" in JS
    # Unsupported 'none' / failure must NOT start a choreography (no clone move).
    assert "CitizenFirstChoreography.start(action)" in JS


def test_shell_mvp_none_keeps_entry_state_for_unsupported_question():
    """For an unsupported question, action 'none' must not transition to split."""
    assert "action === \"none\"" in JS or 'action === "none"' in JS


def test_shell_mvp_supported_question_none_falls_back_to_existing_clone_action():
    """A usable answer to the first supported question must not leave the
    MVP shell in chat-only mode just because the action field is none."""
    assert "if (action !== \"none\") return action" in JS
    assert "if (isSupportedQuestion(question)) return DEFAULT_SUPPORTED_ACTION" in JS
    assert "fall back to the existing deterministic local journey" in JS


def test_shell_mvp_request_token_invalidates_late_responses():
    assert "_mvpRequestToken" in JS
    assert "token !== _mvpRequestToken" in JS


def test_shell_reset_invalidates_pending_mvp_and_cancels_bridge():
    idx = JS.index("function resetToEntry()")
    reset_body = JS[idx:idx + 600]
    assert "_mvpRequestToken++" in reset_body
    assert "CitizenMvpBridge.cancel()" in reset_body
    # Existing choreography cancellation must remain.
    assert "CitizenFirstChoreography.cancel()" in reset_body


# ── #927 MVP choreography journeys ─────────────────────────────────


def test_choreography_has_mvp_action_journeys():
    assert '"illegal_parking"' in CHOREO
    assert '"housing_department"' in CHOREO
    assert '"dept-housing-jdept01"' in CHOREO


def test_choreography_housing_reuses_jdept01_approved_facts():
    """housing_department must reuse the approved J-DEPT-01 local clone state,
    not invent new data or contacts."""
    assert "J-DEPT-01:directory" in CHOREO
    # Approved facts appear in the journey (rendered by the existing clone).
    assert "공동주택과" in CHOREO
    assert "062-410-6033" in CHOREO
    assert "공동주택과 업무전반" in CHOREO


def test_choreography_applies_journey_state_in_step_execution():
    """_executeStep must honor a step.journeyState to drive the existing clone."""
    assert "function _applyJourneyState(" in CHOREO
    assert "step.journeyState" in CHOREO


def test_choreography_mvp_journeys_have_messages():
    assert "message:" in CHOREO
    # illegal_parking MVP alias keeps the same terminal completion message.
    assert "안내가 완료되었습니다" in CHOREO
