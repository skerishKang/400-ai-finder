# Clone-First General Site Platform Strategy

- 상태: `canonical`
- 기준일: 2026-08-12
- 현재 정렬 이슈: #1301
- active onboarding validation: #1232
- historical foundation: #1181, #1283, #1287

## 1. Purpose and precedence

This document is the **canonical product-lifecycle owner** for the ordinary pre-integration 400-ai-finder product path.

The repository has many historical stage documents, audit notes, experiments, and issue bodies. When current documents disagree about the order of a named site's onboarding, use this lifecycle first, then apply the narrower exact-clone, visual-promotion, release-gate, repository-governance, network, and runtime contracts.

Related governing documents:

- [`docs/product/PRODUCT_TRACKS_AND_BOUNDARIES.md`](./PRODUCT_TRACKS_AND_BOUNDARIES.md) — product-track separation
- [`docs/product/exact-official-site-clone-invariant.md`](./exact-official-site-clone-invariant.md) — rules when an `exact` claim is made
- [`docs/product/clone-visual-fidelity-and-promotion-policy.md`](./clone-visual-fidelity-and-promotion-policy.md) — visual/promotion authority
- [`docs/implementation/RELEASE_GATES.md`](../implementation/RELEASE_GATES.md) — readiness gates
- [`docs/operations/REPOSITORY_GOVERNANCE.md`](../operations/REPOSITORY_GOVERNANCE.md) — branch/PR/merge workflow
- [`docs/operations/PROJECT_OWNER_AUTHORITY_AND_MVP_BOUNDARY.md`](../operations/PROJECT_OWNER_AUTHORITY_AND_MVP_BOUNDARY.md) — institution-leader MVP audience, project-owner authority, and Phase-A/Production legal boundary

## 2. Product decision: clone MVP now, actual-site integration later

400-ai-finder has two deliberately separate product phases.

### Phase A — pre-integration faithful-clone MVP

Before an institution authorizes our company to operate or integrate its actual production website, the working product is a **repository-controlled faithful clone MVP**.

The stakeholder experience is:

```text
left  = the target institution's website reproduced as faithfully as the declared MVP scope requires
right = AI conversation / answer / search / navigation / bounded Browser Use
```

The clone is the normal development, test, demonstration, and stakeholder-evaluation surface. AI Finder/Browser actions operate on the clone, not on the institution's production website.

The business objective is to let an institution decision-maker experience:

```text
"our existing website + AI"
```

not a redesigned substitute website and not a generic government-site mockup.

For every named-site MVP, the primary evaluation audience is the target institution's representative, institution head, executive, or equivalent final decision-maker.

For the declared MVP scope, fidelity is therefore a product requirement. A model, agent, reviewer, or implementation worker must not arbitrarily lower the left-side fidelity merely because the actual production-site integration phase has not started yet.

### Phase B — authorized first-party actual-site integration

The actual institution website is a **later stage**.

Only after the institution explicitly authorizes deployment/operation/integration does the project open the first-party actual-site workstream. At that point the project evaluates the concrete production environment and its operational requirements, including credentials, deployment ownership, information security, privacy/PII, authentication, submissions, internal-system integration, incident response, support ownership, rollback, copyright/licensing, redistribution rights, legal/administrative obligations, and other formal rights/obligation relationships.

Those future production concerns are not prerequisites for building, testing, and demonstrating the pre-integration faithful-clone MVP unless the project owner explicitly opens a specific review earlier.

Clone MVP completion must never be described as actual-site control. Conversely, actual-site integration must never be treated as a prerequisite to making the clone visually convincing and functionally useful.

## 3. Canonical lifecycle for a named real site

For a named real institution/site such as Buk-gu or Seo-gu, the ordinary sequence is:

```text
TARGET ACTUAL SITE
(reference source; not our production runtime)
        |
        | scoped read-only reference capture when needed
        v
POINT-IN-TIME REFERENCE BASELINE
(routes / DOM / text / assets / screenshots / provenance)
        |
        v
REPOSITORY-CONTROLLED CLONE CANDIDATE
(faithful reproduction inside the declared MVP scope)
        |
        | structural / content / asset / interaction / visual comparison
        v
CLONE MVP READY
        |
        v
AI FINDER / BROWSER ON THE CLONE
(answer / search / click / navigation / bounded Browser Use)
        |
        | optional explicit recapture when the source needs refreshing
        v
NEW REFERENCE + NEW CLONE CANDIDATE VERSION

--- later, separately authorized ---

INSTITUTION AUTHORIZATION / OPERATING AGREEMENT
        |
        v
FIRST-PARTY ACTUAL-SITE INTEGRATION
```

A new public-site change does not silently mutate an already approved clone. Refresh is an explicit new capture/version/review event.

## 4. Clone != continuous live mirror

The normal clone runtime must not depend on continuously proxying or retrieving the public source site merely to render its citizen-facing surface.

A clone is a **point-in-time, versioned, reproducible product artifact**.

Reference refresh may happen through a deliberate workflow such as:

- owner/operator-triggered recapture;
- a separately approved scheduled refresh;
- controlled read-only comparison;
- separately governed answer-time freshness where that capability is intentionally in scope.

None of these modes silently converts the clone into a permanent live mirror or reverse proxy.

Recommended baseline identity includes, where applicable:

- `source_url`
- `captured_at`
- `source_updated_at`
- route/state/viewport scope
- deterministic checksum or snapshot identity
- source commit / generator identity
- unresolved or `capture_required` items

## 5. Platform structural development != named-site onboarding

Two workflows must not be confused.

### 5.1 Platform/core structural development

Generic platform engineering may use synthetic or offline fixtures to validate:

- SiteSpec contracts;
- archetype/capability contracts;
- generic Site Model semantics;
- structural renderer/preview behavior;
- knowledge/action graph contracts;
- QA/reporting machinery;
- exception handling.

No actual-site capture is required for this type of core engineering evidence.

However, a synthetic/offline structural proof is **not evidence that a named real site has been cloned**.

### 5.2 Named real-site onboarding

For a named real site, the first product evidence is the scoped point-in-time reference baseline. The clone candidate is then compared against that baseline.

Therefore:

```text
structural generated preview
!= reference baseline ready
!= clone candidate
!= clone MVP ready
!= exact
!= resident/default approved
!= actual-site integrated
```

Merged Seo-gu structural/offline work under #1232 remains valid generic platform evidence, but it must not be described as Seo-gu clone or visual-parity completion until a real Seo-gu reference baseline and faithful clone candidate are compared.

## 6. Minimum faithful-clone state below full `exact`

Not every MVP must clone every route of an institution before AI work can begin. The MVP scope may be deliberately bounded.

For example, a first municipal scope may include the homepage, global navigation, selected in-scope civil-service pages, notice/board pages, organization/contact pages, and selected in-scope document routes.

The rule is:

> The scope may be narrow, but the pages and states declared inside the clone scope must not be arbitrarily redesigned.

A `clone_mvp_ready` surface should therefore have, within its declared scope:

- captured reference evidence;
- header/footer/global navigation fidelity;
- layout/theme/typography/color fidelity appropriate to the reference;
- representative text/content structure;
- important images/assets or explicitly recorded unresolved equivalents;
- key controls/interactions;
- desktop/mobile evidence where relevant;
- explicit exceptions for uncaptured or unresolved areas.

The existing `exact` invariant remains a stronger claim. `clone_mvp_ready` does not automatically mean `exact` or resident-default promotion.

## 7. Capture and fidelity gates for named sites

### 7.1 Reference completeness

Declare the intended MVP route/state/viewport scope and capture the source evidence needed to judge that scope.

**Output:** reference inventory, source URLs, capture metadata, DOM/content/screenshot/assets evidence, unresolved items.

### 7.2 Structural/content parity

The clone candidate reproduces the scoped page structure, visible content, links, tables, controls, and navigation semantics rather than replacing them with a simplified substitute.

**Output:** clone candidate, structured fixtures/model where applicable, structural/content comparison.

### 7.3 Asset mapping

Important visible assets are mapped to the clone candidate or explicitly tracked as unresolved. Asset/provenance bookkeeping is separate from fidelity assessment; unresolved repository/public-release questions must not be silently converted into permission to redesign the clone.

**Output:** asset identity/mapping status and unresolved list.

### 7.4 Interaction parity

Within scope, expected navigation and visible interactions behave like the reference experience unless an intentional MVP exception is documented.

**Output:** browser/E2E evidence and exception list.

### 7.5 Visual review

Compare source reference and clone candidate side by side at required viewports. Automated screenshots/diffs are evidence, not the sole approval authority where explicit visual approval is required.

**Output:** comparison evidence and material-difference notes.

### 7.6 AI-on-clone proof

Only after a named site has a reviewable clone surface should the site-level onboarding claim include AI search/navigation/Browser Use validation on that clone.

The AI layer may be separate on the right side; it must not simplify or redesign the left official-site clone merely for implementation convenience.

## 8. Stakeholder-evaluation mode

The ordinary pre-integration clone MVP is a controlled stakeholder/development evaluation surface, not proof that our company currently operates the institution's production website.

Within this phase:

- faithful reproduction is an explicit product objective;
- the primary evaluator is the target institution's representative, institution head, executive, or equivalent final decision-maker;
- the model/agent must not invent additional actual-site deployment requirements as blockers to clone fidelity work;
- copyright, licensing, administrative, legal, rights/obligation, public-redistribution, and other formal Production concerns are evaluated when the first-party/Production phase is actually opened, unless the project owner explicitly asks to open a specific review earlier;
- information-security, privacy, authentication, real submissions, production credentials, and actual operational ownership are likewise evaluated when the first-party phase is actually opened;
- confidential customer/institution business facts are not placed in public repository issues, PRs, or docs;
- public/open-source redistribution decisions are separate from whether the internal/controlled clone should faithfully reproduce the reference.

Existing provenance/rights records may continue as repository hygiene and future-release inputs, but they are not to be misread as a blanket blocker on controlled faithful-clone development or stakeholder demonstration.

Legal/administrative/business judgment authority belongs to the project owner. AI/model/agent/reviewer workers provide evidence, technical analysis, and requested research; they do not override an explicit project-owner decision or elevate unsolicited general legal concerns into product blockers.

## 9. Generic platform principles

### Reuse without generic-looking output

The platform should avoid one bespoke renderer per institution, but reuse must happen beneath the visible product surface.

Site-specific differences should be expressed primarily through:

- data;
- configuration;
- theme tokens;
- parser/capability profiles;
- explicit reviewed overrides.

The shared engine may be generic while each rendered clone remains recognizably the target institution's site.

### Buk-gu remains the first protected golden

Buk-gu remains the first protected municipality golden reference. Generic work must not weaken its frozen compatibility contracts merely to simplify platform architecture.

### Automation is supervised, fidelity is not optional

The initial supervised-automation target remains a 70–80% operating target, with an explicit exception queue. Automation percentage measures how much of the onboarding pipeline was produced automatically; it is **not** evidence of clone fidelity by itself.

Low-confidence, unsupported, missing-asset, capture-required, and parser/runtime gaps remain visible rather than being hidden to inflate the automation rate.

## 10. Relationship to #1232

#1232 is the active multi-site onboarding validation track.

Current interpretation:

1. Buk-gu — protected golden reference.
2. Seo-gu — generic structural platform evidence exists, but faithful-clone/visual proof is still required.
3. A materially different third-site proof must not be counted as the next named-site success until the second-site faithful-clone sequence is demonstrated.

The next named-site product proof after this documentation alignment is therefore:

```text
Seo-gu scoped reference baseline
  -> Seo-gu faithful clone candidate
  -> source-vs-clone review
  -> AI/navigation validation on the clone
```

not another structural-only site preview.

## 11. Actual-site integration is intentionally deferred

This strategy does not authorize control of an institution's actual production website.

The actual-site phase begins only after explicit institutional authorization/operating responsibility is established. That future phase may then define the real deployment architecture and the security/privacy/operations requirements, copyright/licensing/redistribution rights, legal/administrative obligations, and other formal relationships appropriate to that institution.

Until then, development and stakeholder evaluation remain clone-first, and those future Production concerns are not ad-hoc blockers to Phase-A fidelity unless the project owner explicitly opens them earlier.
