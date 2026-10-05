Source: derived from obra/superpowers@8ca22dba9a94 skills/verification-before-completion/SKILL.md (MIT); garrytan/gstack@4015c2870b06 health/SKILL.md (MIT); see THIRD-PARTY-NOTICES.
Sentinel: orchestra-operate/references/gate.md

# Operator: gate mode

Run the project's required checks against the assigned repository and artifact, and report each result as observed. You wrap the project's own tools. You do not add checks, score the code or fix anything.

## Procedure

1. Read the brief's list of checks: each name, its exact argv and its scope. Run nothing else.
2. Confirm the artifact: run `python3 <plugin>/scripts/orchestra.py artifact` and match its head, tree and fingerprint to the brief. A mismatch is `STATUS: BLOCKED`.
3. Check each tool is present, using the project's configured command and local install. A missing required tool blocks. A missing optional tool is `unavailable`.
4. Run the checks one at a time, each in its own invocation. One failed check does not stop the next. Send stdout and stderr to the log path and record the exit code before reading the log, for example:

   ```
   <argv> >"$LOG" 2>&1; echo "exit=$?"
   ```

   Show the last lines of the log in the report and keep the whole log.
5. Keep every failing test name, with the line where it appears.
6. Re-read the artifact. If it differs from step 2, the results are void: report the change and rerun on the new artifact.

## What counts

| Claim | Needs | Does not count |
| --- | --- | --- |
| Tests pass | Full test command, zero failures | An earlier run, one file |
| Build passes | Build command, exit 0 | Lint passing |
| Lint or scan clean | The tool's own exit code 0 | A different tool's pass |
| Bug fixed | The reproducing test passes | Code changed |
| Regression test works | Fails with the fix removed, passes with it | One green run |
| Sibling or tool succeeded | Your own diff and logs | Its success message |

## Scope

- Per work unit: the scoped checks named in the brief.
- Before a merge: the derived impact set the brief names, from the changed surface plus the smoke core.
- Full suite: without the owner's trigger in the brief, report it as not run.
- Visual or live acceptance: walk the actual user path and take the screenshots the brief lists. A built artifact is not a deployed observation.
- Engine gates: the coordinator records gates with `orchestra.py gate <name> -- <argv>`, which checks artifact binding itself. Run that line only when the brief gives it with its lease. Your own run is evidence for the report, not a stamped pass.
- Gate once per artifact: a passed gate with the same name and argv on the current artifact is not rerun, and the engine refuses it without `--again`. Cite the existing receipt. A failed gate always reruns; a later change to the tree makes receipts stale, so gate again then. A wave-boundary gate runs after the wave's builders report and before its review, so the reviewer cites its receipt.

## Report

One row per check: name, argv, working directory, exit code, log path, sha256, artifact before and after, status. Then list: blocked environment items, `unavailable` tools, checks not run and why, and anything that went red. Say "all required checks pass" only when every row shows exit code 0 on one unchanged artifact.
