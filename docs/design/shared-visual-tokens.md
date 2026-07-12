# MVP Shared Visual Tokens (#1065)

Canonical visual token layer shared between the civic canvas (left, exact
official-site clone) and the AI assistant panel (right, monochrome assistant
UI) of the precise-implementation MVP.

## Source of truth

`src/web/static/citizen-shared-tokens.css` is the **single** definition point
for every cross-surface primitive. It is loaded first in
`src/web/static/citizen-action-demo.html` (and therefore in the built
`/mvp/` entry). The assistant CSS (`citizen-copilot-shell.css`) consumes these
tokens directly; it defines only one layout-only token
(`--copilot-rail-width`).

## Ownership model

Every token has exactly one owner:

- **shared** — genuinely cross-surface interaction primitive. Canonical value
  defined once in the shared layer. The civic canvas is frozen by the #1078
  exact-clone invariant, so it may keep an equivalent literal instead of
  referencing the token, but the canonical value is defined only here.
- **assistant** — owned by the AI assistant panel. The civic canvas uses its
  own exact-clone colors and MUST NOT adopt these.
- **civic-exact** — #1078 exact-official-site-clone constants. They live
  verbatim in `citizen-action-demo-canvas.css` and are deliberately **not**
  tokenized (documented in the shared file as comments only).

## Canonical token list

### shared (cross-surface)
| Token | Value | Purpose |
|-------|-------|---------|
| `--mvp-radius-xs` | `3px` | smallest radius (dock toggle) |
| `--mvp-radius-sm` | `4px` | default control radius |
| `--mvp-radius-md` | `8px` | card / placeholder radius |
| `--mvp-radius-lg` | `12px` | decision button radius |
| `--mvp-radius-pill` | `999px` | pill / badge radius |
| `--mvp-control-min-height` | `36px` | min control height |
| `--mvp-touch-target` | `44px` | min touch target (decision buttons) |
| `--mvp-transition-fast` | `120ms` | hover/quick transition |
| `--mvp-transition-base` | `150ms` | base transition |
| `--mvp-transition-slow` | `240ms` | drawer / large transition |
| `--mvp-focus-ring-width` | `2px` | keyboard focus ring width |
| `--mvp-focus-ring-offset` | `2px` | keyboard focus ring offset |

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
| `--mvp-color-warning` | `#b9770e` | warning state |
| `--mvp-color-busy` | `#2980b9` | busy/active-progress state |
| `--mvp-color-disabled-fg` | `#9b9ba5` | disabled foreground |
| `--mvp-color-disabled-bg` | `#e8ebef` | disabled background |
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
| `--mvp-weight-regular` | `400` | |
| `--mvp-weight-medium` | `500` | |
| `--mvp-weight-semibold` | `600` | |
| `--mvp-weight-bold` | `700` | |
| `--mvp-weight-extrabold` | `800` | |
| `--mvp-space-1` | `4px` | |
| `--mvp-space-2` | `8px` | |
| `--mvp-space-3` | `12px` | |
| `--mvp-space-4` | `16px` | |
| `--mvp-space-5` | `24px` | |
| `--mvp-space-6` | `32px` | |

### civic-exact (NOT tokenized — #1078 frozen)
`#2c3e50` nav, `#32966E`/`#466EAA` GNB gradient, `#008575`/`#008b68`/`#009e6d`
green, `#004a99`/`#0054a6`/`#2c5697` blue, `#e6e8ec`/`#e0e0e0`/`#e0e4ec`
dividers, `#000`/`#333`/`#1a252f` text, `#5d6d7e`/`#7f8c9a` muted, `#c0392b`
(safety-stop overlay only), `#fff`/`#f8f9fa`/`#f4f7fb` backgrounds.

## Migration map (hard-coded literal → token)

All substitutions preserve the resolved computed value exactly.

| File | Before | After |
|------|--------|-------|
| citizen-copilot-shell.css | `#fff` | `var(--mvp-color-surface)` |
| citizen-copilot-shell.css | `#0d0d0f` | `var(--mvp-color-text)` |
| citizen-copilot-shell.css | `#e6e6ea` | `var(--mvp-color-divider)` |
| citizen-copilot-shell.css | `#9b9ba5` | `var(--mvp-color-text-muted)` |
| citizen-copilot-shell.css | `#f4f4f6` | `var(--mvp-color-surface-subtle)` |
| citizen-copilot-shell.css | `#ecf0f1` | `var(--mvp-color-surface-2)` |
| citizen-copilot-shell.css | `#d5dce8` | `var(--mvp-color-border-soft)` |
| citizen-copilot-shell.css | `#b8d6ed` | `var(--mvp-color-border-accent)` |
| citizen-copilot-shell.css | `#27ae60` | `var(--mvp-color-success)` |
| citizen-copilot-shell.css | `#c0392b` | `var(--mvp-color-error)` |
| citizen-copilot-shell.css | `#2980b9` | `var(--mvp-color-busy)` |
| citizen-copilot-shell.css | `#5dade2` | `var(--mvp-color-focus)` |
| citizen-copilot-shell.css | `#ef6a4c` | `var(--mvp-color-accent)` |
| citizen-copilot-shell.css | `3px` (radius) | `var(--mvp-radius-xs)` |
| citizen-copilot-shell.css | `4px` (radius) | `var(--mvp-radius-sm)` |
| citizen-copilot-shell.css | `8px` (radius) | `var(--mvp-radius-md)` |
| citizen-copilot-shell.css | `20px` (radius) | `var(--mvp-radius-pill)` |
| citizen-copilot-shell.css | `0.12s` / `0.15s` / `0.25s` | fast / base / slow |
| citizen-copilot-shell.css | `2px solid #5dade2` (focus) | `var(--mvp-focus-ring-width) solid var(--mvp-color-focus)` |

The removed `--copilot-*` semantic tokens (`--copilot-text`,
`--copilot-section-border`, `--copilot-confirm-approve-bg`, etc.) are deleted;
their values now resolve through the shared tokens above.

## Reduced motion

`citizen-shared-tokens.css` ends with a `prefers-reduced-motion: reduce` block
that collapses every transition/animation to an effectively-instant duration.
This affects **motion timing only**, never geometry, color, or content, so it
does not violate the #1078 exact-clone invariant. The first-use shell keeps its
own reduced-motion rules; both layers are consistent.

## Conflict cleanup

- Removed dead `--copilot-breakpoint: 768px` (media queries cannot read custom
  properties; the real breakpoint is the literal `767px` media query).
- De-duplicated repeated `#0d0d0f`, `#e6e6ea`, `#f4f4f6`, `#27ae60`, `#c0392b`
  literals into single token references.
- Assistant focus ring now uses the shared `--mvp-focus-ring-width` /
  `--mvp-focus-ring-offset` geometry everywhere; only the color differs per
  surface (assistant `#5dade2` vs first-use `#8dc7ef`/`#00a58f`).
