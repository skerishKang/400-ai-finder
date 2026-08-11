# 400 AI Finder 현재 기준 문서

- 상태: `canonical`
- 기준일: 2026-08-12
- 기준 main: `c8b1a209fcf39b2c7557deee6c0099aa6def420b`

이 문서는 저장소의 현재 제품상태, 안전경계, 개발순서와 운영기준을 찾기 위한 상위 인덱스다.

저장소에는 장기간 축적된 단계별 기록과 실험문서가 많다. 문서의 존재만으로 현재 구현·승인·운영 상태를 추정하지 않는다. 아래 분류와 각 문서의 상태표시를 우선한다.

## 문서 상태 분류

| 상태 | 의미 |
|---|---|
| `canonical` | 현재 구현과 운영판단의 기준 |
| `active-plan` | 승인된 후속 작업계획. 구현완료를 의미하지 않음 |
| `golden` | 북구 frozen baseline과 회귀계약 |
| `operator` | 실행·검증·배포 운영절차 |
| `historical` | 당시 의사결정·증거. 현재 상태는 별도 확인 필요 |
| `planning-only` | 구현·live 실행·배포를 승인하지 않는 설계자료 |
| `superseded` | 새 문서·이슈가 대체. 역사기록으로만 보존 |

## 현재 제품 상태

- **Buk-gu Frozen Demo:** 완료. 북구는 첫 번째 protected golden reference다.
- **Shared safety/runtime foundation:** SiteSpec identity foundation, shared runtime vocabulary, offline CI, evidence/privacy/timeout/kill-switch contracts가 존재한다.
- **General-site / multi-site AI Browser:** 제품 방향은 재개되었지만 generic onboarding runtime, archetype/capability layer, generic Site Model/preview compiler는 아직 구현됐다고 주장하지 않는다.
- **Live-public AI:** 별도 운영승인 전에는 public operating approval로 간주하지 않는다.
- **Actual-site first-party integration:** 기관 권한·credentials·운영책임 전에는 승인되지 않는다.
- **Rights/license:** #1234의 owner/rights 결정이 별도로 남아 있다.

제품의 장기 형태는 **왼쪽 target website/clone/generated surface + 오른쪽 AI conversation/navigation/Browser Use**다. 북구 전용 기능을 계속 추가하는 것이 아니라, URL/SiteSpec에서 supervised generated preview를 만들고 저신뢰·미지원 항목만 exception으로 올리는 플랫폼이 다음 방향이다.

초기 자동화 목표는 historical #1181의 목표를 유지한다.

```text
URL / SiteSpec
  -> capture / route inventory
  -> semantic analysis
  -> generic Site Model
  -> clone / preview generation
  -> knowledge index
  -> action graph / browser model
  -> automated QA
  -> exception queue
  -> human review
```

목표는 첫 단계부터 100% exact 자동복제가 아니라 **70–80% supervised automation + explicit exceptions**다. `generated_preview`는 `exact` 또는 `resident_default_approved`와 같은 상태가 아니다.

## 현재 기준 문서

### 감사와 개발순서

- [`audit/PROJECT_AUDIT_20260804.md`](audit/PROJECT_AUDIT_20260804.md) — `historical` 감사 기준. 당시 상태와 현재 상태를 혼동하지 않는다.
- [`implementation/ROADMAP_20260804.md`](implementation/ROADMAP_20260804.md) — `historical` 계획. 완료/종료된 이슈 순서를 현재 실행순서로 재사용하지 않는다.
- [`implementation/RELEASE_GATES.md`](implementation/RELEASE_GATES.md) — `canonical`

### 제품과 아키텍처

- [`product/PRODUCT_TRACKS_AND_BOUNDARIES.md`](product/PRODUCT_TRACKS_AND_BOUNDARIES.md) — `canonical`
- [`architecture/UNIFIED_RUNTIME_AND_SITESPEC.md`](architecture/UNIFIED_RUNTIME_AND_SITESPEC.md) — `active-plan`
- [`architecture/clone-first-platform-adr.md`](architecture/clone-first-platform-adr.md) — `historical` architecture decision / compatibility reference
- [`bukgu-golden-compatibility-manifest.md`](bukgu-golden-compatibility-manifest.md) — `golden`

### 보안·개인정보·운영

- [`operations/PUBLIC_AI_API_SECURITY_AND_PRIVACY.md`](operations/PUBLIC_AI_API_SECURITY_AND_PRIVACY.md) — `canonical`
- [`operations/REPOSITORY_GOVERNANCE.md`](operations/REPOSITORY_GOVERNANCE.md) — `canonical`
- [`../SECURITY.md`](../SECURITY.md) — 취약점 신고·비밀정보·개인정보 처리기준
- [`provider-fetch-network-boundary.md`](provider-fetch-network-boundary.md) — 외부 provider·network 경계
- [`live-transition-decision-record.md`](live-transition-decision-record.md) — live 전환 의사결정 기록
- [`operator-quickstart.md`](operator-quickstart.md) — 운영자 실행 안내

### 라이선스와 자산

- [`legal/LICENSING_AND_PROVENANCE_DECISION.md`](legal/LICENSING_AND_PROVENANCE_DECISION.md) — `active-plan`

### 개발기여

- [`../CONTRIBUTING.md`](../CONTRIBUTING.md)
- [`../.github/PULL_REQUEST_TEMPLATE.md`](../.github/PULL_REQUEST_TEMPLATE.md)
- [`../.github/ISSUE_TEMPLATE/bug_report.md`](../.github/ISSUE_TEMPLATE/bug_report.md)
- [`../.github/ISSUE_TEMPLATE/improvement.md`](../.github/ISSUE_TEMPLATE/improvement.md)

## 북구 golden 기준

북구 golden baseline은 범용 플랫폼 refactor보다 우선 보호한다.

- Golden compatibility manifest: [`bukgu-golden-compatibility-manifest.md`](bukgu-golden-compatibility-manifest.md)
- Exact clone invariant: [`product/exact-official-site-clone-invariant.md`](product/exact-official-site-clone-invariant.md)
- Visual promotion policy: [`product/clone-visual-fidelity-and-promotion-policy.md`](product/clone-visual-fidelity-and-promotion-policy.md)
- Fixture manifest: [`../tests/fixtures/official_site_clone_manifest.json`](../tests/fixtures/official_site_clone_manifest.json)

다음은 별개의 상태다.

1. fixture provenance 완료
2. 구조·내용 parity 완료
3. asset mapping 완료
4. interaction parity 완료
5. visual review 완료
6. resident-default 승인

앞 단계가 완료됐다는 이유로 다음 단계가 자동 승인되지 않는다.

## Generated preview와 production promotion 분리

범용 onboarding에서는 다음 상태를 구분한다.

- `generated_preview` — 자동 생성된 비기본/비정식 preview. confidence·unsupported·exception을 명시해야 하며 `exact`를 주장하지 않는다.
- `archetype_golden` — municipality / university / bank 등 유형별 대표 검증 surface.
- `resident_default_approved` / production promotion — 해당 surface가 실제 기본 사용자 경로로 승격된 상태. applicable visual/safety/rights gate를 별도로 통과해야 한다.

URL이 제공되었다는 사실만으로 live network/crawl/provider 실행이 승인되는 것은 아니다. routine CI는 계속 external provider·official-site network 0을 유지한다.

## 현재 작업 이슈

- [#1283 post-Buk-gu multi-site AI Browser governance alignment](https://github.com/skerishKang/400-ai-finder/issues/1283) — 현재 플랫폼 재개 전 문서/운영경계 정렬
- [#1234 코드·공식 캡처·제3자 자산 license/provenance](https://github.com/skerishKang/400-ai-finder/issues/1234) — 별도 owner/rights 결정

완료/역사 참고:

- [#1235 Buk-gu Frozen Demo closeout](https://github.com/skerishKang/400-ai-finder/issues/1235) — `completed`
- [#1181 clone-first multi-site platform](https://github.com/skerishKang/400-ai-finder/issues/1181) — historical planning source; 당시 `not_planned` 종료
- [#1232 generic multi-site onboarding](https://github.com/skerishKang/400-ai-finder/issues/1232) — historical deferred plan
- [#1080 북구 공식 fixture 프로그램](https://github.com/skerishKang/400-ai-finder/issues/1080) — historical/deferred
- [#1150 공식정보 freshness retrieval](https://github.com/skerishKang/400-ai-finder/issues/1150) — historical/deferred
- [#862 actual-site navigator·operational integration](https://github.com/skerishKang/400-ai-finder/issues/862) — 별도 권한 단계
- [#873 full Buk-gu rebuild·integration planning](https://github.com/skerishKang/400-ai-finder/issues/873) — historical planning

## 문서 갱신 규칙

- 문서에 exact SHA, 검증일, 환경과 상태를 기록한다.
- `planned`, `generated`, `implemented`, `tested`, `deployed`, `approved`를 같은 말로 사용하지 않는다.
- `generated_preview`, `archetype_golden`, `resident_default_approved`를 서로 대체어로 사용하지 않는다.
- public issue·PR·문서에는 고객·기관의 비공개 정보, 개인식별정보, API 키, 내부 URL을 기록하지 않는다.
- live 검증은 별도 승인·환경·evidence가 있을 때만 완료로 표기한다.
- 기존 문서가 새 기준과 충돌하면 삭제보다 `superseded` 또는 `historical` 표시와 대체문서 링크를 우선한다.
- 구현 PR은 관련 issue와 release gate를 명시한다.
