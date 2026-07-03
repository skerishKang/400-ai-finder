"""
Tests for citizen-action-executor — Stage #848.

Fake click event harness repair. Validates that the test helper
correctly provides `closest()` and `matches()` on mock targets,
so that Stage #847 canvas delegation does nothing on confirmation buttons.
"""

import subprocess


# ---------------------------------------------------------------------------
# Node harness: makeFixedControlTarget + dispatchFixedControlClick
# ---------------------------------------------------------------------------

_HARNESS = r"""
'use strict';
var vm = require('vm');

// ---------------------------------------------------------------------------
// Fake DOM helpers
// ---------------------------------------------------------------------------
function makeFixedControlTarget(id) {
  return {
    id: id,
    getAttribute: function (name) {
      return name === "id" ? id : null;
    },
    closest: function (selector) {
      if (selector === "#btn-confirm-approve" && id === "btn-confirm-approve") {
        return this;
      }
      if (selector === "#btn-confirm-cancel" && id === "btn-confirm-cancel") {
        return this;
      }
      return null;
    },
    matches: function (selector) {
      return this.closest(selector) === this;
    }
  };
}

function dispatchFixedControlClick(id) {
  var event = {
    target: makeFixedControlTarget(id),
    currentTarget: sandbox.document,
    defaultPrevented: false,
    preventDefault: function () {
      this.defaultPrevented = true;
    },
    stopPropagation: function () {}
  };

  (sandbox._listeners || []).forEach(function (listener) {
    if (listener.e === "click") {
      listener.h(event);
    }
  });
}

// ---------------------------------------------------------------------------
// Sandbox context (required by dispatchFixedControlClick)
// ---------------------------------------------------------------------------
var sandbox = {
  document: {},
  _listeners: []
};

// ---------------------------------------------------------------------------
// Test assertions
// ---------------------------------------------------------------------------
var passed = 0;
var failed = 0;

function assert(condition, message) {
  if (condition) {
    passed++;
  } else {
    failed++;
    console.error("FAIL: " + message);
  }
}

// ---------------------------------------------------------------------------
// Test: makeFixedControlTarget has closest()
// ---------------------------------------------------------------------------
(function() {
  var target = makeFixedControlTarget("btn-confirm-approve");
  assert(typeof target.closest === "function", "makeFixedControlTarget: has closest()");
  assert(target.closest("#btn-confirm-approve") === target,
         "closest('#btn-confirm-approve') returns self for approve button");
  assert(target.closest("#btn-confirm-cancel") === null,
         "closest('#btn-confirm-cancel') returns null for approve button");
  assert(target.closest("[data-action-target]") === null,
         "closest('[data-action-target]') returns null — Stage #847 delegation must NOT fire");
  assert(target.closest("#btn-confirm-approve") !== null,
         "closest returns non-null for own id");
})();

// ---------------------------------------------------------------------------
// Test: makeFixedControlTarget has matches()
// ---------------------------------------------------------------------------
(function() {
  var target = makeFixedControlTarget("btn-confirm-cancel");
  assert(typeof target.matches === "function", "makeFixedControlTarget: has matches()");
  assert(target.matches("#btn-confirm-cancel") === true,
         "matches('#btn-confirm-cancel') is true for cancel button");
  assert(target.matches("#btn-confirm-approve") === false,
         "matches('#btn-confirm-approve') is false for cancel button");
  assert(target.matches("[data-action-target]") === false,
         "matches('[data-action-target]') is false — no data-action-target attribute");
})();

// ---------------------------------------------------------------------------
// Test: dispatchFixedControlClick creates valid event
// ---------------------------------------------------------------------------
(function() {
  sandbox._listeners = [];
  sandbox._captured = [];

  sandbox._listeners.push({
    e: "click",
    h: function(e) {
      sandbox._captured.push({
        id: e.target.id,
        defaultPrevented: e.defaultPrevented
      });
    }
  });

  dispatchFixedControlClick("btn-confirm-approve");
  assert(sandbox._captured.length === 1,
         "dispatchFixedControlClick fires one listener");
  assert(sandbox._captured[0].id === "btn-confirm-approve",
         "event target id is 'btn-confirm-approve'");
  assert(sandbox._captured[0].defaultPrevented === false,
         "event is not defaultPrevented initially");

  dispatchFixedControlClick("btn-confirm-cancel");
  assert(sandbox._captured.length === 2,
         "dispatchFixedControlClick fires for cancel as well");
  assert(sandbox._captured[1].id === "btn-confirm-cancel",
         "second event target id is 'btn-confirm-cancel'");
})();

// ---------------------------------------------------------------------------
// Test: dispatchFixedControlClick does NOT trigger canvas delegation
// ---------------------------------------------------------------------------
(function() {
  sandbox._listeners = [];
  sandbox._delegationFired = false;

  // Simulate Stage #847 canvas delegation: elements with data-action-target
  sandbox._listeners.push({
    e: "click",
    h: function(e) {
      // Canvas delegate checks: closest("[data-action-target]")
      // If this returns non-null, canvas would navigate
      var actionTarget = e.target.closest("[data-action-target]");
      if (actionTarget !== null) {
        sandbox._delegationFired = true;
      }
    }
  });

  dispatchFixedControlClick("btn-confirm-approve");
  assert(sandbox._delegationFired === false,
         "Stage #847 canvas delegation must NOT fire for btn-confirm-approve");

  dispatchFixedControlClick("btn-confirm-cancel");
  assert(sandbox._delegationFired === false,
         "Stage #847 canvas delegation must NOT fire for btn-confirm-cancel");
})();

// ---------------------------------------------------------------------------
// Output results
// ---------------------------------------------------------------------------
console.log(JSON.stringify({ passed: passed, failed: failed }));
"""


def _run_harness():
    result = subprocess.run(
        ["node", "-e", _HARNESS],
        capture_output=True,
        text=True,
        timeout=30,
    )
    if result.returncode != 0:
        raise RuntimeError("Node harness failed: " + result.stderr)
    return result.stdout


class TestFixedControlTargetHarness:
    """Node harness validates makeFixedControlTarget / dispatchFixedControlClick."""

    def test_harness_runs_without_error(self):
        """Harness evaluates without throwing."""
        output = _run_harness()
        assert output, "harness produced no output"

    def test_all_harness_assertions_pass(self):
        """All harness assertions pass (passed == 0 failed)."""
        output = _run_harness()
        import json
        result = json.loads(output)
        assert result["passed"] > 0, "no assertions ran"
        assert result["failed"] == 0, f"{result['failed']} harness assertions failed"

    def test_closest_returns_null_for_data_action_target(self):
        """closest('[data-action-target]') returns null — critical for Stage #847 safety."""
        output = _run_harness()
        import json
        result = json.loads(output)
        # If harness had a failure on this assertion, it would be counted in failed
        assert result["failed"] == 0, "harness failed on data-action-target closest check"

    def test_closest_returns_self_for_own_id(self):
        """closest('#btn-confirm-approve') returns the target itself."""
        output = _run_harness()
        import json
        result = json.loads(output)
        assert result["failed"] == 0

    def test_matches_is_a_function(self):
        """makeFixedControlTarget returns an object with matches() method."""
        output = _run_harness()
        import json
        result = json.loads(output)
        assert result["failed"] == 0

    def test_dispatch_fires_listener(self):
        """dispatchFixedControlClick fires registered click handlers."""
        output = _run_harness()
        import json
        result = json.loads(output)
        assert result["failed"] == 0

    def test_dispatch_does_not_fire_canvas_delegation(self):
        """
        dispatchFixedControlClick does NOT trigger Stage #847 canvas delegation.

        The approval/cancel targets have no [data-action-target] attribute,
        so closest('[data-action-target]') returns null and no navigation fires.
        """
        output = _run_harness()
        import json
        result = json.loads(output)
        assert result["failed"] == 0

    def test_both_approve_and_cancel_ids_work(self):
        """dispatchFixedControlClick works for both btn-confirm-approve and btn-confirm-cancel."""
        output = _run_harness()
        import json
        result = json.loads(output)
        assert result["failed"] == 0