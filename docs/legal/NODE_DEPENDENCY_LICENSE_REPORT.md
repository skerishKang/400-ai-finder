# Node dependency license report

- Status: `repository-derived inventory / not legal approval`
- Related issue: #1234
- Baseline: `package.json` + `package-lock.json` at main `663bcfeddde03ce8b2ff75114e419386cd1d2e81`
- Method: committed lockfile metadata only; `node_modules/` is not used as an inventory source

## Purpose

This report records the resolved Node dependency set represented by the committed root lockfile. It is a provenance and review aid, not a conclusion that every package, browser binary, generated artifact, or public build output is covered by the same license.

## Resolved dependency inventory

| Package | Resolved version | Relationship | Lockfile license | Registry source | Current review classification |
|---|---:|---|---|---|---|
| `playwright` | `1.61.1` | direct root dependency | `Apache-2.0` | npm registry tarball recorded in lockfile | `DOCUMENTED_PACKAGE_METADATA` |
| `playwright-core` | `1.61.1` | transitive dependency of `playwright` | `Apache-2.0` | npm registry tarball recorded in lockfile | `DOCUMENTED_PACKAGE_METADATA` |
| `fsevents` | `2.3.2` | optional transitive dependency, Darwin only | `MIT` | npm registry tarball recorded in lockfile | `DOCUMENTED_PACKAGE_METADATA` |

The lockfile also records integrity digests for each resolved tarball. Those integrity values remain the package-resolution evidence; this report does not replace them.

## Build and distribution boundary

The current repository uses Node tooling and Playwright for browser/contract validation. The committed Cloudflare Pages build is produced by `scripts/build_cloudflare_pages.py`, which assembles repository-controlled web sources and generated static/live artifacts.

This report does **not** infer from that fact alone that no Node package bytes can ever enter a release. If a future bundler, copy step, browser binary, trace artifact, or vendor step adds third-party bytes to public output, that output must be inventoried separately.

In particular:

- `node_modules/` in the Google Drive/local mirror is not a redistribution manifest;
- package metadata in `package-lock.json` is not a substitute for checking license text/notice obligations when package code is redistributed;
- Playwright-managed browser binaries are outside this lockfile package inventory and require separate review if they are ever redistributed;
- test-only use and public redistribution are different legal/provenance states.

## Reproducibility boundary

CI currently installs Node dependencies with:

```text
npm ci --ignore-scripts
```

That command consumes the committed lockfile and is preferable to inventorying an arbitrary synchronized `node_modules/` directory.

For #1231, dependency reproducibility should continue to use the committed lockfile and should fail when required lock state is missing or unexpectedly changed.

## Notice follow-up

Before declaring Node dependency provenance complete:

- [ ] verify upstream/package license text for any package whose bytes are redistributed;
- [ ] determine whether any NOTICE/attribution text is required in release artifacts;
- [ ] inventory browser binaries separately if distribution is introduced;
- [ ] keep package/version/license extraction reproducible from committed dependency definitions;
- [ ] keep dependency audit separate from license identification;
- [ ] do not infer project-wide source-code licensing from dependency licenses.

## Current conclusion

The committed Node lockfile is small and currently resolves three package entries beyond the root package. Their lockfile-declared licenses are documented above. This closes the basic lockfile inventory gap, but it does not by itself satisfy #1234's broader requirements for project-owned code licensing, official-site captures, images, fonts/icons, browser binaries, or other third-party assets.
