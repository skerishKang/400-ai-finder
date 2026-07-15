# Home Asset Identity Audit (#1172)

## 1. Source Inventory Identity

- **Input Path**: `data/official_captures/bukgu_gwangju/home/asset-inventory.json`
- **Route**: `home`
- **Source Final URL**: `https://bukgu.gwangju.kr/`
- **Total Assets**: 174
- **Partial Hash Limit**: 65,536 bytes

## 2. Scan Scope

- **Method**: Repository tracked files only (`git ls-files -z`)
- **Enumerated Tracked Paths**: 626
- **Eligible Tracked Files**: 622
- **Excluded Paths**: 4 (Audit outputs, test and scripts)
- **LFS Pointers**: 0 (Ignored if any)
- **Missing or Unreadable Paths**: 0
- **Manifest SHA**: `86c372bacd9a867e8407ab854b9c4766c3c0193f4c6e4244a7f613a4767eabda`

## 3. Evidence Classification Rules

Captured assets are classified into one of the following based on provided evidence:
- `full_body_equivalent_hash`: The hash covers the full file (`hashed_byte_count == size_bytes` and size > 0).
- `partial_prefix_hash`: The hash only covers a prefix of the file (`hashed_byte_count < size_bytes`).
- `unhashed`: The hash is missing or null.
- `invalid_evidence`: The hash is malformed (violates strict lowercase hexadecimal SHA rule) or the size values are invalid (fail-closed).

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

**By Match Status (Full Hash Evaluated - 35 items)**:
- **One Exact Match Candidate**: 0
- **Multiple Exact Match Candidates**: 0
- **No Exact Match**: 35

**By Not Evaluated Status**:
- **Not Evaluated (Partial Hash)**: 5
- **Not Evaluated (Unhashed)**: 134
- **Not Evaluated (Invalid Evidence)**: 0

## 6. Exact Candidate Results

### One-Match Assets
- None (0)

### Multiple-Match Assets
- None (0)

### No-Match Assets
- 35 full-body-equivalent items were evaluated for exact offline matching against tracked repository files, but zero candidates were found.

### Partial/Unhashed Assets
- Partial/unhashed/invalid evidence was not evaluated for repository exact identity. Only full-body-equivalent hashes received exact-match outcomes.

## 7. Next Steps & Future Approved Asset Capture Priorities

- **Status Check**: This was a **repository identity audit only**. No asset has been promoted to the repository and the canonical fixture remains unchanged.
- **Readiness**: The `home` region remains `capture_required`. Exact visual parity is not claimed.
- **Future Priorities**:
  1. Complete a secure download mechanism to fetch unhashed or partial-prefix assets safely.
  2. Maintain strict integrity checks during download and promote assets only when the hash matches.
  3. Wire the downloaded local assets into the official clone fixtures incrementally, replacing absolute URLs.

No asset download was performed or authorized in this issue.
