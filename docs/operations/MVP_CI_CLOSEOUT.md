# MVP CI Closeout (#1231-E)

## Purpose

Issue #1231 decomposed the MVP contract workflow into parallel diagnostic domains, locked dependencies, added privacy-safe failure artifacts, and added the security-quality domain. This closeout slice records the measured runtime baseline, assigns explicit fail-closed timeouts, and defines the compatibility-check migration target without changing repository protection settings.

## Recent successful-run baseline

The timeout tiers are based on the CTO-provided measurements from recent successful `MVP Contract Checks` runs used for #1231-E planning:

| Job | Approximate successful duration | Timeout |
| --- | ---: | ---: |
| `citizen-browser` | 6m22s | 15 min |
| `page-agent` | 4m33s | 12 min |
| `comparison-evidence` | 2m19s | 10 min |
| `python-contracts` | 40s | 8 min |
| `security-quality` | 28s | 10 min |
| `build-packaging` | 19s | 6 min |
| `cloudflare-function` | 13s | 8 min |
| `snapshot-provenance` | 12s | 6 min |
| `site-adapter` | 8s | 6 min |
| `mvp-contracts` | aggregate-only | 5 min |

The critical path is `citizen-browser`. Its 15-minute timeout is intentionally retained because browser execution has materially more variance than the short contract jobs. `page-agent` and `comparison-evidence` retain substantial browser headroom. `security-quality` retains additional headroom for security-tool and advisory-network variance. The shorter deterministic jobs use smaller but still conservative ceilings.

These timeouts are not performance targets. They are hung-job ceilings intended to fail closed within a meaningful period while preserving normal runtime variance.

## Stable required-check migration plan

**Recommended external required check:** `mvp-contracts`

**Internal component checks:**

- `python-contracts`
- `snapshot-provenance`
- `site-adapter`
- `build-packaging`
- `cloudflare-function`
- `citizen-browser`
- `page-agent`
- `comparison-evidence`
- `security-quality`

The nine domain jobs remain parallel diagnostic and contract boundaries. The stable compatibility check remains `mvp-contracts`: it uses `if: always()`, depends on all nine domains, and explicitly requires every domain result to equal `success`. A failed, cancelled, or skipped domain therefore cannot be treated as an aggregate success.

Using `mvp-contracts` as the external required-check target reduces branch-protection configuration churn when the internal domain decomposition evolves. This is a **recommended target and migration plan**, not a statement that GitHub branch protection or rulesets are already configured this way.

This PR does not mutate branch protection or rulesets, and it does not assume their current configured state.

## Cache decision

No pip, npm, Playwright, custom, or cross-job cache is added in #1231-E. The measured critical path is browser execution itself, so installation caching has not yet demonstrated enough benefit to justify invalidation complexity or security/dependency-freshness tradeoffs.

**Cache optimization deferred pending measured repeated-install benefit.**

## Preserved contracts

The closeout keeps the existing nine domain job names and the `mvp-contracts` compatibility check unchanged. It also preserves the fail-closed aggregate result checks, #1231-C privacy-safe failure artifacts (`actions/upload-artifact@v7.0.1`, five-day retention), Ruff correctness selectors `E9,F63,F7,F82`, Gitleaks, pip-audit, npm audit, `npm ci --ignore-scripts`, and the canonical `KILOCODE_API_KEY` routine-CI offline guard.

No browser contract is removed or weakened, no dependency or action version is migrated, and no production, deployment, provider, Firecrawl, or official-site live call is introduced by this closeout.
