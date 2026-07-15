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

## Permanent browser contract

`tests/browser/verify_mobile_multistep_composer_e2e.mjs`

- Continuous `requestAnimationFrame` probe from **예** through multi-step  
  (collapse → immediate fail; never wait-only-at-end)
- Same element identity: form/input/send/shell/thread/canvas
- Independent browser contexts for:

| Seq | Flow |
|-----|------|
| A | KO housing → 예 → multi-step → EN follow-up |
| B | EN housing action → 예 → multi-step → KO follow-up |
| C | unsupported → KO housing → 예 → multi-step → EN follow-up |

- Viewports: **390×844**, **390×640**
- Desktop regression: **1440×1000** (no mobile fixed dock; containment OK)
- CI: `.github/workflows/mvp-contracts.yml` step for this verifier (+ #1173 scroll containment)

## Measured results (final local run)

### Continuous probe (guidance multi-step)

| Sequence @ viewport | probe samples | firstCollapse | min form | min input |
|---------------------|---------------|---------------|---------|-----------|
| A-ko-en@390x844 | 475 | null | 390×77 | ≈278×37 |
| B-en-ko@390x844 | 498 | null | 390×77 | ≈278×37 |
| C-unsupported@390x844 | 501 | null | 390×77 | ≈278×37 |
| A-ko-en@390x640 | 499 | null | 390×77 | ≈278×37 |
| B-en-ko@390x640 | 495 | null | 390×77 | ≈278×37 |
| C-unsupported@390x640 | 496 | null | 390×77 | ≈278×37 |

Guidance checkpoints: form ~**390×77**, shell `flex/fixed`, canvas `flex`.  
Conversation checkpoints: form ~**390×97**, shell `flex/static`.

### Follow-up markers

- A: `[[1174-SEQ-A-HOUSING-KO]]` then `[[1174-SEQ-A-FOLLOW-EN]]` (each once)
- B: `[[1174-SEQ-B-HOUSING-EN]]` then `[[1174-SEQ-B-FOLLOW-KO]]`
- C: `[[1174-SEQ-C-UNSUPPORTED]]` → housing → `[[1174-SEQ-C-FOLLOW]]`

Duplicate markers: **0**. Stale busy/inert on composer: **0**.

### Desktop 1440×1000

- shell position **static** (mobile dock not applied)
- document height **1000** (= viewport)
- composer visible/enabled after housing answer

### Safety counters

All **0**: console / page / failed resources / external requests / external navigation / popups / live API / official-site.

## Commands

```bash
node tests/browser/verify_mobile_multistep_composer_e2e.mjs
node tests/browser/verify_desktop_chat_scroll_containment_e2e.mjs
python -m pytest tests/test_citizen_first_use_shell.py -q
python scripts/audit_bukgu_home_asset_identity.py --check
```

Headless Chromium does **not** open a real soft keyboard; short viewport + focus/typing geometry is the regression signal.
