# Single-Scenario Adapter Interface

Stage 73 documents the Stage 72 adapter interface skeleton.

This document is documentation-only. It does not add execution behavior.

## Current files

| File | Role |
|---|---|
| `scripts/single_live_smoke_adapter.py` | Adapter selection helper. Currently selects only the fake adapter. |
| `scripts/single_live_smoke_fake_adapter.py` | Deterministic offline payload builder. |
| `scripts/run_single_live_smoke_dry.py` | One-scenario dry runner that now calls the adapter helper. |
| `tests/test_single_live_smoke_adapter.py` | Contract tests for adapter selection. |

## Current behavior

The default adapter name is `fake-single-scenario-live-adapter`.

`get_single_scenario_adapter()` returns the fake adapter only.

Unsupported adapter names raise `SingleLiveSmokeAdapterError`.

The dry runner still produces one Stage 62-compatible payload, writes it through the Stage 60 writer, exports through the Stage 58 helper, and is judged only against the matching single-scenario slice.

## Boundary

Stage 72 adds an interface seam, not a broader execution path.

The current path remains:

```text
one scenario id
  -> adapter helper
  -> fake adapter
  -> Stage 62-compatible payload
  -> Stage 60 writer
  -> Stage 58 export helper
  -> single-scenario judge slice
```

The full matrix is not executed by this path.

## Validation

Recommended focused checks:

```bash
git diff --check
pytest tests/test_single_live_smoke_adapter.py
pytest tests/test_single_live_smoke_fake_adapter.py
pytest tests/test_single_live_smoke_dry.py
```
