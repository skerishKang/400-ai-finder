# 400-ai-finder

> **현재 상태 — 2026-08-12**
>
> Buk-gu Frozen Demo는 완료되었고 북구는 첫 번째 protected golden reference입니다. 현재 제품 방향은 **general-site / multi-site AI Browser platform**으로 다시 열렸습니다. 다만 URL 하나만으로 arbitrary site의 Site Model·generated preview·knowledge·action graph를 모두 만드는 generic onboarding runtime이 이미 완성됐다고 주장하지 않습니다.

## 제품 방향

400-ai-finder의 장기 제품 형태는 단순 FAQ 챗봇이 아니라 다음과 같습니다.

```text
왼쪽: target website / clone / generated preview
오른쪽: AI conversation / answer / navigation / bounded Browser Use
```

사이트마다 처음부터 bespoke 제품을 새로 만드는 대신 다음 흐름을 목표로 합니다.

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

초기 현실적 목표는 **70–80% supervised automation + explicit exceptions**입니다. `generated_preview`는 `exact`, `archetype_golden`, `resident_default_approved`, production approval과 같은 상태가 아닙니다.

## 먼저 읽을 문서

- [현재 기준 문서 인덱스](docs/CURRENT_STATUS.md)
- [제품 트랙과 운영경계](docs/product/PRODUCT_TRACKS_AND_BOUNDARIES.md)
- [Unified Runtime과 canonical SiteSpec](docs/architecture/UNIFIED_RUNTIME_AND_SITESPEC.md)
- [출시·온보딩 게이트](docs/implementation/RELEASE_GATES.md)
- [공개 AI API 보안·개인정보 모델](docs/operations/PUBLIC_AI_API_SECURITY_AND_PRIVACY.md)
- [MVP AI runtime contract](docs/operations/MVP_AI_RUNTIME_CONTRACT.md)
- [저장소 거버넌스](docs/operations/REPOSITORY_GOVERNANCE.md)
- [기여규칙](CONTRIBUTING.md)
- [보안정책](SECURITY.md)
- [2026-08-04 프로젝트 감사](docs/audit/PROJECT_AUDIT_20260804.md) — historical audit
- [2026-08-04 구현 로드맵](docs/implementation/ROADMAP_20260804.md) — historical plan; 현재 실행순서로 사용하지 않음

## 현재 제품 판정

| 영역 | 현재 상태 |
|---|---|
| Buk-gu clone·결정형 시민 여정 | Frozen Demo complete; first protected golden reference |
| 공식 fixture·snapshot | Provenance·checksum·시각정보 관리 |
| 다국어·접근성·모바일 | 강한 contract·browser E2E 보유 |
| Cloudflare AI runtime code | 구현됨. Gemini default path는 3.5 primary → 3.1 same-provider fallback |
| Live-public 운영승인 | 별도 durable abuse/cost/staging gate 없이 자동 승인되지 않음 |
| 공식정보 answer-time freshness | canonical snapshot/evidence foundation 존재; 일반 live retrieval은 별도 승인경계 |
| Multi-site platform | Site profile/SiteSpec/shared-contract foundation 존재; generic arbitrary-site onboarding runtime은 미완료 |
| Actual public-site integration | 기관 권한·credentials·운영책임 전에는 미승인 |
| 라이선스·공개자산 | Inventory 존재; owner/rights #1234 별도 결정 필요 |

## 현재 작업 프로그램

- [#1283 post-Buk-gu multi-site AI Browser governance alignment](https://github.com/skerishKang/400-ai-finder/issues/1283) — platform implementation 전 current contract/governance 정렬
- [#1234 code/official capture/third-party asset license & provenance](https://github.com/skerishKang/400-ai-finder/issues/1234) — 별도 owner/rights 결정

완료·역사 계획인 #1235/#1181/#1232 등은 현재 `docs/CURRENT_STATUS.md`의 분류를 따릅니다. 과거 이슈 순서를 현재 개발순서로 그대로 재실행하지 않습니다.

## 현재 안전경계

- 실제 민원 제출, 로그인, 결제와 production write action을 승인 없이 수행하지 않습니다.
- 주민등록번호·계좌·상세주소 등 고위험 개인정보를 입력·저장하는 서비스로 승인되지 않았습니다.
- 공식도메인 citation과 검증된 canonical snapshot을 같은 상태로 취급하지 않습니다.
- 근거가 없는 연락처·기한·수수료·제출서류는 확정정보로 제공하면 안 됩니다.
- routine CI는 외부 provider·공식사이트 network 없이 재현 가능해야 합니다.
- **URL supplied != live network authorized.** URL 제공은 대상 식별이며 live crawl/fetch/provider 실행은 별도 경계를 따릅니다.
- Buk-gu golden route·DOM·state와 resident-default는 migration·applicable visual approval 없이 변경하지 않습니다.
- generated onboarding preview는 approved resident-default를 자동으로 대체하지 않습니다.

---

## 프로젝트 소개

400-ai-finder는 복잡한 기관 홈페이지, 공공기관 홈페이지, 대학 홈페이지, 기업 지원사업 홈페이지를 사용자가 자연어로 쉽게 탐색할 수 있도록 돕는 AI 기반 홈페이지 파인더입니다.

사용자는 정확한 메뉴명이나 행정 용어를 몰라도 "신청서 어디 있어?", "지원사업 공고 어디서 봐?", "제출서류 뭐야?", "담당자 연락처 찾아줘"처럼 질문할 수 있습니다. AI파인더는 홈페이지 구조, 게시판, 공지사항, 첨부문서, 신청 절차를 분석하여 사용자가 원하는 페이지와 문서로 안내합니다.

## 핵심 목표

- 복잡한 홈페이지 메뉴를 사용자 의도 중심으로 안내합니다.
- 공지사항, 사업공고, 자료실, 첨부파일에 흩어진 정보를 통합 검색합니다.
- 사용자가 해야 할 다음 행동을 단계별로 안내합니다.
- 답변마다 출처 링크, 문서명, 게시일, 첨부파일명을 함께 제공합니다.
- 왼쪽 사이트 surface와 오른쪽 AI 대화·탐색·Browser Use를 공통 제품 구조로 발전시킵니다.
- 장기적으로 사이트별 차이는 archetype, capability, data/config, explicit reviewed override로 흡수하는 것을 목표로 합니다.

## 기존 Python/데모 기반 범위

1. 사이트 프로필(YAML)로 기관을 정의하고, `--site-id` 인자로 대상 기관을 선택합니다.
2. 메뉴 구조와 주요 게시판을 분석합니다.
3. PDF, HWP/HWPX, DOCX, XLSX 등 첨부문서를 파싱합니다.
4. 사용자 질문에 대해 관련 페이지와 문서를 찾아줍니다.
5. 신청 절차, 제출서류, 기한, 담당자 정보를 안내합니다.
6. 답변에 바로가기 링크와 근거를 포함합니다.

> **Buk-gu golden / exact promotion 철칙**: 왼쪽 시민 사이트 화면은 캡처된 광주광역시 북구청 공식 페이지를 그대로 복제한다. `exact`를 주장하는 좌측 surface는 공식 페이지의 내용·구조·표·행·순서·컨트롤·시각 표현을 요약하거나 재설계하지 않습니다. Canonical: [docs/product/exact-official-site-clone-invariant.md](docs/product/exact-official-site-clone-invariant.md)
>
> **Generated preview 경계**: routine onboarding의 `generated_preview`는 non-exact/non-default 상태로 존재할 수 있지만 low-confidence·unsupported·unresolved 항목을 exception으로 드러내야 하며 resident-default를 자동으로 통제할 수 없습니다.
>
> **Visual approval gate**: first resident-default promotion은 applicable accepted reference와의 side-by-side 비교 및 project-owner의 명시적 승인을 따릅니다. Policy: [docs/product/clone-visual-fidelity-and-promotion-policy.md](docs/product/clone-visual-fidelity-and-promotion-policy.md)

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
├── proposal/                  # 사업계획서·제안서 초안
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
- `configs/sites/` 아래 YAML profile로 crawler/operator 대상 기관을 정의합니다.
- 현재 configured YAML profile inventory:

| site_id | 기관명 | 홈페이지 | 분류 |
|---------|--------|----------|------|
| `bukgu_gwangju` | 광주광역시 북구청 | https://bukgu.gwangju.kr/ | LEGACY_BOARD_SITE |
| `gwangju_go_kr` | 광주광역시청 | https://www.gwangju.go.kr/ | LEGACY_BOARD_SITE |
| `seogu_gwangju` | 광주광역시 서구청 | https://www.seogu.gwangju.kr/ | LEGACY_BOARD_SITE |

YAML profile이 존재한다는 사실과 Cloudflare generic resident adapter가 완성됐다는 것은 다른 상태입니다. 현재 arbitrary site를 SiteSpec 하나로 end-to-end resident runtime에 자동 wiring하는 기능은 아직 완성되지 않았습니다.

- CLI 또는 서버 실행 시 `--site-id`로 기본 대상 기관을 지정합니다.
- 운영자 대시보드에서는 runtime에 등록된 site profile을 선택해 기관별 테스트를 전환할 수 있습니다.
- 모바일 사용자 화면은 서버 실행 시 지정된 기본 기관을 유지하며, 운영자용 site 선택 UI를 노출하지 않습니다.

### 📱 모바일 ChatGPT형 사용자 UI (통합 실행: http://localhost:8400, 개별 실행: http://localhost:8080)
- ChatGPT 스타일의 1:1 대화형 채팅 인터페이스입니다.
- 하단 고정 입력창, 메시지 누적, 추천 질문 Chip, 답변 하단 관련 홈페이지 카드 구조를 제공합니다.
- 라이트모드 기본, 다크모드 토글 지원, 핑크색 포인트 버튼입니다.
- CSS/JS가 파일별로 분리되어 유지보수가 용이합니다 (총 8개 CSS + 1개 JS).
- 사이드바 접기/펼치기 기능으로 채팅 이력을 관리합니다.
- 일반 사용자 관점에서 기술적인 용어(`provider`, `model`, `preset` 등)가 전혀 노출되지 않습니다.

### 🖥️ 운영자 대시보드 (http://localhost:8090)
- **서비스 및 사이트 정보 조회**: 현재 가동 중인 서비스명, 사이트 ID, 프로필 세부 사항 및 수집된 홈페이지 구조 요약(진단용 메타 요약)을 모니터링합니다.
- **기관 선택 패널**: 등록된 site profile 목록에서 테스트 대상을 전환할 수 있습니다.
- **LLM 모델 선택 패널**: Python/operator 데모에서는 테스트용 LLM 프리셋 조합을 실시간으로 변경해가며 응답 품질을 비교·테스트할 수 있습니다.
  - **DeepSeek 기본** (preset: `deepseek-primary` / model: `deepseek-v4-flash` / provider: `opencode-go`)
  - **MiMo 기본** (preset: `mimo-primary` / model: `mimo-v2.5-pro` / provider: `opengateway`)
  - **Step 기본** (preset: `step-primary` / model: `stepfun-ai/step-3.5-flash` / provider: `nvidia`)
- **실시간 데모 테스트**: 질문을 직접 입력하거나 빠른 버튼으로 테스트하고, 상세 통계(Fallback 여부, 출처 점수, 경고 등)와 출처 목록 테이블을 점검할 수 있습니다.
- API 응답에 `site_id`, `site_name`, `provider`, `model`, `preset` 정보가 포함되어 어떤 기관과 LLM 조합으로 응답했는지 즉시 확인할 수 있습니다.

### ⚙️ Model-First CLI 및 Preset 시스템
- Python/operator CLI 옵션을 명시하지 않을 경우 해당 Python preset resolver의 기본 조합이 적용됩니다.
- `--provider`, `--model`, `--preset` 인자를 통해 실행 시점에 동적 재정의(override)할 수 있습니다.
- 이 Python/operator preset 체계와 Cloudflare `/api/mvp/ask`의 Gemini default attempt plan은 별도 runtime contract입니다.

### 🧪 StubProvider — API 키 없는 종단간 테스트
- `stub` 프로바이더는 실제 LLM API 호출 없이 source context를 파싱하여 현실적인 grounded answer를 생성합니다.
- API 키 없이 전체 파이프라인을 종단간(end-to-end) 테스트할 수 있습니다.
- `fail_on` 옵션으로 에러 처리 경로를 강제 테스트할 수 있습니다.

### 📦 Snapshot 안정 데모 지원
- `--snapshot` 인자를 통해 사전 수집 및 가공된 스냅샷 JSON 파일을 주입하면, 외부 네트워크 및 API 호출 없이도 시연 대화가 동작합니다.
- 오프라인 환경, 보안 구역, 네트워크 차단 환경에서도 재현 가능한 시연이 가능합니다.
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
- **Pending Configuration 검증**: 환경변수 기반 live 프로바이더는 필요한 endpoint/key 설정이 충족되어야 동작합니다. 미설정 시 명확한 에러를 반환해야 합니다.
- **배포 secrets**: 실제 키는 Git에 커밋하지 않고 deployment secret/binding으로 관리합니다.

## Python/operator LLM 프로바이더 목록

| 프로바이더 | 설명 | 기본 모델 | API Key 필요 |
|-----------|------|----------|-------------|
| `mock` | 테스트용 고정 응답 | mock | ❌ |
| `stub` | Source 기반 응답 (실제 LLM API 호출 없음) | stub | ❌ |
| `opencode-go` | OpenCode-Go Gateway | deepseek-v4-flash | ✅ |
| `opengateway` | OpenGateway | mimo-v2.5-pro | ✅ |
| `nvidia` | NVIDIA NIM | openai/gpt-oss-120b | ✅ |
| `kilocode` | KiloCode | deepseek/deepseek-v4-flash:free | ✅ |
| `mistral` | Mistral AI | mistral-medium-3.5 | ✅ |
| `groq` | Groq | gpt-oss-120b | ✅ |
| `opencode-zen` | OpenCode-Zen Gateway | deepseek-v4-flash-free | ✅ |
| `nous` | Nous Gateway | deepseek/deepseek-v4-flash:free | ✅ |

Cloudflare resident `/api/mvp/ask`의 현재 default provider/model contract는 위 Python 표가 아니라 `docs/operations/MVP_AI_RUNTIME_CONTRACT.md`를 따릅니다.

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

### 빠른 시작 — 광주광역시청 (Live Fetch example)

```bash
PYTHONPATH=. .venv/bin/python scripts/run_all_demos.py \
    --site-id gwangju_go_kr \
    --provider stub \
    --fetch-provider requests
```

이 예시는 network path입니다. URL/site-id가 주어졌다는 사실만으로 automation/CI에서 live execution이 승인되는 것은 아닙니다. 실제 live 사용은 `docs/provider-fetch-network-boundary.md`와 operator policy를 따릅니다.

통합 실행 후 브라우저에서 접속:

- **모바일 사용자 화면**: http://localhost:8400
- **운영자 대시보드**: http://localhost:8090

운영자 대시보드에서는 `--site-id`로 시작한 기본 기관과 별개로, 지원되는 기관 선택 UI를 통해 `/api/test` 테스트 대상을 전환할 수 있습니다.

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
| `--provider` | LLM 프로바이더 이름 | preset/runtime resolver |
| `--model` | LLM 모델 이름 | 프리셋에 따라 자동 결정 |
| `--preset` | Python/operator 프리셋 이름 | - |
| `--snapshot` | 스냅샷 JSON 파일 경로 | - |
| `--mobile-port` | 모바일 서버 포트 | 8400 |
| `--admin-port` | 운영자 서버 포트 | 8090 |
| `--host` | 바인드 호스트 | 0.0.0.0 |

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

*(Live fetch providers such as `requests` require the script's applicable live opt-in. For safe offline runs, use the mock/snapshot path.)*

### 광주광역시청 — 정보공개 (Live Fetch)

```bash
PYTHONPATH=. .venv/bin/python scripts/demo_answer.py \
    --site-id gwangju_go_kr \
    --question "정보공개는 어디서 확인해?" \
    --provider stub \
    --fetch-provider requests --allow-live
```

### 광주광역시청 — 복지 지원사업 (Live Fetch)

```bash
PYTHONPATH=. .venv/bin/python scripts/demo_answer.py \
    --site-id gwangju_go_kr \
    --question "복지 지원사업은 어디서 확인해?" \
    --provider stub \
    --fetch-provider requests --allow-live
```

### Historical validation example — 광주광역시청 Stage 36 (2026-05)

Stage 36에서 광주광역시청(`gwangju_go_kr`) 프로필에 대해 5개 질문의 출처 기반 응답을 검증했습니다. 아래는 historical evidence이며 current live state를 보장하지 않습니다.

| # | 질문 | 검색결과 | 출처 | 대표 출처 |
|---|------|---------|------|----------|
| 1 | 고시공고는 어디서 봐? | 1건 | 1건 | 고시·공고/입법예고 |
| 2 | 정보공개는 어디서 확인해? | 5건 | 5건 | 계약정보공개시스템, 정보공개청구현황 |
| 3 | 시청 조직도는 어디서 봐? | 5건 | 5건 | 시청안내, 어린이시청 |
| 4 | 민원 신청은 어디서 해? | 5건 | 5건 | 광주통합민원 바로응답, 민원신청 |
| 5 | 복지 지원사업은 어디서 확인해? | 5건 | 5건 | 광주복지플랫폼, 금융복지지원센터 |

- 이 historical 결과에서 질문은 `gwangju.go.kr` 도메인의 출처를 반환했습니다.
- 조사 스트립, 가운뎃점 정규화, N-gram fallback 등 한글 검색 강화가 적용되었습니다.

## 테스트 실행

```bash
PYTHONPATH=. .venv/bin/python -m pytest tests/ -v
```

- 전체 테스트는 API 키 없이 실행 가능합니다 (`mock`, `stub` 프로바이더 사용).
- `tests/fixtures/bukgu_gwangju_demo_snapshot.json` 파일을 스냅샷 테스트에 활용합니다.
- Provider live-only tests are opt-in and skipped by default. They require explicit `RUN_LIVE_*_TESTS=1` flags in addition to API keys. See `docs/provider-fetch-network-boundary.md` for details.
- Repository `MVP Contract Checks` routine CI는 provider/official-site network 없이 재현 가능해야 합니다.

## Cloudflare Pages AI MVP 배포

400-ai-finder는 **두 가지 build mode**를 지원합니다. Git merge와 실제 Production runtime activation/config는 서로 다른 상태입니다.

### 배포 방식 구분

| 구분 | 설명 |
|------|------|
| **Python 로컬/서버 데모** | `src/web` 기반 Python 서버. live path는 operator/network policy를 따라 별도 실행 |
| **Cloudflare Pages AI build** | Pages Function 포함 build. 코드 기본 resident attempt plan은 Gemini 3.5 primary → Gemini 3.1 same-provider fallback |
| **Cloudflare Pages 정적 시연** | `--mode static` 전용 비상·회귀검증 모드. 백엔드 없이 결정형 스냅샷 사용 |

### Cloudflare AI runtime 코드 계약

현재 `functions/api/mvp/ask.js` 코드 기본값:

```text
MVP_LLM_ORDER default: gemini
Gemini primary:  gemini-3.5-flash-lite
Gemini fallback: gemini-3.1-flash-lite
Hy3: supported legacy/optional provider, default order에는 없음
```

- Default resident path에는 `GEMINI_API_KEY`가 필요합니다.
- `GEMINI_MODEL`은 primary model override, `GEMINI_FALLBACK_MODEL`은 fallback model override입니다.
- `KILOCODE_API_KEY`는 operator가 `MVP_LLM_ORDER`에 Hy3를 명시적으로 포함하는 optional path에서만 관련됩니다.
- 같은 Gemini provider의 model fallback과 cross-provider fallback은 telemetry에서 구분합니다.
- 실제 Cloudflare Production env에 `GEMINI_MODEL`, `GEMINI_FALLBACK_MODEL`, `MVP_LLM_ORDER`, `MVP_AI_MODE`가 어떤 값으로 설정되어 있는지는 repository code만으로 확정하지 않습니다.
- `MVP_AI_MODE=snapshot_only` 또는 `disabled`는 model provider call을 차단하는 운영 경계입니다.

자세한 current contract는 [`docs/operations/MVP_AI_RUNTIME_CONTRACT.md`](docs/operations/MVP_AI_RUNTIME_CONTRACT.md)를 참고하십시오.

```bash
# Pages Function 포함 기본 build
python3 scripts/build_cloudflare_pages.py

# 오프라인 정적 fallback
python3 scripts/build_cloudflare_pages.py --mode static
```

### Pages deployment topology

`dist/cloudflare-pages/`는 build 산출물이며 **Git에 커밋하지 않습니다** (`.gitignore` 추적 제외). Cloudflare Pages Git integration의 deployment와 repository merge는 별도 상태이므로, public URL만 보고 deployed SHA나 runtime env를 추정하지 않습니다.

| 항목 | 저장소/기존 Pages 기준 |
|---|---|
| Project name | `cgbukku` |
| Connected repository | `skerishKang/400-ai-finder` |
| Production branch | `main` |
| Build command | `python3 scripts/build_cloudflare_pages.py` |
| Build output directory | `dist/cloudflare-pages` |
| Framework preset | None |

**Known project URL:** `https://cgbukku.pages.dev/`

### public 경로

| 경로 | 설명 |
|---|---|
| `/` | 정적 랜딩 페이지 (MVP 카드 포함) |
| `/mvp/` | 시민 첫 화면 및 Buk-gu golden AI Browser entry |
| `/mobile` | 모바일 챗 데모 (`/mobile.html` → 308 redirect) |
| `/admin` | 운영자 화면 (`/admin.html` → 308 redirect) |

### GitHub Actions: Deploy가 아닌 Contract/Test입니다

`.github/workflows/mvp-contracts.yml`의 **"MVP Contract Checks"**는 배포 워크플로가 **아닙니다**. 이 workflow는 contract/browser/build/security 검증을 수행하며 routine CI에서 외부 provider·공식사이트 live network를 요구하지 않습니다.

배포는 GitHub Actions contract workflow와 별도입니다. 실제 deployed SHA는 Cloudflare Pages deployment metadata로 확인합니다.

### 정적 시연 확인 (read-only)

public URL read-only smoke 예시:

```text
curl -sI https://cgbukku.pages.dev/
curl -sI https://cgbukku.pages.dev/mvp/
curl -sI https://cgbukku.pages.dev/mobile
curl -sI https://cgbukku.pages.dev/admin
```

**참고**: public URL 응답만으로 latest deployed commit SHA나 environment binding 값을 확정할 수 없습니다.

### Network / acquisition boundaries

- 정적 모드는 `--mode static`으로 계속 제공되며 CI와 오프라인 fallback 검증에 사용합니다.
- public target URL 또는 site profile이 존재한다는 사실은 live crawl/fetch authorization이 아닙니다.
- 공식사이트 reference collection, crawling, screenshot comparison, Firecrawl, provider-assisted retrieval 등 external network 작업은 applicable controlled read-only / provider-staging 경계와 명시적 opt-in을 따릅니다.
- 실제 site control, login, submission, payment, PII processing은 별도의 authorized first-party integration gate입니다.
- Cloudflare 배포 제어와 secrets/env 변경은 운영권한이 있는 별도 deployment 작업입니다.

더 자세한 내용은 [`docs/provider-fetch-network-boundary.md`](docs/provider-fetch-network-boundary.md), [`docs/implementation/RELEASE_GATES.md`](docs/implementation/RELEASE_GATES.md)를 참고하세요.

### MVP demo docs

- [MVP demo operator runbook](docs/mvp-demo-operator-runbook.md) — how to run, verify, and present the five locked local/static resident-task flows.
- [MVP golden quest fidelity matrix](docs/mvp-golden-quest-fidelity-matrix.md) — locked quest IDs, official paths, local/static boundaries, stop behavior, E2E verifier references, and prohibited regressions.
- [MVP demo milestone snapshot](docs/mvp-demo-milestone-snapshot.md) — one-page closeout summary of the completed local/static MVP scope, locked quest set, verification references, and deferred live/production epics.
- [Hybrid scripted + LLM fallback architecture intent](docs/hybrid-scripted-llm-architecture-intent.md) — historical/intended hybrid architecture reference; current provider contract is documented separately.
- [Live transition decision record](docs/live-transition-decision-record.md) — decision gate for live/provider/API/network and operational integration; document existence is not live-work authorization.
- [Official-site route inventory plan](docs/official-site-route-inventory-plan.md) — planning-only schema and classification guide.
- [Official-site route inventory workflow index](docs/official-site-route-inventory-workflow-index.md) — planning-only route-inventory workflow index.
- [Official-site route inventory planning package closeout](docs/official-site-route-inventory-planning-closeout.md) — historical planning closeout.

### Operator quickstart

실행 흐름, 데모, smoke eval, live provider 사용법은 다음 문서를 참고하십시오:

- [`docs/operator-quickstart.md`](docs/operator-quickstart.md) — 운영자 빠른 안내서
- [`docs/operator-question-log-guide.md`](docs/operator-question-log-guide.md) — sanitized log collection + dry-run analytics
- [`docs/scenario-cache-promotion-review-workflow.md`](docs/scenario-cache-promotion-review-workflow.md) — scenario/cache/retrieval-gap human review workflow
- [`docs/promotion-candidate-review-template.md`](docs/promotion-candidate-review-template.md) — promotion candidate review template
- [`docs/operator-synthetic-promotion-dry-run.md`](docs/operator-synthetic-promotion-dry-run.md) — synthetic promotion dry-run
- [`docs/smoke-eval-flow.md`](docs/smoke-eval-flow.md) — Smoke eval CLI flow
- [`docs/bukgu-live-demo-package.md`](docs/bukgu-live-demo-package.md) — historical/demo live LLM package; current live authorization is separate
- [`docs/operator-controlled-retrieval-gap-validation.md`](docs/operator-controlled-retrieval-gap-validation.md) — controlled retrieval-gap validation
- [`docs/bukgu-demo-one-page-handout.md`](docs/bukgu-demo-one-page-handout.md) — Buk-gu demo handout
- [`docs/bukgu-demo-presentation-outline.md`](docs/bukgu-demo-presentation-outline.md) — Buk-gu demo presentation outline
- [`docs/artifacts/400-ai-finder-bukgu-demo.pptx`](docs/artifacts/400-ai-finder-bukgu-demo.pptx) — Buk-gu demo PPT artifact

### Product design

- [`docs/product/dynamic-retrieval-query-learning-strategy.md`](docs/product/dynamic-retrieval-query-learning-strategy.md) — Dynamic Retrieval + Query Learning Strategy
- [`docs/product/repeated-question-analytics-promotion-plan.md`](docs/product/repeated-question-analytics-promotion-plan.md) — Repeated-Question Analytics and Scenario-Cache Promotion Plan

### Repeated-question analytics dry-run (Stage 353)

```bash
PYTHONPATH=. .venv/bin/python scripts/analyze_question_logs.py \
    --input question-log.jsonl \
    --output repeated-question-report.md
```

Reads sanitized JSONL question logs and produces a Markdown report separating promotion candidates from retrieval gaps. Dry-run only — no scenarios, snapshots, caches, PRs, or commits are created.

## Buk-gu golden / Exact Official-Site Clone

왼쪽 시민 사이트 화면은 캡처된 광주광역시 북구청 공식 페이지를 그대로 복제한다. 이 literal은 Buk-gu golden 및 `exact` 상태의 canonical contract를 보존한다.

Buk-gu golden 및 향후 `exact`를 명시적으로 주장하는 promotion surface에는 [canonical exact-clone invariant](docs/product/exact-official-site-clone-invariant.md)가 적용됩니다.

- 공식 페이지의 내용·구조·표·행·순서·컨트롤·시각 표현을 그대로 보존합니다.
- 현재 manifest에 `capture_required`가 남아 있는 route를 exact 완료라고 주장하지 않습니다.
- generated onboarding preview는 별도 non-exact/non-default 상태이며 exact completion 증거가 아닙니다.
- exact/resident-default promotion을 요청하면 applicable fixture/visual approval requirements를 모두 충족해야 합니다.

관련 자료:

- Canonical invariant: [docs/product/exact-official-site-clone-invariant.md](docs/product/exact-official-site-clone-invariant.md)
- Visual promotion policy: [docs/product/clone-visual-fidelity-and-promotion-policy.md](docs/product/clone-visual-fidelity-and-promotion-policy.md)
- 공식 페이지 fixture manifest: [tests/fixtures/official_site_clone_manifest.json](tests/fixtures/official_site_clone_manifest.json)
- 계약 테스트: [tests/test_exact_official_site_clone_invariant.py](tests/test_exact_official_site_clone_invariant.py)
