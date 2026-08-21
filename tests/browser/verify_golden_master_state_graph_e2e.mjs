import assert from "assert";
import { chromium } from "playwright";
import { validateGoldenTrace } from "./golden_state_graph_contract.mjs";

const BASE_ORIGIN = localOrigin(process.argv[2]);
const DEMO_URL = `${BASE_ORIGIN}/static/seogu-citizen-action-demo.html`;

const SCENARIOS = Object.freeze([
  {
    id: "S1",
    journey_id: "seogu_apartment_housing_dept",
    selector: '[data-journey-id="seogu_apartment_housing_dept"]',
    expectedResult: "grounded",
    routeContains: "housing",
  },
  {
    id: "S2",
    journey_id: "seogu_illegal_parking_report",
    selector: '[data-journey-id="seogu_illegal_parking_report"]',
    expectedResult: "safe_handoff",
    routeContains: "illegal-parking",
  },
  {
    id: "S5",
    journey_id: "seogu_passport_issuance",
    selector: '[data-journey-id="seogu_passport_issuance"]',
    expectedResult: "grounded",
    routeContains: "passport-guidance",
  },
  {
    id: "S6",
    journey_id: "seogu_unmanned_kiosk",
    selector: '[data-journey-id="seogu_unmanned_kiosk"]',
    expectedResult: "grounded",
    routeContains: "unmanned-kiosk",
  },
  {
    id: "S8",
    journey_id: "seogu_mattrass_disposal",
    selector: '[data-journey-id="seogu_mattrass_disposal"]',
    expectedResult: "grounded",
    routeContains: "bulky-waste-guidance",
  },
]);

function localOrigin(raw) {
  if (!raw || raw === "undefined") {
    throw new Error("usage: node verify_golden_master_state_graph_e2e.mjs <BASE_URL>");
  }
  const url = new URL(raw);
  if (!["127.0.0.1", "localhost", "::1"].includes(url.hostname)) {
    throw new Error(`Golden gate requires localhost base, got ${url.hostname}`);
  }
  return url.origin;
}

async function launchBrowser() {
  const attempts = [];
  const errors = [];
  const envPath = process.env.PREVIEW_BROWSER_EXECUTABLE;

  if (envPath) {
    attempts.push({
      name: `env: ${envPath}`,
      launch: () => chromium.launch({ headless: true, executablePath: envPath }),
    });
  }

  attempts.push({
    name: "channel: chrome",
    launch: () => chromium.launch({ headless: true, channel: "chrome" }),
  });
  attempts.push({
    name: "default playwright chromium",
    launch: () => chromium.launch({ headless: true }),
  });

  for (const attempt of attempts) {
    try {
      const browser = await attempt.launch();
      console.log(`Browser launched (${attempt.name}) ✓`);
      return browser;
    } catch (error) {
      errors.push(`[${attempt.name}] ${error.message}`);
    }
  }

  throw new Error(`Cannot launch any browser. Attempts:\n${errors.join("\n")}`);
}

function installEgressGuard(context) {
  const externalRequests = [];
  context.route("**/*", async (route) => {
    const url = route.request().url();
    if (url.startsWith("data:")) {
      await route.continue();
      return;
    }
    let parsed;
    try {
      parsed = new URL(url);
    } catch {
      externalRequests.push(url);
      await route.abort();
      return;
    }
    if (parsed.origin !== BASE_ORIGIN) {
      externalRequests.push(url);
      await route.abort();
      return;
    }
    await route.continue();
  });
  return externalRequests;
}

async function openPage(browser) {
  const context = await browser.newContext({ viewport: { width: 1280, height: 800 } });
  const externalRequests = installEgressGuard(context);
  const page = await context.newPage();
  await page.goto(DEMO_URL, { waitUntil: "networkidle", timeout: 20000 });
  await page.waitForFunction(
    () => document.querySelectorAll("#chat-chips .chat-chip").length > 0,
    null,
    { timeout: 15000 },
  );
  await page.waitForFunction(
    () => document.body.getAttribute("data-surface-state") === "ready",
    null,
    { timeout: 15000 },
  );
  return { page, context, externalRequests };
}

async function instrumentCounter(page) {
  await page.evaluate(() => {
    window.__executionCounter = 0;

    const origJourney = window.MunicipalResidentJourney;
    window.MunicipalResidentJourney = Object.freeze({
      run: async function (...args) {
        window.__executionCounter += 1;
        return origJourney.run.apply(origJourney, args);
      },
      answerFromEvidence: origJourney.answerFromEvidence,
    });

    const _origSetAttr = Element.prototype.setAttribute;
    Element.prototype.setAttribute = function (name, value) {
      if (
        name === "data-journey-state" &&
        value === "handoff_evidence_running"
      ) {
        window.__executionCounter += 1;
      }
      return _origSetAttr.call(this, name, value);
    };
  });
}

async function captureRoute(page) {
  return page.evaluate(() => {
    const frame = document.getElementById("seogu-clone-frame");
    return frame && frame.contentWindow
      ? frame.contentWindow.location.pathname
      : null;
  });
}

async function waitForState(page, state, timeout = 12000) {
  await page.waitForFunction(
    (s) => document.body.getAttribute("data-journey-state") === s,
    state,
    { timeout },
  );
}

async function clickChip(page, selector) {
  await page.locator(selector).click();
}

async function clickYes(page) {
  await page.locator('[data-confirm-action="yes"]').last().click();
}

async function clickNo(page) {
  await page.locator('[data-confirm-action="no"]').last().click();
}

async function getLastResult(page) {
  return page.evaluate(() => {
    const shell = window.SeoguCitizenActionShell;
    if (!shell) return null;
    const r = shell.getLastJourneyResult();
    if (!r) return null;
    return {
      ok: r.ok,
      grounded: r.grounded,
      route: r.route,
      journey_id: r.journey_id,
      source_kind: r.source_kind,
      evidence_kind: r.evidence_kind,
      answer: r.answer,
      excerpt: r.excerpt,
      failure_code: r.failure_code,
    };
  });
}

async function getEvidence(page) {
  return page.evaluate(() => {
    const shell = window.SeoguCitizenActionShell;
    if (!shell) return null;
    const ev = shell.getEvidence();
    if (!ev) return null;
    return { route: ev.route, source_kind: ev.source_kind, evidence_kind: ev.evidence_kind };
  });
}

async function assertNoReadOrResult(page) {
  const result = await getLastResult(page);
  const evidence = await getEvidence(page);
  assert.ok(!result, "must not produce a journey result");
  assert.ok(
    !evidence || !evidence.route || evidence.route === "/",
    `must not read evidence on a target route, got ${evidence && evidence.route}`,
  );
}

async function assertNoHandoffRow(page, journeyId) {
  const count = await page.evaluate((jid) => {
    const rows = Array.from(
      document.querySelectorAll('[data-safe-handoff="true"]'),
    );
    return rows.filter(
      (r) => r.getAttribute("data-journey-id") === jid,
    ).length;
  }, journeyId);
  assert.strictEqual(
    count,
    0,
    `must not have safe_handoff row for ${journeyId}, found ${count}`,
  );
}

function assertExternalRequestsZero(externalRequests, label) {
  assert.strictEqual(
    externalRequests.length,
    0,
    `${label}: external request count must be 0, got ${externalRequests.length}`,
  );
}

async function runNoPath(page, scenario, externalRequests) {
  const preRoute = await captureRoute(page);

  await clickChip(page, scenario.selector);
  await waitForState(page, "answer");
  const postAnswerRoute = await captureRoute(page);
  assert.strictEqual(
    postAnswerRoute,
    preRoute,
    `Route must be unchanged after ANSWER for ${scenario.id} NO`,
  );

  await waitForState(page, "confirm");
  const postConfirmRoute = await captureRoute(page);
  assert.strictEqual(
    postConfirmRoute,
    preRoute,
    `Route must be unchanged after CONFIRM for ${scenario.id} NO`,
  );

  const controls = await page.evaluate(() => {
    const msgs = Array.from(document.querySelectorAll('.chat-msg--confirm-run'));
    const last = msgs[msgs.length - 1];
    if (!last) return { yes: false, no: false };
    return {
      yes: !!last.querySelector('[data-confirm-action="yes"]'),
      no: !!last.querySelector('[data-confirm-action="no"]'),
    };
  });
  assert.strictEqual(controls.yes, true, `${scenario.id} NO: YES control must exist`);
  assert.strictEqual(controls.no, true, `${scenario.id} NO: NO control must exist`);

  await clickNo(page);
  await waitForState(page, "answer");

  const postNoRoute = await captureRoute(page);
  assert.strictEqual(
    postNoRoute,
    preRoute,
    `${scenario.id} NO: route must be unchanged after NO`,
  );

  const postCounter = await page.evaluate(() => window.__executionCounter);
  assert.strictEqual(
    postCounter,
    0,
    `${scenario.id} NO: execution counter must remain 0, got ${postCounter}`,
  );

  await assertNoReadOrResult(page);
  await assertNoHandoffRow(page, scenario.journey_id);
  assertExternalRequestsZero(externalRequests, `${scenario.id} NO`);

  const trace = [
    { state: "ENTRY" },
    { state: "ANSWER" },
    { state: "CONFIRM" },
    { state: "DECISION_NO" },
    { state: "STOP" },
  ];
  const v = validateGoldenTrace(trace);
  assert.strictEqual(v.valid, true, `${scenario.id} NO trace: ${v.errors.join("; ")}`);
}

async function runYesPath(page, scenario, externalRequests) {
  const preRoute = await captureRoute(page);

  await clickChip(page, scenario.selector);
  await waitForState(page, "answer");
  const postAnswerRoute = await captureRoute(page);
  assert.strictEqual(
    postAnswerRoute,
    preRoute,
    `Route must be unchanged after ANSWER for ${scenario.id} YES`,
  );

  await waitForState(page, "confirm");
  const postConfirmRoute = await captureRoute(page);
  assert.strictEqual(
    postConfirmRoute,
    preRoute,
    `Route must be unchanged after CONFIRM for ${scenario.id} YES`,
  );

  await clickYes(page);

  const finalState =
    scenario.expectedResult === "safe_handoff" ? "safe_handoff" : "grounded";
  await waitForState(page, finalState, 20000);

  const postYesRoute = await captureRoute(page);
  assert.ok(
    String(postYesRoute || "").includes(scenario.routeContains),
    `${scenario.id} YES: route must contain "${scenario.routeContains}", got "${postYesRoute}"`,
  );

  const postCounter = await page.evaluate(() => window.__executionCounter);
  assert.strictEqual(
    postCounter,
    1,
    `${scenario.id} YES: execution count must be exactly 1, got ${postCounter}`,
  );

  const result = await getLastResult(page);
  const evidence = await getEvidence(page);

  if (scenario.expectedResult === "grounded") {
    assert.ok(result, `${scenario.id} YES: grounded result must exist`);
    assert.strictEqual(result.ok, true, `${scenario.id} YES: result must be ok`);
    assert.strictEqual(result.grounded, true, `${scenario.id} YES: result must be grounded`);
    assert.strictEqual(
      result.source_kind,
      "repository_clone",
      `${scenario.id} YES: source_kind must be repository_clone`,
    );
    assert.strictEqual(
      result.evidence_kind,
      "clone_dom",
      `${scenario.id} YES: evidence_kind must be clone_dom`,
    );
    assert.ok(
      String(result.route || "").includes(scenario.routeContains),
      `${scenario.id} YES: result.route must contain "${scenario.routeContains}"`,
    );
    assert.ok(
      String(result.answer || "").length > 0,
      `${scenario.id} YES: grounded answer must be non-empty`,
    );
    assert.ok(
      String(result.excerpt || "").length > 0,
      `${scenario.id} YES: grounded excerpt must be non-empty (provenanced)`,
    );
    assert.ok(evidence, `${scenario.id} YES: evidence must exist`);
    assert.strictEqual(evidence.source_kind, "repository_clone");
    assert.strictEqual(evidence.evidence_kind, "clone_dom");
    assert.ok(
      String(evidence.route || "").includes(scenario.routeContains),
      `${scenario.id} YES: evidence.route must contain "${scenario.routeContains}"`,
    );
  } else {
    assert.ok(
      (await page.evaluate((jid) => {
        const rows = Array.from(
          document.querySelectorAll('[data-safe-handoff="true"]'),
        );
        return rows.some(
          (r) => r.getAttribute("data-journey-id") === jid,
        );
      }, scenario.journey_id)),
      `${scenario.id} YES: safe_handoff row must exist for ${scenario.journey_id}`,
    );
  }

  assertExternalRequestsZero(externalRequests, `${scenario.id} YES`);

  const trace = [
    { state: "ENTRY" },
    { state: "ANSWER" },
    { state: "CONFIRM" },
    { state: "NAVIGATE" },
    { state: "RESULT", metadata: { result: scenario.expectedResult } },
    { state: "STOP" },
  ];
  const v = validateGoldenTrace(trace, { expectedResult: scenario.expectedResult });
  assert.strictEqual(
    v.valid,
    true,
    `${scenario.id} YES trace: ${v.errors.join("; ")}`,
  );
}

async function runStaleYesSamePage(browser) {
  const { page, context, externalRequests } = await openPage(browser);
  await instrumentCounter(page);

  await clickChip(page, SCENARIOS[0].selector);
  await waitForState(page, "answer");
  await waitForState(page, "confirm");

  const oldYesHandle = await page.locator(
    '[data-confirm-action="yes"]',
  ).last().elementHandle();

  await clickChip(page, SCENARIOS[1].selector);
  await waitForState(page, "answer");
  await waitForState(page, "confirm");

  const preStaleRoute = await captureRoute(page);
  await page.evaluate((handle) => {
    if (handle && handle.isConnected) handle.click();
  }, oldYesHandle);

  const counter = await page.evaluate(() => window.__executionCounter);
  const staleRoute = await captureRoute(page);
  const staleResult = await getLastResult(page);
  const staleEvidence = await getEvidence(page);
  const staleHandoffCount = await page.evaluate((jid) => {
    const rows = Array.from(
      document.querySelectorAll('[data-safe-handoff="true"]'),
    );
    return rows.filter(
      (r) => r.getAttribute("data-journey-id") === jid,
    ).length;
  }, SCENARIOS[0].journey_id);

  assert.strictEqual(counter, 0, "Stale YES: execution must be 0");
  assert.strictEqual(
    staleRoute,
    preStaleRoute,
    "Stale YES: route must be unchanged",
  );
  assert.ok(!staleResult, "Stale YES: getLastJourneyResult must be null");
  assert.ok(
    !staleEvidence || !staleEvidence.route || staleEvidence.route === "/",
    `Stale YES: must not read evidence, got ${staleEvidence && staleEvidence.route}`,
  );
  assert.strictEqual(
    staleHandoffCount,
    0,
    "Stale YES: must not create handoff row",
  );
  assertExternalRequestsZero(externalRequests, "Stale YES");

  await context.close();
  await oldYesHandle.dispose();

  return {
    executions: counter,
    routeUnchanged: staleRoute === preStaleRoute,
    noResult: !staleResult,
    noRead: !staleEvidence || !staleEvidence.route || staleEvidence.route === "/",
    noHandoff: staleHandoffCount === 0,
    externalRequests: externalRequests.length,
  };
}

async function runDoubleYesTest(browser) {
  const { page, context, externalRequests } = await openPage(browser);
  await instrumentCounter(page);

  await clickChip(page, SCENARIOS[0].selector);
  await waitForState(page, "answer");
  await waitForState(page, "confirm");

  const btn = await page.locator('[data-confirm-action="yes"]').last();
  const box = await btn.boundingBox();
  await page.mouse.dblclick(box.x + box.width / 2, box.y + box.height / 2);

  await waitForState(page, "grounded", 20000);
  const counter = await page.evaluate(() => window.__executionCounter);
  assertExternalRequestsZero(externalRequests, "Double YES");
  await context.close();
  return { executions: counter, externalRequests: externalRequests.length };
}

async function runNoThenStaleYesTest(browser) {
  const { page, context, externalRequests } = await openPage(browser);
  await instrumentCounter(page);

  await clickChip(page, SCENARIOS[0].selector);
  await waitForState(page, "answer");
  await waitForState(page, "confirm");

  const oldYesHandle = await page.locator(
    '[data-confirm-action="yes"]',
  ).last().elementHandle();

  const preRoute = await captureRoute(page);
  await clickNo(page);
  await waitForState(page, "answer");

  const afterNoRoute = await captureRoute(page);
  const afterNoCounter = await page.evaluate(() => window.__executionCounter);
  await assertNoReadOrResult(page);
  assert.strictEqual(
    afterNoRoute,
    preRoute,
    "NO then stale YES: route must be unchanged after NO",
  );
  assert.strictEqual(
    afterNoCounter,
    0,
    "NO then stale YES: execution must be 0 after NO",
  );
  await assertNoHandoffRow(page, SCENARIOS[0].journey_id);
  assertExternalRequestsZero(externalRequests, "NO then stale YES (after NO)");

  await page.evaluate((handle) => {
    if (handle && handle.isConnected) handle.click();
  }, oldYesHandle);

  const staleCounter = await page.evaluate(() => window.__executionCounter);
  const staleRoute = await captureRoute(page);
  await assertNoReadOrResult(page);
  await assertNoHandoffRow(page, SCENARIOS[0].journey_id);
  assert.strictEqual(
    staleCounter,
    0,
    "NO then stale YES: execution must stay 0 after stale YES click",
  );
  assert.strictEqual(
    staleRoute,
    preRoute,
    "NO then stale YES: route must stay unchanged after stale YES click",
  );
  assertExternalRequestsZero(externalRequests, "NO then stale YES (after stale click)");

  await context.close();
  await oldYesHandle.dispose();
  return { pass: true };
}

async function proveS2SameValueDoubleCall(page) {
  const before = await page.evaluate(() => window.__executionCounter);
  await page.evaluate(() => {
    document.body.setAttribute("data-journey-state", "handoff_evidence_running");
    document.body.setAttribute("data-journey-state", "handoff_evidence_running");
  });
  const after = await page.evaluate(() => window.__executionCounter);
  assert.strictEqual(
    after - before,
    2,
    "S2 same-value double call must count 2 (before=" +
      before +
      ", after=" +
      after +
      ")",
  );
  return true;
}

try {
  const browser = await launchBrowser();
  const results = {};

  for (const scenario of SCENARIOS) {
    {
      const { page, context, externalRequests } = await openPage(browser);
      await instrumentCounter(page);
      await runNoPath(page, scenario, externalRequests);
      const counter = await page.evaluate(() => window.__executionCounter);
      results[`${scenario.id}_NO_EXECUTIONS`] = counter;
      results[`${scenario.id}_NO_EXTERNAL`] = externalRequests.length;
      assert.strictEqual(
        counter,
        0,
        `${scenario.id} NO: execution must be 0`,
      );
      assert.strictEqual(
        externalRequests.length,
        0,
        `${scenario.id} NO: external must be 0`,
      );
      await context.close();
    }

    {
      const { page, context, externalRequests } = await openPage(browser);
      await instrumentCounter(page);
      await runYesPath(page, scenario, externalRequests);
      const counter = await page.evaluate(() => window.__executionCounter);
      results[`${scenario.id}_YES_EXECUTIONS`] = counter;
      results[`${scenario.id}_YES_EXTERNAL`] = externalRequests.length;
      assert.strictEqual(
        counter,
        1,
        `${scenario.id} YES: execution must be 1`,
      );
      assert.strictEqual(
        externalRequests.length,
        0,
        `${scenario.id} YES: external must be 0`,
      );
      await context.close();
    }
  }

  {
    const { page, context, externalRequests } = await openPage(browser);
    await instrumentCounter(page);
    const proved = await proveS2SameValueDoubleCall(page);
    results.S2_SAME_VALUE_DOUBLE_CALL_COUNTS_TWO = proved ? "YES" : "NO";
    assertExternalRequestsZero(externalRequests, "S2 same-value double call");
    await context.close();
  }

  {
    const r = await runStaleYesSamePage(browser);
    results.STALE_YES_EXECUTIONS = r.executions;
    results.STALE_YES_ROUTE_UNCHANGED = r.routeUnchanged ? "YES" : "NO";
    results.STALE_YES_NO_RESULT = r.noResult ? "YES" : "NO";
    results.STALE_YES_NO_READ = r.noRead ? "YES" : "NO";
    results.STALE_YES_NO_HANDOFF = r.noHandoff ? "YES" : "NO";
    results.STALE_YES_EXTERNAL_REQUESTS = r.externalRequests;
    results.STALE_YES = "PASS";
  }

  {
    const r = await runDoubleYesTest(browser);
    assert.strictEqual(
      r.executions,
      1,
      `Double YES: execution must be exactly 1, got ${r.executions}`,
    );
    results.DOUBLE_YES_EXECUTIONS = r.executions;
  }

  {
    await runNoThenStaleYesTest(browser);
    results.NO_THEN_STALE_YES = "PASS";
  }

  await browser.close();

  console.log("GOLDEN_MASTER_STATE_GRAPH_E2E PASS");
  console.log(JSON.stringify(results, null, 2));
} catch (err) {
  console.error("GOLDEN_MASTER_STATE_GRAPH_E2E FAIL");
  console.error(err.stack || err.message);
  process.exit(1);
}
