# MVP CI Failure Artifacts

Status: #1231-C implementation contract.

## Purpose

Browser-heavy MVP CI failures must leave enough bounded evidence to diagnose server startup/routing and comparison-harness failures without uploading resident text, secrets, provider errors, or environment dumps.

This slice does not weaken tests and does not add live provider, Firecrawl, production, or official-site calls.

## Allowed sources

Only these pre-existing local CI outputs may be collected:

- `citizen-browser`
  - `/tmp/mobile-link-safety-server.log`
  - `/tmp/housing-e2e-server.log`
- `page-agent`
  - `/tmp/page-agent-e2e-server.log`
  - `/tmp/resident-e2e-server.log`
- `comparison-evidence`
  - `/tmp/comparison-harness-server.log`
  - `/tmp/comparison-evidence-ci.json`

The collector never walks `/tmp`, the repository, the environment, browser profiles, or secret stores.

## Privacy boundary

Log artifacts are tail-bounded to 128 KiB per source and redact:

- email-like values
- Korean phone-number-like values
- Bearer credentials
- API-key/token/secret/authorization assignments
- query strings
- question/prompt/raw-provider-error fields

Comparison evidence is **not copied raw**. The uploaded form is a whitelist summary containing only:

- mode
- scenario ID
- attempt
- external request count
- no-submit result
- action-step count

The collector always writes a manifest declaring the privacy boundary and which optional sources were present.

## Retention and upload

Failure artifacts are uploaded only when their owning CI job has failed. The workflow uses the current GitHub-hosted `actions/upload-artifact` v7 line with a short 5-day retention period and a job/run-specific artifact name. No hidden files are included. GitHub's action supports per-artifact retention controls; the short period is intentional for diagnostic evidence rather than archival storage.

## Screenshot and trace policy (#1231-F)

The responsive harness (`tests/browser/verify_first_use_responsive.mjs`) already
produces deterministic screenshot evidence: exactly 18 PNGs under
`/tmp/400-ai-finder-1116` (320/390 mobile search journey, 390 writing journey,
and 1440 desktop split).

#1231-F connects that existing evidence to the failure-only artifact pipeline
with an exact literal allowlist and adds **one** bounded Playwright trace:

- `320-entry.png`, `320-confirm.png`, `320-first-action.png`,
  `320-search-typing.png`, `320-result.png`, `320-view-switch.png`,
  `320-reset.png`
- `390-entry.png`, `390-confirm.png`, `390-first-action.png`,
  `390-search-typing.png`, `390-result.png`, `390-view-switch.png`,
  `390-reset.png`
- `390-writing-route.png`, `390-writing-typing.png`,
  `390-writing-cancelled.png`
- `1440-desktop.png`
- `responsive-trace.zip` — a single Stage-B trace recorded on the same
  controlled Playwright context that drives the deterministic demo questions
  (`screenshots: false, snapshots: true, sources: false`); in-trace
  screenshots stay off so the trace remains inside the 32 MiB cap, while the
  18 deterministic PNGs provide the visual evidence

Policy:

- Evidence root guard: `lstat`, root symlink rejected, root must be a
  directory directly inside the OS temp directory; only the allowlisted stale
  entries are deleted before a run (no other `/tmp` files are touched);
  allowlisted stale entries that are symlinks/non-files fail closed.
- Exact evidence-root membership: after a run the evidence root must contain
  exactly the 19 allowlisted entries (18 PNG + `responsive-trace.zip`) and
  nothing else. The 360px viewport keeps full functional/browser coverage
  (navigation, assertions, focus checks, state transitions) but produces no
  evidence screenshots, so `360-*.png` files (e.g. from older harness runs)
  fail the contract and are never collected.
- Screenshots are capped at 4 MiB, the trace at 32 MiB; both must be regular
  non-symlink files.
- The collector validates PNG magic (`89 50 4E 47 0D 0A 1A 0A`) and the ZIP
  signature (`50 4B 03 04`), copies binary evidence byte-for-byte (never
  decoded/sanitized), and records missing visual evidence separately as
  `missing_visual_sources`.
- No globs, no recursive `/tmp` walks, no arbitrary fallback directories:
  only allowlisted files produced by the current run are collected.
- Upload remains failure-only, uses `actions/upload-artifact@v7.0.1`, and
  keeps the 5-day retention.
- Broad tracing is forbidden: no global browser-context trace, no Page Agent
  trace, no comparison trace, no live provider path trace, and no arbitrary
  user input trace. The trace is limited to the fixed Stage-B context that
  aborts all external requests.

## Failure semantics

Artifact collection is diagnostic only. It never converts a failed product/golden/browser contract into success, and artifact-upload failure must not hide the original failing contract.
