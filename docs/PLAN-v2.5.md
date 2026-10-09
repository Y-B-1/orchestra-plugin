# Orchestra 2.5 plan: route by diff size, not item count

Status: plan for the approved `docs/DESIGN-v2.5.md` (commit 7102242). Decisions D1 to D5 are settled and are not reopened here. A substantial plan needs an independent critic before any build starts.

## 1. Settled decisions (owner, 2026-10-09)

| # | Decision |
|---|---|
| D1 | Tiny up to 50 changed lines per ask with no interface change; medium up to 400; above that, or more than one session, is large. The tier is the largest ask. The size-check budget is the tier guide times the number of asks. |
| D2 | A real diff over the budget prints a warning with both sizes and continues. It never refuses. |
| D3 | The one pre-PR review is sized by the summed diff: up to 50 lines one Haiku 5.5 diff check; 51 to 400 one Sonnet 5.5 reviewer; over 400 the Opus 5.5 reviewer with lenses derived from the diff, as in 2.4. |
| D4 | The wayfinder map is local markdown at `docs/maps/<name>.md`. |
| D5 | No start-cost number in the engine. The coordinator delegates a unit that is not tiny and either runs beside other work or protects the context ceiling. |

Carried from 2.4 and unchanged: inline-first, builder self-review, one independent pre-PR review, one repair then one fix re-review then hold, lenses from the diff, gate receipts, the guards, minimum worktrees.

## 2. Interface contract (shared by the tasks)

Every task builds to these exact names. A task that finds a contract item unworkable stops and reports BLOCKED; it does not invent a variant. Items marked (mechanism) are plan choices the design left open, listed again in section 8.

1. **Constants** in `engine.py`: `TIER_GUIDE = {'tiny': 50, 'medium': 400}`; reviewer bands by summed changed lines: 0 to 50 `small` (`orchestra:code-reviewer-small`), 51 to 400 `medium` (`orchestra:code-reviewer-medium`), above 400 `full` (`orchestra:code-reviewer`). `INLINE_MAX_ITEMS` stays for 2.4 states. Default policy and the role-to-modes contract do not change, so the policy hash of a 2.4 state still binds. Pinned at 7102242: policy_hash `4b1d85568cf17dffc8adb272d1df95decfaf2a03c18c9176ff17190e4d5fb74d`, contract_hash `7b1f34b2bf297e6e95cdd59306a697f5a2b7410f5a84bc71feb7ffe0213439ed`.
2. **Start.** `start --size {tiny,medium,large} [--asks N] [--owner-request]`. A new run (including `--new-run`) needs `--size`.
   - Missing: `A new run needs --size tiny, medium or large`.
   - `large` without `--owner-request`: `A new run starts at tiny or medium; escalate with route --size large --reason TEXT, or pass --owner-request when the owner asked for a map`.
   - `--asks` is an integer, 1 or more, default 1; otherwise `--asks must be an integer, 1 or more`.
   - `start --items` always refuses: `--items is the 2.4 flag; start with --size` (mechanism).
   - Resuming an existing run needs none of these flags.
3. **Session fields** for a size run: `size`, `asks`, `owner_request` (bool), `base` (2.4), `route_log`. No `route` field. A session carries `items` (a 2.4 run), or `size` (a 2.5 run), or neither (a 2.3 run); both is invalid state. A 2.4 run keeps the 2.4 route check unchanged. `open_session(..., items=None, size=None, asks=None, owner_request=False, require_size=False)`; `require_items` is removed, `items=` stays for 2.4 tests. A resumed or relaunched run copies `size`, `asks`, `owner_request` as it copies `items`.
4. **Route.** `route (--size TIER [--asks N] | --items N) --reason TEXT`, exactly one of the two. `--size` appends `{size, asks, reason, at}` to `route_log` and may move in either direction, to `large` included with no owner request. `route --size` on a 2.4 run: `This run routes by items; use route --items`. `route --items` on a size run: `This run routes by size; use route --size`.
5. **Builder cards.** A builder task JSON may carry `size`: `tiny` or `medium`. Default is the run tier, with `large` read as `medium`. Anything else: `Invalid task size`. Size runs only:
   - `dispatch` of a builder card with size `tiny` needs `--helper REASON`, stored as `helper_reason`; otherwise `Tiny unit: the main session does this work; pass --helper REASON to dispatch a helper`.
   - `inline` is never gated. `--helper` on a medium card is accepted and ignored.
6. **Plan card.** On a size run, `add` of a designer-planner `plan` card needs `size` = `large`, or `session.owner_request`, or `"owner_request": true` in the task JSON (mechanism); otherwise `Plan card needs a large run or an owner request; escalate with route --size large --reason TEXT`. A large run does not force a plan before builders; the design leaves that to the coordinator.
7. **Pre-PR check.** New lease-free, read-only command `orchestra.py prepr` (mechanism: the engine had no pre-PR step to hang the check on). It measures the changed lines with `_changed(session.base)` (the same set the standards lens uses, untracked files included) and prints one JSON object, always with exit 0 on a loaded run:
   `{"base", "changed_lines", "size", "asks", "budget", "over_budget", "reviewer", "agent", "lenses", "warning"}`.
   - `budget` is `TIER_GUIDE[size] * asks`, or null for `large` and for 2.4 and 2.3 runs (`size` null, no warning for those).
   - `reviewer` and `agent` follow item 1 by `changed_lines`. `lenses` is `required_lenses`.
   - `warning` is null, or exactly `Size warning: declared {size} with {asks} ask(s) budgets {budget} changed lines; the diff has {lines}. Run route --size TIER --reason TEXT if the work grew.` The same text goes to stderr.
   - `prepr` writes no state and needs no lease. `status` also shows `size`, `asks`, `owner_request`.
8. **Reviewer agents.** `config/models.json` code-reviewer presets `small` (Haiku 5.5 high) and `medium` (Sonnet 5.5 medium). The generator writes `agents/code-reviewer-small.md` and `agents/code-reviewer-medium.md`, each with the `code-reviewer` tools (`Read`, `Bash`), mode `final`, and a `VARIANT_NOTES` line naming `Lens: combined`.
9. **Combined lens.** `Lens: combined` in `orchestra-review/references/final.md`, with a `Required categories:` line copied from `lenses`. The reviewer opens `correctness.md`, plus `security.md` and `standards.md` when those categories are listed, and reports `categories` equal to the list. A combined brief with no `Required categories:` line is a blocker, like a missing `Lens:` line. One combined receipt can satisfy completion; the `>400` path keeps one card per lens.
10. **Wayfinder.** `skills/orchestra/references/wayfinder.md`, first line `Source: derived from mattpocock/skills@49dd158d1076 skills/engineering/wayfinder/SKILL.md (MIT); see THIRD-PARTY-NOTICES.`, second line `Sentinel: orchestra/references/wayfinder.md`. Full sha `49dd158d1076134a641b33efb035946536778336`. It holds: when to use it (large only, reached by escalation or an owner request, "Never start with the map"), the map file at `docs/maps/<name>.md` (destination, notes, decisions so far one line each with the ticket link, fog, out of scope), ticket types (research, prototype, grilling, task), "One human decision ticket per session", research tickets run together as `investigator` cards through Workflow, and hand-off to a designer-planner `plan` card when no fog remains. Under 5000 bytes.
11. **Version** `2.5.0` in `plugins/orchestra/plugin.json`, `plugins/orchestra/.claude-plugin/plugin.json`, `.claude-plugin/marketplace.json`.

## 3. State migration

No state file is rewritten. A 2.4 state has `items`, `route` and `route_log` entries `{items, reason, at}`; all stay valid and all 2.4 checks stay (`_check_items`, `_check_route`, `route --items`). Because the default policy and the role modes are unchanged (item 1), the policy hash binds it with no rebind. Proof: `tests/fixtures/state-2.4.json`, created once by running the 2.4 engine (`git archive 3088dde plugins/orchestra | tar -x -C $SCRATCH/v24`, then `python3.11 $SCRATCH/v24/plugins/orchestra/scripts/orchestra.py --repo $SCRATCH/repo start --items 3` in a scratch repo, then copy its `state.json`), plus a test pinning both hashes. A 2.3 state still loads through the existing `load_2_3_state` tests, unchanged.

## 4. Tasks

Six tasks. Tier is the expected diff of the task itself.

| Task | Mode | Owns (exact) | Depends on | Tier |
|---|---|---|---|---|
| E1 | builder implementation | `plugins/orchestra/scripts/orchestra_core/engine.py`, `plugins/orchestra/scripts/orchestra.py`, `tests/test_engine.py`, `tests/test_integration.py`, `tests/test_hooks.py`, `tests/fixtures/state-2.4.json` | none | large (about 600 lines) |
| K1 | builder implementation | `plugins/orchestra/config/models.json`, `plugins/orchestra/config/roles.json`, `plugins/orchestra/scripts/generate.py`, `plugins/orchestra/agents/code-reviewer.md`, `.../code-reviewer-standards.md`, `.../code-reviewer-small.md`, `.../code-reviewer-medium.md`, `plugins/orchestra/skills/orchestra-review/references/final.md`, `tests/skill_phrases/orchestra-review.json`, `tests/test_packaging.py`, `docs/models.md`, `docs/roles.md`, `AGENTS.md` | none | medium (about 150 lines) |
| W1 | inline (main session) | `plugins/orchestra/skills/orchestra/references/wayfinder.md`, `plugins/orchestra/THIRD-PARTY-NOTICES`, `docs/SKILL-SOURCES.md`, `tests/test_skills.py`, `tests/skill_phrases/orchestra.json` | none | medium (about 90 lines) |
| S1 | inline (main session) | `plugins/orchestra/skills/orchestra/SKILL.md`, `.../references/coordination.md`, `.../references/cli.md`, `.../references/final-review.md`, `.../references/worktrees.md`, `plugins/orchestra/agents/orchestrator.md` (generated), `tests/skill_phrases/orchestra.json` | W1 (shares `orchestra.json`; links the wayfinder file); contract items 2 to 9 | medium (about 100 lines) |
| R1 | inline (main session) | `plugins/orchestra/plugin.json`, `plugins/orchestra/.claude-plugin/plugin.json`, `.claude-plugin/marketplace.json`, `CHANGELOG.md`, `README.md`, `docs/cli.md`, `SPEC.md`, `tests/test_packaging.py` | E1, K1, W1, S1 | medium (about 90 lines) |
| B1 | coordinator live check | `docs/BUILD-LEDGER.md` | R1 merged and installed | tiny (about 30 lines) |

### E1: engine and CLI

Tests first (names), all failing before the change:

`tests/test_engine.py`, class `SizeRouteTests`:
- `test_new_run_without_size_is_refused_naming_size`, `test_size_large_on_new_run_needs_owner_request_and_names_escalation`, `test_owner_request_allows_large_start`, `test_unknown_size_and_bad_asks_are_refused`
- `test_session_records_size_asks_and_owner_request`, `test_relaunch_keeps_size_asks_and_owner_request`
- `test_route_size_logs_size_asks_reason`, `test_route_size_can_escalate_to_large_without_owner_request`, `test_route_size_refused_on_items_run`, `test_route_items_refused_on_size_run`
- `test_tiny_card_dispatch_needs_helper_reason`, `test_medium_card_dispatch_needs_no_helper`, `test_card_size_overrides_run_size`, `test_large_run_card_defaults_to_medium`, `test_invalid_card_size_is_refused`, `test_inline_reservation_of_a_tiny_card_is_not_gated`
- `test_plan_card_refused_on_tiny_and_medium_run`, `test_plan_card_allowed_on_large_run`, `test_plan_card_allowed_with_session_owner_request`, `test_plan_card_allowed_with_task_owner_request`
- `test_state_with_items_and_size_together_is_invalid`, `test_bad_size_or_asks_in_state_is_invalid`
- `test_one_combined_receipt_covers_all_required_categories`

`tests/test_engine.py`, class `PrePrTests`:
- `test_budget_is_guide_times_asks`, `test_over_budget_warns_with_both_sizes_and_succeeds`, `test_within_budget_has_no_warning`, `test_large_run_has_no_budget`, `test_items_and_2_3_runs_get_no_size_check`
- `test_reviewer_bands_at_50_51_400_401`, `test_reviewer_follows_summed_lines_not_largest_ask`, `test_untracked_files_count_toward_changed_lines`, `test_prepr_writes_no_state`

`tests/test_engine.py`, class `LegacyStateTests` (existing class, added tests): `test_2_4_state_loads_and_keeps_2_4_routing` (from the fixture: inline route still refuses a builder dispatch without `--helper`, `route --items` still works), `test_2_4_policy_and_contract_hash_are_pinned`. The existing 2.4 `RouteTests` stay as they are, except `require_items` cases become `require_size` cases.

`tests/test_integration.py`, class `SizeCli`:
- `test_start_without_size_exits_nonzero_naming_size`, `test_start_size_large_exits_nonzero_naming_escalation`, `test_start_size_medium_with_asks_prints_a_lease`, `test_start_items_is_refused_pointing_to_size`
- `test_route_needs_exactly_one_of_size_or_items`, `test_route_size_logs_and_exits_zero`
- `test_dispatch_tiny_card_without_helper_exits_nonzero`, `test_dispatch_medium_card_exits_zero`
- `test_prepr_over_budget_prints_warning_and_exits_zero`, `test_prepr_names_the_reviewer_agent_for_each_band`

Existing tests that start a run with `--items N` (`test_integration.py` lines about 45, 85, 155, 346, 361, 394 to 396; `test_hooks.py` about 1135, 1447, 1463) move to `--size medium`. `RouteCliIntegration` (about 688 to 742) now copies `tests/fixtures/state-2.4.json` into the state directory and runs the same 2.4 route checks against it. Add `test_hooks.py::test_reviewer_test_block_covers_the_size_variants` (agent types `orchestra:code-reviewer-small` and `-medium` get the same test-suite denial as `orchestra:code-reviewer`).

Acceptance:
- `python3.11 -m unittest tests.test_engine tests.test_integration tests.test_hooks` exits 0.
- `python3.11 plugins/orchestra/scripts/orchestra.py --repo $SCRATCH/repo start` on a new run exits non-zero and the message names `--size`.
- `... start --size large` exits non-zero and the message names `escalate`.

### K1: reviewer-model selection

How a pre-PR reviewer gets its model today: the coordinator dispatches the agent file `orchestra:code-reviewer` (Opus 5.5 medium, from `config/models.json`) and `code-reviewer-standards` for the standards lens; `generate.py` writes one agent per non-default preset in `variants_of`. 2.5 adds two presets, so the generator emits the two new files; the engine's `prepr` names which one to dispatch.

Tests first, in `tests/test_packaging.py`: `test_reviewer_size_variants_are_generated` (small is `claude-haiku-5-5` high, medium is `claude-sonnet-5-5` medium, both in the expected agent set), `test_reviewer_size_variants_keep_the_reviewer_tools` (`Read`, `Bash`, no write tool), and the existing generated-agents-match test. In `tests/skill_phrases/orchestra-review.json`: add `Lens: combined` and `Required categories:`.

Edits: the two presets; `VARIANT_NOTES` for `('code-reviewer', 'small')` and `('code-reviewer', 'medium')`; the `roles.json` code-reviewer prompt names the combined lens; `final.md` gets the combined-lens row and the missing-`Required categories:` blocker (cap 6144 bytes, now 3796); `docs/models.md`, `docs/roles.md` list the two reviewers; the `AGENTS.md` model sentence becomes: "Opus 5.5 medium for the final reviewer above 400 changed lines and for builder repair; Sonnet 5.5 medium for the final reviewer from 51 to 400 lines, builders, the standards lens and docs investigator; Haiku 5.5 high for the final reviewer up to 50 lines, mechanical and cleanup builders, operator and code discovery."

Acceptance:
- `python3.11 plugins/orchestra/scripts/generate.py` then `python3.11 plugins/orchestra/scripts/generate.py --check` exits 0.
- `python3.11 -m unittest tests.test_packaging tests.test_skills` exits 0 (the version and changelog assertions in `test_packaging.py` are R1's, so run R1's line edits only after K1; K1 does not touch them).
- `wc -c plugins/orchestra/agents/code-reviewer-*.md` shows each at most 2650 bytes.
- `grep -c "final reviewer up to 50" AGENTS.md` prints 1.

### W1: wayfinder reference and credit

Tests first: `tests/test_skills.py` adds `references/wayfinder.md` to the `orchestra` list in `TABLE`, moves the distinct-sha count from 6 to 7 (`assertEqual(len(shas), 7, shas)`), and keeps the "Permission is hereby granted" count at 5 (no new license block; same license text as the first pin). `tests/skill_phrases/orchestra.json` adds `Sentinel: orchestra/references/wayfinder.md`, `docs/maps/`, `One human decision ticket per session` and `Never start with the map`.

Edits: the new reference (contract item 10); `THIRD-PARTY-NOTICES` gets a "mattpocock/skills (third pin, Orchestra 2.5.0)" section with `Commit: 49dd158d1076134a641b33efb035946536778336` and `Used for skills/engineering/wayfinder`, in the style of the second-pin section; `docs/SKILL-SOURCES.md` gets a matrix row `Pocock (2.5 pin) | mattpocock/skills | 49dd158d1076134a641b33efb035946536778336 | mattpocock/skills@49dd158d1076:<path> | MIT (Matt Pocock)`, a topic row for large-work mapping, and a file row `orchestra/references/wayfinder.md`. Read the upstream skill with `git -C /Users/yusri/.claude/plugins/marketplaces/mattpocock show origin/HEAD:skills/engineering/wayfinder/SKILL.md`; write it in our own words.

Acceptance: `python3.11 -m unittest tests.test_skills` exits 0; `wc -c plugins/orchestra/skills/orchestra/references/wayfinder.md` under 5000.

### S1: routing text

Tests first: `tests/skill_phrases/orchestra.json` swaps the phrases `` `start --items N` `` and `` `dispatch --helper REASON` `` for `` `start --size` ``, `` `route --size` ``, `` `prepr` ``, ``Tiny unit``, ``Lens: combined`` and `references/wayfinder.md`.

Edits:
- `SKILL.md`: the Route section becomes the tier table (tiny: inline edit, no alignment; medium: grill inline, then execution; large: escalation only, wayfinder). Net change at most +136 bytes (cap 4096, now 3960). Add `references/wayfinder.md` to the reference list.
- `coordination.md`: lane row `plan` reads "Approved substantial design, a large run, or an owner request"; add the question-2 executor table in short form. No four-word phrase shared with `SKILL.md`. `orchestrator.md` must stay at most 10500 bytes (now 9010; regenerated by `generate.py`).
- `cli.md`: `start --size`, `--asks`, `--owner-request`, `route --size`, the tiny-card `--helper` rule, the plan-card rule, `prepr` with its JSON fields and warning text; 2.4 rows marked "2.4 runs only".
- `final-review.md`: step 1 runs `prepr`, step 2 dispatches by `agent`: small or medium is one card with `Lens: combined` and the `Required categories:` line; full keeps the one-card-per-lens flow.
- `worktrees.md`: replace "1 to 5 items / 6 or more" with the tier and unit rule.

Run `generate.py` after K1 is merged, so `orchestrator.md` is built from the merged `roles.json`.

Acceptance: `python3.11 plugins/orchestra/scripts/generate.py --check` exits 0; `python3.11 -m unittest tests.test_skills tests.test_packaging` exits 0; `grep -rn -e "--items" plugins/orchestra/skills` lists only lines marked 2.4.

### R1: release surface

Tests first, `tests/test_packaging.py`: version `'2.5.0'`, changelog heading `## 2.5.0`, and `test_prepr_reviewer_agents_exist` (import the engine band constants, assert each named agent file exists; this is the cross-check between E1 and K1).

Edits: three manifests to 2.5.0; `CHANGELOG.md` section `2.5.0` (route by size, `--size` and `--owner-request`, `prepr` size check, reviewer by summed diff, wayfinder, 2.4 runs keep item routing); `README.md` quick start and routing paragraph (`start --size`), plus an upgrade note: "A run started under 2.4 loads under 2.5 and keeps item routing; new runs use `--size`; `--items` is refused on `start`"; `docs/cli.md` rows for `start`, `route`, `add`, `dispatch`, `prepr`; `SPEC.md` line 13 version text if it names 2.4.

Acceptance: `python3.11 -m unittest discover -s tests` exits 0; `python3.11 plugins/orchestra/scripts/generate.py --check` exits 0; `python3.11 scripts/build_release.py` exits 0 and names `orchestra-2.5.0`.

### B1: benchmark checks (after release, as in 2.4)

Run on the installed 2.5.0 plugin by a headless coordinator on Opus, like the 2.4 rerun (`docs/BUILD-LEDGER.md`, section "2.4 release and benchmark"). The ledger records the 2.4 result (3 files, 5+/5-, 35,990 sub-agent tokens) but not the three edits themselves. B1 states the three one-line edits it uses and says why they match.

1. **Three tiny edits** (acceptance 6). `start --size tiny --asks 3`. Expect: `orchestra.py board` shows 0 builder cards, exactly 1 code-reviewer card, and `prepr` names `orchestra:code-reviewer-small` (about 10 changed lines); sub-agent tokens (`subagent_tokens`, same field as the 2.4 row) at most 35,990.
2. **Two medium units on disjoint files** (acceptance 7), for example two new helper modules with tests of about 60 to 100 lines each in a scratch repo. Run the same work twice from the same base commit: serial (main session does unit A then unit B) and parallel (one Workflow builder in a worktree on A, the main session inline on B). Record wall time from `start` to the last accepted card for each. Pass when parallel wall time is under serial wall time. One run each is noisy; report both times and the token cost of each.

Record both tables in `docs/BUILD-LEDGER.md` in a separate docs-only commit after the merge, the way 2.4 did. That commit is outside the reviewed PR.

## 5. Dependency graph and parallel groups

```
E1 --\
K1 ---+--> R1 --> (merge, gate, pre-PR review) --> B1
W1 -> S1 --/
```

- No cycles. S1 waits for W1 only because both edit `tests/skill_phrases/orchestra.json` and S1 links the new reference. R1 waits for all four because it edits `tests/test_packaging.py` after K1 and states the whole release.
- Parallel: **E1, K1 and W1 start together.** S1 starts when W1 is accepted, and can run while E1 and K1 are still open (the contract fixes the names).
- Executors under the design's question 2: E1 (large) and K1 (medium) are two independent not-tiny units, so each gets a Workflow builder; the main session does W1, then S1, then R1 inline beside them, and B1 itself. Worktrees: E1 and K1 get one each (concurrent writers on disjoint files). W1, S1 and R1 are one writer in sequence in the main checkout, so they use none. Remove both worktrees after the merge, after inspecting each directory.
- Run record: this build runs on the installed 2.4 engine, so `start --items 5` (five tasks, inline route). Dispatch E1 and K1 with `--helper "independent unit beside other work"`.

## 6. Ownership check

| File | Tasks (order) |
|---|---|
| `engine.py`, `orchestra.py`, `tests/test_engine.py`, `tests/test_integration.py`, `tests/test_hooks.py`, `tests/fixtures/state-2.4.json` | E1 |
| `config/models.json`, `config/roles.json`, `generate.py`, `agents/code-reviewer*.md`, `orchestra-review/references/final.md`, `skill_phrases/orchestra-review.json`, `docs/models.md`, `docs/roles.md`, `AGENTS.md` | K1 |
| `references/wayfinder.md`, `THIRD-PARTY-NOTICES`, `docs/SKILL-SOURCES.md`, `tests/test_skills.py` | W1 |
| `tests/skill_phrases/orchestra.json` | W1, then S1 (S1 depends on W1) |
| `SKILL.md`, `coordination.md`, `cli.md` (skill), `final-review.md`, `worktrees.md`, `agents/orchestrator.md` | S1 |
| `tests/test_packaging.py` | K1, then R1 (R1 depends on K1) |
| three manifests, `CHANGELOG.md`, `README.md`, `docs/cli.md`, `SPEC.md` | R1 |
| `docs/BUILD-LEDGER.md` | B1 |

No file appears in two tasks without a dependency. `docs/PLAN-v2.5.md` belongs to the planner only. `agents/orchestrator.md` and `agents/code-reviewer*.md` are written by the same generator in different tasks; their files are disjoint.

## 7. Pre-flight rows

| Producer | Consumer | Produces / consumes | Finding |
|---|---|---|---|
| E1 | S1, R1, B1 | CLI names, error texts and the `prepr` JSON (items 2 to 7) | Fixed by the contract text. S1 and R1 quote it verbatim; no shared file. |
| K1 | E1 | Agent names `orchestra:code-reviewer-small` and `-medium` | E1 holds them as strings. R1's `test_prepr_reviewer_agents_exist` checks the two files exist after merge. |
| K1 | S1 | `Lens: combined` and `Required categories:` in `final.md` | S1's `final-review.md` text quotes them. Phrase tests cover both. |
| W1 | S1 | Path and sentinel of `wayfinder.md`, `orchestra.json` | Ordered by dependency. |
| K1 | S1 | `generate.py` output | S1 regenerates `orchestrator.md` after K1 merges, so a `roles.json` change cannot leave it stale. |
| E1 | R1 | `tests/test_packaging.py` imports engine constants | R1 runs after the E1 merge. |
| none | none | E1 and W1; K1 and W1; E1 and K1 | Share nothing. |

## 8. Gaps and design notes (not decided here)

- **Mechanisms chosen, for the critic to rule:** the `prepr` command name and JSON; `_changed` rather than `git diff --shortstat` (it counts untracked files and matches the standards lens); `start --items` refused outright, reading "accepted only from a 2.4 state" as "`route --items` and resumed 2.4 runs keep working"; a plan card allowed by a session or task `owner_request`; no `route` field on size runs.
- **`asks` is declared by the coordinator.** The engine cannot count asks, and a large `--asks` weakens the warning. This is a convenience check, not isolation.
- **Sensitive paths under D3.** A 10-line change in `auth/` gets the Haiku reviewer. The plan keeps completion safe (the combined review must report the `security` category when `required_lenses` lists it) but does not add a floor, because D3 sets none.
- **Lockfiles and generated files** count in `changed_lines`; the owner's data removed them. A large lockfile pushes the review to Opus (conservative). No ignore list is added.
- **Benchmark inputs** for the 2.4 edits are not recorded in the repository (B1 re-states them). Acceptance 7 rests on one run per arm.
- **Not enforced by the engine:** a large run does not require an accepted plan card before builders (the design checks only the two rules in contract items 5 and 6).
- The design text "the pre-PR step refuses (or warns, D2)" is stale after D2; the plan follows D2.

## 9. Acceptance map

| Design acceptance | Task | Evidence |
|---|---|---|
| 1. `start` without `--size` exits non-zero naming `--size` | E1 | `test_start_without_size_exits_nonzero_naming_size`, the engine twin |
| 2. `start --size large` refused without `--owner-request`, names escalation | E1 | `test_start_size_large_exits_nonzero_naming_escalation` |
| 3. Over-budget diff warns at the pre-PR step and succeeds | E1 (S1 documents the step) | `test_prepr_over_budget_prints_warning_and_exits_zero` |
| 4. Tiny unit dispatch needs `--helper`; medium succeeds | E1 | `test_dispatch_tiny_card_without_helper_exits_nonzero`, `test_dispatch_medium_card_exits_zero` |
| 5. 2.4 state keeps 2.4 routing; 2.3 state still loads | E1 (R1 notes it in README) | `test_2_4_state_loads_and_keeps_2_4_routing`, `RouteCliIntegration` on the fixture, existing 2.3 `LegacyStateTests` |
| 6. Three tiny edits: 0 builders, 1 reviewer, at most 35,990 tokens | B1 (needs E1, K1, S1, R1) | benchmark table 1 |
| 7. Two disjoint medium units finish faster in parallel than serial | B1 (needs E1, S1, R1) | benchmark table 2 |

Other required content: engine and CLI E1; 2.4 `items` migration section 3 and E1; reviewer model selection K1 and contract items 1, 7 to 9; routing text S1; wayfinder and its credit W1; version R1; CHANGELOG R1; README upgrade note R1; benchmark checks B1; `AGENTS.md` model sentence K1.

## 10. Place the reviews

One pre-PR review covers the single v2.5 PR (E1, K1, W1, S1, R1 merged). The operator gates the full Python suite once on the merged candidate (`python3.11 -m unittest discover -s tests`, `generate.py --check`, `build_release.py`). The change is over 400 lines, so under D3 the reviewer is the Opus 5.5 with lenses: correctness always, standards (over 200 lines), and security only if a changed path matches `sensitive_paths` (the plan changes none: `tests/test_hooks.py` is not a `hooks/` directory). A blocked finding on engine code returns to E1; on agents, models or `final.md` to K1; on skill text to S1; on the reference or credits to W1; on release files to R1. No live human check is needed: the two benchmarks are headless runs with the steps in B1. Optional full-suite testing stays on the owner's trigger.

## 11. Self-check

- Every design acceptance item and decision D1 to D5 maps to a task (sections 4 and 9).
- Names agree across tasks through section 2.
- E1 is the largest unit (about 600 lines); it is one engine and CLI change that cannot be split without sharing files.
- Every task has an owner, acceptance commands and a done contract: the report shows the named tests passing with command and exit code.
- A substantial plan needs an independent critic before any build starts.
