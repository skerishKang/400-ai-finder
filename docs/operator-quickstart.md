# Operator Quickstart

운영자가 400-ai-finder를 안전하게 실행하고 smoke 평가를 수행하기 위한 빠른 안내서입니다.

---

## 1. Start with safe offline paths

**기본 원칙:** 로컬 확인 시에는 항상 mock/offline 경로를 먼저 사용하십시오.
Live provider, fetch provider, Firecrawl, 외부 API 호출을 수행하지 않으며 API 키가 필요하지 않습니다.

### 데모 실행 (Snapshot 모드)

```bash
PYTHONPATH=. .venv/bin/python scripts/run_all_demos.py \
    --site-id bukgu_gwangju \
    --snapshot tests/fixtures/bukgu_gwangju_demo_snapshot.json
```

`--snapshot`을 사용하면 외부 네트워크 및 API 호출 없이 시연이 가능합니다.
`--provider`를 생략하면 기본 DeepSeek 프리셋이 적용되지만, snapshot 모드에서는 LLM 호출이 필요하지 않습니다.

### 개별 화면 실행

```bash
# 모바일 화면만
PYTHONPATH=. .venv/bin/python scripts/run_mobile_demo.py \
    --site-id bukgu_gwangju \
    --snapshot tests/fixtures/bukgu_gwangju_demo_snapshot.json

# 운영자 대시보드만
PYTHONPATH=. .venv/bin/python scripts/run_admin_demo.py \
    --site-id bukgu_gwangju \
    --snapshot tests/fixtures/bukgu_gwangju_demo_snapshot.json
```

### 질문-답변 데모 (Offline)

```bash
PYTHONPATH=. .venv/bin/python scripts/demo_answer.py \
    --site-id bukgu_gwangju \
    --question "민원서식 어디서 받아?" \
    --provider stub \
    --snapshot tests/fixtures/bukgu_gwangju_demo_snapshot.json
```

`--provider stub`은 API 키 없이 source context를 기반으로 현실적인 답변을 생성합니다.
`--snapshot`을 함께 사용하면 모든 데이터가 로컬 fixture에서 제공됩니다.

---

## 2. Run smoke evaluation with fixtures

Fixture 기반 smoke eval은 외부 네트워크, live provider, Firecrawl, 실제 pipeline 호출 없이 실행됩니다.

### Schema-only 검증

```bash
PYTHONPATH=. .venv/bin/python scripts/run_smoke_eval.py
```

기본 matrix (`tests/fixtures/smoke_scenario_matrix.json`)를 검증합니다.

### Response fixture 평가

```bash
PYTHONPATH=. .venv/bin/python scripts/run_smoke_eval.py \
    --responses tests/fixtures/smoke_eval_responses.json
```

미리 준비된 response fixture로 judge를 실행합니다.
기존 pipeline/demo 결과, mock live smoke response, 또는 live smoke artifact 등도 평가할 수 있습니다.

### Mock response 빌드 및 평가

```bash
# 빌드만
PYTHONPATH=. .venv/bin/python scripts/build_mock_live_smoke_responses.py \
    --output /tmp/mock_responses.json

# 빌드 후 즉시 평가
PYTHONPATH=. .venv/bin/python scripts/build_mock_live_smoke_responses.py --eval
```

Mock response builder는 실제 provider/fetch/network 호출 없이, 시나리오별 expected domain/keywords/fallback 기준만 사용해 오프라인 평가용 fixture를 생성합니다.

### Live preflight 확인

```bash
PYTHONPATH=. .venv/bin/python scripts/run_smoke_eval.py --live-preflight
```

Live smoke eval을 위한 구성이 준비되었는지 점검합니다.
이 명령은 실제 live provider/fetch/network/pipeline 호출을 수행하지 않습니다.

> 자세한 smoke eval 흐름은 `docs/smoke-eval-flow.md`를 참고하십시오.

---

## 3. Use live providers intentionally

Live fetch provider (예: `requests`, `firecrawl`)를 사용하는 명령은 **명시적 opt-in**이 필요합니다.

### `--allow-live`가 필요한 스크립트

다음 스크립트에서 live fetch provider를 사용하려면 `--allow-live`를 추가하십시오:

| 스크립트 | live fetch 예제 |
|----------|----------------|
| `scripts/demo_answer.py` | `--fetch-provider requests --allow-live` |
| `scripts/run_pipeline.py` | `--fetch-provider requests --allow-live` |

```bash
# Live fetch 예제 (opt-in 필요)
PYTHONPATH=. .venv/bin/python scripts/demo_answer.py \
    --site-id gwangju_go_kr \
    --question "고시공고는 어디서 봐?" \
    --provider stub \
    --fetch-provider requests --allow-live
```

### `--allow-live`가 필요하지 않은 스크립트

다음 스크립트는 `--url`이 필수이므로 명시적 사용자 의도가 이미 확인됩니다:

| 스크립트 | 정책 |
|----------|------|
| `scripts/fetch_url.py` | `--url` required = 명시적 의도 |
| `scripts/diagnose_site.py` | `--url` required = 명시적 의도 |

```bash
# `--url` required → --allow-live 불필요
PYTHONPATH=. .venv/bin/python scripts/fetch_url.py --url "https://example.com"
```

### 데모 서버 실행 시 live fetch

```bash
PYTHONPATH=. .venv/bin/python scripts/run_all_demos.py \
    --site-id gwangju_go_kr \
    --provider stub \
    --fetch-provider requests
```

데모 서버(`run_all_demos.py`, `run_mobile_demo.py`, `run_admin_demo.py`)는 live fetch가 브라우저 UI 액션 후 user-triggered이므로 `--allow-live`가 필요하지 않습니다.

---

## 4. Use live smoke eval (opt-in only)

Live smoke eval은 기본적으로 실행되지 않습니다.
실행하려면 두 가지 조건이 모두 필요합니다:

1. 환경 변수 `RUN_LIVE_SMOKE_EVAL=true` 설정
2. 필요한 API 키/시크릿 설정

```bash
RUN_LIVE_SMOKE_EVAL=true PYTHONPATH=. .venv/bin/python scripts/run_smoke_eval.py --live
```

`--live` 플래그만으로는 실행되지 않습니다.
환경 변수가 없으면 `SmokeLiveEvalGuardError`가 발생합니다.

다른 live-only 테스트도 동일한 정책을 따릅니다:

| 환경 변수 | 대상 |
|-----------|------|
| `RUN_LIVE_SMOKE_EVAL=true` | `scripts/run_smoke_eval.py --live` |
| `RUN_LIVE_FETCH_TESTS=1` | fetch 관련 live 테스트 |
| `RUN_LIVE_PROVIDER_TESTS=1` | provider 관련 live 테스트 |

> 자세한 정책은 `docs/provider-fetch-network-boundary.md`를 참고하십시오.

---

## 5. Understand result output

### Smoke eval 결과

```text
--- Response Judge Report ---
Passed: 12/14 (85.7%)
Failed: 2/14 (14.3%)

Failed scenarios:
- scenario-id-01: site_id mismatch
- scenario-id-02: expected_keywords not found
```

- Pass/Fail 여부는 scenario matrix의 `pass_criteria`에 따라 결정됩니다.
- `--responses`로 평가하면 scenario별 상세 결과가 출력됩니다.
- 실패한 시나리오는 구체적인 이유와 함께 표시됩니다.

### Smoke eval 결과 (Live preflight)

```text
Live smoke eval preflight
Guard check: ready
Live provider config: ready
Fetch provider config: ready
No live provider, fetch, network, or pipeline calls were made.
```

---

## 6. Live site validation notes

Live LLM + live fetch validation (e.g., `demo_answer.py --allow-live --provider nvidia --fetch-provider requests`) can produce useful grounded answers overall, but operators should be aware of the following:

### WARN vs FAIL

- A WARN result does not automatically mean a provider or fetch failure.
- Some municipal websites use menu labels, board names, or legacy URL structures that do not match the user's natural-language query.
- Topics like youth/jobs, employment, welfare, or education may require **alternative Korean keywords** beyond the initial query.

### Keyword guidance

If a live query returns few or no results, try these alternative terms:

```
청년 / 일자리 / 채용 / 취업 / 고용 / 경제 / 기업지원
비즈광주북구 / 정보화교육 / 복지 / 민원 / 고시공고 / 공지사항
```

### Domain grounding check

After receiving an answer, verify that:

- The cited URLs belong to the target site's **official domain** (e.g., `bukgu.gwangju.kr` for Buk-gu).
- Any external official domains (e.g., `workplus.go.kr`) are **contextually relevant** to the question — they are not automatically errors, but operators should confirm alignment.

### Example from Buk-gu validation (Stage 333)

In the Buk-gu (`bukgu_gwangju`) live validation:

| Topic | Result | Note |
|-------|--------|------|
| Notice/announcement (공지사항/고시공고) | PASS | Specific menu URLs provided |
| Welfare programs (복지 지원사업) | PASS | Majority of sources on target domain |
| Civil services (민원 신청) | PASS | All sources on target domain |
| Youth/jobs (청년/일자리) | **WARN** | Relevant pages not reliably discovered with initial query terms |
| Domain correctness | PASS | All cited sources confirmed on target domain |

The youth/jobs WARN occurred because the relevant menu pages (e.g., 비즈광주북구, 정보화교육) use different labeling than the natural-language query "청년" or "일자리". This is a **search coverage limitation**, not a pipeline or provider failure.

### Key takeaway

**Try alternate official menu terms** when a live query does not surface the expected page. The pipeline is designed to discover content based on available crawlable pages and text matching — not all content may be surfaced from every query on the first attempt.

---

## 7. Safety checklist

- [ ] **API 키/시크릿을 코드에 하드코딩하지 마십시오.** `.env` 파일을 사용하고 `.gitignore`에 추가하십시오.
- [ ] **로컬 확인 시 mock/stub 프로바이더를 사용하십시오.** 두 프로바이더 모두 API 키가 필요하지 않습니다.
- [ ] **Live provider 사용 시 `--allow-live`를 명시적으로 추가하십시오.** 실수로 live 호출이 발생하는 것을 방지합니다.
- [ ] **`RUN_LIVE_*_TESTS=1`은 의도적으로 live 테스트를 실행할 때만 설정하십시오.** 기본값으로 설정하지 마십시오.
- [ ] **Firecrawl 사용 시 API 키 설정을 확인하십시오.** 기본 경로가 아닙니다.
- [ ] **README 예제를 그대로 실행하기 전에 safe/offline 여부를 확인하십시오.** Live fetch 예제는 `--allow-live`가 필요합니다.
- [ ] **전체 pytest를 실행하기 전에 live-only 테스트가 skip되는지 확인하십시오.** 기본적으로 `741 passed, 4 skipped`가 예상됩니다.

---

## Operator decision tree

```
처음 실행 / 안전 확인
    │
    ├── 데모 / 시연 → Snapshot 모드 (--snapshot)
    │
    ├── 질문-답변 확인 → --provider stub + --snapshot
    │
    ├── Smoke eval
    │   ├── Schema 검증 → run_smoke_eval.py (기본)
    │   ├── Response 평가 → --responses <fixture>
    │   └── Mock 빌드+평가 → build_mock_live_smoke_responses.py --eval
    │
    ├── Live provider 확인
    │   ├── Fetch 필요 → --fetch-provider requests --allow-live
    │   ├── Live smoke → RUN_LIVE_SMOKE_EVAL=true + --live
    │   ├── 질문-답변 검증 → --provider nvidia --fetch-provider requests --allow-live
    │   └── WARN 결과 해석 → docs/operator-quickstart.md §6 Live site validation notes 참고
    │
    └── 문제 발생
        ├── 에러 메시지 확인
        ├── docs/provider-fetch-network-boundary.md 확인
        └── docs/smoke-eval-flow.md 확인
```

---

## 관련 문서

| 문서 | 설명 |
|------|------|
| `README.md` | 프로젝트 개요, 전체 기능 설명, 데모 실행 예제 |
| `docs/smoke-eval-flow.md` | Smoke eval CLI 흐름 상세 |
| `docs/provider-fetch-network-boundary.md` | Live provider/fetch/network 경계 정책 |
| `docs/smoke-scenario-matrix.md` | Scenario matrix 스키마 및 검증 정책 |
