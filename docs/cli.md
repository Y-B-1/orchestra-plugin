# Portable CLI

The maintained command guide and the task/review schemas live in the package [CLI reference](../plugins/orchestra/skills/orchestra/references/cli.md). The package carries that guide after installation. This page lists every command.

Run `python3 plugins/orchestra/scripts/orchestra.py [--repo REPO] [--state STATE] [--actor ACTOR] [--lease LEASE] COMMAND`. Each command prints a JSON receipt. `--actor` and `--lease` are consistency checks, not authentication. The Lease column says whether the command needs `--lease` from `start`.

| Command | Purpose | Lease |
| --- | --- | --- |
| `start [--policy FILE] [--harness-session ID] [--new-run]` | Start a run and print the lease once. With `--harness-session`, ending that Claude Code session releases the run. | no |
| `where` | Print the repository, the state directory and whether `standing-orders.md` exists. | no |
| `status` | Print cards and session state. Never prints a lease. | no |
| `board` | Group card ids by role and state. | no |
| `artifact [--tasks ID[,ID]]` | Print the whole-repo artifact, or with `--tasks` the artifact scoped to those cards' reserved files plus HEAD. | no |
| `report WORKER TOKEN FILE` | Record a worker's result file against its assignment token. | no |
| `autonomy arm\|disarm\|status` | Arm, disarm or inspect the autonomous loop. | no |
| `classify "SHELL COMMAND"` | Print the guard verdict for a command string without running it. | no |
| `install-profiles [--codex-home DIR]` | Install namespaced Codex worker profiles. | no |
| `uninstall-profiles [--codex-home DIR]` | Remove only the profiles the installer recorded. | no |
| `ready` | List cards that can be dispatched now. | yes |
| `add TASK.json` | Add a card. | yes |
| `dispatch TASK WORKER` | Reserve a card for a worker. | yes |
| `inline TASK` | Reserve a card for the main coordinator. | yes |
| `review REVIEW.json` | Record an independent structured review. | yes |
| `accept TASK` | Accept a card whose current evidence allows it. | yes |
| `gate NAME -- COMMAND...` | Run a configured check; record the actual exit and log hashes. | yes |
| `scan` | Run the configured secret scan; an unavailable optional scanner is reported, not passed. | yes |
| `permit REMOTE TARGET` | Create a release permit for an exact remote and target. Refused while autonomy is active. | yes |
| `release REMOTE TARGET` | Run the release command named in policy under a current permit. Refused while autonomy is active. | yes |
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

## Scoped evidence

A task report and a checkpoint (non-final) review bind to the covered cards' reserved files plus HEAD. An uncommitted edit outside those files does not stale the evidence; an edit inside them, or any new commit, does. A card with no reserved files gets the whole-repo artifact, and a checkpoint review that covers such a card uses the whole-repo artifact too. Final reviews, gates, release permits, release receipts and completion evidence always bind to the whole repository. The newest receipt per category that covers a card decides that category. If it is stale there is no current verdict; the engine never falls back to an older receipt.

## Autonomy

`autonomy arm` needs an active run. If `<state>/autonomy.md` does not exist, `arm` writes the ledger from a template, prints its path and refuses; fill it in and arm again. The ledger holds a goal, completion checks, `max_passes` (1 to 20), `max_stalls` (1 to 2), a deadline and the fixed approval boundaries. Any change to the ledger after `arm` stops the loop. While armed, the Stop hook keeps the run going until a pass or stall cap, the deadline, completion, only parked cards, no ready card or a tampered ledger. Each stop writes a morning report to `<state>/progress.md`, shown at the next session start. While autonomy is active the guard denies release-class commands, every push, deletions and local merges on the default branch, and `permit` and `release` refuse; the coordinator parks the card and continues with others. `arm` reports the permission mode and a keep-awake reminder and changes neither. Credential entry is a prose rule only and is not detected.
