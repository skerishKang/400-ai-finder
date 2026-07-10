# Execution Gates

These gates apply to every local-agent task in the Buk-gu visual-clone
workstream.

## Mandatory failure-stop rule

Every command explicitly required by the owner must exit with code `0` before
the agent may commit or push.

At the first non-zero exit code, missing expected output, unexpected changed
file, hash mismatch, or failed integrity check, the agent must:

1. stop immediately;
2. make no further edits;
3. make no commit;
4. make no push;
5. not retry with an improvised workaround;
6. report raw facts and wait for owner instruction.

A local agent must never decide that a required failure is harmless, expected,
pre-existing, acceptable, or outside scope.

## Forbidden completion language after a required failure

Until the owner explicitly resolves the failure, the agent must not state or
imply any of the following:

- passed;
- complete;
- mechanically complete;
- safe to commit;
- safe to push;
- expected failure;
- harmless failure;
- pre-existing failure;
- visual fidelity approved;
- CI passed;
- merge ready.

## Raw failure handoff

A failure report must contain all of the following:

```text
Task:
Mode:
Failed command:
Exit code:
Raw output:
Files changed so far:
git diff --check:
git status --porcelain=v1 --untracked-files=all:
Commit status:
Push status:
```

`Raw output` must preserve the relevant command output or traceback without
summarizing it into a success claim.

## Re-entry conditions

The agent may resume only after the owner gives an explicit correction or
narrowed instruction. Before resuming, the agent must re-check:

1. current branch;
2. local and remote branch head equality;
3. allowed changed-file scope;
4. clean tracked working tree;
5. the corrected required command list.

## Model escalation matrix

| Task type or event                                                                              | Allowed executor                                             |
| ----------------------------------------------------------------------------------------------- | ------------------------------------------------------------ |
| checksum, byte-for-byte binary copy, deterministic script, or narrow one-file test task         | Gemma may execute                                            |
| exact one-file contract correction with no design decision                                      | Gemma may execute once under explicit owner patch            |
| diagnosis, traceback interpretation, multi-file edit, visual implementation, or scope ambiguity | higher-capability executor required                          |
| first failure of a required command                                                             | stop; owner decides correction and executor                  |
| second failure to honor stop, commit, push, or raw-report rules                                 | higher-capability executor required for later code-edit work |
| asset import and checksum-only task                                                             | Gemma remains eligible                                       |

The execution agent never self-approves an escalation, a retry, a commit, a
push, a visual gate, CI, release, or merge.