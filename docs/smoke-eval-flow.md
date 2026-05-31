# Smoke Eval CLI Flow

Stage 40~66에서 구축한 400-ai-finder의 오프라인 smoke eval 흐름을 정리한 문서입니다.

이 평가 흐름은 기본적으로 외부 네트워크, live provider, Firecrawl, 실제 app pipeline 호출을 수행하지 않습니다. 이미 준비된 시나리오 매트릭스, 응답 fixture, demo/pipeline 결과 JSON, mock live smoke response builder, live smoke artifact fixture, writer-generated live smoke artifact, future live runner payload fixture, 또는 single-scenario live smoke dry-run artifact를 사용해 품질 게이트를 반복 검증합니다.

## 평가 흐름 개요

| Stage | 파일/스크립트 | 역할 |
|---|---|---|
| Stage 40 | `tests/fixtures/smoke_scenario_matrix.json` | 평가 시나리오와 pass criteria 정의 |
| Stage 40 | `docs/smoke-scenario-matrix.md` | 사람이 읽는 시나리오 매트릭스 문서 |
| Stage 41 | `scripts/run_smoke_eval.py` | schema-only 검증 및 response judge |
| Stage 42 | `tests/fixtures/smoke_eval_responses.json` | 오프라인 response fixture |
| Stage 43 | `scripts/export_smoke_responses.py` | demo/pipeline-shaped result를 smoke response fixture로 변환 |
| Stage 51 | `scripts/build_mock_live_smoke_responses.py` | 시나리오 매트릭스 기반 mock live smoke response fixture 생성 |
| Stage 52 | `scripts/build_mock_live_smoke_responses.py --eval` | mock response를 생성한 뒤 기존 response judge로 즉시 dry-run 평가 |
| Stage 54 | `scripts/export_smoke_responses.py --eval` | pipeline/demo-shaped result를 메모리상 fixture로 변환한 뒤 기존 response judge로 즉시 평가 |
| Stage 57 | `tests/fixtures/live_smoke_result_artifact.json` | future live run 결과 artifact shape를 고정하는 정적 fixture |
| Stage 58 | `scripts/export_live_smoke_artifact.py --eval` | live artifact fixture를 Stage 43 pipeline-shaped result로 변환한 뒤 기존 response judge로 즉시 평가 |
| Stage 60 | `scripts/write_live_smoke_artifact.py` | 이미 생성된 result dictionary를 Stage 56/57-compatible live artifact JSON으로 저장 |
| Stage 62 | `tests/fixtures/live_runner_result_payloads.json` | future live runner가 Stage 60 writer에 넘길 최소 result payload contract 고정 |
| Stage 62 | `tests/test_live_runner_result_payload_contract.py` | payload fixture, writer artifact build, export/judge roundtrip 검증 |
| Stage 65 | `scripts/run_single_live_smoke_dry.py` | 실제 호출 없이 단일 scenario dry payload와 artifact 생성 |
| Stage 65 | `tests/test_single_live_smoke_dry.py` | 단일 scenario 경계, payload shape, writer/export/judge slice 검증 |

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

단, 전체 matrix 기준 Stage 42 eval을 통과하려면 `smoke_scenario_matrix.json`에 있는 모든 scenario_id에 대한 response가 있어야 합니다.

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

이 roundtrip은 향후 실제 live runner가 결과를 넘기기 전에, artifact writer와 export/judge 경계가 서로 맞는지 확인하는 오프라인 기준선입니다.

## 9. Live runner result payload contract

Stage 62의 `tests/fixtures/live_runner_result_payloads.json`는 future live runner가 Stage 60 writer에 넘겨야 할 최소 result payload shape를 고정합니다. 이 fixture 자체도 실제 live runner 출력이 아니라 오프라인 계약 fixture입니다.

각 result는 다음 필드를 반드시 포함해야 합니다.

| Field | Required | Description |
|---|---:|---|
| `scenario_id` | yes | `tests/fixtures/smoke_scenario_matrix.json`의 scenario id와 일치해야 합니다. |
| `site_id` | yes | 실행 대상 site profile id입니다. |
| `query` | yes | scenario 질문 원문입니다. |
| `status` | yes | `answered`, `fallback`, `error`, `skipped`, `pending_configuration` 중 하나입니다. |
| `answer` | yes | 정규화된 사용자-facing 답변입니다. |
| `sources` | yes | 정규화된 source 배열입니다. fallback/error에서는 빈 배열이 가능합니다. |
| `fallback_used` | yes | fallback 사용 여부입니다. |
| `ok` | yes | runner-level 성공 여부입니다. |
| `answer_ok` | yes | judge 변환에 사용할 수 있는 답변인지 여부입니다. |

`timing_ms`와 `diagnostics`는 Stage 56/60 live artifact에는 포함될 수 있지만, Stage 62의 최소 runner payload contract에서는 필수 필드가 아닙니다.

Stage 62 contract test는 다음 roundtrip을 검증합니다.

```text
live_runner_result_payloads.json
  -> Stage 60 writer
  -> Stage 56/57-compatible live artifact
  -> Stage 58 export helper
  -> Stage 43 pipeline-shaped result
  -> Stage 42 response judge
```

권장 targeted 검증 명령:

```bash
pytest tests/test_live_runner_result_payload_contract.py
```

## 10. Single-scenario live smoke dry-run

Stage 65의 `scripts/run_single_live_smoke_dry.py`는 future live runner의 아주 좁은 골격입니다. 이 명령은 **정확히 하나의 scenario id만** 받습니다. `all`, `*` 같은 전체 실행 shortcut은 거부됩니다.

```bash
python scripts/run_single_live_smoke_dry.py \
  --scenario-id bukgu-01 \
  --output /tmp/single_live_dry_artifact.json \
  --created-at 2026-05-30T15:00:00Z
```

이 명령이 하는 일은 다음뿐입니다.

```text
one scenario id
  -> deterministic offline dummy payload
  -> Stage 62-compatible result payload
  -> Stage 60 writer
  -> Stage 56/57-compatible live artifact
```

이 명령이 하지 않는 일은 다음과 같습니다.

* 전체 14개 scenario 실행
* live provider 호출
* fetch provider 호출
* Firecrawl 호출
* 외부 홈페이지 네트워크 fetch
* 실제 app pipeline 실행

Stage 65 dry artifact는 Stage 58 helper를 통해 pipeline-shaped result로 변환할 수 있습니다.

```bash
python scripts/export_live_smoke_artifact.py \
  /tmp/single_live_dry_artifact.json \
  --output /tmp/single_live_pipeline_result.json
```

단일 artifact는 결과가 1개뿐이므로 전체 14개 matrix에 대해 `--eval`을 직접 실행하면 나머지 scenario가 누락됩니다. Stage 65 테스트는 단일 scenario slice에 기존 judge를 적용해 경계를 검증합니다.

권장 targeted 검증 명령:

```bash
pytest tests/test_single_live_smoke_dry.py
```

관련 회귀 검증:

```bash
pytest tests/test_live_runner_result_payload_contract.py \
  tests/test_live_smoke_artifact_writer.py \
  tests/test_live_smoke_artifact_export.py
```

## 11. Live preflight check

Stage 48/64의 preflight command는 future live smoke eval 구성을 점검하는 guard입니다.

```bash
python scripts/run_smoke_eval.py --live-preflight
```

이 명령은 필요한 configuration 이름이 set인지 missing인지만 출력합니다. 값 자체를 출력해서는 안 됩니다.

예시:

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

값이 있을 때도 report는 `set`/`missing`만 보여야 합니다.

```bash
AI_FINDER_LIVE_EVAL=true \
AI_FINDER_LIVE_PROVIDER=dummy-provider \
AI_FINDER_LIVE_FETCH_PROVIDER=dummy-fetch \
python scripts/run_smoke_eval.py --live-preflight
```

`--live`는 여전히 guarded and non-executing 상태입니다. opt-in이 있어도 전체 live smoke eval execution은 아직 구현되지 않았습니다.

## 12. Offline boundary

이 문서의 평가 흐름은 다음을 하지 않습니다.

* live provider 호출
* fetch provider 호출
* Firecrawl 호출
* 외부 홈페이지 네트워크 fetch
* 실제 app pipeline 실행
* 전체 14개 live scenario 실행
* Admin/mobile UI 변경

실제 live eval은 별도 Stage에서 `--live` 또는 provider opt-in 방식으로 분리해야 합니다. 현재 `--live`는 여전히 실제 실행되지 않는 guard 상태이며, Stage 65 dry runner도 단일 scenario offline artifact만 생성합니다.

## 13. 권장 검증 명령

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
python scripts/run_single_live_smoke_dry.py \
  --scenario-id bukgu-01 \
  --output /tmp/single_live_dry_artifact.json \
  --created-at 2026-05-30T15:00:00Z
pytest tests/test_smoke_eval_runner.py
pytest tests/test_smoke_response_export.py
pytest tests/test_mock_live_smoke_response_builder.py
pytest tests/test_live_smoke_result_artifact.py
pytest tests/test_live_smoke_artifact_export.py
pytest tests/test_live_smoke_artifact_writer.py
pytest tests/test_live_runner_result_payload_contract.py
pytest tests/test_single_live_smoke_dry.py
pytest
```

## 14. 다음 단계 후보

Stage 66 이후에는 다음 중 하나로 확장할 수 있습니다.

1. single-scenario dry artifact를 CLI 문서/운영 runbook에 연결
2. 실제 provider/fetch 호출 전용 `--live` opt-in 구현 전 추가 safety checklist 보강
3. 실제 provider/fetch 호출을 단일 scenario에만 붙이는 좁은 opt-in stage 추가
4. 단일 scenario live 결과 artifact를 검토한 뒤 순차/rate-limited multi-scenario stage 설계
5. Admin dashboard에 eval result import/export 기능 추가

권장 순서는 실제 live 호출을 바로 넓게 붙이는 것이 아니라, 현재의 mock dry-run, pipeline export eval dry-run, live artifact export eval dry-run, writer dry-run, runner payload contract, single-scenario dry-run을 기준선으로 유지한 상태에서 provider/fetch opt-in과 단일 scenario 실제 호출을 각각 별도 Stage로 분리하는 것입니다.
