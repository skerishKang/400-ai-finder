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

### Alias-resolution observability (#1225-B.1)

The plain `resolve()` / `resolve_site_id()` contract is unchanged and remains
fully backward-compatible: `resolve("bukgu")["site_id"] == "bukgu_gwangju"`.
`SiteSpecResolver.resolve_with_metadata(identifier)` and the one-shot
`resolve_site_id_with_metadata(...)` are **additive** — they return the same
fail-closed resolution plus alias metadata, and no existing caller is wrapped
or changed.

Return contract:

| Field | Meaning |
|---|---|
| `requested_id` | normalized identifier actually used for lookup (`.strip()` applied, matching `resolve()`) |
| `canonical_site_id` | canonical SiteSpec `site_id` the request projected to |
| `resolution_kind` | closed vocabulary: `canonical` \| `legacy_alias` |
| `spec` | defensive deep copy of the canonical SiteSpec |

Examples (Buk-gu):

```python
resolver.resolve_with_metadata("bukgu_gwangju")
# {"requested_id": "bukgu_gwangju", "canonical_site_id": "bukgu_gwangju",
#  "resolution_kind": "canonical", "spec": {...}}

resolver.resolve_with_metadata("bukgu")
# {"requested_id": "bukgu", "canonical_site_id": "bukgu_gwangju",
#  "resolution_kind": "legacy_alias", "spec": {...}}
```

`bukgu` is observable as `legacy_alias`; display labels (`북구청`,
`Gwangju Buk-gu`) and jurisdiction historical aliases (`광주광역시 북구`) are
not resolution kinds and keep failing closed. The metadata `spec` is a
defensive copy — mutating it never mutates resolver state. B.1 introduces
**no telemetry/log persistence**; runtime migration of legacy callers is
deferred to #1225-D.

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
- **Public domain parity (exact allowlist)** — the SiteSpec `domains.public`
  set and the Python profile `allowed_domains` set must be **exactly equal**
  after host normalization (scheme/path/port ignored, host identity
  preserved). Membership-only checks would let an unexpected domain sneak into
  either allowlist undetected, so set equality is the parity mechanism. The
  profile `base_url` host must be a member of the canonical SiteSpec
  public-domain set. The frozen product fact that `bukgu.gwangju.kr` is the
  current canonical public domain is asserted separately and is not the
  parity mechanism.
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
mismatch, domain set mismatch (extra SiteSpec public domain, extra Python
allowed domain, missing canonical domain, mismatched Python allowed domain),
`base_url` host outside the canonical domain set, golden mismatch. Display
labels (`북구청`, `Gwangju Buk-gu`) and jurisdiction historical aliases
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
python -m pytest -q \
  tests/test_sitespec_projection_parity.py \
  tests/test_sitespec_resolver.py \
  tests/test_canonical_sitespec_contract.py \
  tests/test_site_compatibility_registry.py
python -m json.tool configs/sitespec.schema.json > /dev/null
python -m json.tool configs/sites/bukgu_gwangju.sitespec.json > /dev/null
git diff --check
```

## Python SiteProfile identifier dual-read (#1225-D1)

The Python profile loader now resolves identifiers through the canonical
SiteSpec, while keeping unmigrated YAML-only profiles fully functional.

`src/site_profiles/site_profile.py` `SiteProfileLoader.load_by_id()` /
`load_profile()` resolve:

```text
requested identifier
→ SiteSpec resolver (src/site_profiles/sitespec.py)
→ canonical SiteSpec
→ runtime.python_profile
→ corresponding YAML profile
```

| Call | Result |
|---|---|
| `load_by_id("bukgu_gwangju")` | `bukgu_gwangju.yml` via canonical SiteSpec |
| `load_by_id("bukgu")` | same `bukgu_gwangju.yml` via legacy alias projection |
| `load_profile("bukgu_gwangju")` / `load_profile("bukgu")` | same canonical profile |
| `load_by_id("seogu_gwangju")` | exact YAML fallback (no SiteSpec yet) |
| `load_by_id("북구청")` / `"Gwangju Buk-gu"` / `"광주광역시 북구"` | `FileNotFoundError` (fail-closed) |
| `load_file("/tmp/example.yml")` | explicit file-path semantics, unchanged |

Contract rules:

1. **SiteSpec is the single source of truth.** No separate alias table is
   introduced; canonical/legacy mapping comes only from the resolver.
2. **`runtime.python_profile` is the actual projection.** The YAML filename
   is `<python_profile>.yml`, never `<canonical_site_id>.yml`. The generic
   fixture (`sample_city` / legacy `sample` → `sample_runtime.yml`) proves
   this by making the canonical ID differ from the profile filename.
3. **Unmigrated exact-YAML profiles keep loading.** An identifier with no
   SiteSpec falls back to the historical `<identifier>.yml` lookup
   (transitional; e.g. `seogu_gwangju`). A SiteSpec lookup miss never
   rejects existing YAML profiles.
4. **No fallback after SiteSpec resolution.** Once an identifier resolves to
   a SiteSpec, a missing/malformed `runtime.python_profile` is a
   configuration error (`ValueError`) and never falls back to the
   requested-ID YAML.
5. **Identifier fail-closed.** Display labels and jurisdiction historical
   aliases are not runtime identities; unknown identifiers keep the
   existing `FileNotFoundError` public behavior.
6. **Constructor compatibility.** `SiteProfileLoader()` and
   `SiteProfileLoader(temp_dir)` keep working with YAML-only directories:
   the SiteSpec resolver is constructed lazily on first identifier lookup,
   or injected via `sitespec_resolver` — never eagerly in the constructor.
7. **List APIs expose canonical profiles only.** `list_ids()` /
   `list_profiles()` do not surface legacy aliases (`bukgu` is absent), and
   unmigrated exact-YAML profiles remain listed.

Expected changed files for the D1 slice:

* `src/site_profiles/site_profile.py`
* `tests/test_site_profile_dual_read.py`
* `docs/operations/CANONICAL_SITESPEC_CONTRACT.md`

Protected files (`configs/site-registry.json`,
`configs/sites/bukgu_gwangju.sitespec.json`,
`configs/sites/bukgu_gwangju.yml`, `configs/sitespec.schema.json`,
`functions/api/**`, browser/UI files, prompt files, snapshots, golden
fixtures) are unchanged in D1.
