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

## Future work

Future stages should remain narrow and should not mix unrelated boundaries. Good
candidate follow-up stages include:

- audit live/network guard coverage
- audit Firecrawl integration boundary
- audit provider/fetch mock vs live separation
- document or harden individual script opt-in behavior
- audit app pipeline/backend/UI/API behavior separately
