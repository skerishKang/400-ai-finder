import assert from "assert";

/**
 * #1333 Slice B browser contract.
 * Runs inside an existing localhost-only Playwright context against a full
 * Cloudflare Pages live build. No external provider or official-site request.
 */
export async function verifyMunicipalAiShell(page, baseOrigin) {
  const shellUrl = `${baseOrigin}/static/municipal-ai-shell.html?site_id=seogu_gwangju`;
  let capturedPayload = null;

  // The calling Buk-gu test no longer needs its MVP route after its golden flow.
  // Replace it with the exact Slice-A Seo-gu-unconfigured response so this test
  // proves explicit site_id transport without enabling Slice C runtime data.
  await page.unroute("**/api/mvp/ask");
  await page.route("**/api/mvp/ask", async (route) => {
    capturedPayload = JSON.parse(route.request().postData() || "{}");
    await route.fulfill({
      status: 200,
      contentType: "application/json; charset=utf-8",
      body: JSON.stringify({
        ok: false,
        answer: "서구청 AI 주민 여정은 아직 준비 중입니다.",
        action: "none",
        confidence: 1,
        provider: "site_dispatch",
        model: "none",
        failure_code: "site_unconfigured_for_slice",
        site_id: "seogu_gwangju",
        site_status: "recognized_unconfigured",
        fallback_to_bukgu: false,
      }),
    });
  });

  await page.goto(shellUrl, { waitUntil: "networkidle", timeout: 15000 });
  assert.strictEqual(
    await page.getAttribute("body", "data-surface-state"),
    "ready",
    "known Seo-gu surface must initialize",
  );
  assert.strictEqual(
    await page.getAttribute("body", "data-site-id"),
    "seogu_gwangju",
  );
  assert.ok(
    (await page.textContent("#municipal-ai-title")).includes("서구청"),
    "generic shell must label the selected institution",
  );

  await page.waitForFunction(() => {
    return Boolean(
      window.MunicipalAiShell &&
      window.MunicipalAiShell.getEvidence &&
      window.MunicipalAiShell.getEvidence() &&
      window.MunicipalAiShell.getEvidence().ok,
    );
  }, null, { timeout: 15000 });

  const homeEvidence = await page.evaluate(() => window.MunicipalAiShell.getEvidence());
  assert.strictEqual(homeEvidence.ok, true);
  assert.strictEqual(homeEvidence.grounded, true);
  assert.strictEqual(homeEvidence.evidence_kind, "clone_dom");
  assert.strictEqual(homeEvidence.source_kind, "repository_clone");
  assert.strictEqual(homeEvidence.site_id, "seogu_gwangju");
  assert.strictEqual(homeEvidence.route, "");
  assert.ok(homeEvidence.title.includes("서구청"), "home evidence title must be Seo-gu");
  assert.ok(homeEvidence.text.length > 0 && homeEvidence.text.length <= 6000);
  for (const forbidden of [
    "faithful_clone_candidate",
    "asset_byte_fidelity_complete",
    "capture_id",
    "rc-lifecycle",
    "rc-evidence",
  ]) {
    assert.ok(
      !homeEvidence.text.includes(forbidden),
      `hidden/debug evidence leaked into bounded READ text: ${forbidden}`,
    );
  }

  // Route navigation is bounded by the registry: arbitrary/external-like paths
  // are rejected before the iframe location can change.
  assert.strictEqual(
    await page.evaluate(() => window.MunicipalAiShell.navigate("../../outside/")),
    false,
  );
  assert.strictEqual(
    await page.evaluate(() => window.MunicipalAiShell.navigate("https://example.com/")),
    false,
  );
  assert.strictEqual(
    await page.evaluate(() => window.MunicipalAiShell.navigate("notice/")),
    true,
  );

  const frameHandle = await page.$("#municipal-clone-frame");
  assert.ok(frameHandle, "clone iframe must exist");
  const cloneFrame = await frameHandle.contentFrame();
  assert.ok(cloneFrame, "clone iframe must remain same-origin and readable");
  await cloneFrame.waitForURL(/\/seogu\/notice\/$/, { timeout: 15000 });

  const listEvidence = await page.evaluate(() => window.MunicipalAiShell.getEvidence());
  assert.strictEqual(listEvidence.route, "notice/");
  assert.ok(listEvidence.text.length > 0 && listEvidence.text.length <= 6000);

  // Prove a real clone-local list -> captured detail transition. The renderer
  // emits a genuine focusable anchor with a local href. Activate that anchor by
  // keyboard Enter instead of forcing pointer hit-testing through the iframe;
  // this exercises the browser's normal link-navigation behavior and keeps the
  // test independent of table-cell hitbox geometry.
  const detailLink = cloneFrame.locator("a.rc-list-link[data-detail='1']");
  assert.strictEqual(await detailLink.count(), 1, "notice list must expose one captured detail link");
  const detailHref = await detailLink.getAttribute("href");
  assert.ok(detailHref, "captured detail link must have a local href");
  const detailTarget = new URL(detailHref, cloneFrame.url());
  assert.strictEqual(detailTarget.origin, baseOrigin, "detail link must stay same-origin");
  assert.strictEqual(
    detailTarget.pathname,
    "/seogu/notice/detail/",
    "captured notice link must target the modeled local detail route",
  );
  await detailLink.focus();
  assert.strictEqual(
    await detailLink.evaluate((el) => el.ownerDocument.activeElement === el),
    true,
    "captured detail link must be keyboard-focusable",
  );
  await Promise.all([
    cloneFrame.waitForURL(/\/seogu\/notice\/detail\/$/, { timeout: 15000 }),
    detailLink.press("Enter"),
  ]);

  await page.waitForFunction(() => {
    const evidence = window.MunicipalAiShell && window.MunicipalAiShell.getEvidence();
    return evidence && evidence.ok && evidence.route === "notice/detail/";
  }, null, { timeout: 15000 });
  const detailEvidence = await page.evaluate(() => window.MunicipalAiShell.getEvidence());
  assert.strictEqual(detailEvidence.grounded, true);
  assert.strictEqual(detailEvidence.route, "notice/detail/");
  assert.ok(
    detailEvidence.text.includes("사회연대경제"),
    "post-navigation READ must contain captured Seo-gu detail content",
  );
  assert.ok(detailEvidence.text.length <= 6000, "READ text must remain bounded");

  // Existing bridge must send explicit site identity for the generic shell.
  await page.fill("#municipal-chat-input", "사회연대경제 공고 내용을 알려줘");
  await page.click("#municipal-chat-send");
  await page.waitForFunction(() => {
    const thread = document.querySelector("#municipal-chat-thread");
    return thread && thread.textContent.includes("아직 준비 중입니다");
  }, null, { timeout: 10000 });
  assert.ok(capturedPayload, "generic shell must call the MVP bridge");
  assert.strictEqual(capturedPayload.site_id, "seogu_gwangju");
  assert.strictEqual(capturedPayload.question, "사회연대경제 공고 내용을 알려줘");
  assert.ok(typeof capturedPayload.session_id === "string" && capturedPayload.session_id.length >= 16);

  // Unknown surface identity is fail-closed: no fallback iframe and no composer.
  await page.goto(
    `${baseOrigin}/static/municipal-ai-shell.html?site_id=atlantis_gov`,
    { waitUntil: "domcontentloaded", timeout: 15000 },
  );
  assert.strictEqual(await page.getAttribute("body", "data-surface-state"), "unavailable");
  assert.strictEqual(await page.isDisabled("#municipal-chat-input"), true);
  assert.strictEqual(await page.isDisabled("#municipal-chat-send"), true);
  const unknownSrc = await page.getAttribute("#municipal-clone-frame", "src");
  assert.ok(!unknownSrc, "unknown site must not silently load any clone fallback");

  console.log("Municipal AI shell + bounded clone READ contract passed.");
}
