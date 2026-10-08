Sentinel: orchestra/references/autonomy.md

# Autonomy

Orchestra waits at approval boundaries; it never pushes through them.

## Toggle

- `orchestra.py autonomy arm` needs an active run. With no `<state>/autonomy.md`, it writes the template and refuses: fill the ledger, then arm again. A placeholder left in it, or a field that does not parse, refuses and names the field. Otherwise it snapshots the ledger and prints the preconditions report. Read the report to the user, including the keep-awake step, which only the user can take.
- `orchestra.py autonomy disarm` ends the loop with the stop reason `disarmed`.
- `orchestra.py autonomy status` prints active, passes, stalls, the progress signature, the deadline, parked cards and the last stop reason.
- `orchestra.py park TASK --reason TEXT` moves a queued, running or reported card to parked. `orchestra.py unpark TASK` returns it to queued. Both need the lease; `autonomy` takes none.

The ledger holds the goal, the completion checks (each a named gate command), a deadline and the approval boundaries. Pass and stall limits are optional: recorded, shown, never enforced. Edit nothing in it after `arm`; a change stops the loop.

## Loop

Each Stop continues the loop while the deadline and the ledger hold and work remains. No count stops it. The stops are `deadline`, `complete`, `ledger-tampered`, `disarmed`, and `parked-only` or `no-ready-card` when nothing is live. A stall is a pass that leaves the progress signature unchanged; it is counted and reported, never a stop.

A card the pre-PR review blocks goes to its one repair, and a chain the fix re-review blocks is held (references/repair-rounds.md); the loop takes the next ready card. A held chain counts as live work, because the pre-PR review is still owed, unless a card is parked at a boundary: then no final receipt can be recorded and the run stops `parked-only`. `complete` needs every card accepted, no open finding, full coverage, the gates and the triage.

Every end of a run, armed or not, appends a run brief to `<state>/progress.md`; `orchestra.py brief` prints it and SessionStart shows its first 2000 characters. Needs you comes first, then Still failing, Held log and Final rounds. A stop is final for that arm; the user re-arms.

## Approval boundaries

Hard by default; the ledger may pre-authorize the one configured release. Hold exactly one Release line: `- Release: no release, permit or deploy.` by default, or `- Release: pre-authorized <remote> <target>`, which must equal the configured policy release. The Release line overrides Push and Engine-gated actions for that remote and target only. Every other boundary stays hard and not configurable: merge, push, deletion, credential entry and any other engine-gated action. Credential entry is prose only here, so never type one.

At a boundary run `orchestra.py park TASK --reason TEXT` for that card and continue with the other cards. Parked work blocks `finish`. Held work blocks no other card; the owner must settle it before `finish`. `unpark` is the user's morning step. Without pre-authorization an armed run adds no release card; the brief says "ready to release" (references/finishing.md).

Gates run only through `orchestra.py gate NAME -- ...`; completion counts only receipts on the current artifact.

## Relaunch

`orchestra.py autonomy arm --relaunch` keeps autonomy armed when a session ends, so each pass starts with a fresh context. The boundaries still apply between passes. The user ends the interactive session, then runs `orchestra.py relaunch --permission-mode MODE [--model ID]` in a terminal. It runs one `claude -p` pass at a time and ends that pass's session when it exits. After a stalled pass it waits longer, up to 15 minutes, and never stops for stalls. `orchestra.py autonomy settle` checks the stop conditions between passes without counting one.

A pass reads this skill, runs `orchestra.py start`, reads `progress.md` and `status`, dispatches ready cards, parks at boundaries, and ends at the context ceiling after recording state. It makes foreground Agent calls only; `-p` kills background work when it exits. Exit codes: 0 complete, 3 idle, 4 deadline, 5 disarmed, tampered or not armed, 2 usage or an active session, 130 interrupted.
