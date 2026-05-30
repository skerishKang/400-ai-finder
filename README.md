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

### 📱 모바일 ChatGPT형 사용자 UI (http://localhost:8400)
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

실행 후 브라우저에서 접속:

- **모바일 사용자 화면**: http://localhost:8400
- **운영자 대시보드**: http://localhost:8090

운영자 대시보드에서는 `--site-id`로 시작한 기본 기관과 별개로, 기관 선택 패널에서 등록된 profile을 골라 `/api/test` 테스트 대상을 전환할 수 있습니다.

### 개별 실행

**모바일 사용자 화면만:**

```bash
PYTHONPATH=. .venv/bin/python scripts/run_mobile_demo.py \
    --site-id bukgu_gwangju \
    --snapshot tests/fixtures/bukgu_gwangju_demo_snapshot.json \
    --port 8400
```

**광주광역시청 모바일 화면:**

```bash
PYTHONPATH=. .venv/bin/python scripts/run_mobile_demo.py \
    --site-id gwangju_go_kr \
    --provider stub \
    --fetch-provider requests \
    --port 8401
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
    --fetch-provider requests
```

### 광주광역시청 — 정보공개 (Live Fetch)

```bash
PYTHONPATH=. .venv/bin/python scripts/demo_answer.py \
    --site-id gwangju_go_kr \
    --question "정보공개는 어디서 확인해?" \
    --provider stub \
    --fetch-provider requests
```

### 광주광역시청 — 복지 지원사업 (Live Fetch)

```bash
PYTHONPATH=. .venv/bin/python scripts/demo_answer.py \
    --site-id gwangju_go_kr \
    --question "복지 지원사업은 어디서 확인해?" \
    --provider stub \
    --fetch-provider requests
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
