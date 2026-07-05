# Execution Gates

For every task, every listed command must succeed before commit or push.

If a listed command does not succeed:

1. stop;
2. do not edit more files;
3. do not commit or push;
4. report the command, exit code, output, changed files, diff check, and status;
5. wait for owner instruction.

The execution agent does not decide that a failed check is harmless or expected.

`mechanically complete` is allowed only when all listed checks succeed. It is not visual approval, CI approval, release approval, or merge approval.

Use Gemma only for checksum, binary copy, deterministic scripts, and a narrow one-file test task. Use a higher-capability executor for diagnosis, multi-file edits, or visual implementation.