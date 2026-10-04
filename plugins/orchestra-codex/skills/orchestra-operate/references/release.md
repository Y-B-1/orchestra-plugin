Source: derived from obra/superpowers@8ca22dba9a94 skills/finishing-a-development-branch/SKILL.md (MIT); mattpocock/skills@d81f3a183412 skills/engineering/wizard/SKILL.md (MIT); ideas: mattpocock/skills pr (idea level); see THIRD-PARTY-NOTICES.
Sentinel: orchestra-operate/references/release.md

# Operator: release mode

Release is off by default. You act only under an explicit release assignment that names the remote, the target and every command to run. The coordinator or the user has already chosen merge, PR or keep. You execute that choice and nothing wider.

## Before any command

All of these must hold for this exact artifact. If one fails, stop with `STATUS: BLOCKED` and name it.

- The project policy has `release.enabled` true, with the remote, target and argv you were assigned.
- An independent final review of this commit is CLEAN. Review approval does not add external permission.
- The accepted requirements and every required gate are current for this commit: the full sha in each record equals `git rev-parse HEAD`, and the tree is clean.
- Credentials, trust and the target's identity are present and checked. A missing one stops release.
- The base branch is named in the brief. If it is not, ask the coordinator; do not guess.

## Run

- Use the guarded path only. The coordinator issues `orchestra.py permit <remote> <target>`; you run `orchestra.py release <remote> <target>` when the brief supplies the lease and the permit. Without them, stop.
- Merge, then verify the merged result with the scoped checks. A green branch does not prove a green merge. A failing merged result stops everything: leave the branch and worktree in place.
- Name the remote on every push. Preserve history and unrelated bytes. No history rewrite. A rejected push means the remote moved: report it.
- Never force push. Discard a branch or its work only after the user types a confirmation naming it. Only the coordinator can relay that typed confirmation, in the user's own words.
- Never invent database writes, deployment recipes, rollback or pipeline steps. Run only what the brief names.
- A timeout (exit code 124) means the remote state is unknown. Inspect it before any retry.

## When a human must act

A step only a person can take (credentials, a dashboard, a one-off cutover) becomes a bash wizard script: it states each action, waits for confirmation, checks the result and stops on the first failure. Write it to a scratch path and do not commit it. Open each URL before asking for its value, read secrets with hidden input, never echo or log them, and confirm before every irreversible action. Do not paste numbered steps into the report. If the brief assigns a PR, write its body as follows. The pull request body has a summary, before and after evidence, and a merge danger section: one-way or two-way door, and the blast radius.

## Report

Report merge, remote push, pipeline and deployment status separately, each with direct evidence: argv, exit code, log path, the release receipt, and the artifact before and after. Then check the running system through the actual user path and report what you observed. When a result surprises you, confirm it with a second method. An artifact check cannot prove live behavior. Return the exact results and the human actions still needed to the coordinator. You never accept cards or start an autonomous loop.
