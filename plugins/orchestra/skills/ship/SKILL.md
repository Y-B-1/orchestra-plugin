---
name: ship
description: "Load when opening, updating or fixing a pull request: red CI, review comments, merge conflicts, or a PR that must be easy to review. Also load when the owner asks to set up pre-commit hooks or git guardrails. Not for the final message of a run with no PR."
---
# Ship a pull request

Merging into the default branch is the owner step. Never merge a PR yourself.
Use `gh` for all PR state. Read `references/pr-body.md` before you write or rewrite a PR body.

## Make it easy to review
- One concern per commit, in dependency order: schema or types, core logic, wiring, surface, tests. Mechanical changes (renames, generated files, formatting) get their own commits.
- Check the diff before you open: no unrelated edits, no debug leftovers, tests for each behavior change.
- If the diff cannot be read in one sitting, say so and propose a split. Do not polish around it.
- Rewrite history only on a branch nobody else pulled, and only when the owner asked or the PR is yours and unpushed. After a rewrite, `git rev-parse HEAD^{tree}` must equal the tree before it. If it differs, stop.
- Never hide a behavior change in a cleanup commit. Never use `--no-verify`.

## Review comments
1. `gh pr view <n> --comments` and `gh api repos/{owner}/{repo}/pulls/<n>/comments` for inline ones.
2. List each comment as an ask in the ledger: fix, reply, or decline with a reason.
3. A comment with one mechanical answer: make the edit, name the comment in the commit message. A judgement call or an unclear ask: reply with what you would do and leave it to the owner.
4. Re-run the checks that cover each change, push, then say which comments are done.

## Red CI
1. `gh pr checks <n>`; for each failed run, `gh run view <id> --log-failed`. For an external check, open its link from `gh pr checks --json name,link`.
2. Take the first real error, not the last line. Reproduce it locally with the same command before you edit.
3. Fix the cause with the smallest change. Never edit an assertion to pass unless the behavior truly changed. Never weaken, skip or disable a check.
4. Run the failing command and the project's checks locally, commit, push. One failure at a time.
5. After three fix rounds that are still red, stop and report the failing check and what you tried.

## Merge conflicts
1. Update the base: `git fetch origin`, then merge or rebase as the project does. List conflicts with `git diff --name-only --diff-filter=U`.
2. For each file, read both sides and `git log` for each side's intent. Keep both when both are needed; otherwise keep what matches the intended behavior of the newer change. Never take "ours" or "theirs" wholesale without that read.
3. Regenerate lockfiles and generated files with the tool, never by hand.
4. A grep for `<<<<<<<` and `>>>>>>>` must find nothing. Re-run the checks the PR was green on. Say which choices you made and why.

## Watch a PR until green
Only when the owner asks. Do one bounded check, not a loop: `timeout 600 gh pr checks <n> --watch` as a background command. When it exits, handle red CI or new comments as above. No sleep or polling loops in the main session. Report ready only when checks are green, all comments are answered and the branch merges cleanly.

## Pre-commit hooks
Only when the owner asks. Read `references/pre-commit.md`.

## Git guardrails
When the owner asks for git guardrails, read `references/guardrails.md`.

Sources: mattpocock/skills@59db609 engineering/pr, misc/setup-pre-commit; pstack@47c6f80 make-pr-easy-to-review, get-pr-comments, fix-ci, fix-merge-conflicts, babysit; Orchestra 2.15.3 finishing.
