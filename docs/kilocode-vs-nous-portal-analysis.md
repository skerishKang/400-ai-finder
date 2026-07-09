# KiloCode hy3:free vs Nous Portal hy3:free — 비교 분석 및 전환 추천 보고서

> 분석 일자: 2026-07-10
> 대상: cgbukku.pages.dev (Cloudflare Pages MVP) — functions/api/mvp/ask.js
> 컨텍스트: 현재 `--mode static` (스냅샷 기반, LLM 미사용). LLM 활성화 시(`--mode live`) 적용될 정책 분석.

---

## 1. Rate Limit 비교

| 항목 | KiloCode hy3:free | Nous Portal hy3:free (Free tier) |
|---|---|---|
| **Rate limit** | **200 req/hour** per IP | **50 RPM** (3,000 req/hour) per API key |
| **Token limit** | 명시된 토큰 제한 없음 | **500,000 TPM** (tokens per minute) |
| **제한 범위** | IP 주소 기반 | API 키 기반 |
| **Burst 처리** | 200 req/hour = 평균 3.33 req/min | 50 RPM = 순간 폭주 50 req/min |
| **초과 시** | HTTP 429 (Rate limit exceeded) | HTTP 429 (x-ratelimit-* 헤더 상세) |
| **OpenRouter 레이어** | 없음 (KiloCode 자체 게이트웨이) | 있음 (Nous Portal → OpenRouter → hy3 provider) |

### 정량 비교

| 지표 | KiloCode | Nous Portal | 배수 |
|---|---|---|---|
| 시간당 최대 요청 | 200 | **3,000** | **15x** |
| 분당 최대 요청 | 3.33 | **50** | **15x** |
| 토큰 기반 제한 | 없음 | 500K TPM | N/A |

> **Nous Portal이 분당/시간당 모두 15배 더 높은 처리량을 제공함.**

---

## 2. cgbukku.pages.dev 사용 시나리오별 소진 추정

현재 `cgbukku.pages.dev`는 `--mode static`(스냅샷 기반 정적 시연, LLM 호출 없음)으로 배포됨.  
LLM 활성화(`--mode live`) 시나리오에서 분석:

### 시나리오 A — 경량 MVP (북구청 직원 내부 테스트)

| 항목 | 값 |
|---|---|
| 일일 사용자 | 10~20명 |
| 1인당 질문 | 1~2회 |
| 일일 총 요청 | 10~40회 |
| **KiloCode (200 req/h)** | ✅ **여유** (1일 총량이 1시간 제한의 20%) |
| **Nous Portal (50 RPM)** | ✅ **매우 여유** (1분이면 처리 가능) |

### 시나리오 B — 중간 규모 (북구청 주민 대상 파일럿)

| 항목 | 값 |
|---|---|
| 일일 사용자 | 30~50명 |
| 1인당 질문 | 3~5회 |
| 일일 총 요청 | 90~250회 |
| **KiloCode (200 req/h)** | ⚠️ **위험** — 250회/일 = 10.4회/h 평균이지만, **9시 집중(50명×3회=150회/첫1시간)** 시 200 한도 근접. 2시간 연속 집중 시 초과 |
| **Nous Portal (50 RPM)** | ✅ **여유** (250회/일 = 0.17 RPM, 50 RPM의 0.35%) |

### 시나리오 C — 대규모 (본격 서비스)

| 항목 | 값 |
|---|---|
| 일일 사용자 | 100~300명 |
| 1인당 질문 | 5~10회 |
| 일일 총 요청 | 500~3,000회 |
| **KiloCode (200 req/h)** | ❌ **병목** — 500회/일 = 20.8회/h 평균이지만, **출근 시간 1시간에 200회 초과 가능** (예: 50명×4회 = 200회). 300명×2회(첫1시간) = 600회 → **완전 소진 후 429 폭탄** |
| **Nous Portal (50 RPM)** | ✅ **여유** — 3,000회/일 = 2.1 RPM 평균 (50 RPM의 4.2%). 시간당 3,000회 한도이므로 **일일 3만회까지도 문제없음** |

> **결론:** 경량 MVP(시나리오 A)는 KiloCode 200 req/h로 충분.  
> 중간 규모 이상(시나리오 B/C)에서는 Nous Portal 전환이 사실상 필수.

---

## 3. 설정 복잡도 비교

| 항목 | KiloCode hy3:free | Nous Portal hy3:free |
|---|---|---|
| **API 키 발급** | KiloCode 가입 → API key 발급 | Nous Portal 가입 → Free tier → API key 발급 |
| **현재 설정** | `env.KILOCODE_API_KEY` (CF_PAGES_KILOCODE_API_KEY secrets) | 변경 필요 (`env.NOUS_API_KEY`) |
| **Base URL 변경** | `https://api.kilo.ai/api/gateway/v1/chat/completions` | `https://api.nousresearch.com/v1/chat/completions` |
| **Auth 형식** | `Authorization: Bearer ${KILOCODE_API_KEY}` | `Authorization: Bearer ${NOUS_API_KEY}` (동일) |
| **모델명** | `tencent/hy3:free` | `tencent/hy3:free` (동일, OpenRouter 경유) |
| **ask.js 수정 범위** | - | URL 1줄 + env 변수명 2줄 |
| **정적 vs 라이브** | `--mode live`로 빌드 + Pages Functions 배포 | 동일 |

### ask.js 수정 내역 (전환 시)

```js
// 변경 전 (KiloCode)
const apiKey = env.KILOCODE_API_KEY;
// ...
const response = await fetch('https://api.kilo.ai/api/gateway/v1/chat/completions', {
  headers: { 'Authorization': `Bearer ${apiKey}`, ... },
  body: JSON.stringify({ model: 'tencent/hy3:free', ... }),
});

// 변경 후 (Nous Portal)
const apiKey = env.NOUS_API_KEY;
// ...
const response = await fetch('https://api.nousresearch.com/v1/chat/completions', {
  headers: { 'Authorization': `Bearer ${apiKey}`, ... },
  body: JSON.stringify({ model: 'tencent/hy3:free', ... }),
});
```

> **설정 단순도:** 두 옵션 모두 OpenAI 호환 API로, URL과 API 키만 변경하면 됨. 복잡도는 동일 수준.

---

## 4. 비용 비교

| 비용 항목 | KiloCode hy3:free | Nous Portal hy3:free (Free tier) |
|---|---|---|
| **월 기본료** | $0 | $0 |
| **hy3:free 사용료** | $0/1M tokens (프로모션 기간) | $0/1M tokens (프로모션 기간) |
| **월 크레딧** | 별도 크레딧 없음 | $0.10/month (Free tier) |
| **프로모션 만료** | 2026-07-21 이후 $0.20/$0.80 per 1M tokens | 동일 (같은 OpenRouter 기반) |
| **추가 의존성** | KiloCode 단독 | Nous Portal + OpenRouter (2단계) |

> **비용 동일** — hy3:free 프로모션 기간 중에는 둘 다 무료.  
> 프로모션 만료(7/21) 후에는 유료 전환 불가피하며, 요율은 동일(OpenRouter 기준가 적용).

---

## 5. 장단점 분석

### KiloCode hy3:free

| 장점 | 단점 |
|---|---|
| ✅ 현재 설정 그대로 사용 가능 (변경 불필요) | ❌ 200 req/hour — 대규모 트래픽 처리 불가 |
| ✅ KiloCode 단일 게이트웨이 (레이턴시 최소화) | ❌ IP 기반 제한 — Cloudflare IP pool에서 모든 사용자가 한 버킷 공유 |
| ✅ 안정적인 KiloCode 인프라 | ❌ hy3:free 프로모션 만료 시 혜택 종료 |
| ✅ Pages Functions에서 1:1 매핑 | ❌ 토큰 기반 제한이 없어 장기 응답에서 차별 없음 |

### Nous Portal hy3:free

| 장점 | 단점 |
|---|---|
| ✅ **50 RPM / 500K TPM** — 15배 높은 처리량 | ❌ 현재 설정 변경 필요 (URL + env) |
| ✅ API 키 기반 — Cloudflare IP 제약 없음 | ❌ OpenRouter 경유 → 레이턴시 소폭 증가 가능 |
| ✅ Nous Portal 생태계 — 다른 모델로 쉽게 전환 | ❌ OpenRouter 의존성 (이중 장애 지점) |
| ✅ Free tier에 $0.10/month 크레딧 포함 | ❌ Free tier가 헤비 사용에는 부족 ($0.10 크레딧) |
| ✅ 동일한 model ID (`tencent/hy3:free`) 사용 가능 | ❌ hy3:free 프로모션 만료 시 혜택 종료 (동일) |

---

## 6. 최종 추천

### 현재 상황: `--mode static` (스냅샷, LLM 미사용)

Rate limit은 **아직 실질적 이슈가 아님** — LLM 호출이 발생하지 않음.

### `--mode live` 활성화 시 추천 순위

| 순위 | 옵션 | 추천 사유 |
|---|---|---|
| **🥇 1순위** | **KiloCode hy3:free 유지 + 사용량 모니터링** | 현재 설정 변경 불필요. 경량 MVP(200 req/h)에 충분. 429 발생 시 Nous Portal로 전환 검토 |
| **🥈 2순위** | **Nous Portal hy3:free로 전환** | 트래픽 증가(일 250회+ 또는 동시 접속 30명+) 예상 시 사전 전환. 50 RPM으로 여유로운 운영 가능 |
| **🥉 3순위** | **양쪽 모두 준비 (fallback 전략)** | KiloCode 429 시 Nous Portal로 자동 fallback. 가장 안정적이지만 설정 복잡도 증가 |

### 실행 방법 (Nous Portal 전환 시)

```bash
# 1. Nous Portal 가입 및 Free tier API 키 발급
#    https://portal.nousresearch.com → Sign Up → Create API Key

# 2. Cloudflare Pages에 secret 추가
#    대시보드 → cgbukku → Settings → Environment Variables
#    NOUS_API_KEY = <발급받은 API 키>

# 3. functions/api/mvp/ask.js 수정 (위 섹션 3 참조)

# 4. --mode live로 재배포
python3 scripts/build_cloudflare_pages.py --mode live

# 5. (선택) 이전 KILOCODE_API_KEY 환경변수는 제거하거나 유지
```

### 주의사항

| 사항 | 설명 |
|---|---|
| **⏰ hy3:free 프로모션 만료** | **2026-07-21** 이후 `tencent/hy3:free`가 유료 전환됨 ($0.20/$0.80 per 1M tokens). 이 날짜 이전에 유료 모델 전환 또는 타 모델 검토 필요 |
| **🌐 IP vs Key 제한 차이** | KiloCode는 IP 기반이므로 Cloudflare Pages Function의 공인 IP가 한 버킷을 공유. 동시 사용자 증가 시 KiloCode의 200 req/h가 더 빠르게 소진됨 |
| **📊 모니터링** | `--mode live` 전환 후 첫 주간은 429 응답률을 반드시 모니터링. 1% 이상이면 즉시 Nous Portal 전환 |

---

## 7. 요약 테이블

| 항목 | 현재 (KiloCode hy3:free) | 대안 (Nous Portal hy3:free) |
|---|---|---|
| **rate limit** | 200 req/hour per IP | 50 RPM / 500K TPM per API key (15x 여유) |
| **설정 복잡도** | 낮음 (이미 구성됨) | 낮음 (URL + env 변수명 변경만 필요) |
| **비용** | $0 (프로모션 기간) | $0 (프로모션 기간) |
| **추천** | **🥇 1순위** — 경량 MVP 유지 시 | **🥈 2순위** — 트래픽 증가 예상 시 |
| **실행 난이도** | 변경 불필요 | 하 (ask.js 3줄 + Cloudflare secret 1개) |
