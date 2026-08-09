# Asset, license, and provenance inventory

Status: **active repository inventory / owner decision pending**

Related issue: #1234

## Governing contracts

This inventory is subordinate to the repository's clone and mirror safety contracts:

- `docs/product/exact-official-site-clone-invariant.md` — canonical requirements for official-site clone evidence, provenance, fixture integrity, and exactness claims.
- `docs/GOOGLE_DRIVE_MIRROR_SAFETY.md` — Google Drive/local mirror deletion-safety policy.

Nothing in this inventory relaxes the exact-clone invariant. Technical capture provenance and copyright/reuse permission are separate questions and both must be satisfied where applicable.

## Purpose

This document inventories the current repository's major copyright, license, and provenance classes before any project-wide license is selected.

It is intentionally conservative:

- it does **not** select a license for 400 AI Finder code;
- it does **not** assume public-government website content, screenshots, photographs, logos, icons, or visual design are freely redistributable;
- it does **not** treat a URL, public availability, or government authorship as sufficient reuse permission;
- unknown or incomplete provenance is `REVIEW_REQUIRED`, not implicitly approved.

The inventory covers Git-tracked/public-repository material. The Google Drive/local mirror can contain additional ignored, generated, cached, tool-owned, or local-only files; those files are governed separately by `docs/GOOGLE_DRIVE_MIRROR_SAFETY.md` and must not be deleted merely because they are absent from GitHub.

## Repository-level status

| Class | Current status | Decision |
|---|---|---|
| 400 AI Finder original source code | No root project `LICENSE` approved | `OWNER_DECISION_REQUIRED` |
| Project documentation | No repository-wide outbound license approved | `OWNER_DECISION_REQUIRED` |
| Official-site captures / fixtures / screenshots | Technical provenance exists in parts of the project; redistribution terms are not established repository-wide | `REVIEW_REQUIRED` |
| Third-party vendored Page Agent runtime | Upstream/version/commit/license manifest and synchronized vendored MIT license are present | `DOCUMENTED_THIRD_PARTY` |
| Root Node dependency set | Lockfile-derived package/version/license inventory exists | `DOCUMENTED_PACKAGE_METADATA` |
| Images / logos / official visual assets | Asset-by-asset permission status is not established | `REVIEW_REQUIRED` |
| Fonts/icons or other third-party design assets | No repository-wide manifest yet proves complete coverage | `REVIEW_REQUIRED` |

A missing project license means no project-wide license should be inferred from package metadata, third-party files, README language, or repository visibility.

## 1. Original project code

Substantial first-party implementation exists in `src/`, `functions/`, `scripts/`, `tests/`, `configs/`, project documentation, and build tooling.

Current classification: `OWNER_DECISION_REQUIRED`.

Before adding a root `LICENSE`, the repository owner must explicitly decide:

1. who is authorized to license project-owned code;
2. whether all contributors' contributions can be distributed under that license;
3. whether code and non-code assets use the same or different terms;
4. whether customer/institution-confidential material must be excluded before licensing.

No AI worker may choose MIT, Apache-2.0, GPL, proprietary, or another project-wide license on the owner's behalf.

## 2. Vendored Page Agent runtime

Tracked provenance:

- `src/web/examples/page-agent/source-manifest.json`
- `src/web/examples/page-agent/vendor-manifest.json`
- `src/web/examples/page-agent/vendor/page-agent.iife.js`
- `src/web/examples/page-agent/vendor/LICENSE`

Current pinned identity:

- source package: `@alicloud/page-agent`
- upstream repository: `alibaba/page-agent`
- version: `1.12.1`
- pinned upstream commit: `fa4664dfa5379e6e91deaf85bc1db2ae14d8e1d7`
- upstream license: MIT
- vendored runtime kind: custom non-demo IIFE built locally from pinned upstream source
- vendored bundle size: 208,138 bytes
- vendored bundle SHA-256: `ADE2BD44C77C2555143BD3D008FE9C3527D161C2C922A579471CE8A6C6FA3C74`
- vendored license size: 1,119 bytes
- vendored license SHA-256: `393AD563CE5DD0BBE283EC40F9F5D631817262BC9BBD5EB17ED038A9D9F44803`

The vendored `LICENSE` was rechecked against `alibaba/page-agent` at the exact pinned commit and synchronized to that revision. The pinned upstream notice contains the 2026 SimonLuvRamen and Alibaba Group Holding Limited copyright lines.

The source manifest also records that demo auto-init/testing endpoints/CDN behavior were excluded from the controlled local build and that the local experiment is intended to run without non-local runtime requests.

Current classification: `DOCUMENTED_THIRD_PARTY`.

The controlled Pages build copies the Page Agent example tree including `vendor/LICENSE`, and CI asserts that the built license file exists. This preserves the verified MIT notice alongside the vendored runtime in that output.

Remaining work:

- decide whether a root/project `NOTICE` is needed for other present or future components beyond the already preserved vendored notice;
- preserve manifest/version/commit/hash verification when the vendored file changes;
- never remove the vendored license during bundling;
- if the bundle is rebuilt from a different upstream revision, refresh source, license, hash, and build provenance together.

## 3. Node / browser-test dependencies

The reproducible lockfile-derived report is:

- `docs/legal/NODE_DEPENDENCY_LICENSE_REPORT.md`

Current root lock state resolves:

| Package | Version | Relationship | Lockfile license |
|---|---:|---|---|
| `playwright` | `1.61.1` | direct root dependency | `Apache-2.0` |
| `playwright-core` | `1.61.1` | transitive dependency | `Apache-2.0` |
| `fsevents` | `2.3.2` | optional transitive dependency, Darwin only | `MIT` |

Current classification: `DOCUMENTED_PACKAGE_METADATA`.

This records package metadata, not a conclusion that every related browser binary or generated artifact is redistributed under those package licenses. If Playwright-managed browser binaries or package bytes are ever distributed, their actual distribution/notice requirements require separate review.

Do not inventory `node_modules/` merely because the Drive mirror contains it. Dependency provenance should derive from committed dependency definitions/locks and actual build inclusion.

## 4. Official-site captures, snapshots, and fixture data

Relevant tracked classes include official-source and clone material such as:

- `data/official_clone_fixtures/`
- official snapshot fixtures used by the Buk-gu deterministic demo
- capture/region/route manifests and provenance metadata
- screenshots/crops used to validate or render the Buk-gu clone

Current classification: `REVIEW_REQUIRED`.

All technical exactness/provenance decisions continue to follow `docs/product/exact-official-site-clone-invariant.md`.

Technical provenance — source URL, capture time, hash, route/page identity — is **not the same thing as copyright/reuse permission**.

For each published fixture/capture class, the final provenance manifest should record:

- exact path or path pattern;
- source institution/site and canonical URL where known;
- capture/acquisition date;
- raw capture vs structured extraction vs screenshot/crop/transformation/reconstruction;
- transformation details and intended use;
- applicable public-data/copyright/license notice, if verified;
- redistribution status: `APPROVED`, `RESTRICTED`, `REVIEW_REQUIRED`, or `INTERNAL_ONLY`;
- reviewer/evidence reference for any `APPROVED` decision.

Do not mark material `APPROVED` solely because it came from a government website.

## 5. Buk-gu visual assets

Tracked image classes exist under `src/web/static/images/`, including:

- `bukgu_home.png`
- `bukgu_menu.png`
- `bukgu_intake.png`
- `bukgu-crops/`
- `bukgu-current/`

The `bukgu-current/` group contains additional official-site-derived home/mayor/quick-menu/lower-section imagery.

Current classification: `REVIEW_REQUIRED`.

These assets must not automatically inherit an eventual source-code license. Logo/brand marks, photographs/portraits, official graphics, UI screenshots, and project-created graphics can have different rights and provenance.

Before public-release approval, the asset-level manifest should distinguish at least:

- official screenshot/crop;
- official logo/brand mark;
- official photograph/portrait;
- project-created reconstruction;
- project-created icon/graphic;
- third-party stock/icon/font asset;
- generated asset, if any.

## 6. Fonts and icons

Current classification: `REVIEW_REQUIRED`.

A dedicated scan is still needed for:

- locally bundled font files;
- `@font-face` declarations;
- icon fonts;
- SVG/icon packs;
- copied vendor CSS/assets;
- remote font/icon dependencies referenced from HTML/CSS.

The final report must distinguish a runtime remote reference from a redistributed local copy.

## 7. Presentation and documentation media

Repository areas such as `presentation/`, `proposal/`, documentation screenshots, and comparison evidence may contain material whose redistribution terms differ from source code.

Current classification: `REVIEW_REQUIRED`.

Rules:

- do not assume a presentation screenshot is covered by the source-code license;
- do not place institution/customer-confidential media in the public repository;
- record source and permission for externally sourced images;
- prefer project-generated diagrams or independently licensed assets where provenance is unclear.

## 8. Google Drive / local-only material

The Drive mirror includes Git-tracked content plus additional working-state material such as dependency caches, virtual environments, generated output, AI-tool directories, logs, helper scripts, and other local-only files.

This inventory does not classify those paths as disposable and does not authorize their deletion.

Apply `docs/GOOGLE_DRIVE_MIRROR_SAFETY.md`:

- GitHub absence is not deletion evidence;
- unknown ownership/purpose means `HOLD`;
- no wildcard/prefix/GitHub-difference cleanup.

If a local-only artifact is later proposed for public inclusion, it must enter this provenance process before being committed.

## 9. Machine-readable provenance manifest

The repository now defines a data-only provenance contract:

- `configs/provenance-manifest.schema.json`
- `configs/provenance-manifest.json`

The initial manifest is intentionally narrow. It seeds only the two Page Agent vendored artifacts whose upstream revision, MIT terms, integrity identity, and notice path are already verified:

- `src/web/examples/page-agent/vendor/LICENSE`
- `src/web/examples/page-agent/vendor/page-agent.iife.js`

The schema keeps provenance state and redistribution state explicit and supports fail-closed values including `OWNER_DECISION_REQUIRED`, `REVIEW_REQUIRED`, `RESTRICTED`, and `INTERNAL_ONLY`.

Do not add an official-site capture, image, logo, photograph, font, icon, presentation asset, or project-owned code record as approved unless its evidence supports that state. Unknown license identifiers remain null/review-required rather than guessed.

The manifest is data-only: no runtime loader, renderer behavior, or release promotion is implied by the file's existence.

## 10. Release gate

Before treating the public repository as license-complete:

- [ ] repository owner explicitly approves the outbound license for project-owned code;
- [ ] root `LICENSE` is added only after that approval;
- [ ] `NOTICE`/attribution requirements are decided for all redistributed third-party material;
- [x] Page Agent vendored license is synchronized to the pinned upstream revision and its manifest identity is refreshed;
- [x] Page Agent vendored license is preserved in the controlled Pages output;
- [x] basic Node dependency license report is generated from the committed lockfile;
- [x] machine-readable provenance schema/manifest exists for currently verified vendored records;
- [ ] official capture/fixture classes have reviewed redistribution statuses;
- [ ] Buk-gu images/logos/photos/screenshots have asset-level provenance;
- [ ] bundled fonts/icons/third-party design assets have license evidence;
- [ ] presentation/document media is classified;
- [ ] public repo contains no customer/institution-confidential asset;
- [x] existing PR template requires provenance information for new fixture/asset changes.

Until those gates are satisfied, repository visibility must not be described as granting a project-wide open-source license.
