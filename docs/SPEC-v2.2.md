# Orchestra 2.2.0 design specification

Card D4, mode design: the third revision of the card D1 draft (commit `15ba4e79`), after the round-1 critics (C1, C2F), the round-2 critics (C3 spec lens, C4 feasibility lens) and the round-3 critics (C5 spec lens, C6 feasibility lens; amendment of commit `9d6ddba1`). Base: `origin/main` at `0e778c73292d72dbc4ce9a6d725c97cb72bc1d31` (Orchestra 2.1.0, tag `v2.1.0`). All citations are to that commit and are relative to the repository root. The plugin root is `plugins/orchestra`; `P/` below abbreviates it.

This revision adopts the user's held repair model (Round 2), the Round 3 rulings (an uncapped final repair loop, the materiality rule, and full autonomy for this run), the Coordinator ruling on release pre-authorization and the coordinator decisions on the round-2 and round-3 findings. It resolves every critic finding (section 12) and removes what the held model makes unnecessary (section 11). No decision is left open: section 10 lists the accepted answers, every override of them and each choice decided by coordinator recommendation.

## 0. Evidence labels and do-not-touch list

Every factual claim carries one label:

- **OBSERVED**: read in the file at the cited line, or seen in a command run in this assignment or the D1 assignment (git 2.50.1, Python 3, Node).
- **REASONED**: inferred from observed facts. The inference is stated.
- **UNKNOWN**: not established. The section says what settles it.

Proposals for 2.2 behavior are design, not claims. They are written as "New:".

**Do not touch, for this card:** every path except `docs/SPEC-v2.2.md`.

**Do not touch, for the 2.2 build cards that follow:**

- the downstream application repositories, including their copies of the old relaunch script
- the installed plugin cache
- the uncommitted files in the main checkout (the `AGENTS.md` and `.gitignore` edits and the untracked `.agents/skills/e2e/`)
- other sessions' worktrees
- the read-only source reference repositories named in `docs/SKILL-SOURCES.md`
- `docs/SPEC-v2.md` and `docs/PLAN-v2.md`, the historical 2.0 records

`CONTEXT.md` is not owned by this card. A later card copies the glossary below into it if the user wants that.

## 1. Glossary

| Term | Meaning in 2.2 |
|---|---|
| Wave | A named set of builder implementation cards that run together and are reviewed together, joined through the card's `wave` field. Waves are ordered by the first `add` of each label. |
| Wave review | One checkpoint-mode code-reviewer card whose `review_of` covers every builder implementation card of one wave. Its findings are attributed per card. |
| Repair-diff check | The one checkpoint review of a wave's repair commits: a checkpoint receipt whose coverage includes a builder repair card. Its `review_of` covers each repair card, that card's chain ancestors, and each card whose wave findings were all rejected. Its blocking findings sit on chain tips. |
| Chain | A builder card and the repair cards linked to it through `repair_of` / `repaired_by`. The chain tip is the newest card, the one without `repaired_by`. |
| Held | The task state of a chain that still fails after its Opus repair and repair-diff check, or of an unrepaired card the repair-diff check blocks. Its work stays integrated. It blocks nothing until the final phase, and it must be accepted before completion. |
| Held log | The `held_finding` on each held card plus one line per hold, and per gate failure attributed to a held tip, in `<state>/progress.md`. |
| Cleared | A final receipt's `cleared` entry: a held tip the lens checked and found no longer failing in its categories, with the reason. |
| Superseded review | An unstarted review card whose every target an accepted newer review card covers; `supersede` accepts it with `superseded_by`. |
| Release pre-authorization | The optional ledger line `- Release: pre-authorized <remote> <target>` that lets an armed run release that one configured target. |
| Final phase | Operator gate, three parallel lens cards, then final repair rounds until every lens is CLEAN on the current candidate. |
| Final repair round | One Opus repair card per chain with a current attributed final finding, held or not, then a re-check by each failed lens of only the still-failing items. |
| Closing confirmation | One final receipt by a lens whose last CLEAN receipt went stale during the final repair rounds, over the cumulative final-repair diff. |
| Finding | A blocking issue: severity `blocking`, with a stated material impact on a named requirement, test or framework (section 5.6). Receipts covering cards added under 2.2 carry them in `issues`. |
| Note | A non-blocking issue: severity `note`. It goes to the run brief and never triggers repair or hold. |
| Fingerprint | The first 12 hex digits of SHA-256 over a finding's text, lowercased with whitespace collapsed. It keys triage entries. With the chain id and lens category it detects a repeated finding across final rounds. |
| Run brief | The report written to `<state>/progress.md` on every session end path and every autonomy stop, shown at SessionStart and printed by `orchestra.py brief`. It replaces the 2.1 "Autonomy report". |
| Findings ledger | The `findings` list in `state.json`: each finding the coordinator rejected, deferred or triaged, with the reason. It is distinct from the progress ledger, the autonomy ledger and the critic `ledger` axis. |
| Out-of-scope finding | A defect outside the change under review. Only final lens cards raise it, in `out_of_scope`. It never blocks a verdict. |
| Triage | The coordinator's disposition of an out-of-scope finding: `inline`, `card` or `brief`. |
| Lens card | One final-review code-reviewer card with a `Lens:` line. |
| Standards lens | The final lens for repository rules, the charter and cleanliness (`P/skills/orchestra-review/references/standards.md`, new), run on Sonnet medium. The critic `standards` axis is separate and stays. |
| Evidence reuse | Reviewers cite the operator's gate receipts on the same artifact instead of rerunning the suites. |
| Keep/remove lists | Two sections in a builder brief that name exactly what must survive and what must go. |
| Relaunch harness | `orchestra.py relaunch`: a loop that starts one fresh headless coordinator pass after another until the autonomy run stops. |
| Progress signature | A digest of engine state. A pass that leaves it unchanged is a stall. |
| Merged branch | A branch whose tip is an ancestor of the default branch, or whose tree equals the tree of a recent first-parent commit of the default branch, or which is an ancestor of a branch that meets the tree test. |
| Abbreviated long option | A unique prefix of a git long option, which git's parse-options accepts (for example `--al` for `--all`). |

## 2. Binding inputs

**Settled decisions S1 to S7 (handoff, fixed):**

- **S1:** Wave-level review, not per-ticket: builders finish a wave, then one wave reviewer, then builders fix, then one check of the repair diff only. One loop per wave.
- **S2:** Repair escalation is Sonnet builder, then Opus builder `repair`, then park. A cap never stops or blocks a run. No "march of nines".
- **S3:** A parked ticket stays out of the PR, on its own branch, and goes into the user's brief.
- **S4:** Gate between waves only when the next wave depends on the previous wave's code.
- **S5:** Final review is parallel lenses. Correctness and security run on Opus high; the standards/charter lens runs on Sonnet medium.
- **S6:** Out-of-scope findings are raised only at the final review. The coordinator triages each into one of three: fix inline, a new card/batch/plan, or the user's brief.
- **S7:** No lost functionality. Every change keeps existing behavior or names its replacement.

**Round 2 (user, supersedes S2's "park" rung and S3):** two tries per ticket, then the ticket is held. Held work stays in the normal integration: no separate branch and no throwaway wave branch. It is logged, the run continues, and nothing waits on it. At the end, the final lenses run on the integrated candidate, and every held item plus every lens defect is fixed together in Opus repair. Every run writes a brief, and the PR body gets a "Held / next phase" section. "Fixed" is judged against the requirements, tests and frameworks the prompt names. If the guard fail-closed bug does not reproduce, the hardening ships and the gap goes in the CHANGELOG.

**Round 3 (user, supersedes Round 2 items 3 and 7):**

1. The final repair loop has no count limit. Anything still failing is repaired again until it passes. Each round re-checks only the still-failing items. A finding that comes back unchanged gets a fresh approach: investigator re-diagnosis, then repair. The run deadline is the only outer limit. The merge-block recommendation is dropped.
2. Materiality: a finding blocks only with a real, material impact on the named requirements, tests or frameworks. No impact, or under about 20% impact on otherwise mostly correct work, makes it a note. The rule lives in the reviewer and critic skills, the review report schema and the engine's BLOCKED rule.
3. Full autonomy for this run. No decision stays open.

**Coordinator ruling (handoff, 2026-10-05, verbatim):** "Approval boundaries stay hard by default under armed autonomy, but the autonomy ledger may pre-authorize release explicitly (its approval-boundaries field names "release: pre-authorized" plus the exact remote/target). With that line, an armed run releases at the end through the permit with no user input (Round 2 "seamless"); without it, the run ends "ready to release" in the brief. Never inferred, never default."

**Carried from the standing orders into every build card:** tests come first for new behavior; stage explicit paths only; Opus 5.5 and Sonnet 5.5 only, with no 1M-context variants; the repository never names local home paths or downstream product names (charter).

## 3. Scope map

| Handoff scope bullet | Heading |
|---|---|
| Review and repair model (S1 to S6), engine `review_of` on a wave and the failed-ticket state | 5.1 to 5.7; engine in 6; models in 7 |
| Autonomy: continue past failed cards, deadline as the only limit | 5.8 |
| Autonomy: the brief | 5.9 |
| Autonomy: fresh-context relaunch replacing the downstream relaunch script | 5.10 |
| Efficiency: evidence reuse, findings ledger, keep/remove lists | 5.11, 5.12, 5.13 |
| Guard: merged-branch deletion, abbreviated options, fail-closed | 5.14, 5.15, 5.16 |
| Engine fix: read-only reviews collide | 5.17 |
| Release: 2.2.0 version and changelog | 5.18 |
| Follow-up: this repository's merged branches | 5.19 |
| T3 Code support; downstream repositories | 13 |

## 4. Test conventions

- **Python:** `python3 -m unittest discover -s tests -k <test_name>` from the repository root. The full suite is `python3.11 -m unittest discover -s tests` (README.md:92, OBSERVED).
- **TypeScript guard and mods:** `claude plugin test` with function hooks enabled (docs/VALIDATION.md:42, OBSERVED). Test names are the `test('<name>', ...)` titles.
- **Guard corpus:** cases go in `P/config/guard-corpus.json`. `tests/test_guard_corpus.py` and `P/hooks/mod/guard.test.ts` check parity in both guards.
- **Skill text:** phrase files under `tests/skill_phrases/`, checked by `tests/test_skills.py`.
- **Ordering:** each listed test fails on the base commit and passes after the change, unless it is marked "regression (passes today)".

## 5. Change set

### 5.1 Wave review and the repair-diff check (S1)

**Current (OBSERVED):**

- coordination.md:31 lists the states and has no wave concept. coordination.md:38-40 groups low-risk tickets under one review and gives a per-ticket example.
- `review_of` is already a list of task ids (engine.py:559-567).
- `record_review` stores one `findings` list for all covered tasks (engine.py:734-773), and `_review_verdicts` applies it to each of them (engine.py:775-796). REASONED: one finding in a group review blocks `accept` of every covered card (engine.py:806-807).
- Adding a repair sets every chain ancestor to `repairing` and resets its `review_since` (engine.py:584-586). `accept` of a builder then needs a newer verdict (engine.py:808-809). tests/test_engine.py:522-548 pins this. tests/test_engine.py:617-639 also adds a build-phase repair of a repair, which 2.2 refuses; it is a flip (5.2, C6/R3-2).

**New:**

1. A builder implementation card may carry `wave` (a non-empty string). `add` refuses `wave` on any other card: "Only builder implementation cards join a wave". Repair cards never carry a label, so the reviewed-wave refusal below never blocks a repair (N4).
2. A review card may name `"wave:W"` in `review_of`. `add` resolves it to the ids of every card labelled W, freezes the list and stores plain ids (N3). `add` of a W card after a W review exists is refused: "Wave W already has a review; start a new wave".
3. Wave order is the order of each label's first `add`. `status` lists waves in that order (S-g).
4. The wave review is code-reviewer `Mode: checkpoint` over the wave. Its report may carry `task_findings`, which maps each covered id to that card's blocking findings:
   - `record_review` refuses a key that is not covered (except a held tip, 5.4 item 3), or an ordered union of the values that differs from `findings`.
   - **Per-task findings (C4/R2-2):** a receipt's findings for task T are `task_findings[T]` when `task_findings` exists; an empty list or an absent key means CLEAN for T. Without `task_findings`, the 2.1 rule holds: every covered card gets the whole list. One helper, `_task_findings(receipt, T)`, serves all five readers: the verdict in `record_review` (engine.py:762-764), `_review_verdicts` (775-796), the repair precondition (577-579), `accept` (805-806) and the per-task completion loop (914-918). engine.py:749 is the final coverage check, not a findings reader (C6/R3-8).
   - The O22 void (engine.py:790) applies per task: a stale newest receipt voids T's verdicts only when its findings for T are non-empty. The final computation (`final=True`) keeps the whole-receipt rule.
5. The coordinator tries to refute each finding (coordination.md:48). A refuted finding is recorded as `rejected` in the findings ledger (5.12). Each card with a remaining finding gets one Opus repair card (5.2), added after the accept step of item 10.
6. After the repairs report, one repair-diff check runs. Its `review_of` lists, in one card:
   - every repair card of the wave and each one's chain ancestors (B2, F1)
   - every wave card whose wave findings were all rejected in the ledger (S-d)

   Its brief names the fix range and the rejected findings. The check gives each ancestor a verdict newer than its `review_since`, so the original can be accepted after its repair. Tip rule (C3/R2-4): a BLOCKED check must carry `task_findings`, and every key with a non-empty list must be a chain tip: "Attribute repair-diff findings to the chain tip X".
7. One loop per wave: no third review of that wave runs. A chain that still has a blocking finding after the check is held (5.2), including a rejected-only card the check blocks (5.2 item 2b).
8. A consequential foundation becomes a wave of one, reviewed before dependent waves start.
9. A wave member parked at an approval boundary (2.1 `park`) before its wave review runs would leave the review never ready. The coordinator then parks the queued wave review and adds a replacement review whose `review_of` names the other members explicitly (S-a, F5). The parked member, once unparked, gets its own explicit review. The parked original is then cleared with `supersede` (item 11).
10. **Accept before repair (C3/R2-5, C4/R2-4).** After any review receipt, in the build and in the final phase, the coordinator works in this order: record ledger rejections, accept every card that is acceptable now (CLEAN members, the review card, investigator cards), then add and dispatch repairs. A repair lands in the shared tree, so it would make whole-repository report artifacts and wave-scope receipts stale. The engine enforces it: dispatching or starting a builder repair card is refused while any `reported` card passes every `accept` check: "Accept X first; a repair would make its evidence stale". **Park instead (C6/R3-7):** a read-only evidence card (investigator, critic) whose coordinator inspection (cli.md:14) is not done may be parked instead of accepted before the repair dispatches; a parked card is not `reported`, so the refusal no longer names it. Unparked after the repair, it accepts only if its scoped artifact is still current (engine.py:811), otherwise it is re-dispatched (REASONED).
11. **Supersede (C3/R2-10).** `orchestra.py supersede TASK` needs the lease. It accepts TASK and stores `superseded_by` (the covering ids) only when TASK is a review-role card with `review_of`, in state `queued` or `parked`, never dispatched (no `worker`), and every id in its `review_of` is in the `review_of` of an `accepted` review card added after it. Otherwise refused, naming the uncovered id. The brief lists it under Accepted as "superseded by".

**Files:** `P/scripts/orchestra_core/engine.py` (`add_task`, `record_review`, `_task_findings`, `_review_verdicts`, `accept`, `_start_assignment`, `supersede`, `_completion_evidence`); `P/scripts/orchestra.py` (`add` help, `status` waves, `supersede`); `P/skills/orchestra/references/coordination.md`; `P/skills/orchestra-review/references/checkpoint.md`; `P/skills/orchestra/references/cli.md`, `docs/cli.md`; `tests/test_engine.py`; `tests/skill_phrases/orchestra.json`, `orchestra-review.json`.

**No lost functionality:** a wave of one is per-ticket review. Explicit `review_of` ids work unchanged. A report without `task_findings` behaves as in 2.1. Review independence (engine.py:752-753) and artifact binding (engine.py:762-764) are unchanged.

**Acceptance tests (tests/test_engine.py):**

| Test | Behavior |
|---|---|
| `test_wave_review_of_resolves_wave_members_at_add` | `review_of: ["wave:W1"]` stores the ids of W1's builder implementation cards. |
| `test_wave_label_refused_on_repair_and_review_cards` | `wave` on a repair card or a review card is refused. |
| `test_adding_card_to_reviewed_wave_is_refused` | A W1 builder card added after the W1 review raises "already has a review". |
| `test_status_lists_waves_in_first_add_order` | Labels added as W2, W1, W3 are listed in that order. |
| `test_wave_review_task_findings_block_only_named_card` | `{B1: [f], B2: []}`: B2 can be accepted, B1 is refused. |
| `test_task_findings_must_match_findings_union` | A mismatched union, or an unknown key, is refused. |
| `test_review_without_task_findings_blocks_all_covered` | Regression (passes today). |
| `test_repair_diff_check_covering_chain_accepts_original` | Build B1, wave review with a finding on B1, repair R1, check over R1 and B1 CLEAN: R1 then B1 accept. |
| `test_repair_diff_check_covers_card_with_all_findings_rejected` | B2's only finding is rejected in the ledger. The check covers B2 and is CLEAN: B2 accepts with no repair. |
| `test_replacement_wave_review_after_member_parked` | B2 parked before review; the queued wave review parked; a replacement over B1 and B3 runs and both accept. |
| `test_absent_task_findings_key_is_clean_at_every_reader` | Covered C with no key: C accepts; a repair of C is refused ("Repair needs earlier checked coding findings"); the per-task completion loop passes; a stale newest receipt with findings only for B leaves C's verdict. |
| `test_repair_diff_check_finding_on_ancestor_refused` | A BLOCKED check keyed on B1 (repaired by R1) is refused; keyed on R1 it records. |
| `test_clean_wave_member_accepts_after_sibling_repair` | Dispatching R2 while B1 and the review card are acceptable is refused naming B1; after both accept, R2 dispatches and lands, and B1 stays accepted. |
| `test_repair_dispatch_allowed_after_parking_uninspected_investigator` | An acceptable reported investigator card blocks R2's dispatch; after `park` of that card (not `accept`), R2 dispatches. |
| `test_supersede_unstarted_review_when_replacements_cover_it` | Accepted with `superseded_by`; refused for a dispatched card, a non-review card, or a target no accepted newer review covers. |
| `test_parked_member_wave_reaches_completion` (test_integration.py) | B2 parked, wave review parked, replacement over B1 and B3, B2 unparked and reviewed, original superseded, final phase: completion succeeds. |

### 5.2 Repair ladder ending in hold (S2 as amended by Round 2)

**Current (OBSERVED):**

- repair-rounds.md:8-12: rounds 1 to 3 on the default model, round 4 an Opus override, round 5 a breaker to critic `judge`. repair-rounds.md:6 logs each round to `progress.md`.
- `P/config/models.json:49-53` sets builder `repair` to Opus medium with `"dispatch": "override"`.
- A repair needs a builder `repair_of` target in state reported or accepted without `repaired_by`, with checked findings (engine.py:568-580).
- `TASK_STATES` has no held state; `_validate_state` refuses unknown states with "Invalid task state" (engine.py:371).

**New:**

1. Rung 1 is the Sonnet implementation card. Rung 2 is one builder `repair` card on Opus medium (dispatch override, unchanged).
2. `TASK_STATES` gains `held`. `orchestra.py hold TASK --finding TEXT` needs the lease. It is refused unless TASK:
   - (a) is a builder `repair` card in state `reported` with no `repaired_by` and a current verdict with at least one blocking finding, or
   - (b) is a builder implementation card in state `reported` with no `repaired_by` whose current blocking verdict comes from a repair-diff check (the rejected-only card of 5.1 item 6; C3/R2-4).

   Notes never count (5.6). It moves the whole chain to `held`, stores `held_finding` on the tip, and appends `- held <id> (chain <ids>): <finding>` with the time to `<state>/progress.md`. This is the held log (N8: it replaces the per-round log of repair-rounds.md:6).
3. A held card blocks nothing during the build:
   - `_ready` treats a dependency in state `held` as satisfied, so a later wave that depends on held work still runs.
   - A held card reserves no files or resources (it is not in `occupied`).
4. `repair_of` may name a repair card only when that card is `held`, or has a current final receipt with blocking findings attributed to it. During the build this refuses a third try with "Escalation ends at one repair; hold the chain". The same rule covers a builder implementation card whose current blocking verdict comes from a build-phase repair-diff check (the rejected-only card of 5.2 item 2b): `repair_of` may name it only when it is `held` or has a current final receipt with blocking findings attributed to it; otherwise "Repair-diff check blocked X; hold the chain" (C5/R3-6). The final phase (5.5) uses the two allowed forms.
5. The repair target states become `reported`, `accepted` or `held`. Adding a repair to a held tip moves the chain from `held` to `repairing`, as for any repair.
6. `record_review` accepts covered cards in state `reported`, `accepted` or `held`. `_ready` lets a review run when every `review_of` target is in one of those states.
7. `accept` also accepts a `held` card whose current verdicts carry no blocking finding, after the existing `repaired_by` rule. This covers a held tip that every current final receipt lists under `cleared` (5.5 item 3).
8. No round counter, cap or breaker. repair-rounds.md is rewritten to this ladder.

**Files:** `P/scripts/orchestra_core/engine.py` (`TASK_STATES`, `add_task`, `hold`, `_ready`, `record_review`, `accept`, `_validate_state`); `P/scripts/orchestra.py` (`hold`); `P/skills/orchestra/references/repair-rounds.md` (rewrite), `parallel.md:16`; `P/skills/orchestra-build/references/repair.md:7`; `cli.md`, `docs/cli.md`; `tests/test_engine.py`; phrase files.

**No lost functionality:** the Opus valve stays. Rounds 1 to 3 and the round-5 breaker are replaced by the wave loop, hold and the final rounds (named under S7). 2.1 chains deeper than one stay valid history; the new refusal applies to new `add` calls only. `park` keeps its 2.1 meaning for approval boundaries.

**Acceptance tests (tests/test_engine.py):**

| Test | Behavior |
|---|---|
| `test_hold_moves_whole_chain_and_logs` | Hold of R1 sets R1 and B1 to `held`, stores the finding, and appends the progress line. |
| `test_hold_refused_without_current_blocking_findings` | A CLEAN repair card, an implementation card blocked only by its wave review, or a card with `repaired_by` is refused. |
| `test_hold_rejected_only_card_blocked_by_repair_diff_check` | B2 (findings all rejected) blocked on itself by the check: hold succeeds, the chain is B2 alone. |
| `test_dependency_on_held_card_is_ready` | A queued card depending on a held card is ready. |
| `test_held_card_reserves_no_files` | A card writing the held card's files is ready. |
| `test_repair_of_repair_refused_during_build` | A repair of reported R1 raises the hold hint. |
| `test_repair_of_card_blocked_by_repair_diff_check_refused` | B2 (findings all rejected) blocked by the check: a repair of B2 is refused with the hold hint; after `hold B2` it is added. |
| `test_repair_of_held_tip_allowed_and_chain_repairing` | A repair of held R1 is added; R1 and B1 become `repairing`. |
| `test_review_may_cover_held_cards` | A final receipt covering a held card records. |
| `test_accept_held_card_with_clean_current_verdict` | A held chain with a newer CLEAN receipt accepts tip-first. |
| `test_first_repair_of_builder_still_allowed` | Regression (passes today). |
| `repair-rounds ladder` phrase (skill_phrases/orchestra.json) | The ladder sentence is present; no "Round 5" breaker line. |
| Flip (C6/R3-2): `test_second_repair_suspends_entire_same_file_chain` (test_engine.py:617-639) | Today R2 `repair_of` R1 is added right after the BLOCKED `blocked2`. 2.2: `blocked2` carries `task_findings: {R1: [bug2]}` (tip rule) and `hold R1` runs before R2 is added; the rest (R2, `clean2`, accepts, fresh original review) is unchanged. |

### 5.3 Completion and held work

**Current (OBSERVED):** completion needs every task accepted (engine.py:908-909), current final verdicts without findings, no current per-task findings (engine.py:916-918), full category coverage and the required gates (engine.py:919-934). autonomy.md:22: "Parked work blocks `finish`."

**New:** completion is unchanged. A held card is not accepted, so completion refuses with "All tasks must be accepted" until the final phase repairs and accepts it. No exclusion list is needed, and the per-task findings loop needs no change (N1, F4). autonomy.md:22 stays for approval-boundary parks and gains: "Held work never blocks a later wave; the final phase must clear it before `finish`."

**Acceptance test:** `test_completion_refuses_while_card_held` (test_engine.py): every other card accepted, a final review and passing gates, one held chain: refused, naming "accepted".

### 5.4 Gates between waves, and gate failures (S4)

**Current (OBSERVED):** the engine records gates (`gate NAME -- argv`, engine.py:818-862) and schedules none. A repair needs review findings (engine.py:578-580), so a failed gate cannot reach the ladder by itself.

**New:**

1. A wave-boundary gate runs for wave N only when a card of the next wave lists a wave-N card in `dependencies`, or names in `files` or `inputs` a path a wave-N card owns. Otherwise no gate runs between them; the operator gates the candidate once in the final phase.
2. The wave-boundary gate runs after wave N's builders report and before its wave review, so the wave reviewer cites the receipt (5.11).
3. A failed gate enters the ladder as a finding: a reviewer who cites a failed receipt must return BLOCKED and attribute the failure to the responsible cards (S-b). The engine refuses a CLEAN report that cites a failed receipt: "A failed gate receipt needs a blocking finding". In the final phase, the correctness lens does the same with the operator gate.
   - **Held work (C3/R2-1):** when the failure comes from a held chain, the reviewer attributes it in `task_findings` to that held tip. `record_review` accepts the key although the tip is outside the coverage, only when the tip is in state `held` and the report cites a failed gate receipt; otherwise "Task findings name an uncovered task". The finding stays on the receipt and in the held log (`- gate <receipt> attributed to held <tip>: <finding>`), enters no covered card's verdict, and reaches the final lenses with the held log. Wave review briefs carry the held log.
4. `status` shows each wave and whether the next wave depends on it. The engine computes it from stored fields and schedules nothing.

**Files:** `P/skills/orchestra/references/coordination.md`; `P/skills/orchestra-review/references/checkpoint.md`, `final.md`; `P/scripts/orchestra_core/engine.py` (`record_review`, a read-only helper for `status`); `P/scripts/orchestra.py`; `tests/test_engine.py`; phrase files.

**No lost functionality:** gates stay available at any time.

**Acceptance tests:**

| Test | Behavior |
|---|---|
| `test_status_marks_wave_dependency_from_dependencies_and_paths` (test_engine.py) | W2 depends on W1 through `dependencies` and through an owned path: true. An unrelated W3: false. |
| `test_clean_review_citing_failed_gate_refused` (test_engine.py) | Refused. The same report as BLOCKED with the finding records. |
| `test_failed_gate_from_held_chain_does_not_block_later_wave` (test_engine.py) | B1 held, W2 gate failed: a BLOCKED W2 receipt with `{B1: [f], C1: []}` records, C1 accepts, the held log gains the gate line. |
| `test_uncovered_key_refused_unless_held_tip_and_failed_gate` (test_engine.py) | An uncovered key on a non-held card, or with no failed receipt cited, is refused. |
| `wave gate rule` phrase (skill_phrases/orchestra.json) | coordination.md states rules 1 and 2. |

### 5.5 Final phase: parallel lenses and final repair rounds (S5, Round 2, Round 3)

**Current (OBSERVED):**

- final-review.md:8-10: four lens cards, all code-reviewer final on Opus high (models.json:68-71). final.md:16-21 maps lenses to categories.
- final-review.md:14-16 routes correctness findings to repair rounds and other findings to one cleanup card, then runs a fresh four-lens review.
- Completion needs all seven categories (engine.py:35, 38, 919-921). Final receipts bind the whole-repository artifact, so any later edit makes them stale.
- `P/scripts/generate.py:49-55` writes a variant agent for each non-override preset whose model or effort differs from the role default.

**New, lens layout (OD-4 A):**

| Lens | Agent | Categories |
|---|---|---|
| `correctness.md` | `orchestra:code-reviewer` (Opus high) | requirements, correctness, tests, architecture |
| `security.md` | `orchestra:code-reviewer` (Opus high) | security |
| `standards.md` (new) | `orchestra:code-reviewer-standards` (Sonnet medium) | standards, cleanup |

`models.json` gains `code-reviewer.presets.standards = {model: claude-sonnet-5-5, effort: medium}` with no dispatch override, so the generator writes `agents/code-reviewer-standards.md` (OD-18 A). `VARIANT_NOTES` gains `('code-reviewer', 'standards')`. roles.json code-reviewer modes stay `["checkpoint", "final"]`, so the run contract hash is unchanged (engine.py:43-65); only the prompt sentence becomes "the three lens cards". The 50-changed-line specialist rule stays (final-review.md:18-22).

**New, the final phase (resolves B1; replaces the cleanup card and the fresh four-lens review):**

1. The operator gates the integrated candidate.
2. The three lens cards run in parallel. Each covers every task, held ones included, and receives the held log and the gate receipts. Each in-scope blocking finding is attributed in `task_findings` to the chain tip whose change introduced it. A defect no card's change introduced is out of scope (5.7). **Non-builder cause (C5/R3-5):** a defect introduced by a card that is not a builder (operator, designer-planner, an inline edit) has no chain tip; the lens raises it in `out_of_scope` naming that card, and the coordinator triages it `inline` or `card` (a new builder card) by default, never `brief` alone.
3. Engine rules for final receipts: a receipt with blocking findings must carry `task_findings`, and every key must be a chain tip ("Attribute final findings to the chain tip X"). Every final receipt addresses each tip in state `held` at record time (C3/R2-6, C4/R2-3): a blocking finding in `task_findings`, or an entry in `cleared` (tip to a non-empty reason). Omission is refused: "Final receipt must address held tip X". The correctness lens judges the held finding itself; a lens whose categories it does not touch clears it with a lens-scoped reason ("no security defect").
4. **Final repair round.** First the accept step of 5.1 item 10: the lens cards, investigator cards and every acceptable chain. Then one Opus repair card per chain with a current attributed final finding, held or not. A held chain that every current final receipt clears accepts under 5.2 item 7 with no repair. The repairs are added together and dispatched through the Agent tool, as the override preset requires (parallel.md:16). The `repair_of` target is the chain tip (5.2 item 4).
5. **Re-check.** After the round's repairs report, each lens that failed re-runs as a final card over all tasks. Its brief limits the work to the still-failing items and the round's repair diff. Chains that pass are accepted tip-first.
6. **Next round.** Each chain still failing gets another repair round. No count limit. If a finding repeats (same fingerprint as the previous round, or the same chain blocked again by the same lens, keyed on chain id and lens category: C3/N-1), an investigator-code card re-diagnoses it first, and the next repair brief carries the diagnosis and the previous approach to avoid. The run deadline is the only outer limit.
7. **Closing confirmation.** When every re-check is CLEAN, the operator re-gates the candidate. Each lens whose last CLEAN receipt is now stale records one closing confirmation over the cumulative final-repair diff. This keeps "any later edit voids earlier evidence" and engine.py:919-921. A blocking finding there starts another round.
8. Notes never start a round (5.6). Out-of-scope items follow the triage in 5.7.
9. **Round order (C6/R3-6):** final-review.md states that each round (the lens round, a re-check round, the closing confirmations) first adds every card of the round, then has them all report, then records their receipts. A receipt recorded before a later card of the same round is added fails the final coverage filter (engine.py:749, 754, 782).

**Files:** `P/config/models.json`, `P/config/roles.json` (prompt text); `P/scripts/generate.py`; `P/agents/code-reviewer-standards.md` (generated); `P/skills/orchestra/references/final-review.md` (rewrite of routing), `repair-rounds.md`; `P/skills/orchestra-review/references/final.md`, `correctness.md`, `standards.md` (new, with a provenance header), and `P/THIRD-PARTY-NOTICES` plus `docs/SKILL-SOURCES.md` if it derives from a source; `P/scripts/orchestra_core/engine.py` (`record_review`); `AGENTS.md` (model sentence); `docs/models.md`, `docs/roles.md`; `tests/test_packaging.py`, `tests/test_skills.py`, `tests/test_engine.py`, `tests/test_integration.py`; phrase files.

**No lost functionality:** all seven categories stay covered. Architecture checks move into the correctness lens and cleanliness checks into the standards lens; architecture.md and cleanliness.md stay as included checklists. The cleanup card and the fresh four-lens review are replaced by repair rounds plus closing confirmations (named under S7).

**Acceptance tests:**

| Test | Behavior |
|---|---|
| `test_standards_preset_is_sonnet_medium_variant_file` (test_packaging.py) | No `dispatch` key; the agent file has `model: claude-sonnet-5-5`, `effort: medium` and read-only `disallowedTools`. |
| `test_role_matrix_files_and_read_only_enforcement` (updated, test_packaging.py) | The expected set includes `code-reviewer-standards.md`. |
| `test_final_lens_table_covers_every_category` (test_skills.py) | The final.md table's union equals engine `CATEGORIES`. |
| `test_generated_agents_match_the_canonical_source` | Regression: `generate.py --check` exits 0. |
| `test_contract_hash_unchanged_by_lens_change` (test_engine.py) | `_contracts()[1]` equals the 2.1 digest. |
| `test_final_findings_need_task_findings_on_chain_tips` (test_engine.py) | A BLOCKED final without `task_findings`, or keyed on a card with `repaired_by`, is refused. |
| `test_repair_of_accepted_tip_with_final_finding_allowed` (test_engine.py) | Accepted chain, final finding on its tip: the repair is added and the chain becomes `repairing`. |
| `test_final_receipt_must_address_every_held_tip` (test_engine.py) | A final receipt naming a held tip in neither `task_findings` nor `cleared` is refused; an empty reason is refused. |
| `test_held_tip_cleared_by_every_lens_accepts_without_repair` (test_engine.py) | Three lens receipts clear H1: H1 accepts tip-first; a repair of H1 is refused. |
| `test_final_lens_then_repair_then_completion` (test_integration.py) | Lens BLOCKED on B2: repair dispatch refused until the lens card accepts; then repair, re-check, closing confirmation, completion succeeds. |
| `test_final_round_repairs_held_and_lens_chains_then_completes` (test_integration.py) | One held chain with a correctness finding and one lens finding on another chain: round 1 repairs both, re-checks pass, closing confirmations and the gate pass, completion succeeds. |
| `test_final_rounds_repeat_until_clean_with_no_cap` (test_integration.py) | A fake repair fails four times, then passes: five rounds, no stop, completion succeeds. |
| `final round rediagnosis` phrase (skill_phrases/orchestra.json) | final-review.md routes a repeat (fingerprint, or chain id and lens category) to investigator-code before the next repair, and states the accept-before-repair order. |
| `test_final_receipt_stale_when_card_added_after_it` (test_integration.py) | A lens receipt recorded, then a re-check card added: the earlier receipt no longer satisfies final coverage; adding all cards first, then reporting, then recording passes. |
| `final round order` and `non-builder final finding triage` phrases (skill_phrases/orchestra.json) | final-review.md states the add-report-record order (item 9); final-review.md and triage.md route a non-builder-caused final finding to `inline` or `card`, never `brief` alone. |

### 5.6 Materiality: findings and notes (Round 3)

**Current (OBSERVED):** review SKILL.md:39-41 lists the report fields and says minor findings do not block unless a binding requirement makes their effect material. The engine sets the verdict to BLOCKED when `findings` is non-empty (engine.py:762-763). Critic reports use the same receipts (`REVIEW_ROLES`).

**New:**

1. **Rule text** (one paragraph, the same in the review SKILL.md and the critique SKILL.md): a finding blocks only when it has a real, material impact on the requirements, tests or frameworks the prompt names: a named requirement unmet, a named test failing or certain to fail, a binding framework or charter rule broken, or a security or data-loss defect. An issue with no such impact, or one affecting under about 20% of a piece of work that is otherwise correct while every named requirement and test still holds, is a note. Notes go to the run brief and never trigger repair or hold.
2. **Report schema:** the body may carry `issues`, a list of `{text, severity, impact}` with `severity` of `blocking` or `note`. `impact` is required for `blocking`: the requirement, test or framework and the effect.
3. **Engine BLOCKED rule:** with `issues`, `findings` must equal the blocking texts in order, and the verdict is BLOCKED exactly when one exists. Note texts are stored on the receipt as `notes`. `add_task` stamps `rev: "2.2"` on every new card. A review or critic receipt covering any card with `rev` must carry `issues`: "Review of 2.2 cards needs issues with severity" (C3/R2-9). String-only reports, every finding blocking, stay accepted only when every covered card predates 2.2. `issues: []` satisfies the rule for a CLEAN report (C6/R3-1).
4. Notes never count for `accept`, `hold`, the repair precondition "Repair needs earlier checked coding findings" or completion. The run brief lists them.
5. **Severity scale:** review SKILL.md's "Grade severity: critical, major, minor or trivial" is replaced by "Grade each issue `blocking` or `note` by the materiality rule". Mapping: critical and major become `blocking` when the impact test holds; minor, trivial and anything without a named impact become `note`. Confidence and confirmed/plausible stay. The critique SKILL.md requires the same `issues` shape.
6. **Test-helper migration (C6/R3-1):** the 5.6 ticket migrates the shared review helpers to emit `issues` and lands first in the engine wave, so later tickets start green (flip table below).

**Files:** `P/skills/orchestra-review/SKILL.md`, `P/skills/orchestra-critique/SKILL.md`; `P/scripts/orchestra_core/engine.py` (`record_review`); `P/scripts/orchestra.py` (`review` reads the body); `tests/test_engine.py`, `tests/test_integration.py` (helper migration); `tests/skill_phrases/orchestra-review.json`, `orchestra-critique.json`.

**No lost functionality:** string-only reports keep 2.1 behavior for cards migrated from 2.1. The four grades map onto the two severities (item 5). The 2.1 sentence at SKILL.md:41 is replaced by the rule text, which is stricter about what blocks.

**Acceptance tests:**

| Test | Behavior |
|---|---|
| `test_notes_only_report_is_clean_and_accepts` (test_engine.py) | Two notes, no blocking issue: CLEAN, and the card accepts. |
| `test_blocking_issue_needs_impact` (test_engine.py) | A blocking issue with empty `impact` is refused. |
| `test_issues_must_match_findings_and_verdict` (test_engine.py) | Blocking texts differing from `findings`, or a CLEAN verdict with a blocking issue, is refused. |
| `test_repair_refused_for_notes_only` (test_engine.py) | "Repair needs earlier checked coding findings". |
| `test_hold_refused_for_notes_only` (test_engine.py) | Refused. |
| `test_run_brief_lists_notes` (test_engine.py) | Notes appear under "Notes". |
| `test_review_of_2_2_card_without_issues_refused` (test_engine.py) | A string-only report covering a card with `rev` is refused. |
| `test_review_of_migrated_card_keeps_string_findings` (test_engine.py) | Regression: a 2.1 fixture card without `rev` accepts a string-only report, all findings blocking. |
| `test_clean_report_with_empty_issues_accepts` (test_engine.py) | A CLEAN report with `issues: []` covering a 2.2 card records, and the card accepts. |
| `materiality rule` phrases | Both SKILL.md files contain the rule paragraph; review SKILL.md no longer contains "critical, major, minor or trivial". |

**Test flips (C6/R3-1):** these helpers write string-only bodies today, so under the `rev` stamp every review they record would be refused.

| Location | Today | 2.2 |
|---|---|---|
| tests/test_engine.py:42 `EngineFixture.review` | string `findings` only | also writes `issues`: each finding as `{text, severity: blocking, impact}` with a fixture impact; `[]` when CLEAN |
| tests/test_engine.py:505-511 `FinalBlockerTests.record` | string `findings` only | the same `issues` shape |
| tests/test_integration.py:62 and :170 review posts | `findings: []` only | add `issues: []` |

### 5.7 Out-of-scope findings and triage (S6)

**Current (OBSERVED):** review SKILL.md:19 flags scope drift (in scope). final.md:23 puts out-of-lens findings in the summary. No rule covers defects outside the change, and the engine has no field for them.

**New:**

1. checkpoint.md: wave reviewers and repair-diff reviewers raise nothing outside the reviewed change.
2. Final lens reports may carry `out_of_scope`, a list of non-empty strings that never changes the verdict. `record_review` refuses it on a non-final receipt: "Out-of-scope findings are raised only at the final review".
3. The coordinator triages each item with `orchestra.py finding add --review <id> --kind out_of_scope --index N --disposition inline|card|brief --reason TEXT [--card ID]`. The entry is keyed by the item's fingerprint (N5), so a re-lens after an inline fix does not force re-triage of an unchanged item.
4. Completion refuses while an `out_of_scope` item on a current final receipt has no triage entry with its fingerprint (OD-5 B).

**Files:** `P/scripts/orchestra_core/engine.py` (`record_review`, `_completion_evidence`, `add_finding`); `P/scripts/orchestra.py`; `P/skills/orchestra-review/SKILL.md`, `references/checkpoint.md`, `final.md`; `P/skills/orchestra/references/final-review.md`, `triage.md`; `tests/test_engine.py`; phrase files.

**No lost functionality:** scope-drift findings, the final.md note and triage.md:23 stay.

**Acceptance tests (tests/test_engine.py):**

| Test | Behavior |
|---|---|
| `test_checkpoint_review_with_out_of_scope_is_refused` | Refused. |
| `test_final_out_of_scope_does_not_block_verdict` | A CLEAN final with items records CLEAN. |
| `test_completion_requires_triage_of_out_of_scope` | Refused until each item has an entry. |
| `test_triage_carries_forward_by_fingerprint` | A new final receipt repeats an item: the earlier entry satisfies completion. |
| `test_finding_add_rejects_bad_disposition_and_index` | Refused. |

### 5.8 Autonomy continues; the deadline is the only limit

**Current (OBSERVED):** `hook_stop` (engine.py:1084-1118) stops on `ledger-tampered`, `deadline`, `complete`, `cap-stalls`, `cap-passes`, and `parked-only` / `no-ready-card` when nothing is live. A stall is a pass with no newly accepted card. `parse_ledger` requires `max_passes` and `max_stalls` (engine.py:96-106). `_complete` checks only the ledger's checks on the current artifact (engine.py:1074-1082). `autonomy.ts:77, 81, 119` render "pass N/M".

**New:**

1. `cap-passes` and `cap-stalls` are removed as stop reasons. No count stops the loop.
2. Remaining stop reasons: `deadline`, `complete`, `ledger-tampered`, `disarmed`, and `parked-only` / `no-ready-card` (OD-6).
3. `complete` needs the ledger checks and `_completion_evidence` to pass (C3/R2-2): every task accepted (so no `held` or `repairing` card), no current final or per-task finding, full category coverage, the required gates and the out-of-scope triage. `_complete` returns false on its refusal. `_complete` runs the cheap all-accepted check (engine.py:908) before the ledger checks, so neither the ledger checks nor the artifact hashing run while any card is unaccepted (C6/R3-5, K14). A `held` card counts as live work, because the final phase is still owed, only when no non-release card is `parked`; the continuation text then says "start or continue the final phase". **Held and parked (C5/R3-1):** when a parked non-release card coexists with a held chain, no final receipt can be recorded (engine.py:749, 754, 898-900), so the Stop hook and `settle` stop `parked-only`, and the brief's Needs you names both the parked boundary action and the held chains.
4. A stall is a pass that leaves the progress signature (5.10) unchanged. Stalls are counted and reported, and never stop or park (OD-7 C). In-session runs have no back-off; with the item 3 carve-out an idle in-session run stops `parked-only` instead of looping (C5 missing 3). Only the relaunch harness backs off (5.10 item 5.6).
5. `max_passes` and `max_stalls` become optional; recorded and shown, never enforced (OD-8 A). The template drops them. The continuation text drops "of %d".
6. A card that fails its wave review goes to repair, and a chain that fails its repair-diff check is held. The loop takes the next ready card. Approval-boundary parks are unchanged from 2.1.
7. Under `relaunch`, `hook_stop` with no active session is a no-op: no pass, stall or stop is counted, so a Stop in another session between passes changes nothing (C3/N-6). PreToolUse still applies the boundaries then (5.10 item 3), by design.
8. **Release pre-authorization (Coordinator ruling; C3/R2-3, C4/R2-6):**
   1. Approval boundaries hold exactly one `- Release:` line: the fixed `- Release: no release, permit or deploy.` or `- Release: pre-authorized <remote> <target>` (two tokens). Any other `- Release:` line, or two of them, refuses `arm`: "Approval boundaries need exactly one Release line". Every other fixed line (engine.py:69-76) stays required; the pre-authorization line overrides the Push and Engine-gated actions lines (engine.py:72, 75) for that remote and target only.
   2. The pair must equal `policy.release` `remote` and `target` with `enabled` true, or `arm` refuses: "Release pre-authorization must match policy.release". `arm` stores `autonomy.release = {remote, target}`.
   3. `_refuse_under_autonomy` (engine.py:983-986) lets `release_permit` and `check_release` through only for that exact pair. The hooks release deny (hooks.py:194-195) skips class `release` only when the decision's remote and target equal it; the normal permit check (hooks.py:200-210) then runs. `release-multi`, merges, pushes, deletions and every other permit stay denied.
   4. With the line, the coordinator adds the terminal release card after the closing confirmations, and `complete` waits for its acceptance (REASONED: item 3 needs every task accepted). Without it, an armed coordinator adds no release card and the brief's Needs you says "ready to release". An unarmed run ends the same way: no release card, "ready to release" in the brief (C5 missing 1, 5.9).
   5. The template names the optional line in its comment; autonomy.md:22 becomes "Hard by default; the ledger may pre-authorize the one configured release". Both texts say that the Release line overrides Push and Engine-gated actions for that remote and target only (C5/R3-3).

**Files:** `P/scripts/orchestra_core/engine.py` (`parse_ledger`, `arm_autonomy`, `hook_stop`, `_complete`, `_refuse_under_autonomy`, `release_permit`, `check_release`, `_validate_state`, `autonomy_status`); `P/scripts/orchestra_core/hooks.py` (release deny); `P/config/autonomy-template.md`; `P/skills/orchestra/references/finishing.md`; `tests/test_hooks.py`; `P/hooks/mod/autonomy.ts`, `autonomy.test.ts`; `P/skills/orchestra/references/autonomy.md`; `docs/hooks.md`; `tests/test_engine.py`, `tests/test_integration.py` (flip).

**No lost functionality:** the deadline, completion, tamper and disarm stops stay. Pass and stall counts are still reported. The caps are replaced by the deadline (named under S7).

**Acceptance tests:**

| Test | Behavior |
|---|---|
| `test_hook_stop_never_stops_on_pass_count` (test_engine.py) | 50 passes with live work all continue. |
| `test_hook_stop_never_stops_on_stalls` (test_engine.py) | Ten stalled passes continue; `stalls` reads 10. |
| `test_hook_stop_continues_while_held_cards_remain` (test_engine.py) | Only a held card left, nothing ready: continuation, not `no-ready-card`. |
| `test_hook_stop_parked_only_when_held_and_parked` (test_engine.py) | A held chain plus a builder card parked at a boundary: stop `parked-only`; the brief's Needs you names the parked action and the held chain. |
| `test_settle_parked_only_when_held_and_parked` (test_engine.py) | The same state under `relaunch`, no session: `settle` stops `parked-only` and writes the brief. |
| `test_complete_skips_ledger_checks_until_all_accepted` (test_engine.py) | A queued card and a ledger check that writes a marker file: the Stop hook continues and the marker is absent. |
| `test_hook_stop_not_complete_while_held` (test_engine.py) | Ledger checks pass with a held card: no `complete` stop. |
| `test_hook_stop_not_complete_while_final_finding_open` (test_engine.py) | Ledger checks pass, a current final receipt blocks accepted B2: no `complete` stop. |
| `test_hook_stop_not_complete_while_card_repairing` (test_engine.py) | Ledger checks pass, B2 `repairing`, its repair queued: no `complete` stop. |
| `test_hook_stop_without_session_under_relaunch_is_noop` (test_engine.py) | `passes`, `stalls` and state unchanged. |
| `test_arm_preauthorized_release_permits_exact_pair` (test_engine.py) | Present: `release_permit` and `check_release` succeed under autonomy for the pair. |
| `test_permit_refused_under_autonomy_without_preauthorization` (test_engine.py) | Absent: refused as in 2.1 (regression). |
| `test_preauthorization_mismatch_refused` (test_engine.py) | Mismatched: `arm` refuses a pair unlike `policy.release`; a permit for another target is refused. |
| `test_arm_refuses_malformed_release_line` (test_engine.py) | Malformed (`pre-authorized origin`) and doubled Release lines refuse `arm`. |
| `release override scope` phrase (skill_phrases/orchestra.json) and the template test below | autonomy.md and the template comment say the Release line overrides Push and Engine-gated actions for that remote and target only. |
| `test_pretooluse_preauthorized_release_reaches_permit_check` (test_hooks.py) | Exact pair with a permit: allowed; another target: the autonomy deny. |
| `test_hook_stop_deadline_still_stops` (test_engine.py) | Regression. |
| `test_ledger_without_caps_arms` (test_engine.py) | Arms. |
| `test_2_1_ledger_with_caps_still_arms_and_caps_are_ignored` (test_engine.py) | Passes continue beyond `max_passes`. |
| `band renders pass count without maximum` (autonomy.test.ts) | "pass 3". |

**Test flips (C6/R3-3), caps (5.8) and heading (5.9):**

| Location | Today | 2.2 |
|---|---|---|
| test_engine.py:1278 `test_placeholder_or_bad_field_...`, :1311 `test_arm_snapshots_stores_fields_...` | a bad cap refuses; both caps stored | unchanged: a present cap is still validated and recorded (S7); absence arms (`test_ledger_without_caps_arms`) |
| test_engine.py:1335 `test_status_has_the_documented_keys_and_never_the_lease` | fixed key set | the key set gains `signature` (5.10 item 7); the caps stay, `None` when absent |
| test_engine.py:1346 `test_template_carries_the_fields_and_the_fixed_lines` | `max_passes:`, `max_stalls:` in the template | the two cap fields leave the list; it asserts the C5/R3-3 override sentence in the template comment |
| test_engine.py:1356 `test_stop_continues_inside_the_bounds_and_counts_passes` | "Autonomy pass 1 of 3" | "Autonomy pass 1" and no "of 3" |
| test_engine.py:1370 `test_pass_cap_...`, :1379 `test_stall_cap_...` | stop `cap-passes`, `cap-stalls` | removed; replaced by `test_hook_stop_never_stops_on_pass_count`, `test_hook_stop_never_stops_on_stalls` and `test_2_1_ledger_with_caps_still_arms_and_caps_are_ignored` |
| test_engine.py:1626 `test_stop_writes_the_morning_report_...` | cap stop; `## Autonomy report`, `passes: 1 of 1`, `cap-passes` | stop through the deadline (injected clock); `## Run brief`, `passes: 1`, `deadline`; the other fragments stay |
| test_engine.py:1694 `test_report_survives_interrupt_until_the_next_arm` | reason `cap-passes` | stop through the deadline; `autonomy_report()` still returns that `deadline` stop after `interrupt`, while `last_brief` holds the `interrupted` brief |
| test_hooks.py:1421 `test_stop_continues_while_active_and_stops_at_the_pass_cap` | "Autonomy pass 1 of 1", then `cap-passes` | "Autonomy pass 1", then a deadline stop |
| test_hooks.py:1439 `test_session_start_shows_the_report_with_the_progress_path` | "Autonomy report" in context | "Run brief" in context; `deadline` and the path stay |
| test_integration.py:412 `test_stop_continues_then_caps_then_session_start_shows_the_report` | `cap-passes` stop and context | `park c1`, then the Stop hook stops `parked-only`; the context holds `parked-only`, "Run brief" and `progress.md` |
| autonomy.test.ts:30, 55, 141, 224 | `STOPPED` reason `cap-passes`, toast "5/5", disarm text `## Autonomy report` | reason `deadline`, toast "pass 5", text `## Run brief` |

### 5.9 The run brief, every run (S-c, Round 2 item 4)

**Current (OBSERVED):** `_report_text` (engine.py:1058-1072) writes "## Autonomy report", the stop reason, passes and stalls of their maximum, accepted, parked and failures. `_stop_autonomy` appends it to `progress.md` (engine.py:1045-1056). Nothing writes a brief outside autonomy. SessionStart shows the first 2000 characters (hooks.py:261-269).

**New:**

1. One writer, `_brief_text`, replaces `_report_text`. Heading `## Run brief <time>`. Sections in this order, so the 2000-character excerpt keeps what needs the user:
   1. stop or close reason, deadline, passes, stalls
   2. **Needs you**: approval-boundary parks and their staged actions, `brief`-triaged out-of-scope items, deferred findings, and "ready to release" when a run completed without release pre-authorization, armed or unarmed (C5 missing 1)
   3. **Still failing / next phase** (C3/R2-8): each chain with a current blocking finding at the stop or close, and each held tip not yet cleared, with its last finding and final round
   4. **Held log**: `id (chain): held finding`, gate attributions, and whether a final round fixed it or a lens cleared it (reason)
   5. **Final rounds**: per round, the chains repaired and the findings that cleared
   6. **Notes** (5.6)
   7. **Deferred findings**, from the findings ledger
   8. **Parked**, **Accepted** (superseded cards marked "superseded by"; repaired chains marked "repaired (chain ids)", C5/R3-7), **Failures**: as in 2.1
2. **Every end path writes it, armed or not (C4/R2-5, C3/N-3, C3/N-4):** `close_session` (reason `complete` when `relaunch` autonomy is armed, which it stops; otherwise `closed`), `interrupt` and `interrupt_active` (`interrupted`), `end_harness_session` and `end_pass_session` (`ended`, 5.10 item 5.4), each autonomy stop and `settle` (the stop reason). The engine stores top-level `last_brief = {reason, at, text, path}`. SessionStart shows the first 2000 characters of `last_brief` whatever the autonomy state, falling back to the 2.1 `autonomy.report` (hooks.py:261-269). `_report_context` switches its prefix to " Run brief (<reason>): " and, for a run started under 2.1 with no `last_brief`, reads `autonomy.report` under the old " Autonomy report (" prefix (C6/R3-3).
3. `orchestra.py brief` is new, lease-free and read-only. It prints `last_brief`. finishing.md puts its Still failing, Held log, Final rounds, Notes and Needs you sections in the PR body under "Held / next phase".
4. **Release outcome (C5 missing 1):** finishing.md step 2 (finishing.md:11, "You or the user chooses") gains: a run without release pre-authorization, armed or unarmed, adds no release card and ends with "ready to release" under Needs you; the user then assigns the release (an operator card with an explicit assignment), which replaces the in-run question (S7).

**Files:** `P/scripts/orchestra_core/engine.py` (`_brief_text`, `_stop_autonomy`, `close_session`, `interrupt`, `interrupt_active`, `end_harness_session`); `P/scripts/orchestra.py` (`brief`); `P/scripts/orchestra_core/hooks.py` (`_report_context`); `P/skills/orchestra/references/autonomy.md`, `finishing.md`, `handoff.md`; `tests/test_engine.py`, `tests/test_hooks.py`.

**No lost functionality:** every 2.1 report field survives; the heading and cap lines are replaced (C6/R3-3). `autonomy.ts` matches on `last_stop_reason`, not the heading (autonomy.ts:81).

**Acceptance tests:**

| Test | Behavior |
|---|---|
| `test_run_brief_lists_held_log_and_final_rounds` (test_engine.py) | Both sections carry the ids and findings. |
| `test_close_session_writes_run_brief` (test_engine.py) | A completed non-autonomy run appends the brief. |
| `test_close_session_brief_reason_by_mode` (test_engine.py) | Unarmed or in-session autonomy: `closed`; armed `relaunch`: `complete` and autonomy stopped. |
| `test_interrupt_and_harness_end_write_run_brief` (test_engine.py) | Unarmed: `interrupt` gives `interrupted`, `end_harness_session` gives `ended`; `last_brief` updated. |
| `test_run_brief_lists_still_failing_on_deadline` (test_engine.py) | Deadline stop mid-round with B2 blocked: B2 and its finding under "Still failing / next phase". |
| `test_session_start_shows_newest_brief_without_autonomy` (test_hooks.py) | Never armed, closed run: the excerpt is the `closed` brief. |
| `test_brief_command_is_read_only` (test_engine.py) | `state.json` and `progress.md` are unchanged after `brief`. |
| `test_run_brief_needs_you_precedes_accepted` (test_engine.py) | Ordering. |
| `test_session_start_excerpt_contains_needs_you` (test_hooks.py) | With 40 accepted cards the excerpt still holds "Needs you". |
| `test_run_brief_keeps_2_1_lines` (test_engine.py) | Every 2.1 field (reason, passes, stalls, accepted, parked, failures) is present; the heading reads "Run brief". |
| `test_unarmed_completed_run_brief_says_ready_to_release` (test_engine.py) | Unarmed, completion evidence passes, no release card: `close_session`'s brief has "ready to release" under Needs you. |
| `test_run_brief_marks_repaired_chains` (test_engine.py) | An accepted chain B1-R1 is listed under Accepted with "repaired (B1, R1)". |
| `test_session_start_falls_back_to_2_1_autonomy_report` (test_hooks.py) | No `last_brief`, a 2.1 `autonomy.report`: the context starts with " Autonomy report (". |
| `finishing ready to release` phrase (skill_phrases/orchestra.json) | finishing.md states the item 4 outcome. |
| `PR held section` phrase (skill_phrases/orchestra.json) | finishing.md names the "Held / next phase" section with "Still failing". |

### 5.10 Fresh-context relaunch harness

**Current (OBSERVED, downstream harness read-only):** a bash loop with `-n` max passes and `-N` stall streak, a prompt file, a model, `--permission-mode` defaulting to bypass, `--` for another CLI, a STATE.md OPEN check, `SIGIL:` lines, a repository-hash signature, exit codes 0/3/4/5/6 and state under `.orchestra/ralph/`. REASONED from the handoff: it exits 5 at once under 2.x because STATE.md is gone.

**Current (OBSERVED, plugin):** `_autonomy_on` needs an active session (engine.py:980-982). `interrupt`, `interrupt_active`, `end_harness_session` and `close_session` all clear active autonomy through `_kept_autonomy` (engine.py:457-500, 945-954). `open_session` refuses while any session is active (engine.py:443-444). PreToolUse is unarmed when no session is active (hooks.py:361-362).

**Current (OBSERVED, spike I1, `claude -p` 2.1.289):** SessionStart, PreToolUse, Stop (once per turn end) and SessionEnd hooks and the Orchestra mod fire under `-p`. `-p` exits without waiting for background Bash or Agent work and kills it. Workflow under `-p` is UNKNOWN.

**New:**

1. `orchestra.py autonomy arm --relaunch` arms as today and sets `autonomy.relaunch = true`.
2. While `relaunch` is true, `interrupt`, `interrupt_active` and `end_harness_session` end the session but keep autonomy armed (N2, F9). `close_session` stops autonomy with `complete` and writes the brief.
3. While `relaunch` autonomy is armed, `_autonomy_on` reads true even with no active session, so PreToolUse applies the autonomy boundaries before a pass calls `start` (F11).
4. `orchestra.py autonomy settle` is new and lease-free. It evaluates the `hook_stop` stop conditions on an armed autonomy, with or without a session, without counting a pass. If one holds, it stops autonomy with that reason and writes the brief. It prints `{armed, stopped, reason, signature, passes, stalls}` as JSON.
5. `orchestra.py relaunch --permission-mode MODE [--model ID] [--launcher ARGV...]` runs from the repository in the user's terminal:
   1. Preconditions: an active run, autonomy armed with `relaunch`, no active session. Otherwise "End the interactive session first" and exit 2.
   2. It calls `settle`. If the run stopped, it exits with that reason's code.
   3. It launches one pass, `claude -p "$(cat P/config/relaunch-prompt.md)" --permission-mode MODE [--model ID] --output-format text`, with `start_new_session=True`, cwd at the repository and output to `<state>/relaunch/pass-N.log`. The pass environment carries `ORCHESTRA_RELAUNCH_PASS=<fresh nonce>`, and `start` stores it as `session.relaunch_pass`. `--launcher` replaces the command (prompt on stdin); tests use it.
   4. After the pass exits, it ends the active session, bound to a harness id or not, with outcome `pass-exited` (F10), only when its `relaunch_pass` equals the pass nonce. It calls the new engine method `end_pass_session(nonce)` (C5/R3-4): no lease and no harness id, refused unless `session.relaunch_pass` equals `nonce`, keeps `relaunch` autonomy armed, and writes the brief with reason `ended` (`pass-exited` maps to `ended`). Any other active session is left alone and the harness exits 2: "A session not started by this pass is active" (C4/R2-9). The nonce is a cooperative marker, not authentication.
   5. It records `{pass, signature, stalled_streak}` in `<state>/relaunch/harness.json`, outside the repository.
   6. After a stalled pass it waits `min(60 * 2^(streak-1), 900)` seconds, and never stops for stalls (OD-7 C).
   7. On SIGINT or SIGTERM it disarms first (reason `disarmed`, brief written), then forwards the signal to the pass's process group, then exits 130.
6. Inside a pass, the Stop hook does the per-pass accounting and returns no continuation when `relaunch` is true; the harness is the loop (OD-9 B).
7. Progress signature: SHA-256 of canonical JSON of the sorted `(task id, state, report_artifact.fingerprint or null, repaired_by or null)` tuples and the counts of `reviews`, `gates` and `findings`. `settle` and `autonomy status` expose it. `autonomy status` output is already JSON; no `--json` flag is added (F17).
8. `P/config/relaunch-prompt.md` tells the pass to read the orchestra skill, run `orchestra.py start --harness-session <id from SessionStart>`, read `progress.md` and `status`, dispatch ready cards, park at approval boundaries, never end the turn to wait, and end the pass at the context ceiling after recording state. It requires foreground (blocking) Agent calls only and forbids background Bash, because `-p` kills them at exit (F18).
9. Workflow in passes (F18): the first build ticket for 5.10 runs a live check, a two-agent Workflow under `claude -p` against a scratch state directory, and records whether both agents' results return before exit. If yes, the prompt allows foreground Workflow. If no or inconclusive, the prompt forbids Workflow and passes use foreground Agent calls.
10. Exit codes: 0 `complete`; 3 idle (`parked-only`, `no-ready-card`); 4 `deadline`; 5 `disarmed`, `ledger-tampered` or not armed; 2 usage or precondition; 127 launcher not found; 130 interrupted.

**Downstream feature map (S7):**

| Downstream feature | 2.2 replacement |
|---|---|
| `-n` max passes | Removed; the deadline is the only limit. |
| `-N` stall streak exit | Stall count, report and back-off (OD-7). |
| `-p` prompt file | `P/config/relaunch-prompt.md`; per-run override not carried (named). |
| `-m` model | `--model`, default unset (OD-10). |
| `--permission-mode` default bypass | Required flag, no default (OD-11). |
| `--` alternative CLI | `--launcher`. |
| `-v` verify | Ledger completion checks on the current artifact. |
| SIGIL DONE / BLOCKED-USER / NEEDS-APPROVAL / STALLED / RECYCLE | `complete` stop / `parked-only` stop with the brief / parked card at a boundary / stall count / the default pass end. |
| `harness-state.json` resume | `<state>/relaunch/harness.json` plus engine state. |
| STATE.md OPEN check | Active run and armed `relaunch` autonomy. |

**Files:** `P/scripts/orchestra_core/relaunch.py` (new, stdlib); `P/scripts/orchestra.py`; `P/scripts/orchestra_core/engine.py` (`open_session` stores `relaunch_pass`, `interrupt`, `interrupt_active`, `end_harness_session`, `end_pass_session` (new), `close_session`, `_autonomy_on`, `hook_stop`, `settle`, `signature`); `P/scripts/orchestra_core/hooks.py` (armed check with no session); `P/config/relaunch-prompt.md` (new); `autonomy.md`, `cli.md`, `docs/cli.md`, `docs/hooks.md`; `README.md`; `tests/test_engine.py`, `tests/test_hooks.py`, `tests/test_integration.py`, `tests/test_packaging.py`.

**No lost functionality:** in-session autonomy without `--relaunch` behaves as in 2.1 apart from 5.8. Every downstream feature has the named replacement.

**Acceptance tests:**

| Test | Behavior |
|---|---|
| `test_relaunch_autonomy_survives_session_end` (test_engine.py) | `end_harness_session` keeps autonomy armed; the session is inactive. |
| `test_relaunch_autonomy_survives_interrupt` (test_engine.py) | `interrupt` and `interrupt_active` keep it armed. |
| `test_close_session_under_relaunch_stops_complete_with_brief` (test_engine.py) | Stop reason `complete`, brief written. |
| `test_non_relaunch_autonomy_cleared_on_session_end` (test_engine.py) | Regression: 2.1 behavior. |
| `test_pretooluse_armed_without_session_under_relaunch` (test_hooks.py) | No active session, relaunch armed: `git worktree remove x` is denied with the autonomy boundary reason. |
| `test_settle_stops_on_deadline_between_passes` (test_engine.py) | Stops with `deadline` and writes the brief. |
| `test_signature_changes_on_report_hold_or_gate` (test_engine.py) | Each event changes the digest; a no-op does not. |
| `test_relaunch_runs_passes_until_complete` (test_integration.py) | A fake launcher accepts one card per pass; the last pass records a passing check. Exit 0. |
| `test_relaunch_refuses_with_active_session` (test_integration.py) | Exit 2. |
| `test_relaunch_requires_permission_mode` (test_integration.py) | Exit 2. |
| `test_relaunch_backs_off_after_stall_and_never_exits_on_stalls` (test_integration.py) | Injected clock: growing waits, still running after five stalls, deadline exits 4. |
| `test_relaunch_ends_orphaned_pass_session` (test_integration.py) | A bound and an unbound session carrying the pass nonce are ended; the next `start` succeeds. |
| `test_relaunch_leaves_foreign_session_and_exits_2` (test_integration.py) | A session without the nonce stays active; exit 2. |
| `test_end_pass_session_checks_nonce_and_writes_ended_brief` (test_engine.py) | A matching nonce ends the session, autonomy stays armed, `last_brief.reason` is `ended`; a wrong nonce is refused and the session stays active. |
| `test_relaunch_sigint_disarms_before_forwarding` (test_integration.py) | Exit 130; reason `disarmed`; the brief exists before the fake pass sees the signal. |
| `test_relaunch_prompt_ships_and_forbids_background_work` (test_packaging.py) | The file ships and contains the foreground-only sentence. |

### 5.11 Evidence reuse: the operator gates once

**Current (OBSERVED):** checkpoint.md:12 leaves suites to the operator gate. review SKILL.md:26 asks for a before-and-after regression comparison. `run_gate` never refuses a repeat (engine.py:818-862). Receipts carry no gate reference.

**New:**

1. Review reports may carry `gate_receipts`. `record_review` refuses unless every cited receipt exists, is intact, and has an `artifact` equal to the current whole-repository artifact. A cited failed receipt requires a BLOCKED verdict (5.4).
2. `run_gate` refuses a repeat with the same `name` and `argv` when an intact passed receipt on the current artifact exists: "Gate NAME already passed on this artifact (receipt R); pass --again to rerun". A failed gate always reruns.
3. Any later change to the coordinator tree (another wave landing, a repair) makes earlier receipts stale. The operator re-gates and the reviewer cites the new receipt (F14). Reviewers still run targeted probes and the regression comparison, never the full suites.

**Files:** `P/scripts/orchestra_core/engine.py` (`record_review`, `run_gate`); `P/scripts/orchestra.py` (`gate --again`); `P/skills/orchestra-review/SKILL.md`, `final.md`, `checkpoint.md`; `P/skills/orchestra/references/briefs.md`, `final-review.md`; `P/skills/orchestra-operate/references/gate.md`; `tests/test_engine.py`.

**No lost functionality:** `--again` reruns; failed gates rerun freely.

**Acceptance tests (tests/test_engine.py):**

| Test | Behavior |
|---|---|
| `test_gate_repeat_on_same_artifact_refused_without_again` | Refused; `--again` records a new receipt. |
| `test_failed_gate_rerun_allowed` | Reruns without `--again`. |
| `test_review_cites_stale_gate_refused` | A receipt on an older artifact is refused. |
| `test_review_cites_current_passed_gate_accepted` | Stored. |

### 5.12 Findings ledger

**Current (OBSERVED):** no record survives of a rejected or deferred finding except prose in `progress.md`. `state.json` has no `findings` key (engine.py:315-316).

**New:**

1. `state.json` gains an optional `findings` list. Each entry: `{id, fingerprint, text, source: {review, kind: finding|out_of_scope, index}, disposition: rejected|deferred|inline|card|brief, reason, card?, at}`.
2. `orchestra.py finding add ...` needs the lease. `orchestra.py finding list [--for-brief]` is lease-free; `--for-brief` prints a "Known findings" block for reviewer briefs.
3. Reviewer skill rule: do not raise a known finding unless the code at its location changed since the cited review. To contest a rejection, cite its id and the new evidence.
4. A rejection never accepts a card. Acceptance still needs a fresh independent verdict (engine.py:806-811); the repair-diff check gives it (5.1 item 6).

**Files:** `P/scripts/orchestra_core/engine.py` (schema, `_validate_state`, `add_finding`, `list_findings`); `P/scripts/orchestra.py`; `P/skills/orchestra-review/SKILL.md`; `P/skills/orchestra/references/coordination.md`, `briefs.md`, `cli.md`, `docs/cli.md`; `tests/test_engine.py`; phrase files.

**No lost functionality:** `progress.md` lines stay; the ledger only adds records.

**Acceptance tests:**

| Test | Behavior |
|---|---|
| `test_finding_add_requires_lease_and_known_review` (test_engine.py) | Refused without the lease or with an unknown review id. |
| `test_finding_list_for_brief_renders_known_findings` (test_engine.py) | Lists id, text, disposition and reason. |
| `test_rejected_finding_does_not_allow_accept` (test_engine.py) | BLOCKED review plus `rejected` entry: `accept` still refused. |
| `test_2_1_state_without_findings_loads` (test_engine.py) | Absent key reads as empty. |
| `known findings rule` phrase (skill_phrases/orchestra-review.json) | Present. |

### 5.13 Briefs carry exact keep/remove lists

**Current (OBSERVED):** briefs.md:8-13 has six brief parts and no keep or remove list. `_check_contract` runs at add (engine.py:537) and again at dispatch (engine.py:693).

**New:**

1. briefs.md gains a seventh part: builder briefs carry `## Keep` and `## Remove`, each listing exact paths, symbols or behaviors, or the single word `none`.
2. The heading check runs only in `add_task`, not at dispatch, so builder cards queued under 2.1 still dispatch (S-h, F7). A builder card without a `brief` field is not checked, as in 2.1; briefs.md requires the field for builder cards as procedure.
3. checkpoint.md: the reviewer confirms each Keep item holds and each Remove item is gone. A miss is a blocking finding against S7.

**Files:** `P/scripts/orchestra_core/engine.py` (`add_task`); `P/skills/orchestra/references/briefs.md`; `P/skills/orchestra-review/references/checkpoint.md`; `P/skills/orchestra-build/SKILL.md`; `tests/test_engine.py`; phrase files.

**No lost functionality:** cards without `brief` and non-builder briefs are unchanged.

**Acceptance tests (tests/test_engine.py):**

| Test | Behavior |
|---|---|
| `test_builder_brief_without_keep_remove_refused_at_add` | Refused, naming the missing heading. |
| `test_builder_brief_with_none_lists_accepted` | Accepted. |
| `test_queued_2_1_builder_without_headings_still_dispatches` | A card stored without the check dispatches. |
| `test_reviewer_brief_needs_no_keep_remove` | Regression. |

### 5.14 Guard: merged-branch deletion

**Current (OBSERVED):**

- `_git` (guards.py:418-505) denies `branch -D` and forced `-d`/`--delete` (guards.py:451-452), denies push with `--delete` or a `d` short option (guards.py:486-487) and a `:branch` refspec (guards.py:491-492). Non-forced `branch -d`, including `branch -d -r origin/x`, plus `tag -d` and `worktree remove|prune`, are boundary/delete (guards.py:499-502).
- Boundary decisions carry no branch, remote or argv (`_boundary`, guards.py:414-415). The chain combine forces release segments to stand alone and lets the first delete boundary win (guards.py:1799-1808). `-C`, `--git-dir` and `--work-tree` set `changed_repo`, used only for push (guards.py:427-428, 494).
- `classify "git push origin --del x"` returns release with target x: a live hole (F13).
- With autonomy off, boundary is allowed (hooks.py:211); under autonomy, boundary/delete is denied (hooks.py:192-197).

**Repository evidence (OBSERVED, `git for-each-ref`):** 56 local `v2/*` branches; none of the 62 non-main branches is an ancestor of `origin/main`; `feat/v2-roles-guard-mods` and `fix/agent-matcher` are tree-equal to first-parent commits of `origin/main`; all 56 `v2/*` tips are ancestors of `feat/v2-roles-guard-mods`.

**New:**

1. **Shapes.** Both guards classify exactly these as Decision category `merged-delete` with `boundary='delete'` (so every 2.1 delete-boundary rule applies), carrying `kind` (`local` or `remote`), `remote`, `branch` and `argv`:
   - `git branch -D <b>`; `git branch --delete --force <b>` and `-d -f` in any order, combined (`-df`) or abbreviated (5.15)
   - `git push <remote> --delete <b>` or `-d <b>`, flag before or after the remote; any prefix of `--delete` (`--del`) counts as `--delete` (F13)

   Each shape has exactly one branch positional and no other option. The remote is a name, not a URL or path. `boundary_categories` in guard-rules.json stays `[delete, merge]`: `merged-delete` is a category, not a third boundary kind (F3).
2. **Stand alone (F3).** Deny, with the reason named:
   - any command of more than one segment containing a merged-delete: "Execute branch deletions separately"
   - a git global repository option (`-C`, `--git-dir`, `--work-tree`), a `GIT_DIR` / `GIT_WORK_TREE` assignment, a wrapper (`sudo`, `env`, `nice`, `xargs`) or a command substitution: "Branch deletion must run plainly in the session repository"
3. **Still denied:** multi-branch deletes, `:b` refspecs, `--delete` with other push options, forced remote-tracking deletes (`branch -D -r`). Non-forced `branch -d -r` stays boundary/delete as today (F16).
4. **Python check** in hooks.py, when the category is `merged-delete`. It runs before the autonomy-off allow (hooks.py:211) and also when `engine` is None:
   1. Under active autonomy (including relaunch, 5.10), deny with the 2.1 delete-boundary reason (OD-13 A). The autonomy deny at hooks.py:196 changes from `category == 'boundary' and boundary == 'delete'` to `boundary == 'delete'`, so it also matches category `merged-delete` (C4/R2-7).
   2. Resolve the default ref as `_on_default_branch` does (hooks.py:272-285); for a remote delete use `refs/remotes/<remote>/HEAD`, else `<remote>/main`. Unresolvable: deny.
   3. Tip: `refs/heads/<b>` or `refs/remotes/<remote>/<b>`. Missing, the default branch or the checked-out branch: deny.
   4. Remote delete (OD-14 A): `git ls-remote <remote> refs/heads/<b>` with `GIT_TERMINAL_PROMPT=0` and a 3 s timeout must return the tracking sha; otherwise deny (F15).
   5. Merged if (a) `merge-base --is-ancestor <tip> <default>`, or (b) `<tip>^{tree}` is in one `git rev-list --first-parent -n2000 --format=%T <default>` call's output (F15), or (c) `<tip>` is an ancestor of a local branch or remote-tracking ref that meets (b), evaluated afresh at each delete (OD-12 A).
   6. Otherwise deny: "Branch B is not merged into DEFAULT (no ancestor, tree or covering-branch evidence)".
5. **Gate argv (C4/R2-1).** `run_gate` (engine.py:826-828) refuses every decision whose class is not `allow`, not only a non-allow action. No boundary argv (merged-delete, delete, merge) runs unchecked through `gate`: "Gate command forbidden: boundary actions run only through the guarded hook".
6. **Corpus schema (C4/R2-7).** A corpus case may carry `decision_category`; merged-delete cases read `"class": "boundary", "category": "delete", "decision_category": "merged-delete"`. tests/test_guard_corpus.py:37-59 and guard.test.ts:19 accept the key and assert that `decision.category` equals it in both guards.

**Test and corpus flips (F12), each with its new expected class:**

| Location | Today | 2.2 |
|---|---|---|
| tests/test_hooks.py `DENY_COMMANDS`: `git branch -D topic`, `git branch --delete --force topic` | deny | boundary/merged-delete; moved to a new `MERGED_DELETE_COMMANDS` list |
| tests/test_hooks.py `DENY_PUSH_DESTINATION`: `git push --delete origin main` | deny | classifier boundary/merged-delete; the hook still denies it as the default branch; moved to a hook-level test |
| tests/test_hooks.py `test_a2_always_deny_rules_remain`: `git push --delete origin x`, `git branch -D x` | deny | removed from the always-deny loop; covered by `test_merged_delete_denies_unmerged_branch` |
| tests/test_guard_corpus.py:127-136 inline-walker loop | count 21 | the two loop entries leave; count 19 |
| corpus `deny-destructive-3`, `deny-destructive-36`, `deny-push-destination-4`, `inline-r2b-55`, `inline-r2b-60` | deny | boundary/merged-delete |
| corpus `guard-r12-16` (`git -C $(pwd) branch -D x`), `guard-r12-17` (`sudo ...`), `guard-fx4-3` (`nice ... $(echo)`), `inline-r2b-54`, `inline-r2b-80` (`xargs`) | deny | deny (unchanged) |

**Files:** `P/scripts/orchestra_core/guards.py` (`_git`, `_boundary`, chain combine); `P/hooks/mod/guard.ts`; `P/config/guard-rules.json` (`_doc` text); `P/config/guard-corpus.json`; `P/scripts/orchestra_core/hooks.py`; `P/scripts/orchestra_core/engine.py` (`run_gate`); `tests/test_engine.py`; `docs/hooks.md`; `tests/test_guard_corpus.py`, `tests/test_hooks.py`, `P/hooks/mod/guard.test.ts`, `P/hooks/mod/orchestra.test.ts`.

**No lost functionality:** every denied shape outside the listed ones stays denied; non-forced `branch -d` keeps its class; the autonomy deletion boundary and the release permit path are unchanged. Named replacement: a boundary argv in `gate`, accepted by 2.1, is refused; that step runs as a plain command through the hook.

**Acceptance tests:**

| Test | Behavior |
|---|---|
| Corpus, both guards | merged-delete (with `decision_category`): `git branch -D x`, `git branch --delete --force x`, `git branch -df x`, `git branch --del --forc x` (C3/R2-7), `git push origin --delete x`, `git push --delete origin x`, `git push origin -d x`, `git push origin --del x`. |
| Corpus, both guards | deny: `git branch -D x y`, `git push origin --delete x y`, `git push origin :x`, `git push https://h/r.git --delete x`, `git push origin --delete --force x`, `git branch -D -r origin/x`, `git branch -d y && git branch -D x`, `git branch -D a; git branch -D b`, `cd /o && git branch -D x`, `GIT_DIR=/o git branch -D x`. |
| Corpus | `git branch -d -r origin/x` stays boundary/delete. |
| `test_merged_delete_allows_ancestor_branch` (test_hooks.py) | Fast-forward merged branch: allowed. |
| `test_merged_delete_allows_squash_tree_equal_branch` (test_hooks.py) | Allowed. |
| `test_merged_delete_allows_branch_covered_by_tree_equal_branch` (test_hooks.py) | The `v2/*` shape: allowed. |
| `test_merged_delete_denies_unmerged_branch` (test_hooks.py) | Denied, naming the tests. |
| `test_merged_delete_checked_with_autonomy_off_and_no_engine` (test_hooks.py) | No run: unmerged still denied. |
| `test_merged_delete_denied_under_autonomy` (test_hooks.py) | Denied. |
| `test_remote_delete_denied_when_ls_remote_differs_or_times_out` (test_hooks.py) | Moved tip and unreachable remote: denied. |
| `merged-delete is delegated` (orchestra.test.ts) | The mod calls the Python hook for `git branch -D x`. |
| `test_gate_refuses_merged_delete_and_boundary_argv` (test_engine.py) | `gate` with `git branch -D x`, `git branch -d x` or `git worktree remove x`: refused, nothing runs. |
| `test_corpus_decision_category_matches` (test_guard_corpus.py, guard.test.ts) | Every case with `decision_category` matches `decision.category` in both guards. |

### 5.15 Guard: abbreviated long options

**Current (OBSERVED, git 2.50.1 in a scratch repository):** git accepts unique prefixes such as `add --al`/`--upd`, `commit --am`, `reset --har`, `clean --forc`/`--dry`, `branch --del`/`--forc`, `push --mir`/`--del`/`--ta`/`--pru`/`--al`/`--push-o=`, `checkout --forc`, `switch --disc`, `restore --stag`/`--work`. It rejects ambiguous ones (`commit --al`, `push --forc`, `switch --forc`) and never prefix-matches global options or `worktree` subcommands. The guards compare exact strings (guards.py:447-504): `git add --al`, `git add --upd`, `git clean --forc` and `git reset --har` classify as allow. `--git-completion-helper-all` shows no harmless full long option is a strict prefix of a guarded one for the ten verbs. The guards allow `git commit --amend` today.

**New:**

1. In both guards, a verb's long-option token before `--` (the part before `=`) that is a non-empty strict prefix of a guarded long option of that verb counts as that option. The guarded options are those the rules already name, plus push `--delete` (5.14). The same applies to `push_value_options`, `commit_value_options` and `clean_value_options`, so positional counting stays right.
2. An exemption option (clean `--dry-run`, restore `--staged`) counts only in full. Abbreviated exemptions over-deny, the safe direction.
3. A prefix of more than one guarded option takes the most restrictive. Global options are not prefix-matched.
4. `commit --amend` and its prefixes are denied: "Amend rewrites history" (OD-15 A, a scope addition beyond the handoff's literal "classify like the full option"). guard-rules.json gains `commit_guarded_flags: ["--amend"]`.

**Files:** `P/scripts/orchestra_core/guards.py`, `P/hooks/mod/guard.ts`; `P/config/guard-rules.json`, `guard-corpus.json`; `tests/test_guard_corpus.py`; `tests/fixtures/git-long-options.json` (new pinned snapshot); `P/hooks/mod/guard.test.ts`.

**No lost functionality:** every full spelling classifies as today except `commit --amend` (OD-15).

**Acceptance tests:**

| Test | Behavior |
|---|---|
| Corpus deny, both guards | `git add --al`, `git add --a`, `git add --upd`, `git add --no-ignore-rem`, `git reset --har`, `git clean --forc`, `git clean --f`, `git branch --del --forc x y`, `git checkout --forc`, `git switch --disc`, `git push --mir origin`, `git push --ta origin`, `git push --pru origin`, `git push --al origin`, `git commit --am -m x`, `git commit --amend`, `git clean -f --dry`. |
| Corpus release | `git push --push-o=x origin main`. |
| Corpus allow | `git commit -m x file`. |
| `test_no_harmless_option_is_prefix_of_guarded_option` (test_guard_corpus.py) | For each verb in the fixture, no full option outside the guarded set is a strict prefix of a guarded one. |

### 5.16 Guard: fail-closed on chained commands (Round 2 item 6)

**Current (OBSERVED):** the handoff's chain `git status && git diff --quiet && git worktree remove X && rmdir Y || true` and 13 variants classify as boundary/delete in both guards without throwing. The Python hook returns `{}` in about 0.18 s, also with a payload `cwd` that does not exist. The message is the mod's `FAIL_CLOSED` (orchestra.ts:18), returned by `delegate` (orchestra.ts:79-92) on a non-zero exit, non-JSON stdout, malformed output or any thrown error (orchestra.ts:403-406). `runHook` spawns `/bin/sh run-hook.sh` in the session cwd with an 8000 ms timeout (orchestra.ts:75-77) and is shared by `delegate`, `readWhere` (orchestra.ts:95-96), `autonomyCli` (orchestra.ts:104-105) and `--cli status` (orchestra.ts:436-437). In Node, a spawn with a missing cwd throws ENOENT.

**Hypotheses:** H1 (REASONED): the session cwd was a removed worktree, so the spawn failed before Python ran. H2 (REASONED): the hook waited behind an exclusive `state.lock` held during artifact hashing past the timeout. H3 (UNKNOWN): another mod-side exception. H4 (REASONED, C4/R2-8): a malformed deny exits 2 (hooks.py:44-47, 191) and `delegate` maps every non-zero exit to `FAIL_CLOSED` (orchestra.ts:83), hiding the reason.

**New:**

1. A bug-lane diagnosis card tries to reproduce the exact message at the mod seam with the testkit fake `$` (`P/hooks/mod/testkit.ts`) for H1 and H2, and records the result.
2. Only `delegate` spawns in `$.plugin.root`, passing the session cwd inside the payload (F8). `readWhere`, `autonomyCli` and `--cli status` keep their spawn cwd and pass `--repo <session cwd>`; when that directory is gone they return the missing-cwd reason instead of resolving the plugin root as the repository.
3. A PreToolUse payload whose cwd does not exist denies the delegated classes (release, release-multi, boundary) with "Session directory no longer exists: cd to an existing directory, then retry" (OD-16 B).
4. `FAIL_CLOSED` reasons name the class: "Orchestra guard error (spawn: CODE | exit N | timeout | bad output); failing closed".
5. Lock hardening (C6/R3-4): hook state reads poll `fcntl.flock(LOCK_SH | LOCK_NB)` for up to 2 s instead of blocking (`_state`, engine.py:298-336, blocks today). On timeout, PreToolUse denies only the delegated classes (release, release-multi, boundary) with "Orchestra state is busy; retry"; every other class keeps the 2.1 raw-state fallback (hooks.py:357-360). Stop on timeout allows the stop and appends a brief with reason `state busy` to `progress.md`; `last_brief` is not updated, because `state.json` is locked (REASONED).
6. If neither hypothesis reproduces, items 2 to 5 ship as hardening and the CHANGELOG records the unreproduced gap (S-e). 2.2.0 is not held for it.
7. Regression corpus cases add the literal chain and its 13 variants.
8. On exit 2, `delegate` parses stdout and returns its deny reason when one is present; otherwise the item 4 reason (H4).

**Files:** `P/hooks/mod/orchestra.ts`, `orchestra.test.ts`; `P/scripts/orchestra_core/hooks.py` (`main`, missing cwd); `P/scripts/orchestra_core/engine.py` (non-blocking lock poll for hook reads, `hook_stop` busy path); `P/config/guard-corpus.json`; `tests/test_hooks.py`; `CHANGELOG.md`.

**No lost functionality:** fail-closed stays the default for every unexpected mod error; only the reasons and `delegate`'s spawn directory change.

**Acceptance tests:**

| Test | Behavior |
|---|---|
| `delegate spawns the hook from the plugin root when the session cwd is gone` (orchestra.test.ts) | Spawn cwd is `plugin.root`; payload cwd is the removed directory. |
| `cli reads pass --repo and keep their spawn cwd` (orchestra.test.ts) | `where`, `status` and `autonomy` calls carry `--repo <session cwd>`. |
| `delegate failure reason names the failure class` (orchestra.test.ts) | Exit 3, a thrown spawn and a timeout each give their class. |
| `delegate surfaces the reason of an exit-2 deny` (orchestra.test.ts) | Exit 2 with a deny payload: that reason, not `FAIL_CLOSED`. |
| `test_pretooluse_missing_cwd_denies_delegated_class_with_reason` (test_hooks.py) | `git worktree remove X` with a missing cwd: the cd message. |
| `test_pretooluse_missing_cwd_allows_nothing_new` (test_hooks.py) | Regression for allow-class commands. |
| `test_hook_state_read_fails_closed_after_lock_wait` (test_hooks.py) | A held exclusive lock: `git worktree remove x` gets the busy reason within 3 s. |
| `test_hook_busy_lock_keeps_raw_fallback_for_other_classes` (test_hooks.py) | A held exclusive lock: `git status` is allowed through the raw-state fallback within 3 s. |
| `test_hook_stop_allows_stop_and_writes_state_busy_brief_on_lock_timeout` (test_hooks.py) | Armed, a held exclusive lock: Stop returns no continuation within 3 s and `progress.md` gains a `state busy` brief. |
| Corpus cases | The chain and 13 variants are boundary/delete in both guards. Regression (passes today). |

### 5.17 Engine fix: read-only reviews do not collide

**Current (OBSERVED):** `_ready` (engine.py:655-668) puts running cards in `occupied` and refuses a queued card whose reservation collides with an occupied one. The only exemption is a reviewed target in state reported. Two read-only `review_of` critic cards naming the same file therefore collide; live, C2 had to be parked and re-added with no files.

**New:** in `_ready`, a collision is skipped when both cards are read-only reviews (`_read_review`, engine.py:606-607) and share no `resources`. Reviews still collide with writers.

**Files:** `P/scripts/orchestra_core/engine.py` (`_ready`); `tests/test_engine.py`.

**Acceptance tests (tests/test_engine.py):**

| Test | Behavior |
|---|---|
| `test_two_read_only_reviews_on_same_file_do_not_collide` | One running, one queued, same file: the queued one is ready. |
| `test_read_only_reviews_sharing_a_resource_still_collide` | Same resource: not ready. |
| `test_review_still_collides_with_running_writer` | Regression (passes today). |

### 5.18 Release files: version and changelog (N6)

**New:** `P/.claude-plugin/plugin.json:3` and `.claude-plugin/marketplace.json:11` move from 2.1.0 to 2.2.0. `CHANGELOG.md` gains a 2.2.0 entry naming each section of this change set, the held state's mixed-version effect (section 8) and, if 5.16 did not reproduce, the gap.

**Acceptance test:** `test_plugin_and_marketplace_versions_match` (test_packaging.py, regression if it exists today, otherwise new): both files read 2.2.0, and the CHANGELOG's first heading is 2.2.0.

### 5.19 Repository follow-up after 2.2 (this repository only)

Not part of the 2.2.0 change set. After 2.2.0 is installed, an operator cleanup card deletes the `v2/*` branches (56 OBSERVED again in D3 by `git for-each-ref refs/heads/v2`; the handoff says 55; the card recounts, C3/N-7) first, while `feat/v2-roles-guard-mods` still provides covering evidence, then `feat/v2-roles-guard-mods` and `fix/agent-matcher`: children before covering branches (C5/R3-2). Each deletion is one plain `git branch -D <b>` the guard allows. Acceptance for that card: `git for-each-ref refs/heads/v2` prints nothing, and the card log shows each allow decision.

## 6. Engine and state changes

State schema: `state.json` keeps `version: 1` with additive optional keys (OD-17 A). A missing key reads as its default.

| Location | Field | Type | Default | Section |
|---|---|---|---|---|
| `tasks[*]` | `wave` | non-empty str, builder implementation only | absent | 5.1 |
| `tasks[*]` | `held_finding` | non-empty str, on the held tip | absent | 5.2 |
| `tasks[*]` | `rev` | `"2.2"`, stamped by `add_task` | absent (2.1 card) | 5.6 |
| `tasks[*]` | `superseded_by` | list of ids | absent | 5.1 |
| `reviews[*]` | `cleared` | object of held tip id to reason, final only | `{}` | 5.5 |
| `reviews[*]` | `task_findings` | object of id to list of str | absent | 5.1 |
| `reviews[*]` | `notes` | list of str | `[]` | 5.6 |
| `reviews[*]` | `out_of_scope` | list of str, final only | `[]` | 5.7 |
| `reviews[*]` | `gate_receipts` | list of receipt ids | `[]` | 5.11 |
| top level | `findings` | list of ledger entries | `[]` | 5.12 |
| `autonomy` | `max_passes`, `max_stalls` | int, optional | absent | 5.8 |
| `autonomy` | `relaunch` | bool | `false` | 5.10 |
| `autonomy` | `signature` | str | absent | 5.10 |
| `autonomy` | `release` | `{remote, target}` | absent | 5.8 |
| `session` | `relaunch_pass` | str | absent | 5.10 |
| top level | `last_brief` | `{reason, at, text, path}` | absent | 5.9 |

**Card states:** `TASK_STATES` gains `held` (5.2); `supersede` reuses `accepted` (5.1 item 11). `PARKABLE` stays `queued`, `running`, `reported`; `park` and `unpark` keep their 2.1 behavior for approval boundaries.

**Report body keys read by `record_review`** (F17: read from the report body, so `orchestra.py review` needs no new flags): `task_findings`, `issues`, `out_of_scope`, `gate_receipts`, `cleared`. Corpus cases gain the optional key `decision_category` (5.14 item 6).

**Stop reasons:** removed `cap-passes`, `cap-stalls` (still readable in 2.1 reports); kept `deadline`, `complete`, `ledger-tampered`, `disarmed`, `parked-only`, `no-ready-card`; new brief reasons `closed`, `interrupted`, `ended` (5.9; the relaunch outcome `pass-exited` maps to `ended`, 5.10) and `state busy` (5.16 item 5).

**New CLI:** `hold`, `supersede`, `brief`, `finding add|list`, `gate --again`, `autonomy arm --relaunch`, `autonomy settle`, `relaunch`; `add` accepts `wave` and `review_of: ["wave:W"]`; `status` lists waves.

**Policy:** `DEFAULT` (engine.py:38-40) is unchanged, so `policy_hash` (engine.py:201-202) keeps 2.1 runs loadable.

## 7. Model matrix delta

| Role / preset | 2.1 | 2.2 |
|---|---|---|
| code-reviewer `standards` (new, variant `code-reviewer-standards`) | none | Sonnet 5.5 medium |
| code-reviewer `final` (correctness and security lenses) | Opus 5.5 high | unchanged |
| code-reviewer `checkpoint` (wave review, repair-diff check) | Opus 5.5 medium | unchanged |
| builder `repair` (rung 2 and every final repair) | Opus 5.5 medium, override | unchanged |
| investigator-code (final-round re-diagnosis) | as in models.json | unchanged |
| all other roles | as in models.json | unchanged |

`AGENTS.md`'s sentence "Opus 5.5 high for ... final reviewer" gains "except the standards lens, Sonnet 5.5 medium". `P/config/models.json` is the only source of the model matrix; the release done-when checks that no other file in the repository restates it beyond the AGENTS.md summary (N9).

## 8. Migration and compatibility for runs started under 2.1

**What carries over (REASONED):**

- The run contract digest covers only the role-to-modes map (engine.py:43-65) and the policy hash covers `DEFAULT` and the contract (engine.py:201-202). 2.2 changes neither, so a 2.1 run loads under 2.2 without `ACTIVE_MISMATCH` (engine.py:25-27, 311-313).
- `_validate_state` ignores extra keys (engine.py:338-392), so 2.1 state is valid 2.2 state.
- An armed 2.1 autonomy with `max_passes`/`max_stalls` continues past the old cap; the brief prints them as "recorded, not enforced".
- 2.1 parked cards keep their meaning. Queued 2.1 builder cards dispatch without keep/remove headings (5.13).

**Mixed versions on one active run (REASONED):** a 2.1 engine reading 2.2 state ignores `task_findings`, `notes` and `findings` (stricter), rejects any `held` card ("Invalid task state", engine.py:371) and rejects an armed autonomy without `max_passes`. The 2.1 hooks then fail closed for that run (hooks.py:221, 233-240). README upgrade notes: end every 2.1 session before the first `hold` or before arming under 2.2.

**The downstream harness** stays dead until the downstream follow-up PRs remove it (out of scope). The README names `orchestra.py relaunch` as its replacement.

| Test (tests/test_engine.py) | Behavior |
|---|---|
| `test_2_1_state_fixture_loads_under_2_2` | A 2.1 fixture with tasks, reviews, gates and armed autonomy loads; `hook_stop` continues past `max_passes`. |
| `test_2_1_parked_card_keeps_park_semantics` | `unpark` returns it to `queued`; completion still refuses while it is parked. |

## 9. Risks

- **K1:** Held work stays in the candidate between the build and the final phase, so later waves may build on a defect. Mitigation: the final lenses cover held chains first, and completion refuses until they are accepted. Residual: a later wave's gate may fail because of held work; the reviewer attributes it to the held tip outside the coverage (5.4 item 3), so the later cards are not blocked.
- **K2:** No cap on passes or final rounds means a confused run spends until the deadline. Mitigation: stall back-off, the idle stop, and repeat-driven re-diagnosis. `parse_ledger` requires a deadline to arm (engine.py:95-113), so every armed run has that bound (C3/N-5); an unarmed run has no loop.
- **K3:** Under `relaunch`, autonomy outlives sessions by design. If the harness itself dies, the run stays armed with no session until `disarm`. Recovery is manual, as for 2.1 lease loss. Because `_autonomy_on` reads true in that state (5.10 item 3), the boundaries keep applying.
- **K4:** Merged-branch evidence: an offline remote delete is denied (OD-14). The covering rule depends on deletion order. A squash landing does not keep the covered commits; work reverted on the covering branch before landing is gone once the children are deleted (OD-12 A accepts this). The 2000-commit window may deny very old squash merges, the safe direction.
- **K5:** The fail-closed root cause may stay UNKNOWN; then only hardening ships and the gap is in the CHANGELOG.
- **K6:** A 2.1 session still running against 2.2 state fails closed once a card is held (section 8).
- **K7:** The ls-remote and evidence calls add latency inside the mod's 8 s timeout. A slow remote can still hit it and fail closed.
- **K8:** Architecture checks inside the correctness lens put more on one Opus card (OD-4 A).
- **K9:** Abbreviation matching depends on git's option set; the pinned fixture catches drift only when refreshed.
- **K10:** The materiality line ("about 20%") needs judgment. A reviewer could under-block. Mitigation: blocking requires a named impact, security and data-loss defects always block, and notes reach the brief.
- **K11:** Workflow under `-p` is UNKNOWN until the 5.10 live check; the fallback is foreground Agent calls. Whether the pass's Bash calls inherit `ORCHESTRA_RELAUNCH_PASS` is also UNKNOWN (REASONED likely); the same live check records it. If not, step 4 exits 2 and the user ends the session.
- **K12:** Under `relaunch`, every pass end appends a brief, so `progress.md` grows by one brief per pass. The relaunch prompt reads only `orchestra.py brief`.
- **K13:** A lens may clear a held tip on judgment. Mitigation: every lens addresses every held tip with a reason, the reasons reach the brief, and a correctness-lens finding still blocks.
- **K14 (C6/R3-5):** once every card is accepted, the `complete` check in the Stop hook hashes the whole artifact plus each task's scope under the exclusive lock (engine.py:902-938), inside the 10 s Stop timeout. Mitigation: the all-accepted check runs first (5.8 item 3), so the cost falls only on the final passes. Residual: a large repository can still hit the timeout there.

## 10. Decisions

**Open decisions: none.**

**Accepted answers (user, handoff "Open decisions — answered") and their status:**

| OD | Accepted answer | 2.2 status |
|---|---|---|
| OD-1 | A, wave label | Kept; label limited to builder implementation cards, order by first add (5.1). |
| OD-2 | I2 | Overridden by Round 2: the ladder ends in hold, not park (5.2). |
| OD-3 | A, cascade-park | Overridden by Round 2: removed; dependents of held work run (5.2). |
| OD-4 | A, three lens cards | Kept (5.5). |
| OD-5 | B, engine-enforced | Kept, scope changed: keep/remove checked at add only (5.13); a cited failed gate requires BLOCKED instead of being refused (5.4, 5.11). |
| OD-6 | A, idle stop | Kept, amended: a held card counts as live work and blocks `complete`, unless a non-release card is parked, which stops `parked-only` (5.8; round-3 decision 1). |
| OD-7 | C, report and back-off | Kept. |
| OD-8 | A, optional caps | Kept. |
| OD-9 | B, harness is the loop | Kept. |
| OD-10 | C, optional `--model` | Kept. |
| OD-11 | A, required `--permission-mode` | Kept. |
| OD-12 | A, covering rule | Kept; rationale corrected and the reverted-work risk added (K4). |
| OD-13 | A, deny under autonomy | Kept; the draft's park language is dropped; the 2.1 delete-boundary reason applies (5.14). |
| OD-14 | A, ls-remote check | Kept; timeout 3 s (5.14). |
| OD-15 | A, deny amend | Kept; recorded as a scope addition (5.15). |
| OD-16 | B, deny with cd reason | Kept; extended to the CLI callers (5.16). |
| OD-17 | A, schema v1 | Kept. |
| OD-18 | A, generated variant | Kept. |
| Handoff merged-branch evidence ("its tree equals a merged PR head / the squash commit") | as written | CHANGED: the merged PR head clause is dropped, so the guard has no `gh` dependency; only first-parent tree and covering-branch evidence count (5.14 item 4.5). The cleanup follow-up deletes children before covering branches (5.19; round-3 decision 2). |

**Decided by coordinator recommendation** (Round 3 item 3; each is the recommended option and is final for the plan):

1. Hold is an explicit `hold` command after the repair-diff check, not automatic, so the coordinator refutes findings first (5.2).
2. A repair of a repair is allowed only for a held tip or a tip with a current final finding (5.2 item 4).
3. Final in-scope findings must be attributed to chain tips; a defect no card introduced is out of scope (5.5 items 2-3).
4. Each round's re-check is the failed lens over all tasks with its brief limited to the still-failing items; an unchanged fingerprint gets investigator-code re-diagnosis first (5.5 items 5-6).
5. When all re-checks are CLEAN, each stale lens records one closing confirmation over the cumulative final-repair diff, after a re-gate (5.5 item 7). The alternative, completing on stale lens receipts, would break "any later edit voids earlier evidence".
6. Materiality schema: an `issues` list with `severity` and a required `impact` for blocking; string-only reports are refused for 2.2 cards and stay 2.1 only for migrated cards (5.6 item 3; coordinator decision 9 below).
7. Security and data-loss defects are always material (5.6 item 1).
8. Overridden by the Coordinator ruling (section 2): approval boundaries stay hard by default; a ledger line may pre-authorize the one configured release (5.8 item 8). The Round 3 grant covers this build run's coordinator, not the product rule.
9. The wave-boundary gate runs after the builders report and before the wave review (5.4).
10. A wave member parked at a boundary before review: park the wave review, add a replacement with explicit ids, and clear the original with `supersede` (5.1 items 9 and 11).
11. Waves are ordered by first add (5.1 item 3).
12. The run brief is written by `close_session` too, and `orchestra.py brief` prints it (5.9).
13. A held card counts as live for the idle stop; the `complete` stop needs `_completion_evidence` (5.8 item 3). Narrowed by round-3 decision 1.
14. Relaunch passes use foreground Agent calls; Workflow is allowed only if the live check passes (5.10 item 9).
15. Fingerprint: first 12 hex of SHA-256 over the normalized text; it keys triage; final-round repetition is the fingerprint or chain id plus lens category (glossary, 5.5 item 6, 5.7).
16. Lock hardening for the hook read: 2 s wait, then fail closed with a named reason (5.16). Scoped by round-3 decision 12.
17. "Morning brief" is renamed "Run brief", because every run writes it.
18. Downstream repositories are named generically in this spec, per the charter.

**Coordinator decisions after round 2 (binding; recorded as given):**

1. A gate failure from a held chain is attributed to the held tip outside the coverage and does not block the covered cards (5.4 item 3; C3/R2-1).
2. The `complete` stop requires completion evidence: all accepted, nothing held or repairing, no current final finding (5.8 item 3; C3/R2-2).
3. Release pre-authorization: one optional ledger line `- Release: pre-authorized <remote> <target>` matching `policy.release`; only that pair is exempt; a malformed line refuses `arm`; without it the run ends "ready to release" (5.8 item 8; C3/R2-3, C4/R2-6).
4. `run_gate` refuses every boundary argv (5.14 item 5; C4/R2-1).
5. An absent `task_findings` key means CLEAN for that task at every reader; the O22 void applies per task (5.1 item 4; C4/R2-2).
6. Every final receipt addresses each held tip with an attributed finding or a `cleared` reason; only chains with a current attributed finding get a repair (5.5 items 3-4; C3/R2-6, C4/R2-3).
7. An unstarted review card fully replaced by newer accepted reviews leaves through `supersede` (5.1 item 11; C3/R2-10).
8. The brief is written on close, interrupt and harness end, armed or not; SessionStart shows the newest; it has "Still failing / next phase", mirrored in the PR (5.9; C4/R2-5, C3/N-4, C3/R2-8).
9. New 2.2 cards need `issues` on review and critic receipts; string-only findings stay only for migrated 2.1 cards; the four-grade scale is mapped (5.6; C3/R2-9).
10. Tip rule on repair-diff checks; `hold` of a builder card blocked by the check; accept clean members, reviews and investigators before repairs dispatch (5.1 items 6 and 10, 5.2 item 2; C3/R2-4, C3/R2-5, C4/R2-4).
11. Repetition is also keyed on chain id plus lens category (5.5 item 6; C3/N-1).
12. One Opus repair card per chain, not one batched card: a declared change from the handoff's "batched for efficiency"; the batching is the parallel dispatch of those cards in one final repair wave (5.5 item 4; C3/N-2).
13. The deadline stays required for armed autonomy (K2; C3/N-5).

Also declared: 5.2 item 7 (a held chain accepts without repair) needs every final lens to record `cleared` for it with a reason (5.5 item 4).

**Coordinator decisions after round 3 (binding; recorded as given):**

1. Held cards count as live only when no non-release card is `parked`. When a parked non-release card coexists with a held chain, the Stop hook and `settle` stop `parked-only`, and the brief names both the parked boundary action and the held chains (5.8 item 3; C5/R3-1).
2. The handoff's "merged PR head" clause is dropped (no `gh` dependency in the guard), recorded as CHANGED above; the branch cleanup follow-up deletes children before covering branches (5.19; C5/R3-2).
3. The template comment and the autonomy.md text say the Release line overrides Push and Engine-gated actions for that remote and target only (5.8 items 8.1, 8.5; C5/R3-3).
4. `end_pass_session(nonce)` is named, listed in the 5.10 Files, and maps `pass-exited` to brief reason `ended` (5.10 item 5.4; C5/R3-4).
5. A final finding caused by a non-builder card triages as fix-inline or a new builder card by default, never brief alone (5.5 item 2; C5/R3-5).
6. The engine refuses `repair_of` targeting a card whose current blocking verdict comes from a build-phase repair-diff check; hold it instead (5.2 item 4; C5/R3-6).
7. The brief's Accepted list marks repaired chains (5.9 item 1; C5/R3-7).
8. An unarmed run ends "ready to release" in the brief, the same as an armed run without pre-authorization (5.8 item 8.4, 5.9 items 1 and 4; C5 missing 1). No in-session back-off (5.8 item 4; C5 missing 3).
9. `issues: []` satisfies 5.6 item 3 for a CLEAN report. The 5.6 ticket owns migrating `EngineFixture.review`, `FinalBlockerTests.record` and the integration review posts to emit `issues`, and lands first in the engine wave (5.6 item 6 and flip table; C6/R3-1).
10. test_engine.py:617-639 is rewritten to hold R1 first and listed as a flip; the 5.1 citation is corrected (5.1, 5.2 flip; C6/R3-2).
11. Every listed cap and heading test has a flip row; `_report_context` switches to the "Run brief" prefix and also reads the old "Autonomy report" prefix for runs started under 2.1; the 5.9 line reads "every 2.1 report field survives; the heading and cap lines are replaced" (5.8 flip table, 5.9; C6/R3-3).
12. The busy-lock deny is limited to the delegated classes (release, release-multi, boundary); every other class keeps the raw-state fallback; hook reads poll `LOCK_SH|LOCK_NB` for up to 2 s; Stop on lock timeout allows the stop and writes brief reason "state busy" (5.16 item 5; C6/R3-4).
13. A K risk is added, and the cheap all-accepted check runs before the ledger checks (K14, 5.8 item 3; C6/R3-5).
14. The final-review.md change list states the round order: add all cards of a round, report all, then record receipts, with an integration test (5.5 item 9; C6/R3-6).
15. Park is allowed as an alternative to accept for read-only evidence cards before a repair is dispatched (5.1 item 10; C6/R3-7).
16. Both citations are corrected (5.1 item 4, 5.8 item 8.3; C6/R3-8).

## 11. Removed from the draft

- **C1 B3 and C2F F2:** the parked-branch mechanism (`park --branch`, `parked_branch`, `parked_finding`, `parked_by`), the completion check that a parked tip is not an ancestor of HEAD, and any need to extract parked work from the integration. Held work stays integrated (Round 2).
- **C2F F5 (as a park cascade):** wave-member parking for failed tickets. Failed tickets are held after their review, so a wave review never waits on a failed member; boundary parks keep the 5.1 item 9 procedure.
- **C2F F6:** chain-aware and cascade-aware `unpark`. Chains are never parked for failure, and there is no unhold: a repair moves a held chain on.
- **OD-3 cascade:** cascade-parking of dependents and `test_park_cascades_to_dependents`.
- **OD-13 parking language:** "deny with a park hint" for merged deletion; the 2.1 delete-boundary reason applies unchanged.
- The draft's parked-card exclusions from completion and final coverage (`_pre_release_ids` "non-parked"), `test_completion_ignores_parked_cards`, `test_completion_refuses_parked_branch_inside_head`, `test_final_review_coverage_excludes_parked` and `test_release_with_parked_card_out_of_candidate`.
- The draft's K6 and the reference to a model matrix outside the plugin (N9).
- The draft's open-decision framing; every decision is now settled (section 10).

## 12. Critic finding disposition

C1 (spec lens), round 1:

- **B1:** §5.5 (final repair rounds, re-check, closing confirmation). **B2:** §5.1 item 6 (check covers repairs and chain ancestors). **B3:** removed by held model (§11).
- **S-a:** §5.1 items 9 and 11. **S-b:** §5.4 items 2-3, §5.11 item 1. **S-c:** §5.9. **S-d:** §5.1 item 6, §5.2 item 2. **S-e:** §5.16 item 6. **S-g:** §5.1 item 3. **S-h:** §5.13 item 2.
- **N1:** removed by held model (§5.3). **N2:** §5.10 item 2. **N3:** §5.1 items 1-2. **N4:** §5.1 item 1. **N5:** §5.7 item 3. **N6:** §5.18. **N7:** removed by held model. **N8:** §5.2 item 2, §5.9. **N9:** §7, §11.

C2F (feasibility lens), round 1:

- **F1:** §5.1 item 6. **F2:** removed (§11). **F3:** §5.14 items 1-2, 4. **F4:** removed (§5.3). **F5:** removed for failed tickets; boundary parks §5.1 item 9. **F6:** removed (§11).
- **F7:** §5.13 item 2. **F8:** §5.16 item 2. **F9:** §5.10 items 2, 5 step 7. **F10:** §5.10 item 5 step 4. **F11:** §5.10 item 3. **F12:** §5.14 flip table.
- **F13:** §5.14 item 1, §5.15 item 1. **F14:** §5.11 item 3. **F15:** §5.14 item 4 steps 4-5. **F16:** §5.14 item 3. **F17:** §5.10 item 7, §6, §5.5 item 4. **F18:** §5.10 items 8-9.

Round 2, C3 (spec lens):

- **C3/R2-1:** resolved in §5.4 item 3 (held-tip gate attribution outside coverage; coordinator decision 1).
- **C3/R2-2:** resolved in §5.8 item 3 (`_completion_evidence` on the `complete` stop).
- **C3/R2-3:** resolved in §5.8 item 8 (release pre-authorization line, exact pair).
- **C3/R2-4:** resolved in §5.1 item 6 (tip rule on checks) and §5.2 item 2 (b) (hold of a check-blocked builder card).
- **C3/R2-5:** resolved in §5.1 item 10 (accept before repair, engine-enforced).
- **C3/R2-6:** resolved in §5.5 items 3-4 (every held tip addressed; `cleared` with reason).
- **C3/R2-7:** resolved in §5.14 acceptance (`git branch --del --forc x` is merged-delete) and §5.15 (deny case becomes the multi-branch `x y`).
- **C3/R2-8:** resolved in §5.9 item 1 section 3 (Still failing / next phase) and the PR section.
- **C3/R2-9:** resolved in §5.6 items 3 and 5 (`rev` stamp; `issues` required for 2.2 cards; scale mapping).
- **C3/R2-10:** resolved in §5.1 item 11 (`supersede`) with the completion integration test.
- **C3/N-1:** resolved in §5.5 item 6 (chain id plus lens category).
- **C3/N-2:** resolved in §10 coordinator decision 12 (declared).
- **C3/N-3:** resolved in §5.9 item 2 (reason by mode; `test_close_session_brief_reason_by_mode`).
- **C3/N-4:** resolved in §5.9 item 2 (`last_brief` shown at SessionStart regardless of autonomy).
- **C3/N-5:** resolved in §9 K2 (deadline stays required).
- **C3/N-6:** resolved in §5.8 item 7 (no-session Stop is a no-op; PreToolUse boundaries documented as intended).
- **C3/N-7:** resolved in §5.19 (count re-observed; recount at execution).
- **S-a, S-b, S-d (partial in round 2):** completed by C3/R2-10, C3/R2-1 and C3/R2-4 above.

Round 2, C4 (feasibility lens):

- **C4/R2-1:** resolved in §5.14 item 5 (`run_gate` refuses every boundary argv).
- **C4/R2-2:** resolved in §5.1 item 4 (absent key CLEAN at five readers; per-task O22 void).
- **C4/R2-3:** resolved in §5.5 item 4 (repair only chains with a current attributed finding).
- **C4/R2-4:** resolved in §5.1 item 10 and §5.5 item 4 (accept before repair; `test_final_lens_then_repair_then_completion`).
- **C4/R2-5:** resolved in §5.9 item 2 (brief on interrupt, harness end and close; SessionStart).
- **C4/R2-6:** resolved in §5.8 item 8.
- **C4/R2-7:** resolved in §5.14 items 4.1 and 6 (hooks.py:196 change; `decision_category` corpus key).
- **C4/R2-8:** resolved in §5.16 hypothesis H4 and item 8.
- **C4/R2-9:** resolved in §5.10 item 5 steps 3-4 (pass nonce; foreign session left, exit 2).

Round 3, C5 (spec lens):

- **C5/R3-1:** resolved in §5.8 item 3 (held is live only with no parked non-release card; `parked-only` stop from the Stop hook and `settle`; round-3 decision 1).
- **C5/R3-2:** resolved in §10 (PR-head clause CHANGED) and §5.19 (children before covering branches).
- **C5/R3-3:** resolved in §5.8 items 8.1 and 8.5 (Release line overrides Push and Engine-gated actions for the pair only).
- **C5/R3-4:** resolved in §5.10 item 5.4 (`end_pass_session(nonce)`, `pass-exited` to `ended`) and §6.
- **C5/R3-5:** resolved in §5.5 item 2 (non-builder cause triaged `inline` or `card`, never `brief` alone).
- **C5/R3-6:** resolved in §5.2 item 4 (engine refuses repair of a check-blocked card unless held or final-attributed).
- **C5/R3-7:** resolved in §5.9 item 1 section 8 (Accepted marks repaired chains).
- **C5 missing 1 and 3:** resolved in §5.8 item 8.4, §5.9 items 1 and 4 (unarmed run ends "ready to release") and §5.8 item 4 (no in-session back-off). Missing 2 and 4 are C5/R3-1 and C5/R3-2.

Round 3, C6 (feasibility lens):

- **C6/R3-1:** resolved in §5.6 items 3 and 6 (`issues: []` is CLEAN; helper migration first in the engine wave; flip table).
- **C6/R3-2:** resolved in §5.1 Current (citation) and the §5.2 flip of test_engine.py:617-639.
- **C6/R3-3:** resolved in the §5.8 flip table, §5.9 item 2 (`_report_context` prefixes) and the §5.9 no-lost-functionality line.
- **C6/R3-4:** resolved in §5.16 item 5 (delegated classes only, non-blocking poll, Stop `state busy`).
- **C6/R3-5:** resolved in §5.8 item 3 (all-accepted check first) and §9 K14.
- **C6/R3-6:** resolved in §5.5 item 9 (round order; `test_final_receipt_stale_when_card_added_after_it`).
- **C6/R3-7:** resolved in §5.1 item 10 (park as an alternative to accept for read-only evidence cards).
- **C6/R3-8:** resolved in §5.1 item 4 (engine.py:762-764, 805-806) and §5.8 item 8.3 (hooks.py:194-195, 200-210).

## 13. Out of scope

- T3 Code support: a separate add-on plugin after 2.2; the core stays Claude-native.
- Any change to the downstream application repositories, including removing their relaunch scripts and fixing their memory files. Those are the follow-up PRs the handoff assigns to them.
- Moving old plugin cache versions to the Trash (a user step).
- Deleting this repository's merged branches: the post-release card in 5.19.

## 14. Self-check

- **Placeholders:** none. Every "New" names files and tests.
- **Against S1 to S7 and Rounds 2-3:**
  - S1 holds: one wave review, one repair-diff check, no third review (5.1).
  - S2 as amended holds: Sonnet, then Opus repair, then hold. No count stops a run (5.2, 5.5, 5.8).
  - S3 is superseded by Round 2: held work stays in the integration and in the brief (5.2, 5.9).
  - S4, S5 and S6 hold (5.4, 5.5, 5.7).
  - S7 holds: each section names its replacements.
  - Round 3 holds: the final loop has no cap (5.5), materiality lives in both skills, the schema and the engine rule (5.6), and no decision is open (10).
  - The Coordinator ruling holds: release is pre-authorized only by an explicit ledger line naming the configured pair (5.8 item 8).
  - Round 2 critics: every C3 and C4 id has a disposition in section 12, and the 13 coordinator decisions are recorded in section 10.
  - Round 3 critics: every C5 and C6 id has a disposition in section 12, and the 16 coordinator decisions after round 3 are recorded in section 10.
- **Untestable requirements:** none. Each changed behavior names at least one test a builder can write first.
- **Readiness:** ready for independent critic challenge (spec and feasibility) and then planning.
