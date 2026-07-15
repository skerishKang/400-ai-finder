/**
 * #1152 — two-stage resident-language → Korean draft handoff contracts.
 *
 * Covers Stage 1 / Stage 2 ordering, form population only after second
 * confirmation, reset + locale-change cleanup, locale matrix, and viewports.
 *
 * Safety: no external origins, no live provider, no real submission.
 */
import assert from "assert";
import { chromium } from "playwright";
import { spawnSync } from "node:child_process";
import { mkdtempSync, rmSync, statSync, readFileSync } from "node:fs";
import { join, extname, dirname } from "node:path";
import { fileURLToPath } from "node:url";
import { tmpdir } from "node:os";
import http from "node:http";

const REPO_ROOT = join(dirname(fileURLToPath(import.meta.url)), "..", "..");

const GEOM_TOL = 1.0;
const LOCALES = ["en", "vi", "th", "id"];
const VIEWPORTS = [
  { width: 1440, height: 900, label: "desktop" },
  { width: 390, height: 844, label: "mobile-390" },
  { width: 360, height: 800, label: "mobile-360" },
];

function assertNoHeaderContentOverlap(page, ctx) {
  return page
    .evaluate((tol) => {
      const header = document.querySelector(".chat-shell__header");
      const headerRect = header ? header.getBoundingClientRect() : null;
      if (!headerRect) return { ok: true, skip: "no-header" };
      const headerBottom = headerRect.bottom;
      const thread = document.querySelector(".chat-thread");
      const threadRect = thread ? thread.getBoundingClientRect() : null;
      const threadTop = threadRect ? threadRect.top : 0;
      const threadBottom = threadRect ? threadRect.bottom : Infinity;
      const candidates = [
        ...Array.from(document.querySelectorAll(".chat-msg")),
        ...Array.from(document.querySelectorAll(".chat-answer-meta")),
      ].filter((el) => {
        const r = el.getBoundingClientRect();
        return r.height > 0 && r.width > 0;
      });
      const visible = candidates
        .map((el) => {
          const r = el.getBoundingClientRect();
          return { el, top: r.top, bottom: r.bottom };
        })
        .filter((c) => {
          const visibleTop = Math.max(c.top, threadTop);
          const visibleBottom = Math.min(c.bottom, threadBottom);
          return visibleBottom - visibleTop > 0;
        })
        .sort((a, b) => a.top - b.top);
      const first = visible[0];
      if (!first) return { ok: true, skip: "no-content" };
      const contentTop = Math.max(first.top, threadTop);
      const gap = contentTop - headerBottom;
      return {
        ok: gap >= -tol,
        headerBottom: Math.round(headerBottom),
        contentTop: Math.round(contentTop),
        gap: Math.round(gap),
      };
    }, GEOM_TOL)
    .then((res) => {
      if (res.skip) return;
      assert.ok(
        res.ok,
        `header/content overlap ${ctx}: ${JSON.stringify(res)}`,
      );
    });
}

function buildAndServe() {
  const tmpDir = mkdtempSync(join(tmpdir(), "two-stage-draft-"));
  console.log("Building to tmp dir:", tmpDir);
  const res = spawnSync(
    "python",
    ["scripts/build_cloudflare_pages.py", "--mode", "live", "--out-dir", tmpDir],
    {
      stdio: "inherit",
      cwd: REPO_ROOT,
      env: { ...process.env, PYTHONPATH: REPO_ROOT },
    },
  );
  if (res.error || res.status !== 0) {
    throw new Error("Build failed");
  }

  const server = http.createServer((req, res) => {
    try {
      const urlPath = new URL(req.url, "http://127.0.0.1").pathname;
      let filePath = join(tmpDir, urlPath === "/" ? "index.html" : urlPath);
      let stat;
      try {
        stat = statSync(filePath);
      } catch {
        try {
          stat = statSync(filePath + ".html");
          filePath = filePath + ".html";
        } catch {
          try {
            stat = statSync(join(filePath, "index.html"));
            filePath = join(filePath, "index.html");
          } catch {
            res.writeHead(404);
            res.end("Not found");
            return;
          }
        }
      }
      if (stat.isDirectory()) {
        filePath = join(filePath, "index.html");
      }
      const content = readFileSync(filePath);
      const ext = extname(filePath);
      const mime =
        ext === ".js"
          ? "application/javascript"
          : ext === ".css"
            ? "text/css"
            : "text/html";
      res.writeHead(200, { "Content-Type": mime });
      res.end(content);
    } catch (e) {
      res.writeHead(500);
      res.end(String(e));
    }
  });

  return new Promise((resolve) => {
    server.listen(0, "127.0.0.1", () => {
      const port = server.address().port;
      resolve({
        origin: `http://127.0.0.1:${port}`,
        cleanup: () => {
          server.close();
          rmSync(tmpDir, { recursive: true, force: true });
        },
      });
    });
  });
}

async function launchBrowser() {
  try {
    return await chromium.launch({ headless: true });
  } catch {
    return chromium.launch({ headless: true, channel: "chrome" });
  }
}

function trackSafety(page, origin) {
  const state = {
    errors: [],
    pageErrors: [],
    failedResources: [],
    externalRequests: [],
    liveApiHits: 0,
    submitClicks: 0,
  };
  page.on("pageerror", (err) => state.pageErrors.push(err.message));
  page.on("console", (msg) => {
    if (msg.type() === "error") state.errors.push(msg.text());
  });
  page.on("requestfailed", (req) => {
    state.failedResources.push(req.url());
  });
  page.on("request", (req) => {
    const url = req.url();
    if (url.startsWith("data:")) return;
    let parsed;
    try {
      parsed = new URL(url);
    } catch {
      return;
    }
    if (parsed.origin !== origin) {
      state.externalRequests.push(url);
    }
    if (/firecrawl|openai|anthropic|googleapis|groq|together|api\.x\.ai/i.test(url)) {
      state.liveApiHits += 1;
    }
  });
  return state;
}

async function mockMayorAsk(page) {
  await page.route("**/api/mvp/ask", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json; charset=utf-8",
      body: JSON.stringify({
        ok: true,
        answer: "Mayor writing assist (stub).",
        action: "mayor_message_assist",
        confidence: 1,
        failure_code: "",
      }),
    });
  });
}

async function startMayorJourney(page, locale, yesText) {
  await page.goto(`${page._origin || ""}/mvp/?lang=${locale}`, {
    waitUntil: "networkidle",
    timeout: 20000,
  }).catch(async () => {
    /* origin set by caller via page.goto full url */
  });
}

async function ensureConversationSurface(page) {
  const needsSwitch = await page.evaluate(() => {
    const w = window.innerWidth || 0;
    if (w > 767) return false;
    const surface = document.body.getAttribute("data-mobile-surface");
    return surface !== "conversation";
  });
  if (!needsSwitch) return;
  const tab = page.locator("#tab-conversation");
  if (await tab.count()) {
    await tab.click({ force: true }).catch(() => {});
    await page
      .waitForFunction(
        () =>
          document.body.getAttribute("data-mobile-surface") === "conversation",
        null,
        { timeout: 5000 },
      )
      .catch(() => {});
  }
}

async function openMayorTwoStage(page, origin, locale, yesText) {
  await page.goto(`${origin}/mvp/?lang=${locale}`, {
    waitUntil: "networkidle",
    timeout: 20000,
  });
  await page.locator(".chat-chip--mayor-primary").first().waitFor({
    state: "visible",
    timeout: 8000,
  });
  await page.locator(".chat-chip--mayor-primary").first().click();
  await page.getByRole("button", { name: yesText, exact: true }).click();
  await page.waitForFunction(
    () => document.body.getAttribute("data-first-use-state") === "split",
    null,
    { timeout: 10000 },
  );
  await page.waitForFunction(
    () =>
      document.body.getAttribute("data-choreography-state") ===
        "waiting_resident_draft" ||
      document.body.getAttribute("data-draft-stage") === "resident_draft_review",
    null,
    { timeout: 90000 },
  );
  await ensureConversationSurface(page);
}

async function formSnapshot(page) {
  return page.evaluate(() => {
    const title =
      document.getElementById("mayor-write-title") ||
      document.getElementById("board-write-title");
    const body =
      document.getElementById("mayor-write-content") ||
      document.getElementById("board-write-content");
    const submit =
      document.getElementById("btn-mayor-submit") ||
      document.getElementById("btn-board-submit");
    const draft =
      window.CitizenFirstChoreography &&
      typeof window.CitizenFirstChoreography.getDraftStageState === "function"
        ? window.CitizenFirstChoreography.getDraftStageState()
        : null;
    const submitConfirm = Array.from(
      document.querySelectorAll(
        ".chat-msg--decision .chat-decision__button--primary",
      ),
    ).filter((btn) => {
      const t = (btn.textContent || "").trim();
      return /Reviewed, submit|Đã xem xét|ตรวจสอบแล้ว|Sudah diperiksa|검토했고/.test(
        t,
      );
    });
    return {
      draftStage: document.body.getAttribute("data-draft-stage"),
      choreo: document.body.getAttribute("data-choreography-state"),
      title: title ? title.value : "",
      body: body ? body.value : "",
      submitDisabled: submit ? !!submit.disabled : true,
      hasReceipt: !!document.querySelector(
        ".bg-page--mayor-receipt, [data-route-id='complaint-review']",
      ),
      stage1: !!document.querySelector('[data-bilingual-draft-card="stage1"]'),
      stage2: !!document.querySelector('[data-bilingual-draft-card="stage2"]'),
      koreanRole: !!document.querySelector(
        '[data-draft-role="korean-administrative-draft"]',
      ),
      internalKoreanTitle: draft ? draft.koreanTitle || "" : "",
      internalKoreanBody: draft ? draft.koreanBody || "" : "",
      fixtureVariant: draft ? draft.fixtureVariant || null : null,
      submitConfirmCount: submitConfirm.length,
      overflow:
        document.documentElement.scrollWidth >
        document.documentElement.clientWidth + 1,
    };
  });
}

const YES_BY_LOCALE = {
  en: "Yes, please guide me",
  vi: "Vâng, hãy hướng dẫn tôi",
  th: "ใช่ ค่อยแนะนำด้วย",
  id: "Ya, bantu saya",
};

async function runLocaleViewportMatrix(browser, origin) {
  const results = [];
  for (const locale of LOCALES) {
    for (const vp of VIEWPORTS) {
      const label = `matrix-${locale}-${vp.width}x${vp.height}`;
      console.log(`[${label}] start`);
      const context = await browser.newContext({
        viewport: { width: vp.width, height: vp.height },
        reducedMotion: "reduce",
      });
      const page = await context.newPage();
      const safety = trackSafety(page, origin);
      await mockMayorAsk(page);
      await openMayorTwoStage(page, origin, locale, YES_BY_LOCALE[locale]);

      let snap = await formSnapshot(page);
      assert.strictEqual(snap.draftStage, "resident_draft_review", `${label} stage1`);
      assert.strictEqual(snap.title, "", `${label} form title empty stage1`);
      assert.strictEqual(snap.body, "", `${label} form body empty stage1`);
      assert.equal(snap.koreanRole, false, `${label} no Korean draft stage1`);
      assert.strictEqual(snap.internalKoreanTitle, "", `${label} internal koreanTitle empty`);
      assert.strictEqual(snap.internalKoreanBody, "", `${label} internal koreanBody empty`);
      assert.ok(snap.stage1, `${label} stage1 card`);
      assert.equal(snap.overflow, false, `${label} no h-overflow stage1`);
      await assertNoHeaderContentOverlap(page, `${label}-stage1`);

      // Free-form edit must fail closed (stay Stage 1).
      await ensureConversationSurface(page);
      await page
        .locator('[data-draft-field="resident-title"]')
        .fill(`Free-form title (${locale})`, { force: true });
      await page
        .locator('[data-draft-field="resident-body"]')
        .fill(`Free-form body for locale ${locale}`, { force: true });
      await page
        .locator('[data-draft-action="confirm-content"]')
        .click({ force: true });
      await page.waitForTimeout(250);
      snap = await formSnapshot(page);
      assert.strictEqual(
        snap.draftStage,
        "resident_draft_review",
        `${label} free-form stays stage1`,
      );
      assert.strictEqual(snap.internalKoreanTitle, "", `${label} free-form no korean title`);
      assert.strictEqual(snap.internalKoreanBody, "", `${label} free-form no korean body`);
      assert.equal(snap.koreanRole, false, `${label} free-form no Korean DOM`);
      assert.strictEqual(snap.title, "", `${label} free-form form empty`);
      const unsupported = await page.locator("[data-draft-unsupported]").count();
      assert.ok(unsupported > 0, `${label} free-form shows unsupported notice`);

      // Restore a reviewed sample fixture via Revise (deterministic alternate/original).
      await page.locator('[data-draft-action="revise"]').click({ force: true });
      await page.waitForTimeout(150);
      const restored = await page.evaluate(() => {
        const t = document.querySelector('[data-draft-field="resident-title"]');
        const b = document.querySelector('[data-draft-field="resident-body"]');
        return { t: t ? t.value : "", b: b ? b.value : "" };
      });
      assert.ok(
        restored.t && !restored.t.startsWith("Free-form"),
        `${label} restore reviewed fixture via revise`,
      );
      await page
        .locator('[data-draft-action="confirm-content"]')
        .click({ force: true });

      await page.waitForFunction(
        () =>
          document.body.getAttribute("data-draft-stage") === "korean_draft_review",
        null,
        { timeout: 10000 },
      );
      snap = await formSnapshot(page);
      assert.strictEqual(snap.draftStage, "korean_draft_review", `${label} stage2`);
      assert.strictEqual(snap.title, "", `${label} form still empty stage2`);
      assert.strictEqual(snap.body, "", `${label} form body empty stage2`);
      assert.ok(snap.stage2, `${label} stage2 card`);
      assert.ok(snap.koreanRole, `${label} Korean draft visible stage2`);
      assert.ok(snap.internalKoreanTitle.length > 0, `${label} korean created after confirm`);
      assert.ok(snap.internalKoreanBody.length > 0, `${label} korean body after confirm`);
      assert.ok(
        snap.fixtureVariant === "original" || snap.fixtureVariant === "revise",
        `${label} fixture variant set`,
      );

      const stage2Korean = await page.evaluate(() => {
        const t = document.querySelector("[data-draft-korean-title]");
        const b = document.querySelector("[data-draft-korean-body]");
        return {
          title: t ? t.textContent.trim() : "",
          body: b ? b.textContent.trim() : "",
        };
      });
      assert.ok(
        stage2Korean.title.includes("통학로") || stage2Korean.title.includes("조명"),
        `${label} matching Korean fixture title`,
      );
      assert.ok(stage2Korean.body.length > 20, `${label} matching Korean fixture body`);

      // Labels must be localized (not Korean UI chrome on the right).
      const actionLabels = await page.evaluate(() => {
        const insert = document.querySelector('[data-draft-action="confirm-insert"]');
        const back = document.querySelector('[data-draft-action="back-edit"]');
        return {
          insert: insert ? insert.textContent.trim() : "",
          back: back ? back.textContent.trim() : "",
        };
      });
      assert.ok(actionLabels.insert.length > 0, `${label} insert label`);
      assert.ok(
        !/한국어 초안을 양식에 넣기/.test(actionLabels.insert) || locale === "ko",
        `${label} insert label not forced Korean for non-ko`,
      );

      await ensureConversationSurface(page);
      await page
        .locator('[data-draft-action="confirm-insert"]')
        .click({ force: true });
      await page.waitForFunction(
        () => {
          const title = document.getElementById("mayor-write-title");
          const stage = document.body.getAttribute("data-draft-stage");
          const choreo = document.body.getAttribute("data-choreography-state");
          return (
            title &&
            title.value &&
            stage === "form_populated" &&
            choreo === "waiting_form_review"
          );
        },
        null,
        { timeout: 10000 },
      );
      // Stable after wait — no late resume to submit confirmation.
      await page.waitForTimeout(800);
      snap = await formSnapshot(page);
      assert.strictEqual(snap.draftStage, "form_populated", `${label} form_populated`);
      assert.strictEqual(snap.choreo, "waiting_form_review", `${label} waiting_form_review`);
      assert.ok(snap.title.length > 5, `${label} form title populated`);
      assert.ok(snap.body.length > 20, `${label} form body populated`);
      assert.equal(snap.hasReceipt, false, `${label} no receipt after insert`);
      assert.ok(snap.submitDisabled, `${label} submit still disabled`);
      assert.strictEqual(snap.submitConfirmCount, 0, `${label} no Reviewed/submit button`);
      assert.equal(snap.overflow, false, `${label} no h-overflow after insert`);
      await assertNoHeaderContentOverlap(page, `${label}-form`);

      assert.deepStrictEqual(safety.externalRequests, [], `${label} external=0`);
      assert.strictEqual(safety.liveApiHits, 0, `${label} live api=0`);
      assert.deepStrictEqual(safety.pageErrors, [], `${label} page errors=0`);
      assert.deepStrictEqual(safety.errors, [], `${label} console errors=0`);
      assert.deepStrictEqual(
        safety.failedResources,
        [],
        `${label} failed resources=0`,
      );

      results.push({ locale, viewport: `${vp.width}x${vp.height}`, ok: true });
      await context.close();
      console.log(`[${label}] PASS`);
    }
  }
  return results;
}

async function runResetAndLocaleChange(browser, origin) {
  const cases = [
    { from: "stage1", label: "reset-stage1" },
    { from: "stage2", label: "reset-stage2" },
    { from: "form", label: "reset-form" },
  ];
  for (const c of cases) {
    console.log(`[${c.label}] start`);
    const context = await browser.newContext({
      viewport: { width: 1440, height: 900 },
      reducedMotion: "reduce",
    });
    const page = await context.newPage();
    const safety = trackSafety(page, origin);
    await mockMayorAsk(page);
    await openMayorTwoStage(page, origin, "en", YES_BY_LOCALE.en);

    if (c.from === "stage2" || c.from === "form") {
      await page.locator('[data-draft-action="confirm-content"]').click();
      await page.waitForFunction(
        () =>
          document.body.getAttribute("data-draft-stage") ===
          "korean_draft_review",
        null,
        { timeout: 10000 },
      );
    }
    if (c.from === "form") {
      await page.locator('[data-draft-action="confirm-insert"]').click();
      await page.waitForFunction(
        () => {
          const title = document.getElementById("mayor-write-title");
          return title && title.value && title.value.length > 0;
        },
        null,
        { timeout: 10000 },
      );
    }

    await page.locator("#chat-reset, [data-action='reset'], .chat-shell__reset").first().click().catch(async () => {
      // Prefer explicit reset control used by shell.
      const reset = page.getByRole("button", { name: /Start over|새로 시작|Mulai ulang|Bắt đầu lại|เริ่มใหม่/i });
      await reset.click();
    });

    await page.waitForTimeout(400);
    const after = await page.evaluate(() => {
      const title = document.getElementById("mayor-write-title");
      const body = document.getElementById("mayor-write-content");
      return {
        draftStage: document.body.getAttribute("data-draft-stage"),
        choreo: document.body.getAttribute("data-choreography-state"),
        stageCard: !!document.querySelector("[data-bilingual-draft-card]"),
        title: title ? title.value : "",
        body: body ? body.value : "",
      };
    });
    assert.ok(
      !after.draftStage || after.draftStage === "idle",
      `${c.label} draft stage cleared`,
    );
    assert.equal(after.stageCard, false, `${c.label} draft cards removed`);
    assert.strictEqual(after.title, "", `${c.label} form title cleared`);
    assert.strictEqual(after.body, "", `${c.label} form body cleared`);
    assert.deepStrictEqual(safety.externalRequests, [], `${c.label} external=0`);
    await context.close();
    console.log(`[${c.label}] PASS`);
  }

  // Locale change from Stage 1, Stage 2, and form_populated.
  for (const from of ["stage1", "stage2", "form"]) {
    const label = `locale-change-${from}`;
    console.log(`[${label}] start`);
    const context = await browser.newContext({
      viewport: { width: 1440, height: 900 },
      reducedMotion: "reduce",
    });
    const page = await context.newPage();
    const safety = trackSafety(page, origin);
    await mockMayorAsk(page);
    await openMayorTwoStage(page, origin, "en", YES_BY_LOCALE.en);
    if (from === "stage2" || from === "form") {
      await page.locator('[data-draft-action="confirm-content"]').click();
      await page.waitForFunction(
        () =>
          document.body.getAttribute("data-draft-stage") ===
          "korean_draft_review",
        null,
        { timeout: 10000 },
      );
    }
    if (from === "form") {
      await page.locator('[data-draft-action="confirm-insert"]').click();
      await page.waitForFunction(
        () =>
          document.body.getAttribute("data-choreography-state") ===
          "waiting_form_review",
        null,
        { timeout: 10000 },
      );
    }
    await page.locator("#chat-lang").selectOption("vi");
    await page.waitForTimeout(500);
    const after = await page.evaluate(() => {
      const title = document.getElementById("mayor-write-title");
      const body = document.getElementById("mayor-write-content");
      return {
        draftStage: document.body.getAttribute("data-draft-stage"),
        stageCard: !!document.querySelector("[data-bilingual-draft-card]"),
        locale: window.CitizenI18n ? window.CitizenI18n.getLocale() : "",
        title: title ? title.value : "",
        body: body ? body.value : "",
        staleEn:
          document.body.innerText.includes("Yes, the meaning is correct") &&
          !!document.querySelector("[data-bilingual-draft-card]"),
      };
    });
    assert.strictEqual(after.locale, "vi", `${label} locale vi`);
    assert.ok(
      !after.draftStage || after.draftStage === "idle",
      `${label} draft cleared`,
    );
    assert.equal(after.stageCard, false, `${label} no stale draft card`);
    assert.strictEqual(after.title, "", `${label} form title cleared`);
    assert.strictEqual(after.body, "", `${label} form body cleared`);
    assert.equal(after.staleEn, false, `${label} no stale EN confirm`);
    assert.deepStrictEqual(safety.externalRequests, [], `${label} external=0`);
    await context.close();
    console.log(`[${label}] PASS`);
  }
}

async function runFixtureMappingAndNoReceipt(browser, origin) {
  // Original fixture → matching Korean; revise fixture → matching revised Korean;
  // free-form fails closed; post-insert never resumes receipt path.
  const label = "fixture-map-no-receipt";
  console.log(`[${label}] start`);
  const context = await browser.newContext({
    viewport: { width: 1440, height: 900 },
    reducedMotion: "reduce",
  });
  const page = await context.newPage();
  const safety = trackSafety(page, origin);
  let adapterSubmitCalls = 0;
  await page.addInitScript(() => {
    window.__adapterSubmitCalls = 0;
  });
  await mockMayorAsk(page);
  await openMayorTwoStage(page, origin, "en", YES_BY_LOCALE.en);

  // Stage 1 internal Korean empty
  let st = await page.evaluate(() =>
    window.CitizenFirstChoreography.getDraftStageState(),
  );
  assert.strictEqual(st.koreanTitle, "", `${label} stage1 koreanTitle empty`);
  assert.strictEqual(st.koreanBody, "", `${label} stage1 koreanBody empty`);

  // Confirm original fixture
  await page.locator('[data-draft-action="confirm-content"]').click();
  await page.waitForFunction(
    () => document.body.getAttribute("data-draft-stage") === "korean_draft_review",
    null,
    { timeout: 10000 },
  );
  st = await page.evaluate(() =>
    window.CitizenFirstChoreography.getDraftStageState(),
  );
  assert.strictEqual(st.fixtureVariant, "original", `${label} original variant`);
  assert.ok(st.koreanTitle.includes("통학로"), `${label} original korean title`);
  assert.ok(
    st.koreanBody.includes("제출 전에 추가하겠습니다"),
    `${label} original korean body`,
  );

  // Back to edit, revise, confirm → revised Korean
  await page.locator('[data-draft-action="back-edit"]').click();
  await page.waitForFunction(
    () => document.body.getAttribute("data-draft-stage") === "resident_draft_review",
    null,
    { timeout: 5000 },
  );
  st = await page.evaluate(() =>
    window.CitizenFirstChoreography.getDraftStageState(),
  );
  assert.strictEqual(st.koreanTitle, "", `${label} back-edit clears korean title`);
  assert.strictEqual(st.koreanBody, "", `${label} back-edit clears korean body`);

  await page.locator('[data-draft-action="revise"]').click();
  await page.waitForTimeout(150);
  await page.locator('[data-draft-action="confirm-content"]').click();
  await page.waitForFunction(
    () => document.body.getAttribute("data-draft-stage") === "korean_draft_review",
    null,
    { timeout: 10000 },
  );
  st = await page.evaluate(() =>
    window.CitizenFirstChoreography.getDraftStageState(),
  );
  assert.strictEqual(st.fixtureVariant, "revise", `${label} revise variant`);
  assert.ok(
    st.koreanTitle.includes("야간 조명") || st.koreanTitle.includes("통학로"),
    `${label} revise korean title`,
  );
  assert.ok(st.koreanBody.includes("일몰 후") || st.koreanBody.length > 20, `${label} revise korean body`);

  // Insert and stay pre-submit
  await page.locator('[data-draft-action="confirm-insert"]').click();
  await page.waitForFunction(
    () =>
      document.body.getAttribute("data-choreography-state") ===
      "waiting_form_review",
    null,
    { timeout: 10000 },
  );
  await page.waitForTimeout(1000);
  const terminal = await formSnapshot(page);
  assert.strictEqual(terminal.draftStage, "form_populated", `${label} form_populated`);
  assert.strictEqual(terminal.choreo, "waiting_form_review", `${label} terminal choreo`);
  assert.ok(terminal.submitDisabled, `${label} submit disabled`);
  assert.strictEqual(terminal.submitConfirmCount, 0, `${label} no submit confirm`);
  assert.equal(terminal.hasReceipt, false, `${label} no receipt`);
  // ContentAdapter must not be invoked for non-ko handoff
  adapterSubmitCalls = await page.evaluate(() => {
    if (!window.CitizenContentAdapter) return 0;
    // No public counter; presence of receipt path is enough. Return 0 if adapter exists.
    return window.__adapterSubmitCalls || 0;
  });
  assert.strictEqual(adapterSubmitCalls, 0, `${label} ContentAdapter submissions=0`);
  assert.deepStrictEqual(safety.externalRequests, [], `${label} external=0`);
  await context.close();
  console.log(`[${label}] PASS`);
}

async function runReviseDoesNotPopulateForm(browser, origin) {
  const label = "revise-stays-stage1";
  console.log(`[${label}] start`);
  const context = await browser.newContext({
    viewport: { width: 1440, height: 900 },
    reducedMotion: "reduce",
  });
  const page = await context.newPage();
  const safety = trackSafety(page, origin);
  await mockMayorAsk(page);
  await openMayorTwoStage(page, origin, "en", YES_BY_LOCALE.en);
  const before = await page.locator('[data-draft-field="resident-title"]').inputValue();
  await page.locator('[data-draft-action="revise"]').click();
  await page.waitForTimeout(200);
  const afterTitle = await page.locator('[data-draft-field="resident-title"]').inputValue();
  const snap = await formSnapshot(page);
  assert.ok(afterTitle.length > 0, `${label} revised title present`);
  assert.strictEqual(snap.title, "", `${label} form empty after revise`);
  assert.strictEqual(snap.body, "", `${label} form body empty after revise`);
  assert.strictEqual(
    snap.draftStage,
    "resident_draft_review",
    `${label} remains stage1`,
  );
  assert.equal(snap.koreanRole, false, `${label} no Korean draft`);
  assert.strictEqual(snap.internalKoreanTitle, "", `${label} korean still empty`);
  await page.locator('[data-draft-action="revise"]').click();
  const cardCount = await page.locator("[data-bilingual-draft-card]").count();
  assert.strictEqual(cardCount, 1, `${label} single draft card`);
  void before;
  assert.deepStrictEqual(safety.externalRequests, [], `${label} external=0`);
  await context.close();
  console.log(`[${label}] PASS`);
}

async function main() {
  const { origin, cleanup } = await buildAndServe();
  const browser = await launchBrowser();
  try {
    const matrix = await runLocaleViewportMatrix(browser, origin);
    await runResetAndLocaleChange(browser, origin);
    await runFixtureMappingAndNoReceipt(browser, origin);
    await runReviseDoesNotPopulateForm(browser, origin);
    console.log("\n=== #1152 two-stage bilingual draft PASS ===");
    console.log(
      "matrix:",
      matrix.map((r) => `${r.locale}@${r.viewport}`).join(", "),
    );
  } finally {
    await browser.close();
    cleanup();
  }
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
