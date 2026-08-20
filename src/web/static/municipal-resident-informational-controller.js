/*
 * municipal-resident-informational-controller.js
 *
 * ONE SHARED INFORMATIONAL RESIDENT CONTROLLER (#1365).
 *
 * This is the single shared top-level orchestrator used by BOTH Buk-gu and
 * Seo-gu for the canonical resident informational confirm flow:
 *
 *   ANSWER (first answer + state)
 *   → CONFIRM (showConfirmRun → YES / NO)
 *   → YES: navigate + execute lower-level journey → result/stop
 *   → NO: stop on answer, zero execution
 *
 * It composes MunicipalResidentConfirmGate (which owns confirm UI + YES/NO
 * decision + stale-confirm generation guard + double-action protection).
 * The controller owns the answer→confirm scheduling (setAnswer + render +
 * schedule showConfirmRun) via a per-call renderAnswer callback. It does
 * NOT set journey-state or invalidate itself — those remain in the shell's
 * adapter hooks for exact timing preservation.
 *
 * Site shells (Buk-gu / Seo-gu) supply only:
 *   - the gate adapter (getThread, getInput, displayName, setJourneyState,
 *     isMobileSurfaceMode, yesButtonClassName/style, onYes, onNo, etc.)
 *   - a renderAnswer callback per startConfirmFlow call
 *   - the delay before showConfirmRun
 *
 * The controller is intentionally minimal: a thin coordinator that
 * centralizes the confirm-scheduling seam so both shells share ONE
 * canonical sequence owner without duplicating the scheduling logic.
 */

(function (root) {
  "use strict";

  function createInformationalController(gateAdapter) {
    var gate = root.MunicipalResidentConfirmGate.createConfirmGate(
      gateAdapter || {},
    );

    return Object.freeze({
      // Stale-confirm guard: shells call this to bump the generation before
      // rendering a new confirm-run, making prior YES/NO controls inert.
      invalidate: function () {
        gate.invalidate();
      },

      getGeneration: function () {
        return gate.getGeneration();
      },

      // Canonical answer→confirm scheduling.
      //   params.renderAnswer() — shell renders the answer bubble and may
      //     set ANSWER state. The controller does NOT set state itself;
      //     renderAnswer owns the ANSWER state transition for exact timing
      //     preservation per shell.
      //   params.question — the question string (passed to showConfirmRun).
      //   params.displayName — optional display name override.
      //   params.delay — ms before the confirm-run bubble appears (default 300).
      //
      // The controller's role is:
      //   1. renderAnswer() — shell renders the answer (ANSWER state).
      //   2. setTimeout → gate.showConfirmRun — canonical confirm bubble.
      //
      // This is the ONE canonical site for answer→confirm scheduling.
      // Shells must NOT duplicate this timing outside the controller.
      startConfirmFlow: function (params) {
        params = params && typeof params === "object" ? params : {};
        var delay =
          typeof params.delay === "number" ? params.delay : 300;
        var question =
          typeof params.question === "string" ? params.question : "";

        // 1. Render the answer (shell-owned: sets ANSWER + appends bubble).
        if (typeof params.renderAnswer === "function") {
          params.renderAnswer();
        }

        // 2. Schedule the canonical confirm-run bubble.
        //    onYes / onNo are wired at gate construction; per-call overrides
        //    are supported via opts (same as gate.showConfirmRun).
        setTimeout(function () {
          var opts = { question: question };
          if (typeof params.displayName === "string") {
            opts.displayName = params.displayName;
          }
          // Per-call onYes/onNo overrides (used by Buk-gu showConfirmRunForAction).
          if (typeof params.onYes === "function") {
            opts.onYes = params.onYes;
          }
          if (typeof params.onNo === "function") {
            opts.onNo = params.onNo;
          }
          gate.showConfirmRun(opts);
        }, delay);
      },

      // Direct passthrough for paths that render answer separately and
      // only need the confirm-run bubble (Buk-gu showConfirmRunForAction).
      showConfirmRun: function (opts) {
        gate.showConfirmRun(opts);
      },
    });
  }

  var api = Object.freeze({
    createInformationalController: createInformationalController,
  });

  if (typeof root !== "undefined") {
    root.MunicipalResidentInformationalController = api;
  }
  if (typeof module !== "undefined" && module.exports) {
    module.exports = api;
  }
})(typeof window !== "undefined" ? window : this);
