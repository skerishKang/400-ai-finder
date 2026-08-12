/**
 * Browser E2E verifier for #1232 generic offline structural preview QA.
 *
 * Pure offline harness. It:
 *   1. builds the preview into an OS temp dir via the CLI (no network);
 *   2. serves it from 127.0.0.1 on an OS-assigned port (port 0);
 *   3. launches an already-installed Chrome/Chromium (no browser download);
 *   4. aborts any non-loopback request;
 *   5. verifies route/content/a11y/responsive/network contracts;
 *   6. cleans up.
 *
 * Reuses only the existing Playwright 1.61.1 dependency. No new dependency.
 *
 * Usage:
 *   node tests/browser/verify_generic_offline_preview_e2e.mjs
 */

import assert from "assert";
import { spawn, spawnSync } from "child_process";
import {
  mkdtempSync,
  rmSync,
  readFileSync,
  readdirSync,
  statSync,
} from "fs";
import { tmpdir } from "os";
import { join, dirname } from "path";
import { fileURLToPath } from "url";
import { createServer } from "net";

function getFreePort() {
  return new Promise((resolve, reject) => {
    const srv = createServer();
    srv.listen(0, "127.0.0.1", () => {
      const port = srv.address().port;
      srv.close(() => resolve(port));
    });
    srv.on("error", reject);
  });
}

const __filename = fileURLToPath(import.meta.url);
const REPO_ROOT = join(dirname(__filename), "..", "..");
const BUNDLE = join(
  REPO_ROOT,
  "tests",
  "fixtures",
  "platform",
  "site-model",
  "seogu.json",
);
const SCRIPT = join(REPO_ROOT, "scripts", "build_offline_site_preview.py");
const PYTHON = process.env.PYTHON_BIN || "python";

// ── Known browser executable paths for fallback (no browser download) ─────
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
  for (const p of KNOWN_BROWSER_PATHS) {
    let exists = false;
    try {
      readFileSync(p);
      exists = true;
    } catch (_) {}
    if (exists) {
      attempts.push({
        name: `path: ${p}`,
        launch: () => chromium.launch({ headless: true, executablePath: p }),
      });
    }
  }
  attempts.push({
    name: "default playwright chromium",
    launch: () => chromium.launch({ headless: true }),
  });

  for (const attempt of attempts) {
    try {
      const browser = await attempt.launch();
      console.log(`  Browser launched (${attempt.name}) ✓`);
      return browser;
    } catch (e) {
      errors.push(`  [${attempt.name}] ${e.message}`);
    }
  }
  throw new Error(`Cannot launch any browser. Attempts:\n${errors.join("\n")}`);
}

function isLocal(url) {
  try {
    const parsed = new URL(url);
    const host = parsed.hostname.replace(/^\[|\]$/g, "");
    return (
      (parsed.protocol === "http:" || parsed.protocol === "https:") &&
      (host === "127.0.0.1" || host === "localhost" || host === "::1")
    );
  } catch {
    return false;
  }
}

// import chromium lazily so a missing module fails clearly, not at parse time.
import { chromium } from "playwright";

function walk(dir, base = dir) {
  const out = [];
  for (const entry of readdirSync(dir)) {
    const full = join(dir, entry);
    const st = statSync(full);
    if (st.isDirectory()) out.push(...walk(full, base));
    else out.push(full.slice(base.length + 1));
  }
  return out;
}

async function waitForServer(base, timeoutMs = 15000) {
  const deadline = Date.now() + timeoutMs;
  while (Date.now() < deadline) {
    try {
      const res = await fetch(base + "/");
      if (res.ok) return;
    } catch (_) {
      /* not ready */
    }
    await new Promise((r) => setTimeout(r, 100));
  }
  throw new Error("preview server did not become ready");
}

function escSubstr(value) {
  return String(value)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");
}

async function main() {
  // ── Build preview into OS temp dir (no network) ──────────────────────────
  const OUT_DIR = mkdtempSync(join(tmpdir(), "400-ai-finder-1232-"));
  const build = spawnSync(
    PYTHON,
    [SCRIPT, "--bundle", BUNDLE, "--out-dir", OUT_DIR],
    { encoding: "utf-8" },
  );
  assert.strictEqual(
    build.status,
    0,
    `preview build failed:\n${build.stdout}\n${build.stderr}`,
  );
  console.log("  preview built -> " + OUT_DIR);

  // ── Serve on an OS-assigned free port (127.0.0.1) ───────────────────────
  const port = await getFreePort();
  const server = spawn(
    PYTHON,
    [
      "-m",
      "http.server",
      String(port),
      "--bind",
      "127.0.0.1",
      "--directory",
      OUT_DIR,
    ],
    { encoding: "utf-8" },
  );
  server.stderr.on("data", (d) => process.stderr.write(String(d)));
  const cleanup = () => {
    try {
      server.kill("SIGKILL");
    } catch (_) {}
    try {
      rmSync(OUT_DIR, { recursive: true, force: true });
    } catch (_) {}
  };
  try {
    const BASE = `http://127.0.0.1:${port}`;
    await waitForServer(BASE);

    // ── Browser ─────────────────────────────────────────────────────────────
    const browser = await launchBrowser();
    const externalRequests = [];
    const pageErrors = [];

    const context = await browser.newContext({
      viewport: { width: 1440, height: 900 },
      reducedMotion: "reduce",
    });
    const page = await context.newPage();
    await page.route("**/*", (route) => {
      const url = route.request().url();
      if (isLocal(url)) route.continue();
      else {
        externalRequests.push(url);
        route.abort();
      }
    });
    page.on("pageerror", (e) => pageErrors.push("pageerror: " + e.message));
    page.on("console", (msg) => {
      if (msg.type() === "error") pageErrors.push("console: " + msg.text());
    });

    // ── ROUTE ────────────────────────────────────────────────────────────────
    await page.goto(BASE + "/", { waitUntil: "networkidle", timeout: 15000 });

    const manifest = JSON.parse(
      readFileSync(join(OUT_DIR, "preview-manifest.json"), "utf-8"),
    );
    const expectedPaths = new Set([
      manifest.root_output_path,
      ...manifest.routes.map((r) => r.output_path),
    ]);
    const actualFiles = new Set(
      walk(OUT_DIR, OUT_DIR).filter((f) => f.endsWith(".html")),
    );
    assert.deepStrictEqual(
      actualFiles,
      expectedPaths,
      `route files mismatch: ${[...actualFiles]} vs ${[...expectedPaths]}`,
    );

    // Every modeled local route resolves over HTTP.
    for (const path of expectedPaths) {
      const res = await fetch(BASE + "/" + path);
      assert.strictEqual(
        res.status,
        200,
        `route not served 200: ${path} (${res.status})`,
      );
      assert.ok(
        (res.headers.get("content-type") || "").includes("text/html"),
        `route not html: ${path}`,
      );
    }

    // Links exactly action-graph derived.
    const linkData = await page.evaluate(() =>
      Array.from(document.querySelectorAll("a")).map((a) => ({
        href: a.getAttribute("href"),
        text: a.textContent.trim(),
      })),
    );
    assert.strictEqual(
      linkData.length,
      manifest.action_count,
      `expected ${manifest.action_count} links, got ${linkData.length}`,
    );
    for (const l of linkData) {
      assert.ok(l.href, "link must have href");
      assert.ok(l.href.startsWith("routes/"), `unexpected link href: ${l.href}`);
      assert.ok(l.text.length > 0, "link must have non-empty text");
      const res = await fetch(BASE + "/" + l.href);
      assert.strictEqual(res.status, 200, `link target missing: ${l.href}`);
    }

    // ── CONTENT ──────────────────────────────────────────────────────────────
    const bundle = JSON.parse(readFileSync(BUNDLE, "utf-8"));
    const byRoute = new Map(
      bundle.site_model.routes.map((r) => [r.route_id, r]),
    );
    for (const [rid, rt] of byRoute) {
      if (rid === manifest.root_output_path.replace(".html", "") &&
          rid === "route-homepage") {
        // root handled separately
      }
      if (rid === "route-homepage") continue;
      const html = readFileSync(join(OUT_DIR, `routes/${rid}.html`), "utf-8");
      for (const key of ["title", "category", "content_type", "document_id"]) {
        const val = rt[key];
        if (val !== null && val !== undefined) {
          assert.ok(
            html.includes(escSubstr(val)),
            `route ${rid}: ${key} not rendered`,
          );
        }
      }
      if (rt.source_types) {
        const st = Array.isArray(rt.source_types)
          ? rt.source_types.join(", ")
          : rt.source_types;
        assert.ok(
          html.includes(escSubstr(st)),
          `route ${rid}: source_types not rendered`,
        );
      }
    }

    // Capability state parity on root.
    const rootHtml = readFileSync(join(OUT_DIR, "index.html"), "utf-8");
    for (const b of bundle.capability_bindings) {
      assert.ok(rootHtml.includes(b.capability_id), `capability id ${b.capability_id}`);
      assert.ok(rootHtml.includes(b.candidate_state), `candidate ${b.candidate_state}`);
      assert.ok(rootHtml.includes(b.binding_state), `binding ${b.binding_state}`);
    }
    // review_required stays review_required (not "supported").
    assert.ok(
      (rootHtml.match(/review_required/g) || []).length >= 2,
      "directory review_required must remain",
    );
    assert.ok(!rootHtml.includes("supported"), "review_required must not read as supported");

    // ── A11Y ────────────────────────────────────────────────────────────────
    const landmarks = await page.evaluate(() => ({
      header: !!document.querySelector("header"),
      nav: !!document.querySelector("nav"),
      main: !!document.querySelector("main"),
      footer: !!document.querySelector("footer"),
      buttons: document.querySelectorAll("button").length,
      inputs: document.querySelectorAll("input").length,
      selects: document.querySelectorAll("select").length,
      textareas: document.querySelectorAll("textarea").length,
      anchors: Array.from(document.querySelectorAll("a")).map((a) =>
        a.textContent.trim(),
      ),
    }));
    assert.ok(landmarks.header, "header landmark required");
    assert.ok(landmarks.nav, "nav landmark required (root has outgoing actions)");
    assert.ok(landmarks.main, "main landmark required");
    assert.ok(landmarks.footer, "footer landmark required");
    assert.strictEqual(landmarks.buttons, 0, "no button allowed");
    assert.strictEqual(landmarks.inputs, 0, "no input allowed");
    assert.strictEqual(landmarks.selects, 0, "no select allowed");
    assert.strictEqual(landmarks.textareas, 0, "no textarea allowed");
    for (const t of landmarks.anchors) {
      assert.ok(t.length > 0, "every link needs a non-empty accessible name");
    }
    const uniqueAnchors = new Set(landmarks.anchors);
    assert.strictEqual(
      uniqueAnchors.size,
      landmarks.anchors.length,
      "no duplicate interactive control names",
    );

    // Keyboard Tab reaches a modeled link (summary is focusable first; keep
    // tabbing until an anchor is focused).
    await page.evaluate(() => document.body.focus());
    let focusedTag = "";
    for (let i = 0; i < 20; i++) {
      await page.keyboard.press("Tab");
      focusedTag = await page.evaluate(
        () => document.activeElement && document.activeElement.tagName,
      );
      if (focusedTag === "A") break;
    }
    assert.strictEqual(focusedTag, "A", "Tab must reach a modeled link");

    // Route page has header/main/footer and NO nav.
    const routePage = await context.newPage();
    await routePage.goto(BASE + "/routes/route-000001.html", {
      waitUntil: "networkidle",
    });
    const routeLandmarks = await routePage.evaluate(() => ({
      header: !!document.querySelector("header"),
      nav: !!document.querySelector("nav"),
      main: !!document.querySelector("main"),
      footer: !!document.querySelector("footer"),
    }));
    assert.ok(routeLandmarks.header, "route header required");
    assert.ok(!routeLandmarks.nav, "route page must NOT have nav");
    assert.ok(routeLandmarks.main, "route main required");
    assert.ok(routeLandmarks.footer, "route footer required");
    await routePage.close();

    // ── RESPONSIVE ───────────────────────────────────────────────────────────
    for (const vp of [
      { width: 390, height: 844 },
      { width: 1440, height: 900 },
    ]) {
      await page.setViewportSize(vp);
      await page.goto(BASE + "/", { waitUntil: "networkidle" });
      const overflow = await page.evaluate(() => {
        const de = document.documentElement;
        return de.scrollWidth - window.innerWidth;
      });
      assert.ok(
        overflow <= 1,
        `horizontal overflow at ${vp.width}x${vp.height}: ${overflow}px`,
      );
    }

    // ── NETWORK ────────────────────────────────────────────────────────────
    assert.deepStrictEqual(
      externalRequests,
      [],
      `external requests: ${externalRequests.join(", ")}`,
    );
    assert.deepStrictEqual(pageErrors, [], `page errors: ${pageErrors.join("\n")}`);

    await browser.close();
    console.log("Generic offline preview E2E passed.");
  } finally {
    cleanup();
  }
}

main().catch((error) => {
  console.error("Generic offline preview E2E FAILED:");
  console.error(error && error.stack ? error.stack : error);
  process.exit(1);
});
