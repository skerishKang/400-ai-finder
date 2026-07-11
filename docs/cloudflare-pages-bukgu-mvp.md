# 북구청 MVP — Cloudflare Pages (정적 시연 + Live LLM 이중 모드)

> **Clone invariant:** 좌측 시민 사이트의 공식 페이지 clone은 [canonical invariant](product/exact-official-site-clone-invariant.md)를 따른다. 이 Cloudflare Pages 문서의 내용은 exact-clone 계약을 약화하지 않는다. Live retrieval이나 분석은 canonical fixture 기반 왼쪽 화면을 대체하지 않는다.

이 문서는 `400-ai-finder` 저장소의 북구청 MVP를 Cloudflare Pages에서 실행하는
**두 가지 모드(정적 시연 / Live LLM)** 에 대한 설명이다.

---

## 1. 정적 시연 모드 (명시적 fallback)

`--mode static`으로 빌드한 `/mvp/` 경로는 네트워크 없는 **정적 fallback**으로 동작한다.

### 성격

- 이 배포본은 **북구청 스냅샷 기반 정적 시연본**이며, **실제 공공서비스 운영본이 아니다.**
- 모든 답변/메뉴 안내는 빌드 시점에 고정된 북구청 스냅샷
  (`tests/fixtures/bukgu_gwangju_demo_snapshot.json`)에서 결정론적으로 생성된다.
- 빌드 및 런타임에 **외부 LLM / 외부 API / 크롤링 / Firecrawl / live fetch / API Key 를
  일절 사용하지 않는다.** 네트워크 호출이 발생하지 않는다.
- `static-api-shim.js` 는 `/api/ask`, `/api/test`, `/api/info` 세 가지만 가로채고,
  그 외 모든 `fetch()` 는 즉시 `Promise.reject(new Error("Static demo: network disabled"))`
  로 차단한다 (네이티브 fetch 위임 `_nativeFetch` 없음). "네트워크 호출 없음" 문구와 실제
  동작이 일치한다.
- 질문 범위 정직성: 빌드 시점 스냅샷 질문과 정규화 후 정확히 일치하는 질문에만 스냅샷 답변을
  반환한다. 범위를 벗어난 질문에는 "정적 시연본은 북구청 스냅샷 기반의 제한된 안내 흐름"
  안내(bounded-demo 응답, 빈 sources/search_results)를 반환하여 같은 답변으로 가장하지
  않는다.
- `mobile.html` 의 Jinja `{{site_name}}` 토큰은 빌드 시점에 현재 기관명(**전남광주통합특별시 북구**)으로 정적 치환되며,
  결과물에 `{{site_name}}` 가 남지 않는다.
- 운영자 화면은 **북구청 단일 정적 시연본**으로 고정된다. 프로필 목록은 `bukgu_gwangju`
  하나만 노출되고, 모델 프리셋 선택은 비활성화되어 "Snapshot 데모 · 모델 전환 없음"으로
  표기된다.
- `404.html` 이 생성되어, 존재하지 않는 페이지에서도 외부 호출 없이 시연 홈으로 돌아갈 수 있다.

### 원본 보존

- 원본 Python MVP(`src/web/templates`, `src/web/static`)는 그대로 유지된다.
- 빌드 스크립트는 원본을 복사/주입할 뿐, 원본을 이동·삭제·대규모 재구성하지 않는다.
- 기존 `ssj-bukku` Worker는 **변경·삭제하지 않는다.**

### 빌드 산출물

- `dist/cloudflare-pages` 는 빌드 산출물이며 **Git에 커밋하지 않는다**
  (`.gitignore` 의 `dist/` 규칙 참조).
- 생성물 구성:
  - `index.html` — 정적 랜딩 페이지
  - `mobile.html` — 모바일 챗 데모 (원본 `mobile_demo.html` 기반, `{{site_name}}` 정적 치환)
  - `admin.html` — 운영자 화면 (원본 `admin_demo.html` 기반, 북구청 고정 · 모델 프리셋 비활성화)
  - `404.html` — 정적 오류 페이지 (외부 호출 없음, 시연 홈 복귀)
  - `static/` — 원본 `src/web/static` 의 사본 (이미지·CSS·JS)
  - `snapshot-data.js` — 빌드 시점에 인라인된 북구청 스냅샷 + 단일 프로필
  - `static-api-shim.js` — 백엔드 없는 결정형 `/api/*` 응답 shim (비 /api 는 즉시 차단)

### 로컬 빌드

```bash
python3 scripts/build_cloudflare_pages.py --mode static
```

빌드는 재현 가능하다(결정형). 출력은 `dist/cloudflare-pages/` 에 생성된다.

---

## 2. Live LLM 모드 (MVP Mode)

기본 배포는 `functions/api/mvp/ask.js` Cloudflare Pages Function에서 **Gemini를 1차,
HY3를 2차 폴백**으로 사용한다. 공급자 선택은 운영자 환경변수로만 제어하며 주민에게
모델 선택이나 비밀키를 노출하지 않는다.

### 활성화 조건

- Cloudflare Pages에 `GEMINI_API_KEY` 또는 `KILOCODE_API_KEY` 중 하나 이상이 설정되어야 한다.
- 기본 순서는 `MVP_LLM_ORDER=gemini,hy3`이다. 첫 공급자가 키 누락, HTTP 오류, 빈 응답이면 다음 공급자를 시도한다.
- 프론트엔드에서 `/api/mvp/ask`로 POST 요청을 보내면 Function이 동작한다.
- 정적 시연과 달리 **네트워크 호출이 발생**한다.

### API contract

**Endpoint:** `POST /api/mvp/ask`

**Request:**
```json
{
  "question": "불법주차 신고하려면 어디에 전화하나요?"
}
```

**Success Response (200):**
```json
{
  "ok": true,
  "question": "불법주차 신고하려면 어디에 전화하나요?",
  "answer": "북구청 교통과...",
  "action": "illegal_parking",
  "confidence": 0.95,
  "provider": "gemini",
  "model": "gemini-3.1-flash-lite",
  "failure_code": "",
  "retrieved_at": "2026-07-11T04:15:00.000Z",
  "freshness_state": "live_official",
  "source_url": "https://search.bukgu.gwangju.kr/RSA/front/Search.jsp?qt=...",
  "sources": [
    {
      "title": "북구청 통합검색: 불법 주정차 신고",
      "url": "https://search.bukgu.gwangju.kr/RSA/front/Search.jsp?qt=...",
      "official": true
    }
  ],
  "search_queries": ["북구청 불법주차 신고"],
  "captured_at": "",
  "verified_at": "",
  "official_route_id": "",
  "official_page_id": "",
  "snapshot_id": "",
  "canonical_sha256": "",
  "fallback_used": false
}
```

공동주택 담당부서 질문은 요청 시 외부 조회 대신 검증·커밋된
`apartment-dept` 공식 스냅샷을 사용한다. 이 경우 `freshness_state`는
`official_snapshot`이고 `captured_at`, `verified_at`, `official_route_id`,
`official_page_id`, `snapshot_id`, `canonical_sha256`로 출처와 생성물 일치 여부를
추적한다.

그 밖의 질문은 모델 호출 전에 북구청 공식 홈페이지와 통합검색 결과를 서버에서
병렬 조회한다. HTML의 실행 가능 요소를 제거하고 길이를 제한한 공식 근거를 Gemini와
HY3에 공통 주입하며, 조회에 성공한 경우에만 `live_official`과 실제 조회 URL을
반환한다. 공식 사이트 조회가 실패해도 모델 공급자 호출은 계속하되 `model_only`, 빈
`sources`로 표시한다. Gemini Interactions 모드는 서버 조회 근거와 Google Search 인용을
함께 보존하며, 공식 도메인 근거가 없고 일반 웹 인용만 있는 경우에는 `live_web`을
사용할 수 있다.

**Validation rules:**
| 항목 | 조건 | 실패 시 |
|---|---|---|
| `question` | 필수, 문자열, 300자 이내 | `invalid_input` (status 200, `ok: false`) 또는 400 |
| `action` | 서버의 7개 시연 규칙으로 결정 | 그 밖의 질문은 `'none'` |
| `answer` | 선택된 공급자의 비어 있지 않은 답변 | 빈 응답이면 다음 공급자 시도 후 fail-closed |
| 최신성 메타데이터 | `retrieved_at`, `freshness_state`, `source_url`, `sources`; 스냅샷이면 capture/verify/route/page/snapshot/checksum 필드 | 근거가 없으면 `model_only` 또는 `unavailable` |
| 공급자 메타데이터 | `provider`, `model`, `fallback_used` | 키와 원시 오류는 절대 응답하지 않음 |
| CORS | production/preview `cgbukku.pages.dev`와 localhost allowlist + `Vary: Origin` | |

### 실패 모드

| 상황 | HTTP status | `ok` | `failure_code` |
|---|---|---|---|
| 질문 없음 | 400 | false | — |
| 질문 300자 초과 | 200 | false | `invalid_input` |
| 모든 API key 미설정 | 200 | false | `config_error` |
| 모든 설정 공급자의 HTTP 오류 | 200 | false | `upstream_error` |
| 마지막 공급자의 빈/비정상 응답 | 200 | false | `empty_response` 또는 `malformed_response` |

> 모든 실패 응답은 **status 200**으로 반환되어 MVP 정적 shim과의 contract 일관성을 유지한다.
> 단, 질문 누락(400)과 Method Not Allowed(405)는 예외.

### 환경 변수 / Secrets

| 변수 | 설명 | 설정 위치 |
|---|---|---|
| `MVP_LLM_ORDER` | 공급자 우선순위, 기본 `gemini,hy3` | Cloudflare Pages → Variables |
| `GEMINI_API_KEY` | Gemini 인증 키 | Cloudflare Pages → Secrets |
| `KILOCODE_API_KEY` | KiloCode HY3 인증 키 | Cloudflare Pages → Secrets |
| `GEMINI_MODEL` | 기본 `gemini-3.1-flash-lite` | Cloudflare Pages → Variables |
| `GEMINI_API_STYLE` | 기본 `openai`, 선택값 `interactions` | Cloudflare Pages → Variables |
| `GEMINI_API_ENDPOINT` | Gemini endpoint override | Cloudflare Pages → Variables |
| `HY3_MODEL` | 기본 `tencent/hy3:free` | Cloudflare Pages → Variables |
| `HY3_API_ENDPOINT` | HY3 endpoint override | Cloudflare Pages → Variables |

실제 키는 `.env.example`에 값을 적지 않고 Cloudflare secret으로만 저장한다.

### 호출 제한 관련 주의사항

- Cloudflare Pages Functions와 Gemini API의 현재 요청 한도·비용은 배포 시점의 공식 요금제와 quota 문서를 확인한다.
- 과도한 호출 방지를 위해 클라이언트 측에서 디바운스(예: 1초 간격) 적용을 권장.
- 구체적인 비용 및 rate limit 수치는 Gemini API 공식 문서와 Cloudflare Pages 요금제를 직접 확인해야 한다.

---

## 3. Cloudflare Pages 설정

Cloudflare Pages 콘솔에서 다음과 같이 설정한다.

| 항목 | 값 |
|---|---|
| Project name | `cgbukku` |
| Production branch | `main` |
| Framework preset | `None` |
| Build command | `python3 scripts/build_cloudflare_pages.py` |
| Build output directory | `dist/cloudflare-pages` |
| Root directory | _(비움)_ |
| Environment variables | `MVP_LLM_ORDER=gemini,hy3`, `GEMINI_API_KEY`, `KILOCODE_API_KEY` |

> 빌드 산출물(`dist/cloudflare-pages`)은 Git에 추적되지 않으므로,
> Cloudflare Pages 빌드 단계에서 위 Build command 가 산출물을 직접 생성한다.

---

## 4. 배포 운영 경계 (운영자 전용)

배포 파이프라인의 무결성을 보호하기 위한 경계입니다. 일반 개발·검증 작업은 로컬 정적 아티팩트로 수행하며 배포 제어는 운영자 책임입니다.

- `wrangler.toml` / `wrangler.jsonc` / Worker 코드: 이 정적 Pages 배포에서는 추가하지 않습니다 (프레임워크 preset `None`, 빌드 명령만 사용). Pages Function(`/api/mvp/ask`)은 Functions 자동 배포로 동작합니다.
- 원본 `src/web/templates`, `src/web/static` 이동·삭제·재구조화는 배포 산출물 정합성을 위해 피합니다.
- `ssj-bukku` Worker 변경·삭제는 운영 승인 하에만 진행합니다.
- 실제 외부 API Key는 소스코드·설정에 하드코딩하지 않습니다 (`.env` + `.gitignore` 방식, Cloudflare Pages Secrets 사용).
- 북구청 공식 사이트 참고·크롤링·스크린샷 비교, Firecrawl·외부 API·live provider reference 수집은 현재 제품 방향에서 허용되는 참고·수집 작업입니다. live-dependent 실험 실행은 별도 operational stage(명시적 opt-in + 자격 증명)로 분리되어 있습니다.
- **Live LLM 모드** 사용 시 Gemini API 호출이 발생합니다. 개발·테스트 목적으로만 사용하고, 프로덕션 트래픽은 별도 승인을 받으세요.

---

## 5. Production Verification Checklist (read-only)

Cloudflare Pages dashboard는 read-only로 확인하는 것을 권장합니다. 설정 변경·재배포는 배포 권한 보유 운영자만 수행하며, secrets/env는 해당 운영자 책임 하에 다룹니다.

### 5.1. Deployment 상태 확인

- Cloudflare Pages dashboard → `cgbukku` 프로젝트 → **Deployments** 탭
- Latest production deployment의 **status / SHA / time**을 확인
- SHA가 `origin/main` (`786b38e99a3b2b8aef878337e09d933609e5fbcc`) 또는 해당 PR merge commit과 일치하는지 비교

### 5.2. public URL 확인

```bash
curl -sI https://cgbukku.pages.dev/       # HTTP 200
curl -sI https://cgbukku.pages.dev/mvp/   # HTTP 200
curl -sI https://cgbukku.pages.dev/mobile  # HTTP 200 (from /mobile.html 308)
curl -sI https://cgbukku.pages.dev/admin   # HTTP 200 (from /admin.html 308)
```

각 경로의 `<title>` 태그로 올바른 아티팩트인지 확인:

| 경로 | title |
|---|---|
| `/` | `400 AI 파인더 — 정적 시연 (Cloudflare Pages)` |
| `/mvp/` | `시민 행정 도우미 — 로컬 시연용` |
| `/mobile` | `400 AI 파인더` |
| `/admin` | `운영자 화면 — AI 홈페이지 파인더` |

### 5.3. Live LLM 모드 확인

```bash
# GEMINI_API_KEY 또는 KILOCODE_API_KEY가 설정된 배포에서 동작
curl -s -X POST https://cgbukku.pages.dev/api/mvp/ask \
  -H 'Content-Type: application/json' \
  -d '{"question":"불법주차 신고하려면?"}' | jq .
```

- 응답에 `ok: true`, `answer` (비어 있지 않음), `action`, `confidence`가 포함되어야 함.
- Gemini 응답 실패 시 HY3가 설정되어 있으면 `provider: "hy3"`, `fallback_used: true`로 응답.
- 두 키가 모두 없으면 `ok: false`, `failure_code: "config_error"` 응답.

### 5.4. public URL만으로 deployed SHA 확정 불가

public 정적 HTML은 빌드 커밋 SHA를 노출하지 않습니다. 정확한 SHA는 Cloudflare Pages deployment metadata에서 확인하세요.

---

## 6. 현재 정적 아티팩트 vs 의도된 제품 아키텍처

이 문서는 **현재 정적 배포본**(빌드 시점 스냅샷, LLM/API/network 없음)과
**Live LLM 모드**(Cloudflare Pages Function + Gemini/HY3 공급자 체인)를 함께 설명한다.
범위를 벗어난 질문에 대해 "정적 시연본은 … 제한된 안내 흐름" 응답(bounded-demo)을
반환하는 것은 **현재 배포 제약**이며, 최종 제품 의도가 아니다. 의도된 제품은
정해지지 않은 자연어 질문에 대해 **LLM fallback**으로 답하고 가능하면 known
resident-task flow로 연결한다. 상세는
[`docs/hybrid-scripted-llm-architecture-intent.md`](hybrid-scripted-llm-architecture-intent.md) 참고.
이 정적 아티팩트가 LLM/API/network를 쓰지 않는다는 사실은 유지되며, 그것이
제품 전체를 local/static-only로 고정하는 뜻으로 읽혀서는 안 된다. 현재의 exact/static/
bounded-demo 매칭 동작은 **현재 배포 제약**이고, 의도된 routing model은
**LLM intent router + fallback**이다. 상세는
[`docs/hybrid-scripted-llm-architecture-intent.md`](hybrid-scripted-llm-architecture-intent.md)
의 "Question entry and routing model" 섹션 참고.

## Boundaries

- 배포 CLI 기본값은 Live LLM 모드이며, `--mode static`에서만 백엔드 없는 결정형 시연을 만든다. Live 응답에는 `GEMINI_API_KEY` 또는 `KILOCODE_API_KEY`가 필요하다.
- 기본 검증 흐름은 로컬 정적 아티팩트만으로 충분하다.
- 배포 제어(Retry deployment / Redeploy / Create deployment)는 배포 권한 보유 운영자 전용이며, secrets/env는 해당 운영자 책임 하에 다룹니다.
- live-dependent 실험 경로(Firecrawl/외부 API/live provider 호출)는 별도 operational stage로 분리되어 있으며, 명시적 opt-in과 자격 증명(env) 설정 하에 실행됩니다. 자세한 경계는 [`provider-fetch-network-boundary.md`](provider-fetch-network-boundary.md)를 참고하세요.
- `dist/cloudflare-pages`는 `.gitignore`로 추적 제외되어 Git에 커밋하지 않습니다 (빌드 산출물).
