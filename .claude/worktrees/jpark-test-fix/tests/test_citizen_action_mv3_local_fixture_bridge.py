"""
Stage #852 — MV3 local fixture bridge contract tests (minimized).
Zero-execution static analysis + node. No browser, no server, no network.
"""
import json, re, subprocess
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
BRIDGE = REPO / "extensions" / "citizen-action-local-bridge"
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
# 1. manifest structure
# ---------------------------------------------------------------------------
class TestManifest:
    def test_manifest_content_script_contract(self):
        import json as _j
        m = _j.loads(read(BRIDGE / "manifest.json"))
        assert m["manifest_version"] == 3
        assert len(m["content_scripts"]) == 1
        assert m["content_scripts"][0]["world"] == "ISOLATED"
        assert m["content_scripts"][0]["js"] == ["protocol.js", "content-script.js"]
        assert m["content_scripts"][0]["all_frames"] is False
        assert m["content_scripts"][0]["run_at"] == "document_idle"
        assert m["action"]["default_state"] == "disabled"

    def test_exact_4_localhost_matches(self):
        import json as _j
        m = _j.loads(read(BRIDGE / "manifest.json"))
        expect = {
            "http://localhost/static/citizen-action-demo.html",
            "http://127.0.0.1/static/citizen-action-demo.html",
            "http://localhost/citizen-action-demo.html",
            "http://127.0.0.1/citizen-action-demo.html",
        }
        assert set(m["content_scripts"][0]["matches"]) == expect

    def test_no_broad_permissions_or_background(self):
        import json as _j
        m = _j.loads(read(BRIDGE / "manifest.json"))
        for f in ["background","permissions","host_permissions",
                  "optional_host_permissions","web_accessible_resources",
                  "externally_connectable"]:
            assert f not in m, "forbidden field %s" % f
        for x in m["content_scripts"][0]["matches"]:
            assert "<all_urls>" not in x and "*://" not in x
            assert not x.startswith("https://") and not x.startswith("file://")
            assert "bukgu" not in x and "gov" not in x

# ---------------------------------------------------------------------------
# 2. protocol — accepted: 6 actions with exact explanation_id
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

def valid_action(action_type):
    for atype, exp_id, over in VALID:
        if atype == action_type:
            return {
                "action_type": atype,
                "route_id": over["route_id"],
                "target_id": over["target_id"],
                "explanation_id": exp_id,
                "requires_user_confirmation": over["ruc"],
                "choice_ids": [],
            }
    raise AssertionError("unknown valid action type")

class TestProtocolValid:
    @pytest.mark.parametrize("atype,exp_id,over", VALID)
    def test_(self, atype, exp_id, over):
        msg = dict(type="CITIZEN_ACTION_BRIDGE_EXECUTE_V1",
                   action=dict(action_type=atype, choice_ids=[],
                               explanation_id=exp_id, requires_user_confirmation=over["ruc"],
                               route_id=over["route_id"], target_id=over["target_id"]))
        r = node("console.log(JSON.stringify(P.validateActionMessage(%s)));" % json.dumps(msg))
        assert r["ok"] is True
        assert r["action"]["explanation_id"] == exp_id
        assert r["action"]["explanation_id"] in (
            "highlight_element","scroll_to_element","open_route",
            "click_element","prefill_draft","stop_for_confirmation")

# ---------------------------------------------------------------------------
# 3. protocol — blocked
# ---------------------------------------------------------------------------
class TestProtocolBlocked:
    @pytest.mark.parametrize("atype", [
        "LOGIN","SUBMIT","UPLOAD_FILE","PAY","ENTER_IDENTITY",
    ])
    def test_strict_banned(self, atype):
        msg = dict(type="CITIZEN_ACTION_BRIDGE_EXECUTE_V1",
                   action=dict(action_type=atype, route_id=None, target_id=None,
                               explanation_id="highlight_element",
                               requires_user_confirmation=False, choice_ids=[]))
        r = node("console.log(JSON.stringify(P.validateActionMessage(%s)));" % json.dumps(msg))
        assert r["ok"] is False and r["reason_code"] == "sensitive_action_blocked"

    @pytest.mark.parametrize("atype,wrong_exp", [
        ("OPEN_ALLOWLISTED_ROUTE", "wrong_id"),
        ("OPEN_ALLOWLISTED_ROUTE", ""),
        ("HIGHLIGHT_ALLOWLISTED_ELEMENT", "click_element"),
        ("HIGHLIGHT_ALLOWLISTED_ELEMENT", None),
    ])
    def test_wrong_or_missing_exp(self, atype, wrong_exp):
        action = valid_action(atype)
        if wrong_exp is None:
            del action["explanation_id"]
        else:
            action["explanation_id"] = wrong_exp
        msg = dict(type="CITIZEN_ACTION_BRIDGE_EXECUTE_V1", action=action)
        r = node("console.log(JSON.stringify(P.validateActionMessage(%s)));" % json.dumps(msg))
        assert r["ok"] is False and r["reason_code"] == "invalid_action_shape"

    @pytest.mark.parametrize("atype,field,bad,code", [
        ("OPEN_ALLOWLISTED_ROUTE", "route_id", "bad-route", "unallowlisted_route"),
        ("CLICK_ALLOWLISTED_ELEMENT", "target_id", "bad-target", "unallowlisted_target"),
        ("PREFILL_APPROVED_DRAFT", "target_id", "complaint-draft-review", "unallowlisted_target"),
        ("HIGHLIGHT_ALLOWLISTED_ELEMENT", "choice_ids", ["x"], "invalid_action_shape"),
        ("HIGHLIGHT_ALLOWLISTED_ELEMENT", "extra", "x", "invalid_action_shape"),
        ("PREFILL_APPROVED_DRAFT", "draft_text", "raw content", "invalid_action_shape"),
    ])
    def test_shape_or_vocab_violation(self, atype, field, bad, code):
        action = valid_action(atype)
        action[field] = bad
        msg = dict(type="CITIZEN_ACTION_BRIDGE_EXECUTE_V1", action=action)
        r = node("console.log(JSON.stringify(P.validateActionMessage(%s)));" % json.dumps(msg))
        assert r["ok"] is False and r["reason_code"] == code

    def test_malformed_and_unknown_type(self):
        r = node("console.log(JSON.stringify(P.validateActionMessage('x')));")
        assert r["ok"] is False and r["reason_code"] == "malformed_message"
        r = node("console.log(JSON.stringify(P.validateActionMessage({type:'X',action:{}})));")
        assert r["ok"] is False and r["reason_code"] == "unknown_message_type"

    def test_blocked_never_echoes(self):
        msg = dict(type="CITIZEN_ACTION_BRIDGE_EXECUTE_V1",
                   action=dict(action_type="LOGIN", route_id=None, target_id=None,
                               explanation_id="highlight_element",
                               requires_user_confirmation=False, choice_ids=[],
                               raw_password="secret123"))
        r = node("console.log(JSON.stringify(P.validateActionMessage(%s)));" % json.dumps(msg))
        assert r["ok"] is False
        assert set(r.keys()) == {"ok", "reason_code"}

# ---------------------------------------------------------------------------
# 4. fixture location guard
# ---------------------------------------------------------------------------
class TestLocation:
    @pytest.mark.parametrize("url", [
        "http://localhost/static/citizen-action-demo.html",
        "http://127.0.0.1/static/citizen-action-demo.html",
        "http://localhost:8000/static/citizen-action-demo.html",
        "http://127.0.0.1:8401/static/citizen-action-demo.html",
    ])
    def test_valid(self, url):
        r = node("console.log(JSON.stringify({ok:P.isLocalFixtureLocation('%s')}));" % url)
        assert r["ok"] is True

    @pytest.mark.parametrize("url", [
        "https://localhost/static/citizen-action-demo.html",
        "http://localhost.evil/static/citizen-action-demo.html",
        "http://127.0.0.1.evil/static/citizen-action-demo.html",
        "http://example.com/static/citizen-action-demo.html",
        "http://localhost/wrong.html",
    ])
    def test_invalid(self, url):
        r = node("console.log(JSON.stringify({ok:P.isLocalFixtureLocation('%s')}));" % url)
        assert r["ok"] is False

# ---------------------------------------------------------------------------
# 5. content-script: banned API + required features
# ---------------------------------------------------------------------------
BANNED = [
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
    (r"\.click\s*\(", "element.click"),
    (r"scrollIntoView", "scrollIntoView"),
    (r"innerHTML", "innerHTML"),
]

class TestContentScript:
    def test_no_banned_api(self):
        src = strip_comments(read(CS))
        for pat, label in BANNED:
            assert not re.findall(pat, src), "%s must not appear" % label

    def test_has_guard_marker_runtime(self):
        src = strip_comments(read(CS))
        assert "isLocalFixtureLocation" in src
        assert "citizen-action-mv3-local-bridge-status" in src
        assert "chrome.runtime.onMessage" in src
        assert "MV3 로컬 브리지 활성" in read(CS)

# ---------------------------------------------------------------------------
# 6. no remote code in extension
# ---------------------------------------------------------------------------
class TestNoRemote:
    @pytest.mark.parametrize("f", ["protocol.js","content-script.js"])
    def test_no_nonlocalhost_url(self, f):
        src = strip_comments(read(BRIDGE / f))
        hits = re.findall(r"http[s]?://(?!localhost|127\.0\.0\.1)[a-zA-Z0-9.\-]+", src)
        assert not hits

# ---------------------------------------------------------------------------
# 7. readiness document
# ---------------------------------------------------------------------------
class TestReadiness:
    def test_exists_and_key_claims(self):
        t = read(DOC).lower()
        assert DOC.exists()
        assert "local fixture" in t or "local only" in t
        assert "authorization" in t or "written" in t
        found = sum(1 for p in ["background","service_worker","chrome.storage",
                                 "telemetry","live domain"] if p in t)
        assert found >= 3
        for exp in ["highlight_element","scroll_to_element","open_route",
                    "click_element","prefill_draft","stop_for_confirmation"]:
            assert exp in read(DOC)
        assert "port" in t and ("restrict" in t or "not limit" in t)