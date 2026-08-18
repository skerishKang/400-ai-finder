/*
 * seogu-sitespec-metadata.js
 * Seo-gu (서구) browser-side projection of the canonical SiteSpec display
 * identity for the citizen UI (#1343 Seo-gu MVP — Buk-gu parity slice).
 *
 * This is the SITE-SPECIFIC data island that parameterizes the shared
 * Buk-gu canonical resident shell. It deliberately mirrors the shape of
 * citizen-sitespec-metadata.js (Buk-gu) so the shared shell reads either
 * projection through one interface — but NO Buk-gu facts, questions or
 * routes are hardcoded into the shared shell. Buk-gu-specific data lives in
 * Buk-gu's own metadata module; Seo-gu data lives here.
 *
 * AUTHORITATIVE SOURCE: configs/sites/seogu_gwangju.yml
 * Locale fallback rule: vi / th / id have no SiteSpec locale institution
 * label, so their derived names deterministically fall back to the approved
 * English display label "Gwangju Seo-gu". No new translations are invented.
 */

(function () {
  "use strict";

  var INSTITUTION = Object.freeze({
    default_label: "서구청",
    locale_labels: Object.freeze({
      ko: "서구청",
      en: "Gwangju Seo-gu",
    }),
    names: Object.freeze({
      ko: "서구청",
      en: "Gwangju Seo-gu",
      vi: "Gwangju Seo-gu",
      th: "Gwangju Seo-gu",
      id: "Gwangju Seo-gu",
    }),
  });

  window.SeoguSiteSpecMetadata = Object.freeze({
    site_id: "seogu_gwangju",
    schema_version: "1.0.0",
    display: INSTITUTION,
    // Clone root for the bounded same-origin READ surface (kept in sync with
    // municipal-site-surface-registry.js seogu_gwangju.clone_root).
    clone_root: "/seogu/",
    // Resident-facing shell copy. Mirrors Buk-gu copy structure but is
    // Seo-gu-specific text — never a hardcoded Buk-gu string.
    copy: Object.freeze({
      product_title: "서구청 AI 민원 네비게이터",
      eyebrow: "SEOGU AI CIVIC NAVIGATOR",
      hero_headline: "서구의 모든 행정,<br /><em>한 문장으로.</em>",
      hero_sub: "찾고, 클릭하고, 작성하는 과정까지 AI가 주민과 함께합니다.",
      vision_label: "SEOGU VISION",
      vision_text: "주민이 체감하는 AI 행정",
      agent_ready: "AI AGENT READY",
      chat_title: "AI 민원 네비게이터",
      greeting:
        "안녕하세요. 서구청 민원 안내 AI입니다. 궁금한 사항을 물어보시면 관련 화면을 함께 열어 경로를 안내해 드립니다.",
      composer_hint: "첫 질문 후 서구청 안내 화면과 함께 경로를 보여드립니다.",
      privacy_warning:
        "주민등록번호·전화번호·이메일·상세주소 등 개인정보는 입력하지 마세요.",
      service_attribution: "AI Agent by PADIEM",
      disclosure:
        "본 AI 행정서비스 시연 시스템은 주식회사 파디엠(PADIEM)이 기획·개발했습니다.",
      canvas_loading: "서구청 안내 화면을 준비하는 중…",
      canvas_label: "서구청 안내 화면",
    }),
  });
})();
