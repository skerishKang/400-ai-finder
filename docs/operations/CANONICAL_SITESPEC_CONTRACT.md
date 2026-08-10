# Canonical SiteSpec Contract

Additive foundation for Issue #1225 (phase A).

## Purpose

The repository carries site identity in several shapes:

| Concept | Current value | Where it lives |
|---|---|---|
| Python profile | `bukgu_gwangju` | `configs/sites/bukgu_gwangju.yml` |
| Compatibility registry id | `bukgu` | `configs/site-registry.json` |
| UI/docs labels | `북구`, `북구청`, `Gwangju Buk-gu` | product code, docs |
| Public domain | `bukgu.gwangju.kr` | profile, captures |

This phase adds a **canonical SiteSpec schema + Buk-gu canonical instance +
offline contract test**. It does not migrate or rewire any existing runtime.

## Files

- `configs/sitespec.schema.json` — fail-closed canonical SiteSpec schema
- `configs/sites/bukgu_gwangju.sitespec.json` — Buk-gu canonical instance
- `tests/test_canonical_sitespec_contract.py` — offline contract test (stdlib + pytest only)

## Canonical / legacy ID contract

- `site_id` is the canonical immutable ID: `bukgu_gwangju`.
- `legacy_ids` holds compatibility aliases: `bukgu`.
- The canonical ID must never appear inside `legacy_ids` (contract-tested).
- `configs/site-registry.json` remains the compatibility registry and is not
  redefined or modified by this phase (scope-tested).

## Naming evidence (repository-sourced, no invention)

- Korean official name `전남광주통합특별시 북구`:
  `configs/sites/bukgu_gwangju.yml` (`name`),
  `data/official_captures/bukgu_gwangju/home/capture-metadata.json` (`site_name`),
  official homepage `<meta name="title">`.
- `북구청`: product code/docs (`functions/api/mvp/ask.js`, official snapshots).
- `Gwangju Buk-gu`: `configs/site-registry.json` (`display_name`), docs, tests.
- Public domain `bukgu.gwangju.kr`: `configs/sites/bukgu_gwangju.yml`
  (`base_url`, `allowed_domains`), captures.
- Golden commit `7217c0f738a6aa4468bdde3119d8c2d1ec9dd610`:
  `configs/site-registry.json`, `docs/bukgu-golden-compatibility-manifest.md`,
  `docs/architecture/clone-first-platform-adr.md` (frozen baseline).

## Non-goals (this phase)

- No `configs/site-registry.json` migration.
- No Python site profile / Cloudflare adapter / `ask.js` / evidence-policy change.
- No shared runtime vocabulary (#1228), no UI label replacement, no docs
  global search/replace, no historical fixture ID rewrite.
- No live provider / Firecrawl / official-site network access.

## Verification

```bash
python -m pytest -q tests/test_canonical_sitespec_contract.py
python -m json.tool configs/sitespec.schema.json > /dev/null
python -m json.tool configs/sites/bukgu_gwangju.sitespec.json > /dev/null
git diff --check
```
