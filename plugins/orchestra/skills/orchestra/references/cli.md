# Portable CLI and evidence

Use Python 3.11+ with `plugins/orchestra/scripts/orchestra.py`. Common options precede the command: `--repo`, `--state`, `--actor`, `--lease`. Paths with spaces are supported. Actor/lease values are consistency checks, not authentication.

1. Inspect the target repository and applicable project rules. Run `route facts.json` with checked facts.
2. Run `--repo /path/to/project start --policy policy.json`. Save the returned lease. Policy and run data stay outside the application.
3. Add bounded cards with `--lease LEASE add task.json`; run `ready`, then `dispatch TASK WORKER`.
4. Start the actual native worker only after reserving the card. Give the full brief and selected native profile. Return a startup receipt naming actual cwd/root/HEAD. A reservation token alone does not prove a worker is running.
5. Run `report WORKER TOKEN result.txt`. Inspect results and group returned builders with `review-groups`.
6. Record independent structured reviews with `--lease LEASE review review.json`; accept covered cards with `accept TASK`.
7. Integrate changes, make tracked memory edits, freeze the candidate, run configured `gate NAME -- COMMAND...` checks and final review. Run `audit-policy audit-facts.json`; dispatch one independent auditor per needed axis.
8. For a configured authorized release, run `permit REMOTE TARGET`, then `release REMOTE TARGET`. Inspect the remote and running system separately. Run `finish` only after completion checks. For another run, use `start --new-run` after the previous session closes.

Read-only evidence cards need coordinator inspection before acceptance; builder cards need current independent review by default. Use `review_required: true` for other consequential artifacts. Review groups cover several task IDs in one report. Tiny reads do not need a run. A changed artifact invalidates old final evidence, including documentation edits.

## Task example

```json
{
  "id": "B1", "role": "builder", "mode": "implementation",
  "inputs": ["approved settings spec"], "acceptance": ["invalid values show an error"],
  "files": ["src/settings.py"], "resources": ["preview:5101"], "dependencies": [],
  "outcome": "settings-validation", "review_group": "settings-validation"
}
```

Owned directories cover descendants. A shared Git index, build directory, port, fixture or database needs a resource reservation even when files differ. Parallel writers use separate worktrees; the dispatcher owns their creation, integration and preservation. Mark consequential foundations `foundational: true`; their checkpoint precedes dependent dispatch. A repair card also names `repair_of` and needs an intact BLOCKED review of that builder.

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

This example is a schema explanation, not a valid approval receipt. Final reports enumerate every card. Findings make the verdict BLOCKED; the coordinator checks findings against source before repair. Report metadata, verdict, current artifact and stored file hashes must agree. Semantic truth remains independent human/model judgment; a JSON label cannot prove correctness.

## Policy

Copy `config/policy.default.json` to an external project policy. Configure `required_checks` as `{name, argv}` objects. A release also needs `release.enabled`, an explicit `authorization` statement, exact `remote`, `target` and `argv`. Required scanners use `secret_scan.required: true` and exact `argv`; `scan` records unavailable optional scanners rather than green evidence. Gate commands are bounded and reject recognized destructive/release operations.

For unattended continuation, explicitly create a ledger with completion criteria, scope and authority. Run `autonomy ledger.md --max-passes 20 --max-stalls 2` under the active lease. Stop never arms itself. Use `interrupt` on cancellation; late reports fail. The main must also stop actual workers through the harness. Completed evidence and prior policies stay in external history; the package never adopts unrelated old runs automatically.
