# 라이브 전환 게이트 검증 체크리스트

> **기준 문서:** [`live-transition-decision-record.md`](live-transition-decision-record.md) §3  
> **2026-07-10 업데이트:** 현재 Cloudflare MVP Function은 **Gemini**(`gemini-3.1-flash-lite`)를 사용합니다.
> 아래 hy3/kilocode 참조는 이전 결정 기록입니다.  
> **리포지토리:** `/root/400-ai-finder` (main SHA: `703dbf6`)
> **작성일:** 2026-07-10

---

## 상태 요약

| 게이트 | 상태 |
|--------|------|
| 1. Explicit issue scope | ⚠️ **부분 충족** |
| 2. Confidentiality boundary | ✅ **충족** |
| 3. Allowed host / provider | ✅ **충족** |
| 4. No secret leakage | ✅ **충족** |
| 5. No uncontrolled crawling | ✅ **충족** |
| 6. No site-affecting action | ✅ **충족** |
| 7. Rollback plan | ⚠️ **부분 충족** |
| 8. Test plan split | ✅ **충족** |
| 9. Report format | ❌ **미충족** |
| 10. CI / local default | ✅ **충족** |

**전체:** 7/10 ✅ 충족, 2/10 ⚠️ 부분 충족, 1/10 ❌ 미충족  
**→ Mode 3 (controlled live navigation) 진입 차단:** 게이트 #9 (Report format) 미충족으로 Mode 3 진행 불가.

---

## 게이트별 상세 평가

### Gate 1 — Explicit issue scope
**요구사항:** Named issue with purpose, in/out of scope, chosen work mode

| 항목 | 상태 | 근거 |
|------|------|------|
| Named issue | ⚠️ | live-transition-decision-record.md가 mode 2를 "지금 활성화 중"이라고 명시하지만, 이 전환 자체를 스코핑한 단일 issue/PR이 없음. `#862`(navigator+live)와 `#930/#931`(fail-closed diagnostics)가 참조되나 이 전환 단계를 직접 스코핑하지 않음. |
| Purpose & in/out of scope | ⚠️ | 문서에 mode 2의 목적이 설명되어 있으나, 별도 issue로 공식 스코핑되지 않음. |
| Chosen work mode | ✅ | 문서 §2에서 mode 2를 명시적으로 선택함. |
| **종합** | ⚠️ | 문서에 의도는 명확하지만, 공식 issue 기반 스코핑 부재. Mode 3 진입 전에 scoped issue 생성 권장. |

**권장:** `#862` 또는 새 issue에서 "Enable provider-assisted LLM answering (mode 2)"를 명시적으로 스코핑할 것.

---

### Gate 2 — Confidentiality boundary
**요구사항:** No confidential business/client/person details in public docs, issues, PRs, logs, fixtures

| 항목 | 상태 | 근거 |
|------|------|------|
| Public docs | ✅ | 모든 문서에 기밀 정보 없음. `.env`는 `.gitignore` 처리됨. |
| Code/fixtures | ✅ | 테스트 fixture에 canary secret 사용, 실제 API 키 미포함. |
| Logs/artifacts | ✅ | `conversation_log`는 일반 대화 로그, 기밀 정보 미포함. |
| **종합** | ✅ | 문서/코드 전반적으로 기밀 정보 노출 없음. |

---

### Gate 3 — Allowed host / provider
**요구사항:** hy3/kilocode provider; allowlist host = `bukgu.gwangju.kr`

| 항목 | 상태 | 근거 |
|------|------|------|
| Provider: hy3/kilocode | ✅ | `BUILTIN_PROVIDERS["kilocode"]` 등록됨. `functions/api/mvp/ask.js`에서 `tencent/hy3:free` 사용. `KILOCODE_API_KEY` env var로 인증. |
| Allowlist host: `bukgu.gwangju.kr` | ✅ | `configs/sites/bukgu_gwangju.yml`에 `allowed_domains: [bukgu.gwangju.kr]`. `base_url: "https://bukgu.gwangju.kr/"` |
| CF Pages function uses approved path | ✅ | `/api/mvp/ask` Cloudflare Function은 hy3/kilocode만 호출, 다른 provider로 fallback 없음. |
| **종합** | ✅ | 승인된 provider와 host만 사용. |

---

### Gate 4 — No secret leakage
**요구사항:** No secrets in repo, logs, artifacts, screenshots, or PR text

| 항목 | 상태 | 근거 |
|------|------|------|
| Closed failure vocabulary | ✅ | `FAILURE_CONFIGURATION`, `FAILURE_TIMEOUT` 등 고정 코드만 노출. `ProviderResult.failure_code`는 절대 raw 예외 텍스트/URL/API 키를 포함하지 않음. |
| Secret leak tests | ✅ | `test_mvp_failure_codes.py`에서 canary secret(`CANARY_SECRET`, `CANARY_URL`)이 응답에 누출되지 않음을 검증. |
| API key handling | ✅ | `.env` 파일, Cloudflare Pages secrets(`KILOCODE_API_KEY`)로 안전하게 관리. 코드에 API 키 하드코딩 없음. |
| **종합** | ✅ | 여러 계층의 비밀 보호 조치 구현 및 테스트 완료. |

---

### Gate 5 — No uncontrolled crawling
**요구사항:** No open-ended crawl; navigation is bounded and listed

| 항목 | 상태 | 근거 |
|------|------|------|
| Crawl bounds defined | ✅ | `configs/sites/bukgu_gwangju.yml`: `max_depth: 3`, `max_pages: 200`, `respect_robots: true` |
| Allow/deny patterns | ✅ | `deny_patterns`에 `print=`, `utm_`, `mid=`, `seq=` 등 보호 패턴 명시. |
| Live LLM answering ≠ crawling | ✅ | Mode 2는 LLM API 호출만 수행, 사이트 크롤링 없음. |
| **종합** | ✅ | 크롤링 범위가 명시적으로 제한됨. Mode 2는 크롤링 없음. |

---

### Gate 6 — No site-affecting action
**요구사항:** No form submission / authentication / payment / receipt / completion unless separately approved

| 항목 | 상태 | 근거 |
|------|------|------|
| Form submission | ✅ | 모든 MVP action은 `STOP_FOR_USER_CONFIRMATION`. 실제 제출/결제 없음. |
| Authentication | ✅ | 로그인/인증 코드 없음. |
| Payment/receipt | ✅ | 결제/수령 관련 코드 없음. |
| **종합** | ✅ | 읽기 전용 LLM 응답만 수행. site-affecting action 없음. |

---

### Gate 7 — Rollback plan
**요구사항:** How to stop/disable the live path (e.g. provider flag)

| 항목 | 상태 | 근거 |
|------|------|------|
| Provider flag exists | ✅ | `mvp_provider` injection parameter. `decide_bukgu_quest_action()`이 quest-match 시 provider 우회. `mock` provider가 기본값. Cloudflare function은 API key 없으면 config_error 반환. |
| Documented rollback procedure | ❌ | 문서화된 중단/비활성화 절차 없음. 메커니즘은 존재하지만 "이렇게 하면 live path를 중단할 수 있다"는 공식 rollback plan 없음. |
| **종합** | ⚠️ | 기술적 메커니즘은 존재하나 절차 문서화 부재. Mode 3 진입 전에 rollback plan 문서화 권장. |

**권장:** 다음 내용을 문서에 추가:
- `KILOCODE_API_KEY` env var 제거 또는 빈 값 설정 → live provider 비활성화
- `AI_FINDER_LLM_PROVIDER=mock` 설정 → 모든 LLM 호출을 mock으로 전환
- Cloudflare Pages: `KILOCODE_API_KEY` secret 관리 (CF_PAGES_KILOCODE_API_KEY에서 KILOCODE_API_KEY로 통일 완료)
- quest registry에 등록된 quest만 응답, 미등록 질문은 모두 `none` 처리

---

### Gate 8 — Test plan split
**요구사항:** Local/static tests remain default; live-only validation is opt-in and separate

| 항목 | 상태 | 근거 |
|------|------|------|
| Local/static tests as default | ✅ | `test_mvp_action_contract.py`, `test_mvp_failure_codes.py` 모두 injectable fake provider 사용. 네트워크 호출 없음. |
| Live-only tests opt-in | ✅ | KiloCode live test: `RUN_LIVE_KILOCODE_TESTS=1` 필요. 문서화된 opt-in 정책 (`provider-fetch-network-boundary.md` §325). |
| Test isolation | ✅ | `MockProvider`, `StubProvider`, fake providers로 완전히 격리된 테스트. |
| **종합** | ✅ | 테스트 분리 정책이 코드와 문서 모두에 명확히 구현됨. |

---

### Gate 9 — Report format
**요구사항:** What was fetched/clicked/called (host, method/purpose, time, outcome) — without confidential payloads

| 항목 | 상태 | 근거 |
|------|------|------|
| Formal post-action report format | ❌ | 구현된 post-action report 없음. `logs/conversations.jsonl`은 일반 대화 로그로, 요구되는 구조화된 리포트(host, method/purpose, time, outcome)가 아님. |
| Operator dashboard | ⚠️ | `admin_demo.py`에서 `llm_live`, `llm_status`, `llm_label` 표시하나, 세부 호출 이력 리포트는 아님. |
| Report documentation | ❌ | Gate §3에서 "Report format"을 요구사항으로 명시했으나, 실제 format이 정의되거나 구현되지 않음. |
| **종합** | ❌ | **Mode 3 (controlled live navigation) 진입을 위한 critical blocker.** Post-action report format이 정의되지 않았고 구현되지 않음. |

**권장:** post-action report format 정의 및 구현. 예시 구조:
```json
{
  "host": "api.kilo.ai",
  "method": "POST /api/gateway/v1/chat/completions",
  "purpose": "resident_question_answering",
  "time": "2026-07-10T12:34:56+09:00",
  "outcome": "success",
  "failure_code": "",
  "provider": "kilocode",
  "model": "tencent/hy3:free"
}
```

---

### Gate 10 — CI / local default
**요구사항:** Confirm CI and default local tests do not require live network

| 항목 | 상태 | 근거 |
|------|------|------|
| Default provider = mock | ✅ | `get_provider()` fallback이 `mock`. `.env.example`의 기본값도 `mock`. |
| CI workflow config exists | ✅ | `.github/workflows/mvp-contracts.yml` 존재, Cloudflare Function test step 있음 (env gate으로 live 테스트와 분리) |
| Local tests networking-free | ✅ | 모든 기본 pytest가 live network 없이 통과. |
| **종합** | ✅ | CI 설정 완료, live network 없이 동작함을 명시적으로 검증 가능. |

**권장:** 현재 workflow 유지 중 (mvp-contracts.yml) Cloudflare Function test 포함. 향후 추가 workflow가 필요하면 `.github/workflows/`에 추가 가능.

---

## 다음 단계 (Mode 3: Controlled Live Navigation) 진입 조건

Mode 3 (controlled live navigation — click/fetch the real `bukgu.gwangju.kr` site)로 진행하려면 **10개 게이트 모두 충족**이 필요합니다. 현재 상태:

| 선결 조건 | 현재 | 필요 조치 |
|-----------|------|-----------|
| Gate 1 (Issue scope) | ⚠️ 부분 | Scoped issue 생성 (또는 #862 확장) |
| Gate 2~6 | ✅ 충족 | 추가 조치 불필요 |
| Gate 7 (Rollback plan) | ⚠️ 부분 | Rollback 절차 문서화 |
| Gate 8 (Test split) | ✅ 충족 | 추가 조치 불필요 |
| **Gate 9 (Report format)** | **❌ 미충족** | **Post-action report format 정의 및 구현 (Critical)** |
| Gate 10 (CI/local default) | ✅ 충족 | 추가 조치 불필요 |

**Mode 3 진입을 위해 필요한 최소 작업:**
1. Post-action report format 정의 및 구현 (Gate #9 해소)
2. Rollback plan 문서화 (Gate #7 해소)
3. Mode 3 전환을 위한 scoped issue 생성 (Gate #1 해소)

---

## 부록: 현재 구현된 Mode 2 컴포넌트

| 컴포넌트 | 파일 | 설명 |
|----------|------|------|
| LLM router (Python) | `src/llm/bukgu_mvp_router.py` | 질문→action 결정 로직, quest registry 우선, provider fallback |
| Provider abstraction | `src/llm/openai_compatible_provider.py` | OpenAI 호환 API provider (closed failure vocabulary) |
| KiloCode provider | `src/llm/__init__.py` | `BUILTIN_PROVIDERS["kilocode"]` 등록 |
| API endpoint (Python) | `src/web/mobile_demo.py` (lines 235-339) | `POST /api/mvp/ask` handler |
| API endpoint (CF Pages) | `functions/api/mvp/ask.js` | hy3/kilocode LLM 프록시 (Cloudflare Pages) |
| Live status detection | `src/llm/runtime_status.py` | `is_live_llm_provider()`로 live 여부 판별 |
| Test split | `tests/test_mvp_action_contract.py` | Fake provider 사용, live 호출 없음 |
| Failure code tests | `tests/test_mvp_failure_codes.py` | Sanitized failure code 검증 |
