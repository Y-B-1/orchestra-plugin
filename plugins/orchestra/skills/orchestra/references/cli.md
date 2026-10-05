# Portable CLI and evidence

Use Python 3.11+ with `plugins/orchestra/scripts/orchestra.py`. Common options precede the command: `--repo`, `--state`, `--actor`, `--lease`. Paths with spaces are supported. Actor/lease values are consistency checks, not authentication.

1. Inspect the target repository and applicable project rules.
2. Run `--repo /path/to/project start --policy policy.json --harness-session SESSION_ID`. Take SESSION_ID from the SessionStart context on Claude Code; ending that harness session then releases the run. Save the returned lease: `start` prints it once and `status` never does. Policy and run data stay outside the application. `where` prints the repository, the state directory and whether `standing-orders.md` exists, without the lease.
3. Add bounded cards with `--lease LEASE add task.json`; run `ready`, then choose `dispatch TASK WORKER` or `inline TASK`. A builder implementation card may carry `"wave": "W"` to join wave W; `status` lists the waves.
4. Start the actual native worker only after reserving the card. Give the full brief and selected native profile. Return a startup receipt naming actual cwd/root/HEAD. A reservation token alone does not prove a worker is running.
5. Run `report WORKER TOKEN result.txt`. Inspect results and group returned builders by hand.
6. Record independent structured reviews with `--lease LEASE review review.json`; accept covered cards with `accept TASK`.
7. Integrate changes, make tracked memory edits, freeze the candidate, run configured `gate NAME -- COMMAND...` checks and final review. Dispatch one independent critic per needed axis (`spec`, `standards`, `ledger`, and `surface` by judgment).
8. For a configured authorized release, run `permit REMOTE TARGET`, then `release REMOTE TARGET`. Inspect the remote and running system separately. Run `finish` only after completion checks. For another run, use `start --new-run` after the previous session closes.

Read-only evidence cards need coordinator inspection before acceptance; builder cards need current independent review by default. Use `review_required: true` for other consequential artifacts. Review groups cover several task IDs in one report. A review card may name `"wave:W"` in `review_of`: `add` resolves it to every card labelled W and stores plain ids, and a card added to wave W after its review exists is refused. A wave review report may carry `task_findings`, a map from each covered id to that card's blocking findings; a missing key or an empty list is clean for that card, and without the map every covered card gets the whole `findings` list. A repair-diff check carries `repair_check: true`. Tiny reads do not need a run. A changed artifact invalidates old final evidence, including documentation edits.

`inline TASK` reserves the same card for the main actor and returns an assignment token; it does not start a child agent. Run `report MAIN_ACTOR TOKEN result.txt` when done. Disjoint worker cards can run concurrently. Inline work cannot replace code-reviewer or critic assignments, bypass ownership, or accept unreviewed implementation.

## Task example

```json
{
  "id": "B1", "role": "builder", "mode": "implementation",
  "inputs": ["approved settings spec"], "acceptance": ["invalid values show an error"],
  "files": ["src/settings.py"], "resources": ["preview:5101"], "dependencies": [],
  "outcome": "settings-validation", "review_group": "settings-validation"
}
```

Owned directories cover descendants; use explicit paths, never globs. A shared Git index, build directory, port, fixture or database needs a resource reservation even when files differ. Parallel writers use separate worktrees; the dispatcher owns their creation, integration and preservation. Mark consequential foundations `foundational: true`; their checkpoint precedes dependent dispatch.

A code-reviewer or critic card can name `review_of: ["B1"]` to start when B1 reports. Do not also put B1 in accepted `dependencies`. Review-card files describe read scope; avoid the target's exclusive resources. Review_of grants no permission to edit inspected files. Reported workers free running capacity but retain reservations until acceptance.

A repair card names `repair_of` and needs an intact current BLOCKED review of that builder. It replaces an accepted dependency on the original. Creation suspends the original chain as repairing and transfers its reservations to the queued repair. Report the repair, obtain fresh independent review of repair and ancestor IDs, accept the repair, then accept ancestors. Old reports remain history; old CLEAN coverage cannot approve repaired work. The ladder has one repair rung. Accept every acceptable overlapping card before adding a repair, since a repair lands in the shared tree and makes its evidence stale. `hold TASK --finding TEXT` (lease) ends the ladder for a repair card, or an implementation card blocked by a repair-diff check, that still has a current blocking verdict: it moves the whole chain to `held`, logs the finding in `progress.md`, reserves nothing and lets later waves run, and the final phase must clear it before `finish`. `supersede TASK` (lease) accepts a queued or parked, never dispatched review card whose every covered id a newer accepted review also covers.

Group returned low-risk builder cards by hand when they share an explicit group/outcome or input, and isolate consequential foundations. Check group coherence and context size before dispatch. Avoid a new reviewer for each micro-ticket.

## Review schema

Write the report outside the application. Obtain the exact artifact and enumerate covered task IDs: `artifact --tasks ID[,ID]` for a checkpoint review (scoped to the covered cards' reserved files plus HEAD; a card with no reserved files gets the whole repo), plain `artifact` for a final review. The report uses:

```json
{
  "reviewer": "independent-worker-id",
  "categories": ["requirements", "correctness", "security", "tests", "architecture", "standards", "cleanup"],
  "tasks": ["B1"], "findings": [], "verdict": "CLEAN", "final": true,
  "summary": "Describe the inspected code, exercised failures, coverage and remaining gaps.",
  "artifact": {"copy": "replace this example with the complete artifact command output"}
}
```

This example is a schema explanation, not a valid approval receipt. Final reports enumerate every pre-release card, including read-only review cards. They may omit the one terminal release card. Findings make the verdict BLOCKED; the coordinator checks findings against source before repair. The newest applicable current verdict governs each category. Missing or altered governing evidence blocks; it never restores an older approval. A newly checked intact replacement can supersede it. Report metadata, verdict, current artifact and stored file hashes must agree. Semantic truth remains independent human/model judgment; a JSON label cannot prove correctness.

## Policy

Copy `config/policy.default.json` to an external project policy. Configure `required_checks` as `{name, argv}` objects. A release also needs `release.enabled`, an explicit `authorization` statement, exact `remote`, `target` and `argv`. Required scanners use `secret_scan.required: true` and exact `argv`; `scan` records unavailable optional scanners rather than green evidence. Set `required_review_categories` to a non-empty subset of the seven categories to narrow what a final review must cover; the default keeps all seven. Gate commands are bounded and reject recognized destructive/release operations.

Add at most one operator card with `mode: release`. Dispatch it before `permit`; its ordinary dependencies must already be accepted. Release checks every pre-release card and final evidence, excluding only that terminal operation. After execution, inspect the release receipt and remote, report and accept the operator card, then run `finish`. Release validates the active actor/lease, checks known Git destinations against policy, and records actual exit/log evidence. A known Git push must use exactly four argv elements: the engine’s resolved Git executable, push, the explicit remote and one refspec. Wrappers, global options and push options are rejected. Its source must resolve to the reviewed full HEAD, both when permitting and immediately before execution. A timeout stops ordinary process-group descendants; deliberately detached processes are outside that guarantee.

For unattended continuation, explicitly create a ledger with completion criteria, scope and authority. Run `autonomy arm` (no lease; ledger at `<state>/autonomy.md`, written from a template when missing), `autonomy disarm` or `autonomy status`. No pass or stall count stops the loop; the deadline is the limit. `max_passes` and `max_stalls` are optional, and a 2.1 ledger that carries them has them recorded, not enforced. The ledger's one `- Release:` line is `no release, permit or deploy` or `pre-authorized <remote> <target>`, which must equal the policy release. `autonomy arm --relaunch` keeps autonomy armed between sessions; `autonomy settle` (no lease) checks the stop conditions without counting a pass and prints `{armed, stopped, reason, signature, passes, stalls}`. Run `park TASK --reason TEXT` and `unpark TASK` under the active lease: a parked card holds no capacity or reservation and blocks `finish`. Stop never arms itself. Use `interrupt` on cancellation; late reports fail. The main must also stop actual workers through the harness. Completed evidence and prior policies stay in external history; the package never adopts unrelated old runs automatically.

Outside an armed run, the guard allows a non-force push of one branch or tag, `gh pr merge` and `gh release create` without `permit`. Inside an armed run they need the engine permit, and while autonomy is active they are denied.

## Gates, findings, briefs and relaunch

`gate [--again] NAME -- COMMAND...` refuses a repeat of a passed gate with the same argv on an unchanged artifact unless `--again` is given; a failed gate always reruns. It refuses boundary commands, which run only through the guarded hook.

`finding add --review ID --kind finding|out_of_scope --index N --disposition D --reason TEXT [--card ID]` (lease) records what became of one review item. A `finding` takes `rejected`, `deferred`, `inline`, `card` or `brief`; an `out_of_scope` item takes `inline`, `card` or `brief`. A rejection never accepts a card. `finding list [--for-brief]` (no lease) prints the ledger, or a "Known findings" block for a reviewer brief. A reviewer does not raise a known finding unless the code at its location changed.

`brief` (no lease, read-only) prints the newest run brief. Every end of a run writes one to `<state>/progress.md`. Put its Needs you, Still failing, Held log, Final rounds and Notes sections in the PR body under "Held / next phase".

`relaunch --permission-mode MODE [--model ID] [--launcher ARGV...]` runs in the user's terminal after the interactive session ends, with `autonomy arm --relaunch` set. It runs one fresh `claude -p` pass at a time until a stop and never stops for stalls. Exit codes: 0 complete, 3 idle, 4 deadline, 5 disarmed, tampered or not armed, 2 usage or an active session, 127 launcher not found, 130 interrupted.

## Other commands

`classify "SHELL COMMAND"` prints the guard's verdict for a command string without running it. `status` prints cards, session state and `waves` (each wave's card ids and whether the next wave depends on it) with no lease; `board` groups card ids by role and state, `ready` lists dispatchable cards; `scan` runs the configured secret scan.
