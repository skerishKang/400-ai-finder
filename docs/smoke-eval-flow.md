# Smoke Eval CLI Flow

Stage 40~60에서 구축한 400-ai-finder의 오프라인 smoke eval 흐름을 정리한 문서입니다.

이 평가 흐름은 기본적으로 외부 네트워크, live provider, Firecrawl, 실제 app pipeline 호출을 수행하지 않습니다. 이미 준비된 시나리오 매트릭스, 응답 fixture, demo/pipeline 결과 JSON, mock live smoke response builder, live smoke artifact fixture, 또는 writer-generated live smoke artifact를 사용해 품질 게이트를 반복 검증합니다.

## 평가 흐름 개요

| Stage | 파일/스크립트 | 역할 |
|---|---|---|
| Stage 40 | `tests/fixtures/smoke_scenario_matrix.json` | 평가 시나리오와 pass criteria 정의 |
| Stage 40 | `docs/smoke-scenario-matrix.md` | 사람이 읽는 시나리오 매트릭스 문서 |
| Stage 41 | `scripts/run_smoke_eval.py` | schema-only 검증 및 response judge |
| Stage 42 | `tests/fixtures/smoke_eval_responses.json` | 오프라인 response fixture |
| Stage 42 | `scripts/run_smoke_eval.py --responses` | response fixture pass/fail 평가 |
| Stage 43 | `scripts/export_smoke_responses.py` | demo/pipeline-shaped result를 smoke response fixture로 변환 |
| Stage 51 | `scripts/build_mock_live_smoke_responses.py` | 시나리오 매트릭스 기반 mock live smoke response fixture 생성 |
| Stage 52 | `scripts/build_mock_live_smoke_responses.py --eval` | mock response를 생성한 뒤 기존 response judge로 즉시 dry-run 평가 |
| Stage 54 | `scripts/export_smoke_responses.py --eval` | pipeline/demo-shaped result를 메모리상 fixture로 변환한 뒤 기존 response judge로 즉시 평가 |
| Stage 57 | `tests/fixtures/live_smoke_result_artifact.json` | future live run 결과 artifact shape를 고정하는 정적 fixture |
| Stage 58 | `scripts/export_live_smoke_artifact.py --eval` | live artifact fixture를 Stage 43 pipeline-shaped result로 변환한 뒤 기존 response judge로 즉시 평가 |
| Stage 60 | `scripts/write_live_smoke_artifact.py` | 이미 생성된 result dictionary를 Stage 56/57-compatible live artifact JSON으로 저장 |

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

## 3. Mock live smoke response build

Stage 51의 mock response builder는 `smoke_scenario_matrix.json`을 읽어 Stage 42-compatible response fixture를 생성합니다.

```bash
python scripts/build_mock_live_smoke_responses.py \
  --output /tmp/mock_live_smoke_responses.json
```

이 명령은 실제 live provider, fetch provider, 외부 네트워크, app pipeline을 호출하지 않습니다. 시나리오별 expected domain, expected keywords, fallback 기준만 사용해 오프라인 평가용 mock response fixture를 만듭니다.

출력된 fixture는 기존 response judge에 그대로 넣을 수 있습니다.

```bash
python scripts/run_smoke_eval.py \
  --matrix tests/fixtures/smoke_scenario_matrix.json \
  --responses /tmp/mock_live_smoke_responses.json
```

## 4. Mock smoke eval dry-run

Stage 52의 dry-run 명령은 mock response fixture를 만든 뒤, 같은 프로세스에서 기존 response judge를 즉시 실행합니다.

```bash
python scripts/build_mock_live_smoke_responses.py --eval
```

기대 출력:

```text
Smoke response eval loaded
Evaluated responses: 14
Passed: 14
Failed: 0

Status: response eval passed
```

이 경로는 live smoke eval을 실제로 실행하는 기능이 아닙니다. 목적은 live eval 연결 전에 judge, scenario matrix, response fixture 구조가 서로 맞물리는지 빠르게 확인하는 것입니다.

## 5. Demo/pipeline result export

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

## 6. Pipeline export eval dry-run

Stage 54의 `--eval` 명령은 pipeline/demo-shaped result JSON을 파일로 다시 저장하지 않고, 메모리상에서 Stage 42 response fixture 형식으로 변환한 뒤 기존 response judge를 즉시 실행합니다.

```bash
python scripts/export_smoke_responses.py \
  tests/fixtures/smoke_pipeline_results_roundtrip.json \
  --eval
```

기대 출력:

```text
Smoke response eval loaded
Evaluated responses: 14
Passed: 14
Failed: 0

Status: response eval passed
```

이 경로는 이미 생성된 pipeline/demo-shaped result의 export 호환성과 judge 통과 여부를 한 번에 확인하기 위한 오프라인 dry-run입니다. 실제 provider, fetch provider, 외부 네트워크, app pipeline은 호출하지 않습니다.

다른 matrix 파일로 평가해야 할 때는 `--matrix`를 함께 지정할 수 있습니다.

```bash
python scripts/export_smoke_responses.py \
  /tmp/pipeline_results.json \
  --matrix tests/fixtures/smoke_scenario_matrix.json \
  --eval
```

## 7. Live artifact export eval dry-run

Stage 58의 `--eval` 명령은 Stage 56/57 live smoke result artifact를 Stage 43 pipeline-shaped result로 변환한 뒤 기존 response judge를 즉시 실행합니다.

```bash
python scripts/export_live_smoke_artifact.py \
  tests/fixtures/live_smoke_result_artifact.json \
  --eval
```

기대 출력:

```text
Smoke response eval loaded
Evaluated responses: 14
Passed: 14
Failed: 0

Status: response eval passed
```

이 경로는 실제 live smoke eval을 실행하지 않습니다. 이미 생성된 artifact 또는 정적 fixture가 기존 export/judge 체계와 호환되는지 검증하는 오프라인 dry-run입니다. 실제 provider, fetch provider, 외부 네트워크, app pipeline은 호출하지 않습니다.

변환 결과를 파일로 저장해야 할 때는 `--output`을 사용합니다.

```bash
python scripts/export_live_smoke_artifact.py \
  tests/fixtures/live_smoke_result_artifact.json \
  --output /tmp/live_pipeline_results.json
```

저장된 `/tmp/live_pipeline_results.json`은 Stage 54 명령으로 다시 평가할 수 있습니다.

```bash
python scripts/export_smoke_responses.py \
  /tmp/live_pipeline_results.json \
  --matrix tests/fixtures/smoke_scenario_matrix.json \
  --eval
```

## 8. Live artifact writer dry-run

Stage 60의 writer는 이미 만들어진 result dictionary 또는 pipeline/demo-shaped result JSON을 Stage 56/57-compatible live artifact JSON으로 저장합니다. 이 명령은 live runner가 아니며, provider/fetch/network/app pipeline을 실행하지 않습니다.

```bash
python scripts/write_live_smoke_artifact.py \
  tests/fixtures/smoke_pipeline_results_roundtrip.json \
  --output /tmp/written_live_artifact.json \
  --created-at 2026-05-30T13:15:00Z
```

writer output은 Stage 58 helper로 즉시 재평가할 수 있습니다.

```bash
python scripts/export_live_smoke_artifact.py \
  /tmp/written_live_artifact.json \
  --eval
```

기대 출력:

```text
Smoke response eval loaded
Evaluated responses: 14
Passed: 14
Failed: 0

Status: response eval passed
```

이 roundtrip은 향후 실제 live runner가 결과를 넘기기 전에, artifact writer와 export/judge 경계가 서로 맞는지 확인하는 오프라인 기준선입니다.

## 9. Live preflight check

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

## 10. Offline boundary

이 문서의 평가 흐름은 다음을 하지 않습니다.

* live provider 호출
* Firecrawl 호출
* 외부 홈페이지 네트워크 fetch
* 실제 app pipeline 실행
* Admin/mobile UI 변경

실제 live eval은 별도 Stage에서 `--live` 또는 provider opt-in 방식으로 분리해야 합니다.
`--live`는 여전히 실제 실행되지 않는 guard 상태이며, provider / fetch / network / app pipeline 호출이 전혀 발생하지 않습니다.

## 11. 권장 검증 명령

Smoke eval 관련 변경 후 기본 검증:

```bash
git diff --check
python scripts/run_smoke_eval.py \
  --matrix tests/fixtures/smoke_scenario_matrix.json
python scripts/run_smoke_eval.py \
  --matrix tests/fixtures/smoke_scenario_matrix.json \
  --responses tests/fixtures/smoke_eval_responses.json
python scripts/build_mock_live_smoke_responses.py --eval
python scripts/export_smoke_responses.py \
  tests/fixtures/smoke_pipeline_results_roundtrip.json \
  --eval
python scripts/export_live_smoke_artifact.py \
  tests/fixtures/live_smoke_result_artifact.json \
  --eval
python scripts/write_live_smoke_artifact.py \
  tests/fixtures/smoke_pipeline_results_roundtrip.json \
  --output /tmp/written_live_artifact.json \
  --created-at 2026-05-30T13:15:00Z
python scripts/export_live_smoke_artifact.py \
  /tmp/written_live_artifact.json \
  --eval
pytest tests/test_smoke_eval_runner.py
pytest tests/test_smoke_response_export.py
pytest tests/test_mock_live_smoke_response_builder.py
pytest tests/test_live_smoke_result_artifact.py
pytest tests/test_live_smoke_artifact_export.py
pytest tests/test_live_smoke_artifact_writer.py
pytest
```

## 12. 다음 단계 후보

Stage 60 이후에는 다음 중 하나로 확장할 수 있습니다.

1. 실제 provider/fetch 호출 전용 `--live` opt-in 구현
2. live runner가 Stage 60 writer에 넘길 최소 result payload contract 추가
3. live artifact writer 결과를 Stage 58 helper로 재평가하는 저장/검증 명령 묶음 추가
4. Admin dashboard에 eval result import/export 기능 추가
5. demo/pipeline result fixture builder 보강

권장 순서는 실제 live 호출을 바로 넓게 붙이는 것이 아니라, 현재의 mock dry-run, pipeline export eval dry-run, live artifact export eval dry-run, writer dry-run 경로를 기준선으로 유지한 상태에서 provider/fetch opt-in, 실행 결과 artifact writer, judge 연결을 각각 별도 Stage로 분리하는 것입니다.
