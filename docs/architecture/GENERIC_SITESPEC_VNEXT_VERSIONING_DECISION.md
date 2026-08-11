# Generic SiteSpec vNext — Versioning and Compatibility Decision

- Status: `active-plan`
- Date: 2026-08-12
- Issue: #1287
- Phase: Slice A — architecture/versioning decision
- Inventory baseline: `0372be87159e6693e67f4a75994827559d23f121`
- Runtime/schema mutation authorized by this document: **none**

## 1. Decision

The existing `configs/sitespec.schema.json` remains the **SiteSpec v1 Buk-gu identity / compatibility contract**.

Generic multi-site onboarding will use a **new additive vNext contract namespace beside v1**. Slice B must not rewrite v1 in place.

The migration direction is:

```text
SiteSpec v1
  current Buk-gu canonical identity / legacy compatibility
  unchanged
        |
        | later adapter/projection proof
        v
Generic SiteSpec vNext
  arbitrary-site onboarding contract
  identity + domains + entry points
  + archetype + capabilities
  + capture/browser/knowledge/action policy
  + provenance + typed extensions
```

The first vNext contract slice is data/schema/test only. It does not wire a resident runtime, add a real second site, execute live capture, or change Production.

## 2. Why v1 is preserved

Phase 0 inspection found that v1 is not merely a loose configuration file.

### v1 owns current Buk-gu compatibility semantics

`configs/sitespec.schema.json` currently requires:

- canonical `site_id`
- `legacy_ids`
- municipal `jurisdiction` with effective-date history
- `display`
- `domains.public`
- `runtime.python_profile`
- `runtime.cloudflare_adapter`
- `clone.golden_commit` and subject

The `clone` schema description is explicitly tied to the frozen Buk-gu golden identity.

### Python loading depends on v1 projection semantics

`SiteProfileLoader` currently resolves:

```text
requested identifier
 -> v1 SiteSpec resolver
 -> canonical SiteSpec
 -> runtime.python_profile
 -> YAML SiteProfile
```

After a SiteSpec resolves, `runtime.python_profile` is authoritative and missing/malformed projection fails closed. This behavior is already contract-tested.

### Frozen compatibility registry has a separate purpose

`configs/site-registry.json` is the current Buk-gu frozen reference-adapter registry, not a generic multi-site inventory.

Its tests intentionally require exactly one adapter and reject a copied second-site adapter. Slice B must not repurpose it.

### Runtime vocabulary has a separate purpose

`configs/contracts/runtime-vocabulary.json` / schema are current-state inventory/drift artifacts with:

```text
inventory_only: true
runtime_wired: false
```

They are not generic SiteSpec/runtime configuration inputs and must not be promoted to that role by Slice B.

## 3. Namespace decision for Slice B

Slice B must add new files whose names cannot be confused with v1 `*.sitespec.json` files consumed by the current `SiteSpecResolver` glob.

### Reserved v1 paths — unchanged

```text
configs/sitespec.schema.json
configs/sites/*.sitespec.json
```

The current resolver reads `configs/sites/*.sitespec.json`. Therefore **vNext instances must not use the `.sitespec.json` filename suffix inside `configs/sites/` in Slice B**.

### Chosen vNext schema namespace

Slice B should use:

```text
configs/platform/site-spec-v2.schema.json
configs/platform/archetype.schema.json
configs/platform/capability.schema.json
configs/platform/onboarding-report.schema.json
```

Synthetic fixtures should live only under tests, for example:

```text
tests/fixtures/platform/site-spec-v2/
  municipality.json
  university.json
  financial.json
  unknown.json
```

This naming is deliberate:

- it does not collide with the v1 resolver glob;
- it keeps platform contracts separate from current runtime projections;
- it permits a future loader to opt into v2 explicitly;
- it does not imply that v1 is deprecated or removed.

## 4. Versioning rule

The new generic contract line starts as schema version **`2.0.0`**.

Meaning:

- `1.x` continues to mean the current Buk-gu identity/compatibility SiteSpec family;
- `2.x` means the new generic onboarding contract family;
- v2 is not silently accepted by the v1 resolver;
- no automatic v1 -> v2 write migration is introduced in Slice B;
- a later Slice C adapter may project v1 Buk-gu data into a v2 object for parity testing.

Using `2.0.0` is a semantic break in the contract model, not a claim that the whole product/runtime is version 2.

## 5. Generic v2 core ownership

The v2 **core** should contain only site-agnostic concepts.

Required conceptual groups:

```text
$schema
schema_version
identity
domains
entry_points
archetype
capabilities
capture_policy
browser_policy
knowledge_policy
action_policy
provenance
extensions
```

### 5.1 Identity

Generic core identity owns:

- canonical `site_id`
- `legacy_ids`
- default display label
- locale display labels

Required semantics retained from v1:

- canonical ID and legacy alias are distinct;
- duplicate aliases fail closed;
- canonical/legacy collisions fail closed;
- display labels are not runtime identifiers;
- identifiers use a closed machine-safe format.

### 5.2 Domains

Generic core owns explicit public-domain scope.

Slice B may support role-tagged domains if the schema remains closed and unambiguous, but it must not infer live authorization from domain presence.

**Target URL/domain presence is not live network authorization.**

### 5.3 Entry points

V2 should have explicit entry points such as homepage and optional search/service roots rather than leaving every runtime to own unrelated URL constants.

This is declarative data only in Slice B; no fetch is performed.

## 6. Archetype contract decision

Initial closed vocabulary:

```text
municipality
university
bank
public_agency
support_portal
company
unknown
```

An archetype record must support:

- `id`
- `state`
- `confidence`
- optional evidence/reference metadata

Initial state vocabulary:

```text
configured
detected
unknown
review_required
```

Confidence is a bounded numeric value from `0.0` through `1.0`.

Rules:

- `unknown` is valid and must not be coerced into the nearest known class;
- low confidence must remain visible to the onboarding report;
- archetype is a parser/QA prior, not permission to hard-code sites by ID;
- archetype does not replace capability detection.

## 7. Capability contract decision

Initial closed capability IDs:

```text
site_search
notice_board
document_library
directory
service_catalog
faq
calendar
form
contact
map_or_location
auth_boundary
```

Initial capability state vocabulary:

```text
configured
detected
unsupported
review_required
not_detected
```

Each capability record must support at least:

- `id`
- `state`
- `confidence`
- zero or more entry-point/route references
- browser/action safety level
- zero or more evidence/provenance references

Confidence is bounded `0.0..1.0`.

A capability marked `unsupported` or `review_required` must remain visible in the onboarding report. It cannot be silently omitted to raise the automation percentage.

## 8. Browser/action safety vocabulary

Slice B needs only a declarative closed safety level, not an executor.

Initial levels:

```text
read_only
navigate
prepare_input
high_risk_boundary
unsupported
```

Meaning:

- `read_only`: inspect/read content only;
- `navigate`: same generated/local surface navigation target can be described;
- `prepare_input`: reversible local preparation may be modeled but no external write is authorized;
- `high_risk_boundary`: authentication, submission, payment, identity verification, personal-file upload or comparable boundary requires separate authorization/policy;
- `unsupported`: no browser/action contract is claimed.

These values do not authorize actual-site control or external writes.

## 9. Typed extensions

Municipal/legal identity must move out of arbitrary-site core semantics.

Initial extension keys may include:

```text
municipality
university
financial
```

Rules:

- extension objects are optional;
- only the extension relevant to the site should be populated unless a reviewed multi-role case requires more;
- municipal `jurisdiction` effective-date semantics belong under `extensions.municipality` in v2 design;
- university and financial sites must not fabricate municipal jurisdiction values;
- v1 jurisdiction behavior remains unchanged.

Slice B should define only the minimum extension fields needed to prove the type separation. It should not attempt a full university/banking ontology.

## 10. Runtime projection separation

V2 canonical data must not require a runtime adapter to exist.

Therefore these v1 concepts do **not** belong in required v2 core identity:

```text
runtime.python_profile
runtime.cloudflare_adapter
clone.golden_commit
clone.golden_commit_subject
```

They remain:

- v1 compatibility/projection fields;
- or later adapter/promotion metadata when applicable.

A future runtime projection may refer to a v2 site, but a site is valid v2 data before Python/Cloudflare adapters exist.

## 11. Onboarding Report contract decision

Slice B should define a separate `onboarding-report` schema rather than storing generated-run state in SiteSpec.

Required groups:

```text
schema_version
run_id
input
acquisition
site_identity
archetype
capabilities
artifacts
metrics
exceptions
provenance
change_scope
promotion
```

### 11.1 Metrics

Required ratios:

```text
automation_ratio
human_review_ratio
unsupported_ratio
```

Each is bounded `0.0..1.0`.

Slice B tests must enforce a deterministic accounting rule. Recommended rule:

```text
automation_ratio + human_review_ratio + unsupported_ratio == 1.0
```

Use a defined decimal tolerance in tests to avoid floating-point noise.

### 11.2 Exception categories

Initial closed categories:

```text
low_confidence_classification
unsupported_component
unsupported_capability
unresolved_asset
source_or_provenance_gap
auth_or_high_risk_boundary
generic_parser_or_runtime_gap
site_specific_override_required
```

Each exception should record:

- stable local exception ID
- category
- severity/review state
- affected artifact/capability reference when applicable
- human-readable summary

### 11.3 Change and promotion flags

Required:

```text
shared_core_changed: boolean
production_promotion_requested: boolean
```

A generated preview normally has `production_promotion_requested:false`.

The report must never use successful generation as evidence of exact/resident-default/Production approval.

## 12. Synthetic Slice B fixture matrix

No real network site is required.

Required offline synthetic cases:

### Municipality

- archetype `municipality`
- municipality extension present
- multiple reusable capabilities
- no fake runtime adapter requirement

### University

- archetype `university`
- university extension present
- no municipal jurisdiction required
- notice/document/directory/calendar capabilities possible

### Financial

- archetype `bank`
- financial extension present
- `auth_boundary` capability demonstrates high-risk separation
- no real account/login/payment operation

### Unknown

- archetype `unknown`
- low confidence/review state allowed
- explicit exceptions required
- schema remains valid without fabricating a known class

These fixtures prove schema semantics only. They do not claim live product support for those industries.

## 13. Slice B protected surfaces

Slice B must leave these unchanged unless a new dedicated migration decision is approved:

```text
configs/sitespec.schema.json
configs/sites/bukgu_gwangju.sitespec.json
configs/site-registry.json
configs/site-registry.schema.json
src/site_profiles/sitespec.py
src/site_profiles/site_profile.py
functions/api/mvp/site-metadata.js
functions/api/mvp/ask.js
configs/contracts/runtime-vocabulary.json
configs/contracts/runtime-vocabulary.schema.json
Buk-gu golden route/target/DOM/state/fixture files
```

Existing tests for v1 resolver/profile/registry/projection/golden behavior remain authoritative and must stay green.

## 14. Slice B allowed change set

The first implementation PR should be limited to new generic contracts, synthetic fixtures, tests and this plan's necessary documentation references.

Expected new contract files:

```text
configs/platform/site-spec-v2.schema.json
configs/platform/archetype.schema.json
configs/platform/capability.schema.json
configs/platform/onboarding-report.schema.json
```

Expected test scope:

```text
tests/test_platform_site_spec_v2_contract.py
tests/test_platform_archetype_capability_contract.py
tests/test_platform_onboarding_report_contract.py
tests/fixtures/platform/site-spec-v2/*.json
```

Exact filenames may be adjusted only if a collision/build reason is documented before implementation. They must remain outside the v1 resolver glob.

## 15. Slice C boundary

Only after Slice B contracts are merged and green should Slice C add a **Buk-gu v1 -> v2 projection proof**.

Slice C must initially be non-resident/non-default and offline.

It should prove:

- canonical site ID parity;
- legacy alias preservation;
- display/domain parity;
- municipal extension derived from v1 jurisdiction;
- current Python/Cloudflare projection IDs remain compatibility metadata, not v2 core requirements;
- Buk-gu golden route/DOM/state behavior is unchanged.

It must not switch the resident runtime to v2 merely because projection parity passes.

## 16. Explicit non-goals

This decision does not authorize:

- a real second-site onboarding;
- live crawling or official-site fetch;
- provider/Firecrawl/API execution;
- generic clone compiler implementation;
- Tool Use/search runtime implementation;
- Browser Use executor implementation;
- `ask.js` refactor;
- Production/Cloudflare environment mutation;
- actual-site control;
- login, payment, submission, identity verification or PII processing;
- v1 removal/deprecation;
- registry repurposing;
- agent/skill changes.

## 17. Exit criteria for Slice A

Slice A is complete when:

- Phase 0 dependency inventory is recorded on #1287;
- v1 preservation is explicit;
- v2 namespace/file-path decision is explicit;
- v1 resolver glob collision is prevented;
- generic vs municipality/runtime/golden ownership is explicit;
- archetype/capability/confidence/state vocabularies are fixed for Slice B;
- onboarding-report metrics/exceptions are fixed for Slice B;
- Slice B protected and allowed files are explicit;
- no runtime/schema behavior was changed by Slice A;
- exact-head CI is green.
