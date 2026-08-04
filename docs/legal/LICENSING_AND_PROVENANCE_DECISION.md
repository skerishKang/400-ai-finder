# 라이선스와 자산 provenance 결정기록

- 상태: `active-plan`
- 기준일: 2026-08-04
- 관련 이슈: #1234

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

## 2. 결정이 필요한 질문

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

## 5. 공개저장소 반입 규칙

반입 전 확인:

- source URL 또는 원저작자
- license·terms
- version·capture date
- modification
- attribution
- 개인정보
- public redistribution 가능 여부
- build output notice 필요 여부

불명확하면:

1. public repo에 반입하지 않는다.
2. placeholder 또는 자체생성 asset으로 대체한다.
3. private evidence store에 제한보관한다.
4. issue에 원문을 붙이지 않고 검토상태만 기록한다.

## 6. 공식사이트 fixture 원칙

- public source라는 이유만으로 모든 콘텐츠의 자유재배포를 가정하지 않는다.
- page text, data table, logo, photo와 layout design은 별도 검토할 수 있다.
- fixture는 exact source URL·capture date·checksum을 가진다.
- 삭제·수정된 공식페이지의 snapshot 보관목적과 retention을 기록한다.
- 주민 개인정보 또는 민원본문이 포함된 공개페이지는 별도 검토한다.
- screenshot과 resident-facing clone 사용권한을 구분한다.

## 7. 발표·영업자료

- presentation의 image·screenshot마다 provenance를 추적한다.
- demo용 공식사이트 화면과 상용배포 asset을 구분한다.
- 기관 선정 전 자료는 “controlled demonstration”으로 표시한다.
- 실제 기관 partnership·endorsement로 오인될 표현을 피한다.

## 8. 후보 산출물

소유자 승인 후 다음을 검토한다.

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
- [ ] license·terms
- [ ] notice path
- [ ] modified 여부
- [ ] capture/generated date
- [ ] checksum
- [ ] PII review
- [ ] redistribution review
- [ ] visual/resident-default approval과 별개임을 확인

## 10. Incident

불명확하거나 무단인 asset이 발견되면:

1. build·deployment에서 비활성화 여부 판단
2. 공개경로와 clone에서 제거·대체
3. history·release artifact 영향범위 확인
4. 권리자·기관 문의 필요성 검토
5. provenance manifest와 incident record 갱신

## 11. 완료조건

- code·fixture·visual asset·vendor inventory 완료
- 자체 코드 저작권자와 license를 owner가 승인
- third-party notice 완전성 검증
- 공식 캡처·fixture 사용정책 결정
- 불명확 asset 제거·대체
- 필요한 경우 root LICENSE·NOTICE 반영
- PR template에 provenance gate 적용
