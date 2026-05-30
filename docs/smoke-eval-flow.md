# Smoke Eval CLI Flow

Stage 40~43에서 구축한 400-ai-finder의 오프라인 smoke eval 흐름을 정리한 문서입니다.

이 평가 흐름은 기본적으로 외부 네트워크, live provider, Firecrawl, 실제 app pipeline 호출을 수행하지 않습니다. 이미 준비된 시나리오 매트릭스, 응답 fixture, 또는 demo/pipeline 결과 JSON을 사용해 품질 게이트를 반복 검증합니다.

## 평가 흐름 개요

| Stage | 파일/스크립트 | 역할 |
|---|---|---|
| Stage 40 | `tests/fixtures/smoke_scenario_matrix.json` | 평가 시나리오와 pass criteria 정의 |
| Stage 40 | `docs/smoke-scenario-matrix.md` | 사람이 읽는 시나리오 매트릭스 문서 |
| Stage 41 | `scripts/run_smoke_eval.py` | schema-only 검증 및 response judge |
| Stage 42 | `tests/fixtures/smoke_eval_responses.json` | 오프라인 response fixture |
| Stage 42 | `scripts/run_smoke_eval.py --responses` | response fixture pass/fail 평가 |
| Stage 43 | `scripts/export_smoke_responses.py` | demo/pipeline-shaped result를 smoke response fixture로 변환 |

## 1. Schema-only eval

시나리오 매트릭스 구조만 검증합니다.

```bash
python scripts/run_smoke_eval.py \
  --matrix tests/fixtures/smoke_scenario_matrix.json
```

기대 출력:

```text
Smoke scenario matrix loaded
Total scenarios: 14
...
Status: schema-only eval passed
```

이 단계는 질문 실행이나 응답 품질 판단을 하지 않습니다. JSON 구조, scenario 수, site/category 분포, pass criteria 구조가 평가 가능한 상태인지 확인하는 용도입니다.

## 2. Offline response fixture eval

Stage 42의 response fixture를 Stage 41 judge에 넣어 pass/fail을 평가합니다.

```bash
python scripts/run_smoke_eval.py \
  --matrix tests/fixtures/smoke_scenario_matrix.json \
  --responses tests/fixtures/smoke_eval_responses.json
```

기대 출력:

```text
Smoke response eval loaded
Evaluated responses: 14
Passed: 14
Failed: 0

Status: response eval passed
```

실패가 있으면 실패한 scenario와 check 이름이 출력됩니다.

예시:

```text
Failed scenarios:
- bukgu-01: source_domain, no_cross_site_urls

Status: response eval failed
```

## 3. Demo/pipeline result export

`SiteDemoRunner` 또는 유사한 demo/pipeline-shaped result JSON을 Stage 42 response fixture 형식으로 변환합니다.

입력 JSON 예시:

```json
{
  "results": [
    {
      "scenario_id": "bukgu-01",
      "result": {
        "site_id": "bukgu_gwangju",
        "answer": "민원서식은 북구청에서 확인할 수 있습니다.",
        "sources": [
          {
            "title": "민원서식",
            "url": "https://bukgu.gwangju.kr/menu.es"
          }
        ],
        "ok": true,
        "answer_ok": true,
        "fallback_used": false
      }
    }
  ]
}
```

변환 명령:

```bash
python scripts/export_smoke_responses.py \
  /tmp/pipeline_results.json \
  --output /tmp/smoke_responses.json
```

출력된 `/tmp/smoke_responses.json`은 Stage 42 eval에 그대로 넣을 수 있습니다.

```bash
python scripts/run_smoke_eval.py \
  --matrix tests/fixtures/smoke_scenario_matrix.json \
  --responses /tmp/smoke_responses.json
```

단, Stage 42 eval을 통과하려면 `smoke_scenario_matrix.json`에 있는 모든 scenario_id에 대한 response가 있어야 합니다.

## 4. Live preflight check

Stage 48 adds a guarded preflight command for future live smoke eval work.

```bash
python scripts/run_smoke_eval.py --live-preflight
```

This command only reports whether required configuration names are set or missing. It must not print configuration values.

Example output:

```text
Live smoke eval preflight
Live opt-in: disabled
Config names:
- AI_FINDER_LIVE_EVAL: missing
- AI_FINDER_LIVE_PROVIDER: missing
- AI_FINDER_LIVE_FETCH_PROVIDER: missing

Status: preflight completed
No live provider, fetch, network, or pipeline calls were made.
```

With values present:

```bash
AI_FINDER_LIVE_EVAL=true \
AI_FINDER_LIVE_PROVIDER=dummy-provider \
AI_FINDER_LIVE_FETCH_PROVIDER=dummy-fetch \
python scripts/run_smoke_eval.py --live-preflight
```

The report should show `set`/`missing` only. It should not print the actual values.

`--live` remains guarded and non-executing. Even with opt-in enabled, live smoke eval execution is not implemented yet.

## 5. Offline boundary

이 문서의 평가 흐름은 다음을 하지 않습니다.

* live provider 호출
* Firecrawl 호출
* 외부 홈페이지 네트워크 fetch
* 실제 app pipeline 실행
* Admin/mobile UI 변경

실제 live eval은 별도 Stage에서 `--live` 또는 provider opt-in 방식으로 분리해야 합니다.
`--live`는 여전히 실제 실행되지 않는 guard 상태이며, provider / fetch / network / app pipeline 호출이 전혀 발생하지 않습니다.

## 6. 권장 검증 명령

Stage 40~44 관련 변경 후 기본 검증:

```bash
git diff --check
python scripts/run_smoke_eval.py \
  --matrix tests/fixtures/smoke_scenario_matrix.json
python scripts/run_smoke_eval.py \
  --matrix tests/fixtures/smoke_scenario_matrix.json \
  --responses tests/fixtures/smoke_eval_responses.json
pytest tests/test_smoke_eval_runner.py
pytest tests/test_smoke_response_export.py
pytest
```

## 7. 다음 단계 후보

Stage 50 이후에는 다음 중 하나로 확장할 수 있습니다.

1. optional live smoke eval mock adapter 추가
2. 실제 provider/fetch 호출 전용 `--live` opt-in 구현
3. live 실행 결과를 Stage 42 response judge에 연결
4. Admin dashboard에 eval result import/export 기능 추가
5. demo/pipeline result fixture builder 보강

권장 순서는 live 호출을 바로 붙이는 것이 아니라, mock adapter와 dry-run 경로를 먼저 추가한 뒤 provider/fetch opt-in을 별도 Stage로 분리하는 것입니다.
