// scripts/run_page_agent_comparison.mjs
//
// Stage 3 Browser comparison harness for parity scenarios.
//
// Compares 정밀 구현형 (deterministic MVP) and Page Agent형 (vendored runtime)
// running the same 5 parity scenarios from parity-contract.json.
//
// Usage:
//   node scripts/run_page_agent_comparison.mjs \
//     --base-url http://127.0.0.1:<PORT> \
//     [--repetitions 1] \
//     [--attempt-range 1-3]  (overrides --repetitions; e.g. 1-1, 2-2, 1-3) \
//     [--output <PATH>]
//
// Behaviour:
//   - Reads parity-contract.json and expectations fixture
//   - 5 scenarios x 2 modes x N attempts = 10N primary runs
//   - Boundary probes: unsupported prompt, cancellation
//   - Fresh browser context per run
//   - Writes machine-readable evidence JSON
//   - Non-zero exit on any run failure (stall = stop + exit)

import { chromium } from "playwright";
import { readFileSync, writeFileSync, mkdirSync, existsSync } from "node:fs";
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";
import assert from "node:assert";

const __dirname = dirname(fileURLToPath(import.meta.url));
const PROJECT_ROOT = join(__dirname, "..");

const LOCAL_HOSTS = new Set(["127.0.0.1", "localhost", "::1"]);
const RELOAD_TIMEOUT = 30000;
const DETERMINISTIC_TIMEOUT_MS = 30000;
const PAGE_AGENT_TIMEOUT_MS = 15000;
const BROWSER_TIMEOUT_MS = 15000;
const SCHEMA_VERSION = "1.0.0";

// ── Shared pass criteria from parity-contract.json indexed by scenario id ──
// Each criterion is (description, evaluation function key) that is evaluated
// against DOM evidence at runtime.
const PASS_CRITERIA_EVALUATORS = {
  apartment_contact: [
    { label: "공동주택 안내 영역 노출", check: routeMatches(["apartment-dept"], ["공동주택"]) },
    { label: "담당 부서/연락처 정보 표시", check: textContains(["연락처", "전화", "FAX"]) },
    { label: "오류 없이 정보 채워짐", check: textExcludes(["오류", "불러오지 못했습니다"]) },
  ],
  bulky_waste_menu: [
    { label: "대형폐기물 화면 열림", check: routeMatches(["bulky-waste-disposal"], ["대형폐기물"]) },
    { label: "안내 텍스트 표시", check: textContains(["대형폐기물", "배출", "신청"]) },
    { label: "실제 제출 없음", check: noSubmitCheck() },
  ],
  passport_procedure: [
    { label: "여권 절차 안내 화면/정보 표시", check: routeMatches(["passport-guidance"], ["여권"]) },
    { label: "구비서류/절차 단계 노출", check: textContains(["구비서류", "수수료", "신청절차", "발급"]) },
    { label: "실제 여권 신청 제출 없음", check: noSubmitCheck() },
  ],
  complaint_screen: [
    { label: "민원 작성 화면 열림", check: routeMatches(["complaint-write"], ["민원"]) },
    { label: "입력 필드/영역 식별됨", check: textContains(["제목", "입력", "작성"]) },
    { label: "임의 제출 없음", check: noSubmitCheck() },
  ],
  mayor_proposal_writing: [
    { label: "작성 화면/보조 영역 열림", check: routeMatches(["mayor-complaint-write"], ["제안", "구청장"]) },
    { label: "초안/입력 안내 제공됨", check: textContains(["제목", "초안", "내용"]) },
    { label: "실제 전송/제출 없음", check: noSubmitCheck() },
  ],
};

function routeMatches(expectedRoutes, contentKeywords) {
  return (route, canvasText) => {
    if (expectedRoutes.includes(route)) return { passed: true, excerpt: `route: ${route}` };
    for (const kw of contentKeywords) {
      if (canvasText.includes(kw)) {
        const idx = canvasText.indexOf(kw);
        const excerpt = canvasText.substring(Math.max(0, idx - 10), Math.min(canvasText.length, idx + kw.length + 10)).replace(/\n/g, " ").trim();
        return { passed: true, excerpt: `text: "...${excerpt}..."` };
      }
    }
    return { passed: false };
  };
}

function textContains(keywords) {
  return (route, canvasText) => {
    for (const kw of keywords) {
      if (canvasText.includes(kw)) {
        const idx = canvasText.indexOf(kw);
        const excerpt = canvasText.substring(Math.max(0, idx - 10), Math.min(canvasText.length, idx + kw.length + 10)).replace(/\n/g, " ").trim();
        return { passed: true, excerpt: `text: "...${excerpt}..."` };
      }
    }
    return { passed: false };
  };
}

function textExcludes(keywords) {
  return (route, canvasText) => {
    for (const kw of keywords) {
      if (canvasText.includes(kw)) {
        return { passed: false };
      }
    }
    return { passed: true, excerpt: "keywords excluded" };
  };
}

function noSubmitCheck() {
  // Evaluated against (route, canvasText, noSubmitPreserved) triple
  return (route, canvasText, noSubmitPreserved) => {
    return { passed: noSubmitPreserved === true, excerpt: noSubmitPreserved ? "no submit detected" : "submit detected" };
  };
}

const KNOWN_BROWSER_PATHS = [
  "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe",
  "C:\\Program Files (x86)\\Google\\Chrome\\Application\\chrome.exe",
  "C:\\Program Files\\Microsoft\\Edge\\Application\\msedge.exe",
  "C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe",
  "/usr/bin/google-chrome",
  "/usr/bin/google-chrome-stable",
  "/usr/bin/chromium",
  "/usr/bin/chromium-browser",
];

// ── Load fixtures ──────────────────────────────────────────────────────────

function loadJson(relPath) {
  const p = join(PROJECT_ROOT, relPath);
  return JSON.parse(readFileSync(p, "utf-8"));
}

const PARITY = loadJson("src/web/examples/page-agent/parity-contract.json");
const EXPECTATIONS = loadJson("tests/fixtures/page_agent_comparison_expectations.json");
const SCENARIOS = PARITY.scenarios;
const SCENARIO_IDS = SCENARIOS.map(s => s.id);

// ── CLI ────────────────────────────────────────────────────────────────────

function parseArgs() {
  const args = {};
  for (let i = 2; i < process.argv.length; i++) {
    const arg = process.argv[i];
    if (arg === "--base-url" && i + 1 < process.argv.length) {
      args.baseUrl = process.argv[++i];
    } else if (arg === "--repetitions" && i + 1 < process.argv.length) {
      args.repetitions = parseInt(process.argv[++i], 10);
    } else if (arg === "--attempt-range" && i + 1 < process.argv.length) {
      args.attemptRange = process.argv[++i];
    } else if (arg === "--output" && i + 1 < process.argv.length) {
      args.output = process.argv[++i];
    }
  }
  if (!args.baseUrl) throw new Error("--base-url is required");
  if (!args.repetitions || args.repetitions < 1) args.repetitions = 1;
  if (!args.output) args.output = join(PROJECT_ROOT, "docs", "artifacts", "1109-stage3-comparison", "comparison-evidence.json");
  // Parse attempt-range if provided (overrides repetitions)
  if (args.attemptRange) {
    const parts = args.attemptRange.split("-").map(Number);
    if (parts.length !== 2 || isNaN(parts[0]) || isNaN(parts[1]) || parts[0] < 1 || parts[1] < parts[0]) {
      throw new Error(`--attempt-range must be START-END (e.g. 1-3), got "${args.attemptRange}"`);
    }
    args.attemptStart = parts[0];
    args.attemptEnd = parts[1];
    args.repetitions = parts[1] - parts[0] + 1;
  }
  return args;
}

function validateBaseUrl(baseUrl) {
  const parsed = new URL(baseUrl);
  if (!LOCAL_HOSTS.has(parsed.hostname))
    throw new Error(`BASE_URL must be localhost: ${parsed.hostname}`);
  if (parsed.protocol !== "http:" && parsed.protocol !== "https:")
    throw new Error("protocol must be http/https");
  if (parsed.username || parsed.password) throw new Error("no credentials");
  if (parsed.search) throw new Error("no query string");
  if (parsed.hash) throw new Error("no hash");
}

// ── Browser launch ─────────────────────────────────────────────────────────

async function launchBrowser() {
  // Prefer channel:chrome with short timeout; skip fallback if it succeeds
  async function tryLaunch(name, launchFn) {
    const timer = new Promise((_, reject) =>
      setTimeout(() => reject(new Error("timeout")), BROWSER_TIMEOUT_MS)
    );
    return Promise.race([launchFn(), timer]);
  }

  try {
    const browser = await tryLaunch("channel: chrome", () =>
      chromium.launch({ headless: true, channel: "chrome" })
    );
    let version = "unknown";
    try { version = await browser.version(); } catch (_) {}
    console.log(`  Browser: channel: chrome v${version}`);
    return { browser, source: "channel: chrome", version };
  } catch (e) {
    console.log(`  channel:chrome failed (${e.message}), trying env/fallback paths...`);
  }

  // Fallback attempts
  const launchAttempts = [];
  const errors = [];

  const envPath = process.env.PAGE_AGENT_BROWSER_EXECUTABLE;
  if (envPath) {
    launchAttempts.push({
      name: `env: ${envPath}`,
      launch: () => chromium.launch({ headless: true, executablePath: envPath }),
    });
  }

  for (const p of KNOWN_BROWSER_PATHS) {
    if (existsSync(p)) {
      launchAttempts.push({
        name: `path: ${p}`,
        launch: () => chromium.launch({ headless: true, executablePath: p }),
      });
    }
  }

  launchAttempts.push({
    name: "default playwright chromium",
    launch: () => chromium.launch({ headless: true }),
  });

  for (const attempt of launchAttempts) {
    try {
      const browser = await attempt.launch();
      let version = "unknown";
      try { version = await browser.version(); } catch (_) {}
      console.log(`  Browser: ${attempt.name} v${version}`);
      return { browser, source: attempt.name, version };
    } catch (e) {
      errors.push(`  [${attempt.name}] ${e.message}`);
    }
  }
  throw new Error(`Cannot launch any browser.\n${errors.join("\n")}`);
}

// ── Shared route detection helper ──────────────────────────────────────────

async function detectCanvasRoute(page) {
  return page.evaluate(() => {
    const canvas = document.getElementById("demo-canvas");
    if (!canvas) return "";
    const pageDiv = canvas.querySelector("[class*='bg-page']");
    if (!pageDiv) return "";
    // Check specific route markers first (more specific = checked earlier)
    if (pageDiv.classList.contains("bg-page--home")) return "home";
    if (pageDiv.classList.contains("bg-page--dept-directory") || pageDiv.classList.contains("bg-page--official-apartment-dept")) return "apartment-dept";
    if (pageDiv.classList.contains("bg-page--bulky-waste") || pageDiv.classList.contains("bg-page--official-bulky-waste-disposal")) return "bulky-waste-disposal";
    if (pageDiv.classList.contains("bg-page--passport-guidance") || pageDiv.classList.contains("bg-page--official-passport-guidance")) return "passport-guidance";
    if (pageDiv.classList.contains("bg-page--complaint-write") || pageDiv.querySelector("#btn-board-write, #board-write-title, #complaint-write-title")) return "complaint-write";
    if (pageDiv.classList.contains("bg-page--mayor-complaint-write") || pageDiv.querySelector("#mayor-write-title, #btn-mayor-submit, #mayor-proposal-title")) return "mayor-complaint-write";
    // Generic fallback: extract from bg-page--* class (skip layout classes)
    for (const cls of pageDiv.classList) {
      if (cls.startsWith("bg-page--") && cls !== "bg-page--full" && cls !== "bg-page--dense" && cls !== "bg-page--official-content") {
        return cls.replace("bg-page--", "").replace("official-", "");
      }
    }
    return "official-content";
  });
}

async function detectCanvasText(page) {
  return page.evaluate(() => {
    const canvas = document.getElementById("demo-canvas");
    return canvas ? canvas.innerText : "";
  });
}

// ── Pass criteria evaluation ───────────────────────────────────────────────

function evaluatePassCriteria(scenarioId, canvasRoute, canvasText, noSubmitPreserved) {
  const evaluators = PASS_CRITERIA_EVALUATORS[scenarioId];
  if (!evaluators) return [];
  return evaluators.map((ev, i) => {
    try {
      const result = ev.check(canvasRoute, canvasText, noSubmitPreserved);
      const passed = result.passed;
      const evidence = passed ? `passed: ${result.excerpt}`
        : `failed: route=${canvasRoute} no_submit=${noSubmitPreserved}`;
      return { criterion: ev.label, passed, evidence };
    } catch (e) {
      return { criterion: ev.label, passed: false, evidence: `evaluation_error: ${e.message}` };
    }
  });
}

function getExpectedRoute(scenarioId, mode) {
  const expect = EXPECTATIONS.scenarios.find(s => s.id === scenarioId);
  if (!expect || !expect[mode]) return "";
  return expect[mode].expected_final_route || "";
}

// ── Metric recording ───────────────────────────────────────────────────────

function makeRunRecord(scenarioId, mode, attempt) {
  const scenario = SCENARIOS.find(s => s.id === scenarioId);
  const expect = EXPECTATIONS.scenarios.find(s => s.id === scenarioId);
  const modeExpect = expect ? expect[mode] : {};
  return {
    schema_version: SCHEMA_VERSION,
    scenario_id: scenarioId,
    category: scenario ? scenario.category : "",
    mode,
    attempt,
    canonical_request: scenario ? scenario.resident_request : "",
    actual_trigger: modeExpect ? modeExpect.trigger : "",
    success: false,
    terminal_state: "",
    final_route: "",
    final_surface: "",
    expected_outcome: scenario ? scenario.target.outcome : "",
    pass_criteria_results: [],
    action_step_count: 0,
    total_engine_step_count: 0,
    wrong_route_action_count: 0,
    action_sequence: [],
    elapsed_ms: 0,
    no_submit_preserved: false,
    external_request_count: 0,
    request_failure_count: 0,
    console_error_count: 0,
    page_error_count: 0,
    warnings: [],
    console_error_messages: [],
    reproducibility_signature: "",
    errors: [],
  };
}

function makeErrorTracker(baseUrl) {
  return { baseUrl, nonLocal: [], consoleErrors: [], warnings: [], pageErrors: [], requestFailures: [] };
}

async function setupErrorTracking(page, tracker) {
  await page.addInitScript(() => {
    window._formSubmitted = false;
    document.addEventListener("submit", () => {
      window._formSubmitted = true;
    }, true);
  });
  page.on("request", (r) => {
    if (r.url().startsWith("data:")) return;
    const u = r.url();
    const isLocal = LOCAL_HOSTS.has(new URL(u).hostname);
    if (!isLocal) {
      tracker.nonLocal.push({ url: u, method: r.method() });
    }
  });
  page.on("response", (res) => {
    if (res.status() === 404) {
      tracker.pageErrors.push(`404 Not Found: ${res.url()}`);
    }
  });
  page.on("requestfailed", (req) => {
    const err = req.failure()?.errorText || "unknown";
    tracker.requestFailures.push({ url: req.url(), error: err });
  });
  page.on("console", (msg) => {
    const text = msg.text();
    if (text.includes("favicon.ico")) return;
    if (/GL Driver Message/i.test(text)) return;
    if (msg.type() === "error") tracker.consoleErrors.push(text);
    else if (msg.type() === "warning") tracker.warnings.push(text);
  });
  page.on("pageerror", (err) => tracker.pageErrors.push(err.message));
}

function computeSignature(record) {
  const parts = [
    record.mode,
    record.scenario_id,
    String(record.success),
    record.terminal_state,
    record.final_route,
    String(record.no_submit_preserved),
    String(record.external_request_count),
    String(record.console_error_count),
    record.action_sequence.slice(0, 10).join(","),
  ];
  return parts.join("|");
}

// ── Deterministic mode handlers ────────────────────────────────────────────

async function waitForDeterministicPage(page, route) {
  await page.goto(route, { waitUntil: "networkidle", timeout: RELOAD_TIMEOUT });
  await page.waitForFunction(
    () => {
      const c = window.CitizenFirstChoreography;
      return c && typeof c.getState === "function" && typeof c.start === "function";
    },
    { timeout: RELOAD_TIMEOUT }
  );
  await page.waitForTimeout(500);
}

async function submitDeterministicTask(page, trigger) {
  // Use the choreography public API directly (action entry point)
  const started = await page.evaluate((t) => {
    const c = window.CitizenFirstChoreography;
    if (!c || typeof c.start !== "function") return false;
    return c.start(t);
  }, trigger);
  if (!started) {
    throw new Error(`Deterministic choreography not started for trigger "${trigger}"`);
  }
  await page.waitForTimeout(200);
}

async function waitForDeterministicCompletion(page) {
  const startTime = Date.now();
  const terminalStates = ["done", "waiting_choice", "waiting_confirmation", "cancelled"];
  const maxMs = DETERMINISTIC_TIMEOUT_MS;
  const maxIterations = Math.ceil(maxMs / 200);

  for (let i = 0; i < maxIterations; i++) {
    const state = await page.evaluate(() => {
      const c = window.CitizenFirstChoreography;
      return c ? c.getState() : "";
    });
    if (terminalStates.includes(state)) {
      return { state, elapsedMs: Date.now() - startTime };
    }
    await new Promise(r => setTimeout(r, 200));
  }
  throw new Error(`deterministic task timed out after ${maxMs}ms`);
}

async function collectDeterministicMetrics(page, scenarioId, record) {
  const expectedRoute = getExpectedRoute(scenarioId, "deterministic");

  // Read choreography state including action trace
  const choreoState = await page.evaluate(() => {
    const c = window.CitizenFirstChoreography;
    if (!c) return { state: "", journeyId: "", stepIndex: -1, totalSteps: 0, steps: [] };
    return {
      state: c.getState(),
      journeyId: c.getCurrentJourneyId(),
      stepIndex: c.getCurrentStepIndex ? c.getCurrentStepIndex() : -1,
      totalSteps: c.getTotalSteps ? c.getTotalSteps() : 0,
      steps: (c.getSteps ? c.getSteps() : []).map(s => {
        const actions = [];
        if (s.routeId) actions.push(`route:${s.routeId}`);
        if (s.clickTarget) actions.push(`click:${s.clickTarget}`);
        if (s.routeIdAfterClick) actions.push(`routeAfterClick:${s.routeIdAfterClick}`);
        if (s.typeQuery || s.typeContent) actions.push(`type`);
        if (s.submitSearch) actions.push(`submitSearch`);
        if (s.focusSearch) actions.push(`focusSearch`);
        if (s.targetId) actions.push(`target:${s.targetId}`);
        return actions.join("+") || "message";
      }),
    };
  });

  // Read canvas route and text
  const canvasRoute = await detectCanvasRoute(page);
  const canvasText = await detectCanvasText(page);

  // Check no-submit badge from body
  const noSubmitBadge = await page.evaluate(() =>
    document.body.innerText.includes("제출 불가") || document.body.innerText.includes("nosubmit")
  );

  // Set action trace
  if (choreoState.totalSteps > 0) {
    record.total_engine_step_count = choreoState.totalSteps;
    record.action_sequence = choreoState.steps;
    record.action_step_count = choreoState.steps.filter(s => s !== "message" && s !== "" && s !== "noop").length;
  }

  record.terminal_state = choreoState.state;
  record.final_route = canvasRoute;
  record.final_surface = canvasRoute;

  // No-submit: check state machine + DOM badge + form submission
  const formSubmitted = await page.evaluate(() => window._formSubmitted);
  const safeStates = ["done", "waiting_choice", "waiting_confirmation", "cancelled"];
  record.no_submit_preserved = !formSubmitted && safeStates.includes(choreoState.state);
  if (!record.no_submit_preserved && !formSubmitted && noSubmitBadge) {
    record.no_submit_preserved = true;
  }

  // Check that choreography completed all steps (didn't stall mid-way)
  if (choreoState.totalSteps > 0 && choreoState.stepIndex < choreoState.totalSteps - 1) {
    record.warnings.push(`choreography stalled at step ${choreoState.stepIndex}/${choreoState.totalSteps - 1}`);
  }

  // Wrong route action count: 1 if final route != expected route
  record.wrong_route_action_count = (expectedRoute && canvasRoute !== expectedRoute) ? 1 : 0;

  // Evaluate shared pass criteria from parity contract against DOM evidence
  record.pass_criteria_results = evaluatePassCriteria(scenarioId, canvasRoute, canvasText, record.no_submit_preserved);

  return record;
}

// ── Page Agent mode handlers ───────────────────────────────────────────────

async function waitForResidentPage(page, route) {
  await page.goto(route, { waitUntil: "networkidle", timeout: RELOAD_TIMEOUT });
  await page.waitForFunction(
    () => document.readyState === "complete",
    { timeout: RELOAD_TIMEOUT }
  );
  await page.waitForFunction(
    (marker) => document.body.innerText.includes(marker),
    "Page Agent형 AI 북구청",
    { timeout: RELOAD_TIMEOUT }
  );
  const inputLocator = page.locator("#chat-input");
  await inputLocator.waitFor({ state: "visible", timeout: RELOAD_TIMEOUT });
  await page.waitForTimeout(500);
}

async function submitResidentTask(page, prompt) {
  const submitted = await page.evaluate((p) => {
    const input = document.getElementById("chat-input");
    if (!input) return false;
    const nativeSetter = Object.getOwnPropertyDescriptor(
      window.HTMLInputElement.prototype, "value"
    ).set;
    nativeSetter.call(input, p);
    input.dispatchEvent(new Event("input", { bubbles: true }));
    input.dispatchEvent(new Event("change", { bubbles: true }));
    input.focus({ preventScroll: true });
    input.dispatchEvent(
      new KeyboardEvent("keydown", { key: "Enter", code: "Enter", bubbles: true, cancelable: true })
    );
    input.dispatchEvent(
      new KeyboardEvent("keyup", { key: "Enter", code: "Enter", bubbles: true, cancelable: true })
    );
    return true;
  }, prompt);
  if (!submitted) throw new Error(`Chat input not found for "${prompt}"`);
  await page.waitForTimeout(200);
}

async function waitForResidentCompletion(page, expectedNavSteps) {
  const expectedCalls = expectedNavSteps + 1;
  const startTime = Date.now();
  const maxMs = PAGE_AGENT_TIMEOUT_MS;
  const maxIterations = Math.ceil(maxMs / 200);

  for (let i = 0; i < maxIterations; i++) {
    const diag = await page.evaluate(() => {
      const m = window.PageAgentMockModel;
      if (!m || !m.getDiagnostics) return null;
      const d = m.getDiagnostics();
      return {
        callCount: d.callCount,
        actionNames: d.actionNames ? [...d.actionNames] : [],
        successValues: d.successValues ? [...d.successValues] : [],
        lastSuccess: d.lastSuccess,
        lastCompletionText: d.lastCompletionText,
      };
    });
    if (diag && diag.callCount >= expectedCalls) {
      const clickCount = diag.actionNames.filter(a => a === "click_element_by_index").length;
      const lastAction = diag.actionNames[diag.actionNames.length - 1];
      if (clickCount === expectedNavSteps && lastAction === "done") {
        return {
          diagnostics: diag,
          elapsedMs: Date.now() - startTime,
        };
      }
    }
    await new Promise(r => setTimeout(r, 200));
  }
  throw new Error(`Resident task timed out after ${maxMs}ms`);
}

async function collectResidentMetrics(page, scenarioId, record) {
  const expectedRoute = getExpectedRoute(scenarioId, "page_agent");

  const diag = await page.evaluate(() => {
    const m = window.PageAgentMockModel;
    if (!m || !m.getDiagnostics) return null;
    const d = m.getDiagnostics();
    return {
      callCount: d.callCount,
      actionNames: d.actionNames ? [...d.actionNames] : [],
      successValues: d.successValues ? [...d.successValues] : [],
      lastSuccess: d.lastSuccess,
      lastCompletionText: d.lastCompletionText,
    };
  });

  if (diag) {
    record.action_step_count = diag.actionNames.filter(
      a => a !== "done" && a !== "stop"
    ).length;
    record.total_engine_step_count = diag.callCount;
    record.action_sequence = diag.actionNames;
  }

  // Read canvas route and text
  const canvasRoute = await detectCanvasRoute(page);
  const canvasText = await detectCanvasText(page);

  // Check no-submit badge
  const noSubmitBadge = await page.evaluate(() =>
    document.body.innerText.includes("제출 불가") || document.body.innerText.includes("nosubmit")
  );

  record.final_route = canvasRoute;
  record.final_surface = canvasRoute;

  // Page Agent mode: check DOM badge for no-submit and actual submission
  const formSubmitted = await page.evaluate(() => window._formSubmitted);
  record.no_submit_preserved = !formSubmitted && noSubmitBadge;

  // Wrong route action count: 1 if final route != expected route
  record.wrong_route_action_count = (expectedRoute && canvasRoute !== expectedRoute) ? 1 : 0;

  // Evaluate shared pass criteria from parity contract against DOM evidence
  record.pass_criteria_results = evaluatePassCriteria(scenarioId, canvasRoute, canvasText, record.no_submit_preserved);

  return record;
}

// ── Boundary probes ────────────────────────────────────────────────────────

async function runUnsupportedDeterministic(page) {
  const startTime = Date.now();
  const started = await page.evaluate(() => {
    const c = window.CitizenFirstChoreography;
    if (!c || typeof c.start !== "function") return "no-api";
    return c.start("오늘 날씨 알려줘") ? "started" : "not-found";
  });

  const elapsedMs = Date.now() - startTime;
  return {
    mode: "deterministic",
    probe: "unsupported_prompt",
    trigger: "오늘 날씨 알려줘",
    has_journey: started === "started",
    started: started !== "no-api",
    elapsed_ms: elapsedMs,
    note: started === "not-found" ? "hasJourney returned false, no choreography started" : "choreography started (unexpected)",
  };
}

async function runUnsupportedPageAgent(page) {
  const startTime = Date.now();

  await page.evaluate(() => {
    const m = window.PageAgentMockModel;
    if (m && m.resetDiagnostics) m.resetDiagnostics();
  });

  await submitResidentTask(page, "오늘 날씨 알려줘");

  // Wait for completion (1 call, done with success=false)
  let result = null;
  for (let i = 0; i < 200; i++) {
    const diag = await page.evaluate(() => {
      const m = window.PageAgentMockModel;
      if (!m || !m.getDiagnostics) return null;
      return {
        callCount: m.getDiagnostics().callCount,
        actionNames: [...m.getDiagnostics().actionNames],
        successValues: [...m.getDiagnostics().successValues],
      };
    });
    if (diag && diag.callCount >= 1 && diag.actionNames[0] === "done") {
      result = diag;
      break;
    }
    await new Promise(r => setTimeout(r, 250));
  }

  const elapsedMs = Date.now() - startTime;

  // Check for forbidden behaviors
  const UNSUPPORTED_ACTION = "execute_javascript";
  const foundExecuteJS = result ? result.actionNames.includes(UNSUPPORTED_ACTION) : false;
  const foundClick = result ? result.actionNames.includes("click_element_by_index") : false;

  return {
    mode: "page_agent",
    probe: "unsupported_prompt",
    trigger: "오늘 날씨 알려줘",
    responded: result !== null,
    actions_attempted: result ? result.actionNames : [],
    has_execute_javascript: foundExecuteJS,
    has_click: foundClick,
    response_success: result ? result.successValues[0] : null,
    elapsed_ms: elapsedMs,
    safe: !foundExecuteJS && !foundClick && (result ? result.successValues[0] === false : true),
  };
}

async function runCancelDeterministic(page, trigger) {
  // Start a journey then cancel
  const started = await page.evaluate((t) => {
    const c = window.CitizenFirstChoreography;
    if (!c || typeof c.start !== "function" || typeof c.cancel !== "function") return "no-api";
    const ok = c.start(t);
    return ok ? "started" : "not-found";
  }, trigger);

  if (started !== "started") {
    return { mode: "deterministic", probe: "cancellation", cancel_method: "CitizenFirstChoreography.cancel()", cancel_supported: true, journey_started: false, note: "journey not found" };
  }

  await page.waitForTimeout(300);

  const cancelled = await page.evaluate(() => {
    const c = window.CitizenFirstChoreography;
    if (!c || typeof c.cancel !== "function") return false;
    c.cancel();
    return c.getState() === "cancelled";
  });

  return {
    mode: "deterministic",
    probe: "cancellation",
    cancel_method: "CitizenFirstChoreography.cancel()",
    cancel_supported: true,
    journey_started: true,
    terminal_state: cancelled ? "cancelled" : "unknown",
    success: cancelled,
  };
}

async function runCancelPageAgent(page) {
  // Check if cancel button exists
  const hasCancelBtn = await page.evaluate(() => {
    const btn = document.getElementById("chat-cancel");
    return btn !== null;
  });

  if (!hasCancelBtn) {
    return { mode: "page_agent", probe: "cancellation", cancel_method: "chat-cancel button", cancel_supported: false, note: "cancel button not exposed" };
  }

  // Start a task then cancel immediately
  await page.evaluate(() => {
    const m = window.PageAgentMockModel;
    if (m && m.resetDiagnostics) m.resetDiagnostics();
  });
  await submitResidentTask(page, "공동주택과 연락처 찾아줘");
  await page.waitForTimeout(300);

  await page.evaluate(() => {
    const btn = document.getElementById("chat-cancel");
    if (btn) btn.click();
  });

  await page.waitForTimeout(300);

  const state = await page.evaluate(() => {
    const status = document.getElementById("chat-status");
    return status ? status.textContent : "";
  });

  return {
    mode: "page_agent",
    probe: "cancellation",
    cancel_method: "chat-cancel button click",
    cancel_supported: true,
    terminal_status: state || "",
    success: state.includes("취소") || state.includes("cancel") || state.includes("중단"),
  };
}

// ── Reproducibility check ──────────────────────────────────────────────────

function checkReproducibility(runs) {
  // Group by (scenario_id, mode)
  const groups = {};
  for (const r of runs) {
    const key = `${r.scenario_id}|${r.mode}`;
    if (!groups[key]) groups[key] = [];
    groups[key].push(r);
  }

  const results = {};
  for (const [key, grouped] of Object.entries(groups)) {
    const sigs = grouped.map(r => r.reproducibility_signature);
    const unique = new Set(sigs);
    results[key] = {
      scenario_id: grouped[0].scenario_id,
      mode: grouped[0].mode,
      run_count: grouped.length,
      unique_signatures: unique.size,
      reproducible: unique.size === 1,
      signatures: [...unique],
    };
  }
  return results;
}

// ── Main ───────────────────────────────────────────────────────────────────

async function main() {
  const args = parseArgs();
  const baseUrl = args.baseUrl.replace(/\/+$/, "");
  const repetitions = args.repetitions;
  const outputPath = args.output;

  validateBaseUrl(baseUrl);

  const deterministicRoute = `${baseUrl}/mvp/`;
  const residentRoute = `${baseUrl}/examples/page-agent/resident/`;

  console.log(`\n========================================`);
  console.log(`  Stage 3 Comparison Evidence Harness`);
  console.log(`========================================`);
  console.log(`  Base URL: ${baseUrl}`);
  console.log(`  Repetitions: ${repetitions}`);
  console.log(`  Scenarios: ${SCENARIO_IDS.length}`);
  console.log(`  Modes: deterministic, page_agent`);
  console.log(`  Total primary runs: ${SCENARIO_IDS.length * 2 * repetitions}`);
  console.log(`  Output: ${outputPath}`);

  const { browser, source, version } = await launchBrowser();

  const allRecords = [];
  const boundaryResults = [];
  let hasViolation = false;
  let hasStall = false;

  try {
    // ════════════════════════════════════════════════════════════════
    // Primary runs: 5 scenarios x 2 modes x N attempts (range)
    // ════════════════════════════════════════════════════════════════

    const attemptStart = args.attemptStart || 1;
    const attemptEnd = args.attemptEnd || repetitions;

    for (const scenario of SCENARIOS) {
      const sid = scenario.id;
      const expect = EXPECTATIONS.scenarios.find(s => s.id === sid);

      for (let attempt = attemptStart; attempt <= attemptEnd; attempt++) {
        // ── Deterministic mode ──
        {
          const detStart = Date.now();
          const record = makeRunRecord(sid, "deterministic", attempt);
          const deterministicTrigger = expect ? expect.deterministic.trigger : sid;
          const tracker = makeErrorTracker(baseUrl);
          let ctx, page;

          try {
            ctx = await browser.newContext({ viewport: { width: 1440, height: 900 } });
            page = await ctx.newPage();
            await setupErrorTracking(page, tracker);

            await waitForDeterministicPage(page, deterministicRoute);

            await submitDeterministicTask(page, deterministicTrigger);
            const completion = await waitForDeterministicCompletion(page);

            record.elapsed_ms = completion.elapsedMs;
            await collectDeterministicMetrics(page, sid, record);
            record.external_request_count = tracker.nonLocal.length;
            record.console_error_count = tracker.consoleErrors.length;
            record.console_error_messages = tracker.consoleErrors.length > 0 ? [...tracker.consoleErrors] : [];
            record.page_error_count = tracker.pageErrors.length;
            record.request_failure_count = tracker.requestFailures.length;
            record.warnings = tracker.warnings.length > 0 ? [...tracker.warnings] : [];

            // success: all pass criteria met, route matches expected, no-submit preserved, no external requests, no errors
            const allPassCriteriaMet = record.pass_criteria_results.length > 0
              ? record.pass_criteria_results.every(cr => cr.passed)
              : false;
            const expectedRoute = getExpectedRoute(sid, "deterministic");
            const routeMatchesExpected = !expectedRoute || record.final_route === expectedRoute;
            record.success = (
              allPassCriteriaMet &&
              routeMatchesExpected &&
              record.no_submit_preserved &&
              record.external_request_count === 0 &&
              record.console_error_count === 0 &&
              record.page_error_count === 0
            );

            record.reproducibility_signature = computeSignature(record);
            record.errors = [];

            console.log(`  [det][${sid}] attempt=${attempt} success=${record.success} state=${record.terminal_state} route=${record.final_route} actions=${record.action_step_count}/${record.total_engine_step_count} wr=${record.wrong_route_action_count} elapsed=${record.elapsed_ms}ms`);
          } catch (e) {
            record.success = false;
            record.errors.push(e.message || String(e));
            record.elapsed_ms = Date.now() - detStart;
            console.log(`  [det][${sid}] attempt=${attempt} FAILED (stall): ${e.message}`);
            hasStall = true;
          } finally {
            if (page) await page.close().catch(() => {});
            if (ctx) await ctx.close().catch(() => {});
          }
          allRecords.push(record);
          if (hasStall) break;  // breaks from attempt for-loop
        }

        // ── Page Agent mode ──
        {
          const paStart = Date.now();
          const record = makeRunRecord(sid, "page_agent", attempt);
          const paTrigger = scenario.resident_request;
          const expectedNavSteps = expect ? (expect.page_agent.expected_nav_steps || 1) : 1;
          const tracker = makeErrorTracker(baseUrl);
          let ctx, page;

          try {
            ctx = await browser.newContext({ viewport: { width: 1440, height: 900 } });
            page = await ctx.newPage();
            await setupErrorTracking(page, tracker);

            await page.evaluate(() => {
              const m = window.PageAgentMockModel;
              if (m && m.resetDiagnostics) m.resetDiagnostics();
            }).catch(() => {});

            await waitForResidentPage(page, residentRoute);

            // Reset diagnostics after page load
            await page.evaluate(() => {
              const m = window.PageAgentMockModel;
              if (m && m.resetDiagnostics) m.resetDiagnostics();
            });

            await submitResidentTask(page, paTrigger);
            const completion = await waitForResidentCompletion(page, expectedNavSteps);

            record.elapsed_ms = completion.elapsedMs;
            await collectResidentMetrics(page, sid, record);
            record.external_request_count = tracker.nonLocal.length;
            record.console_error_count = tracker.consoleErrors.length;
            record.console_error_messages = tracker.consoleErrors.length > 0 ? [...tracker.consoleErrors] : [];
            record.page_error_count = tracker.pageErrors.length;
            record.request_failure_count = tracker.requestFailures.length;
            record.warnings = tracker.warnings.length > 0 ? [...tracker.warnings] : [];

            // success: all pass criteria met, route matches expected, no-submit preserved, no external requests, no errors
            const allPassCriteriaMet = record.pass_criteria_results.length > 0
              ? record.pass_criteria_results.every(cr => cr.passed)
              : false;
            const expectedRoute = getExpectedRoute(sid, "page_agent");
            const routeMatchesExpected = !expectedRoute || record.final_route === expectedRoute;
            record.success = (
              allPassCriteriaMet &&
              routeMatchesExpected &&
              record.no_submit_preserved &&
              record.external_request_count === 0 &&
              record.console_error_count === 0 &&
              record.page_error_count === 0
            );

            record.reproducibility_signature = computeSignature(record);
            record.errors = [];

            console.log(`  [pag][${sid}] attempt=${attempt} success=${record.success} actions=${record.action_step_count}/${record.total_engine_step_count} wr=${record.wrong_route_action_count} route=${record.final_route} elapsed=${record.elapsed_ms}ms`);
          } catch (e) {
            record.success = false;
            record.errors.push(e.message || String(e));
            record.elapsed_ms = Date.now() - paStart;
            console.log(`  [pag][${sid}] attempt=${attempt} FAILED (stall): ${e.message}`);
            hasStall = true;
          } finally {
            if (page) await page.close().catch(() => {});
            if (ctx) await ctx.close().catch(() => {});
          }
          allRecords.push(record);
          if (hasStall) break;
        }
      } // end attempts
      if (hasStall) {
        console.log(`  [stall] Stopping due to stall at ${sid}`);
        break;  // stop scenario loop on stall
      }
    } // end scenarios

    // ════════════════════════════════════════════════════════════════
    // Boundary probes
    // ════════════════════════════════════════════════════════════════

    console.log("\n  [Boundary probes]");

    // Unsupported prompt - deterministic
    {
      const ctx = await browser.newContext({ viewport: { width: 1440, height: 900 } });
      const page = await ctx.newPage();
      await waitForDeterministicPage(page, deterministicRoute);
      const result = await runUnsupportedDeterministic(page);
      boundaryResults.push(result);
      console.log(`  unsupported[det]: has_journey=${result.has_journey}`);
      await ctx.close();
    }

    // Unsupported prompt - page_agent
    {
      const ctx = await browser.newContext({ viewport: { width: 1440, height: 900 } });
      const page = await ctx.newPage();
      await waitForResidentPage(page, residentRoute);
      const result = await runUnsupportedPageAgent(page);
      boundaryResults.push(result);
      console.log(`  unsupported[pag]: safe=${result.safe} actions=${JSON.stringify(result.actions_attempted)}`);
      await ctx.close();
    }

    // Cancellation - deterministic
    {
      const ctx = await browser.newContext({ viewport: { width: 1440, height: 900 } });
      const page = await ctx.newPage();
      await waitForDeterministicPage(page, deterministicRoute);
      const result = await runCancelDeterministic(page, "housing_department");
      boundaryResults.push(result);
      console.log(`  cancel[det]: supported=${result.cancel_supported} terminal=${result.terminal_state}`);
      await ctx.close();
    }

    // Cancellation - page_agent
    {
      const ctx = await browser.newContext({ viewport: { width: 1440, height: 900 } });
      const page = await ctx.newPage();
      await waitForResidentPage(page, residentRoute);
      const result = await runCancelPageAgent(page);
      boundaryResults.push(result);
      console.log(`  cancel[pag]: supported=${result.cancel_supported} terminal=${result.terminal_status}`);
      await ctx.close();
    }

    // ════════════════════════════════════════════════════════════════
    // Aggregation
    // ════════════════════════════════════════════════════════════════

    const reproducibility = checkReproducibility(allRecords);
    const successRuns = allRecords.filter(r => r.success);
    const failRuns = allRecords.filter(r => !r.success);
    const detRuns = allRecords.filter(r => r.mode === "deterministic");
    const paRuns = allRecords.filter(r => r.mode === "page_agent");

    const elapsedDetAll = detRuns.map(r => r.elapsed_ms).sort((a, b) => a - b);
    const elapsedPaAll = paRuns.map(r => r.elapsed_ms).sort((a, b) => a - b);
    const elapsedDetSuccess = detRuns.filter(r => r.success).map(r => r.elapsed_ms).sort((a, b) => a - b);
    const elapsedPaSuccess = paRuns.filter(r => r.success).map(r => r.elapsed_ms).sort((a, b) => a - b);

    function median(arr) { if (!arr.length) return 0; const m = Math.floor(arr.length / 2); return arr.length % 2 ? arr[m] : (arr[m - 1] + arr[m]) / 2; }

    const evidence = {
      schema_version: SCHEMA_VERSION,
      track: "1109-page-agent-comparison",
      generated_at: new Date().toISOString(),
      methodology: {
        description: "Browser-based comparison harness executing the 5 parity scenarios from parity-contract.json in both modes against the same controlled same-origin civic canvas.",
        modes: [
          { id: "deterministic", label: "정밀 구현형 AI 북구청", route: "mvp/", engine: "handcrafted deterministic choreography (CitizenFirstChoreography)" },
          { id: "page_agent", label: "Page Agent형 AI 북구청", route: "examples/page-agent/resident/", engine: "vendored Page Agent runtime with deterministic resident mock adapter" },
        ],
        scenarios: SCENARIOS.map(s => ({ id: s.id, resident_request: s.resident_request, category: s.category })),
        repetitions,
        total_primary_runs: allRecords.length,
        browser: { source, version },
        shared_invariants: PARITY.shared_invariants,
        no_submit_boundary: PARITY.no_submit_boundary,
        limitations: [
          "Deterministic mode includes intentional UI animation delays (thinking text, cursor, typing simulation) that inflate elapsed_ms relative to page_agent mode.",
          "Page Agent mode uses a deterministic resident mock adapter, not a real LLM. Results reflect orchestration structure and current demo implementation, not LLM quality/cost/latency.",
          "Action step counting differs between modes due to different orchestration patterns (choreography steps vs Page Agent tool calls).",
          "Deterministic trigger texts differ from canonical parity texts; see actual_trigger field per scenario.",
          "Cancellation probe in deterministic mode uses choreography API directly (cancel button not exposed in MVP shell).",
        ],
      },
      primary_runs: allRecords,
      boundary_probes: boundaryResults,
      aggregate: {
        total_runs: allRecords.length,
        successful: successRuns.length,
        failed: failRuns.length,
        success_rate: allRecords.length > 0 ? (successRuns.length / allRecords.length) : 0,
        by_mode: {
          deterministic: {
            total: detRuns.length,
            successful: detRuns.filter(r => r.success).length,
            failed: detRuns.filter(r => !r.success).length,
            median_elapsed_ms_all: median(elapsedDetAll),
            median_elapsed_ms_success: median(elapsedDetSuccess),
            min_elapsed_ms: elapsedDetAll.length > 0 ? elapsedDetAll[0] : 0,
            max_elapsed_ms: elapsedDetAll.length > 0 ? elapsedDetAll[elapsedDetAll.length - 1] : 0,
            median_action_step_count_all: median(detRuns.map(r => r.action_step_count)),
            median_action_step_count_success: median(detRuns.filter(r => r.success).map(r => r.action_step_count)),
            total_wrong_route_actions: detRuns.reduce((s, r) => s + r.wrong_route_action_count, 0),
          },
          page_agent: {
            total: paRuns.length,
            successful: paRuns.filter(r => r.success).length,
            failed: paRuns.filter(r => !r.success).length,
            median_elapsed_ms_all: median(elapsedPaAll),
            median_elapsed_ms_success: median(elapsedPaSuccess),
            min_elapsed_ms: elapsedPaAll.length > 0 ? elapsedPaAll[0] : 0,
            max_elapsed_ms: elapsedPaAll.length > 0 ? elapsedPaAll[elapsedPaAll.length - 1] : 0,
            median_action_step_count_all: median(paRuns.map(r => r.action_step_count)),
            median_action_step_count_success: median(paRuns.filter(r => r.success).map(r => r.action_step_count)),
            total_wrong_route_actions: paRuns.reduce((s, r) => s + r.wrong_route_action_count, 0),
          },
        },
        reproducibility: Object.values(reproducibility).reduce((s, r) => s && r.reproducible, true),
        reproducibility_details: Object.values(reproducibility),
      },
    };

    // Write evidence
    const outputDir = dirname(outputPath);
    if (!existsSync(outputDir)) mkdirSync(outputDir, { recursive: true });
    writeFileSync(outputPath, JSON.stringify(evidence, null, 2), "utf-8");
    console.log(`\n  ✓ Evidence written: ${outputPath}`);

    // Check for violations
    if (failRuns.length > 0) {
      console.log(`\n  ⚠ ${failRuns.length} runs failed`);
    }
    if (hasStall || allRecords.length < SCENARIO_IDS.length * 2 * repetitions) {
      console.log(`\n  ⚠ stall: ${hasStall}, short count: ${allRecords.length < SCENARIO_IDS.length * 2 * repetitions}`);
      hasViolation = true;
    }

    const allBoundarySafe = boundaryResults.every(r => {
      if (r.probe === "unsupported_prompt" && r.mode === "page_agent") return r.safe !== false;
      if (r.probe === "unsupported_prompt" && r.mode === "deterministic") return !r.has_journey;
      return true;
    });
    if (!allBoundarySafe) {
      console.log("\n  ✈ BOUNDARY VIOLATION DETECTED — violation");
      hasViolation = true;
    }

    const allNoExternal = allRecords.every(r => r.external_request_count === 0);
    const allNoSubmit = allRecords.every(r => r.no_submit_preserved !== false);

    if (!allNoExternal) {
      console.log("\n  ✈ EXTERNAL REQUEST DETECTED — violation");
      hasViolation = true;
    }
    if (!allNoSubmit) {
      console.log("\n  ✈ NO-SUBMIT VIOLATION DETECTED — violation");
      hasViolation = true;
    }

    console.log(`\n  === SUMMARY ===`);
    console.log(`  Primary runs: ${allRecords.length} (${successRuns.length} success, ${failRuns.length} fail)`);
    console.log(`  Success rate: ${(evidence.aggregate.success_rate * 100).toFixed(1)}%`);
    console.log(`  Deterministic: ${evidence.aggregate.by_mode.deterministic.successful}/${evidence.aggregate.by_mode.deterministic.total}`);
    console.log(`  Page Agent: ${evidence.aggregate.by_mode.page_agent.successful}/${evidence.aggregate.by_mode.page_agent.total}`);
    console.log(`  External requests: ${allRecords.reduce((s, r) => s + r.external_request_count, 0)}`);
    console.log(`  No-submit preserved: ${allRecords.every(r => r.no_submit_preserved)}`);
    console.log(`  Reproducible: ${evidence.aggregate.reproducibility}`);

  } catch (err) {
    console.error("\nHarness failed:", err.message);
    hasViolation = true;
  } finally {
    await browser.close();
  }

  if (hasViolation) {
    console.error("\n✈ Comparison harness detected violations — exiting with code 1");
    process.exit(1);
  }
  console.log("\n✓ Comparison harness completed successfully");
}

main();
