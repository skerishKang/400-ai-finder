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
- `legacy_ids` holds compatibility aliases: `bukgu`. The array may be empty
  for new sites with no historical alias; values must be unique and must never
  collide with the canonical `site_id` (contract-tested).
- The canonical ID must never appear inside `legacy_ids` (contract-tested).
- `configs/site-registry.json` remains the compatibility registry and is not
  redefined or modified by this phase. PR-scope registry non-change is verified
  out-of-band via `git diff origin/main..HEAD -- configs/site-registry.json`
  (no fake in-CI scope guard).

## Jurisdiction effective-date contract

The canonical jurisdiction identity is time-bound. `effective_from` is the
date the canonical name became effective; `historical_aliases` carry prior
legal identities with their `effective_until` date. Dates are `YYYY-MM-DD`
and schema/contract-validated.

Buk-gu instance:

| Field | Value |
|---|---|
| `canonical_name` | `전남광주통합특별시 북구` |
| `short_name` | `북구` |
| `effective_from` | `2026-07-01` |
| historical alias | `광주광역시 북구` → `effective_until: 2026-06-30` |

Display/institution labels (`북구청`, `Gwangju Buk-gu`) are **not**
jurisdiction legal identity aliases. They live under `display`
(`default_label`, `locale_labels`) and must not appear inside
`jurisdiction.historical_aliases` (contract-tested).

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

## Clone governance

The Buk-gu golden surface remains governed by the canonical clone invariant:

[docs/product/exact-official-site-clone-invariant.md](../product/exact-official-site-clone-invariant.md)

This SiteSpec is an identity data contract only. It does not relax, weaken, or
restate that invariant, and it does not change the exact-clone obligations of
the left civic-site surface.

## Dual-read resolver (#1225-B)

`src/site_profiles/sitespec.py` resolves both canonical and legacy site IDs
to the same canonical SiteSpec, reading only `configs/sites/*.sitespec.json`
(sorted, deterministic enumeration). `configs/site-registry.json` remains the
frozen compatibility registry and is **not** a resolver source.

| Identifier | Result |
|---|---|
| `bukgu_gwangju` | Buk-gu canonical SiteSpec (direct) |
| `bukgu` | same Buk-gu canonical SiteSpec (legacy dual-read) |
| `북구청` / `Gwangju Buk-gu` / `광주광역시 북구` | fail-closed (`SiteSpecNotFoundError`) |
| `""`, whitespace, unknown IDs | fail-closed (`SiteSpecNotFoundError`) |

Collision policy: duplicate canonical IDs, a legacy alias claimed by two
SiteSpecs, or a canonical ID colliding with another SiteSpec's legacy alias
raise `SiteSpecLoadError` at load time — first-match-wins is prohibited.
Empty `legacy_ids` is valid (new sites with no historical alias). The resolver
is additive foundation only; no runtime is migrated to it in this phase.

## Projection parity (#1225-C)

The canonical SiteSpec instance and the existing system projections must
intentionally agree (or intentionally disagree only as declared legacy
projections). `tests/test_sitespec_projection_parity.py` is a drift-detection
contract layer: it verifies parity between the SiteSpec and the frozen
compatibility registry, the Python site profile, and the dual-read resolver —
without any runtime migration.

Canonical vs compatibility projection (Buk-gu):

| Concept | Canonical projection | Compatibility (legacy) projection |
|---|---|---|
| site ID | `bukgu_gwangju` | `bukgu` (registry adapter / `default_site_id`) |
| Python profile | `runtime.python_profile` = `bukgu_gwangju` | — |
| Cloudflare adapter | — | `runtime.cloudflare_adapter` = `bukgu` |
| public domain | `domains.public` = `bukgu.gwangju.kr` | profile `base_url` / `allowed_domains` |
| golden commit | `clone.golden_commit` | registry adapter `golden_commit` |

Parity contracts enforced:

- **Python profile identity** — SiteSpec `runtime.python_profile` equals the
  Python profile identifier, and the profile `site_id` equals the canonical
  SiteSpec `site_id` (`bukgu_gwangju`).
- **Public domain parity** — `bukgu.gwangju.kr` exists in
  `domains.public` and matches the profile `base_url` host and
  `allowed_domains` (URL scheme/path normalized, host identity preserved).
- **Compatibility registry projection** — `runtime.cloudflare_adapter` equals
  the frozen registry adapter `site_id`, and that adapter ID is a declared
  `legacy_ids` alias (not the canonical ID).
- **Default compatibility ID** — registry `default_site_id` is one of the
  SiteSpec's declared legacy aliases.
- **Golden parity** — SiteSpec `clone.golden_commit` equals the registry
  adapter `golden_commit` (`7217c0f738a6aa4468bdde3119d8c2d1ec9dd610`).
- **Resolver parity** — the #1225-B resolver maps both `bukgu_gwangju` and
  `bukgu` to the same canonical `site_id == bukgu_gwangju`.

Drift regressions are tested on deep-copied configs only (product files are
never mutated): python_profile mismatch, profile `site_id` mismatch,
undeclared registry adapter, undeclared `default_site_id`, Cloudflare adapter
mismatch, domain mismatch, golden mismatch. Display labels
(`북구청`, `Gwangju Buk-gu`) and jurisdiction historical aliases
(`광주광역시 북구`) are **not** site identifiers and never satisfy parity.

Phase C is projection parity / drift detection only — **no runtime wiring**:
no Python request-path migration, no Cloudflare request-path migration, no
registry lookup migration, no UI metadata migration. `configs/site-registry.json`
remains untouched.

## Non-goals (this phase)

- No `configs/site-registry.json` migration.
- No Python site profile / Cloudflare adapter / `ask.js` / evidence-policy change.
- No shared runtime vocabulary (#1228), no UI label replacement, no docs
  global search/replace, no historical fixture ID rewrite.
- No live provider / Firecrawl / official-site network access.

## Verification

```bash
python -m pytest -q tests/test_sitespec_resolver.py tests/test_canonical_sitespec_contract.py tests/test_site_compatibility_registry.py
python -m json.tool configs/sitespec.schema.json > /dev/null
python -m json.tool configs/sites/bukgu_gwangju.sitespec.json > /dev/null
git diff --check
```
