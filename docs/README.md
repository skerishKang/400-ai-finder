# Docs

> 400-ai-finder / AI파인더 문서 목록 — 파일을 기능/성격별로 분류하여 정리

---

## 제품 문서

제품의 개요, 문제 정의, 범위, 아키텍처, 시나리오 등을 정의하는 핵심 문서입니다.

| 파일 | 설명 |
|------|------|
| [`00-product-brief.md`](00-product-brief.md) | 제품 개요 — AI 홈페이지 파인더 소개 |
| [`01-problem-definition.md`](01-problem-definition.md) | 문제 정의 — 사용자가 겪는 정보 탐색 어려움 |
| [`02-mvp-scope.md`](02-mvp-scope.md) | MVP 범위 — 초기 버전의 기능과 제약 |
| [`03-system-architecture.md`](03-system-architecture.md) | 시스템 아키텍처 — 수집/분석/응답 파이프라인 |
| [`04-user-scenarios.md`](04-user-scenarios.md) | 사용자 시나리오 — 대표적인 질문-답변 흐름 |
| [`05-model-plan.md`](05-model-plan.md) | 모델 활용 계획 — 모델 독립적 구조와 교체 방안 |
| [`06-roadmap.md`](06-roadmap.md) | 로드맵 — 단계별 개발 계획 (Stage 0~) |

---

## MVP / 데모 문서

MVP 정적 데모 시연과 관련된 문서입니다. 북구청 스냅샷 기반 데모, 골든 퀘스트, 발표 자료 등을 포함합니다.

| 파일 | 설명 |
|------|------|
| [`mvp-demo-milestone-snapshot.md`](mvp-demo-milestone-snapshot.md) | MVP 데모 마일스톤 스냅샷 — 현재 완료/미완료 상태 기록 |
| [`mvp-golden-quest-fidelity-matrix.md`](mvp-golden-quest-fidelity-matrix.md) | MVP 골든 퀘스트 정합성 매트릭스 — 5개 대표 퀘스트 정합성 계약 |
| [`mvp-demo-operator-runbook.md`](mvp-demo-operator-runbook.md) | MVP 데모 운영 매뉴얼 — 리뷰어/운영자용 실행 안내 |
| [`cloudflare-pages-bukgu-mvp.md`](cloudflare-pages-bukgu-mvp.md) | Cloudflare Pages 북구 MVP 정적 시연 배포 |
| [`bukgu-quest-engine.md`](bukgu-quest-engine.md) | 북구 퀘스트 엔진 Phase 1 — 시나리오 기반 경로 |
| [`bukgu-demo-presentation-outline.md`](bukgu-demo-presentation-outline.md) | 북구 데모 발표 구성안 |
| [`bukgu-demo-one-page-handout.md`](bukgu-demo-one-page-handout.md) | 북구 데모 요약자료 (원페이지) |
| [`bukgu-live-demo-package.md`](bukgu-live-demo-package.md) | 북구 라이브 LLM 데모 패키지 |
| [`demo-scenario.md`](demo-scenario.md) | 시연 시나리오 — 북구청 + 광주광역시청 |

---

## 운영 문서

운영자가 시스템을 안전하게 실행하고 모니터링하며 품질을 평가하기 위한 안내서입니다.

| 파일 | 설명 |
|------|------|
| [`operator-quickstart.md`](operator-quickstart.md) | 운영자 빠른 시작 — 로컬 오프라인 경로 실행 |
| [`operator-question-log-guide.md`](operator-question-log-guide.md) | 운영자 질문 로그 가이드 — 로그 수집 및 분석 |
| [`operator-synthetic-promotion-dry-run.md`](operator-synthetic-promotion-dry-run.md) | 운영자 합성 프로모션 드라이런 가이드 |
| [`operator-controlled-retrieval-gap-validation.md`](operator-controlled-retrieval-gap-validation.md) | 운영자 제어된 검색 갭 검증 가이드 |
| [`scenario-cache-promotion-review-workflow.md`](scenario-cache-promotion-review-workflow.md) | 시나리오/캐시 프로모션 검토 워크플로우 |
| [`promotion-candidate-review-template.md`](promotion-candidate-review-template.md) | 프로모션 후보 검토 템플릿 |
| [`smoke-scenario-matrix.md`](smoke-scenario-matrix.md) | 스모크 시나리오 매트릭스 — 제품 품질 시나리오 정의 |
| [`smoke-eval-flow.md`](smoke-eval-flow.md) | 스모크 평가 CLI 흐름 — 오프라인 평가 파이프라인 |
| [`live-smoke-eval-design.md`](live-smoke-eval-design.md) | 라이브 스모크 평가 설계 — 실시간 평가 확장 |

---

## 결정 기록

아키텍처 방향과 주요 의사결정을 기록한 문서입니다.

| 파일 | 설명 |
|------|------|
| [`live-transition-decision-record.md`](live-transition-decision-record.md) | 라이브 전환 결정 기록 — 로컬/정적 → 라이브 전환 게이트 |
| [`hybrid-scripted-llm-architecture-intent.md`](hybrid-scripted-llm-architecture-intent.md) | 하이브리드 스크립트 + LLM 아키텍처 의도 기록 |

---

## 설계 / 기획

UI/UX 디자인, HTML/CSS 재구성, 참조 장부 등 시각적/구조적 설계 문서입니다.

| 파일 | 설명 |
|------|------|
| [`design_mockups.md`](design_mockups.md) | #863-B 북구 시맨틱 HTML/CSS 재구성 보고서 |
| [`design/863-bukgu-reference-ledger.md`](design/863-bukgu-reference-ledger.md) | #863 북구 참조 장부 — 승인된 스크린샷 원장 |
| [`design/863-reference-reset.md`](design/863-reference-reset.md) | 참조 리셋 — 시각적 아이덴티티 베이스라인 |
| [`design/863-home-layout-spec.md`](design/863-home-layout-spec.md) | #868 홈 레이아웃 명세 |
| [`design/863-current-home-crop-manifest.md`](design/863-current-home-crop-manifest.md) | #868 현재 홈 상단 크롭 매니페스트 |
| [`design/868-home-full-carousel-crop-manifest.md`](design/868-home-full-carousel-crop-manifest.md) | #868 홈 캐러셀 배너 크롭 매니페스트 |
| [`design/868-home-lower-crop-manifest.md`](design/868-home-lower-crop-manifest.md) | #868 홈 하단 카드 크롭 매니페스트 |
| [`design/868-side-building.txt`](design/868-side-building.txt) | #868 사이드 빌딩 이미지 크롭 좌표 |
| [`design/863-local-execution-contract.md`](design/863-local-execution-contract.md) | #867–#870 로컬 실행 계약 |
| [`design/863-agent-gates-v1.md`](design/863-agent-gates-v1.md) | #872 실행 게이트 |
| [`design/872-local-agent-control-matrix.md`](design/872-local-agent-control-matrix.md) | #872 로컬 에이전트 장애 정지 및 에스컬레이션 제어 매트릭스 |

---

## 제품 정책 / 감사 (product/)

Crawl 필터, 라이브 스모크, 검색 정책 등 제품 안전성과 확장에 관한 정책 및 감사 문서입니다.

| 파일 | 설명 |
|------|------|
| [`product/dynamic-retrieval-query-learning-strategy.md`](product/dynamic-retrieval-query-learning-strategy.md) | 동적 검색 및 질문 학습 전략 |
| [`product/repeated-question-analytics-promotion-plan.md`](product/repeated-question-analytics-promotion-plan.md) | 반복 질문 분석 및 시나리오/캐시 프로모션 계획 |
| [`product/no-source-fallback-scope-and-rule-expansion-policy.md`](product/no-source-fallback-scope-and-rule-expansion-policy.md) | 무소스 폴백 범위 및 규칙 확장 정책 |
| [`product/query-rewrite-retrieval-integration-audit.md`](product/query-rewrite-retrieval-integration-audit.md) | 질문 재작성-검색 통합 감사 |
| [`product/crawl-budget-path-filtering-policy.md`](product/crawl-budget-path-filtering-policy.md) | 크롤 예산 경로 필터링 정책 |
| [`product/municipal-service-crawl-index-completeness-audit.md`](product/municipal-service-crawl-index-completeness-audit.md) | 지방자치단체 서비스 크롤/인덱스 완전성 감사 |
| [`product/crawl-path-filter-integration-boundary-audit.md`](product/crawl-path-filter-integration-boundary-audit.md) | 크롤 경로 필터 통합 경계 감사 |
| [`product/municipal-crawl-filters-candidate-audit.md`](product/municipal-crawl-filters-candidate-audit.md) | 지자체 크롤 필터 구성 후보 감사 |
| [`product/first-real-crawl-filters-post-merge-audit.md`](product/first-real-crawl-filters-post-merge-audit.md) | 첫 번째 실제 크롤 필터 병합 후 감사 |
| [`product/crawl-filters-first-second-rollout-comparison-audit.md`](product/crawl-filters-first-second-rollout-comparison-audit.md) | 첫 번째/두 번째 크롤 필터 롤아웃 비교 감사 |
| [`product/bukgu-crawl-filter-no-live-readiness-audit.md`](product/bukgu-crawl-filter-no-live-readiness-audit.md) | 북구 크롤 필터 노-라이브 준비 상태 감사 |
| [`product/bukgu-no-live-crawl-filter-track-closure-audit.md`](product/bukgu-no-live-crawl-filter-track-closure-audit.md) | 북구 노-라이브 크롤 필터 트랙 종료 감사 |
| [`product/new-municipal-profile-onboarding-boundary.md`](product/new-municipal-profile-onboarding-boundary.md) | 신규 지자체 프로필 온보딩 경계 |
| [`product/fourth-municipal-profile-onboarding-candidate-audit.md`](product/fourth-municipal-profile-onboarding-candidate-audit.md) | 네 번째 지자체 프로필 온보딩 후보 감사 |
| [`product/controlled-live-smoke-boundary-for-crawl-filters.md`](product/controlled-live-smoke-boundary-for-crawl-filters.md) | 크롤 필터용 제어된 라이브 스모크 경계 |
| [`product/bukgu-local-first-controlled-live-smoke-plan.md`](product/bukgu-local-first-controlled-live-smoke-plan.md) | 북구 로컬 우선 제어된 라이브 스모크 계획 |
| [`product/bukgu-controlled-live-smoke-approval-packet.md`](product/bukgu-controlled-live-smoke-approval-packet.md) | 북구 제어된 라이브 스모크 승인 패킷 |

---

## 기술 설계 문서

단일 시나리오 어댑터, 스모크 평가, Provider/네트워크 경계, 설정 등 기술 설계 문서입니다.

| 파일 | 설명 |
|------|------|
| [`config-constants-consolidation-audit.md`](config-constants-consolidation-audit.md) | 설정 상수 통합 감사 |
| [`provider-fetch-network-boundary.md`](provider-fetch-network-boundary.md) | Provider / Fetch / 네트워크 경계 정책 |
| [`fetch-compat-diagnostic-boundary.md`](fetch-compat-diagnostic-boundary.md) | Fetch 호환성 진단 경계 (Stage #800) |
| [`controlled-live-one-time-validation-contract.md`](controlled-live-one-time-validation-contract.md) | 제어된 라이브 1회 검증 실행 계약 (Stage 821) |
| [`citizen-action-mv3-local-fixture-readiness.md`](citizen-action-mv3-local-fixture-readiness.md) | 시민 액션 MV3 로컬 픽스처 준비 |
| [`single-scenario-adapter-interface.md`](single-scenario-adapter-interface.md) | 단일 시나리오 어댑터 인터페이스 |
| [`real-single-scenario-adapter-design.md`](real-single-scenario-adapter-design.md) | 실제 단일 시나리오 어댑터 설계 노트 |
| [`single-scenario-live-opt-in-safety-checklist.md`](single-scenario-live-opt-in-safety-checklist.md) | 단일 시나리오 라이브 옵트인 안전 체크리스트 |
| [`live-smoke-result-artifact-schema.md`](live-smoke-result-artifact-schema.md) | 라이브 스모크 결과 아티팩트 스키마 |

---

## 공식 사이트 경로 인벤토리

#862 공식 사이트 액션 내비게이터 트랙을 위한 경로/콘텐츠 인벤토리 기획 문서입니다.
> **기획 전용** — 실제 라이브 실행 권한을 부여하지 않습니다.

| 파일 | 설명 |
|------|------|
| [`official-site-route-inventory-plan.md`](official-site-route-inventory-plan.md) | 경로 인벤토리 계획 — 스키마 및 프로세스 정의 |
| [`official-site-route-inventory-workflow-index.md`](official-site-route-inventory-workflow-index.md) | 워크플로우 인덱스 — 문서 간 관계 정리 |
| [`official-site-route-inventory-first-scope-selection.md`](official-site-route-inventory-first-scope-selection.md) | 첫 번째 스코프 선택 계획 |
| [`official-site-route-inventory-first-local-static-records.md`](official-site-route-inventory-first-local-static-records.md) | 첫 번째 로컬/정적 시드 레코드 |
| [`official-site-route-inventory-first-scope-issue-draft.md`](official-site-route-inventory-first-scope-issue-draft.md) | 첫 번째 스코프 이슈 초안 패키지 |
| [`official-site-route-inventory-prioritization-rubric.md`](official-site-route-inventory-prioritization-rubric.md) | 경로 인벤토리 우선순위 평가 루브릭 |
| [`official-site-route-inventory-authorization-checklist.md`](official-site-route-inventory-authorization-checklist.md) | 실행 전 승인 체크리스트 |
| [`official-site-route-inventory-post-action-report-template.md`](official-site-route-inventory-post-action-report-template.md) | 수집 후 보고서 템플릿 |
| [`official-site-route-inventory-planning-closeout.md`](official-site-route-inventory-planning-closeout.md) | 기획 패키지 종료 보고서 |
| [`scoped-route-inventory-issue-template.md`](scoped-route-inventory-issue-template.md) | 스코프 경로 인벤토리 이슈 템플릿 |

---

> **참고:** 디자인 참조 이미지와 아티팩트는 [`artifacts/`](artifacts/) 디렉토리에 있습니다.
> 제품 소스 코드와 설정 파일은 [`src/`](../src/) 및 [`configs/`](../configs/)를 참조하세요.
