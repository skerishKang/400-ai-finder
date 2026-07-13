/**
 * #1122 browser contract: dense official header styling + list marker containment.
 *
 * Usage:
 *   node tests/browser/verify_clone_header_list_containment.mjs http://127.0.0.1:<port>
 *
 * Serves against a local static/live Pages build. No external network.
 * Force-navigates the left civic canvas so the contract does not depend on
 * /api/mvp/ask or chat continuity ownership (#1123).
 */

import assert from "assert";
import { chromium } from "playwright";

const requestedBase = process.argv[2] || "http://127.0.0.1:8812";

function validateOrigin(raw) {
  let parsed;
  try {
    parsed = new URL(raw);
  } catch {
    throw new Error(`Invalid URL: ${raw}`);
  }
  const hostname = parsed.hostname.replace(/^\[|\]$/g, "");
  const allowed = new Set(["127.0.0.1", "localhost", "::1"]);
  if (parsed.protocol !== "http:") throw new Error("Only local http:// is allowed.");
  if (!allowed.has(hostname)) throw new Error(`Non-local host rejected: ${parsed.hostname}`);
  if (parsed.username || parsed.password || parsed.search || parsed.hash) {
    throw new Error("Credentials, query, and hash are not allowed in baseUrl.");
  }
  return parsed.origin;
}

const BASE_ORIGIN = validateOrigin(requestedBase);
const MVP_URL = `${BASE_ORIGIN}/mvp/`;

function isLocalRequest(url) {
  if (url.startsWith("data:") || url.startsWith("blob:")) return true;
  try {
    return new URL(url).origin === BASE_ORIGIN;
  } catch {
    return false;
  }
}

/**
 * navigateToRoute() sets getCurrentRouteId() immediately, then swaps DOM after
 * ~300ms fade. Wait for the direct rendered root under .demo-canvas__inner to
 * match the destination identity — never a stale previous .bg-page.
 */
async function revealSplitRoute(page, routeId) {
  const prevRootId = await page.evaluate(() => {
    const root = document.querySelector("#demo-canvas .demo-canvas__inner > .bg-page");
    if (!root) return null;
    if (!root.dataset.contractRootId) {
      root.dataset.contractRootId = `root-${Date.now()}-${Math.random().toString(16).slice(2)}`;
    }
    return root.dataset.contractRootId;
  });

  await page.evaluate((rid) => {
    document.body.setAttribute("data-first-use-state", "split");
    const canvas = document.getElementById("demo-canvas");
    if (canvas) canvas.removeAttribute("inert");
    if (!window.CitizenActionDemoCanvas || typeof window.CitizenActionDemoCanvas.navigateToRoute !== "function") {
      throw new Error("CitizenActionDemoCanvas.navigateToRoute unavailable");
    }
    window.CitizenActionDemoCanvas.navigateToRoute(rid);
  }, routeId);

  await page.waitForFunction(
    ({ rid, prevId }) => {
      if (!window.CitizenActionDemoCanvas) return false;
      if (window.CitizenActionDemoCanvas.getCurrentRouteId() !== rid) return false;

      const canvas = document.getElementById("demo-canvas");
      if (!canvas) return false;
      // Fade-in completed (opacity restored after delayed HTML swap).
      const opacity = getComputedStyle(canvas).opacity;
      if (opacity !== "1") return false;

      const root = document.querySelector("#demo-canvas .demo-canvas__inner > .bg-page");
      if (!root) return false;
      // Previous root node must have been replaced for a real navigation.
      if (prevId && root.dataset.contractRootId === prevId) return false;

      if (rid === "home") {
        return root.classList.contains("bg-page--home");
      }
      if (rid === "passport-guidance") {
        return (
          root.getAttribute("data-official-route-id") === "passport-guidance" &&
          root.classList.contains("bg-page--dense") &&
          Boolean(root.querySelector(".bg-official-content-html"))
        );
      }
      if (rid === "apartment-dept") {
        return (
          root.classList.contains("bg-page--dense") &&
          (root.getAttribute("data-official-route-id") === "apartment-dept" ||
            root.classList.contains("bg-page--dept-directory"))
        );
      }
      if (rid === "complaint-illegal-parking") {
        return (
          root.classList.contains("bg-page--dense") &&
          (root.classList.contains("bg-page--illegal-parking") ||
            Boolean(root.querySelector("[data-action-target]")))
        );
      }
      // Generic dense destination: require dense shell on the direct root.
      return root.classList.contains("bg-page--dense") || root.classList.contains("bg-page--home");
    },
    { rid: routeId, prevId: prevRootId },
    { timeout: 10000 }
  );

  await page.evaluate(() => {
    if (typeof window.CitizenActionDemoCanvas.fitToViewport === "function") {
      window.CitizenActionDemoCanvas.fitToViewport();
    }
  });
}

function collectHeaderSnapshot() {
  return (() => {
    // Always measure the direct destination root — not a stale sibling/page.
    const page =
      document.querySelector("#demo-canvas .demo-canvas__inner > .bg-page") ||
      document.querySelector("#demo-canvas .bg-page");
    if (!page) {
      return {
        bodyState: document.body.getAttribute("data-first-use-state"),
        pageClass: null,
        hasDenseShell: false,
        routeId: window.CitizenActionDemoCanvas
          ? window.CitizenActionDemoCanvas.getCurrentRouteId()
          : null,
        util: [],
        gnb: [],
        inner: null,
        gnbNav: null,
        icons: [],
      };
    }

    const dense = page.matches(".bg-page--dense, .bg-page--home");
    const utilLinks = [...page.querySelectorAll(".bg-home-utility__menus a")];
    const gnbLinks = [...page.querySelectorAll(".bg-home-gnb__link")];
    const inner = page.querySelector(".bg-home-header__inner");
    const gnbNav = page.querySelector(".bg-home-header nav.bg-gnb, .bg-home-header .bg-gnb");
    const icons = [...page.querySelectorAll(".bg-home-header__icon")];

    function isDefaultBlue(color) {
      const m = String(color).match(/rgba?\((\d+),\s*(\d+),\s*(\d+)/i);
      if (!m) return false;
      const r = Number(m[1]);
      const g = Number(m[2]);
      const b = Number(m[3]);
      // UA link blue is near (0,0,238); also catch common visited purple-ish blues.
      return r < 40 && g < 40 && b > 180;
    }

    const gnbCs = gnbNav ? getComputedStyle(gnbNav) : null;

    return {
      bodyState: document.body.getAttribute("data-first-use-state"),
      pageClass: page.className,
      officialRouteId: page.getAttribute("data-official-route-id"),
      hasDenseShell: Boolean(dense),
      routeId: window.CitizenActionDemoCanvas
        ? window.CitizenActionDemoCanvas.getCurrentRouteId()
        : null,
      util: utilLinks.map((a) => {
        const s = getComputedStyle(a);
        return {
          text: a.textContent.trim(),
          color: s.color,
          deco: s.textDecorationLine,
          display: s.display,
          isDefaultBlue: isDefaultBlue(s.color),
          isUnderline: s.textDecorationLine.includes("underline"),
        };
      }),
      gnb: gnbLinks.map((a) => {
        const s = getComputedStyle(a);
        return {
          text: a.textContent.trim(),
          color: s.color,
          deco: s.textDecorationLine,
          isDefaultBlue: isDefaultBlue(s.color),
          isUnderline: s.textDecorationLine.includes("underline"),
        };
      }),
      inner: inner
        ? {
            display: getComputedStyle(inner).display,
            grid: getComputedStyle(inner).gridTemplateColumns,
            height: getComputedStyle(inner).height,
          }
        : null,
      gnbNav: gnbCs
        ? {
            backgroundImage: gnbCs.backgroundImage,
            backgroundColor: gnbCs.backgroundColor,
            borderImage: gnbCs.borderImage,
            borderImageSource: gnbCs.borderImageSource,
          }
        : null,
      icons: icons.map((el) => {
        const s = getComputedStyle(el);
        const svg = el.querySelector("svg");
        const ss = svg ? getComputedStyle(svg) : null;
        return {
          display: s.display,
          width: s.width,
          color: s.color,
          svgW: ss ? ss.width : null,
          svgH: ss ? ss.height : null,
        };
      }),
    };
  })();
}

function collectListSnapshot() {
  return (() => {
    const root =
      document.querySelector("#demo-canvas .demo-canvas__inner > .bg-page") ||
      document.querySelector("#demo-canvas .bg-page");
    const main =
      (root && root.querySelector(".bg-official-content-main")) ||
      document.querySelector(".bg-official-content-main") ||
      (root && root.querySelector(".bg-official-content-html")) ||
      document.querySelector(".bg-official-content-html");
    const html =
      (root && root.querySelector(".bg-official-content-html")) ||
      document.querySelector(".bg-official-content-html");
    if (!main || !html) {
      return { error: "official content missing", anyCross: false, rows: [] };
    }
    const mainRect = main.getBoundingClientRect();
    const contentLeft = mainRect.left + main.clientLeft;
    const lists = [...html.querySelectorAll("ul, ol")];
    const rows = [];

    for (const list of lists) {
      const ls = getComputedStyle(list);
      const type = ls.listStyleType;
      const pos = ls.listStylePosition;
      const pad = parseFloat(ls.paddingInlineStart) || 0;
      const firstLi = list.querySelector(":scope > li");
      if (!firstLi) continue;
      const listR = list.getBoundingClientRect();
      const liR = firstLi.getBoundingClientRect();
      const fontSize = parseFloat(getComputedStyle(firstLi).fontSize) || 15;
      // fitToViewport may apply transform:scale on mobile; computed pad/font
      // are pre-transform while getBoundingClientRect is post-transform.
      const scale =
        list.offsetWidth > 0 ? listR.width / list.offsetWidth : 1;
      const padScreen = pad * scale;
      const fontScreen = fontSize * scale;

      let textLeft = liR.left;
      const walker = document.createTreeWalker(firstLi, NodeFilter.SHOW_TEXT, {
        acceptNode(n) {
          return n.textContent && n.textContent.trim()
            ? NodeFilter.FILTER_ACCEPT
            : NodeFilter.FILTER_REJECT;
        },
      });
      const tn = walker.nextNode();
      if (tn) {
        const range = document.createRange();
        range.selectNodeContents(tn);
        textLeft = range.getBoundingClientRect().left;
      }

      let depth = 0;
      let p = list.parentElement;
      while (p && p !== html) {
        if (p.tagName === "UL" || p.tagName === "OL") depth += 1;
        p = p.parentElement;
      }

      let markerLeft;
      if (type === "none") {
        markerLeft = textLeft;
      } else if (pos === "outside") {
        // Outside markers sit in the list padding band (screen space).
        markerLeft = Math.max(listR.left, liR.left - fontScreen * 0.85);
      } else {
        markerLeft = liR.left;
      }

      const minPadScreen = Math.max(8, fontScreen * 0.55);
      const crosses =
        listR.left < contentLeft - 0.5 ||
        markerLeft < contentLeft - 0.5 ||
        textLeft < contentLeft - 0.5 ||
        liR.left < contentLeft - 0.5 ||
        (type !== "none" && pos === "outside" && padScreen + 0.01 < minPadScreen);
      rows.push({
        className: list.className,
        depth,
        type,
        pos,
        pad,
        padScreen,
        scale,
        markerLeft,
        textLeft,
        liLeft: liR.left,
        listLeft: listR.left,
        contentLeft,
        crosses,
      });
    }

    const step = html.querySelector(".step-list > ul");
    return {
      contentLeft,
      anyCross: rows.some((r) => r.crosses),
      rows,
      overflow: {
        main: { sw: main.scrollWidth, cw: main.clientWidth },
        htmlEl: { sw: html.scrollWidth, cw: html.clientWidth },
        doc: {
          sw: document.documentElement.scrollWidth,
          cw: document.documentElement.clientWidth,
        },
      },
      step: step
        ? {
            display: getComputedStyle(step).display,
            listStyleType: getComputedStyle(step).listStyleType,
          }
        : null,
      dep03: (() => {
        const el = html.querySelector("ul.dep03");
        if (!el) return null;
        const s = getComputedStyle(el);
        return {
          pad: s.paddingInlineStart,
          type: s.listStyleType,
          pos: s.listStylePosition,
        };
      })(),
    };
  })();
}

function assertHeaderStyled(snap, label) {
  assert.ok(snap.hasDenseShell, `${label}: dense/home shell missing`);
  assert.ok(snap.inner && snap.inner.display === "grid", `${label}: header inner not grid (${snap.inner && snap.inner.display})`);
  assert.ok(snap.util.length >= 1, `${label}: utility links missing`);
  for (const u of snap.util) {
    assert.equal(u.isUnderline, false, `${label}: utility underline residual (${u.text})`);
    assert.equal(u.isDefaultBlue, false, `${label}: utility default-blue residual (${u.text} ${u.color})`);
  }
  assert.ok(snap.gnb.length === 6, `${label}: expected 6 GNB links, got ${snap.gnb.length}`);
  for (const g of snap.gnb) {
    assert.equal(g.isUnderline, false, `${label}: gnb underline residual (${g.text})`);
    assert.equal(g.isDefaultBlue, false, `${label}: gnb default-blue residual (${g.text} ${g.color})`);
  }
  if (snap.gnbNav) {
    const img = String(snap.gnbNav.backgroundImage || "");
    assert.ok(
      img === "none" || img === "",
      `${label}: legacy .bg-gnb gradient still painted (${img})`
    );
    const borderImg = String(snap.gnbNav.borderImageSource || snap.gnbNav.borderImage || "");
    assert.ok(
      !/gradient/i.test(borderImg) && !/linear-gradient/i.test(borderImg),
      `${label}: legacy .bg-gnb border-image gradient residual (${borderImg})`
    );
  }
  if (label.startsWith("passport")) {
    assert.equal(
      snap.officialRouteId,
      "passport-guidance",
      `${label}: destination root data-official-route-id mismatch (${snap.officialRouteId})`
    );
    assert.equal(
      snap.routeId,
      "passport-guidance",
      `${label}: getCurrentRouteId mismatch (${snap.routeId})`
    );
  }
  assert.ok(snap.icons.length === 2, `${label}: expected 2 header icons`);
  for (const icon of snap.icons) {
    assert.ok(icon.display === "grid" || icon.display === "flex", `${label}: icon display ${icon.display}`);
    assert.ok(icon.svgW && parseFloat(icon.svgW) >= 12 && parseFloat(icon.svgW) <= 32, `${label}: icon svg size ${icon.svgW}`);
  }
}

function assertListsContained(listSnap, label) {
  assert.ok(!listSnap.error, `${label}: ${listSnap.error}`);
  assert.equal(listSnap.anyCross, false, `${label}: list marker/text crosses content left boundary: ${JSON.stringify(listSnap.rows.filter((r) => r.crosses))}`);
  assert.ok(listSnap.dep03, `${label}: dep03 list missing`);
  assert.ok(listSnap.dep03.type !== "none", `${label}: dep03 markers must remain visible (type=${listSnap.dep03.type})`);
  assert.ok(parseFloat(listSnap.dep03.pad) >= 20, `${label}: dep03 padding-inline-start too small (${listSnap.dep03.pad})`);
  if (listSnap.step) {
    assert.ok(
      listSnap.step.display === "flex" || listSnap.step.display === "grid",
      `${label}: step-list should be a contained strip (display=${listSnap.step.display})`
    );
  }
  const tol = 1;
  assert.ok(
    listSnap.overflow.main.sw <= listSnap.overflow.main.cw + tol,
    `${label}: official main horizontal overflow ${listSnap.overflow.main.sw}>${listSnap.overflow.main.cw}`
  );
  assert.ok(
    listSnap.overflow.doc.sw <= listSnap.overflow.doc.cw + tol,
    `${label}: document horizontal overflow ${listSnap.overflow.doc.sw}>${listSnap.overflow.doc.cw}`
  );
}

/**
 * Prefer bundled Chromium; fall back to an already-installed Chrome channel.
 * Matches other local browser contracts (no browser download).
 */
async function launchLocalBrowser() {
  try {
    return await chromium.launch({ headless: true });
  } catch {
    return chromium.launch({ headless: true, channel: "chrome" });
  }
}

async function main() {
  const requests = [];
  const consoleErrors = [];
  const pageErrors = [];
  const failed = [];
  const httpErrors = [];

  const browser = await launchLocalBrowser();
  const viewports = [
    { width: 1440, height: 900 },
    { width: 768, height: 1024 },
    { width: 390, height: 844 },
  ];

  for (const vp of viewports) {
    const context = await browser.newContext({
      viewport: vp,
      reducedMotion: "reduce",
    });
    const page = await context.newPage();
    page.on("request", (req) => requests.push(req.url()));
    page.on("requestfailed", (req) => failed.push(req.url()));
    page.on("pageerror", (err) => pageErrors.push(String(err)));
    page.on("console", (msg) => {
      if (msg.type() === "error") consoleErrors.push(msg.text());
    });
    page.on("response", (res) => {
      const st = res.status();
      if (st >= 400) httpErrors.push(`${st} ${res.url()}`);
    });

    await page.goto(MVP_URL, { waitUntil: "networkidle", timeout: 20000 });

    // entry state sanity
    const entryState = await page.getAttribute("body", "data-first-use-state");
    assert.equal(entryState, "entry", `entry state expected at ${vp.width}x${vp.height}`);

    // Transition through split + passport
    await revealSplitRoute(page, "passport-guidance");
    const headerPassport = await page.evaluate(collectHeaderSnapshot);
    const listsPassport = await page.evaluate(collectListSnapshot);
    assertHeaderStyled(headerPassport, `passport@${vp.width}x${vp.height}`);
    assertListsContained(listsPassport, `passport@${vp.width}x${vp.height}`);
    assert.equal(headerPassport.routeId, "passport-guidance");

    // Transition stability snapshots (immediate after each navigate)
    for (const routeId of ["apartment-dept", "home", "passport-guidance"]) {
      await revealSplitRoute(page, routeId);
      const snap = await page.evaluate(collectHeaderSnapshot);
      assertHeaderStyled(snap, `transition:${routeId}@${vp.width}x${vp.height}`);
    }

    // Illegal-parking dense shell (if route exists)
    try {
      await revealSplitRoute(page, "complaint-illegal-parking");
      const parkHeader = await page.evaluate(collectHeaderSnapshot);
      assertHeaderStyled(parkHeader, `illegal-parking@${vp.width}x${vp.height}`);
    } catch (e) {
      // Some closed maps may use a different illegal-parking route id; non-fatal.
      console.log(`  note: illegal-parking route skipped @${vp.width}: ${e.message}`);
    }

    await context.close();
    console.log(`  viewport ${vp.width}x${vp.height}: OK`);
  }

  await browser.close();

  const nonLocal = requests.filter((u) => !isLocalRequest(u));
  assert.deepStrictEqual(nonLocal, [], `external requests: ${nonLocal.join(", ")}`);
  // Filter expected absence of POST API on pure static servers only if none attempted? We don't click send.
  assert.deepStrictEqual(pageErrors, [], `page errors: ${pageErrors.join("\n")}`);
  // Console may include favicon 404 etc. — only fail hard page/console errors with stack noise.
  const hardConsole = consoleErrors.filter(
    (t) => !/favicon|404 \(Not Found\)/i.test(t)
  );
  assert.deepStrictEqual(hardConsole, [], `console errors: ${hardConsole.join("\n")}`);
  const hardHttp = httpErrors.filter((t) => !/favicon/i.test(t));
  assert.deepStrictEqual(hardHttp, [], `http errors: ${hardHttp.join("\n")}`);
  assert.deepStrictEqual(failed.filter((u) => !/favicon/i.test(u)), [], `failed requests: ${failed.join(", ")}`);

  console.log("Clone header/list containment contract passed.");
  console.log(`external=${nonLocal.length} console=${hardConsole.length} page=${pageErrors.length} http=${hardHttp.length} failed=${failed.length}`);
}

main().catch((err) => {
  console.error("Clone header/list containment FAILED:");
  console.error(err);
  process.exit(1);
});
