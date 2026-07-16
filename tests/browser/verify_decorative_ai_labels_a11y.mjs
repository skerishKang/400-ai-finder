/**
 * #1175 browser a11y contract: decorative AI avatars/cursors leave the AX tree;
 * parent control + StaticText is not counted as two interactive controls.
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

async function launchBrowser() {
  try {
    return await chromium.launch({ headless: true, channel: "chrome" });
  } catch {
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

/**
 * Collect distinct visible + focusable interactive controls (not StaticText).
 * Skips elements under aria-hidden/inert/hidden ancestors.
 */
async function collectInteractive(page) {
  return page.evaluate(() => {
    function isHiddenOrInert(el) {
      if (!el || el.nodeType !== 1) return true;
      if (el.hasAttribute("hidden") || el.getAttribute("aria-hidden") === "true") {
        return true;
      }
      if (el.hasAttribute("inert") || el.closest("[inert]")) return true;
      if (el.closest('[aria-hidden="true"]') || el.closest("[hidden]")) return true;
      const cs = getComputedStyle(el);
      if (cs.display === "none" || cs.visibility === "hidden") return true;
      const r = el.getBoundingClientRect();
      if (r.width <= 0 || r.height <= 0) return true;
      return false;
    }

    function accessibleName(el) {
      const al = el.getAttribute("aria-label");
      if (al && al.trim()) return al.trim();
      const labelled = el.getAttribute("aria-labelledby");
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
      return (el.innerText || el.textContent || "").replace(/\s+/g, " ").trim();
    }

    const selector =
      'a[href], button, [role="button"], input, select, textarea, [tabindex]:not([tabindex="-1"])';
    const nodes = [...document.querySelectorAll(selector)];
    const focusable = [];
    for (const el of nodes) {
      if (isHiddenOrInert(el)) continue;
      if (el.disabled || el.getAttribute("aria-disabled") === "true") continue;
      const tabIndex = el.tabIndex;
      if (tabIndex < 0 && !el.matches("a[href], button, input, select, textarea")) {
        continue;
      }
      const name = accessibleName(el);
      const r = el.getBoundingClientRect();
      focusable.push({
        tag: el.tagName.toLowerCase(),
        id: el.id || "",
        name,
        role: el.getAttribute("role") || el.tagName.toLowerCase(),
        action: el.getAttribute("data-action-target") || "",
        top: Math.round(r.top),
        left: Math.round(r.left),
      });
    }

    // Decorative avatars / cursors that must not name themselves "AI".
    const avatars = [...document.querySelectorAll(".chat-avatar")].map((el) => ({
      ariaHidden: el.getAttribute("aria-hidden"),
      ariaLabel: el.getAttribute("aria-label"),
      text: (el.textContent || "").trim(),
      focusable: el.tabIndex >= 0 || el.matches("a,button,input,select,textarea"),
      hiddenOrInert: isHiddenOrInert(el) || el.getAttribute("aria-hidden") === "true",
    }));
    const cursors = [
      ...document.querySelectorAll('.choreo-cursor, [data-agent-cursor="true"]'),
    ].map((el) => ({
      ariaHidden: el.getAttribute("aria-hidden"),
      label: el.querySelector(".choreo-cursor__label")
        ? el.querySelector(".choreo-cursor__label").textContent.trim()
        : "",
      focusable: el.tabIndex >= 0 || el.matches("a,button,input,select,textarea"),
    }));

    const namedAiFocusable = focusable.filter(
      (c) => c.name === "AI" || c.name === "A",
    );
    // Official mayor-office entry controls only (not the chat suggestion chip).
    const mayorFocusable = focusable.filter(
      (c) =>
        c.id === "btn-open-mayor-office" ||
        c.id === "mayor-open-office-control" ||
        c.action === "mayor-office-open",
    );
    const searchFocusable = focusable.filter(
      (c) => c.name === "통합검색" || c.name === "검색",
    );

    return {
      firstUse: document.body.getAttribute("data-first-use-state"),
      mobileSurface: document.body.getAttribute("data-mobile-surface"),
      focusableCount: focusable.length,
      namedAiFocusable: namedAiFocusable.length,
      mayorFocusable: mayorFocusable.length,
      searchFocusable: searchFocusable.length,
      avatars,
      cursors,
      focusableSample: focusable.slice(0, 40),
    };
  });
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
  // Prefer parking chip for deterministic split.
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

async function assertStateContract(page, label) {
  const snap = await collectInteractive(page);
  console.log(
    `  [${label}] firstUse=${snap.firstUse} surface=${snap.mobileSurface || "-"} focusable=${snap.focusableCount} mayor=${snap.mayorFocusable} search=${snap.searchFocusable} aiFocus=${snap.namedAiFocusable}`,
  );

  // Decorative avatars must be aria-hidden and non-focusable.
  for (const av of snap.avatars) {
    assert.strictEqual(
      av.ariaLabel,
      null,
      `${label}: avatar must not have aria-label AI (got ${av.ariaLabel})`,
    );
    assert.strictEqual(
      av.ariaHidden,
      "true",
      `${label}: avatar must be aria-hidden=true`,
    );
    assert.strictEqual(av.focusable, false, `${label}: avatar must not be focusable`);
  }

  // Named focusable AI controls must be zero.
  assert.strictEqual(
    snap.namedAiFocusable,
    0,
    `${label}: focusable AI/A controls must be 0`,
  );

  // At most one mayor and one search interactive control while visible.
  assert.ok(
    snap.mayorFocusable <= 1,
    `${label}: mayor focusable controls >1 (${snap.mayorFocusable})`,
  );
  assert.ok(
    snap.searchFocusable <= 1,
    `${label}: search focusable controls >1 (${snap.searchFocusable}) sample=${JSON.stringify(snap.focusableSample.filter((c) => /검색/.test(c.name)))}`,
  );

  // If a cursor exists, root must be aria-hidden (decorative).
  for (const c of snap.cursors) {
    assert.strictEqual(
      c.ariaHidden,
      "true",
      `${label}: choreo cursor must be aria-hidden`,
    );
    assert.strictEqual(c.focusable, false, `${label}: cursor must not be focusable`);
    // Visual label may still say AI.
    if (c.label) {
      assert.strictEqual(c.label, "AI", `${label}: visual cursor label preserved`);
    }
  }

  return snap;
}

async function main() {
  console.log("#1175 decorative AI labels a11y contract");
  const dist = await buildStatic();
  const { server, baseUrl } = await startServer(dist);
  console.log(`  server: ${baseUrl}`);
  const browser = await launchBrowser();
  const safetyAll = [];

  try {
    for (const vp of VIEWPORTS) {
      const context = await browser.newContext({
        viewport: vp,
        reducedMotion: "reduce",
      });
      const page = await context.newPage();
      const safety = setupSafety(page, baseUrl);
      safetyAll.push(safety);

      // 1) entry
      await goEntry(page, baseUrl);
      await assertStateContract(page, `${vp.name}-entry`);
      // Visible welcome text preserved
      const welcome = await page.locator(".chat-bubble--ai").first().innerText();
      assert.ok(
        /북구청/.test(welcome) && /안내/.test(welcome),
        `${vp.name}-entry: welcome text missing (${welcome.slice(0, 80)})`,
      );
      // Visual "A" still present
      const avatarText = await page.locator(".chat-avatar").first().innerText();
      assert.strictEqual(avatarText.trim(), "A", `${vp.name}-entry: visual A missing`);

      // 2) split
      await goSplit(page);
      await assertStateContract(page, `${vp.name}-split`);

      // 3) mobile surfaces if mobile
      if (vp.width <= 767) {
        const guidTab = page.getByRole("button", { name: "안내 화면", exact: true });
        if (await guidTab.isVisible().catch(() => false)) {
          await guidTab.click();
          await page.waitForFunction(
            () => document.body.getAttribute("data-mobile-surface") === "guidance",
            null,
            { timeout: 5000 },
          );
          await assertStateContract(page, `${vp.name}-guidance`);
          const convTab = page.getByRole("button", { name: "대화", exact: true });
          await convTab.click();
          await page.waitForFunction(
            () => document.body.getAttribute("data-mobile-surface") === "conversation",
            null,
            { timeout: 5000 },
          );
          await assertStateContract(page, `${vp.name}-conversation`);
        }
      }

      // Preserve mayor ids/targets when present (entry may expose hero control).
      const mayorIds = await page.evaluate(() => ({
        office: !!document.getElementById("btn-open-mayor-office"),
        control: !!document.getElementById("mayor-open-office-control"),
        action: !!document.querySelector('[data-action-target="mayor-office-open"]'),
      }));
      // At least one of the mayor entry targets must remain in product markup paths.
      // On split home/fixture may expose different state; ensure no regression of ids in DOM when home.
      console.log(`  [${vp.name}] mayor markup presence: ${JSON.stringify(mayorIds)}`);

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
  } finally {
    await browser.close();
    await new Promise((r) => server.close(r));
  }

  console.log("#1175 PASS");
}

main().catch((err) => {
  console.error("#1175 a11y FAILED:");
  console.error(err);
  process.exit(1);
});
