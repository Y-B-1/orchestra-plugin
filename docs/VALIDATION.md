# Validation evidence — 2026-09-30

## Checked

| Check | Result |
| --- | --- |
| Python 3.11 unit/integration suite | 89 tests pass (1.0.1 refresh) |
| Canonical agent drift | 14 generated Claude files match |
| Skill Creator frontmatter check | Pass |
| Claude plugin manifest, strict | Pass, no warnings |
| Claude marketplace manifest, strict | Pass, no warnings |
| Claude marketplace add/install/list/uninstall/remove, isolated configuration | All exit 0; correct plugin ID/version discovered |
| Paths with spaces | Native installation, hooks and local release pass |
| Real local release | Structured CLI pushed only a disposable bare Git target; remote full HEAD matched the candidate |
| Dirty/stale evidence rejection | Pass; changed reports/logs, wrong metadata, incomplete coverage and invalidated artifacts reject |
| Autonomous continuation | Explicit intact ledger only; pass/stall caps and interrupt rejection pass |
| Independent skill forward-test | Produced conditional design/plan, concurrent ownership, one outcome review group and explicit audit decisions; fixture sources unchanged |
| Source comparison | All 31 source flow states and all 14 source responsibilities mapped |
| Independent final code review and spec/parity audit | Both CLEAN at a82d3e01859193ea2b85fc54c7cff6d7accdde4e; no unresolved blocking findings |
| Application source preservation | Original HEAD remained fd140bd32df441db36b1f70bd2d506a8582958f9; working tree remained clean |

The suite includes actual subprocess commands, locking/concurrency, schema rejection, release receipts, and repeat-run history. Final-audit regressions cover newer BLOCKED review precedence, repair chains, reported-work review scheduling, terminal release cards, actor/lease rejection, plugin state-path protection, release destinations, literal shell wrappers and process timeouts. The local release fixture has no production remote, deployment or credentials.

## Native limits observed

Claude Code 2.1.284 accepted packaging and installation. A live print-mode attempt failed before model execution because its OAuth session expired and could not refresh. Authentication needs renewal before live model testing. No login or global credential change was performed.

Hook adapters were exercised with native-shaped payloads and real package entrypoints, including allowed/denied directions. Persisted native hook trust was neither written nor bypassed. Trusted automatic startup in a user's normal session remains a user trust check, not an established smoke-test result.

Claude's validator accepts manifest JSON paths and supported directories. Passing an individual agent Markdown path makes that command parse the file as JSON; those exploratory invocations failed for command-shape reasons and do not validate agent content. Directory invocations returned no component records. Canonical references, model settings, generated agent files and worker contracts were checked separately; do not mistake an empty validator result for a semantic agent test.

Other harness adapters, native Windows, production releases and deployed-system checks are outside this validation. GitHub distribution is separate from universal public-directory approval. Shell guards do not interpret arbitrary scripts, stdin, aliases or authenticate worker identities.

Final independent review and the checked candidate hash are recorded in BUILD-LEDGER.md. Native authentication or trust limitations do not become green evidence.

## 1.0.1 refresh

Inline assignments share worker ownership, dependency, capacity, lease and independent review checks.

## 2.0.0 status

Checked in the 2.0.0 candidate worktree, headless: the Python 3.14 unit and integration suite (338 tests), generator drift check (Claude agents match the canonical source), skill byte budgets and provenance tests, packaging and release-archive builds. The suite adds guard corpus parity, scoped-evidence, autonomy, SessionEnd and linked-worktree cases. The TypeScript guard and mods tests run through `claude plugin test` with function hooks enabled; their results belong in BUILD-LEDGER.md with the candidate hash, not here.

Not established by the headless checks, and recorded separately as live user checks when performed: trusted automatic startup with exactly one SessionStart context, the mods heartbeat marker advancing in an interactive session, `/orchestra-board` and `/orchestra-autonomy` rendering, the SessionEnd release after `/exit`, `clear` and `resume` rebinding, the picker's model reaching the main session, and an autonomy run that stops at its pass cap. Treat any of these not listed as observed in the ledger as unperformed.

Known limits are in the [release notes](RELEASE-NOTES-2.0.0.md).

