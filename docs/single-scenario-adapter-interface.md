# Single-Scenario Adapter Interface

Stage 73 documents the Stage 72 adapter interface skeleton. Stage 75 adds the Stage 74 real adapter placeholder boundary.

This document is documentation-only. It does not add execution behavior.

## Current files

| File | Role |
|---|---|
| `scripts/single_live_smoke_adapter.py` | Adapter selection helper. Currently selects only the fake adapter. |
| `scripts/single_live_smoke_fake_adapter.py` | Deterministic offline payload builder. |
| `scripts/single_live_smoke_real_adapter.py` | Future real adapter placeholder. Importable, but raises if called. |
| `scripts/run_single_live_smoke_dry.py` | One-scenario dry runner that now calls the adapter helper. |
| `tests/test_single_live_smoke_adapter.py` | Contract tests for adapter selection. |
| `tests/test_single_live_smoke_real_adapter_placeholder.py` | Contract tests proving the placeholder is inert. |

## Current behavior

The default adapter name is `fake-single-scenario-live-adapter`.

`get_single_scenario_adapter()` returns the fake adapter only.

Unsupported adapter names raise `SingleLiveSmokeAdapterError`.

The real placeholder name is `real-single-scenario-live-adapter`, but that name is not selectable through the adapter helper yet.

Calling `build_real_single_live_result_payload()` raises `SingleLiveSmokeRealAdapterNotImplementedError`.

The dry runner still produces one Stage 62-compatible payload, writes it through the Stage 60 writer, exports through the Stage 58 helper, and is judged only against the matching single-scenario slice.

## Boundary

Stage 72 adds an interface seam. Stage 74 adds an inert placeholder. Neither stage adds a broader execution path.

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
