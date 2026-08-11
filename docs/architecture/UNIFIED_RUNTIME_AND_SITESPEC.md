# Unified Runtime과 canonical SiteSpec

- 상태: `active-plan`
- 기준일: 2026-08-12
- 현재 정렬 이슈: #1283
- historical foundation: #1225, #1228, #1229, #1230, #1232

## 1. 현재 문제와 구현 사실

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

새 기관이나 명칭 변경이 추가되면 서로 다른 계층의 값이 drift할 수 있다.

현재 저장소에는 canonical SiteSpec foundation과 dual-read/projection contract가 존재하지만, 이를 **임의의 기관·대학·은행·기업을 표현하는 범용 SiteSpec이 이미 완성된 상태로 해석하면 안 된다.**

현재 `configs/sitespec.schema.json`은 Buk-gu/지자체 identity migration을 위해 설계된 foundation이다. 현재 schema는 `jurisdiction`, `runtime`, `clone`을 필수로 두고, `clone.golden_commit` 및 Cloudflare/Python projection 정보를 포함한다. 이는 현재 Buk-gu golden compatibility에 유효한 계약이지만 대학·은행 등 모든 사이트 유형의 최종 범용 schema라는 뜻은 아니다.

또한 `configs/contracts/runtime-vocabulary.json`은 shared vocabulary inventory이지만 현재 `inventory_only: true`, `runtime_wired: false` 상태다. 문서가 이를 generic multi-site runtime wiring 완료로 과장해서는 안 된다.

## 2. 목표

하나의 canonical contract 계층에서 runtime별 adapter를 생성하거나 검증한다.

```text
Canonical contracts
  ├─ SiteSpec
  ├─ Archetype / Capability vocabulary   (planned)
  ├─ ProviderSpec
  ├─ ActionSpec
  ├─ EvidencePolicy
  └─ ApiSchema
        ↓
  Python adapter
  Cloudflare adapter
  Compatibility registry
  UI/operator metadata
  CI / onboarding QA
```

런타임 구현언어와 배포는 계속 분리할 수 있다. **의미와 vocabulary의 원본을 가능한 한 하나로 만든다.**

장기 제품 흐름은 다음을 목표로 한다. 이 흐름은 #1283 문서 정렬만으로 구현됐다고 주장하지 않는다.

```text
URL / SiteSpec
  -> site discovery
  -> archetype detection
  -> capability detection
  -> capture / route inventory
  -> generic Site Model
  -> generated preview
  -> knowledge index
  -> action graph / browser model
  -> automated QA
  -> exception queue
  -> focused human review
```

초기 목표는 100% 무검토 자동화가 아니라 70–80% supervised automation과 명시적 exception handling이다.

## 3. SiteSpec

### 3.1 현재 canonical SiteSpec foundation

현재 구현된 schema/instance는 Buk-gu identity와 compatibility migration에 초점을 둔다.

개념적 현재 형태:

```yaml
schema_version: "1.0.0"
site_id: "bukgu_gwangju"
legacy_ids:
  - "bukgu"

jurisdiction:
  canonical_name: "공식 확인된 현재 명칭"
  short_name: "북구"
  effective_from: "YYYY-MM-DD"
  historical_aliases: []

display:
  default_label: "북구청"
  locale_labels: {}

domains:
  public:
    - "bukgu.gwangju.kr"

runtime:
  python_profile: "bukgu_gwangju"
  cloudflare_adapter: "bukgu"

clone:
  golden_commit: "40-hex-sha"
  golden_commit_subject: "..."
```

이 구조는 **현재 구현 사실을 설명하는 것**이며, 아래의 범용 vNext 개념과 동일하지 않다.

### 3.2 범용 SiteSpec vNext 방향 — planned only

일반 사이트 플랫폼에서는 site identity와 유형별 속성을 분리할 필요가 있다. 아래 vocabulary는 설계 방향이며 `configs/sitespec.schema.json`에 아직 구현되지 않았다.

```yaml
identity:
  site_id: "..."
  legacy_ids: []
  display: {}

domains:
  public: []

entry_points:
  homepage: "https://.../"
  search: null

archetype:
  id: "municipality | university | bank | public_agency | support_portal | company | ..."
  confidence: 0.0

capabilities:
  - id: "site_search"
    confidence: 0.0
  - id: "notice_board"
    confidence: 0.0

capture_policy: {}
browser_policy: {}
knowledge_policy: {}
action_policy: {}
provenance: {}

extensions:
  municipality: null
  university: null
  financial: null
```

원칙:

- `ARCHETYPE`은 사이트 유형별 기본 가정과 detector/QA preset을 위한 개념이다.
- `CAPABILITY`는 실제 재사용 단위다. 예: `site_search`, `notice_board`, `document_library`, `directory`, `service_catalog`, `faq`, `calendar`, `form`, `contact`, `auth_boundary`.
- site는 `core + archetype + detected capabilities + site config + explicit exceptions/overrides` 방향으로 표현한다.
- municipality-only 필드는 core 필수값이 아니라 유형별 extension 후보로 검토한다.
- 한 사이트의 예외 때문에 shared core에 `if site_id == ...` 분기가 누적되는 것을 피한다.
- confidence와 unsupported 상태를 schema/runtime에서 숨기지 않는다.
- `generated_preview`는 exact/resident-default promotion과 별도 상태다.

### 3.3 identity 원칙

- `site_id`는 변경이 어려운 canonical machine ID다.
- `legacy_ids`는 migration·compatibility 용도다.
- 공식명·과거명·display label의 역할을 분리한다.
- 법적/행정 identity가 필요한 유형은 effective date와 historical alias를 보존한다.
- 그렇지 않은 유형에 municipal `jurisdiction` semantics를 억지로 적용하지 않는다.
- source URL과 page title 원문은 당시 snapshot/provenance에 보존한다.

### 3.4 현재 Buk-gu migration

현재 `bukgu`와 `bukgu_gwangju`를 즉시 하나로 치환하지 않는다.

1. canonical SiteSpec resolver/alias contract 유지
2. dual-read compatibility 유지
3. runtime projection parity 유지
4. test fixture와 public URL compatibility 유지
5. consumer migration evidence 확보
6. legacy ID deprecation은 별도 결정

범용 SiteSpec 변경은 Buk-gu existing contract를 깨뜨리는 in-place rewrite로 수행하지 않는다. vNext 설계 시 backward compatibility, adapter/projection, migration test를 별도 platform issue에서 결정한다.

## 4. ProviderSpec

현재 Cloudflare resident default provider path는 Gemini provider 하나를 기본으로 사용하며, 같은 provider 안에서 primary model → fallback model 순서를 갖는다.

현재 runtime fact:

```yaml
provider_id: gemini
runtime_support:
  cloudflare: true
models:
  primary: gemini-3.5-flash-lite
  fallback: gemini-3.1-flash-lite
env:
  api_key: GEMINI_API_KEY
  primary_model_override: GEMINI_MODEL
  fallback_model_override: GEMINI_FALLBACK_MODEL
endpoint_policy:
  production_default: code_owned_google_endpoint
  local_override:
    explicit_opt_in: true
    loopback_only: true
```

Hy3 remains supported/legacy optional code but is not in the default provider order. It is reached only when an operator explicitly includes it through the runtime order contract.

원칙:

- provider ID와 display name을 분리한다.
- primary model과 same-provider fallback model을 구분한다.
- model fallback과 provider fallback을 같은 의미로 기록하지 않는다.
- secret env 이름과 endpoint override policy를 검증한다.
- provider 목록이 README·Python·Cloudflare에서 따로 drift하지 않도록 한다.
- mock·stub·local provider와 production provider를 capability로 구분한다.
- repository defaults와 실제 deployed environment override는 같은 상태라고 추정하지 않는다.

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
- 향후 범용 action graph에서는 site-specific action ID와 reusable capability/action semantics를 구분한다.

## 6. EvidencePolicy

공통 enum 예시:

```text
canonical_snapshot
verified_live_source
supplementary_official_citation
model_only
```

Runtime별 freshness 상태는 별도 vocabulary를 가질 수 있으며 evidence level과 혼동하지 않는다.

각 evidence는 필요에 따라 다음 metadata를 가진다.

- source URL
- captured_at
- verified_at
- source_updated_at
- snapshot ID
- checksum
- retrieval request ID
- policy version

공식도메인 citation이라는 사실만으로 canonical/verified evidence로 승격하지 않는다. 고위험 claim은 applicable evidence policy를 따른다.

## 7. ApiSchema

개념적 envelope 예시:

```json
{
  "ok": true,
  "answer": "...",
  "action": "passport_guidance",
  "confidence": 1.0,
  "provider": "gemini",
  "model": "gemini-3.5-flash-lite",
  "selection_reason": "primary_provider",
  "sources": [],
  "meta": {
    "schema_version": "1.0",
    "request_id": "...",
    "provider_attempts": []
  }
}
```

공개 시민 응답과 operator diagnostic은 분리할 수 있다. 내부 오류·secret·raw provider body는 시민 응답에 포함하지 않는다. 실제 response shape는 `MVP_AI_RUNTIME_CONTRACT.md`와 runtime contract tests를 authoritative source로 본다.

## 8. Runtime adapter

### Python adapter

- SiteSpec을 기존 site profile object로 projection
- crawler limits·domain·patterns 적용
- provider runtime capability 확인
- output에 canonical site ID 포함

현재 모든 future general-site fields가 Python runtime에 wired됐다고 주장하지 않는다.

### Cloudflare adapter

- 현재 Buk-gu SiteSpec metadata는 checked-in JS projection을 통해 Cloudflare runtime에서 사용한다.
- action·locale·evidence vocabulary contract를 유지한다.
- production provider endpoint는 code-owned default를 사용한다.
- server secret은 생성산출물에 포함하지 않는다.

현재 Cloudflare resident runtime 전체가 arbitrary SiteSpec으로 parameterized됐다고 주장하지 않는다.

### Compatibility registry

- golden commit과 frozen source를 current compatibility contract와 연결
- 현재 Buk-gu adapter matrix를 유지
- 새 기관은 generic capability가 검증될 때만 appropriate registry/promotion 단계로 이동

## 9. Archetype과 Capability — planned platform layer

### Archetype

사이트 부류별 반복되는 정보구조·수집전략·QA preset을 제공하는 보조계층이다.

후보:

- municipality
- university
- bank
- public agency
- support-program portal
- company

Archetype은 사이트를 고정된 템플릿으로 강제하는 값이 아니라 detection/prior/QA preset 역할을 한다.

### Capability

사이트 종류를 가로질러 재사용되는 실제 기능단위다.

초기 후보:

```text
site_search
notice_board
document_library
directory
service_catalog
faq
calendar
form
contact
map_or_location
auth_boundary
```

동일 capability는 municipality/university/company 등 여러 archetype에서 재사용할 수 있어야 한다.

## 10. 모듈 경계

### Cloudflare Function

```text
handler
  -> request validation
  -> site/action resolution
  -> official context
  -> evidence policy
  -> provider/model attempt plan
  -> locale policy
  -> response schema
  -> telemetry
```

### 시민 shell / AI Browser

```text
shell façade
  -> state machine
  -> chat/composer
  -> recommendations
  -> journey router
  -> browser history
  -> locale
  -> accessibility/motion
  -> browser/action bridge
```

장기 제품 UX는 왼쪽 target site/clone/generated surface와 오른쪽 AI conversation/navigation/Browser Use를 공통 shell에서 제공하는 방향이다.

기존 Buk-gu public façade, DOM ID, data attribute와 route vocabulary는 migration 없이 변경하지 않는다.

## 11. 생성·검증 전략

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

1. current inventory와 contract audit
2. generic vNext schema/interface design
3. Buk-gu compatibility adapter/projection
4. generated preview path
5. second-site onboarding
6. archetype/capability gaps를 shared core로 승격
7. cross-domain validation
8. source-of-truth migration은 evidence 후 결정

## 12. 북구 golden 보호

- 기존 golden commit·manifest는 즉시 재작성하지 않는다.
- generic projection/generated preview는 별도 preview/debug route에서 실행한다.
- route·target·DOM·state·visual baseline을 비교한다.
- applicable parity와 rollback이 확보되기 전 resident-default를 전환하지 않는다.
- golden source를 삭제하는 refactor는 별도 migration issue가 필요하다.
- generated preview 성공률을 높이기 위해 Buk-gu exact/golden contract를 약화하지 않는다.

## 13. 완료조건 — future platform

이 문서의 전체 platform 방향은 다음이 충족될 때 완료로 볼 수 있다.

- arbitrary-site를 표현할 generic SiteSpec/Site Model contract가 versioned 형태로 존재한다.
- archetype과 capability vocabulary가 정의되고 onboarding 결과에 confidence/exception이 기록된다.
- Python·Cloudflare·registry/shared contracts의 drift가 CI에서 차단된다.
- Buk-gu legacy/canonical ID와 golden observable behavior가 안전하게 보존된다.
- URL/SiteSpec에서 generated preview, knowledge, action/browser model, QA, exception report를 생성한다.
- 두 번째 지자체가 bespoke renderer 없이 또는 최소 reviewed override로 onboarding된다.
- 대학 등 교차도메인 사이트가 같은 core/capability 구조로 검증된다.
- automation/human-review/unsupported 비율을 정직하게 측정한다.

현재 이 완료조건을 이미 충족했다고 주장하지 않는다.
