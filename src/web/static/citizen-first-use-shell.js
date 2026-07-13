/*
 * citizen-first-use-shell.js
 * Local deterministic controller for the first chat-only entry transition.
 *
 * Guarantees:
 * - no fetch/XHR/WebSocket/EventSource/sendBeacon;
 * - no browser persistence or cookie access;
 * - no provider, runner, live-site, or external-origin behavior;
 * - choreography delegation to CitizenFirstChoreography (no direct clone actions).
 */

(function () {
  "use strict";

  var STATE_ENTRY = "entry";
  var STATE_TRANSITIONING = "transitioning";
  var STATE_SPLIT = "split";
  // #1067 — semantic journey axis (independent of layout first-use-state).
  var JOURNEY_ENTRY = "entry";
  var JOURNEY_ANSWER = "answer";
  var JOURNEY_CONFIRM = "confirm";
  var JOURNEY_NAVIGATE = "navigate";
  var JOURNEY_RESULT = "result";
  var TRANSITION_DURATION_MS = 1100;
  var SUPPORTED_QUESTION_ACTIONS = {
    "불법 주정차 신고는 어디서 하나요?": "illegal_parking",
    "공동주택 관련 문의는 어느 부서에 해야 하나요?": "housing_department",
    "침대 매트리스 버리고 싶어요": "bulky_waste",
    "대형폐기물은 어떻게 버리나요?": "bulky_waste",
    "가구 버리려면 어디서 신청해요?": "bulky_waste",
    "매트리스 폐기 신청은 어디서 하나요?": "bulky_waste",
    "여권 발급은 어디서 하나요?": "passport_guidance",
    "여권 재발급은 어떻게 하나요?": "passport_guidance",
    "무인민원발급기 어디 있어요?": "unmanned_kiosk",
    "무인민원발급기로 뭘 발급받을 수 있어요?": "unmanned_kiosk",
    "무인민원발급기 이용방법 알려줘": "unmanned_kiosk",
    "민원서류 발급받으려면 어디로 가야 해요?": "unmanned_kiosk",
    "가로등이 고장났어요. 신고할게요": "streetlight_report",
    "쓰레기 무단투기 신고할래 (AI 도움)": "litter_ai_assist",
    // #1114 — mayor proposal entry (same journey object as the canonical question)
    "구청장에게 제안하고 싶어요": "mayor_message_assist",
  };
  var SPLIT_FOLLOW_UP_MESSAGE =
    "북구청 안내 화면을 왼쪽에 열어두었습니다. 메뉴 이동과 세부 안내를 이어서 보여드리겠습니다. 새 질문을 시작하려면 '새 대화'를 선택해 주세요.";

  var body = document.body;
  var canvas = document.getElementById("demo-canvas");
  var chatShell = document.getElementById("chat-shell");
  var chatThread = document.getElementById("chat-thread");
  var chatForm = document.getElementById("chat-composer-form");
  var chatInput = document.getElementById("chat-composer-input");
  var chatSend = document.getElementById("chat-composer-send");
  var resetButton = document.getElementById("chat-reset");
  var chipsContainer = document.getElementById("chat-chips");
  // #1067: SR-only journey progress (not a conversation message / not #chat-thread).
  var journeyStatusEl = document.getElementById("chat-journey-status");
  var splitTimer = null;
  // #1132: pending layout completion callback so reduced-motion can finish
  // entry→split without waiting on a decorative TRANSITION_DURATION timer.
  var _pendingSplitComplete = null;
  var lastSplitQuestion = null;
  var currentState = STATE_ENTRY;
  var currentJourneyState = JOURNEY_ENTRY;
  // #1067: while true, choreography cancelled events must not map to answer.
  var _journeyResetting = false;
  // #1067: invalidate confirm-run / decision buttons created before a reset.
  var _confirmGeneration = 0;
  // #1067: suppress repeated polite status announcements for the same phase.
  var _lastJourneyAnnouncement = "";
  var _lastAnnouncedJourneyState = "";

  // ── #1132: motion preference (canonical owner for shell + choreography) ──
  // Materialized on body as data-reduced-motion. Runtime OS changes update
  // the attribute and emit citizen:motion-preferencechange without resetting
  // journey/layout/surface/chat/choreography state.
  var reducedMotionQuery =
    typeof window.matchMedia === "function"
      ? window.matchMedia("(prefers-reduced-motion: reduce)")
      : null;
  var reducedMotion = Boolean(reducedMotionQuery && reducedMotionQuery.matches);

  // ── MVP mode (#925 / #927) ──────────────────────────────────────
  // Enabled only with ?mvp=1. In MVP mode the shell calls the model-backed
  // /api/mvp/ask endpoint (via citizen-mvp-bridge.js) and uses the returned
  // action to drive the EXISTING local choreography. The default static flow
  // below is completely unchanged when ?mvp=1 is absent, and this file performs
  // no fetch itself (the bridge file does, and is loaded only in MVP mode).
  var _mvpRequestToken = 0;
  var _questRuntimeResult = null;

  // ── #1133: browser history owner (shell-only) ──────────────────────
  // Single owner for history.state + popstate restore. Snapshots never store
  // chat text, model answers, secrets, DOM HTML, or element references.
  var HISTORY_OWNER = "citizen-first-shell";
  var HISTORY_VERSION = 1;
  var _historyFlowSequence = 1;
  var _historyFlowId = "flow-1";
  var _historyRestoring = false;
  var _historyWriteSuppressed = false;
  var _historyRouteSuppressToken = 0;
  var _lastWrittenHistorySnapshot = null;
  var _historyPopListenerBound = false;

  /**
   * #1067: aria-busy for website choreography progress only.
   * Layout transitioning and MVP composer-lock use data-chat-busy instead.
   * Does not move focus.
   */
  function _applyJourneyBusy(journeyState) {
    var busy = journeyState === JOURNEY_NAVIGATE;
    if (chatShell) {
      chatShell.setAttribute("aria-busy", busy ? "true" : "false");
    }
    if (canvas) {
      canvas.setAttribute("aria-busy", busy ? "true" : "false");
    }
  }

  /**
   * #1067: single owner for semantic journey SR announcements + busy flags.
   * Does not re-read AI answers or confirm bubbles (#chat-thread owns those).
   * Does not call .focus().
   *
   * @param {string} nextState
   * @param {{ announceReset?: boolean }} [options]
   */
  function syncJourneyAccessibility(nextState, options) {
    options = options || {};
    _applyJourneyBusy(nextState);

    // Explicit reset may re-announce the same entry phrase later; clear guard.
    if (options.announceReset) {
      _lastJourneyAnnouncement = "";
      _lastAnnouncedJourneyState = "";
    }

    var text = null;
    if (nextState === JOURNEY_ENTRY && options.announceReset) {
      text = "새 질문을 입력할 수 있습니다.";
    } else if (nextState === JOURNEY_NAVIGATE) {
      text = "북구청 안내 화면에서 경로를 진행하고 있습니다.";
    } else if (nextState === JOURNEY_RESULT) {
      text =
        "안내 경로가 완료되었습니다. 대화로 돌아가 새 질문을 입력할 수 있습니다.";
    }
    // answer / confirm / cold entry: no status-region copy
    // (answer + confirm content already live in #chat-thread).

    if (text === null) {
      return;
    }
    if (
      text === _lastJourneyAnnouncement &&
      nextState === _lastAnnouncedJourneyState
    ) {
      return;
    }
    _lastJourneyAnnouncement = text;
    _lastAnnouncedJourneyState = nextState;
    if (journeyStatusEl) {
      journeyStatusEl.textContent = text;
    }
  }

  /**
   * #1067: set semantic journey state on body. Layout state (data-first-use-state)
   * is independent and unchanged by this axis.
   * @param {string} nextState
   * @param {{ announceReset?: boolean }} [options]
   */
  function setJourneyState(nextState, options) {
    options = options || {};
    if (_journeyResetting && nextState !== JOURNEY_ENTRY) {
      return;
    }
    if (
      nextState !== JOURNEY_ENTRY &&
      nextState !== JOURNEY_ANSWER &&
      nextState !== JOURNEY_CONFIRM &&
      nextState !== JOURNEY_NAVIGATE &&
      nextState !== JOURNEY_RESULT
    ) {
      return;
    }
    var changed = currentJourneyState !== nextState;
    if (body && body.getAttribute("data-journey-state") !== nextState) {
      body.setAttribute("data-journey-state", nextState);
    }
    if (!changed && !options.announceReset) {
      // Re-assert busy if composer lock flipped aria-busy via legacy path.
      _applyJourneyBusy(currentJourneyState);
      return;
    }
    currentJourneyState = nextState;
    syncJourneyAccessibility(nextState, options);
    // Semantic-only changes use replaceState (never push).
    if (!shouldSuppressHistoryWrite() && !options.skipHistory) {
      writeHistorySnapshot("replace");
    }
  }

  function getJourneyState() {
    return currentJourneyState;
  }

  function getJourneyAccessibilityState() {
    return {
      journeyState: currentJourneyState,
      announcedState: _lastAnnouncedJourneyState,
      chatBusy: !!(chatShell && chatShell.getAttribute("aria-busy") === "true"),
      canvasBusy: !!(canvas && canvas.getAttribute("aria-busy") === "true"),
      reducedMotion: reducedMotion
    };
  }

  // ── #1133 history helpers ──────────────────────────────────────────

  function normalizeHistoryJourneyState(journeyState) {
    if (journeyState === JOURNEY_ENTRY) return JOURNEY_ENTRY;
    if (journeyState === JOURNEY_ANSWER) return JOURNEY_ANSWER;
    if (journeyState === JOURNEY_CONFIRM) return JOURNEY_ANSWER;
    if (journeyState === JOURNEY_NAVIGATE) return JOURNEY_ANSWER;
    if (journeyState === JOURNEY_RESULT) return JOURNEY_RESULT;
    return null;
  }

  function isClosedRouteId(routeId) {
    if (typeof routeId !== "string" || !routeId || routeId.length > 96) {
      return false;
    }
    if (
      window.CitizenActionDemoCanvas &&
      typeof window.CitizenActionDemoCanvas.hasRoute === "function"
    ) {
      return !!window.CitizenActionDemoCanvas.hasRoute(routeId);
    }
    if (
      window.CitizenActionDemoMap &&
      typeof window.CitizenActionDemoMap.isValidRoute === "function"
    ) {
      return !!window.CitizenActionDemoMap.isValidRoute(routeId);
    }
    return routeId === "home";
  }

  function getCurrentRouteIdSafe() {
    if (
      window.CitizenActionDemoCanvas &&
      typeof window.CitizenActionDemoCanvas.getCurrentRouteId === "function"
    ) {
      var rid = window.CitizenActionDemoCanvas.getCurrentRouteId();
      if (isClosedRouteId(rid)) return rid;
    }
    return "home";
  }

  function getMobileSurfaceForSnapshot() {
    if (!body) return "conversation";
    var surface = body.getAttribute("data-mobile-surface");
    if (surface === "guidance") return "guidance";
    return "conversation";
  }

  function getLayoutStateForSnapshot() {
    if (currentState === STATE_SPLIT) return STATE_SPLIT;
    // Never persist transitioning; treat in-flight reveal as entry.
    return STATE_ENTRY;
  }

  function createHistorySnapshot(overrides) {
    overrides = overrides || {};
    var journey =
      normalizeHistoryJourneyState(
        overrides.journeyState != null ? overrides.journeyState : currentJourneyState
      ) || JOURNEY_ENTRY;
    var layout =
      overrides.layoutState != null ? overrides.layoutState : getLayoutStateForSnapshot();
    if (layout !== STATE_ENTRY && layout !== STATE_SPLIT) {
      layout = STATE_ENTRY;
    }
    var routeId =
      overrides.routeId != null ? overrides.routeId : getCurrentRouteIdSafe();
    if (!isClosedRouteId(routeId)) {
      routeId = "home";
    }
    var mobileSurface =
      overrides.mobileSurface != null
        ? overrides.mobileSurface
        : getMobileSurfaceForSnapshot();
    if (mobileSurface !== "guidance") {
      mobileSurface = "conversation";
    }
    return {
      owner: HISTORY_OWNER,
      version: HISTORY_VERSION,
      flowId: _historyFlowId,
      layoutState: layout,
      journeyState: journey,
      routeId: routeId,
      mobileSurface: mobileSurface
    };
  }

  function validateHistorySnapshot(snapshot) {
    if (!snapshot || typeof snapshot !== "object") return false;
    if (snapshot.owner !== HISTORY_OWNER) return false;
    if (snapshot.version !== HISTORY_VERSION) return false;
    if (typeof snapshot.flowId !== "string" || !/^flow-\d+$/.test(snapshot.flowId)) {
      return false;
    }
    if (snapshot.flowId.length > 32) return false;
    if (snapshot.layoutState !== STATE_ENTRY && snapshot.layoutState !== STATE_SPLIT) {
      return false;
    }
    if (
      snapshot.journeyState !== JOURNEY_ENTRY &&
      snapshot.journeyState !== JOURNEY_ANSWER &&
      snapshot.journeyState !== JOURNEY_RESULT
    ) {
      return false;
    }
    if (!isClosedRouteId(snapshot.routeId)) return false;
    if (
      snapshot.mobileSurface !== "conversation" &&
      snapshot.mobileSurface !== "guidance"
    ) {
      return false;
    }
    return true;
  }

  function coerceHistorySnapshot(raw) {
    if (!raw || typeof raw !== "object") return null;
    var journey = normalizeHistoryJourneyState(raw.journeyState);
    if (!journey) return null;
    if (raw.layoutState === STATE_TRANSITIONING) return null;
    var snapshot = {
      owner: raw.owner,
      version: raw.version,
      flowId: raw.flowId,
      layoutState: raw.layoutState,
      journeyState: journey,
      routeId: raw.routeId,
      mobileSurface: raw.mobileSurface
    };
    if (!validateHistorySnapshot(snapshot)) return null;
    return snapshot;
  }

  function historySnapshotsEqual(a, b) {
    if (!a || !b) return false;
    return (
      a.owner === b.owner &&
      a.version === b.version &&
      a.flowId === b.flowId &&
      a.layoutState === b.layoutState &&
      a.journeyState === b.journeyState &&
      a.routeId === b.routeId &&
      a.mobileSurface === b.mobileSurface
    );
  }

  function beginNewHistoryFlow() {
    _historyFlowSequence += 1;
    if (_historyFlowSequence > 1000000) {
      _historyFlowSequence = 1;
    }
    _historyFlowId = "flow-" + _historyFlowSequence;
    _lastWrittenHistorySnapshot = null;
  }

  /**
   * Canonical same-document relative URL for history writes.
   * Deduplicates keys, drops empty values, never changes pathname/hash/origin.
   */
  function buildCanonicalHistoryUrl(options) {
    options = options || {};
    var managed = {
      journey: true,
      "dept-state": true,
      replay: true,
      "replay-mode": true,
      "replay-step": true
    };
    var current;
    try {
      current = new URLSearchParams(window.location.search || "");
    } catch (_) {
      current = new URLSearchParams();
    }
    var out = new URLSearchParams();
    current.forEach(function (value, key) {
      if (managed[key]) return;
      if (out.has(key)) return;
      if (value === "" || value == null) return;
      if (String(key).length > 64 || String(value).length > 128) return;
      out.set(key, value);
    });

    if (!options.dropJourneyQuery) {
      var journeyVal = null;
      var deptVal = null;
      if (options.query && typeof options.query === "object") {
        if (typeof options.query.journey === "string") {
          journeyVal = options.query.journey;
        }
        if (typeof options.query.deptState === "string") {
          deptVal = options.query.deptState;
        } else if (typeof options.query["dept-state"] === "string") {
          deptVal = options.query["dept-state"];
        }
      } else if (options.preserveJourneyQuery !== false) {
        try {
          var existingJourney = current.get("journey");
          var existingDept = current.get("dept-state");
          if (existingJourney === "J-DEPT-01") {
            journeyVal = existingJourney;
            if (
              existingDept === "directory" ||
              existingDept === "result" ||
              existingDept === "menu"
            ) {
              deptVal = existingDept;
            }
          }
        } catch (_) {
          /* ignore */
        }
      }
      if (
        journeyVal === "J-DEPT-01" &&
        journeyVal.length <= 32 &&
        (deptVal === "directory" || deptVal === "result" || deptVal === "menu") &&
        deptVal.length <= 32
      ) {
        out.set("journey", journeyVal);
        out.set("dept-state", deptVal);
      }
    }

    var path = window.location.pathname || "";
    var hash = window.location.hash || "";
    var qs = out.toString();
    return path + (qs ? "?" + qs : "") + hash;
  }

  function shouldSuppressHistoryWrite() {
    return _historyRestoring || _historyWriteSuppressed;
  }

  /**
   * @param {"replace"|"push"} mode
   * @param {{
   *   force?: boolean,
   *   dropJourneyQuery?: boolean,
   *   preserveJourneyQuery?: boolean,
   *   query?: { journey?: string, deptState?: string },
   *   routeId?: string,
   *   layoutState?: string,
   *   journeyState?: string,
   *   mobileSurface?: string
   * }} [options]
   */
  function writeHistorySnapshot(mode, options) {
    if (shouldSuppressHistoryWrite()) return;
    if (!window.history) return;
    options = options || {};
    var writeMode = mode === "push" ? "push" : "replace";
    if (
      writeMode === "push" &&
      typeof window.history.pushState !== "function"
    ) {
      return;
    }
    if (
      writeMode === "replace" &&
      typeof window.history.replaceState !== "function"
    ) {
      return;
    }

    var snapshot = createHistorySnapshot(options);
    if (!validateHistorySnapshot(snapshot)) return;

    var urlAffecting = !!(
      options.force ||
      options.dropJourneyQuery ||
      (options.query && typeof options.query === "object")
    );
    if (
      !urlAffecting &&
      _lastWrittenHistorySnapshot &&
      historySnapshotsEqual(_lastWrittenHistorySnapshot, snapshot)
    ) {
      return;
    }

    var url = buildCanonicalHistoryUrl(options);
    try {
      if (writeMode === "push") {
        window.history.pushState(snapshot, "", url);
      } else {
        window.history.replaceState(snapshot, "", url);
      }
      _lastWrittenHistorySnapshot = {
        owner: snapshot.owner,
        version: snapshot.version,
        flowId: snapshot.flowId,
        layoutState: snapshot.layoutState,
        journeyState: snapshot.journeyState,
        routeId: snapshot.routeId,
        mobileSurface: snapshot.mobileSurface
      };
    } catch (_) {
      /* history write is best-effort; never throw */
    }
  }

  function clearTransientHistoryIndicators() {
    try {
      var nodes = document.querySelectorAll(".executor-highlight, .is-agent-target");
      for (var i = 0; i < nodes.length; i++) {
        nodes[i].classList.remove("executor-highlight");
        nodes[i].classList.remove("is-agent-target");
      }
    } catch (_) {
      /* ignore */
    }
    try {
      if (chatThread) {
        var temps = chatThread.querySelectorAll(".chat-msg--temp");
        for (var t = 0; t < temps.length; t++) {
          if (temps[t] && temps[t].parentNode) {
            temps[t].parentNode.removeChild(temps[t]);
          }
        }
      }
    } catch (_) {
      /* ignore */
    }
  }

  function invalidateActiveRunsForHistoryRestore() {
    _mvpRequestToken++;
    _confirmGeneration++;
    if (window.CitizenMvpBridge && typeof window.CitizenMvpBridge.cancel === "function") {
      window.CitizenMvpBridge.cancel();
    }
    if (
      window.CitizenFirstChoreography &&
      typeof window.CitizenFirstChoreography.cancel === "function"
    ) {
      window.CitizenFirstChoreography.cancel();
    }
    if (typeof _clearMayorEntryTimers === "function") {
      _clearMayorEntryTimers();
    }
    if (splitTimer !== null) {
      window.clearTimeout(splitTimer);
      splitTimer = null;
    }
    _pendingSplitComplete = null;
    clearChatMotionStyles();
    if (
      window.CitizenActionDemoCanvas &&
      typeof window.CitizenActionDemoCanvas.hideCursor === "function"
    ) {
      window.CitizenActionDemoCanvas.hideCursor();
    }
    clearTransientHistoryIndicators();
    setComposerDisabled(false);
  }

  /**
   * Restore a validated shell-owned snapshot without replaying chat, MVP,
   * choreography, or confirm automation. Does not call .focus().
   */
  function restoreHistorySnapshot(snapshot) {
    if (!validateHistorySnapshot(snapshot)) return false;
    if (snapshot.flowId !== _historyFlowId) {
      // Stale flow after reset: keep current UI; reassert current entry state.
      writeHistorySnapshot("replace", { force: true, dropJourneyQuery: true });
      return false;
    }

    _historyRestoring = true;
    _historyWriteSuppressed = true;
    _historyRouteSuppressToken += 1;
    var routeGuard = _historyRouteSuppressToken;
    try {
      invalidateActiveRunsForHistoryRestore();

      // 6. canvas route (routechange must not push while suppressed)
      if (
        window.CitizenActionDemoCanvas &&
        typeof window.CitizenActionDemoCanvas.navigateToRoute === "function" &&
        isClosedRouteId(snapshot.routeId)
      ) {
        window.CitizenActionDemoCanvas.navigateToRoute(snapshot.routeId);
      }

      // 7. layout — immediate, no decorative transition
      if (body) {
        body.classList.add("first-use-shell--no-motion");
      }
      if (snapshot.layoutState === STATE_SPLIT) {
        setState(STATE_SPLIT, { preserveMobileSurface: true });
      } else {
        setState(STATE_ENTRY);
      }
      clearChatMotionStyles();
      if (typeof window !== "undefined" && window.requestAnimationFrame) {
        window.requestAnimationFrame(function () {
          if (body) {
            body.classList.remove("first-use-shell--no-motion");
          }
        });
      } else if (body) {
        body.classList.remove("first-use-shell--no-motion");
      }

      // 8. stable journey only (confirm/navigate already normalized to answer)
      setJourneyState(snapshot.journeyState);

      // 9. mobile surface via existing owner (no focus)
      if (snapshot.layoutState === STATE_SPLIT && isMobileSurfaceMode()) {
        showMobileSurfaceSwitch();
        setMobileSurface(
          snapshot.mobileSurface === "guidance" ? "guidance" : "conversation"
        );
      }

      // 10. aria-busy false (restorable states are never navigate)
      _applyJourneyBusy(currentJourneyState);
      setComposerDisabled(false);

      _lastWrittenHistorySnapshot = {
        owner: snapshot.owner,
        version: snapshot.version,
        flowId: snapshot.flowId,
        layoutState: snapshot.layoutState,
        journeyState: snapshot.journeyState,
        routeId: snapshot.routeId,
        mobileSurface: snapshot.mobileSurface
      };
    } catch (_) {
      /* restore is fail-closed; never throw to popstate */
    } finally {
      _historyRestoring = false;
      // Canvas route commit is async (~300ms fade). Keep write suppression
      // until after that window so restore cannot create a new push entry.
      window.setTimeout(function () {
        if (routeGuard !== _historyRouteSuppressToken) return;
        _historyWriteSuppressed = false;
        _lastWrittenHistorySnapshot = createHistorySnapshot();
      }, 450);
    }
    return true;
  }

  function handleHistoryPopState(event) {
    var raw = event ? event.state : null;
    var snapshot = coerceHistorySnapshot(raw);
    if (!snapshot) {
      // null / foreign / malformed / unknown route — ignore safely
      return;
    }
    if (snapshot.flowId !== _historyFlowId) {
      writeHistorySnapshot("replace", { force: true, dropJourneyQuery: true });
      return;
    }
    restoreHistorySnapshot(snapshot);
  }

  function handleCanvasRouteChange(event) {
    if (shouldSuppressHistoryWrite()) return;
    var detail = event && event.detail ? event.detail : null;
    if (!detail || typeof detail !== "object") return;
    var routeId = detail.routeId;
    var previousRouteId = detail.previousRouteId;
    if (!isClosedRouteId(routeId)) return;
    // Same-route re-render: no browser history entry.
    if (routeId === previousRouteId) return;
    if (
      _lastWrittenHistorySnapshot &&
      _lastWrittenHistorySnapshot.routeId === routeId &&
      _lastWrittenHistorySnapshot.flowId === _historyFlowId
    ) {
      writeHistorySnapshot("replace", { routeId: routeId });
      return;
    }
    // Meaningful civic route change → bounded push.
    writeHistorySnapshot("push", { routeId: routeId });
  }

  function handleHistoryCommitRequest(event) {
    if (shouldSuppressHistoryWrite()) return;
    var detail = event && event.detail ? event.detail : null;
    if (!detail || typeof detail !== "object") return;

    var routeId = detail.routeId;
    var query = detail.query && typeof detail.query === "object" ? detail.query : null;
    if (!query) return;
    if (!isClosedRouteId(routeId)) return;

    var journey = query.journey;
    var deptState =
      typeof query.deptState === "string"
        ? query.deptState
        : typeof query["dept-state"] === "string"
          ? query["dept-state"]
          : null;
    if (journey !== "J-DEPT-01" || journey.length > 32) return;
    if (
      deptState !== "directory" &&
      deptState !== "result" &&
      deptState !== "menu"
    ) {
      return;
    }
    if (deptState.length > 32) return;

    writeHistorySnapshot("push", {
      routeId: routeId,
      query: { journey: journey, deptState: deptState },
      force: true
    });
  }

  function materializeInitialHistory() {
    // Exactly one replaceState on load. Never push the initial entry.
    writeHistorySnapshot("replace", { force: true });
  }

  function getHistoryState() {
    var snap = createHistorySnapshot();
    return {
      owner: snap.owner,
      version: snap.version,
      flowId: snap.flowId,
      layoutState: snap.layoutState,
      journeyState: snap.journeyState,
      routeId: snap.routeId,
      mobileSurface: snap.mobileSurface,
      restoring: _historyRestoring
    };
  }

  /**
   * #1132: materialize body data-reduced-motion and notify listeners.
   * Does not change journey/layout/surface/chat/choreography state.
   * Does not call .focus().
   * @param {boolean} nextReduced
   * @param {{ emit?: boolean }} [options]
   */
  function setReducedMotionPreference(nextReduced, options) {
    options = options || {};
    var next = !!nextReduced;
    var prev = reducedMotion;
    reducedMotion = next;
    if (body) {
      body.setAttribute("data-reduced-motion", next ? "true" : "false");
    }
    // Only on normal → reduced: collapse decorative waits mid-flight.
    // Does not cancel journey, reset chat, or change surface/route.
    if (next && !prev) {
      if (currentState === STATE_TRANSITIONING) {
        finishPendingSplitTransition();
      }
      if (_mayorEntryInFlight) {
        finishMayorEntryWithoutMotion();
      }
    }
    if (options.emit === false) {
      return;
    }
    if (prev === next) {
      return;
    }
    try {
      if (typeof window !== "undefined" && typeof window.CustomEvent === "function") {
        window.dispatchEvent(new CustomEvent("citizen:motion-preferencechange", {
          detail: { reduced: next }
        }));
      }
    } catch (_) {
      /* CustomEvent unavailable */
    }
  }

  function finishPendingSplitTransition() {
    if (splitTimer !== null) {
      window.clearTimeout(splitTimer);
      splitTimer = null;
    }
    if (typeof _pendingSplitComplete === "function") {
      var complete = _pendingSplitComplete;
      _pendingSplitComplete = null;
      complete();
      return;
    }
    if (currentState === STATE_TRANSITIONING) {
      completeSplit();
    }
  }

  /**
   * Schedule entry→split completion. Under reduced motion, run immediately
   * (no TRANSITION_DURATION wait). Stores a pending callback for runtime
   * preference changes mid-transition.
   * @param {function(): void} completeFn
   */
  function scheduleSplitCompletion(completeFn) {
    if (splitTimer !== null) {
      window.clearTimeout(splitTimer);
      splitTimer = null;
    }
    _pendingSplitComplete = completeFn;
    if (prefersReducedMotion()) {
      _pendingSplitComplete = null;
      completeFn();
      return;
    }
    splitTimer = window.setTimeout(function () {
      splitTimer = null;
      var fn = _pendingSplitComplete;
      _pendingSplitComplete = null;
      if (typeof fn === "function") {
        fn();
      }
    }, TRANSITION_DURATION_MS);
  }

  /**
   * #1132: ack/confirm bubble delay after split paint.
   * Reduced motion keeps a 0ms task boundary (async order preserved via setTimeout 0).
   */
  function splitAckDelayMs() {
    return prefersReducedMotion() ? 0 : 220;
  }

  /**
   * Map choreography internal states onto the shared semantic journey axis.
   * idle leaves the current shell journey state alone.
   */
  function _mapChoreographyToJourneyState(choreoState) {
    // #1133: history restore cancels active runs; do not let cancelled/running
    // events overwrite the restored stable journey state.
    if (_historyRestoring) {
      return;
    }
    if (_journeyResetting) {
      setJourneyState(JOURNEY_ENTRY);
      return;
    }
    if (choreoState === "running") {
      setJourneyState(JOURNEY_NAVIGATE);
      return;
    }
    if (choreoState === "waiting_choice" || choreoState === "waiting_confirmation") {
      setJourneyState(JOURNEY_CONFIRM);
      return;
    }
    if (choreoState === "done") {
      setJourneyState(JOURNEY_RESULT);
      return;
    }
    if (choreoState === "cancelled") {
      // Explicit reset uses _journeyResetting; other cancels (아니요-style
      // "직접 작성" / "수정할게요") return to answer.
      setJourneyState(JOURNEY_ANSWER);
    }
    // idle: keep current journey state
  }

  function _onChoreographyStateChange(event) {
    var detail = event && event.detail ? event.detail : null;
    var choreoState = detail && detail.state ? detail.state : null;
    if (!choreoState) return;
    _mapChoreographyToJourneyState(choreoState);
  }

  function isMvpMode() {
    // Live build injects ?mvp=1 into URL before shell init.
    // body data-mvp check is a compatibility path — not the current build activation method.
    if (document.body && document.body.getAttribute("data-mvp") === "1") return true;
    // Fallback: check URL parameter
    if (!window.location || !window.location.search) return false;
    try {
      return new URLSearchParams(window.location.search).get("mvp") === "1";
    } catch (_) {
      return false;
    }
  }

  function normalizeMvpAction(result) {
    if (!result || result.ok !== true) return "none";
    var a = result.action;
    if (a === "illegal_parking" || a === "housing_department" || a === "bulky_waste" || a === "passport_guidance" || a === "unmanned_kiosk" || a === "streetlight_report" || a === "litter_ai_assist" || a === "mayor_message_assist" || a === "none") {
      return a;
    }
    return "none";
  }

  function clearQuestRuntimeState() {
    if (!body) return;
    _questRuntimeResult = null;
    body.removeAttribute("data-quest-id");
    body.removeAttribute("data-quest-name");
    body.removeAttribute("data-quest-match-status");
    body.removeAttribute("data-quest-stop-condition");
    body.removeAttribute("data-quest-source-mode");
  }

  function applyQuestRuntimeState(result) {
    clearQuestRuntimeState();
    if (!body || !result || !result.quest) return;
    _questRuntimeResult = result;
    var quest = result.quest || {};
    var plan = result.action_plan || {};
    if (typeof quest.quest_id === "string") {
      body.setAttribute("data-quest-id", quest.quest_id);
    }
    if (typeof quest.quest_name === "string") {
      body.setAttribute("data-quest-name", quest.quest_name);
    }
    if (typeof quest.match_status === "string") {
      body.setAttribute("data-quest-match-status", quest.match_status);
    }
    if (typeof plan.stop_condition === "string") {
      body.setAttribute("data-quest-stop-condition", plan.stop_condition);
    } else if (typeof quest.stop_condition === "string") {
      body.setAttribute("data-quest-stop-condition", quest.stop_condition);
    }
    if (typeof plan.source_mode === "string") {
      body.setAttribute("data-quest-source-mode", plan.source_mode);
    } else if (typeof quest.source_mode === "string") {
      body.setAttribute("data-quest-source-mode", quest.source_mode);
    }
  }

  function asObject(value) {
    if (!value || typeof value !== "object" || Array.isArray(value)) return {};
    return value;
  }

  function asArray(value) {
    return Array.isArray(value) ? value : [];
  }

  function textValue(value) {
    if (typeof value === "string") return value.trim();
    if (typeof value === "number" || typeof value === "boolean") return String(value);
    return "";
  }

  function sourceModeLabel(value) {
    var sourceMode = textValue(value);
    if (sourceMode === "local_static") return "북구청 공식 화면 기준";
    if (sourceMode === "live_official" || sourceMode === "live") return "북구청 최신 공식 데이터";
    if (sourceMode === "cached_official" || sourceMode === "cache") return "북구청 공식 데이터 사본";
    return sourceMode ? "공식 자료 확인" : "";
  }

  function stopConditionLabel(value) {
    var stopCondition = textValue(value);
    if (stopCondition === "STOP_FOR_USER_CONFIRMATION") return "사용자 확인 후 진행";
    if (stopCondition === "COMPLETE" || stopCondition === "DONE") return "안내 완료";
    if (stopCondition === "RUNNING") return "AI가 안내 중";
    return stopCondition ? "안내 준비 완료" : "";
  }

  function resultSummary(value) {
    var obj = asObject(value);
    var parts = [];
    Object.keys(obj).forEach(function (key) {
      var text = textValue(obj[key]);
      if (text) parts.push(text);
    });
    return parts.join(" / ");
  }

  function actionLabels(actions) {
    var labels = [];
    asArray(actions).forEach(function (action) {
      var label = textValue(asObject(action).label);
      if (label) labels.push(label);
    });
    return labels;
  }

  function normalizeQuestCardPayload(result) {
    var source = asObject(result || _questRuntimeResult);
    var quest = asObject(source.quest);
    var plan = asObject(source.action_plan);
    var planResult = Object.keys(asObject(plan.result)).length ? plan.result : quest.result;
    var finalWarning = asObject(plan.final_warning || quest.final_warning);
    var payload = {
      questName: textValue(quest.quest_name || plan.quest_name),
      questId: textValue(quest.quest_id || plan.quest_id),
      officialPath: asArray(plan.official_path || quest.official_path).map(textValue).filter(Boolean).join(" > "),
      actionLabels: actionLabels(plan.browser_actions),
      resultText: resultSummary(planResult),
      sourceMode: textValue(plan.source_mode || quest.source_mode),
      sourceModeLabel: sourceModeLabel(plan.source_mode || quest.source_mode),
      stopCondition: textValue(plan.stop_condition || quest.stop_condition),
      stopConditionLabel: stopConditionLabel(plan.stop_condition || quest.stop_condition),
      finalWarningText: textValue(finalWarning.warning_text),
    };
    if (!payload.questName && !payload.questId && !payload.officialPath && !payload.resultText) {
      return null;
    }
    return payload;
  }

  function makeQuestCardRow(label, value, modifier) {
    if (!value) return null;
    var row = document.createElement("div");
    row.className = "chat-quest-card__row" + (modifier ? " " + modifier : "");

    var labelEl = document.createElement("span");
    labelEl.textContent = label;
    row.appendChild(labelEl);

    var valueEl = document.createElement("strong");
    valueEl.textContent = value;
    row.appendChild(valueEl);
    return row;
  }

  function renderQuestProgressCard(result) {
    var payload = normalizeQuestCardPayload(result);
    if (!payload) return null;

    var card = document.createElement("div");
    card.className = "chat-quest-card";
    card.setAttribute("data-quest-card", "action_plan");
    if (payload.questId) {
      card.setAttribute("data-quest-id", payload.questId);
    }
    if (payload.sourceMode) {
      card.setAttribute("data-source-mode", payload.sourceMode);
    }

    var title = document.createElement("div");
    title.className = "chat-quest-card__title";
    title.textContent = payload.questName || "Quest";
    card.appendChild(title);

    [
      makeQuestCardRow("공식 경로", payload.officialPath),
      makeQuestCardRow("확인 결과", payload.resultText),
      makeQuestCardRow("정보 기준", payload.sourceModeLabel),
      makeQuestCardRow("진행 상태", payload.stopConditionLabel),
    ].forEach(function (row) {
      if (row) card.appendChild(row);
    });

    if (payload.actionLabels.length) {
      var actions = document.createElement("div");
      actions.className = "chat-quest-card__actions";
      var actionsLabel = document.createElement("span");
      actionsLabel.className = "chat-quest-card__actions-label";
      actionsLabel.textContent = "AI가 수행할 작업";
      actions.appendChild(actionsLabel);

      var list = document.createElement("ol");
      list.className = "chat-quest-card__action-list";
      payload.actionLabels.forEach(function (label) {
        var item = document.createElement("li");
        item.className = "chat-quest-card__action";
        item.textContent = label;
        list.appendChild(item);
      });
      actions.appendChild(list);
      card.appendChild(actions);
    }

    var warningRow = makeQuestCardRow("확인 사항", payload.finalWarningText, "chat-quest-card__row--warning");
    if (warningRow) card.appendChild(warningRow);

    return card;
  }

  function appendQuestProgressCard(container, result) {
    if (!container || typeof container.appendChild !== "function") return false;
    var card = renderQuestProgressCard(result);
    if (!card) return false;
    container.appendChild(card);
    return true;
  }

  function resolveMvpActionForQuestion(question, result, hasUsableMvpResult) {
    // Exact presentation prompts are product-owned routes. Keep them stable
    // even when the live model is unavailable or classifies a chip loosely.
    var normalized = normalizeQuestion(question);
    var mapped = SUPPORTED_QUESTION_ACTIONS[normalized];
    if (mapped) return mapped;
    if (!hasUsableMvpResult) return "none";
    var action = normalizeMvpAction(result);
    if (action !== "none") return action;
    return "none";
  }

  function _withMvpBridge(onReady) {
    if (window.CitizenMvpBridge && typeof window.CitizenMvpBridge.ask === "function") {
      onReady(window.CitizenMvpBridge);
      return;
    }
    var existing = document.querySelector('script[data-mvp-bridge="1"]');
    if (!existing) {
      var s = document.createElement("script");
      s.src = "/static/citizen-mvp-bridge.js";
      s.setAttribute("data-mvp-bridge", "1");
      s.onload = function () { onReady(window.CitizenMvpBridge); };
      s.onerror = function () { onReady(null); };
      document.head.appendChild(s);
    } else {
      var tries = 0;
      var iv = window.setInterval(function () {
        tries++;
        if (window.CitizenMvpBridge && typeof window.CitizenMvpBridge.ask === "function") {
          window.clearInterval(iv);
          onReady(window.CitizenMvpBridge);
        } else if (tries > 20) {
          window.clearInterval(iv);
          onReady(null);
        }
      }, 50);
    }
  }

  function normalizeQuestion(value) {
    return String(value || "").replace(/\s+/g, " ").trim();
  }

  function isSupportedQuestion(value) {
    return Boolean(SUPPORTED_QUESTION_ACTIONS[normalizeQuestion(value)]);
  }

  /**
   * #1132: read-only motion preference. Canonical owner for this shell;
   * choreography prefers this over its own matchMedia fallback.
   * Does not call .focus() or mutate journey/layout state.
   */
  function prefersReducedMotion() {
    return reducedMotion;
  }

  function isLegacyJourneyLoad() {
    if (!window.location || !window.location.search) {
      return false;
    }
    var params = new URLSearchParams(window.location.search);
    return params.getAll("journey").length === 1;
  }

  function setCanvasAvailability(isAvailable) {
    if (!canvas) {
      return;
    }
    if (isAvailable) {
      canvas.removeAttribute("inert");
      canvas.setAttribute("aria-hidden", "false");
    } else {
      canvas.setAttribute("inert", "");
      canvas.setAttribute("aria-hidden", "true");
    }
  }

  // ── Mobile surface switch (Stage A, shell-level only) ──────────────
  // Exposes an explicit conversation / guidance surface on mobile. The
  // guidance surface reuses the canonical #demo-canvas (no DOM clone,
  // no summary card). Desktop ignores this entirely.
  var mobileSurfaceSwitch = document.getElementById("mobile-surface-switch");
  var tabConversation = document.getElementById("tab-conversation");
  var tabGuidance = document.getElementById("tab-guidance");

  function isMobileSurfaceMode() {
    // Judged from the APPLIED responsive breakpoint (CSS media query
    // match), NOT a user-agent string. Matches the @media (max-width:
    // 767px) rule that switches the shell to the mobile column layout.
    try {
      return !!window.matchMedia && window.matchMedia("(max-width: 767px)").matches;
    } catch (_) {
      return false;
    }
  }

  function setMobileSurface(surface) {
    if (!isMobileSurfaceMode()) {
      // Desktop: the switch is hidden and never drives layout.
      return;
    }
    if (body) {
      body.setAttribute("data-mobile-surface", surface);
    }
    if (tabConversation) {
      tabConversation.setAttribute(
        "aria-pressed",
        surface === "conversation" ? "true" : "false"
      );
    }
    if (tabGuidance) {
      tabGuidance.setAttribute(
        "aria-pressed",
        surface === "guidance" ? "true" : "false"
      );
    }
    if (surface === "conversation") {
      // Activate conversation: chat-shell interactive, canvas inert+hidden.
      if (chatShell) {
        chatShell.removeAttribute("inert");
        chatShell.setAttribute("aria-hidden", "false");
      }
      if (canvas) {
        canvas.setAttribute("inert", "");
        canvas.setAttribute("aria-hidden", "true");
      }
    } else if (surface === "guidance") {
      // Activate guidance: canvas interactive, chat-shell inert+hidden.
      if (canvas) {
        canvas.removeAttribute("inert");
        canvas.setAttribute("aria-hidden", "false");
      }
      if (chatShell) {
        chatShell.setAttribute("inert", "");
        chatShell.setAttribute("aria-hidden", "true");
      }
    }
  }

  // Synchronize surface/focus state when the responsive breakpoint flips
  // (e.g. 767px → desktop). No UA sniffing; driven purely by matchMedia.
  function syncResponsiveMode() {
    if (isMobileSurfaceMode()) {
      return;
    }
    // Desktop: drop the mobile surface override and hide the switch.
    hideMobileSurfaceSwitch();
    if (chatShell) {
      // Remove the mobile-only inert/aria-hidden (desktop keeps both panes).
      chatShell.removeAttribute("inert");
      chatShell.setAttribute("aria-hidden", "false");
    }
    if (canvas) {
      // Restore canvas availability to the current first-use state:
      // available in split/transitioning, hidden in entry.
      var state = body ? body.getAttribute("data-first-use-state") : "";
      setCanvasAvailability(state === "split" || state === "transitioning");
    }
  }

  var _mobileMedia = null;
  try {
    if (window.matchMedia) {
      _mobileMedia = window.matchMedia("(max-width: 767px)");
      var _onMobileChange = function () { syncResponsiveMode(); };
      if (typeof _mobileMedia.addEventListener === "function") {
        _mobileMedia.addEventListener("change", _onMobileChange);
      } else if (typeof _mobileMedia.addListener === "function") {
        // Legacy Safari/old Chromium fallback.
        _mobileMedia.addListener(_onMobileChange);
      }
    }
  } catch (_) {
    /* matchMedia unavailable — responsive sync is best-effort only */
  }

  function showMobileSurfaceSwitch() {
    if (mobileSurfaceSwitch && isMobileSurfaceMode()) {
      mobileSurfaceSwitch.removeAttribute("hidden");
    }
  }

  function hideMobileSurfaceSwitch() {
    if (mobileSurfaceSwitch) {
      mobileSurfaceSwitch.setAttribute("hidden", "");
    }
    if (body) {
      body.removeAttribute("data-mobile-surface");
    }
  }

  function focusComposerIfAllowed() {
    // Shell-level composer focus guard: on mobile the conversation/
    // guidance switch owns visibility, so the shell must NOT pull focus
    // back into the composer during automated journey transitions,
    // after journey completion, or after reset. Explicit user taps still
    // focus (handled by the browser natively). Desktop keyboard
    // behavior is preserved.
    if (chatInput && !isMobileSurfaceMode()) {
      chatInput.focus();
    }
  }

  // ── Static Bukgu Homepage Fixture ───────────────────────────────────
  // Renders the Bukgu Office main portal layout as a static fixture for the
  // initial left surface (first visible canvas content on split).
  // Uses existing CSS classes from citizen-action-demo-canvas.css and
  // existing image assets from /static/images/bukgu-current/.

  function _bukguSearchIcon() {
    return '<svg viewBox="0 0 24 24" aria-hidden="true" focusable="false"><circle cx="10.8" cy="10.8" r="6.3" fill="none" stroke="currentColor" stroke-width="2"/><path d="M16 16l4.4 4.4" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"/></svg>';
  }
  function _bukguMenuIcon() {
    return '<svg viewBox="0 0 24 24" aria-hidden="true" focusable="false"><path d="M4 7h16M4 12h16M4 17h16" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"/></svg>';
  }
  function _bukguArrowLeft() {
    return '<svg viewBox="0 0 24 24" aria-hidden="true" focusable="false"><path d="M14.5 5.5L8 12l6.5 6.5" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"/></svg>';
  }
  function _bukguArrowRight() {
    return '<svg viewBox="0 0 24 24" aria-hidden="true" focusable="false"><path d="M9.5 5.5L16 12l-6.5 6.5" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"/></svg>';
  }

  function _renderBukguHomeFixture() {
    if (!canvas) return;
    // Keep the split reveal on the canonical canvas renderer. The historical
    // fallback below intentionally remains for shells loaded without the
    // canvas module, but must not overwrite newer home controls and routes.
    if (window.CitizenActionDemoCanvas &&
        typeof window.CitizenActionDemoCanvas.navigateToRoute === "function") {
      window.CitizenActionDemoCanvas.navigateToRoute("home");
      return;
    }
    var assets = "/static/images/bukgu-current";
    var searchIcon = _bukguSearchIcon();
    var menuIcon = _bukguMenuIcon();
    var arrowLeft = _bukguArrowLeft();
    var arrowRight = _bukguArrowRight();

    // Quick links
    var quickItems = [
      ["home-quick-work.png", "업무검색"],
      ["home-quick-office.png", "청사안내"],
      ["home-quick-donation.png", "고향사랑기부제"],
      ["home-quick-money.png", "부끄머니"],
      ["home-quick-reservation.png", "통합예약"],
      ["home-quick-waiting.png", "일반민원 대기현황"],
    ];
    var quickHtml = "";
    for (var i = 0; i < quickItems.length; i++) {
      quickHtml +=
        '<a href="#" class="bg-home-quick-link">' +
          '<img src="' + assets + '/' + quickItems[i][0] + '" alt="" class="bg-home-quick-link__icon" />' +
          '<span class="bg-home-quick-link__label">' + quickItems[i][1] + '</span>' +
        '</a>';
    }

    var html =
      '<div class="bg-page bg-page--full bg-page--home" data-home-reference-state="R-HOME-01">' +

        // Skip navigation
        '<div class="bg-skip"><a href="#bg-content-main">본문으로 바로가기</a></div>' +

        // Government strip
        '<div class="bg-home-gov-strip">' +
          '<div class="bg-home-gov-strip__inner">' +
            '<img src="' + assets + '/home-government-notice.png" alt="본 누리집은 전남광주통합특별시 북구청 공식 누리집입니다." class="bg-home-gov-strip__notice" />' +
          '</div>' +
        '</div>' +

        // Utility bar (weather, major sites)
        '<div class="bg-home-utility" aria-label="사이트 도구">' +
          '<div class="bg-home-utility__inner">' +
            '<div class="bg-home-utility__weather">' +
              '<strong>26\u00B0C</strong>' +
              '<span>\uBBF8\uC138\uBA3C\uC9C0 <b>\uC88B\uC74C</b></span>' +
              '<span>\uCD08\uBBF8\uC138\uBA3C\uC9C0 <b>\uC88B\uC74C</b></span>' +
            '</div>' +
            '<div class="bg-home-utility__menus">' +
              '<a href="#">\uC8FC\uC694\uC0AC\uC774\uD2B8 <span aria-hidden="true">\u25BE</span></a>' +
              '<a href="#">SNS <span aria-hidden="true">\u25BE</span></a>' +
              '<a href="#">KOR <span aria-hidden="true">\u25BE</span></a>' +
            '</div>' +
          '</div>' +
        '</div>' +

        // Header + Logo + GNB
        '<header class="bg-header">' +
          '<div class="bg-home-header">' +
          '<div class="bg-home-header__inner">' +
            '<a href="#" class="bg-home-header__identity" aria-label="\uC804\uB0A8\uAD11\uC8FC\uD1B5\uD569\uD2B9\uBCC4\uC2DC\uBD81\uAD6C \uD648">' +
              '<img src="' + assets + '/home-identity.png" alt="\uC804\uB0A8\uAD11\uC8FC\uD1B5\uD569\uD2B9\uBCC4\uC2DC\uBD81\uAD6C" />' +
            '</a>' +
            '<nav class="bg-gnb" aria-label="\uC8FC\uBA54\uB274">' +
              '<div class="bg-home-gnb">' +
              '<a href="#" class="bg-home-gnb__link bg-home-gnb__link--active">\uC885\uD569\uBBFC\uC6D0</a>' +
              '<a href="#" class="bg-home-gnb__link">\uC18C\uD1B5\uAD11\uC7A5</a>' +
              '<a href="#" class="bg-home-gnb__link">\uB354\uBD88\uC5B4\uBCF5\uC9C0</a>' +
              '<a href="#" class="bg-home-gnb__link">\uBD84\uC57C\uBCC4\uC815\uBCF4</a>' +
              '<a href="#" class="bg-home-gnb__link">\uC815\uBCF4\uACF5\uAC1C</a>' +
              '<a href="#" class="bg-home-gnb__link">\uBD81\uAD6C\uC18C\uAC1C</a>' +
            '</div>' +
            '</nav>' +
            '<div class="bg-home-header__actions">' +
              '<button type="button" class="bg-home-header__icon" aria-label="\uD1B5\uD569\uAC80\uC0C9">' + searchIcon + '<span>\uD1B5\uD569\uAC80\uC0C9</span></button>' +
              '<button type="button" class="bg-home-header__icon" aria-label="\uC804\uCCB4\uBA54\uB274">' + menuIcon + '<span>\uC804\uCCB4\uBA54\uB274</span></button>' +
            '</div>' +
          '</div>' +
        '</div>' +
        '</header>' +

        // Search section
        '<section class="bg-home-search" aria-label="\uD1B5\uD569\uAC80\uC0C9">' +
          '<div class="bg-home-search__inner">' +
            '<img src="' + assets + '/home-civic-brand.png" alt="\uBE5B\uB098\uB294 \uBD81\uAD6C, \uD568\uAED8\uD558\uB294 \uBD81\uAD6C - \uD589\uBCF5\uD55C \uAD6C\uBBFC\uC744 \uC704\uD55C \uB530\uB73B\uD55C \uBCC0\uD654" class="bg-home-search__brand" />' +
            '<div class="bg-home-search__cluster">' +
              '<div class="bg-home-search__field">' +
                '<input type="text" placeholder="\uAC80\uC0C9\uC5B4\uB97C \uC785\uB825\uD558\uC138\uC694." aria-label="\uAC80\uC0C9\uC5B4" disabled />' +
                '<button type="button" aria-label="\uAC80\uC0C9" disabled>' + searchIcon + '</button>' +
              '</div>' +
              '<div class="bg-home-search__tags"><span>#\uACF5\uB3D9\uC8FC\uD0DD\uACFC</span><span>#\uC704\uC0DD\uACFC</span><span>#\uD3D0\uAE30\uBB3C</span><span>#\uBD80\uAF34\uBA38\uB2C8</span></div>' +
            '</div>' +
          '</div>' +
        '</section>' +

        // Main content
        '<main id="bg-content-main" class="bg-home-main">' +

          // Lead banners (sliding visual area)
          '<section class="bg-home-lead" aria-label="\uC8FC\uC694 \uC548\uB0B4">' +
            '<article class="bg-home-lead__mayor">' +
              '<img src="' + assets + '/home-mayor-card.png" alt="\uB530\uB73B\uD55C \uBD81\uAD6C\uB97C \uB9CC\uB4E4\uACA0\uC2B5\uB2C8\uB2E4. \uBD81\uAD6C\uCCAD\uC7A5 \uC2E0\uC218\uC815\uC785\uB2C8\uB2E4." />' +
            '</article>' +
            '<article class="bg-home-lead__banner" aria-label="\uC18C\uC18D \uACF5\uBB34\uC6D0 \uC0AC\uCE6D \uD53C\uD574\uC8FC\uC758 \uC54C\uB9BC">' +
              '<img src="' + assets + '/home-alert-banner.png" alt="\uC8FC\uC694 \uC54C\uB9BC \uBC30\uB108" />' +
            '</article>' +
          '</section>' +

          // Quick links
          '<nav class="bg-home-quick" aria-label="\uBE60\uB978 \uC11C\uBE44\uC2A4">' +
            '<button type="button" class="bg-home-quick__arrow" aria-label="\uC774\uC804" disabled>' + arrowLeft + '</button>' +
            '<div class="bg-home-quick__items">' + quickHtml + '</div>' +
            '<button type="button" class="bg-home-quick__arrow" aria-label="\uB2E4\uC74C" disabled>' + arrowRight + '</button>' +
          '</nav>' +

          // Notice board + Major sites
          '<section class="bg-home-notice-sites" aria-label="\uACF5\uC9C0\uC640 \uC8FC\uC694 \uC0AC\uC774\uD2B8">' +
            '<article class="bg-home-notice">' +
              '<div class="bg-home-notice__tabs" role="tablist" aria-label="\uAC8C\uC2DC\uD310">' +
                '<button type="button" role="tab" aria-selected="true">\uACF5\uC9C0\uC0AC\uD56D</button>' +
                '<button type="button" role="tab">\uACE0\uC2DC/\uACF5\uACE0</button>' +
                '<button type="button" role="tab">\uC785\uCC30\uACF5\uACE0</button>' +
                '<button type="button" role="tab">\uCDE4\uC6A9\uACF5\uACE0</button>' +
                '<button type="button" class="bg-home-notice__more" aria-label="\uB354\uBCF4\uAE30">+</button>' +
              '</div>' +
              '<ul class="bg-home-notice__list">' +
                '<li><b>07</b><span>\uCCAD\uC0AC \uC2B9\uAC15\uAE30 \uC815\uAE30\uC810\uAC80 \uC548\uB0B4</span></li>' +
                '<li><b>07</b><span>2026\uB144 \uD558\uBC18\uAE30 \uAD6C\uBBFC \uAD50\uC721 \uD504\uB85C\uADF8\uB7A8 \uC548\uB0B4</span></li>' +
                '<li><b>07</b><span>\uC5EC\uB984\uCCA0 \uC548\uC804\uC218\uC808 \uC2DC\uC124 \uD655\uBCF4 \uC0AC\uC5C5 \uC548\uB0B4</span></li>' +
                '<li><b>07</b><span>\uD3D0\uAE30\uBB3C \uBC30\uCD9C \uC2E0\uCCAD \uC77C\uC790 \uBCC0\uACBD \uC548\uB0B4</span></li>' +
              '</ul>' +
            '</article>' +
            '<article class="bg-home-sites">' +
              '<div class="bg-home-sites__head"><h2>\uC8FC\uC694\uC0AC\uC774\uD2B8</h2><span>\u2039&nbsp;&nbsp;1 / 4&nbsp;&nbsp;\u2161&nbsp;&nbsp;\u203A</span></div>' +
              '<div class="bg-home-sites__grid">' +
                '<a href="#"><i class="bg-home-sites__glyph bg-home-sites__glyph--chart"></i>\uD1B5\uACC4\uC815\uBCF4</a>' +
                '<a href="#"><i class="bg-home-sites__glyph bg-home-sites__glyph--school"></i>\uD3C9\uC0DD\uD559\uC2B5\uAD00</a>' +
                '<a href="#"><i class="bg-home-sites__glyph bg-home-sites__glyph--sun"></i>\uCCAD\uB144\uC13C\uD130</a>' +
                '<a href="#"><i class="bg-home-sites__glyph bg-home-sites__glyph--culture"></i>\uBB38\uD654\uC13C\uD130</a>' +
                '<a href="#"><i class="bg-home-sites__glyph bg-home-sites__glyph--park"></i>\uACF5\uC6D0\uC2DC\uC124 \uC608\uC57D</a>' +
                '<a href="#"><i class="bg-home-sites__glyph bg-home-sites__glyph--sport"></i>\uCCB4\uC721\uC2DC\uC124 \uC608\uC57D</a>' +
              '</div>' +
            '</article>' +
          '</section>' +

          // Lower section
          '<section class="bg-home-lower" aria-label="\uD558\uB2E8 \uC18C\uC2DD\uACFC \uBD84\uC57C\uBCC4 \uC815\uBCF4">' +
            '<section class="bg-home-lower-cards" aria-label="\uC8FC\uC694 \uC18C\uC2DD">' +
              '<article class="bg-home-lower-card">' +
                '<div class="bg-home-lower-card__head"><h2>\uACE0\uD5A5\uC0AC\uB791\uAE30\uBD80\uC81C</h2><span aria-hidden="true">\u2039&nbsp;\u2161&nbsp;\u203A&nbsp;+</span></div>' +
                '<img src="' + assets + '/home-lower-hometown-donation.png" alt="\uACE0\uD5A5\uC0AC\uB791\uAE30\uBD80\uC81C \uC548\uB0B4" />' +
              '</article>' +
              '<article class="bg-home-lower-card">' +
                '<div class="bg-home-lower-card__head"><h2>\uD604\uC7A5\uC2A4\uCF00\uCE58</h2><span aria-hidden="true">\u2039&nbsp;<b>1</b> / 4&nbsp;\u2161&nbsp;\u203A&nbsp;+</span></div>' +
                '<img src="' + assets + '/home-lower-field-sketch.png" alt="\uD604\uC7A5\uC2A4\uCF00\uCE58" />' +
              '</article>' +
              '<article class="bg-home-lower-card">' +
                '<div class="bg-home-lower-card__head"><h2>\uCE74\uB4DC\uB274\uC2A4</h2><span aria-hidden="true">+</span></div>' +
                '<img src="' + assets + '/home-lower-card-news.png" alt="\uCE74\uB4DC\uB274\uC2A4" />' +
              '</article>' +
              '<article class="bg-home-lower-card">' +
                '<div class="bg-home-lower-card__head"><h2>\uC54C\uB9AC\uBBF8</h2><span aria-hidden="true">\u2039&nbsp;<b>1</b> / 4&nbsp;\u2161&nbsp;\u203A&nbsp;+</span></div>' +
                '<img src="' + assets + '/home-lower-notifier.png" alt="\uC54C\uB9AC\uBBF8" />' +
              '</article>' +
            '</section>' +
          '</section>' +

        '</main>' +

        // Footer
        '<footer class="bg-home-footer" aria-label="\uC0AC\uC774\uD2B8 \uD558\uB2E8">' +
          '<div class="bg-home-footer__inner">' +
            '<nav class="bg-home-footer__nav" aria-label="\uD558\uB2E8 \uBA54\uB274">' +
              '<a href="#">\uBD80\uC11C\uC548\uB0B4 <span aria-hidden="true">\u2303</span></a>' +
              '<a href="#">\uB3D9 \uD589\uC815\uBCF5\uC9C0\uC13C\uD130 <span aria-hidden="true">\u2303</span></a>' +
              '<a href="#">\uC8FC\uC694 \uC0AC\uC774\uD2B8 <span aria-hidden="true">\u2303</span></a>' +
              '<a href="#">\uC720\uAD00\uAE30\uAD00 <span aria-hidden="true">\u2303</span></a>' +
            '</nav>' +
            '<div class="bg-home-footer__legal">' +
              '<p><strong>\uC804\uB0A8\uAD11\uC8FC\uD1B5\uD569\uD2B9\uBCC4\uC2DC \uBD81\uAD6C</strong></p>' +
              '<p>61118 \uAD11\uC8FC \uBD81\uAD6C \uC6B0\uCE58\uB85C 77 (\uD50C\uB9BC\uB3D9)</p>' +
              '<p>\uB300\uD45C\uC804\uD654 062-410-8114 | \uD64D\uBCF4\uAD00\uB780\uBA54\uC77C webmaster@bukgu.gwangju.kr</p>' +
              '<p>\uD3C9\uC77C 09:00 ~ 18:00 (\uC811\uC218\uC2DC\uAC04 09:00 ~ 17:30) / \uD1A0/\uC77C\uC694\uC77C \uAD6C\uAD6C\uC815\uC0AC\uBB34\uC548\uB0B4 \uD655\uC778</p>' +
            '</div>' +
          '</div>' +
        '</footer>' +
      '</div>';

    canvas.innerHTML = '<div class="demo-canvas__inner">' + html + '</div>';
  }

  function setComposerDisabled(isDisabled) {
    if (chatInput) {
      chatInput.disabled = isDisabled;
    }
    if (chatSend) {
      chatSend.disabled = isDisabled;
    }
    if (chatShell) {
      // Composer lock CSS signal only. Semantic aria-busy is owned by journey
      // navigate (website choreography), not MVP answer wait / layout transition.
      chatShell.setAttribute("data-chat-busy", isDisabled ? "true" : "false");
    }
    // Keep journey busy mapping authoritative after any composer lock toggle.
    _applyJourneyBusy(currentJourneyState);
  }

  function setState(nextState, options) {
    options = options || {};
    currentState = nextState;
    body.setAttribute("data-first-use-state", nextState);

    if (nextState === STATE_ENTRY) {
      setCanvasAvailability(false);
      setComposerDisabled(false);
      if (resetButton) {
        resetButton.hidden = true;
      }
      if (chipsContainer) {
        chipsContainer.hidden = false;
      }
      hideMobileSurfaceSwitch();
      // Layout-only → replace (never push). Skip while history restore owns writes.
      if (!shouldSuppressHistoryWrite() && !options.skipHistory) {
        writeHistorySnapshot("replace");
      }
      return;
    }

    if (nextState === STATE_TRANSITIONING) {
      setCanvasAvailability(false);
      setComposerDisabled(true);
      if (resetButton) {
        resetButton.hidden = true;
      }
      if (chipsContainer) {
        chipsContainer.hidden = true;
      }
      hideMobileSurfaceSwitch();
      // transitioning is never persisted to history.state
      return;
    }

    setCanvasAvailability(true);
    setComposerDisabled(false);
    if (resetButton) {
      resetButton.hidden = false;
    }
    if (chipsContainer) {
      chipsContainer.hidden = false;
    }
    // Mobile: expose the conversation/guidance switch once split is live.
    showMobileSurfaceSwitch();
    // #1133: history restore applies mobile surface after layout.
    if (!options.preserveMobileSurface) {
      setMobileSurface("conversation");
    }
    if (!shouldSuppressHistoryWrite() && !options.skipHistory) {
      writeHistorySnapshot("replace");
    }
  }

  function clearChatMotionStyles() {
    if (!chatShell) return;
    chatShell.style.removeProperty("transition");
    chatShell.style.removeProperty("transform");
    chatShell.style.removeProperty("transform-origin");
    body.removeAttribute("data-split-motion");
  }

  function fitOfficialCanvas() {
    if (window.CitizenActionDemoCanvas &&
        typeof window.CitizenActionDemoCanvas.fitToViewport === "function") {
      window.CitizenActionDemoCanvas.fitToViewport();
    }
  }

  function resetOfficialCanvasScroll() {
    if (!canvas) return;
    canvas.scrollTop = 0;
    canvas.scrollLeft = 0;
  }

  function clearPreviousJourneyLocationState() {
    // #1133: shell-owned replace only — never a bare pushState/empty state.
    try {
      writeHistorySnapshot("replace", {
        force: true,
        dropJourneyQuery: true
      });
    } catch (_) {
      // URL state is an enhancement; the DOM and scroll reset still proceed.
    }
  }

  function startCinematicSplit() {
    if (window.CitizenFirstChoreography &&
        typeof window.CitizenFirstChoreography.cancel === "function") {
      window.CitizenFirstChoreography.cancel();
    }
    if (window.CitizenActionDemoCanvas &&
        typeof window.CitizenActionDemoCanvas.hideCursor === "function") {
      window.CitizenActionDemoCanvas.hideCursor();
    }
    clearPreviousJourneyLocationState();
    resetOfficialCanvasScroll();

    // Paint the official canvas before the reveal starts so the animation
    // exposes a complete page rather than a loading placeholder.
    _renderBukguHomeFixture();
    resetOfficialCanvasScroll();

    if (prefersReducedMotion() || !chatShell || !window.requestAnimationFrame) {
      setState(STATE_TRANSITIONING);
      fitOfficialCanvas();
      resetOfficialCanvasScroll();
      return;
    }

    var firstRect = chatShell.getBoundingClientRect();
    setState(STATE_TRANSITIONING);
    fitOfficialCanvas();
    resetOfficialCanvasScroll();
    var lastRect = chatShell.getBoundingClientRect();
    var scaleX = lastRect.width ? firstRect.width / lastRect.width : 1;
    var scaleY = lastRect.height ? firstRect.height / lastRect.height : 1;
    var translateX = firstRect.left - lastRect.left;
    var translateY = firstRect.top - lastRect.top;

    body.setAttribute("data-split-motion", "active");
    chatShell.style.transition = "none";
    chatShell.style.transformOrigin = "top left";
    chatShell.style.transform =
      "translate(" + translateX + "px," + translateY + "px) " +
      "scale(" + scaleX + "," + scaleY + ")";
    chatShell.getBoundingClientRect();

    window.requestAnimationFrame(function () {
      window.requestAnimationFrame(function () {
        chatShell.style.transition =
          "transform " + TRANSITION_DURATION_MS + "ms cubic-bezier(0.16, 1, 0.3, 1), " +
          "border-radius 900ms ease, box-shadow 900ms ease";
        chatShell.style.transform = "translate(0,0) scale(1,1)";
      });
    });
  }

  function scrollChatToLatest() {
    if (chatThread) {
      chatThread.scrollTop = chatThread.scrollHeight;
    }
  }

  function appendChatMessage(role, text) {
    if (!chatThread) {
      return null;
    }
    // #1133: history restore must never append or replay messages.
    if (_historyRestoring) {
      return null;
    }

    var message = document.createElement("div");
    message.className = "chat-msg chat-msg--" + role;

    if (role === "ai") {
      var avatar = document.createElement("div");
      avatar.className = "chat-avatar";
      avatar.setAttribute("aria-label", "AI");
      avatar.textContent = "A";
      message.appendChild(avatar);
    }

    var bubble = document.createElement("div");
    bubble.className = "chat-bubble chat-bubble--" + role;
    bubble.textContent = text;
    message.appendChild(bubble);
    chatThread.appendChild(message);
    scrollChatToLatest();
    return message;
  }

  function freshnessLabel(value) {
    if (value === "live_official") return "최신 공식자료 확인";
    if (value === "official_snapshot") return "북구청 공식 스냅샷";
    if (value === "live_web") return "최신 웹자료 확인 · 공식 출처 재확인 필요";
    if (value === "model_only") return "현재 공식 출처 없음";
    return "최신성 확인 불가";
  }

  function formatRetrievedAt(value) {
    if (!value) return "";
    try {
      return new Date(value).toLocaleString("ko-KR", {
        timeZone: "Asia/Seoul",
        year: "numeric",
        month: "2-digit",
        day: "2-digit",
        hour: "2-digit",
        minute: "2-digit",
      });
    } catch (_) {
      return "";
    }
  }

  function appendAnswerFreshness(message, result) {
    if (!message || !result || result.ok !== true) return;
    var sources = Array.isArray(result.sources) ? result.sources.slice(0, 3) : [];
    var provenanceTime = result.freshness_state === "official_snapshot"
      ? (result.verified_at || result.captured_at)
      : result.retrieved_at;
    var retrievedAt = formatRetrievedAt(provenanceTime);
    if (!retrievedAt && !sources.length && !result.freshness_state) return;

    var meta = document.createElement("div");
    meta.className = "chat-answer-meta";
    meta.setAttribute("data-freshness-state", result.freshness_state || "unknown");

    var status = document.createElement("span");
    status.className = "chat-answer-meta__status";
    status.textContent = freshnessLabel(result.freshness_state) + (retrievedAt ? " · " + retrievedAt : "");
    meta.appendChild(status);

    sources.forEach(function (source) {
      if (!source || typeof source.url !== "string") return;
      var link;
      try {
        var parsed = new URL(source.url);
        if (parsed.protocol !== "https:" && parsed.protocol !== "http:") return;
        link = document.createElement("a");
        link.href = parsed.toString();
      } catch (_) {
        return;
      }
      link.className = "chat-answer-meta__source";
      link.target = "_blank";
      link.rel = "noopener noreferrer";
      link.textContent = source.official ? "공식 출처" : "참고 출처";
      link.setAttribute("aria-label", (source.title || "답변 출처") + " 새 창 열기");
      meta.appendChild(link);
    });

    var bubble = message.querySelector && message.querySelector(".chat-bubble");
    (bubble || message).appendChild(meta);
    scrollChatToLatest();
  }

  function renderEntryConversation() {
    if (!chatThread) {
      return;
    }
    chatThread.innerHTML = "";
    appendChatMessage(
      "ai",
      "안녕하세요. 북구청 민원 안내 AI입니다. 궁금한 민원을 물어보시면 관련 화면을 함께 열어 경로를 안내해 드립니다."
    );
  }

  function _questDisplayName(question) {
    if (!question) return "이 안내";
    if (question.indexOf("불법 주정차") !== -1) return "불법 주정차 신고";
    if (question.indexOf("공동주택") !== -1) return "공동주택 부서 문의";
    if (question.indexOf("침대") !== -1 || question.indexOf("매트리스") !== -1) return "대형폐기물 배출";
    if (question.indexOf("대형폐기물") !== -1 || question.indexOf("가구") !== -1) return "대형폐기물 배출";
    if (question.indexOf("여권") !== -1) return "여권 발급 안내";
    if (question.indexOf("무인민원발급기") !== -1 || question.indexOf("민원서류") !== -1) return "무인민원발급기 안내";
    if (question.indexOf("가로등") !== -1) return "가로등 고장 신고";
    if (question.indexOf("쓰레기") !== -1) return "쓰레기 무단투기 신고";
    // #1114 — mayor proposal writing assist (static question path)
    if (question.indexOf("구청장") !== -1) return "구청장 제안 작성";
    return "이 안내";
  }

  function _actionDisplayName(action) {
    if (action === "illegal_parking") return "불법 주정차 신고";
    if (action === "housing_department") return "공동주택 부서 문의";
    if (action === "bulky_waste") return "대형폐기물 배출";
    if (action === "passport_guidance") return "여권 발급 안내";
    if (action === "unmanned_kiosk") return "무인민원발급기 안내";
    if (action === "streetlight_report") return "가로등 고장 신고";
    if (action === "litter_ai_assist") return "쓰레기 무단투기 신고";
    // #1114 — mayor proposal writing assist (model-backed action path)
    if (action === "mayor_message_assist") return "구청장 제안 작성";
    return "이 안내";
  }

  function startChoreography(question) {
    // #1067: positive confirm → navigate (choreography start also emits running).
    setJourneyState(JOURNEY_NAVIGATE);
    if (window.CitizenFirstChoreography && question) {
      window.CitizenFirstChoreography.start(question);
    }
    // Do NOT unconditionally pull focus into the composer. On mobile the
    // conversation/guidance switch owns visibility and keyboard state; on
    // desktop the existing keyboard flow is preserved via the guard.
    focusComposerIfAllowed();
  }

  function showConfirmRun(question) {
    var displayName = _questDisplayName(question);
    var msgDiv = document.createElement("div");
    msgDiv.className = "chat-msg chat-msg--ai chat-msg--confirm-run";
    msgDiv.setAttribute("data-msg-type", "confirm-run");
    var gen = _confirmGeneration;

    var bubble = document.createElement("div");
    bubble.className = "chat-bubble chat-bubble--ai";

    var text = document.createElement("p");
    text.style.margin = "0 0 10px 0";
    text.textContent = displayName + "에 대해 안내해 드릴까요?";
    bubble.appendChild(text);

    var btnRow = document.createElement("div");
    btnRow.style.display = "flex";
    btnRow.style.gap = "8px";

    var yesBtn = document.createElement("button");
    yesBtn.type = "button";
    yesBtn.textContent = "예, 안내해 주세요";
    yesBtn.style.cssText = "padding:8px 16px;border:0;border-radius:18px;background:#ef6a4c;color:#fff;font:inherit;font-size:0.85rem;font-weight:600;cursor:pointer;";
    yesBtn.addEventListener("click", function () {
      if (gen !== _confirmGeneration) return;
      msgDiv.removeAttribute("data-msg-type");
      var btns = bubble.querySelectorAll("button");
      for (var i = 0; i < btns.length; i++) btns[i].disabled = true;
      // Mobile: switch the active surface to guidance BEFORE the
      // scripted navigation starts, and close the composer keyboard.
      if (isMobileSurfaceMode() && chatInput) {
        chatInput.blur();
      }
      setMobileSurface("guidance");
      startChoreography(question);
    });

    var noBtn = document.createElement("button");
    noBtn.type = "button";
    noBtn.textContent = "아니요";
    noBtn.style.cssText = "padding:8px 16px;border:1px solid #d0d0d5;border-radius:18px;background:#fff;color:#0d0d0f;font:inherit;font-size:0.85rem;cursor:pointer;";
    noBtn.addEventListener("click", function () {
      if (gen !== _confirmGeneration) return;
      msgDiv.removeAttribute("data-msg-type");
      var btns = bubble.querySelectorAll("button");
      for (var i = 0; i < btns.length; i++) btns[i].disabled = true;
      // Decline navigation — remain on the answered chat without clone drive.
      setJourneyState(JOURNEY_ANSWER);
      focusComposerIfAllowed();
    });

    btnRow.appendChild(yesBtn);
    btnRow.appendChild(noBtn);
    bubble.appendChild(btnRow);

    var avatar = document.createElement("div");
    avatar.className = "chat-avatar";
    avatar.setAttribute("aria-label", "AI");
    avatar.textContent = "A";
    msgDiv.appendChild(avatar);
    msgDiv.appendChild(bubble);

    chatThread.appendChild(msgDiv);
    chatThread.scrollTop = chatThread.scrollHeight;
    // #1067: confirm-run bubble shown — wait for resident decision.
    setJourneyState(JOURNEY_CONFIRM);
  }

  // MVP confirm-run step: mirrors showConfirmRun but maps an action code to a
  // display name instead of a free-text question. The local choreography must
  // NOT start until the citizen explicitly chooses [예, 안내해 주세요].
  function showConfirmRunForAction(action) {
    var displayName = _actionDisplayName(action);
    var msgDiv = document.createElement("div");
    msgDiv.className = "chat-msg chat-msg--ai chat-msg--confirm-run";
    msgDiv.setAttribute("data-msg-type", "confirm-run");
    var gen = _confirmGeneration;

    var bubble = document.createElement("div");
    bubble.className = "chat-bubble chat-bubble--ai";

    var text = document.createElement("p");
    text.style.margin = "0 0 10px 0";
    text.textContent = displayName + "에 대해 안내해 드릴까요?";
    bubble.appendChild(text);

    var btnRow = document.createElement("div");
    btnRow.style.display = "flex";
    btnRow.style.gap = "8px";

    var yesBtn = document.createElement("button");
    yesBtn.type = "button";
    yesBtn.textContent = "예, 안내해 주세요";
    yesBtn.style.cssText = "padding:8px 16px;border:0;border-radius:18px;background:#ef6a4c;color:#fff;font:inherit;font-size:0.85rem;font-weight:600;cursor:pointer;";
    yesBtn.addEventListener("click", function () {
      if (gen !== _confirmGeneration) return;
      msgDiv.removeAttribute("data-msg-type");
      var btns = bubble.querySelectorAll("button");
      for (var i = 0; i < btns.length; i++) btns[i].disabled = true;
      // Mobile: switch to guidance + close composer keyboard before
      // the scripted navigation starts.
      if (isMobileSurfaceMode() && chatInput) {
        chatInput.blur();
      }
      setMobileSurface("guidance");
      setJourneyState(JOURNEY_NAVIGATE);
      if (window.CitizenFirstChoreography && action) {
        window.CitizenFirstChoreography.start(action);
      }
    });

    var noBtn = document.createElement("button");
    noBtn.type = "button";
    noBtn.textContent = "아니요";
    noBtn.style.cssText = "padding:8px 16px;border:1px solid #d0d0d5;border-radius:18px;background:#fff;color:#0d0d0f;font:inherit;font-size:0.85rem;cursor:pointer;";
    noBtn.addEventListener("click", function () {
      if (gen !== _confirmGeneration) return;
      msgDiv.removeAttribute("data-msg-type");
      var btns = bubble.querySelectorAll("button");
      for (var i = 0; i < btns.length; i++) btns[i].disabled = true;
      setJourneyState(JOURNEY_ANSWER);
      focusComposerIfAllowed();
    });

    btnRow.appendChild(yesBtn);
    btnRow.appendChild(noBtn);
    bubble.appendChild(btnRow);

    var avatar = document.createElement("div");
    avatar.className = "chat-avatar";
    avatar.setAttribute("aria-label", "AI");
    avatar.textContent = "A";
    msgDiv.appendChild(avatar);
    msgDiv.appendChild(bubble);

    chatThread.appendChild(msgDiv);
    chatThread.scrollTop = chatThread.scrollHeight;
    setJourneyState(JOURNEY_CONFIRM);
  }

  function completeSplit() {
    splitTimer = null;
    _pendingSplitComplete = null;
    setState(STATE_SPLIT);
    clearChatMotionStyles();
    fitOfficialCanvas();
    // Delay chat message slightly so the canvas fade-in is visible first.
    // #1132: reduced motion uses 0ms task boundary (still async; no 220ms wait).
    window.setTimeout(function () {
      appendChatMessage(
        "ai",
        "질문을 확인했습니다. 왼쪽에 북구청 안내 화면을 열었습니다."
      );
      // Ack is an assistant answer before the confirm gate.
      setJourneyState(JOURNEY_ANSWER);
      if (lastSplitQuestion) {
        showConfirmRun(lastSplitQuestion);
      }
      lastSplitQuestion = null;
    }, splitAckDelayMs());
  }

  function beginSupportedTransition(question) {
    lastSplitQuestion = question;
    appendChatMessage("user", question);
    if (chatInput) {
      chatInput.value = "";
    }

    startCinematicSplit();
    scheduleSplitCompletion(completeSplit);
  }

  // ── #1114: central mayor-proposal entry ─────────────────────────
  // Canonical pair used by chip / composer / static / MVP / manual hero:
  //   question: 구청장에게 제안하고 싶어요
  //   action:   mayor_message_assist
  // Chat path shows the existing AI cursor click on the hero blue control
  // BEFORE cinematic split. Manual hero click skips automated re-click.
  // Shared continuation always uses MAYOR_MESSAGE_ASSIST_JOURNEY (confirm-run
  // gate, no direct final-route jump, no second cursor DOM).
  var MAYOR_CANONICAL_QUESTION = "구청장에게 제안하고 싶어요";
  var MAYOR_CANONICAL_ACTION = "mayor_message_assist";
  var MAYOR_CONTROL_SELECTOR = "#mayor-open-office-control";
  var _mayorEntryInFlight = false;
  var _mayorEntryTimer = null;
  var _mayorEntryAuxTimers = [];
  // #1132: options for mid-flight reduced-motion flush (not a public API).
  var _mayorEntryPendingOptions = null;

  function isMayorQuestion(value) {
    return normalizeQuestion(value) === MAYOR_CANONICAL_QUESTION;
  }

  function isMayorAction(value) {
    return value === MAYOR_CANONICAL_ACTION;
  }

  function _clearMayorEntryTimers() {
    if (_mayorEntryTimer !== null) {
      window.clearTimeout(_mayorEntryTimer);
      _mayorEntryTimer = null;
    }
    for (var i = 0; i < _mayorEntryAuxTimers.length; i++) {
      window.clearTimeout(_mayorEntryAuxTimers[i]);
    }
    _mayorEntryAuxTimers = [];
    _mayorEntryInFlight = false;
    _mayorEntryPendingOptions = null;
    var control = document.getElementById("mayor-open-office-control");
    if (control) {
      control.classList.remove("executor-highlight");
      control.classList.remove("is-agent-target");
    }
  }

  function _scheduleMayorAux(fn, delayMs) {
    var id = window.setTimeout(fn, delayMs);
    _mayorEntryAuxTimers.push(id);
    return id;
  }

  function _isMayorControlVisuallyAvailable(control) {
    if (!control) return false;
    var rect = control.getBoundingClientRect();
    if (!rect || rect.width <= 0 || rect.height <= 0) return false;
    try {
      var style = window.getComputedStyle(control);
      if (!style) return true;
      if (style.display === "none" || style.visibility === "hidden") return false;
      if (Number(style.opacity) === 0) return false;
    } catch (_) {
      /* getComputedStyle unavailable — rely on rect only */
    }
    return true;
  }

  function _beginMayorSplitContinuation(options) {
    options = options || {};
    var useActionConfirm = !!options.useActionConfirm;
    // Keep lastSplitQuestion for the static confirm-run path. MVP confirm uses
    // the action code via completeMvpSplit (MAYOR_CANONICAL_ACTION).
    if (useActionConfirm) {
      lastSplitQuestion = MAYOR_CANONICAL_QUESTION;
      startCinematicSplit();
      scheduleSplitCompletion(function () {
        completeMvpSplit(MAYOR_CANONICAL_ACTION);
      });
      return;
    }
    lastSplitQuestion = MAYOR_CANONICAL_QUESTION;
    startCinematicSplit();
    scheduleSplitCompletion(completeSplit);
  }

  /**
   * #1132: when motion is reduced mid mayor cursor→split, finish decorative
   * delays without canceling the journey or moving focus.
   */
  function finishMayorEntryWithoutMotion() {
    if (!_mayorEntryInFlight) {
      return;
    }
    var pending = _mayorEntryPendingOptions || {};
    if (window.CitizenActionDemoCanvas &&
        typeof window.CitizenActionDemoCanvas.hideCursor === "function") {
      window.CitizenActionDemoCanvas.hideCursor();
    }
    // Clear decorative timers/highlights, then continue the same confirm path.
    _clearMayorEntryTimers();
    _beginMayorSplitContinuation({
      useActionConfirm: !!pending.useActionConfirm
    });
  }

  /**
   * Canonical mayor entry controller.
   * @param {{
   *   source?: "chat"|"hero",
   *   userInitiatedControlClick?: boolean,
   *   skipUserMessage?: boolean,
   *   useActionConfirm?: boolean
   * }} options
   */
  function startMayorProposalEntry(options) {
    options = options || {};
    var source = options.source === "hero" ? "hero" : "chat";
    var userInitiatedControlClick = !!options.userInitiatedControlClick;
    var skipUserMessage = !!options.skipUserMessage;
    var useActionConfirm = !!options.useActionConfirm;

    if (currentState === STATE_TRANSITIONING || _mayorEntryInFlight) {
      return;
    }
    // Idempotent: already split for the same canonical mayor question.
    if (
      currentState === STATE_SPLIT &&
      lastSplitQuestion === MAYOR_CANONICAL_QUESTION &&
      !skipUserMessage
    ) {
      return;
    }

    // Single user-message echo for all entry points (unless already echoed).
    if (!skipUserMessage && currentState !== STATE_SPLIT) {
      appendChatMessage("user", MAYOR_CANONICAL_QUESTION);
      if (chatInput) chatInput.value = "";
    }

    // Manual hero activation: the user click IS the canonical activation.
    // Do not re-drive an automated second click on the same control.
    if (userInitiatedControlClick || source === "hero") {
      _beginMayorSplitContinuation({ useActionConfirm: useActionConfirm });
      return;
    }

    // Chat / model path: when the hero blue control is visible, show the
    // existing AI cursor → highlight → click/ripple, then split. Stay on
    // first-use-state=entry until the click animation finishes.
    var control = document.getElementById("mayor-open-office-control");
    var canvasApi = window.CitizenActionDemoCanvas;
    var canAnimate =
      _isMayorControlVisuallyAvailable(control) &&
      canvasApi &&
      typeof canvasApi.showCursorAt === "function" &&
      typeof canvasApi.clickAnimation === "function";

    if (!canAnimate) {
      // Mobile (control hidden) or missing cursor API — keep order without a
      // visible click, still one split / one confirm path.
      _beginMayorSplitContinuation({ useActionConfirm: useActionConfirm });
      return;
    }

    _mayorEntryInFlight = true;
    _mayorEntryPendingOptions = { useActionConfirm: useActionConfirm };
    var reduced = prefersReducedMotion();

    // #1132: reduced motion keeps static highlight only — no cursor/ripple wait.
    if (reduced) {
      control.classList.add("executor-highlight");
      control.classList.add("is-agent-target");
      if (typeof canvasApi.hideCursor === "function") {
        canvasApi.hideCursor();
      }
      window.setTimeout(function () {
        if (!_mayorEntryInFlight) return;
        control.classList.remove("executor-highlight");
        control.classList.remove("is-agent-target");
        _mayorEntryInFlight = false;
        _mayorEntryPendingOptions = null;
        _mayorEntryAuxTimers = [];
        _beginMayorSplitContinuation({ useActionConfirm: useActionConfirm });
      }, 0);
      return;
    }

    // #1140: align with canvas cursor move(1140)+dwell(300)+click-read(340).
    var moveDelay = 100;
    var clickDelay = 120;
    var afterClickDelay = 1440 + 340;
    var splitAt = clickDelay + afterClickDelay;

    if (typeof canvasApi.hideCursor === "function") {
      canvasApi.hideCursor();
    }
    control.classList.add("executor-highlight");
    control.classList.add("is-agent-target");

    _scheduleMayorAux(function () {
      if (!_mayorEntryInFlight) return;
      canvasApi.showCursorAt(MAYOR_CONTROL_SELECTOR);
    }, moveDelay);

    _scheduleMayorAux(function () {
      if (!_mayorEntryInFlight) return;
      // Visual click only — do NOT fire a real DOM click (would re-enter).
      canvasApi.clickAnimation(MAYOR_CONTROL_SELECTOR);
    }, clickDelay);

    _mayorEntryTimer = window.setTimeout(function () {
      _mayorEntryTimer = null;
      if (!_mayorEntryInFlight) return;
      control.classList.remove("executor-highlight");
      control.classList.remove("is-agent-target");
      _mayorEntryInFlight = false;
      _mayorEntryPendingOptions = null;
      _mayorEntryAuxTimers = [];
      _beginMayorSplitContinuation({ useActionConfirm: useActionConfirm });
    }, splitAt);
  }

  // Back-compat alias used by earlier #1114 wiring.
  function beginMayorProposalEntry() {
    startMayorProposalEntry({ source: "hero", userInitiatedControlClick: true });
  }

  function handleSubmission(event) {
    if (event) {
      event.preventDefault();
    }

    // Bounded split/follow-up: never start another transition while one is in
    // flight, and never run without a composer input element.
    if (currentState === STATE_TRANSITIONING || !chatInput) {
      return;
    }
    // #1114: also block while mayor cursor→split sequence is scheduled.
    if (_mayorEntryInFlight) {
      return;
    }

    var question = normalizeQuestion(chatInput.value);
    if (!question) {
      focusComposerIfAllowed();
      return;
    }

    if (isMvpMode()) {
      handleMvpSubmission(question);
      return;
    }

    if (currentState === STATE_SPLIT) {
      appendChatMessage("user", question);
      chatInput.value = "";
      if (isMayorQuestion(question)) {
        if (window.CitizenFirstChoreography) {
          window.CitizenFirstChoreography.cancel();
        }
        // Control is hidden after split; skip automated cursor re-click.
        startMayorProposalEntry({
          source: "chat",
          skipUserMessage: true,
          userInitiatedControlClick: true
        });
        return;
      }
      if (isSupportedQuestion(question)) {
        // Cancel current choreography and start new quest (no duplicate message)
        if (window.CitizenFirstChoreography) {
          window.CitizenFirstChoreography.cancel();
        }
        lastSplitQuestion = question;
        startCinematicSplit();
        scheduleSplitCompletion(completeSplit);
      } else {
        appendChatMessage("ai", SPLIT_FOLLOW_UP_MESSAGE);
        setJourneyState(JOURNEY_ANSWER);
        focusComposerIfAllowed();
      }
      return;
    }

    // Entry: mayor converges on the canonical controller (cursor → split).
    if (isMayorQuestion(question)) {
      startMayorProposalEntry({ source: "chat" });
      return;
    }

    if (isSupportedQuestion(question)) {
      beginSupportedTransition(question);
      return;
    }

    appendChatMessage("user", question);
    chatInput.value = "";
    appendChatMessage(
      "ai",
"현재 첫 화면에서는 불법 주정차 신고, 공동주택 문의, 대형폐기물 처리, 여권 발급 안내, 무인민원발급기 안내를 준비했습니다. 예시 질문으로 다시 입력해 주세요."
    );
    // #1067: general/unsupported static answer — stay in answer, no navigation.
    setJourneyState(JOURNEY_ANSWER);
    focusComposerIfAllowed();
  }

  // ── MVP submission (#925 / #927) ───────────────────────────────

  function handleMvpSubmission(question) {
    clearQuestRuntimeState();
    // 1. echo user message
    appendChatMessage("user", question);
    if (chatInput) chatInput.value = "";
    // 2. lock composer against duplicate submission
    setComposerDisabled(true);

    var token = ++_mvpRequestToken;

    _withMvpBridge(function (bridge) {
      if (token !== _mvpRequestToken) return; // superseded by a newer submit/reset
      if (!bridge || typeof bridge.ask !== "function") {
        setComposerDisabled(false);
        focusComposerIfAllowed();
        appendChatMessage("ai", "현재 AI 안내를 연결하지 못했습니다.");
        setJourneyState(JOURNEY_ANSWER);
        return;
      }
      bridge.ask(question).then(function (result) {
        if (token !== _mvpRequestToken) return; // late/aborted response ignored
        setComposerDisabled(false);
        focusComposerIfAllowed();
        // 5. assistant bubble MUST show the server's model answer, but only
        // for an explicit success. Any other result (ok:false, missing,
        // malformed, rejected, or ok:true with a blank answer) fails closed to
        // the generic Korean message so untrusted diagnostic/answer text never
        // reaches the citizen chat DOM.
        var isExplicitSuccess = result && result.ok === true;
        var normalizedAnswer = (
          isExplicitSuccess &&
          typeof result.answer === "string"
        )
          ? result.answer.trim()
          : "";

        // A non-empty answer is the only signal that the result is usable. A
        // blank (or missing/non-string) answer fails closed: no answer is
        // rendered and the action is degraded to "none" so no split or
        // choreography can start from an untrusted/blank success.
        var hasUsableMvpResult = Boolean(normalizedAnswer);

        var answer = hasUsableMvpResult
          ? normalizedAnswer
          : "현재 AI 안내를 연결하지 못했습니다.";
        var answerMessage = appendChatMessage("ai", answer);
        appendAnswerFreshness(answerMessage, result);
        // #1067: model or fail-closed answer is always semantic "answer".
        setJourneyState(JOURNEY_ANSWER);
        if (hasUsableMvpResult) {
          applyQuestRuntimeState(result);
        } else {
          clearQuestRuntimeState();
        }
        // 4. inspect action; only approved local actions move the clone. If a
        // usable MVP answer misses the action for the supported first question,
        // fall back to the existing deterministic local journey instead of
        // leaving the citizen-facing MVP stuck in chat-only mode.
        var action = resolveMvpActionForQuestion(question, result, hasUsableMvpResult);
        if (action === "illegal_parking") {
          beginMvpSplitThenChoreography(question, "illegal_parking");
        } else if (action === "housing_department") {
          beginMvpSplitThenChoreography(question, "housing_department");
        } else if (action === "bulky_waste") {
          beginMvpSplitThenChoreography(question, "bulky_waste");
        } else if (action === "passport_guidance") {
          beginMvpSplitThenChoreography(question, "passport_guidance");
        } else if (action === "unmanned_kiosk") {
          beginMvpSplitThenChoreography(question, "unmanned_kiosk");
        } else if (action === "streetlight_report") {
          beginMvpSplitThenChoreography(question, "streetlight_report");
        } else if (action === "litter_ai_assist") {
          beginMvpSplitThenChoreography(question, "litter_ai_assist");
        } else if (isMayorAction(action) || action === "mayor_message_assist") {
          // #1114: model-backed mayor action reuses the shared controller
          // (cursor-before-split when hero control is visible). User message
          // already echoed above; bridge already answered once.
          startMayorProposalEntry({
            source: "chat",
            skipUserMessage: true,
            useActionConfirm: true
          });
        } else if (action === "none") {
          // Keep the entry chat; do not move the clone or start a choreography.
          // Journey remains answer (set above).
        }
        // Any other value: treated as none (no split, no clone move).
      }).catch(function () {
        if (token !== _mvpRequestToken) return;
        setComposerDisabled(false);
        focusComposerIfAllowed();
        appendChatMessage("ai", "현재 AI 안내를 연결하지 못했습니다.");
        setJourneyState(JOURNEY_ANSWER);
      });
    });
  }

  function beginMvpSplitThenChoreography(question, action) {
    lastSplitQuestion = question;
    startCinematicSplit();
    scheduleSplitCompletion(function () {
      completeMvpSplit(action);
    });
  }

  function completeMvpSplit(action) {
    splitTimer = null;
    _pendingSplitComplete = null;
    setState(STATE_SPLIT);
    clearChatMotionStyles();
    fitOfficialCanvas();
    // Delay chat message slightly so the canvas fade-in is visible first.
    // #1132: reduced motion uses 0ms task boundary (confirm-run still after ack).
    window.setTimeout(function () {
      appendChatMessage(
        "ai",
        "질문을 확인했습니다. 왼쪽에 북구청 안내 화면을 열었습니다."
      );
      appendQuestProgressCard(chatThread);
      // Bridge answer already set answer; ack reinforces answer before confirm.
      setJourneyState(JOURNEY_ANSWER);
      // MVP confirm-run step: do NOT start the local choreography until the
      // citizen explicitly confirms. The confirm bubble shows the resolved
      // action's display name and only starts Choreography.start(action) when
      // the citizen presses [예, 안내해 주세요]. Pressing [아니요] keeps the
      // chat as-is and never starts the choreography.
      if (window.CitizenFirstChoreography && action) {
        showConfirmRunForAction(action);
      }
      focusComposerIfAllowed();
    }, splitAckDelayMs());
  }

  function resetToEntry() {
    // #1067: guard so choreography cancelled events during reset cannot map
    // to answer; final semantic state must be entry.
    _journeyResetting = true;
    // #1133: new flow — prior history entries become stale and non-restorable.
    beginNewHistoryFlow();
    _confirmGeneration++;
    // Invalidate any in-flight MVP response so a late answer cannot re-open the
    // clone or restart an action after the user reset.
    _mvpRequestToken++;
    clearQuestRuntimeState();
    if (window.CitizenMvpBridge && typeof window.CitizenMvpBridge.cancel === "function") {
      window.CitizenMvpBridge.cancel();
    }
    if (window.CitizenFirstChoreography) {
      window.CitizenFirstChoreography.cancel();
    }
    // Cancel any in-flight #1114 mayor cursor→split sequence.
    _clearMayorEntryTimers();
    if (window.CitizenActionDemoCanvas &&
        typeof window.CitizenActionDemoCanvas.hideCursor === "function") {
      window.CitizenActionDemoCanvas.hideCursor();
    }
    lastSplitQuestion = null;
    if (splitTimer !== null) {
      window.clearTimeout(splitTimer);
      splitTimer = null;
    }
    _pendingSplitComplete = null;
    clearChatMotionStyles();

    // Clear canvas content so split-state HTML isn't left behind
    if (canvas) {
      canvas.innerHTML = '<div class="demo-canvas__inner"><div class="demo-canvas__loading" aria-live="polite">북구청 안내 화면을 준비하는 중…</div></div>';
    }

    body.classList.add("first-use-shell--no-motion");
    // skipHistory: single replace after entry snapshot is fully ready.
    setState(STATE_ENTRY, { skipHistory: true });
    // #1067: explicit reset announces readiness; cold load does not.
    setJourneyState(JOURNEY_ENTRY, { announceReset: true, skipHistory: true });
    // Reset scroll position to top
    if (chatThread) {
      chatThread.scrollTop = 0;
    }
    renderEntryConversation();
    if (chatInput) {
      chatInput.value = "";
      // Only refocus on desktop; on mobile the surface switch owns
      // visibility and must NOT auto-focus the composer after reset.
      // setJourneyState / syncJourneyAccessibility never call .focus().
      // History restore path never reaches here.
      focusComposerIfAllowed();
    }
    _journeyResetting = false;
    // #1133: reset never pushState; replace current entry with new-flow entry.
    writeHistorySnapshot("replace", { force: true, dropJourneyQuery: true });
    window.requestAnimationFrame(function () {
      body.classList.remove("first-use-shell--no-motion");
    });
  }

  if (chatForm) {
    chatForm.addEventListener("submit", handleSubmission);
  }

  if (resetButton) {
    resetButton.addEventListener("click", resetToEntry);
  }

  // Mobile surface tabs: switch the active surface. State (chat, route,
  // prefilled values, confirmation, journey, cursor) is preserved because
  // the canonical chat DOM and canonical civic DOM are never cloned.
  function handleSurfaceTabClick(targetSurface) {
    if (!isMobileSurfaceMode()) {
      return;
    }
    if (targetSurface === "conversation") {
      setMobileSurface("conversation");
    } else if (targetSurface === "guidance") {
      setMobileSurface("guidance");
    } else {
      return;
    }
    // #1133: mobile surface-only changes replace the current history entry.
    writeHistorySnapshot("replace");
  }
  if (tabConversation) {
    tabConversation.addEventListener("click", function () {
      handleSurfaceTabClick("conversation");
    });
  }
  if (tabGuidance) {
    tabGuidance.addEventListener("click", function () {
      handleSurfaceTabClick("guidance");
    });
  }

  // #965: chip click → submit question
  if (chipsContainer) {
    chipsContainer.addEventListener("click", function (e) {
      var chip = e.target.closest("[data-chip-question]");
      if (!chip) return;
      var question = chip.getAttribute("data-chip-question");
      if (!question) return;
      if (chatInput) {
        chatInput.value = question;
      }
      // Trigger submission
      if (chatForm) {
        chatForm.dispatchEvent(new Event("submit", { cancelable: true }));
      }
    });
  }

  // #1114: hero "열린구청장실 바로가기" → same canonical controller.
  // Manual click is the activation; no automated second click / no bridge.
  var mayorControl = document.getElementById("mayor-open-office-control");
  if (mayorControl) {
    mayorControl.addEventListener("click", function (e) {
      e.preventDefault();
      startMayorProposalEntry({
        source: "hero",
        userInitiatedControlClick: true
      });
    });
  }

  // #1067: subscribe to choreography state events for semantic journey mapping.
  // Layout first-use-state remains independent of this axis.
  if (typeof window !== "undefined" && typeof window.addEventListener === "function") {
    window.addEventListener("citizen:choreography-statechange", _onChoreographyStateChange);
    // #1133: single popstate owner + canvas/choreography history contracts.
    if (!_historyPopListenerBound) {
      window.addEventListener("popstate", handleHistoryPopState);
      _historyPopListenerBound = true;
    }
    window.addEventListener("citizen:canvas-routechange", handleCanvasRouteChange);
    window.addEventListener("citizen:history-commit-request", handleHistoryCommitRequest);
  }

  // #1132: materialize motion preference before first paint consumers read it.
  setReducedMotionPreference(reducedMotion, { emit: false });
  if (reducedMotionQuery) {
    var _onReducedMotionMediaChange = function (event) {
      var matches = event && typeof event.matches === "boolean"
        ? event.matches
        : !!(reducedMotionQuery && reducedMotionQuery.matches);
      setReducedMotionPreference(matches);
    };
    if (typeof reducedMotionQuery.addEventListener === "function") {
      reducedMotionQuery.addEventListener("change", _onReducedMotionMediaChange);
    } else if (typeof reducedMotionQuery.addListener === "function") {
      reducedMotionQuery.addListener(_onReducedMotionMediaChange);
    }
  }

  // Init layout/journey without intermediate history writes; one replace below.
  if (isLegacyJourneyLoad()) {
    setState(STATE_SPLIT, { skipHistory: true });
    setJourneyState(JOURNEY_ENTRY, { skipHistory: true });
  } else {
    setState(STATE_ENTRY, { skipHistory: true });
    setJourneyState(JOURNEY_ENTRY, { skipHistory: true });
    renderEntryConversation();
  }
  // #1133: materialize exactly one shell-owned history entry (replace only).
  materializeInitialHistory();

  window.CitizenFirstUseShell = Object.freeze({
    getState: function () { return currentState; },
    getJourneyState: getJourneyState,
    getJourneyAccessibilityState: getJourneyAccessibilityState,
    // #1132: read-only motion preference (canonical owner).
    prefersReducedMotion: prefersReducedMotion,
    // #1133: read-only history diagnostic (no mutable setter).
    getHistoryState: getHistoryState,
    getQuestRuntimeResult: function () { return _questRuntimeResult; },
    isSupportedQuestion: isSupportedQuestion,
    renderQuestProgressCard: renderQuestProgressCard,
    appendQuestProgressCard: appendQuestProgressCard,
    reset: resetToEntry,
    // #1114 test/diagnostic surface — same controller used by chip/hero paths.
    startMayorProposalEntry: startMayorProposalEntry,
    mayorCanonicalQuestion: MAYOR_CANONICAL_QUESTION,
    mayorCanonicalAction: MAYOR_CANONICAL_ACTION,
    states: Object.freeze({
      entry: STATE_ENTRY,
      transitioning: STATE_TRANSITIONING,
      split: STATE_SPLIT
    }),
    // #1067: semantic journey axis (shared static + MVP + desktop + mobile).
    journeyStates: Object.freeze({
      entry: JOURNEY_ENTRY,
      answer: JOURNEY_ANSWER,
      confirm: JOURNEY_CONFIRM,
      navigate: JOURNEY_NAVIGATE,
      result: JOURNEY_RESULT
    })
  });
})();
