# Hooks

Orchestra registers three hooks in `plugins/orchestra/hooks/hooks.json`. Each runs `python3 "${CLAUDE_PLUGIN_ROOT}/scripts/lean.py" hook <name>` and reads the hook event as JSON on stdin. No hook ever asks for permission.

| Event | Matcher | Effect |
| --- | --- | --- |
| SessionStart | all | Tells the main session that Orchestra is on, prints the ask ledger path and the `lean.py` path, names the `orchestra` skill for a prompt with more than one ask, and on the default branch says work starts on a new branch. It creates no folder |
| PreToolUse | `Bash`, `PowerShell`, `Agent`, `Task`, `Workflow`, MCP `merge_pull_request` tools | Denies a command or tool call that merges into the default branch, a second Fable critic, and (during a run) a subagent that inherits the main session's model. Allows everything else by printing nothing |
| Stop | all | Under an active goal, blocks stopping until the goal is done, but stays quiet while a worker runs and never repeats a prompt for unchanged work. When no goal was set, reminds once per ledger state about open asks |

## The ledger and goal files

State is per session and lives in the Git common directory of the repository, outside the working tree: `.git/orchestra/sessions/<session id>/asks.md` (the ask ledger) and `goal.json` (the goal) in the same folder. The session id comes from the hook event, and from `CLAUDE_CODE_SESSION_ID` in a Bash command, so another session or worktree of the same repository never sees this session's goal or ledger. Without a session id the folder is `.git/orchestra/`; an active goal there is still enforced, so a Claude Code version that does not set `CLAUDE_CODE_SESSION_ID` falls back to one shared goal rather than none. Outside a Git repository the folder is `.orchestra/` in the current directory. A folder is created when something is written (`goal set`, the reminder, `lean.py ledger`), never by SessionStart. A ledger or goal that a session wrote under `<top level>/.orchestra/` before the folder became a Git repository is still read from there. `lean.py ledger` prints the ledger path.

The ledger may start with a header `base: <ref> (<sha>) | branch: <name>`. A ledger line is `- [mark] ID: text` (a `*` bullet and extra spaces also parse), with any `| files: ... | after: ...` fields after the text. The marks are `[ ]` todo, `[>]` running, `[x]` done and `[~]` dropped with a reason. A line marked `[ ]` or `[>]` is open. The review result is one line, `- [x] review: clean` (or `- [>] review: round N`, which is open).

## The guard (PreToolUse)

The default branch is the target of `refs/remotes/origin/HEAD`. Without it, the guard takes the first local branch of `main`, `master` and `trunk`, else `main`; a repository whose default branch has another name and no `origin/HEAD` is unprotected until `git remote set-head origin -a` runs. One `git for-each-ref` per repository gives the default branch, the current branch and the local branches; a command with no `git` or `gh` word, and any command that is not a push or an API write, starts no git process.

The guard splits the command into simple commands at `&&`, `||`, `;`, `|`, `&`, newlines, subshell and group brackets, `$(` and backticks, outside quotes. It drops backslash-newline pairs and does not read heredoc bodies (a body a shell runs, and the `$( )` spans of an unquoted one, are read). It follows `cd DIR` and `pushd DIR` to the later commands, reads the payload of `sh`, `bash`, `zsh`, `dash` and `ksh` with `-c` (also `-lc`, `-ce`) and of `eval`, and skips shell keywords (`if`, `then`, `do`, `while`, `!`), `VAR=value`, wrappers with their options and values (`sudo -u USER`, `env -u VAR`, `nice -n N`, `timeout N`, `npx`, `xargs`, `time`) and `python3 .../lean.py run SECONDS --`. Git's `-C DIR`, `--git-dir` and `--work-tree` select the repository whose branches are read. A command is checked only when `gh` or `git` is the command itself, so `echo gh pr merge` and `grep "git push origin main"` run. A backtick span inside double quotes is a command substitution that a shell runs, so it is checked; put such text in single quotes or a quoted heredoc. It denies:

- `gh pr merge`, also with an option such as `-R OWNER/REPO` before `pr` or between `pr` and `merge`;
- a `gh api` write (not a GET) to an endpoint that ends in `/merge` or `/merges`, or a GraphQL `query=` field with a `mergePullRequest` or `enablePullRequestAutoMerge` mutation; a path or jq text that only contains `merge` is not read;
- a `gh api` write (any method other than GET, or a call with fields) to `git/refs/heads/main`, a `contents/` write with `branch=main`, a ref create of `refs/heads/main`, or a rename of `main`;
- `git push` with a destination ref that is the default branch, written as `main`, `HEAD:main`, `refs/heads/main`, a wildcard refspec that matches it, or `HEAD` or `@` while on it;
- a force push (`+main`, `-f`) or a delete (`:main`, `--delete main`) of the default branch;
- `git push --mirror`, and `git push --all` or `--branches` while a local default branch exists;
- a bare `git push` (options such as `-o` allowed) while the default branch is checked out.

When the guard cannot read a command that mentions merge or push, it denies it rather than letting it through. A hook that cannot start (no `python3`), crashes or times out lets the command run: `onFailure: "block"` is not set, because it would block every Bash call on a machine without Python. An MCP tool whose name ends in `merge_pull_request` is denied; other MCP write tools, `curl` to the API and scripts are not read.

Everything else runs: pushing other branches and tags, deleting other branches, removing worktrees, `git merge` in the local checkout, `git reset`, opening and reading pull requests. Claude Code's permission mode decides those as usual.

The deny reason tells the agent to push its branch and open a pull request; merging is the owner's step. The guard reads command text. It does not follow aliases, variables or scripts, so it is a safety net for agents, not isolation.

## One Fable critic, and the model matrix

The hook reads `Agent` (and the older `Task`) calls through `subagent_type` and `model`, and `Workflow` calls through `script` or the file at `scriptPath`. It starts no git process unless it needs the session folder, and it prints nothing for input it cannot read.

One Fable critic (no switch):

- An `Agent` call for `orchestra:critic-fable` (or `critic-fable`) is denied while one runs in this session. "Running" is a `critic-fable` subagent transcript (its type is read from the `agent-*.meta.json` beside it) that is mid-turn and written in the last 10 minutes. A call it allows also writes `fable.lock` in the session folder; the lock counts for 30 minutes unless a critic transcript finished after it was written.
- A `Workflow` script that names `critic-fable` twice, or once on a line with or inside `map(`, `forEach(`, `for (`, `while (`, `parallel(`, `pipeline(` or `Array.from`, is denied; so is one that names it while a critic runs. It is a text check: a mention in a comment counts.
- A model override containing `fable` on any other agent type is denied.
- Deny texts: "only one Fable critic may run at a time. ... Wait for the running critic-fable to finish"; "a workflow may name critic-fable once, outside any loop or fan-out"; "the Fable model runs only as orchestra:critic-fable, one at a time".

The model matrix applies during a run, when this session's ledger has an open ask (`[ ]` or `[>]`):

- An `Agent` call with no `subagent_type`, or `general-purpose`, `claude` or `fork`, is denied: "every subagent names an orchestra:* agent type ... inherits the main session's model". Every other type (Explore, Plan, `orchestra:*`, other plugins') runs.
- A `Workflow` script with more `agent(` calls than `agentType` words is denied: "Add agentType to each agent() call".
- Outside a run the matrix never fires. `ORCHESTRA_MATRIX=off` in the environment turns it off.

## The Stop hook and /orchestra:goal

`/orchestra:goal TEXT` runs `lean.py goal set` before the model starts (a command pre-run line), so the goal is set even if the model skips a step; the goal text stays in the prompt and never reaches the shell. `goal set` writes `goal.json` with state `active` for the session. While a goal is active, each stop attempt counts one continuation, and the Stop hook blocks with the reason when any of these holds:

- no ledger exists yet, or it has no ask line the hook can read;
- the ledger has open asks (the reason names them);
- the working tree has uncommitted changes to tracked files;
- HEAD has commits beyond the base (the ledger header's base, else `origin/<default branch>`) and the ledger has no `- [x] review: clean` line;
- HEAD has commits beyond the base, the repository has a remote, and the work is on the default branch or a detached HEAD (the reason says to create a feature branch, push it and open a PR, since pushing the default branch is denied), or `origin/<branch>` does not hold HEAD;
- the same, the remote is on GitHub and no open pull request holds the current head (read with `gh pr view`; when `gh` is missing, not signed in or slow, this check is skipped rather than holding the goal open).

When HEAD has no commits beyond the base (questions, research, a review), the branch, push and review conditions are skipped: the goal is done once every ask is marked.

Two rules keep the hook from looping, both carried over from 2.15:

- **A running worker keeps it quiet.** When an agent transcript (`agent-*.jsonl`) of the session is mid-turn (its last assistant record stopped for a tool call, not `end_turn`) and was written in the last 10 minutes, or a Workflow `journal.jsonl` written in the last hour has an agent with a `started` record and no `result` or `failed` record, the hook lets the turn end without a prompt or a counted continuation. The app wakes the session when the worker finishes. A worker that just finished does not count, since nothing would wake the session.
- **No prompt twice for the same state.** The hook keeps a fingerprint of what is missing, HEAD, the working tree (tracked changes, and the size and time of untracked files) and the ledger. When a stop finds the same fingerprint as the last prompt, it does not block: it shows the owner one line saying nothing changed, then stays quiet until the work changes.

When the last message ends with a question, the prompt adds: do not wait for an answer; decide, log the decision in the ledger and continue.

When none holds, the goal state becomes `done` and the session stops. After the goal's limit of stop attempts (60, or `lean.py goal set --limit N`, or `ORCHESTRA_GOAL_LIMIT` in the environment) the state becomes `capped`, the owner sees a message and the hook stops blocking. `lean.py goal stop REASON` sets the state to `stopped`; with `--session ID` it stops that session's goal, and from a terminal with no session id it stops every active goal of the repository. `lean.py goal status` prints the goal and the open asks.

When no goal file exists, the Stop hook blocks once when this session's ledger has open asks, and stays quiet when the stop is already a continuation (`stop_hook_active`), while a worker runs, or when it already reminded about the same ledger state, so it never loops.

## Bounded commands

`lean.py run SECONDS -- CMD` runs a command in its own process group and stops the group after SECONDS (exit 124), so a hanging test cannot hold a builder. A child that starts its own session or group is not reached. A command killed by signal N exits 128+N. SECONDS must be a positive number. When `lean.py` itself is stopped (SIGTERM, SIGINT or SIGHUP, as a Bash tool timeout does), it stops the command's group too. It is a CLI, not a hook.

## Checks

`tests/test_lean.py` runs the guard, the Stop hook and the CLI against scratch repositories. `scripts/live-check.py` runs all three hooks in real headless sessions ([live check](live-check.md)).
