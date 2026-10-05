# Portable CLI

The maintained command guide and the task/review schemas live in the package [CLI reference](../plugins/orchestra/skills/orchestra/references/cli.md). The package carries that guide after installation. This page lists every command.

Run `python3 plugins/orchestra/scripts/orchestra.py [--repo REPO] [--state STATE] [--actor ACTOR] [--lease LEASE] COMMAND`. Each command prints a JSON receipt. `--actor` and `--lease` are consistency checks, not authentication. The Lease column says whether the command needs `--lease` from `start`.

| Command | Purpose | Lease |
| --- | --- | --- |
| `start [--policy FILE] [--harness-session ID] [--new-run]` | Start a run and print the lease once. With `--harness-session`, ending that Claude Code session releases the run. | no |
| `where` | Print the repository, the state directory and whether `standing-orders.md` exists. | no |
| `status` | Print cards, session state and the waves in first-add order. Never prints a lease. | no |
| `board` | Group card ids by role and state. | no |
| `artifact [--tasks ID[,ID]]` | Print the whole-repo artifact, or with `--tasks` the artifact scoped to those cards' reserved files plus HEAD. | no |
| `report WORKER TOKEN FILE` | Record a worker's result file against its assignment token. | no |
| `autonomy arm [--relaunch]\|disarm\|status\|settle` | Arm, disarm or inspect the autonomous loop. `arm --relaunch` keeps autonomy armed between sessions; `settle` checks the stop conditions without counting a pass. | no |
| `brief` | Print the newest run brief. Read-only. | no |
| `finding list [--for-brief]` | List the findings ledger, or render a "Known findings" block for reviewer briefs. | no |
| `relaunch --permission-mode MODE [--model ID] [--launcher ARGV...]` | Run fresh `claude -p` passes from a terminal until a stop. `--launcher ARGV...` must come last; every later word goes to the launcher. | no |
| `classify "SHELL COMMAND"` | Print the guard verdict for a command string without running it. | no |
| `ready` | List cards that can be dispatched now. | yes |
| `add TASK.json` | Add a card. A builder implementation card may carry `"wave": "W"`; a review card may name `"wave:W"` in `review_of`. | yes |
| `dispatch TASK WORKER` | Reserve a card for a worker. | yes |
| `inline TASK` | Reserve a card for the main coordinator. | yes |
| `review REVIEW.json` | Record an independent structured review. | yes |
| `accept TASK` | Accept a card whose current evidence allows it. | yes |
| `gate [--again] NAME -- COMMAND...` | Run a configured check; record the actual exit and log hashes. A passed gate on an unchanged artifact refuses a repeat unless `--again`. | yes |
| `scan` | Run the configured secret scan; an unavailable optional scanner is reported, not passed. | yes |
| `permit REMOTE TARGET` | Create a release permit for an exact remote and target. Refused while autonomy is active. | yes |
| `release REMOTE TARGET` | Run the release command named in policy under a current permit. Refused while autonomy is active. | yes |
| `finding add --review ID --kind finding\|out_of_scope --index N --disposition D --reason TEXT [--card ID]` | Record what happened to a review finding. | yes |
| `hold TASK --finding TEXT` | End the repair ladder: move a blocked repair chain to `held` and log the finding. | yes |
| `supersede TASK` | Accept an unstarted review that newer accepted reviews cover in full. | yes |
| `park TASK --reason TEXT` | Set a card aside at an approval boundary. | yes |
| `unpark TASK` | Return a parked card to the queue. | yes |
| `interrupt` | Stop dispatch and continuation; late reports then fail. | yes |
| `finish` | Close the run after completion checks. A parked card blocks it. | yes |

## Changes in 2.0.0

- Removed: the three advisory commands for lane routing, review grouping and audit-axis selection. The coordinator now chooses lanes, groups reported cards and picks audit axes by hand, following the skill's coordination and audit-axes references. Calling a removed command exits with an unknown-command error.
- New: `artifact --tasks`, `autonomy arm|disarm|status`, `park`, `unpark` and `where`; `start --harness-session`.
- `status` and `board` no longer show the lease. `start` still prints it once. If it is lost, end the harness session (SessionEnd releases the run). For a run without a harness session, read the actor and lease from the run's `state.json` in the state directory and run `interrupt` with them. The lease is a consistency token, not a secret.
- The policy keys `reserved_ports` and `denied_tools` are gone. An old policy file that still carries them loads unchanged.
- `required_review_categories` may be narrowed to a non-empty subset of the seven final-review categories.
- A live run is invalidated only when a role or a mode is added, removed or renamed. Editing a skill or method file no longer invalidates it.

## Changes in 2.2.0

- New: `hold`, `supersede`, `brief`, `finding add|list`, `gate --again`, `autonomy arm --relaunch`, `autonomy settle`, `relaunch`, the `wave` card field and `"wave:W"` in `review_of`, and `waves` in `status`.
- Changed: autonomy has no pass or stall cap. Caps in a 2.1 ledger are recorded, not enforced. The run brief replaces the autonomy report.
- Changed: `gate` refuses boundary commands, and a repeat of a passed gate needs `--again`.
- Every 2.1 command keeps working. A run started under 2.1 loads under 2.2; see the README upgrade note before mixing versions on one run.

## Scoped evidence

A task report and a checkpoint (non-final) review bind to the covered cards' reserved files plus HEAD. An uncommitted edit outside those files does not stale the evidence; an edit inside them, or any new commit, does. A card with no reserved files gets the whole-repo artifact, and a checkpoint review that covers such a card uses the whole-repo artifact too. Final reviews, gates, release permits, release receipts and completion evidence always bind to the whole repository. The newest receipt per category that covers a card decides that category. If it is stale there is no current verdict; the engine never falls back to an older receipt.

## Waves, repair and hold

A wave is a label on builder implementation cards. `add` refuses `wave` on any other card, and refuses a card for wave W once a review of W exists ("Wave W already has a review; start a new wave"). A review card names `"review_of": ["wave:W"]`; `add` resolves it to the ids of every card labelled W and stores plain ids. `status` lists `waves` in the order each label first appeared, each with its card ids and `next_depends`, whether a card of the next wave depends on it through `dependencies`, `files` or `inputs`. A wave-boundary gate is due only when `next_depends` is true.

A wave review is a checkpoint review. Its report may carry `task_findings`, which maps each covered card to its own blocking findings: an empty list or a missing key means clean for that card. Without `task_findings`, every covered card gets the whole `findings` list, as in 2.1. A repair-diff check carries `repair_check: true`.

The repair ladder has one repair rung: the Sonnet implementation card, then one Opus builder `repair` card. `hold TASK --finding TEXT` ends it. It is refused unless TASK is a repair card in state `reported` with a current blocking verdict, or an implementation card whose current blocking verdict comes from a repair-diff check. It moves the whole chain to `held`, stores the finding and appends a `held` line to `<state>/progress.md`. A held card reserves nothing and satisfies a dependency, so a later wave still runs; `finish` still needs the final phase to clear it. `supersede TASK` accepts a queued or parked review card that was never dispatched, when every id it covers is covered by a newer accepted review; otherwise it is refused and names the uncovered id.

Accept a card before adding a repair that overlaps its evidence: dispatching a repair is refused while a reported card passes every `accept` check and shares reserved files with it ("Accept X first; a repair would make its evidence stale").

## Findings ledger and run brief

`finding add` records a disposition for one item of a recorded review: `--kind finding` takes `rejected`, `deferred`, `inline`, `card` or `brief`; `--kind out_of_scope` takes `inline`, `card` or `brief`. `--index` points at the item in that receipt, and `--card` names the card for `card`. A rejection never accepts a card: acceptance still needs a fresh independent verdict, which the repair-diff check gives. `finding list` prints every entry; `finding list --for-brief` prints a "Known findings" block (id, disposition, text, reason) to paste into a reviewer brief.

Every end of a run, armed or not, appends a run brief to `<state>/progress.md` and stores it as `last_brief`. `brief` prints it without a lease and changes nothing. Sections, in order: reason, deadline, passes and stalls; Needs you; Still failing / next phase; Held log; Final rounds; Notes; Deferred findings; Parked, Accepted and Failures. SessionStart shows its first 2000 characters. Every write to `progress.md` is a single append.

`gate --again` reruns a check that already passed on the same artifact with the same argv. A failed gate always reruns. A gate refuses every command the guard does not classify `allow`, and every boundary command (deletion, merge, branch deletion): those run only through the guarded hook.

## Autonomy

`autonomy arm` needs an active run. If `<state>/autonomy.md` does not exist, `arm` writes the ledger from a template, prints its path and refuses; fill it in and arm again. The ledger holds a goal, completion checks, a deadline and the fixed approval boundaries. `max_passes` and `max_stalls` are optional: a ledger that still carries them (as 2.1 ledgers do) records and shows them, and never enforces them. Any change to the ledger after `arm` stops the loop. While armed, the Stop hook keeps the run going until the deadline, completion, only parked cards, no ready card, a tampered ledger or `disarm`. No count of passes or stalls stops it. A stall is a pass that leaves the progress signature unchanged; it is counted and reported, and the band shows "pass N". Each stop writes a run brief to `<state>/progress.md`, shown at the next session start.

The ledger holds exactly one `- Release:` line: `- Release: no release, permit or deploy.` by default, or `- Release: pre-authorized <remote> <target>`, which must equal `policy.release` (enabled, same remote and target) or `arm` refuses. The pre-authorization lets `permit` and `release` through for that exact remote and target only, and overrides the Push and Engine-gated actions lines for them. Everything else stays denied while autonomy is active: every other push and permit, release inside a multi-command line, deletions and local merges on the default branch. The coordinator parks the card and continues with others. `arm` reports the permission mode and a keep-awake reminder and changes neither. Credential entry is a prose rule only and is not detected.

`arm --relaunch` also sets `relaunch`: ending a session (`interrupt`, harness end) leaves autonomy armed, `finish` stops it with `complete`, and the guard applies the boundaries even with no active session. `autonomy settle` is lease-free; it evaluates the stop conditions without counting a pass, stops autonomy and writes the brief when one holds, and prints `{armed, stopped, reason, signature, passes, stalls}`. `autonomy status` prints the signature too.

## Relaunch

`relaunch --permission-mode MODE [--model ID] [--launcher ARGV...]` runs from the repository in the user's terminal and replaces the downstream shell harness. `--permission-mode` is required and has no default. It needs an active run, autonomy armed with `--relaunch` and no active session; otherwise it prints "End the interactive session first" and exits 2. It calls `settle`, launches one `claude -p` pass with the shipped pass prompt, waits for it to exit, ends that pass's session when its nonce matches, records `{pass, signature, stalled_streak}` in `<state>/relaunch/harness.json` and repeats. Pass output goes to `<state>/relaunch/pass-N.log`. After a stalled pass it waits `min(60 * 2^(streak-1), 900)` seconds and never stops for stalls; the deadline is the only limit. `--launcher ARGV...` replaces the `claude` command and receives the prompt on stdin; it must come last, and every later word goes to the launcher. Each pass gets `ORCHESTRA_RELAUNCH_PASS` and `ORCHESTRA_STATE_DIR` in its environment. SIGINT or SIGTERM disarms first, forwards the signal to the pass, waits up to 10 seconds for it and exits 130.

Exit codes: 0 `complete`; 3 idle (`parked-only`, `no-ready-card`); 4 `deadline`; 5 `disarmed` or `ledger-tampered`; 2 usage or precondition (not armed with `--relaunch`, an active session, or a session not started by this pass); 127 launcher not found; 130 interrupted. If autonomy already stopped, `relaunch` exits with that stop's code.

| Downstream option | In 2.2 |
| --- | --- |
| `-n` max passes, `-N` stall streak | Removed; stall count, report and back-off; the deadline is the only limit |
| `-p` prompt file | The shipped pass prompt; no per-run override |
| `-m` model | `--model`, unset by default |
| `--permission-mode` default | Required, no default |
| `--` alternative CLI | `--launcher` |
| `-v` verify | The ledger's completion checks on the current artifact |
