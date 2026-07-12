# #872 Local-Agent Failure-Stop and Escalation Control Matrix

## Purpose

This control matrix governs local execution agents used for the #863 Buk-gu
visual reconstruction workstream. It prevents an agent from converting a
failed required check into an unauthorized commit, push, or completion claim.

## Required outcome matrix

| Situation | Required agent action | Commit/push allowed |
|---|---|---|
| Every required command exits 0 and scope remains clean | report raw results and await owner review | only when owner explicitly authorized commit/push |
| One required command fails | stop immediately and send raw failure handoff | no |
| An unexpected tracked file changes | stop immediately and identify the file | no |
| Source hash or dimensions differ | stop immediately and preserve source bytes | no |
| A screenshot label is unreadable or conflicts with ledger | stop and request owner decision | no |
| Local render attempts an external request | stop and report request URL/method | no |
| Owner supplies a corrected narrow instruction | re-check branch, scope, and command list before resuming | only after all corrected checks pass |

## Failure handoff minimum

A failure handoff is invalid unless it includes:

1. exact failed command;
2. exit code;
3. raw output or traceback;
4. files changed so far;
5. `git diff --check`;
6. `git status --porcelain=v1 --untracked-files=all`;
7. whether commit was attempted;
8. whether push was attempted.

## Completion-language control

After any required failure, the agent may state only factual failure status. It
must not claim pass, completion, expected failure, harmless failure, visual
approval, CI approval, release readiness, or merge readiness.

## Executor escalation

| Work | Executor |
|---|---|
| checksum, source copy, deterministic scripts, narrow one-file tests | Gemma eligible |
| one exact one-file contract correction | Gemma eligible once |
| diagnosis, multi-file edits, visual implementation, ambiguous source interpretation | higher-capability executor |
| second protocol failure involving stop/report/commit/push rules | higher-capability executor required for later code-edit work |

The project owner decides retries, scope changes, executor changes, PR review,
issue closure, and merge.
