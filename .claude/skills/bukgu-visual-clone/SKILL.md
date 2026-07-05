---
name: bukgu-visual-clone
description: Reconstruct approved Buk-gu local-demo screens from user-supplied screenshots using semantic DOM/CSS, provenance-controlled local assets, and matched-viewport visual evidence. Use only when an approved reference ledger exists. Never use for live-site crawling, mirroring, scraping, login, form entry, submission, or deployment.
disable-model-invocation: true
---

# Buk-gu no-network visual-clone skill

Run manually as `/bukgu-visual-clone <mode>`.

Supported modes:

- `reference-import`: import approved source screenshots byte-for-byte and verify them.
- `patch-apply`: apply an exact implementation patch supplied by the project owner.
- `render-verify`: generate local visual evidence and run offline validation.
- `audit-handoff`: produce a factual handoff without claiming visual approval.

This skill is a local reconstruction workflow. It is not a website mirroring, scraper, crawler, replay, browser-control, or deployment workflow.

## Non-negotiable boundaries

1. Work only from user-supplied or ledger-approved local files.
2. Never access the live Buk-gu site or any external URL.
3. Never run fetch, crawler, Firecrawl, provider, API, browser automation against an external origin, login, upload, CAPTCHA, payment, form entry, or submission.
4. Never use a whole screenshot as a runtime page background, `<img>` page surface, canvas cover, or overlay substitute.
5. Never redraw, regenerate, optimize, rename, crop, or alter a source reference image unless an approved crop manifest explicitly authorizes the derived local crop.
6. Never invent official text, identity, logo treatment, GNB labels, utility labels, content cards, footer details, or route structure.
7. Preserve the current approved identity from the reference ledger. For the active #863 workstream it is `전남광주통합특별시북구`.
8. Never modify `main`, merge a PR, rebase, amend, reset, clean, stash, or force-push.
9. Never create a new branch unless the project owner explicitly authorizes one.

## Decision authority

The project owner/lead agent owns:

- issue scope and dependency order;
- visual interpretation and ledger approval;
- exact DOM/CSS/JS/test patches;
- PR review and merge decision.

A local execution agent may only perform the requested mode and report raw results. It must stop when the requested input, exact patch, or approval reference is missing.

## Required repository files

Read these before starting:

- `docs/design/863-bukgu-reference-ledger.md`
- `docs/design/863-home-layout-spec.md` when working on home
- `docs/design/863-local-execution-contract.md`
- `docs/artifacts/863-reference/source/manifest.md`

If any document conflicts with a newer project-owner instruction, stop and request an updated ledger or patch. Do not resolve the ambiguity yourself.

## Mode: reference-import

Use only when the owner identifies exact local source PNG files and their destination names.

1. Confirm the current branch is the owner-specified PR branch.
2. Confirm only the named source binary files and, if needed, the source manifest are eligible to change.
3. Copy the source files byte-for-byte to the ledger destination.
4. Run SHA-256 verification and image-dimension verification offline.
5. Run `git diff --check` and `git status --short`.
6. Commit only the approved binary import with the specified normal commit message.
7. Push normally.

Stop if a source file is missing, hash differs, dimensions differ, or an unapproved file changes.

## Mode: patch-apply

Use only when the owner supplies an exact patch or unambiguous file-by-file edit contract.

1. Confirm the patch cites a ledger capture ID and an issue number.
2. Limit changed files to the approved list.
3. Preserve all reference source binaries unchanged.
4. Use semantic HTML/CSS and individual approved local assets only.
5. Scope page-specific geometry under the route root, for example `.bg-page--home`.
6. Keep the official-looking left viewport separate from the local chat shell.
7. Do not add remote URLs, external assets, network calls, or unapproved interaction behavior.
8. Run only the owner-specified local tests, syntax checks, and diff checks.

Stop if the patch requires a design decision not recorded in the ledger.

## Mode: render-verify

Use only against the local fixture.

1. Use the exact viewport declared in the ledger.
2. Capture the requested local render and comparison artifact.
3. Keep the reference image unchanged; do not edit it to hide visual differences.
4. Record browser console errors, external-request count, and local/session-storage writes.
5. Run the requested offline test, syntax check, and `git diff --check`.
6. Report raw paths, dimensions, hashes where requested, commands, outputs, and `git status --short`.

    Do not declare a visual gate passed. The project owner reviews the actual images.
    Any required check failure invokes the mandatory failure-stop rule; do not describe a render or comparison as passed after that failure.

## Mode: audit-handoff

Use this report format exactly:

```text
Branch:
Local HEAD before:
Local HEAD after:
Remote HEAD after push:
Changed files:
Reference capture IDs used:
Asset hash checks:
Viewport(s):
Commands run and raw results:
Console errors:
External requests:
Storage writes:
Git status --short:
Unresolved items:
```

Do not state that CI passed unless GitHub workflow and commit-status data are actually present. Local test success is local validation only.

## Visual reconstruction rules

- The source screenshot is a specification, not the runtime implementation.
- Build hierarchy before decoration: global strips → header/GNB → search/brand → lead cards → quick links → content modules → footer.
- Use local crops only for visual material that cannot be faithfully recreated as DOM/CSS: official logo, portrait, banner artwork, editorial images, and certification badges.
- Use DOM/CSS for containers, spacing, type, lines, tabs, lists, buttons, controls, and labels.
- Treat differing carousel slides as distinct reference states; do not blend them.
- In split-screen mode, retain a fixed desktop official canvas and scale it uniformly inside the left frame. Do not invent an unofficial responsive layout.

## Mandatory failure-stop and executor control

`execution-gates.md` is binding for every mode.

If any owner-required command fails, exits non-zero, produces an unexpected
result, or reveals an unapproved changed file, stop immediately. Do not make a
workaround edit, commit, or push. Report the failed command, exit code, raw
output, changed-file status, `git diff --check`, `git status --porcelain=v1
--untracked-files=all`, and commit/push status.

A local execution agent cannot classify a failure as expected, harmless,
pre-existing, or acceptable. It cannot claim completion, visual approval, CI
approval, release readiness, or merge readiness after a required failure.

Use Gemma only for checksum, byte-for-byte copy, deterministic scripts, narrow
one-file tests, or one explicit one-file contract correction. Use a
higher-capability executor for diagnosis, multi-file edits, visual
implementation, or scope ambiguity. A second failure to honor the required
stop/report/commit/push protocol requires escalation for later code-edit work.

## Required stop conditions

Stop and report rather than improvising when:

- no approved reference ledger exists;
- screenshot text or an icon is unreadable;
- the needed official route screen was not supplied;
- a required asset is unavailable or has a hash mismatch;
- the requested change affects a route outside the assigned scope;
- local render requires external network;
- a visual requirement conflicts with the ledger.

## Supporting files

- `reference-ledger-template.md`: template for a new screenshot set.
- `local-handoff-template.md`: copy-ready report template for local agents.
