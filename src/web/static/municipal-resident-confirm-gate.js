/*
 * municipal-resident-confirm-gate.js
 *
 * ONE GOLDEN ENGINE for the resident confirmation lifecycle (#1365).
 *
 * This is the SINGLE canonical owner of the informational confirm-run state
 * machine shared by every municipality surface (Buk-gu golden master, Seo-gu,
 * and any future site). It owns:
 *
 *   ENTRY → ANSWER → CONFIRM → (YES | NO)
 *   YES → NAVIGATE → READ → RESULT / safe_handoff
 *   NO  → canonical answer/stop, zero navigation, zero READ
 *
 * plus reset, stale-confirm handling (generation counter) and double-action
 * protection (button disable + generation guard).
 *
 * Site shells (Buk-gu / Seo-gu) must NOT re-implement this lifecycle. They
 * supply only an adapter of surface-specific hooks (thread, input, display
 * name, journey-state mapping, mobile surface, YES/NO continuation). The gate
 * renders the canonical confirm-run bubble and owns the decision transition.
 *
 * A chip click is NEVER confirmation — the shell shows the answer first, then
 * calls showConfirmRun for an explicit YES/NO decision.
 */

(function (root) {
  "use strict";

  var CONFIRM_PROMPT_SUFFIX = "에 대해 안내해 드릴까요?";

  function _defaultConfirmPrompt() {
    return CONFIRM_PROMPT_SUFFIX;
  }

  function createConfirmGate(adapter) {
    adapter = adapter && typeof adapter === "object" ? adapter : {};

    // Single generation counter — the canonical stale-confirm guard. Every
    // showConfirmRun captures the current generation; invalidate() bumps it so
    // any previously rendered confirm-run YES/NO controls become inert.
    var generation = 0;

    function invalidate() {
      generation += 1;
    }

    function getGeneration() {
      return generation;
    }

    function getThread() {
      return typeof adapter.getThread === "function" ? adapter.getThread() : null;
    }

    function getInput() {
      return typeof adapter.getInput === "function" ? adapter.getInput() : null;
    }

    function resolveDisplayName(question, override) {
      if (typeof override === "string" && override.length) return override;
      if (typeof adapter.displayName === "function") {
        var d = adapter.displayName(question);
        if (d) return d;
      }
      return question || "이 안내";
    }

    function localize(key, fallback) {
      if (typeof adapter.localize === "function") {
        var v = adapter.localize(key, fallback);
        if (v != null && v !== undefined) return v;
      }
      return fallback;
    }

    function confirmPrompt() {
      if (typeof adapter.confirmPrompt === "function") {
        var p = adapter.confirmPrompt();
        if (p) return p;
      }
      return _defaultConfirmPrompt();
    }

    function isMobileSurfaceMode() {
      if (typeof adapter.isMobileSurfaceMode === "function") {
        return !!adapter.isMobileSurfaceMode();
      }
      try {
        return !!root.matchMedia && root.matchMedia("(max-width: 767px)").matches;
      } catch (_) {
        return false;
      }
    }

    function applyJourneyState(state) {
      if (typeof adapter.setJourneyState === "function") adapter.setJourneyState(state);
    }

    function scrollToLatest(msgDiv) {
      if (typeof adapter.scrollToLatest === "function") {
        try {
          adapter.scrollToLatest(msgDiv);
          return;
        } catch (_) {
          /* fall through to default append */
        }
      }
      var t = getThread();
      if (t && msgDiv && typeof t.appendChild === "function") {
        t.appendChild(msgDiv);
        t.scrollTop = t.scrollHeight;
      }
    }

    function showConfirmRun(opts) {
      opts = opts && typeof opts === "object" ? opts : {};
      var thread = getThread();
      if (!thread) return;

      var question = typeof opts.question === "string" ? opts.question : "";
      var displayName = resolveDisplayName(question, opts.displayName);
      var gen = generation;

      var yesBtnClass =
        typeof adapter.yesButtonClassName === "string" && adapter.yesButtonClassName.length
          ? adapter.yesButtonClassName
          : "chat-decision__button chat-decision__button--primary";
      var noBtnClass =
        typeof adapter.noButtonClassName === "string" && adapter.noButtonClassName.length
          ? adapter.noButtonClassName
          : "chat-decision__button chat-decision__button--secondary";
      var yesBtnStyle = typeof adapter.yesButtonStyle === "string" ? adapter.yesButtonStyle : "";
      var noBtnStyle = typeof adapter.noButtonStyle === "string" ? adapter.noButtonStyle : "";

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
      text.textContent = displayName + confirmPrompt();
      bubble.appendChild(text);

      var btnRow = document.createElement("div");
      btnRow.style.display = "flex";
      btnRow.style.gap = "8px";

      var yesBtn = document.createElement("button");
      yesBtn.type = "button";
      yesBtn.className = yesBtnClass;
      if (yesBtnStyle) yesBtn.style.cssText = yesBtnStyle;
      yesBtn.textContent = localize("action.yesGuide", "예, 안내해 주세요");
      yesBtn.setAttribute("data-confirm-action", "yes");
      yesBtn.addEventListener("click", function () {
        // Stale-confirm guard: a newer confirm-run (or reset) invalidated this one.
        if (gen !== generation) return;
        msgDiv.removeAttribute("data-msg-type");
        var btns = bubble.querySelectorAll("button");
        for (var i = 0; i < btns.length; i += 1) btns[i].disabled = true;
        // Double-action protection: surface prep (mobile switch / canvas reveal)
        // then the only allowed transition trigger.
        if (typeof adapter.onYesSurfacePrepare === "function") {
          adapter.onYesSurfacePrepare(question);
        }
        if (typeof opts.onYes === "function") {
          opts.onYes(question);
        } else if (typeof adapter.onYes === "function") {
          adapter.onYes(question);
        }
      });

      var noBtn = document.createElement("button");
      noBtn.type = "button";
      noBtn.className = noBtnClass;
      if (noBtnStyle) noBtn.style.cssText = noBtnStyle;
      noBtn.textContent = localize("action.no", "아니요");
      noBtn.setAttribute("data-confirm-action", "no");
      noBtn.addEventListener("click", function () {
        if (gen !== generation) return;
        msgDiv.removeAttribute("data-msg-type");
        var btns = bubble.querySelectorAll("button");
        for (var i = 0; i < btns.length; i += 1) btns[i].disabled = true;
        // NO: stay on the answered state — zero navigation, zero READ, zero handoff.
        applyJourneyState("answer");
        if (typeof opts.onNo === "function") {
          opts.onNo();
        } else if (typeof adapter.onNo === "function") {
          adapter.onNo();
        }
      });

      btnRow.appendChild(yesBtn);
      btnRow.appendChild(noBtn);
      bubble.appendChild(btnRow);

      msgDiv.appendChild(avatar);
      msgDiv.appendChild(bubble);

      scrollToLatest(msgDiv);

      // Confirm-run bubble shown — wait for the resident's explicit decision.
      applyJourneyState("confirm");
    }

    return Object.freeze({
      showConfirmRun: showConfirmRun,
      invalidate: invalidate,
      getGeneration: getGeneration,
    });
  }

  var api = Object.freeze({
    createConfirmGate: createConfirmGate,
    CONFIRM_PROMPT_SUFFIX: CONFIRM_PROMPT_SUFFIX,
  });

  if (typeof root !== "undefined") {
    root.MunicipalResidentConfirmGate = api;
  }
  if (typeof module !== "undefined" && module.exports) {
    module.exports = api;
  }
})(typeof window !== "undefined" ? window : this);
