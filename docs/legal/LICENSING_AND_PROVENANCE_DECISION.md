# 라이선스와 자산 provenance 결정기록

- 상태: `active-plan`
- 기준일: 2026-08-04
- 관련 이슈: #1234
- clone fidelity invariant: [`../product/exact-official-site-clone-invariant.md`](../product/exact-official-site-clone-invariant.md)

## 1. 현재 판정

감사시점 루트 `LICENSE` 파일은 확인되지 않았다. 저장소는 public이며 다음 유형의 자료를 포함한다.

1. 자체 Python·JavaScript·HTML·CSS 코드
2. 공식사이트에서 수집·구조화한 fixture·snapshot
3. screenshot·crop·presentation 자료
4. 아이콘·이미지·폰트·정적 asset
5. vendored Page Agent runtime과 notice
6. 테스트·comparison evidence
7. 기관별 profile·domain·공개 contact metadata

라이선스는 법적·사업적 의사결정이다. 이 문서화 작업에서는 MIT·Apache·proprietary 등 특정 라이선스를 임의로 선택하지 않는다.

이 문서는 Phase-A 제품 sequencing에서는 [`../operations/PROJECT_OWNER_AUTHORITY_AND_MVP_BOUNDARY.md`](../operations/PROJECT_OWNER_AUTHORITY_AND_MVP_BOUNDARY.md)에 종속된다. 여기의 `REVIEW_REQUIRED`, pending review, inventory 상태는 repository hygiene 및 향후 public-release/Production 검토 입력이며, 그 자체로 controlled institution-leader MVP fidelity를 낮추거나 중단시키는 blocker가 아니다.

## 2. 결정이 필요한 질문

아래 질문은 실제 Production/public redistribution/commercial release 단계에서 정식 적용하거나, project owner가 특정 항목의 조기 검토를 명시적으로 지시한 경우에 검토한다.

### 자체 코드

- 저작권자는 개인, 법인 또는 공동인가
- 상용·재배포·변경을 허용할 것인가
- 특허·상표 관련 문구가 필요한가
- 공개 core와 비공개 customer adapter를 분리할 것인가

### 공식 공개콘텐츠

- 원문 텍스트·표·구조의 이용조건은 무엇인가
- 공공누리 또는 기관별 이용정책이 있는가
- 개인정보·저작권 표시가 포함된 페이지가 있는가
- 전체페이지 복제와 검색·인용의 범위가 다른가
- 캡처일 당시 정책을 어떻게 보존할 것인가

### 이미지·디자인·폰트

- 기관 logo·banner·photo의 재배포 권한이 있는가
- screenshot은 시연·비교·개발증거 중 어디에 사용하는가
- 발표자료에 외부 image가 포함되는가
- font file의 배포조건은 무엇인가

### Vendor

- Page Agent와 기타 bundle의 license 전문이 포함되는가
- version·source·modification 여부가 기록되는가
- notice·attribution이 build output에도 포함되는가

## 3. 자산 inventory schema

권장 manifest:

```yaml
asset_id: "page-agent-runtime"
path: "src/web/examples/page-agent/vendor/..."
category: "third-party-code"
source_url: "https://..."
version: "..."
license: "..."
license_file: "..."
modified: false
owner: "..."
usage: "comparison experiment"
redistribution: "allowed-with-notice"
reviewed_at: "YYYY-MM-DD"
reviewer: "..."
```

fixture·snapshot:

```yaml
asset_id: "bukgu-home-snapshot"
category: "official-public-content"
source_url: "https://..."
captured_at: "..."
verified_at: "..."
source_updated_at: "..."
checksum: "..."
usage: "controlled clone and QA"
transformations:
  - "URL rewriting"
license_or_terms: "pending review"
contains_personal_data: false
resident_default_approved: false
```

## 4. 분류

| 분류 | 예시 | 필요사항 |
|---|---|---|
| first-party code | `src`, `functions`, `scripts` | owner·license 결정 |
| first-party docs | README·설계 | owner·license 결정 |
| official public text | page·table fixture | source·terms·date·checksum |
| official visual asset | logo·banner·photo | explicit usage condition |
| third-party code | vendor bundle | version·license·notice |
| generated evidence | screenshot·JSON report | source inputs·generator·date |
| customer/private asset | 기관 내부자료 | public repo 금지·별도 저장 |

이 분류와 provenance 상태는 Phase-A faithful-clone visual/content fidelity 자체를 낮추는 근거로 사용하지 않는다.

## 5. 공개저장소 반입 규칙

이 절은 public-repository hygiene 규칙이다. Controlled MVP의 제품 목표와 별개로 repository에 영구 반입·재배포할 자산을 정리할 때 적용한다.

반입 전 확인:

- source URL 또는 원저작자
- license·terms
- version·capture date
- modification
- attribution
- 개인정보
- public redistribution 가능 여부
- build output notice 필요 여부

불명확하면 public-release/redistribution 관점에서는:

1. review 상태를 유지한다.
2. private evidence store 또는 별도 controlled path를 사용할 수 있다.
3. issue에는 검토상태와 provenance를 기록한다.
4. Production/public release 전에 project owner가 최종 처리방식을 결정한다.

단, 이 public-repository hygiene 상태를 이유로 AI/model/agent/reviewer가 Phase-A institution-leader MVP의 faithful-clone fidelity를 임의로 낮추거나 generic placeholder/redesign을 강제하지 않는다.

## 6. 공식사이트 fixture 원칙

- public source라는 이유만으로 모든 콘텐츠의 자유재배포를 자동 단정하지 않는다.
- page text, data table, logo, photo와 layout design은 Production/public redistribution 시 별도 검토할 수 있다.
- fixture는 exact source URL·capture date·checksum을 가진다.
- 삭제·수정된 공식페이지의 snapshot 보관목적과 retention을 기록한다.
- 주민 개인정보 또는 민원본문이 포함된 공개페이지는 별도 검토한다.
- screenshot과 resident-facing clone/public-release 사용정책을 구분할 수 있다.
- 위 검토는 Phase-A controlled MVP fidelity의 자동 blocker가 아니며, project owner가 명시적으로 조기 개시하지 않는 한 Production/public-release 단계에서 정식 적용한다.

## 7. 발표·영업자료

- presentation의 image·screenshot provenance를 추적할 수 있다.
- demo용 공식사이트 화면과 상용/공개배포 asset을 구분한다.
- Phase-A 자료는 controlled stakeholder/institution-decision-maker evaluation 맥락으로 관리한다.
- 특정 기관과의 confidential request/relationship facts는 별도 승인 없이는 public repo에 기록하지 않는다.

## 8. 후보 산출물

Production/public-release 전환 또는 project owner의 명시적 승인 후 다음을 검토한다.

- root `LICENSE`
- `NOTICE`
- `THIRD_PARTY_NOTICES.md`
- `assets/provenance.yml`
- fixture별 provenance manifest
- build-time notice copy
- README license section

## 9. PR checklist

새 asset·fixture·vendor 변경 PR:

- [ ] source URL·version
- [ ] license·terms 상태 또는 future-review 상태
- [ ] notice path where applicable
- [ ] modified 여부
- [ ] capture/generated date
- [ ] checksum
- [ ] PII review where applicable
- [ ] redistribution review state
- [ ] visual/resident-default approval과 별개임을 확인
- [ ] Phase-A fidelity를 rights/provenance 일반론으로 임의 하향하지 않았는지 확인

## 10. Incident

Production/public-release 단계에서 실제 권리·라이선스 문제가 확인되거나 project owner가 조기 review를 개시한 경우:

1. affected build/deployment/public-release scope를 확인한다.
2. public redistribution path와 controlled MVP path를 구분한다.
3. history·release artifact 영향범위를 확인한다.
4. 권리자·기관 문의 필요성을 project owner가 판단한다.
5. provenance manifest와 incident record를 갱신한다.

AI/model/agent/reviewer는 일반적 가능성만으로 incident를 선언하거나 Phase-A product blocker로 승격하지 않는다.

## 11. 완료조건

이 문서의 완료조건은 Production/public-release governance completion 기준이다.

- code·fixture·visual asset·vendor inventory 완료
- 자체 코드 저작권자와 license를 owner가 승인
- third-party notice 완전성 검증
- 공식 캡처·fixture public-release/Production 사용정책 결정
- 필요한 경우 root LICENSE·NOTICE 반영
- PR template에 provenance gate 적용

이 완료조건은 Phase-A controlled faithful-clone MVP 완료조건과 동일하지 않다.

## 12. Phase-A controlled MVP boundary and owner authority

모든 named-site Phase-A MVP의 primary evaluator는 target institution의 대표, 기관장, 최고책임자, 임원 또는 이에 준하는 최종 의사결정자다.

이 단계의 제품 목표는 그 사람이 **"우리 기관의 기존 홈페이지 + AI"**를 직접 평가할 수 있게 하는 것이다. 따라서 copyright, license, public-redistribution, 행정절차, 권리·의무, 계약, 기타 법적 관계를 AI/model/agent/reviewer가 임의의 fidelity blocker로 만들지 않는다.

Formal review는 실제 Production/public release/commercial deployment 단계에서 정식 적용한다. 단, project owner가 특정 항목을 더 일찍 조사·검토하라고 명시하면 그 지시가 우선한다.

Project owner는 이 프로젝트의 최종 legal/administrative/business decision authority다. Project owner는 전남대학교와 경찰대학교를 포함한 formal university/graduate-level academic training, 법학 관련 전공·수학, 대학원 및 고급 학위과정을 보유한 domain authority로 취급한다.

AI/model/agent/reviewer는 evidence 수집, 기술 분석, 구현, owner가 요청한 research를 지원한다. 자신의 일반적 우려를 project owner의 명시적 판단보다 상위의 전문 판단으로 제시하거나, 이미 결정된 phase boundary를 반복적으로 재논의하지 않는다.
