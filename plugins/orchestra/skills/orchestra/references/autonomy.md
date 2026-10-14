Sentinel: orchestra/references/autonomy.md

# Autonomy

Orchestra waits at approval boundaries; it never pushes through them.

## Toggle

- `orchestra.py autonomy arm` needs an active run. With no `<state>/autonomy.md`, it writes the template and refuses: fill the ledger, then arm again. A placeholder left in it, or a field that does not parse, refuses and names the field. Otherwise it snapshots the ledger and prints the preconditions report. Read the report to the user, including the keep-awake step, which only the user can take. Arm only a run started with `start --harness-session`: ending that session releases the run and ends autonomy. A run started without it stays active and armed after the session ends, until `interrupt` or `disarm`.
- `orchestra.py autonomy disarm` ends the loop with the stop reason `disarmed`.
- `orchestra.py autonomy status` prints active, passes, stalls, the progress signature, the deadline, parked cards, `pull_requests` (whether the ledger allows a pull request push) and the last stop reason.
- `orchestra.py park TASK --reason TEXT` moves a queued, running or reported card to parked. `orchestra.py unpark TASK` returns it to queued. Both need the lease; `autonomy` takes none.

The ledger holds the goal, the completion checks (each a named gate command), a deadline and the approval boundaries. Pass and stall limits are optional: recorded, shown, never enforced. Edit nothing in it after `arm`; a change stops the loop.

## Loop

The Stop hook is the loop. When the turn ends, it continues only if there is work you can do now: a ready card to dispatch, a reported card to review or accept, an open final finding, a held chain owed its final review, or, with every card accepted, the final review, gates and pull request. Then it sends one line, `Autonomy pass N: ...`, and you act on it.

- Workers still running and nothing else to do: the turn ends quietly. The harness wakes the session when a background worker finishes. Do not poll, sleep or end a turn only to say you are waiting.
- The same prompt never repeats. A continued turn that changes nothing ends as a stall: with workers running it just ends; with none running the run stops `stalled`.

The stops are `deadline`, `complete`, `ledger-tampered`, `disarmed`, `stalled`, and `parked-only` or `no-ready-card` when nothing is live. No count stops the loop.

A card the pre-PR review blocks goes to its one repair, and a chain the fix re-review blocks is held (references/repair-rounds.md); the loop takes the next ready card. A held chain counts as live work, because the pre-PR review is still owed, unless a card is parked at a boundary: then no final receipt can be recorded and the run stops `parked-only`. `complete` needs every card accepted, no open finding, full coverage, the gates and the triage.

Every end of a run, armed or not, appends a run brief to `<state>/progress.md`; `orchestra.py brief` prints it and SessionStart shows its first 2000 characters. Needs you comes first, then Still failing, Held log and Final rounds. A stop is final for that arm; the user re-arms. Ending the session ends autonomy when the run was started with `--harness-session`.

## Context

Long runs rely on Claude Code's auto-compaction, set by the user, not by Orchestra. Recommend `"autoCompactWindow": 400000` in `~/.claude/settings.json`; Claude Code caps it at the model's window, so it has no effect on a smaller model. `progress.md` and `orchestra.py status` survive compaction; after one, reread them before the next dispatch.

## Approval boundaries

Hard by default; the ledger may pre-authorize the one configured release. Hold exactly one Release line: `- Release: no release, permit or deploy.` by default, or `- Release: pre-authorized <remote> <target>`, which must equal the configured policy release. The Release line overrides Push and Engine-gated actions for that remote and target only. Every other boundary stays hard and not configurable: merge, push to the default branch, deletion other than merged cleanup, credential entry and any other engine-gated action. Credential entry is prose only here, so never type one.

Pull requests are the way out. When every card is accepted: commit, run the final review and the completion gates on that commit, then push and open the pull request in the same turn; once `complete` holds, the loop sends no further turn. Push exactly `git push [-u] <remote> <refspec>` as its own command: a configured remote by name (no `push` or `pushurl` mapping), a local branch or `HEAD`/`@` as source, no env prefix, wrapper or other option, and one destination branch that is never a tag, the remote's default branch, `main`, `master` or the release target. `arm` asks each remote for its default branch; one that did not answer refuses the push. A ledger with the 2.5 line `- Push: no push to any branch.` allows no push. Then `gh pr create --base <default> --head <branch> --title TEXT --body-file FILE`. Never merge: the owner merges after the run. Record each with `orchestra.py pr URL`; the brief lists it under Needs you.

Cleanup is allowed only for branches provably merged into the default branch (ancestor, squash tree match or covering branch), such as work the owner merged after an earlier run: `git branch -d|-D <b>`, `git push <remote> --delete <b>`, `git worktree remove <path>` (no `--force`) for a linked worktree of this repository whose branch passes the same check, never the session's own directory or the main worktree, and `git worktree prune`. Each runs alone: no chaining, quoting, wrappers or `-C`. `rm` and every other deletion stay denied.

At a boundary run `orchestra.py park TASK --reason TEXT` for that card and continue with the other cards. Parked work blocks `finish`. Held work blocks no other card; the owner must settle it before `finish`. `unpark` is the user's morning step. Without pre-authorization an armed run adds no release card; the brief says "ready to release" (references/finishing.md).

Gates run only through `orchestra.py gate NAME -- ...`; completion counts only receipts on the current artifact.
