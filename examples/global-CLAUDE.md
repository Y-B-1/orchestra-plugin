# Global engineering guidelines

<!-- Example for ~/.claude/CLAUDE.md with the Orchestra plugin installed.
     Copy it, then delete what you do not want. Keep it short: it loads into every session. -->

Three layers: how to think while coding (sections 1 to 4), how to run a session (section 5), and which process to use (section 6, from the `orchestra` plugin).

**Project rules live in the project.** Each repository keeps its charter in `AGENTS.md` at its root. Claude Code loads it when the project has no `CLAUDE.md`. This file is the only `CLAUDE.md`.

## 1. Think before coding

- Plan read-only before you edit.
- State your assumptions. When unsure, ask every question whose prerequisites are settled in one round, each with your recommended answer.
- Never ask what the codebase can answer; read it instead.
- If two readings of the request exist, show both. If a simpler approach exists, say so.

## 2. Simplicity first

Write the minimum code that solves the problem. No unrequested features, configurability or abstractions for single-use code. If 200 lines could be 50, rewrite.

## 3. Surgical changes

Every changed line traces to the request. Match the existing style. Mention unrelated dead code; do not delete it. Remove only the orphans your change made.

## 4. Goal-driven execution

Turn each task into a check that returns yes or no, then loop until it passes:

- "Add validation": write tests for invalid inputs, then make them pass.
- "Fix the bug": write a test that reproduces it, then make it pass.
- "Refactor X": the tests pass before and after.

Completion claims carry evidence: the command, its exit code, or a screenshot.

## 5. Session mechanics

- Load the minimum context that makes the task solvable.
- Keep state on disk (spec, progress file, commits), not in the conversation. A repository with a memory file (`docs/AGENT-MEMORY.md`) updates it in the commit that closes a batch.
- Commit every working iteration. A bad step is a revert, not a debugging session.
- Match check scope to blast radius: fast checks per edit, a scoped end-to-end run per unit, a derived impact set before merge. Run the full suite only when the owner asks. Any commit after a green run voids that run as evidence.
- Subagents that edit files run in separate worktrees when two or more run at once. A worktree lives for one unit of work. Before you remove it, inspect the directory for uncommitted edits, and preserve them on a named branch.
- Never use `git stash` in a repository that uses worktrees: the stash is shared by all of them.
- A rule that binds a subagent goes inline in its brief or into a hook. Parent context does not cross a delegation boundary.
- Before a status claim about background work, check that the process is alive.
- If a rule must always hold, propose a hook or a check instead of another sentence here.

## 6. Process routing (Orchestra)

The top-level session is the coordinator. For any prompt with more than one ask it loads the `orchestra` skill and follows it:

- **Ledger:** one line per ask the user made, in the ask ledger (`.git/orchestra/sessions/<session id>/asks.md`, printed at session start), marked todo, running, done or dropped with a reason.
- **Plan by novelty, not size:** copy, styles, small fixes, renames, refactors with a clear target, test cleanup and docs need no plan. A new feature whose shape is a real choice gets a short spec first.
- **Parallel units:** pack asks into 3 to 6 units with disjoint files and start them all in one Workflow in the first minutes, with dependent units chained inside the script. Do one unit yourself meanwhile. Builders share the checkout and commit their own units.
- **One review:** builders check their own work. After every unit lands, run the full checks once, do the test hygiene pass, and get one independent review of the whole diff. One repair, then one re-review of only the raised findings.
- **Finish:** push the branch and open a pull request. Merging into the default branch is the owner's step; the plugin's guard blocks it and nothing else.

`/orchestra:goal TEXT` keeps the session working until every ask is done or dropped and the branch is pushed.

**Human-only steps** (credentials, dashboards, one-off cutovers): generate a bash wizard script instead of numbered steps in chat.
