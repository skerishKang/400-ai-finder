# Local Execution Contract for #867–#870

> Historical status (2026-07-10): this narrow executor contract is retained for
> provenance and reproducible reference-import work only. It is superseded for
> product development by `docs/design/bukgu-ai-agent-product-directive.md`.
> Authorized MVP implementation may include live public-content inspection,
> interactive routes, visible cursor/typing behavior, and form preparation.

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

## Mandatory failure-stop and reporting

The local model must follow
`.claude/skills/bukgu-visual-clone/execution-gates.md`.

Any owner-required command failure, non-zero exit code, unexpected result,
unapproved changed file, checksum mismatch, or failed integrity check means:
stop immediately; make no more edits; do not commit; do not push; report the
failed command, exit code, raw output or traceback, changed files, diff check,
status, and commit/push status.

The local model must not call such a failure expected, harmless, pre-existing,
acceptable, or complete. It must wait for an explicit owner correction before
resuming.

## Executor selection

Gemma is limited to checksum, binary-copy, deterministic-script, narrow
one-file test work, and one exact one-file contract correction. Diagnosis,
multi-file edits, visual implementation, or scope ambiguity require a
higher-capability executor.

A second failure to follow the required stop, reporting, commit, or push
protocol requires escalation to a higher-capability executor for later
code-edit work.
