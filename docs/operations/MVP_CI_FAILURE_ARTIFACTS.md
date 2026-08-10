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

## Screenshot and trace policy

Current repository browser contracts use direct Playwright scripts and do not presently produce Playwright trace or screenshot files. This slice does not fabricate screenshots or enable broad tracing because either could capture full resident question text. A later enhancement may add screenshot/trace generation only after a test-only redaction/fixture boundary is defined. If a safe screenshot or trace is explicitly produced in the future, it must be added to the collector allowlist rather than uploading arbitrary browser output directories.

## Failure semantics

Artifact collection is diagnostic only. It never converts a failed product/golden/browser contract into success, and artifact-upload failure must not hide the original failing contract.
