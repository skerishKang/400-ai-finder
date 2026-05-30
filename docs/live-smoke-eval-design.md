# Live Smoke Eval Design

이 문서는 400-ai-finder의 기존 오프라인 평가(Offline Smoke Eval) 체계를 확장하여 실제 라이브 환경(Live Provider 및 Fetch)을 연결하고 품질을 평가하기 위한 라이브 스모크 평가 모드(Live Smoke Eval Mode) 설계서입니다.

## 1. 배경 및 필요성

현재까지 구축된 스모크 평가 프레임워크는 사전에 정의된 시나리오와 모의 응답(Response Fixture)만을 사용하여 오프라인 환경에서 게이트를 평가했습니다. 
하지만 실제 서비스 운영과 LLM/크롤러 파이프라인의 실시간 성능 검증을 위해서는 실제 외부 API 및 웹페이지 Fetch 작업을 수반하는 실시간 평가(Live Eval)가 필요합니다.
라이브 환경은 네트워크 지연, API 레이트 리밋, 크롤러 차단 및 LLM 응답 불일치(Flakiness) 위험이 상존하므로, 안전하게 오프라인 평가와 격리하여 점진적으로 확장해야 합니다.

## 2. 설계 원칙 및 경계 정의

1. **오프라인과 라이브 평가의 명확한 격리 (Offline-by-Default)**
   - 기본 평가는 항상 완전한 오프라인 환경에서 동작합니다.
   - 라이브 평가는 오프라인 품질 통과 상태에서 실행되어야 하며, 개발자나 CI 파이프라인의 명시적인 opt-in이 있을 때만 가동됩니다.
2. **명시적 Opt-In 실행 모델**
   - 평가 스크립트 실행 시 `--live` 옵션을 지정하거나, `AI_FINDER_LIVE_EVAL=true` 환경 변수를 주입해야만 라이브 파이프라인이 구동됩니다.
3. **일관성 있는 평가 데이터 규격 (Compatible Output Shape)**
   - 라이브 평가의 결과물 역시 Stage 42에서 정의된 `smoke_eval_responses.json` 형식(또는 Stage 43 export 규격)과 100% 동일한 구조를 가집니다.
   - 기존의 `run_smoke_eval.py`의 판정 로직(`evaluate_response_fixture`)을 재사용하여 일관된 품질 점수를 산출합니다.

## 3. 설정 및 요구사항 정의

### A. 라이브 Provider 및 API Key 필수 검증
- 라이브 모드가 구동되면 타겟 시나리오의 LLM Provider API Key(예: `OPENCODE_API_KEY`, `NVIDIA_API_KEY`, `OPENGATEWAY_API_KEY` 등) 존재 여부를 먼저 확인합니다.
- API Key가 누락된 경우 즉시 평가가 거부(Crash)되지 않으며, `Pending Configuration` 상태로 처리하여 해당 시나리오를 Failed/Skipped로 온전히 로깅해야 합니다.

### B. Fetch 및 네트워크 타임아웃 요구사항
- 실시간 웹 크롤링(예: `Firecrawl` 등) 수행 시 네트워크 단절 등으로 인해 전체 평가 세션이 행(Hang)에 걸리는 현상을 방지해야 합니다.
- 각 Fetch 요청 당 기본 타임아웃은 최대 15초(또는 Config에 정의된 타임아웃)로 제한하며, 실패 시에는 Fallback 모드로 즉각 전향하여 평가의 연속성을 보장해야 합니다.

## 4. 라이브 평가 실행 흐름

```mermaid
sequenceDiagram
    participant CLI as eval_runner
    participant Opt as Option Validator
    participant Pipeline as Live Pipeline
    participant Judge as Response Judge

    CLI->>Opt: --live 플래그 및 API Key 검사
    alt API Key 누락 또는 --live 미지정
        Opt-->>CLI: 실행 중단 또는 Offline 모드 제한
    else Opt-in 승인
        Opt->>Pipeline: 14개 시나리오 질문 순차 실행
        Pipeline->>Pipeline: Live Fetch & LLM API 호출
        Pipeline-->>CLI: 실시간 결과물(SiteDemoRunner output shape) 수집
        CLI->>CLI: export_pipeline_results_fixture() 변환
        CLI->>Judge: evaluate_response_fixture() 판정
        Judge-->>CLI: Scenario Pass/Fail 통계 산출
        CLI-->>CLI: smoke-report.md (Live) 작성 및 Exit Code 반환
    end
```

## 5. 보안 및 안전장치
- **크롤링 대역폭 제한**: 실시간 평가 중 대상 기관 홈페이지에 가해지는 트래픽 부하를 방지하기 위해, 순차 실행(Single-threaded) 및 요청 간 최소 1~2초의 Delay(Sleep) 주입을 보장해야 합니다.
- **민감 정보 보호**: 라이브 평가 결과 리포트나 디버그 로그 파일에 어떠한 경우에도 외부 API Key, User Session Cookie, Private Endpoint 주소 등이 그대로 노출되어 기록되어서는 안 됩니다.

## 6. 구현 및 배포 로드맵

1. **Stage 46**: 설계 완료 및 검증 (본 단계)
2. **Stage 47**: `--live` CLI 옵션 핸들러 구현 및 Live 시뮬레이션용 Mock 테스트 보강
3. **Stage 48**: 외부 Key 감지 및 안전 조치 적용을 포함한 실제 Live Smoke Eval 결합 검증
