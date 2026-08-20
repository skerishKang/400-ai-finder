/*
 * municipal-resident-informational-controller.js
 *
 * ONE SHARED INFORMATIONAL RESIDENT BEHAVIOR ENGINE (#1365/#1366).
 *
 * Single shared top-level orchestrator for informational resident journeys
 * across all municipality surfaces (Buk-gu Golden Master, Seo-gu, and future sites).
 *
 * CANONICAL TOP-LEVEL LIFECYCLE OWNERSHIP:
 *
 *   ANSWER (initial answer / split state)
 *   → CONFIRM (showConfirmRun → YES / NO)
 *   → NO: canonical stop on answer, zero navigation, zero READ, zero handoff
 *   → YES: NAVIGATE / RUNNING
 *          → grounded clone journey (S1, S5, S6) → GROUNDED / FAILED
 *          → external official handoff (S2, S7, S8) → SAFE_HANDOFF / HANDOFF_EVIDENCE_FAILED
 *          → site choreography execution (Buk-gu Golden Master)
 *          → failure handling
 *
 * Composes MunicipalResidentConfirmGate for confirm UI, YES/NO decision,
 * stale-confirm generation guard, and double-action protection.
 *
 * Site shells (Buk-gu / Seo-gu) supply only thin adapters:
 *   - DOM / UI element access (thread, input, send, surface)
 *   - rendering callbacks (renderAnswer, renderGroundedResult, renderHandoffEvidence, etc.)
 *   - display name / localization
 *   - site-specific preparation hooks (onYesSurfacePrepare, onNo)
 */

(function (root) {
  "use strict";

  function createInformationalController(adapter) {
    adapter = adapter && typeof adapter === "object" ? adapter : {};

    var latestJourneyResult = null;
    var latestEvidence = null;

    function setJourneyState(state) {
      if (typeof adapter.setJourneyState === "function") {
        adapter.setJourneyState(state);
      }
    }

    function setComposerDisabled(disabled) {
      if (typeof adapter.setComposerDisabled === "function") {
        adapter.setComposerDisabled(disabled);
        return;
      }
      var input = typeof adapter.getInput === "function" ? adapter.getInput() : null;
      var send = typeof adapter.getSend === "function" ? adapter.getSend() : null;
      if (input) input.disabled = !!disabled;
      if (send) send.disabled = !!disabled;
    }

    function focusComposer() {
      if (typeof adapter.focusComposer === "function") {
        adapter.focusComposer();
        return;
      }
      var input = typeof adapter.getInput === "function" ? adapter.getInput() : null;
      if (input && typeof input.focus === "function") {
        try {
          input.focus();
        } catch (_) {}
      }
    }

    // Gate adapter with controller-level state hooks
    var gateAdapter = Object.assign({}, adapter, {
      setJourneyState: function (state) {
        setJourneyState(state);
      },
    });

    var gate = root.MunicipalResidentConfirmGate.createConfirmGate(gateAdapter);

    function invalidate() {
      gate.invalidate();
      latestJourneyResult = null;
    }

    function getGeneration() {
      return gate.getGeneration();
    }

    // Shared bounded READ polling for clone evidence (25ms poll contract)
    function waitForEvidence(surface, route, timeoutMs) {
      if (typeof adapter.waitForEvidence === "function") {
        return adapter.waitForEvidence(route, timeoutMs);
      }
      var limit = typeof timeoutMs === "number" ? timeoutMs : 8000;
      return new Promise(function (resolve) {
        var deadline = Date.now() + limit;
        function check() {
          var ev = surface && typeof surface.readEvidence === "function"
            ? surface.readEvidence()
            : null;
          if (ev && ev.ok && ev.route === route) {
            resolve(ev);
            return;
          }
          if (Date.now() >= deadline) {
            resolve(ev || null);
            return;
          }
          setTimeout(check, 25);
        }
        check();
      });
    }

    // Shared external official handoff runner (local evidence first -> fail-closed decision)
    async function runHandoff(params) {
      params = params && typeof params === "object" ? params : {};
      var journey = params.journey || {};
      var handoff = journey.handoff || {};
      var surface = params.surface || (typeof adapter.getSurface === "function" ? adapter.getSurface() : null);

      setJourneyState("handoff_evidence_running");

      // 1. Bounded navigation to repository-controlled local evidence route
      var navigated = false;
      if (surface && handoff.local_evidence_route && typeof surface.navigate === "function") {
        navigated = surface.navigate(handoff.local_evidence_route);
      }

      // 2. Bounded clone READ evidence wait
      var evidence = null;
      if (navigated) {
        evidence = await waitForEvidence(surface, handoff.local_evidence_route, params.timeoutMs);
      }
      if (evidence && evidence.ok) {
        latestEvidence = evidence;
        if (typeof adapter.onEvidence === "function") {
          adapter.onEvidence(evidence);
        }
      }

      // 3. Required-marker validation
      var evidenceText = evidence && evidence.ok ? String(evidence.text || "") : "";
      var required = Array.isArray(handoff.required_markers) ? handoff.required_markers : [];
      var missingMarkers = required.filter(function (m) {
        return evidenceText.indexOf(m) === -1;
      });

      // 4. Render handoff evidence row (explain verified vs unverified scope)
      if (typeof adapter.renderHandoffEvidence === "function") {
        adapter.renderHandoffEvidence(journey, handoff, evidence, missingMarkers);
      }

      // 5. Fail-closed evidence gate
      var gatePassed = Boolean(evidence) && evidence.ok === true && missingMarkers.length === 0;
      if (gatePassed) {
        // Explicit resident-activated official handoff, then STOP
        setJourneyState("safe_handoff");
        if (typeof adapter.renderHandoffDestination === "function") {
          adapter.renderHandoffDestination(journey, handoff);
        }
      } else {
        // Fail-closed STOP with no actionable external destination
        setJourneyState("handoff_evidence_failed");
        if (typeof adapter.renderHandoffBlocked === "function") {
          adapter.renderHandoffBlocked(journey, handoff);
        }
      }
    }

    // Shared grounded clone journey runner (MunicipalResidentJourney orchestration)
    async function runGroundedJourney(params) {
      params = params && typeof params === "object" ? params : {};
      var journey = params.journey || {};
      var surface = params.surface || (typeof adapter.getSurface === "function" ? adapter.getSurface() : null);

      if (!surface || !root.MunicipalResidentJourney || typeof root.MunicipalResidentJourney.run !== "function") {
        setJourneyState("failed");
        if (typeof adapter.renderGroundedFailure === "function") {
          adapter.renderGroundedFailure(null, journey);
        }
        return;
      }

      setJourneyState("running");
      var result = await root.MunicipalResidentJourney.run(journey, surface, { timeout_ms: params.timeoutMs });
      latestJourneyResult = result;
      if (typeof adapter.onJourneyResult === "function") {
        adapter.onJourneyResult(result);
      }

      if (result && result.ok && result.grounded) {
        setJourneyState("grounded");
        if (typeof adapter.renderGroundedResult === "function") {
          adapter.renderGroundedResult(result, journey);
        }
      } else {
        setJourneyState("failed");
        if (typeof adapter.renderGroundedFailure === "function") {
          adapter.renderGroundedFailure(result, journey);
        }
      }
    }

    // Shared top-level YES execution continuation
    async function executeYesContinuation(params) {
      params = params && typeof params === "object" ? params : {};
      setComposerDisabled(true);
      setJourneyState("navigate");

      try {
        if (typeof params.execute === "function") {
          await params.execute(params.question, params.journey);
        } else if (params.journey && params.journey.handoff) {
          await runHandoff(params);
        } else if (params.journey && (params.journey.entry_route || params.journey.evidence_route)) {
          await runGroundedJourney(params);
        } else if (typeof adapter.executeAction === "function") {
          await adapter.executeAction(params.question, params.journey);
        } else if (typeof adapter.onYes === "function") {
          await adapter.onYes(params.question, params.journey);
        }
      } catch (err) {
        latestJourneyResult = null;
        if (typeof adapter.onJourneyResult === "function") {
          adapter.onJourneyResult(null);
        }
        setJourneyState("failed");
        if (typeof adapter.renderError === "function") {
          adapter.renderError(err, params.question);
        }
      } finally {
        setComposerDisabled(false);
        focusComposer();
        if (typeof adapter.onExecutionComplete === "function") {
          adapter.onExecutionComplete();
        }
      }
    }

    // Canonical top-level answer -> confirm -> YES/NO flow
    function startConfirmFlow(params) {
      params = params && typeof params === "object" ? params : {};
      var delay = typeof params.delay === "number" ? params.delay : 300;
      var question = typeof params.question === "string" ? params.question : "";
      var displayName = typeof params.displayName === "string" ? params.displayName : undefined;

      // 1. Render answer (ANSWER state)
      if (typeof params.renderAnswer === "function") {
        params.renderAnswer();
      } else if (typeof adapter.renderAnswer === "function") {
        adapter.renderAnswer(question, params.journey);
      }
      setJourneyState("answer");

      // 2. Schedule canonical confirm bubble
      setTimeout(function () {
        var opts = {
          question: question,
          onYes: function (q) {
            executeYesContinuation({
              question: q,
              journey: params.journey,
              surface: params.surface,
              execute: params.execute,
              timeoutMs: params.timeoutMs,
            });
          },
          onNo: function () {
            setJourneyState("answer");
            if (typeof params.onNo === "function") {
              params.onNo();
            } else if (typeof adapter.onNo === "function") {
              adapter.onNo();
            }
            focusComposer();
          },
        };
        if (typeof displayName === "string") {
          opts.displayName = displayName;
        }
        gate.showConfirmRun(opts);
      }, delay);
    }

    function showConfirmRun(opts) {
      opts = opts && typeof opts === "object" ? opts : {};
      var originalOnYes = opts.onYes;
      var originalOnNo = opts.onNo;

      var wrappedOpts = Object.assign({}, opts, {
        onYes: function (q) {
          if (typeof originalOnYes === "function") {
            executeYesContinuation({
              question: q,
              execute: originalOnYes,
            });
          } else if (typeof adapter.executeAction === "function") {
            executeYesContinuation({
              question: q,
              execute: function (question) { return adapter.executeAction(question); },
            });
          } else if (typeof adapter.onYes === "function") {
            executeYesContinuation({
              question: q,
              execute: function (question) { return adapter.onYes(question); },
            });
          }
        },
        onNo: function () {
          setJourneyState("answer");
          if (typeof originalOnNo === "function") {
            originalOnNo();
          } else if (typeof adapter.onNo === "function") {
            adapter.onNo();
          }
          focusComposer();
        },
      });

      gate.showConfirmRun(wrappedOpts);
    }

    return Object.freeze({
      invalidate: invalidate,
      getGeneration: getGeneration,
      startConfirmFlow: startConfirmFlow,
      showConfirmRun: showConfirmRun,
      runHandoff: runHandoff,
      runGroundedJourney: runGroundedJourney,
      executeYesContinuation: executeYesContinuation,
      getLastJourneyResult: function () { return latestJourneyResult; },
      getLastEvidence: function () { return latestEvidence; },
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
