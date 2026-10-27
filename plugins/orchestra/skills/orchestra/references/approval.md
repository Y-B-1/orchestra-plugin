Sentinel: orchestra/references/approval.md

# Approval and guard modes

## Modes

`guard_mode` in `policy.json` is `minimal` (default), `normal` or `protect`; the hook reads it on every call, and no mode ever asks. Minimal leaves generic commands to Claude Code's permission mode and keeps Orchestra's own checks (locks, state, worker limits, the merge guard after `approved`). Normal warns or allows routine git work: stash, wholesale add, `commit -a`, amend, multi-ref and refspec pushes, and release actions without a question. A softened push that deletes a tag, the default or a protected branch stays denied. Protect keeps every strict verdict and, while a run is active, denies a release without a current permit. An unreadable policy or an unknown value counts as protect. An autonomous run, active or stopped with its report kept, is always strict. `classify` prints the protect verdict whatever the mode. `release_workflows` (globs, default `release*`, `publish*`, `deploy*`) names the workflows `gh workflow run` treats as releases; a workflow not found locally counts as one.

## What the run may do

Branch from the default branch (`arm` refuses on it), push its own branches, open, comment on, review and approve pull requests, and delete what it created: its run branches and worktrees, and files inside a linked worktree. `orchestra.py base TASK` prints the branch a card's pull request targets: the default branch, or the head of its one open parent pull request. Two open parents defer the card (exit 2): wait for them to merge. Open the pull request in the turn that finishes the last card and record it with `orchestra.py pr URL --task ID` while autonomy is active: only a pull request recorded then counts as the run's. GitHub does not let an account approve its own pull request, so the run's approval is an Orchestra review record, not a GitHub approval.

Denied during the run: `gh pr merge` (the merge guard below is the only way through), a `gh api` write outside pull request creation, comments and reviews, `gh workflow run`, `gh pr edit --base`, an unknown `gh` command, edits of `.claude/settings.json` and `settings.local.json`, and the scheduler tools. A push never lands on the default branch, a protected branch or a tag.

## The unattended lock

When the run stops and keeps its report, the owner has not yet approved it: releases, merges, `autonomy disarm`, `start --new-run`, scheduler tools and settings edits stay denied from tool calls, and `effective = protect` applies to everything else. Softened pushes stay denied. `start --new-run` is also refused by the engine until the owner approves or disarms. The lock clears when a receipt for the run is recorded, or when `autonomy disarm` is run again on the stopped run (the first call on an active run only stops it). The owner types `approved`, or runs `orchestra.py autonomy disarm` in a terminal. Re-arming moves an old receipt aside.

## Approval

The owner types the word `approved`, alone, in their own session. The UserPromptSubmit hook records a receipt only when all hold: the prompt is exactly that word; a run exists and its autonomy is stopped (a stale loop is stopped first, and a stop made by the bound session in the same call records nothing); the run stopped and kept its report. It makes one `gh pr list` call and stores the PRs that are open at their recorded head with a clean review, in merge order, plus the excluded ones with a reason. The receipt keeps a prompt hash, never the text. The reply prints one command per PR:

`gh pr merge N -R OWNER/REPO --merge --delete-branch --match-head-commit SHA`

If a later pull request still shows a run branch as its base after its parent merged, run `gh pr edit N --base DEFAULT` first, then the printed command. After a head moves, record the PR again with `pr URL` and type `approved` again.

## The merge guard

Once a run recorded a pull request, `gh pr merge` must name the number with `-R` and the recorded repository, or the recorded pull request URL (no other repository, env prefix, branch or `gh api`), so the checkout's remotes cannot pick another repository. A PR whose base is a run branch merges while its parent is open; once the parent has merged, retarget it first. A PR whose base is the default branch merges only when autonomy is off, the receipt names this run and the PR, the live head equals the receipt, the command pins that head, every lower-order PR is merged, and it carries no flag besides `-R`, `--merge`, `--delete-branch` and the pin. A PR the run did not open that targets the default branch is the owner's to merge in a terminal. The guard writes no state; its answer is final in every mode.

## Not contained

The prompt hook cannot prove a human typed the word: the payload marks no scheduled, subagent or other-session prompt. Contained: no receipt while the loop is active; the whole prompt must be the word; a scheduler or `SendMessage` call whose text is only that word is denied in every mode; scheduler tools are denied during the run. Not contained: a prompt scheduled before the stop that fires after it, another owner session, shell schedulers (`crontab`, `at`, `claude -p`) and a hostile agent.

Known gap: a command run from a directory outside the repository and its worktrees finds no run and gets neither the allowances nor the lock. The only backstop that does not depend on the agent is a server-side ruleset: protect the default branch and tags on the host, require a pull request and block deletion and force pushes.
