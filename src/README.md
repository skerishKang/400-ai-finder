# src

AI파인더의 실제 구현 코드가 들어 있는 폴더입니다.

## 구조

- `answer/` — `AnswerComposer` 기반 근거 기반 답변 생성
- `crawler/` — URL 수집, sitemap, homepage map, crawl path filter
- `demo/` — 데모 runner, snapshot helper, metadata helper
- `diagnostics/` — 사이트 진단 도구
- `fetch/` — fetch provider 추상화: mock, requests, firecrawl
- `indexer/` — 문서 index 생성/보강
- `llm/` — LLM provider 추상화, model presets
- `pipeline/` — 전체 pipeline runner, smoke reporter
- `search/` — keyword search, query rewrite, source match guard
- `site_profiles/` — 사이트 profile loader/schema
- `strategy/` — fallback/strategy router
- `web/` — 모바일 UI, 운영자 대시보드, 정적 파일 서버
  - `static/mobile/` — 모바일 ChatGPT형 UI CSS/JS
  - `static/admin/` — 운영자 대시보드 CSS/JS
  - `templates/` — HTML templates

## 주요 안전 장치

- `crawl_path_filter.py`는 crawl budget 보호를 위한 pure URL filter입니다.
- `source_match_guard.py`는 검색 결과가 질문과 약하게 매칭될 때 no-results/warn으로 낮춥니다.
- `answer_composer.py`는 source context 외 URL이 답변에 포함되는지 사후 검증합니다.
- `static_server.py`는 `..` 기반 정적 파일 경로 탈출을 `commonpath()`로 차단합니다.
- 모바일/관리자 UI의 외부 링크는 `safeUrl()`과 `noopener noreferrer`로 안전하게 렌더링합니다.

## 테스트

```bash
PYTHONPATH=. python -m pytest tests/ -q
```

API 키 없이 실행하려면 `mock` 또는 `stub` provider를 사용하세요.
