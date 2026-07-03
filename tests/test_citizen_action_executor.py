"""
Contract tests for citizen-action-executor (Stage #848).
Verifies the allowlisted action executor's state machine and safety constraints.
No canvas/shell loaded — only map + executor in VM sandbox.
"""

import json
import os
import re
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
STATIC = REPO_ROOT / "src" / "web" / "static"

# ---------------------------------------------------------------------------
# JS VM runner — sets up sandbox with fake DOM and canvas adapter stub.
# Only citizen-action-demo-map.js and citizen-action-executor.js are loaded.
# Test code is injected via vm.runInContext so it runs inside the sandbox.
# ---------------------------------------------------------------------------

_MAP_PATH = json.dumps(str(STATIC / "citizen-action-demo-map.js"))
_EXECUTOR_PATH = json.dumps(str(STATIC / "citizen-action-executor.js"))

_RUNNER_HEAD = f"""
const vm = require('vm');
const fs = require('fs');

const mapJS = fs.readFileSync({_MAP_PATH}, "utf8");
const executorJS = fs.readFileSync({_EXECUTOR_PATH}, "utf8");

// -------------------------------------------------------------------
// Fake DOM element factory
// -------------------------------------------------------------------
var elements = {{}};
var timerSeq = 0;
var timerCallbacks = {{}};

function makeElement(id, tag) {{
  tag = tag || "DIV";
  var _className = "";
  var _children = [];
  var _text = "";
  var _innerHTML = "";

  var el = {{ id: id, tagName: tag.toUpperCase(), _parent: null }};

  Object.defineProperty(el, "className", {{
    get: function() {{ return _className; }},
    set: function(v) {{ _className = String(v); }},
    enumerable: true
  }});

  el.classList = {{
    add: function(cls) {{
      var parts = _className.length > 0 ? _className.split(" ") : [];
      if (parts.indexOf(cls) === -1) parts.push(cls);
      _className = parts.join(" ");
    }},
    contains: function(cls) {{
      var parts = _className.length > 0 ? _className.split(" ") : [];
      return parts.indexOf(cls) !== -1;
    }}
  }};

  Object.defineProperty(el, "textContent", {{
    get: function() {{ return _text; }},
    set: function(v) {{ _text = String(v); }},
    enumerable: true
  }});

  Object.defineProperty(el, "innerHTML", {{
    get: function() {{
      if (_children.length > 0) {{
        var html = "";
        for (var ci = 0; ci < _children.length; ci++) {{
          var c = _children[ci];
          html += "<" + c.tagName.toLowerCase();
          if (c.id) html += ' id="' + c.id + '"';
          if (c.className) html += ' class="' + c.className + '"';
          html += ">";
          if (c.innerHTML) html += c.innerHTML;
          html += "</" + c.tagName.toLowerCase() + ">";
        }}
        return html;
      }}
      return _innerHTML;
    }},
    set: function(v) {{
      _innerHTML = String(v);
      _children = [];
    }},
    enumerable: true
  }});

  el.style = {{ display: "block" }};

  el.addEventListener = function(e, h) {{
    sandbox._listeners = sandbox._listeners || [];
    sandbox._listeners.push({{ e: e, h: h, id: el.id }});
  }};
  el.removeEventListener = function(e, h) {{
    sandbox._listeners = sandbox._listeners || [];
    sandbox._listeners = sandbox._listeners.filter(function(l) {{
      return !(l.e === e && l.h === h);
    }});
  }};

  el.focus = function() {{ sandbox.focusId = el.id; }};
  el.scrollIntoView = function() {{ sandbox.scrollId = el.id; }};
  el.click = function() {{ sandbox.clickId = el.id; }};

  el.setAttribute = function(n, v) {{ el["_attr_" + n] = String(v); }};
  el.getAttribute = function(n) {{
    if (n === "id") return el.id || null;
    return el["_attr_" + n] !== undefined ? el["_attr_" + n] : null;
  }};

  el.appendChild = function(child) {{
    _children.push(child);
    child._parent = el;
    return child;
  }};

  el.querySelector = function(sel) {{
    var queue = _children.slice();
    while (queue.length > 0) {{
      var node = queue.shift();
      if (node._matches && node._matches(sel)) return node;
      if (node._children) queue = queue.concat(node._children);
    }}
    return null;
  }};

  el._matches = function(selector) {{
    if (selector.indexOf("[data-action-target=") !== -1) {{
      var m = selector.match(/\\[data-action-target="([^"]+)"\\]/);
      if (m) return el.getAttribute("data-action-target") === m[1];
    }}
    if (selector.indexOf("#") === 0) return el.id === selector.slice(1);
    if (selector.indexOf(".") === 0) {{
      var cls = selector.slice(1);
      var parts = _className.length > 0 ? _className.split(" ") : [];
      return parts.indexOf(cls) !== -1;
    }}
    return false;
  }};

  return el;
}}

// -------------------------------------------------------------------
// Canvas adapter stub (replaces citizen-action-demo-canvas.js)
// -------------------------------------------------------------------
var canvasStub = {{
  _currentRoute: null,
  navigateToRoute: function(routeId) {{ canvasStub._currentRoute = routeId; }},
  getCurrentRouteId: function() {{ return canvasStub._currentRoute || "home"; }},
  getTargetElement: function(targetId) {{
    return elements[targetId] || null;
  }}
}};

// -------------------------------------------------------------------
// Sandbox
// -------------------------------------------------------------------
var sandbox = {{
  document: {{
    getElementById: function(id) {{
      if (!elements[id]) elements[id] = makeElement(id);
      return elements[id];
    }},
    createElement: function(tag) {{
      var id = "el_" + String(Object.keys(elements).length + 1);
      var el = makeElement(id, tag);
      elements[id] = el;
      return el;
    }},
    addEventListener: function(e, h) {{
      sandbox._listeners = sandbox._listeners || [];
      sandbox._listeners.push({{ e: e, h: h }});
    }},
    removeEventListener: function(e, h) {{
      sandbox._listeners = sandbox._listeners || [];
      sandbox._listeners = sandbox._listeners.filter(function(l) {{
        return !(l.e === e && l.h === h);
      }});
    }}
  }},
  window: {{}},
  setTimeout: function(fn) {{
    timerSeq++;
    timerCallbacks[timerSeq] = fn;
    return timerSeq;
  }},
  clearTimeout: function(id) {{
    delete timerCallbacks[id];
  }},
  console: {{
    log: function() {{
      var args = Array.prototype.slice.call(arguments);
      process.stdout.write(args.join(" ") + "\\n");
    }},
    error: function() {{
      var args = Array.prototype.slice.call(arguments);
      process.stderr.write(args.join(" ") + "\\n");
    }}
  }},
  // Drain helper
  drainUntilTerminalOrWait: function() {{
    var keys = Object.keys(timerCallbacks);
    while (keys.length > 0) {{
      var snap = sandbox.window.CitizenActionDemoExecutor.getSnapshot();
      if (["waiting","paused","stopped","cancelled","blocked"].indexOf(snap.status) !== -1) break;
      var id = keys[0];
      var fn = timerCallbacks[id];
      delete timerCallbacks[id];
      fn();
      keys = Object.keys(timerCallbacks);
    }}
  }}
}};

// Wire up sandbox
sandbox.window = sandbox;
sandbox.window.CitizenActionDemoCanvas = canvasStub;
sandbox.timerCallbacks = timerCallbacks;
sandbox.elements = elements;
sandbox.canvasStub = canvasStub;
sandbox.sandbox = sandbox;

var cx = vm.createContext(sandbox);
vm.runInContext(mapJS, cx);
vm.runInContext(executorJS, cx);

// Make executor accessible as a global inside the context
vm.runInContext("const executor = window.CitizenActionDemoExecutor;", cx);
"""


def _run_js(test_code):
    """Run JS test code inside the VM sandbox via node -e. Returns stdout."""
    full_script = (
        _RUNNER_HEAD
        + "\n// --- TEST CODE ---\n"
        + f"vm.runInContext({json.dumps(test_code)}, cx);\n"
    )
    result = subprocess.run(
        ["node", "-e", full_script],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        timeout=30,
    )
    return result.stdout


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_full_valid_flow():
    """Valid ASK→PRESENT_CHOICES→OPEN→HIGHLIGHT→SCROLL→CLICK→STOP executes in
    deterministic order and ends in 'stopped'."""
    plan = {
        "plan_status": "guided",
        "actions": [
            {"action_type": "ASK_CLARIFYING_QUESTION", "route_id": None, "target_id": None,
             "explanation_id": "ask_clarifying_question", "requires_user_confirmation": False,
             "choice_ids": []},
            {"action_type": "PRESENT_CHOICES", "route_id": None, "target_id": None,
             "explanation_id": "present_category_choices", "requires_user_confirmation": False,
             "choice_ids": ["illegal-parking"]},
            {"action_type": "OPEN_ALLOWLISTED_ROUTE", "route_id": "civil-service",
             "target_id": None, "explanation_id": "open_route",
             "requires_user_confirmation": False, "choice_ids": []},
            {"action_type": "HIGHLIGHT_ALLOWLISTED_ELEMENT", "route_id": None,
             "target_id": "nav-complaint-category", "explanation_id": "highlight_element",
             "requires_user_confirmation": False, "choice_ids": []},
            {"action_type": "SCROLL_TO_ALLOWLISTED_ELEMENT", "route_id": None,
             "target_id": "nav-complaint-category", "explanation_id": "scroll_to_element",
             "requires_user_confirmation": False, "choice_ids": []},
            {"action_type": "CLICK_ALLOWLISTED_ELEMENT", "route_id": None,
             "target_id": "nav-complaint-category", "explanation_id": "click_element",
             "requires_user_confirmation": False, "choice_ids": []},
            {"action_type": "STOP_FOR_USER_CONFIRMATION", "route_id": None, "target_id": None,
             "explanation_id": "stop_for_confirmation", "requires_user_confirmation": True,
             "choice_ids": []},
        ],
        "requires_user_confirmation": True,
        "hard_stop_required": True,
        "reason_codes": [],
    }
    plan_json = json.dumps(plan)
    test_code = f"""
    // Set up click target as a button on the route opened by OPEN action
    var el = document.getElementById('nav-complaint-category');
    el.setAttribute('data-action-target', 'nav-complaint-category');
    el.tagName = 'BUTTON';
    const plan = {plan_json};
    executor.startPlan(plan);
    drainUntilTerminalOrWait();
    console.log(executor.getSnapshot().status === 'stopped' ? 'PASS' : 'FAIL');
    """
    assert "PASS" in _run_js(test_code)


def test_route_advancement():
    """OPEN_ALLOWLISTED_ROUTE advances actionIndex."""
    plan = {
        "plan_status": "guided",
        "actions": [
            {"action_type": "OPEN_ALLOWLISTED_ROUTE", "route_id": "civil-service",
             "target_id": None, "explanation_id": "open_route",
             "requires_user_confirmation": False, "choice_ids": []},
            {"action_type": "STOP_FOR_USER_CONFIRMATION", "route_id": None, "target_id": None,
             "explanation_id": "stop_for_confirmation", "requires_user_confirmation": True,
             "choice_ids": []},
        ],
        "requires_user_confirmation": True,
        "hard_stop_required": True,
        "reason_codes": [],
    }
    plan_json = json.dumps(plan)
    test_code = f"""
    const plan = {plan_json};
    executor.startPlan(plan);
    // Execute one tick
    var keys = Object.keys(timerCallbacks);
    if (keys.length > 0) {{
        timerCallbacks[keys[0]]();
        delete timerCallbacks[keys[0]];
    }}
    console.log(executor.getSnapshot().actionIndex === 1 ? 'PASS' : 'FAIL');
    """
    assert "PASS" in _run_js(test_code)


def test_trace_labels_and_fixed_text():
    """Trace contains '순서 01', 'T+0', and fixed Korean explanation."""
    plan = {
        "plan_status": "guided",
        "actions": [
            {"action_type": "ASK_CLARIFYING_QUESTION", "route_id": None, "target_id": None,
             "explanation_id": "ask_clarifying_question", "requires_user_confirmation": False,
             "choice_ids": []},
            {"action_type": "STOP_FOR_USER_CONFIRMATION", "route_id": None, "target_id": None,
             "explanation_id": "stop_for_confirmation", "requires_user_confirmation": True,
             "choice_ids": []},
        ],
        "requires_user_confirmation": True,
        "hard_stop_required": True,
        "reason_codes": [],
    }
    plan_json = json.dumps(plan)
    test_code = f"""
    const plan = {plan_json};
    executor.startPlan(plan);
    drainUntilTerminalOrWait();
    const trace = document.getElementById('action-trace').innerHTML;
    const hasOrder = trace.includes('순서 01');
    const hasElapsed = trace.includes('T+0');
    const hasFixedText = trace.includes('추가 정보가 필요하여 질문을 드립니다.');
    console.log((hasOrder && hasElapsed && hasFixedText) ? 'PASS' : 'FAIL');
    """
    assert "PASS" in _run_js(test_code)


def test_timer_singleton():
    """Only one pending timer at a time."""
    plan = {
        "plan_status": "guided",
        "actions": [
            {"action_type": "OPEN_ALLOWLISTED_ROUTE", "route_id": "civil-service",
             "target_id": None, "explanation_id": "open_route",
             "requires_user_confirmation": False, "choice_ids": []},
            {"action_type": "STOP_FOR_USER_CONFIRMATION", "route_id": None, "target_id": None,
             "explanation_id": "stop_for_confirmation", "requires_user_confirmation": True,
             "choice_ids": []},
        ],
        "requires_user_confirmation": True,
        "hard_stop_required": True,
        "reason_codes": [],
    }
    plan_json = json.dumps(plan)
    test_code = f"""
    const plan = {plan_json};
    executor.startPlan(plan);
    console.log(Object.keys(timerCallbacks).length === 1 ? 'PASS' : 'FAIL');
    // Execute first tick
    var keys = Object.keys(timerCallbacks);
    if (keys.length > 0) {{
        timerCallbacks[keys[0]]();
        delete timerCallbacks[keys[0]];
    }}
    console.log(Object.keys(timerCallbacks).length === 1 ? 'PASS' : 'FAIL');
    """
    assert "PASS" in _run_js(test_code)


def test_strict_validation_blocked():
    """Invalid plans go to 'blocked' state."""
    cases = [
        ("Unknown action kind", {
            "plan_status": "guided",
            "actions": [{"action_type": "UNKNOWN_KIND", "route_id": None, "target_id": None,
                         "explanation_id": "open_route", "requires_user_confirmation": False,
                         "choice_ids": []}],
            "requires_user_confirmation": False, "hard_stop_required": True, "reason_codes": [],
        }),
        ("Extra action field", {
            "plan_status": "guided",
            "actions": [{"action_type": "STOP_FOR_USER_CONFIRMATION", "route_id": None,
                         "target_id": None, "explanation_id": "stop_for_confirmation",
                         "requires_user_confirmation": True, "choice_ids": [], "extra": "x"}],
            "requires_user_confirmation": True, "hard_stop_required": True, "reason_codes": [],
        }),
        ("Extra plan field", {
            "plan_status": "guided",
            "actions": [{"action_type": "STOP_FOR_USER_CONFIRMATION", "route_id": None,
                         "target_id": None, "explanation_id": "stop_for_confirmation",
                         "requires_user_confirmation": True, "choice_ids": []}],
            "requires_user_confirmation": True, "hard_stop_required": True,
            "reason_codes": [], "extra": "x",
        }),
    ]

    for case_name, plan in cases:
        plan_json = json.dumps(plan)
        test_code = f"""
        const plan = {plan_json};
        executor.startPlan(plan);
        console.log(executor.getSnapshot().status === 'blocked' ? 'PASS' : 'FAIL');
        """
        assert "PASS" in _run_js(test_code), f"Failed case: {case_name}"


def test_validation_blocks_unknown_route():
    """Unknown route_id in OPEN_ALLOWLISTED_ROUTE blocks."""
    plan = {
        "plan_status": "guided",
        "actions": [{"action_type": "OPEN_ALLOWLISTED_ROUTE", "route_id": "invalid-route",
                     "target_id": None, "explanation_id": "open_route",
                     "requires_user_confirmation": False, "choice_ids": []}],
        "requires_user_confirmation": False, "hard_stop_required": True, "reason_codes": [],
    }
    plan_json = json.dumps(plan)
    test_code = f"""
    const plan = {plan_json};
    executor.startPlan(plan);
    console.log(executor.getSnapshot().status === 'blocked' ? 'PASS' : 'FAIL');
    """
    assert "PASS" in _run_js(test_code)


def test_validation_blocks_unknown_target():
    """Unknown target_id in HIGHLIGHT/SCROLL/CLICK blocks."""
    plan = {
        "plan_status": "guided",
        "actions": [{"action_type": "HIGHLIGHT_ALLOWLISTED_ELEMENT", "route_id": None,
                     "target_id": "invalid-target", "explanation_id": "highlight_element",
                     "requires_user_confirmation": False, "choice_ids": []}],
        "requires_user_confirmation": False, "hard_stop_required": True, "reason_codes": [],
    }
    plan_json = json.dumps(plan)
    test_code = f"""
    const plan = {plan_json};
    executor.startPlan(plan);
    console.log(executor.getSnapshot().status === 'blocked' ? 'PASS' : 'FAIL');
    """
    assert "PASS" in _run_js(test_code)


def test_validation_blocks_invalid_choice():
    """Choice IDs outside the closed allowlist block."""
    plan = {
        "plan_status": "guided",
        "actions": [{"action_type": "PRESENT_CHOICES", "route_id": None, "target_id": None,
                     "explanation_id": "present_category_choices",
                     "requires_user_confirmation": False,
                     "choice_ids": ["invalid-choice"]}],
        "requires_user_confirmation": False, "hard_stop_required": True, "reason_codes": [],
    }
    plan_json = json.dumps(plan)
    test_code = f"""
    const plan = {plan_json};
    executor.startPlan(plan);
    console.log(executor.getSnapshot().status === 'blocked' ? 'PASS' : 'FAIL');
    """
    assert "PASS" in _run_js(test_code)


def test_validation_blocks_selector_like():
    """Selector-like target_id (starting with '.') blocks."""
    plan = {
        "plan_status": "guided",
        "actions": [{"action_type": "HIGHLIGHT_ALLOWLISTED_ELEMENT", "route_id": None,
                     "target_id": ".my-class", "explanation_id": "highlight_element",
                     "requires_user_confirmation": False, "choice_ids": []}],
        "requires_user_confirmation": False, "hard_stop_required": True, "reason_codes": [],
    }
    plan_json = json.dumps(plan)
    test_code = f"""
    const plan = {plan_json};
    executor.startPlan(plan);
    console.log(executor.getSnapshot().status === 'blocked' ? 'PASS' : 'FAIL');
    """
    assert "PASS" in _run_js(test_code)


def test_validation_blocks_url_like():
    """URL-like route_id blocks."""
    plan = {
        "plan_status": "guided",
        "actions": [{"action_type": "OPEN_ALLOWLISTED_ROUTE", "route_id": "http://evil.com",
                     "target_id": None, "explanation_id": "open_route",
                     "requires_user_confirmation": False, "choice_ids": []}],
        "requires_user_confirmation": False, "hard_stop_required": True, "reason_codes": [],
    }
    plan_json = json.dumps(plan)
    test_code = f"""
    const plan = {plan_json};
    executor.startPlan(plan);
    console.log(executor.getSnapshot().status === 'blocked' ? 'PASS' : 'FAIL');
    """
    assert "PASS" in _run_js(test_code)


def test_no_echo_of_rejected_input():
    """Blocked plans do not echo raw route_id/target_id in status or trace."""
    plan = {
        "plan_status": "guided",
        "actions": [{"action_type": "OPEN_ALLOWLISTED_ROUTE", "route_id": "http://evil.com",
                     "target_id": None, "explanation_id": "open_route",
                     "requires_user_confirmation": False, "choice_ids": []}],
        "requires_user_confirmation": False, "hard_stop_required": True, "reason_codes": [],
    }
    plan_json = json.dumps(plan)
    test_code = f"""
    const plan = {plan_json};
    executor.startPlan(plan);
    const status = document.getElementById('executor-status').textContent;
    const trace = document.getElementById('action-trace').innerHTML;
    console.log(!status.includes('http://evil.com') && !trace.includes('http://evil.com') ? 'PASS' : 'FAIL');
    """
    assert "PASS" in _run_js(test_code)


def test_pause_resume_preserves_action():
    """Pause halts execution; resume continues remaining actions."""
    plan = {
        "plan_status": "guided",
        "actions": [
            {"action_type": "OPEN_ALLOWLISTED_ROUTE", "route_id": "civil-service",
             "target_id": None, "explanation_id": "open_route",
             "requires_user_confirmation": False, "choice_ids": []},
            {"action_type": "STOP_FOR_USER_CONFIRMATION", "route_id": None, "target_id": None,
             "explanation_id": "stop_for_confirmation", "requires_user_confirmation": True,
             "choice_ids": []},
        ],
        "requires_user_confirmation": True,
        "hard_stop_required": True,
        "reason_codes": [],
    }
    plan_json = json.dumps(plan)
    test_code = f"""
    const plan = {plan_json};
    executor.startPlan(plan);
    // Execute first action
    var keys = Object.keys(timerCallbacks);
    if (keys.length > 0) {{
        timerCallbacks[keys[0]]();
        delete timerCallbacks[keys[0]];
    }}
    executor.pause();
    var snap1 = executor.getSnapshot();
    executor.resume();
    drainUntilTerminalOrWait();
    var snap2 = executor.getSnapshot();
    console.log(snap1.status === 'paused' && snap2.status === 'stopped' ? 'PASS' : 'FAIL');
    """
    assert "PASS" in _run_js(test_code)


def test_cancel_prevents_work():
    """Cancel stops execution immediately."""
    plan = {
        "plan_status": "guided",
        "actions": [
            {"action_type": "OPEN_ALLOWLISTED_ROUTE", "route_id": "civil-service",
             "target_id": None, "explanation_id": "open_route",
             "requires_user_confirmation": False, "choice_ids": []},
            {"action_type": "STOP_FOR_USER_CONFIRMATION", "route_id": None, "target_id": None,
             "explanation_id": "stop_for_confirmation", "requires_user_confirmation": True,
             "choice_ids": []},
        ],
        "requires_user_confirmation": True,
        "hard_stop_required": True,
        "reason_codes": [],
    }
    plan_json = json.dumps(plan)
    test_code = f"""
    const plan = {plan_json};
    executor.startPlan(plan);
    executor.cancel();
    drainUntilTerminalOrWait();
    console.log(executor.getSnapshot().status === 'cancelled' ? 'PASS' : 'FAIL');
    """
    assert "PASS" in _run_js(test_code)


def test_click_only_for_allowlisted_targets():
    """Click only works on buttons registered as navTargets for current route."""
    plan = {
        "plan_status": "guided",
        "actions": [
            {"action_type": "CLICK_ALLOWLISTED_ELEMENT", "route_id": None,
             "target_id": "nav-civil-service", "explanation_id": "click_element",
             "requires_user_confirmation": False, "choice_ids": []},
            {"action_type": "STOP_FOR_USER_CONFIRMATION", "route_id": None, "target_id": None,
             "explanation_id": "stop_for_confirmation", "requires_user_confirmation": True,
             "choice_ids": []},
        ],
        "requires_user_confirmation": True,
        "hard_stop_required": True,
        "reason_codes": [],
    }
    plan_json = json.dumps(plan)
    test_code = f"""
    const plan = {plan_json};
    // Set up a clickable button for the current route (home → nav-civil-service)
    var el = document.getElementById('nav-civil-service');
    el.setAttribute('data-action-target', 'nav-civil-service');
    el.tagName = 'BUTTON';
    canvasStub._currentRoute = 'home';
    executor.startPlan(plan);
    var keys = Object.keys(timerCallbacks);
    if (keys.length > 0) {{
        timerCallbacks[keys[0]]();
        delete timerCallbacks[keys[0]];
    }}
    console.log(clickId === 'nav-civil-service' ? 'PASS' : 'FAIL');
    """
    assert "PASS" in _run_js(test_code)


def test_prefill_wait_and_unchanged_body():
    """Prefill enters waiting state without modifying body content."""
    plan = {
        "plan_status": "guided",
        "actions": [
            {"action_type": "PREFILL_APPROVED_DRAFT", "route_id": None,
             "target_id": "complaint-body", "explanation_id": "prefill_draft",
             "requires_user_confirmation": True, "choice_ids": []},
            {"action_type": "STOP_FOR_USER_CONFIRMATION", "route_id": None, "target_id": None,
             "explanation_id": "stop_for_confirmation", "requires_user_confirmation": True,
             "choice_ids": []},
        ],
        "requires_user_confirmation": True,
        "hard_stop_required": True,
        "reason_codes": [],
    }
    plan_json = json.dumps(plan)
    test_code = f"""
    const plan = {plan_json};
    var bodyEl = document.getElementById('complaint-body');
    bodyEl.setAttribute('data-action-target', 'complaint-body');
    bodyEl.textContent = 'original text';
    executor.startPlan(plan);
    drainUntilTerminalOrWait();
    console.log(executor.getSnapshot().status === 'waiting' && bodyEl.textContent === 'original text' ? 'PASS' : 'FAIL');
    """
    assert "PASS" in _run_js(test_code)


def test_cancel_during_prefill_leaves_body_unchanged():
    """Cancel while waiting for prefill leaves the body text unchanged."""
    plan = {
        "plan_status": "guided",
        "actions": [
            {"action_type": "PREFILL_APPROVED_DRAFT", "route_id": None,
             "target_id": "complaint-body", "explanation_id": "prefill_draft",
             "requires_user_confirmation": True, "choice_ids": []},
            {"action_type": "STOP_FOR_USER_CONFIRMATION", "route_id": None, "target_id": None,
             "explanation_id": "stop_for_confirmation", "requires_user_confirmation": True,
             "choice_ids": []},
        ],
        "requires_user_confirmation": True,
        "hard_stop_required": True,
        "reason_codes": [],
    }
    plan_json = json.dumps(plan)
    test_code = f"""
    const plan = {plan_json};
    var bodyEl = document.getElementById('complaint-body');
    bodyEl.setAttribute('data-action-target', 'complaint-body');
    bodyEl.textContent = 'original text';
    executor.startPlan(plan);
    drainUntilTerminalOrWait();
    executor.cancel();
    console.log(bodyEl.textContent === 'original text' ? 'PASS' : 'FAIL');
    """
    assert "PASS" in _run_js(test_code)


def test_prefill_approval_writes_fixed_text():
    """Approve writes fixed PREFILL_TEXT and proceeds to STOP."""
    plan = {
        "plan_status": "guided",
        "actions": [
            {"action_type": "PREFILL_APPROVED_DRAFT", "route_id": None,
             "target_id": "complaint-body", "explanation_id": "prefill_draft",
             "requires_user_confirmation": True, "choice_ids": []},
            {"action_type": "STOP_FOR_USER_CONFIRMATION", "route_id": None, "target_id": None,
             "explanation_id": "stop_for_confirmation", "requires_user_confirmation": True,
             "choice_ids": []},
        ],
        "requires_user_confirmation": True,
        "hard_stop_required": True,
        "reason_codes": [],
    }
    plan_json = json.dumps(plan)
    expected_text = "본 시연을 위해 자동으로 생성된 민원 초안 내용입니다. 실제 제출 시에는 상세 내용을 직접 입력하셔야 합니다."
    test_code = f"""
    const plan = {plan_json};
    var bodyEl = document.getElementById('complaint-body');
    bodyEl.setAttribute('data-action-target', 'complaint-body');
    executor.startPlan(plan);
    drainUntilTerminalOrWait();
    // Find and click the approve button via document-level listener
    var listeners = _listeners || [];
    for (var li = 0; li < listeners.length; li++) {{
        var l = listeners[li];
        if (l.e === 'click' && !l.id) {{
            l.h({{ target: {{ id: 'btn-confirm-approve' }}, stopPropagation: function() {{}} }});
            break;
        }}
    }}
    drainUntilTerminalOrWait();
    console.log(bodyEl.textContent === '{expected_text}' && executor.getSnapshot().status === 'stopped' ? 'PASS' : 'FAIL');
    """
    assert "PASS" in _run_js(test_code)


def test_no_action_after_stop():
    """Once stopped, no further route/click/prefill executes."""
    plan = {
        "plan_status": "guided",
        "actions": [
            {"action_type": "STOP_FOR_USER_CONFIRMATION", "route_id": None, "target_id": None,
             "explanation_id": "stop_for_confirmation", "requires_user_confirmation": True,
             "choice_ids": []},
        ],
        "requires_user_confirmation": True,
        "hard_stop_required": True,
        "reason_codes": [],
    }
    plan_json = json.dumps(plan)
    test_code = f"""
    const plan = {plan_json};
    executor.startPlan(plan);
    drainUntilTerminalOrWait();
    const snap = executor.getSnapshot();
    console.log(snap.status === 'stopped' && Object.keys(timerCallbacks).length === 0 ? 'PASS' : 'FAIL');
    """
    assert "PASS" in _run_js(test_code)


def test_static_analysis_no_prohibited_apis():
    """Executor source must not contain dangerous capabilities."""
    executor_path = STATIC / "citizen-action-executor.js"
    with open(executor_path, "r", encoding="utf-8") as f:
        content = f.read()

    prohibited = [
        r"fetch\(",
        r"XMLHttpRequest",
        r"WebSocket",
        r"EventSource",
        r"sendBeacon",
        r"localStorage",
        r"sessionStorage",
        r"indexedDB",
        r"<iframe",
        r"window\.location",
        r"location\.href",
        r"login",
        r"upload",
        r"payment",
        r"identity",
        r"e-sign",
        r"submit",
    ]

    for p in prohibited:
        if re.search(p, content, re.IGNORECASE):
            pytest.fail(f"Prohibited API/keyword found: {p}")
