# #1177 Freeze home asset audit scan universe

## Problem

`scripts/audit_bukgu_home_asset_identity.py` originally rebuilt its repository
index on every normal run / `--check` via `git ls-files` + working-tree file
hashes. Unrelated feature PRs (for example #1173) then produced:

```text
Check failed: Report drift detected
```

Working-tree hashing was also Windows `core.autocrlf` sensitive, so checkout
line endings could change the scan manifest SHA without any intentional
repository change.

Simply regenerating the report on each branch does **not** fix the design:
the next unrelated file addition would drift again.

## Fix

1. **Frozen scan manifest** (Git blob universe at a fixed commit):

   `data/official_clone_asset_audits/bukgu_gwangju/home-repository-scan-manifest.json`

2. **Normal generation and `--check`** load that manifest only. They never call
   `git ls-files`, never re-hash the current working tree, and never refresh
   the manifest.

3. **Explicit refresh** (operator-only):

   ```bash
   python scripts/audit_bukgu_home_asset_identity.py \
     --refresh-scan-manifest \
     --snapshot-ref 0a86d643b5bc8f4379bafd2aa42704c579de6c9b
   ```

   Uses `git rev-parse`, `git ls-tree -r -z --name-only`, and batched
   `git cat-file` blob bytes. Fail closed if the ref cannot be resolved.

## Snapshot pin

| Field | Value |
|-------|--------|
| Snapshot commit | `0a86d643b5bc8f4379bafd2aa42704c579de6c9b` |
| Enumerated paths | 626 |
| Eligible entries | 622 |
| Excluded | 4 |
| Canonical manifest SHA (Git blobs) | `1997cac4b492034649a0920afa2672fcf93cec287b5b685eb8ff609f1172dd0e` |
| Legacy working-tree SHA (superseded) | `86c372bacd9a867e8407ab854b9c4766c3c0193f4c6e4244a7f613a4767eabda` |

The legacy SHA matched Windows CRLF working-tree bytes, not Git objects. #1177
re-pins on repository blob bytes for cross-platform stability.

## Report identity (unchanged conclusions)

| Metric | Count |
|--------|------:|
| asset_total | 174 |
| full_body_equivalent_hash_count | 35 |
| partial_prefix_hash_count | 5 |
| unhashed_count | 134 |
| invalid_evidence_count | 0 |
| evaluated_full_hash_count | 35 |
| one_exact_candidate_count | 0 |
| multiple_exact_candidates_count | 0 |
| no_exact_match_count | 35 |

Generator `2.0.1`, report `schema_version` `2`.

## Boundaries

- No asset download / promotion
- No canonical clone fixture change
- No source capture/inventory change
- No live network / Firecrawl / 북구청 access
- #1170 renderer not touched
- #1173 worktree not modified
