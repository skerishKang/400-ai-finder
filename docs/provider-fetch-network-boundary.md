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
| `scripts/run_pipeline.py` | Yes, app pipeline may cross provider/fetch boundaries | Yes, `--allow-live` guard in `main()` | `tests/test_run_pipeline_live_guard.py` | Stage 318: live opt-in guard added. Safe offline path via `--provider mock --fetch-provider mock` |
| `scripts/demo_answer.py` | Yes, demo answer flow may cross provider/fetch boundaries | Audited: import-safe but default path may reach live LLM/fetch through preset/profile (Stage 319) | Not established by this document | Stage 320: documented. Follow-up: import-safety test and guard decision |
| `scripts/fetch_url.py` | Yes, fetch utility can cross network/fetch boundaries | Not established by this document | Not established by this document | Audit separately before hardening |
| `scripts/diagnose_site.py` | Yes, site diagnostics may cross network/fetch boundaries | Audited: import-safe, default requests live HTTP, fetch-only (Stage 321) | Not established by this document | Stage 322: documented. Follow-up: import-safety test or guard decision |

This table records the current boundary status only. Stage 307 does not change
any script behavior, add any guards, or run live network paths.

Future guard hardening should be split by script or boundary. Good follow-up
candidates include adding import-safety tests or guard decisions for
`demo_answer.py` and `diagnose_site.py` before adding any new guard behavior.

## `scripts/run_pipeline.py` live boundary

`run_pipeline.py` is import-safe. Importing `scripts.run_pipeline` does not execute the
pipeline and does not call `requests.get()`, `RequestsFetchProvider.fetch()`, or
`FirecrawlFetchProvider.fetch()`. This import boundary is locked by
`tests/test_run_pipeline_import_boundary.py` (Stage 315).

The live/network boundary is the CLI execution path. `main()` parses required
`--url` and `--query` arguments, constructs a `PipelineRunner`, and calls
`PipelineRunner.run()`.

The default LLM provider is safe/offline because `--provider` defaults to
`AI_FINDER_LLM_PROVIDER` or `"mock"`. The fetch boundary is different:
`--fetch-provider` defaults to `AI_FINDER_FETCH_PROVIDER` or `None`; when no fetch
provider is selected, the pipeline can fall back to the direct `requests`-based
crawler path. Therefore, a CLI invocation with a real URL can perform live HTTP
fetching unless the caller explicitly selects the mock fetch provider.

Safe offline usage is available through `--fetch-provider mock`, with the default
mock LLM provider. Firecrawl remains reachable through the Firecrawl fetch
provider and requires `FIRECRAWL_API_KEY`. Live LLM providers such as
OpenAI-compatible providers remain reachable through provider selection and their
own API key configuration.

`run_pipeline.py` now requires explicit live opt-in for any provider/fetch
combination that can leave the offline/mock boundary. The safe no-network CLI
path is `--provider mock --fetch-provider mock`; because the default fetch
provider is `None`, a default CLI invocation is blocked unless `--allow-live` is
passed.

`--allow-live` permits the CLI to reach the existing live fetch/provider paths,
but it does not replace provider-specific API key requirements. For example,
Firecrawl still requires `FIRECRAWL_API_KEY`, and live LLM providers still require
their own API key configuration.

This guard is tested by `tests/test_run_pipeline_live_guard.py` (Stage 318).

## `fetch_url.py` live boundary

`scripts/fetch_url.py` is import-safe. Importing the module does not perform a
provider, fetch, network, Firecrawl, or API call. Network behavior is triggered
from the CLI path when `main()` calls the selected provider's `fetch()` method.

The default provider is `requests`, which performs live HTTP. Provider selection
can be controlled with the `--provider` flag. The mock provider is the safe
offline/no-network path and should be used for local checks that must avoid live
fetching.

`--list-providers` is an informational path and does not require a live fetch.
The Firecrawl provider can be selected, but it requires the `FIRECRAWL_API_KEY`
environment variable and crosses the Firecrawl API boundary.

`fetch_url.py` currently has no dry-run/no-network option and no explicit live
opt-in guard. URL validation for the requests path is handled by
`RequestsFetchProvider`, which accepts `http://` and `https://` URLs and fails
gracefully for invalid schemes.

Current provider tests are offline or mocked. There is no direct `fetch_url.py`
guard or CLI test coverage yet. The current live/network risk is medium: the
default provider is live HTTP, but a user must consciously invoke the CLI with a
URL before network behavior occurs.

### `fetch_url.py` live opt-in decision

`fetch_url.py` does not currently require an additional explicit live opt-in
guard beyond its existing CLI shape.

The decision is based on the current boundary:

- importing `scripts.fetch_url` is network-free
- `--list-providers` is a no-network informational path
- `--provider mock` is the safe offline/no-network path
- live fetch behavior requires a user-provided `--url`
- Firecrawl requires `FIRECRAWL_API_KEY`

Because `--url` is required, a live fetch cannot occur without conscious
user-provided input. This differs from automated live runners such as
`scripts/run_smoke_eval.py`, where broad live evaluation requires an explicit
guard and preflight flow.

Adding another environment-variable opt-in guard to `fetch_url.py` would change
the user-facing CLI behavior and could break existing examples. For the current
risk profile, the documented safe paths and tests are the intended boundary.

This decision does not make live provider, fetch, network, or Firecrawl
execution part of normal tests. Future changes to `fetch_url.py` live opt-in
behavior should be handled in a separate audit/code stage.

## `scripts/demo_answer.py` live boundary

`demo_answer.py` is import-safe based on the Stage 319 audit: module-level imports
are stdlib-only, and heavier provider/pipeline imports are lazy inside `main()`.
The audit did not execute `scripts/demo_answer.py`, the demo answer path, the
pipeline, live fetch, Firecrawl, or live LLM/API providers.

The execution boundary is the CLI path: `run_demo()` constructs a
`SiteDemoRunner`, which can call `PipelineRunner.run()`. The CLI requires
`--site-id` and `--question`. `--provider`, `--model`, `--preset`, and
`--fetch-provider` default to `None`.

The safe cached/offline path is `--snapshot`. A safe explicit provider/fetch path
is also available through `--provider mock --fetch-provider mock`. However, an
all-default invocation can resolve through preset/profile logic: the default
preset path can select a live LLM provider such as `opencode-go`, and
`fetch_provider=None` can resolve through a profile preferred fetch provider such
as `requests`. Therefore, default demo execution can leave the offline/mock
boundary.

`demo_answer.py` currently has no `--dry-run`, `--no-network`, `--allow-live`, or
`--live` flag, and no explicit live opt-in guard. A natural guard may occur when
a selected live provider is not configured, but missing provider configuration is
not a deliberate live opt-in policy. Firecrawl remains reachable through
`--fetch-provider firecrawl` or profile configuration and still requires
`FIRECRAWL_API_KEY`. Live LLM providers remain reachable through `--provider` or
`--preset` and their own API key configuration.

Current direct coverage is incomplete: there are no direct `demo_answer.py`
import-safety or guard tests yet. `SiteDemoRunner` has mocked/offline tests, but
those do not establish a CLI guard for `scripts/demo_answer.py`. Current risk is
MEDIUM-HIGH until a follow-up stage decides whether to add import-safety tests
and/or an explicit live opt-in guard.

## `scripts/diagnose_site.py` live boundary

`diagnose_site.py` is import-safe based on the Stage 321 audit. Module-level
imports are stdlib plus import-safe project imports, and the audit did not
execute `scripts/diagnose_site.py`, site diagnosis, live fetch, Firecrawl, or
API paths.

The execution boundary is the CLI path: `run_diagnostics()` constructs
`SiteDiagnostics`, and `SiteDiagnostics.run()` diagnoses one or more fetch
providers through `_diagnose_provider()`. This is a fetch-only diagnostics script:
it does not call `PipelineRunner` and does not reach LLM providers.

The CLI requires `--url`. `--provider` defaults to `None` and resolves through
`AI_FINDER_FETCH_PROVIDER` before falling back to `"requests"`. Therefore, the
default execution path uses the requests fetch provider and can perform live HTTP.
The safe offline path is `--provider mock`.

Firecrawl remains reachable through `--provider firecrawl`, and can also be
included by `--provider all` when `FIRECRAWL_API_KEY` is configured. Missing
Firecrawl configuration can naturally skip or fail that provider path, but this
is not the same as an explicit live opt-in policy.

`diagnose_site.py` currently has no `--dry-run`, `--no-network`, `--allow-live`,
or `--live` flag, and no explicit live opt-in guard. Current direct coverage is
incomplete: there are no direct `diagnose_site.py` import-safety or guard tests
yet. `SiteDiagnostics` has mocked/offline unit tests, but those do not establish
a CLI guard for `scripts/diagnose_site.py`. Current risk is MEDIUM.

## Future work

Future stages should remain narrow and should not mix unrelated boundaries. Good
candidate follow-up stages include:

- add import-safety tests or guard decisions for `demo_answer.py` and `diagnose_site.py`
- audit Firecrawl integration boundary
- audit provider/fetch mock vs live separation
- audit app pipeline/backend/UI/API behavior separately
