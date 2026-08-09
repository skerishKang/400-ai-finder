# Google Drive Mirror Safety Policy

## Purpose

This repository is mirrored to Google Drive as a working-folder backup and AI-readable workspace. The Drive mirror may contain files and directories that are intentionally **not tracked by GitHub**.

The purpose of this policy is to prevent accidental deletion of valid local or Drive-only content when comparing the working folder with GitHub.

## Critical rule

> **Absence from GitHub is never, by itself, evidence that a file or directory is safe to delete.**

A GitHub repository represents tracked version-controlled content. The Google Drive mirror represents a broader working-folder state and may legitimately contain untracked, ignored, generated, cached, tool-specific, environment-specific, or local-only content.

Therefore:

- Do not delete a Drive/local path merely because the same path does not exist on GitHub `main`.
- Do not treat `git ls-files`, GitHub tree listings, or repository diffs as a deletion allowlist for the Drive mirror.
- Do not make the Drive tree match GitHub by destructive synchronization.
- When comparing GitHub and Drive, use the comparison primarily to verify that expected tracked files are present in Drive, not to conclude that Drive-only files are disposable.

## Expected Drive-only / local-only content

The mirror may legitimately include categories such as:

- `.git/` metadata, refs, objects, worktrees, logs, and local Git state
- ignored dependencies such as `node_modules/`
- virtual environments such as `.venv/`
- caches such as `.pytest_cache/`, `__pycache__/`, and tool caches
- generated or built output such as `dist/`
- local logs and diagnostics
- local AI/tool configuration such as `.agents/`, `.codex/`, `.claude/`, `.antigravitycli/`, or similar tool directories
- temporary patch, migration, debug, or helper scripts
- local-only configuration or runtime artifacts
- files intentionally excluded by `.gitignore`
- local worktree files that have not been committed yet

The presence of one of these categories does **not** automatically mean it should be retained forever. It means its GitHub absence is not sufficient evidence for deletion.

## Deletion gate

Before deleting, moving, cleaning, pruning, or bulk-reconciling any path from the local/Drive mirror, the operator or AI worker must establish all of the following:

1. **Exact path identity** — identify the exact file or directory. Do not rely on substring, prefix, wildcard, or fuzzy matching for destructive operations.
2. **Classification** — determine whether the path is Git-tracked, ignored, generated, cached, tool-owned, environment-owned, local-only work, or unknown.
3. **Purpose/ownership** — determine why the path exists and whether another tool, worktree, sync process, developer, or AI worker may still rely on it.
4. **Independent deletion reason** — establish a reason to delete that does not depend solely on "it is not on GitHub."
5. **Safety check** — check for active work, uncommitted content, worktree references, sync activity, secrets/configuration, or other dependencies.
6. **Explicit approval where uncertain or destructive** — if purpose or ownership is uncertain, classify the path as `HOLD` and do not delete it until the user explicitly approves deletion.

Unknown means **HOLD**, not delete.

## Prohibited shortcuts

Unless a separately reviewed cleanup task explicitly authorizes them with an exact validated scope, do not use destructive shortcuts against the mirrored working folder, including:

- `git clean` as a general cleanup mechanism
- recursive deletion based on GitHub-vs-Drive difference alone
- wildcard deletion
- prefix/substring-based deletion
- "make Drive identical to GitHub" cleanup
- deleting an entire ignored directory merely because it is ignored
- deleting unknown tool/config folders without establishing ownership and purpose

## GitHub vs. Drive authority boundary

Use each source for the question it can answer safely:

### GitHub is authoritative for

- committed source history
- authoritative `main` HEAD
- branches, pull requests, issues, reviews, and CI status
- what content is version-controlled

### Google Drive / local mirror is authoritative for

- what is physically present in the mirrored working folder
- local-only and ignored working artifacts
- local tool state and generated files visible in that mirror

Neither source alone authorizes deletion from the other.

## Safe comparison rule

A GitHub ↔ Drive comparison may produce these cases:

| Case | Default interpretation | Action |
|---|---|---|
| Tracked on GitHub and present in Drive | expected | no cleanup action |
| Tracked on GitHub but absent in Drive | possible sync/mirror problem | investigate; do not infer deletion elsewhere |
| Absent on GitHub but present in Drive | possibly ignored/generated/local-only | preserve and classify |
| Purpose unknown | insufficient evidence | `HOLD` |

## Synchronization awareness

Google Drive sync activity can create or update temporary and metadata files. During active synchronization:

- do not perform broad local cleanup,
- do not delete synchronization-related temporary files simply because they are untracked,
- do not interpret a partially indexed Drive search result as proof that a file is absent,
- prefer direct folder listing/readback for existence checks when possible.

## AI worker instruction

Any AI model or automation working on `400-ai-finder` must follow this rule:

> **Never delete or recommend deleting a local/Google Drive file solely because it is missing from GitHub. First classify the exact path, establish an independent deletion reason, and obtain explicit user approval when ownership or purpose is uncertain.**

This rule has higher priority than cosmetic repository cleanup, tree parity, disk-space optimization, or convenience.
