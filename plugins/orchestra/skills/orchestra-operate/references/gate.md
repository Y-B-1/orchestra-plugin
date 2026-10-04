Source: derived from obra/superpowers@8ca22dba9a94 skills/verification-before-completion/SKILL.md (MIT); garrytan/gstack@4015c2870b06 health/SKILL.md (MIT); see THIRD-PARTY-NOTICES.
Sentinel: orchestra-operate/references/gate.md

# Operator: gate mode

Run the project's required checks against the assigned repository and artifact, and report each result as observed. You wrap the project's own tools. You do not add checks, score the code or fix anything.

## Procedure

1. Read the brief's list of checks: each name, its exact argv and its scope. Run nothing else.
2. Confirm the artifact: `git rev-parse HEAD` and `git status --porcelain | shasum`. Match them to the brief. A mismatch is `STATUS: BLOCKED`.
3. Check each tool is present, using the project's configured command and local install. A missing required tool blocks. A missing optional tool is `unavailable`.
4. Run the checks one at a time, each in its own invocation. One failed check does not stop the next. Send stdout and stderr to the log path and record the exit code before reading the log, for example:

   ```
   <argv> >"$LOG" 2>&1; echo "exit=$?"
   ```

   Never pipe the checker into `tee`, `grep` or `tail` in the same command. Show the last lines of the log in the report and keep the whole log.
5. Count failures from the full log. Keep every failing test name, with the line where it appears.
6. Re-read the artifact. If it differs from step 2, the results are void: report the change and rerun on the new artifact.

## What counts

| Claim | Needs | Does not count |
| --- | --- | --- |
| Tests pass | this run's command, exit code 0, 0 failures in the log | an earlier run, "ran clean before" |
| Lint or scan clean | the tool's own exit code 0 | a different tool's pass |
| Build succeeds | the build command, exit code 0 | a passing linter or tests |
| Regression test works | the same test seen red, then green | green once |
| Requirement met | a check per line of the requirement | tests green |

A check with no known red case needs a failure direction. Run it on the known-bad input named in the brief, or report `failure direction unproven`.

## Scope

- Per work unit: the scoped checks named in the brief.
- Before a merge: the derived impact set the brief names, from the changed surface plus the smoke core.
- Full suite: only when the brief carries the owner's trigger. Otherwise report it as not run.
- Visual or live acceptance: walk the actual user path and take the screenshots the brief lists. A built artifact is not a deployed observation.
- Engine gates: the coordinator records gates with `orchestra.py gate <name> -- <argv>`, which checks artifact binding itself. Run that line only when the brief gives it with its lease. Your own run is evidence for the report, not a stamped pass.

## Report

One row per check: name, argv, working directory, exit code, log path, sha256, artifact before and after, status. Then list: blocked environment items, `unavailable` tools, checks not run and why, and anything that went red. Say "all required checks pass" only when every row shows exit code 0 on one unchanged artifact.
