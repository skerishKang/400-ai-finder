# #872 Execution Gates

A listed check must succeed before commit or push.

When a listed check does not succeed:

- stop the task;
- do not change more files;
- do not commit or push;
- record command, exit code, output, changed files, diff check, and status;
- wait for a new instruction.

Only the owner decides whether a check or contract changes.

Gemma use: checksums, binary copy, deterministic scripts, and a narrow one-file test task. Use a higher-capability executor for diagnosis, multi-file edits, or visual implementation.
