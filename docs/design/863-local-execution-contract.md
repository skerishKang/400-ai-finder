# Local Execution Contract for #867–#870

The assistant owns product decisions, visual analysis, issue scope, source edits, test design, PR review, and merge decisions.

The local model performs only explicitly assigned mechanical work:

1. import approved binary source captures unchanged;
2. verify checksum, dimensions, and clean git status;
3. run the assistant-specified local test, syntax, and diff checks;
4. render requested local screenshots at exact viewports;
5. report commands and raw results without interpreting product fidelity.

The local model must not:

- invent, rename, crop, redraw, optimize, or replace reference assets;
- alter official identity, menu labels, chat copy, layout, or visual hierarchy without an exact assistant patch;
- browse the live official site;
- call network, provider, Firecrawl, crawler, or API paths;
- merge, rebase, amend, reset, clean, stash, force-push, or change main.

## Initial assigned operation

Import the two exact files named in `docs/artifacts/863-reference/source/manifest.md` into that same directory. Verify SHA-256 values and decoded dimensions. Make one normal additive commit only:

`assets(#867): add approved current Buk-gu home references`

No source code, CSS, JavaScript, test, crop, or render artifact change belongs in this import commit.