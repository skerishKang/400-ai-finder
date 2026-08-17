import assert from "assert";

/**
 * Browser E2E for #1333 Slice B + #1335 Slice C + #1337 Slice D.
 * Runs inside an existing localhost-only Playwright context against a full
 * Cloudflare Pages live build. All API/provider behavior is intercepted and
 * deterministic; no external provider or official-site request is made.
 */
export async function verifyMunicipalAiShell(page, baseOrigin) {
  const shellUrl = `${baseOrigin}/static/municipal-ai-shell.html?site_id=seogu_gwangju`;
  let capturedSitePayload = null;
  let capturedGeneralPayload = null;
  let siteApiCalls = 0;
  let generalApiCalls = 0;

  await page.unroute("**/api/mvp/ask");
  await page.route("**/api/mvp/ask", async (route) => {
    siteApiCalls += 1;
    capturedSitePayload = JSON.parse(route.request().postData() || "{}");
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

  await page.route("**/api/mvp/general", async (route) => {
    generalApiCalls += 1;
    capturedGeneralPayload = JSON.parse(route.request().postData() || "{}");
    await route.fulfill({
      status: 200,
      headers: { "X-Request-ID": "general-e2e-request-0001" },
      contentType: "application/json; charset=utf-8",
      body: JSON.stringify({
        ok: true,
        question: capturedGeneralPayload.question || "",
        answer: "회의록은 안건별로 결정사항, 담당자, 완료 기한을 분리해 적고 마지막에 후속 조치를 모아 두면 읽기 쉽습니다.",
        action: "none",
        confidence: 0.82,
        provider: "gemini",
        model: "mock-general-model",
        failure_code: "",
        grounded: false,
        source_kind: "general_model",
        evidence_kind: "none",
        answer_scope: "general_model",
        freshness_state: "model_only",
        source_url: "",
        sources: [],
        search_queries: [],
        site_id: "seogu_gwangju",
        site_status: "recognized_unconfigured",
        fallback_to_bukgu: false,
        request_id: "general-e2e-request-0001",
        schema_version: "1.0",
      }),
    });
  });

  await page.goto(shellUrl, { waitUntil: "networkidle", timeout: 15000 });
  assert.strictEqual(
    await page.getAttribute("body", "data-surface-state"),
    "ready",
    "known Seo-gu surface must initialize",
  );
  assert.strictEqual(await page.getAttribute("body", "data-site-id"), "seogu_gwangju");
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

  assert.strictEqual(
    await page.evaluate(() => window.MunicipalAiShell.navigate("../../outside/")),
    false,
  );
  assert.strictEqual(
    await page.evaluate(() => window.MunicipalAiShell.navigate("https://example.com/")),
    false,
  );

  const frameHandle = await page.$("#municipal-clone-frame");
  assert.ok(frameHandle, "clone iframe must exist");
  const cloneFrame = await frameHandle.contentFrame();
  assert.ok(cloneFrame, "clone iframe must remain same-origin and readable");

  const registryContract = await page.evaluate(() => {
    const list = window.MunicipalResidentJourneyRegistry.list("seogu_gwangju");
    return {
      count: list.length,
      ids: list.map((item) => item.journey_id),
      hasStoredAnswer: list.some((item) => Object.prototype.hasOwnProperty.call(item, "answer")),
      piiBearingMatch: Boolean(
        window.MunicipalResidentJourneyRegistry.match(
          "seogu_gwangju",
          "사회연대경제 공고 내용을 알려줘 010-1234-5678",
        ),
      ),
    };
  });
  assert.strictEqual(registryContract.count, 2);
  assert.deepStrictEqual(
    registryContract.ids,
    ["seogu_notice_social_economy", "seogu_organization_leadership"],
  );
  assert.strictEqual(registryContract.hasStoredAnswer, false, "journey config must not store factual final answers");
  assert.strictEqual(registryContract.piiBearingMatch, false, "PII-bearing extra text must not exact-match a local golden journey");

  await page.evaluate(() => {
    window.__municipalJourneyEvidenceRoutes = [];
    window.addEventListener("municipal-clone-evidence", (event) => {
      if (event && event.detail && event.detail.ok) {
        window.__municipalJourneyEvidenceRoutes.push(event.detail.route);
      }
    });
  });

  // ── Journey A: notice list -> captured detail -> READ -> grounded answer ──
  capturedSitePayload = null;
  capturedGeneralPayload = null;
  const siteCallsBeforeNotice = siteApiCalls;
  const generalCallsBeforeNotice = generalApiCalls;
  await page.evaluate(() => { window.__municipalJourneyEvidenceRoutes = []; });
  await page.fill("#municipal-chat-input", "사회연대경제 공고 내용을 알려줘");
  await page.click("#municipal-chat-send");
  await page.waitForFunction(() => {
    const result = window.MunicipalAiShell && window.MunicipalAiShell.getLastJourneyResult();
    return (
      document.body.getAttribute("data-journey-state") === "grounded" &&
      result && result.ok && result.journey_id === "seogu_notice_social_economy"
    );
  }, null, { timeout: 15000 });

  const noticeResult = await page.evaluate(() => window.MunicipalAiShell.getLastJourneyResult());
  const noticeEvidence = await page.evaluate(() => window.MunicipalAiShell.getEvidence());
  const noticeRoutes = await page.evaluate(() => window.__municipalJourneyEvidenceRoutes.slice());
  assert.strictEqual(siteApiCalls, siteCallsBeforeNotice, "supported notice journey must not call site API");
  assert.strictEqual(generalApiCalls, generalCallsBeforeNotice, "supported notice journey must not call general API");
  assert.strictEqual(noticeResult.grounded, true);
  assert.strictEqual(noticeResult.source_kind, "repository_clone");
  assert.strictEqual(noticeResult.evidence_kind, "clone_dom");
  assert.strictEqual(noticeResult.route, "notice/detail/");
  assert.ok(noticeResult.answer.includes("사회연대경제"));
  assert.ok(noticeResult.excerpt.includes("사회연대경제"));
  assert.strictEqual(noticeEvidence.route, "notice/detail/");
  assert.ok(noticeEvidence.text.includes("사회연대경제"));
  for (const line of noticeResult.excerpt.split("\n").filter(Boolean)) {
    assert.ok(noticeEvidence.text.includes(line), `notice answer line must come from READ evidence: ${line}`);
  }
  const noticeListIndex = noticeRoutes.indexOf("notice/");
  const noticeDetailIndex = noticeRoutes.indexOf("notice/detail/");
  assert.ok(noticeListIndex !== -1, `notice journey must load list route; got ${noticeRoutes.join(",")}`);
  assert.ok(noticeDetailIndex > noticeListIndex, `notice detail must follow list route; got ${noticeRoutes.join(",")}`);
  const noticeMessage = page.locator(
    '.message--ai[data-grounded="true"][data-source-kind="repository_clone"][data-journey-id="seogu_notice_social_economy"]',
  );
  assert.strictEqual(await noticeMessage.count(), 1);
  assert.strictEqual(await noticeMessage.getAttribute("data-evidence-route"), "notice/detail/");
  assert.ok((await noticeMessage.textContent()).includes("근거 · 저장소 기반 기관 안내 · notice/detail/"));

  // ── Journey B: different capability family, organization direct READ ─────
  const siteCallsBeforeOrg = siteApiCalls;
  const generalCallsBeforeOrg = generalApiCalls;
  await page.evaluate(() => { window.__municipalJourneyEvidenceRoutes = []; });
  await page.fill("#municipal-chat-input", "서구청 조직도에서 구청장과 부구청장 구조를 알려줘");
  await page.click("#municipal-chat-send");
  await page.waitForFunction(() => {
    const result = window.MunicipalAiShell && window.MunicipalAiShell.getLastJourneyResult();
    return (
      document.body.getAttribute("data-journey-state") === "grounded" &&
      result && result.ok && result.journey_id === "seogu_organization_leadership"
    );
  }, null, { timeout: 15000 });

  const orgResult = await page.evaluate(() => window.MunicipalAiShell.getLastJourneyResult());
  const orgEvidence = await page.evaluate(() => window.MunicipalAiShell.getEvidence());
  const orgRoutes = await page.evaluate(() => window.__municipalJourneyEvidenceRoutes.slice());
  assert.strictEqual(siteApiCalls, siteCallsBeforeOrg, "supported organization journey must not call site API");
  assert.strictEqual(generalApiCalls, generalCallsBeforeOrg, "supported organization journey must not call general API");
  assert.strictEqual(orgResult.grounded, true);
  assert.strictEqual(orgResult.source_kind, "repository_clone");
  assert.strictEqual(orgResult.route, "organization/");
  assert.strictEqual(orgEvidence.route, "organization/");
  for (const marker of ["행정조직도", "구청장", "부구청장"]) {
    assert.ok(orgEvidence.text.includes(marker), `organization READ missing marker: ${marker}`);
    assert.ok(orgResult.answer.includes(marker), `organization grounded answer missing marker: ${marker}`);
  }
  for (const line of orgResult.excerpt.split("\n").filter(Boolean)) {
    assert.ok(orgEvidence.text.includes(line), `organization answer line must come from READ evidence: ${line}`);
  }
  assert.ok(orgRoutes.includes("organization/"), `organization journey must load organization route; got ${orgRoutes.join(",")}`);
  assert.ok(!orgRoutes.includes("notice/detail/"), "organization journey must not be a disguised notice-detail flow");
  const orgMessage = page.locator(
    '.message--ai[data-grounded="true"][data-source-kind="repository_clone"][data-journey-id="seogu_organization_leadership"]',
  );
  assert.strictEqual(await orgMessage.count(), 1);
  assert.strictEqual(await orgMessage.getAttribute("data-evidence-route"), "organization/");
  assert.ok((await orgMessage.textContent()).includes("근거 · 저장소 기반 기관 안내 · organization/"));

  const markerFailure = await page.evaluate(() => {
    const journey = window.MunicipalResidentJourneyRegistry.match(
      "seogu_gwangju",
      "서구청 조직도에서 구청장과 부구청장 구조를 알려줘",
    );
    return window.MunicipalResidentJourney.answerFromEvidence(journey, {
      ok: true,
      grounded: true,
      evidence_kind: "clone_dom",
      source_kind: "repository_clone",
      site_id: "seogu_gwangju",
      route: "organization/",
      title: "행정조직도",
      text: "행정조직도\n구청장",
    });
  });
  assert.strictEqual(markerFailure.ok, false);
  assert.strictEqual(markerFailure.grounded, false);
  assert.strictEqual(markerFailure.failure_code, "journey_evidence_marker_missing");

  // ── Slice D: unmatched question offers model-only answer but does NOT call it
  // until the resident explicitly activates the button.
  capturedSitePayload = null;
  capturedGeneralPayload = null;
  const siteCallsBeforeOffer = siteApiCalls;
  const generalCallsBeforeOffer = generalApiCalls;
  const generalQuestion = "회의록을 깔끔하게 정리하는 방법을 알려줘";
  await page.fill("#municipal-chat-input", generalQuestion);
  await page.click("#municipal-chat-send");
  await page.waitForFunction(() => (
    document.body.getAttribute("data-journey-state") === "general_model_offer" &&
    document.querySelector('[data-general-fallback-offer="true"] [data-general-model-action="request"]')
  ), null, { timeout: 10000 });

  assert.strictEqual(siteApiCalls, siteCallsBeforeOffer, "unmatched question must not silently call site API");
  assert.strictEqual(generalApiCalls, generalCallsBeforeOffer, "unmatched question must not silently call general model");
  const offer = page.locator('[data-general-fallback-offer="true"]');
  assert.ok((await offer.textContent()).includes("기관 홈페이지 근거가 아닌 일반 AI 모델 답변"));

  await offer.locator('[data-general-model-action="request"]').click();
  await page.waitForFunction(() => {
    const result = window.MunicipalAiShell && window.MunicipalAiShell.getLastGeneralResult();
    return document.body.getAttribute("data-journey-state") === "general_model" && result && result.ok;
  }, null, { timeout: 10000 });

  assert.strictEqual(siteApiCalls, siteCallsBeforeOffer, "general opt-in must not call site-grounded API");
  assert.strictEqual(generalApiCalls, generalCallsBeforeOffer + 1, "general model must be called exactly once after opt-in");
  assert.ok(capturedGeneralPayload, "general model request payload must be captured");
  assert.strictEqual(capturedGeneralPayload.site_id, "seogu_gwangju");
  assert.strictEqual(capturedGeneralPayload.question, generalQuestion);
  assert.ok(typeof capturedGeneralPayload.session_id === "string" && capturedGeneralPayload.session_id.length >= 16);

  const generalResult = await page.evaluate(() => window.MunicipalAiShell.getLastGeneralResult());
  assert.strictEqual(generalResult.grounded, false);
  assert.strictEqual(generalResult.source_kind, "general_model");
  assert.strictEqual(generalResult.evidence_kind, "none");
  assert.strictEqual(generalResult.answer_scope, "general_model");
  assert.strictEqual(generalResult.freshness_state, "model_only");
  assert.deepStrictEqual(generalResult.sources, []);
  assert.strictEqual(generalResult.source_url, "");

  const generalMessage = page.locator(
    '.message--ai[data-grounded="false"][data-source-kind="general_model"][data-answer-scope="general_model"]',
  );
  assert.strictEqual(await generalMessage.count(), 1);
  const generalText = await generalMessage.textContent();
  assert.ok(generalText.includes("회의록은 안건별로 결정사항"));
  assert.ok(generalText.includes("근거 · 일반 AI 모델 · 기관 안내 화면 근거 아님"));
  assert.ok(!generalText.includes("근거 · 저장소 기반 기관 안내"));
  assert.strictEqual(await generalMessage.getAttribute("data-evidence-kind"), "none");

  // Unknown surface identity remains fail-closed before either API path exists.
  await page.goto(
    `${baseOrigin}/static/municipal-ai-shell.html?site_id=atlantis_gov`,
    { waitUntil: "domcontentloaded", timeout: 15000 },
  );
  assert.strictEqual(await page.getAttribute("body", "data-surface-state"), "unavailable");
  assert.strictEqual(await page.isDisabled("#municipal-chat-input"), true);
  assert.strictEqual(await page.isDisabled("#municipal-chat-send"), true);
  const unknownSrc = await page.getAttribute("#municipal-clone-frame", "src");
  assert.ok(!unknownSrc, "unknown site must not silently load any clone fallback");

  console.log("Municipal AI shell grounded journeys + explicit general-model fallback passed.");
}
