# Unified Runtime과 canonical SiteSpec

- 상태: `active-plan`
- 기준일: 2026-08-04
- 관련 이슈: #1225, #1228, #1229, #1230, #1232

## 1. 문제

현재 프로젝트에는 세 가지 설정·계약 계층이 있다.

```text
Python runtime
  configs/sites/*.yml
  src/llm
  crawler / index / operator

Cloudflare runtime
  functions/api/mvp/ask.js
  provider / action / locale / snapshot / response constants

Platform compatibility
  configs/site-registry.json
  golden commit / frozen contract sources
```

각 계층은 정당한 목적이 있지만 다음 의미를 별도로 관리한다.

- site ID와 기관명
- domain allowlist
- provider·model
- action·route
- locale
- freshness·evidence 상태
- runtime capability
- feature flag

새 기관이나 행정명칭 변경이 추가되면 서로 다른 계층의 값이 drift할 수 있다.

## 2. 목표

하나의 canonical contract로부터 runtime별 adapter를 생성하거나 검증한다.

```text
Canonical contracts
  ├─ SiteSpec
  ├─ ProviderSpec
  ├─ ActionSpec
  ├─ EvidencePolicy
  └─ ApiSchema
        ↓
  Python adapter
  Cloudflare adapter
  Compatibility registry
  UI/operator metadata
  CI matrix
```

런타임 구현언어와 배포는 계속 분리할 수 있다. **의미와 vocabulary의 원본만 하나로 만든다.**

## 3. SiteSpec

### 3.1 권장 구조

```yaml
schema_version: "1.0"
site_id: "bukgu_gwangju"
legacy_ids:
  - "bukgu"

jurisdiction:
  canonical_name: "공식 확인된 현재 명칭"
  short_name: "북구"
  aliases:
    - value: "광주광역시 북구"
      valid_until: "YYYY-MM-DD"
  effective_from: "YYYY-MM-DD"

public_domains:
  - "bukgu.gwangju.kr"
  - "search.bukgu.gwangju.kr"

entry_points:
  homepage: "https://.../"
  search: "https://.../"

classification:
  site_type: "LEGACY_BOARD_SITE"
  tags:
    - "municipal"

capture:
  respect_robots: true
  max_depth: 3
  max_pages: 200
  allow_patterns: []
  deny_patterns: []
  protected_patterns: []

clone:
  golden_commit: "40-hex-sha"
  compatibility_manifest: "docs/..."
  resident_default_policy: "owner_visual_approval_required"

runtime:
  python_profile: true
  cloudflare_citizen: true
  generic_platform: "preview"

locales:
  - ko
  - en
  - vi
  - th
  - id
```

### 3.2 identity 원칙

- `site_id`는 변경이 어려운 canonical machine ID다.
- `legacy_ids`는 migration·compatibility 용도다.
- `canonical_name`은 공식 근거와 effective date를 가진다.
- `short_name`과 locale별 display name은 UI용이다.
- 과거 명칭을 삭제하지 않고 validity를 기록한다.
- source URL과 page title 원문은 당시 snapshot에 보존한다.

### 3.3 migration

현재 `bukgu`와 `bukgu_gwangju`를 즉시 하나로 치환하지 않는다.

1. alias registry 추가
2. dual-read·canonical-write
3. API와 logs에 canonical ID + received legacy ID 기록
4. test fixture와 public URL compatibility 유지
5. consumer migration evidence 확보
6. legacy ID deprecation 결정

## 4. ProviderSpec

권장 필드:

```yaml
provider_id: gemini
runtime_support:
  python: false
  cloudflare: true
models:
  default: gemini-3.1-flash-lite
endpoint_policy:
  production_locked: true
  local_override:
    explicit_opt_in: true
    loopback_only: true
secret_env:
  - GEMINI_API_KEY
limits:
  timeout_ms: 15000
  max_output_tokens: 700
telemetry:
  usage_supported: true
```

원칙:

- provider ID와 display name을 분리한다.
- default model은 runtime마다 다를 수 있지만 명시한다.
- secret env 이름과 endpoint override policy를 schema로 검증한다.
- provider 목록이 README·Python·Cloudflare에서 따로 drift하지 않도록 한다.
- mock·stub·local provider와 production provider를 capability로 구분한다.

## 5. ActionSpec

```yaml
action_id: passport_guidance
intent_examples:
  ko:
    - "여권 발급은 어디서 하나요?"
routes:
  canonical: passport-guidance
safety:
  writes_external_state: false
  requires_confirmation: false
evidence:
  minimum_level: canonical_snapshot
fallback:
  when_unavailable: general_direction_only
```

원칙:

- action ID는 모델 출력 allowlist이자 runtime contract다.
- route와 DOM target은 별도 vocabulary로 유지한다.
- action의 evidence requirement와 write risk를 함께 기록한다.
- deterministic classifier와 model result의 우선순위를 명시한다.
- locale별 intent example은 data로 관리한다.

## 6. EvidencePolicy

공통 enum 예시:

```text
canonical_snapshot
verified_live_source
supplementary_official_citation
snapshot_unavailable
model_only
unavailable
```

각 상태는 다음 metadata를 가질 수 있다.

- source URL
- captured_at
- verified_at
- source_updated_at
- snapshot ID
- checksum
- retrieval request ID
- policy version

고위험 claim type별 최소등급은 #1226에서 구현한다.

## 7. ApiSchema

공통 envelope 예시:

```json
{
  "ok": true,
  "data": {
    "answer": "...",
    "action": "passport_guidance",
    "confidence": 1.0,
    "sources": []
  },
  "meta": {
    "schema_version": "1.0",
    "site_id": "bukgu_gwangju",
    "locale": "ko",
    "provider": "gemini",
    "model": "...",
    "freshness_state": "canonical_snapshot",
    "request_id": "...",
    "latency_ms": 0,
    "policy_version": "..."
  }
}
```

공개 시민 응답과 operator diagnostic은 분리할 수 있다. 내부 오류·secret·raw provider body는 시민 응답에 포함하지 않는다.

## 8. Runtime adapter

### Python adapter

- SiteSpec을 기존 site profile object로 변환
- crawler limits·domain·patterns 적용
- provider runtime capability 확인
- output에 canonical site ID 포함

### Cloudflare adapter

- build time에 필요한 최소 JSON/ES module 생성
- action·locale·evidence vocabulary 검증
- production endpoint를 code-owned allowlist로 고정
- server secret은 생성산출물에 포함하지 않음

### Compatibility registry

- golden commit과 frozen source를 SiteSpec clone section과 연결
- 현재 북구 adapter matrix를 유지
- 새 기관은 generic capability가 검증될 때만 registry에 승격

## 9. 모듈 경계

### Cloudflare Function

```text
handler
  -> request validation
  -> site/action resolution
  -> official context
  -> evidence policy
  -> provider runner
  -> locale policy
  -> response schema
  -> telemetry
```

### 시민 shell

```text
shell façade
  -> state machine
  -> chat/composer
  -> recommendations
  -> journey router
  -> browser history
  -> locale
  -> accessibility/motion
  -> live bridge
```

기존 public façade, DOM ID, data attribute와 route vocabulary는 migration 없이 변경하지 않는다.

## 10. 생성·검증 전략

가능한 두 방식:

### A. 생성

canonical YAML/JSON에서 runtime artifact를 생성한다.

장점: drift 최소화
단점: build complexity와 generated file review 필요

### B. 독립 adapter + contract test

각 runtime 설정은 유지하되 canonical schema와 비교한다.

장점: 점진적 도입
단점: 중복은 남음

권장 순서:

1. inventory와 schema
2. contract test
3. read adapter
4. generated artifact 후보
5. dual-run parity
6. source-of-truth 전환

## 11. 북구 golden 보호

- 기존 golden commit·manifest는 즉시 재작성하지 않는다.
- generic projection은 별도 preview route에서 실행한다.
- route·target·DOM·state·visual baseline을 비교한다.
- parity와 rollback이 확보되기 전 resident-default를 전환하지 않는다.
- golden source를 삭제하는 refactor는 별도 migration issue가 필요하다.

## 12. 완료조건

- SiteSpec·ProviderSpec·ActionSpec·EvidencePolicy·ApiSchema가 versioned schema로 존재한다.
- Python·Cloudflare·registry의 drift가 CI에서 차단된다.
- `bukgu` legacy ID가 canonical ID와 안전하게 공존한다.
- 기관명·alias·effective date가 단일 metadata에서 생성된다.
- 북구 generic preview가 golden observable behavior를 재현한다.
- 다른 지자체와 교차도메인 사이트가 bespoke renderer 없이 onboarding된다.
