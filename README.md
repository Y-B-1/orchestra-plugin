# Orchestra

Orchestra is a Claude Code plugin that turns the main session into a coordinator with six worker roles. It sizes each request, does small work inline, sends large work to parallel workers, reviews the result once before the pull request, and checks evidence before any release. It can also run unattended overnight inside a written ledger. No API key, daemon or extra service is needed.

The role count does not limit concurrency. Several instances of one role can run on disjoint files. The engine defaults to 20 workers (`max_workers`); harness limits and machine capacity still apply.

## Install

Prerequisites: Python 3.11 or later, Git and Claude Code. Native checks used Claude Code 2.1.289. Windows is not supported by the POSIX locking core; use WSL.

```sh
claude plugin marketplace add Y-B-1/orchestra-plugin
claude plugin install orchestra@orchestra-distribution
```

Restart the client. Enable the plugin and review its hook definition in the native trust interface; installation does not grant trust. Once trusted, every session starts with the coordinator contract. The coordinator runs on whatever model and effort you pick; explicit user or managed settings can override defaults.

Orchestra sets no context limit. For long runs, set Claude Code's auto-compaction in `~/.claude/settings.json`:

```json
{ "autoCompactWindow": 400000 }
```

The value is in tokens (100000 to 1000000). Claude Code caps it at the model's window, so it has no effect on a 200K model. Run state lives on disk (`progress.md`, `state.json`) and survives compaction.

No installer changes application instructions, resumes old work, grants release rights or writes hook trust. Existing project rules still apply. If a project carries older Orchestra enforcement of its own, port it separately to avoid two competing coordinators.

### Function hooks (optional)

On Claude Code the plugin also registers a function-hook module. It classifies commands in process, adds `/orchestra-board` and `/orchestra-autonomy on|off|status`, shows verdict and stop toasts and an autonomy status band, and appends the run's standing orders to `orchestra:` agent briefs. It needs `CLAUDE_CODE_ENABLE_FUNCTION_HOOKS=1` and the `$` APIs the module uses; it is tested on Claude Code 2.1.289 (CLI) and 2.1.286 (Desktop with that variable set). If the module is off or fails, the Python hooks do the same guarding and the CLI does everything else. See [hook policy](docs/hooks.md).

## How Orchestra works

From your first message to a finished branch:

1. **Session start.** The SessionStart hook gives the main session the coordinator contract and skill path, and the session id for `start --harness-session`. If a run brief is pending from the last run, its first 2000 characters show here.
2. **Read and answer.** The coordinator reads the project instructions and the repository state, then names the outcome, the owned files, the acceptance checks and every missing decision. A self-contained question gets a direct answer with no run.
3. **Triage and size.** Work is sized by the diff it will produce, not by item count. When the area is unknown, `investigator-code` cards scout it and return size estimates. Each separately stated ask counts (`--asks N`); the tier is the largest ask and the budget is the tier guide times the count.

   | Size | Diff | Route |
   | --- | --- | --- |
   | tiny | up to 50 changed lines | Inline edit in the main session, no alignment. A tiny builder card needs `dispatch --helper REASON`. |
   | medium | up to 400 | Grill inline, then build every unit inline in sequence. |
   | large | above 400, or more than one session can align | Escalation only: `route --size large --reason TEXT`, or an owner request. Map it, then a plan card; 2+ units go to builders through Workflow. |

   Tiny escalates to medium when an edit needs a decision or the diff passes the guide. Medium escalates to large when grilling outgrows one context or answers open questions faster than they close.
4. **Grill and record decisions.** The main session asks the questions, never a worker, in frontier rounds with a recommended answer for each. Settled terms go in the glossary; hard-to-reverse choices go in decision records.
5. **Map large work.** A large run charts its open decisions in a wayfinder map, `docs/maps/<name>.md`, one ticket per decision. Research tickets run together as `investigator` cards; prototype and grilling tickets need the owner. When nothing is left to decide, a `designer-planner` plan card takes over, followed by an independent `critic` challenge.
6. **Start the run.** `orchestra.py start --size tiny|medium [--asks N]` prints the lease once (`--size large` needs `--owner-request`). The coordinator writes `standing-orders.md`, a verbatim copy of the binding project rules, and pastes it into every brief.
7. **Cards, dispatch and reservations.** Each piece of work is a card with a role and mode, inputs, dependencies, owned files and acceptance criteria. The engine reserves atomically and refuses unknown or cyclic dependencies, overlapping ownership and exhausted capacity. Dependent cards start after their prerequisites are accepted. Concurrent editors work in separate worktrees, and the coordinator uses as few as it can.
8. **Inline work.** The coordinator reserves its own card with `inline TASK` and works beside disjoint workers under the same ownership and capacity checks. After it launches a Workflow or background agent, it starts its inline card in the same turn.
9. **Builders self-review.** A builder writes the failing test first, then the code. It ends its report with one `SELF_REVIEW:` line listing its checks and criteria, and a nonempty `ARTIFACT:` line. The engine refuses a builder report without them and accepts the card only on a clean line on the current artifact.
10. **Gates.** Checks run only through `orchestra.py gate NAME -- COMMAND...`, which records the actual exit and log hashes against the artifact. A passed gate on an unchanged artifact refuses a repeat unless `--again`. When the PR candidate is frozen, the operator gates the impact set and e2e; the full suite runs only on the owner's request.
11. **Size check and reviewer pick.** `orchestra.py prepr` compares the diff with the budget and warns when it is over; the warning never blocks. It also names the pre-PR reviewer: up to 400 changed lines, one Sonnet card (`code-reviewer-medium`, `Lens: combined`); above 400, one Opus card per lens in parallel.
12. **One pre-PR review.** This is the only independent code review. Lenses come from the diff: correctness always; security when a changed file matches policy `sensitive_paths`; standards and cleanup above `standards_min_lines` (default 200). Reviewers read the review packages and cite gate receipts instead of rerunning suites. A reviewer never fixes code or approves their own work.
13. **Repair, then hold.** A chain with a current finding gets one Opus builder `repair` card, then one fix re-review of the fix diff only (`repair_check: true`). CLEAN accepts the chain. BLOCKED holds it with `orchestra.py hold TASK --finding TEXT`: the work stays in place, the held log records it, and the run continues.
14. **Findings ledger.** The coordinator tries to refute each finding against the source and records what happened with `finding add`: rejected, deferred, inline, card or brief. Out-of-scope defects never change a verdict; each is fixed inline, made a card or left in the brief. `finding list --for-brief` gives reviewers the items not to re-raise.
15. **Finish and run brief.** `orchestra.py finish` closes the run once every card is accepted, nothing is parked or held, findings are triaged and the gates are current. Every end of a run appends a run brief to `progress.md`: Needs you first, then Still failing, Held log and Final rounds. `orchestra.py brief` prints it.
16. **Release.** Release is disabled by default. Project policy must name authorization, remote, target, commands and checks. During a run, a release action runs when a current engine permit matches it; otherwise Claude Code asks you to approve it. Without a release assignment, the brief says "ready to release".

```text
message ──> session start ──> read ──> answer? ──yes──> reply, no run
                                         │ no
                                         v
                              triage: size by diff, count asks
                   tiny ─────────────────┼──────────────── medium
             inline edit                 │            grill inline, build inline
                   │              large (escalation)               │
                   │          wayfinder map ──> plan card          │
                   │          ──> critic ──> Workflow builders     │
                   │          + coordinator inline card            │
                   └──────────────┬──────────────────────────────┘
                                  v
             builders: test first, SELF_REVIEW ──> accept
                                  v
             frozen candidate ──> gate ──> prepr (size check, reviewer)
                                  v
                        one pre-PR review (lenses)
                     CLEAN │                 │ finding
                           │      one Opus repair ──> fix re-review
                           │            CLEAN │         │ BLOCKED
                           │<─────────────────┘         └──> hold for owner
                           v
             finish ──> run brief ──> release (permit, or you approve)
```

### The autonomous branch

For unattended work, the same flow runs inside a ledger:

1. Run `orchestra.py autonomy arm` during an active run. The first call writes the ledger template to `<state>/autonomy.md` and refuses. Fill in the goal, deadline and completion checks, then arm again.
2. `arm` snapshots the ledger and prints a preconditions report, including a keep-awake step only you can take.
3. The Stop hook drives the loop. It continues a turn only when the coordinator can act now (see [Autonomous mode](#autonomous-mode)).
4. At an approval boundary the coordinator parks the card with `park TASK --reason TEXT` and moves on to other cards.
5. The coordinator may push a feature branch and open a pull request with `gh pr create`. You merge it after the run.
6. The run ends at the deadline, at completion or at another stop, and writes the run brief. You read it at the next session start.
7. In the morning, `unpark TASK` returns parked cards to the queue, and you settle any held chain before `finish`.

## Roles and models

The coordinator runs in the main session and is never dispatched as a worker. Six worker roles do the rest. Each worker loads its role skill and the shared `orchestra-worker` contract, and reads one mode file for its brief's `Mode:` line. Agent files in `plugins/orchestra/agents/` are generated from [`config/models.json`](plugins/orchestra/config/models.json) and [`config/roles.json`](plugins/orchestra/config/roles.json); each pins its model, effort and `tools:` allowlist. Agent types are `orchestra:<file name>`.

| Role (agent type) | What it does | Model / effort | Subtypes |
| --- | --- | --- | --- |
| Coordinator (`orchestrator`, main session) | Routes, reserves, dispatches, checks evidence, integrates; does inline work | Your selection | `main` |
| Investigator (`orchestra:investigator`) | Read-only source discovery and primary-source research. Tools: Read, Bash, WebFetch, WebSearch | Sonnet 5.5 medium | `docs`: Sonnet 5.5 medium (`orchestra:investigator`)<br>`code`: Haiku 5.5 high, Read and Bash only (`orchestra:investigator-code`) |
| Designer-planner (`orchestra:designer-planner`) | Product dossier, design and plan, as separate phases and artifacts. Tools: Read, Write, Edit, Bash, WebFetch, WebSearch | Sonnet 5.5 high | `product`, `design`, `plan`: Sonnet 5.5 high |
| Critic (`orchestra:critic`) | Independent challenge, conformance on one named axis, shipped-surface audit. Read-only. Tools: Read, Bash, WebFetch, WebSearch | Opus 5.5 high | Challenge: `requirements`, `feasibility`, `scope`, `judge`<br>Conformance: `spec`, `standards`, `ledger`<br>Audit: `surface`<br>All Opus 5.5 high |
| Builder (`orchestra:builder`) | Bounded implementation, tests first, self-review; repair of checked findings; end-of-run cleanup. Tools: Read, Edit, Write, Bash | Sonnet 5.5 medium | `implementation`, `frontend`, `sensitive`: Sonnet 5.5 medium<br>`mechanical`: Haiku 5.5 high (`orchestra:builder-mechanical`)<br>`cleanup`: Haiku 5.5 high (`orchestra:builder-cleanup`)<br>`repair`: Opus 5.5 medium, dispatched through the Agent tool with the model override |
| Code reviewer (`orchestra:code-reviewer`) | The pre-PR review of the integrated candidate and the fix re-review of a repair. Never fixes code. Read-only. Tools: Read, Bash | Opus 5.5 medium | Mode `final`, by lens:<br>above 400 lines, one card per lens: Opus 5.5 medium (`orchestra:code-reviewer`)<br>`standards` lens: Sonnet 5.5 medium (`orchestra:code-reviewer-standards`)<br>up to 400 lines, `Lens: combined`: Sonnet 5.5 medium (`orchestra:code-reviewer-medium`) |
| Operator (`orchestra:operator`) | Runs named checks and reports actual exits, preserves unfinished work, executes a project-authorized release. Never fixes code. Tools: Read, Write, Bash | Haiku 5.5 high | `gate`, `cleanup`, `release`: Haiku 5.5 high |

Workers never delegate, never own coordinator state and never release outside an explicit operator release card. [Role contracts](docs/roles.md) and the [model matrix](docs/models.md) have the details and the v1 to v2 role mapping.

## Guards

The PreToolUse hook classifies shell, edit and agent calls, then applies the run state.

| | No run active | Run active (interactive) | Autonomy armed |
| --- | --- | --- | --- |
| Destructive Git: `stash` (every form), `reset --hard`, `clean -f`, `branch -D` (unless provably merged), `git add .`/`-A`/`--all`, `commit -a`, `--amend`, force push, wholesale restore | Denied | Denied | Denied |
| Release actions: `git push`, `gh pr merge`, `gh release create`, npm or pnpm publish, deploy tools, `az` deployments | Allowed | Runs when a current engine permit matches; otherwise Claude Code asks you | Denied, card parked. Exception: a ledger `- Release: pre-authorized <remote> <target>` line that matches `policy.release` |
| Feature-branch push and `gh pr create` | Allowed | Push as above; `gh pr create` allowed | Allowed: explicit remote and branch, not the remote's default branch, `main` or `master`; `HEAD` resolves to the current branch |
| Merge: `gh pr merge`, local merge, pull, rebase or cherry-pick on the default branch | Allowed | `gh pr merge` as a release; local merges allowed | Denied, card parked; you merge the PR after the run |
| Push to the default branch | Allowed | As a release | Denied |
| Deletion: `rm`, branch or tag deletion, `git worktree remove` | Allowed | Allowed | Denied |
| Credential entry | Not detected | Not detected | Forbidden by procedure, not detected |
| Agent types | Any; workers cannot delegate | Only `orchestra:*` agents may be started; workers cannot delegate | Same |
| Reviewer and critic test runs | Not checked | Denied while a gate receipt is current: they cite it instead | Same |
| Run state and installed config files | Protected | Protected | Protected |

Guards are best effort, not a sandbox. Native hooks cover supported tool calls and recognizable commands. They do not stop encoded payloads, alias or variable indirection, interpreter one-liners, `gh api` calls, or MCP and terminal tools that push or merge; using those to get around the guard is forbidden by procedure, not enforced. Agent types are routing hints, not authentication. Use host sandboxing, branch protection and tool policy for stronger isolation. Details: [hook policy](docs/hooks.md).

## Autonomous mode

`orchestra.py autonomy arm|disarm|status` (on Claude, `/orchestra-autonomy on|off|status`) lets an active run continue unattended within a written ledger at `<state>/autonomy.md`.

**Ledger fields.** `goal`, `deadline` (ISO 8601 with a UTC offset, in the future), and completion checks, one `NAME: argv...` per line, each run with `orchestra.py gate NAME -- argv...`. The fixed approval boundaries follow:

```text
- Release: no release, permit or deploy.
- Merge: no pull request merge, and no local merge on the default branch.
- Push: push only a feature branch for a pull request; never the default branch.
- Deletion: no deletion of files, branches or tags.
- Credential entry: never enter credentials.
- Engine-gated actions: nothing that needs a permit.
```

You may replace the Release line with `- Release: pre-authorized <remote> <target>`, which must equal the configured `policy.release`. It overrides Push and Engine-gated actions for that remote and target only. A placeholder left in the ledger, or a field that does not parse, refuses `arm` and names the field. Any edit after `arm` stops the loop. Old `max_passes` and `max_stalls` fields are recorded and shown, never enforced.

**Loop.** The Stop hook continues a turn only when the coordinator can act now: a ready card, a reported card waiting for review, an open final finding, or a held chain owed its final review. Then it sends one line, `Autonomy pass N: ...`. While only background workers are running, the turn ends quietly and Claude Code wakes the session when a worker finishes. A continuation is never repeated for an unchanged board; that turn counts as a stall, never a stop.

**Stops.** `deadline`, `complete`, `ledger-tampered`, `disarmed`, `parked-only` and `no-ready-card`. The deadline is the only limit; no count of passes or stalls stops the run. `complete` needs every card accepted, no open finding, full review coverage, the gates and the triage. A stop is final for that arm; you re-arm. Ending the session ends autonomy.

**Boundaries.** Merge, pushes to the default branch, any other release, deletion and credential entry are hard. The coordinator parks the card and continues. `permit` and `release` are refused while autonomy is active, except for the one pre-authorized pair. Without pre-authorization an armed run adds no release card; the brief says "ready to release". `arm` reports the permission mode and a keep-awake reminder and changes neither.

## Commands

Run `python3.11 plugins/orchestra/scripts/orchestra.py [--repo REPO] COMMAND`. Each command prints a JSON receipt. Commands that change a run need the `--lease` that `start` printed.

```sh
python3.11 plugins/orchestra/scripts/orchestra.py --repo /path/to/project start --size medium
python3.11 plugins/orchestra/scripts/orchestra.py --repo /path/to/project board
```

| Command | Purpose |
| --- | --- |
| `start --size tiny\|medium [--asks N]` | Start a run and print the lease once |
| `status`, `board`, `ready` | Show cards and session state; list dispatchable cards |
| `route --size TIER --reason TEXT` | Change the tier mid-run |
| `add TASK.json`, `dispatch TASK WORKER [--helper REASON]`, `inline TASK` | Add a card; reserve it for a worker or the coordinator |
| `report WORKER TOKEN FILE`, `accept TASK` | Record a worker's result; accept a card on current evidence |
| `gate [--again] [--timeout S] NAME -- COMMAND...` | Run a check and record its receipt |
| `prepr` | Size check and pre-PR reviewer pick (read-only) |
| `review REVIEW.json` | Record the pre-PR review or the fix re-review |
| `finding add\|list`, `hold TASK --finding TEXT` | Findings ledger; end a repair ladder |
| `park TASK --reason TEXT`, `unpark TASK` | Set a card aside at a boundary; return it |
| `autonomy arm\|disarm\|status`, `brief` | Autonomous mode; print the newest run brief |
| `permit REMOTE TARGET`, `release REMOTE TARGET` | Release under configured policy |
| `classify "COMMAND"` | Print the guard verdict for a command without running it |
| `interrupt`, `finish` | Stop dispatch; close the run |

Every command, flag and schema: [CLI guide](docs/cli.md) and the package [CLI reference](plugins/orchestra/skills/orchestra/references/cli.md). Run state lives under the user state directory, outside the checkout (`orchestra.py where` prints it).

## Example instruction files

Two starting points, based on the files this project runs with:

- [`examples/global-CLAUDE.md`](examples/global-CLAUDE.md): a user-level `~/.claude/CLAUDE.md`. It sets coding discipline and session mechanics and routes work through Orchestra's size tiers, lanes and roles.
- [`examples/project-AGENTS.md`](examples/project-AGENTS.md): a project charter saved as `AGENTS.md` at the repository root. Its standing orders are the rules the coordinator pastes verbatim into every worker brief.

Keep global habits in the first file and project rules in the second. Do not copy rules the plugin's guard already enforces.

## Upgrade notes

See the [changelog](CHANGELOG.md) for full entries. Do not mix versions on one active run.

- **2.5 to 2.6.** The relaunch harness is gone: `orchestra.py relaunch`, `autonomy arm --relaunch`, `autonomy settle` and `config/relaunch-prompt.md`. Autonomy runs in the interactive session and ends with it. A 2.5 state armed with `--relaunch` loads as plain autonomy; re-arm in a live session to keep going. A 2.5 ledger with `- Push: no push to any branch.` still arms.
- **2.4 to 2.5.** A 2.4 run loads and keeps item routing; new runs use `--size`, and `start --items` is refused. Do not resume a 2.5 run with a 2.4 engine.
- **2.3 to 2.4.** A 2.3 run loads when its policy is unchanged, keeps 2.3 routing and is rebound to 2.4 on its first write. Its gate and review receipts go stale: rerun the gate and the pre-PR review before `finish`. A queued `code-reviewer` checkpoint card no longer dispatches. A policy or role change during an active run is refused: end that run with the version that started it, or move its `state.json` out of the state directory.
- **2.1 to 2.2.** A 2.1 run loads; its `max_passes` and `max_stalls` are recorded, not enforced. End every 2.1 session before the first `hold` or before arming under 2.2, or the 2.1 hooks fail closed.
- **1.0.1 to 2.0.** A finished or interrupted 1.0.1 run needs `start --new-run`. A run still active must be ended with 1.0.1 first, from its repository: `python3.11 ~/.claude/plugins/cache/orchestra-distribution/orchestra/1.0.1/scripts/orchestra.py --lease LEASE interrupt` (or `finish`); the lease is `session.lease` in that script's `status`. If you already upgraded, move the run's `state.json` out of the state directory: `$ORCHESTRA_STATE_DIR`, else `${XDG_STATE_HOME:-~/.local/state}/orchestra/<id>`, where `<id>` is the first 24 hex characters of the SHA-256 of the repository's absolute path (`orchestra.py where` prints it). See the [2.0.0 release notes](docs/RELEASE-NOTES-2.0.0.md).

Reinstall from the marketplace, then restart the client:

```sh
claude plugin uninstall orchestra@orchestra-distribution
claude plugin marketplace remove orchestra-distribution
claude plugin marketplace add Y-B-1/orchestra-plugin
claude plugin install orchestra@orchestra-distribution
claude plugin list
```

To try a local checkout before it is published, use the same steps with `claude plugin marketplace add /path/to/orchestra-plugin`. A marketplace name can exist only once, so remove the installed one first. Orchestra hooks are absent between uninstall and install, so run these in a plain terminal, not from an Orchestra-guarded session. `claude plugin list` must show exactly one `orchestra@orchestra-distribution`.

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
