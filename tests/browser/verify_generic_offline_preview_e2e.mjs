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
    const interceptedRequests = [];
    const pageErrors = [];

    const context = await browser.newContext({
      viewport: { width: 1440, height: 900 },
      reducedMotion: "reduce",
    });

    // Context-wide interception: every page created from this context - the
    // root page AND every per-route page opened below - is covered. A
    // page-scoped interceptor would leave later pages unguarded.
    await context.route("**/*", (route) => {
      const url = route.request().url();
      interceptedRequests.push(url);
      if (isLocal(url)) route.continue();
      else {
        externalRequests.push(url);
        route.abort();
      }
    });
    context.on("weberror", (e) =>
      pageErrors.push("weberror: " + e.error().message),
    );
    context.on("console", (msg) => {
      if (msg.type() === "error") pageErrors.push("console: " + msg.text());
    });

    const page = await context.newPage();

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

    // ── NAV GRAPH (generic, per source route) ───────────────────────────────
    // Each modeled action must render on the page of its own from_route_id,
    // with an href relative to that page. No root-only assumption: a route
    // with zero outgoing actions has no nav, a route with modeled outgoing
    // actions has a nav holding exactly those actions.
    const bundle = JSON.parse(readFileSync(BUNDLE, "utf-8"));
    const rootRouteId = bundle.site_model.root_route_id;
    const outputPathFor = (rid) =>
      rid === rootRouteId ? "index.html" : `routes/${rid}.html`;
    const resolveHref = (sourcePath, href) => {
      const slash = sourcePath.lastIndexOf("/");
      const base = slash === -1 ? "" : sourcePath.slice(0, slash);
      const joined = base ? `${base}/${href}` : href;
      const out = [];
      for (const seg of joined.split("/")) {
        if (seg === "" || seg === ".") continue;
        if (seg === "..") out.pop();
        else out.push(seg);
      }
      return out.join("/");
    };

    const actionsBySource = new Map();
    for (const a of bundle.action_graph.actions) {
      if (!actionsBySource.has(a.from_route_id)) {
        actionsBySource.set(a.from_route_id, []);
      }
      actionsBySource.get(a.from_route_id).push(a);
    }

    const readNav = (p) =>
      p.evaluate(() => {
        const navEl = document.querySelector("nav");
        return {
          navLinks: navEl
            ? Array.from(navEl.querySelectorAll("a")).map((a) => ({
                href: a.getAttribute("href"),
                text: a.textContent.trim(),
              }))
            : null,
          anchorTotal: document.querySelectorAll("a").length,
          header: !!document.querySelector("header"),
          main: !!document.querySelector("main"),
          footer: !!document.querySelector("footer"),
        };
      });

    const navDistribution = {};
    let renderedLinkTotal = 0;
    for (const route of bundle.site_model.routes) {
      const rid = route.route_id;
      const outPath = outputPathFor(rid);
      const expected = actionsBySource.get(rid) || [];
      // pages created from the same context => covered by context.route above
      const rp = await context.newPage();
      try {
        await rp.goto(`${BASE}/${outPath}`, {
          waitUntil: "networkidle",
          timeout: 15000,
        });
        const observed = await readNav(rp);
        assert.ok(observed.header, `${rid}: header landmark required`);
        assert.ok(observed.main, `${rid}: main landmark required`);
        assert.ok(observed.footer, `${rid}: footer landmark required`);

        if (expected.length === 0) {
          assert.strictEqual(
            observed.navLinks,
            null,
            `${rid}: route with zero outgoing actions must have no nav`,
          );
          assert.strictEqual(
            observed.anchorTotal,
            0,
            `${rid}: route with zero outgoing actions must have no link`,
          );
        } else {
          assert.ok(
            observed.navLinks,
            `${rid}: route with ${expected.length} outgoing action(s) needs nav`,
          );
          assert.strictEqual(
            observed.navLinks.length,
            expected.length,
            `${rid}: nav links must equal modeled outgoing actions`,
          );
          assert.strictEqual(
            observed.anchorTotal,
            observed.navLinks.length,
            `${rid}: anchors outside nav are not modeled`,
          );
          for (let i = 0; i < expected.length; i++) {
            const { href, text } = observed.navLinks[i];
            const target = outputPathFor(expected[i].to_route_id);
            assert.ok(href, `${rid}: link must have href`);
            assert.ok(text.length > 0, `${rid}: link needs accessible name`);
            assert.ok(!href.includes("\\"), `${rid}: backslash href ${href}`);
            assert.ok(
              !href.includes("routes/routes"),
              `${rid}: doubled dir in href ${href}`,
            );
            assert.ok(!href.startsWith("/"), `${rid}: absolute href ${href}`);
            assert.strictEqual(
              resolveHref(outPath, href),
              target,
              `${rid}: href ${href} on ${outPath} must resolve to ${target}`,
            );
            const res = await fetch(`${BASE}/${target}`);
            assert.strictEqual(res.status, 200, `link target missing: ${target}`);
          }
          renderedLinkTotal += observed.navLinks.length;
        }
        navDistribution[rid] = expected.length === 0 ? 0 : observed.navLinks.length;
      } finally {
        await rp.close();
      }
    }

    // 1:1 - every modeled action rendered exactly once, nothing extra.
    assert.strictEqual(
      renderedLinkTotal,
      bundle.action_graph.actions.length,
      `rendered links ${renderedLinkTotal} != modeled actions ${bundle.action_graph.actions.length}`,
    );
    assert.strictEqual(
      renderedLinkTotal,
      manifest.action_count,
      `rendered links ${renderedLinkTotal} != manifest.action_count`,
    );

    // Frozen Seo-gu fixture parity: its action graph is a root star, so the
    // generic renderer must place 9 links on root and 0 on every route page.
    assert.strictEqual(navDistribution[rootRouteId], 9, "root nav must be 9");
    const nonRootNav = Object.entries(navDistribution).filter(
      ([rid]) => rid !== rootRouteId,
    );
    assert.strictEqual(nonRootNav.length, 9, "expected 9 non-root routes");
    for (const [rid, count] of nonRootNav) {
      assert.strictEqual(count, 0, `${rid}: frozen fixture models no outgoing action`);
    }
    console.log(
      `  nav graph: root=${navDistribution[rootRouteId]} links, ` +
        `non-root=${nonRootNav.map(([, c]) => c).join(",")} ` +
        `(total ${renderedLinkTotal} = ${manifest.action_count} modeled actions)`,
    );

    // ── CONTENT ──────────────────────────────────────────────────────────────
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
    // nav presence is derived from the modeled graph, never assumed.
    const rootExpectedOutgoing = (actionsBySource.get(rootRouteId) || []).length;
    assert.strictEqual(
      landmarks.nav,
      rootExpectedOutgoing > 0,
      `root nav presence must match its ${rootExpectedOutgoing} modeled outgoing action(s)`,
    );
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
    // tabbing until an anchor is focused). Only meaningful when the route
    // actually models outgoing actions.
    if (rootExpectedOutgoing > 0) {
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
    }

    // ── CONTEXT-WIDE INTERCEPTION COVERAGE ──────────────────────────────────
    // Proof the interceptor is context-scoped, not root-page-scoped: the
    // context handler observed the document request of every per-route page
    // created after context.route() was installed.
    for (const route of bundle.site_model.routes) {
      const outPath = outputPathFor(route.route_id);
      assert.ok(
        interceptedRequests.includes(`${BASE}/${outPath}`),
        `context interceptor never saw ${outPath}; interception is not context-wide`,
      );
    }

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
    // Context-wide: covers the root page and every per-route page.
    assert.deepStrictEqual(
      externalRequests,
      [],
      `external requests: ${externalRequests.join(", ")}`,
    );
    assert.strictEqual(externalRequests.length, 0, "external request count must be 0");
    for (const url of interceptedRequests) {
      assert.ok(isLocal(url), `non-loopback request slipped through: ${url}`);
    }
    assert.deepStrictEqual(pageErrors, [], `page errors: ${pageErrors.join("\n")}`);
    console.log(
      `  network: ${interceptedRequests.length} intercepted (all loopback), ` +
        `${externalRequests.length} external`,
    );

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
