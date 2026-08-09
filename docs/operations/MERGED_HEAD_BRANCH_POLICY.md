# Merged head branch policy

- Status: `canonical`
- Effective date: 2026-08-10
- Related issue: #1233

## Decision

For ordinary short-lived pull-request branches, the repository policy is to **delete the head branch after the pull request is merged**.

The preferred repository setting is GitHub's **Automatically delete head branches** option. Until that setting is verified as enabled, the same policy is applied manually through evidence-based cleanup.

This is a policy decision, not a statement that the repository setting is already enabled.

## Why

Merged feature/docs/test branches should not remain indefinitely because stale heads make active work harder to identify, increase branch-inventory cost, and can mislead automated workers about the current development baseline.

Deletion of a merged PR head does not delete the merged commit from `main`; the PR, merge commit, and Git history remain the normal evidence trail.

## Default deletion rule

A branch is eligible for routine post-merge deletion when all of the following are true:

1. it is not the default branch;
2. it is not protected;
3. its pull request is merged;
4. it is not an explicitly retained golden, release, rollback, recovery, or long-lived integration branch;
5. no open PR uses the branch;
6. no current worktree/active task depends on the branch name;
7. the merged content is reachable from the intended target branch;
8. no separate preservation requirement is recorded.

Ordinary `feat/`, `fix/`, `docs/`, `test/`, `chore/`, `refactor/`, and similar short-lived PR heads should normally be removed after these checks.

## Exceptions

Do not auto-delete or manually delete a branch merely because its PR is merged when the branch is explicitly classified as one of the following:

- `KEEP_CORE`
- `KEEP_REQUIRED`
- golden/reference branch
- release branch
- rollback/recovery artifact branch
- active multi-PR integration branch
- evidence-preservation branch
- branch with unresolved ownership or operational dependency

If a branch must survive a merge, that retention requirement should be documented before merge and, where appropriate, enforced through branch protection or an explicit repository record.

## Unknown or unmerged branches

An unmerged branch without sufficient evidence is `HOLD_NEEDS_MORE_EVIDENCE`, not an automatic deletion candidate.

Do not infer deletion safety from:

- branch-name prefixes;
- age alone;
- absence from current GitHub files;
- apparent duplication;
- local/Drive differences;
- lack of an open PR alone.

The Google Drive/local mirror remains governed by `docs/GOOGLE_DRIVE_MIRROR_SAFETY.md`; remote branch cleanup never authorizes deletion of local/Drive-only content.

## Current reconciliation baseline

At the latest 2026-08-10 reconciliation under #1233, a fresh remote listing showed **24 heads** composed consistently as:

- 14 historical `KEEP` refs;
- 5 historical `HOLD_NEEDS_MORE_EVIDENCE` refs;
- active `feat/1227-runtime-control-foundation`;
- active `docs/1233-merged-head-policy` for PR #1241;
- active `legal/1234-machine-provenance-manifest` for PR #1242;
- merged PR #1239 head `docs/1234-provenance-inventory`, a routine merged-head cleanup candidate;
- merged PR #1240 head `legal/1234-page-agent-license-sync`, a routine merged-head cleanup candidate.

The previously merged #1238 branch `docs/drive-mirror-deletion-safety` is no longer present.

This baseline is informational and must be refreshed before any future destructive operation.

## Manual fallback procedure

If automatic merged-head deletion is not enabled or does not apply:

1. refresh `main`, open PRs, and remote branch inventory;
2. identify the exact merged PR and exact head SHA;
3. confirm the intended merged content is reachable from the target branch;
4. confirm the branch is not protected/retained/active;
5. preserve any separately required archival evidence;
6. delete only the exact branch ref;
7. refresh the inventory after deletion.

No wildcard, prefix, substring, or GitHub-difference deletion is permitted.

## Relationship to release and documentation governance

This policy complements `docs/operations/REPOSITORY_GOVERNANCE.md` and `docs/CURRENT_STATUS.md`, which define:

- release tag, changelog, deployment SHA, and rollback records;
- canonical/active-plan/golden/operator/historical/planning-only/superseded document status;
- exact-head pre-merge verification;
- issue closeout evidence.

## Completion rule for #1233

The branch-governance portion of #1233 is considered policy-complete when:

- remote heads have an evidence-based classification;
- unsafe/unknown refs remain held rather than guessed away;
- proven deletion candidates are processed or explicitly recorded as routine cleanup debt;
- merged-head auto-deletion is the documented default policy;
- release/document governance remains canonical and linked.

Repository setting activation, when tooling permits, is an operational application of this policy rather than a reason to weaken or bypass the evidence rules above.
