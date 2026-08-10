import assert from "node:assert/strict";
import fs from "node:fs";
import vm from "node:vm";

const BRIDGE = fs.readFileSync("src/web/static/citizen-mvp-bridge.js", "utf8");

function response({ ok = true, headerId = "", data = {}, jsonError = false } = {}) {
  return {
    ok,
    headers: {
      get(name) {
        return String(name).toLowerCase() === "x-request-id" ? headerId : null;
      },
    },
    json() {
      return jsonError ? Promise.reject(new Error("bad json")) : Promise.resolve(data);
    },
  };
}

function loadBridge(fetchImpl) {
  const window = {
    AbortController,
    CitizenI18n: {
      getLocale() { return "ko"; },
      normalizeLocale() { return "ko"; },
      t() { return "현재 AI 안내를 연결하지 못했습니다."; },
    },
  };
  const context = vm.createContext({
    window,
    fetch: fetchImpl,
    AbortController,
    Promise,
    Object,
    Array,
    String,
    RegExp,
  });
  vm.runInContext(BRIDGE, context, { filename: "citizen-mvp-bridge.js" });
  return window.CitizenMvpBridge;
}

const VALID_ID = "mvp_abc12345_12345678";
const OTHER_ID = "mvp_other999_87654321";

{
  const bridge = loadBridge(async () => response({
    headerId: VALID_ID,
    data: { ok: true, answer: "ok", action: "none", request_id: VALID_ID, schema_version: "1.0" },
  }));
  const result = await bridge.ask("질문");
  assert.equal(result.ok, true);
  assert.equal(result.request_id, VALID_ID);
  assert.equal(result.schema_version, "1.0");
}

{
  const bridge = loadBridge(async () => response({
    headerId: "",
    data: { ok: true, answer: "ok", action: "none", request_id: VALID_ID, schema_version: "1.0.0" },
  }));
  const result = await bridge.ask("질문");
  assert.equal(result.request_id, VALID_ID, "body ID survives a stripped response header");
  assert.equal(result.schema_version, "1.0.0");
}

{
  const bridge = loadBridge(async () => response({
    headerId: VALID_ID,
    data: { ok: true, answer: "ok", action: "none", schema_version: "1.0" },
  }));
  const result = await bridge.ask("질문");
  assert.equal(result.request_id, VALID_ID, "header ID works when old body lacks request_id");
}

{
  const bridge = loadBridge(async () => response({
    headerId: VALID_ID,
    data: { ok: true, answer: "ok", action: "none", request_id: OTHER_ID, schema_version: "1.0" },
  }));
  const result = await bridge.ask("질문");
  assert.equal(result.request_id, "", "header/body mismatch must fail closed");
}

{
  const bridge = loadBridge(async () => response({
    ok: false,
    headerId: VALID_ID,
    data: { ok: false, failure_code: "rate_limited", request_id: VALID_ID, schema_version: "1.0" },
  }));
  const result = await bridge.ask("질문");
  assert.equal(result.ok, false);
  assert.equal(result.answer, "현재 AI 안내를 연결하지 못했습니다.");
  assert.equal(result.action, "none");
  assert.equal(result.request_id, VALID_ID, "HTTP failures keep safe correlation ID");
  assert.equal(result.schema_version, "1.0");
  assert.equal("failure_code" in result, false, "internal failure diagnostics stay out of bridge failure envelope");
}

{
  const bridge = loadBridge(async () => response({ ok: false, headerId: VALID_ID, jsonError: true }));
  const result = await bridge.ask("질문");
  assert.equal(result.request_id, VALID_ID, "malformed JSON keeps sanitized header correlation ID");
  assert.equal(result.schema_version, "");
}

{
  const bridge = loadBridge(async () => response({
    headerId: "not valid !!!",
    data: { ok: true, answer: "ok", action: "none", request_id: "<script>x</script>", schema_version: "v1" },
  }));
  const result = await bridge.ask("질문");
  assert.equal(result.request_id, "");
  assert.equal(result.schema_version, "");
}

{
  const bridge = loadBridge(async () => { throw new Error("offline"); });
  const result = await bridge.ask("질문");
  assert.equal(result.ok, false);
  assert.equal(result.request_id, "");
  assert.equal(result.schema_version, "");
}

console.log("MVP bridge request identity contract: PASS");
