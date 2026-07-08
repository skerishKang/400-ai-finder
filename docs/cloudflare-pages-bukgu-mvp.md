# 북구청 MVP 정적 시연 — Cloudflare Pages

이 문서는 `400-ai-finder` 저장소의 북구청 MVP를 Cloudflare Pages에서 단독 실행하는
**정적 시연 배포본**에 대한 설명이다.

## 성격

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

## 원본 보존

- 원본 Python MVP(`src/web/templates`, `src/web/static`)는 그대로 유지된다.
- 빌드 스크립트는 원본을 복사/주입할 뿐, 원본을 이동·삭제·대규모 재구성하지 않는다.
- 기존 `ssj-bukku` Worker는 **변경·삭제하지 않는다.**

## 빌드 산출물

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

## 로컬 빌드

```bash
python3 scripts/build_cloudflare_pages.py
```

빌드는 재현 가능하다(결정형). 출력은 `dist/cloudflare-pages/` 에 생성된다.

## Cloudflare Pages 설정

Cloudflare Pages 콘솔에서 다음과 같이 설정한다.

| 항목 | 값 |
| --- | --- |
| Project name | `cgbukku` |
| Production branch | `main` |
| Framework preset | `None` |
| Build command | `python3 scripts/build_cloudflare_pages.py` |
| Build output directory | `dist/cloudflare-pages` |
| Root directory | _(비움)_ |
| Environment variables | _(비움)_ |

> 빌드 산출물(`dist/cloudflare-pages`)은 Git에 추적되지 않으므로,
> Cloudflare Pages 빌드 단계에서 위 Build command 가 산출물을 직접 생성한다.

## 금지 사항 (준수)

- `wrangler.toml` / `wrangler.jsonc` / Worker 코드 추가 금지
- API Key, 실제 외부 API 호출 금지
- 실제 북구청 사이트·LLM provider·Firecrawl·requests fetch 등 live/network 호출 금지
- `ssj-bukku` Worker 변경·삭제 금지
- 원본 `src/web/templates`, `src/web/static` 이동·삭제·재구성 금지

## Production Verification Checklist (read-only)

Cloudflare Pages dashboard에서 read-only로만 확인합니다. 설정 변경·재배포·secret 열람은 하지 않습니다.

### 1. Deployment 상태 확인

- Cloudflare Pages dashboard → `cgbukku` 프로젝트 → **Deployments** 탭
- Latest production deployment의 **status / SHA / time**을 확인
- SHA가 `origin/main` (`786b38e99a3b2b8aef878337e09d933609e5fbcc`) 또는 해당 PR merge commit과 일치하는지 비교

### 2. public URL 확인

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

### 3. public URL만으로 deployed SHA 확정 불가

public 정적 HTML은 빌드 커밋 SHA를 노출하지 않습니다. 정확한 SHA는 Cloudflare dashboard의 deployment metadata에서만 확인할 수 있습니다.

## Boundaries

- 이 배포는 **백엔드 없는 결정형 정적 시연**입니다. 실제 AI/LLM/외부API/Firecrawl/live-site crawling과 완전히 별개입니다.
- **Retry deployment / Redeploy / Create deployment 클릭 금지**
- **secrets / env 열람 금지**
- **live provider / API / Firecrawl 테스트 금지**
- `ssj-bukku` Worker 변경·삭제 금지
- 원본 `src/web/templates`, `src/web/static` 이동·삭제·재구성 금지
- `dist/cloudflare-pages` Git 커밋 금지 (.gitignore로 추적 제외)
