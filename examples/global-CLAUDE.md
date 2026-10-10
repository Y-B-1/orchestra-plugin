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

The top-level session is the coordinator. It loads the `orchestra` skill (session start injects the path and the harness session id) and dispatches workers. The card engine is `python3 <plugin>/scripts/orchestra.py`; `--help` lists the commands.

**Size each ask by the diff it will produce**, not by the message:

| Tier | Changed lines | How it runs |
|---|---|---|
| tiny | up to 50 | inline edit in the main session |
| medium | up to 400 | inline, one unit after another |
| large | by escalation or owner request | 2+ independent units go to builders through the Workflow tool; the coordinator takes its own inline card in the same turn |

Start a run with `start --size tiny|medium`. Escalate with `route --size large --reason TEXT`.

**Lanes** (route by readiness and consequence):

- **answer:** a self-contained question. No ceremony.
- **investigate:** an unknown API or behavior. Investigator first; evidence before design.
- **direct:** settled, bounded, low risk. Goal, ownership, acceptance checks, self-review, then the pre-PR review.
- **design:** a product choice remains. Look facts up yourself; put decisions to the owner and wait.
- **plan:** an approved substantial design. Designer-planner in plan mode, then an independent critic.
- **bug:** investigator diagnosis and a failing behavior test before any repair. After the fix, name the check that would have caught the bug.
- **review:** an independent code-reviewer.
- **full-test:** only on the owner's explicit request.

**Roles:** `investigator` (code, docs), `designer-planner` (product, design, plan), `critic`, `builder` (implementation, frontend, sensitive, mechanical, repair, cleanup), `code-reviewer`, `operator` (gate, cleanup, release). The plugin pins each role's model, effort and tool allowlist.

**Briefs:** every worker brief has a `Mode: <mode>` line, the objective, owned files, checkable acceptance criteria, the project's standing orders pasted verbatim and the plugin root path. Reports start with `STATUS:` and `ARTIFACT:`.

**Independence:** the agent that built a change never approves it. One independent pre-PR review covers the frozen candidate. `prepr` picks the reviewer: Sonnet with one combined lens up to 400 changed lines, Opus with one card per lens above that. Any later edit voids earlier evidence.

**Guard:** the plugin's PreToolUse hook denies force push, `reset --hard`, `clean -f`, `branch -D` on an unmerged branch, `stash`, wholesale `git add`, `commit -a` and Agent calls from subagents. Do not register these again in projects. Never route around the guard with `gh api`, an MCP tool or a terminal tool.

**Autonomy:** an unattended run needs a written ledger (`<state>/autonomy.md`): completion checks, a deadline with UTC offset, approval boundaries. `orchestra.py autonomy arm` refuses without it. While armed, push, pull request merge and deletion are denied, and release is denied unless the ledger pre-authorizes that exact remote and target. Blocked cards park instead.

**Human-only steps** (credentials, dashboards, one-off cutovers): generate a bash wizard script instead of numbered steps in chat.
