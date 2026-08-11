---
name: Improvement
about: Shared core·archetype·capability·안전·운영 개선을 제안합니다
title: "improvement: "
labels: ""
assignees: ""
---

## 이 이슈가 필요한 이유

<!-- Routine site onboarding의 단순 site-specific difference라면 별도 Issue가 아니라 onboarding exception/report로 처리하는 것을 우선합니다. 아래 중 공통/재사용/안전/production 관점에서 Issue로 승격할 이유를 설명하세요. -->

- [ ] Shared core/runtime/parser/compiler bug
- [ ] Reusable capability gap
- [ ] Archetype contract gap
- [ ] Security/privacy/evidence/safety problem
- [ ] Repeating onboarding failure pattern
- [ ] Golden compatibility / migration need
- [ ] Production promotion blocker
- [ ] Repository/documentation governance
- [ ] Other — explain below

## 문제와 사용자 영향

<!-- 현재 무엇이 어렵고 누구에게 어떤 영향이 있는지 적으세요. -->

## 재현 범위 / affected sites

- Site(s) / site_id(s):
- Archetype(s):
- Capability(ies):
- 한 사이트에만 국한되는가, 여러 사이트에서 재현되는가:
- 관련 onboarding exception/report:

## Product track

- [ ] Buk-gu golden clone
- [ ] 근거 기반 AI 시민안내
- [ ] 공식정보 freshness
- [ ] Python crawler·operator runtime
- [ ] Cloudflare citizen runtime
- [ ] Page Agent comparison
- [ ] Multi-site / general-site platform
- [ ] Routine onboarding exception escalation
- [ ] Authorized first-party integration
- [ ] Repository·documentation governance

## 목표 release / readiness gate

- [ ] Gate A
- [ ] Gate B
- [ ] Gate C
- [ ] Gate D
- [ ] Gate E
- [ ] Gate F
- [ ] Gate G1 — Generated onboarding preview
- [ ] Gate G2 — Archetype golden validation
- [ ] Gate G3 — Resident/default or production promotion
- [ ] Gate H
- [ ] No promotion

## 제안

<!-- site-specific override로 해결할지, shared capability/core를 고칠지 구분하세요. -->

- Proposed resolution class: `site override / archetype / capability / shared core / policy / promotion`
-

## 포함범위

-

## 제외범위

-

## 안전·개인정보·비용 영향

- External network/provider:
- `URL supplied != live network authorized` 확인:
- Actual submit/login/payment:
- PII/secret:
- Public API abuse/cost:
- Evidence/source:
- Golden compatibility:

## 데이터·출처

- 필요한 fixture / source:
- Provenance:
- Freshness:
- License / asset review:

## 기술경계

- SiteSpec / site ID:
- Archetype:
- Capability:
- Provider / model / action / locale:
- API schema:
- UI / DOM / state:
- Browser Use / action boundary:
- Migration / legacy compatibility:

## Generated-preview 영향

- Automation ratio 영향:
- Review/unsupported 비율 영향:
- Exception을 숨기지 않고 명시할 수 있는가:
- Shared core를 바꾸지 않고 site-specific override로 해결 가능한가:
- Production promotion과 무관한 generated preview 문제인가:

## 수용 기준

- [ ]
- [ ]
- [ ]

## 검증계획

- Unit / contract:
- Build:
- Browser / viewport:
- Generated onboarding QA:
- Accessibility:
- Visual comparison (when applicable):
- Controlled live (separate approval only):

## 배포와 rollback / isolation

- Deployment impact:
- Rollback:
- Failed-site isolation:

## 의존 이슈와 순서

-

## Routine onboarding 여부 확인

- [ ] 이 문제는 단순 site-specific exception이 아니라 별도 Issue로 승격할 공통 가치/위험이 있다.
- [ ] `generated_preview` 문제를 `exact`/resident-default/production 문제로 과장하지 않았다.
