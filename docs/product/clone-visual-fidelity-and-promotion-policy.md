# Clone Visual Fidelity and Promotion Policy

## 1. Purpose and scope

This policy governs **visual fidelity review** and **resident-default promotion** for all cloned official-site surfaces in the 400-ai-finder product. It applies to every candidate renderer that presents an official-site fixture to the resident/user-facing product path.

The policy establishes:

- Independent readiness dimensions that must each be satisfied before promotion
- A fail-closed state model — no promotion without documented visual approval
- Required evidence, viewport coverage, and human approval authority
- Bounded maintenance rules that preserve approved baselines under narrow conditions
- Rollback and erratum procedures

This policy supplements the [exact-official-site-clone-invariant](./exact-official-site-clone-invariant.md). The invariant defines what an exact clone **is**; this policy defines how a renderer **becomes** an approved resident-facing clone.

## 2. Governing principle

A structurally complete fixture or renderer is **not** automatically an approved visual clone. No renderer may become the resident-facing default until it has been compared against the accepted reference and explicitly approved by the project owner.

CI evidence, automated screenshots, model review, and developer self-review are necessary evidence but **cannot grant first-promotion approval**. Only a human project owner performing a documented side-by-side visual review can authorize first promotion.

## 3. Readiness dimensions

The following six dimensions are **independent**. Progress in one does not imply progress in another.

### 3.1 Capture completeness

All official-site pages, regions, and assets within scope have been captured (via authorized reference capture or committed source inventory). The manifest `capture_required` list is empty for the route scope.

**State:** `capture_required` (incomplete), `capture_complete`

### 3.2 Structural / content parity

The fixture reproduces the official page's DOM structure, text content, link targets, tables, rows, controls, and ordered items. Interactivity (click, navigate, form) is wired as far as the fixture permits.

**State:** `structure_ready`

### 3.3 Asset mapping readiness

Official imagery (icons, photos, banners, logos) referenced in the fixture has been identified in the official-source inventory. Candidates for local repository matching have been evaluated.

**State:** `asset_mapping_ready`

### 3.4 Interaction parity

User interactions (navigation clicks, form input, pagination, tab switching, accordion expand/collapse) produce the same visible outcomes as the official site within the fixture's scope.

**State:** `interaction_ready`

### 3.5 Visual fidelity review

The candidate renderer has been compared against the accepted visual reference (side-by-side at specified viewports). Material visual differences have been documented. A human project owner has reviewed the comparison and recorded explicit approval or rejection.

**State:** `visual_review_pending`, `visual_review_approved`, `visual_review_rejected`

### 3.6 Resident-default approval

The renderer has passed visual review and has been explicitly approved by the project owner for the resident-facing product default route.

**State:** `resident_default_approved`

## 4. Terminology

Terms **must not** be treated as interchangeable:

| Term | Meaning |
|------|---------|
| `capture_required` | Incomplete capture; route not yet fixture-ready |
| `structure_ready` | Structural/content parity achieved; visual fidelity not established |
| `asset_mapping_ready` | Official asset inventory complete; local promotion not yet performed |
| `interaction_ready` | Interaction parity achieved within fixture scope |
| `visual_review_pending` | Visual comparison not yet completed or reviewed |
| `resident_default_approved` | Full approval granted; renderer serves as resident-facing default |
| `exact` | Reserved for routes that satisfy all applicable dimensions and have explicit project-owner approval |

`exact` is **not** a synonym for "structurally complete" or "textually complete."

## 5. Fail-closed state model

- Without visual approval, a candidate renderer exists **only** on the preview/debug route.
- Without a complete or valid approval record, the renderer **must not** be promoted to resident default.
- A candidate that substitutes unresolved official imagery with generic cards, emoji, or arbitrary placeholders is **not** an exact approved clone.
- Generating a screenshot is **not** approval.
- A screenshot without a side-by-side reference comparison is **evidence only**, not approval.
- Model review, CI results, developer self-review, and local-worker reports are **non-authorizing** evidence. They inform the project owner but cannot grant approval.
- First resident-default promotion requires the project owner's direct visual review and explicit recorded approval.

## 6. Reference and baseline ownership

Each approved baseline requires:

- **Accepted reference identity**: the SHA, capture date, and source URL of the official-site reference used for comparison
- **Candidate renderer identity**: the renderer module path, its integrity SHA, and its provenance chain (fixture JSON → generator → projection)
- **Approval record**: the approval.md artifact (see §17–18) stored in the visual-approvals directory

The accepted reference is **owned** by the project owner or their delegate. The reference must be an unmodified capture of the official site at a known point in time.

## 7. Required viewport evidence

Visual comparison evidence must cover at minimum:

- **Desktop**: 1440×1000 viewport (full page or content-area screenshot)
- **Mobile**: 390×844 viewport (full page or content-area screenshot)

Additional viewports may be required by the project owner for routes with specific responsive behavior.

## 8. Side-by-side visual review

The review must present reference and candidate images adjacent (left/right or overlay) at the same viewport dimensions. The reviewer must inspect:

- Layout and spacing fidelity
- Typography and text alignment
- Color and contrast consistency
- Image and icon placement
- Responsive behavior at specified breakpoints
- Interactive element appearance (hover, focus, active states where captured)

Differences must be classified as:

- **Material**: visible to a casual user; affects comprehension, navigation, or trust
- **Acceptable**: within the tolerance defined by the project owner for the route
- **Resolved**: previously flagged and now corrected

## 9. Human approval authority

| Role | May approve |
|------|-------------|
| Project owner (CTO or designated representative) | First promotion, re-approval after drift, superseding baselines |
| Developer / CI / model / local worker | **No** — evidence contributor only |
| Automated screenshot diff tool | **No** — evidence contributor only |
| Third-party reviewer delegated by project owner | Yes, with explicit written delegation recorded in the approval artifact |

## 10. Approved renderer identity and SHA

The approval record must capture:

- **Renderer module path** (e.g., `citizen-action-demo-canvas.js`)
- **Fixture identity** (e.g., `fixture_id`, `fixture_sha256`, `clone_status`)
- **PR head SHA** at the time of approval
- **Generator version** where applicable
- **All committed asset SHAs** that materially affect the visual output

## 11. Drift detection

After approval, drift is detected by:

- Comparing the approved baseline candidate screenshot against current renderer output at the same viewports
- Running the comparison through the same side-by-side review process (§8)
- Identifying any material visual differences introduced since approval

Drift requiring re-approval: any material difference not covered by bounded maintenance (§15).

## 12. Preview/debug route versus resident-default route

Every candidate renderer must be accessible via a **preview/debug route** before and during visual review. The preview route:

- Is **not** the resident-facing product entry point
- May display diagnostic overlays, fixture boundaries, or version labels
- Must be accessible without authentication (on localhost or CI preview deploy)

Promotion to the resident-default route removes preview-only affordances and sets the renderer as the primary citizen surface.

**Preview/debug candidates must not automatically control the resident-default route.** A candidate may only become the resident default via the explicit approval process defined here.

## 13. Unresolved asset and fallback rules

- Unresolved official imagery (not yet downloaded, mapped, or committed) must not be replaced with generic cards, emoji, or arbitrary placeholders in the resident-facing renderer.
- Fixture metadata may record unresolved assets (e.g., `data-source-asset-url`).
- The renderer must fail closed when unresolved assets would cause visual degradation in the resident-facing path.
- A renderer with unresolved official assets is **not** an exact approved clone and **cannot** be approved as resident-default until those assets are resolved or a documented exemption is granted by the project owner.

## 14. First promotion

First promotion of any renderer to the resident-default route requires:

1. All six readiness dimensions evaluated (§3)
2. Visual review evidence at required viewports (§7–8)
3. Side-by-side comparison with accepted reference (§8)
4. Project-owner direct visual review and explicit approval (§9)
5. Signed approval record (§18)
6. Evidence-bearing PR (§16)

Without these, the candidate **must not** be promoted.

## 15. Bounded maintenance changes

Changes that **do not** require full re-approval are limited to those satisfying **all** of:

1. Renderer identity and route composition are preserved (no new modules, no route refactors)
2. Official asset set has not materially changed (no new images replacing existing ones, no deleted assets affecting layout)
3. Major layout, spacing, hierarchy, and responsive composition are unchanged
4. The approved baseline remains valid (not superseded, not rolled back)
5. Change scope and tolerance thresholds are documented in a PR or issue referenced by the approval record

When any condition is **not** met, the change requires first-promotion-level re-approval by the project owner.

### Examples of bounded maintenance

- Text content update from fixture regeneration (same DOM structure, same layout)
- CSS-only color palette adjustment within pre-approved tolerances
- Bug fix that restores a previously approved visual state after accidental drift

### Examples requiring full re-approval

- Route addition or removal affecting the visual composition
- Layout restructuring (column count, spacing system, responsive breakpoints)
- Asset substitution (new official images, icon set replacement)
- Interactive behavior change (new controls, removed controls, different navigation patterns)

## 16. Evidence-bearing PR requirements

Every PR that proposes a visual change to an approved renderer or first-time promotion must include:

| Field | Requirement |
|-------|-------------|
| Related issue | Issue number(s) |
| Base SHA | Full 40-char SHA of the base commit |
| Proposed PR head SHA | Full 40-char SHA of the PR's head |
| Previous renderer identity/SHA | Renderer path + integrity SHA before change |
| Proposed renderer identity/SHA | Renderer path + integrity SHA after change |
| Readiness state before | §3 dimension states |
| Readiness state after | §3 dimension states |
| Accepted reference artifact path | Path to reference screenshot |
| Candidate artifact path | Path to candidate screenshot |
| Desktop viewport | Reference + candidate at 1440×1000 |
| Mobile viewport | Reference + candidate at 390×844 |
| Material visual differences | Description or "none" |
| Unresolved assets and fallbacks | List of remaining unresolved assets |
| Interaction parity evidence | Reference to E2E test results |
| CI/check evidence | Link to CI run or local test output |
| Project-owner approval | Path to approval record, or explicit "not yet approved" with reason |
| Rollback renderer/SHA | Previous approved renderer identity for rollback |
| Network/live/provider activity | Declaration: "none" or detailed list |
| Confidential-data declaration | Declaration that no confidential/PII data is included |

`N/A` is permitted for fields that do not apply to a given PR, but the **reason** for `N/A` must be stated.

## 17. Artifact storage and naming

Visual approval artifacts are stored under:

```
docs/artifacts/visual-approvals/<site_id>/<route_id>/<pr-number>-<head-sha>/
```

### Required files

```
reference-desktop-1440x1000.png
candidate-desktop-1440x1000.png
reference-mobile-390x844.png
candidate-mobile-390x844.png
comparison-notes.md
approval.md
```

- Screenshots are optional when the PR explicitly states a reason for their absence (e.g., "fixture-only change, no visual difference expected — N/A because renderer output is deterministic text and layout with no external imagery").
- `comparison-notes.md` documents the reviewer's findings during side-by-side comparison.
- `approval.md` is the canonical approval record (see §18).

This PR (#1199) does **not** create or commit any screenshot binaries; it codifies the storage rule only.

## 18. Approval record

`approval.md` must contain:

| Field | Description |
|-------|-------------|
| site | Site identifier (e.g., `bukgu_gwangju`) |
| route | Route identifier (e.g., `home`) |
| accepted reference identity | Reference SHA, source URL, capture date |
| candidate renderer identity | Renderer path, integrity SHA, fixture identity |
| PR head SHA | Full 40-char SHA |
| tested viewport | Viewport dimensions evaluated |
| material differences | Description of any differences found and their classification |
| unresolved assets / fallbacks | List of assets not yet resolved at approval time |
| approver authority | Role (project owner / delegate) |
| approval result | Approved, rejected, or conditionally approved with conditions listed |
| approval date | ISO 8601 date |
| superseded approval | Link to prior approval.md if replacing an existing baseline |
| rollback identity | Renderer identity to revert to if rollback is needed |

## 19. Superseding an approved baseline

To replace an existing approved baseline:

1. Complete the same first-promotion process (§14) for the candidate
2. The new approval record must reference the superseded approval record
3. The old approval record is retained (not deleted) with a note that it is superseded
4. The rollback identity in the new record points to the superseded renderer

## 20. Rollback procedure

When an approved resident-default renderer exhibits unapproved visual drift:

1. Identify the drift. A material visual difference from the approved baseline warrants rollback.
2. Determine rollback target: the previous approval record's `rollback identity`.
3. Create a rollback PR that restores the renderer to the previous approved identity.
4. The rollback PR must include a `comparison-notes.md` documenting the drift and the restoration.
5. The rollback PR does **not** require new visual approval (it restores a previously approved state).
6. After rollback, the original approval record remains valid. The project owner may authorize re-application of the change that caused drift, subject to full re-approval.

## 21. Incident and erratum procedure

When an approved state is found to have been reached without proper process, or when a historical document is found to have been used as authority for something it did not establish:

1. **Do not delete or rewrite** the historical document. Preserve the original text.
2. Add a visible **erratum** section (marked with date and issue number) at the top of the document.
3. The erratum must state:
   - What the document did establish
   - What the document did **not** establish
   - How the document was subsequently misinterpreted or misapplied
   - The corrective action taken
4. If a renderer was promoted without proper approval, demote it to preview/debug route until proper approval is completed.
5. Record the incident in the relevant approval record's `comparison-notes.md` or a dedicated `erratum.md` in the same directory.

## 22. Relationships to #1080, #1181, #1197, #1198 and #1199

| Issue | Relationship |
|-------|-------------|
| #1080 | Exact fixture long-term program. This policy defines the visual approval gate that #1080-expanded fixtures must pass before promotion. |
| #1181 | Multi-site platform strategy. This policy applies to every site onboarded under #1181. Visual fidelity gate is independent of site count; multi-site reuse does not weaken it. The clone-first strategy document (`./clone-first-general-site-platform-strategy.md`) expands on this relationship. |
| #1197 | Restoration of the approved home composition (PR #1200, SHA `87db3e1ce7d01646a8fc0e8eed6ce2fc63b7ebaa`). Completed recovery work. This policy codifies the gate that was missing when the #1197 restoration became necessary. |
| #1198 | Permanent visual approval gate (automated/repository promotion gate). This policy defines the human-process rules; #1198 tracks the automated/repository tooling to enforce and record them. |
| #1199 | Policy and document governance (this issue). Establishes this document, the exact-clone invariant additions, the document inventory, the #1170 erratum, and the PR template. |
