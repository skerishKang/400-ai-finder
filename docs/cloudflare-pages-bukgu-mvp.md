# 북구청 MVP 정적 시연 — Cloudflare Pages

이 문서는 `400-ai-finder` 저장소의 북구청 MVP를 Cloudflare Pages에서 단독 실행하는
**정적 시연 배포본**에 대한 설명이다.

## 성격

- 이 배포본은 **북구청 스냅샷 기반 정적 시연본**이며, **실제 공공서비스 운영본이 아니다.**
- 모든 답변/메뉴 안내는 빌드 시점에 고정된 북구청 스냅샷
  (`tests/fixtures/bukgu_gwangju_demo_snapshot.json`)에서 결정론적으로 생성된다.
- 빌드 및 런타임에 **외부 LLM / 외부 API / 크롤링 / Firecrawl / live fetch / API Key 를
  일절 사용하지 않는다.** 네트워크 호출이 발생하지 않는다.

## 원본 보존

- 원본 Python MVP(`src/web/templates`, `src/web/static`)는 그대로 유지된다.
- 빌드 스크립트는 원본을 복사/주입할 뿐, 원본을 이동·삭제·대규모 재구성하지 않는다.
- 기존 `ssj-bukku` Worker는 **변경·삭제하지 않는다.**

## 빌드 산출물

- `dist/cloudflare-pages` 는 빌드 산출물이며 **Git에 커밋하지 않는다**
  (`.gitignore` 의 `dist/` 규칙 참조).
- 생성물 구성:
  - `index.html` — 정적 랜딩 페이지
  - `mobile.html` — 모바일 챗 데모 (원본 `mobile_demo.html` 기반)
  - `admin.html` — 운영자 화면 (원본 `admin_demo.html` 기반)
  - `static/` — 원본 `src/web/static` 의 사본 (이미지·CSS·JS)
  - `snapshot-data.js` — 빌드 시점에 인라인된 북구청 스냅샷
  - `static-api-shim.js` — 백엔드 없는 결정형 `/api/*` 응답 shim

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
