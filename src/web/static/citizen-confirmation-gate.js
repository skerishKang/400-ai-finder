/*
 * citizen-confirmation-gate.js
 * Shared canonical resident confirmation gate (#1365 / #1366 / #1367).
 *
 * ONE_CANONICAL_RESIDENT_ENGINE: this module owns the answer→confirm→YES/NO
 * progression and the data-journey-state axis. Site-specific code must NOT
 * implement its own confirmation state machine.
 *
 * Buk-gu and Seo-gu both delegate to this implementation via an adapter:
 *
 *   var gate = CitizenConfirmationGate.create({
 *     thread: <DOMElement>,
 *     setJourneyState: function(state) { ... },
 *     onConfirm: function(question) { ... },       // YES → start navigation/choreography
 *     onDecline: function() { ... },               // NO → stay on answer
 *     getDisplayName: function(question) { ... },   // site-specific label resolution
 *     isMobile: function() { ... },                 // mobile detection
 *     onMobileSurface: function(surface) { ... },   // set mobile surface
 *     focusComposer: function() { ... },            // restore composer focus
 *   });
 *
 * The gate exposes:
 *   gate.invalidate()         — cancel any in-flight confirmation (stale protection)
 *   gate.showConfirmRun(question) — render the answer→confirm→YES/NO sequence
 *
 * The caller is responsible for showing the first answer message BEFORE
 * calling showConfirmRun, and for setting data-journey-state="answer" before
 * the gate transitions to "confirm".
 *
 * Privacy/safety guarantees:
 * - No localStorage, sessionStorage, cookies, fetch, XHR, WebSocket, analytics.
 * - No provider import, no external URLs, no DOM automation beyond the chat thread.
 * - All content is local — no personal data collection.
 */
(function () {
  "use strict";

  var JOURNEY_ANSWER = "answer";
  var JOURNEY_CONFIRM = "confirm";
  var JOURNEY_NAVIGATE = "navigate";

  function create(config) {
    if (!config || typeof config !== "object") {
      throw new Error("CitizenConfirmationGate.create requires a config object");
    }
    if (!config.thread || typeof config.setJourneyState !== "function") {
      throw new Error("CitizenConfirmationGate.create requires thread and setJourneyState");
    }

    var _generation = 0;

    function _invalidate() {
      _generation += 1;
    }

    function _showConfirmRun(question) {
      var gen = _generation;
      var thread = config.thread;

      var displayName = typeof config.getDisplayName === "function"
        ? config.getDisplayName(question)
        : question;

      var msgDiv = document.createElement("div");
      msgDiv.className = "chat-msg chat-msg--ai chat-msg--confirm-run";
      msgDiv.setAttribute("data-msg-type", "confirm-run");

      var avatar = document.createElement("div");
      avatar.className = "chat-avatar";
      avatar.setAttribute("aria-hidden", "true");
      avatar.textContent = "A";

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
      yesBtn.className = "chat-decision__button chat-decision__button--primary";
      yesBtn.textContent = "예, 안내해 주세요";
      yesBtn.setAttribute("data-confirm-action", "yes");
      yesBtn.addEventListener("click", function () {
        if (gen !== _generation) return;
        msgDiv.removeAttribute("data-msg-type");
        var btns = bubble.querySelectorAll("button");
        for (var i = 0; i < btns.length; i++) btns[i].disabled = true;

        // Mobile: switch to guidance surface before navigation starts.
        if (typeof config.isMobile === "function" && config.isMobile()) {
          if (typeof config.onMobileSurface === "function") {
            config.onMobileSurface("guidance");
          }
        }
        config.setJourneyState(JOURNEY_NAVIGATE);

        // YES is the ONLY transition trigger for navigation/choreography.
        if (typeof config.onConfirm === "function") {
          config.onConfirm(question);
        }
      });

      var noBtn = document.createElement("button");
      noBtn.type = "button";
      noBtn.className = "chat-decision__button chat-decision__button--secondary";
      noBtn.textContent = "아니요";
      noBtn.setAttribute("data-confirm-action", "no");
      noBtn.addEventListener("click", function () {
        if (gen !== _generation) return;
        msgDiv.removeAttribute("data-msg-type");
        var btns = bubble.querySelectorAll("button");
        for (var i = 0; i < btns.length; i++) btns[i].disabled = true;

        // NO = zero navigation, zero READ, stay on answer.
        config.setJourneyState(JOURNEY_ANSWER);
        if (typeof config.focusComposer === "function") {
          config.focusComposer();
        }
      });

      btnRow.appendChild(yesBtn);
      btnRow.appendChild(noBtn);
      bubble.appendChild(btnRow);

      msgDiv.appendChild(avatar);
      msgDiv.appendChild(bubble);
      thread.appendChild(msgDiv);
      thread.scrollTop = thread.scrollHeight;

      // Confirm-run bubble shown — wait for resident decision.
      config.setJourneyState(JOURNEY_CONFIRM);
    }

    return Object.freeze({
      invalidate: _invalidate,
      showConfirmRun: _showConfirmRun,
    });
  }

  window.CitizenConfirmationGate = Object.freeze({
    create: create,
    STATES: Object.freeze({
      ANSWER: JOURNEY_ANSWER,
      CONFIRM: JOURNEY_CONFIRM,
      NAVIGATE: JOURNEY_NAVIGATE,
    }),
  });
})();
