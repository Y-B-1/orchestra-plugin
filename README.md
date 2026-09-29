# Orchestra

Orchestra packages a main coordinator and ten worker contracts for Codex and Claude Code. It routes work into lanes, dispatches ready independent cards, groups reviews, and checks evidence before release. No classifier API key, daemon or Charge installation is needed.

The role count does not limit useful concurrency. Multiple instances of the same role can run on disjoint files and resources. The portable core defaults to 20 workers; actual harness limits and machine capacity still apply.

## Install

Prerequisites: Python 3.11 or later, Git, and a supported Codex or Claude Code client. Native checks used Codex CLI 0.158.0 and Claude Code 2.1.284. Windows is not supported by the POSIX locking core; use WSL. Other harnesses can use the portable CLI and contracts but need their own native adapter.

Codex:

```sh
codex plugin marketplace add Y-B-1/orchestra-plugin --ref main
codex plugin add orchestra@orchestra-distribution
git clone https://github.com/Y-B-1/orchestra-plugin.git
python3.11 orchestra-plugin/plugins/orchestra/scripts/orchestra.py install-profiles
```

The last command installs namespaced worker profiles once in the user configuration. Plugin installation alone does not discover plugin-local Codex agent files. The installer preserves unrelated profiles and records file hashes. Rerun after updates. Keep the clone while profiles refer to its method paths.

Claude Code:

```sh
claude plugin marketplace add Y-B-1/orchestra-plugin
claude plugin install orchestra@orchestra-distribution
```

Restart the client after installation. Enable the plugin and review its hook definition in the native trust interface. Codex skips untrusted hooks; installation does not grant trust. Once enabled and trusted, startup supplies the main coordinator contract. Claude also uses the plugin's default main agent. Explicit user or managed settings can override defaults.

No installer changes application instructions, restores symlinks, resumes old work, grants release rights or writes hook trust. Existing project rules remain applicable. Port a project's old Orchestra enforcement separately to avoid competing coordinators.

## Roles and models

[Role contracts](docs/roles.md) describe responsibilities and timing. [Model matrix](docs/models.md) lists provider settings. Worker profiles embed their relevant procedures; the main skill loads phase references as needed. The generator produces 13 Codex worker profiles and 14 Claude profiles, including three settings presets. These are ten worker roles, not 27 agents that always run.

The final code review always checks requirements, correctness, security, tests, architecture, standards and cleanup. An auditor runs a separate pass for each needed conformance axis. Gatekeeper runs actual commands; releaser executes only a configured authorized target. A reviewer cannot approve their own work.

## Run the workflow

Read [the CLI guide](docs/cli.md) for task and review schemas. Run state lives under the user state directory, outside the application checkout. Use `route` with inspected facts, `review-groups` with reported cards, and `audit-policy` with conformance facts. The core enforces dependencies, reservations, capacity, lifecycle and evidence freshness; the coordinator supplies semantic facts and checks findings.

```sh
python3.11 plugins/orchestra/scripts/orchestra.py --repo /path/to/project start
python3.11 plugins/orchestra/scripts/orchestra.py --repo /path/to/project board
```

Release is disabled by default. Explicit project policy names authorization, exact remote, target, commands and required checks. Configuring Orchestra never grants permission beyond the user's instructions. Native hooks cover supported tool calls and recognizable commands; they are not a sandbox for arbitrary scripts or hostile workers.

## Check and distribute

```sh
python3.11 -m unittest discover -s tests
python3.11 plugins/orchestra/scripts/generate.py --check
claude plugin validate --strict plugins/orchestra
claude plugin validate --strict .claude-plugin/marketplace.json
python3.11 scripts/build_release.py
```

[Source comparison](docs/source-parity.md), [hook policy](docs/hooks.md), and [validation evidence](docs/VALIDATION.md) record what was preserved, changed, checked and not established. GitHub supplies an installable marketplace and release archives. Public directory listing requires a separate host submission; publishing this repository does not claim marketplace approval.

MIT license covers the original package code and instructions. Private source snapshots and application history are not distributed.
