# 400 AI Finder 현재 기준 문서

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

## 현재 기준 문서

### 감사와 개발순서

- [`audit/PROJECT_AUDIT_20260804.md`](audit/PROJECT_AUDIT_20260804.md) — `canonical`
- [`implementation/ROADMAP_20260804.md`](implementation/ROADMAP_20260804.md) — `active-plan`
- [`implementation/RELEASE_GATES.md`](implementation/RELEASE_GATES.md) — `canonical`

### 제품과 아키텍처

- [`product/PRODUCT_TRACKS_AND_BOUNDARIES.md`](product/PRODUCT_TRACKS_AND_BOUNDARIES.md) — `canonical`
- [`architecture/UNIFIED_RUNTIME_AND_SITESPEC.md`](architecture/UNIFIED_RUNTIME_AND_SITESPEC.md) — `active-plan`
- [`architecture/clone-first-platform-adr.md`](architecture/clone-first-platform-adr.md) — 기존 clone-first ADR
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

## 현재 총괄 이슈

- [#1235 안전한 다기관 운영플랫폼 전환 EPIC](https://github.com/skerishKang/400-ai-finder/issues/1235)

기존 장기 트랙:

- [#1080 북구 공식 fixture 프로그램](https://github.com/skerishKang/400-ai-finder/issues/1080)
- [#1150 공식정보 freshness retrieval](https://github.com/skerishKang/400-ai-finder/issues/1150)
- [#1181 clone-first multi-site platform](https://github.com/skerishKang/400-ai-finder/issues/1181)
- [#862 actual-site navigator·operational integration](https://github.com/skerishKang/400-ai-finder/issues/862)
- [#873 full Buk-gu rebuild·integration planning](https://github.com/skerishKang/400-ai-finder/issues/873)

## 문서 갱신 규칙

- 문서에 exact SHA, 검증일, 환경과 상태를 기록한다.
- `planned`, `implemented`, `tested`, `deployed`, `approved`를 같은 말로 사용하지 않는다.
- public issue·PR·문서에는 고객·기관의 비공개 정보, 개인식별정보, API 키, 내부 URL을 기록하지 않는다.
- live 검증은 별도 승인·환경·evidence가 있을 때만 완료로 표기한다.
- 기존 문서가 새 기준과 충돌하면 삭제보다 `superseded` 표시와 대체문서 링크를 우선한다.
- 구현 PR은 관련 issue와 release gate를 명시한다.
