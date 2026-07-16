# Clone-First General Site Platform Strategy

## Purpose

This document records the **strategic direction** for extending the clone-first approach to multiple municipal sites, as initiated by #1181. It describes the architectural gates that each site onboarding and capture-to-promotion pipeline must follow.

This document is a **strategy and planning reference** only. It does **not** authorize implementation of a multi-site platform or live integration. The current product remains Buk-gu-specific. All implementation work requires separate issues, PRs, and approvals.

## Governing policy

Visual fidelity and promotion are governed by:
- [`docs/product/clone-visual-fidelity-and-promotion-policy.md`](./clone-visual-fidelity-and-promotion-policy.md) — visual approval, promotion gate, and incident policy
- [`docs/product/exact-official-site-clone-invariant.md`](./exact-official-site-clone-invariant.md) — exact clone definition and invariant

## Gates for every site onboarding / capture / migration

Each new site follows six stages. No stage is implied by completion of an earlier stage.

### 1. Capture completeness

All target routes, regions, and assets for the site scope are captured from the official site via authorized reference capture. The manifest `capture_required` list is populated and tracked.

**Output:** capture inventory, authorization record, captured reference artifacts.

### 2. Structural / content parity

The captured content is committed as structured fixtures. The fixture reproduces the official page DOM structure, text, links, tables, and controls.

**Output:** canonical fixture JSON, browser projection, structural parity tests.

### 3. Asset mapping

Official-site imagery referenced in fixtures is inventoried, hashed, and evaluated for repository identity matching. Assets are either resolved (downloaded, committed, wired) or tracked as unresolved with metadata.

**Output:** asset identity audit, asset resolution PRs, wired asset projections.

### 4. Interaction parity

Within the fixture scope, user interactions produce the same visible outcomes as the official site. Navigation, form controls, pagination, and dynamic behaviors are wired.

**Output:** E2E interaction parity tests.

### 5. Visual review

The candidate renderer is compared side-by-side against the accepted visual reference at required viewports (1440×1000 desktop, 390×844 mobile minimum). Material differences are documented. CI screenshots, automated diffs, and model reviews are evidence — not approval.

**Output:** visual comparison evidence, `comparison-notes.md`.

### 6. Resident-default promotion

After visual review approval by the project owner, the renderer is promoted to the resident-facing default route. The approval record is stored in `docs/artifacts/visual-approvals/<site_id>/<route_id>/`.

**Output:** `approval.md`, updated resident-default route configuration.

## Key principles

### Generic renderers are preview/debug until approved

A generic renderer (one that supports multiple sites through parameterization) must be tested on a **preview/debug route** before receiving project-owner visual approval. The generic renderer must not auto-promote to resident-default for any site without passing the full approval process.

### Dual-run parity includes visual comparison

"Parity" between two renderer modes (e.g., deterministic vs. Page Agent) is not limited to DOM/action parity. It must also include comparison against the accepted visual reference. Two modes may produce the same DOM structure but differ in visual presentation; that difference must be evaluated during visual review.

### Buk-gu is the golden reference, not visual golden approval

Buk-gu is the first golden reference adapter. Structural fixture completion for Buk-gu does **not** imply visual golden approval. The same approval process applies to Buk-gu as to any future site.

### Multi-site reuse does not weaken the visual gate

The visual fidelity gate, promotion rules, and fail-closed state model established in the governing policy apply uniformly across all sites. Platform reuse reduces engineering overhead but does not reduce approval requirements.

### Automation goal: supervised onboarding

The long-term automation goal is **supervised onboarding** — tooling that accelerates capture, fixture generation, asset mapping, and interaction test creation, while keeping every promotion gated by human visual review. Unreviewed resident-default promotion is not a goal.

## Relationship to #1181

- #1181 is the multi-site platform parent issue.
- This document records the strategic direction informed by #1181.
- This document does **not** implement #1181, create a second municipal adapter, or authorize live integration.
- The clone-first-platform ADR (`docs/architecture/clone-first-platform-adr.md`) records the architecture decision for the Buk-gu golden reference and compatibility-first migration rules.

## Non-authorization statement

This document is a **future strategy reference**. None of the following are authorized by this document:

- Implementation of a multi-site platform compiler or runtime
- Onboarding of a second municipal site
- Live official-site retrieval, crawling, or API calls for any site
- Promotion of any generic renderer to resident-default
- Weakening of the exact-clone invariant or visual approval policy for any site

All such work requires separate issues, PRs, and project-owner approval.
