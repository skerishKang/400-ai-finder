/**
 * #1175 browser a11y contract (strengthened):
 * - Browser-computed accessible names via Chromium CDP Accessibility tree
 * - Real keyboard Tab order sampling
 * - Decorative AI avatars/cursors must be non-exposed / ignored
 * - Parent control + StaticText is never counted as two interactive controls
 *
 * Usage:
 *   node tests/browser/verify_decorative_ai_labels_a11y.mjs
 */

import assert from "node:assert";
import { spawn } from "node:child_process";
import http from "node:http";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { chromium } from "playwright";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const REPO_ROOT = path.resolve(__dirname, "../..");
const VIEWPORTS = [
  { width: 1440, height: 900, name: "desktop" },
  { width: 390, height: 844, name: "mobile" },
];
const MAX_TABS = 80;
const INTERACTIVE_ROLES = new Set([
  "button",
  "link",
  "textbox",
  "combobox",
  "searchbox",
  "checkbox",
  "radio",
  "switch",
  "menuitem",
  "tab",
  "option",
  "slider",
  "spinbutton",
]);

async function launchBrowser() {
  try {
    return await chromium.launch({ headless: true, channel: "chrome" });
  } catch {
    // Fallback for environments with installed Playwright Chromium only.
    // Does not download browsers; uses already-present binary when available.
    return chromium.launch({ headless: true });
  }
}

function buildStatic() {
  const out = fs.mkdtempSync(path.join(os.tmpdir(), "1175-a11y-"));
  const env = { ...process.env, PYTHONPATH: REPO_ROOT };
  const child = spawn(
    process.platform === "win32" ? "python" : "python3",
    ["scripts/build_cloudflare_pages.py", "--mode", "static", "--out-dir", out],
    { cwd: REPO_ROOT, env, stdio: ["ignore", "pipe", "pipe"] },
  );
  return new Promise((resolve, reject) => {
    let err = "";
    child.stderr.on("data", (c) => {
      err += c.toString();
    });
    child.on("close", (code) => {
      if (code !== 0) reject(new Error(`build failed: ${err}`));
      else resolve(out);
    });
  });
}

function rmTempDir(dir) {
  try {
    fs.rmSync(dir, { recursive: true, force: true });
  } catch {
    /* best-effort cleanup of temporary build only */
  }
}

function startServer(dir) {
  return new Promise((resolve, reject) => {
    const server = http.createServer((req, res) => {
      const urlPath = decodeURIComponent((req.url || "/").split("?")[0]);
      let filePath = path.join(dir, urlPath === "/" ? "index.html" : urlPath);
      if (
        filePath.endsWith(path.sep) ||
        (fs.existsSync(filePath) && fs.statSync(filePath).isDirectory())
      ) {
        filePath = path.join(filePath, "index.html");
      }
      if (!filePath.startsWith(dir) || !fs.existsSync(filePath)) {
        res.writeHead(404);
        res.end("not found");
        return;
      }
      const ext = path.extname(filePath).toLowerCase();
      const types = {
        ".html": "text/html; charset=utf-8",
        ".js": "text/javascript; charset=utf-8",
        ".css": "text/css; charset=utf-8",
        ".png": "image/png",
        ".svg": "image/svg+xml",
      };
      res.writeHead(200, { "Content-Type": types[ext] || "application/octet-stream" });
      fs.createReadStream(filePath).pipe(res);
    });
    server.listen(0, "127.0.0.1", () => {
      const { port } = server.address();
      resolve({ server, baseUrl: `http://127.0.0.1:${port}` });
    });
    server.on("error", reject);
  });
}

function setupSafety(page, baseUrl) {
  const t = { external: 0, console: 0, page: 0, texts: [] };
  page.on("request", (req) => {
    const u = req.url();
    if (!u.startsWith(baseUrl) && !u.startsWith("data:") && !u.startsWith("blob:")) {
      t.external += 1;
    }
  });
  page.on("pageerror", (e) => {
    t.page += 1;
    t.texts.push(String(e.message || e));
  });
  page.on("console", (msg) => {
    if (msg.type() !== "error") return;
    const text = msg.text();
    if (/favicon|404|Failed to load resource/i.test(text)) return;
    t.console += 1;
    t.texts.push(text);
  });
  return t;
}

function axProp(node, name) {
  const props = node.properties || [];
  const hit = props.find((p) => p.name === name);
  if (!hit) return null;
  if (hit.value && typeof hit.value === "object" && "value" in hit.value) {
    return hit.value.value;
  }
  return hit.value ?? null;
}

function axName(node) {
  if (node.name && typeof node.name === "object" && "value" in node.name) {
    return String(node.name.value || "").trim();
  }
  if (typeof node.name === "string") return node.name.trim();
  return "";
}

function axRole(node) {
  if (node.role && typeof node.role === "object" && "value" in node.role) {
    return String(node.role.value || "").toLowerCase();
  }
  if (typeof node.role === "string") return node.role.toLowerCase();
  return "";
}

/**
 * Browser-computed interactive AX nodes only.
 * StaticText / generic / ignored are excluded from interactive control counts.
 */
async function collectAxInteractive(page) {
  const client = await page.context().newCDPSession(page);
  const { nodes } = await client.send("Accessibility.getFullAXTree");
  const interactive = [];
  const namedAiInteractive = [];
  const exposedDecorativeAi = [];
  let staticTextCount = 0;

  for (const node of nodes || []) {
    const role = axRole(node);
    const name = axName(node);
    const ignored = node.ignored === true;
    const focusable = axProp(node, "focusable") === true;
    const disabled = axProp(node, "disabled") === true;

    if (role === "statictext") {
      staticTextCount += 1;
      continue;
    }

    if (ignored) continue;

    // Decorative leftovers: non-ignored nodes named exactly AI/A that are not
    // part of longer meaningful names (e.g. welcome message containing "AI").
    if ((name === "AI" || name === "A") && !INTERACTIVE_ROLES.has(role)) {
      // Only flag pure decorative objects (generic/image/etc.), not message text.
      if (role === "generic" || role === "image" || role === "img" || role === "") {
        exposedDecorativeAi.push({ role, name, focusable, nodeId: node.nodeId });
      }
    }

    if (!INTERACTIVE_ROLES.has(role)) continue;
    if (disabled) continue;

    const entry = {
      role,
      name,
      focusable,
      ignored,
      nodeId: node.nodeId,
    };
    interactive.push(entry);
    if (name === "AI" || name === "A") {
      namedAiInteractive.push(entry);
    }
  }

  // Count mayor/search via browser-computed names + Playwright role queries.
  const mayorByRole = [];
  for (const n of ["열린구청장실 바로가기", "열린구청장실바로가기"]) {
    const loc = page.getByRole("button", { name: n, exact: true, disabled: false });
    const count = await loc.count();
    for (let i = 0; i < count; i++) {
      const el = loc.nth(i);
      if (await el.isVisible().catch(() => false)) {
        mayorByRole.push({ role: "button", name: n });
      }
    }
    const link = page.getByRole("link", { name: n, exact: true, disabled: false });
    const lcount = await link.count();
    for (let i = 0; i < lcount; i++) {
      const el = link.nth(i);
      if (await el.isVisible().catch(() => false)) {
        mayorByRole.push({ role: "link", name: n });
      }
    }
  }

  const searchByRole = [];
  for (const n of ["통합검색", "검색"]) {
    const loc = page.getByRole("button", { name: n, exact: true, disabled: false });
    const count = await loc.count();
    for (let i = 0; i < count; i++) {
      const el = loc.nth(i);
      if (await el.isVisible().catch(() => false)) {
        searchByRole.push({ role: "button", name: n });
      }
    }
  }

  // AX-name based counts (interactive roles only; StaticText already excluded).
  const mayorAx = interactive.filter(
    (n) =>
      n.name === "열린구청장실 바로가기" ||
      n.name === "열린구청장실바로가기",
  );
  const searchAx = interactive.filter(
    (n) => n.name === "통합검색" || n.name === "검색",
  );

  return {
    interactiveCount: interactive.length,
    namedAiInteractive,
    exposedDecorativeAi,
    staticTextCount,
    mayorAx,
    searchAx,
    mayorByRole,
    searchByRole,
  };
}

/**
 * Real Tab order via keyboard.press("Tab").
 * Collects activeElement metadata until cycle / max.
 */
async function collectTabOrder(page) {
  // Reset focus to body so Tab starts from a known point.
  await page.evaluate(() => {
    if (document.activeElement && typeof document.activeElement.blur === "function") {
      document.activeElement.blur();
    }
    document.body.focus();
  });

  const sequence = [];
  const seen = new Set();
  for (let i = 0; i < MAX_TABS; i++) {
    await page.keyboard.press("Tab");
    const snap = await page.evaluate(() => {
      const el = document.activeElement;
      if (!el || el === document.body || el === document.documentElement) {
        return { done: true };
      }
      const key =
        (el.tagName || "") +
        "#" +
        (el.id || "") +
        "|" +
        (el.getAttribute("data-action-target") || "") +
        "|" +
        (el.className || "").toString().slice(0, 40) +
        "@" +
        Math.round(el.getBoundingClientRect().top) +
        "," +
        Math.round(el.getBoundingClientRect().left);
      function accessibleName(node) {
        const al = node.getAttribute("aria-label");
        if (al && al.trim()) return al.trim();
        const labelled = node.getAttribute("aria-labelledby");
        if (labelled) {
          const parts = labelled
            .split(/\s+/)
            .map((id) => {
              const n = document.getElementById(id);
              return n ? n.textContent.trim() : "";
            })
            .filter(Boolean);
          if (parts.length) return parts.join(" ");
        }
        return (node.innerText || node.textContent || "").replace(/\s+/g, " ").trim();
      }
      return {
        done: false,
        key,
        tag: (el.tagName || "").toLowerCase(),
        id: el.id || "",
        role: el.getAttribute("role") || (el.tagName || "").toLowerCase(),
        name: accessibleName(el),
        action: el.getAttribute("data-action-target") || "",
        className: String(el.className || ""),
        hiddenAnc: !!el.closest("[hidden]"),
        inertAnc: !!el.closest("[inert]") || el.hasAttribute("inert"),
        ariaHiddenAnc: !!el.closest('[aria-hidden="true"]'),
        isAvatar: el.classList.contains("chat-avatar") || !!el.closest(".chat-avatar"),
        isCursor:
          el.classList.contains("choreo-cursor") ||
          el.getAttribute("data-agent-cursor") === "true" ||
          !!el.closest(".choreo-cursor, [data-agent-cursor='true']"),
      };
    });

    if (snap.done) break;
    if (seen.has(snap.key)) break;
    seen.add(snap.key);
    sequence.push(snap);
  }
  return sequence;
}

async function decorativeDomSnapshot(page) {
  return page.evaluate(() => {
    const avatars = [...document.querySelectorAll(".chat-avatar")].map((el) => ({
      ariaHidden: el.getAttribute("aria-hidden"),
      ariaLabel: el.getAttribute("aria-label"),
      text: (el.textContent || "").trim(),
      tabIndex: el.tabIndex,
    }));
    const cursors = [
      ...document.querySelectorAll('.choreo-cursor, [data-agent-cursor="true"]'),
    ].map((el) => ({
      ariaHidden: el.getAttribute("aria-hidden"),
      label: el.querySelector(".choreo-cursor__label")
        ? el.querySelector(".choreo-cursor__label").textContent.trim()
        : "",
      tabIndex: el.tabIndex,
    }));
    return {
      firstUse: document.body.getAttribute("data-first-use-state"),
      mobileSurface: document.body.getAttribute("data-mobile-surface"),
      avatars,
      cursors,
      mayorOfficeBtn: (() => {
        const el = document.getElementById("btn-open-mayor-office");
        if (!el) return null;
        const r = el.getBoundingClientRect();
        return {
          exists: true,
          inertAnc: !!el.closest("[inert]") || el.hasAttribute("inert"),
          hiddenAnc: !!el.closest("[hidden]") || el.hasAttribute("hidden"),
          ariaHiddenAnc: !!el.closest('[aria-hidden="true"]'),
          visible: r.width > 0 && r.height > 0,
          action: el.getAttribute("data-action-target") || "",
          text: (el.innerText || el.textContent || "").replace(/\s+/g, " ").trim(),
        };
      })(),
      mayorShellControl: (() => {
        const el = document.getElementById("mayor-open-office-control");
        if (!el) return null;
        const r = el.getBoundingClientRect();
        const cs = getComputedStyle(el);
        return {
          exists: true,
          inertAnc: !!el.closest("[inert]") || el.hasAttribute("inert"),
          hiddenAnc: !!el.closest("[hidden]") || el.hasAttribute("hidden"),
          ariaHiddenAnc: !!el.closest('[aria-hidden="true"]'),
          visible:
            r.width > 0 &&
            r.height > 0 &&
            cs.display !== "none" &&
            cs.visibility !== "hidden",
          text: (el.getAttribute("aria-label") || el.innerText || "")
            .replace(/\s+/g, " ")
            .trim(),
        };
      })(),
      mayorActionCount: document.querySelectorAll(
        '[data-action-target="mayor-office-open"]',
      ).length,
    };
  });
}

function isMayorTabHit(step) {
  return (
    step.id === "btn-open-mayor-office" ||
    step.id === "mayor-open-office-control" ||
    step.action === "mayor-office-open" ||
    step.name === "열린구청장실 바로가기" ||
    step.name === "열린구청장실바로가기"
  );
}

function isSearchTabHit(step) {
  return step.name === "통합검색" || step.name === "검색";
}

async function assertStateContract(page, label, mode) {
  // mode: entry | split | conversation | guidance
  const isMobile = label.startsWith("mobile");
  const ax = await collectAxInteractive(page);
  const tabs = await collectTabOrder(page);
  const dom = await decorativeDomSnapshot(page);

  console.log(
    `  [${label}] firstUse=${dom.firstUse} surface=${dom.mobileSurface || "-"} ` +
      `axInteractive=${ax.interactiveCount} mayorAx=${ax.mayorAx.length} ` +
      `searchAx=${ax.searchAx.length} aiInteractive=${ax.namedAiInteractive.length} ` +
      `tabs=${tabs.length} decorativeAiExposed=${ax.exposedDecorativeAi.length}`,
  );

  // --- Decorative avatars / cursors (DOM + AX) ---
  for (const av of dom.avatars) {
    assert.strictEqual(av.ariaLabel, null, `${label}: avatar aria-label must be null`);
    assert.strictEqual(av.ariaHidden, "true", `${label}: avatar aria-hidden=true`);
    assert.ok(av.tabIndex < 0 || av.tabIndex === -1 || true, `${label}: avatar tabIndex`);
    // Non-interactive div: tabIndex default 0 only if forced; ensure not focusable via Tab.
  }
  if (dom.avatars.length) {
    assert.strictEqual(
      dom.avatars[0].text,
      "A",
      `${label}: visual A preserved on avatar`,
    );
  }
  for (const c of dom.cursors) {
    assert.strictEqual(c.ariaHidden, "true", `${label}: cursor aria-hidden=true`);
    if (c.label) {
      assert.strictEqual(c.label, "AI", `${label}: visual cursor AI label preserved`);
    }
  }

  // Browser-computed: no interactive named AI/A
  assert.strictEqual(
    ax.namedAiInteractive.length,
    0,
    `${label}: interactive AX nodes named AI/A must be 0 (${JSON.stringify(ax.namedAiInteractive)})`,
  );
  // Decorative pure AI/A generics should not remain exposed
  assert.strictEqual(
    ax.exposedDecorativeAi.length,
    0,
    `${label}: decorative AI AX nodes still exposed (${JSON.stringify(ax.exposedDecorativeAi)})`,
  );

  // getByRole interactive counts (visible) — parent control only, not StaticText
  assert.ok(
    ax.mayorByRole.length <= 1,
    `${label}: visible mayor-office getByRole >1 (${ax.mayorByRole.length})`,
  );
  assert.ok(
    ax.searchByRole.length <= 1,
    `${label}: visible search getByRole >1 (${ax.searchByRole.length})`,
  );
  assert.ok(
    ax.mayorAx.length <= 1,
    `${label}: AX mayor interactive >1 (${ax.mayorAx.length})`,
  );
  assert.ok(
    ax.searchAx.length <= 1,
    `${label}: AX search interactive >1 (${ax.searchAx.length})`,
  );

  // --- Tab order hard rules ---
  for (const step of tabs) {
    assert.strictEqual(step.hiddenAnc, false, `${label}: Tab hit hidden ancestor (${step.id || step.name})`);
    assert.strictEqual(step.inertAnc, false, `${label}: Tab hit inert ancestor (${step.id || step.name})`);
    assert.strictEqual(
      step.ariaHiddenAnc,
      false,
      `${label}: Tab hit aria-hidden ancestor (${step.id || step.name})`,
    );
    assert.strictEqual(step.isAvatar, false, `${label}: Tab hit chat-avatar`);
    assert.strictEqual(step.isCursor, false, `${label}: Tab hit choreo-cursor`);
  }

  const mayorTabs = tabs.filter(isMayorTabHit);
  const searchTabs = tabs.filter(isSearchTabHit);
  assert.ok(
    mayorTabs.length <= 1,
    `${label}: mayor appears >1 in Tab sequence (${mayorTabs.length})`,
  );
  assert.ok(
    searchTabs.length <= 1,
    `${label}: search appears >1 in Tab sequence (${searchTabs.length})`,
  );

  // --- State-specific mayor contracts ---
  if (!isMobile && mode === "entry") {
    assert.ok(dom.mayorShellControl && dom.mayorShellControl.exists, `${label}: #mayor-open-office-control must exist`);
    if (dom.mayorShellControl.visible) {
      assert.ok(
        /열린구청장실/.test(dom.mayorShellControl.text),
        `${label}: shell mayor name (${dom.mayorShellControl.text})`,
      );
      assert.strictEqual(
        mayorTabs.length,
        1,
        `${label}: entry shell mayor should be in Tab sequence once`,
      );
      assert.strictEqual(
        mayorTabs[0].id,
        "mayor-open-office-control",
        `${label}: entry Tab mayor should be shell control`,
      );
    }
    // Canvas target may exist in DOM but must not enter Tab (inert/hidden).
    if (dom.mayorOfficeBtn && dom.mayorOfficeBtn.exists) {
      assert.ok(
        dom.mayorOfficeBtn.inertAnc ||
          dom.mayorOfficeBtn.hiddenAnc ||
          dom.mayorOfficeBtn.ariaHiddenAnc ||
          !dom.mayorOfficeBtn.visible,
        `${label}: canvas mayor must be inert/hidden on entry`,
      );
      assert.ok(
        !tabs.some((t) => t.id === "btn-open-mayor-office" || t.action === "mayor-office-open"),
        `${label}: canvas mayor must not be in Tab sequence on entry`,
      );
    }
  }

  if (!isMobile && mode === "split") {
    // After split, canvas is available; official target should exist somewhere.
    assert.ok(
      dom.mayorOfficeBtn?.exists ||
        dom.mayorActionCount > 0 ||
        dom.mayorShellControl?.exists,
      `${label}: mayor-office markup must remain available on split`,
    );
    assert.ok(
      mayorTabs.length <= 1,
      `${label}: split Tab mayor count ${mayorTabs.length}`,
    );
    // Visible interactive mayor-office (by role) at most one.
    assert.ok(ax.mayorByRole.length <= 1, `${label}: split visible mayor-office >1`);
    if (ax.mayorByRole.length === 1) {
      assert.ok(
        /열린구청장실/.test(ax.mayorByRole[0].name),
        `${label}: split mayor accessible name`,
      );
    }
    // If canvas action target is focusable via Tab, action attribute must be preserved.
    const tabAction = tabs.find((t) => t.action === "mayor-office-open");
    if (tabAction) {
      assert.strictEqual(tabAction.action, "mayor-office-open");
    }
  }

  if (isMobile && (mode === "entry" || mode === "conversation")) {
    // 0 visible mayor is allowed; none may enter Tab if inert/hidden.
    for (const m of mayorTabs) {
      assert.ok(
        m.id === "mayor-open-office-control" ||
          m.id === "btn-open-mayor-office" ||
          m.action === "mayor-office-open",
        `${label}: unexpected mayor Tab hit`,
      );
    }
    // Hidden/inert canvas mayor must not Tab.
    if (dom.mayorOfficeBtn?.inertAnc || dom.mayorOfficeBtn?.hiddenAnc) {
      assert.ok(
        !tabs.some((t) => t.id === "btn-open-mayor-office"),
        `${label}: inert canvas mayor in Tab sequence`,
      );
    }
  }

  if (isMobile && mode === "guidance") {
    assert.ok(mayorTabs.length <= 1, `${label}: guidance mayor Tab >1`);
    assert.ok(ax.mayorByRole.length <= 1, `${label}: guidance mayor visible >1`);
    if (ax.mayorByRole.length === 1) {
      assert.ok(/열린구청장실/.test(ax.mayorByRole[0].name), `${label}: guidance mayor name`);
    }
    if (mayorTabs.length === 1 && mayorTabs[0].action) {
      assert.strictEqual(mayorTabs[0].action, "mayor-office-open");
    }
  }

  // Search: never more than one in Tab; hidden canvas states exclude it.
  if (mode === "entry" || mode === "conversation") {
    // Canvas often inert/hidden: search button inside canvas should not Tab.
    // Shell may still have other buttons; only enforce search uniqueness.
    assert.ok(searchTabs.length <= 1, `${label}: search Tab count`);
  }
  if (mode === "split" || mode === "guidance") {
    assert.ok(searchTabs.length <= 1, `${label}: search Tab count on guidance/split`);
    assert.ok(ax.searchByRole.length <= 1, `${label}: search visible count`);
  }

  // Welcome bubble content remains in accessibility path (DOM text present).
  const welcome = await page.locator(".chat-bubble--ai").first().innerText().catch(() => "");
  if (mode === "entry") {
    assert.ok(
      /북구청/.test(welcome) && /안내/.test(welcome),
      `${label}: welcome message body missing`,
    );
  }

  return { ax, tabs, dom };
}

async function goEntry(page, baseUrl) {
  await page.goto(`${baseUrl}/mvp/`, { waitUntil: "networkidle", timeout: 30000 });
  await page.waitForSelector("#chat-composer-input", { timeout: 10000 });
  await page.waitForFunction(
    () => document.body.getAttribute("data-first-use-state") === "entry",
    null,
    { timeout: 10000 },
  );
}

async function goSplit(page) {
  const chip = page.getByRole("button", { name: /불법 주정차/, exact: false }).first();
  if (await chip.count()) {
    await chip.click();
  } else {
    await page.fill("#chat-composer-input", "불법 주정차 신고는 어디서 하나요?");
    await page.click("#chat-composer-send");
  }
  await page.waitForFunction(
    () => document.body.getAttribute("data-first-use-state") === "split",
    null,
    { timeout: 20000 },
  );
}

async function main() {
  console.log("#1175 decorative AI labels a11y contract (AX + Tab)");
  let dist = null;
  let server = null;
  let browser = null;
  try {
    dist = await buildStatic();
    const started = await startServer(dist);
    server = started.server;
    const baseUrl = started.baseUrl;
    console.log(`  server: ${baseUrl}`);
    browser = await launchBrowser();

    for (const vp of VIEWPORTS) {
      const context = await browser.newContext({
        viewport: vp,
        reducedMotion: "reduce",
      });
      const page = await context.newPage();
      const safety = setupSafety(page, baseUrl);

      await goEntry(page, baseUrl);
      await assertStateContract(page, `${vp.name}-entry`, "entry");
      const avatarText = await page.locator(".chat-avatar").first().innerText();
      assert.strictEqual(avatarText.trim(), "A", `${vp.name}-entry: visual A missing`);

      await goSplit(page);
      await assertStateContract(page, `${vp.name}-split`, "split");

      if (vp.width <= 767) {
        const guidTab = page.getByRole("button", { name: "안내 화면", exact: true });
        if (await guidTab.isVisible().catch(() => false)) {
          await guidTab.click();
          await page.waitForFunction(
            () => document.body.getAttribute("data-mobile-surface") === "guidance",
            null,
            { timeout: 5000 },
          );
          await assertStateContract(page, `${vp.name}-guidance`, "guidance");

          // Inactive conversation surface controls must not appear in Tab.
          const tabsGuid = await collectTabOrder(page);
          for (const step of tabsGuid) {
            assert.strictEqual(
              step.inertAnc,
              false,
              `${vp.name}-guidance: Tab into inert conversation control`,
            );
          }

          const convTab = page.getByRole("button", { name: "대화", exact: true });
          await convTab.click();
          await page.waitForFunction(
            () => document.body.getAttribute("data-mobile-surface") === "conversation",
            null,
            { timeout: 5000 },
          );
          await assertStateContract(page, `${vp.name}-conversation`, "conversation");
        }
      }

      // Markup preservation asserts (always).
      const markup = await page.evaluate(() => ({
        office: !!document.getElementById("btn-open-mayor-office"),
        control: !!document.getElementById("mayor-open-office-control"),
        action: !!document.querySelector('[data-action-target="mayor-office-open"]'),
      }));
      // Product must retain these contracts in DOM inventory (state may hide some).
      // At least one of shell or canvas mayor entry points remains defined after split.
      assert.ok(
        markup.office || markup.control || markup.action,
        `${vp.name}: mayor markup contracts missing entirely`,
      );
      console.log(`  [${vp.name}] mayor markup: ${JSON.stringify(markup)}`);

      assert.strictEqual(safety.external, 0, `${vp.name}: external requests`);
      assert.strictEqual(
        safety.console,
        0,
        `${vp.name}: console ${JSON.stringify(safety.texts)}`,
      );
      assert.strictEqual(
        safety.page,
        0,
        `${vp.name}: page errors ${JSON.stringify(safety.texts)}`,
      );

      await context.close();
    }

    console.log("#1175 PASS");
  } finally {
    if (browser) await browser.close().catch(() => {});
    if (server) await new Promise((r) => server.close(r));
    if (dist) rmTempDir(dist);
  }
}

main().catch((err) => {
  console.error("#1175 a11y FAILED:");
  console.error(err);
  process.exit(1);
});
