# MVP Shared Visual Tokens (#1065)

Canonical visual token layer for the precise-implementation MVP, consumed by
the **AI assistant panel** (`citizen-copilot-shell.css`). Loaded first in
`citizen-action-demo.html` (and therefore the built `/mvp/` entry) so the
assistant CSS resolves its tokens.

## Scope of THIS pull request

This PR tokenizes **`citizen-copilot-shell.css` only** — the assistant chat /
copilot shell on the right of the first-use surface. It establishes the single
source of truth for the assistant's visual + interaction primitives and
documents ownership.

Out of scope (kept on their own systems, intentionally not touched):
- **civic canvas** (`citizen-action-demo-canvas.css`) — frozen by the #1078
  exact-official-site-clone invariant; keeps its own hard-coded literals.
- **first-use shell** (`citizen-first-use-shell.css`) — keeps its own
  `--first-use-*` system, separate motion timings, and `#8dc7ef` focus color.

Future PRs may extend the layer to those surfaces; this PR does not.

## Ownership model

Every token has exactly one owner:

- **shared** — a primitive whose *value* is genuinely embodied by BOTH
  surfaces. Only a tiny set qualifies, because #1078 freezes civic colors /
  geometry. The civic canvas uses the same number as a hard-coded literal
  (e.g. `border-radius: 4px`, `transition: … 0.12s`); the assistant references
  the token. This coincidence is locked by a contract test.
- **assistant** — owned by the AI assistant panel. The civic canvas uses its
  own exact-clone colors and MUST NOT adopt these.

There is **no civic-exact token**: those #1078 constants live verbatim in the
civic canvas CSS and are documented as comments in `citizen-shared-tokens.css`
for traceability only.

## Canonical token list

### shared (value embodied by both surfaces)
| Token | Value | Civic embodiment (literal) |
|-------|-------|----------------------------|
| `--mvp-radius-sm` | `4px` | civic `border-radius: 4px` (buttons, cards) |
| `--mvp-transition-fast` | `120ms` | civic `transition: … 0.12s` |
| `--mvp-focus-ring-width` | `2px` | civic focus highlight is 2px-class |
| `--mvp-focus-ring-offset` | `2px` | — |

### assistant (AI panel only)
| Token | Value | Purpose |
|-------|-------|---------|
| `--mvp-color-text` | `#0d0d0f` | neutral text |
| `--mvp-color-text-muted` | `#9b9ba5` | muted/placeholder text |
| `--mvp-color-surface` | `#ffffff` | panel/control surface |
| `--mvp-color-surface-subtle` | `#f4f4f6` | active/subtle surface |
| `--mvp-color-surface-2` | `#ecf0f1` | choice button surface |
| `--mvp-color-divider` | `#e6e6ea` | divider / control border |
| `--mvp-color-border-soft` | `#d5dce8` | hover border |
| `--mvp-color-border-accent` | `#b8d6ed` | accent border |
| `--mvp-color-success` | `#27ae60` | success state |
| `--mvp-color-error` | `#c0392b` | error state |
| `--mvp-color-busy` | `#2980b9` | busy/active-progress state |
| `--mvp-color-focus` | `#5dade2` | assistant focus ring color |
| `--mvp-color-accent` | `#ef6a4c` | composer / primary accent |
| `--mvp-font-size-xs` | `0.6875rem` | 11px |
| `--mvp-font-size-sm` | `0.75rem` | 12px |
| `--mvp-font-size-base` | `0.8125rem` | 13px |
| `--mvp-font-size-md` | `0.875rem` | 14px |
| `--mvp-font-size-lg` | `0.9375rem` | 15px |
| `--mvp-font-size-input` | `0.9rem` | composer input |
| `--mvp-font-size-send` | `0.85rem` | composer send |
| `--mvp-font-size-xl` | `0.95rem` | chat shell title / bubble |
| `--mvp-font-size-2xl` | `1.375rem` | canvas / demo title |
| `--mvp-weight-semibold` | `600` | |
| `--mvp-weight-bold` | `700` | |
| `--mvp-radius-xs` | `3px` | smallest radius (dock toggle) |
| `--mvp-radius-md` | `8px` | card / placeholder radius |
| `--mvp-transition-base` | `150ms` | base transition |

## Removed speculative tokens (per review)

The following were declared in the first revision but are **not connected to
any production selector**, so they were removed to keep the layer small and
honest:

- `--mvp-radius-lg`, `--mvp-radius-pill` (no production usage; pill controls
  keep a literal `border-radius: 20px`)
- `--mvp-transition-slow` (the only `0.25s` usage keeps a literal `0.25s`)
- spacing scale (`--mvp-space-1..6`) — not yet applied
- `--mvp-weight-regular`, `--mvp-weight-medium`, `--mvp-weight-extrabold`
- `--mvp-control-min-height`, `--mvp-touch-target`
- `--mvp-color-warning`, `--mvp-color-disabled-fg`, `--mvp-color-disabled-bg`

The assistant currently expresses disabled state via `opacity` + `cursor` and
has no warning surface, so those tokens were speculative.

## Migration map (hard-coded literal → token)

Every substitution preserves the **resolved computed value exactly**
(`0.15s` ≡ `150ms`, `0.12s` ≡ `120ms`). Two values were intentionally kept as
literals because their tokenized forms would NOT be equal:

| File | Before | After | Value-equal? |
|------|--------|-------|--------------|
| citizen-copilot-shell.css | `#fff` | `var(--mvp-color-surface)` | yes |
| citizen-copilot-shell.css | `#0d0d0f` | `var(--mvp-color-text)` | yes |
| citizen-copilot-shell.css | `#e6e6ea` | `var(--mvp-color-divider)` | yes |
| citizen-copilot-shell.css | `#9b9ba5` | `var(--mvp-color-text-muted)` | yes |
| citizen-copilot-shell.css | `#f4f4f6` | `var(--mvp-color-surface-subtle)` | yes |
| citizen-copilot-shell.css | `#ecf0f1` | `var(--mvp-color-surface-2)` | yes |
| citizen-copilot-shell.css | `#d5dce8` | `var(--mvp-color-border-soft)` | yes |
| citizen-copilot-shell.css | `#b8d6ed` | `var(--mvp-color-border-accent)` | yes |
| citizen-copilot-shell.css | `#27ae60` | `var(--mvp-color-success)` | yes |
| citizen-copilot-shell.css | `#c0392b` | `var(--mvp-color-error)` | yes |
| citizen-copilot-shell.css | `#2980b9` | `var(--mvp-color-busy)` | yes |
| citizen-copilot-shell.css | `#5dade2` | `var(--mvp-color-focus)` | yes |
| citizen-copilot-shell.css | `#ef6a4c` | `var(--mvp-color-accent)` | yes |
| citizen-copilot-shell.css | `3px` (radius) | `var(--mvp-radius-xs)` | yes |
| citizen-copilot-shell.css | `4px` (radius) | `var(--mvp-radius-sm)` | yes |
| citizen-copilot-shell.css | `8px` (radius) | `var(--mvp-radius-md)` | yes |
| citizen-copilot-shell.css | `0.12s` | `var(--mvp-transition-fast)` | yes (`120ms`) |
| citizen-copilot-shell.css | `0.15s` | `var(--mvp-transition-base)` | yes (`150ms`) |
| citizen-copilot-shell.css | `2px solid #5dade2` (focus) | `var(--mvp-focus-ring-width) solid var(--mvp-color-focus)` | yes |
| citizen-copilot-shell.css | `20px` (radius, badge/toggle) | `20px` (literal — kept) | n/a (unchanged) |
| citizen-copilot-shell.css | `0.25s` (drawer transition) | `0.25s` (literal — kept) | n/a (unchanged) |

The removed `--copilot-*` semantic tokens (`--copilot-text`,
`--copilot-section-border`, `--copilot-confirm-approve-bg`, etc.) are deleted;
their values now resolve through the shared tokens above. The dead
`--copilot-breakpoint` token was also removed.

## Reduced motion

`citizen-shared-tokens.css` ends with a `prefers-reduced-motion: reduce` block
that collapses every transition/animation to an effectively-instant duration.
This affects **motion timing only**, never geometry, color, or content, so it
does not violate the #1078 exact-clone invariant. The first-use shell keeps
its own reduced-motion rules; both layers are consistent.

## Contract tests

- `tests/test_citizen_shared_visual_tokens.py` (Python, runs in CI): token
  stylesheet load order, key token values + ownership, detection of any
  unresolved `var(--mvp-*)` referenced by the assistant CSS, proof that the
  shared primitives are embodied by the civic canvas literals, focus-visible
  presence, success/error/busy/disabled token definitions, and the
  reduced-motion media block.
- `tests/browser/verify_first_use_responsive.mjs` (strengthened): adds
  reduced-motion and disabled-state checks at 390 / 768 / 1440px on top of the
  existing geometry + focus-visible contract.
