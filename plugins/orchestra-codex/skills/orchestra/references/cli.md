# Portable CLI and evidence

Use Python 3.11+ with `plugins/orchestra/scripts/orchestra.py`. Common options precede the command: `--repo`, `--state`, `--actor`, `--lease`. Paths with spaces are supported. Actor/lease values are consistency checks, not authentication.

1. Inspect the target repository and applicable project rules. Run `route facts.json` with checked facts.
2. Run `--repo /path/to/project start --policy policy.json`. Save the returned lease. Policy and run data stay outside the application.
3. Add bounded cards with `--lease LEASE add task.json`; run `ready`, then choose `dispatch TASK WORKER` or `inline TASK`.
4. Start the actual native worker only after reserving the card. Give the full brief and selected native profile. Return a startup receipt naming actual cwd/root/HEAD. A reservation token alone does not prove a worker is running.
5. Run `report WORKER TOKEN result.txt`. Inspect results and group returned builders with `review-groups`.
6. Record independent structured reviews with `--lease LEASE review review.json`; accept covered cards with `accept TASK`.
7. Integrate changes, make tracked memory edits, freeze the candidate, run configured `gate NAME -- COMMAND...` checks and final review. Run `audit-policy audit-facts.json`; dispatch one independent auditor per needed axis.
8. For a configured authorized release, run `permit REMOTE TARGET`, then `release REMOTE TARGET`. Inspect the remote and running system separately. Run `finish` only after completion checks. For another run, use `start --new-run` after the previous session closes.

Read-only evidence cards need coordinator inspection before acceptance; builder cards need current independent review by default. Use `review_required: true` for other consequential artifacts. Review groups cover several task IDs in one report. Tiny reads do not need a run. A changed artifact invalidates old final evidence, including documentation edits.

`inline TASK` reserves the same card for the main actor and returns an assignment token; it does not start a child agent. Run `report MAIN_ACTOR TOKEN result.txt` when done. Disjoint worker cards can run concurrently. Inline work cannot replace code-reviewer, auditor or red-teamer assignments, bypass ownership, or accept unreviewed implementation. The `route` facts may include `execution: "inline"` or `"worker"`; omission returns `decide` and available options. The coordinator supplies judgment; the rubric does not classify free-text prompts.

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

A code-reviewer, auditor or red-teamer card can name `review_of: ["B1"]` to start when B1 reports. Do not also put B1 in accepted `dependencies`. Review-card files describe read scope; avoid the target's exclusive resources. Review_of grants no permission to edit inspected files. Reported workers free running capacity but retain reservations until acceptance.

A repair card names `repair_of` and needs an intact current BLOCKED review of that builder. It replaces an accepted dependency on the original. Creation suspends the original chain as repairing and transfers its reservations to the queued repair. Report the repair, obtain fresh independent review of repair and ancestor IDs, accept the repair, then accept ancestors. Old reports remain history; old CLEAN coverage cannot approve repaired work.

`review-groups` combines returned low-risk builder cards with the same explicit group/outcome or shared input. It isolates consequential foundations. The coordinator checks group coherence and context size before dispatch; the rubric cannot infer semantic relatedness from arbitrary text. Avoid a new reviewer for each micro-ticket.

## Review schema

Write the report outside the application. Obtain the exact artifact from `artifact` and enumerate covered task IDs. The report uses:

```json
{
  "reviewer": "independent-worker-id",
  "categories": ["requirements", "correctness", "security", "tests", "architecture", "standards", "cleanup"],
  "tasks": ["B1"], "findings": [], "verdict": "CLEAN", "final": true,
  "summary": "Describe the inspected code, exercised failures, coverage and remaining gaps.",
  "artifact": {"copy": "replace this example with the complete artifact command output"}
}
```

This example is a schema explanation, not a valid approval receipt. Final reports enumerate every pre-release card, including read-only review cards. They may omit the one terminal releaser. Findings make the verdict BLOCKED; the coordinator checks findings against source before repair. The newest applicable current verdict governs each category. Missing or altered governing evidence blocks; it never restores an older approval. A newly checked intact replacement can supersede it. Report metadata, verdict, current artifact and stored file hashes must agree. Semantic truth remains independent human/model judgment; a JSON label cannot prove correctness.

## Policy

Copy `config/policy.default.json` to an external project policy. Configure `required_checks` as `{name, argv}` objects. A release also needs `release.enabled`, an explicit `authorization` statement, exact `remote`, `target` and `argv`. Required scanners use `secret_scan.required: true` and exact `argv`; `scan` records unavailable optional scanners rather than green evidence. Gate commands are bounded and reject recognized destructive/release operations.

Add at most one releaser/release card. Dispatch it before `permit`; its ordinary dependencies must already be accepted. Release checks every pre-release card and final evidence, excluding only that terminal operation. After execution, inspect the release receipt and remote, report and accept the releaser, then run `finish`. Release validates the active actor/lease, checks known Git destinations against policy, and records actual exit/log evidence. A known Git push must use exactly four argv elements: the engine’s resolved Git executable, push, the explicit remote and one refspec. Wrappers, global options and push options are rejected. Its source must resolve to the reviewed full HEAD, both when permitting and immediately before execution. A timeout stops ordinary process-group descendants; deliberately detached processes are outside that guarantee.

For unattended continuation, explicitly create a ledger with completion criteria, scope and authority. Run `autonomy ledger.md --max-passes 20 --max-stalls 2` under the active lease. Stop never arms itself. Use `interrupt` on cancellation; late reports fail. The main must also stop actual workers through the harness. Completed evidence and prior policies stay in external history; the package never adopts unrelated old runs automatically.
