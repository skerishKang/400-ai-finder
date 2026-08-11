## Summary

<!-- 무엇을 왜 변경했는지 3~6문장으로 설명하세요. -->

## Change mode

- [ ] Shared core / product change
- [ ] Routine site onboarding
- [ ] Onboarding exception escalation
- [ ] Golden / production promotion
- [ ] Docs / governance only

## Related issue

- Closes / Tracks #
- Routine onboarding with no shared-core change may use `N/A` with a reason when the governing onboarding contract permits it.

## Product track

- [ ] Buk-gu golden clone
- [ ] 근거 기반 AI 시민안내
- [ ] 공식정보 freshness
- [ ] Python crawler·operator runtime
- [ ] Cloudflare citizen runtime
- [ ] Page Agent comparison
- [ ] Multi-site / general-site platform
- [ ] Routine site onboarding
- [ ] Authorized first-party integration
- [ ] Repository·documentation governance

## Release / readiness gate

- [ ] Gate A — Frozen controlled demo
- [ ] Gate B — Protected public pilot
- [ ] Gate C — Evidence-safe AI pilot
- [ ] Gate D — Unified platform foundation
- [ ] Gate E — Modular runtime
- [ ] Gate F — Official freshness staging
- [ ] Gate G1 — Generated onboarding preview
- [ ] Gate G2 — Archetype golden validation
- [ ] Gate G3 — Resident/default or production promotion
- [ ] Gate H — Authorized operational integration
- [ ] No promotion

`generated_preview` is not the same state as `exact`, `archetype_golden`, `resident_default_approved`, or production approval.

## Scope

### Included

-

### Excluded

-

## Exact refs

- Base branch / SHA:
- Head branch / SHA:
- Changed files:

## Network and provider mode

- [ ] Offline / mock
- [ ] Fixture only
- [ ] Controlled read-only live
- [ ] Provider staging
- [ ] Production integration

External targets, methods and limits:

**URL supplied != live network authorized.** If a target URL is present, state separately whether any live capture/fetch/provider call was authorized and executed.

## Data, privacy and secrets

- [ ] No API key·token·credential committed
- [ ] No raw citizen transcript or unnecessary PII
- [ ] No customer·institution private data
- [ ] Test data is synthetic or approved public fixture
- [ ] New fixture/asset includes source, date, checksum and provenance
- [ ] Logs and errors are sanitized

## Safety impact

- [ ] No actual submit
- [ ] No login·payment
- [ ] No production write action
- [ ] Model actions·URLs are validated by closed schema/allowlist when applicable
- [ ] High-risk administrative claims meet evidence policy when applicable
- [ ] Rate limit·timeout·cost effect reviewed when applicable

## Routine onboarding report

<!-- Required for Routine site onboarding. Otherwise `N/A — reason`. -->

- Input site / URL / site_id:
- Proposed/detected archetype:
- Archetype confidence:
- Detected capabilities:
- Unsupported / uncertain capabilities:
- Automation ratio:
- Human-review ratio:
- Unsupported ratio:
- Generated artifacts:
- Exception queue summary:
- Provenance/acquisition mode:
- Shared core changed: `YES / NO`
- Site-specific override(s):
- Production promotion requested: `YES / NO`

If `shared core changed: YES`, the relevant shared-core Issue, contracts, tests and migration impact are mandatory. Do not hide a reusable engine fix inside a routine onboarding PR.

## Golden compatibility

- [ ] Closed Buk-gu route IDs unchanged or migration issue linked
- [ ] Closed target IDs unchanged or migration issue linked
- [ ] DOM IDs·data state·public window APIs preserved
- [ ] Canonical fixture identity preserved
- [ ] No-submit boundary preserved
- [ ] Resident-default visual approval supplied when applicable
- [ ] Generated preview only; no golden/default promotion claimed
- [ ] Not applicable

## Validation

### Commands

```text
# exact commands
```

### Results

- Python:
- Node / Function:
- Build:
- Browser:
- Accessibility / responsive:
- Generated onboarding QA:
- Page Agent / comparison:

## Browser and visual evidence

- Surface state: `generated_preview / archetype_golden / resident_default / N/A`
- Viewports:
- Routes / states:
- Automated visual/browser evidence:
- Side-by-side accepted reference:
- Material differences / unresolved items:
- Project-owner visual approval:

For Gate G1 generated preview, project-owner first-promotion visual approval is not required because no resident-default/exact promotion is granted. For Gate G2/G3 or explicit exact/golden promotion, follow the applicable visual policy.

## API and schema

- Schema version:
- Provider/model impact:
- Freshness/evidence impact:
- Failure codes:
- Timeout/retry/model-fallback/provider-fallback:
- Request ID/telemetry:

## Migration and compatibility

- Data/config migration:
- Legacy IDs / URLs:
- Dual-read / dual-serve period:
- Deprecation:

## Deployment

- [ ] No deployment impact
- [ ] Preview/debug only
- Environment:
- Deployment method:
- Expected deployed SHA:
- Secrets owner:
- Smoke plan:

Generated preview creation is not production deployment approval.

## Rollback / isolation

<!-- Shared core/product change: rollback target. Routine onboarding: failed-site isolation/removal path. -->

-

## Known limitations, exceptions and follow-ups

-

Only reusable capability gaps, shared runtime/parser/compiler bugs, safety issues, repeating failure patterns and production blockers should normally be escalated into separate Issues. Do not create one Issue per routine site-specific difference by default.

## Pre-merge exact-head check

- [ ] PR head SHA rechecked
- [ ] Base / behind state rechecked
- [ ] Exact-head CI complete for required checks
- [ ] Mergeability rechecked
- [ ] Reviews and unresolved threads rechecked
- [ ] Changed filenames rechecked
- [ ] No unexpected artifacts, secrets or PII
- [ ] Generated preview does not overclaim exact/golden/production status
