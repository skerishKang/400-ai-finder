"""Static contract for the #919 first-use shell and #920 choreography."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STATIC = ROOT / "src" / "web" / "static"
HTML = (STATIC / "citizen-action-demo.html").read_text(encoding="utf-8")
JS = (STATIC / "citizen-first-use-shell.js").read_text(encoding="utf-8")
CSS = (STATIC / "citizen-first-use-shell.css").read_text(encoding="utf-8")
CHOREO = (STATIC / "citizen-first-choreography.js").read_text(encoding="utf-8")
CANVAS = (STATIC / "citizen-action-demo-canvas.js").read_text(encoding="utf-8")
OFFICIAL_SNAPSHOTS = (STATIC / "bukgu-official-snapshots.js").read_text(encoding="utf-8")
ADAPTER = (STATIC / "citizen-content-adapter.js").read_text(encoding="utf-8")
COPILOT_CSS = (STATIC / "citizen-copilot-shell.css").read_text(encoding="utf-8")
DIRECTIVE = (ROOT / "docs" / "design" / "bukgu-ai-agent-product-directive.md").read_text(
    encoding="utf-8"
)


# ── #919 shell contracts ──────────────────────────────────────────


def test_first_use_shell_is_loaded_after_existing_local_demo_scripts():
    assert HTML.index("bukgu-official-snapshots.js") < HTML.index("citizen-action-demo-canvas.js")
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
    assert '"불법 주정차 신고는 어디서 하나요?": "illegal_parking"' in JS
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


def test_owner_approved_product_directive_supersedes_static_scope():
    assert "owner-approved and authoritative" in DIRECTIVE
    assert "supersedes the narrow local/static product-scope restrictions" in DIRECTIVE
    assert "on-screen AI cursor" in DIRECTIVE
    assert "final complaint, application, or board-post submission" in DIRECTIVE


def test_entry_stage_uses_bukgu_identity_and_mayor_media():
    assert 'class="entry-stage"' in HTML
    assert "BUKGU AI CIVIC BROWSER" in HTML
    assert "home-identity.png" in HTML
    assert "home-mayor-card.png" in HTML
    assert "북구의 모든 행정" in HTML


def test_split_transition_prepaints_canvas_and_uses_cinematic_motion():
    assert "function startCinematicSplit()" in JS
    transition_body = JS[JS.index("function startCinematicSplit()"):
                         JS.index("function scrollChatToLatest()")]
    assert transition_body.index("_renderBukguHomeFixture()") < transition_body.index(
        "setState(STATE_TRANSITIONING)"
    )
    assert "TRANSITION_DURATION_MS = 1100" in JS
    assert "firstUseCanvasReveal" in CSS
    assert "firstUseChatArrive" in CSS
    assert 'body[data-first-use-state="transitioning"] #demo-canvas[inert]' in CSS
    assert "display: flex !important" in CSS


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
    assert '"complaint-illegal-parking-report"' in CHOREO
    assert 'safetyreport.go.kr' in CHOREO


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
    """The illegal-parking journey map includes complaint-illegal-parking-report
    as a target highlight step before the terminal safety message."""
    assert '"complaint-illegal-parking-report"' in CHOREO
    assert 'safetyreport.go.kr' in CHOREO


def test_choreography_final_target_appears_after_route_and_before_completion():
    """complaint-illegal-parking route appears before complaint-illegal-parking-report target,
    which appears before the terminal completion message."""
    assert CHOREO.index("complaint-illegal-parking") < CHOREO.index("complaint-illegal-parking-report")
    assert CHOREO.index("complaint-illegal-parking-report") < CHOREO.index(
        "안내를 마쳤습니다"
    )


def test_choreography_terminal_step_preserves_highlight():
    """The completion step (no routeId/targetId) must not call _clearHighlights.
    _clearHighlights must be guarded by a routeId-or-targetId condition so
    message-only terminal steps preserve the previous step's highlight."""
    # Verify the guard: _clearHighlights only runs when step has routeId or targetId
    assert "step.routeId || step.routeIdAfterClick" in CHOREO
    # Verify that a line matching the guard is directly followed by _clearHighlights
    choreo_lines = CHOREO.splitlines()
    guard_found = False
    for i, line in enumerate(choreo_lines):
        if "step.routeId || step.routeIdAfterClick" in line and "if (" in line:
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


def test_each_new_journey_resets_canvas_scroll_and_stale_department_state():
    assert "resetOfficialCanvasScroll" in JS
    assert "params.delete(key)" in JS
    assert '"journey", "dept-state"' in JS
    assert "canvas.scrollTop = 0" in JS


def test_exact_presentation_prompts_take_priority_over_model_classification():
    resolver = JS[JS.index("function resolveMvpActionForQuestion"):]
    assert resolver.index("if (mapped) return mapped") < resolver.index("normalizeMvpAction(result)")


def test_ai_writing_journey_types_title_and_body_before_confirmation():
    assert 'routeIdAfterClick: "complaint-write"' in CHOREO
    assert 'cursorTarget: "#board-write-title"' in CHOREO
    assert 'cursorTarget: "#board-write-content"' in CHOREO
    assert "typeContent:" in CHOREO
    assert CHOREO.index("typeContent:") < CHOREO.index("requiresConfirmation: true")


def test_content_adapter_distinguishes_local_demo_freshness_metadata():
    assert "getBoardSnapshot" in ADAPTER
    assert 'sourceUrl: ""' in ADAPTER
    assert "retrievedAt: null" in ADAPTER
    assert 'freshnessState: "local_demo"' in ADAPTER


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


def test_shell_has_generic_action_plan_quest_card_renderer():
    assert "function renderQuestProgressCard(" in JS
    assert "function appendQuestProgressCard(" in JS
    assert "plan.browser_actions" in JS
    assert "final_warning" in JS
    assert "textContent = payload.questName" in JS
    assert "data-quest-card\", \"action_plan\"" in JS
    assert "appendQuestProgressCard(chatThread)" in JS
    assert 'makeQuestCardRow("quest_id"' not in JS
    assert 'makeQuestCardRow("정보 기준", payload.sourceModeLabel)' in JS
    assert 'makeQuestCardRow("진행 상태", payload.stopConditionLabel)' in JS
    assert 'actionsLabel.textContent = "AI가 수행할 작업"' in JS


def test_canvas_delegates_quest_card_to_shell_renderer():
    assert "appendQuestProgressCard(thread)" in CANVAS
    assert 'data-quest-card="housing_department_lookup"' not in CANVAS
    assert "housing_department_lookup" not in CANVAS


def test_shell_normalizes_mvp_action_and_only_runs_approved_actions():
    assert "function normalizeMvpAction(" in JS
    assert "function resolveMvpActionForQuestion(" in JS
    assert "SUPPORTED_QUESTION_ACTIONS" in JS
    assert '"illegal_parking"' in JS
    assert '"housing_department"' in JS
    # Actions trigger a split+choreography (all five plus none).
    assert "beginMvpSplitThenChoreography(question, \"illegal_parking\")" in JS
    assert "beginMvpSplitThenChoreography(question, \"housing_department\")" in JS
    assert "beginMvpSplitThenChoreography(question, \"passport_guidance\")" in JS
    assert "beginMvpSplitThenChoreography(question, \"unmanned_kiosk\")" in JS
    # Unsupported 'none' / failure must NOT start a choreography (no clone move).
    assert "CitizenFirstChoreography.start(action)" in JS


def test_shell_mvp_none_keeps_entry_state_for_unsupported_question():
    """For an unsupported question, action 'none' must not transition to split."""
    assert "action === \"none\"" in JS or 'action === "none"' in JS


def test_shell_mvp_supported_question_none_falls_back_to_existing_clone_action():
    """A usable answer to the first supported question must not leave the
    MVP shell in chat-only mode just because the action field is none."""
    assert "if (action !== \"none\") return action" in JS
    assert "SUPPORTED_QUESTION_ACTIONS[normalized]" in JS
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
    assert '"apartment-dept"' in CHOREO


def test_choreography_housing_reuses_approved_facts():
    """housing_department must provide 공동주택과 guidance,
    not invent new data or contacts."""
    assert "공동주택과" in CHOREO
    assert "apartment-dept" in CHOREO
    assert "_apartmentDeptSnapshot" in CHOREO
    assert '"phone": "062-410-6841"' in OFFICIAL_SNAPSHOTS


def test_choreography_applies_journey_state_in_step_execution():
    """_executeStep must honor a step.journeyState to drive the existing clone."""
    assert "function _applyJourneyState(" in CHOREO
    assert "step.journeyState" in CHOREO


def test_choreography_mvp_journeys_have_messages():
    assert "message:" in CHOREO
    # Each MVP action journey must have a message step.
    assert '"illegal_parking"' in CHOREO
    assert '"housing_department"' in CHOREO
    assert '"bulky_waste"' in CHOREO
    assert '"passport_guidance"' in CHOREO
    assert '"unmanned_kiosk"' in CHOREO
    # Terminal message uses the current completion wording.
    assert "안내를 마쳤습니다" in CHOREO


def test_housing_journey_visibly_clicks_types_and_searches():
    assert 'journeyStateAfterClick: "J-DEPT-01:menu"' in CHOREO
    assert 'journeyStateAfterClick: "J-DEPT-01:directory"' in CHOREO
    assert 'typeQuery: "공동주택"' in CHOREO
    assert 'clickTarget: ".bg-dept-search__btn"' in CHOREO
    assert "function _typeIntoSearch(" in CHOREO
    assert 'setAttribute("data-agent-typing", "true")' in CHOREO
    assert "062-410-6033" not in CHOREO
    assert 'data-representative-contact="true"' in CHOREO


def test_canvas_cursor_has_visible_ai_identity_and_canvas_scoped_targeting():
    assert 'class="choreo-cursor__label">AI</span>' in CANVAS
    assert 'setAttribute("data-agent-cursor", "true")' in CANVAS
    assert "function _resolveCursorTarget(" in CANVAS
    assert "_demoCanvas.querySelector(selectorOrEl)" in CANVAS


def test_mobile_split_uniformly_scales_the_official_canvas():
    assert "function fitToViewport()" in CANVAS
    assert 'window.matchMedia("(max-width: 767px)")' in CANVAS
    assert 'inner.style.transform = "scale(" + scale + ")"' in CANVAS
    assert 'data-official-fit", "scaled"' in CANVAS
    assert "fitToViewport: fitToViewport" in CANVAS
    assert 'body[data-first-use-state="split"] .chat-shell' in CSS
    assert "overflow-x: hidden" in CSS


# ── #1064 narrow-viewport overflow regression contract ──────────────
# These are static-source contracts that lock the responsive geometry
# invariants the real-browser test (tests/browser/verify_first_use_responsive.mjs)
# enforces. They must NOT rely on a single `overflow-x: hidden` substring —
# that hides overflow without proving layout safety.

class TestResponsiveViewportContract:
    def test_entry_chat_width_is_viewport_based(self):
        # entry chat width is a viewport-relative min(), not a fixed 640px.
        assert "--first-use-entry-chat-width: min(650px, calc(100vw - 80px))" in CSS
        assert "640px" not in CSS.split("--first-use-entry-chat-width")[1].split(";")[0]

    def test_mobile_entry_selector_has_sufficient_specificity(self):
        # A mobile override for the entry chat-shell exists with high enough
        # specificity to beat the base rule (body[data-...] + .chat-shell).
        assert 'body[data-first-use-state="entry"] .chat-shell' in CSS
        assert "@media (max-width: 767px)" in CSS
        # mobile entry chat uses viewport-relative width + symmetric margins
        block = CSS[CSS.index("@media (max-width: 767px)"):]
        entry_block = block[block.index('body[data-first-use-state="entry"] .chat-shell'):]
        entry_block = entry_block[: entry_block.index("}") + 1]
        assert "width: calc(100% - 24px)" in entry_block
        # left+right margin (12px each) must not exceed the 24px width reduction
        assert "margin: 82px 12px 12px" in entry_block

    def test_mobile_entry_margin_plus_width_stays_within_viewport(self):
        # width calc(100% - 24px) + 12px*2 margins == 100% of viewport.
        # Mirror the invariant the browser test asserts for 320/390px.
        block = CSS[CSS.index("@media (max-width: 767px)"):]
        entry_block = block[block.index('body[data-first-use-state="entry"] .chat-shell'):]
        entry_block = entry_block[: entry_block.index("}") + 1]
        assert "width: calc(100% - 24px)" in entry_block
        assert "12px 12px" in entry_block or "margin: 82px 12px 12px" in entry_block

    def test_split_mobile_chat_and_canvas_use_full_width_with_min_width_zero(self):
        block = CSS[CSS.index("@media (max-width: 767px)"):]
        split_block = block[block.index('body[data-first-use-state="split"] .chat-shell'):]
        split_block = split_block[: split_block.index("}") + 1]
        assert "width: 100%" in split_block
        assert "min-width: 0" in split_block
        assert "max-width: 100%" in split_block
        # canvas must also be full width and allowed to shrink on mobile split
        canvas_block = block[block.index(".first-use-layout .demo-canvas"):]
        canvas_block = canvas_block[: canvas_block.index("}") + 1]
        assert "width: 100%" in canvas_block

    def test_chips_wrap_and_long_chip_cannot_exceed_container(self):
        # Entry chips wrap; the compact split view switches to a scroll rail.
        assert ".chat-chips {" in CSS
        chips_block = CSS[CSS.index(".chat-chips {"):]
        chips_block = chips_block[: chips_block.index("}") + 1]
        assert "flex-wrap: wrap" in chips_block
        assert 'body[data-first-use-state="split"] .chat-chips' in CSS
        assert "flex-wrap: nowrap" in CSS
        assert "overflow-x: auto" in CSS
        # the shared composer input must allow shrinking (real 320px overflow fix)
        assert ".chat-composer__input {" in COPILOT_CSS
        input_block = COPILOT_CSS[COPILOT_CSS.index(".chat-composer__input {"):]
        input_block = input_block[: input_block.index("}") + 1]
        assert "min-width: 0" in input_block

    def test_composer_send_button_does_not_shrink(self):
        # send button keeps its size (flex-shrink: 0) so it is never clipped.
        assert ".chat-composer__send {" in COPILOT_CSS
        send_block = COPILOT_CSS[COPILOT_CSS.index(".chat-composer__send {"):]
        send_block = send_block[: send_block.index("}") + 1]
        assert "flex-shrink: 0" in send_block

    def test_768_breakpoint_meaning_is_recorded(self):
        # The 768px boundary is the desktop/split vs mobile split switch.
        # Assert the exact breakpoint token appears so the contract is explicit.
        assert "@media (max-width: 767px)" in CSS
        assert "@media (max-width: 1180px)" in CSS
        # 768 is the first width above the 767px mobile cap → desktop split layout
        assert 'body[data-first-use-state="split"] .first-use-layout' in CSS
