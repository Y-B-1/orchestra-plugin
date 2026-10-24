# Portable CLI

The maintained command guide and the task/review schemas live in the package [CLI reference](../plugins/orchestra/skills/orchestra/references/cli.md). The package carries that guide after installation. This page lists every command.

Run `python3 plugins/orchestra/scripts/orchestra.py [--repo REPO] [--state STATE] [--actor ACTOR] [--lease LEASE] COMMAND`. Each command prints a JSON receipt. A card-moving command adds a `board` key, one line saying what moved and what waits. Run from a linked worktree, any command except `where` is refused when the main checkout holds the run state. `--actor` and `--lease` are consistency checks, not authentication. The Lease column says whether the command needs `--lease` from `start`.

| Command | Purpose | Lease |
| --- | --- | --- |
| `start [--policy FILE] [--harness-session ID] [--new-run] --size tiny\|medium\|large [--asks N] [--owner-request]` | Start a run and print the lease once. `--size` is required for a new run; `large` needs `--owner-request`. `--items` is refused (2.4 flag). With `--harness-session`, ending that Claude Code session releases the run. `--new-run` is refused while a stopped autonomous run keeps its report and the owner has no receipt for it. An unknown policy key in `--policy` is refused. | no |
| `where` | Print the repository, the state directory and whether `standing-orders.md` exists. | no |
| `status` | Print cards, session state (`size`, `asks`, `owner_request`, or the 2.4 route) and `required_lenses`. Never prints a lease. | no |
| `prepr` | Print the size check and the pre-PR reviewer: `base`, `changed_lines`, `size`, `asks`, `budget`, `over_budget`, `reviewer`, `agent`, `lenses`, `warning`. Read-only; the warning never blocks. | no |
| `board` | Group card ids by role and state; `leftover_worktrees` counts every entry under `.claude/worktrees/`, landed or not. | no |
| `waves` | Print overlaps, unmet prerequisites, ordered waves, the cards startable now, `idle_workers` and `prep` (blocked builder cards no `prep_for` card prepares). Read-only. | no |
| `worktrees` | List the entries under `.claude/worktrees/` with branch, card, `landed` and `clean`, and print `git worktree remove <path>` for each landed clean one. Read-only; the engine never creates or removes a worktree. | no |
| `refusals [--last N]` | Print the newest refused commands (exit 2) from the refusal log, default 10. Read-only. | no |
| `card TASK [--out FILE]` | Print the brief skeleton rendered for a card, or write it to FILE. Read-only. | no |
| `ledger [--cards ID[,ID]]` | Print BUILD-LEDGER rows (card, role, commit, evidence, status) for accepted cards from engine facts. Read-only. | no |
| `package TASK` | Write a reviewer package (brief, report, self-review, diff stat) under `<state>/packages` and print its path. | no |
| `wave [--inline ID] [--helper REASON] [--serial REASON] [--emit] ID ...` | Start every named card in one step, all or none. `--emit` also prints per card `agent_type`, `model_override`, `isolation`, `fast_forward`, `prompt` (with an `Assignment: WORKER TOKEN` line) and `agent_call`; a card may carry `variant` (`standards` or `medium`). `wave --emit` records each card's base for the `report` base check. | yes |
| `artifact [--tasks ID[,ID]]` | Print the whole-repo artifact, or with `--tasks` the artifact scoped to those cards' reserved files plus HEAD. | no |
| `report [--accept --lease LEASE] WORKER TOKEN FILE` | Record a worker's result file against its assignment token. The same worker may replace the report until the card is accepted or a review covers it. A builder report must answer every acceptance line verbatim. It is refused when its commit is not built on the card's recorded base (recorded by `wave --emit`; `dispatch` and `inline` record none). `--accept` (inline cards only) records the report and accepts the card in one call. | no (`--accept`: yes) |
| `autonomy arm\|disarm\|status` | Arm, disarm or inspect the autonomous loop. | no |
| `brief` | Print the newest run brief. Read-only. | no |
| `finding list [--for-brief]` | List the findings ledger, or render a "Known findings" block for reviewer briefs. | no |
| `classify "SHELL COMMAND"` | Print the classifier's decision for a command string without running it. The hook then applies the run state: a `releasemulti` category is the release-multi class, so its result depends on whether a run or autonomy is active. It prints the strict (protect) verdict, including `soften` (`warn` or `allow`) when `normal` mode relaxes it, and `workflow` for a `gh workflow run`. | no |
| `ready` | List cards that can be dispatched now. | yes |
| `route --size TIER [--asks N] --reason TEXT` | Change the tier after `start`, either way; the reason is logged in `route_log`. A 2.4 run uses `route --items N --reason TEXT` instead. | yes |
| `add TASK.json` | Add a card. A builder card may carry `size` (`tiny` or `medium`). On a size run a designer-planner plan card needs a large run or an owner request. On a 2.4 workflow route, the plan card must be accepted first. | yes |
| `dispatch TASK WORKER [--helper REASON]` | Reserve a card for a worker. A tiny builder card (and any builder card on a 2.4 inline route) needs `--helper REASON`. | yes |
| `inline TASK` | Reserve a card for the main coordinator. | yes |
| `review REVIEW.json [--token TOKEN] [--defer-out-of-scope REASON]` | Record the independent pre-PR review (`final: true`) or the fix re-review (`repair_check: true`). `--token` reports the review card, records the receipt and accepts the card in one step; it covers sibling final lens cards that review the same cards, and takes critic and repair_check receipts. `--defer-out-of-scope REASON` (with `--token`) records each out-of-scope item as deferred to a brief. An empty `cleared` means none; a mismatch refusal names each key with both values; a one-task receipt gets `task_findings` filled; out-of-scope items on a non-final receipt are kept as notes. | yes |
| `accept TASK [--ruling TEXT]` | Accept a card whose current evidence allows it. The refusal names the failing check. `--ruling TEXT` accepts a worker card whose only gap is an unmet criterion, with the coordinator's reason; it is never allowed for an inline card or a failing check. | yes |
| `gate [--again] [--timeout SECONDS] NAME -- COMMAND...` | Run a configured check; record the actual exit and log hashes. A passed gate on an unchanged artifact refuses a repeat unless `--again`. `--timeout` overrides `gate_timeout_seconds` for this run. Processes the check leaves running in its own process group are stopped when it exits; one that starts a new session or group is not tracked. | yes |
| `scan` | Run the configured secret scan; an unavailable optional scanner is reported, not passed. | yes |
| `permit REMOTE TARGET` | Create a release permit for an exact remote and target. It stays valid until the artifact changes or the session ends, and is not used up by a release. Refused while autonomy is active. | yes |
| `release REMOTE TARGET` | Run the release command named in policy under a current permit. Refused while autonomy is active. | yes |
| `finding add --review ID --kind finding\|out_of_scope --index N --disposition D --reason TEXT [--card ID]` | Record what happened to a review finding. | yes |
| `hold TASK --finding TEXT` | End the repair ladder: move a blocked repair chain to `held` and log the finding. | yes |
| `pr URL [--task ID]` | Record a pull request the run opened (an http(s) URL). With `gh`, it must be open, from this repository, based on the default or a run branch and headed by the local branch tip; it stores the head, the cards it carries and whether the head has a clean review. A rerun refreshes the entry. The run brief lists it under Needs you. | yes |
| `base TASK` | Print the branch the card's pull request targets: the default branch, or the head branch of its one open parent pull request. Two or more open parents exit 2 with `deferred: wait for pull request(s) N, M to merge`. Read-only. | no |
| `park TASK --reason TEXT` | Set a card aside at an approval boundary. | yes |
| `unpark TASK` | Return a parked card to the queue. | yes |
| `cancel TASK --reason TEXT` | Drop a queued or parked card that should never run. Refused while another card depends on it, a review covers it or it is in a repair chain; the drop is kept in the state's `cancelled` list. | yes |
| `interrupt` | Stop dispatch and continuation; late reports then fail. | yes |
| `finish` | Close the run after completion checks. A parked card blocks it. A refusal for leftover worktrees points to `worktrees`. A run that changed files needs a current final review even with no cards. | yes |

## Changes in 2.14.0

- New commands: `card`, `ledger`, `package`, `refusals [--last N]` and `worktrees`; new flags `wave --emit`, `report --accept`, `accept --ruling TEXT` and `review --defer-out-of-scope REASON`. The `board` key rides on card-moving command output. There is no `--lease @session` and no engine-owned worktree or `engine_worktrees` policy key: the engine only reads and reports worktrees.
- `start` returns `resume` per requeued card: the old worker and the saved report path.
- The autonomy ledger may carry `- Repairs: up to N per chain` (N from 1 to 3; absent means 1). A sibling repair with disjoint files no longer waits on a parent reservation.
- A worker's shell command carrying `orchestra.py ... --lease` is denied in every guard mode ([hooks](hooks.md#worker-limits-added-in-214)).
- Loosened: out-of-scope items on a non-final review receipt are kept as notes instead of refused.

## Changes in 2.11.0

- New: `base TASK`, `pr URL --task ID`, the policy keys `guard_mode` (`normal` or `protect`), `release_workflows` and `max_worktrees` (default 3), and the `UserPromptSubmit` approval hook. An unknown policy key is refused at `start`.
- Changed: `complete` waits for a verified pull request when the branch holds commits; every stop of an autonomous run keeps its report; the ledger's Merge, Push and Deletion lines changed, and a pre-2.11 ledger is refused at `arm` with a re-fill message; `arm` moves an earlier approval receipt aside.
- Run engine commands from the main checkout. A linked worktree resolves a different state directory, so the run is not found there.

## Changes in 2.7.1

- `start --recover --harness-session ID` gives the session that owns the run a fresh lease when it has lost its own (after compaction or a restart). Running cards keep their assignments; release permits are cleared. The id is in the SessionStart context.
- `cancel TASK --reason TEXT` drops a card that should never run.
- A worker that cannot do its card ends its report with a line `BLOCKED: reason`. The card is parked with that reason; no `SELF_REVIEW` is needed.
- The files already modified or untracked when a run starts are recorded as its baseline: the size warning and the review lenses count only what the run changes. Interpreter leftovers (`__pycache__`, `*.pyc`, tool caches, `.DS_Store`) are never evidence.
- Evidence stays strict: staging or committing after a review makes it stale. After committing, record the independent review again, then `accept` succeeds (the report needs unchanged files, not the same HEAD). Sparse-checkout paths and deletions are handled; interpreter leftovers are never evidence.
- `review` names the keys a report file is missing.
- `autonomy arm` records a digest of each remote's push URL, not the URL.

## Changes in 2.6.0

- Removed: the relaunch harness, `orchestra.py relaunch`, `autonomy arm --relaunch` and `autonomy settle`. A 2.5 state armed with `--relaunch` does not re-arm on `start`; re-arm in a live session.
- Changed: during an interactive run, a release action without a current permit asks the user instead of being denied.
- Changed: under autonomy the pull request push has one exact shape, and merged branches and worktrees may be cleaned up ([hook policy](hooks.md#autonomy-boundaries)).
- Changed: the Stop loop continues a turn only on actionable work: a ready or reported card, an open final finding, or a held chain owed its final review.
- Changed: `start --policy` validates the policy file, and CLI errors exit 2 with a JSON error.

## Changes in 2.0.0

- Removed: the three advisory commands for lane routing, review grouping and audit-axis selection. The coordinator now chooses lanes, groups reported cards and picks audit axes by hand, following the skill's coordination and audit-axes references. Calling a removed command exits with an unknown-command error.
- New: `artifact --tasks`, `autonomy arm|disarm|status`, `park`, `unpark` and `where`; `start --harness-session`.
- `status` and `board` no longer show the lease. `start` still prints it once. If it is lost, end the harness session (SessionEnd releases the run). For a run without a harness session, read the actor and lease from the run's `state.json` in the state directory and run `interrupt` with them. The lease is a consistency token, not a secret.
- The policy keys `reserved_ports` and `denied_tools` are gone. An old policy file that still carries them loads unchanged.
- `required_review_categories` may be narrowed to a non-empty subset of the seven final-review categories.
- A live run is invalidated only when a role or a mode is added, removed or renamed. Editing a skill or method file no longer invalidates it.

## Changes in 2.2.0

- New: `hold`, `brief`, `finding add|list`, `gate --again`, `autonomy arm --relaunch`, `autonomy settle` and `relaunch`. The 2.2 wave field and `supersede` are removed in 2.4; the relaunch harness, `--relaunch` and `settle` are removed in 2.6.
- Changed: autonomy has no pass or stall cap. Caps in a 2.1 ledger are recorded, not enforced. The run brief replaces the autonomy report.
- Changed: `gate` refuses boundary commands, and a repeat of a passed gate needs `--again`.
- Every 2.1 command keeps working. A run started under 2.1 loads under 2.2; see the README upgrade note before mixing versions on one run.

## Changes in 2.5.0

- New: `start --size`, `--asks`, `--owner-request`, `route --size`, `prepr`, the builder card `size` field, and the reviewer agent `code-reviewer-medium` (`Lens: combined`).
- Changed: a new run needs `--size`; `start --items` is refused. A 2.4 run keeps `route --items` and its item routes.
- New: `gate --timeout SECONDS` for one run. `report` replaces a reported card's report for the same worker and token until the card is accepted, a review lists it or a repair of it exists ("A review covers this report; route a change through a repair card").
- Changed: a builder report needs a nonempty `ARTIFACT:` line ("Builder report needs a nonempty ARTIFACT line").

## Changes in 2.4.0

- New: `start --items N`, `route`, `dispatch --helper REASON`, the `SELF_REVIEW:` builder line, `required_lenses` in `status`, and the policy keys `sensitive_paths` and `standards_min_lines` (default 200). Lenses: correctness always; security when a changed file matches `sensitive_paths`; standards and cleanup above `standards_min_lines` changed lines.
- Changed: only the pre-PR review and the fix re-review are recorded. Reviewers cite gate receipts (`current_gate_ids`) and do not rerun suites.
- Removed: waves, `supersede`, `task_findings`, the checkpoint review and the checkpoint reviewer.

## Scoped evidence

A task report binds to the covered cards' reserved files, the index, the status and the policy, not to HEAD. An uncommitted edit outside those files does not stale the evidence, and a commit that leaves those files alone does not either; an edit inside them does. `accept` compares the reported commit. A card with no reserved files gets the whole-repo artifact. Reviews, gates, release permits, release receipts and completion evidence always bind to the whole repository. The newest receipt per category that covers a card decides that category. If it is stale there is no current verdict; the engine never falls back to an older receipt.

## Repair and hold

The repair ladder has one repair rung: the Sonnet implementation card, then one Opus builder `repair` card, then one fix re-review (`repair_check: true`, `final: false`). `hold TASK --finding TEXT` ends it. It is refused unless TASK is a repair card in state `reported` with a current blocking verdict, or an implementation card whose current blocking verdict comes from a fix re-review. It moves the whole chain to `held`, stores the finding and appends a `held` line to `<state>/progress.md`. A held card reserves nothing and satisfies a dependency; `finish` still needs the final phase to clear it.

Accept a card before adding a repair that overlaps its evidence: dispatching a repair is refused while a reported card passes every `accept` check and shares reserved files with it ("Accept X first; a repair would make its evidence stale").

## Findings ledger and run brief

`finding add` records a disposition for one item of a recorded review: `--kind finding` takes `rejected`, `deferred`, `inline`, `card` or `brief`; `--kind out_of_scope` takes `inline`, `card` or `brief`. `--index` points at the item in that receipt, and `--card` names the card for `card`. A rejection never accepts a card: acceptance still needs a fresh independent verdict, which the repair-diff check gives. `finding list` prints every entry; `finding list --for-brief` prints a "Known findings" block (id, disposition, text, reason) to paste into a reviewer brief.

Every end of a run, armed or not, appends a run brief to `<state>/progress.md` and stores it as `last_brief`. `brief` prints it without a lease and changes nothing. Sections, in order: reason, deadline, passes and stalls; Needs you; Still failing / next phase; Held log; Final rounds; Notes; Deferred findings; Parked, Accepted and Failures. SessionStart shows its first 2000 characters. Every write to `progress.md` is a single append.

`gate --again` reruns a check that already passed on the same artifact with the same argv. A failed gate always reruns. A gate refuses every command the guard does not classify `allow`, and every boundary command (deletion, merge, branch deletion): those run only through the guarded hook.

## Autonomy

`autonomy arm` needs an active run. If `<state>/autonomy.md` does not exist, `arm` writes the ledger from a template, prints its path and refuses; fill it in and arm again. The ledger holds a goal, completion checks, a deadline and the fixed approval boundaries. `max_passes` and `max_stalls` are optional: a ledger that still carries them (as 2.1 ledgers do) records and shows them, and never enforces them. Any change to the ledger after `arm` stops the loop. While armed, the Stop hook keeps the run going until the deadline, completion, only parked cards, no live card, a tampered ledger, a stall with no worker running (`stalled`) or `disarm`. It continues a turn only when the coordinator can act now: a ready or reported card, an open final finding, a held chain owed its final review, or, with every card accepted, the final review, gates and pull request still owed. When only workers are running, the turn ends and the harness wakes the session as each one finishes. A continuation is never sent twice for the same progress signature: a continued turn that changes nothing ends and counts as a stall. No count of passes or stalls stops the run; the band shows "pass N". Ending the session ends autonomy when the run was started with `--harness-session`; arm only such a run. Each stop writes a run brief to `<state>/progress.md`, shown at the next session start.

The ledger holds exactly one `- Release:` line: `- Release: no release, permit or deploy.` by default, or `- Release: pre-authorized <remote> <target>`, which must equal `policy.release` (enabled, same remote and target) or `arm` refuses. The pre-authorization lets `permit` and `release` through for that exact remote and target only, and overrides the Push and Engine-gated actions lines for them. Autonomy may push its own branches, open, review and stack pull requests with `gh`, and clean up what it created; it never merges to the default branch. The owner types `approved`, and the merges run in the printed order ([approval flow](hooks.md#approval-and-the-merge-guard)). A push must be exactly `git push [-u|--set-upstream] <remote> <refspec>` with a configured remote name, a local branch as source and one destination branch other than the remote's default branch, `main` or `master` ([hook policy](hooks.md#autonomy-boundaries)). Cleanup covers the run's own branches and worktrees, provably merged branches and files inside a linked worktree. A ledger with the 2.5 line `- Push: no push to any branch.` is refused at `arm`. Everything else stays denied while autonomy is active: every other push and permit, release inside a multi-command line, other deletion, and local merges on the default branch. The coordinator parks the card and continues with others. `arm` reports the permission mode and a keep-awake reminder and changes neither. Credential entry is a prose rule only and is not detected.

