"""
Stage #852 — MV3 local fixture bridge contract tests.
Zero-execution static analysis + node. No browser, no server, no network.
"""
import json, re, subprocess
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
BRIDGE = REPO / "extensions" / "citizen-action-local-bridge"
MANIFEST = BRIDGE / "manifest.json"
PROTOCOL = BRIDGE / "protocol.js"
CS = BRIDGE / "content-script.js"
DOC = REPO / "docs" / "citizen-action-mv3-local-fixture-readiness.md"

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def read(p):
    with open(p, encoding="utf-8") as f:
        return f.read()

def strip_comments(src):
    return re.sub(r'/\*[\s\S]*?\*/', '', re.sub(r'//[^\n]*', '', src))

def node(script):
    r = subprocess.run(["node", "-e", "var P=require('%s');\n%s" % (PROTOCOL, script)],
                      capture_output=True, text=True, timeout=30, cwd=str(REPO))
    if r.returncode:
        raise RuntimeError("node failed: %s" % r.stderr)
    lines = [l for l in r.stdout.strip().split("\n") if l.strip()]
    return json.loads(lines[-1]) if lines else {}

# ---------------------------------------------------------------------------
# 1. manifest
# ---------------------------------------------------------------------------
class TestManifest:
    _p = None
    @classmethod
    def m(cls):
        if cls._p is None: cls._p = json.loads(read(MANIFEST))
        return cls._p

    def test_valid_json(self): json.loads(read(MANIFEST))
    def test_v3(self): assert self.m().get("manifest_version") == 3
    def test_one_cs(self): assert len(self.m()["content_scripts"]) == 1

    @pytest.mark.parametrize("f", [
        "background","permissions","host_permissions",
        "optional_host_permissions","web_accessible_resources","externally_connectable",
    ])
    def test_no_forbidden_field(self, f): assert f not in self.m()

    def test_all_frames_false(self):
        assert self.m()["content_scripts"][0].get("all_frames") is False
    def test_run_at_idle(self):
        assert self.m()["content_scripts"][0].get("run_at") == "document_idle"
    def test_world_isolated(self):
        assert self.m()["content_scripts"][0].get("world") == "ISOLATED"
    def test_js_order(self):
        assert self.m()["content_scripts"][0]["js"] == ["protocol.js", "content-script.js"]

    MATCHES = [
        "http://localhost/static/citizen-action-demo.html",
        "http://127.0.0.1/static/citizen-action-demo.html",
        "http://localhost/citizen-action-demo.html",
        "http://127.0.0.1/citizen-action-demo.html",
    ]
    def test_exact_4_matches(self):
        assert len(self.m()["content_scripts"][0]["matches"]) == 4
    def test_matches_exact(self):
        assert set(self.m()["content_scripts"][0]["matches"]) == set(self.MATCHES)
    def test_no_wildcard(self):
        for x in self.m()["content_scripts"][0]["matches"]:
            assert "<all_urls>" not in x and "*://" not in x
            assert not x.startswith("https://") and not x.startswith("file://")
    def test_no_forbidden_host(self):
        for x in self.m()["content_scripts"][0]["matches"]:
            for bad in ["bukgu","gov","go.kr","localhost:8001","localhost:3000"]:
                assert bad not in x

# ---------------------------------------------------------------------------
# 2. protocol — valid messages (parametrized)
# ---------------------------------------------------------------------------
VALID = [
    ("HIGHLIGHT_ALLOWLISTED_ELEMENT", "highlight_element",
     dict(route_id=None, target_id="complaint-category-illegal-parking", ruc=False)),
    ("SCROLL_TO_ALLOWLISTED_ELEMENT", "scroll_to_element",
     dict(route_id=None, target_id="nav-civil-service", ruc=False)),
    ("CLICK_ALLOWLISTED_ELEMENT", "click_element",
     dict(route_id=None, target_id="complaint-category-illegal-parking", ruc=False)),
    ("OPEN_ALLOWLISTED_ROUTE", "open_route",
     dict(route_id="civil-service", target_id=None, ruc=False)),
    ("PREFILL_APPROVED_DRAFT", "prefill_draft",
     dict(route_id=None, target_id="complaint-body", ruc=True)),
    ("STOP_FOR_USER_CONFIRMATION", "stop_for_confirmation",
     dict(route_id=None, target_id=None, ruc=True)),
]

class TestProtocolValid:
    @pytest.mark.parametrize("atype,exp_id,over", VALID)
    def test_(self, atype, exp_id, over):
        msg = dict(type="CITIZEN_ACTION_BRIDGE_EXECUTE_V1",
                   action=dict(action_type=atype, choice_ids=[],
                               explanation_id=exp_id, requires_user_confirmation=over["ruc"],
                               route_id=over["route_id"], target_id=over["target_id"]))
        r = node("console.log(JSON.stringify(P.validateActionMessage(%s)));" % json.dumps(msg))
        assert r["ok"] is True
        assert r["action"]["action_type"] == atype

# ---------------------------------------------------------------------------
# 3. protocol — blocked
# ---------------------------------------------------------------------------
class TestProtocolBlocked:
    @pytest.mark.parametrize("atype", [
        "LOGIN","SUBMIT","UPLOAD_FILE","PAY","ENTER_IDENTITY",
        "ASK_CLARIFYING_QUESTION","PRESENT_CHOICES",
    ])
    def test_forbidden_type_blocked(self, atype):
        msg = dict(type="CITIZEN_ACTION_BRIDGE_EXECUTE_V1",
                   action=dict(action_type=atype, route_id=None, target_id=None,
                               explanation_id="highlight_element",
                               requires_user_confirmation=False, choice_ids=[]))
        r = node("console.log(JSON.stringify(P.validateActionMessage(%s)));" % json.dumps(msg))
        assert r["ok"] is False
        assert r["reason_code"] in ("sensitive_action_blocked", "unsupported_action")

    def test_unknown_route(self):
        msg = dict(type="CITIZEN_ACTION_BRIDGE_EXECUTE_V1",
                   action=dict(action_type="OPEN_ALLOWLISTED_ROUTE",
                               route_id="bad-route", target_id=None,
                               explanation_id="open_route", requires_user_confirmation=False, choice_ids=[]))
        r = node("console.log(JSON.stringify(P.validateActionMessage(%s)));" % json.dumps(msg))
        assert r["ok"] is False and r["reason_code"] == "unallowlisted_route"

    def test_unknown_target(self):
        msg = dict(type="CITIZEN_ACTION_BRIDGE_EXECUTE_V1",
                   action=dict(action_type="CLICK_ALLOWLISTED_ELEMENT",
                               route_id=None, target_id="bad-target",
                               explanation_id="click_element", requires_user_confirmation=False, choice_ids=[]))
        r = node("console.log(JSON.stringify(P.validateActionMessage(%s)));" % json.dumps(msg))
        assert r["ok"] is False and r["reason_code"] == "unallowlisted_target"

    def test_extra_root_key(self):
        msg = dict(type="CITIZEN_ACTION_BRIDGE_EXECUTE_V1", extra="x",
                   action=dict(action_type="HIGHLIGHT_ALLOWLISTED_ELEMENT",
                               route_id=None, target_id="complaint-category-illegal-parking",
                               explanation_id="highlight_element", requires_user_confirmation=False, choice_ids=[]))
        r = node("console.log(JSON.stringify(P.validateActionMessage(%s)));" % json.dumps(msg))
        assert r["ok"] is False and r["reason_code"] == "invalid_action_shape"

    def test_extra_action_key(self):
        msg = dict(type="CITIZEN_ACTION_BRIDGE_EXECUTE_V1",
                   action=dict(action_type="HIGHLIGHT_ALLOWLISTED_ELEMENT",
                               route_id=None, target_id="complaint-category-illegal-parking",
                               explanation_id="highlight_element", requires_user_confirmation=False, choice_ids=[],
                               raw_password="secret"))
        r = node("console.log(JSON.stringify(P.validateActionMessage(%s)));" % json.dumps(msg))
        assert r["ok"] is False and r["reason_code"] == "invalid_action_shape"

    def test_draft_text_rejected(self):
        msg = dict(type="CITIZEN_ACTION_BRIDGE_EXECUTE_V1",
                   action=dict(action_type="PREFILL_APPROVED_DRAFT",
                               route_id=None, target_id="complaint-body",
                               explanation_id="prefill_draft", requires_user_confirmation=True, choice_ids=[],
                               draft_text="raw user content"))
        r = node("console.log(JSON.stringify(P.validateActionMessage(%s)));" % json.dumps(msg))
        assert r["ok"] is False and r["reason_code"] == "invalid_action_shape"

    def test_non_empty_choice_ids(self):
        msg = dict(type="CITIZEN_ACTION_BRIDGE_EXECUTE_V1",
                   action=dict(action_type="HIGHLIGHT_ALLOWLISTED_ELEMENT",
                               route_id=None, target_id="complaint-category-illegal-parking",
                               explanation_id="highlight_element", requires_user_confirmation=False,
                               choice_ids=["illegal-parking"]))
        r = node("console.log(JSON.stringify(P.validateActionMessage(%s)));" % json.dumps(msg))
        assert r["ok"] is False and r["reason_code"] == "invalid_action_shape"

    def test_wrong_prefill_target(self):
        msg = dict(type="CITIZEN_ACTION_BRIDGE_EXECUTE_V1",
                   action=dict(action_type="PREFILL_APPROVED_DRAFT",
                               route_id=None, target_id="complaint-draft-review",
                               explanation_id="prefill_draft", requires_user_confirmation=True, choice_ids=[]))
        r = node("console.log(JSON.stringify(P.validateActionMessage(%s)));" % json.dumps(msg))
        assert r["ok"] is False and r["reason_code"] == "unallowlisted_target"

    def test_not_object(self):
        r = node("console.log(JSON.stringify(P.validateActionMessage('x')));")
        assert r["ok"] is False and r["reason_code"] == "malformed_message"

    def test_wrong_message_type(self):
        r = node("console.log(JSON.stringify(P.validateActionMessage({type:'X',action:{}})));")
        assert r["ok"] is False and r["reason_code"] == "unknown_message_type"

    def test_blocked_never_echoes(self):
        msg = dict(type="CITIZEN_ACTION_BRIDGE_EXECUTE_V1",
                   action=dict(action_type="LOGIN", route_id=None, target_id=None,
                               explanation_id="highlight_element", requires_user_confirmation=False, choice_ids=[],
                               raw_password="secret123"))
        r = node("console.log(JSON.stringify(P.validateActionMessage(%s)));" % json.dumps(msg))
        assert r["ok"] is False
        assert set(r.keys()) == {"ok", "reason_code"}
        assert r["reason_code"] in (
            "malformed_message","unknown_message_type","unsupported_action",
            "invalid_action_shape","unallowlisted_route","unallowlisted_target",
            "sensitive_action_blocked","inactive_fixture")

# ---------------------------------------------------------------------------
# 4. fixture location guard
# ---------------------------------------------------------------------------
class TestLocation:
    @pytest.mark.parametrize("url", [
        "http://localhost/static/citizen-action-demo.html",
        "http://127.0.0.1/static/citizen-action-demo.html",
        "http://localhost/citizen-action-demo.html",
        "http://127.0.0.1/citizen-action-demo.html",
    ])
    def test_valid(self, url):
        r = node("console.log(JSON.stringify({ok:P.isLocalFixtureLocation('%s')}));" % url)
        assert r["ok"] is True

    @pytest.mark.parametrize("url", [
        "http://localhost:8000/static/citizen-action-demo.html",
        "https://localhost/static/citizen-action-demo.html",
        "http://example.com/static/citizen-action-demo.html",
        "http://bukgu.go.kr/static/citizen-action-demo.html",
        "file:///tmp/citizen-action-demo.html",
    ])
    def test_invalid(self, url):
        r = node("console.log(JSON.stringify({ok:P.isLocalFixtureLocation('%s')}));" % url)
        assert r["ok"] is False

# ---------------------------------------------------------------------------
# 5. content-script: banned API + required features
# ---------------------------------------------------------------------------
class TestContentScript:
    BANNED_PATTERNS = [
        (r"window\.addEventListener", "window.addEventListener"),
        (r"window\.postMessage", "window.postMessage"),
        (r"fetch\s*\(", "fetch("),
        (r"XMLHttpRequest", "XMLHttpRequest"),
        (r"WebSocket", "WebSocket"),
        (r"chrome\.storage", "chrome.storage"),
        (r"localStorage", "localStorage"),
        (r"sessionStorage", "sessionStorage"),
        (r"indexedDB", "indexedDB"),
        (r"document\.cookie", "document.cookie"),
        (r"\beval\s*\(", "eval("),
        (r"new Function", "new Function"),
        (r"\bimport\s*\(", "import()"),
        (r"window\.open", "window.open"),
        (r"location\.assign", "location.assign"),
        (r"location\.href", "location.href"),
        (r"history\.pushState", "history.pushState"),
        (r"history\.replaceState", "history.replaceState"),
        (r"\.click\s*\(", "element.click"),
        (r"scrollIntoView", "scrollIntoView"),
        (r"innerHTML", "innerHTML"),
    ]

    def test_no_banned_api(self):
        src = strip_comments(read(CS))
        for pat, label in self.BANNED_PATTERNS:
            assert not re.findall(pat, src), "%s must not appear" % label

    def test_has_runtime_on_message(self):
        assert "chrome.runtime.onMessage" in strip_comments(read(CS))
    def test_has_fixture_guard(self):
        assert "isLocalFixtureLocation" in strip_comments(read(CS))
    def test_has_status_marker_id(self):
        assert "citizen-action-mv3-local-bridge-status" in strip_comments(read(CS))
    def test_has_korean_text(self):
        assert "MV3 로컬 브리지 활성" in read(CS)
    def test_marker_data_state(self):
        src = read(CS)
        assert 'data-state="active"' in src or 'setAttribute("data-state", "active")' in src

# ---------------------------------------------------------------------------
# 6. no remote code path in extension
# ---------------------------------------------------------------------------
class TestNoRemote:
    @pytest.mark.parametrize("f", ["manifest.json","protocol.js","content-script.js"])
    def test_no_network(self, f):
        src = read(BRIDGE / f)
        if f.endswith(".json"):
            src2 = src
        else:
            src2 = strip_comments(src)
        hits = re.findall(r"http[s]?://(?!localhost|127\.0\.0\.1)[a-zA-Z0-9.\-]+", src2)
        assert not hits, "non-localhost URL in %s: %s" % (f, hits)

# ---------------------------------------------------------------------------
# 7. readiness document
# ---------------------------------------------------------------------------
class TestReadiness:
    def test_exists(self): assert DOC.exists()
    def test_local_only(self):
        t = read(DOC).lower()
        assert "local fixture" in t or "local only" in t
    def test_auth_prereqs(self):
        t = read(DOC).lower()
        assert "written" in t or "authorization" in t
    def test_lists_prohibited(self):
        t = read(DOC).lower()
        found = sum(1 for p in ["background","service_worker","chrome.storage","telemetry","live domain"] if p in t)
        assert found >= 3