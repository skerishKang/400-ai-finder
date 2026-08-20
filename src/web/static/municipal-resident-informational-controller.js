/*
 * municipal-resident-informational-controller.js
 *
 * ONE SHARED INFORMATIONAL RESIDENT CONTROLLER (#1365).
 *
 * This is the single shared top-level owner for the canonical informational
 * resident lifecycle used by Buk-gu and Seo-gu:
 *
 *   ANSWER → CONFIRM → NO: ANSWER/STOP
 *                    → YES: NAVIGATE → EXECUTE → RESULT / SAFE STOP
 *
 * MunicipalResidentConfirmGate owns the confirm UI, YES/NO decision seam,
 * stale-generation guard and control deactivation. This controller owns when
 * those decisions advance the resident lifecycle. Site adapters may supply
 * data, evidence/surface operations and rendering callbacks, but they must not
 * own the top-level progression policy.
 */

(function (root) {
  "use strict";

  function createInformationalController(adapter) {
    adapter = adapter && typeof adapter === "object" ? adapter : {};

    var activeFlow = null;
    var flowGeneration = 0;

    function setJourneyState(state) {
      if (typeof adapter.setJourneyState === "function") {
        adapter.setJourneyState(state);
      }
    }

    function setInteractionDisabled(disabled) {
      if (typeof adapter.setInteractionDisabled === "function") {
        adapter.setInteractionDisabled(!!disabled);
      }
    }

    function focusInput() {
      if (typeof adapter.focusInput === "function") {
        adapter.focusInput();
      }
    }

    function prepareExecution(flow) {
      if (typeof adapter.prepareExecution === "function") {
        adapter.prepareExecution(flow);
      }
    }

    function renderUnexpectedFailure(error, flow) {
      if (typeof adapter.renderUnexpectedFailure === "function") {
        adapter.renderUnexpectedFailure(error, flow);
      }
    }

    function createFlow(params) {
      params = params && typeof params === "object" ? params : {};
      flowGeneration += 1;
      var flow = {
        generation: flowGeneration,
        question: typeof params.question === "string" ? params.question : "",
        displayName:
          typeof params.displayName === "string" ? params.displayName : undefined,
        journey:
          params.journey && typeof params.journey === "object"
            ? params.journey
            : null,
        executeConfirmed:
          typeof params.executeConfirmed === "function"
            ? params.executeConfirmed
            : typeof params.onYes === "function"
              ? params.onYes
              : null,
        renderAnswer:
          typeof params.renderAnswer === "function" ? params.renderAnswer : null,
        delay: typeof params.delay === "number" ? params.delay : 300,
        handoffTimeoutMs:
          typeof params.handoffTimeoutMs === "number"
            ? params.handoffTimeoutMs
            : 8000,
        decisionConsumed: false,
      };
      activeFlow = flow;
      return flow;
    }

    function isCurrentFlow(flow) {
      return Boolean(
        flow &&
        activeFlow === flow &&
        flow.generation === flowGeneration
      );
    }

    function consumeFlow() {
      var flow = activeFlow;
      if (!flow || flow.decisionConsumed) return null;
      flow.decisionConsumed = true;
      activeFlow = null;
      return flow;
    }

    function readEvidence() {
      if (typeof adapter.readEvidence === "function") {
        return adapter.readEvidence();
      }
      return null;
    }

    function waitForEvidence(route, timeoutMs) {
      return new Promise(function (resolve) {
        var deadline = Date.now() + (timeoutMs || 8000);
        function check() {
          var evidence = readEvidence();
          if (evidence && evidence.ok && evidence.route === route) {
            resolve(evidence);
            return;
          }
          if (Date.now() >= deadline) {
            resolve(evidence || null);
            return;
          }
          setTimeout(check, 25);
        }
        check();
      });
    }

    async function runHandoff(flow) {
      var journey = flow.journey || {};
      var handoff = journey.handoff || {};

      setJourneyState("handoff_evidence_running");

      var navigated = false;
      if (
        handoff.local_evidence_route &&
        typeof adapter.navigate === "function"
      ) {
        navigated = !!adapter.navigate(handoff.local_evidence_route);
      }

      var evidence = null;
      if (navigated) {
        evidence = await waitForEvidence(
          handoff.local_evidence_route,
          flow.handoffTimeoutMs,
        );
      }

      if (typeof adapter.setEvidence === "function") {
        adapter.setEvidence(evidence, flow);
      }

      var evidenceText =
        evidence && evidence.ok ? String(evidence.text || "") : "";
      var missingMarkers = (handoff.required_markers || []).filter(function (marker) {
        return evidenceText.indexOf(marker) === -1;
      });

      if (typeof adapter.renderHandoffEvidence === "function") {
        adapter.renderHandoffEvidence(
          journey,
          handoff,
          evidence,
          missingMarkers,
          flow,
        );
      }

      var evidenceGatePassed =
        Boolean(evidence) && evidence.ok === true && missingMarkers.length === 0;

      if (evidenceGatePassed) {
        if (typeof adapter.renderHandoffDestination === "function") {
          adapter.renderHandoffDestination(journey, handoff, flow);
        }
        setJourneyState("safe_handoff");
        return {
          ok: true,
          safe_stop: true,
          evidence: evidence,
          missing_markers: [],
        };
      }

      if (typeof adapter.renderHandoffBlocked === "function") {
        adapter.renderHandoffBlocked(journey, handoff, flow);
      }
      setJourneyState("handoff_evidence_failed");
      return {
        ok: false,
        safe_stop: true,
        evidence: evidence,
        missing_markers: missingMarkers,
      };
    }

    async function runManagedJourney(flow) {
      var journey = flow.journey;

      if (journey && journey.handoff) {
        return runHandoff(flow);
      }

      if (typeof adapter.runJourney !== "function") {
        throw new Error("informational resident adapter missing runJourney");
      }

      setJourneyState("running");
      var result = await adapter.runJourney(journey, flow);

      if (typeof adapter.setJourneyResult === "function") {
        adapter.setJourneyResult(result, flow);
      }

      if (result && result.ok && result.grounded) {
        setJourneyState("grounded");
        if (typeof adapter.renderGroundedResult === "function") {
          adapter.renderGroundedResult(result, journey, flow);
        }
      } else {
        setJourneyState("failed");
        if (typeof adapter.renderJourneyFailure === "function") {
          adapter.renderJourneyFailure(result, journey, flow);
        }
      }
      return result;
    }

    function runConfirmedFlow(question) {
      var flow = consumeFlow();
      if (!flow) return;

      // The shared controller, not a site shell, owns the canonical YES
      // continuation and the transition into execution.
      setInteractionDisabled(true);
      setJourneyState("navigate");
      prepareExecution(flow);

      var task;
      try {
        if (flow.journey) {
          task = runManagedJourney(flow);
        } else {
          var execute =
            flow.executeConfirmed ||
            (typeof adapter.executeConfirmed === "function"
              ? adapter.executeConfirmed
              : typeof adapter.onYes === "function"
                ? adapter.onYes
                : null);
          task = typeof execute === "function"
            ? execute(question, flow)
            : undefined;
        }
      } catch (error) {
        task = Promise.reject(error);
      }

      Promise.resolve(task)
        .catch(function (error) {
          if (flow.journey) {
            if (typeof adapter.clearExecutionResult === "function") {
              adapter.clearExecutionResult(flow);
            }
            setJourneyState("failed");
          }
          renderUnexpectedFailure(error, flow);
        })
        .finally(function () {
          setInteractionDisabled(false);
          focusInput();
        });
    }

    function stopAfterNo() {
      var flow = consumeFlow();
      if (!flow) return;
      if (typeof adapter.onNo === "function") {
        adapter.onNo(flow);
      }
      focusInput();
    }

    // Build the gate with controller-owned decision callbacks. Surface-only
    // preparation remains an adapter hook, but YES/NO progression never returns
    // to a site-owned top-level state machine.
    var gateAdapter = {};
    Object.keys(adapter).forEach(function (key) {
      if (key !== "onYes" && key !== "onNo") {
        gateAdapter[key] = adapter[key];
      }
    });
    gateAdapter.onYes = runConfirmedFlow;
    gateAdapter.onNo = stopAfterNo;

    var gate = root.MunicipalResidentConfirmGate.createConfirmGate(gateAdapter);

    function invalidate() {
      flowGeneration += 1;
      activeFlow = null;
      gate.invalidate();
    }

    function showFlowConfirm(flow) {
      if (!isCurrentFlow(flow)) return;
      var opts = { question: flow.question };
      if (typeof flow.displayName === "string") {
        opts.displayName = flow.displayName;
      }
      gate.showConfirmRun(opts);
    }

    function startConfirmFlow(params) {
      var flow = createFlow(params);

      // Shared owner of ANSWER transition. The site callback only renders the
      // municipality-specific answer surface/copy.
      setJourneyState("answer");
      if (flow.renderAnswer) {
        flow.renderAnswer();
      }

      setTimeout(function () {
        showFlowConfirm(flow);
      }, flow.delay);
    }

    function showConfirmRun(opts) {
      // Buk-gu already renders its first answer before calling this method.
      // Register the same controller-owned YES/NO continuation and show the
      // shared gate immediately; this is no longer a raw gate passthrough.
      var flow = createFlow(opts);
      showFlowConfirm(flow);
    }

    return Object.freeze({
      invalidate: invalidate,
      getGeneration: function () {
        return gate.getGeneration();
      },
      startConfirmFlow: startConfirmFlow,
      showConfirmRun: showConfirmRun,
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
