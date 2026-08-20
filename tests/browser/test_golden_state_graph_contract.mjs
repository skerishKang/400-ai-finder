import assert from "assert";
import test from "node:test";
import {
  GOLDEN_STATES,
  GOLDEN_TRANSITIONS,
  validateGoldenTrace,
} from "./golden_state_graph_contract.mjs";

const YES_TRACE = [
  { state: "ENTRY" },
  { state: "ANSWER" },
  { state: "CONFIRM" },
  { state: "NAVIGATE" },
  { state: "RESULT", metadata: { result: "grounded" } },
  { state: "STOP" },
];

const NO_TRACE = [
  { state: "ENTRY" },
  { state: "ANSWER" },
  { state: "CONFIRM" },
  { state: "DECISION_NO" },
  { state: "STOP" },
];

test("GOLDEN_STATES is the exact canonical set", () => {
  assert.deepStrictEqual(GOLDEN_STATES, [
    "ENTRY",
    "ANSWER",
    "CONFIRM",
    "DECISION_NO",
    "NAVIGATE",
    "RESULT",
    "STOP",
  ]);
});

test("GOLDEN_TRANSITIONS is the exact adjacency contract", () => {
  assert.deepStrictEqual(GOLDEN_TRANSITIONS, {
    ENTRY: ["ANSWER"],
    ANSWER: ["CONFIRM"],
    CONFIRM: ["DECISION_NO", "NAVIGATE"],
    DECISION_NO: ["STOP"],
    NAVIGATE: ["RESULT"],
    RESULT: ["STOP"],
    STOP: [],
  });
});

test("canonical YES trace validates", () => {
  const r = validateGoldenTrace(YES_TRACE);
  assert.strictEqual(r.valid, true);
  assert.deepStrictEqual(r.states, [
    "ENTRY",
    "ANSWER",
    "CONFIRM",
    "NAVIGATE",
    "RESULT",
    "STOP",
  ]);
});

test("canonical NO trace validates", () => {
  const r = validateGoldenTrace(NO_TRACE);
  assert.strictEqual(r.valid, true);
  assert.deepStrictEqual(r.states, [
    "ENTRY",
    "ANSWER",
    "CONFIRM",
    "DECISION_NO",
    "STOP",
  ]);
});

test("YES trace requires RESULT metadata equal to expectedResult", () => {
  const r = validateGoldenTrace(YES_TRACE, { expectedResult: "grounded" });
  assert.strictEqual(r.valid, true);
});

test("historical shortcut ENTRY → NAVIGATE is rejected", () => {
  const r = validateGoldenTrace([
    { state: "ENTRY" },
    { state: "NAVIGATE" },
    { state: "RESULT" },
    { state: "STOP" },
  ]);
  assert.strictEqual(r.valid, false);
  assert.ok(
    r.errors.some((e) => e.includes("ENTRY") && e.includes("NAVIGATE")),
    "must name ENTRY→NAVIGATE violation: " + r.errors,
  );
});

test("ANSWER → NAVIGATE is rejected", () => {
  const r = validateGoldenTrace([
    { state: "ENTRY" },
    { state: "ANSWER" },
    { state: "NAVIGATE" },
    { state: "RESULT" },
    { state: "STOP" },
  ]);
  assert.strictEqual(r.valid, false);
  assert.ok(
    r.errors.some((e) => e.includes("ANSWER") && e.includes("NAVIGATE")),
    "must name ANSWER→NAVIGATE violation: " + r.errors,
  );
});

test("CONFIRM → RESULT is rejected", () => {
  const r = validateGoldenTrace([
    { state: "ENTRY" },
    { state: "ANSWER" },
    { state: "CONFIRM" },
    { state: "RESULT" },
    { state: "STOP" },
  ]);
  assert.strictEqual(r.valid, false);
  assert.ok(
    r.errors.some((e) => e.includes("CONFIRM") && e.includes("RESULT")),
    "must name CONFIRM→RESULT violation: " + r.errors,
  );
});

test("DECISION_NO → NAVIGATE is rejected", () => {
  const r = validateGoldenTrace([
    { state: "ENTRY" },
    { state: "ANSWER" },
    { state: "CONFIRM" },
    { state: "DECISION_NO" },
    { state: "NAVIGATE" },
    { state: "RESULT" },
    { state: "STOP" },
  ]);
  assert.strictEqual(r.valid, false);
  assert.ok(
    r.errors.some((e) => e.includes("DECISION_NO") && e.includes("NAVIGATE")),
    "must name DECISION_NO→NAVIGATE violation: " + r.errors,
  );
});

test("duplicate NAVIGATE is rejected", () => {
  const r = validateGoldenTrace([
    { state: "ENTRY" },
    { state: "ANSWER" },
    { state: "CONFIRM" },
    { state: "NAVIGATE" },
    { state: "RESULT" },
    { state: "NAVIGATE" },
    { state: "RESULT" },
    { state: "STOP" },
  ]);
  assert.strictEqual(r.valid, false);
  assert.ok(
    r.errors.some((e) => e.includes("duplicate NAVIGATE")),
    "must report duplicate NAVIGATE: " + r.errors,
  );
});

test("duplicate RESULT is rejected", () => {
  const r = validateGoldenTrace([
    { state: "ENTRY" },
    { state: "ANSWER" },
    { state: "CONFIRM" },
    { state: "NAVIGATE" },
    { state: "RESULT" },
    { state: "NAVIGATE" },
    { state: "RESULT" },
    { state: "STOP" },
  ]);
  assert.strictEqual(r.valid, false);
  assert.ok(
    r.errors.some((e) => e.includes("duplicate RESULT")),
    "must report duplicate RESULT: " + r.errors,
  );
  assert.ok(
    r.errors.some((e) => e.includes("duplicate NAVIGATE")),
    "must also report duplicate NAVIGATE: " + r.errors,
  );
});

test("anything after STOP is rejected", () => {
  const r = validateGoldenTrace([
    { state: "ENTRY" },
    { state: "ANSWER" },
    { state: "CONFIRM" },
    { state: "NAVIGATE" },
    { state: "RESULT" },
    { state: "STOP" },
    { state: "NAVIGATE" },
  ]);
  assert.strictEqual(r.valid, false);
  assert.ok(
    r.errors.some((e) => e.includes("after STOP")),
    "must name after-STOP violation: " + r.errors,
  );
});

test("RESULT without STOP is rejected", () => {
  const r = validateGoldenTrace([
    { state: "ENTRY" },
    { state: "ANSWER" },
    { state: "CONFIRM" },
    { state: "NAVIGATE" },
    { state: "RESULT" },
  ]);
  assert.strictEqual(r.valid, false);
  assert.ok(
    r.errors.some((e) => e.includes("RESULT") && e.includes("STOP")),
    "must name RESULT-without-STOP violation: " + r.errors,
  );
});

test("missing ANSWER is rejected", () => {
  const r = validateGoldenTrace([
    { state: "ENTRY" },
    { state: "CONFIRM" },
    { state: "DECISION_NO" },
    { state: "STOP" },
  ]);
  assert.strictEqual(r.valid, false);
  assert.ok(
    r.errors.some((e) => e.includes("ENTRY") && e.includes("CONFIRM")),
    "must name ENTRY→CONFIRM shortcut: " + r.errors,
  );
});

test("missing CONFIRM on YES path is rejected", () => {
  const r = validateGoldenTrace([
    { state: "ENTRY" },
    { state: "ANSWER" },
    { state: "NAVIGATE" },
    { state: "RESULT" },
    { state: "STOP" },
  ]);
  assert.strictEqual(r.valid, false);
  assert.ok(
    r.errors.some((e) => e.includes("ANSWER") && e.includes("NAVIGATE")),
    "must name ANSWER→NAVIGATE: " + r.errors,
  );
});

test("navigate before YES is rejected (NAVIGATE appears before CONFIRM decision)", () => {
  const r = validateGoldenTrace([
    { state: "ENTRY" },
    { state: "NAVIGATE" },
    { state: "ANSWER" },
    { state: "CONFIRM" },
    { state: "NAVIGATE" },
    { state: "RESULT" },
    { state: "STOP" },
  ]);
  assert.strictEqual(r.valid, false);
  assert.ok(
    r.errors.some((e) => e.includes("ENTRY") && e.includes("NAVIGATE")),
    "must name ENTRY→NAVIGATE shortcut: " + r.errors,
  );
});

test("NO then navigate is rejected", () => {
  const r = validateGoldenTrace([
    { state: "ENTRY" },
    { state: "ANSWER" },
    { state: "CONFIRM" },
    { state: "DECISION_NO" },
    { state: "NAVIGATE" },
    { state: "RESULT" },
    { state: "STOP" },
  ]);
  assert.strictEqual(r.valid, false);
  assert.ok(
    r.errors.some((e) => e.includes("DECISION_NO") && e.includes("NAVIGATE")),
    "must name DECISION_NO→NAVIGATE: " + r.errors,
  );
});

test("RESULT before NAVIGATE is rejected", () => {
  const r = validateGoldenTrace([
    { state: "ENTRY" },
    { state: "ANSWER" },
    { state: "CONFIRM" },
    { state: "NAVIGATE" },
    { state: "CONFIRM" },
    { state: "RESULT" },
    { state: "STOP" },
  ]);
  assert.strictEqual(r.valid, false);
  assert.ok(
    r.errors.some((e) => e.includes("CONFIRM") && e.includes("RESULT")),
    "must name CONFIRM→RESULT: " + r.errors,
  );
});

test("wrong result metadata is rejected when expectedResult supplied", () => {
  const r = validateGoldenTrace(YES_TRACE, { expectedResult: "wrong_value" });
  assert.strictEqual(r.valid, false);
  assert.ok(
    r.errors.some((e) => e.includes("metadata.result")),
    "must name metadata mismatch: " + r.errors,
  );
});

test("missing result metadata is rejected when expectedResult supplied", () => {
  const trace = [
    { state: "ENTRY" },
    { state: "ANSWER" },
    { state: "CONFIRM" },
    { state: "NAVIGATE" },
    { state: "RESULT" },
    { state: "STOP" },
  ];
  const r = validateGoldenTrace(trace, { expectedResult: "grounded" });
  assert.strictEqual(r.valid, false);
  assert.ok(
    r.errors.some((e) => e.includes("metadata missing")),
    "must name missing metadata: " + r.errors,
  );
});

test("trace with RESULT metadata matching expectedResult passes", () => {
  const trace = [
    { state: "ENTRY" },
    { state: "ANSWER" },
    { state: "CONFIRM" },
    { state: "NAVIGATE" },
    { state: "RESULT", metadata: { result: "safe_handoff" } },
    { state: "STOP" },
  ];
  const r = validateGoldenTrace(trace, { expectedResult: "safe_handoff" });
  assert.strictEqual(r.valid, true);
});

test("empty trace is rejected", () => {
  const r = validateGoldenTrace([]);
  assert.strictEqual(r.valid, false);
  assert.ok(r.errors.some((e) => e.includes("empty")));
});

test("non-array input is rejected", () => {
  const r = validateGoldenTrace("not-an-array");
  assert.strictEqual(r.valid, false);
  assert.ok(r.errors.some((e) => e.includes("array")));
});

test("unknown state is rejected", () => {
  const r = validateGoldenTrace([
    { state: "ENTRY" },
    { state: "ANSWER" },
    { state: "UNKNOWN" },
    { state: "STOP" },
  ]);
  assert.strictEqual(r.valid, false);
  assert.ok(r.errors.some((e) => e.includes("unknown state")));
});

test("first state must be ENTRY", () => {
  const r = validateGoldenTrace([
    { state: "ANSWER" },
    { state: "CONFIRM" },
    { state: "STOP" },
  ]);
  assert.strictEqual(r.valid, false);
  assert.ok(r.errors.some((e) => e.includes("first state must be ENTRY")));
});

test("NO path does not require RESULT metadata (no expectedResult)", () => {
  const r = validateGoldenTrace(NO_TRACE, { expectedResult: undefined });
  assert.strictEqual(r.valid, true);
});

test("NO path rejects when expectedResult is supplied (no RESULT to hold metadata)", () => {
  const r = validateGoldenTrace(NO_TRACE, { expectedResult: "must_have_result" });
  assert.strictEqual(r.valid, false);
  assert.ok(
    r.errors.some((e) => e.includes("expectedResult") && e.includes("RESULT")),
    "must reject NO path with expectedResult: " + r.errors,
  );
});
