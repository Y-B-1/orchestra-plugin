Sentinel: orchestra/references/autonomy.md

# Autonomy

Orchestra waits at approval boundaries; it never pushes through them.

## Toggle

- `orchestra.py autonomy arm` needs an active run. With no `<state>/autonomy.md`, it writes the template and refuses: fill the ledger, then arm again. A placeholder left in it, or a field that does not parse, refuses and names the field. Otherwise it snapshots the ledger and prints the preconditions report. Read the report to the user, including the keep-awake step, which only the user can take.
- `orchestra.py autonomy disarm` ends the loop with the stop reason `disarmed`.
- `orchestra.py autonomy status` prints active, passes and max_passes, stalls and max_stalls, the deadline, parked cards and the last stop reason.
- `orchestra.py park TASK --reason TEXT` moves a queued, running or reported card to parked. `orchestra.py unpark TASK` returns it to queued. Both need the lease; `autonomy` takes none.

The ledger holds the goal, the completion checks (each a named gate command), the pass and stall limits, a deadline and the approval boundaries. Edit nothing in it after `arm`; a change stops the loop.

## Loop

Each Stop continues the loop while the caps, the deadline and the ledger hold and a card is ready, running or reported. A stall is a pass with no newly accepted card. When the loop ends, the stop reason and a morning report land in `<state>/progress.md`. A stop is final for that arm; the user re-arms.

## Approval boundaries

Hard and not configurable: release, merge, push, deletion, credential entry and any engine-gated action. Credential entry is prose only here, so never type one. At a boundary run `orchestra.py park TASK --reason TEXT` for that card and continue with the other cards. Parked work blocks `finish`. `unpark` is the user's morning step.

Gates run only through `orchestra.py gate NAME -- ...`; completion counts only receipts on the current artifact.
