# Asset, license, and provenance inventory

Status: **initial repository inventory / owner decision pending**

Related issue: #1234

## Purpose

This document inventories the current repository's major copyright, license, and provenance classes before any project-wide license is selected.

It is intentionally conservative:

- it does **not** select a license for 400 AI Finder code;
- it does **not** assume that public-government website content, screenshots, photographs, logos, icons, or visual design are freely redistributable;
- it does **not** treat a URL, public availability, or government authorship as sufficient reuse permission;
- unknown or incomplete provenance is `REVIEW_REQUIRED`, not implicitly approved.

This inventory covers Git-tracked/public-repository material. The Google Drive/local mirror may contain additional ignored, generated, cached, tool-owned, or local-only files; those files are governed separately by `docs/GOOGLE_DRIVE_MIRROR_SAFETY.md` and must not be deleted merely because they are absent from GitHub.

## Repository-level license status

| Class | Current status | Decision |
|---|---|---|
| 400 AI Finder original source code | No root `LICENSE` found at this inventory baseline | `OWNER_DECISION_REQUIRED` |
| Project documentation | No repository-wide explicit outbound license identified | `OWNER_DECISION_REQUIRED` |
| Official-site captures / fixtures / screenshots | Source/provenance exists in parts of the project, but redistribution terms are not established by this inventory | `REVIEW_REQUIRED` |
| Third-party vendored Page Agent runtime | Upstream/version/commit/license manifest and vendored license are present | `DOCUMENTED_THIRD_PARTY` |
| npm dependency set | Direct dependency currently includes Playwright; dependency-specific notices still require automated/manual verification | `REVIEW_REQUIRED` |
| Images / logos / official visual assets | Multiple Buk-gu-derived PNG assets are present; asset-by-asset permission status is not established here | `REVIEW_REQUIRED` |
| Fonts/icons or other third-party design assets | No repository-wide manifest yet proves full coverage | `REVIEW_REQUIRED` |

A missing root license means no new project license should be inferred from package metadata, third-party files, README language, or repository visibility.

## 1. Original project code

### Observed code areas

The repository contains substantial first-party implementation in areas including:

- `src/`
- `functions/`
- `scripts/`
- `tests/`
- `configs/`
- project-owned documentation and build tooling

### Current classification

`OWNER_DECISION_REQUIRED`

Before adding a root `LICENSE`, the repository owner must explicitly decide:

1. who is authorized to license the project-owned code;
2. whether all contributors' contributions can be distributed under that license;
3. whether code and non-code assets should use the same or different terms;
4. whether any customer/institution-confidential material must be excluded before licensing.

No AI worker may choose MIT, Apache-2.0, GPL, proprietary, or another project-wide license on the owner's behalf.

## 2. Vendored Page Agent runtime

### Tracked provenance already present

Source tree:

- `src/web/examples/page-agent/source-manifest.json`
- `src/web/examples/page-agent/vendor-manifest.json`
- `src/web/examples/page-agent/vendor/page-agent.iife.js`
- `src/web/examples/page-agent/vendor/LICENSE`

The existing manifests identify:

- source package: `@alicloud/page-agent`
- upstream repository: `alibaba/page-agent`
- version: `1.12.1`
- pinned upstream commit: `fa4664dfa5379e6e91deaf85bc1db2ae14d8e1d7`
- upstream license: MIT
- vendored runtime kind: custom non-demo IIFE built locally from the pinned upstream source
- vendored bundle size: 208,138 bytes
- vendored license size: 1,070 bytes
- bundle SHA-256: `ADE2BD44C77C2555143BD3D008FE9C3527D161C2C922A579471CE8A6C6FA3C74`
- license SHA-256: `062A52901BED47A901076645239CE20B74EF9EDC8239149A7842CE153B959F9D`

The source manifest also records that demo auto-init/testing endpoints/CDN behavior were excluded from the controlled local build and that the local experiment is intended to run without non-local runtime requests.

### Current classification

`DOCUMENTED_THIRD_PARTY`

### Remaining work

- verify that the vendored `LICENSE` text exactly matches the upstream license at the pinned revision;
- determine whether a root/project `NOTICE` should reproduce attribution for this vendored component;
- keep the manifest/version/commit/hash check as a provenance gate when the vendored file changes;
- do not replace or remove the vendored license during bundling.

## 3. npm / browser-test dependencies

Current root `package.json` directly declares:

- `playwright: ^1.61.1`

The lockfile should remain the resolution source for CI, but a lockfile is not a license inventory.

### Current classification

`REVIEW_REQUIRED`

### Required follow-up

Generate a reproducible dependency report from the committed lockfile containing, at minimum:

- package name;
- resolved version;
- source/package registry identity;
- declared license;
- notice/attribution requirement if any;
- whether the package is development/test-only or shipped into public build output.

Do not copy `node_modules/` into a provenance manifest merely because the Drive mirror contains it. Inventory should be derived from committed dependency definitions/lockfiles and actual build inclusion.

## 4. Official-site captures, snapshots, and fixture data

Relevant tracked classes include official-source and clone material under paths such as:

- `data/official_clone_fixtures/`
- official snapshot fixtures used by the Buk-gu deterministic demo
- capture/region/route manifests and provenance metadata
- screenshots/crops used to validate or render the Buk-gu clone

### Current classification

`REVIEW_REQUIRED`

Technical provenance (source URL, capture time, hash, route/page identity) is **not the same thing as copyright/reuse permission**.

For each published fixture/capture class, the final provenance manifest should record:

- exact path or path pattern;
- source institution/site;
- canonical source URL where known;
- capture/acquisition date;
- whether the stored material is raw capture, structured extraction, screenshot, crop, transformation, or hand-authored reconstruction;
- transformation details;
- intended project use (testing, fidelity comparison, demo rendering, documentation, etc.);
- applicable public-data/copyright/license notice, if verified;
- redistribution status: `APPROVED`, `RESTRICTED`, `REVIEW_REQUIRED`, or `INTERNAL_ONLY`;
- reviewer/evidence reference for any `APPROVED` decision.

Do not mark material `APPROVED` solely because it came from a government website.

## 5. Buk-gu visual assets

The synchronized source tree confirms tracked image classes under `src/web/static/images/`, including examples such as:

- `bukgu_home.png`
- `bukgu_menu.png`
- `bukgu_intake.png`
- `bukgu-crops/`
- `bukgu-current/`

The `bukgu-current/` group contains additional official-site-derived visual material such as current home/mayor/quick-menu/lower-section imagery.

### Current classification

`REVIEW_REQUIRED`

These assets must not be automatically assigned the eventual source-code license. Logo/brand, photograph, portrait, official graphic, UI screenshot, and hand-created project graphic can have different rights/provenance.

Before public-release approval, produce an asset-level manifest that distinguishes at least:

- official screenshot/crop;
- official logo/brand mark;
- official photograph/portrait;
- project-created reconstruction;
- project-created icon/graphic;
- third-party stock/icon/font asset;
- generated asset, if any.

## 6. Fonts and icons

### Current classification

`REVIEW_REQUIRED`

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

### Current classification

`REVIEW_REQUIRED`

Rules:

- do not assume a presentation screenshot is covered by the source-code license;
- do not place institution/customer-confidential media in the public repository;
- record source and permission for externally sourced images;
- prefer project-generated diagrams or independently licensed assets where provenance is unclear.

## 8. Google Drive / local-only material

The Drive mirror includes Git-tracked content plus additional working-state material such as `.git/`, dependency caches, virtual environments, generated output, AI-tool directories, logs, helper scripts, and other local-only files.

This license inventory does not classify those paths as disposable and does not authorize their deletion.

Apply `docs/GOOGLE_DRIVE_MIRROR_SAFETY.md`:

- GitHub absence is not deletion evidence;
- unknown ownership/purpose means `HOLD`;
- no wildcard/prefix/GitHub-difference cleanup.

If a local-only artifact is later proposed for public inclusion, it must enter this provenance process before being committed.

## 9. Required machine-readable manifest

A follow-up PR should introduce a machine-readable provenance manifest only after the categories/fields are stable. Suggested record shape:

```json
{
  "path": "src/web/static/images/example.png",
  "class": "official_screenshot",
  "source": {
    "url": "...",
    "captured_at": "..."
  },
  "license_or_terms": {
    "status": "REVIEW_REQUIRED",
    "identifier": null,
    "notice": null,
    "evidence": null
  },
  "redistribution": "REVIEW_REQUIRED"
}
```

Do not fill unknown license identifiers with guesses.

## 10. Release gate

Before treating the public repository as license-complete:

- [ ] repository owner explicitly approves the outbound license for project-owned code;
- [ ] root `LICENSE` is added only after that approval;
- [ ] `NOTICE`/attribution requirements are decided and implemented;
- [ ] Page Agent vendored license/provenance is re-verified;
- [ ] dependency license report is generated from committed locks;
- [ ] official capture/fixture classes have reviewed redistribution statuses;
- [ ] Buk-gu images/logos/photos/screenshots have asset-level provenance;
- [ ] bundled fonts/icons/third-party design assets have license evidence;
- [ ] presentation/document media is classified;
- [ ] public repo contains no customer/institution-confidential asset;
- [ ] new asset PR template/checklist requires provenance fields.

Until those gates are satisfied, repository visibility must not be described as granting a project-wide open-source license.