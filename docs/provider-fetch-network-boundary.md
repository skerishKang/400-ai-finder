# Provider / Fetch / Network Boundary

This document records the current boundary between offline/mock development paths
and live provider, fetch, network, Firecrawl, app pipeline, backend, UI, and API
paths.

## Default policy

Normal development and automated tests should use offline or mock paths by
default. Live provider, fetch, network, or Firecrawl calls should require an
explicit opt-in path and must not be triggered accidentally by ordinary test
commands.

API keys, secrets, and external network availability must not be required for
normal unit tests.

## Current guarded live path

`scripts/run_smoke_eval.py` has a live evaluation guard and preflight flow. The
guard behavior is covered by `tests/test_live_smoke_eval_guard.py`.

This guard is specific to the smoke evaluation runner and should not be assumed
to protect every other script.

## Scripts with possible live/network behavior

The following scripts may cross into live provider, fetch, network, or pipeline
behavior and should be treated carefully:

- `scripts/run_pipeline.py`
- `scripts/demo_answer.py`
- `scripts/fetch_url.py`
- `scripts/diagnose_site.py`

Stage 305 does not change these scripts. Their guard behavior should be audited
or hardened in separate follow-up stages.

## Provider and fetch layers

`src/llm/` contains the LLM provider layer, including base, mock, stub,
OpenAI-compatible, and model preset code.

`src/fetch/` contains the fetch provider layer, including base, requests,
Firecrawl, and mock provider code.

`src/fetch/firecrawl_provider.py` is the Firecrawl provider boundary. Current
Firecrawl coverage is not a live integration test; it should not be treated as
proof that live Firecrawl execution is safe or guarded.

Provider and fetch behavior changes should be handled in narrow follow-up stages
after a dedicated audit.

## App pipeline, backend, UI, and API layers

`src/pipeline/` and `scripts/run_pipeline.py` are app pipeline boundaries.

`src/web/` contains backend/API/UI demo boundaries, including mobile/admin demo
and static server code.

Stage 305 does not change app pipeline, backend, UI, or API behavior.

## Live guard coverage matrix

The live guard used by `scripts/run_smoke_eval.py` is not a global guard for all
scripts. Other scripts that can cross provider, fetch, network, Firecrawl, or
pipeline boundaries must be audited or hardened separately.

| Script | Possible live/network behavior | Known guard/preflight | Guard test coverage | Current policy / next action |
|---|---|---|---|---|
| `scripts/run_smoke_eval.py` | Yes, live smoke evaluation path | Yes, live guard and preflight | Covered by `tests/test_live_smoke_eval_guard.py` | Keep as the current guarded live path |
| `scripts/run_pipeline.py` | Yes, app pipeline may cross provider/fetch boundaries | Not established by this document | Not established by this document | Audit separately before hardening |
| `scripts/demo_answer.py` | Yes, demo answer flow may cross provider/fetch boundaries | Not established by this document | Not established by this document | Audit separately before hardening |
| `scripts/fetch_url.py` | Yes, fetch utility can cross network/fetch boundaries | Not established by this document | Not established by this document | Audit separately before hardening |
| `scripts/diagnose_site.py` | Yes, site diagnostics may cross network/fetch boundaries | Not established by this document | Not established by this document | Audit separately before hardening |

This table records the current boundary status only. Stage 307 does not change
any script behavior, add any guards, or run live network paths.

Future guard hardening should be split by script or boundary. Good follow-up
candidates include auditing `scripts/run_pipeline.py` and `scripts/fetch_url.py`
before adding any new guard behavior.

## Future work

Future stages should remain narrow and should not mix unrelated boundaries. Good
candidate follow-up stages include:

- audit live/network guard coverage
- audit Firecrawl integration boundary
- audit provider/fetch mock vs live separation
- document or harden individual script opt-in behavior
- audit app pipeline/backend/UI/API behavior separately
