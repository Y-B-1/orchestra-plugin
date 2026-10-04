# Orchestra 2.2.0 design specification

Card D1, mode design. Base: `origin/main` at `0e778c73292d72dbc4ce9a6d725c97cb72bc1d31` (Orchestra 2.1.0, tag `v2.1.0`). All citations are to that commit and are relative to the repository root. The plugin root is `plugins/orchestra`; `P/` below abbreviates it.

This document turns the seven settled decisions and the 2.2 handoff scope into a change set that can be tested. It decides nothing that is still open. Every choice not fixed by a settled input sits in section 10 (Open decisions) with options and one recommendation. Where a change-set section depends on such a choice, it names the decision (`OD-n`) and describes the recommended option. If the user picks a different option, that section changes with it.

## 0. Evidence labels and do-not-touch list

Every factual claim carries one label:

- **OBSERVED**: read in the file at the cited line, or seen in a command run in this assignment (git 2.50.1, Python 3, Node, in this worktree or in a scratch directory outside it).
- **REASONED**: inferred from observed facts. The inference is stated.
- **UNKNOWN**: not established. The section says what would settle it.

Proposals for 2.2 behavior are design, not claims. They are written as "New:".

**Do not touch, for this card:** every path except `docs/SPEC-v2.2.md`.

**Do not touch, for the 2.2 build cards that follow this design:**

- the downstream application repositories (the Devops and Commercial repositories), including their `scripts/orca-ralph.sh` files
- the installed plugin cache
- the uncommitted files in the main checkout (the `AGENTS.md` and `.gitignore` edits and the untracked `.agents/skills/e2e/`)
- other sessions' worktrees
- the read-only source reference repositories named in `docs/SKILL-SOURCES.md`
- `docs/SPEC-v2.md` and `docs/PLAN-v2.md`, which are the historical 2.0 records

`CONTEXT.md` is not owned by this card, so the proposed glossary is in section 1. A later card copies the entries into `CONTEXT.md` if the user wants that.

## 1. Glossary (proposed entries)

| Term | Meaning in 2.2 |
|---|---|
| Wave | A named set of builder cards that run together and are reviewed together. A card joins a wave through its `wave` field (OD-1). |
| Wave review | One checkpoint-mode code-reviewer card whose `review_of` covers every builder card of one wave. Its findings are attributed to individual cards. |
| Repair-diff check | One checkpoint-mode review of only the repair commits of a wave, against the findings they answer (checkpoint.md "Re-review of a fix round"). |
| Escalation rung | A card's position in the ladder: implementation (Sonnet builder), then repair (Opus builder `repair` preset), then park. |
| Park | Moving a card, or a whole repair chain, to the `parked` state. Its work stays on its own branch, out of the integration, and is listed in the morning brief. |
| Parked branch | The branch that holds a parked card's commits (`parked_branch`). |
| Last finding | The finding that caused the park (`parked_finding`). |
| Morning brief | The autonomy report appended to `<state>/progress.md` when autonomy stops. It extends the 2.1 "Autonomy report". |
| Findings ledger | The new `findings` list in `state.json`. It records each finding the coordinator rejected, deferred or triaged, with the reason. It is distinct from the progress ledger (`progress.md`), the autonomy ledger (`autonomy.md`) and the critic `ledger` axis. |
| Out-of-scope finding | A defect a reviewer sees outside the change under review. It is raised only by final-review lens cards, in a separate `out_of_scope` list, and never blocks the verdict. |
| Triage | The coordinator's disposition of an out-of-scope finding: `inline` (fix now), `card` (a new card, batch or plan) or `brief` (into the morning brief). |
| Lens card | One final-review code-reviewer card with a `Lens:` line. |
| Standards lens | The final-review lens for repository rules and the charter (`P/skills/orchestra-review/references/standards.md`, new), run on Sonnet medium. It is distinct from the critic `standards` conformance axis, which stays. |
| Evidence reuse | Reviewers cite the operator's gate receipts on the same artifact instead of rerunning the suites. |
| Keep/remove lists | Two sections in a builder brief that name exactly what must survive and what must go. |
| Relaunch harness | `orchestra.py relaunch`, the plugin-level loop that starts a fresh headless coordinator pass until the autonomy run ends. |
| Pass | One fresh headless coordinator session started by the relaunch harness. |
| Progress signature | A digest of engine state. A pass that leaves it unchanged is a stall. |
| Idle | Autonomy has no running or reported card and no ready card. |
| Merged branch | A branch whose tip is an ancestor of the default branch, or whose tree equals the tree of a first-parent commit of the default branch (a squash or rebase landing), or, under OD-12, an ancestor of such a branch. |
| Abbreviated long option | A unique prefix of a git long option, which git's parse-options accepts (for example `--al` for `--all`). |

## 2. Settled inputs (fixed, not reopened)

- **S1:** Wave-level review, not per-ticket: builders finish a wave, then one wave reviewer, then builders fix, then one check of the repair diff only. One loop per wave.
- **S2:** Repair escalation is Sonnet builder, then Opus builder `repair`, then park. A cap never stops or blocks a run. No "march of nines".
- **S3:** A parked ticket stays out of the PR, on its own branch, and goes into the user's brief.
- **S4:** Gate between waves only when the next wave depends on the previous wave's code.
- **S5:** Final review is parallel lenses. Correctness and security run on Opus high; the standards/charter lens runs on Sonnet medium.
- **S6:** Out-of-scope findings are raised only at the final review. The coordinator triages each into one of three: fix inline, a new card/batch/plan, or the user's brief.
- **S7:** No lost functionality. Every change keeps existing behavior or names its replacement.

These bind every build card, carried over from the standing orders:

- Tests come first for new behavior.
- Stage explicit paths only.
- Use only Opus 5.5 and Sonnet 5.5, with no 1M-context variants.
- The charter forbids publishing personal paths or product delivery state, so the repository text never names local home paths or downstream product names.

## 3. Scope map (every handoff scope bullet has a heading)

| Handoff bullet | Heading |
|---|---|
| Review and repair model, items 1 to 6, in coordination.md, repair-rounds.md, final-review.md, roles.json/models.json (standards-lens preset), engine (`review_of` on a wave, park state) | 5.1 to 5.6, with engine detail in section 6 and the model delta in section 7 |
| Autonomy: park-and-continue, deadline as the only stop | 5.7 |
| Autonomy: morning brief | 5.8 |
| Autonomy: fresh-context relaunch replacing `orca-ralph.sh` | 5.9 |
| Efficiency: evidence reuse | 5.10 |
| Efficiency: findings ledger | 5.11 |
| Efficiency: keep/remove lists in briefs | 5.12 |
| Guard: merged-branch deletion | 5.13 |
| Guard: abbreviated long options | 5.14 |
| Guard: fail-closed on chained commands | 5.15 |
| Repo follow-ups after 2.2 (the plugin repository's branch deletion) | 5.16. The downstream repositories are out of scope (section 11). |
| Out of scope: T3 Code support | 11 |

## 4. Test conventions

- **Python:** `python3 -m unittest discover -s tests -k <test_name>` from the repository root. The full suite is `python3.11 -m unittest discover -s tests` (README.md:92, OBSERVED).
- **TypeScript guard and mods:** `claude plugin test` with function hooks enabled (docs/VALIDATION.md:42, OBSERVED). Test names below are the `test('<name>', ...)` titles.
- **Guard corpus:** cases go in `P/config/guard-corpus.json`. `tests/test_guard_corpus.py` and `P/hooks/mod/guard.test.ts` check parity against both guards.
- **Skill text:** phrase files go under `tests/skill_phrases/`, checked by `tests/test_skills.py`.
- **Ordering:** each listed test must fail on the base commit and pass after the change, unless it is marked "regression (passes today)".

## 5. Change set

### 5.1 Wave-level review (S1)

**Current (OBSERVED):**

- coordination.md:31 lists the states and has no wave concept.
- coordination.md:38 says early review goes to consequential foundations, and low-risk related tickets are grouped under one review "with stated coverage".
- coordination.md:40 gives a per-ticket checkpoint example (R1 reviews B1).
- In the engine, `review_of` is already a list of task ids (`P/scripts/orchestra_core/engine.py:559-567`).
- `record_review` stores one `findings` list for every covered task (engine.py:734-773).
- `_review_verdicts` applies that list to each covered task (engine.py:775-796). REASONED: one finding in a group review therefore blocks `accept` of every covered card (engine.py:806-807), including cards with no defect.

**New:**

1. A task may carry `wave` (a non-empty string). A review card may name `"wave:<W>"` in `review_of`.
   - `add_task` resolves it to the ids of every non-review card in wave W, freezes the list, and stores plain ids.
   - Adding a card to a wave that already has a wave review is refused: "Wave W already has a review; start a new wave".
2. The wave review is code-reviewer `Mode: checkpoint` over the wave.
3. The review report JSON may carry `task_findings`: an object that maps each covered task id to its list of findings.
   - `record_review` refuses a report where a key is not a covered task, or where the ordered union of the values differs from `findings`.
   - A task's verdict uses its own list. A covered task with an empty list has a CLEAN verdict from that receipt.
   - Without `task_findings`, 2.1 behavior holds: every covered task gets the whole list.
4. Builders fix through repair cards (5.2). Then one repair-diff check runs: a single checkpoint card whose `review_of` lists every repair card of the wave and whose brief names the fix range.
5. One loop per wave: after the repair-diff check, no third review of that wave runs. A card still holding findings parks (5.2, 5.3).
6. A consequential foundation becomes a wave of one, reviewed before dependent waves start. This replaces coordination.md:38's "early independent review".

**Files:**

- `P/scripts/orchestra_core/engine.py`: `add_task`, `record_review`, `_review_verdicts`, `_validate_state`.
- `P/scripts/orchestra.py`: `add` help text.
- `P/skills/orchestra/references/coordination.md`: Kanban, the example, and the waves paragraph.
- `P/skills/orchestra-review/references/checkpoint.md`: wave scope and `task_findings`.
- `P/skills/orchestra/references/cli.md`, `docs/cli.md`.
- `tests/test_engine.py`, `tests/skill_phrases/orchestra.json`, `tests/skill_phrases/orchestra-review.json`.

**No lost functionality:**

- Per-ticket review is still expressible as a wave of one.
- `review_of` with explicit ids still works unchanged.
- A report without `task_findings` behaves exactly as in 2.1.
- Review independence (engine.py:752-753) and artifact binding (engine.py:762-764) are unchanged.

**Acceptance tests (tests/test_engine.py):**

| Test | Behavior |
|---|---|
| `test_wave_review_of_resolves_wave_members_at_add` | A review card with `review_of: ["wave:W1"]` stores the ids of W1's builder cards. |
| `test_adding_card_to_reviewed_wave_is_refused` | `add` of a W1 card after the W1 review exists raises "already has a review". |
| `test_wave_review_task_findings_block_only_named_card` | The wave covers B1 and B2, and the report has `task_findings` `{B1: [f], B2: []}`. B2 can be accepted. B1 is refused with "current review findings". |
| `test_task_findings_must_match_findings_union` | A mismatched union is refused, and so is an unknown key. |
| `test_review_without_task_findings_blocks_all_covered` | Regression (passes today): the 2.1 group semantics hold. |

### 5.2 Repair escalation: Sonnet builder, then Opus repair, then park (S2)

**Current (OBSERVED):**

- repair-rounds.md:8-12: rounds 1 to 3 use "the builder default model", round 4 is an Opus dispatch override, and round 5 is a breaker to critic `judge`, then design or planning, and the user is told.
- repair-rounds.md:6: "The engine does not enforce the cap; you do."
- `P/config/models.json:49-53` already sets the builder `repair` preset to Opus medium with `"dispatch": "override"`. REASONED: this contradicts repair-rounds.md:10, which puts rounds 1 to 3 on the default (Sonnet) model.
- The engine allows a repair of a repair: the `repair_of` target must be a builder card in state reported or accepted with checked findings, and a repair card is itself a builder card (engine.py:568-589).

**New (interpretation per OD-2, recommended option I2):**

1. The first rung is the Sonnet implementation card that the wave review found defective.
2. The second rung is one builder `repair` card on Opus medium (dispatch override, unchanged).
3. The engine refuses a repair whose `repair_of` is itself a repair card: "Escalation ends at one repair; park the chain". This is the only new engine refusal for S2.
4. If the repair-diff check still has findings for that card, the coordinator parks the chain (5.3).
5. No round counter, cap or breaker stops the run. repair-rounds.md is rewritten to this ladder.
6. When the user is present (no autonomy), the coordinator may still send a parked card to critic `judge` and then design. This keeps the 2.1 round-5 route as an option, not a stop.

**Files:**

- `P/scripts/orchestra_core/engine.py`: `add_task`.
- `P/skills/orchestra/references/repair-rounds.md` (rewrite).
- `P/skills/orchestra/references/parallel.md:16`: the round-4 wording.
- `P/skills/orchestra-build/references/repair.md:7`: rung instead of round number.
- `P/config/roles.json`: the builder prompt sentence is unchanged, so no contract change.
- `tests/test_engine.py`, `tests/skill_phrases/orchestra.json`, `tests/skill_phrases/orchestra-build.json`.

**No lost functionality:**

- The Opus valve stays, and so does the critic-judge route (as a user-present option).
- Rounds 1 to 3 on Sonnet repair go away. Their replacement is the wave fix loop. This is named under S7.
- Repair chains created under 2.1 with depth greater than one stay valid history. The new refusal applies only to new `add` calls.

**Acceptance tests:**

| Test | Behavior |
|---|---|
| `test_repair_of_repair_is_refused_with_park_hint` (test_engine.py) | `add` of a repair whose `repair_of` is a repair card raises the escalation message. |
| `test_first_repair_of_builder_still_allowed` (test_engine.py) | Regression (passes today). |
| `repair-rounds ladder` phrase (skill_phrases/orchestra.json) | repair-rounds.md contains the ladder sentence and contains no "Round 5" breaker line. |

### 5.3 Park state; a parked ticket stays out of the PR (S3)

**Current (OBSERVED):**

- `park` (engine.py:609-628):
  - refuses a card under repair and asks for its open repair card instead (engine.py:615-618)
  - drops the assignment and the report
  - puts the ancestors back to `repairing` (engine.py:623-627)
- `unpark` returns the card to `queued` (engine.py:637-644).
- Completion needs every task accepted (engine.py:908-909). A final review must cover all tasks or all pre-release tasks (engine.py:749-750).
- autonomy.md:22: "Parked work blocks `finish`." REASONED: a parked card therefore blocks the PR, which contradicts S3.
- No branch or finding is recorded on park.

**New:**

1. `park TASK --reason TEXT [--branch B] [--finding TEXT]`.
   - `--branch` is required when the card or its chain has a builder report. The engine checks that `refs/heads/B` exists.
   - The branch is stored as `parked_branch` and the finding as `parked_finding`.
2. Parking the open repair card of a chain parks the whole chain: the ancestors take state `parked` with the same reason. `unpark` of the open card returns it to `queued` and the ancestors to `repairing`.
3. Parked cards and parked chains are excluded from:
   - the "all tasks accepted" check in `_completion_evidence`
   - the required coverage set in `record_review` for final reviews and in `_review_verdicts(final=True)`

   `_pre_release_ids` becomes "non-release, non-parked".
4. Completion refuses when any `parked_branch` tip is an ancestor of `HEAD`: "Parked work is inside the candidate: B". This proves the parked commits stayed out of the integration.
5. Dependents of a parked card are cascade-parked with the reason "depends on parked X" (OD-3).

**Files:**

- `P/scripts/orchestra_core/engine.py`: `park`, `unpark`, `_completion_evidence`, `_pre_release_ids`, `record_review`, `_validate_state`.
- `P/scripts/orchestra.py`: `park` arguments.
- `P/skills/orchestra/references/autonomy.md`: line 22 rewritten.
- `P/skills/orchestra/references/finishing.md`, `cli.md`, `docs/cli.md`.
- `tests/test_engine.py`, `tests/test_integration.py`.

**No lost functionality:**

- `park` and `unpark` keep their 2.1 signatures, and `--reason` is still required.
- The 2.1 guarantee "parked work blocks finish" is replaced by "parked work is provably outside the candidate and listed in the brief". This is named under S7.
- Parking a card that has no builder report needs no branch, exactly as in 2.1.

**Acceptance tests (test_engine.py unless noted):**

| Test | Behavior |
|---|---|
| `test_park_builder_with_report_requires_existing_branch` | Park without `--branch`, or with a missing ref, is refused. With a real branch, it is stored. |
| `test_park_open_repair_parks_whole_chain` | Ancestors become `parked`. `unpark` restores `queued` and `repairing`. |
| `test_completion_ignores_parked_cards` | Every non-parked card is accepted, there is a final review over them, and the gates pass: `check_completion` succeeds. |
| `test_completion_refuses_parked_branch_inside_head` | Merge the parked branch into HEAD and completion is refused, naming the branch. |
| `test_final_review_coverage_excludes_parked` | A final review that covers exactly the non-parked pre-release ids is accepted. |
| `test_park_cascades_to_dependents` | A queued dependent of a parked card becomes parked with reason "depends on parked". Applies under OD-3 option A. |
| `test_release_with_parked_card_out_of_candidate` (test_integration.py) | End to end: release proceeds with one parked card on its own branch. |

### 5.4 Gate between waves only on code dependency (S4)

**Current (OBSERVED):**

- The engine does not schedule gates. A gate is a receipt recorded with `gate NAME -- argv` (engine.py:818-862).
- coordination.md:40 places "G1 gates" before final review in the example.
- No rule ties gates to waves.

**New:**

1. A wave-boundary gate runs before wave N+1 only when a card of wave N+1 meets either test:
   - it lists a wave-N card in `dependencies`
   - its `files` or `inputs` name a path that a wave-N card owns
2. Otherwise no gate runs between the waves. The operator gates the integrated candidate once before final review (5.10).
3. `orchestra.py board` and `status` show, for each wave, whether the next wave depends on it. The engine computes this from the stored fields. It schedules nothing.

**Files:**

- `P/skills/orchestra/references/coordination.md`.
- `P/scripts/orchestra_core/engine.py`: a read-only helper used by `status`.
- `P/scripts/orchestra.py`: `board` output.
- `tests/test_engine.py`, `tests/skill_phrases/orchestra.json`.

**No lost functionality:** Gates stay available at any time. Only the procedure stops requiring them between independent waves.

**Acceptance tests:**

| Test | Behavior |
|---|---|
| `test_status_marks_wave_dependency_from_dependencies_and_paths` (test_engine.py) | W2 depends on W1 through `dependencies` and through an owned path, so `depends_on_previous` is true. An unrelated W3 shows false. |
| `wave gate rule` phrase (skill_phrases/orchestra.json) | coordination.md states the S4 rule. |

### 5.5 Final review as parallel lenses; standards-lens preset (S5)

**Current (OBSERVED):**

- final-review.md:8-10: four lens cards (correctness, architecture, security, cleanliness), all code-reviewer final.
- models.json:68-71: final runs on Opus high.
- `P/skills/orchestra-review/references/final.md:16-21` maps the lenses to categories:
  - correctness covers requirements, correctness, tests and standards
  - architecture covers architecture
  - security covers security
  - cleanliness covers cleanup
- Completion needs the policy's `required_review_categories`, all seven by default (engine.py:35, 38, 919-921).
- The roles.json code-reviewer prompt says "the four lens cards together cover every category".
- `P/scripts/generate.py:49-55` emits a variant agent file for each preset whose model or effort differs from the role default, unless the preset is a dispatch override.

**New (lens layout per OD-4, recommended option A):**

1. Three parallel lens cards, each code-reviewer `Mode: final` with a `Lens:` line:

   | Lens | Agent | Categories |
   |---|---|---|
   | `correctness.md` | `orchestra:code-reviewer` (Opus high) | requirements, correctness, tests, architecture. The architecture lens checks move into it. |
   | `security.md` | `orchestra:code-reviewer` (Opus high) | security |
   | `standards.md` (new) | `orchestra:code-reviewer-standards` (Sonnet medium) | standards, cleanup. Holds the repository rules, the charter, and the cleanliness checks. |

2. `models.json` gains `code-reviewer.presets.standards = {model: claude-sonnet-5-5, effort: medium}` with no dispatch override, so the generator writes `agents/code-reviewer-standards.md`. A variant agent can run inside a Workflow script, which a dispatch override cannot (parallel.md:16). `VARIANT_NOTES` gains `('code-reviewer', 'standards')`: " Mode: final. Lens: standards.md. Repository rules, charter and cleanliness."
3. roles.json code-reviewer modes stay `["checkpoint", "final"]`. REASONED: the run contract hash is built from the role-to-modes map only (engine.py:43-65), so 2.1 runs keep their contract (section 8). Only the prompt sentence changes to "the three lens cards".
4. The 50-changed-line specialist rule is unchanged (final-review.md:18-22).

**Files:**

- `P/config/models.json`, `P/config/roles.json` (prompt text only).
- `P/scripts/generate.py`: `VARIANT_NOTES`.
- `P/agents/code-reviewer-standards.md` (generated).
- `P/skills/orchestra/references/final-review.md`.
- `P/skills/orchestra-review/references/final.md`, `correctness.md`, `standards.md` (new, with a provenance header).
- `P/THIRD-PARTY-NOTICES` and `docs/SKILL-SOURCES.md` if `standards.md` derives from a source.
- `AGENTS.md` (the model sentence).
- `docs/models.md`, `docs/roles.md`.
- `tests/test_packaging.py`, `tests/test_skills.py` (the TABLE), the phrase files.

**No lost functionality:**

- All seven categories stay covered by final verdicts, so `_completion_evidence` is unchanged.
- The architecture checks are kept, inside the correctness lens. The cleanliness checks are kept, inside the standards lens.
- The critic `standards` axis is unchanged.
- The architecture.md and cleanliness.md files stay as included checklists. Under OD-4 option A they are no longer standalone lens names.

**Acceptance tests:**

| Test | Behavior |
|---|---|
| `test_standards_preset_is_sonnet_medium_variant_file` (test_packaging.py) | The preset exists, has no `dispatch` key, and `agents/code-reviewer-standards.md` has `model: claude-sonnet-5-5`, `effort: medium` and read-only `disallowedTools`. |
| `test_role_matrix_files_and_read_only_enforcement` (updated, test_packaging.py) | The expected set includes `code-reviewer-standards.md`. |
| `test_final_lens_table_covers_every_category` (test_skills.py) | Parsing the final.md table gives a union equal to engine `CATEGORIES`. |
| `test_generated_agents_match_the_canonical_source` | Regression: `generate.py --check` exits 0. |
| `test_contract_hash_unchanged_by_lens_change` (test_engine.py) | `_contracts()[1]` equals the digest of the 2.1 role-to-modes map. |

### 5.6 Out-of-scope findings only at final review; triage (S6)

**Current (OBSERVED):**

- review SKILL.md:19 flags scope drift (changed files the ticket does not need), which is an in-scope finding about the diff.
- final.md:23: "Findings outside your lens go in the summary as a note."
- No rule covers defects found outside the change.
- triage.md:23 records rejected enhancements as out of scope in the project's own file.
- The engine has no field for out-of-scope findings.

**New:**

1. checkpoint.md: wave and repair-diff reviewers raise nothing outside the reviewed change.
2. Final lens reports may carry `out_of_scope`, a list of non-empty strings that never changes the verdict.
3. `record_review` refuses `out_of_scope` on a non-final receipt: "Out-of-scope findings are raised only at the final review".
4. The coordinator triages each item with `orchestra.py finding add --review <receipt-id> --kind out_of_scope --index N --disposition inline|card|brief --reason TEXT [--card ID]`, stored in the findings ledger (5.11).
5. Under OD-5 option B, completion refuses while any `out_of_scope` item on a current final receipt has no triage entry.

**Files:**

- `P/scripts/orchestra_core/engine.py`: `record_review`, `_completion_evidence`.
- `P/scripts/orchestra.py`: the `finding` subcommand.
- `P/skills/orchestra-review/SKILL.md` (verdict JSON fields), `references/checkpoint.md`, `references/final.md`.
- `P/skills/orchestra/references/final-review.md` (triage routing), `triage.md`.
- `tests/test_engine.py`, the phrase files.

**No lost functionality:**

- Scope-drift findings stay (they are in scope).
- The final.md note for out-of-lens findings stays.
- triage.md:23 stays for enhancement requests.

**Acceptance tests (test_engine.py):**

| Test | Behavior |
|---|---|
| `test_checkpoint_review_with_out_of_scope_is_refused` | A non-final report with `out_of_scope` is refused. |
| `test_final_out_of_scope_does_not_block_verdict` | A CLEAN final with `out_of_scope` items records CLEAN. |
| `test_completion_requires_triage_of_out_of_scope` | Completion is refused until each item has a `finding add` entry. Applies under OD-5 option B. |
| `test_finding_add_rejects_bad_disposition_and_index` | An unknown disposition, or an index out of range, is refused. |

### 5.7 Park-and-continue; the deadline as the only stop (autonomy)

**Current (OBSERVED):**

- `hook_stop` (engine.py:1084-1118) stops for each of these reasons:
  - `ledger-tampered`
  - `deadline`
  - `complete`
  - `cap-stalls` (engine.py:1106-1107)
  - `cap-passes` (engine.py:1108-1109)
  - `parked-only` or `no-ready-card` when nothing is live (engine.py:1110-1112)
- A stall is a pass with no newly accepted card (engine.py:1101-1102).
- `parse_ledger` requires `max_passes` from 1 to 20 and `max_stalls` from 1 to 2 (engine.py:96-106).
- The template asks for both (`P/config/autonomy-template.md:6-7`).
- `autonomy.ts:77, 81, 119` render "pass N/M" and "stalls N/M".
- autonomy.md:18: "A stop is final for that arm".

**New:**

1. `cap-passes` and `cap-stalls` are removed as stop reasons. No count ever stops the loop.
2. Stop reasons that remain:
   - `deadline`
   - `complete` (every completion check passed on the current artifact)
   - `ledger-tampered` (safety)
   - `disarmed` (the user)
   - `parked-only` / `no-ready-card` (idle, OD-6)
3. A stall is a pass that leaves the progress signature (5.9) unchanged. Stalls are counted and reported. Under OD-7 option C they never stop or park, and in the relaunch harness they slow the next launch.
4. `max_passes` and `max_stalls` become optional (OD-8). A 2.1 ledger that carries them still arms and parses. The values are recorded and shown but never enforced.
5. The template drops both lines.
6. The continuation text drops "of %d".
7. A card that fails a gate, a review or its repair rung is parked with its branch (5.3), and the loop takes the next ready card.

**Files:**

- `P/scripts/orchestra_core/engine.py`: `parse_ledger`, `hook_stop`, `_validate_state` (autonomy ints become optional), `autonomy_status`, `_report_text`.
- `P/config/autonomy-template.md`.
- `P/hooks/mod/autonomy.ts`, `P/hooks/mod/autonomy.test.ts`.
- `P/skills/orchestra/references/autonomy.md`.
- `docs/hooks.md`.
- `tests/test_engine.py`, `tests/test_hooks.py`.

**No lost functionality:**

- The deadline, completion, tamper and disarm stops are unchanged.
- The idle stop is kept under OD-6 option A.
- The pass and stall counts are still recorded and reported.
- Removing the two caps is the S2 change, and its replacement is the deadline. This is named under S7.

**Acceptance tests:**

| Test | Behavior |
|---|---|
| `test_hook_stop_never_stops_on_pass_count` (test_engine.py) | 50 continuing passes with live work return continuation text each time, with no `cap-passes`. |
| `test_hook_stop_never_stops_on_stalls` (test_engine.py) | Ten stalled passes keep continuing. `stalls` reads 10. |
| `test_hook_stop_deadline_still_stops` (test_engine.py) | Regression. |
| `test_ledger_without_caps_arms` (test_engine.py) | A ledger with no `max_*` lines arms. |
| `test_2_1_ledger_with_caps_still_arms_and_caps_are_ignored` (test_engine.py) | Both fields are present, and the loop passes beyond `max_passes`. |
| `band renders pass count without maximum` (autonomy.test.ts) | Status without `max_passes` renders "pass 3". |

### 5.8 Morning brief

**Current (OBSERVED):**

- `_report_text` (engine.py:1058-1072) writes these sections:
  - "## Autonomy report <time>"
  - the stop reason
  - passes N of M and stalls N of M
  - accepted
  - parked, as `id: reason`
  - failures (gate exits and BLOCKED reviews since arm)
- `_stop_autonomy` appends the report to `<state>/progress.md` (engine.py:1045-1056).
- SessionStart shows the first 2000 characters and the path (`P/scripts/orchestra_core/hooks.py:261-269`).

**New:** `## Morning brief <time>` replaces the heading. The sections come in this order, so the 2000-character SessionStart excerpt keeps what needs the user:

1. stop reason, deadline, passes, stalls
2. **Needs you**: each parked card (unpark, merge or drop), each `brief`-triaged out-of-scope finding, each deferred finding, and any staged approval-boundary action named in a park reason
3. **Parked**: `id (role/mode): reason; branch B; last finding F`
4. **Deferred findings**: from the findings ledger, with source review and reason
5. **Out-of-scope findings for you**: those triaged `brief`
6. **Accepted**: as in 2.1
7. **Failures**: as in 2.1

**Files:**

- `P/scripts/orchestra_core/engine.py`: `_report_text`.
- `P/scripts/orchestra_core/hooks.py`: the label text only.
- `P/skills/orchestra/references/autonomy.md`, `handoff.md` (a progress-ledger note).
- `tests/test_engine.py`, `tests/test_hooks.py`.

**No lost functionality:** Every 2.1 line survives: the stop reason, passes, stalls, accepted, parked id and reason, and failures. Only the heading word and the order change. `autonomy.ts` matches on `last_stop_reason`, not on the heading (autonomy.ts:81, OBSERVED).

**Acceptance tests:**

| Test | Behavior |
|---|---|
| `test_morning_brief_lists_parked_branch_and_last_finding` (test_engine.py) | The brief carries the branch and the finding. |
| `test_morning_brief_lists_deferred_and_brief_triaged_findings` (test_engine.py) | Both kinds appear under their sections. |
| `test_morning_brief_needs_you_precedes_accepted` (test_engine.py) | Ordering. |
| `test_session_start_excerpt_contains_needs_you` (test_hooks.py) | With 40 accepted cards, the 2000-character excerpt still holds the "Needs you" section. |
| `test_morning_brief_keeps_2_1_lines` (test_engine.py) | Regression: the stop reason, passes, stalls, accepted, parked and failures lines are present. |

### 5.9 Fresh-context relaunch harness (replaces the downstream `orca-ralph.sh`)

**Current (OBSERVED, downstream harness read-only):**

- The downstream harness is a bash loop with `-n` max passes (default 20) and `-N` stall streak (default 2).
- It takes a prompt file, a model, and `--permission-mode` (default `bypassPermissions`), plus `--` for an alternative CLI.
- It refuses unless `docs/orchestra/STATE.md` shows an OPEN run.
- Each pass runs `claude -p "<prompt>" --permission-mode <mode>` and greps the last `SIGIL:` line.
- Its progress signature is the main tip, HEAD, `git status`, plan files and the memory file.
- Exit codes: 0 DONE (only with observed progress and an optional verify), 3 STALLED, 4 EXHAUSTED, 5 BLOCKED-USER or not ready, 6 NEEDS-APPROVAL.
- It keeps its state in the repository under `.orchestra/ralph/`.
- REASONED from the handoff: it exits 5 at once under 2.x because STATE.md is gone.

**Current (OBSERVED, plugin):**

- `_autonomy_on` requires an active coordinator session (engine.py:980-982).
- `end_harness_session` clears active autonomy when the bound session ends (engine.py:488-500, via `_kept_autonomy` at 478-481).
- `arm_autonomy` needs an active session (engine.py:995-996).
- REASONED: 2.1 autonomy therefore cannot outlive the session that armed it, which is the capability gap the handoff names.

**New:**

1. `orchestra.py autonomy arm --relaunch` arms as today and sets `autonomy.relaunch = true`.
2. While `relaunch` is true, `end_harness_session` ends the coordinator session but keeps autonomy armed. `_autonomy_on` stays false between passes, because no session is active, so guard behavior between passes is unchanged.
3. `orchestra.py autonomy settle` is new and lease-free, like `arm`/`disarm`.
   - It evaluates the same stop conditions as `hook_stop` (tamper, deadline, complete, idle) on an armed autonomy, whether or not a session is active, without counting a pass.
   - If one holds, it stops autonomy with that reason, which writes the morning brief. Otherwise it is a no-op.
   - It prints JSON: `{armed, stopped, reason, signature, passes, stalls}`.
4. `orchestra.py relaunch --permission-mode MODE [--model ID] [--launcher ARGV...]` runs from the repository in the user's terminal. The loop:
   1. Preconditions: an active run exists; autonomy is armed with `relaunch`; no coordinator session is active. If a session is active, it says "End the interactive session first" and exits 2.
   2. It calls `settle`. If the run stopped, it exits with the code for that reason.
   3. It launches one pass: `claude -p "$(cat P/config/relaunch-prompt.md)" --permission-mode MODE [--model ID] --output-format text`, with cwd set to the repository and output going to `<state>/relaunch/pass-N.log`. `--launcher` replaces `claude -p ...`, with the prompt on stdin, as the downstream `--` did. Tests use it.
   4. After the pass exits: if the engine session is still active and bound to a harness session id, the harness ends it the way `end_harness_session` does, with outcome `pass-exited`. This covers a pass killed without SessionEnd.
   5. It records the signature in `<state>/relaunch/harness.json` (`{pass, signature, stalled_streak}`). This file is outside the repository, unlike the downstream `.orchestra/ralph/`.
   6. Back-off: after a stalled pass it waits `min(60 * 2^(streak-1), 900)` seconds before the next launch, and it never stops for stalls (OD-7 option C).
   7. On SIGINT or SIGTERM it runs `autonomy disarm` (reason `disarmed`) and exits 130.
5. Inside a pass, the Stop hook does the per-pass accounting (passes, stalls by signature) and returns no continuation when `relaunch` is true. The harness is the loop (OD-9 option B).
6. Progress signature: SHA-256 of the canonical JSON of:
   - sorted `(task id, state, report_artifact.fingerprint or null, repaired_by or null, parked_branch or null)`
   - the counts of `reviews`, `gates` and `findings`

   `settle` and `autonomy status --json` expose it. It reads engine state only; it does not hash the repository.
7. `P/config/relaunch-prompt.md` is the pass prompt. It tells the pass to:
   - read the orchestra skill
   - run `orchestra.py start --harness-session <id from SessionStart>`
   - read `progress.md` and `status`
   - dispatch ready cards and park at approval boundaries
   - never end the turn to wait
   - end the pass at the context working ceiling after recording state

   It has no sigils, because engine state replaces model claims.
8. Exit codes:
   - 0: `complete`
   - 3: idle (`parked-only` or `no-ready-card`)
   - 4: `deadline`
   - 5: `disarmed`, `ledger-tampered`, or not armed
   - 2: usage or precondition error
   - 127: launcher not found
   - 130: interrupted

**Downstream feature map (S7):**

| Downstream feature | 2.2 replacement |
|---|---|
| `-n` max passes | Removed; the deadline is the only stop (S2, handoff). |
| `-N` stall streak exit | Stall count, report and back-off (OD-7). |
| `-p` prompt file | `P/config/relaunch-prompt.md`. A per-run override is not carried; named. |
| `-m` model | `--model`, default unset (OD-10). |
| `--permission-mode` default bypass | Required flag with no default (OD-11). |
| `--` alternative CLI | `--launcher`. |
| `-v` verify | Ledger completion checks, gated on the current artifact. |
| SIGIL DONE | `complete` stop. |
| SIGIL BLOCKED-USER | `parked-only` stop with the morning brief. |
| SIGIL NEEDS-APPROVAL | Parked card at a boundary. |
| SIGIL STALLED | Stall count. |
| SIGIL RECYCLE | The default pass end. |
| `harness-state.json` resume | `<state>/relaunch/harness.json` plus engine state. |
| STATE.md OPEN check | Active run and armed `relaunch` autonomy. |

**Files:**

- `P/scripts/orchestra_core/relaunch.py` (new, stdlib).
- `P/scripts/orchestra.py`: `relaunch`, `autonomy settle`, `arm --relaunch`.
- `P/scripts/orchestra_core/engine.py`: `end_harness_session`, `hook_stop`, a `settle` method, `signature`, `_validate_state`.
- `P/config/relaunch-prompt.md` (new).
- `P/skills/orchestra/references/autonomy.md`, `cli.md`, `docs/cli.md`, `docs/hooks.md`.
- `README.md`: the overnight section.
- `tests/test_engine.py`, `tests/test_integration.py` (fake launcher), `tests/test_packaging.py` (the prompt file ships).

**No lost functionality:** In-session autonomy without `--relaunch` behaves as in 2.1, apart from 5.7. Every downstream feature has the replacement named in the table.

**Acceptance tests:**

| Test | Behavior |
|---|---|
| `test_relaunch_autonomy_survives_session_end` (test_engine.py) | After `arm --relaunch`, `end_harness_session` leaves `autonomy.active` true and the session inactive. |
| `test_non_relaunch_autonomy_cleared_on_session_end` (test_engine.py) | Regression: the 2.1 behavior. |
| `test_settle_stops_on_deadline_between_passes` (test_engine.py) | Past the deadline, `settle` stops with `deadline` and appends the brief. |
| `test_signature_changes_on_report_park_or_gate` (test_engine.py) | Each event changes the digest. A no-op does not. |
| `test_relaunch_runs_passes_until_complete` (test_integration.py) | A fake launcher accepts one card per pass, and the last pass records a passing check gate. Exit 0, with N pass logs. |
| `test_relaunch_refuses_with_active_session` (test_integration.py) | Exit 2 and the message. |
| `test_relaunch_requires_permission_mode` (test_integration.py) | Missing flag gives exit 2. Applies under OD-11 option A. |
| `test_relaunch_backs_off_after_stall_and_never_exits_on_stalls` (test_integration.py) | An injected clock and sleep record a growing wait. After five stalled passes it is still running, until the deadline exits 4. |
| `test_relaunch_ends_orphaned_pass_session` (test_integration.py) | A fake launcher opens a session and exits without SessionEnd. The harness ends it, and the next pass's `start` succeeds. |
| `test_relaunch_sigint_disarms` (test_integration.py) | SIGINT gives exit 130 and stop reason `disarmed`. |
| `test_relaunch_prompt_ships` (test_packaging.py) | The file exists in the release archive. |

### 5.10 Evidence reuse: the operator gates once

**Current (OBSERVED):**

- checkpoint.md:12: "The operator gate reruns the builder's acceptance suite; you do not."
- review SKILL.md:26 asks for a before-and-after regression comparison.
- `run_gate` records a receipt every time and never refuses a repeat (engine.py:818-862).
- Review receipts carry no reference to gate receipts.

**New:**

1. Review reports may carry `gate_receipts` (a list of receipt ids). `record_review` refuses unless every cited receipt exists, is intact, has `passed` true, and has an `artifact` equal to the current whole-repository artifact.
2. `run_gate` refuses a repeat with the same `name` and `argv` when an intact passed receipt on the current artifact exists: "Gate NAME already passed on this artifact (receipt R); pass --again to rerun". `--again` reruns it.
3. Briefs for wave, repair-diff and final reviewers list the current gate receipt ids and log paths. Reviewers read those logs. They still run targeted probes and the regression before-and-after comparison (SKILL.md:26), and never the full suites.

**Files:**

- `P/scripts/orchestra_core/engine.py`: `record_review`, `run_gate`.
- `P/scripts/orchestra.py`: `gate --again`.
- `P/skills/orchestra-review/SKILL.md`, `references/final.md`, `checkpoint.md`.
- `P/skills/orchestra/references/briefs.md`, `final-review.md`.
- `P/skills/orchestra-operate/references/gate.md`.
- `tests/test_engine.py`.

**No lost functionality:** Rerunning is still possible with `--again`. A failed gate is never blocked from rerunning. Probes and regression comparisons stay with the reviewer.

**Acceptance tests (test_engine.py):**

| Test | Behavior |
|---|---|
| `test_gate_repeat_on_same_artifact_refused_without_again` | A second identical gate is refused. `--again` records a new receipt. |
| `test_failed_gate_rerun_allowed` | After exit 1, the same gate runs again without `--again`. |
| `test_review_cites_stale_or_failed_gate_refused` | A cited receipt on an older artifact, or one that failed, is refused. |
| `test_review_cites_current_passed_gate_accepted` | Accepted, and the receipt id is stored. |

### 5.11 Findings ledger

**Current (OBSERVED):**

- coordination.md:48 says to try to refute each finding.
- No record survives of a rejected or deferred finding apart from the prose lines of `progress.md` (handoff.md:8).
- Later reviewers have no list of findings already ruled on.
- `state.json` has no `findings` key (engine.py:315-316).

**New:**

1. `state.json` gains an optional top-level `findings` list. Each entry:

   ```
   {id, text, source: {review, kind: finding|out_of_scope, index},
    disposition: rejected|deferred|inline|card|brief, reason, card?, at}
   ```

2. `orchestra.py finding add ...` needs the lease. `orchestra.py finding list [--for-brief]` is lease-free. `--for-brief` prints a "Known findings" block that the coordinator pastes into reviewer briefs.
3. Reviewer skill rule: do not raise a finding listed under Known findings unless the code at its location changed since the cited review. If you believe a rejected finding still holds, cite its id and the new evidence.
4. A rejected finding does not let the coordinator accept a card. Acceptance still needs a fresh independent CLEAN verdict (engine.py:806-811), so independence is unchanged.

**Files:**

- `P/scripts/orchestra_core/engine.py`: the state schema, `_validate_state`, `add_finding`, `list_findings`, `signature`.
- `P/scripts/orchestra.py`.
- `P/skills/orchestra-review/SKILL.md`, `P/skills/orchestra/references/coordination.md`, `briefs.md`, `cli.md`, `docs/cli.md`.
- `tests/test_engine.py`, the phrase files.

**No lost functionality:** `progress.md` lines stay. The ledger adds structured records and replaces nothing.

**Acceptance tests:**

| Test | Behavior |
|---|---|
| `test_finding_add_requires_lease_and_known_review` (test_engine.py) | Refused without the lease, and refused for an unknown review id. |
| `test_finding_list_for_brief_renders_known_findings` (test_engine.py) | The block lists id, text, disposition and reason. |
| `test_rejected_finding_does_not_allow_accept` (test_engine.py) | A BLOCKED review and a `rejected` ledger entry: `accept` is still refused. |
| `test_2_1_state_without_findings_loads` (test_engine.py) | Absent key is treated as empty. |
| `known findings rule` phrase (skill_phrases/orchestra-review.json) | Reviewer rule present. |

### 5.12 Briefs carry exact keep/remove lists

**Current (OBSERVED):**

- briefs.md:8-13 lists six brief parts: objective, Mode, ownership, acceptance, rules, and tools and report.
- None of them is a keep or remove list.
- The engine checks a brief file only for its `Mode:` line (engine.py:402-411).

**New:**

1. briefs.md gains a seventh part. Builder briefs carry `## Keep` and `## Remove`, each listing exact paths, symbols or behaviors, or the single word `none`.
2. Under OD-5 option B, `_check_contract` refuses a builder task whose `brief` file lacks either heading.
3. checkpoint.md: the reviewer confirms every Keep item still holds and every Remove item is gone. Each miss is a finding. This makes S7 checkable on every card.

**Files:**

- `P/scripts/orchestra_core/engine.py`: `_check_contract`.
- `P/skills/orchestra/references/briefs.md`.
- `P/skills/orchestra-review/references/checkpoint.md`.
- `P/skills/orchestra-build/SKILL.md` (honor the lists).
- `tests/test_engine.py`, the phrase files.

**No lost functionality:** Tasks without a `brief` field are unchanged, as in 2.1. Non-builder briefs are unchanged.

**Acceptance tests:**

| Test | Behavior |
|---|---|
| `test_builder_brief_without_keep_remove_refused` (test_engine.py) | Refused, naming the missing heading. |
| `test_builder_brief_with_none_lists_accepted` (test_engine.py) | Accepted. |
| `test_reviewer_brief_needs_no_keep_remove` (test_engine.py) | Regression. |

### 5.13 Guard: merged-branch deletion

**Current (OBSERVED):**

- `_git` (`P/scripts/orchestra_core/guards.py:418-505`) denies `branch -D`, and `-d`/`--delete` with `-f`/`--force`, as "Forced branch deletion discards refs" (guards.py:451-452).
- It denies `push` with `--delete` or a `d` short option as "Push needs one explicit remote and refspec" (category release, guards.py:486-487).
- It denies a `:branch` refspec (guards.py:491-492).
- Non-forced `branch -d`, `tag -d` and `worktree remove|prune` are boundary/delete (guards.py:499-502).
- The TS guard mirrors this (`P/hooks/mod/guard.ts`) and the corpus pins parity.
- Boundary classes are delegated to Python (`P/hooks/mod/orchestra.ts:15`).
- Under autonomy, boundary/delete is denied with a park hint (hooks.py:192-197).

**Current repository evidence (OBSERVED, `git for-each-ref` in this worktree):**

- 56 local `v2/*` branches and 0 remote ones. The handoff says 55; the count mismatch is noted for the follow-up.
- Among all 62 non-main branches, none is an ancestor of `origin/main`.
- Six refs are tree-equal to a first-parent commit of `origin/main`:
  - `feat/v2-roles-guard-mods`
  - `fix/agent-matcher`
  - `origin/fix/hook-homebrew-python`
  - `origin/fix/sonnet-5-5`
  - remote twins
- All 56 `v2/*` tips are ancestors of `feat/v2-roles-guard-mods`.

**New:**

1. **Shapes.** Both guards classify exactly these shapes as class `boundary`, new category `merged-delete`:
   - `git branch -D <b>`
   - `git branch --delete --force <b>`, and `-d -f` in any order, combined, or abbreviated (5.14)
   - `git push <remote> --delete <b>` / `-d <b>`, with the flag before or after the remote

   Each shape has exactly one branch positional and no other options. The remote must be a name, not a URL or path.

   Everything else stays as today. In particular these are still denied:
   - multi-branch deletes
   - `:b` refspecs
   - `--delete` with other push options
   - `-r` remote-tracking deletes
2. **TS side.** The TS mod delegates the class as it already does for `boundary`.
3. **Python decision** (hooks.py, before the autonomy branch and in every run state, armed or not):
   1. Under active autonomy, deny with the park hint (OD-13 option A). The fixed ledger line "Deletion: no deletion of files, branches or tags" (engine.py:73) is hard.
   2. Resolve the default ref the way `_on_default_branch` does (hooks.py:272-285): `refs/remotes/origin/HEAD`, else `refs/remotes/origin/main`. For a remote delete, use `refs/remotes/<remote>/HEAD`, else `<remote>/main`. An unresolvable ref is denied.
   3. Find the tip: `refs/heads/<b>` for a local delete, `refs/remotes/<remote>/<b>` for a remote delete. A missing ref is denied. The default branch itself, and the checked-out branch, are denied.
   4. For a remote delete under OD-14 option A, `git ls-remote <remote> refs/heads/<b>` runs with `GIT_TERMINAL_PROMPT=0` and a 4 s timeout. The command is allowed only if it returns the same sha as the local tracking ref. A timeout or failure is denied.
   5. Merged if any of these holds:
      - (a) `git merge-base --is-ancestor <tip> <default>`
      - (b) `<tip>^{tree}` equals the tree of one of the most recent 2000 first-parent commits of `<default>`
      - (c) under OD-12 option A, `<tip>` is an ancestor of a local branch or remote-tracking ref that satisfies (b)
   6. Not merged: deny with "Branch B is not merged into DEFAULT (no ancestor, tree or covering-branch evidence)".
4. **Reasons and budget.** Every git call is local except step 4, and each has a timeout. The deny reason names the failed test. `GUARD_DIGEST_FILES` (guards.py:16-17) already covers the changed files, so `guard_digest` changes.

**Files:**

- `P/scripts/orchestra_core/guards.py`: `_git`.
- `P/hooks/mod/guard.ts`: the same classification.
- `P/config/guard-rules.json`: `boundary_categories` gains `merged-delete`, plus the `_doc` text.
- `P/config/guard-corpus.json`.
- `P/scripts/orchestra_core/hooks.py`: the merged evidence check.
- `docs/hooks.md`.
- `tests/test_guard_corpus.py`, `tests/test_hooks.py`, `P/hooks/mod/guard.test.ts`, `P/hooks/mod/orchestra.test.ts`.

**No lost functionality:**

- Every currently denied shape outside the listed ones stays denied.
- Non-forced `branch -d` keeps its 2.1 boundary/delete class.
- The autonomy deletion boundary is unchanged.
- The release permit path for pushes is unchanged.

**Acceptance tests:**

| Test | Behavior |
|---|---|
| Corpus cases (test_guard_corpus.py, guard.test.ts) | These are class boundary, category `merged-delete`, in both guards: `git branch -D x`, `git branch --delete --force x`, `git branch -df x`, `git push origin --delete x`, `git push --delete origin x`, `git push origin -d x`. |
| Corpus cases | These stay deny: `git branch -D x y`, `git push origin --delete x y`, `git push origin :x`, `git push https://h/r.git --delete x`, `git push origin --delete --force x`, `git branch -D -r origin/x`. |
| `test_merged_delete_allows_ancestor_branch` (test_hooks.py) | A temporary repository with a branch fast-forward merged into the default: allowed. |
| `test_merged_delete_allows_squash_tree_equal_branch` (test_hooks.py) | The branch tree equals a squash commit's tree: allowed. |
| `test_merged_delete_allows_branch_covered_by_tree_equal_branch` (test_hooks.py) | The v2/* shape. Applies under OD-12 option A. |
| `test_merged_delete_denies_unmerged_branch` (test_hooks.py) | One extra commit: denied, naming the tests. |
| `test_merged_delete_denied_under_autonomy` (test_hooks.py) | Applies under OD-13 option A. |
| `test_remote_delete_denied_when_ls_remote_differs_or_times_out` (test_hooks.py) | A fake remote with a moved tip, and an unreachable remote. Applies under OD-14 option A. |
| `merged-delete is delegated` (orchestra.test.ts) | The mod calls the Python hook for `git branch -D x`. |

### 5.14 Guard: abbreviated long options

**Current (OBSERVED, git 2.50.1 in a scratch repository outside this worktree):**

- Git accepts these unique prefixes:
  - `add --a`, `--al` (as `--all`), `--upd`, `--no-ignore-rem`
  - `commit --am` (as `--amend`), `--mess=`
  - `reset --har`
  - `clean --f`, `--forc`, `--dry`
  - `branch --del`, `--forc`
  - `tag --del`
  - `push --mir`, `--del`, `--ta`, `--pru`, `--follow`, `--al`, `--push-o=`
  - `checkout --forc`, `switch --disc`, `restore --stag`, `--work`
- Git rejects these as ambiguous: `commit --al`/`--a`, `push --forc`/`--for`, `switch --forc`.
- Git does not accept prefixes of global options (`--git-d=`) or of `worktree` subcommands.
- The guards compare exact strings (guards.py:447-504). OBSERVED results today:
  - `git add --al`, `git add --upd`, `git clean --forc` and `git reset --har` classify as allow.
  - `git push --forc` classifies as release.
- `git <verb> --git-completion-helper-all` shows that, for add, commit, push, clean, branch, tag, reset, checkout, switch and restore, no harmless full long option is a strict prefix of a guarded long option (only `--` itself, which is already the separator).
- The guards do not deny `git commit --amend` even in full form. The standing orders forbid amend procedurally.

**New:**

1. In both guards, for the verb's long-option tokens before `--`, compare the part before `=`.
   - A token that is a non-empty strict prefix of a guarded long option of that verb counts as that option.
   - The guarded options are those the rules already name: `wholesale_add_flags`, commit `--all`, push force/mirror and `push_multi_flags`, clean `--force`, reset `--hard`, branch and tag `--delete`/`--force`, checkout and switch `--force`/`--discard-changes`, restore `--worktree`/`--staged`.
   - The same applies to value options in `push_value_options`, `commit_value_options` and `clean_value_options`, so positional counting stays right.
2. An exemption option (clean `--dry-run`, restore `--staged` when it narrows a wholesale restore) counts only when spelled in full. Abbreviated exemptions over-deny, which is the safe direction.
3. A prefix of more than one guarded option is treated as the most restrictive of them.
4. Global options are not prefix-matched, matching git.
5. `commit --amend` and its prefixes are handled under OD-15. Under the recommended option A they are denied: "Amend rewrites history".
6. guard-rules.json gains no option lists beyond what it names today, except `commit_guarded_flags` with `--amend` under OD-15.

**Files:**

- `P/scripts/orchestra_core/guards.py`, `P/hooks/mod/guard.ts`.
- `P/config/guard-rules.json`, `P/config/guard-corpus.json`.
- `tests/test_guard_corpus.py`.
- `tests/fixtures/git-long-options.json` (new): a pinned snapshot of `--git-completion-helper-all` for the ten verbs.
- `P/hooks/mod/guard.test.ts`.

**No lost functionality:** Every full spelling classifies as today. The only new denials are abbreviations of options already denied, plus amend under OD-15.

**Acceptance tests:**

| Test | Behavior |
|---|---|
| Corpus deny cases, both guards | `git add --al`, `git add --a`, `git add --upd`, `git add --no-ignore-rem`, `git reset --har`, `git clean --forc`, `git clean --f`, `git branch --del --forc x`, `git checkout --forc`, `git switch --disc`, `git push --mir origin`, `git push --ta origin`, `git push --pru origin`, `git push --al origin` |
| Corpus release case | `git push --push-o=x origin main` (a value option, one remote, one refspec). |
| Corpus cases under OD-15 option A | Deny `git commit --am -m x`, `git commit --amend`. Allow `git commit -m x file`. |
| Corpus case | `git clean -f --dry` denied, because an abbreviated exemption does not exempt. |
| `test_no_harmless_option_is_prefix_of_guarded_option` (test_guard_corpus.py) | For each verb in the pinned fixture, no full long option outside the guarded set is a strict prefix of a guarded option. |

### 5.15 Guard: fail-closed on chained commands

**Current (OBSERVED):**

- The handoff's chain `git status && git diff --quiet && git worktree remove X && rmdir Y || true` classifies as boundary/delete in both guards. So do 13 variants: quoted paths, `$VAR`, `$(...)`, `-C`, a for loop, `if`, a subshell, a newline, `|| :` and `--force`. Neither guard throws.
- The Python hook end to end returns `{}` with exit 0 in about 0.18 s, including when the payload `cwd` does not exist.
- So the handoff's premise of a "parser fault" is not supported for the stated shape.
- The message comes from the mod (`FAIL_CLOSED`, orchestra.ts:18). `delegate` (orchestra.ts:79-92) returns it for any of:
  - a non-zero exit
  - stdout that is not JSON
  - malformed `hookSpecificOutput`
  - the `.catch` handler (orchestra.ts:403-406), on any thrown error
- `runHook` spawns `/bin/sh run-hook.sh` with `cwd` set to the session cwd and `timeoutMs: 8000` (orchestra.ts:75-77).
- OBSERVED in Node: spawning with a nonexistent cwd yields an ENOENT error and no exit status.

**Hypotheses (UNKNOWN, to be settled by the first build ticket):**

- **H1 (REASONED):** The session cwd was a removed worktree, for example after an earlier `git worktree remove` of the directory the shell was in. The spawn then fails before Python runs.
- **H2 (REASONED):** The hook waited behind an exclusive `state.lock` held during artifact hashing (`report`, `record_review`, `accept` and `hook_stop` hash under the write lock) and passed the 8 s timeout.
- **H3 (UNKNOWN):** Another mod-side exception.

The fix is chosen after reproduction, in the bug lane: investigator diagnosis, then a failing test, then the builder fix.

**New:**

1. A diagnosis card reproduces the exact message at the mod seam, using the testkit fake `$` (`P/hooks/mod/testkit.ts`), for H1 and H2. It records which reproduces.
2. `runHook` spawns in `$.plugin.root`, which always exists, and passes the session cwd only inside the payload.
3. Python with a payload cwd that does not exist (OD-16 option B): deny the delegated classes (release, release-multi, boundary) with "Session directory no longer exists: cd to an existing directory, then retry". Allow-class commands never reach Python from the mod.
4. `FAIL_CLOSED` reasons name the failure class: "Orchestra guard error (spawn: CODE | exit N | timeout | bad output); failing closed".
5. If H2 reproduces, the fix is to compute the artifact outside the exclusive lock where the engine already allows it, or to give the hook's read a shorter lock wait with a named reason. This becomes its own ticket with its own failing test.
6. Regression corpus cases add the literal chain and its 13 variants.

**Files:**

- `P/hooks/mod/orchestra.ts`, `P/hooks/mod/orchestra.test.ts`.
- `P/scripts/orchestra_core/hooks.py`: `main`, missing-cwd handling.
- `P/config/guard-corpus.json`.
- `tests/test_hooks.py`.
- Under H2, also `P/scripts/orchestra_core/engine.py`.

**No lost functionality:** Fail-closed stays the default for every unexpected mod error. Only the reasons get more specific, and the spawn directory changes.

**Acceptance tests:**

| Test | Behavior |
|---|---|
| `delegate spawns the hook from the plugin root when the session cwd is gone` (orchestra.test.ts) | The fake `$` records the spawn cwd equal to `plugin.root` and the payload cwd equal to the removed directory. |
| `delegate failure reason names the failure class` (orchestra.test.ts) | Exit 3 gives "exit 3". A thrown spawn gives "spawn". A timeout gives "timeout". |
| `test_pretooluse_missing_cwd_denies_delegated_class_with_reason` (test_hooks.py) | `git worktree remove X` with a nonexistent cwd is denied with the cd message. Applies under OD-16 option B. |
| `test_pretooluse_missing_cwd_allows_nothing_new` (test_hooks.py) | Regression for allow-class commands through the direct Claude hook path. |
| Corpus cases | The literal chain and 13 variants are boundary/delete in both guards. Regression (passes today). |
| `test_hook_read_does_not_exceed_timeout_while_artifact_hashes` (test_hooks.py) | Only if H2 reproduces. |

### 5.16 Repository follow-ups after 2.2 (this repository only)

**Current (OBSERVED):** 56 local `v2/*` branches, plus `feat/v2-roles-guard-mods` and `fix/agent-matcher` (5.13).

**New:** Not part of the 2.2 change set. After 2.2.0 is installed, an operator cleanup card deletes these branches using the 5.13 rule.

- Order: the `v2/*` branches first, while `feat/v2-roles-guard-mods` still exists to provide covering evidence (OD-12). Then `feat/v2-roles-guard-mods` and `fix/agent-matcher`.
- Each deletion is one `git branch -D <b>` the guard allows. No guard bypass.
- Under OD-12 option B (no covering rule), the `v2/*` branches stay undeletable by the agent. The card then reports them to the user instead of deleting them.

**Acceptance (for that later card):** `git for-each-ref refs/heads/v2` prints nothing. Every deletion appears in the card log with the guard's allow decision.

## 6. Engine and state changes

State schema: `state.json` keeps `version: 1` with additive optional keys (OD-17 option A). A missing key reads as its default.

| Location | Field | Type | Default | Section |
|---|---|---|---|---|
| `tasks[*]` | `wave` | non-empty str | absent | 5.1 |
| `tasks[*]` | `parked_branch` | non-empty str | absent | 5.3 |
| `tasks[*]` | `parked_finding` | non-empty str | absent | 5.3 |
| `tasks[*]` | `parked_by` | `coordinator`, `cascade` or `chain` | `coordinator` | 5.3 |
| `reviews[*]` | `task_findings` | object of id to list of str | absent (whole list applies) | 5.1 |
| `reviews[*]` | `out_of_scope` | list of str, final only | `[]` | 5.6 |
| `reviews[*]` | `gate_receipts` | list of receipt ids | `[]` | 5.10 |
| top level | `findings` | list of ledger entries | `[]` | 5.11 |
| `autonomy` | `max_passes`, `max_stalls` | int, now optional | absent | 5.7 |
| `autonomy` | `relaunch` | bool | `false` | 5.9 |
| `autonomy` | `signature` | str | absent | 5.9 |

**Card states:** no new state. `parked` (engine.py:80) gains chain parking and cascade parking. `PARKABLE` stays `queued`, `running`, `reported`. The chain rule parks `repairing` ancestors only through their open repair card.

**Stop reasons:**

- Removed from production: `cap-passes`, `cap-stalls`. They stay readable in 2.1 reports.
- Kept: `deadline`, `complete`, `ledger-tampered`, `disarmed`, `parked-only`, `no-ready-card`.

**New CLI:**

- `park --branch --finding`
- `finding add|list`
- `gate --again`
- `autonomy arm --relaunch`
- `autonomy settle`
- `autonomy status --json` gains `signature`
- `relaunch`
- `add` accepts `review_of: ["wave:W"]`

**Policy:** `DEFAULT` (engine.py:38-40) is unchanged. REASONED: `policy_hash` includes the defaults and the contract (engine.py:201-202), so leaving both unchanged keeps 2.1 runs loadable.

## 7. Model matrix delta

| Role / preset | 2.1 | 2.2 |
|---|---|---|
| code-reviewer `standards` (new preset, generated variant `code-reviewer-standards`) | none | Sonnet 5.5 medium |
| code-reviewer `final` (correctness and security lenses) | Opus 5.5 high | unchanged |
| code-reviewer `checkpoint` (wave review and repair-diff check) | Opus 5.5 medium | unchanged |
| builder `repair` (the single escalation rung) | Opus 5.5 medium, dispatch override | unchanged |
| builder presets other than repair | Sonnet 5.5 medium | unchanged |
| all other roles | as in models.json | unchanged |

Consequences:

- REASONED: `AGENTS.md`'s sentence "Opus 5.5 high for ... final reviewer" needs "except the standards lens, Sonnet 5.5 medium".
- REASONED: The user's global model matrix (the user-level `CLAUDE.md`, section 7) also says the final code-reviewer runs on Opus high. The handoff's done-when check "`models.json` still matches the matrix" will fail until the user updates that file. This design does not own that file. It is listed as risk K6.

## 8. Migration and compatibility for runs started under 2.1

**What carries over (REASONED):**

- The run contract digest covers only the role-to-modes map (engine.py:43-65). The policy hash covers `DEFAULT` and the contract (engine.py:201-202). 2.2 changes neither, so a run started under 2.1 loads under 2.2 without `ACTIVE_MISMATCH` (engine.py:25-27, 311-313).
- `_validate_state` checks named keys and does not reject extra keys (engine.py:338-392). So 2.1 state is valid 2.2 state, and new keys default.
- An armed 2.1 autonomy has `max_passes`/`max_stalls`. 2.2 ignores them for stopping (5.7). The pass continues past the old cap. The morning brief prints them as "recorded, not enforced".
- A 2.1 park without a branch stays valid. The branch requirement applies to new park calls only. At completion, a 2.1-parked builder card with no `parked_branch` is excluded like any parked card. The brief lists it as "branch: not recorded".

**Mixed versions on one active run (REASONED):**

- A 2.1 engine (a session started before the update) reading 2.2 state:
  - ignores `task_findings`, so it is stricter
  - ignores `findings`
  - counts parked cards as blocking, so it is stricter
  - rejects an armed autonomy that lacks `max_passes` ("Invalid autonomy state"). The 2.1 hooks then fail closed for that run (hooks.py:221, 233-240): Stop returns no continuation, and the autonomy column applies.
- Guidance, carried in the README upgrade notes: finish or disarm a 2.1 autonomy run before arming under 2.2, and do not arm `--relaunch` while a 2.1 session is still running.

**The downstream harness:** It stays dead until the downstream follow-up PRs remove it (out of scope here). The README names `orchestra.py relaunch` as its replacement.

**Tests:**

| Test (test_engine.py) | Behavior |
|---|---|
| `test_2_1_state_fixture_loads_under_2_2` | A fixture copied from a 2.1 run with tasks, reviews, gates and armed autonomy loads. `hook_stop` continues past `max_passes`. |
| `test_2_1_parked_card_without_branch_excluded_and_listed` | Completion passes, and the brief shows "branch: not recorded". |

## 9. Risks

- **K1:** Parked work excluded from completion could hide a half-integrated ticket. Mitigation: the completion check that the parked tip is not an ancestor of HEAD (5.3). Residual: cherry-picked or copied changes are not detected (REASONED).
- **K2:** Removing the caps means a confused coordinator can spend passes until the deadline. Mitigation: stall back-off (OD-7) and the idle stop (OD-6). Cost is bounded only by the user's deadline.
- **K3:** Under `relaunch`, autonomy outlives sessions by design. A crashed pass without SessionEnd leaves an active session. The harness ends it after the pass exits (5.9 step 4), but if the harness itself dies, the run stays armed with an active session until `start` or `disarm`. Recovery is manual, as for 2.1 lease loss.
- **K4:** Merged-branch evidence:
  - With a local tracking ref alone, a moved remote branch could be deleted. OD-14 option A adds an ls-remote check, which needs the network and denies offline.
  - The covering-branch rule (OD-12 option A) depends on deletion order. Deleting the covering branch first strands the children.
  - The 2000-commit first-parent window could miss very old squash merges and deny them, which is safe.
- **K5:** The fail-closed root cause is UNKNOWN. If neither H1 nor H2 reproduces, 5.15 ships only the reason-naming and spawn-directory changes, and the original failure may recur with a clearer message.
- **K6:** The user-level model matrix still says the final reviewer runs on Opus high. The release done-when check conflicts with S5 until the user edits it.
- **K7:** A 2.1 session still running against a 2.2-armed run fails closed (section 8). The user may see unexpected denials until the old sessions end.
- **K8:** The ls-remote and merged-evidence git calls add latency to a 10 s hook (8 s in the mod). A slow repository or remote may hit the timeout and fail closed.
- **K9:** Moving the architecture checks into the correctness lens (OD-4 option A) puts more work on one Opus card. That lens could miss architecture issues that a dedicated card would find (REASONED).
- **K10:** Abbreviation matching depends on git's option set. A future git that adds a harmless option that is a prefix of a guarded one would over-deny it. The pinned-fixture test catches this only when the fixture is refreshed.
- **K11:** The handoff counts 55 `v2/*` branches; 56 are observed. The follow-up card must list them, not trust either count.

## 10. Open decisions (options, one recommendation each)

- **OD-1, wave definition.**
  - A: a `wave` label on cards, and `review_of: ["wave:W"]` resolved and frozen at add time.
  - B: no wave entity; a wave is whatever a review's `review_of` lists, plus `task_findings`.
  - C: a first-class wave object with ordering and gate flags.
  - **Recommend A.** It gives the handoff's "`review_of` on a wave" with two fields, and the board can show waves.
- **OD-2, how S1's "builders fix" maps onto S2's ladder.**
  - I1: after the wave review, a Sonnet builder fixes, then the repair-diff check, then Opus repair, then another check, then park.
  - I2: the Sonnet implementation is the first rung. Wave findings go straight to one Opus `repair` card, then the repair-diff check, then park.
  - **Recommend I2.** It keeps one loop per wave, matches models.json:49-53 (repair is already Opus) and the roles.json builder rule "Repair mode needs independently checked coding findings; implementation is the first attempt".
- **OD-3, dependents of a parked card.**
  - A: cascade-park them with the reason "depends on parked X".
  - B: leave them queued and exclude them from completion.
  - C: leave them queued and block completion.
  - **Recommend A.** It keeps the board truthful and the brief complete. C contradicts S3, because the PR could never be cut.
- **OD-4, final lens layout under S5.**
  - A: three cards: correctness+architecture (Opus high), security (Opus high), standards+cleanliness (Sonnet medium).
  - B: five cards: correctness, architecture and security on Opus high; standards and cleanliness on Sonnet medium.
  - C: three cards with architecture moved into the standards lens.
  - **Recommend A.** It matches S5's three named lenses, keeps every category covered, and keeps judgment-heavy architecture on Opus.
- **OD-5, engine enforcement of procedure rules** (S6 triage at completion, E3 keep/remove headings, E1 cited gate receipts).
  - A: procedure only, through skills and phrase tests.
  - B: engine-enforced where machine-checkable, as written in 5.6, 5.10 and 5.12.
  - **Recommend B.** These rules exist to survive unattended runs, and prose is no lock (coordination.md:37).
- **OD-6, idle with the deadline not reached.**
  - A: stop with `parked-only` / `no-ready-card`, as in 2.1, and write the brief.
  - B: keep passing until the deadline.
  - **Recommend A.** Idle is not a cap. Nothing remains that autonomy may do, and B spends passes for nothing. The handoff's "deadline is the only stop" is then read as "the only time or count limit". The user should confirm this reading.
- **OD-7, stalls.**
  - A: report only, with immediate relaunch.
  - B: after K stalled passes, park the stuck cards.
  - C: report only, plus relaunch back-off (60 s doubling to 15 min).
  - **Recommend C.** B ends a run through stalls, which works like a cap and contradicts S2. A burns passes fastest.
- **OD-8, the `max_passes` / `max_stalls` ledger fields.**
  - A: optional; accepted and recorded but not enforced; dropped from the template.
  - B: removed, so ledgers that carry them are refused.
  - C: still required but ignored.
  - **Recommend A.** 2.1 ledgers keep arming, and nobody fills in dead fields.
- **OD-9, the Stop hook inside a relaunch pass.**
  - A: it keeps continuing in-session, and a new `autonomy recycle` call ends a pass.
  - B: with `relaunch` it never blocks; one pass is one headless turn and the harness is the loop.
  - **Recommend B.** It is simpler, needs no new command, and a turn that ends to "wait" is repaired by the next pass.
- **OD-10, the model for passes.**
  - A: no `--model`; the user's selection applies, matching `orchestrator.selection: "user"` in models.json.
  - B: always Opus 5.5.
  - C: an optional `--model` passthrough with no default.
  - **Recommend C.** It behaves as A by default and lets the user pin Opus 5.5 without code changes.
- **OD-11, the permission mode for passes.**
  - A: `--permission-mode` is required, with no default.
  - B: default `bypassPermissions`, as downstream.
  - C: the headless default mode.
  - **Recommend A.** Bypass is a security choice the user makes explicitly. C would deny most tool use unattended.
- **OD-12, the covering-branch rule for merged deletion.**
  - A: also allow a tip that is an ancestor of a branch that is itself tree-merged.
  - B: direct evidence only (ancestor or tree-equal).
  - C: add GitHub PR state through `gh` (network).
  - **Recommend A.** It is needed for the 56 `v2/*` branches (OBSERVED: none qualify directly, all are covered), stays local, and is safe because the covering branch's landed tree contains every covered commit's history.
- **OD-13, merged deletion under autonomy.**
  - A: still denied with a park hint; the fixed ledger line holds.
  - B: allowed when merged.
  - **Recommend A.** autonomy.md:22 calls the boundaries "hard and not configurable".
- **OD-14, remote-delete freshness.**
  - A: an `ls-remote` check against the local tracking ref, with a 4 s timeout, denying on failure.
  - B: the local tracking ref only.
  - **Recommend A.** A stale tracking ref could delete unmerged remote work. Denying offline is the safe failure.
- **OD-15, `commit --amend`.**
  - A: deny `--amend` and its prefixes in both guards.
  - B: classify `--am` like `--amend` (allow) and leave amend to the standing orders.
  - **Recommend A.** The handoff lists `commit --am` among the forms to catch, and the standing orders forbid amend. Users keep amend in their own terminal.
- **OD-16, PreToolUse with a payload cwd that no longer exists.**
  - A: treat as no run and allow (current Python behavior).
  - B: deny the delegated classes with an actionable "cd to an existing directory" reason.
  - C: resolve the run from the harness project directory, if the mods API exposes one (UNKNOWN).
  - **Recommend B.** A lets a delete boundary through under autonomy whenever the cwd vanished. B is honest and safe.
- **OD-17, state schema version.**
  - A: stay at `version: 1` with additive optional keys.
  - B: bump to `version: 2` and require `start --new-run`.
  - **Recommend A.** 2.1 runs continue under 2.2 (section 8). B strands active runs on upgrade.
- **OD-18, standards-lens dispatch.**
  - A: a generated variant agent (`code-reviewer-standards`).
  - B: a dispatch override of `code-reviewer`, as builder `repair` does.
  - **Recommend A.** Lens cards run in parallel from a Workflow script, and parallel.md:16 forbids override dispatch from scripts.

## 11. Out of scope

- T3 Code support. It is a separate add-on plugin after 2.2; the core stays Claude-native.
- Any change to the Devops or Commercial repositories, including removing their `orca-ralph.sh`, `orca-ralph-PROMPT.md` and `orca-ralph.test.sh` and fixing their memory files. Those are the follow-up PRs the handoff assigns to those repositories.
- Moving old plugin cache versions to the Trash (a user step).
- Editing the user-level model matrix (K6).
- Deleting this repository's merged branches. That is a post-release operator card (5.16), not part of 2.2.0.

## 12. Self-check

- **Placeholders:** none. Every "New" names files and tests.
- **Contradiction scan against S1 to S7:**
  - S2 "a cap never stops" holds: no count-based stop remains (5.7, OD-7).
  - S3 holds: parked work is excluded and proven outside the candidate (5.3).
  - S5's three named lenses and models hold (5.5, section 7).
  - S6 holds: out-of-scope findings are refused before final (5.6).
  - S7 holds: each section has a no-lost-functionality paragraph naming replacements.
- **Known tensions:**
  - The handoff's "deadline is the only stop" versus the idle, complete, tamper and disarm stops. These are not settled inputs, so they sit in OD-6.
  - The handoff's "parser fault" premise is contradicted by the observations in 5.15.
- **Untestable requirements:** none. Each changed behavior lists at least one test a builder can write first.
- **Readiness:** the spec is ready for independent critic challenge (spec and feasibility). The open decisions above need user answers before planning starts.
