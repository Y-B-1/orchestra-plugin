Sentinel: orchestra/references/autonomy.md

# Autonomy

Overnight mode runs only on an explicit user request. Orchestra waits at approval boundaries; it never pushes through them.

## Toggle

`orchestra.py autonomy arm|disarm|status` is the one entry. `arm` needs an active run. With no `<state>/autonomy.md`, it writes the template and refuses: fill the ledger, then arm again. The ledger holds the goal, the completion checks (each a named gate command), the pass and stall limits, a deadline and the approval boundaries. Edit nothing in it after `arm`; a change stops the loop. `arm` prints the preconditions report. Read it to the user, including the keep-awake step, which only the user can take.

## Loop

Each Stop continues the loop while the caps, the deadline and the ledger hold and a card is ready, running or reported. A stall is a pass with no newly accepted card. When the loop ends, the stop reason and a morning report land in `<state>/progress.md`. A stop is final for that arm; the user re-arms.

## Approval boundaries

Hard and not configurable: release, merge, push, deletion, credential entry and any engine-gated action. Credential entry is prose only here, so never type one. At a boundary run `orchestra.py park TASK --reason TEXT` for that card and continue with the other cards. Parked work blocks `finish`. `unpark` is the user's morning step.

Gates run only through `orchestra.py gate NAME -- ...`; completion counts only receipts on the current artifact.
