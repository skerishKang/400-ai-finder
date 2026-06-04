# Smoke Scenario Matrix — AI 홈페이지 파인더

Stage 40에서 정의한 제품 품질 시나리오 매트릭스입니다.
Stage 41에서 이 매트릭스를 기반으로 자동/반자동 평가 러너를 구현합니다.

## 개요

| 항목 | 값 |
|------|-----|
| 대상 기관 | `bukgu_gwangju`, `gwangju_go_kr` |
| 시나리오 수 | 14개 (기관당 7개) |
| 카테고리 수 | 6개 |
| 기계 판독 파일 | `tests/fixtures/smoke_scenario_matrix.json` |
| 기준 HEAD | `4a4da76` |

## 카테고리 정의

| # | 카테고리 | 설명 | 예시 |
|---|---------|------|------|
| 1 | `service_navigation` | 메뉴/서비스 안내 | "민원서식 어디서 받아?" |
| 2 | `document_lookup` | 서식/문서 조회 | "주민등록등본 발급 서류가 뭐야?" |
| 3 | `department_contact` | 부서/담당자 조회 | "세무과 전화번호 알려줘" |
| 4 | `fee_hour_location` | 이용요금/시간/위치 | "구청 민원실 운영시간이 어떻게 돼?" |
| 5 | `ambiguous_query` | 애매하거나 짧은 질문 | "지원금", "복지" |
| 6 | `low_confidence_fallback` | 관련 근거가 없는 질문 | "우주여행 예약하는 방법 알려줘" |

## 품질 게이트 (Quality Gate)

모든 시나리오에 공통으로 적용되는 통과/실패 기준입니다.

| 기준 | 설명 |
|------|------|
| `site_id_match` | 응답의 `site_id`가 시나리오의 `expected_site_id`와 일치해야 함 |
| `grounded_source` | 출처에 제목과 URL이 있고, URL이 예상 도메인을 포함해야 함 |
| `no_unsupported_facts` | 답변이 출처 제목/URL과 모순되는 사실을 포함하면 안 됨 |
| `clear_fallback` | 출처가 없거나 점수가 낮을 때, fallback 안내 메시지가 포함되어야 함 |
| `no_cross_site_confusion` | 출처 URL이 다른 기관의 도메인이면 안 됨 |

## 시나리오 매트릭스

### 광주광역시 북구청 (`bukgu_gwangju`)

| ID | 카테고리 | 질문 | 예상 도메인 | 핵심 키워드 | 최소 출처 |
|----|---------|------|------------|------------|----------|
| bukgu-01 | service_navigation | 민원서식 어디서 받아? | bukgu.gwangju.kr | 민원서식, 종합민원 | 1건 |
| bukgu-02 | service_navigation | 교육접수는 어디서 해? | bukgu.gwangju.kr | 교육접수 | 1건 |
| bukgu-03 | document_lookup | 주민등록등본 발급 서류가 뭐야? | bukgu.gwangju.kr | 주민등록, 등본, 발급 | 0건+ |
| bukgu-04 | department_contact | 세무과 전화번호 알려줘 | bukgu.gwangju.kr | 세무, 전화, 연락처 | 0건+ |
| bukgu-05 | fee_hour_location | 구청 민원실 운영시간이 어떻게 돼? | bukgu.gwangju.kr | 운영시간, 민원실 | 0건+ |
| bukgu-06 | ambiguous_query | 지원금 | bukgu.gwangju.kr | 지원, 사업 | 0건+ |
| bukgu-07 | low_confidence_fallback | 우주여행 예약하는 방법 알려줘 | bukgu.gwangju.kr | _(없음)_ | 0건 |

### 광주광역시청 (`gwangju_go_kr`)

| ID | 카테고리 | 질문 | 예상 도메인 | 핵심 키워드 | 최소 출처 |
|----|---------|------|------------|------------|----------|
| gwangju-01 | service_navigation | 고시공고는 어디서 봐? | gwangju.go.kr | 고시, 공고 | 1건 |
| gwangju-02 | service_navigation | 정보공개는 어디서 확인해? | gwangju.go.kr | 정보공개 | 1건 |
| gwangju-03 | document_lookup | 시청 민원서식 양식 어디서 다운로드해? | gwangju.go.kr | 민원서식, 양식 | 0건+ |
| gwangju-04 | department_contact | 시청 조직도는 어디서 봐? | gwangju.go.kr | 조직도, 시청 | 1건 |
| gwangju-05 | fee_hour_location | 시청 방문 주차장 있어? | gwangju.go.kr | 주차, 방문 | 0건+ |
| gwangju-06 | ambiguous_query | 복지 | gwangju.go.kr | 복지, 지원 | 0건+ |
| gwangju-07 | low_confidence_fallback | 외계인 등록증 발급 받으려면? | gwangju.go.kr | _(없음)_ | 0건 |

## 시나리오 상세 통과 조건

### service_navigation (메뉴/서비스 안내)

- `site_id` 일치 필수
- 출처 1건 이상, URL이 예상 도메인 포함
- 답변에 핵심 키워드 중 하나 이상 포함
- 다른 기관 도메인 URL이 출처에 없어야 함

### document_lookup (서식/문서 조회)

- `site_id` 일치 필수
- 출처가 있으면 예상 도메인의 URL이어야 함
- 출처가 없으면 fallback 안내 포함 ("홈페이지에서 직접 확인" 등)
- 답변에 관련 키워드 포함

### department_contact (부서/담당자 조회)

- `site_id` 일치 필수
- 출처가 있으면 예상 도메인의 URL이어야 함
- 출처가 없으면 fallback 안내 포함
- 답변에 부서명 또는 연락처 관련 키워드 포함

### fee_hour_location (이용요금/시간/위치)

- `site_id` 일치 필수
- 출처가 있으면 예상 도메인의 URL이어야 함
- 출처가 없으면 fallback 안내 포함
- 답변에 시간/위치/요금 관련 키워드 포함

### ambiguous_query (애매한 질문)

- `site_id` 일치 필수
- 답변이 비어있지 않아야 함
- 출처가 없으면 fallback 안내 포함
- 정확한 답을 요구하지 않음 — 관련 메뉴라도 안내하면 통과

### low_confidence_fallback (근거 부족)

- `site_id` 일치 필수
- 답변이 비어있지 않아야 함
- **fallback 메시지 필수** — "홈페이지에서 직접 확인", "관련 정보를 찾을 수 없습니다" 등
- 출처가 있더라도 해당 기관의 것이어야 함
- 다른 기관 정보로 대답하면 안 됨

## Fixture 파일 구조

`tests/fixtures/smoke_scenario_matrix.json`은 Stage 41 평가 러너가 읽는 기계 판독 파일입니다.

```json
{
  "_meta": {
    "version": "1.0.0",
    "stage": 40,
    "baseline_head": "4a4da76"
  },
  "quality_gate": {
    "site_id_match": "...",
    "grounded_source": "...",
    "no_unsupported_facts": "...",
    "clear_fallback": "...",
    "no_cross_site_confusion": "..."
  },
  "scenarios": [
    {
      "id": "bukgu-01",
      "site_id": "bukgu_gwangju",
      "category": "service_navigation",
      "question": "민원서식 어디서 받아?",
      "expected_domain": "bukgu.gwangju.kr",
      "pass_criteria": { ... }
    }
  ]
}
```

### `quality_gate` 정책

`quality_gate`는 smoke scenario matrix의 선택적(optional) 최상위 문서 메타데이터입니다.
`evaluate_response()`에서 사용되지 않으며, provider, fetch, network, Firecrawl, app pipeline, backend, UI, API 동작에 영향을 주지 않습니다.

값이 `null`이 아닌 형태로 제공될 경우 `validate_matrix()`는 dict여야 함을 요구합니다.
`quality_gate`가 없거나 `quality_gate: null`인 경우는 선택적/생략 케이스로 허용됩니다.

`quality_gate`의 내부 스키마는 의도적으로 유연하게(intentionally flexible) 유지됩니다.
매트릭스 작성자는 자유로운 키와 값을 사용하여 품질 기대치를 문서화할 수 있습니다.
유효성 검사기는 현재 `quality_gate`의 내부 키 식별(known key), 필수 키(required key), 값 타입(value type), 허용 값(allowed value)을 강제하지 않습니다.

향후 `quality_gate` 내부 키 또는 값에 대한 hardening이 필요하면 별도의 감사(audit) 스테이지를 거친 후 협소한 후속 스테이지에서 구현합니다.

### `_meta` 정책

`_meta`는 smoke scenario matrix의 선택적(optional) 최상위 문서 메타데이터입니다.
`evaluate_response()`에서 사용되지 않으며, provider, fetch, network, Firecrawl, app pipeline, backend, UI, API 동작에 영향을 주지 않습니다.

값이 `null`이 아닌 형태로 제공될 경우 `validate_matrix()`는 dict여야 함을 요구합니다.
`_meta`가 없거나 `_meta: null`인 경우는 선택적/생략 케이스로 허용됩니다.

`_meta`의 내부 스키마는 의도적으로 유연하게(intentionally flexible) 유지됩니다.
매트릭스 작성자는 자유로운 키와 값을 사용하여 매트릭스 출처, 사용법, 버전 정보 또는 기타 메타데이터를 문서화할 수 있습니다.
유효성 검사기는 현재 `_meta`의 내부 키 식별(known key), 필수 키(required key), 값 타입(value type), 허용 값(allowed value)을 강제하지 않습니다.

매트릭스 `_meta`와 라이브 아티팩트/내보내기(export) `_meta`는 shape가 다를 수 있습니다.
향후 `_meta` 내부 키 또는 값에 대한 hardening이 필요하면 별도의 감사(audit) 스테이지를 거친 후 협소한 후속 스테이지에서 구현합니다.

### Source object 정책

`evaluate_response()`가 소비하는 source object는 의도적으로 유연하게(intentionally flexible) 유지됩니다.
Source object는 서로 다른 response fixture, mock, 또는 provider/fetch-facing pipeline shape에서 전달될 수 있습니다.

URL 키로 `url`, `href`, `link` 세 가지 별칭(alias)을 인식합니다.
제목 키로 `title`, `name` 두 가지 별칭을 인식합니다.

알려지지 않은(unknown) source 필드는 허용되며 `evaluate_response()`에서 무시됩니다.
유효성 검사기는 source object의 추가 키를 거부하지 않습니다.
딕셔너리가 아닌(non-dict) source 항목은 helper 함수에서 필터링되거나 빈 값으로 처리됩니다.

이러한 유연성은 의도적인 설계로, provider, fetch, network, Firecrawl, app pipeline, backend, UI, API 통합 shape와의 호환성을 유지하기 위함입니다.
향후 source object 키 또는 값에 대한 hardening이 필요하면 별도의 감사(audit) 스테이지를 거친 후 협소한 후속 스테이지에서 구현합니다.

## Stage 41 연동 안내

Stage 41에서 이 매트릭스를 활용하는 방식:

1. `smoke_scenario_matrix.json` 로드
2. 각 시나리오의 `question`과 `site_id`로 파이프라인 실행
3. 응답의 `site_id`, `sources`, `answer`를 `pass_criteria`와 대조
4. 결과를 리포트로 출력 (통과/실패/경고)

## 비고

- 이 매트릭스는 **문서 아티팩트**입니다. 백엔드/API 변경을 포함하지 않습니다.
- 시나리오 추가/수정은 JSON 파일과 이 문서를 동시에 업데이트합니다.
- `min_sources: 0건+`은 출처가 없어도 fallback으로 통과할 수 있음을 의미합니다.
- `min_sources: 1건`은 최소 1건의 유효한 출처가 필요함을 의미합니다.
