# #1174 Mobile multi-step composer preservation

**Issue:** #1174  
**Branch:** `fix/1174-mobile-composer-multistep`  
**Base main:** `016f4161a5b053ca78b8d91c1bc553d0f2c7aa81`

## Root cause

On `≤767px`, clicking **예** called `setMobileSurface("guidance")` which:

1. Set `#chat-shell` to `inert` + `aria-hidden="true"`
2. CSS: `body[data-mobile-surface="guidance"] .chat-shell { display: none !important; }`

The composer lives inside `#chat-shell`, so it became **disconnected from the visible layout** (0×0 / non-interactive) for the entire multi-step civic guidance flow.

## Fix (no second composer, guidance retained)

### JS (`citizen-first-use-shell.js`)

- Guidance surface: keep `#chat-shell` **non-inert** and `aria-hidden="false"`
- Hide thread from a11y via `#chat-thread[aria-hidden=true]` while docked
- Conversation surface: clear thread `aria-hidden` as before

### CSS (`citizen-first-use-shell.css`, mobile only)

- Guidance: `#chat-shell` remains `display: flex`, **fixed bottom dock**
- Hide header / journey status / thread / chips / disclosure only
- Keep the same `#chat-composer-form` / input / send with min sizes
- Canvas remains primary guidance surface with bottom padding for the dock

Desktop split grid and #1173 containment are unchanged.

## Permanent contract

`tests/browser/verify_mobile_composer_multistep_e2e.mjs` (`390×844`):

1. Housing supported question  
2. Confirm **예** → guidance multi-step  
3. Measure composer at entry / answer / before-yes / after-yes / mid-flow / after-multistep  
4. Focus + English follow-up without reload  
5. Single composer DOM; safety counters 0  

Unit contract: `tests/test_citizen_first_use_shell.py` mobile surface asserts updated for #1174.

## How to run

```bash
node tests/browser/verify_mobile_composer_multistep_e2e.mjs
python -m pytest tests/test_citizen_first_use_shell.py -q
```
