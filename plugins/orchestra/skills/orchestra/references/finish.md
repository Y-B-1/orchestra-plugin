# Finishing

Load before you write the final message, open a PR, or clean up.

## Own every result
Read each unit's diff yourself before you count it as done; a builder's "done" is a claim, not evidence. Write the final message from the code and the check output, never by forwarding a worker's text. A claim with "should", "probably" or "seems" needs its check run.

## Units that fail
A unit that dies or hits its cap gets one retry with a smaller scope and the original brief plus what is already done. A second failure becomes an open item in the final message, never a pass. When scope changes mid-run, start a fresh unit with the whole new scope; do not chain a correction onto a redirected worker. Before you redispatch a unit, stop its old worker and confirm it stopped (live process, `git status`).

## Evidence
- Checks bind to the final tree: any edit after a green run makes it stale. Run the project's checks once on the final tree and report each command with its exit code.
- A probe that a new build must pass keys on behavior only the new build produces, never on a version field. Name the record each fact came from. A red run proves the check only when its failure text is the mismatch you predicted.
- A blocked check (missing tool, credentials) is reported as blocked, not passed and not failed.
- After a change to a core module many things import, run the full test suite, not just the nearby tests.

## Worktrees and branches
Before you remove a worktree, look inside it: `git -C <path> status --porcelain`. Uncommitted or untracked work is committed to a named branch first, never left on a detached HEAD, never stashed. Then remove the worktrees and branches this run created.

## PR body
To open or update a PR, fix red CI, answer review comments, resolve merge conflicts or make a PR easy to review, load the `ship` skill; it holds the body template.

What changed per ask, the decisions you made, the check results, and a short "merge risk" line: reversible or not, what it touches (data, auth, public API), and files a human should read.

## Steps only a person can take
Credentials, dashboards, one-off migrations in production: write a small bash script that runs the steps in order, confirms each and stops on the first failure. Never a list of steps in chat. Scope the stages from `.env.example` and the `secrets.*`/`vars.*` refs in CI, and mark unknown UI steps as unknown. Read secrets with hidden input (`read -s`), upsert `.env` idempotently, check with `bash -n`, and confirm statically that every secret name matches a CI ref; do not run it yourself.

## Make the next run easier
If this run hit a mistake that a check could catch (a lint rule, a test helper, a type), add the check when it is small, or list it as a follow-up. Prefer a check over another line of instructions. Code in the touched area that breaks the project's own conventions is fixed in its own small commit before new work builds on it.

## Retro on request
Read the session, then list candidates by severity under: navigation pointers, missing or unwired checks (a repo with no hook or CI running its checks is a finding), standards (mechanical goes to a check, judgement to the standards file), steering-file bloat and no-ops, tool economy, and information access.
