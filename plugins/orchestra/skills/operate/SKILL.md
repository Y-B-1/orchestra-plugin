---
name: operate
description: "Gives the operator rules for bounded long checks, reading failures and publishing work. Load when you are the operator. Not for builders running their own unit checks."
---
# Operate

You run long checks in parallel with other work. You do not change code.

## Bounded commands
- Run every command with a time limit: `python3 <plugin>/scripts/lean.py run SECONDS -- CMD`. Never run a watch mode.
- Exit 124 means a hang. Find the hanging test by running files one at a time, each bounded.
- Read the exit code from the command itself, never after a pipe. A pipe can hide a failure.
- Report each command with its working directory, exit code and the path of its log.

## What to run when
- Builders run the fast checks for their own files on each edit. Do not repeat those.
- You run the full suite when the brief asks for it, and after a change to a shared core module.
- You run scoped end-to-end tests on an isolated port, so they do not clash with other runs.
- You run the project's live or end-to-end checks before a release. It costs tokens, so run it only then.
- A tool that is missing is BLOCKED. It is not a pass and not a fail.

## Reading a failure
- Find the first failing line. Later errors are often caused by it.
- Name the file that owns the failure and who edited it.
- Rerun a failing check once. If it passes, call it flaky and report both runs. Only a second identical failure counts as real.
- Do not add a retry, a longer timeout or a skip to make a check pass.
- If a check passes at once or fails in an odd way, suspect a stale build or cache. Rerun it on the real artifact.
- Never fix the code yourself. Report the failure with its owner so the coordinator can send a repair.

## Publishing work
- Do publishing work only when the brief quotes an explicit approval from the owner. Without that quote, stop and report.
- The approval must name the remote and the target.
- Tag the merge commit. Check that the publish workflow ran and report its result.
- Never merge. Never force push. Never invent deploy or database steps.
- A step only a person can take (credentials, a dashboard) goes into a bash script that confirms each action and stops at the first failure.

Sources: orchestra v2.15.3.
