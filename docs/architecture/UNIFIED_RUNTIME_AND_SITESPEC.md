# Unified Runtime과 canonical SiteSpec

- 상태: `active-plan`
- 기준일: 2026-08-12
- 현재 lifecycle 정렬: #1301
- active onboarding validation: #1232
- completed generic-contract foundation: #1287
- historical foundation: #1225, #1228, #1229, #1230

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
- domain declarations
- provider·model
- action·route
- locale
- freshness·evidence 상태
- runtime capability
- feature flag

새 기관이나 명칭 변경이 추가되면 서로 다른 계층의 값이 drift할 수 있다.

현재 저장소에는 두 세대의 SiteSpec 관련 계약이 함께 존재한다.

1. Buk-gu/municipality-shaped SiteSpec v1 foundation + dual-read/projection compatibility
2. #1287에서 추가된 versioned Generic SiteSpec vNext / archetype / capability / onboarding-report contract foundation

이 사실을 다음 두 극단 중 어느 쪽으로도 과장하면 안 된다.

- `generic contracts are still planned only` — 현재는 사실이 아님
- `arbitrary-site end-to-end runtime is complete` — 이것도 사실이 아님

현재 Generic vNext는 **contract foundation이 구현된 상태**이며, arbitrary-site faithful clone compiler, full acquisition runtime, generic AI Browser surface wiring까지 모두 완료됐다는 뜻은 아니다.

또한 `configs/contracts/runtime-vocabulary.json`의 historical/current shared vocabulary role과 Generic vNext contracts는 같은 계층이라고 가정하지 않는다. Runtime별 wiring 여부는 실제 code/test evidence를 기준으로 판단한다.

## 2. 목표

하나의 canonical contract 계층에서 runtime별 adapter를 생성하거나 검증한다.

```text
Canonical contracts
  ├─ SiteSpec v1 compatibility
  ├─ Generic SiteSpec vNext
  ├─ Archetype / Capability vocabulary
  ├─ Onboarding Report
  ├─ ProviderSpec
  ├─ ActionSpec
  ├─ EvidencePolicy
  └─ ApiSchema
        ↓
  Python adapter
  Cloudflare adapter
  Compatibility registry
  Clone/onboarding engine
  UI/operator metadata
  CI / onboarding QA
```

런타임 구현언어와 배포는 계속 분리할 수 있다. **의미와 vocabulary의 원본을 가능한 한 하나로 만든다.**

### 2.1 Platform structural development flow

Synthetic/offline fixture를 사용한 shared-core 개발은 다음처럼 진행할 수 있다.

```text
Generic SiteSpec
  -> archetype / capability contract
  -> synthetic/offline discovery input
  -> generic Site Model
  -> structural preview
  -> knowledge/action contract
  -> automated QA
  -> exception/report contract
```

이 흐름은 named real site의 clone 완료 증거가 아니다.

### 2.2 Named real-site onboarding flow

실제 이름을 가진 기관/site를 onboard할 때는 canonical clone lifecycle을 따른다.

```text
ACTUAL TARGET SITE
  -> scoped point-in-time reference baseline
  -> Generic SiteSpec / archetype / capabilities
  -> generic Site Model
  -> faithful clone candidate
  -> structural/content/asset/interaction/visual comparison
  -> clone MVP ready
  -> knowledge index
  -> action graph / browser model
  -> AI-on-clone validation
  -> automated QA / exception queue
```

초기 자동화 목표는 100% 무검토 자동화가 아니라 70–80% supervised automation과 명시적 exception handling이다.

Automation ratio는 fidelity evidence가 아니다.

## 3. SiteSpec

### 3.1 현재 canonical SiteSpec v1 foundation

현재 v1 schema/instance는 Buk-gu identity와 compatibility migration에 초점을 둔다.

개념적 형태:

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

이 구조는 현재 Buk-gu compatibility 사실을 설명하며 Generic vNext와 동일하지 않다.

### 3.2 Generic SiteSpec vNext contract foundation — implemented

#1287에서 arbitrary-site를 표현하기 위한 versioned generic contract foundation이 추가됐다.

개념적 core vocabulary:

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
  id: "municipality | university | bank | public_agency | support_portal | company | unknown"
  confidence: 0.0

capabilities:
  - id: "site_search"
    state: "detected | configured | review_required | unsupported | not_detected"
    confidence: 0.0

capture_policy: {}
browser_policy: {}
knowledge_policy: {}
action_policy: {}
provenance: {}
extensions: {}
```

현재 구현 사실:

- versioned generic SiteSpec schema/fixtures 존재
- archetype vocabulary/confidence semantics 존재
- capability vocabulary/state/confidence semantics 존재
- onboarding-report contract foundation 존재
- Buk-gu compatibility/projection evidence 존재
- Seo-gu offline generic Site Model/structural preview evidence 존재

현재 미완료/비주장:

- arbitrary URL acquisition이 production-ready라는 주장
- arbitrary-site faithful clone compiler가 완성됐다는 주장
- 모든 Generic vNext field가 Python/Cloudflare resident runtime에 wired됐다는 주장
- structural preview가 named-site faithful clone이라는 주장

원칙:

- `ARCHETYPE`은 사이트 유형별 detector/QA prior다.
- `CAPABILITY`는 실제 재사용 단위다. 예: `site_search`, `notice_board`, `document_library`, `directory`, `service_catalog`, `faq`, `calendar`, `form`, `contact`, `map_or_location`, `auth_boundary`.
- site는 `core + archetype + detected capabilities + site config + explicit exceptions/overrides` 방향으로 표현한다.
- municipality-only 필드는 generic core 필수값으로 강제하지 않는다.
- shared core에 `if site_id == ...` 분기가 누적되는 것을 피한다.
- confidence와 unsupported/review-required 상태를 숨기지 않는다.

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

Generic vNext는 Buk-gu v1을 destructive in-place rewrite하지 않고 versioned/additive contract + adapter/projection으로 확장한다.

## 4. ProviderSpec

현재 Cloudflare resident default provider path는 Gemini provider 하나를 기본으로 사용하며, 같은 provider 안에서 primary model -> fallback model 순서를 갖는다.

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
- repository defaults와 actual deployed environment override는 같은 상태라고 추정하지 않는다.

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
- 범용 action graph에서는 site-specific action ID와 reusable capability/action semantics를 구분한다.

Pre-integration clone MVP의 Browser Use는 controlled clone surface에서 검증한다. Actual production-site authenticated/submission/write actions는 future first-party integration 단계다.

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

Clone visible-surface freshness와 answer evidence freshness는 별개일 수 있다. Newer answer evidence가 있다고 해서 approved clone이 자동으로 live mirror가 되지는 않는다.

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

현재 모든 Generic vNext field가 Python runtime에 wired됐다고 주장하지 않는다.

### Cloudflare adapter

- 현재 Buk-gu SiteSpec metadata는 checked-in JS projection을 통해 Cloudflare runtime에서 사용한다.
- action·locale·evidence vocabulary contract를 유지한다.
- production provider endpoint는 code-owned default를 사용한다.
- server secret은 생성산출물에 포함하지 않는다.

현재 Cloudflare resident runtime 전체가 arbitrary Generic SiteSpec으로 parameterized됐다고 주장하지 않는다.

### Compatibility registry

- golden commit과 frozen source를 current compatibility contract와 연결
- 현재 Buk-gu adapter matrix를 유지
- 새 기관은 faithful clone/onboarding evidence가 확보될 때 appropriate promotion 단계로 이동

## 9. Archetype과 Capability — implemented contract layer, partial runtime wiring

### Archetype

사이트 부류별 반복되는 정보구조·수집전략·QA preset을 제공하는 보조계층이다.

현재 contract vocabulary에는 municipality, university, bank, public agency, support portal, company, unknown 등 일반사이트 분류를 표현할 수 있는 foundation이 존재한다.

Archetype은 사이트를 고정된 템플릿으로 강제하는 값이 아니라 detection/prior/QA preset 역할을 한다.

### Capability

사이트 종류를 가로질러 재사용되는 실제 기능단위다.

초기 contract vocabulary:

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

Contract vocabulary 존재는 해당 capability의 live acquisition/browser implementation이 모두 완료됐다는 의미가 아니다.

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

Pre-integration stable product shape:

```text
left:  faithful clone surface
right: AI conversation / answer / navigation / Browser Use
```

Conceptual shell:

```text
shell façade
  -> clone/site surface
  -> state machine
  -> chat/composer
  -> recommendations
  -> journey router
  -> browser history
  -> locale
  -> accessibility/motion
  -> browser/action bridge
```

기존 Buk-gu public façade, DOM ID, data attribute와 route vocabulary는 migration 없이 변경하지 않는다.

Actual production-site surface는 기관의 first-party integration 승인이 생긴 뒤 별도 adapter/deployment 단계에서 다룬다.

## 11. 생성·검증 전략

### Shared-core structural generation

canonical JSON/contracts에서 generic artifacts를 생성하거나 adapter + contract test로 검증한다.

이 모드는 synthetic/offline evidence로 충분할 수 있다.

### Named-site clone generation

Named site에서는 구조 생성보다 reference baseline이 먼저다.

권장 순서:

1. current inventory와 contract audit
2. Generic vNext contracts / Buk-gu compatibility
3. shared structural engine proof
4. named-site declared MVP scope
5. actual-site point-in-time reference baseline
6. generic Site Model / theme / content mapping
7. faithful clone candidate
8. structural/content/asset/interaction/visual comparison
9. clone MVP readiness
10. AI-on-clone knowledge/action/browser validation
11. second-site gaps를 shared core/capability로 승격
12. cross-domain validation
13. source-of-truth migration은 evidence 후 결정

## 12. 북구 golden 보호

- 기존 golden commit·manifest는 즉시 재작성하지 않는다.
- generic projection/structural preview는 별도 preview/debug evidence로 유지할 수 있다.
- route·target·DOM·state·visual baseline을 비교한다.
- applicable parity와 rollback이 확보되기 전 resident-default를 전환하지 않는다.
- golden source를 삭제하는 refactor는 별도 migration issue가 필요하다.
- generic success률을 높이기 위해 Buk-gu exact/golden contract를 약화하지 않는다.

## 13. Clone lifecycle과 actual-site integration boundary

Current pre-integration development의 기본은 faithful clone이다.

기관이 actual production site 운영/통합 권한을 부여한 뒤 future first-party integration phase가 열린다.

그때 실제 환경 기준으로 information security, privacy/PII, authentication, real submissions/payment/write, internal-system integration, hosting/deployment ownership, monitoring/incident/support, staging/rollback을 정의한다.

이 future production 조건은 current clone fidelity, clone comparison, AI-on-clone stakeholder evaluation을 위한 선행 blocker가 아니다.

## 14. Future platform 완료조건

전체 platform 방향은 다음이 충족될 때 완료로 볼 수 있다.

- arbitrary-site를 표현할 Generic SiteSpec/Site Model contract가 versioned 형태로 존재한다.
- archetype/capability vocabulary와 onboarding report가 runtime/onboarding 결과에 사용된다.
- Python·Cloudflare·registry/shared contracts의 drift가 CI에서 차단된다.
- Buk-gu legacy/canonical ID와 golden observable behavior가 안전하게 보존된다.
- named site의 reference baseline에서 faithful clone candidate를 생성하고 비교할 수 있다.
- URL/SiteSpec onboarding에서 knowledge, action/browser model, QA, exception report를 생성한다.
- 두 번째 지자체가 bespoke renderer 없이 또는 최소 reviewed override로 faithful clone MVP까지 onboarding된다.
- 대학 등 교차도메인 사이트가 같은 core/capability 구조로 검증된다.
- automation/human-review/unsupported 비율을 정직하게 측정한다.
- actual-site production integration은 institution authorization 이후 별도 단계로 유지된다.

현재 이 완료조건을 이미 모두 충족했다고 주장하지 않는다.
