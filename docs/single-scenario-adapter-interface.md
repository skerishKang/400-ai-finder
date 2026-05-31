# Single-Scenario Adapter Interface

Stage 73 documents the Stage 72 adapter interface skeleton. Stage 75 adds the Stage 74 real adapter placeholder boundary. Stage 77 notes the Stage 76 selector test coverage. Stage 79 documents the Stage 78 adapter allowlist. Stage 81 documents the Stage 80 adapter name normalization behavior. Stage 83 documents the Stage 82 adapter name type guard. Stage 85 documents the Stage 84 supported-adapter error diagnostics. Stage 87 documents the Stage 86 unsupported adapter error helper extraction. Stage 89 documents the Stage 88 padded adapter rejection coverage. Stage 91 documents the Stage 90 payload-helper normalized adapter rejection coverage. Stage 93 documents the Stage 92 whitespace-only payload-helper default adapter coverage. Stage 95 documents the Stage 94 explicit None payload-helper default adapter coverage. Stage 97 documents the Stage 96 explicit None selector default adapter coverage. Stage 99 documents the Stage 98 whitespace-only selector default adapter coverage. Stage 101 documents the Stage 100 empty-string selector function coverage. Stage 103 documents the Stage 102 supported-adapter payload-helper coverage. Stage 105 documents the Stage 104 padded supported-adapter payload-helper coverage. Stage 107 documents the Stage 106 payload-helper case-sensitive adapter rejection coverage. Stage 109 documents the Stage 108 padded uppercase payload-helper rejection coverage. Stage 111 documents the Stage 110 padded uppercase direct selector rejection coverage. Stage 113 documents the Stage 112 real adapter placeholder error-message coverage. Stage 115 documents the Stage 114 real adapter placeholder error hierarchy coverage. Stage 117 documents the Stage 116 real adapter base NotImplementedError catch coverage. Stage 119 documents the Stage 118 real adapter no-mutation coverage. Stage 121 documents the Stage 120 real adapter deep no-mutation coverage. Stage 123 documents the Stage 122 real adapter shape-agnostic failure coverage. Stage 125 documents the Stage 124 real adapter no-scenario-inspection coverage.

This document is documentation-only. It does not add execution behavior.

## Current files

| File | Role |
|---|---|
| `scripts/single_live_smoke_adapter.py` | Adapter selection helper. Currently selects only the fake adapter through an explicit allowlist. |
| `scripts/single_live_smoke_fake_adapter.py` | Deterministic offline payload builder. |
| `scripts/single_live_smoke_real_adapter.py` | Future real adapter placeholder. Importable, but raises if called. |
| `scripts/run_single_live_smoke_dry.py` | One-scenario dry runner that now calls the adapter helper. |
| `tests/test_single_live_smoke_adapter.py` | Contract tests for adapter selection, including selector type guarding, selector normalization, padded non-allowlisted adapter rejection, centralized unsupported-adapter error construction, supported-adapter error diagnostics, Stage 76 payload-helper selector coverage, Stage 78 allowlist coverage, Stage 90 payload-helper normalized rejection coverage, Stage 92 whitespace-only payload-helper default coverage, Stage 94 explicit None payload-helper default coverage, Stage 96 explicit None selector default coverage, Stage 98 whitespace-only selector default coverage, Stage 100 empty-string selector function coverage, Stage 102 supported-adapter payload-helper coverage, Stage 104 padded supported-adapter payload-helper coverage, Stage 106 payload-helper case-sensitive rejection coverage, Stage 108 padded uppercase payload-helper rejection coverage, and Stage 110 padded uppercase direct selector rejection coverage. |
| `tests/test_single_live_smoke_real_adapter_placeholder.py` | Contract tests proving the placeholder is inert, including Stage 112 exact error-message coverage, Stage 114 error hierarchy coverage, Stage 116 base NotImplementedError catch coverage, Stage 118 no-mutation coverage, Stage 120 deep no-mutation coverage, Stage 122 shape-agnostic failure coverage, and Stage 124 no-scenario-inspection coverage. |

## Current behavior

The default adapter name is `fake-single-scenario-live-adapter`.

Adapter names must be `str` or `None`. Non-string adapter names fail with `SingleLiveSmokeAdapterError` before whitespace normalization.

Adapter names are trimmed before selection. Empty or whitespace-only adapter names use the default fake adapter in both direct selector and payload-helper paths. The direct selector returns the fake adapter function for an explicit empty-string adapter name. Explicit `None` adapter names also use the default fake adapter. Passing the supported fake adapter name explicitly through `build_single_live_adapter_payload()` returns the fake payload, including when the supported name has outer whitespace. Matching remains case-sensitive in both direct selector and payload-helper paths, so an uppercase form of the supported fake adapter name is rejected rather than silently normalized, including when that uppercase name has outer whitespace. Padded non-allowlisted adapter names are trimmed and then rejected.

`SUPPORTED_SINGLE_SCENARIO_ADAPTER_NAMES` currently contains only `fake-single-scenario-live-adapter`.

`get_single_scenario_adapter()` returns the fake adapter only.

Unsupported adapter names raise `SingleLiveSmokeAdapterError` and include the current supported adapter list in the error message. The unsupported adapter error message is constructed through `unsupported_single_scenario_adapter_error_message()` so selector branches share the same message format.

The real placeholder name is `real-single-scenario-live-adapter`, but that name is not selectable through the adapter helper yet. Stage 76 also verifies that this name is rejected through `build_single_live_adapter_payload()`, Stage 78 verifies that this name is not in the supported adapter allowlist, Stage 88 verifies that padded forms of this name are trimmed and still rejected through direct selector resolution, and Stage 90 verifies the same normalized rejection behavior through the payload helper.

Calling `build_real_single_live_result_payload()` raises `SingleLiveSmokeRealAdapterNotImplementedError`, a `NotImplementedError` subclass that is also catchable through the base `NotImplementedError` type, with the exact message `Real single-scenario adapter is not implemented. Use the fake adapter path.`, without mutating the input scenario, including nested scenario data, before requiring a specific scenario shape, and without inspecting scenario fields.

The dry runner still produces one Stage 62-compatible payload, writes it through the Stage 60 writer, exports through the Stage 58 helper, and is judged only against the matching single-scenario slice.

## Boundary

Stage 72 adds an interface seam. Stage 74 adds an inert placeholder. Stage 76 hardens selector tests. Stage 78 adds an explicit allowlist. Stage 80 normalizes adapter names by trimming outer whitespace while preserving case-sensitive matching. Stage 82 rejects non-string adapter names with `SingleLiveSmokeAdapterError` before normalization. Stage 84 improves unsupported adapter diagnostics without adding another selectable adapter. Stage 86 centralizes unsupported adapter error message construction without changing adapter selection. Stage 88 adds direct selector padded adapter rejection coverage without changing adapter selection. Stage 90 adds payload-helper padded adapter rejection coverage without changing adapter selection. Stage 92 adds payload-helper whitespace-only default adapter coverage without changing adapter selection. Stage 94 adds payload-helper explicit None default adapter coverage without changing adapter selection. Stage 96 adds direct selector explicit None default adapter coverage without changing adapter selection. Stage 98 adds direct selector whitespace-only default adapter coverage without changing adapter selection. Stage 100 adds direct selector empty-string function coverage without changing adapter selection. Stage 102 adds supported-adapter payload-helper coverage without changing adapter selection. Stage 104 adds padded supported-adapter payload-helper coverage without changing adapter selection. Stage 106 adds payload-helper uppercase supported-name rejection coverage without changing adapter selection. Stage 108 adds padded uppercase supported-name payload-helper rejection coverage without changing adapter selection. Stage 110 adds padded uppercase supported-name direct selector rejection coverage without changing adapter selection. Stage 112 adds exact real-adapter placeholder error-message coverage without enabling real adapter execution. Stage 114 adds real-adapter placeholder error hierarchy coverage without enabling real adapter execution. Stage 116 adds base NotImplementedError catch coverage without enabling real adapter execution. Stage 118 adds real-adapter placeholder no-mutation coverage without enabling real adapter execution. Stage 120 adds real-adapter placeholder deep no-mutation coverage without enabling real adapter execution. Stage 122 adds real-adapter placeholder shape-agnostic failure coverage without enabling real adapter execution. Stage 124 adds real-adapter placeholder no-scenario-inspection coverage without enabling real adapter execution. None of these stages add a broader execution path.

The current successful path remains:

```text
one scenario id
  -> adapter helper
  -> fake adapter
  -> Stage 62-compatible payload
  -> Stage 60 writer
  -> Stage 58 export helper
  -> single-scenario judge slice
```

The placeholder path is intentionally blocked:

```text
real adapter placeholder
  -> raises SingleLiveSmokeRealAdapterNotImplementedError
```

The full matrix is not executed by this path.

## Validation

Recommended focused checks:

```bash
git diff --check
pytest tests/test_single_live_smoke_adapter.py
pytest tests/test_single_live_smoke_fake_adapter.py
pytest tests/test_single_live_smoke_real_adapter_placeholder.py
pytest tests/test_single_live_smoke_dry.py
```
