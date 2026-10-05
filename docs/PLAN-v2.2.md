# Orchestra 2.2 implementation plan

Status: plan for review. Built from `docs/SPEC-v2.2.md` at bca4e98a2b83e1e8c4e5e69eba7a1f4ca6ed9f6d (section 10 has no open decision), and aligned by card D5 with the spec as amended for critic C7 in the same commit (C7/R4-1 to R4-8 and the coordinator decisions after C7, spec section 10). Critic C8 (feasibility) checked it at a5f46e4: P-1 and P-2 were blocking and are fixed in this amendment, with notes P-3 to P-13 (marked C8/P-n where they changed text).

Labels: OBSERVED (read or run in this worktree at bca4e98), REASONED (follows from the spec and the code), UNKNOWN (not established).

`P` = `plugins/orchestra`. Line numbers are at bca4e98.

## 0. Rules gate

Run twice, once before slicing and once on this finished plan. Both passes are clean apart from the gaps in section 9.

| Binding rule | How the plan holds it |
|---|---|
| Portable workflow; Python 3.11+ stdlib and Git only | `relaunch.py` is stdlib only. No new dependency anywhere. |
| One coordinator; workers never delegate | Every ticket is one builder card. The coordinator merges, gates, records, accepts and does the release-card work (5.18) itself. |
| Parallel writers in separate worktrees with explicit paths | One worktree per ticket, created off the wave base. The ownership table (section 3) is disjoint within each wave. |
| Hot files have one owner per wave | `engine.py`, `hooks.py`, `guards.py`, `test_engine.py` and `test_hooks.py` each have at most one owner per wave (section 3). |
| Models per `config/models.json`, Opus 5.5 and Sonnet 5.5 only | Builders run Sonnet 5.5 medium. The repair rung runs builder `repair` (Opus 5.5 medium, dispatch override). The wave reviewer is `code-reviewer-checkpoint`. Final lenses: correctness and security on Opus high, standards on Sonnet medium (settled decision 5). |
| Tests first; assert behavior, never the mock | Every ticket names its tests. The done contract needs the red run on the wave base before the code changes. |
| Explicit-path commits; no stash, `add -A`, amend, rebase, force or `reset --hard` | Carried into every ticket's standing orders (section 2). |
| Independent review; later edits void evidence | Wave review per wave, repair-diff check, then final lenses on the frozen candidate (section 7). |
| Test invalid inputs, stale evidence, reservations, hooks, install/uninstall | Spec tests cover refusals, stale receipts (5.11), reservations (5.17, held cards) and hooks (5.14, 5.16). The packaging tests stay in the final gate. |
| Check live hook discovery separately from unit tests | Live checks X1 and L1 (section 7). |
| No credentials, personal paths or delivery state in the public repository | No ticket writes any. The X1 log stays in a mktemp directory and is never committed. |
| Settled decisions 1 to 7 | 1, 2 and 4 drive sections 6 and 7. 5 drives K2 and P1x. 6 drives E2 and K1/K2. 7 means each ticket keeps 2.1 behavior or names the replacement the spec gives. 3 is superseded by hold, per the spec. |

## 1. File map (OBSERVED)

| Area | Files | Responsibility |
|---|---|---|
| Engine | `P/scripts/orchestra_core/engine.py`, `P/scripts/orchestra.py` | Run state, cards, reviews, gates, autonomy. CLI surface. |
| Hooks | `P/scripts/orchestra_core/hooks.py` | PreToolUse, Stop, SessionStart and SessionEnd decisions. |
| Guards | `P/scripts/orchestra_core/guards.py`, `P/hooks/mod/guard.ts`, `P/config/guard-rules.json`, `P/config/guard-corpus.json`, `P/hooks/mod/fixtures/{sync.py,guard-fixtures.ts}` | Command classification in both guards, plus the shared corpus. |
| Mods | `P/hooks/mod/orchestra.ts`, `autonomy.ts`, `*.test.ts`, `testkit.ts` | Function-hook delegate, CLI reads, status band. |
| Packaging | `P/config/{models.json,roles.json}`, `P/scripts/generate.py`, `P/agents/*.md` (generated) | Model matrix and agent files. |
| Skills | `P/skills/orchestra*/` | Coordinator and worker procedure. |
| Tests | `tests/test_{engine,hooks,integration,guard_corpus,packaging,skills}.py`, `tests/skill_phrases/*.json` | Unit, integration, corpus, packaging and skill-text checks. |
| Docs | `README.md`, `AGENTS.md`, `docs/{cli,hooks,models,roles}.md` | Public documentation. |

Commands (OBSERVED unless marked):
- Scoped Python: `python3.11 -m unittest discover -s tests -k NAME [-k NAME ...]`. Per file: `python3.11 -m unittest discover -s tests -p 'test_engine.py'`.
- Full Python suite: `python3.11 -m unittest discover -s tests`. At bca4e98 it ran 339 tests, OK, exit 0, in about 268 s.
- TypeScript: `CLAUDE_CODE_ENABLE_FUNCTION_HOOKS=1 claude plugin test plugins/orchestra`. It runs every `*.test.ts` and cannot be narrowed by name, so it is the scoped command for any `.ts` change.
- Generator: `python3.11 plugins/orchestra/scripts/generate.py --check` (write mode without `--check`).
- Corpus fixtures: `python3 plugins/orchestra/hooks/mod/fixtures/sync.py` (write) and `--check`.
- Manifests: `claude plugin validate --strict plugins/orchestra` and `claude plugin validate --strict .claude-plugin/marketplace.json`.

## 2. Standing orders for every ticket

Each brief carries these verbatim, together with: the `Mode:` line, the plugin root (the ticket worktree's `plugins/orchestra`), the ticket text below, and its Keep and Remove lists.

> Project charter (AGENTS.md): Build the approved portable workflow, not an application. Keep source reference repositories read-only. Never publish private audit snapshots, credentials, personal paths or product delivery state. One main coordinator owns state, assignments and integration and can execute reserved inline work alongside disjoint workers. Workers do not delegate. Parallel writers use separate worktrees and own explicit paths; preserve sibling edits. Models follow `plugins/orchestra/config/models.json` (Opus 5.5 `claude-opus-5-5` and Sonnet 5.5 `claude-sonnet-5-5` only; the generator writes `agents/*.md`) ... Use Python 3.11+ standard library and Git. Test invalid inputs, stale evidence, independent review, reservations, hooks and install/uninstall behavior. Do not claim arbitrary-shell or hostile-worker isolation from prompts or caller-supplied identifiers. Check live hook/profile discovery separately from unit tests. Commit each working iteration with explicit paths. Never stage wholesale, stash, force push, reset hard or remove unpreserved work. The only public target is this clean package repository. Keep feedback concise; detailed evidence belongs in docs/BUILD-LEDGER.md.
>
> Session rules: Never print or handle credentials; never echo `~/.claude/settings.json` env values. No `git stash` (any form), no `add -A` / `add .` / `add -u` / globs, no `commit -a`, no force push, no `reset --hard`, no `clean -f`, no `branch -D` (until the 2.2 rule ships), no amend, no rebase. Stage explicit paths only. Never route around the guard with `gh api`, MCP or terminal tools. No permanent deletion of files; move to `~/.Trash/claude-cleanup-<date>/`. Do not touch other sessions' worktrees. A builder never approves its own work; final review covers the frozen candidate; any later edit voids earlier evidence. Tests first for new behavior and bug fixes; assert behavior, never the mock. Commits end with `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`. Models: Opus 5.5 and Sonnet 5.5 only, per `config/models.json`. No 1M-context variants.
>
> Settled decisions 1 to 7, verbatim from the brief (fixed inputs, never reopened).

**Plan rules for every builder:**

1. **Flip rule.** A 2.1 test may break only because of a behavior change named in the ticket's spec sections (a new refusal, a renamed heading or message, a changed constructor call, a removed cap). Update the assertion to the new behavior; never weaken it. Fix it with the smallest fixture step that satisfies the new rule: add `issues`, accept the overlapping reported card first, add `task_findings`, add Keep/Remove headings, or hold before the repair. Never weaken an assertion. List every flipped test and its step in the report. Delete a 2.1 test only where the spec's flip table says it is removed.
2. **Edit only your owned paths.** If a needed change falls outside them, stop and report `STATUS: BLOCKED` naming the file.
3. **Strings are spec literals.** Copy refusal messages, progress lines and headings character for character from the spec section named in the ticket.
4. **Generated files.** Run the generator or `sync.py` in write mode. Commit only the generated files your ticket owns.

**Done contract (every ticket).** The report starts with `STATUS:` and `ARTIFACT: <commit sha> <owned paths>`. It then gives:
- the tests-first names, with the red run on the wave base (command, failure count, exit code). Names marked (regression), or that guard behavior the base already has, are reported green on the base instead;
- for every `-k` command, the `Ran N` line and the list of tests-first names it actually ran (a `-k` pattern that matches nothing still exits 0);
- the green run of every acceptance command, with its exit code;
- the flipped 2.1 tests and their fixture steps;
- confirmation that each Keep item holds and each Remove item is gone;
- anything left unresolved.

## 3. Waves and ownership

Each ticket's builder works in its own worktree off the wave base. The wave base is design/2.2 at the previous wave's closing tip, or a5f46e4 for W1 (code identical to bca4e98; the spec text includes the C7 amendment). Line numbers in this plan stay at bca4e98.

| Wave | Tickets | Gate before next wave | Why |
|---|---|---|---|
| W1 | E1, G1, M1, K1, K2, P1x, X1 (spike) | yes | E2 builds on E1's engine and test helpers; G2 builds on G1's guards and corpus. |
| W2 | E2, G2 | yes | E3 builds on E2's engine (findings ledger, `gate_receipts`). |
| W3 | E3 | yes | E4 builds on `_task_findings`, waves and the tip rule. |
| W4 | E4 | yes | E5 needs the `held` state. |
| W5 | E5 | yes | E6's brief reads `final_round` and `final_findings`. |
| W6 | E6 | yes | E7 stops write the run brief; it needs E6's writer and hooks changes. |
| W7 | E7 | yes | E8 needs signature, held-live completion and the cap removal. |
| W8 | E8 | yes | H1 calls `settle`, `end_pass_session` and `arm --relaunch`. |
| W9 | H1, D1 | final gate (section 6) | Last wave. |

**Ownership table.** Each row is one file. A cell names the ticket that owns that file in that wave. "new" means the ticket creates the file. No cell holds two tickets.

| File | W1 | W2 | W3 | W4 | W5 | W6 | W7 | W8 | W9 |
|---|---|---|---|---|---|---|---|---|---|
| P/scripts/orchestra_core/engine.py | E1 | E2 | E3 | E4 | E5 | E6 | E7 | E8 | |
| P/scripts/orchestra.py | E1 | E2 | E3 | E4 | | E6 | | E8 | H1 |
| P/scripts/orchestra_core/hooks.py | | G2 | | | | E6 | | E8 | |
| P/scripts/orchestra_core/guards.py | G1 | G2 | | | | | | | |
| P/scripts/orchestra_core/relaunch.py | | | | | | | | | H1 new |
| tests/test_engine.py | E1 | E2 | E3 | E4 | E5 | E6 | E7 | E8 | |
| tests/test_hooks.py | E1 | G2 | E3 | E4 | E5 | E6 | E7 | E8 | |
| tests/test_integration.py | E1 | E2 | E3 | E4 | E5 | | E7 | E8 | H1 |
| tests/test_guard_corpus.py | G1 | G2 | | | | | | | |
| tests/test_packaging.py | P1x | | | | | | | | H1 |
| tests/test_skills.py | K2 | | | | | | | | |
| tests/fixtures/git-long-options.json | G1 new | | | | | | | | |
| tests/skill_phrases/orchestra.json | K1 | | | | | | | | |
| tests/skill_phrases/orchestra-{review,critique,build,operate}.json | K2 | | | | | | | | |
| P/hooks/mod/guard.ts, guard.test.ts | G1 | G2 | | | | | | | |
| P/hooks/mod/fixtures/guard-fixtures.ts (generated) | G1 | G2 | | | | | | | |
| P/hooks/mod/fixtures/sync.py | | G2 | | | | | | | |
| P/hooks/mod/orchestra.ts | M1 | | | | | | | | |
| P/hooks/mod/orchestra.test.ts | M1 | G2 | | | | | | | |
| P/hooks/mod/autonomy.ts, autonomy.test.ts | | | | | | | E7 | | |
| P/config/guard-rules.json, guard-corpus.json | G1 | G2 | | | | | | | |
| P/config/autonomy-template.md | | | | | | | E7 | | |
| P/config/models.json, roles.json | P1x | | | | | | | | |
| P/config/relaunch-prompt.md | | | | | | | | | H1 new |
| P/scripts/generate.py | P1x | | | | | | | | |
| P/agents/orchestrator.md (generated) | K1 | | | | | | | | |
| P/agents/code-reviewer{,-checkpoint,-standards}.md (generated) | P1x | | | | | | | | |
| P/skills/orchestra/references/{coordination,briefs,triage,handoff,parallel,finishing,repair-rounds,final-review,autonomy}.md | K1 | | | | | | | | |
| P/skills/orchestra/references/cli.md | | | | | | | | | D1 |
| P/skills/orchestra-review/SKILL.md, references/{checkpoint,final,correctness}.md, references/standards.md | K2 (standards.md new) | | | | | | | | |
| P/skills/orchestra-critique/SKILL.md, orchestra-build/SKILL.md, orchestra-build/references/repair.md, orchestra-operate/references/gate.md | K2 | | | | | | | | |
| AGENTS.md, docs/models.md, docs/roles.md | P1x | | | | | | | | |
| README.md, docs/cli.md, docs/hooks.md | | | | | | | | | D1 |

Spike X1 owns no repository path. Its scratch directory comes from `mktemp -d`, outside the repository.

Shared resources, by name:
- **design/2.2 tip**: only the coordinator merges into it.
- **generator output**: `generate.py` writes every `P/agents/*.md`. K1 commits only `orchestrator.md`; P1x commits only the three `code-reviewer*.md` files.
- **corpus fixture**: `guard-fixtures.ts` is written by `sync.py`. G1 owns it in W1 and G2 in W2.

## 4. Tickets

Architectural tickets (marked **[A]**) are checkpoint-worthy. Under 2.2 the wave reviewer covers them, with the checkpoint lens. Every ticket is role `builder`; the preset is given per ticket. In the Tests first lists, names in backticks are spec test names. "Flip" means an existing 2.1 test whose fixture changes.

### W1

#### E1 [A]: materiality, keep/remove at add, read-only review collision
- **Goal:** add review `issues` with severities, stamp `rev: "2.2"` on cards, and migrate the shared test helpers first. Add the keep/remove heading check in `add_task`. Let two read-only reviews with no shared resource run together.
- **Spec:** 5.6 (items 2 to 4 and 6), 5.13 items 1 and 2 (the engine side), 5.17, and section 6 rows `rev` and `notes`.
- **Class / preset:** Architectural; builder `implementation` (`Mode: implementation`).
- **Starting artifact:** design/2.2 at the C8 amendment tip (code identical to bca4e98).
- **Owns:** engine.py, orchestra.py (`review` reads the body), test_engine.py, test_integration.py, test_hooks.py (helper migration only).
- **Depends on:** none.
- **Order inside the ticket:**
  1. Helper migration. Commit 1 changes the `EngineFixture.review` helper (test_engine.py:42), the `FinalBlockerTests.record` helper (505-511), the direct report writes at test_engine.py:144, 1016 and 1122 and test_hooks.py:1236, and the test_integration.py review writers, so that they emit `issues`. The suite stays green on the 2.1 engine. Verify with the three file runs below before any engine edit.
  2. Engine changes.
  3. Flips. Add `## Keep` and `## Remove` lines to the builder brief fixtures at test_engine.py:382-412.
- **Signatures:**
  - `record_review(...)` keeps its 2.1 signature and reads `issues` from the report body.
  - Store `notes: list[str]` on the receipt.
  - `add_task` stamps `rev`.
  - Add the module constant `KEEP_REMOVE = ('## Keep', '## Remove')`, checked against the builder `brief` text in `add_task` only, never in `_start_assignment`.
  - In `_ready`, skip a collision when `_read_review(a) and _read_review(b)` and their resources do not intersect.
- **Tests first:**
  - `test_notes_only_report_is_clean_and_accepts`
  - `test_blocking_issue_needs_impact`
  - `test_issues_must_match_findings_and_verdict`
  - `test_repair_refused_for_notes_only`
  - `test_review_of_2_2_card_without_issues_refused`
  - `test_review_of_migrated_card_keeps_string_findings`
  - `test_clean_report_with_empty_issues_accepts`
  - `test_builder_brief_without_keep_remove_refused_at_add`
  - `test_builder_brief_with_none_lists_accepted`
  - `test_queued_2_1_builder_without_headings_still_dispatches`
  - `test_reviewer_brief_needs_no_keep_remove`
  - `test_two_read_only_reviews_on_same_file_do_not_collide`
  - `test_read_only_reviews_sharing_a_resource_still_collide`
  - `test_review_still_collides_with_running_writer` (regression)

  `test_hold_refused_for_notes_only` goes to E4 and `test_run_brief_lists_notes` to E6.
- **Acceptance:**
  - `python3.11 -m unittest discover -s tests -k test_notes_only_report_is_clean_and_accepts -k test_blocking_issue_needs_impact -k test_issues_must_match_findings_and_verdict -k test_repair_refused_for_notes_only -k test_review_of_2_2_card_without_issues_refused -k test_review_of_migrated_card_keeps_string_findings -k test_clean_report_with_empty_issues_accepts -k test_builder_brief_without_keep_remove_refused_at_add -k test_builder_brief_with_none_lists_accepted -k test_queued_2_1_builder_without_headings_still_dispatches -k test_reviewer_brief_needs_no_keep_remove -k test_two_read_only_reviews_on_same_file_do_not_collide -k test_read_only_reviews_sharing_a_resource_still_collide -k test_review_still_collides_with_running_writer` exits 0.
  - `python3.11 -m unittest discover -s tests -p 'test_engine.py'`, the same with `-p 'test_integration.py'`, and with `-p 'test_hooks.py'` each exit 0.
- **Keep:** string-only reports for cards without `rev`; `_check_contract` at dispatch; the reviewed-target exemption in `_ready`.
- **Remove:** none.

#### G1: abbreviated long options and `commit --amend`; the chained-command regression corpus
- **Goal:** in both guards, read a unique long-option prefix as the guarded option. Deny `commit --amend`. Add the 5.16 item 7 chain and its 13 variants as regression cases.
- **Spec:** 5.15 (all), 5.16 item 7.
- **Class / preset:** Bounded; builder `sensitive`.
- **Starting artifact:** design/2.2 at the C8 amendment tip (code identical to bca4e98).
- **Owns:** guards.py, guard.ts, guard.test.ts, guard-rules.json (`commit_guarded_flags: ["--amend"]`), guard-corpus.json, guard-fixtures.ts (via `sync.py`), test_guard_corpus.py, tests/fixtures/git-long-options.json (new).
- **Depends on:** none.
- **Decisions:**
  - Add a `_long_prefix(verb, token, guarded) -> str | None` helper in guards.py and the same helper in guard.ts.
  - The fixture `git-long-options.json` maps each of the ten verbs in 5.15 to its full long options, taken once from `git <verb> --git-completion-helper-all` (git 2.50.1). The builder records the git version inside the file.
  - Push `--delete` and its prefixes classify as deny in W1, the 2.1 meaning of `--delete`. This closes the F13 hole now; G2 moves the shape to merged-delete.
- **Tests first:**
  - `test_no_harmless_option_is_prefix_of_guarded_option`
  - the corpus deny, release and allow rows of 5.15
  - the 14 chain cases of 5.16 item 7, each boundary/delete in both guards (regression)
- **Acceptance:**
  - `python3.11 -m unittest discover -s tests -p 'test_guard_corpus.py'` exits 0.
  - `python3 plugins/orchestra/hooks/mod/fixtures/sync.py --check` exits 0.
  - `CLAUDE_CODE_ENABLE_FUNCTION_HOOKS=1 claude plugin test plugins/orchestra` exits 0.
  - `python3.11 -m unittest discover -s tests -k test_mod_fixtures_are_in_sync_with_the_corpus` exits 0.
- **Keep:** every full spelling's class, apart from `commit --amend`; exemptions counting only in full; no prefix matching of global options or `worktree` subcommands.
- **Remove:** none.

#### M1: mod delegate hardening and the H1/H2 diagnosis
- **Goal:** try to reproduce the `FAIL_CLOSED` message at the mod seam for H1 and H2 with the testkit fake `$`, and record the result in the report. `delegate` spawns from the plugin root. CLI reads pass `--repo` and keep their spawn cwd. Failure reasons name the failure class. An exit-2 deny surfaces its own reason.
- **Spec:** 5.16 items 1, 2, 4 and 8.
- **Class / preset:** Bounded; builder `sensitive` (bug lane: diagnose and write the failing test before the fix).
- **Starting artifact:** design/2.2 at the C8 amendment tip (code identical to bca4e98).
- **Owns:** orchestra.ts, orchestra.test.ts. `testkit.ts` is read-only to M1. If the fake `$` cannot express a missing cwd, M1 reports BLOCKED naming `testkit.ts`.
- **Depends on:** none.
- **Signatures:**
  - `failClosed(kind: 'spawn' | 'exit' | 'timeout' | 'bad output', detail: string): string` returns "Orchestra guard error (spawn: CODE | exit N | timeout | bad output); failing closed", filled in for the one class.
  - `runHook(args, opts: {cwd: string})` takes an explicit cwd. `delegate` passes `$.plugin.root`. `readWhere`, `autonomyCli` and `--cli status` keep the session cwd and add `--repo <session cwd>`. When that directory is missing, they return "Session directory no longer exists: cd to an existing directory, then retry".
- **Tests first** (`test(...)` titles):
  - "delegate spawns the hook from the plugin root when the session cwd is gone"
  - "cli reads pass --repo and keep their spawn cwd"
  - "delegate failure reason names the failure class"
  - "delegate surfaces the reason of an exit-2 deny"
- **Acceptance:** `CLAUDE_CODE_ENABLE_FUNCTION_HOOKS=1 claude plugin test plugins/orchestra` exits 0. The report states for H1 and H2 separately: reproduced, not reproduced, or inconclusive, with the test that shows it.
- **Keep:** fail-closed for every unexpected error; the 8000 ms timeout.
- **Remove:** none.

#### K1: orchestra coordinator skill references
- **Goal:** write the coordinator procedure for waves, the ladder and hold, gates, the final phase, triage, the ledger, keep/remove, the brief, autonomy and relaunch.
- **Spec:** the coordinator-skill items of 5.1, 5.2, 5.3, 5.4, 5.5, 5.7, 5.8, 5.9, 5.10, 5.11, 5.12 and 5.13:
  - coordination.md: 5.1, 5.4 items 1 and 2, 5.12.
  - briefs.md: 5.11, 5.12 (the Known findings block), 5.13 item 1.
  - triage.md: 5.5 item 2 (non-builder cause), 5.7.
  - handoff.md: 5.9.
  - parallel.md:16: 5.2 and 5.5 item 4.
  - finishing.md: 5.8 item 4, 5.9 items 3 and 4.
  - repair-rounds.md (rewrite to the ladder): 5.2.
  - final-review.md: 5.5 items 1 to 9, 5.7, 5.11.
  - autonomy.md: 5.3, 5.8, 5.9, 5.10.
- **Class / preset:** Bounded; builder `mechanical`.
- **Starting artifact:** design/2.2 at the C8 amendment tip (code identical to bca4e98).
- **Owns:**
  - P/skills/orchestra/references/{coordination,briefs,triage,handoff,parallel,finishing,repair-rounds,final-review,autonomy}.md
  - tests/skill_phrases/orchestra.json
  - P/agents/orchestrator.md (regenerated)
- **Depends on:** none (procedure text only). Docs may lead the code inside one PR: no test checks CLI names against `orchestra.py` (OBSERVED, test_skills.py).
- **Phrase literals** (decided here):
  - Remove `"Round 5"`.
  - Add:
    - `"Sonnet builder, one Opus repair, then hold"` (repair-rounds ladder)
    - `"only when the next wave depends on its code"` (wave gate rule)
    - `"investigator-code re-diagnoses a repeated finding before the next repair"` (final round rediagnosis)
    - `"add every card of the round, then let all report, then record"` (final round order)
    - `"a non-builder cause goes to inline or card, never brief alone"` (non-builder final finding triage; in both final-review.md and triage.md)
    - `"overrides Push and Engine-gated actions for that remote and target only"` (release override scope)
    - `"ready to release"` (finishing ready to release)
    - `"an explicit release assignment from the user, before or after the brief, counts"` (finishing release assignment; spec 5.9 item 4, C7/R4-8)
    - `"Held / next phase"` (PR held section)
  - autonomy.md:22 also gains "Held work never blocks a later wave; the final phase must clear it before `finish`".
- **Constraints** (OBSERVED, test_skills.py):
  - briefs.md must stay at or under 1800 bytes (it is 1593 now), and orchestrator.md at or under 10500 bytes. Fit the Keep/Remove part and the known-findings line by tightening first; drop no rule.
  - **Budget rule** (coordinator decision 10 after C7): if a rule still cannot fit, K1 reports DONE, not BLOCKED, with the measured size and the minimum new cap (at most 15% above the old one). test_skills.py is K2's file in W1, so the coordinator raises the cap at test_skills.py:206 (briefs.md) or :210 (orchestrator.md) as reserved inline work at the W1 merge, after K2 merges, and records the old cap, the new cap and the reason in docs/BUILD-LEDGER.md. In that overflow case K1's acceptance is the file run with the one failing budget test named and its failure quoted: `python3.11 -m unittest discover -s tests -p 'test_skills.py'` shows exactly one failure, in `test_budgets` (briefs.md) or `test_generated_agent_budgets` (orchestrator.md), with the measured size (C8/P-12).
  - `exact artifact` stays only in repair-rounds.md, `empty context` only in briefs.md, and `reserve every card` only in parallel.md.
  - Keep repair-rounds.md's Source header.
  - final-review.md keeps `` `Lens: specialist:<name>` `` and `specialists.md`, and never says "The lens never gates".
  - autonomy.md keeps the strings `autonomy arm`, `autonomy disarm`, `autonomy status`, `park TASK --reason TEXT` and `unpark TASK`, and contains no `--max-passes`.
  - No four-word phrase may be shared between SKILL.md and coordination.md.
  - `test_handoff_ledger_line_has_the_six_e2_fields` must stay green.
- **Tests first:** add the phrase literals above to orchestra.json and see `test_per_directory_phrase_files` fail.
- **Acceptance:**
  - `python3.11 -m unittest discover -s tests -p 'test_skills.py'` exits 0.
  - `python3.11 plugins/orchestra/scripts/generate.py --check` exits 0, after running it without `--check` and committing only orchestrator.md.
  - `grep -c "never brief alone" plugins/orchestra/skills/orchestra/references/final-review.md plugins/orchestra/skills/orchestra/references/triage.md` shows at least 1 for each file.
- **Keep:** the 2.1 `park` meaning for approval boundaries; the specialist rule (final-review.md:18-22); the `progress.md` lines.
- **Remove:** rounds 1 to 3, the round-5 breaker and the per-round log of repair-rounds.md:6 to 12; the fresh four-lens review and the cleanup card in final-review.md.

#### K2: role skills (review, critique, build, operate)
- **Goal:** add the materiality rule and severity line, the three-lens final table, the standards lens, the checkpoint wave and repair-diff duties, keep/remove checks, evidence reuse, the known-findings rule and the repair rung.
- **Spec:**
  - 5.5: the lens table, standards.md, and correctness.md taking the architecture category.
  - 5.6: items 1 and 5, both SKILL.md files.
  - 5.7: items 1 and 2 (checkpoint.md, final.md, review SKILL.md).
  - 5.11: review SKILL.md, final.md, checkpoint.md, operate gate.md.
  - 5.12 item 3 (review SKILL.md).
  - 5.13 item 3 (checkpoint.md) and build SKILL.md.
  - 5.1 and 5.4 (checkpoint.md, final.md).
  - 5.2 (build references/repair.md:7).
- **Class / preset:** Bounded; builder `mechanical`.
- **Starting artifact:** design/2.2 at the C8 amendment tip (code identical to bca4e98).
- **Owns:**
  - P/skills/orchestra-review/SKILL.md
  - P/skills/orchestra-review/references/{checkpoint,final,correctness}.md and references/standards.md (new)
  - P/skills/orchestra-critique/SKILL.md
  - P/skills/orchestra-build/SKILL.md and references/repair.md
  - P/skills/orchestra-operate/references/gate.md
  - tests/skill_phrases/orchestra-{review,critique,build,operate}.json
  - tests/test_skills.py
- **Depends on:** none.
- **Decisions:**
  - standards.md carries `Sentinel: orchestra-review/references/standards.md` and no Source header. The test rule allows a header only for a sourced SKILL-SOURCES row (OBSERVED), and the text is Orchestra-only. Spec 5.5 Files now says Sentinel only (coordinator decision 11 after C7).
  - final.md holds the three-lens table and names which checklist files each lens reads. A lens file never names another lens file (`test_a_lens_file_never_points_into_another_lens_file`), so correctness.md takes the architecture category without naming architecture.md. final.md keeps `specialist:<name>` and documents `cleared` (5.5 item 3).
  - test_skills.py:
    - Add `'references/standards.md'` to TABLE under orchestra-review.
    - Add the materiality paragraph to IDENTICAL_COPIES for the review and critique SKILL.md files.
    - Add `test_final_lens_table_covers_every_category`: every category in the final.md table belongs to exactly one of the three lenses, and the union equals {requirements, correctness, tests, architecture, security, standards, cleanup}.
  - Phrase literals:
    - `"a finding blocks only when it has a real, material impact"` in orchestra-review.json and orchestra-critique.json (materiality rule).
    - `"do not raise a known finding unless the code at its location changed"` in orchestra-review.json (known findings rule).
    - `"Sentinel: orchestra-review/references/standards.md"`.
    - `"## Keep"` in orchestra-build.json.
    - `"repair_check: true"` in orchestra-review.json (repair check marker; checkpoint.md tells the reviewer of a repair-diff check to put it in the report; spec 5.1 item 6, C7/R4-7).
- **Constraints:**
  - Each SKILL.md stays at or under 4096 bytes (review is 3752 now).
  - Each reference file stays at or under 6144 bytes.
  - Review SKILL.md no longer contains "critical, major, minor or trivial".
  - `test_specialist_contract_has_both_sides` and `test_worker_contract_phrases_do_not_repeat_in_role_skills` stay green.
  - **Budget rule** (coordinator decision 10 after C7): compress first. If the review SKILL.md (test_skills.py:201) or a reference file (:205) still cannot hold a rule, K2 raises that cap in test_skills.py by the minimum needed (at most 15%), records the old cap, the new cap and the reason in its report for docs/BUILD-LEDGER.md, and reports DONE. No budget is a reason for BLOCKED.
- **Tests first:** `test_final_lens_table_covers_every_category`, the TABLE entry (standards.md is missing until it is written), and the phrase literals.
- **Acceptance:**
  - `python3.11 -m unittest discover -s tests -p 'test_skills.py'` exits 0.
  - `python3.11 -m unittest discover -s tests -k test_final_lens_table_covers_every_category` exits 0.
- **Keep:** scope-drift findings (review SKILL.md:19); confidence and confirmed/plausible; the final.md out-of-lens note.
- **Remove:** "Grade severity: critical, major, minor or trivial"; the four-lens split in final.md.

#### P1x: standards-lens packaging and the model matrix
- **Goal:** add the `code-reviewer-standards` variant on Sonnet medium, change the code-reviewer prompt to "the three lens cards", and record the matrix sentence.
- **Spec:** 5.5 (models.json, roles.json, generate.py, generated agents, AGENTS.md, docs/models.md, docs/roles.md), section 7.
- **Class / preset:** Bounded; builder `mechanical`.
- **Starting artifact:** design/2.2 at the C8 amendment tip (code identical to bca4e98).
- **Owns:** models.json, roles.json, generate.py, P/agents/code-reviewer.md, P/agents/code-reviewer-checkpoint.md, P/agents/code-reviewer-standards.md (new, generated), tests/test_packaging.py, AGENTS.md, docs/models.md, docs/roles.md.
- **Depends on:** none.
- **Decisions:**
  - `models.json`: `code-reviewer.presets.standards = {"model": "claude-sonnet-5-5", "effort": "medium"}`, with no dispatch override.
  - `generate.py` `VARIANT_NOTES[('code-reviewer', 'standards')] = ' Mode: final. Lens: standards. Standards and cleanup categories only.'`
  - roles.json code-reviewer `modes` stay `["checkpoint", "final"]`, so the contract hash is unchanged. The prompt's "the four lens cards" becomes "the three lens cards".
  - AGENTS.md gains "except the standards lens, Sonnet 5.5 medium".
- **Tests first** (test_packaging.py):
  - `test_standards_preset_is_sonnet_medium_variant_file` (new): the file exists, its frontmatter model is Sonnet 5.5, effort is medium, and the description names `Lens: standards`.
  - Flip `test_role_matrix_files_and_read_only_enforcement`: add `code-reviewer-standards` to its agent-name set.
  - `test_claude_variant_descriptions_name_their_mode` stays green.
- **Acceptance:**
  - `python3.11 -m unittest discover -s tests -p 'test_packaging.py'` exits 0.
  - `python3.11 plugins/orchestra/scripts/generate.py --check` exits 0.
  - `python3.11 -m unittest discover -s tests -k test_generated_agent_budgets -k test_generated_agents_match_the_canonical_source` exits 0.
- **Keep:** the final preset on Opus high; checkpoint on Opus medium; the run contract hash; `test_manifest_versions_are_equal` at 2.1.0 (the release card bumps it).
- **Remove:** none.

#### X1 (Spike, never merged): Workflow under `claude -p`, and pass env inheritance
- **Goal:** answer two questions and report the answers:
  - Do both agents of a two-agent Workflow return before `claude -p` exits (5.10 item 9)?
  - Does a Bash call inside the pass see `ORCHESTRA_RELAUNCH_PASS` (K11, which 5.10 item 5.3 relies on)?
- **Class / preset:** Spike; builder `implementation`. It runs in its own worktree and does L0 in a `mktemp -d` scratch repository; no repository path is edited and nothing is committed (coordinator decision 14 after C7: the I1 spike showed `claude -p` runs from a worker).
- **Depends on:** none.
- **Steps:** see L0 in section 7.
- **Done contract:**
  - For Workflow: yes, no or inconclusive, citing `pass.log`, `a.txt`, `b.txt` and `WORKFLOW-DONE`.
  - For env: yes or no, citing `env.txt`.
  - The `claude --version` used.
  - The result feeds H1: the prompt allows foreground Workflow only on yes. The env answer is recorded only: H1 binds the pass through the marker file of spec 5.10 item 5.3 whatever it is, so env = no is not a failure and blocks nothing.

### W2

#### E2 [A]: findings ledger, out-of-scope triage, evidence reuse, failed-gate rule, gate argv
- **Goal:**
  - Add the `findings` ledger and the `finding add|list` commands.
  - Add `out_of_scope` on final receipts only, and the completion triage check.
  - Add `gate_receipts` on reviews, the `run_gate` repeat refusal with `--again`, and the rule that a CLEAN review citing a failed gate is refused.
  - `run_gate` refuses every non-allow decision.
- **Spec:** 5.12, 5.7 items 2 to 4, 5.11 items 1 and 2, 5.4 item 3 (base rule; the held-tip exception is in E4), 5.14 item 5, and section 6 rows `findings`, `out_of_scope` and `gate_receipts`.
- **Class / preset:** Architectural; builder `implementation`.
- **Starting artifact:** design/2.2 at the W1 closing tip.
- **Owns:** engine.py, orchestra.py, test_engine.py, test_integration.py (fixture upkeep only).
- **Depends on:** E1.
- **Signatures:**
  - `add_finding(self, actor, lease, review_id, kind, index, disposition, reason, card=None) -> dict`. It needs the lease. `kind` is `finding` or `out_of_scope`. `index` must point at an existing item of that receipt. Dispositions:
    - for `finding`: one of `rejected`, `deferred`, `inline`, `card`, `brief`;
    - for `out_of_scope`: one of `inline`, `card`, `brief`.
  - `list_findings(self, for_brief=False) -> list | str`. It is lease-free. `for_brief` renders a "Known findings" block (id, text, disposition, reason).
  - `_fingerprint(text) -> str` is the SHA-256 hex of the text with whitespace collapsed (N5).
  - `run_gate(self, actor, lease, name, argv, again=False)`.
  - CLI:
    - `finding add --review ID --kind finding|out_of_scope --index N --disposition D --reason TEXT [--card ID]`
    - `finding list [--for-brief]`
    - `gate NAME [--again] -- ARGV`
- **Tests first:**
  - `test_finding_add_requires_lease_and_known_review`
  - `test_finding_list_for_brief_renders_known_findings`
  - `test_rejected_finding_does_not_allow_accept`
  - `test_2_1_state_without_findings_loads`
  - `test_finding_add_rejects_bad_disposition_and_index`
  - `test_checkpoint_review_with_out_of_scope_is_refused`
  - `test_final_out_of_scope_does_not_block_verdict`
  - `test_completion_requires_triage_of_out_of_scope`
  - `test_triage_carries_forward_by_fingerprint`
  - `test_gate_repeat_on_same_artifact_refused_without_again`
  - `test_failed_gate_rerun_allowed`
  - `test_review_cites_stale_gate_refused`
  - `test_review_cites_current_passed_gate_accepted`
  - `test_clean_review_citing_failed_gate_refused`
  - `test_gate_refuses_merged_delete_and_boundary_argv`. This uses `git branch -d x` and `git worktree remove x`, which are boundary on the W1 classifier, and `git branch -D x`, which is deny on W1 and merged-delete after G2. All three are refused, so the test is independent of G2 (REASONED).
- **Acceptance:**
  - `python3.11 -m unittest discover -s tests -k test_finding_ -k test_rejected_finding_does_not_allow_accept -k test_2_1_state_without_findings_loads -k test_checkpoint_review_with_out_of_scope_is_refused -k test_final_out_of_scope_does_not_block_verdict -k test_completion_requires_triage_of_out_of_scope -k test_triage_carries_forward_by_fingerprint -k test_gate_repeat_on_same_artifact_refused_without_again -k test_failed_gate_rerun_allowed -k test_review_cites_ -k test_clean_review_citing_failed_gate_refused -k test_gate_refuses_merged_delete_and_boundary_argv` exits 0.
  - `python3.11 -m unittest discover -s tests -p 'test_engine.py'` exits 0.
- **Keep:** the `progress.md` lines; failed gates rerun freely; gates available at any time.
- **Remove:** none. The named replacement is that a boundary argv in `gate` is refused (5.14).

#### G2 [A]: merged-branch deletion
- **Goal:** classify the merged-delete shapes in both guards. Enforce the stand-alone denials. Add the hooks.py merge check, which runs before the autonomy-off allow and also when the engine is None. Change the autonomy deny to `boundary == 'delete'`. Add `decision_category` to the corpus schema.
- **Spec:** 5.14 items 1 to 4 and 6, the 5.14 flip table, and section 6 (corpus key).
- **Class / preset:** Architectural; builder `sensitive`.
- **Starting artifact:** design/2.2 at the W1 closing tip.
- **Owns:** guards.py, guard.ts, guard.test.ts, guard-rules.json (`_doc` only), guard-corpus.json, fixtures/sync.py (`decision_category?` in `CorpusCase`), guard-fixtures.ts, hooks.py, test_hooks.py, test_guard_corpus.py, orchestra.test.ts.
- **Depends on:** G1 (same guard files; the abbreviation rule feeds `--del`). M1 (orchestra.test.ts after M1's `delegate` change).
- **Signatures:**
  - Decision gains optional `kind`, `remote`, `branch` and `argv` fields when `category == 'merged-delete'`, in both guards.
  - hooks.py `_merged_delete_check(decision, cwd, autonomy) -> dict | None` returns a deny payload or None. Inside it: `_branch_merged(repo, tip, default) -> bool` (ancestor, tree in `rev-list --first-parent -n2000 --format=%T`, or a covering branch) and `_remote_tip_matches(repo, remote, branch) -> bool` (`ls-remote`, `GIT_TERMINAL_PROMPT=0`, 3 s timeout).
- **Tests first:**
  - test_hooks.py:
    - `test_merged_delete_allows_ancestor_branch`
    - `test_merged_delete_allows_squash_tree_equal_branch`
    - `test_merged_delete_allows_branch_covered_by_tree_equal_branch`
    - `test_merged_delete_denies_unmerged_branch`
    - `test_merged_delete_checked_with_autonomy_off_and_no_engine`
    - `test_merged_delete_denied_under_autonomy`
    - `test_remote_delete_denied_when_ls_remote_differs_or_times_out`
  - test_guard_corpus.py and guard.test.ts: `test_corpus_decision_category_matches`.
  - orchestra.test.ts: "merged-delete is delegated".
  - The corpus rows of 5.14 in both guards.
- **Flips** (5.14 table):
  - `DENY_COMMANDS` entries move to a new `MERGED_DELETE_COMMANDS` list.
  - The `DENY_PUSH_DESTINATION` entry `git push --delete origin main` moves to a hook-level test.
  - `test_a2_always_deny_rules_remain` drops its two delete entries.
  - The inline-walker count at test_guard_corpus.py:127-136 goes from 21 to 19.
  - Corpus `deny-destructive-3`, `deny-destructive-36`, `deny-push-destination-4`, `inline-r2b-55` and `inline-r2b-60` become boundary/merged-delete.
- **Acceptance:**
  - `python3.11 -m unittest discover -s tests -k test_merged_delete_ -k test_remote_delete_denied_when_ls_remote_differs_or_times_out -k test_corpus_decision_category_matches` exits 0.
  - `python3.11 -m unittest discover -s tests -p 'test_hooks.py'` exits 0.
  - `python3.11 -m unittest discover -s tests -p 'test_guard_corpus.py'` exits 0.
  - `python3 plugins/orchestra/hooks/mod/fixtures/sync.py --check` exits 0.
  - `CLAUDE_CODE_ENABLE_FUNCTION_HOOKS=1 claude plugin test plugins/orchestra` exits 0.
- **Keep:**
  - every other denied shape;
  - non-forced `branch -d` and `branch -d -r` as boundary/delete;
  - `boundary_categories` `[delete, merge]`;
  - the release permit path;
  - corpus `guard-r12-16`, `guard-r12-17`, `guard-fx4-3`, `inline-r2b-54` and `inline-r2b-80` as deny.
- **Remove:** the two always-deny delete entries named in the flips.

### W3

#### E3 [A]: wave review and the repair-diff check
- **Goal:**
  - Add the `wave` label and `"wave:W"` resolution.
  - Add per-task findings at all five readers, and the per-task O22 void.
  - Add the tip rule for repair-diff checks, the `repair_check` marker, and accept-before-repair at dispatch for overlapping reported cards only (C7/R4-1).
  - Add `supersede`, and a `status` waves list with `next_depends`.
- **Spec:** 5.1 (all items), 5.4 item 4, section 6 rows `wave`, `superseded_by`, `task_findings` and `repair_check`.
- **Class / preset:** Architectural; builder `implementation`.
- **Starting artifact:** design/2.2 at the W2 closing tip.
- **Owns:** engine.py, orchestra.py, test_engine.py, test_integration.py, test_hooks.py (fixture upkeep only).
- **Depends on:** E2 (the ledger feeds rejected-only coverage; `gate_receipts` sits next to `task_findings` in `record_review`).
- **Signatures:**
  - `_task_findings(receipt, task_id) -> list[str]`. With `task_findings` present it returns that task's entry; an absent key returns `[]`. Without `task_findings` it returns `findings`. It is used by:
    - the `record_review` verdict;
    - `_review_verdicts`;
    - the repair precondition in `add_task`;
    - `accept`;
    - the per-task loop in `_completion_evidence`.
  - `_accept_refusal(self, state, cache, task_id) -> str | None` is factored out of `accept`. `_evidence_scopes(self, state, task_id) -> list` returns the scopes the card's acceptance depends on: its own `_scope_of` when it is accepted on its report artifact (engine.py:810-811), otherwise the stored `scope` of each covering receipt (engine.py:769, 786). `_start_assignment` refuses a builder `repair` card with "Accept X first; a repair would make its evidence stale" while a `reported` card has `_accept_refusal(...) is None` and one of its evidence scopes overlaps the repair's `_reservation` files: `None` on either side overlaps, otherwise the `_collides` path rule (equal or parent), resources ignored (spec 5.1 item 10).
  - `record_review` stores `repair_check: true` from the body on checkpoint receipts and refuses it otherwise: "repair_check must be true on a checkpoint receipt".
  - `supersede(self, actor, lease, task_id) -> dict`.
  - `status()` gains `waves: [{wave, tasks, next_depends}]` in first-add order. `next_depends` is true when a card of the next wave lists a member in `dependencies`, or when its `files` or `inputs` collide with a member's `files` under `_collides` path rules.
  - CLI: `supersede TASK`. The `add` help names `wave` and `review_of: ["wave:W"]`.
- **Tests first** (test_engine.py unless noted):
  - `test_wave_review_of_resolves_wave_members_at_add`
  - `test_wave_label_refused_on_repair_and_review_cards`
  - `test_adding_card_to_reviewed_wave_is_refused`
  - `test_status_lists_waves_in_first_add_order`
  - `test_wave_review_task_findings_block_only_named_card`
  - `test_task_findings_must_match_findings_union`
  - `test_review_without_task_findings_blocks_all_covered`
  - `test_repair_diff_check_covering_chain_accepts_original`
  - `test_repair_diff_check_covers_card_with_all_findings_rejected`
  - `test_replacement_wave_review_after_member_parked`
  - `test_absent_task_findings_key_is_clean_at_every_reader`
  - `test_repair_diff_check_finding_on_ancestor_refused`
  - `test_clean_wave_member_accepts_after_sibling_repair`
  - `test_repair_dispatch_refused_only_by_overlapping_acceptable_cards`
  - `test_record_review_stores_repair_check_marker`
  - `test_supersede_unstarted_review_when_replacements_cover_it`
  - `test_status_marks_wave_dependency_from_dependencies_and_paths`
  - test_integration.py: `test_parked_member_wave_reaches_completion`
- **Flips:** test_engine.py:617-639 (`test_second_repair_suspends_entire_same_file_chain`). Add `task_findings: {R1: [bug2]}` to blocked2 and to any other BLOCKED repair-diff fixture the tip rule refuses. Where accept-before-repair refuses an existing fixture, accept the overlapping reported card first. test_engine.py:1499 (park) is not flipped.
- **Acceptance:**
  - `python3.11 -m unittest discover -s tests -k test_wave_ -k test_adding_card_to_reviewed_wave_is_refused -k test_status_lists_waves_in_first_add_order -k test_task_findings_must_match_findings_union -k test_review_without_task_findings_blocks_all_covered -k test_repair_diff_check_ -k test_replacement_wave_review_after_member_parked -k test_absent_task_findings_key_is_clean_at_every_reader -k test_clean_wave_member_accepts_after_sibling_repair -k test_repair_dispatch_refused_only_by_overlapping_acceptable_cards -k test_record_review_stores_repair_check_marker -k test_supersede_unstarted_review_when_replacements_cover_it -k test_status_marks_wave_dependency_from_dependencies_and_paths -k test_parked_member_wave_reaches_completion` exits 0.
  - The file runs for test_engine.py and test_integration.py each exit 0.
- **Keep:**
  - explicit `review_of` ids;
  - the 2.1 whole-list rule without `task_findings`;
  - review independence and artifact binding;
  - the whole-receipt O22 rule for `final=True`.
- **Remove:** none.

### W4

#### E4 [A]: the hold state, the repair ladder, held work at completion, the held-tip gate attribution
- **Goal:**
  - Add `held` to `TASK_STATES`, and the `hold` command with the held log.
  - Make held cards ready-transparent and reserve-free.
  - Add the `repair_of` limits.
  - Let reviews cover held cards, and let `accept` take a held card.
  - Accept a held tip as an uncovered `task_findings` key only with a failed gate receipt.
- **Spec:** 5.2 (all), 5.3, 5.4 item 3 (held work), section 6 row `held_finding`.
- **Class / preset:** Architectural; builder `implementation`.
- **Starting artifact:** design/2.2 at the W3 closing tip.
- **Owns:** engine.py, orchestra.py, test_engine.py, test_hooks.py and test_integration.py (fixture upkeep only).
- **Depends on:** E3.
- **Signatures:**
  - Module function `_append_progress(state_dir, text)`: one `os.open(path, O_WRONLY | O_APPEND | O_CREAT)` and one `os.write` of the whole entry, locked or not; it may read the file only to choose the separator (spec 5.9 item 5, C7/R4-2). E4 adds it for its two writers; E6 moves the brief writers onto it.
  - `hold(self, actor, lease, task_id, finding) -> dict` appends `- held <id> (chain <ids>): <finding>` and the time to `<state>/progress.md` through `_append_progress`.
  - "Current blocking verdict comes from a repair-diff check" means the current blocking receipt carries `repair_check: true` (stored by E3; spec 5.2 item 2b, C7/R4-7). Both the `hold` precondition and the "Repair-diff check blocked X" refusal read that key.
  - `_ready`: a `held` dependency counts as satisfied; held cards are not added to `occupied`.
  - `add_task` `repair_of` refusals:
    - "Escalation ends at one repair; hold the chain"
    - "Repair-diff check blocked X; hold the chain"
  - `record_review` accepts an uncovered key only for a `held` tip when the report cites a failed receipt. It appends `- gate <receipt> attributed to held <tip>: <finding>` through `_append_progress`. Otherwise "Task findings name an uncovered task".
  - CLI: `hold TASK --finding TEXT`.
- **Tests first:**
  - `test_hold_moves_whole_chain_and_logs`
  - `test_hold_refused_without_current_blocking_findings`
  - `test_hold_rejected_only_card_blocked_by_repair_diff_check`
  - `test_repair_diff_check_without_repair_card_holds_rejected_only_card`
  - `test_dependency_on_held_card_is_ready`
  - `test_held_card_reserves_no_files`
  - `test_repair_of_repair_refused_during_build`
  - `test_repair_of_card_blocked_by_repair_diff_check_refused`
  - `test_repair_of_held_tip_allowed_and_chain_repairing`
  - `test_review_may_cover_held_cards`
  - `test_accept_held_card_with_clean_current_verdict`
  - `test_first_repair_of_builder_still_allowed`
  - `test_hold_refused_for_notes_only`
  - `test_completion_refuses_while_card_held`
  - `test_failed_gate_from_held_chain_does_not_block_later_wave`
  - `test_uncovered_key_refused_unless_held_tip_and_failed_gate`
- **Flips:** test_engine.py:617-639 adds `hold R1` before the R2 repair (5.2 flip, C6/R3-2).
- **Acceptance:**
  - `python3.11 -m unittest discover -s tests -k test_hold_ -k test_repair_diff_check_without_repair_card_holds_rejected_only_card -k test_dependency_on_held_card_is_ready -k test_held_card_reserves_no_files -k test_repair_of_ -k test_review_may_cover_held_cards -k test_accept_held_card_with_clean_current_verdict -k test_first_repair_of_builder_still_allowed -k test_completion_refuses_while_card_held -k test_failed_gate_from_held_chain_does_not_block_later_wave -k test_uncovered_key_refused_unless_held_tip_and_failed_gate -k test_second_repair_suspends_entire_same_file_chain` exits 0.
  - `python3.11 -m unittest discover -s tests -p 'test_engine.py'` exits 0.
- **Keep:** `PARKABLE`; `park` and `unpark` 2.1 behavior, for approval boundaries only (C7/R4-1); 2.1 chains deeper than one stay valid (the refusal applies to new `add` calls only); the Opus override.
- **Remove:** none.

### W5

#### E5 [A]: final receipts, held tips, final repair rounds
- **Goal:**
  - Final receipts attribute findings to chain tips and address every held tip, with a finding or `cleared`. `cleared` is refused on non-final receipts.
  - Add the final-finding `repair_of` form, and the final-round bookkeeping.
- **Spec:** 5.5 items 3 to 7 (engine), section 6 row `cleared`.
- **Class / preset:** Architectural; builder `implementation`.
- **Starting artifact:** design/2.2 at the W4 closing tip.
- **Owns:** engine.py, test_engine.py, test_integration.py, test_hooks.py (fixture upkeep only).
- **Depends on:** E4.
- **Decisions** (now spec text, 5.5 items 3 and 4 and section 6; coordinator decision 13 after C7):
  - A repair card added with a current final finding stores `final_round: int` and `final_findings: list[str]`, for E6's brief.
  - The round is 1 + the highest existing `final_round` when any card of that round has reported. Otherwise it is the same round. The first round is 1.
  - Refusals:
    - "Attribute final findings to the chain tip X"
    - "Final receipt must address held tip X"
    - for `cleared` on a non-final receipt: "Cleared entries are allowed only on final receipts" (spec 5.5 item 3).
- **Tests first:**
  - test_engine.py:
    - `test_contract_hash_unchanged_by_lens_change`
    - `test_final_findings_need_task_findings_on_chain_tips`
    - `test_repair_of_accepted_tip_with_final_finding_allowed`
    - `test_final_receipt_must_address_every_held_tip`
    - `test_held_tip_cleared_by_every_lens_accepts_without_repair`
  - test_integration.py:
    - `test_final_lens_then_repair_then_completion`
    - `test_final_round_repairs_held_and_lens_chains_then_completes`
    - `test_final_rounds_repeat_until_clean_with_no_cap`
    - `test_final_receipt_stale_when_card_added_after_it`
- **Acceptance:**
  - `python3.11 -m unittest discover -s tests -k test_contract_hash_unchanged_by_lens_change -k test_final_findings_need_task_findings_on_chain_tips -k test_repair_of_accepted_tip_with_final_finding_allowed -k test_final_receipt_must_address_every_held_tip -k test_held_tip_cleared_by_every_lens_accepts_without_repair -k test_final_lens_then_repair_then_completion -k test_final_round_repairs_held_and_lens_chains_then_completes -k test_final_rounds_repeat_until_clean_with_no_cap -k test_final_receipt_stale_when_card_added_after_it` exits 0.
  - The file runs for test_engine.py and test_integration.py each exit 0.
- **Keep:** the final coverage filter (engine.py:749, 754, 782); the stale-receipt rule (engine.py:919-921); the specialist lens.
- **Remove:** none.

### W6

#### E6 [A]: the run brief on every end path; hook missing-cwd and lock hardening
- **Goal:**
  - One brief writer for every end path, stored as `last_brief`, plus the `brief` command.
  - SessionStart shows the brief whatever the autonomy state, with a 2.1 fallback.
  - PreToolUse denies the delegated classes when the cwd is missing.
  - Hook state reads poll a non-blocking lock for 2 s. On busy: delegated classes are denied and other classes use the raw fallback. The Stop busy path lives in the hooks.py Stop branch (C7/R4-3).
  - Every `progress.md` write is a single append (C7/R4-2); end paths keep a stopped autonomy brief in `last_brief` (C7/R4-5).
- **Spec:** 5.9 items 1 to 3 and 5 (and item 4 in the brief content), 5.16 items 3 and 5, section 6 row `last_brief`.
- **Class / preset:** Architectural; builder `implementation`.
- **Starting artifact:** design/2.2 at the W5 closing tip.
- **Owns:** engine.py, hooks.py, orchestra.py, test_engine.py, test_hooks.py.
- **Depends on:** E5 (the brief reads `final_round`), E4 (held log), E2 (ledger), E1 (notes).
- **Signatures:**
  - `_brief_text(self, state, reason, at) -> str` replaces `_report_text`. It writes `## Run brief <time>` and the eight sections of 5.9 item 1, in order.
  - `_write_brief(self, state, reason)` appends to `progress.md` through `_append_progress` (E4) and sets `last_brief = {reason, at, text, path}`. It is called by:
    - `close_session` (`closed`);
    - `interrupt` and `interrupt_active` (`interrupted`);
    - `end_harness_session` (`ended`);
    - `_stop_autonomy` (the stop reason), which no longer reads and rewrites `progress.md` (engine.py:1044-1054).
  - Kept stop brief (C7/R4-5): while `_kept_autonomy(state)` returns a stopped report (engine.py:478-482), the end paths that do not stop autonomy still append their brief but leave `last_brief` unchanged (E8 applies the same rule in `end_pass_session`).
  - `brief(self) -> str` is lease-free and read-only. CLI: `brief`.
  - `Engine.__init__(..., lock_wait=None)`. With `lock_wait` set, `_state(write=False)` polls `LOCK_SH | LOCK_NB` until the wait ends, then raises `StateBusy(EngineError)`.
  - Module function `write_busy_brief(state_dir, at)` appends a `state busy` brief to `progress.md` through `_append_progress`, without touching `state.json`.
  - hooks.py:
    - `handle_event(..., busy=False, missing_cwd=False)`.
    - `main` builds the engine with `lock_wait=2.0`, sets `missing_cwd` when the payload cwd does not exist, and maps `StateBusy` to `busy=True`.
    - Stop branch (hooks.py:147-156), when `busy` and `_raw_autonomy_active` (hooks.py:232): poll `LOCK_EX | LOCK_NB` on `state.lock` until `STOP_LOCK_BUDGET = 8.0` seconds after the hook started (the 2 s read poll counts); if it frees, release it and run `hook_stop`; otherwise return no continuation and call `write_busy_brief`. Unarmed and busy: return `{}` and write nothing. `autonomy.active` stays true.
    - `_report_context` reads `last_brief` from `engine.status()`, uses " Run brief (<reason>): " and falls back to `autonomy.report` under " Autonomy report (".
  - Messages: "Session directory no longer exists: cd to an existing directory, then retry" and "Orchestra state is busy; retry".
- **Tests first:**
  - test_engine.py:
    - `test_run_brief_lists_held_log_and_final_rounds`
    - `test_close_session_writes_run_brief`
    - `test_interrupt_and_harness_end_write_run_brief`
    - `test_run_brief_lists_still_failing_on_deadline`
    - `test_brief_command_is_read_only`
    - `test_run_brief_needs_you_precedes_accepted`
    - `test_run_brief_keeps_2_1_lines`
    - `test_unarmed_completed_run_brief_says_ready_to_release`
    - `test_run_brief_marks_repaired_chains`
    - `test_run_brief_lists_notes`
    - `test_progress_writes_are_single_appends` (C7/R4-2)
    - `test_end_paths_keep_stopped_autonomy_brief` (C7/R4-5)
  - test_hooks.py:
    - `test_session_start_shows_newest_brief_without_autonomy`
    - `test_session_start_excerpt_contains_needs_you`
    - `test_session_start_falls_back_to_2_1_autonomy_report`
    - `test_pretooluse_missing_cwd_denies_delegated_class_with_reason`
    - `test_pretooluse_missing_cwd_allows_nothing_new`
    - `test_hook_state_read_fails_closed_after_lock_wait`
    - `test_hook_busy_lock_keeps_raw_fallback_for_other_classes`
    - `test_hook_stop_allows_stop_and_writes_state_busy_brief_on_lock_timeout` (patches `STOP_LOCK_BUDGET`; asserts `autonomy.active` stays true)
    - `test_hook_stop_busy_unarmed_writes_no_brief` (C7/R4-3)
    - `test_hook_stop_runs_when_lock_frees_within_budget` (C7/R4-3)
- **Flips** (heading only; the cap-to-deadline changes are E7's). Line numbers are at bca4e98 and will have moved: find each test by the assertion it holds. The binding rule is every assertion of `## Autonomy report` or `'Autonomy report'` in test_engine.py and test_hooks.py (C8/P-4):
  - test_engine.py:1626, 1642, 1661, 1673, 1679 and 1694: `## Autonomy report` becomes `## Run brief`. Where a test asserts the heading next to a cap stop, keep the cap stop as it is.
  - test_engine.py:1652 and 1663 (spec flip table, C7/R4-4): count `## Run brief` instead of `## Autonomy report`; the cap stop stays until E7.
  - test_engine.py:1694: `last_brief` still holds the stop brief after `interrupt` (C7/R4-5).
  - test_hooks.py:1439 and 1448: "Autonomy report" becomes "Run brief".
  - test_hooks.py:1463 and 1471 (tests at 1460 and 1465): also assert "Run brief" absent.
  - `test_main_uses_existing_repository_state_and_policy` (test_hooks.py:586, assertion at :606): assert the constructor call with `lock_wait=2.0` (C8/P-3).
  - test_hooks.py:1452 and 1465 (mock engines): stub `engine.status.return_value` with a dict that has no `last_brief` key.
- **Acceptance:**
  - `python3.11 -m unittest discover -s tests -k test_run_brief_ -k test_close_session_writes_run_brief -k test_interrupt_and_harness_end_write_run_brief -k test_brief_command_is_read_only -k test_unarmed_completed_run_brief_says_ready_to_release -k test_session_start_ -k test_pretooluse_missing_cwd_ -k test_hook_state_read_fails_closed_after_lock_wait -k test_hook_busy_lock_keeps_raw_fallback_for_other_classes -k test_hook_stop_allows_stop_and_writes_state_busy_brief_on_lock_timeout -k test_progress_writes_are_single_appends -k test_end_paths_keep_stopped_autonomy_brief -k test_hook_stop_busy_unarmed_writes_no_brief -k test_hook_stop_runs_when_lock_frees_within_budget` exits 0.
  - The file runs for test_engine.py and test_hooks.py each exit 0.
- **Keep:** every 2.1 report field; `autonomy.report` readable; the raw-state fallback (hooks.py:357-360) for non-delegated classes; blocking locks for CLI writers (`lock_wait=None`).
- **Remove:** the `## Autonomy report` heading.

### W7

#### E7 [A]: autonomy without caps; signature stalls; held work live; 2.1 compatibility
- **Goal:**
  - Stop on caps never; a 2.1 ledger with caps still arms, and its caps are recorded but not enforced.
  - Add the progress signature, and stalls by signature.
  - `_complete` checks all-accepted before running ledger checks.
  - Held cards count as live work; the run stops `parked-only` only when a held chain and a parked boundary card remain.
  - The band reads "pass N". The template loses the cap fields and gains the Release-line comment and the override sentence.
- **Spec:**
  - 5.8 items 1 to 7;
  - the 5.8 item 8 template text;
  - 5.10 item 7 (signature);
  - section 8;
  - section 6 rows `max_passes`/`max_stalls` and `signature`.
- **Class / preset:** Architectural; builder `implementation`.
- **Starting artifact:** design/2.2 at the W6 closing tip.
- **Owns:** engine.py, test_engine.py, test_hooks.py, test_integration.py, autonomy.ts, autonomy.test.ts, autonomy-template.md.
- **Depends on:** E6 (deadline stops write the run brief), E4 (held), E5 (final findings open).
- **Signatures:**
  - `_signature(self, state) -> str` is the SHA-256 of canonical JSON (5.10 item 7). `autonomy_status()` gains `signature`.
  - `_complete(self, state)` runs the all-accepted and evidence checks first, and the ledger completion checks only after they pass.
  - `hook_stop` prints "Autonomy pass N" without "of M".
  - `parse_ledger` accepts a ledger with no caps.
- **Tests first:**
  - `test_hook_stop_never_stops_on_pass_count`
  - `test_hook_stop_never_stops_on_stalls`
  - `test_hook_stop_continues_while_held_cards_remain`
  - `test_hook_stop_parked_only_when_held_and_parked`
  - `test_complete_skips_ledger_checks_until_all_accepted` (patches `Engine.artifact` and asserts zero calls while a card is queued; C7/R4-6)
  - `test_hook_stop_not_complete_while_held`
  - `test_hook_stop_not_complete_while_final_finding_open`
  - `test_hook_stop_not_complete_while_card_repairing`
  - `test_hook_stop_deadline_still_stops` (regression)
  - `test_ledger_without_caps_arms`
  - `test_2_1_ledger_with_caps_still_arms_and_caps_are_ignored`
  - `test_signature_changes_on_report_hold_or_gate`
  - `test_2_1_state_fixture_loads_under_2_2`, with the fixture as an inline dict in test_engine.py
  - `test_2_1_parked_card_keeps_park_semantics`
  - autonomy.test.ts: "band renders pass count without maximum"
- **Flips** (5.8 table, as amended for C7/R4-4):
  - unchanged: test_engine.py:1278 and 1311;
  - test_engine.py:1335 gains `signature`;
  - test_engine.py:1346 drops the cap fields and asserts the override sentence;
  - test_engine.py:1356;
  - test_engine.py:1370 and 1379 are removed;
  - test_engine.py:1626 and 1694 stop by the deadline; 1694 asserts `last_brief` still holds the `deadline` brief;
  - test_engine.py:1652 and 1663 stop by the deadline (1663: `last_stop_reason` `deadline`);
  - test_hooks.py:1421;
  - test_integration.py:412 becomes the `parked-only` path;
  - autonomy.test.ts:30, 55, 141 and 224.
  - test_engine.py:1324 `test_arm_again_resets_counters_and_clears_the_old_report` stops through the deadline instead of `passes='1'`; the autonomy.test.ts band assertions at 70, 178, 186, 201, 219, 271, 289 and 292 ("pass 2/5" becomes "pass 2"). Both are now spec flip rows (coordinator decision 12 after C7).
  - The regressions at 1387 (stall reset, now by signature) and 1611 stay green.
- **Acceptance:**
  - `python3.11 -m unittest discover -s tests -k test_hook_stop_ -k test_complete_skips_ledger_checks_until_all_accepted -k test_ledger_without_caps_arms -k test_2_1_ -k test_signature_changes_on_report_hold_or_gate -k test_template_carries_the_fields_and_the_fixed_lines -k test_status_has_the_documented_keys_and_never_the_lease` exits 0.
  - The file runs for test_engine.py, test_hooks.py and test_integration.py each exit 0.
  - `CLAUDE_CODE_ENABLE_FUNCTION_HOOKS=1 claude plugin test plugins/orchestra` exits 0.
- **Keep:** the deadline, completion, tamper and disarm stops; pass and stall counts reported; a present cap still validated and recorded.
- **Remove:** the `cap-passes` and `cap-stalls` stops (still readable in 2.1 reports); the template cap fields.

### W8

#### E8 [A]: pre-authorized release; the relaunch engine side
- **Goal:**
  - Add the ledger `Release:` line, stored as `autonomy.release`. While armed, `release_permit` and `check_release` are allowed only for that exact pair, and the hooks release deny skips that exact pair.
  - Add relaunch autonomy, which survives session ends. Add `settle`, `end_pass_session`, `relaunch_pass` on `start`, the close-under-relaunch `complete` stop, the hook_stop no-op without a session, and the PreToolUse armed check without a session.
- **Spec:** 5.8 item 8 (items 1 to 4; the template text was E7's), 5.10 items 1 to 4, 5.10 item 5.4 (`end_pass_session`), 5.10 item 6, 5.9 item 2 (`end_pass_session` and `settle` briefs), section 6 rows `relaunch`, `release` and `relaunch_pass`.
- **Class / preset:** Architectural; builder `sensitive` (release and boundary path).
- **Starting artifact:** design/2.2 at the W7 closing tip.
- **Owns:** engine.py, hooks.py, orchestra.py, test_engine.py, test_hooks.py, test_integration.py (fixture upkeep only).
- **Depends on:** E7 (signature, held-live stops), E6 (briefs).
- **Signatures:**
  - `parse_ledger` (spec 5.8 item 8 and spec section on the ledger, binding text): the approval boundaries hold exactly one Release line, either the fixed `- Release: no release, permit or deploy.` or one `- Release: pre-authorized <remote> <target>`, never both. Otherwise it refuses with "Approval boundaries need exactly one Release line". Add `test_arm_from_shipped_template_accepts_fixed_release_line` (arms from `config/autonomy-template.md` as shipped) and `test_ledger_with_both_release_lines_refused` (C8/P-10).
  - `arm_autonomy(self, home=None, relaunch=False)` refuses a pair unlike `policy.release` with "Release pre-authorization must match policy.release".
  - `_refuse_under_autonomy(self, state, action, remote=None, target=None)` exempts `release_permit` and `check_release` for the exact pair.
  - `_kept_autonomy` keeps a `relaunch` autonomy.
  - `_autonomy_on(state)` is true without a session when `relaunch` is armed.
  - `open_session(self, actor, harness_session=None, relaunch_pass=None)`. The CLI `start` reads `ORCHESTRA_RELAUNCH_PASS`. Without it, while `relaunch` autonomy is armed, `open_session` takes the nonce from the single `<state>/relaunch/pass-<nonce>.marker`; with none or several it stores none (spec 5.10 item 5.3).
  - `end_pass_session(self, nonce) -> dict` needs no lease and refuses unless the nonce matches. It writes the `ended` brief, keeping a stopped autonomy brief in `last_brief` (spec 5.9 item 2, C7/R4-5).
  - `settle(self) -> dict` returns `{armed, stopped, reason, signature, passes, stalls}` without counting a pass.
  - `close_session` under relaunch stops with `complete`.
  - `hook_stop` is a no-op with no session under relaunch, and returns no continuation inside a relaunch pass.
  - hooks.py: in `main` and `_raw_autonomy_active`, armed relaunch autonomy is active without a session. The release deny skips class `release` only for the exact pair.
  - CLI: `autonomy arm --relaunch`, `autonomy settle`.
- **Tests first:**
  - Release:
    - `test_arm_preauthorized_release_permits_exact_pair`
    - `test_permit_refused_under_autonomy_without_preauthorization`
    - `test_preauthorization_mismatch_refused`
    - `test_arm_refuses_malformed_release_line`
    - `test_pretooluse_preauthorized_release_reaches_permit_check`
  - Relaunch:
    - `test_relaunch_autonomy_survives_session_end`
    - `test_relaunch_autonomy_survives_interrupt`
    - `test_close_session_under_relaunch_stops_complete_with_brief`
    - `test_non_relaunch_autonomy_cleared_on_session_end`
    - `test_pretooluse_armed_without_session_under_relaunch`
    - `test_settle_stops_on_deadline_between_passes`
    - `test_end_pass_session_checks_nonce_and_writes_ended_brief`
    - `test_open_session_takes_pass_nonce_from_marker_without_env`
    - `test_settle_parked_only_when_held_and_parked`
    - `test_hook_stop_without_session_under_relaunch_is_noop`
    - `test_close_session_brief_reason_by_mode`
- **Acceptance:**
  - `python3.11 -m unittest discover -s tests -k test_arm_preauthorized_release_permits_exact_pair -k test_permit_refused_under_autonomy_without_preauthorization -k test_preauthorization_mismatch_refused -k test_arm_refuses_malformed_release_line -k test_pretooluse_preauthorized_release_reaches_permit_check -k test_relaunch_autonomy_ -k test_close_session_ -k test_non_relaunch_autonomy_cleared_on_session_end -k test_pretooluse_armed_without_session_under_relaunch -k test_settle_ -k test_end_pass_session_checks_nonce_and_writes_ended_brief -k test_open_session_takes_pass_nonce_from_marker_without_env -k test_hook_stop_without_session_under_relaunch_is_noop` exits 0.
  - The file runs for test_engine.py and test_hooks.py each exit 0.
- **Keep:**
  - in-session autonomy without `--relaunch` as in 2.1 (apart from 5.8);
  - `release-multi`, merges, pushes and deletions denied under autonomy;
  - `open_session` refusing while a session is active.
- **Remove:** none.

### W9

#### H1 [A]: the relaunch harness
- **Goal:** add `orchestra.py relaunch`, which runs fresh `claude -p` passes until a stop. It covers:
  - preconditions and exit codes;
  - nonce-bound session cleanup;
  - stall back-off with no stall exit;
  - the SIGINT disarm-then-forward order;
  - `harness.json`;
  - the shipped pass prompt.
- **Spec:** 5.10 items 5, 8 and 10, and the downstream feature map.
- **Class / preset:** Architectural; builder `implementation`.
- **Starting artifact:** design/2.2 at the W8 closing tip, plus the X1 result pasted into the brief.
- **Owns:** P/scripts/orchestra_core/relaunch.py (new), orchestra.py, P/config/relaunch-prompt.md (new), test_integration.py, test_packaging.py.
- **Depends on:** E8, and X1 for the Workflow sentence only (the pass binding uses the marker file whatever X1's env answer is).
- **Signatures:**
  - `relaunch.run(repo, state_dir, permission_mode, model=None, launcher=None, clock=time.time, sleep=time.sleep) -> int`. Exit codes per 5.10 item 10: 0, 3, 4, 5, 2, 127 or 130.
  - Pass logs go to `<state>/relaunch/pass-N.log`; state to `<state>/relaunch/harness.json` `{pass, signature, stalled_streak}`.
  - Before each launch, remove stale `<state>/relaunch/pass-*.marker` files and write `pass-<nonce>.marker`; remove it after step 4 (spec 5.10 item 5.3).
  - Back-off is `min(60 * 2 ** (streak - 1), 900)`.
  - The child starts with `start_new_session=True`.
  - CLI: `relaunch --permission-mode MODE [--model ID] [--launcher ARGV...]`. `--permission-mode` is required.
- **Prompt** (5.10 item 8):
  - read the orchestra skill;
  - `start --harness-session <id>`;
  - read `progress.md` and `status`;
  - dispatch ready cards and park at boundaries;
  - never end the turn to wait;
  - end at the context ceiling after recording state;
  - foreground Agent calls only; no background Bash.
  - Workflow sentence: if X1 answered yes, "Workflow is allowed in the foreground"; otherwise "Do not use the Workflow tool".
- **Tests first:**
  - test_integration.py (all with a `--launcher` fake and injected clock and sleep):
    - `test_relaunch_runs_passes_until_complete`
    - `test_relaunch_refuses_with_active_session`
    - `test_relaunch_requires_permission_mode`
    - `test_relaunch_backs_off_after_stall_and_never_exits_on_stalls`
    - `test_relaunch_ends_orphaned_pass_session`
    - `test_relaunch_leaves_foreign_session_and_exits_2`
    - `test_relaunch_sigint_disarms_before_forwarding`
    - `test_relaunch_pass_marker_binds_session_without_env`
  - test_packaging.py: `test_relaunch_prompt_ships_and_forbids_background_work`
- **Acceptance:**
  - `python3.11 -m unittest discover -s tests -k test_relaunch_` exits 0.
  - The file runs for test_integration.py and test_packaging.py each exit 0.
  - After committing: `D=$(mktemp -d); python3.11 scripts/build_release.py --out "$D"` exits 0, and `tar -tzf "$D"/orchestra-*.tar.gz | grep relaunch-prompt.md` finds the file (C8/P-13).
- **Keep:** in-session autonomy; the downstream feature map's named replacements.
- **Remove:** none.

#### D1: public and CLI documentation
- **Goal:** document the new CLI, the hooks behavior and the upgrade notes:
  - CLI: `hold`, `supersede`, `brief`, `finding add|list`, `gate --again`, `autonomy arm --relaunch`, `autonomy settle`, `relaunch`, `add` with `wave` and `"wave:W"`, `status` waves.
  - hooks: merged-delete, missing cwd, state busy, release pre-authorization, relaunch armed without a session.
  - README: end every 2.1 session before the first `hold` or before arming under 2.2; `orchestra.py relaunch` replaces the downstream harness.
- **Spec:** the documentation files named in 5.1, 5.2, 5.8, 5.10, 5.12 and 5.14, and section 8 (README).
- **Class / preset:** Bounded; builder `mechanical`.
- **Starting artifact:** design/2.2 at the W8 closing tip.
- **Owns:** README.md, docs/cli.md, docs/hooks.md, P/skills/orchestra/references/cli.md.
- **Depends on:** E8. H1 runs in the same wave; D1 documents H1's CLI as written in this plan, and the final review checks the two agree.
- **Tests first:** none new. This is documentation; the text is checked by the existing skill tests.
- **Acceptance:**
  - `python3.11 -m unittest discover -s tests -p 'test_skills.py'` exits 0.
  - `python3.11 -m unittest discover -s tests -p 'test_packaging.py'` exits 0.
  - cli.md stays without Sentinel or Source lines.
  - `grep -c "relaunch" README.md` is at least 1.
- **Keep:** every 2.1 command's documentation.
- **Remove:** none.

## 5. Dependency graph, readiness and pre-flight

The graph has no cycle (REASONED: every edge points to an earlier wave):
- E1 → E2 → E3 → E4 → E5 → E6 → E7 → E8 → {H1, D1}
- G1 → G2, and M1 → G2
- X1 → H1
- K1, K2 and P1x have no successors.

**Readiness:** every W1 ticket is ready at bca4e98. Each later ticket becomes ready when its predecessors in the graph above are merged and the gate after its wave has passed.

**Pre-flight** (producer → consumer):

| Producer → consumer | Produced | Consumed | Finding |
|---|---|---|---|
| E1 → E2 to E8 | `issues` in test helpers; `rev` stamp | Every later test fixture writes reports | OK once E1's migration commit lands first. Later tickets write new fixtures through the migrated helpers. Every engine ticket's acceptance includes the file runs of test_engine.py, test_hooks.py and test_integration.py. |
| E2 → E3 | the ledger and `rejected` entries | rejected-only coverage (5.1 item 6) | OK; same names. |
| E2 → E4 | `gate_receipts` and the failed-receipt rule | held-tip gate attribution (5.4 item 3) | OK; E4 adds only the uncovered-key exception. |
| E3 → E4 | `_task_findings`, tip rule, uncovered-key refusal | held states, ladder | Conflict at test_engine.py:617-639: E3 adds `task_findings`, E4 adds `hold R1`. Ruled by the spec (5.1 and 5.2 flips); sequential owners. |
| E4 → E5 | `held`, `held_finding`, repair_of forms | held-tip addressing, final repair form | OK. |
| E5 → E6 | `final_round`, `final_findings` | brief "Final rounds" and "Still failing" | Spec field names (5.5 item 4, section 6); E6's brief must read exactly these. |
| E4 → E6 | `_append_progress` | brief writers, `write_busy_brief` | OK; E6 routes every `progress.md` writer through it. |
| E6 → E7 | `_write_brief`, `last_brief`, Run brief heading | deadline stops write the brief | OK. E7 changes only stop reasons in tests E6 already re-headed. |
| E6 → E8 | `_write_brief` reasons `closed`, `interrupted`, `ended` | `end_pass_session`, close under relaunch | OK. |
| E7 → E8 | `_signature`, held-live `parked-only` rule | `settle` returns signature and reuses the stop conditions | OK. |
| E7 → E8 | template Release-line comment | `parse_ledger` Release line | The template text is E7's; the parser is E8's. E7 writes the comment from the 5.8 item 5 wording. |
| E8 → H1 | `settle`, `end_pass_session`, `arm --relaunch`, `start` env or marker read | harness loop | OK. Exit-code mapping from `settle.reason` follows 5.10 item 10. |
| X1 → H1 | Workflow and env answers | prompt sentence | If env is no, the marker fallback of spec 5.10 item 5.3 binds the pass; H1 always writes the marker, so nothing blocks. |
| G1 → G2 | `_long_prefix`, `--del` read as `--delete` (deny) | merged-delete shapes | G2 flips `--del` from deny to merged-delete. The W1 corpus rows for push `--delete` prefixes change class in W2 (named flip). |
| M1 → G2 | `delegate` from plugin root | "merged-delete is delegated" | OK; G2 adds one `test(...)` only. |
| K1, K2, P1x ↔ engine tickets | text and packaging | nothing in code | No shared files. The phrase literals are this plan's. |
| D1 ↔ H1 | docs | H1 CLI | Same wave, no shared file. The CLI names are fixed in this plan. |

## 6. Gates

Order inside each wave (settled decision 1):
1. The builders report.
2. The coordinator merges each ticket branch into design/2.2.
3. The operator runs the wave gate.
4. One wave reviewer (code-reviewer `Mode: checkpoint`) covers every ticket in the wave and cites the gate receipt (5.4 item 2, 5.11).
5. Each ticket with a blocking finding gets one builder `repair` card (Opus).
6. The repairs merge, the operator re-gates, and one repair-diff check reviews the repair diff only.
7. The next wave's base is that tip.

A spike is never merged and never reviewed in the wave.

| Wave | Gate yes/no | Scoped gate commands (each must exit 0) |
|---|---|---|
| W1 | yes | `python3.11 -m unittest discover -s tests -p 'test_engine.py'`; the same with `test_integration.py`, `test_hooks.py`, `test_guard_corpus.py`, `test_skills.py` and `test_packaging.py`; `CLAUDE_CODE_ENABLE_FUNCTION_HOOKS=1 claude plugin test plugins/orchestra`; `python3.11 plugins/orchestra/scripts/generate.py --check`; `python3 plugins/orchestra/hooks/mod/fixtures/sync.py --check`. W1 touches every test file, so this impact set covers every Python test file. It is derived from the wave, not a full-suite trigger. |
| W2 | yes | `-p 'test_engine.py'`, `-p 'test_hooks.py'`, `-p 'test_integration.py'`, `-p 'test_guard_corpus.py'`; `claude plugin test` (as above); `sync.py --check` |
| W3 | yes | `-p 'test_engine.py'`, `-p 'test_hooks.py'`, `-p 'test_integration.py'` |
| W4 | yes | `-p 'test_engine.py'`, `-p 'test_hooks.py'`, `-p 'test_integration.py'` (held cards meet the integration helpers) |
| W5 | yes | `-p 'test_engine.py'`, `-p 'test_hooks.py'`, `-p 'test_integration.py'` |
| W6 | yes | `-p 'test_engine.py'`, `-p 'test_hooks.py'`, `-p 'test_integration.py'` (brief text in integration contexts) |
| W7 | yes | `-p 'test_engine.py'`, `-p 'test_hooks.py'`, `-p 'test_integration.py'`; `claude plugin test` |
| W8 | yes | `-p 'test_engine.py'`, `-p 'test_hooks.py'`, `-p 'test_integration.py'` |
| W9 | final | the final gate below |

In this table, `-p 'X'` means `python3.11 -m unittest discover -s tests -p 'X'`.

**Final gate** (operator, on the frozen candidate after W9 merges; each command must exit 0):
- `python3.11 -m unittest discover -s tests`
- `python3.11 plugins/orchestra/scripts/generate.py --check`
- `CLAUDE_CODE_ENABLE_FUNCTION_HOOKS=1 claude plugin test plugins/orchestra`
- `python3 plugins/orchestra/hooks/mod/fixtures/sync.py --check`
- `claude plugin validate --strict plugins/orchestra`
- `claude plugin validate --strict .claude-plugin/marketplace.json`
- `python3.11 scripts/build_release.py`

`test_manifest_versions_are_equal` keeps asserting 2.1.0 until the release card changes it. The release card re-runs this gate after the version bump, because any later commit voids earlier evidence.

## 7. Reviews and live checks

- **Wave reviews:** one per wave, using code-reviewer-checkpoint on Opus medium. Each covers every ticket merged in its wave (spikes excepted), with the checkpoint lens on the architectural tickets.
- **Final review:** the three parallel lenses on the frozen candidate (settled decision 5), each over every ticket:
  - correctness, Opus high: requirements, correctness, tests and architecture;
  - security, Opus high;
  - standards, Sonnet medium: standards, cleanup and the charter.

  Out-of-scope findings are raised only here and triaged inline, card or brief (settled decision 6). Run as 2.1 lens cards if the installed engine is still 2.1 (REASONED: the build runs on the installed 2.1.0 engine).
- **Release:** the coordinator's release card (5.18: version 2.2.0, CHANGELOG with every section, the mixed-version note and the 5.16 gap if M1 did not reproduce it), outside this plan's tickets.
- **Live check L0** (X1, run by a builder in its own worktree):
  1. `D=$(mktemp -d) && cd "$D" && git init -q && git commit -q --allow-empty -m init`
  2. `ORCHESTRA_RELAUNCH_PASS=probe-123 claude -p "Use the Workflow tool to run two agents in parallel. Agent one writes the word one to a.txt. Agent two writes the word two to b.txt. Wait for both. Then run printenv ORCHESTRA_RELAUNCH_PASS > env.txt with Bash in the foreground. Then print WORKFLOW-DONE followed by both agents' results." --permission-mode bypassPermissions --output-format text > pass.log 2>&1; echo "exit $?"`
  3. `cat a.txt b.txt env.txt; grep -c WORKFLOW-DONE pass.log; claude --version`
  4. The scratch repository is disposable, so bypassPermissions is safe there; if the log still shows a tool denial, record that answer as inconclusive, never no (C8/P-11). Record Workflow = yes only if `a.txt` and `b.txt` exist and `pass.log` holds WORKFLOW-DONE with both results; no if the files are missing; inconclusive otherwise. Record env = yes if `env.txt` reads `probe-123`. Write both answers into docs/BUILD-LEDGER.md through the coordinator. The log stays in `$D`.
- **Live check L1** (a coordinator step after the W9 merge and the final gate, before release; coordinator decision 15 after C7):
  1. Install the candidate through the isolated marketplace route that docs/VALIDATION.md row 12 uses.
  2. In a scratch clone with the plugin enabled, run a session that executes `git branch -D <a merged branch>`: expect allow. Then `git branch -D <an unmerged branch>`: expect the "not merged" reason.
  3. `cd` into a directory, remove it from another shell, then ask the session to run `git worktree remove x`: expect "Session directory no longer exists: cd to an existing directory, then retry".
  4. Arm `autonomy arm --relaunch` with a ledger of one trivial card and a deadline 15 minutes ahead. Run `orchestra.py relaunch --permission-mode acceptEdits` in a terminal: expect exit 0 (`complete`) or 4 (`deadline`), and a `## Run brief` in `progress.md`.
  5. Record the results in docs/BUILD-LEDGER.md (UNKNOWN until performed).

## 8. Failure routing

| Event | Route |
|---|---|
| Builder `STATUS: BLOCKED` (a file outside ownership, a missing fake) | Coordinator. It amends ownership by moving the file into the ticket in the same wave only when no sibling owns it; otherwise it queues a follow-up ticket in the next wave. |
| Wave review blocking finding on a ticket | One builder `repair` card (Opus medium, override) against that ticket's tip, then the repair-diff check. |
| Repair-diff check still blocks | The chain is held. On the installed 2.1 engine there is no `hold`, so the coordinator emulates it: the held ticket's code stays merged in design/2.2 (no separate branch, nothing reverted), the coordinator logs it in `progress.md` (held log: ticket, finding, tip) and in the run brief, and the chain's last card stays reported. Later-wave cards carry no engine `dependencies` on earlier-wave cards (the wave base already carries the code), so nothing waits on a held chain. The held chain goes into the final lenses and the final repair rounds (spec 5.5). A cap never stops the run. |
| Wave gate fails | The reviewer attributes the failure to the responsible ticket as a blocking finding; route as above. |
| X1 Workflow inconclusive or no | H1's prompt forbids Workflow (5.10 item 9). Not a failure. |
| X1 env no | Not a failure. The pass binds through the marker file (spec 5.10 item 5.3), which H1 always writes. |
| A skill text exceeds its byte budget after compression | Not BLOCKED. The ticket raises that budget test's cap by the minimum needed (at most 15%) and records it; K1's raise is applied by the coordinator at the W1 merge (K1, K2). |
| M1 reproduces neither hypothesis | Items 2 to 5 ship as hardening; the release card's CHANGELOG records the gap (5.16 item 6). |
| Final lens blocking finding | A final repair round per spec 5.5 (Opus repair per chain, re-check, closing confirmation). |
| Final out-of-scope item | Coordinator triage: inline, card or brief. A non-builder cause goes to inline or card, never brief alone. |

## 9. Coverage

| Spec item | Ticket(s) |
|---|---|
| 5.1 items 1 to 11 (engine, CLI) | E3 (item 10 overlap rule: `test_repair_dispatch_refused_only_by_overlapping_acceptable_cards`; item 6 marker: `test_record_review_stores_repair_check_marker`) |
| 5.1 (coordination.md, checkpoint.md, cli docs) | K1, K2, D1 |
| 5.2 items 1 to 8 (engine, CLI) | E4 (item 2b marker: `test_repair_diff_check_without_repair_card_holds_rejected_only_card`) |
| 5.2 (repair-rounds.md, parallel.md:16, build repair.md, cli docs) | K1, K2, D1 |
| 5.3 | E4 (`test_completion_refuses_while_card_held`), K1 (autonomy.md:22) |
| 5.4 items 1 and 2 | K1 (coordination.md), K2 (checkpoint.md); applied in section 6 of this plan |
| 5.4 item 3 | E2 (failed-receipt rule), E4 (held tip), K2 (final.md correctness lens) |
| 5.4 item 4 | E3 |
| 5.5 lens table, models, generator, agents, AGENTS.md, docs | P1x, K2 |
| 5.5 items 1 to 9 procedure | K1 (final-review.md, triage.md, parallel.md) |
| 5.5 engine items 3 to 7 | E5 |
| 5.6 items 1 and 5 | K2 |
| 5.6 items 2 to 4 and 6 | E1 (`test_hold_refused_for_notes_only` in E4, `test_run_brief_lists_notes` in E6) |
| 5.7 items 1 and 2 (skills) | K2, K1 (final-review.md, triage.md) |
| 5.7 items 2 to 4 (engine) | E2 |
| 5.8 items 1 to 7 | E7; K1 (autonomy.md); D1 (docs/hooks.md) |
| 5.8 item 8 (Release line) | E8 (engine, hooks), E7 (template), K1 (autonomy.md, finishing.md) |
| 5.9 item 5 (single appends) | E4 (`_append_progress` for hold and gate lines), E6 (brief writers, `test_progress_writes_are_single_appends`) |
| 5.9 item 2 kept stop brief | E6 (`test_end_paths_keep_stopped_autonomy_brief`), E8 (`end_pass_session`) |
| 5.9 items 1 to 3 | E6; `end_pass_session` and `settle` briefs in E8; K1 (handoff.md, finishing.md, autonomy.md) |
| 5.9 item 4 | K1 (finishing.md), E6 (brief Needs you) |
| 5.10 items 1 to 4, 5.4 and 6 | E8 |
| 5.10 item 5.3 marker file | E8 (`test_open_session_takes_pass_nonce_from_marker_without_env`), H1 (`test_relaunch_pass_marker_binds_session_without_env`) |
| 5.10 item 5 (harness), 8, 10 | H1 |
| 5.10 item 7 | E7 |
| 5.10 item 9 | X1 → H1 |
| 5.10 docs | K1 (autonomy.md), D1 (cli.md, docs/cli.md, docs/hooks.md, README.md) |
| 5.11 items 1 and 2 | E2 |
| 5.11 item 3 and skill text | K1 (briefs.md, final-review.md), K2 (review SKILL.md, final.md, checkpoint.md, gate.md) |
| 5.12 items 1, 2 and 4 | E2 |
| 5.12 item 3 and docs | K2 (review SKILL.md), K1 (coordination.md, briefs.md), D1 (cli docs) |
| 5.13 items 1 and 3 | K1 (briefs.md), K2 (checkpoint.md, build SKILL.md) |
| 5.13 item 2 | E1 |
| 5.14 items 1 to 4 and 6, flips | G2 |
| 5.14 item 5 | E2 |
| 5.14 docs/hooks.md | D1 |
| 5.15 | G1 |
| 5.16 items 1, 2, 4 and 8 | M1 |
| 5.16 items 3 and 5 | E6 (Stop branch busy path: `test_hook_stop_busy_unarmed_writes_no_brief`, `test_hook_stop_runs_when_lock_frees_within_budget`) |
| 5.16 item 6 | Release card (CHANGELOG), fed by M1's diagnosis |
| 5.16 item 7 | G1 |
| 5.17 | E1 |
| 5.18 | Coordinator release card (out of this plan, per the brief) |
| 5.19 | Coordinator follow-up after 2.2.0 is installed (out of this plan, per the brief) |
| Section 6 schema rows | E1 (`rev`, `notes`), E2 (`findings`, `out_of_scope`, `gate_receipts`), E3 (`wave`, `superseded_by`, `task_findings`, `repair_check`), E4 (`held_finding`, `held`), E5 (`cleared`, `final_round`, `final_findings`), E6 (`last_brief`), E7 (caps optional, `signature`), E8 (`relaunch`, `release`, `relaunch_pass`) |
| Section 7 | P1x |
| Section 8 | E7 (tests), D1 (README upgrade notes) |

## 10. Gaps, risks and self-check

**Open items: none.** The coordinator decisions after C7 (spec section 10) closed every item this plan had left open; the rest below are notes and risks.

- **G-1 Byte budgets (closed, decision 10).** Builders compress first; a rule that still cannot fit raises that budget test's cap by the minimum needed (at most 15%), recorded in docs/BUILD-LEDGER.md (K1, K2, section 8). No ticket reports BLOCKED for a budget.
- **G-2 Provenance header (closed, decision 11).** standards.md carries a Sentinel line only; spec 5.5 Files now says so.
- **G-3 Lens cross-references.** correctness.md cannot name architecture.md (OBSERVED test). final.md carries the inclusion instead.
- **G-4 Spec flip-table omissions (closed, decision 12).** test_engine.py:1324 (the brief's ":1325"; the def is at 1324) and the autonomy.test.ts band assertions are spec flip rows and stay in E7.
- **G-5 Plan-defined names (closed, decision 13).** Accepted. The spec now carries `final_round`, `final_findings`, the `cleared` refusal, `StateBusy`, `lock_wait` and `write_busy_brief`; the rest stay plan-level names:
  - `final_round` and `final_findings` (E5), with their round rule;
  - the `cleared` refusal message;
  - `KEEP_REMOVE`;
  - `StateBusy`, `lock_wait` and `write_busy_brief`;
  - `_long_prefix`;
  - `_merged_delete_check`;
  - the phrase literals;
  - the standards VARIANT_NOTES text.
- **G-6 TypeScript scope.** `claude plugin test` cannot be filtered by name (OBSERVED), so the TypeScript tickets run every mod test.
- **G-7 Sequential owners.** The template, test_hooks.py and the hooks are edited by several engine tickets in different waves. Each later ticket starts from the merged tip, so there is no concurrent edit.
- **G-8 X1 (closed, decision 14).** A builder runs L0 in its own worktree with `claude -p`. The env answer no longer gates H1: the marker file of spec 5.10 item 5.3 is always written.
- **L1 live check (decided, decision 15).** A coordinator step after the W9 merge and the final gate, before release (section 7); UNKNOWN until performed.
- **G-9 Stale text found in passing** (raise at the final review, not tickets):
  - the SKILL-SOURCES "Final review lenses" row;
  - the checkpoint VARIANT_NOTES phrase "one reported ticket" (wave reviews now cover many);
  - docs/VALIDATION.md:44 "stops at its pass cap".
- **G-10 Build engine.** The build runs on the installed 2.1.0 engine, so wave-label, hold and lens features are procedure only until the release. Section 8 routes holds as parks (REASONED).
- **G-11 Nine sequential engine waves.** This is forced by the one-owner rule for engine.py and test_engine.py. Merging E3 and E4 would save a gate but exceed one fresh context (REASONED).
- **Self-check:**
  - Every 5.x item maps to a ticket or to a named coordinator card (section 9).
  - Every ticket has an owner, tests-first names (D1 and X1 excepted, with reasons), an exact command and the done contract (section 2).
  - Names agree across tickets: `_task_findings`, `hold`, `settle`, `end_pass_session`, `_signature` and `last_brief`.
  - No file has two owners in one wave (section 3).
  - No ticket exceeds one fresh context (REASONED; E3 and E8 are the largest).
