# Home Asset Identity Audit (#1172)

## 1. Source Inventory Identity

- **Input Path**: `data/official_captures/bukgu_gwangju/home/asset-inventory.json`
- **Route**: `home`
- **Source Final URL**: `https://bukgu.gwangju.kr/`
- **Total Assets**: 174
- **Partial Hash Limit**: 65,536 bytes

## 2. Scan Scope

- **Method**: Repository tracked files only (`git ls-files -z`)
- **Eligible Tracked Files**: 622
- **Excluded Paths**:
  - Audit report output (`data/official_clone_asset_audits/bukgu_gwangju/home-repository-match-audit.json`)
  - This document (`docs/artifacts/1172-home-asset-identity-audit.md`)
  - Audit scripts/tests
- **LFS Pointers**: 0 (Ignored if any)

## 3. Evidence Classification Rules

Captured assets are classified into one of the following based on provided evidence:
- `full_body_equivalent_hash`: The hash covers the full file (`hashed_byte_count == size_bytes` and size > 0).
- `partial_prefix_hash`: The hash only covers a prefix of the file (`hashed_byte_count < size_bytes`).
- `unhashed`: The hash is missing or null.
- `invalid_capture_evidence`: The hash is malformed or the size values are invalid (fail-closed).

## 4. Exact Match Rule

Exact repository matching is performed **only** for `full_body_equivalent_hash` assets.
A match requires both:
- `size_bytes` exactly equal to the repository file byte size.
- `sha256` exactly equal to the repository full-file SHA-256.

*No match is claimed based solely on filename equality, same extension, or identical partial hash prefixes.*

## 5. Summary Counts

- **Total Assets**: 174
- **Full Body Equivalent Hash**: 35
- **Partial Prefix Hash**: 5
- **Unhashed**: 134
- **Invalid Evidence**: 0

**By Match Status**:
- **One Exact Match Candidate**: 0
- **Multiple Exact Match Candidates**: 0
- **No Exact Match**: 35

## 6. Exact Candidate Results

### One-Match Assets
- None (0)

### Multiple-Match Assets
- None (0)

### No-Match Assets
- 35 full-body-equivalent items were evaluated for exact offline matching against tracked repository files, but zero candidates were found.

### Partial/Unhashed Assets
- 139 assets (5 partial prefix, 134 unhashed) were safely isolated into `non_authoritative_candidates` or `no_repo_exact_match` without any exact match claim, preserving the strict byte-identity rule.

## 7. Next Steps & Future Approved Asset Capture Priorities

- **Status Check**: This was a **repository identity audit only**. No asset has been promoted to the repository and the canonical fixture remains unchanged.
- **Readiness**: The `home` region remains `capture_required`. Exact visual parity is not claimed.
- **Future Priorities**:
  1. Complete a secure download mechanism to fetch `unhashed` or `partial_prefix_hash` assets safely.
  2. Maintain strict integrity checks during download and promote assets only when the hash matches.
  3. Wire the downloaded local assets into the official clone fixtures incrementally, replacing absolute URLs.

