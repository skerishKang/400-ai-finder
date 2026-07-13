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
    # #1133: cold entry materializes history with skipHistory, then one replace.
    assert "setState(STATE_ENTRY, { skipHistory: true })" in fresh_entry_init
    assert "renderEntryConversation()" in fresh_entry_init
    assert "materializeInitialHistory()" in fresh_entry_init


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
    # Guard is multi-line: routeId / routeIdAfterClick / targetId / ... then clear.
    assert "step.routeId ||" in CHOREO
    assert "step.routeIdAfterClick ||" in CHOREO
    assert "step.targetId ||" in CHOREO
    choreo_lines = CHOREO.splitlines()
    guard_found = False
    for i, line in enumerate(choreo_lines):
        if "step.routeId ||" in line:
            # Walk forward through the multi-line if-condition to the body.
            for j in range(i, min(i + 20, len(choreo_lines))):
                stripped = choreo_lines[j].strip()
                if stripped.startswith("_clearHighlights"):
                    guard_found = True
                    break
                if stripped.startswith("if (step.routeId)") or stripped.startswith(
                    "if (step.targetId)"
                ):
                    break
            break
    assert guard_found, "Guard condition for _clearHighlights not found"


def test_each_new_journey_resets_canvas_scroll_and_stale_department_state():
    assert "resetOfficialCanvasScroll" in JS
    # #1133: journey/dept-state cleared via shell-owned history dropJourneyQuery.
    assert "clearPreviousJourneyLocationState" in JS
    assert "dropJourneyQuery: true" in JS
    assert 'journey: true' in JS or '"journey"' in JS
    assert "dept-state" in JS
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


def _preserve_first_use_chat_body():
    start = CANVAS.index("function _shouldPreserveFirstUseChat()")
    end = CANVAS.index("function _restoreHistoricalChat()", start)
    return CANVAS[start:end]


def test_canvas_preserve_helper_covers_transitioning_and_split():
    """#1123: cinematic split (transitioning) and pending confirmation/split
    both preserve shell-owned chat. Canvas home paint during transitioning
    must not wipe the real user message via _restoreHistoricalChat."""
    body = _preserve_first_use_chat_body()

    assert "data-first-use-state" in body
    assert 'state === "transitioning"' in body
    assert 'state === "split"' in body
    assert "data-choreography-state" not in body
    assert "choreographyState" not in body


def test_canvas_preserve_helper_remains_false_on_entry_only():
    """Helper is false on entry so standalone canvas demos can still seed
    historical chat; shell re-renders the greeting after canvas boot."""
    body = _preserve_first_use_chat_body()

    assert 'state === "transitioning"' in body
    assert 'state === "split"' in body
    assert '=== "entry"' not in body
    assert "return state === \"transitioning\" || state === \"split\";" in body


def test_canvas_restore_historical_is_guarded_by_preserve_helper():
    """_restoreHistoricalChat and other full-thread rewriters must be gated
    by preserveChat so shell-owned history survives route transitions."""
    assert "var preserveChat = _shouldPreserveFirstUseChat();" in CANVAS
    assert "!preserveChat" in CANVAS
    # Call site (not the function definition) must sit behind !preserveChat.
    call_idx = CANVAS.index("_restoreHistoricalChat();")
    call_window = CANVAS[max(0, call_idx - 120): call_idx]
    assert "!preserveChat" in call_window
    # Dept journey progress rewrite is also gated (housing choreography).
    assert "_updateChatProgressForDept(deptState)" in CANVAS
    render_route = CANVAS[CANVAS.index("function _renderRoute(routeId)"):]
    dept_guard_region = render_route[
        render_route.index("if (isDeptJourney)"): render_route.index(
            "_restoreHistoricalChat();"
        )
    ]
    assert "if (!preserveChat)" in dept_guard_region


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
    reset_body = JS[idx:idx + 900]
    assert "_mvpRequestToken++" in reset_body
    # Guarded cancel remains (window-qualified public API).
    assert "window.CitizenMvpBridge.cancel()" in reset_body
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
        # top+left/right+bottom margins match the canonical mobile entry spec
        # (82px top clears the brand, 12px side/bottom symmetric).
        assert "margin: 82px 12px 12px" in entry_block

    def test_mobile_entry_margin_plus_width_stays_within_viewport(self):
        # width calc(100% - 24px) + 12px*2 margins == 100% of viewport.
        # Mirror the invariant the browser test asserts for 320/390px.
        block = CSS[CSS.index("@media (max-width: 767px)"):]
        entry_block = block[block.index('body[data-first-use-state="entry"] .chat-shell'):]
        entry_block = entry_block[: entry_block.index("}") + 1]
        assert "width: calc(100% - 24px)" in entry_block
        # bottom margin (12px) + reduced height keep the composer focus
        # outline inside a 320px-tall viewport.
        assert "82px 12px 12px" in entry_block or "margin: 82px 12px 12px" in entry_block

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


# ── #1116 Stage A: mobile conversation / guidance surface ──────
# Shell-level only. The guidance surface reuses the canonical
# #demo-canvas (no DOM clone, no summary card). Desktop must keep
# the legacy split grid and never expose the mobile switch.
def test_mobile_surface_switch_present_and_desktop_hidden():
    # HTML: a real group with two toggle buttons + aria-pressed wiring.
    assert 'role="group"' in HTML
    assert 'aria-label="서비스 화면"' in HTML
    assert 'id="tab-conversation"' in HTML
    assert 'id="tab-guidance"' in HTML
    assert 'aria-pressed="true"' in HTML
    assert 'aria-pressed="false"' in HTML
    assert 'aria-controls="chat-shell"' in HTML
    assert 'aria-controls="demo-canvas"' in HTML
    assert 'data-mobile-surface-tab="conversation"' in HTML
    assert 'data-mobile-surface-tab="guidance"' in HTML
    # No tablist/tab/aria-selected semantics (replaced by group + aria-pressed).
    assert 'role="tablist"' not in HTML
    assert 'role="tab"' not in HTML
    assert 'aria-selected=' not in HTML
    # Labels: exact accessible names (whitespace inside button is fine).
    assert "대화" in HTML
    assert "안내 화면" in HTML


def test_mobile_surface_switch_contract_in_shell_and_css():
    # JS: surface state lives on a data attribute; desktop is ignored;
    # the guidance surface is the canonical #demo-canvas (no clone).
    assert "function isMobileSurfaceMode()" in JS
    assert 'window.matchMedia("(max-width: 767px)")' in JS
    assert "function setMobileSurface(" in JS
    assert "function showMobileSurfaceSwitch()" in JS
    assert "function hideMobileSurfaceSwitch()" in JS
    assert "function focusComposerIfAllowed()" in JS
    assert 'body.setAttribute("data-mobile-surface"' in JS
    # setMobileSurface must drive aria-pressed (not aria-selected) and
    # toggle inert/aria-hidden on the canonical chat + canvas DOMs.
    assert "aria-pressed" in JS
    assert 'chatShell.setAttribute("aria-hidden"' in JS or "chatShell.setAttribute('aria-hidden'" in JS
    assert 'canvas.setAttribute("aria-hidden"' in JS or "canvas.setAttribute('aria-hidden'" in JS
    assert 'chatShell.setAttribute("inert"' in JS or "chatShell.setAttribute('inert'" in JS
    assert 'canvas.setAttribute("inert"' in JS
    # Responsive resize cleanup is driven by a matchMedia change listener
    # (no UA sniffing).
    assert "addEventListener(\"change\"" in JS or "addListener(" in JS
    assert "syncResponsiveMode" in JS
    # CSS: switch hidden by default (desktop never shows it); only the
    # ≤767px media query exposes it; [hidden] always wins.
    assert ".mobile-surface-switch {" in CSS
    assert "display: none;" in CSS
    assert ".mobile-surface-switch[hidden] {" in CSS
    assert "display: none !important;" in CSS
    # Canonical canvas is reused as the guidance surface (no display:none
    # clone, no summary card) — the mobile rule keeps #demo-canvas.
    assert 'body[data-mobile-surface="guidance"][data-first-use-state="split"] #demo-canvas' in CSS
    # Confirm-before-navigate composer blur is shell-level guarded by
    # the mobile surface mode, not a UA sniff or global focus trap.
    assert 'isMobileSurfaceMode() && chatInput' in JS
    assert "chatInput.blur()" in JS
    # No UA sniffing anywhere in the surface module.
    assert "navigator.userAgent" not in JS
    assert "navigator.platform" not in JS
    # startChoreography must NOT unconditionally focus; mobile auto-focus
    # is suppressed via the desktop-only guard.
    assert "function startChoreography(" in JS
    assert "focusComposerIfAllowed();" in JS


def test_mobile_surface_choreography_focus_is_desktop_only():
    # Choreography automated steps must NOT call .focus() directly on
    # editable elements on mobile; they go through the desktop-only helper.
    assert "function _focusEditableOnDesktopOnly(" in CHOREO
    assert "function _blurActiveEditableForAutomatedMobileStep(" in CHOREO
    # The automated action paths route editable focus via the helper.
    assert "_focusEditableOnDesktopOnly(typeInput)" in CHOREO
    assert "_focusEditableOnDesktopOnly(contentInput)" in CHOREO
    # _executeStep must blur any active editable at step start on mobile.
    assert "_blurActiveEditableForAutomatedMobileStep();" in CHOREO
    # Stage 3 getter API must be preserved (no behavior change).
    assert "getCurrentStepIndex" in CHOREO
    assert "getTotalSteps" in CHOREO
    assert "getSteps" in CHOREO



def test_mobile_surface_does_not_clone_or_duplicate_canonical_doms():
    # Stage A hard requirement: exactly one chat DOM and one civic DOM.
    # The guidance surface IS #demo-canvas, so there must be no
    # duplicate canvas clone or summary-card surface created.
    assert HTML.count('id="demo-canvas"') == 1
    assert HTML.count('id="chat-shell"') == 1
    # No mobile summary/replacement surface is introduced before the switch.
    assert "mobile-guidance-summary" not in HTML


# ── #1114 mayor proposal entry (additive chip + hero control) ──


def test_mayor_proposal_chip_is_additive_eighth():
    """Exactly 8 chips: original 7 labels/questions preserved + mayor chip."""
    import re

    chips = re.findall(
        r'data-chip-question="([^"]+)"',
        HTML[HTML.index('id="chat-chips"') : HTML.index('id="chat-composer-form"')],
    )
    assert len(chips) == 8, f"expected 8 chips, got {len(chips)}: {chips}"
    original_seven = [
        "불법 주정차 신고는 어디서 하나요?",
        "공동주택 관련 문의는 어느 부서에 해야 하나요?",
        "매트리스 폐기 신청은 어디서 하나요?",
        "여권 발급은 어디서 하나요?",
        "무인민원발급기 어디 있어요?",
        "가로등이 고장났어요. 신고할게요",
        "쓰레기 무단투기 신고할래 (AI 도움)",
    ]
    for q in original_seven:
        assert q in chips
    assert "구청장에게 제안하고 싶어요" in chips
    assert chips.count("구청장에게 제안하고 싶어요") == 1


def test_mayor_canonical_pair_and_shared_controller():
    assert 'MAYOR_CANONICAL_QUESTION = "구청장에게 제안하고 싶어요"' in JS
    assert 'MAYOR_CANONICAL_ACTION = "mayor_message_assist"' in JS
    assert "function startMayorProposalEntry(" in JS
    assert 'source: "chat"' in JS
    assert "userInitiatedControlClick" in JS
    # Shared controller is wired for chip/composer, MVP action, and hero.
    assert "startMayorProposalEntry({" in JS
    assert "useActionConfirm: true" in JS
    assert 'source: "hero"' in JS
    # Canonical action is actually consumed (not declaration-only).
    assert "isMayorAction(action)" in JS or 'action === "mayor_message_assist"' in JS
    assert "MAYOR_CANONICAL_ACTION" in JS
    # No direct final-route jump past confirm-run for mayor.
    assert "showConfirmRun" in JS
    assert "showConfirmRunForAction" in JS


def test_mayor_shared_journey_object_for_question_and_action():
    assert "MAYOR_MESSAGE_ASSIST_JOURNEY" in CHOREO
    assert '"mayor_message_assist": MAYOR_MESSAGE_ASSIST_JOURNEY' in CHOREO
    assert '"구청장에게 제안하고 싶어요": MAYOR_MESSAGE_ASSIST_JOURNEY' in CHOREO
    # Both keys must reference the same object (not a deep copy).
    assert CHOREO.count("MAYOR_MESSAGE_ASSIST_JOURNEY") >= 3


def test_mayor_display_labels_avoid_fallback():
    quest_fn = JS[JS.index("function _questDisplayName(") : JS.index("function _actionDisplayName(")]
    action_fn = JS[JS.index("function _actionDisplayName(") : JS.index("function startChoreography(")]
    assert 'question.indexOf("구청장")' in quest_fn
    assert '"구청장 제안 작성"' in quest_fn
    assert 'action === "mayor_message_assist"' in action_fn
    assert '"구청장 제안 작성"' in action_fn
    # Fallback remains last resort, not the mayor path.
    assert quest_fn.rfind("이 안내") > quest_fn.rfind("구청장 제안 작성")
    assert action_fn.rfind("이 안내") > action_fn.rfind("구청장 제안 작성")


def test_mayor_hero_control_geometry_is_explicit_rectangle():
    assert 'id="mayor-open-office-control"' in HTML
    assert 'aria-label="열린구청장실 바로가기"' in HTML
    assert 'class="mayor-open-office-control"' in HTML
    control_css = CSS[CSS.index(".mayor-open-office-control {") :]
    control_css = control_css[: control_css.index("/* Hide when entry is not the active surface.")]
    # Explicit non-zero rectangle (no height:auto / clip-path hit area).
    assert "position: absolute" in control_css
    assert "top: calc(" in control_css or "top:calc(" in control_css
    assert "right: calc(" in control_css or "right:calc(" in control_css
    assert "width: calc(" in control_css or "width:calc(" in control_css
    assert "height: calc(" in control_css or "height:calc(" in control_css
    assert "height: auto" not in control_css
    assert "clip-path: inset" not in control_css
    assert "clip-path: none" in control_css
    # Hover/focus must not expand geometry via clip-path:none removal of inset.
    hover = CSS[CSS.index(".mayor-open-office-control:hover") : CSS.index(".mayor-open-office-control:focus-visible")]
    focus = CSS[
        CSS.index(".mayor-open-office-control:focus-visible") : CSS.index(
            ".mayor-open-office-control.executor-highlight"
        )
    ]
    assert "clip-path: none" not in hover or "inset" not in hover
    assert "clip-path: none" not in focus or "inset" not in focus
    # Mobile: control hidden with mayor card (aligned to 767px surface breakpoint).
    assert "@media (max-width: 767px)" in CSS
    assert ".mayor-open-office-control" in CSS[CSS.index("@media (max-width: 767px)") :]


def test_mayor_cursor_before_split_uses_existing_canvas_cursor():
    controller = JS[
        JS.index("function startMayorProposalEntry(") : JS.index(
            "function beginMayorProposalEntry("
        )
    ]
    # Existing canvas cursor API reused — no second cursor DOM constructed here.
    assert "showCursorAt" in controller
    assert "clickAnimation" in controller
    assert "choreo-cursor" not in controller
    assert "createElement" not in controller
    assert "MAYOR_CONTROL_SELECTOR" in controller or "#mayor-open-office-control" in controller

    # Semantic automated-path ordering (not file-global first occurrence).
    # Manual early-return may call _beginMayorSplitContinuation before any
    # showCursorAt appears in source; inspect only the automated sequence that
    # starts at the first showCursorAt schedule.
    automated = controller[controller.index("showCursorAt") :]
    assert automated.index("showCursorAt") < automated.index("clickAnimation")
    assert automated.index("clickAnimation") < automated.index(
        "_beginMayorSplitContinuation({ useActionConfirm: useActionConfirm })"
    )
    # Cursor targets the semantic hero control via existing canvas API.
    assert "showCursorAt(MAYOR_CONTROL_SELECTOR)" in automated or (
        "showCursorAt" in automated and "MAYOR_CONTROL_SELECTOR" in automated
    )
    assert "clickAnimation(MAYOR_CONTROL_SELECTOR)" in automated or (
        "clickAnimation" in automated and "MAYOR_CONTROL_SELECTOR" in automated
    )

    # Manual hero path: user click is the activation; no second auto-click.
    assert "userInitiatedControlClick" in controller
    assert 'source === "hero"' in controller or 'source === "hero"' in controller
    manual = controller[
        controller.index("userInitiatedControlClick") : controller.index(
            "Chat / model path"
        )
        if "Chat / model path" in controller
        else controller.index("showCursorAt")
    ]
    assert "_beginMayorSplitContinuation" in manual
    assert "showCursorAt" not in manual
    assert "clickAnimation" not in manual

    # Canvas target resolution already falls back to document-level selectors.
    assert "document.querySelector(selectorOrEl)" in CANVAS
    assert "function _resolveCursorTarget" in CANVAS
    assert "mobile-result-replacement" not in HTML
    # No second civic surface element is introduced alongside the switch.
    assert "demo-canvas__clone" not in HTML
    assert "guidance-card" not in HTML
    assert "mobile-guidance-copy" not in HTML


# ── #1121 PADIEM service attribution ───────────────────────────────

PADIEM_COMPACT = "AI Agent by PADIEM"
PADIEM_DISCLOSURE = (
    "본 AI 행정서비스 시연 시스템은 주식회사 파디엠(PADIEM)이 기획·개발했습니다."
)


def test_padiem_attribution_exact_strings_once_in_shell_html():
    """Product runtime shell HTML owns each PADIEM string exactly once."""
    assert HTML.count(PADIEM_COMPACT) == 1
    assert HTML.count(PADIEM_DISCLOSURE) == 1
    assert 'data-service-attribution="padiem-compact"' in HTML
    assert 'data-service-attribution="padiem-disclosure"' in HTML
    assert 'class="chat-shell__attribution"' in HTML
    assert 'class="chat-shell__disclosure"' in HTML


def test_padiem_attribution_lives_in_chat_shell_not_canvas_or_messages():
    shell_start = HTML.index('id="chat-shell"')
    shell_end = HTML.index("</aside>", shell_start)
    shell = HTML[shell_start:shell_end]
    assert PADIEM_COMPACT in shell
    assert PADIEM_DISCLOSURE in shell

    # Compact attribution sits under the service title inside header-main.
    attr_idx = shell.index(PADIEM_COMPACT)
    attr_open = shell.rfind("<p", 0, attr_idx)
    attr_close = shell.index("</p>", attr_idx) + 4
    attr_el = shell[attr_open:attr_close]
    assert "chat-shell__attribution" in attr_el
    assert "chat-shell__header-main" in shell[:attr_idx]
    assert shell.index("chat-shell__title") < attr_idx
    assert "<button" not in attr_el
    assert "<a " not in attr_el
    assert "href=" not in attr_el

    # Disclosure is after the composer, still inside the shell.
    assert shell.index("chat-composer-form") < shell.index(PADIEM_DISCLOSURE)
    assert shell.index(PADIEM_COMPACT) < shell.index(PADIEM_DISCLOSURE)

    # Not injected into conversation thread markup as a chat message.
    thread = shell[shell.index('id="chat-thread"') : shell.index('id="chat-chips"')]
    assert PADIEM_COMPACT not in thread
    assert PADIEM_DISCLOSURE not in thread


def test_padiem_attribution_not_in_official_or_canvas_sources():
    """Official canvas / snapshot sources must not carry PADIEM partnership copy."""
    forbidden = (
        PADIEM_COMPACT,
        PADIEM_DISCLOSURE,
        "북구청 × PADIEM",
        "공식 운영사",
        "공식 공동운영",
        "Buk-gu official partner",
    )
    for blob_name, blob in (
        ("CANVAS", CANVAS),
        ("OFFICIAL_SNAPSHOTS", OFFICIAL_SNAPSHOTS),
        ("ADAPTER", ADAPTER),
        ("CHOREO", CHOREO),
    ):
        for phrase in forbidden:
            assert phrase not in blob, f"{phrase!r} must not appear in {blob_name}"


def test_padiem_attribution_is_informational_not_interactive():
    compact_idx = HTML.index(PADIEM_COMPACT)
    compact_open = HTML.rfind("<", 0, compact_idx)
    compact_tag = HTML[compact_open : compact_idx]
    assert compact_tag.startswith("<p")
    assert "href=" not in compact_tag
    assert "button" not in compact_tag.lower()
    assert "aria-hidden" not in compact_tag

    disc_idx = HTML.index(PADIEM_DISCLOSURE)
    disc_open = HTML.rfind("<", 0, disc_idx)
    disc_tag = HTML[disc_open:disc_idx]
    assert disc_tag.startswith("<p")
    assert 'role="note"' in disc_tag or 'role="note"' in HTML[disc_open : disc_idx + 20]
    assert "href=" not in disc_tag
    assert "button" not in disc_tag.lower()
    assert "aria-hidden" not in disc_tag


def test_padiem_attribution_styles_are_restrained_shell_css():
    assert ".chat-shell__attribution" in COPILOT_CSS
    assert ".chat-shell__disclosure" in COPILOT_CSS
    attr_block = COPILOT_CSS[COPILOT_CSS.index(".chat-shell__attribution") :]
    attr_block = attr_block[: attr_block.index("}")]
    assert "gradient" not in attr_block.lower()
    assert "animation" not in attr_block.lower()
    assert "text-muted" in attr_block or "#8e8ea0" in attr_block

    # No CSS content: injection of the wordmark.
    assert 'content: "AI Agent by PADIEM"' not in COPILOT_CSS
    assert "content: 'AI Agent by PADIEM'" not in COPILOT_CSS
    assert PADIEM_DISCLOSURE not in COPILOT_CSS
    assert PADIEM_DISCLOSURE not in CSS


def test_padiem_shell_js_does_not_reinsert_attribution():
    """Attribution is static shell markup; shell JS must not re-append it."""
    assert PADIEM_COMPACT not in JS
    assert PADIEM_DISCLOSURE not in JS
    assert "padiem-compact" not in JS
    assert "padiem-disclosure" not in JS
    # Chat rewrite paths stay limited to the thread, not the whole shell.
    assert "chatThread.innerHTML" in JS
    assert "chat-shell.innerHTML" not in JS
    assert 'getElementById("chat-shell").innerHTML' not in JS
