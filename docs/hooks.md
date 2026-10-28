# Hooks

Orchestra registers three hooks in `plugins/orchestra/hooks/hooks.json`. Each runs `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/lean.py" hook <name>` and reads the hook event as JSON on stdin. No hook ever asks for permission.

| Event | Matcher | Effect |
| --- | --- | --- |
| SessionStart | all | Tells the main session that Orchestra is on, prints the ask ledger path and the `lean.py` path, and says to load the `orchestra` skill for a prompt with more than one ask |
| PreToolUse | `Bash` | Denies a command that merges into the default branch. Allows everything else by printing nothing |
| Stop | all | Under an active goal, blocks stopping until the goal is done. When no goal was set, reminds once about open asks |

## The ledger and goal files

State lives in the Git common directory of the repository, outside the working tree: `.git/orchestra/asks.md` (the ask ledger) and `.git/orchestra/goal.json` (the goal). All worktrees of one repository share them. Outside a Git repository the folder is `.orchestra-lean/` in the current directory. `lean.py ledger` prints the ledger path.

A ledger line is `- [mark] ID: text`, with any `| files: ... | after: ...` fields after the text. The marks are `[ ]` todo, `[>]` running, `[x]` done and `[~]` dropped with a reason. A line marked `[ ]` or `[>]` is open.

## The guard (PreToolUse)

The default branch is the target of `refs/remotes/origin/HEAD`. Without it, the guard takes the first local branch of `main`, `master` and `trunk`, else `main`.

The guard splits the command at `&&`, `||`, `;`, `|`, newlines, `$(` and backticks, and also reads the payload of `sh -c`, `bash -c` and `zsh -c`. It denies:

- `gh pr merge`, also with an option such as `-R OWNER/REPO` between `pr` and `merge`;
- a `gh api` call to a `/merge` or `/merges` endpoint, or a GraphQL `mergePullRequest` or `enablePullRequestAutoMerge` mutation;
- `git push` with a destination ref that is the default branch, written as `main`, `HEAD:main`, `refs/heads/main` or `HEAD` while on it;
- a force push (`+main`, `-f`) or a delete (`:main`, `--delete main`) of the default branch;
- a bare `git push` while the default branch is checked out.

Everything else runs: pushing other branches and tags, deleting other branches, removing worktrees, `git merge` in the local checkout, `git reset`, opening and reading pull requests. Claude Code's permission mode decides those as usual.

The deny reason tells the agent to push its branch and open a pull request; merging is the owner's step. The guard reads command text. It does not follow aliases, variables or scripts, so it is a safety net for agents, not isolation.

## The Stop hook and /orchestra:goal

`/orchestra:goal TEXT` runs `lean.py goal set TEXT`, which writes `goal.json` with state `active`. While a goal is active, each stop attempt counts one continuation, and the Stop hook blocks with the reason when any of these holds:

- no ledger exists yet;
- the ledger has open asks (the reason names them);
- the working tree has uncommitted changes to tracked files;
- the repository has a remote and the current branch has no upstream, or is ahead of it.

When none holds, the goal state becomes `done` and the session stops. After 60 continuations the state becomes `capped` and the hook stops blocking. `lean.py goal stop REASON` sets the state to `stopped` for a blocker only the owner can clear. `lean.py goal status` prints the goal and the open asks.

When no goal file exists, the Stop hook blocks once when the ledger has open asks, and stays quiet when the stop is already a continuation (`stop_hook_active`), so it never loops.

## Bounded commands

`lean.py run SECONDS -- CMD` runs a command in its own process group and stops the group after SECONDS (exit 124), so a hanging test cannot hold a builder. It is a CLI, not a hook.

## Checks

`tests/test_lean.py` runs the guard, the Stop hook and the CLI against scratch repositories. `scripts/live-check.py` runs all three hooks in real headless sessions ([live check](live-check.md)).
