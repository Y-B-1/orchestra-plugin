# Orchestra

Orchestra packages a main coordinator and six worker roles for Codex and Claude Code. It routes work into lanes, dispatches ready independent cards, reviews returned work, and checks evidence before release. No classifier API key, daemon or Charge installation is needed. Version 2.0.0 is a breaking release; see [release notes](docs/RELEASE-NOTES-2.0.0.md).

The role count does not limit useful concurrency. Multiple instances of the same role can run on disjoint files and resources. The portable core defaults to 20 workers; actual harness limits and machine capacity still apply.

## Install

Prerequisites: Python 3.11 or later, Git, and a supported Codex or Claude Code client. Native checks used Codex CLI 0.159.0 and Claude Code 2.1.289. Windows is not supported by the POSIX locking core; use WSL. Other harnesses can use the portable CLI and contracts but need their own native adapter.

Codex:

```sh
codex plugin marketplace add Y-B-1/orchestra-plugin --ref main
codex plugin add orchestra@orchestra-distribution
git clone https://github.com/Y-B-1/orchestra-plugin.git
python3.11 orchestra-plugin/plugins/orchestra/scripts/orchestra.py install-profiles
```

Codex installs the generated native package; Claude installs the canonical package. The generator checks both against the same source.

The last command installs namespaced worker profiles once in the user configuration. Plugin installation alone does not discover plugin-local Codex agent files. The installer preserves unrelated profiles and records file hashes. Rerun after updates. Keep the clone while profiles refer to its method paths.

Claude Code:

```sh
claude plugin marketplace add Y-B-1/orchestra-plugin
claude plugin install orchestra@orchestra-distribution
```

Restart the client after installation. Enable the plugin and review its hook definition in the native trust interface. Codex skips untrusted hooks; installation does not grant trust. Once enabled and trusted, startup supplies the main coordinator contract. Claude also uses the plugin's default main agent, whose model and effort follow your picker. Explicit user or managed settings can override defaults.

No installer changes application instructions, restores symlinks, resumes old work, grants release rights or writes hook trust. Existing project rules remain applicable. Port a project's old Orchestra enforcement separately to avoid competing coordinators.

### Upgrade from 1.0.1

A 1.0.1 run that was finished or interrupted leaves the repository unarmed under 2.0.0. Plain `start` and `status` then say to run `start --new-run`, which archives the old state and starts a fresh run.

A run left active across the upgrade is different. Old role names are rejected, so a live 1.0.1 run cannot continue, and 2.0.0 cannot clear it: its policy hash differs, so `interrupt`, `finish` and `start --new-run` all refuse it. End it with 1.0.1 first, from its repository, with 1.0.1 still installed. Claude Code: `python3.11 ~/.claude/plugins/cache/orchestra-distribution/orchestra/1.0.1/scripts/orchestra.py --lease LEASE interrupt` (or `finish`). Codex only: `python3.11 ~/.codex/plugins/cache/orchestra-distribution/orchestra/1.0.1/scripts/orchestra.py --lease LEASE interrupt`. LEASE is the value `start` printed; if you lost it, the same script's `status` prints the state, and the lease is `session.lease` in that output. If you already upgraded with a run active, move that run's `state.json` out of the state directory by hand; the repository is then unarmed. Run `orchestra.py where` (any version) from the repository to print the state directory. It is `$ORCHESTRA_STATE_DIR` when set, otherwise `${XDG_STATE_HOME:-~/.local/state}/orchestra/<id>`, where `<id>` is the first 24 hex characters of the SHA-256 of the repository's absolute path. Then reinstall from the marketplace, restart the client, and rerun `install-profiles` from an updated clone for Codex so the new profiles replace the old ones.

```sh
claude plugin uninstall orchestra@orchestra-distribution
claude plugin marketplace remove orchestra-distribution
claude plugin marketplace add Y-B-1/orchestra-plugin
claude plugin install orchestra@orchestra-distribution
claude plugin list
```

```sh
codex plugin marketplace upgrade orchestra-distribution
codex plugin remove orchestra@orchestra-distribution
codex plugin add orchestra@orchestra-distribution
git -C orchestra-plugin pull --ff-only
python3.11 orchestra-plugin/plugins/orchestra/scripts/orchestra.py install-profiles
```

### Install a checkout first

To run a build from a local clone before it is published, install it the same way and restart. A marketplace name can exist only once, so remove the installed one first. Installing the new version first matters for releases: the 2.0.0 guard allows an ordinary non-force push and pull request merge outside an armed run, which the 1.0.1 guard denied.

```sh
claude plugin uninstall orchestra@orchestra-distribution
claude plugin marketplace remove orchestra-distribution
claude plugin marketplace add /path/to/orchestra-plugin
claude plugin install orchestra@orchestra-distribution
claude plugin list
```

Orchestra hooks are absent between uninstall and install, so run these in a plain terminal rather than from an Orchestra-guarded session. `claude plugin list` must show exactly one `orchestra@orchestra-distribution`.

### Mods and function hooks

On Claude Code the plugin also registers a function-hook module that classifies commands in process, adds `/orchestra-board` and `/orchestra-autonomy`, and shows toasts and a status band. It needs a Claude Code build with function hooks enabled (`CLAUDE_CODE_ENABLE_FUNCTION_HOOKS=1`) and the `$` APIs the module uses; it is tested on Claude Code 2.1.289 (CLI) and 2.1.286 (embedded in Desktop with that variable set). There is no version floor and no explicit API check: if a needed API is missing, session start fails, the guard stays not ready, and guarded calls fall back to the Python hooks. In that case, and with function hooks off, the Python hooks do the same guarding and the CLI does everything else. See [hook policy](docs/hooks.md).

## Roles and models

[Role contracts](docs/roles.md) describe responsibilities and the v1 to v2 mapping. [Model matrix](docs/models.md) lists provider settings. The coordinator runs in the main session and never as a worker. The six worker roles are investigator, designer-planner, critic, builder, code-reviewer and operator; each role has one skill and loads one mode file for its brief's `Mode:` line. The generator produces 10 Codex worker profiles and 8 Claude worker agents plus the orchestrator.

Every final integration review covers requirements, correctness, security, tests, architecture, standards and cleanup, in four lenses (correctness, architecture, security, cleanliness). A critic runs a separate pass for each needed conformance axis. The operator runs actual commands and executes only a configured authorized release. A reviewer cannot approve their own work.

| v1 role | v2 role and mode |
| --- | --- |
| orchestrator | orchestrator / main |
| investigator, investigator-code | investigator / docs, code |
| founder-mind (design) | designer-planner / product |
| founder-mind (audit) | critic / surface |
| designer-planner | designer-planner / design, plan |
| red-teamer | critic / requirements, feasibility, scope, judge |
| auditor | critic / spec, standards, ledger |
| builder | builder / implementation, frontend, sensitive, mechanical |
| builder-repair | builder / repair |
| code-reviewer, code-reviewer-checkpoint | code-reviewer / final, checkpoint |
| gatekeeper | operator / gate |
| janitor | operator / cleanup |
| releaser | operator / release |

## Run the workflow

Read [the CLI guide](docs/cli.md) for commands and the package [CLI reference](plugins/orchestra/skills/orchestra/references/cli.md) for task and review schemas. Run state lives under the user state directory, outside the application checkout. The core enforces dependencies, reservations, capacity, lifecycle and evidence freshness; the coordinator supplies semantic facts and checks findings.

```sh
python3.11 plugins/orchestra/scripts/orchestra.py --repo /path/to/project start
python3.11 plugins/orchestra/scripts/orchestra.py --repo /path/to/project board
```

Release is disabled by default. Explicit project policy names authorization, exact remote, target, commands and required checks. Configuring Orchestra never grants permission beyond the user's instructions. Outside an armed run, ordinary pushes and pull request merges are not gated by a permit; inside one they need the engine permit. Native hooks cover supported tool calls and recognizable commands; they are not a sandbox for arbitrary scripts or hostile workers.

### Autonomous mode

`orchestra.py autonomy arm|disarm|status` (on Claude, `/orchestra-autonomy on|off|status`) lets the run continue unattended within a written ledger of goal, completion checks, pass and stall caps and a deadline. Release, push, merge, deletion and credential entry are hard boundaries: the coordinator parks the card and continues with other cards. A morning report lands in the run's `progress.md` and in the next session start. See the [CLI guide](docs/cli.md).

## Check and distribute

```sh
python3.11 -m unittest discover -s tests
python3.11 plugins/orchestra/scripts/generate.py --check
claude plugin validate --strict plugins/orchestra
claude plugin validate --strict .claude-plugin/marketplace.json
python3.11 scripts/build_release.py
```

[Source comparison](docs/source-parity.md), [hook policy](docs/hooks.md), and [validation evidence](docs/VALIDATION.md) record what was preserved, changed, checked and not established. GitHub supplies an installable marketplace and release archives. Public directory listing requires a separate host submission; publishing this repository does not claim marketplace approval.

MIT license covers the original package code and instructions. Skill files derive in part from MIT-licensed sources credited in `plugins/orchestra/THIRD-PARTY-NOTICES`. Private source snapshots and application history are not distributed.
