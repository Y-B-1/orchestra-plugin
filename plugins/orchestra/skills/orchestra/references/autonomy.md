Sentinel: orchestra/references/autonomy.md

# Autonomy

Orchestra waits at approval boundaries; it never pushes through them.

## Toggle

- `orchestra.py autonomy arm` needs an active run. With no `<state>/autonomy.md`, it writes the template and refuses: fill the ledger, then arm again. A placeholder left in it, or a field that does not parse, refuses and names the field. Otherwise it snapshots the ledger and prints the preconditions report. Read the report to the user, including the keep-awake step, which only the user can take. Arm only a run started with `start --harness-session`: ending that session releases the run and ends autonomy. A run started without it stays active and armed after the session ends, until `interrupt` or `disarm`.
- `orchestra.py autonomy disarm` ends the loop with the stop reason `disarmed`.
- `orchestra.py autonomy status` prints active, passes, stalls, the progress signature, the deadline, parked cards, `pull_requests` (whether the ledger allows a pull request push) and the last stop reason.
- `orchestra.py park TASK --reason TEXT` moves a queued, running or reported card to parked. `orchestra.py unpark TASK` returns it to queued. Both need the lease; `autonomy` takes none. A card only the owner can unblock (a secret, a code, an account action, an approval boundary) is parked with a reason that starts `needs-owner:`; any other parked card is yours to unpark.

The ledger holds the goal, the completion checks (each a named gate command), a deadline and the approval boundaries. Pass and stall limits are optional: recorded, shown, never enforced. Edit nothing in it after `arm`; a change stops the loop.

## Loop

The Stop hook is the loop, a fixed goal like `/goal`: the run goes on until the ledger is done or only the owner can unblock it. When the turn ends, it continues if there is work you can do now: a ready card to dispatch, a reported card to review or accept, an open final finding, a held chain owed its final review, or, with every card accepted, the final review, gates and pull request. Then it sends one line, `Autonomy pass N: ...`, and you act on it.

- Workers or your inline card still running and nothing else to do: the turn ends quietly. The harness wakes the session when background work finishes. Do not poll, sleep or end a turn only to say you are waiting.
- The same prompt never repeats. When nothing is live, an idle board, a failing gate, an unchanged pass, a silent worker or an unpublished branch each gets a nudge: re-plan against the ledger, add a repair card, name what is missing, or fix the exact push error. A worker silent past the limit is parked `lost-worker` on the repeat.
- Parked cards without `needs-owner:` get a nudge to unpark. The same unchanged board three times parks every unfinished card `needs-owner:escalated` and stops the run.

The stops are `deadline`, `complete`, `ledger-tampered`, `disarmed`, `stale` (a loop nobody drives, stopped from another session), `interrupted`, `ended`, `finished`, `parked-only` (every parked card needs the owner) and `needs-owner:escalated`. Each keeps the morning report. No count stops the loop.

A card the pre-PR review blocks goes to its one repair, and a chain the fix re-review blocks is held (references/repair-rounds.md); the loop takes the next ready card. A held chain counts as live work, because the pre-PR review is still owed, unless a card is parked at a boundary: then no final receipt can be recorded and, once every parked reason starts `needs-owner:`, the run stops `parked-only`. `complete` needs every card accepted, no open finding, full coverage, the gates, the triage and, when the branch holds commits, a verified pull request for the current head (the nudges to publish it carry the push error to fix).

Every end of a run, armed or not, appends a run brief to `<state>/progress.md`; `orchestra.py brief` prints it and SessionStart shows its first 2000 characters. Needs you comes first, then Still failing, Held log and Final rounds. A stop is final for that arm; the user re-arms. Ending the session ends autonomy when the run was started with `--harness-session`.

## Context

Long runs rely on Claude Code's auto-compaction, set by the user, not by Orchestra. Recommend `"autoCompactWindow": 400000` in `~/.claude/settings.json`; Claude Code caps it at the model's window, so it has no effect on a smaller model. `progress.md` and `orchestra.py status` survive compaction; after one, reread them before the next dispatch.

## Approval boundaries

Hold exactly one Release line: `- Release: no release, permit or deploy.` by default, or `- Release: pre-authorized <remote> <target>`, which must equal the configured policy release and overrides Push and Engine-gated actions for that remote and target only. The Merge, Push and Deletion lines are fixed template text; an older ledger is refused at `arm` with a re-fill message. Credential entry is prose only here, so never type one.

The run pushes its own branches and opens, reviews and stacks pull requests; it never merges to the default branch, releases, or deletes the default branch or tags. The owner's `approved` turns its pull requests into merges: references/approval.md.

At a boundary run `orchestra.py park TASK --reason 'needs-owner: TEXT'` for that card and continue with the other cards. Parked work blocks `finish`. Held work blocks no other card; the owner must settle it before `finish`. `unpark` is the user's morning step. Without pre-authorization an armed run adds no release card; the brief says "ready to release" (references/finishing.md).

Gates run only through `orchestra.py gate NAME -- ...`; completion counts only receipts on the current artifact.
