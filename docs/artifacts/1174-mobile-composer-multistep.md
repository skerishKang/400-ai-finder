# #1174 Mobile multi-step composer preservation

**Issue:** #1174  
**Branch:** `fix/1174-mobile-composer-multistep`  
**Starting main SHA:** `016f4161a5b053ca78b8d91c1bc553d0f2c7aa81`

## Exact root cause

First collapse transition on `390×844` (pre-fix main):

| Field | Value |
|-------|--------|
| Trigger | Confirm bubble **예, 안내해 주세요** click |
| Code | `setMobileSurface("guidance")` in `showConfirmRun` / `showConfirmRunForAction` |
| JS | `#chat-shell` received `inert` + `aria-hidden="true"` |
| CSS | `body[data-mobile-surface="guidance"] .chat-shell { display: none !important; }` |
| Effect | Nested `#chat-composer-form` / input / send became non-rendered (**width/height 0**, not focusable) |

Before (guidance, pre-fix):

```text
chat-shell: display:none, inert, aria-hidden=true
composer: isConnected=true but geometry 0×0, offsetParent=null, inert ancestor
canvas: visible (guidance)
```

After (guidance, post-fix):

```text
chat-shell: display:flex, position:fixed; bottom:0, non-inert, aria-hidden=false
composer: same DOM node, non-zero box (~390×77), viewport dock, no inert/aria-hidden ancestor
thread/header/chips: display:none (CSS only)
canvas: display:flex primary guidance surface + padding-bottom for dock
```

## Product fix (minimal)

### JS (`citizen-first-use-shell.js`)

- Guidance: do **not** set `inert` / hide entire shell
- Keep shell interactive so the **same** composer remains operable
- Set `#chat-thread[aria-hidden=true]` only (conversation transcript off a11y tree while docked)

### CSS (`citizen-first-use-shell.css`, `max-width: 767px` only)

- Guidance shell: fixed bottom dock (not `display:none`)
- Hide header / journey / thread / chips / disclosure
- Keep single `#chat-composer-form` with min sizes
- Canvas remains visible with bottom padding for the dock
- Desktop rules unchanged (no fixed dock at 1440)

**Canonical DOM counts always 1:** `#chat-shell`, `#chat-thread`, `#chat-composer-form`, `#demo-canvas`.

## Permanent browser contract (fail-closed)

`tests/browser/verify_mobile_multistep_composer_e2e.mjs`

### Continuous probe (from 예 through multi-step)

Each rAF sample records:

- `routeId` via `CitizenActionDemoCanvas.getCurrentRouteId()`
- URL `journey` / `dept-state`
- `data-journey-state` / `data-choreography-state`
- `data-mobile-surface`
- canvas visible geometry
- form/input/send geometry + a11y

**Immediate violations (any sample):**

- `input.disabled` → `input-disabled`
- `input.readOnly` → `input-readonly`
- `send.disabled` → `send-disabled`
- form/input/send disconnected, zero geometry, `display:none`, `visibility:hidden`
- inert / aria-hidden ancestor
- viewport exit
- canonical DOM count ≠ 1 for shell/thread/form/input/send/canvas

Probe starts **after** housing answer, **immediately before** 예 — no `/api/mvp/ask` request lock window.

### Explicit multi-step coverage (J-DEPT-01)

Aligned with `verify_housing_quest_e2e.mjs` + runtime choreography:

| Gate | Canonical signal |
|------|------------------|
| Explicit start | `data-choreography-state === "running"` **or** `data-journey-state === "navigate"` |
| Menu | `journey=J-DEPT-01` + `dept-state=menu` |
| Directory/search | `journey=J-DEPT-01` + `dept-state=directory` |
| Result/table | `journey=J-DEPT-01` + `dept-state=result` |
| Explicit terminal | `data-choreography-state === "done"` only |

Also require `data-journey-state === "result"` and/or final `dept-state=result`.

**Forbidden success conditions (removed):**

- `text.length > 30`
- `!ch` / missing choreography attribute
- `idle` / `cancelled` as terminal success
- canvas merely visible / time elapsed alone

Coverage is proven from **rAF samples + history/event stateTrace** (`history.pushState` / `replaceState`, `citizen:choreography-statechange`, body attribute mutations). Reduced-motion steps can last only a few frames; sequential wait-for-each-dept-state alone is insufficient.

Choreography attribute never appearing → **FAIL**.

### Mid-flow focus/typing operability

At first observed `dept-state=directory` (in-page, same turn as state commit):

1. `input.focus()` → `document.activeElement === input`
2. type `[[1174-OPERABILITY-PROBE]]` (not sent)
3. assert value, then clear
4. assert send remains enabled

### Each ask request

- HTTP **200**
- user count === before + 1
- **assistant exact +1 landing** (MutationObserver trace: latest AI has marker at that instant)
- latest landing assistant contains current marker
- marker count === 1 after settle
- follow-up also asserts assistant exact +1

### Sequences (independent browser contexts)

| Seq | Flow |
|-----|------|
| A | KO housing → 예 → multi-step → EN follow-up |
| B | EN housing action → 예 → multi-step → KO follow-up |
| C | unsupported → KO housing → 예 → multi-step → EN follow-up |

- Viewports: **390×844**, **390×640**
- Desktop regression: **1440×1000** (no mobile fixed dock; containment OK)
- CI: `.github/workflows/mvp-contracts.yml` step for this verifier (+ #1173 scroll containment)

## Measured results (fail-closed local run)

### Continuous probe + state coverage

| Sequence @ viewport | probe samples | firstCollapse | min form | min input | inputDisabled | inputReadOnly | sendDisabled | mid-flow operability | assistant exact +1 |
|---------------------|---------------|---------------|---------|-----------|---------------|---------------|--------------|----------------------|--------------------|
| A-ko-en@390x844 | 7 | null | 390×77 | ≈278.5×37 | 0 | 0 | 0 | PASS (directory) | PASS |
| B-en-ko@390x844 | 10 | null | 390×77 | ≈278.5×37 | 0 | 0 | 0 | PASS (directory) | PASS |
| C-unsupported@390x844 | 14 | null | 390×77 | ≈278.5×37 | 0 | 0 | 0 | PASS (directory) | PASS |
| A-ko-en@390x640 | 15 | null | 390×77 | ≈278.5×37 | 0 | 0 | 0 | PASS (directory) | PASS |
| B-en-ko@390x640 | 14 | null | 390×77 | ≈278.5×37 | 0 | 0 | 0 | PASS (directory) | PASS |
| C-unsupported@390x640 | 15 | null | 390×77 | ≈278.5×37 | 0 | 0 | 0 | PASS (directory) | PASS |

Sample counts are lower than the previous geometry-only run because reduced-motion multi-step finishes in ~100ms; coverage still holds via event/history stateTrace.

### Observed state sequence (canonical)

All 6 mobile runs observed:

```text
explicit start: data-choreography-state=running | data-journey-state=navigate
dept-state sequence: menu → directory → result  (journey=J-DEPT-01)
explicit terminal: data-choreography-state=done
terminal journey: data-journey-state=result
terminal URL: journey=J-DEPT-01&dept-state=result
routeId: home (throughout J-DEPT path)
```

Example compact sequence (source-aware):

```text
running/navigate/- → running/navigate/menu → running/navigate/directory
→ running/navigate/result → done/result/result
```

Guidance checkpoints: form ~**390×77**, shell `flex/fixed`, canvas visible.  
Conversation checkpoints: form ~**390×97**, shell `flex/static`.

### Follow-up markers

- A: `[[1174-SEQ-A-HOUSING-KO]]` then `[[1174-SEQ-A-FOLLOW-EN]]` (each once; latest AI at landing)
- B: `[[1174-SEQ-B-HOUSING-EN]]` then `[[1174-SEQ-B-FOLLOW-KO]]`
- C: `[[1174-SEQ-C-UNSUPPORTED]]` → housing → `[[1174-SEQ-C-FOLLOW]]`

Duplicate markers: **0**. Stale busy/inert/loading on composer after multi-step: **0**.

### Desktop 1440×1000

- shell position **static** (mobile dock not applied)
- document height **1000** (= viewport)
- composer visible/enabled after housing answer

### Safety counters

All **0**: console / page / failed resources / external requests / external navigation / popups / live API / Firecrawl / official-site.

## Commands

```bash
node tests/browser/verify_mobile_multistep_composer_e2e.mjs
node tests/browser/verify_desktop_chat_scroll_containment_e2e.mjs
node tests/browser/verify_mobile_link_safety.mjs http://127.0.0.1:<port>/mobile.html
node tests/browser/verify_housing_quest_e2e.mjs http://127.0.0.1:<port>
node tests/browser/verify_first_use_responsive.mjs
python -m pytest tests/test_citizen_first_use_shell.py tests/test_bukgu_home_asset_identity_audit.py -q
python scripts/audit_bukgu_home_asset_identity.py --check
```

Headless Chromium does **not** open a real soft keyboard; continuous enabled/readOnly=false + mid-flow focus/typing is the operability regression signal.
