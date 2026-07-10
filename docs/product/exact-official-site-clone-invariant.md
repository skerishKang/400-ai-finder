# Exact Official-Site Clone Invariant

> 최상위 product invariant. 이 문서는 저장소 전체에서 좌측 시민 사이트 화면의
> **공식 사이트 그대로 복제(exact clone)** 원칙을 규정한다. 모든 MVP architecture /
> product direction / design direction / route·quest / civic canvas / build·deploy /
> reference ledger / visual review / official-site integration / fixture·snapshot /
> testing 문서는 이 문서를 단일 원천(canonical)으로 인용한다.

이전 방향은 폐기되었다. 현재 계약은 exact official-site clone이다.

## 목적

- 좌측 화면은 광주광역시 북구청 공식 사이트(`https://bukgu.gwangju.kr`)의 복제본이다.
- 우측 AI는 좌측 복제 사이트를 검색·클릭·이동하여 안내한다.
- AI가 좌측 화면을 새로 디자인하거나 요약하거나 재구성하지 않는다.
- 공식 페이지의 내용·구조·표·행·순서·컨트롤·시각 표현을 요약하거나 재설계하지 않는다.

## exact clone 정의

- 공식 공개 source의 모든 캡처 항목을 그대로 보존한다.
- 페이지 구조, 문구, 표, 행, 순서, 링크, 컨트롤, 시각 구조를 그대로 보존한다.
- 공식 페이지에서 빠진 것이 clone에도 빠지고, 공식 페이지에 있는 것은 clone에도 있어야 한다.
- 임의 추가·삭제·수정은 금지된다.
- 다음 항목을 포함하여 완전히 보존한다:
  - 공식 페이지 계층
  - 메뉴와 breadcrumb
  - 제목과 부제목
  - 탭
  - 버튼과 컨트롤
  - 표 머리글
  - 전체 행
  - 행 순서
  - 행 개수
  - 모든 공개 셀 값
  - 부서명 / 팀명 / 직책
  - 공개 전화번호
  - 담당업무
  - 날짜 / 최근 업데이트
  - 링크와 route target
  - 입력 요소
  - 화면 상태
  - 레이아웃 / 간격 / 그룹 구조 / 크기
  - 반응형 표현
  - 공식 페이지의 보이는 스타일

## canonical fixture 원칙

- fixture는 공식 source의 완전한 committed snapshot이다.
- fixture 데이터의 축약·재작성·선택은 금지된다.
- fixture가 production page의 유일한 content source이다.
- 테스트가 별도 expected literal을 독립 원본처럼 소유하지 않는다.
  (테스트는 fixture를 읽어 render output과 비교한다. 테스트 파일에 공식 content 전체를
  다시 복사해 expected literal로 만들지 않는다.)
- canonical fixture나 snapshot은 중복 제거를 위한 내부 저장 방식일 뿐이다.
  fixture에 저장된 내용도 공식 페이지를 그대로 보존해야 한다.

## 갱신 원칙

- 공식 페이지 변경은 승인된 controlled read-only validation으로 확인한다.
- 각 fixture entry는 다음 source metadata를 가져야 한다:
  - `source_url` (공식 북구청 공개 도메인)
  - `captured_at` (capture/verification date)
  - `source_updated_at` (source update date, 없으면 명시적 `null`)
  - `page_title`
  - `route_page_identifier`
  - `full_content_checksum` 또는 `deterministic_identity`
- 정상 테스트에서는 network 0 (외부 조회 불필요).

## 금지 사례

다음은 명시적으로 잘못된 예이다:

- 19행 표를 4행으로 줄임
- 직원별 번호를 대표번호 하나로 교체
- 여러 번호를 임의 범위로 결합
- 공식 담당업무를 짧게 다시 작성
- 표를 custom card로 교체
- 공식 breadcrumb를 삭제
- 공식 업데이트 날짜를 누락
- AI 메시지를 공식 페이지 데이터로 사용
- 모바일에서 공식 페이지 대신 요약 화면 표시

다음 표현으로 공식 페이지와 다른 결과를 허용하지 않는다:
"high-fidelity", "closely enough", "근사", "대표적인 정보", "요약 화면", "간소 버전",
"representative", "approximation", "summary", "simplified", "demo-quality reproduction".

금지 동작:
- 요약 / 축약 / 간소화 / 재설계를 하지 않는다
- 대표 행만 표시 / 대표 연락처만 표시 / 일부 행 선택 / 행 생략을 하지 않는다
- 공식 문구 다시 쓰기 / 담당업무를 짧게 바꾸기 / 전화번호를 임의 범위로 결합하지 않는다
- 공식 표를 카드나 대시보드로 교체하지 않는다
- 실제 페이지 대신 유사 화면을 제작하지 않는다
- AI 답변이나 choreography 메시지를 왼쪽 공식 페이지 데이터의 원본으로 사용하지 않는다
- 공식 source가 없는 내용을 추측하거나 만들어 넣지 않는다
- 기밀인 의뢰·고객·관계자 정보를 저장소 어디에도 기록하지 않는다

## PR review 원칙

리뷰 시 다음을 차단한다:

- source fixture와 render output 불일치
- 누락 행
- 추가 synthetic 행
- 순서 변경
- 문구 변경
- visual redesign
- incomplete capture
- approximate language
- fixture 없는 official-page renderer

## 관련 문서

- primary README — 좌측 화면 exact clone 철칙 명시 + 본 문서 링크
- `docs/mvp-demo-milestone-snapshot.md`
- `docs/design_mockups.md`
- `docs/ui-comparison-analysis-2026-07-10.md`
- `docs/design/863-home-layout-spec.md`
- `docs/artifacts/863-semantic/followup-3/crop-manifest.md`
- `tests/fixtures/official_site_clone_manifest.json` — 공식 페이지 fixture manifest
- `tests/test_exact_official_site_clone_invariant.py` — 본 invariant 계약 테스트
