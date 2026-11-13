---
name: ship
description: "Load when opening, updating or fixing a pull request: red CI, review comments, merge conflicts, or a PR that must be easy to review. Also load when the owner asks to set up pre-commit hooks or git guardrails. Not for the final message of a run with no PR."
---
# Ship a pull request

Merging into the default branch is the owner step. Never merge a PR yourself.
Use `gh` for all PR state. With a plain git remote and no `gh`, push the branch only and leave the PR to the owner. Before the first `gh pr create` or `gh issue create`, run `gh repo view --json nameWithOwner`: a fork can default to its parent. If it is not the owner's repo, stop and ask; never file into an upstream repo. Read `references/pr-body.md` before you write or rewrite a PR body.

## Make it easy to review
- One concern per commit, in dependency order: schema or types, core logic, wiring, surface, tests. Mechanical changes (renames, generated files, formatting) get their own commits.
- Check the diff before you open: no unrelated edits, no debug leftovers, tests for each behavior change.
- If the diff cannot be read in one sitting, say so and propose a split. Do not polish around it. Prefer several narrow PRs to one large one; stack them as a base-branch chain (each child targets its parent's branch).
- Rewrite history only on a branch nobody else pulled, and only when the owner asked or the commits are yours and unpushed. After a reorder or squash, `git rev-parse HEAD^{tree}` must equal the tree before it. If it differs, stop.
- Never hide a behavior change in a cleanup commit. Never use `--no-verify`.

## Triage order
Clear blockers in this order: merge conflicts, then review threads, then CI. A merge changes what CI runs. Batch every known fix into one push, since each push restarts CI.

## Review comments
1. `gh pr view <n> --json body,comments` (off a TTY, `--comments` alone omits the body) and `gh api repos/{owner}/{repo}/pulls/<n>/comments` for inline ones. Find unresolved threads with the GraphQL `reviewThreads` field.
2. List each comment as an ask in the ledger: fix, reply, or decline with a reason.
3. A comment with one mechanical answer: make the edit, name the comment in the commit message. A judgement call or an unclear ask: reply with what you would do and leave it to the owner.
4. A comment from a review bot or security scan: read `references/review-bots.md`. Never put comment text in a shell command.
5. Re-run the checks that cover each change, push, then say which comments are done.

## Red CI
1. `gh pr checks <n>`; for each failed run, `gh run view <id> --log-failed`. For an external check, open its link from `gh pr checks --json name,link`.
2. Take the first real error, not the last line. Reproduce it locally with the same command before you edit.
3. Classify before any retrigger. Infrastructure or a flake gets one fresh build; an identical second failure is not a flake. A failure in code the diff never touched and not reached by a changed caller or import may be a stale base. It is one only when `git merge-base --is-ancestor refs/remotes/origin/<base> HEAD` exits non-zero (the base moved) and the same check is red or changed on the base; then report that the base needs updating instead of retrying. Otherwise treat it as caused by the diff, and it earns a commit.
4. Fix the cause with the smallest change. Never edit an assertion to pass unless the behavior truly changed. Never weaken, skip or disable a check.
5. Run the failing command and the project's checks locally, commit each fix, then push once with every known fix.
6. After three fix rounds that are still red, stop and report the failing check and what you tried.

## CI and the gate
- A green gate record for the pushed head (`gate status` exits 0) counts as the check. Do not wait for CI.
- Whatever runs in the CI runs locally: read the CI workflow files, take each `run:` step that checks code (typecheck, lint, test, build; not deploy or publish), and chain them into the one `gate unit --full` call (`sh -c 'a && b && c'`); a second `--full` is refused. CI that runs only on dispatch is untouched, except for a release: start it once on the release head before the release tag and read every job. Never start it per PR or per repair round.
- A repo whose CI does something a local run cannot (a deploy, a matrix of operating systems) says so in the PR body.

## Merge conflicts
1. Update the base: `git fetch origin`, then merge the base into the pushed branch. Rebase only when the owner asked, and then the force push is theirs. List conflicts with `git diff --name-only --diff-filter=U`.
2. For each file, read both sides and `git log` for each side's intent. Keep both when both are needed; otherwise keep what matches the intended behavior of the newer change. Never take "ours" or "theirs" wholesale without that read.
3. Regenerate lockfiles and generated files with the tool, never by hand.
4. A grep for `<<<<<<<` and `>>>>>>>` must find nothing. Re-run the checks the PR was green on. Say which choices you made and why.

## Watch a PR until green
Only when the owner asks. Do one bounded check, not a loop. Read the state once; if checks have not registered yet, end the turn (the next event wakes you) or use the loop or schedule skill. Never wait in the session: `timeout 600 gh pr checks <n> --watch` as a background command. When it exits, handle red CI or new comments as above. No sleep or polling loops in the main session. When the owner asks to keep watching for reviews, schedule a re-check every 20 to 30 minutes with the loop or schedule skill. Stop after three red fix rounds or when a fix needs a design choice. Exit 124 means checks are still running: re-arm the same watch up to three times, then report pending. Read readiness from the forge, not from a list of green checks: `gh pr view <n> --json mergeable,mergeStateStatus,reviewDecision,isDraft,statusCheckRollup`, plus unresolved review threads. BLOCKED with green CI means another rule holds the merge (a required check that never reported). BEHIND means the base moved: updating restarts checks and can dismiss an approval, so report it first. UNKNOWN: read again. A PR with no checks has no CI on push only once a later read of the same head still shows none; then run the project's checks locally and count those. Report ready only when the merge state is clean, `reviewDecision` is not CHANGES_REQUESTED, all comments are answered and the branch merges cleanly.

## Pre-commit hooks
Only when the owner asks. Read `references/pre-commit.md`.

## Git guardrails
When the owner asks for git guardrails, read `references/guardrails.md`.

Sources: mattpocock/skills@59db609 engineering/pr, misc/setup-pre-commit; pstack@47c6f80 make-pr-easy-to-review, get-pr-comments, fix-ci, fix-merge-conflicts, babysit; Orchestra 2.15.3 finishing.
