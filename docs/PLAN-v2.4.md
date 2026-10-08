# Orchestra 2.4 plan: inline first, review before the PR

Status: settled decisions recorded 2026-10-08. The ticket plan (section 3) follows the engine map.

## 1. Settled decisions (owner, 2026-10-08)

| # | Decision |
|---|---|
| S1 | Model matrix and worker tool allowlists. Done in 90a726d and 86aea84. |
| S2 | Builder `cleanup` stays on Haiku 5.5 high. Move it back to Sonnet 5.5 medium only if the next benchmark shows weaker cleanup. |
| S3 | A request of 1 to 5 items runs inline. The main session plans and edits the work itself, and it may start helper subagents, including through Workflow. A request of 6 or more items goes to the designer-planner, which groups the work into PRs, and Workflow builders do the work. The engine records the item count at `start` and enforces the route. |
| S4 | Independent code review runs only before a PR: one final review of the PR candidate. There is no review after each ticket or wave. Lenses are chosen from the diff paths: correctness always, security on sensitive paths, standards above a size threshold. |
| S5 | Delete checkpoint review, wave reviews, gates between waves, the `wave` label and the `code-reviewer-checkpoint` agent. Card `dependencies` remain the only ordering. |
| S6 | A builder reviews its own work before it reports. It reruns its fast checks and walks its own diff against each acceptance criterion, and its report carries both. The engine accepts a builder card on that self-review when the reported artifact is still current. |
| S7 | After the pre-PR review finds problems: one repair, then a fix re-review of only the fix diff, still before the PR. A chain still blocked after that is held for the owner. |
| S8 | Test suites run in two places only: the checks a builder or the inline session runs on its own work, and before the PR the gap those did not cover (the derived impact set, e2e). A full suite runs only on the owner's request. |
| S9 | During an Orchestra run, the guard denies non-Orchestra subagent types (general-purpose, Explore, Plan, claude) from the main session and names the `orchestra:*` agent to use. Outside a run they stay allowed. |
| S10 | When a current gate receipt exists, the guard denies test-runner commands from code-reviewer and critic agents and tells them to cite the receipt. With no receipt they may run tests. |
| S11 | Grouping work into PRs belongs to the inline session (1 to 5 items) or the designer-planner (6 or more). Worktrees are the minimum needed. Work whose files intersect shares one worktree. A single writer, or writers in sequence, use no worktree. Concurrent writers on disjoint files get one worktree per group. |

## 2. Interface contract (shared by the tickets)

Every ticket builds to these exact names. A ticket that finds a contract item unworkable stops and reports BLOCKED; it does not invent a variant.

1. **Self-review line.** A builder report (any card whose role is `builder`, dispatched or inline) carries one line that starts with `SELF_REVIEW: ` followed by one JSON object:
   `{"checks": [{"command": "<cmd>", "exit_code": <int>}], "criteria": [{"criterion": "<text>", "met": <bool>, "evidence": "<text>"}]}`.
   `checks` and `criteria` are non-empty. `report` refuses a builder report with no line, more than one line, bad JSON or a wrong shape, with the error `Builder report needs one SELF_REVIEW line`. The engine stores the parsed object on the task as `self_review`.
2. **Builder acceptance.** `accept` accepts a builder card when all hold: every check has `exit_code` 0, every criterion has `met: true`, the reported artifact is still current, no current final-review or fix re-review finding names the card, and any repair of it is accepted. Independent review is no longer needed to accept a builder card. Refusal texts: `Self-review has a failing check or unmet criterion`, `Reported artifact is stale`.
3. **Routing.** `orchestra.py start --items N` (integer, 1 or more) is required when it opens a new run. It stores `session.items` and `session.route`: `inline` for 1 to 5, `workflow` for 6 or more. `orchestra.py route --items N --reason TEXT` changes both mid-run and appends `{items, reason, at}` to `session.route_log`. A state with no `items` (made by 2.3) keeps 2.3 routing: no route check.
   - `inline` route: `dispatch` of a builder card needs `--helper REASON`, stored on the task as `helper_reason`; without it the error is `Inline route: the main session does this work; pass --helper REASON to dispatch a helper`. `add` refuses a designer-planner card in `plan` mode: `Inline route: no plan card; the main session groups the work`.
   - `workflow` route: `dispatch` and `inline` of a builder card refuse until a designer-planner `plan` card is accepted: `Workflow route: accept the designer-planner plan card first`.
4. **Review receipts.** Only two kinds are recorded:
   - The **pre-PR review**: `final: true`, covering every pre-release card, as today.
   - The **fix re-review**: `final: false` and `repair_check: true`. Its `tasks` are repair cards whose chain starts at a card with a current final-review finding, plus their ancestors. It is the only non-final code-reviewer receipt. A non-final `critic` receipt (plan or conformance challenge) is still allowed.
   Any other non-final receipt is refused: `Only the pre-PR review and the fix re-review are recorded`.
5. **Repair ladder.** A current final-review finding allows one repair card per chain. After the repair reports, one fix re-review covers the fix diff. CLEAN: the repaired chain accepts. BLOCKED: `hold` the chain; no second repair on that chain without the owner. After a CLEAN fix re-review, completion counts the last pre-PR review as current when every file changed since its artifact belongs to a repair card that the CLEAN fix re-review covered.
6. **Required lenses.** Completion needs the categories `requirements, correctness, tests, architecture` always; `security` when a changed file matches a glob in policy `sensitive_paths` (default `["**/auth/**", "**/security/**", "**/*secret*", "**/hooks/**", "**/guard*", "**/migrations/**", ".github/**"]`); `standards, cleanup` when the run's diff exceeds policy `standards_min_lines` (default 200) changed lines. The changed set is the diff from the run's base commit (store `session.base` at `start`) to the working tree, untracked files included. An explicit policy `required_review_categories` still overrides the derived set. `status` shows the derived set as `required_lenses`.
7. **Deleted.** The `wave` field and `wave:W` in `review_of`, `_check_wave`, `_waves`, `status()['waves']`, wave attribution in `task_findings`, gate-to-held-tip attribution, `supersede` if nothing else uses it, the checkpoint `code-reviewer` mode and the `code-reviewer-checkpoint` agent. `add` refuses a `wave` key: `Waves are removed; use dependencies`.
8. **Gate receipts for hooks.** `Engine.current_gate_ids()` returns the ids of passed gate receipts whose artifact equals the current whole-repository artifact; it returns `[]` when none exist.
9. **Agent guard.** While a run is active (an engine is loaded with an active session), PreToolUse from the main session on `Agent` or `Task` with a `subagent_type` that does not start with `orchestra:` is denied: `Orchestra run active: use an orchestra:* agent (investigator-code for search, builder for edits)`. An empty or missing `subagent_type` counts as non-Orchestra. Outside a run nothing changes.
   - **Subagent guard (owner, 2026-10-08).** Workflow agents never pass through `Agent` or `Task`. While a run is active, PreToolUse from a subagent (payload `agent_id` set) whose `agent_type` does not start with `orchestra:` is denied: `Orchestra run active: this agent is not an orchestra:* agent; stop and report. Start Agent and Workflow workers with an orchestra:<role> type`. `SubagentStart` cannot block (live probe, Claude Code 2.1.292), so it returns the same text as context.
10. **Reviewer test block.** PreToolUse from a subagent whose payload `agent_type` starts with `orchestra:code-reviewer` or `orchestra:critic`, on a shell command that runs a test suite, is denied when `engine.current_gate_ids()` is non-empty: `Cite gate receipt <ids>; reviewers do not rerun suites`. Test-suite commands: `pytest`, `python -m pytest`, `python -m unittest`, `npm test`, `npm run test*`, `pnpm test`, `yarn test`, `npx vitest`, `npx jest`, `npx playwright test`, `go test`, `cargo test`, `make test`. A single-file targeted probe such as `python -m unittest tests.test_x.Class.test_y` is allowed: a unittest or pytest target that names a single test method or `file::test`.

## 3. Tickets

All three run in parallel, each in its own worktree from `main` at the plan commit. Their files do not intersect.

| Card | Mode / agent | Owns | Contract items |
|---|---|---|---|
| E1 | builder implementation, `orchestra:builder` | `plugins/orchestra/scripts/orchestra_core/engine.py`, `plugins/orchestra/scripts/orchestra.py`, `tests/test_engine.py`, `tests/test_integration.py` | 1–8 |
| H1 | builder sensitive, `orchestra:builder` | `plugins/orchestra/scripts/orchestra_core/hooks.py`, `plugins/orchestra/scripts/orchestra_core/guards.py`, `tests/test_hooks.py`, `tests/test_guard_corpus.py`, `docs/hooks.md` | 9–10 (uses item 8 through a fake engine in tests) |
| K1 | builder implementation, `orchestra:builder` | everything under `plugins/orchestra/skills/`, `plugins/orchestra/config/`, `plugins/orchestra/scripts/generate.py`, `plugins/orchestra/agents/`, `tests/test_packaging.py`, `tests/test_skills.py`, `tests/skill_phrases/`, `AGENTS.md`, `README.md`, `SPEC.md`, `docs/models.md`, `docs/roles.md`, `docs/cli.md` | documents 1–10 and S3, S4, S6–S8, S11 |

Pre-PR (coordinator): merge the three branches, the operator gates the full Python suite once, then the pre-PR review with lenses derived per contract item 6 (this change touches hooks, so security runs; it exceeds 200 lines, so standards runs). Then the benchmark rerun.
