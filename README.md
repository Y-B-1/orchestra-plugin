# Orchestra

Orchestra is a Claude Code plugin for prompts that hold more than one ask. It splits the prompt into asks, runs every independent ask at the same time, reviews the finished work once, and pushes a branch for you to merge. `/orchestra:goal` keeps a session working until every ask is done. One guard blocks merging into the default branch; everything else runs.

Version 3.0.0 is a rewrite. The plugin is now one coordinator skill, five agents, one command and three small hooks in one Python file (`scripts/lean.py`, standard library only). It needs no API key, daemon or extra service.

## Install

Prerequisites: Python 3.11 or later, Git and Claude Code.

```sh
claude plugin marketplace add Y-B-1/orchestra-plugin
claude plugin install orchestra@orchestra-distribution
```

Updates: Claude Code does not auto-update third-party marketplaces unless you turn it on. In a session run `/plugin`, open the Marketplaces tab, select `orchestra-distribution` and choose Enable auto-update. Without it, run `claude plugin marketplace update orchestra-distribution`, then `claude plugin update orchestra@orchestra-distribution`. A new copy arrives only when the version in `plugin.json` changes, which every release does.

Restart the client, then enable the plugin and review its hooks in the native trust interface. Installation does not grant trust.

## How a multi-request prompt runs

1. **Session start.** The SessionStart hook tells the main session that Orchestra is on and prints the path of the ask ledger.
2. **Ask ledger.** The main session writes one line per ask to the ledger, in the user's order: an id, the files the ask touches, what it waits for, and a status mark (`[ ]` todo, `[>]` running, `[x]` done, `[~]` dropped with a reason). The ledger lives in the Git directory (`.git/orchestra/asks.md`), outside the working tree.
3. **Plan by novelty.** Copy, styles, small fixes, renames, refactors with a clear target, test cleanup and docs need no plan, however many there are. A new page, feature or capability whose shape is a real choice gets a short spec, written by its own builder first. Only a large or risky feature gets a separate planner and critic, and only that ask waits for them.
4. **Units in one Workflow.** Asks are packed into 3 to 6 units, one builder each. Asks that edit the same file share a unit or run in order. The whole dependency graph runs in one Workflow script, so a dependent unit starts the moment its inputs finish. The main session builds one unit itself while the Workflow runs. Builders with disjoint files share the checkout; only units that must edit the same file use a worktree.
5. **Builders check and commit.** Each builder checks its work against its asks, runs the checks for its own files (bounded with `lean.py run SECONDS -- CMD`) and commits its own files with explicit paths.
6. **One review.** When every unit has landed, the main session runs the project's full checks once. One `orchestra:reviewer` reviews the whole diff against the ledger. Real findings go to one repair builder, then one re-review of only the repair diff and only the raised findings. New notes go in the final message, not another round.
7. **Test hygiene.** Before every pull request, a cleanup unit removes duplicate, skipped and implementation-detail tests, replaces brittle markup snapshots with behavior checks and removes lint suppressions without a reason. A failing test is fixed, never silenced.
8. **Push and pull request.** The main session pushes the branch and opens a pull request when the remote is GitHub. It deletes the worktrees and branches it created. The final message lists each ask with its status, the decisions made without asking, the check results and the branch or pull request. Merging is the owner's step.

## Agents

| Agent | Model | Effort | Job |
| --- | --- | --- | --- |
| `orchestra:builder` | Sonnet 5.5 | medium | Builds one unit, checks it and commits it |
| `orchestra:reviewer` | Opus 5.5 | medium | One independent review of the whole diff, and the scoped re-review of a repair |
| `orchestra:planner` | Sonnet 5.5 | high | A short spec for one large or risky feature |
| `orchestra:critic` | Opus 5.5 | high | Challenges that spec before it is built |
| `orchestra:investigator` | Haiku 5.5 | high | Fast read-only discovery of the files an ask touches |

The main session runs on the model and effort you pick.

## /orchestra:goal

`/orchestra:goal TEXT` starts a goal. The main session records it with `lean.py goal set`, writes the ledger and works without stopping to ask; it lists the calls it made at the end. While a goal is active, the Stop hook blocks the session from stopping until every ledger line is `[x]` or `[~]`, the changes are committed and the branch is pushed. It stops blocking after 60 continuations. When only the owner can unblock the work, the session runs `lean.py goal stop REASON`.

Without a goal, the Stop hook reminds the session once when the ledger still has open asks, and never loops.

## The guard

The PreToolUse hook reads every Bash command and denies only the steps that merge into the default branch: `gh pr merge`, a `gh api` merge call, a push to the default branch, and a force push or delete of it. Everything else runs, including pushing other branches, opening pull requests and deleting stale branches and worktrees. Orchestra never asks for permission; Claude Code's permission mode decides everything else. The guard is a safety net for agents, not isolation. See [hooks](docs/hooks.md).

## What 3.0.0 removed, and why

Versions up to 2.15.3 ran a Python card engine with leases, reservations, receipts, gates and an autonomy mode, a 7,000-line board mod, three guard modes, size tiers, eight role skills and twelve agents. A benchmark on long multi-request prompts showed that this smaller design delivers about the same quality in about 40% less time than plain Claude Code (7.4 against 12.7 minutes per task, at the same cost), and in about a third of the time and cost of 2.15.3: the removed parts cost time without a measured quality gain. The ask ledger and Git now hold all state, `/orchestra:goal` replaces autonomy, and one guard replaces the guard modes. Details: [docs/BENCHMARK.md](docs/BENCHMARK.md).

## Set up your agent session (once)

Do this once after installing, then again only when a session feels slow or forgetful. It takes about fifteen minutes and needs no plugin feature: it is advice, plus a script you run yourself. Everything here was checked against the Claude Code documentation in October 2026.

### 1. See what loads before you type

Context you pay for in every session comes from a short list: the system prompt, MCP tool definitions, the skill listing (name and description of every skill and plugin skill), agent descriptions, your `CLAUDE.md` files, auto memory and hook output. Look at it first.

- `/context` shows the breakdown for the current session; `/context all` expands each item. It also warns about context-heavy tools and memory bloat.
- `/skills` lists skills; press `t` to sort them by token count.
- `claude plugin details <plugin>` prints a plugin's always-on tokens. Orchestra's always-on cost is one skill description, five agent descriptions, one command description and a two-line session-start note. The skill body loads only when the skill runs.
- The script below lists the instruction files, skill and agent descriptions and MCP servers on disk, biggest first. It is standard-library Python and runs on Windows too. Run it from a project root: `python scan.py`.

<details>
<summary>scan.py</summary>

```python
"""One-off: list what your sessions load before you type anything, biggest first. Run from a project root."""
import glob, json, os, re
from pathlib import Path

home = Path.home()
rows = []

def add(kind, path, text):
    rows.append((len(text), kind, str(path)))

def read(path):
    try:
        return Path(path).read_text(encoding='utf-8', errors='replace')
    except OSError:
        return ''

# Instruction files: always loaded in full.
for p in [home / '.claude/CLAUDE.md', Path('CLAUDE.md'), Path('CLAUDE.local.md'), Path('AGENTS.md')]:
    if p.is_file():
        add('instructions (all of it, every session)', p, read(p))

# Skills and agents: only the description sits in context; the body loads when used.
roots = [home / '.claude/skills', Path('.claude/skills')] + [Path(x) for x in glob.glob(str(home / '.claude/plugins/cache/**/skills'), recursive=True)]
for root in roots:
    for skill in glob.glob(str(root / '*/SKILL.md')):
        text = read(skill)
        match = re.search(r'^description:\s*(.*)$', text, re.M)
        add('skill description (body loads on use)', skill, (match.group(1) if match else '') + Path(skill).parent.name)
for root in [home / '.claude/agents', Path('.claude/agents')] + [Path(x) for x in glob.glob(str(home / '.claude/plugins/cache/**/agents'), recursive=True)]:
    for agent in glob.glob(str(root / '*.md')):
        match = re.search(r'^description:\s*(.*)$', read(agent), re.M)
        add('agent description', agent, match.group(1) if match else '')

# MCP servers: every tool's name and schema is loaded unless tool search defers it. Count the servers here;
# /context shows the real token cost of their tools.
for config in [Path('.mcp.json'), home / '.claude.json']:
    try:
        servers = json.loads(read(config)).get('mcpServers', {})
    except ValueError:
        servers = {}
    for name in servers:
        add('MCP server (see /context for its tools)', f'{config}: {name}', '')

print(f'{"~tokens":>8}  {"kind":<42} source')
for size, kind, path in sorted(rows, reverse=True):
    print(f'{size // 4:>8}  {kind:<42} {path}')
print(f'{sum(r[0] for r in rows) // 4:>8}  total of the above (plus tools, system prompt and memory: run /context)')
```

</details>

### 2. Trim what you do not use

- **MCP servers.** Tool search is on by default: only tool names load at start and a schema loads when the tool is needed. `ENABLE_TOOL_SEARCH=auto:10` loads tools up front only while they fit in 10 percent of the window; `false` loads everything. A server entry can set `"alwaysLoad": true` for the few tools you use constantly. `/mcp disable <server>` switches a server off for now; `disabledMcpjsonServers` in settings rejects one that a project's `.mcp.json` asks for. Remove servers you have not called in a month.
- **Plugins.** `claude plugin disable <name>@<marketplace> --scope local` turns one off for a single repository without uninstalling it. Keep a plugin enabled globally only if you would use it in most projects.
- **Skills.** Only the description sits in context. Set `disable-model-invocation: true` in a skill you invoke by name, or `skillOverrides` to `"off"`, `"name-only"` or `"user-invocable-only"` in settings. Descriptions longer than 1,536 characters are cut; `skillListingMaxDescChars` and `skillListingBudgetFraction` tune the listing.
- **Instruction files.** Keep each `CLAUDE.md` under 200 lines. `@path` imports do not reduce cost, because the imported text loads too. Files in subdirectories load only when Claude works there, so a rule that matters in one package belongs in that package. Move reference material that is needed rarely into a skill or a doc the file links to.
- **Habits.** `/clear` between unrelated tasks. `/compact` with a focus sentence at a natural break; the skill listing is not injected again afterward, and skill bodies that ran come back capped at 5,000 tokens each.

### 3. Your global `~/.claude/CLAUDE.md`

It loads into every session in every project, so it holds only what is true everywhere: how you want the agent to think, your Git habits, which tools you prefer and what it must never do. Aim for 60 lines.

- Put in: plan before editing, state assumptions, keep changes minimal, evidence for every "done" claim, commit each working step with explicit paths, never `git stash` when worktrees are in use, never push to the default branch.
- Leave out: build commands, file layouts, domain terms and anything about one repository. Those belong in that repository.
- Add a routing line for Orchestra: a prompt with more than one ask loads the `orchestra` skill.
- Prefer a hook or a check to another sentence when a rule must always hold.

[`examples/global-CLAUDE.md`](examples/global-CLAUDE.md) is a ready starting point. Copy it, then delete what you do not want.

### 4. Each project's `AGENTS.md`

It holds what only this repository can tell the agent. Claude Code reads `AGENTS.md` itself (2.1.277 or later) when the directory has no `CLAUDE.md`. If you keep a `CLAUDE.md` as well, `CLAUDE.md` wins; put `@AGENTS.md` in it so both tools read one file.

- Put in: the commands that build, test and lint (fast check per edit, scoped test per unit, full suite on request), the layout and who owns what, the conventions a newcomer would get wrong, what is never allowed (migrations, secrets, release) and where state and decisions live.
- Give the agents a short section of **binding rules**, each one checkable. The reviewer checks the diff against them, so keep them where it will look: this file.
- Test each line: if deleting it would not cause a mistake, delete it. Do not repeat what a guard, a hook or the linter already enforces.
- Keep it under 200 lines and update it in the commit that changes the behavior it describes.

[`examples/project-AGENTS.md`](examples/project-AGENTS.md) is a starting charter.

### 5. The one-time checklist

1. Run `/context`, then `scan.py`, and write down the five biggest items.
2. Disable or remove every MCP server, plugin and skill you did not use this month.
3. Cut your global `CLAUDE.md` to what holds everywhere; move the rest to project files.
4. Give each active project an `AGENTS.md` with commands, ownership and standing orders.
5. Start a fresh session, run `/context` again, and compare the totals.

To have the agent do the file-based part for you, paste: "Run `python scan.py` in this repository. Also list `~/.claude/CLAUDE.md`, `CLAUDE.md`, `AGENTS.md`, `.mcp.json` and the enabled plugins with their sizes. Report the ten largest fixed-context items with a one-line recommendation each. Change nothing." You still run `/context` yourself: the agent cannot open slash commands.

## Upgrade notes

See the [changelog](CHANGELOG.md) for full entries.

- **2.x to 3.0.** 3.0.0 has no run state, no CLI engine and no autonomy mode. Finish or interrupt any active 2.x run with the 2.x plugin before you upgrade. The old run state under `${XDG_STATE_HOME:-~/.local/state}/orchestra` is no longer read; delete it when you no longer need it. The `/orchestra-board` and `/orchestra-autonomy` commands are gone; use `/orchestra:goal` instead of autonomy.

Reinstall from the marketplace, then restart the client:

```sh
claude plugin uninstall orchestra@orchestra-distribution
claude plugin marketplace remove orchestra-distribution
claude plugin marketplace add Y-B-1/orchestra-plugin
claude plugin install orchestra@orchestra-distribution
claude plugin list
```

To try a local checkout before it is published, use the same steps with `claude plugin marketplace add /path/to/orchestra-plugin`. A marketplace name can exist only once, so remove the installed one first. `claude plugin list` must show exactly one `orchestra@orchestra-distribution`.

## Uninstall

Run `claude plugin uninstall orchestra@orchestra-distribution` and `claude plugin marketplace remove orchestra-distribution`. To leave no trace, also delete `.git/orchestra/` in each repository where you used it; it holds the ask ledger and the goal file.

## Check and distribute

To publish a release: raise the version in both manifests (`plugins/orchestra/plugin.json` and `plugins/orchestra/.claude-plugin/plugin.json`), add `docs/release-notes/v<version>.md`, merge, then run the [Release workflow](.github/workflows/release.yml) from main (Actions, Release, Run workflow), or push the tag `v<version>`. Either way it checks that the commit is on main, that the tag matches `plugin.json` and that the notes exist, then builds the archives and publishes the release with their checksums. Run by hand, it creates the tag itself.

All checks run locally. Before a push, run:

```sh
scripts/check.sh
```

It runs the unit tests on Python 3.11 and 3.13 (3.13 through `uv` when it is not on `PATH`), a JSON check of `hooks/hooks.json`, and the strict plugin and marketplace validation. It lists any check it could not run as SKIPPED. Before a release, also run `python3 scripts/live-check.py`: it runs the hooks in three real headless sessions ([live check](docs/live-check.md)). [CI](.github/workflows/ci.yml) runs only when started by hand (Actions, CI, Run workflow). To build the release archives locally, run `python3.11 scripts/build_release.py`.

GitHub supplies an installable marketplace and release archives. Public directory listing requires a separate host submission; publishing this repository does not claim marketplace approval.

MIT license covers the package code and instructions. Ideas from MIT-licensed sources are credited in `plugins/orchestra/THIRD-PARTY-NOTICES`.
