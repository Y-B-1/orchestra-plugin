# Finishing

Load before you write the final message, open a PR, or clean up.

## Own every result
Read each unit's diff yourself before you count it as done; a builder's "done" is a claim, not evidence. Write the final message from the code and the check output, never by forwarding a worker's text. A claim with "should", "probably" or "seems" needs its check run. Before the first `gh issue create` or `gh pr create` of a session, do the target-repo check at the top of the `orchestra:ship` skill.

## Units that fail
A unit that dies or hits its cap gets one retry with the original brief plus what is already done. Pick the retry by cause: a smaller scope after a context limit or a cap, the same brief after a dropped connection, a different model after a tool error. A stopped worker that returns late is checked against the tree as it is now; a finding only it has goes to a fresh unit. A second failure becomes an open item in the final message, never a pass. When scope changes mid-run, start a fresh unit with the whole new scope; do not chain a correction onto a redirected worker. Before you redispatch a unit, stop its old worker and confirm it stopped (live process, `git status`).

## Evidence
- Checks bind to the final tree: any edit after a green run makes it stale. Run the test gate once on the final tree (full unit run once per PR, later runs scoped, e2e scoped) and report each command with its exit code; `gate status` exits 0 before the push.
- A probe that a new build must pass keys on behavior only the new build produces, never on a version field. Name the record each fact came from. A red run proves the check only when its failure text is the mismatch you predicted.
- A blocked check (missing tool, credentials) is reported as blocked, not passed and not failed.
- After a change to a core module many things import, widen the scoped run to its importers; the full run stays one per PR.

## Worktrees and branches
Before you remove a worktree, look inside it: `git -C <path> status --porcelain --untracked-files=all --ignored=matching --ignore-submodules=none` (an ignored `.env` may exist nowhere else), and list commits only its HEAD reflog reaches (`git -C <path> reflog`). Uncommitted, untracked or reflog-only work is committed to a named branch first, never left on a detached HEAD, never stashed. A locked worktree is not removed by deleting its folder. Then remove the worktrees and branches this run created, only a branch that is pushed or merged by ancestry: `git rev-list --left-right --count refs/remotes/origin/<branch>...<branch>` must show no commits ahead, and a remote that someone else advanced (behind or diverged) is not removed. Call a branch merged only by ancestry against `refs/remotes/origin/<base>` (the short `origin/<base>` can name a tag or a local branch first). A branch with an open PR is held, even when a newer closed PR is listed first.

## PR body
To open or update a PR, fix red CI, answer review comments, resolve merge conflicts or make a PR easy to review, call the Skill tool with `orchestra:ship`; it holds the body template.

Its sections: Summary, Evidence, Merge danger, Reviewer guide.

## Steps only a person can take
Credentials, dashboards, one-off migrations in production: write a small bash script that runs the steps in order, confirms each and stops on the first failure. Never a list of steps in chat. Put the stages in one function called on the last line, so an edit mid-run cannot corrupt bash's read; single-quote values written to `.env`; offer saved values as defaults, so a re-run resumes; fail at end of input instead of looping; end with a summary of the steps not done. Scope the stages from `.env.example` and the `secrets.*`/`vars.*` refs in CI, and mark unknown UI steps as unknown. Read secrets with hidden input (`read -s`), upsert `.env` idempotently, check with `bash -n`, and confirm statically that every secret name matches a CI ref; do not run it yourself.

## Calls waiting on the owner
Only the owner merges, so every run ends with at least one call. Open the final message with one sentence naming what waits on the owner. List each call: the PR or link, what it changes for users, the evidence, the risk and your pick. Use plain words, no hashes, paths or CI jargon. Never shrink an item to fit a word count. Never mark done what still waits on the owner. Name a screen you did not see; embed a screenshot or say "no screenshot yet".

## Re-pitch on request
When the owner says a message did not land, restate it with the missing context, in short sentences, with the project's glossary terms.

## Make the next run easier
If this run hit a mistake that a check could catch (a lint rule, a test helper, a type), add the check when it is small, or list it as a follow-up. Prefer a check over another line of instructions. End the final message with one line on the environment gap this run hit (a missing check, log or test seam), if any. For recurring upkeep (a ratchet that takes one file off an exception list, a nightly survey), offer a `/schedule` routine; the owner approves it. Code in the touched area that breaks the project's own conventions is fixed in its own small commit before new work builds on it.

## Retro before the push
A fixed step after the review is clean (ledger line `- [ ] retro`). Input is only what the run recorded for this branch: review findings, repair rounds, failed or retried units, gate failures, the owner's corrections. Do not reread the session. Write at most 3 candidates, each with its cheapest home: a check, a path rule, the repo memory, the charter. Run the retro before the final scoped e2e run. A small check lands in the same PR, gets one `orchestra:reviewer-light` re-review on its files like hygiene, and `gate unit --scoped` on them before `gate status`; the rest go in the PR body. With no findings, retries or corrections, write one line and move on. Keep a candidate by the filter in "Retro on request".

## Retro on request
Locate the session transcript with `$CLAUDE_CODE_SESSION_ID` (the folder under `~/.claude/projects/`). Keep a candidate only if it is durable, specific, changes a decision, is not already covered by its target file, and no lint, script or flag could enforce it (that goes to a check instead). Edit no steering file before the owner approves it. Look also for moments the owner handed over context the agent could have fetched itself. Read the session, then list candidates by severity under: navigation pointers, missing or unwired checks (a repo with no hook or CI running its checks is a finding), standards (mechanical goes to a check, judgement to the standards file), steering-file bloat and no-ops, tool economy, and information access.
