Source: derived from obra/superpowers@8ca22dba9a94 skills/finishing-a-development-branch/SKILL.md (MIT); mattpocock/skills@d81f3a183412 skills/engineering/wizard/SKILL.md (MIT); ideas: mattpocock/skills pr (idea level); see THIRD-PARTY-NOTICES.
Sentinel: orchestra/references/finishing.md

# Finishing a branch

Finish after final review is clean and the named project checks are green on the frozen candidate. A later edit voids both.

## Steps

1. Detect the environment: current branch, linked worktree or not, remote, the base branch. Confirm the base with the user's configuration, not a guess.
2. Choose the outcome: merge, pull request or keep the branch. You or the user chooses; a worker never does. A release is an operator card with an explicit assignment. A run without release pre-authorization, armed or unarmed, adds no release card and ends with "ready to release" under Needs you in the run brief; the user then assigns the release. An explicit release assignment from the user, before or after the brief, counts as that assignment, and "ready to release" applies only when there is none. Armed without pre-authorization the permit stays refused, so that card runs after the run stops. With the ledger's Release line, add the terminal release card after the closing confirmations; `complete` waits for its acceptance.
3. Merge, then verify the merged result with the scoped checks. A green branch does not prove a green merge.
4. Run only the commands that project configuration authorizes, under the permit, then check the live path the change affects.
5. Never force push. Discard a branch or its work only after the user types a confirmation naming it.

## Pull request body

The pull request body has a summary, before and after evidence, and a merge danger section: one-way or two-way door, and the blast radius.

Add a "Held / next phase" section from `orchestra.py brief`: its Still failing, Held log, Final rounds, Notes and Needs you sections, unedited.

## Human-only steps

A step only a person can take (credentials, a dashboard, a one-off cutover) becomes a bash wizard script: it states each action, waits for confirmation, checks the result and stops on the first failure. Hand the user the script, not a numbered list in chat.
