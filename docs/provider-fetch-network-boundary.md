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
- `scripts/run_all_demos.py`
- `scripts/run_mobile_demo.py`
- `scripts/run_admin_demo.py`

These scripts have been audited and their guard/policy decisions documented in
the following sections and the live guard coverage matrix below.

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
and static server code. Stage 311 audited the web demo server entrypoints; the
boundary policy is documented in the "Web demo boundary" section below.

## Live guard coverage matrix

The live guard used by `scripts/run_smoke_eval.py` is not a global guard for all
scripts. Other scripts that can cross provider, fetch, network, Firecrawl, or
pipeline boundaries must be audited or hardened separately.

| Script | Possible live/network behavior | Known guard/preflight | Guard test coverage | Current policy / next action |
|---|---|---|---|---|
| `scripts/run_smoke_eval.py` | Yes, live smoke evaluation path | Yes, live guard and preflight | Covered by `tests/test_live_smoke_eval_guard.py` | Keep as the current guarded live path |
| `scripts/run_pipeline.py` | Yes, app pipeline may cross provider/fetch boundaries | Yes, `--allow-live` guard in `main()` | `tests/test_run_pipeline_live_guard.py` | Stage 318: live opt-in guard added. Safe offline path via `--provider mock --fetch-provider mock` |
| `scripts/demo_answer.py` | Yes, demo answer flow may cross provider/fetch boundaries | Yes, `--allow-live` guard in `main()` | `tests/test_demo_answer_live_guard.py` | Stage 326: live opt-in guard added. Safe offline path via `--snapshot` or `--provider mock --fetch-provider mock` |
| `scripts/fetch_url.py` | Yes, fetch utility can cross network/fetch boundaries | Import-safe, default requests live HTTP, fetch-only (Stage 312). Stage 307 decision: no explicit live opt-in guard required in current scope | Stage 311: import-safety locked by `tests/test_fetch_url_import_boundary.py` | Stage 312/307: guard not required (fetch-only CLI, required --url, no PipelineRunner/LLM path). Safe path: `--provider mock` |
| `scripts/diagnose_site.py` | Yes, site diagnostics may cross network/fetch boundaries | Import-safe, default requests live HTTP, fetch-only (Stage 321). Stage 327 decision: no explicit live opt-in guard required in current scope | Stage 323: import-safety locked by `tests/test_diagnose_site_import_boundary.py` | Stage 322: documented. Stage 327: guard not required (fetch-only diagnostics, required --url, no PipelineRunner/LLM path). Safe path: `--provider mock` |
| `scripts/run_all_demos.py` | Yes, web demo wrapper; may cross provider/fetch boundaries through UI/API after server start | Import-safe. Stage 311 decision: no explicit live opt-in guard required in current scope | None yet | Stage 312: documented. No guard required (web demo, user-triggered via browser UI/API after server start, not automatic at script start). Safe path: import only, do not start server |
| `scripts/run_mobile_demo.py` | Yes, web demo wrapper; may cross provider/fetch boundaries through UI/API after server start | Import-safe. Stage 311 decision: no explicit live opt-in guard required in current scope | None yet | Stage 312: documented. No guard required (web demo, user-triggered via browser UI/API after server start, not automatic at script start). Safe path: import only, do not start server |
| `scripts/run_admin_demo.py` | Yes, web demo wrapper; may cross provider/fetch boundaries through UI/API after server start | Import-safe. Stage 311 decision: no explicit live opt-in guard required in current scope | None yet | Stage 312: documented. No guard required (web demo, user-triggered via browser UI/API after server start, not automatic at script start). Safe path: import only, do not start server |

This table records the current boundary status only. Stage 307 does not change
any script behavior, add any guards, or run live network paths.

Future guard hardening should be split by script or boundary.

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

`demo_answer.py` now requires explicit live opt-in for any demo execution path
that can leave the cached/offline or explicit mock boundary.

The cached/offline path `--snapshot` remains allowed without `--allow-live`, and
the explicit offline provider path is `--provider mock --fetch-provider mock`.

All-default demo execution is blocked unless `--allow-live` is passed because
provider/model/preset/fetch-provider defaults can resolve through preset/profile
logic to live LLM and live fetch providers. Live providers and live presets
therefore require `--allow-live`, but this flag does not replace provider-specific
configuration. For example, Firecrawl still requires `FIRECRAWL_API_KEY`, and live
LLM providers still require their own API key configuration.

`demo_answer.py` is import-safe based on the Stage 319 audit: module-level imports
are stdlib-only, and heavier provider/pipeline imports are lazy inside `main()`.
The Stage 326 guard does not change the import-safety status.

The execution boundary is the CLI path: `run_demo()` constructs a
`SiteDemoRunner`, which can call `PipelineRunner.run()`. The CLI requires
`--site-id` and `--question`. The guard runs before `run_demo()` or
`SiteDemoRunner` are reached.

Guard test coverage is provided by `tests/test_demo_answer_live_guard.py`:

| Path | Requires `--allow-live`? |
|---|---|
| `--snapshot` | No (cached/offline path) |
| `--provider mock --fetch-provider mock` | No (explicit offline path) |
| all-default invocation | Yes |
| live LLM provider (`openai_compatible`, `mistral`, `opencode-go`, `groq`, etc.) | Yes |
| live fetch provider (`requests`, `firecrawl`) | Yes |
| preset path (`--preset deepseek-primary`) | Yes |
| `--allow-live` with default path | Yes, permits execution |

Current risk is MEDIUM. The guard is in place, import-safety is locked, and
safe offline paths are documented.

## `scripts/diagnose_site.py` live boundary

Stage 327 decided that `diagnose_site.py` does not currently require an
additional explicit live opt-in guard. The script is a single-purpose fetch
diagnostics CLI: it requires `--url`, does not call `PipelineRunner`, and does
not reach LLM providers. Its default `requests` provider can perform live HTTP,
but live fetch is the expected purpose of this diagnostics tool.

The safe offline path remains `--provider mock`. Firecrawl remains reachable
through `--provider firecrawl` or `--provider all` when `FIRECRAWL_API_KEY` is
configured. Missing Firecrawl configuration can naturally skip or fail that
provider path, but this is not an explicit live opt-in policy.

This risk profile is closer to `fetch_url.py` than to `run_pipeline.py` or
`demo_answer.py`. The decision should be reconsidered only if `diagnose_site.py`
is later used in automation/CI, expands into `PipelineRunner` or LLM provider
behavior, or starts encouraging live network use in normal development tests.

`diagnose_site.py` is import-safe based on the Stage 321 audit. Module-level
imports are stdlib plus import-safe project imports, and import-safety is locked
by `tests/test_diagnose_site_import_boundary.py` (Stage 323).

The execution boundary is the CLI path: `run_diagnostics()` constructs
`SiteDiagnostics`, and `SiteDiagnostics.run()` diagnoses one or more fetch
providers through `_diagnose_provider()`. The CLI requires `--url`.
`--provider` defaults to `None` and resolves through `AI_FINDER_FETCH_PROVIDER`
before falling back to `"requests"`. Therefore, the default execution path uses
the requests fetch provider and can perform live HTTP. The safe offline path is
`--provider mock`. This is a fetch-only diagnostics script: it does not call
`PipelineRunner` and does not reach LLM providers.

Current risk is MEDIUM. Import-safety is locked. The safe offline path is
documented. No additional explicit live opt-in guard is required for the current
scope.

## Web demo boundary

Stage 311 audited the web demo server entrypoints:

- `scripts/run_all_demos.py`
- `scripts/run_mobile_demo.py`
- `scripts/run_admin_demo.py`

These entrypoints are import-safe in the current implementation. Project imports
are lazy and occur inside `main()`, so importing the wrapper modules does not
start a demo server, open a browser, call a provider, fetch a URL, require an API
key, or contact Firecrawl.

The `src.web.*` modules are also import-safe for the current boundary. Their
top-level imports are standard-library-only, and project-specific provider/fetch
work is reached from request handlers rather than module import.

No additional `--allow-live` guard is required for these web demo wrappers in the
current shape. Unlike immediate-execution CLI scripts such as `run_pipeline.py`
and `demo_answer.py`, the web demo wrappers do not automatically run a
provider/fetch pipeline at script start. Live provider/fetch behavior is
user-triggered through browser UI/API requests such as `POST /api/ask` or
`POST /api/test`.

The required `--site-id` argument records explicit user intent to launch a demo
for a selected site. Starting the local demo server is therefore treated as a
web UI boundary, while any live provider/fetch behavior remains behind
user-triggered UI/API actions.

Safe path:

- import the wrapper modules only;
- do not start the demo server;
- do not send browser/API requests to `/api/ask` or `/api/test`;
- do not configure live provider credentials in tests unless a live-only test
  explicitly opts in.

## Firecrawl integration boundary

Stage 330 audited the Firecrawl integration boundary. The Firecrawl provider is
network-free at import time, and provider construction is also network-free: it
only reads configuration such as `FIRECRAWL_API_KEY`. The implementation does not
depend on a Firecrawl SDK; it uses `requests` with a lazy import.

The live boundary is `FirecrawlFetchProvider.fetch()`. That method is the point
where the provider can make a Firecrawl API request through `requests.post()`.
Missing `FIRECRAWL_API_KEY` is handled gracefully by returning
`FetchResult(ok=False)` rather than raising during import or construction.

The fetch provider registry/factory remains informational and network-free.
Looking up or constructing the Firecrawl provider does not itself perform a live
Firecrawl API call. Current tests are mock-based and do not call the real
Firecrawl service.

Firecrawl remains reachable from user-facing scripts only through explicit
provider selection or guarded live execution paths:

- `scripts/fetch_url.py`: `--provider firecrawl`; this remains a conscious
  required-`--url` fetch path, and Stage 312 decided no additional explicit guard
  is required in the current scope.
- `scripts/run_pipeline.py`: `--fetch-provider firecrawl`; this is blocked unless
  `--allow-live` is passed after Stage 318.
- `scripts/demo_answer.py`: `--fetch-provider firecrawl` or profile/preset
  resolution; this is blocked unless `--allow-live` is passed after Stage 326.
  The `--snapshot` path remains cached/offline.
- `scripts/diagnose_site.py`: `--provider firecrawl` or `--provider all`; this is
  a required-`--url` fetch diagnostics path, and Stage 327 decided no additional
  explicit guard is required in the current scope.

`--allow-live` is only an execution opt-in. It does not replace provider-specific
configuration. Firecrawl still requires `FIRECRAWL_API_KEY`.

Current risk is LOW, with a borderline MEDIUM note for the
`diagnose_site.py --provider all` path because that command can include
Firecrawl when `FIRECRAWL_API_KEY` is configured. Live Firecrawl integration
execution remains deferred.

## Provider live test opt-in policy

Provider live-only tests are opt-in. Default pytest runs must remain mock-safe and must not call live provider APIs, even when API key environment variables are present.

API key environment variables alone are not sufficient to run live tests. A live provider test requires both the provider API key and the matching explicit `RUN_LIVE_*_TESTS` flag.

| Provider | API key env var | Required opt-in flag | Default pytest behavior |
| --- | --- | --- | --- |
| Firecrawl | `FIRECRAWL_API_KEY` | `RUN_LIVE_FIRECRAWL_TESTS=1` | skipped |
| KiloCode | `KILOCODE_API_KEY` | `RUN_LIVE_KILOCODE_TESTS=1` | skipped |
| Groq | `GROQ_API_KEY` | `RUN_LIVE_GROQ_TESTS=1` | skipped |
| OpenGateway | `OPENGATEWAY_API_KEY` | `RUN_LIVE_OPENGATEWAY_TESTS=1` | skipped |

This protects local and CI runs from accidental live calls when a developer shell contains stale, invalid, or unrelated API key environment variables.

Default validation should use normal pytest without live opt-in flags. Live provider tests, when intentionally run, must be treated as integration tests and must not be required for routine local validation.

Do not set `RUN_LIVE_*_TESTS=1` in routine local or CI test runs. Do not rely on API key presence as the live-test trigger.

## Future work

Future stages should remain narrow and should not mix unrelated boundaries. Good
candidate follow-up stages include:

- audit provider/fetch mock vs live separation
- add import-safety contract tests for web demo entrypoints (Stage 311 suggested)
