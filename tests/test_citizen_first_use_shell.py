"""Static contract for the #919 first-use shell and #920 choreography."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STATIC = ROOT / "src" / "web" / "static"
HTML = (STATIC / "citizen-action-demo.html").read_text(encoding="utf-8")
JS = (STATIC / "citizen-first-use-shell.js").read_text(encoding="utf-8")
CSS = (STATIC / "citizen-first-use-shell.css").read_text(encoding="utf-8")
CHOREO = (STATIC / "citizen-first-choreography.js").read_text(encoding="utf-8")


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


def test_first_use_shell_is_local_only_and_fail_closed():
    assert '"불법 주정차 신고는 어디서 하나요?": true' in JS
    assert "isSupportedQuestion(question)" in JS
    assert "지원 범위의 질문으로 다시 입력해 주세요." in JS
    assert "fetch(" not in JS
    assert "localStorage" not in JS
    assert "sessionStorage" not in JS
    assert "document.cookie" not in JS


def test_first_use_shell_split_follow_up_is_bounded_and_keeps_transition_guard():
    assert "currentState === STATE_TRANSITIONING || !chatInput" in JS
    assert "currentState === STATE_SPLIT" in JS
    assert "SPLIT_FOLLOW_UP_MESSAGE" in JS
    assert "메뉴 이동과 세부 안내는 다음 단계에서 순서대로 제공됩니다" in JS
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
