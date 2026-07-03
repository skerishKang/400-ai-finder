"""
Contract tests for citizen-action-executor (Stage #848).
Verifies the allowlisted action executor's state machine and safety constraints.
"""

import os
import subprocess
import pytest
import tempfile

JS_RUNNER_CODE = r'''
console.log('RUNNER_STARTED');
const vm = require('vm');
const fs = require('fs');

const mapJS = fs.readFileSync('./src/web/static/citizen-action-demo-map.js', 'utf8');
const canvasJS = fs.readFileSync('./src/web/static/citizen-action-demo-canvas.js', 'utf8');
const executorJS = fs.readFileSync('./src/web/static/citizen-action-executor.js', 'utf8');
const testCode = process.argv[2];

const elements = {};

function makeElement(id, tag) {
  tag = tag || 'DIV';
  var el = {
    id: id,
    tagName: tag.toUpperCase(),
    classList: {
      add: function(cls) { this._classes = this._classes || []; this._classes.push(cls); },
      contains: function(cls) { return (this._classes || []).indexOf(cls) !== -1; }
    },
    _classes: [],
    _text: '',
    get textContent() { return this._text; },
    set textContent(v) { this._text = v; },
    style: { display: 'block' },
    focus: function() { sandbox.focusId = this.id; },
    scrollIntoView: function() { sandbox.scrollId = this.id; },
    click: function() { sandbox.clickId = this.id; },
    setAttribute: function(n, v) {
      sandbox.attrs = sandbox.attrs || {};
      sandbox.attrs[this.id + n] = v;
    },
    getAttribute: function(n) {
      if (n === 'id') return this.id || null;
      return sandbox.attrs ? sandbox.attrs[this.id + n] : null;
    },
    appendChild: function(child) {
      this._children = this._children || [];
      this._children.push(child);
      child._parent = this;
      return child;
    },
    addEventListener: function(e, h) {
      sandbox._listeners = sandbox._listeners || [];
      sandbox._listeners.push({ e: e, h: h, id: this.id });
    },
    querySelector: function(sel) {
      // Search all descendants recursively for a match
      var queue = (this._children || []).slice();
      while (queue.length > 0) {
        var node = queue.shift();
        if (node.matches && node.matches(sel)) return node;
        if (node._children) queue.push.apply(queue, node._children);
      }
      return null;
    },
    matches: function(selector) {
      // Simple: matches by id or attribute patterns used in this harness
      if (selector.indexOf('[data-action-target=') !== -1) {
        var m = selector.match(/\[data-action-target="([^"]+)"\]/);
        if (m) return this.getAttribute && this.getAttribute('data-action-target') === m[1];
      }
      if (selector.indexOf('#') === 0) return this.id === selector.slice(1);
      return false;
    },
    closest: function(selector) {
      var cur = this;
      while (cur) {
        if (cur.matches && cur.matches(selector)) return cur;
        cur = cur._parent;
      }
      return null;
    }
  };
  return el;
}

var fakeCanvasInner = makeElement('demo-canvas-inner', 'DIV');
var fakeCanvas = makeElement('demo-canvas', 'MAIN');
fakeCanvas.appendChild(fakeCanvasInner);

const sandbox = {
  document: {
    getElementById: function(id) {
      if (id === 'demo-canvas') return fakeCanvas;
      if (id === 'copilot-rail') return makeElement('copilot-rail', 'ASIDE');
      if (!elements[id]) elements[id] = makeElement(id);
      return elements[id];
    },
    createElement: function(tag) {
      var el = makeElement('dynamic-' + Math.random(), tag);
      elements[el.id] = el;
      return el;
    },
    addEventListener: function(e, h) {
      sandbox._listeners = sandbox._listeners || [];
      sandbox._listeners.push({ e: e, h: h });
    },
    removeEventListener: function(e, h) {
      sandbox._listeners = sandbox._listeners || [];
      sandbox._listeners = sandbox._listeners.filter(function(l) {
        return !(l.e === e && l.h === h);
      });
    }
  },
  window: {
    CitizenActionDemoCanvas: {
      navigateToRoute: function(r) { sandbox.lastRoute = r; },
      getCurrentRouteId: function() { return sandbox.lastRoute || 'home'; },
      getTargetElement: function(t) {
        // Search using querySelector on the fake canvas (like the real implementation)
        if (!elements[t]) elements[t] = makeElement(t);
        var child = fakeCanvasInner.querySelector('[data-action-target="' + t + '"]');
        if (child) return child;
        // Fallback: return the element if it has the attribute set directly
        var el = elements[t];
        if (el.getAttribute && el.getAttribute('data-action-target') === t) return el;
        return null;
      }
    },
    CitizenActionDemoMap: {
      isValidRoute: function(r) {
        return ['home', 'civil-service', 'complaint-category',
                'complaint-intake', 'complaint-review', 'handoff-stop'].indexOf(r) !== -1;
      },
      isValidTarget: function(t) {
        return ['nav-civil-service', 'nav-complaint-category',
                'complaint-category-illegal-parking',
                'complaint-category-public-parking-inconvenience',
                'complaint-category-residential-parking',
                'complaint-category-traffic-or-facility-safety',
                'complaint-category-other-or-unsure',
                'complaint-body', 'complaint-draft-review',
                'confirm-draft-prefill', 'handoff-notice'].indexOf(t) !== -1;
      },
      getRoute: function(r) {
        var routes = {
          'home': { navTargets: ['nav-civil-service'] },
          'civil-service': { navTargets: ['nav-complaint-category'] },
          'complaint-category': { navTargets: ['complaint-category-illegal-parking'] },
          'complaint-intake': { navTargets: ['complaint-draft-review', 'complaint-body'] },
          'complaint-review': { navTargets: ['confirm-draft-prefill'] },
          'handoff-stop': { navTargets: [] }
        };
        return routes[r];
      }
    }
  },
  setTimeout: function(fn) {
    sandbox.queue = sandbox.queue || [];
    sandbox.queue.push(fn);
    return sandbox._timerSeq = (sandbox._timerSeq || 0) + 1;
  },
  clearTimeout: function() { sandbox.queue = []; },
  console: {
    log: function() {
      var args = Array.prototype.slice.call(arguments);
      process.stdout.write(args.join(' ') + '\n');
    },
    error: function() {
      var args = Array.prototype.slice.call(arguments);
      process.stderr.write(args.join(' ') + '\n');
    }
  }
};
sandbox.window = sandbox;
var cx = vm.createContext(sandbox);

vm.runInContext(mapJS, cx);
vm.runInContext(canvasJS, cx);
vm.runInContext(executorJS, cx);

cx.executor = sandbox.window.CitizenActionDemoExecutor;
cx.sandbox = sandbox;
cx.makeElement = makeElement;
cx.fakeCanvasInner = fakeCanvasInner;

try {
  vm.runInContext(testCode, cx);
} catch (e) {
  console.log('ERROR: ' + e.message);
}
'''

def _run_js_test(test_code):
    with tempfile.NamedTemporaryFile(mode='w', suffix='.js', dir='/mnt/g/Ddrive/BatangD/task/workdiary/400-ai-finder-stage848-v2', delete=False) as f:
        f.write(JS_RUNNER_CODE)
        runner_path = f.name

    try:
        result = subprocess.run(
            ["node", runner_path, test_code],
            cwd="/mnt/g/Ddrive/BatangD/task/workdiary/400-ai-finder-stage848-v2",
            capture_output=True,
            text=True
        )
        return result.stdout
    finally:
        if os.path.exists(runner_path):
            os.remove(runner_path)

def _drain_timers():
    return r"""
    while(sandbox.queue && sandbox.queue.length > 0) {
      const snap = executor.getSnapshot();
      if (['waiting', 'paused', 'stopped', 'cancelled', 'blocked'].includes(snap.status)) break;
      sandbox.queue.shift()();
    }
    """

# ---------------------------------------------------------------------------
# Test Cases
# ---------------------------------------------------------------------------

def test_valid_navigation_plan():
    test_code = f"""
    const plan = {{
      plan_status: 'guided',
      actions: [
        {{ action_type: 'OPEN_ALLOWLISTED_ROUTE', route_id: 'civil-service', target_id: null, explanation_id: 'open', requires_user_confirmation: false, choice_ids: [] }},
        {{ action_type: 'STOP_FOR_USER_CONFIRMATION', route_id: null, target_id: null, explanation_id: 'stop', requires_user_confirmation: true, choice_ids: [] }}
      ],
      requires_user_confirmation: true,
      hard_stop_required: true,
      reason_codes: []
    }};
    executor.startPlan(plan);
    {_drain_timers()}
    console.log(executor.getSnapshot().status === 'stopped' ? 'PASS' : 'FAIL');
    """
    assert 'PASS' in _run_js_test(test_code)

def test_invalid_plan_blocked():
    test_code = """
    const plan = {
      plan_status: 'guided',
      actions: [{ action_type: 'OPEN_ALLOWLISTED_ROUTE', route_id: 'civil-service' }],
      requires_user_confirmation: true,
      hard_stop_required: true,
      reason_codes: []
    };
    executor.startPlan(plan);
    console.log(sandbox.document.getElementById('executor-status').textContent.includes('유효하지 않은') ? 'PASS' : 'FAIL');
    """
    assert 'PASS' in _run_js_test(test_code)

def test_prefill_approval_flow():
    test_code = f"""
    // Create complaint-body as a child of the canvas so querySelector finds it
    var bodyEl = sandbox.document.getElementById('complaint-body');
    bodyEl.setAttribute('data-action-target', 'complaint-body');
    fakeCanvasInner.appendChild(bodyEl);
    bodyEl._parent = fakeCanvasInner;

    // Wire btn-confirm-approve for closest() lookup
    var btn = sandbox.document.getElementById('btn-confirm-approve');
    var confirmSection = makeElement('copilot-confirmation', 'SECTION');
    confirmSection._parent = null;
    btn._parent = confirmSection;

    const plan = {{
      plan_status: 'guided',
      actions: [
        {{ action_type: 'OPEN_ALLOWLISTED_ROUTE', route_id: 'complaint-intake', target_id: null, explanation_id: 'open', requires_user_confirmation: false, choice_ids: [] }},
        {{ action_type: 'PREFILL_APPROVED_DRAFT', route_id: null, target_id: 'complaint-body', explanation_id: 'prefill', requires_user_confirmation: true, choice_ids: [] }},
        {{ action_type: 'STOP_FOR_USER_CONFIRMATION', route_id: null, target_id: null, explanation_id: 'stop', requires_user_confirmation: true, choice_ids: [] }}
      ],
      requires_user_confirmation: true,
      hard_stop_required: true,
      reason_codes: []
    }};
    executor.startPlan(plan);
    {_drain_timers()}

    const snap1 = executor.getSnapshot();

    if (snap1.status === 'waiting') {{
      // Fire the document-level click listener (no element id), not the canvas
      // element-level handler which would swallow the event before it bubbles to document
      var listeners = sandbox._listeners || [];
      for (var i = 0; i < listeners.length; i++) {{
        var l = listeners[i];
        if (l.e === 'click' && !l.id) {{
          l.h({{ target: btn, stopPropagation: function() {{}} }});
          break;
        }}
      }}
      {_drain_timers()}

      const snap2 = executor.getSnapshot();
      const bodyAfter = sandbox.document.getElementById('complaint-body').textContent;

      if (bodyAfter !== '' && snap2.status === 'stopped') {{
        console.log('PASS');
      }} else {{
        console.log('FAIL: Body after="' + bodyAfter + '" status=' + snap2.status);
      }}
    }} else {{
      console.log('FAIL: snap1.status=' + snap1.status);
    }}
    """
    assert 'PASS' in _run_js_test(test_code)

def test_no_action_after_stop():
    test_code = f"""
    const plan = {{
      plan_status: 'guided',
      actions: [
        {{ action_type: 'OPEN_ALLOWLISTED_ROUTE', route_id: 'civil-service', target_id: null, explanation_id: 'open', requires_user_confirmation: false, choice_ids: [] }},
        {{ action_type: 'STOP_FOR_USER_CONFIRMATION', route_id: null, target_id: null, explanation_id: 'stop', requires_user_confirmation: true, choice_ids: [] }}
      ],
      requires_user_confirmation: true,
      hard_stop_required: true,
      reason_codes: []
    }};
    executor.startPlan(plan);

    // Drain all timers: OPEN fires (schedules next), then STOP fires (sets stopped).
    // After STOP, state is 'stopped' and _scheduleNext() is NOT called, so no more timers fire.
    while(sandbox.queue && sandbox.queue.length > 0) {{
      const snap = executor.getSnapshot();
      if (['paused', 'cancelled'].includes(snap.status)) break;
      sandbox.queue.shift()();
    }}

    // Status must be 'stopped'; no action runs after STOP (no more timers fire).
    const snap = executor.getSnapshot();
    const remaining = sandbox.queue ? sandbox.queue.length : 0;
    console.log((snap.status === 'stopped' && remaining === 0) ? 'PASS' : 'FAIL');
    """
    assert 'PASS' in _run_js_test(test_code)

def test_pause_resume():
    test_code = f"""
    const plan = {{
      plan_status: 'guided',
      actions: [
        {{ action_type: 'OPEN_ALLOWLISTED_ROUTE', route_id: 'civil-service', target_id: null, explanation_id: 'open', requires_user_confirmation: false, choice_ids: [] }},
        {{ action_type: 'STOP_FOR_USER_CONFIRMATION', route_id: null, target_id: null, explanation_id: 'stop', requires_user_confirmation: true, choice_ids: [] }}
      ],
      requires_user_confirmation: true,
      hard_stop_required: true,
      reason_codes: []
    }};
    executor.startPlan(plan);

    // Execute first action
    sandbox.queue.shift()();

    executor.pause();
    const snap1 = executor.getSnapshot();

    executor.resume();
    {_drain_timers()}
    const snap2 = executor.getSnapshot();

    console.log(snap1.status === 'paused' && snap2.status === 'stopped' ? 'PASS' : 'FAIL');
    """
    assert 'PASS' in _run_js_test(test_code)

def test_cancel():
    test_code = f"""
    const plan = {{
      plan_status: 'guided',
      actions: [
        {{ action_type: 'OPEN_ALLOWLISTED_ROUTE', route_id: 'civil-service', target_id: null, explanation_id: 'open', requires_user_confirmation: false, choice_ids: [] }},
        {{ action_type: 'STOP_FOR_USER_CONFIRMATION', route_id: null, target_id: null, explanation_id: 'stop', requires_user_confirmation: true, choice_ids: [] }}
      ],
      requires_user_confirmation: true,
      hard_stop_required: true,
      reason_codes: []
    }};
    executor.startPlan(plan);
    executor.cancel();
    {_drain_timers()}
    console.log(executor.getSnapshot().status === 'cancelled' ? 'PASS' : 'FAIL');
    """
    assert 'PASS' in _run_js_test(test_code)
