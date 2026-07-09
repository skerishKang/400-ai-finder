# 400-ai-finder

400-ai-finder는 복잡한 기관 홈페이지, 공공기관 홈페이지, 대학 홈페이지, 기업 지원사업 홈페이지를 사용자가 자연어로 쉽게 탐색할 수 있도록 돕는 AI 기반 홈페이지 파인더입니다.

사용자는 정확한 메뉴명이나 행정 용어를 몰라도 "신청서 어디 있어?", "지원사업 공고 어디서 봐?", "제출서류 뭐야?", "담당자 연락처 찾아줘"처럼 질문할 수 있습니다. AI파인더는 홈페이지 구조, 게시판, 공지사항, 첨부문서, 신청 절차를 분석하여 사용자가 원하는 페이지와 문서로 안내합니다.

## 핵심 목표

- 복잡한 홈페이지 메뉴를 사용자 의도 중심으로 재구성합니다.
- 공지사항, 사업공고, 자료실, 첨부파일에 흩어진 정보를 통합 검색합니다.
- 사용자가 해야 할 다음 행동을 단계별로 안내합니다.
- 답변마다 출처 링크, 문서명, 게시일, 첨부파일명을 함께 제공합니다.
- 초기 버전은 브라우저 확장프로그램 없이 작동합니다.
- 장기적으로는 브라우저 확장프로그램 또는 기관 홈페이지 삽입형 위젯으로 확장합니다.

## 초기 MVP 범위

1. 사이트 프로필(YAML)로 기관을 정의하고, `--site-id` 인자로 대상 기관을 선택합니다.
2. 메뉴 구조와 주요 게시판을 분석합니다.
3. PDF, HWP/HWPX, DOCX, XLSX 등 첨부문서를 파싱합니다.
4. 사용자 질문에 대해 관련 페이지와 문서를 찾아줍니다.
5. 신청 절차, 제출서류, 기한, 담당자 정보를 요약합니다.
6. 답변에 바로가기 링크와 근거를 포함합니다.

## 프로젝트 구조

```
400-ai-finder/
├── configs/sites/             # 사이트 프로필 설정 (YAML)
├── data/
│   ├── raw/                   # 원본 수집 데이터
│   ├── processed/             # 가공된 홈페이지 지도 (JSON/MD)
│   └── index/                 # 검색 인덱스 (JSONL)
├── docs/                      # 기획·설계 문서
├── examples/                  # 예시 질문·답변·지도
├── presentation/              # 발표자료 (대상별 HTML/PPT)
├── prompts/                   # LLM 프롬프트 템플릿
├── proposal/                  # 사업계획서·제안서
├── scripts/                   # 실행 스크립트 (데모, 파이프라인, 유틸리티)
├── src/
│   ├── answer/                # AnswerComposer — 근거 기반 답변 생성
│   ├── crawler/               # 홈페이지 수집 (URL, sitemap, 지도)
│   ├── demo/                  # SiteDemoRunner — 데모 실행 엔진
│   ├── diagnostics/           # 사이트 진단
│   ├── fetch/                 # Fetch Provider (requests, firecrawl, mock)
│   ├── indexer/               # 문서 색인·보강
│   ├── llm/                   # LLM Provider 추상화 (mock, stub, openai_compatible)
│   ├── pipeline/              # 파이프라인 Runner, Smoke Reporter
│   ├── search/                # 키워드 검색 엔진
│   ├── site_profiles/         # 사이트 프로필 로더
│   ├── strategy/              # 전략 라우터 (Fallback 포함)
│   └── web/                   # 웹 UI (모바일 + 운영자 대시보드)
│       ├── templates/         # HTML 템플릿 (Jinja-style)
│       └── static/            # CSS/JS 정적 자산
│           ├── mobile/        # 모바일 UI (8개 CSS + 1개 JS)
│           └── admin/         # 운영자 UI (CSS + JS)
└── tests/                     # pytest 테스트 스위트 + fixtures
```

## 주요 기능 및 특징

### 🏛️ 다중 기관 지원 — 사이트 프로필 시스템
- `configs/sites/` 아래 YAML 파일 하나로 새 기관을 추가할 수 있습니다.
- 현재 지원 프로필:

| site_id | 기관명 | 홈페이지 | 분류 |
|---------|--------|----------|------|
| `bukgu_gwangju` | 광주광역시 북구청 | https://bukgu.gwangju.kr/ | LEGACY_BOARD_SITE |
| `gwangju_go_kr` | 광주광역시청 | https://www.gwangju.go.kr/ | LEGACY_BOARD_SITE |

- CLI 또는 서버 실행 시 `--site-id`로 기본 대상 기관을 지정합니다.
- 운영자 대시보드에서는 등록된 site profile 목록을 불러와 테스트 대상 기관을 선택하고 전환할 수 있습니다.
- 모바일 사용자 화면은 서버 실행 시 지정된 기본 기관을 유지하며, 운영자용 site 선택 UI를 노출하지 않습니다.

### 📱 모바일 ChatGPT형 사용자 UI (통합 실행: http://localhost:8400, 개별 실행: http://localhost:8080)
- ChatGPT 스타일의 1:1 대화형 채팅 인터페이스입니다.
- 하단 고정 입력창, 메시지 누적, 추천 질문 Chip, 답변 하단 관련 홈페이지 카드 구조를 제공합니다.
- 라이트모드 기본, 다크모드 토글 지원, 핑크색 포인트 버튼입니다.
- CSS/JS가 파일별로 분리되어 유지보수가 용이합니다 (총 8개 CSS + 1개 JS).
- 사이드바 접기/펼치기 기능으로 채팅 이력을 관리합니다.
- 일반 사용자 관점에서 기술적인 용어(`provider`, `model`, `preset` 등)가 전혀 노출되지 않습니다.

### 🖥️ 운영자 대시보드 (http://localhost:8090)
- **서비스 및 사이트 정보 조회**: 현재 가동 중인 서비스명, 사이트 ID, 프로필 세부 사항 및 수집된 홈페이지 구조 요약을 모니터링합니다.
- **기관 선택 패널**: 등록된 site profile 목록에서 북구청(`bukgu_gwangju`)과 광주광역시청(`gwangju_go_kr`)을 선택해 같은 대시보드에서 기관별 테스트를 전환할 수 있습니다.
- **LLM 모델 선택 패널**: 대시보드 화면에서 테스트용 LLM 프리셋 조합을 실시간으로 변경해가며 응답 품질을 비교·테스트할 수 있습니다.
  - **DeepSeek 기본** (preset: `deepseek-primary` / model: `deepseek-v4-flash` / provider: `opencode-go`)
  - **MiMo 기본** (preset: `mimo-primary` / model: `mimo-v2.5-pro` / provider: `opengateway`)
  - **Step 기본** (preset: `step-primary` / model: `stepfun-ai/step-3.5-flash` / provider: `nvidia`)
- **실시간 데모 테스트**: 질문을 직접 입력하거나 빠른 버튼으로 테스트하고, 상세 통계(Fallback 여부, 출처 점수, 경고 등)와 출처 목록 테이블을 점검할 수 있습니다.
- API 응답에 `site_id`, `site_name`, `provider`, `model`, `preset` 정보가 포함되어 어떤 기관과 LLM 조합으로 응답했는지 즉시 확인할 수 있습니다.

### ⚙️ Model-First CLI 및 Preset 시스템
- CLI 옵션을 명시하지 않을 경우 **DeepSeek 기본** 조합(`deepseek-primary`)이 자동 적용됩니다.
- `--provider`, `--model`, `--preset` 인자를 통해 실행 시점에 유연하게 동적 재정의(override)할 수 있습니다.
- 모델 이름만 지정하면 프리셋에 정의된 provider를 자동으로 찾아 연결합니다 (Model-First 해석).
- 프리셋 순서: DeepSeek(1순위) → MiMo(2순위) → Step(3순위).

### 🧪 StubProvider — API 키 없는 종단간 테스트
- `stub` 프로바이더는 실제 LLM API 호출 없이 source context를 파싱하여 현실적인 grounded answer를 생성합니다.
- API 키 없이 전체 파이프라인을 종단간(end-to-end) 테스트할 수 있습니다.
- `fail_on` 옵션으로 에러 처리 경로를 강제 테스트할 수 있습니다.

### 📦 Snapshot 안정 데모 지원
- `--snapshot` 인자를 통해 사전 수집 및 가공된 스냅샷 JSON 파일을 주입하면, 외부 네트워크 및 API 호출 없이도 시연 대화가 완벽하게 동작합니다.
- 오프라인 환경, 보안 구역, 네트워크 차단 환경에서도 안정적으로 시연할 수 있습니다.
- Smoke eval CLI 흐름은 `docs/smoke-eval-flow.md`를 참고하십시오.
- 운영자 빠른 시작 안내는 `docs/operator-quickstart.md`를 참고하십시오.

### 🛡️ 실패 대응 Hardening (예외 복구)
- **API Key 누락**: `Pending configuration` 에러를 명확히 반환합니다.
- **API 통신 타임아웃/커넥션 에러**: 백엔드가 Crash되지 않고 안전하게 포착합니다.
- **사용자 안내**: 에러 시 `"현재 AI 답변을 생성할 수 없습니다..."` 메시지를 표시합니다.
- **Fallback 출처**: 검색 결과가 없으면 홈페이지 지도의 메뉴 링크를 출처로 제공합니다.
- **Snapshot 모드**: 네트워크/API 불가 환경에서도 사전 수집 데이터로 안정 동작합니다.

### 🔒 보안 주의사항
- **API Key 노출 금지**: 실제 외부 LLM 공급자 API Key는 소스코드, 테스트 코드, 설정 파일(.env 등)에 하드코딩되어서는 안 됩니다. `.env.example` 파일에 환경변수 이름만 기재하고, `.gitignore`에 `.env`가 포함되어 있는지 확인하십시오.
- **로컬 Mock/Stub 테스트**: 로컬 개발 및 테스트 시에는 `mock` 또는 `stub` 프로바이더를 활용하십시오. 두 프로바이더 모두 API 키를 요구하지 않습니다.
- **Pending Configuration 검증**: `opencode-go`, `opencode-zen`, `nous` 등 환경변수 기반 프로바이더는 Base URL과 API Key가 모두 설정되어야 동작합니다. 미설정 시 명확한 에러를 반환합니다.
- **프로덕션 배포 시**: `.env` 파일에 실제 키를 넣고, Git에 커밋하지 마십시오.

## LLM 프로바이더 목록

| 프로바이더 | 설명 | 기본 모델 | API Key 필요 |
|-----------|------|----------|-------------|
| `mock` | 테스트용 고정 응답 | mock | ❌ |
| `stub` | Source 기반 시뮬레이션 응답 | stub | ❌ |
| `opencode-go` | OpenCode-Go Gateway | deepseek-v4-flash | ✅ |
| `opengateway` | OpenGateway | mimo-v2.5-pro | ✅ |
| `nvidia` | NVIDIA NIM | openai/gpt-oss-120b | ✅ |
| `kilocode` | KiloCode | deepseek/deepseek-v4-flash:free | ✅ |
| `mistral` | Mistral AI | mistral-medium-3.5 | ✅ |
| `groq` | Groq | gpt-oss-120b | ✅ |
| `opencode-zen` | OpenCode-Zen Gateway | deepseek-v4-flash-free | ✅ |
| `nous` | Nous Gateway | deepseek/deepseek-v4-flash:free | ✅ |

## 발표자료와 제안서

외부 설명과 제안을 위한 자료는 별도 폴더에 정리합니다.

- `presentation/`: 대상별 발표자료와 HTML 소개자료
- `presentation/master/ai-finder-master.html`: 통합 HTML 소개자료
- `presentation/audience-company-ceo/`: 회사 대표 대상 사업화 설명자료
- `presentation/audience-public-institution/`: 공기업 및 기관 대상 도입 제안자료
- `presentation/audience-consumer/`: 일반 소비자 대상 쉬운 소개자료
- `proposal/`: 사업계획서와 PoC 제안서 초안

## 데모 실행

### 빠른 시작 — 북구청 (Snapshot 모드)

```bash
PYTHONPATH=. .venv/bin/python scripts/run_all_demos.py \
    --site-id bukgu_gwangju \
    --snapshot tests/fixtures/bukgu_gwangju_demo_snapshot.json
```
*(옵션에 `--provider`를 생략하거나 미지정 시 기본 DeepSeek 프리셋 설정이 적용되며, 스냅샷 모드로 안정 구동됩니다.)*

### 빠른 시작 — 광주광역시청 (Live Fetch)

```bash
PYTHONPATH=. .venv/bin/python scripts/run_all_demos.py \
    --site-id gwangju_go_kr \
    --provider stub \
    --fetch-provider requests
```
*(네트워크가 필요합니다. `--provider stub`은 API 키 없이 동작합니다.)*

통합 실행 후 브라우저에서 접속:

- **모바일 사용자 화면**: http://localhost:8400
- **운영자 대시보드**: http://localhost:8090

운영자 대시보드에서는 `--site-id`로 시작한 기본 기관과 별개로, 기관 선택 패널에서 등록된 profile을 골라 `/api/test` 테스트 대상을 전환할 수 있습니다.

### 개별 실행

개별 모바일 서버는 scripts/run_mobile_demo.py의 --port 기본값인 8080을 사용합니다.

**모바일 사용자 화면만:**

```bash
PYTHONPATH=. .venv/bin/python scripts/run_mobile_demo.py \
    --site-id bukgu_gwangju \
    --snapshot tests/fixtures/bukgu_gwangju_demo_snapshot.json \
    --port 8080
```

**광주광역시청 모바일 화면:**

```bash
PYTHONPATH=. .venv/bin/python scripts/run_mobile_demo.py \
    --site-id gwangju_go_kr \
    --provider stub \
    --fetch-provider requests \
    --port 8080
```

**운영자 대시보드만:**

```bash
PYTHONPATH=. .venv/bin/python scripts/run_admin_demo.py \
    --site-id bukgu_gwangju \
    --snapshot tests/fixtures/bukgu_gwangju_demo_snapshot.json \
    --port 8090
```

### CLI 옵션

| 옵션 | 설명 | 기본값 |
|------|------|--------|
| `--site-id` | 사이트 프로필 ID (필수) | - |
| `--provider` | LLM 프로바이더 이름 | 자동 해석 (deepseek-primary) |
| `--model` | LLM 모델 이름 | 프리셋에 따라 자동 결정 |
| `--preset` | 프리셋 이름 (`deepseek-primary`, `mimo-primary`, `step-primary`) | - |
| `--snapshot` | 스냅샷 JSON 파일 경로 | - |
| `--mobile-port` | 모바일 서버 포트 | 8400 |
| `--admin-port` | 운영자 서버 포트 | 8090 |
| `--host` | 바인드 호스트 | 0.0.0.0 |

### 프리셋 미지정 시 동작

`--provider`, `--model`, `--preset` 모두 지정하지 않으면 `resolve_provider_model()`이 자동으로 `deepseek-primary` 프리셋을 선택합니다:

```
DeepSeek (1순위) → MiMo (2순위) → Step (3순위)
```

## 질문-답변 데모 예시

### 북구청 — 민원서식 (Snapshot)

```bash
PYTHONPATH=. .venv/bin/python scripts/demo_answer.py \
    --site-id bukgu_gwangju \
    --question "민원서식 어디서 받아?" \
    --provider stub \
    --snapshot tests/fixtures/bukgu_gwangju_demo_snapshot.json
```

### 광주광역시청 — 고시공고 (Live Fetch)

```bash
PYTHONPATH=. .venv/bin/python scripts/demo_answer.py \
    --site-id gwangju_go_kr \
    --question "고시공고는 어디서 봐?" \
    --provider stub \
    --fetch-provider requests --allow-live
```

*(Live fetch providers such as `requests` require `--allow-live`. For safe offline runs, use the mock provider and omit `--allow-live`.)*

### 광주광역시청 — 정보공개 (Live Fetch)

```bash
PYTHONPATH=. .venv/bin/python scripts/demo_answer.py \
    --site-id gwangju_go_kr \
    --question "정보공개는 어디서 확인해?" \
    --provider stub \
    --fetch-provider requests --allow-live
```

*(Live fetch providers such as `requests` require `--allow-live`. For safe offline runs, use the mock provider and omit `--allow-live`.)*

### 광주광역시청 — 복지 지원사업 (Live Fetch)

```bash
PYTHONPATH=. .venv/bin/python scripts/demo_answer.py \
    --site-id gwangju_go_kr \
    --question "복지 지원사업은 어디서 확인해?" \
    --provider stub \
    --fetch-provider requests --allow-live
```

### Stage 36 — 광주광역시청 검증 결과 (2026-05)

Stage 36에서 광주광역시청(`gwangju_go_kr`) 프로필에 대해 5개 질문의 출처 기반 응답을 검증했습니다.

| # | 질문 | 검색결과 | 출처 | 대표 출처 |
|---|------|---------|------|----------|
| 1 | 고시공고는 어디서 봐? | 1건 | 1건 | 고시·공고/입법예고 |
| 2 | 정보공개는 어디서 확인해? | 5건 | 5건 | 계약정보공개시스템, 정보공개청구현황 |
| 3 | 시청 조직도는 어디서 봐? | 5건 | 5건 | 시청안내, 어린이시청 |
| 4 | 민원 신청은 어디서 해? | 5건 | 5건 | 광주통합민원 바로응답, 민원신청 |
| 5 | 복지 지원사업은 어디서 확인해? | 5건 | 5건 | 광주복지플랫폼, 금융복지지원센터 |

- 모든 질문이 `gwangju.go.kr` 도메인의 출처를 반환합니다.
- 조사 스트립, 가운뎃점 정규화, N-gram fallback 등 한글 검색 강화가 적용되었습니다.

## 테스트 실행

```bash
PYTHONPATH=. .venv/bin/python -m pytest tests/ -v
```

- 전체 테스트는 API 키 없이 실행 가능합니다 (`mock`, `stub` 프로바이더 사용).
- `tests/fixtures/bukgu_gwangju_demo_snapshot.json` 파일을 스냅샷 테스트에 활용합니다.
- Provider live-only tests are opt-in and skipped by default. They require explicit `RUN_LIVE_*_TESTS=1` flags in addition to API keys. See `docs/provider-fetch-network-boundary.md` for details.

## Cloudflare Pages 정적 시연 배포

400-ai-finder는 **두 가지 배포 방식**을 지원합니다. 이 둘은 완전히 독립적이며, 각각 다른 목적에 사용됩니다.

### 배포 방식 구분

| 구분 | 설명 |
|------|------|
| **Python 로컬/서버 데모** | `src/web` 기반 Python 서버. 실제 AI·API·크롤링 사용 가능 (→ [`docs/operator-quickstart.md`](docs/operator-quickstart.md)) |
| **Cloudflare Pages 정적 시연** | `dist/cloudflare-pages/` 빌드 산출물. 백엔드 없음, 결정형 스냅샷 기반, 네트워크 호출 없음 |

### 정적 Pages 시연 개요

Cloudflare Pages는 GitHub `main` push 시 **자동으로** `python3 scripts/build_cloudflare_pages.py`를 실행하여 정적 시연 산출물(`dist/cloudflare-pages/`)을 프로덕션에 배포합니다. 자세한 설정값은 [`docs/cloudflare-pages-bukgu-mvp.md`](docs/cloudflare-pages-bukgu-mvp.md)를 참고하세요.

| 항목 | 값 |
|---|---|
| Project name | `cgbukku` |
| Connected repository | `skerishKang/400-ai-finder` |
| Production branch | `main` |
| Build command | `python3 scripts/build_cloudflare_pages.py` |
| Build output directory | `dist/cloudflare-pages` |
| Framework preset | None |
| Root directory | _(empty)_ |

**Production URL:** `https://cgbukku.pages.dev/`

### public 경로

| 경로 | 설명 |
|---|---|
| `/` | 정적 랜딩 페이지 (MVP 카드 포함) |
| `/mvp/` | 시민 첫 화면 시연 entry (백엔드 없음) |
| `/mobile` | 모바일 챗 데모 (`/mobile.html` → 308 redirect) |
| `/admin` | 운영자 화면 (`/admin.html` → 308 redirect) |

### 생성된 `dist/` 디렉토리

`dist/cloudflare-pages/`는 빌드 산출물이며 **Git에 커밋하지 않습니다** (`.gitignore`에 의해 추적 제외). 배포 시 Cloudflare Pages 빌드 단계에서 직접 생성합니다.

### GitHub Actions: Deploy가 아닌 Contract/Test입니다

`.github/workflows/mvp-contracts.yml`의 **"MVP Contract Checks"**는 배포 워크플로가 **아닙니다**. 이 workflow는 다음만 수행합니다:

- pytest contract 테스트 실행
- `tests/test_build_cloudflare_pages.py` — 임시 출력 디렉터리에 정적 Pages build를 실행하고 산출물 contract를 검증
- `node tests/browser/verify_mvp_shell_runtime.mjs` — 브라우저 런타임 시나리오 검증

배포는 **Cloudflare Pages Git integration이 자동**으로 담당하며, GitHub Actions workflow 내에서 `wrangler`, `cloudflare/pages-action`, publish 명령 등을 사용하지 않습니다.

### 정적 시연 확인 (read-only)

Cloudflare Pages dashboard에서 read-only로 확인:

1. Latest production deployment status / SHA / time
2. SHA가 `origin/main` 또는 해당 PR merge commit과 일치하는지 비교

public URL read-only 확인:

```
curl -sI https://cgbukku.pages.dev/         # 200
curl -sI https://cgbukku.pages.dev/mvp/     # 200
curl -sI https://cgbukku.pages.dev/mobile    # 200
curl -sI https://cgbukku.pages.dev/admin     # 200
```

**참고**: public URL만으로 latest deployed commit SHA는 확정할 수 없습니다. 정확한 SHA는 Cloudflare Pages deployment metadata에서 확인하세요.

### Boundaries

- 이 정적 시연은 **백엔드 없는 결정형 데모**입니다. 기본 검증 흐름은 이 로컬 정적 아티팩트만으로 충분합니다.
- 북구청 공식 사이트 참고·클릭·검색·스크린샷 비교, route/content inventory, crawling/scraping, 그리고 Firecrawl·외부 API·live provider reference 수집은 현재 제품 방향에서 **허용되는 참고·수집 작업**입니다.
- live-dependent 실험 경로(Firecrawl/외부 API/live provider 호출)는 별도 operational stage로 분리되어 있으며, 명시적 opt-in과 자격 증명(env) 설정 하에 실행됩니다. 자세한 경계는 [`docs/provider-fetch-network-boundary.md`](docs/provider-fetch-network-boundary.md)를 참고하세요.
- Cloudflare 배포 제어는 운영자 전용입니다. 배포 재실행(Retry/Redeploy/Create deployment)은 배포 권한 보유 운영자만 수행하며, secrets/env는 해당 운영자 책임 하에 다룹니다.

더 자세한 내용은 [`docs/cloudflare-pages-bukgu-mvp.md`](docs/cloudflare-pages-bukgu-mvp.md)를 참고하세요.

### MVP demo docs

- [MVP demo operator runbook](docs/mvp-demo-operator-runbook.md) — how to run, verify, and present the five locked local/static resident-task flows.
- [MVP golden quest fidelity matrix](docs/mvp-golden-quest-fidelity-matrix.md) — locked quest IDs, official paths, local/static boundaries, stop behavior, E2E verifier references, and prohibited regressions.
- [MVP demo milestone snapshot](docs/mvp-demo-milestone-snapshot.md) — one-page closeout summary of the completed local/static MVP scope, locked quest set, verification references, and deferred live/production epics.
- [Live transition decision record](docs/live-transition-decision-record.md) — decision gate for any future live/provider/API/network, operational integration, or production rebuild work; this document is not live-work authorization.
- [Official-site route inventory plan](docs/official-site-route-inventory-plan.md) — planning-only schema and classification guide for future #862 route/content inventory; no live collection or inventory dataset is included.
- [Official-site route inventory workflow index](docs/official-site-route-inventory-workflow-index.md) — planning-only index tying together the route inventory planning docs and workflow order; does not authorize live work.
- [Official-site route inventory planning package closeout](docs/official-site-route-inventory-planning-closeout.md) — planning-only closeout of the route inventory planning package; preparation for future scoped issues, not live-work authorization.

### Operator quickstart

실행 흐름, 데모, smoke eval, live provider 사용법은 다음 문서를 참고하십시오:

- [`docs/operator-quickstart.md`](docs/operator-quickstart.md) — 운영자 빠른 안내서 (offline → live 순서)
- [`docs/operator-question-log-guide.md`](docs/operator-question-log-guide.md) — Operator Question Log Guide (sanitized log collection + dry-run analytics)
- [`docs/scenario-cache-promotion-review-workflow.md`](docs/scenario-cache-promotion-review-workflow.md) — Scenario/Cache Promotion Review Workflow (cache/scenario/retrieval-gap/monitor-only 분류 + human review 체크리스트)
- [`docs/promotion-candidate-review-template.md`](docs/promotion-candidate-review-template.md) — Promotion Candidate Review Template (copy-pasteable 후킹 review template)
- [`docs/operator-synthetic-promotion-dry-run.md`](docs/operator-synthetic-promotion-dry-run.md) — 합성 로그 기반 promotion dry-run 안내 (cache/scenario/retrieval-gap/monitor-only 리허설)
- [`docs/smoke-eval-flow.md`](docs/smoke-eval-flow.md) — Smoke eval CLI 흐름
- [`docs/bukgu-live-demo-package.md`](docs/bukgu-live-demo-package.md) — Buk-gu live LLM demo package (외부 시연용)
- [`docs/operator-controlled-retrieval-gap-validation.md`](docs/operator-controlled-retrieval-gap-validation.md) — Controlled retrieval-gap validation operator guide (no answer generation, no live boundary crossing)
- [`docs/bukgu-demo-one-page-handout.md`](docs/bukgu-demo-one-page-handout.md) — Buk-gu demo one-page handout (외부 시연용 1페이지 요약)
- [`docs/bukgu-demo-presentation-outline.md`](docs/bukgu-demo-presentation-outline.md) — Buk-gu demo presentation outline (5~7분 발표 구성안)
- [`docs/artifacts/400-ai-finder-bukgu-demo.pptx`](docs/artifacts/400-ai-finder-bukgu-demo.pptx) — Buk-gu demo PPT slide deck (6~7 slides, 5~7분 발표용)

### Product design

- [`docs/product/dynamic-retrieval-query-learning-strategy.md`](docs/product/dynamic-retrieval-query-learning-strategy.md) — Dynamic Retrieval + Query Learning Strategy
- [`docs/product/repeated-question-analytics-promotion-plan.md`](docs/product/repeated-question-analytics-promotion-plan.md) — Repeated-Question Analytics and Scenario-Cache Promotion Plan

### Repeated-question analytics dry-run (Stage 353)

```bash
PYTHONPATH=. .venv/bin/python scripts/analyze_question_logs.py \
    --input question-log.jsonl \
    --output repeated-question-report.md
```

Reads sanitized JSONL question logs and produces a Markdown report separating
promotion candidates from retrieval gaps. Dry-run only — no scenarios, snapshots,
caches, PRs, or commits are created.
