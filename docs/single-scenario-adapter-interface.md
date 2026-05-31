# Single-Scenario Adapter Interface

Stage 73 documents the Stage 72 adapter interface skeleton. Stage 75 adds the Stage 74 real adapter placeholder boundary. Stage 77 notes the Stage 76 selector test coverage. Stage 79 documents the Stage 78 adapter allowlist. Stage 81 documents the Stage 80 adapter name normalization behavior. Stage 83 documents the Stage 82 adapter name type guard. Stage 85 documents the Stage 84 supported-adapter error diagnostics. Stage 87 documents the Stage 86 unsupported adapter error helper extraction.

This document is documentation-only. It does not add execution behavior.

## Current files

| File | Role |
|---|---|
| `scripts/single_live_smoke_adapter.py` | Adapter selection helper. Currently selects only the fake adapter through an explicit allowlist. |
| `scripts/single_live_smoke_fake_adapter.py` | Deterministic offline payload builder. |
| `scripts/single_live_smoke_real_adapter.py` | Future real adapter placeholder. Importable, but raises if called. |
| `scripts/run_single_live_smoke_dry.py` | One-scenario dry runner that now calls the adapter helper. |
| `tests/test_single_live_smoke_adapter.py` | Contract tests for adapter selection, including selector type guarding, selector normalization, centralized unsupported-adapter error construction, supported-adapter error diagnostics, Stage 76 payload-helper selector coverage, and Stage 78 allowlist coverage. |
| `tests/test_single_live_smoke_real_adapter_placeholder.py` | Contract tests proving the placeholder is inert. |

## Current behavior

The default adapter name is `fake-single-scenario-live-adapter`.

Adapter names must be `str` or `None`. Non-string adapter names fail with `SingleLiveSmokeAdapterError` before whitespace normalization.

Adapter names are trimmed before selection. Empty or whitespace-only adapter names use the default fake adapter. Matching remains case-sensitive.

`SUPPORTED_SINGLE_SCENARIO_ADAPTER_NAMES` currently contains only `fake-single-scenario-live-adapter`.

`get_single_scenario_adapter()` returns the fake adapter only.

Unsupported adapter names raise `SingleLiveSmokeAdapterError` and include the current supported adapter list in the error message. The unsupported adapter error message is constructed through `unsupported_single_scenario_adapter_error_message()` so selector branches share the same message format.

The real placeholder name is `real-single-scenario-live-adapter`, but that name is not selectable through the adapter helper yet. Stage 76 also verifies that this name is rejected through `build_single_live_adapter_payload()`, and Stage 78 verifies that this name is not in the supported adapter allowlist.

Calling `build_real_single_live_result_payload()` raises `SingleLiveSmokeRealAdapterNotImplementedError`.

The dry runner still produces one Stage 62-compatible payload, writes it through the Stage 60 writer, exports through the Stage 58 helper, and is judged only against the matching single-scenario slice.

## Boundary

Stage 72 adds an interface seam. Stage 74 adds an inert placeholder. Stage 76 hardens selector tests. Stage 78 adds an explicit allowlist. Stage 80 normalizes adapter names by trimming outer whitespace while preserving case-sensitive matching. Stage 82 rejects non-string adapter names with `SingleLiveSmokeAdapterError` before normalization. Stage 84 improves unsupported adapter diagnostics without adding another selectable adapter. Stage 86 centralizes unsupported adapter error message construction without changing adapter selection. None of these stages add a broader execution path.

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
