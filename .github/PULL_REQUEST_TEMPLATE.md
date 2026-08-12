## Summary

<!-- 무엇을 왜 변경했는지 3~6문장으로 설명하세요. -->

## Change mode

- [ ] Shared core / product change
- [ ] Platform structural proof
- [ ] Named-site clone onboarding
- [ ] Onboarding exception escalation
- [ ] Exact / golden / resident-default promotion
- [ ] Authorized first-party actual-site integration
- [ ] Docs / governance only

## Related issue

- Closes / Tracks #
- Routine onboarding with no shared-core change may use `N/A` only when the governing onboarding contract permits it and the reason is stated.

## Product track

- [ ] Buk-gu golden clone
- [ ] 근거 기반 AI 시민안내
- [ ] 공식정보 freshness
- [ ] Python crawler·operator runtime
- [ ] Cloudflare citizen runtime
- [ ] Page Agent comparison
- [ ] Multi-site / general-site clone platform
- [ ] Named-site clone onboarding
- [ ] Platform structural proof
- [ ] Authorized first-party actual-site integration
- [ ] Repository·documentation governance

## Release / readiness gate

- [ ] Gate A — Frozen controlled demo
- [ ] Gate B — Protected public AI pilot
- [ ] Gate C — Evidence-safe AI pilot
- [ ] Gate D — Unified platform foundation
- [ ] Gate E — Modular runtime
- [ ] Gate F — Official freshness staging
- [ ] Gate G0 — Generic structural/platform proof
- [ ] Gate G1 — Named-site reference baseline
- [ ] Gate G2 — Faithful clone candidate
- [ ] Gate G3 — Clone MVP review/readiness
- [ ] Gate G4 — AI-on-clone onboarding proof
- [ ] Gate G5 — Optional exact/archetype-golden/resident-default promotion
- [ ] Gate H — Authorized first-party actual-site integration
- [ ] No promotion

```text
structural preview
!= reference baseline
!= faithful clone
!= clone MVP ready
!= exact
!= resident/default approved
!= actual-site integrated
```

## Scope

### Included

-

### Excluded

-

## Exact refs

- Base branch / SHA:
- Head branch / SHA:
- Changed files:

## Current product-stage statement

- [ ] This PR remains in pre-integration clone-MVP scope.
- [ ] This PR explicitly opens future Gate H actual-site integration scope.
- [ ] Not applicable.

If Gate H is not selected, do not introduce actual production-site operation requirements as an unrelated blocker to faithful-clone fidelity work.

## Network / reference mode

- [ ] Offline / mock
- [ ] Fixture only
- [ ] Controlled read-only reference capture
- [ ] Provider staging
- [ ] Production integration

External targets, methods, route/state limits and capture scope:

Tool/CLI network capability and project-task capture scope are separate facts. State what was actually executed.

## Data, privacy, secrets and confidentiality

- [ ] No API key·token·credential committed
- [ ] No raw citizen transcript or unredacted PII
- [ ] No customer·institution private material
- [ ] No confidential stakeholder/business relationship detail in public repo
- [ ] Test data is synthetic or approved reference fixture
- [ ] Logs/errors are sanitized

## Named-site clone report

<!-- Required for Named-site clone onboarding. Otherwise `N/A — reason`. -->

- Target site / site_id:
- Declared MVP clone scope:
- Representative routes/states/viewports:
- Reference capture mode:
- Source URLs:
- `captured_at`:
- `source_updated_at` where available:
- Reference snapshot identity / checksum:
- Reference DOM/content/screenshot artifact identity:
- Proposed/detected archetype:
- Archetype confidence:
- Detected capabilities:
- Unsupported / uncertain capabilities:
- Clone candidate identity:
- Clone generator/source commit identity:
- Structural parity state:
- Content parity state:
- Asset mapping / unresolved asset state:
- Interaction parity state:
- Responsive/accessibility state:
- Visual comparison state:
- Material differences / unresolved items:
- AI-on-clone state:
- Automation ratio:
- Human-review ratio:
- Unsupported ratio:
- Exception queue summary:
- Shared core changed: `YES / NO`
- Site-specific override(s):
- Exact/default promotion requested: `YES / NO`
- Actual-site integration requested: `YES / NO`

If `shared core changed: YES`, the relevant shared-core Issue, contracts, tests and migration impact are mandatory.

## Platform structural proof report

<!-- Required for Gate G0 / platform structural proof. -->

- Fixture type: `synthetic / offline real-site-derived fixture / other`
- SiteSpec/archetype/capability artifacts:
- Site Model artifacts:
- Structural preview artifacts:
- QA/report artifacts:
- Explicit statement that no named-site faithful-clone claim is made:

## Golden compatibility

- [ ] Closed Buk-gu route IDs unchanged or migration issue linked
- [ ] Closed target IDs unchanged or migration issue linked
- [ ] DOM IDs·data state·public window APIs preserved
- [ ] Canonical fixture identity preserved
- [ ] No-submit boundary preserved
- [ ] Exact/golden promotion evidence supplied when applicable
- [ ] No exact/default promotion claimed
- [ ] Not applicable

## Validation

### Commands / checks

```text
# exact commands/checks
```

### Results

- Python:
- Node / Function:
- Build:
- Browser:
- Accessibility / responsive:
- Reference-vs-clone QA:
- Generated onboarding QA:
- Page Agent / comparison:

## Browser and visual evidence

- Surface state: `structural_preview / reference_baseline / clone_candidate / clone_mvp_ready / exact / resident_default / N/A`
- Viewports:
- Routes / states:
- Automated visual/browser evidence:
- Side-by-side source reference:
- Material differences / unresolved items:
- Project-owner visual review where applicable:

Automated browser/screenshot QA does not by itself convert a structural preview into a faithful clone or an exact/default promotion.

## AI-on-clone evidence

- Resident tasks / simulations:
- Search / click / navigate / read behavior:
- Answer grounding / source behavior:
- Model-assisted fallback behavior when applicable:
- Wrong-action / failure evidence:
- Known limitations:

## API and schema

- Schema version:
- Provider/model impact:
- Freshness/evidence impact:
- Failure codes:
- Timeout/retry/model-fallback/provider-fallback:
- Request ID/telemetry:

## Actual-site integration — Gate H only

<!-- Leave N/A unless the institution has actually opened the first-party integration phase. -->

- Institutional authorization / operating scope:
- Deployment/hosting owner:
- Credentials/secret owner:
- Information-security scope:
- Privacy/PII scope:
- Authentication/submission/payment/write scope:
- Internal-system integration:
- Monitoring/incident/support owner:
- Staging/rollback:

These Gate H items are future production requirements and are not mandatory fields for ordinary pre-integration clone-MVP work.

## Migration and compatibility

- Data/config migration:
- Legacy IDs / URLs:
- Dual-read / dual-serve period:
- Deprecation:

## Deployment

- [ ] No deployment impact
- [ ] Preview/debug only
- [ ] Controlled stakeholder clone surface
- [ ] Production integration
- Environment:
- Deployment method:
- Expected deployed SHA:
- Secrets owner:
- Smoke plan:

Clone-MVP generation/demonstration is not actual-site integration approval.

## Rollback / isolation

-

## Known limitations, exceptions and follow-ups

-

## Pre-merge exact-head check

- [ ] Remote `main` FULL SHA rechecked
- [ ] Open PR / relevant issue state rechecked
- [ ] PR exact head SHA rechecked
- [ ] Base / behind state rechecked
- [ ] Exact changed filenames and diff rechecked
- [ ] Exact-head CI complete for required checks
- [ ] Mergeability rechecked
- [ ] Comments, reviews and unresolved threads rechecked
- [ ] No unexpected artifacts, secrets, PII or private customer data
- [ ] No structural-preview / clone / exact / actual-site status overclaim
- [ ] Head unchanged since readiness review

## Merge rule

- [ ] Squash merge only
- [ ] Exact current head supplied as `expected_head_sha` / equivalent lease
- [ ] No direct push to `main`
- [ ] No rebase/amend/force-push without explicit project-owner approval
- [ ] No assertion/skip/xfail/coverage weakening to obtain green CI
