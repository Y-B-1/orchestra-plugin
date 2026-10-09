# Orchestra 2.5 plan: route by diff size, not item count

Status: plan for the approved `docs/DESIGN-v2.5.md`, repaired after the critic's BLOCKED review of 0cf91c7. Decisions D1 to D5 are settled and are not reopened here. A substantial plan needs an independent critic before any build starts.

## 1. Settled decisions and rulings

| # | Decision |
|---|---|
| D1 | Tiny up to 50 changed lines per ask with no interface change; medium up to 400; above that, or more than one session, is large. The tier is the largest ask. The size-check budget is the tier guide times the number of asks. |
| D2 | A real diff over the budget prints a warning with both sizes and continues. It never refuses. |
| D3 | The one pre-PR review is sized by the summed diff: up to 50 lines one Haiku 5.5 diff check; 51 to 400 one Sonnet 5.5 reviewer; over 400 the Opus 5.5 reviewer with lenses derived from the diff, as in 2.4. |
| D4 | The wayfinder map is local markdown at `docs/maps/<name>.md`. |
| D5 | No start-cost number in the engine. The coordinator delegates a unit that is not tiny and either runs beside other work or protects the context ceiling. |
| O1 | Owner, 2026-10-09: benchmarks run before the merge, lean. A failure blocks the merge (task B1). |
| C1 | Critic rulings: keep `prepr` (name and JSON); keep `_changed(base)` for measuring; keep `start --items` in argparse and refuse it with the contracted message; keep E1 as one unit; K1 runs inline in the main session beside E1 (no agent). |

Carried from 2.4 and unchanged: inline-first, builder self-review, one independent pre-PR review, one repair then one fix re-review then hold, lenses from the diff, gate receipts, the guards, minimum worktrees.

## 2. Interface contract (shared by the tasks)

Every task builds to these exact names. A task that finds a contract item unworkable stops and reports BLOCKED; it does not invent a variant. Items marked (mechanism) are plan choices the design left open; section 8 lists them.

1. **Constants** in `engine.py`: `TIER_GUIDE = {'tiny': 50, 'medium': 400}`; `REVIEWER_BANDS = ((50, 'small', 'orchestra:code-reviewer-small'), (400, 'medium', 'orchestra:code-reviewer-medium'))`, the band whose upper bound is not exceeded by the summed changed lines; above the last bound `REVIEWER_FULL = ('full', 'orchestra:code-reviewer')`. R1's test imports `REVIEWER_BANDS` and `REVIEWER_FULL`. `INLINE_MAX_ITEMS` stays for 2.4 states. Default policy and the role-to-modes contract do not change, so the policy hash of a 2.4 state still binds. No new policy key (it would change `policy_hash`, `engine.py:269`). Pinned at 7102242: policy_hash `4b1d85568cf17dffc8adb272d1df95decfaf2a03c18c9176ff17190e4d5fb74d`, contract_hash `7b1f34b2bf297e6e95cdd59306a697f5a2b7410f5a84bc71feb7ffe0213439ed`.
2. **Start.** `start --size {tiny,medium,large} [--asks N] [--owner-request]`. A new run (including `--new-run`) needs `--size`.
   - Missing: `A new run needs --size tiny, medium or large`.
   - `large` without `--owner-request`: `A new run starts at tiny or medium; escalate with route --size large --reason TEXT, or pass --owner-request when the owner asked for a map`.
   - `--asks` is an integer, 1 or more, default 1; otherwise `--asks must be an integer, 1 or more`. It counts the separately stated asks in the request: changes the owner could accept or reject on their own. The tier is the largest single ask, not the sum.
   - `start --items` stays in argparse and always refuses: `--items is the 2.4 flag; start with --size`.
   - `--size`, `--asks` or `--owner-request` on a resumed run (a session record already exists) refuse like the 2.4 `--items` rule: `--size, --asks and --owner-request apply to a new run; use start --new-run, or route --size to change the tier`. A resumed run needs none of the flags.
   - With `--new-run`, `_check_start(size, asks, owner_request)` (all of the above except the resumed-run rule) runs before `archive_inactive`, so a refused start leaves the ended run in place (`orchestra.py:136-139`).
3. **Session fields** for a size run: `size`, `asks`, `owner_request` (bool), `base` (2.4), `route_log`. No `route` field. A session carries `items` (a 2.4 run), or `size` (a 2.5 run), or neither (a 2.3 run); both is invalid state (`Invalid session size`). A 2.4 run keeps the 2.4 route check unchanged. `open_session(..., items=None, size=None, asks=None, owner_request=False, require_size=False)`; `require_items` is removed, `items=` stays for the 2.4 tests. A resumed or relaunched run copies `size`, `asks`, `owner_request` as it copies `items`.
4. **Route.** `route (--size TIER [--asks N] | --items N) --reason TEXT`, exactly one of the two.
   - `--size` appends `{size, asks, reason, at}` to `route_log` and may move either way, to `large` included with no owner request. Without `--asks` it keeps the current count.
   - `route --size` on a 2.4 run: `This run routes by items; use route --items`. `route --items` on a size run: `This run routes by size; use route --size`.
   - `route --size` on a 2.3 run (neither field): `This run has no route; start a new run with --size`. `route --items` on a 2.3 run behaves as in 2.4.
5. **Builder cards.** A builder task JSON may carry `size`: `tiny` or `medium`; anything else: `Invalid task size`. The value is validated on every run and enforced on size runs only (2.4 and 2.3 runs ignore it). A card with no `size` takes the run tier when it is dispatched, not when it was added (`large` reads as `medium`), so an escalation reaches cards already in the board. Size runs:
   - `dispatch` of a builder card whose size is `tiny` needs `--helper REASON`, stored as `helper_reason`; otherwise `Tiny unit: the main session does this work; pass --helper REASON to dispatch a helper`.
   - `inline` is never gated. `--helper` on a medium card is accepted and ignored.
6. **Plan card.** On a size run, `add` of a designer-planner `plan` card needs `size` = `large`, or `session.owner_request`, or `"owner_request": true` in the task JSON (mechanism); otherwise `Plan card needs a large run or an owner request; escalate with route --size large --reason TEXT`. A large run does not force a plan before builders.
7. **Pre-PR check.** New lease-free, read-only command `orchestra.py prepr`. It measures changed lines with `_changed(session.base)` and prints one JSON object, exit 0 on a loaded run:
   `{"base", "changed_lines", "size", "asks", "budget", "over_budget", "reviewer", "agent", "lenses", "warning"}`.
   - `budget` is `TIER_GUIDE[size] * asks`, or null for `large` and for 2.4 and 2.3 runs (`size` null, no warning). `over_budget` is a bool, false when `budget` is null.
   - `reviewer` and `agent` follow item 1 by `changed_lines`. `lenses` is `required_lenses`.
   - **No base** (a 2.3 run, or a state with no session): `_changed(None)` is never called. `base` null, `changed_lines` null, `reviewer` `full`, `agent` `orchestra:code-reviewer`, `lenses` as `_required_lenses` returns for no base (every category, or the explicit policy list), `warning` null.
   - `warning` is null, or exactly `Size warning: declared {size} with {asks} ask(s) budgets {budget} changed lines; the diff has {lines}. Run route --size TIER --reason TEXT if the work grew.` The same text goes to stderr.
   - `prepr` is stateless: it recomputes the budget from the current `size` and `asks` on every call. So a `route` clears the warning only when the new budget covers the diff. This is a deliberate refinement of the design, not a way to silence it.
   - `prepr` writes no state and needs no lease. `status` also shows `size`, `asks`, `owner_request`.
   - Known limits, not fixed in 2.5: untracked binary files count through `splitlines()` while tracked binary files count 0; lockfiles and generated files count.
8. **Reviewer agents.** `config/models.json` code-reviewer presets `small` (Haiku 5.5 high) and `medium` (Sonnet 5.5 medium). The generator writes `agents/code-reviewer-small.md` and `agents/code-reviewer-medium.md`, each with the `code-reviewer` tools (`Read`, `Bash`), mode `final`, and a `VARIANT_NOTES` line naming `Lens: combined`. The fix re-review (mechanism) uses the agent `prepr` named for the pre-PR review; in the small and medium bands it is a non-final review by the band's agent on the fix diff, with `repair_check: true` and no `Required categories:` line; in the full band the 2.4 flow.
9. **Combined lens.** `Lens: combined` in `orchestra-review/references/final.md`, with a `Required categories:` line copied from `lenses`. The reviewer opens `correctness.md`, plus `security.md` and `standards.md` when those categories are listed, and reports `categories` equal to the list. A combined brief with no `Required categories:` line is a blocker, like a missing `Lens:` line. It is written as a paragraph after the lens table, never as a table row that starts with a backticked name (`test_final_lens_table_covers_every_category`, `tests/test_skills.py:340-348`). One combined receipt can satisfy completion; the full band keeps one card per lens.
10. **Wayfinder.** `skills/orchestra/references/wayfinder.md`, first line `Source: derived from mattpocock/skills@49dd158d1076 skills/engineering/wayfinder/SKILL.md (MIT); see THIRD-PARTY-NOTICES.`, second line `Sentinel: orchestra/references/wayfinder.md`. Full sha `49dd158d1076134a641b33efb035946536778336`. It holds: when to use it (large only, reached by escalation or an owner request, "Never start with the map"), the map file at `docs/maps/<name>.md` (destination, notes, decisions so far one line each with the ticket link, fog, out of scope), ticket types (research, prototype, grilling, task), "One human decision ticket per session", research tickets run together as `investigator` cards through Workflow, and hand-off to a designer-planner `plan` card when no fog remains. Under 5000 bytes.
11. **Version** `2.5.0` in `plugins/orchestra/plugin.json`, `plugins/orchestra/.claude-plugin/plugin.json`, `.claude-plugin/marketplace.json`.

## 3. State migration

No state file is rewritten. A 2.4 state has `items`, `route` and `route_log` entries `{items, reason, at}`; all stay valid and all 2.4 checks stay (`_check_items`, `_check_route`, `route --items`). Because the default policy and the role modes are unchanged (item 1), the policy hash binds it with no rebind.

**Fixture.** `tests/fixtures/state-2.4.json` is committed with `"repo": "@REPO@"` and `"base": "@BASE@"`, as `state-2.3.json` holds `@REPO@`. It is made once from a real 2.4 run, then scrubbed:
1. `git archive 3088dde plugins/orchestra | tar -x -C "$SCRATCH/v24"`; make a scratch git repo with one commit; run `python3.11 "$SCRATCH/v24/plugins/orchestra/scripts/orchestra.py" --repo "$SCRATCH/repo" start --items 3 --state "$SCRATCH/st"`; copy `$SCRATCH/st/state.json`.
2. Replace the repo path with `@REPO@` and the base commit with `@BASE@`. The file holds no personal path: `grep -c -e "/Users" -e "/private" -e "/tmp" tests/fixtures/state-2.4.json` prints 0.

`load_2_4_state(root, repo, name='state-2.4')` sits beside `load_2_3_state` (`tests/test_engine.py:21`). It fills `repo` with the resolved test repo and `base` with that repo's `HEAD`, writes `state.json`, and returns `(state dir, lease)`. `tests/test_integration.py` does not import from `test_engine.py`, so it carries its own six-line copy for `RouteCliIntegration`.

A 2.3 state still loads through the existing `load_2_3_state` tests, unchanged. The reverse direction does not hold: a 2.4 engine loads a 2.5 run silently (same policy hash, no `items`, so `engine.py:432,480` find nothing to refuse) and applies no routing check. R1's README note says so.

## 4. Tasks

Six tasks. Tier is the expected diff of the task itself. "Pin" marks a test that passes on the 2.4 code at the start; every other named test is written first and fails first.

| Task | Executor | Owns (exact) | Depends on | Tier |
|---|---|---|---|---|
| E1 | one builder (implementation) in a worktree | `plugins/orchestra/scripts/orchestra_core/engine.py`, `plugins/orchestra/scripts/orchestra.py`, `tests/test_engine.py`, `tests/test_integration.py`, `tests/test_hooks.py`, `tests/fixtures/state-2.4.json` | none | large (about 700 lines) |
| K1 | main session, inline | `plugins/orchestra/config/models.json`, `plugins/orchestra/config/roles.json`, `plugins/orchestra/scripts/generate.py`, `plugins/orchestra/agents/code-reviewer.md`, `.../code-reviewer-standards.md`, `.../code-reviewer-small.md`, `.../code-reviewer-medium.md`, `plugins/orchestra/skills/orchestra-review/references/final.md`, `tests/skill_phrases/orchestra-review.json`, `tests/test_packaging.py`, `docs/models.md`, `docs/roles.md`, `AGENTS.md` | none | medium (about 150 lines) |
| W1 | main session, inline | `plugins/orchestra/skills/orchestra/references/wayfinder.md`, `plugins/orchestra/THIRD-PARTY-NOTICES`, `docs/SKILL-SOURCES.md`, `tests/test_skills.py`, `tests/skill_phrases/orchestra.json` | none | medium (about 90 lines) |
| S1 | main session, inline | `plugins/orchestra/skills/orchestra/SKILL.md`, `.../references/coordination.md`, `.../references/triage.md`, `.../references/cli.md`, `.../references/final-review.md`, `.../references/repair-rounds.md`, `.../references/parallel.md`, `.../references/worktrees.md`, `plugins/orchestra/agents/orchestrator.md` (generated), `tests/skill_phrases/orchestra.json` | W1 (shares `orchestra.json`, links the reference); K1 (regenerates after `roles.json`); contract items 2 to 9 | medium (about 150 lines) |
| R1 | main session, inline | `plugins/orchestra/plugin.json`, `plugins/orchestra/.claude-plugin/plugin.json`, `.claude-plugin/marketplace.json`, `CHANGELOG.md`, `README.md`, `docs/cli.md`, `SPEC.md`, `tests/test_packaging.py` | E1 (merged), K1, W1, S1 | medium (about 90 lines) |
| B1 | coordinator live check | step 1 writes no repository file; step 2 owns `docs/BUILD-LEDGER.md` | R1 and the operator gate | tiny (about 30 lines) |

### E1: engine and CLI

Tests first (names).

`tests/test_engine.py`, class `SizeRouteTests`:
- start: `test_new_run_without_size_is_refused_naming_size`, `test_size_large_on_new_run_needs_owner_request_and_names_escalation`, `test_owner_request_allows_large_start`, `test_unknown_size_and_bad_asks_are_refused`, `test_start_flags_on_a_resumed_run_are_refused`
- session: `test_session_records_size_asks_and_owner_request`, `test_relaunch_keeps_size_asks_and_owner_request`, `test_state_with_items_and_size_together_is_invalid`, `test_bad_size_or_asks_in_state_is_invalid`
- route: `test_route_size_logs_size_asks_reason`, `test_route_size_without_asks_keeps_the_current_count`, `test_route_size_can_escalate_to_large_without_owner_request`, `test_route_size_refused_on_items_run`, `test_route_items_refused_on_size_run`, `test_route_size_refused_on_2_3_run`
- cards: `test_tiny_card_dispatch_needs_helper_reason`, `test_medium_card_dispatch_needs_no_helper`, `test_card_size_overrides_run_size`, `test_card_without_size_reads_the_run_tier_at_dispatch` (add on a tiny run, escalate to medium, dispatch with no helper), `test_large_run_card_defaults_to_medium`, `test_invalid_card_size_is_refused`, `test_card_size_on_items_and_2_3_runs_is_validated_and_ignored`, `test_inline_reservation_of_a_tiny_card_is_not_gated`
- plan card: `test_plan_card_refused_on_tiny_and_medium_run`, `test_plan_card_allowed_on_large_run`, `test_plan_card_allowed_with_session_owner_request`, `test_plan_card_allowed_with_task_owner_request`

`tests/test_engine.py`, class `PrePrTests`:
- `test_budget_is_guide_times_asks`, `test_over_budget_warns_with_both_sizes_and_succeeds`, `test_within_budget_has_no_warning`, `test_route_to_a_fitting_tier_clears_the_warning` (and a route that still leaves the diff over budget keeps it), `test_large_run_has_no_budget`, `test_items_run_gets_no_size_check`
- `test_prepr_without_a_base_reports_nulls_and_the_full_reviewer` (the 2.3 fixture), `test_prepr_on_a_state_with_no_session_reports_nulls`
- `test_reviewer_bands_at_50_51_400_401`, `test_reviewer_follows_summed_lines_not_largest_ask`, `test_untracked_files_count_toward_changed_lines`, `test_prepr_writes_no_state`

`tests/test_engine.py`, class `LegacyStateTests` (existing class): `test_2_4_state_loads_and_keeps_2_4_routing` (through `load_2_4_state`: the inline route still refuses a builder dispatch without `--helper`, `route --items` still works), `test_2_4_fixture_holds_only_placeholders`, and two pins: `test_2_4_policy_and_contract_hash_are_pinned` (both values from item 1) and `test_one_combined_receipt_covers_all_required_categories`. The existing 2.4 `RouteTests` stay, except the `require_items` cases become `require_size` cases.

`tests/test_integration.py`, class `SizeCli`:
- `test_start_without_size_exits_nonzero_naming_size`, `test_start_size_large_exits_nonzero_naming_escalation`, `test_start_size_medium_with_asks_prints_a_lease`, `test_start_items_is_refused_pointing_to_size`, `test_start_flags_on_a_resumed_run_exit_nonzero`
- `test_new_run_with_bad_size_asks_or_large_leaves_the_ended_run_in_place` (the ended run is not archived)
- `test_route_needs_exactly_one_of_size_or_items`, `test_route_size_logs_and_exits_zero`
- `test_dispatch_tiny_card_without_helper_exits_nonzero`, `test_dispatch_medium_card_exits_zero`
- `test_prepr_over_budget_prints_warning_and_exits_zero`, `test_prepr_names_the_reviewer_agent_for_each_band`, `test_prepr_on_a_2_3_state_exits_zero_with_nulls`

Existing tests that start a run with `--items N` (`test_integration.py` lines about 45, 85, 155, 346, 361, 394 to 396; `test_hooks.py` about 1135, 1447, 1463) move to `--size medium`. `RouteCliIntegration` (about 688 to 742) now writes the 2.4 state through its local `load_2_4_state` copy and runs the same 2.4 route checks against it. In `tests/test_hooks.py`, a pin: `test_reviewer_test_block_covers_the_size_variants` (agent types `orchestra:code-reviewer-small` and `-medium` get the same test-suite denial as `orchestra:code-reviewer`; the prefix match already covers them).

Acceptance:
- `python3.11 -m unittest tests.test_engine tests.test_integration tests.test_hooks` exits 0.
- On a new scratch repo, `python3.11 plugins/orchestra/scripts/orchestra.py --repo $SCRATCH/repo start` exits 2 and the message names `--size`; `... start --size large` exits 2 and the message names `escalate`.

### K1: reviewer-model selection (inline)

How a pre-PR reviewer gets its model today: the coordinator dispatches the agent file `orchestra:code-reviewer` (Opus 5.5 medium, from `config/models.json`) and `code-reviewer-standards` for the standards lens; `generate.py` writes one agent per non-default preset in `variants_of`. 2.5 adds two presets, so the generator emits two new files; `prepr` names which one to dispatch.

Tests first, in `tests/test_packaging.py`: `test_reviewer_size_variants_are_generated` (small is `claude-haiku-5-5` high, medium is `claude-sonnet-5-5` medium, both in the expected agent set), `test_reviewer_size_variants_keep_the_reviewer_tools` (`Read`, `Bash`, no write tool). In `tests/skill_phrases/orchestra-review.json`: add `Lens: combined` and `Required categories:`. The existing generated-agents-match test is a pin.

Edits: the two presets; `VARIANT_NOTES` for `('code-reviewer', 'small')` and `('code-reviewer', 'medium')`; the `roles.json` code-reviewer prompt names the combined lens; `final.md` gets the combined-lens paragraph (contract item 9; cap 6144 bytes, now 3796); `docs/models.md` and `docs/roles.md` list the two reviewers; the `AGENTS.md` model sentence becomes: "Opus 5.5 medium for the final reviewer above 400 changed lines and for builder repair; Sonnet 5.5 medium for the final reviewer from 51 to 400 lines, builders, the standards lens and docs investigator; Haiku 5.5 high for the final reviewer up to 50 lines, mechanical and cleanup builders, operator and code discovery."

Acceptance:
- `python3.11 plugins/orchestra/scripts/generate.py` then `python3.11 plugins/orchestra/scripts/generate.py --check` exits 0.
- `python3.11 -m unittest tests.test_packaging tests.test_skills` exits 0. K1 leaves the version and changelog assertions in `test_packaging.py` to R1.
- `wc -c plugins/orchestra/agents/code-reviewer-*.md`: each at most 2650 bytes; the agents total stays under 32000.
- `grep -c "final reviewer up to 50" AGENTS.md` prints 1.

### W1: wayfinder reference and credit (inline)

Tests first: `tests/test_skills.py` adds `references/wayfinder.md` to the `orchestra` list in `TABLE`, moves the distinct-sha count from 6 to 7 (`assertEqual(len(shas), 7, shas)`), and keeps the "Permission is hereby granted" count at 5 (no new license block; same license text as the first pin). `tests/skill_phrases/orchestra.json` adds `Sentinel: orchestra/references/wayfinder.md`, `docs/maps/`, `One human decision ticket per session` and `Never start with the map`.

Edits: the new reference (contract item 10); `THIRD-PARTY-NOTICES` gets a "mattpocock/skills (third pin, Orchestra 2.5.0)" section with `Commit: 49dd158d1076134a641b33efb035946536778336` and `Used for skills/engineering/wayfinder`, in the style of the second-pin section; `docs/SKILL-SOURCES.md` gets a matrix row `Pocock (2.5 pin) | mattpocock/skills | 49dd158d1076134a641b33efb035946536778336 | mattpocock/skills@49dd158d1076:<path> | MIT (Matt Pocock)`, a topic row for large-work mapping, and a file row `orchestra/references/wayfinder.md`. Read the upstream skill at the pinned sha, never `origin/HEAD`: `git -C <local mattpocock/skills clone> show 49dd158d1076134a641b33efb035946536778336:skills/engineering/wayfinder/SKILL.md`. Write it in our own words.

Acceptance: `python3.11 -m unittest tests.test_skills` exits 0; `wc -c plugins/orchestra/skills/orchestra/references/wayfinder.md` under 5000.

### S1: routing text (inline, after K1 and W1)

Tests first: `tests/skill_phrases/orchestra.json` swaps the phrases `` `start --items N` `` and `` `dispatch --helper REASON` `` for `` `start --size` ``, `` `route --size` ``, `` `prepr` ``, `Tiny unit`, `Lens: combined`, `references/wayfinder.md`, `largest ask` and `by file`.

Edits:
- `SKILL.md`: the Route section becomes the tier table (tiny: inline edit, no alignment; medium: grill inline, then execution; large: escalation only, wayfinder) and points to `references/triage.md` for sizing. Net change at most +136 bytes (cap 4096, now 3960). Add `references/wayfinder.md` to the reference list.
- `triage.md` (new section "Size and align"; cap per `test_skills.py`, aim under 5000 bytes) holds the procedure, which `SKILL.md` and `coordination.md` cannot carry in their budgets:
  - Sizing an unknown area: read the files the work touches; if the area is unknown, start one `investigator-code` card, or a Workflow fan-out of `investigator-code` cards, one per area, each returning a size estimate and the files found.
  - Counting asks: `--asks` counts separately stated asks; the tier is the largest single ask; the budget is the guide times the count.
  - Grouping tweaks by file: tiny tweaks form one group per file and the main session does them in one serial pass.
  - Escalation: tiny to medium when the edit needs a decision or the diff passes the guide; medium to large when grilling passes the context ceiling (40% to 60% of the window) or answers open questions faster than they close; the command is `route --size TIER --reason TEXT`.
  - Grilling rules: main session only, never a worker; questions in frontier rounds, each with a recommended answer; settled terms go to the glossary; hard-to-reverse choices become decision records.
- `coordination.md`: lane row `plan` reads "Approved substantial design, a large run, or an owner request"; add the question-2 executor rule in short form. No four-word phrase shared with `SKILL.md`; growth at most 1490 bytes so `orchestrator.md` stays at most 10500 (now 9010; regenerated by `generate.py` after K1).
- `cli.md`: `start --size`, `--asks`, `--owner-request`, `route --size`, the tiny-card `--helper` rule, the plan-card rule, `prepr` with its JSON fields and warning text; 2.4 rows marked "2.4 runs only".
- `final-review.md`: step 1 runs `prepr`, step 2 dispatches by `agent` (small or medium: one card with `Lens: combined` and the `Required categories:` line; full: one card per lens). Line 31's `git diff --shortstat BASE..HEAD` becomes the `changed_lines` that `prepr` reports, so the specialist threshold uses `_changed`.
- `repair-rounds.md` line 11 (row 2): on a size run the repair card carries `"size": "medium"` or is dispatched with `--helper REASON`; on a 2.4 run `--helper REASON` as before. Row 3 names the fix re-review agent (contract item 8).
- `parallel.md` line 14: the agent-file list gains `code-reviewer-small` and `code-reviewer-medium`.
- `worktrees.md`: "1 to 5 items / 6 or more" becomes the tier and unit rule.

Acceptance: `python3.11 plugins/orchestra/scripts/generate.py --check` exits 0; `python3.11 -m unittest tests.test_skills tests.test_packaging` exits 0; `grep -rn -e "--items" plugins/orchestra/skills` lists only lines marked 2.4.

### R1: release surface (inline)

Tests first, `tests/test_packaging.py`: version `'2.5.0'`, changelog heading `## 2.5.0`, and `test_prepr_reviewer_agents_exist` (import `REVIEWER_BANDS` and `REVIEWER_FULL`, assert each named agent file exists: the cross-check between E1 and K1).

Edits: three manifests to 2.5.0; `CHANGELOG.md` section `2.5.0` (route by size, `--size` and `--owner-request`, `prepr` size check, reviewer by summed diff, wayfinder, 2.4 runs keep item routing); `README.md` quick start and routing paragraph (`start --size`) plus the upgrade note: "A run started under 2.4 loads under 2.5 and keeps item routing; new runs use `--size`; `--items` is refused on `start`. Do not resume a 2.5 run with a 2.4 engine: 2.4 loads it without a routing check."; `docs/cli.md` rows for `start`, `route`, `add`, `dispatch`, `prepr`; `SPEC.md` line 13 version text if it names 2.4.

Acceptance (derived set; the full suite runs once, at the operator gate):
- `python3.11 -m unittest tests.test_packaging tests.test_skills` exits 0.
- `python3.11 plugins/orchestra/scripts/generate.py --check` exits 0.
- `python3.11 scripts/build_release.py` exits 0 and names `orchestra-2.5.0`.

### B1: benchmarks before the merge (owner decision O1)

Runs on the merged `v2.5` candidate after R1 and after the operator's full-suite gate, before the pre-PR review, and edits no repository file in step 1. A failure blocks the merge.

**Pre-merge load path (does not touch main or the installed plugin).** `claude --plugin-dir "$V25/plugins/orchestra"` loads the branch checkout for that session only; `$V25` is the `v2.5` checkout. No `claude plugin update`, no marketplace change. The installed 2.4.0 stays as it is. Before each run, check which copy loaded: run with `--output-format stream-json --verbose` and read the orchestra plugin path from the init event, or run with `--debug` and find `Plugin "orchestra" from --plugin-dir overrides installed version` in the log under `~/.claude/debug/` (headless `--output-format json` does not show hook context). The path must be under `$V25`, not the 2.4.0 cache path; if two `orchestra` plugins load, or the cache path shows, stop: the run would measure 2.4. (2.4.0 was installed after the merge with `claude plugin marketplace update orchestra-distribution` then `claude plugin update orchestra@orchestra-distribution`; that step comes after this plan's merge.)

1. **Three tiny edits** (acceptance 6), once. Base: a scratch clone checked out at `e43a7bc`, the base of the 2.4 rerun (`docs/BUILD-LEDGER.md:175`): the FC3 tag in `hooks.py` and `tests/test_hooks.py`, and the E1 labels in `docs/SKILL-SOURCES.md`. Run `claude -p --plugin-dir "$V25/plugins/orchestra" --model claude-opus-5-5 --output-format json` with a prompt that states those edits. The 2.4 prompt and permission flags are not recorded; B1 records the ones it uses. The prompt makes the coordinator `start --size tiny --asks 3`.
   - Pass when both hold: no builder card with `inline: false` (count from `state.json`, path from `where`: `python3.11 -c` filter on `tasks` with `role == 'builder'` and `inline is False`; must print 0), and sub-agent tokens at most 35,990.
   - Sub-agent tokens: the sum of `subagent_tokens` from the session's agent notifications, the 2.4 definition behind 35,990, supplied by the coordinator. Do not sum per-turn transcript usage: it counts the context again on every turn.
   - Report, not pass criteria: reviewer cards started (expect 1, `orchestra:code-reviewer-small`), `prepr` output, wall time.
2. **Two medium units on disjoint files** (acceptance 7). B1 writes the two unit briefs into the scratch notes before the first run, each naming its files, behavior and test command, each about 250 to 400 changed lines with tests (for example a CSV-to-markdown table converter and a semver range parser as new modules). The briefs are identical in every run, in scratch clones at one base. Four runs: the serial arm twice (the main session does unit A then unit B inline, `--size medium --asks 2`) and the parallel arm twice (one Workflow builder on unit A in a worktree, the main session inline on unit B). Wall time is `duration_ms` from the JSON output. Compare the better of two runs of each arm. Pass when the parallel arm's better time is under the serial arm's. Report all four times and the token cost of each.
3. After the merge, record both tables in `docs/BUILD-LEDGER.md` in a separate docs-only commit on main, as 2.4 did. That commit is outside the reviewed PR.

Failure routing: a builder started on the tiny run returns to S1 (text) or E1 (check); tokens over 35,990 or a parallel arm that is not faster go to the owner as a result, not to a builder. A repair after the pre-PR review that touches `engine.py`, `orchestra.py` or skill routing text reruns the tiny benchmark.

## 5. Dependency graph and parallel groups

```
E1 ----------------------\
K1 -> W1 -> S1 -> R1 -> merge E1 -> operator gate -> B1 -> pre-PR review -> merge to main -> ledger commit
```

R1 needs E1 merged into `v2.5` (its test imports engine constants). K1 and W1 are independent and are done in either order inline; S1 follows both (it shares `orchestra.json` with W1 and regenerates `orchestrator.md` after K1's `roles.json`). No cycles.

- **Parallel:** E1 runs beside the main-session chain K1, W1, S1. Nothing else runs concurrently. The design's question 2 allows exactly this: one not-tiny unit with a worker (it runs beside other work and protects the coordinator's context) and the rest inline.
- **Worktrees:** one, for E1 (a concurrent writer on files disjoint from the main checkout). K1, W1, S1 and R1 are one writer in sequence in the main checkout. Remove E1's worktree after the merge, after inspecting the directory.
- **Run record:** this build runs on the installed 2.4 engine, so `start --items 5` (five code tasks, inline route). Dispatch E1 with `--helper "independent unit beside other work"`.

## 6. Ownership check

| File | Tasks (order) |
|---|---|
| `engine.py`, `orchestra.py`, `tests/test_engine.py`, `tests/test_integration.py`, `tests/test_hooks.py`, `tests/fixtures/state-2.4.json` | E1 |
| `config/models.json`, `config/roles.json`, `generate.py`, `agents/code-reviewer*.md`, `orchestra-review/references/final.md`, `skill_phrases/orchestra-review.json`, `docs/models.md`, `docs/roles.md`, `AGENTS.md` | K1 |
| `references/wayfinder.md`, `THIRD-PARTY-NOTICES`, `docs/SKILL-SOURCES.md`, `tests/test_skills.py` | W1 |
| `tests/skill_phrases/orchestra.json` | W1, then S1 (S1 depends on W1) |
| `SKILL.md`, `coordination.md`, `triage.md`, `cli.md` (skill), `final-review.md`, `repair-rounds.md`, `parallel.md`, `worktrees.md`, `agents/orchestrator.md` | S1 |
| `tests/test_packaging.py` | K1, then R1 (R1 depends on K1) |
| three manifests, `CHANGELOG.md`, `README.md`, `docs/cli.md`, `SPEC.md` | R1 |
| `docs/BUILD-LEDGER.md` | B1 (step 3) |

No file appears in two tasks without a dependency. `docs/PLAN-v2.5.md` belongs to the planner only. `agents/orchestrator.md` and `agents/code-reviewer*.md` come from the same generator in different tasks; the files are disjoint.

## 7. Pre-flight rows

| Producer | Consumer | Produces / consumes | Finding |
|---|---|---|---|
| E1 | S1, R1, B1 | CLI names, error texts and the `prepr` JSON (items 2 to 7) | Fixed by the contract text. S1 and R1 quote it verbatim; no shared file. |
| E1 | R1 | `REVIEWER_BANDS`, `REVIEWER_FULL` | Named in item 1; R1 runs after the E1 merge. |
| K1 | E1 | Agent names `orchestra:code-reviewer-small` and `-medium` | E1 holds them as strings in `REVIEWER_BANDS`. R1's `test_prepr_reviewer_agents_exist` checks the files exist after merge. |
| K1 | S1 | `Lens: combined`, `Required categories:`, `generate.py` output | S1's `final-review.md` quotes them; phrase tests cover both; S1 regenerates `orchestrator.md` after K1. |
| W1 | S1 | Path and sentinel of `wayfinder.md`, `orchestra.json` | Ordered by dependency. |
| E1 | E1 | `load_2_4_state` in `test_engine.py` and its copy in `test_integration.py` | Same task; both read the one fixture and fill the same two placeholders. |
| none | none | E1 and K1; E1 and W1; E1 and S1 | Share nothing. |

## 8. Gaps and design notes (not decided here)

- **Mechanisms chosen:** the `prepr` command and JSON (accepted by the critic); a plan card allowed by a session or task `owner_request`; no `route` field on size runs; the fix re-review agent follows the pre-PR band; `route --size` refused on a 2.3 run; the resumed-run flag message.
- **`asks` is declared by the coordinator.** The engine cannot count asks, and a large `--asks` weakens the warning. This is a convenience check, not isolation.
- **Sensitive paths under D3.** A 10-line change in `auth/` gets the Haiku reviewer. The combined review must still report `security` when `required_lenses` lists it, so completion is not weakened, but D3 sets no floor.
- **Measuring limits** (item 7): untracked binaries count by `splitlines()`, tracked binaries count 0, lockfiles and generated files count (a large lockfile moves the review to Opus). No new policy key, because it would change `policy_hash`.
- **Benchmark inputs:** the 2.4 prompt, permission flags and token definition are not in the repository; the coordinator supplies them to B1, and B1 records them in the ledger. Acceptance 7 compares the better of two runs per arm; run-to-run noise is still large.
- **Not enforced by the engine:** a large run does not require an accepted plan card before builders.
- **B1 and the installed plugin:** whether `--plugin-dir` shadows the installed same-name 2.4.0 plugin was not tested while planning; B1's skill-path check settles it, and a failed check is a gap to report, not a pass.

## 9. Acceptance map

| Design acceptance | Task | Evidence |
|---|---|---|
| 1. `start` without `--size` exits non-zero naming `--size` | E1 | `test_start_without_size_exits_nonzero_naming_size` and the engine twin |
| 2. `start --size large` refused without `--owner-request`, names escalation | E1 | `test_start_size_large_exits_nonzero_naming_escalation` |
| 3. Over-budget diff warns at the pre-PR step and succeeds | E1 (S1 documents the step) | `test_prepr_over_budget_prints_warning_and_exits_zero` |
| 4. Tiny unit dispatch needs `--helper`; medium succeeds | E1 | `test_dispatch_tiny_card_without_helper_exits_nonzero`, `test_dispatch_medium_card_exits_zero` |
| 5. 2.4 state keeps 2.4 routing; 2.3 state still loads | E1 (R1 notes it in README) | `test_2_4_state_loads_and_keeps_2_4_routing`, `RouteCliIntegration` on the fixture, existing 2.3 `LegacyStateTests` |
| 6. Three tiny edits: 0 builders, tokens at most 35,990 | B1 step 1 (needs E1, K1, S1, R1) | pass criteria in B1 |
| 7. Two disjoint medium units finish faster in parallel than serial | B1 step 2 (needs E1, S1, R1) | pass criterion in B1 |

Other required content: engine and CLI, E1; 2.4 `items` migration, section 3 and E1; reviewer model selection, K1 and contract items 1, 7 to 9; routing text, S1; wayfinder and its credit, W1; version, R1; CHANGELOG, R1; README upgrade note, R1; benchmark checks, B1; `AGENTS.md` model sentence, K1.

## 10. Place the reviews

One pre-PR review covers the single v2.5 PR (E1, K1, W1, S1, R1 merged), after B1 passes. The operator gates the full Python suite once on the merged candidate (`python3.11 -m unittest discover -s tests`, `generate.py --check`, `build_release.py`). The change is over 400 lines, so under D3 the reviewer is the Opus 5.5 with lenses: correctness always, standards (over 200 lines), and security only if a changed path matches `sensitive_paths` (the plan changes none: `tests/test_hooks.py` is not a `hooks/` directory). A blocked finding on engine code returns to E1; on agents, models or `final.md` to K1; on skill text to S1; on the reference or credits to W1; on release files to R1. B1 is the only live check; its exact steps are above. Optional full-suite testing stays on the owner's trigger.

## 11. Self-check

- Every design acceptance item and decisions D1 to D5 map to a task (sections 4 and 9); the owner decision O1 moves B1 before the merge.
- Names agree across tasks through section 2.
- E1 is the largest unit (about 700 lines); engine, CLI and their tests cannot be split without sharing files.
- Every task has an owner, acceptance commands and a done contract: the report shows the named tests passing with command and exit code.
- A substantial plan needs an independent critic before any build starts.
