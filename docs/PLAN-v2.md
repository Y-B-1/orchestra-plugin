# Orchestra 2.0.0 plan

- Input: `docs/SPEC-v2.md`. The plan makes no product decisions. Every ticket cites SPEC sections, and a contradiction found while building goes back to design, not to builder judgment.
- Starting artifact: `feat/v2-roles-guard-mods` at `8c1f1953666cc6d5e0e81579e3b37aa2212c26f1`, plus the commit that adds this revision of SPEC-v2 and PLAN-v2.
- Policy revision: `AGENTS.md` blob `182417468e23bfa02c1afbd15bac1d031141a18e`.
- Python module paths: `plugins/orchestra/scripts/orchestra_core/{guards,hooks,engine,routing}.py`. The CLI is `plugins/orchestra/scripts/orchestra.py`.

## 0. How to read this plan

`$SCRATCH` is a fixed scratch directory outside the repository (coordinator ruling R1, round 6). It is outside the repository and independent of any session, so it survives restarts. It holds the ticket worktrees (`$SCRATCH/wt/<ticket>`), briefs, logs, live-check wizards (`$SCRATCH/wizards/`) and the L1 files (`$SCRATCH/release-notes-log.md`, `$SCRATCH/pr-body.md`, `$SCRATCH/release-notes.md`). The coordinator records it in `docs/BUILD-LEDGER.md`. Every brief and wizard that uses it sets `SCRATCH` explicitly.

### 0.1 Dispatch names during the build

The installed plugin is 1.0.1 until L1 step 1. Until then, workers are dispatched under their **v1** agent names. Each ticket gives its v2 role first and then the v1 dispatch name in brackets.

This build is not tracked in the engine (coordinator ruling FF1/FF3, round 5). The v1 engine binds evidence to the main checkout, and a CLI run from a ticket copy would recompute the contract hash; OBSERVED by the coordinator: the v1 state has 0 tasks and no session. The coordinator keeps the build ledger `docs/BUILD-LEDGER.md` instead, one row per card: card, owner, worktree path, merged commit, review verdict, acceptance. SPEC 8.5's engine reservation stays as v2 product behavior; it is not used for this build.

| v2 role/mode | v1 dispatch name |
| --- | --- |
| critic/requirements, feasibility, scope, judge | `orchestra:red-teamer` |
| critic/spec, standards, ledger | `orchestra:auditor` |
| critic/surface | `orchestra:founder-mind` (audit) |
| designer-planner/design, plan | `orchestra:designer-planner` |
| builder/implementation, frontend, sensitive, mechanical | `orchestra:builder` |
| builder/cleanup | `orchestra:builder`, v1 mode `implementation`, with a brief that states the cleanup pass (SPEC E7) |
| builder/repair (round 4) | `orchestra:builder-repair` |
| code-reviewer/checkpoint | `orchestra:code-reviewer-checkpoint` |
| code-reviewer/final, each lens | `orchestra:code-reviewer`, v1 mode `final`, with a `Lens:` line in the brief |
| investigator/docs | `orchestra:investigator` |
| investigator/code | `orchestra:investigator-code` |
| operator/gate | `orchestra:gatekeeper` |
| operator/release | `orchestra:releaser`. Executed by the coordinator, per the user's authorization (U1). |

Executor (SPEC 8.5), applied to this build:
- Two or more ready, independent cards run as one Workflow script. Each `agent()` sets `agentType` to the v1 dispatch name above, passes `effort` per 0.2, and carries the brief with its `Mode:` line and its worktree path. During this build no `agent()` sets `isolation: 'worktree'`; the coordinator creates the worktrees (0.3).
- Before the script starts, the coordinator writes a ledger row for every card it runs. After it ends, the coordinator records each agent's report in that row.
- A lone card uses one Agent dispatch. A round-4 repair card always uses the Agent tool with the `model` override.

### 0.2 Models

- Claude builders run Sonnet 5.5 medium (all presets, including cleanup), except fix round 4, which runs Opus 5.5 (SPEC E1).
- Checkpoint review runs Opus 5.5 medium. Final review lenses and critic run Opus 5.5 high. Investigator docs and operator run Sonnet 5.5 medium. Investigator code runs Sonnet 5.5 low.
- The coordinator runs on the user's picker selection.
- If a ticket runs on Codex instead, the AGENTS.md mapping applies:
  - builder and builder cleanup: `gpt-6.1-sol` medium;
  - review, critic and checked repair: `gpt-6.1-sol` high;
  - bounded discovery and hygiene: `gpt-6-luna` high.
- Model and effort stay fixed for the whole assignment.

### 0.3 Worktrees

Every builder ticket, and every card that writes a document (for example an MX repair card), gets its own git worktree on its own ticket branch. The coordinator creates it before dispatch:

```
git worktree add "$SCRATCH/wt/<ticket>" -b v2/<ticket> feat/v2-roles-guard-mods
```

The path is outside the repository, and the brief names it. Workflow agents do not use `isolation: 'worktree'` during this build. A ticket's "starting artifact" is `feat/v2-roles-guard-mods` after its prerequisites are merged.

Integration is strictly serial, one ticket at a time:
1. The ticket's builder reports PASS on its branch.
2. The coordinator merges the ticket branch into `feat/v2-roles-guard-mods` (regenerating per 0.5) and runs `--check`. On the merged commit it then reruns the ticket's acceptance test modules, each with `python3 -m unittest discover -s tests -p '<module>.py'`, plus `test_skills.py` for every S ticket. Every module must exit 0 before the checkpoint review or acceptance; a failure is repaired like a BLOCKED checkpoint (below).
3. The checkpoint reviewer (where named) reviews that merged commit, against the ticket's diff.
4. On CLEAN, the coordinator accepts the ticket and commits its ledger row with an explicit path (`git add docs/BUILD-LEDGER.md`). A ledger-only commit does not void an accepted checkpoint, because the ledger is not a ticket path.
5. Only then does the next merge happen.

A BLOCKED checkpoint is repaired under SPEC E1 from a new worktree at the merged HEAD. The repair is merged and re-reviewed before any other merge. The coordinator removes each worktree after inspecting its directory, once its branch is merged and accepted.

A document-writing card commits only its owned path, with an explicit `git add <path>`. One-time exception: MX was dispatched before this rule and runs in the main checkout under its current brief. Its explicit-path commit lands directly on `feat/v2-roles-guard-mods` and counts as its merge (step 2), at its position in the serial order; MXR then reviews that commit. MX's path is disjoint from every ticket, so a coordinator merge may come before it, but the coordinator never starts a merge while MX is committing (an `index.lock` failure is retried, never forced). Any later document-writing card uses a worktree and the serial merge above.

### 0.4 Rules to restate verbatim in every brief

- Python 3.11+ stdlib only.
- Never hand-edit generated files (`plugins/*/agents/*.md`, `plugins/*/profiles/codex/*.toml`, `plugins/orchestra-codex/**`). Regenerate with `python3 plugins/orchestra/scripts/generate.py` and check with `--check`.
- Never put private audit snapshots, credentials or personal absolute paths in the repo. Refer to the audit by finding ID only. Write `~`, `$REPO` or `<repo>` for paths.
- Commit with explicit paths only (`git add <path>`). Never `git add -A` or `git add .`, never `git stash`, never force push, never `reset --hard`.
- Codex models only `gpt-6.1-sol` and `gpt-6-luna`; Claude models only `claude-opus-5-5` and `claude-sonnet-5-5`.
- You are not alone. Preserve sibling edits. Never delegate, change coordinator state, reserve other work, or release.
- `Mode: <mode>` line, and for final review a `Lens: <lens>` line (SPEC 8.1).
- Report shape: `STATUS: PASS|ISSUES|BLOCKED`, `ARTIFACT: <full sha> <dirty fingerprint>`, changed paths, commands with exit codes and log paths, findings, uncertainties.

### 0.5 Shared generated resource

Every ticket that changes `plugins/orchestra/**` also changes the generated mirror `plugins/orchestra-codex/**`. Tickets that change `config/roles.json`, `config/models.json`, `generate.py` or skills also change `agents/` and `profiles/`.

- No ticket owns generated files. Each ticket regenerates inside its own worktree, so that its checks pass, and commits the regenerated output.
- At each merge the coordinator resolves any conflict in a generated path by accepting either side and rerunning `python3 plugins/orchestra/scripts/generate.py`. Generated output is never merged by hand.
- `--check` must exit 0 after every merge.

### 0.6 Live checks

Interactive checks are human steps. The coordinator writes a bash wizard script in `$SCRATCH/wizards/` (0), and the user runs it. Every live-check wizard that loads the worktree with `claude --plugin-dir <worktree>/plugins/orchestra`:

- runs `claude plugin disable orchestra@orchestra-distribution` first, with a `trap` that runs `claude plugin enable orchestra@orchestra-distribution` on exit;
- asserts exactly one Orchestra SessionStart context in the session (proof that v1 is not loaded beside v2);
- exports `CLAUDE_CODE_ENABLE_FUNCTION_HOOKS=1` for any `claude -p` step;
- prints the observed result, which the coordinator records in `docs/BUILD-LEDGER.md` during INT;
- starts any engine run it needs in a scratch repository outside `$REPO`, never in the main checkout (this build is not tracked in the engine, 0.1).

## 1. Tickets

The common check is:

```
python3 plugins/orchestra/scripts/generate.py --check
```

Unit test modules run one at a time with:

```
python3 -m unittest discover -s tests -p '<module>.py'
```

`tests/` has no `__init__.py` (OBSERVED), so `discover -p` is the supported form. Every ticket's acceptance includes `--check` exiting 0. A ticket is accepted only after its acceptance test modules pass on the merged commit and its checkpoint review (where named) is CLEAN on that commit (0.3).

### P0: confirmation red team of this revision

| Field | Value |
| --- | --- |
| Role | critic/feasibility and critic/scope [v1 `orchestra:red-teamer`], two independent cards; a critic/judge card only if they disagree |
| Starting artifact | The commit that adds this revision |
| Owned | Nothing. Read-only. Report returned as the final message. |
| Deps | None |
| Acceptance | Each report is PASS, or ISSUES with findings mapped to SPEC/PLAN sections. The designer-planner repairs findings; product contradictions go to the user. |

### I1: platform facts (accepted)

Done. Recorded as `docs/RESEARCH-v2.md` Q1 to Q6. The coordinator's round 3 probe (SPEC 3.3) closes the Q1 runtime gap.

### I2: upstream skill sources at pinned SHAs (read-only, parallel with P0)

| Field | Value |
| --- | --- |
| Role | investigator/docs [v1 `orchestra:investigator`], Sonnet 5.5 medium |
| Owned | Nothing. Report returned as the final message. The coordinator records the SHAs and the mapping table in `docs/RESEARCH-v2.md`. |
| Deps | None |

Scope, per source: repository URL, path, 40-character commit SHA, license file text at that SHA (MIT confirmed or not), byte size, and an adopt list and an avoid list against SPEC 8.2.

Sources:
- obra/superpowers: brainstorming, writing-plans, executing-plans, subagent-driven-development, dispatching-parallel-agents, using-git-worktrees, finishing-a-development-branch, systematic-debugging, test-driven-development, verification-before-completion, requesting-code-review (with its reviewer prompt), receiving-code-review, writing-skills, using-superpowers (avoid list only).
- mattpocock/skills: `skills/engineering/` improve-codebase-architecture, codebase-design, domain-modeling, code-review, tdd, implement, diagnosing-bugs, grill-with-docs, to-spec, to-tickets, prototype, triage, handoff, retro, writing-for-agents; `skills/productivity/grill-me`; the GLOSSARY/ADR templates.
- garrytan/gstack: `cso`, `deslop-shared-libs`, `health`, the diff-scope specialist rules; the preamble, telemetry and persona parts named for the avoid list.
- Spec-kit (assess gate) and BMAD (lenses): license at a pinned SHA, or "idea level only".
- Claude Code built-in `security-review` and `simplify`: license status. If none is published, record "idea level only, own words".

Acceptance: every source has a SHA and a license verdict, or is marked UNKNOWN with the reason. A path that does not exist at the SHA is reported, not guessed.

### MX: capability matrix (selection before authoring)

| Field | Value |
| --- | --- |
| Goal | SPEC 8.4: the capability matrix in `docs/SKILL-SOURCES.md`, a synthesis per capability built from I2's texts at their pinned SHAs. |
| Role | designer-planner/plan [v1 `orchestra:designer-planner`], Opus 5.5 high |
| Deps | I2 (and its RESEARCH-v2 entry by the coordinator) |
| Owned | New: `docs/SKILL-SOURCES.md` |

Scope:
- Input: the pinned upstream texts at the path outside the repository that the coordinator names in the brief (SPEC 8.4), and the existing Orchestra skill files. Nothing from memory or another revision.
- One row per SPEC 8.4 capability, with columns for Superpowers, Pocock, gstack, and "Existing Orchestra / other" (the current Orchestra skill files; Spec-kit and BMAD, MIT at their pinned SHAs; the Claude built-ins, idea level). Each cell is a path at the pinned SHA, or "none".
- Per row: Base (Superpowers, or the best-fitting source when Superpowers has none); Merged in from others (each stronger or more thorough element, its source and why); Gaps filled; Synthesis notes; Rejected (only conflicts with Orchestra, or adds nothing, each with a one-line reason); Destination skill file(s).
- This is a synthesis, not a contest: no row names a winner. Upstream skills that map to no row are listed under "Not used" with a reason.
- License limits of SPEC 8.2 are marked per base and per merged element (MIT text or idea level).
- The gstack `cso` verdict is recorded on the security-review row (O11).

Acceptance:
- `grep -c "^| " docs/SKILL-SOURCES.md` shows at least the 17 capability rows plus header rows.
- For each SPEC 8.4 capability, `grep -n -i "<capability>" docs/SKILL-SOURCES.md` prints its row.
- Every SHA cited appears in the RESEARCH-v2 I2 table.
- No upstream text longer than one line is copied into the matrix.
- Every file in the SPEC 8.2 table appears as a destination: for each, `grep -c "<file path>" docs/SKILL-SOURCES.md` prints at least 1.
- `grep -n -i "winner" docs/SKILL-SOURCES.md` prints nothing.

### MXR: matrix critic

| Field | Value |
| --- | --- |
| Role | critic/spec [v1 `orchestra:auditor`], read-only, report returned as the final message |
| Deps | MX |
| Owned | Nothing |
| Acceptance | PASS against SPEC 8.4: every row present; each base follows the base rule (Superpowers unless it has no candidate); each merged element names its source and why it is stronger; every rejection is a conflict with Orchestra or adds nothing, with a reason; no silent drops; destinations cover every file in SPEC 8.2; license marks match I2. The brief names the pinned-text path, so the critic checks the cited paths. ISSUES route to an MX repair card, then a fresh MXR. |

### B1: thin end-to-end slice (version, mod skeleton, package exclusion)

| Field | Value |
| --- | --- |
| Goal | Prove the pipe: 2.0.0 manifests; a mod module that loads next to the classic hooks from one plugin; the API presence check; the Codex package excludes mod files. SPEC B-F3, 10.1, 10.2 and the marker part of 10.3. |
| Role | builder/implementation [v1 `orchestra:builder`] |
| Deps | P0 |
| Checkpoint | R1, code-reviewer/checkpoint |

Owned paths:
- The five version manifests (SPEC B-F3), apart from the generated `plugins/orchestra-codex/.codex-plugin/plugin.json`.
- `plugins/orchestra/.claude-plugin/plugin.json`: the hooks array and `types`.
- New: `plugins/orchestra/hooks/mods.json`, `plugins/orchestra/hooks/mod/orchestra.ts`, `plugins/orchestra/hooks/mod/marker.ts`, `plugins/orchestra/types/index.d.ts`.
- `plugins/orchestra/scripts/generate.py`: the `codex_package` exclusion of `hooks/mods.json`, `hooks/mod/` and `types/` only.
- `tests/test_packaging.py`: the version-equality test and the exclusion test only.

Mod skeleton scope:
- `session.start` runs the API presence check (SPEC 10.2). If the core APIs exist, it writes the marker with `rules_sha256: null` and heartbeats every 5 s, re-reading `$.session.id()` each tick.
- `session.end` only retires the heartbeat (`heartbeat_ms: 0`). (B1 scope; B5 replaces this with the SPEC 10.3 lifecycle.)
- No guard yet. A null `rules_sha256` never matches, so Python keeps guarding.

Acceptance:
- `python3 -m unittest discover -s tests -p 'test_packaging.py'` exits 0.
- `claude plugin validate plugins/orchestra` exits 0 on Claude Code 2.1.289 and lists `session.start` and `session.end`.
- `python3 scripts/build_release.py --out "$SCRATCH/b1"` on the committed candidate exits 0.
- Live (0.6): the SessionStart Orchestra context appears once; the marker appears and `heartbeat_ms` advances over 10 s or more; after `/exit`, `heartbeat_ms` is 0. Whether the validator accepted the `typeof` check, or the fallback was used, is recorded.
- The same under `claude -p` with the env switch, outcome recorded.

### B2: guard fixes, shared rules table and corpus

| Field | Value |
| --- | --- |
| Goal | SPEC A1 to A10, A12 to A15, 5.1 and B-F4, in Python. Creates the shared rules table and the corpus with the fixed class vocabulary. A15 resolves run state for a linked worktree from the main worktree. |
| Role | builder/sensitive [v1 `orchestra:builder`] |
| Deps | B1 |
| Checkpoint | R2, code-reviewer/checkpoint, on the diff plus the corpus |

Owned paths:
- `plugins/orchestra/scripts/orchestra_core/guards.py`
- `plugins/orchestra/scripts/orchestra_core/hooks.py`: PreToolUse, the class-to-decision mapping for unarmed and armed runs (autonomy columns come in B10), the unloadable-state rule in `main()`, the A15 state resolution for linked worktrees, `_protected` (B-F4, A8, the marker directory), the marker check, `--from-mod`
- `plugins/orchestra/scripts/run-hook.sh` (A10, including `--cli`)
- `plugins/orchestra/hooks/claude.json`: PreToolUse matcher only
- New: `plugins/orchestra/config/guard-rules.json`, `plugins/orchestra/config/guard-corpus.json`
- `tests/test_hooks.py`
- New: `tests/test_guard_corpus.py`
- `tests/test_integration.py`: the A15 linked-worktree test only

Acceptance:
- `test_hooks.py`, `test_guard_corpus.py` and `test_integration.py` exit 0.
- A15 (SPEC 5 acceptance): on a temporary repository with `git worktree add`, a push from the linked worktree without a permit denies while the main checkout is armed and allows while it is unarmed; a bare common directory stays unarmed. The linked-worktree command strings are corpus cases with their state-independent class.
- Every A-row test listed in SPEC 5 acceptance exists, including: `test_release_unconfigured` flipped (unarmed push allowed); armed push without a permit denied; unloadable state denies release; unarmed `gh pr merge N --squash --delete-branch` and `gh release create` allowed; an Edit to the marker directory denied.
- B-F4: the regression test uses `.claude/hooks.json` under a cwd of `<tmp>/.claude/plugins/x`.
- The corpus uses only the five SPEC 5.1 classes, and contains every command string in the existing `test_hooks.py` deny and allow tests plus the A14 boundary cases.
- `bash -n plugins/orchestra/scripts/run-hook.sh` exits 0.
- Latency evidence (10 runs before and after) is recorded.

Repair card B2-r2 (D4, R2b, D4-RT): owned paths `plugins/orchestra/scripts/orchestra_core/guards.py`, `plugins/orchestra/config/guard-rules.json` (the `wrappers` table, new runner entries and their `_doc` strings), `plugins/orchestra/config/guard-corpus.json` (append only, except where a SPEC rule flips an expectation, which the report names), `tests/test_guard_corpus.py`, `tests/test_hooks.py` (guard tests only), plus generated Codex copies. Scope: A5 rule (6) with every SPEC deny and allow case, implemented with a quote-aware pre-pass in `classify_command` before segmentation where `_split` would cut a producer from its consumer; the 16 `test_a2_always_deny_rules_remain` loop commands (10 missing), the 5 concatenated commands (`f1_deny2` and the four in the quote-blind test) and the refspec loop commands appended to the corpus; the coverage walker extended to local names bound in the same function to a literal, a literal concatenation or a list of them, to tuple-unpacking loops whose target is concatenated with literals, and to loop variables that reach any walker sink (`classify_command`, `bash`, `command=`, payload `command`). Acceptance: `python3 -m unittest discover -s tests -p '<module>.py'` exits 0 for `test_hooks.py`, `test_guard_corpus.py` and `test_integration.py`; `--check` exits 0; the walker test gains a case per new shape and asserts it finds all 16 loop commands and the 5 concatenated commands in `tests/test_hooks.py`; `$SCRATCH/logs/B2-r2-probe.log` shows each rule (6) deny case denying and each allow case allowing.

### B4: role consolidation and skill skeleton (schema foundation)

| Field | Value |
| --- | --- |
| Goal | SPEC 7 and 8.1, mechanically: 7 roles with builder `cleanup`; `dispatch: override`; orchestrator `selection: user` (U7); read-only `disallowedTools` and Codex `sandbox_mode`; the skill directories with two-skill preload; one mode file per mode; the generate-time resolution checks; the engine `Mode:` brief check; engine role keys and contract root. Content is moved and renamed, not rewritten. |
| Role | builder/implementation [v1 `orchestra:builder`] |
| Deps | B1, I1. Runs in parallel with B2 in a separate worktree. |
| Checkpoint | R4, code-reviewer/checkpoint |

Owned paths:
- `plugins/orchestra/config/roles.json` (7 roles, `skill` field, builder `cleanup`, methods per SPEC 7.2)
- `plugins/orchestra/config/models.json` (builder `cleanup` preset; `claude.orchestrator` `{"selection": "user"}`)
- `plugins/orchestra/scripts/generate.py`: `skills:` bare names (two per worker, `orchestra` for the orchestrator); no `model:`/`effort:` for `selection: user`; `sandbox_mode = "read-only"` on investigator, critic and code-reviewer profiles and their variants; refusal on unresolved skill names, `disable-model-invocation: true`, or a missing mode file. B1's exclusion edit stays.
- `plugins/orchestra/scripts/orchestra_core/engine.py`: `_contracts` root `skills/`; role keys (`releaser` to `operator`/release, `auditor`/`red-teamer` to `critic`); `add_task` `Mode:` line check for cards with a brief file.
- `plugins/orchestra/skills/**`: create `orchestra-worker/` and the six role skills, each with `SKILL.md` and `references/<mode>.md` for every declared mode, plus the review lens files and `specialists.md`. Move the existing method text into them. Each file carries a one-line sentinel the live check can quote, after the frontmatter and any `Source:` header. Each file that a later S ticket rewrites also carries a line starting `Stub:`; the S ticket removes it. Keep `orchestra/` with `coordination.md`, `cli.md` and `briefs.md`; move the worker contract out of `briefs.md` into `orchestra-worker/SKILL.md`. Create every file named in the SPEC 8.2 table that does not yet exist as a stub with its sentinel and a `Stub:` line, including `orchestra/references/triage.md`, `handoff.md`, `parallel.md`, `worktrees.md`, `finishing.md`, `repair-rounds.md`, `final-review.md`, `audit-axes.md` and `autonomy.md`. B4 leaves `orchestra/references/cli.md` unchanged: it is Orchestra text only, owned by B8 and B7, and gets no `Stub:` line (SPEC 8.4).
- `tests/test_engine.py`: role names and the `Mode:` check only
- `tests/test_packaging.py`: role matrix, `sandbox_mode`, orchestrator without `model:`/`effort:`, the generate refusal test, and the two-sentinel test for every Codex worker profile (SPEC 8.3) only
- New: `tests/test_skills.py` (SPEC 8.3 acceptance list, apart from the provenance tests that S0 adds)
- New: `tests/skill_phrases/<dir>.json` for each of the 8 skill directories, seeded with the sentinels

Acceptance:
- `test_engine.py`, `test_packaging.py`, `test_routing.py`, `test_integration.py` and `test_skills.py` exit 0.
- `--check` exits 0 and reports 19 native profiles.
- `ls plugins/orchestra/agents` and `ls plugins/orchestra/profiles/codex` match SPEC 7.1 acceptance exactly.
- A `test_skills.py` test lists every file of the SPEC 8.2 table and asserts that each exists, and that each file except `orchestra/references/cli.md` carries its sentinel; every file a later S ticket rewrites carries a `Stub:` line.
- `grep -rn "Read references/\|Read SKILL.md" plugins/orchestra/agents` prints nothing.
- `cat plugins/orchestra/agents/*.md | wc -c` prints a number under 32000.
- `grep -n "^model:\|^effort:" plugins/orchestra/agents/orchestrator.md` prints nothing.
- `test_packaging.py` asserts that every generated Codex worker profile's `developer_instructions` contains the `orchestra-worker` sentinel and its role skill sentinel.
- `grep -rn "founder-mind\|red-teamer\|auditor\|gatekeeper\|janitor\|releaser\|builder-repair" plugins/orchestra/config plugins/orchestra/scripts` prints nothing, apart from deliberate legacy-mapping text.
- Live (0.6):
  - `orchestra:orchestrator` is the main agent, and the main session reports the picker's model; switching the picker changes it;
  - a dispatched `orchestra:builder` with `Mode: repair` quotes both preloaded sentinels without a Read or Skill call, then reads `orchestra-build/references/repair.md` and quotes its sentinel;
  - `claude --debug` shows no skill-skip warning;
  - a dispatched `orchestra:critic` is refused the Write tool;
  - an Agent call with `model: claude-opus-5-5` runs `builder` on Opus;
  - a Workflow `agent()` with `agentType: 'orchestra:builder'` and `Mode: repair` quotes both preload sentinels and the `repair.md` sentinel (SPEC 8.5; repeated at L1 restart point B).

### B3: lease release on session end (F5), SubagentStart, CLI additions

| Field | Value |
| --- | --- |
| Goal | SPEC B-F5 and A11: harness-session binding, classic SessionEnd with the O6 reason policy and a 10 s timeout, the SessionStart session-id line, SubagentStart worker context only for `orchestra:` agents, and `start --harness-session` and `where`. |
| Role | builder/sensitive [v1 `orchestra:builder`] |
| Deps | B2, B4 |
| Checkpoint | R3, code-reviewer/checkpoint |

Owned paths:
- `plugins/orchestra/scripts/orchestra_core/engine.py`: optional `harness_session`, `end_harness_session`, `mark_harness_rebind`, `apply_harness_rebind`
- `plugins/orchestra/scripts/orchestra.py`: `start --harness-session`, `where`
- `plugins/orchestra/scripts/orchestra_core/hooks.py`: SessionStart line and rebind, SessionEnd, SubagentStart (A11)
- `plugins/orchestra/hooks/claude.json`: SessionEnd entry with `"timeout": 10`
- `tests/test_engine.py`, `tests/test_hooks.py` (including the `test_session_context_only` update), `tests/test_integration.py`

Acceptance:
- `test_engine.py`, `test_hooks.py` and `test_integration.py` exit 0.
- Integration: start with `--harness-session S`; SessionEnd with S and reason `prompt_input_exit`; `start --new-run` exits 0.
- Further tests: reason `clear` and reason `resume` leave the run armed; another id leaves it armed; a run without a harness session is untouched; a repeated SessionEnd is idempotent; SubagentStart for a non-`orchestra:` agent returns `{}`.
- Rebind tests (SPEC B-F5): SessionEnd `clear` with S, then SessionStart `clear` with S2, binds S2, and SessionEnd `prompt_input_exit` with S2 then releases and `start --new-run` exits 0 (integration); the same for `resume`; SessionStart `startup` with S2 after SessionEnd `clear` does not rebind; a `pending_rebind` older than 60 s does not rebind and is removed; SessionEnd `resume` with S then SessionStart `fork` with S2 rebinds; SessionStart `compact` after SessionEnd `clear` does not rebind; a Codex SessionStart `resume` does not rebind; a negative-age `pending_rebind` is stale; after a rebind, SessionEnd `prompt_input_exit` with the old id does not release; a second SessionStart `clear` does not rebind again; a release removes `pending_rebind` and keeps `harness_session`; SessionEnd `clear` with another id records nothing; a rebind error (unloadable state) still returns the SessionStart context. Rebind tests inject the clock.
- `where` output has no `lease` key (test).
- Live (0.6): the SessionEnd latency over 10 runs is recorded; the `session_id` before and after `/clear`, `/resume` and `/branch` is recorded, with the SessionEnd `reason`, the `source` of the SessionStart that follows each and the gap between the two hooks, and `status` shows the rebound `harness_session`; start a run, `/exit`, then `status` in a new shell shows `session.active: false`.

### B8: engine trim and U3a

| Field | Value |
| --- | --- |
| Goal | SPEC 11.1 and 11.2: remove `route`, `audit-policy`, `review-groups` and `routing.py`; remove the two policy keys; contract hash over the role/mode map only; policy-narrowable categories; lease-free `status`; `interrupt_active` for the Interrupt hook. |
| Role | builder/sensitive [v1 `orchestra:builder`] |
| Deps | B3 |
| Checkpoint | R8, code-reviewer/checkpoint |

Owned paths:
- `plugins/orchestra/scripts/orchestra_core/engine.py`: contract hash, categories, status redaction, `interrupt_active`
- `plugins/orchestra/scripts/orchestra.py`: remove the three subcommands and the routing import
- Delete: `plugins/orchestra/scripts/orchestra_core/routing.py`, `tests/test_routing.py`
- `plugins/orchestra/config/policy.default.json`
- `plugins/orchestra/scripts/orchestra_core/hooks.py`: Interrupt path only
- `tests/test_engine.py` (including `test_method_missing_and_changed_contract_invalidates_run`), `tests/test_integration.py` (the `review-groups` call), `tests/test_hooks.py` (Interrupt)
- `plugins/orchestra/skills/orchestra/references/cli.md`: remove the trimmed commands only
- `README.md`: remove the trimmed command line only

Acceptance:
- `test_engine.py`, `test_hooks.py` and `test_integration.py` exit 0.
- Every SPEC 11.1 and 11.2 test listed in SPEC 11 acceptance exists.
- `ls plugins/orchestra/scripts/orchestra_core/routing.py tests/test_routing.py` exits non-zero.
- `python3 plugins/orchestra/scripts/orchestra.py route`, `... audit-policy` and `... review-groups` each exit non-zero.
- `grep -n "reserved_ports\|denied_tools" plugins/orchestra/config/policy.default.json` prints nothing.
- `grep -rn "review-groups\|audit-policy\|orchestra.py route" README.md plugins/orchestra/skills/orchestra/references/cli.md` prints nothing.

### B9: evidence bound to owned paths plus HEAD (U3b)

| Field | Value |
| --- | --- |
| Goal | SPEC 11.3: `artifact(scope)`, scoped `report_artifact` and non-final review receipts with stored scope, whole-repo final evidence, `artifact --tasks`. |
| Role | builder/sensitive [v1 `orchestra:builder`] |
| Deps | B8 |
| Checkpoint | R9, code-reviewer/checkpoint |

Owned paths:
- `plugins/orchestra/scripts/orchestra_core/engine.py`
- `plugins/orchestra/scripts/orchestra.py`: `artifact --tasks`
- `tests/test_engine.py`, `tests/test_integration.py`

Acceptance:
- `test_engine.py` and `test_integration.py` exit 0.
- Tests: an edit outside the scope keeps a scoped verdict current; an edit inside stales it; a new commit stales it; a final review still binds the whole repo; a task with no reserved files gets the whole-repo artifact; `artifact --tasks` output is accepted by `review`.

### B10: autonomous overnight mode, engine and hooks (U8)

| Field | Value |
| --- | --- |
| Goal | SPEC 12.1 to 12.6: `autonomy arm|disarm|status`, the ledger template and parser, the loop and stop reasons, parking, boundary denial in PreToolUse, release refusal while active, the morning report and its SessionStart display, the preconditions report. |
| Role | builder/sensitive [v1 `orchestra:builder`] |
| Deps | B9 |
| Checkpoint | R10, code-reviewer/checkpoint |

Owned paths:
- `plugins/orchestra/scripts/orchestra_core/engine.py`: autonomy, `hook_stop`, progress measure, `park`/`unpark`, `parked` state, report
- `plugins/orchestra/scripts/orchestra.py`: `autonomy arm|disarm|status`, `park`, `unpark`
- `plugins/orchestra/scripts/orchestra_core/hooks.py`: Stop, the autonomy columns of the PreToolUse mapping (including the default-branch merge rule), applied to the state that A15 resolves; SessionStart report display, read-only engine load for SessionStart in `main()`
- New: `plugins/orchestra/config/autonomy-template.md`
- `tests/test_engine.py`, `tests/test_hooks.py`, `tests/test_integration.py`

Acceptance:
- `test_engine.py`, `test_hooks.py` and `test_integration.py` exit 0.
- Every test listed in SPEC 12 acceptance exists: caps, deadline, completion, parked-only, tampered ledger, boundary park, release refusal while active, Stop continue and Stop stop, boundary denial while active and allow while autonomy is off, the default-branch merge rule, push and `rm` denial in a linked worktree of the armed repository (A15), the linked-worktree merge test (SPEC 12 acceptance: the branch is read from the payload `cwd`'s worktree), SessionStart report.
- Confirm point: before acceptance, the coordinator confirms the SPEC O12 defaults (park and continue; `parked-only`; local merges on non-default branches; every push denied while active) with the user, or records that the defaults apply because the user did not override.
- Live (0.6): a two-card run, `autonomy arm` with `max_passes: 1`; one Stop continues into the next card; the next Stop stops with `cap-passes`; the next SessionStart shows the report. The `permission_mode` line printed by `arm` is recorded against the session's actual mode.

### B5: mods module (full)

| Field | Value |
| --- | --- |
| Goal | SPEC 10.3 to 10.5: the TypeScript classifier over `guard-rules.json`, the `tool.call` guard with fail-closed `.catch` and Python delegation for `release`, `release-multi` and `boundary`, the marker `rules_sha256`, `agent.offer`, `agent.spawn` standing orders, `/orchestra-board`, verdict toasts. |
| Role | builder/implementation [v1 `orchestra:builder`] |
| Deps | B2, B3, B4, B8, I1. B8 is needed because the board renders `orchestra.py status`, which is lease-free only after B8 (SPEC 10.5, 11.2). |
| Checkpoint | R5, code-reviewer/checkpoint, on guard parity and fail-closed paths |

Owned paths:
- `plugins/orchestra/hooks/mod/**`, except `autonomy.ts` and `autonomy.test.ts`
- `plugins/orchestra/types/index.d.ts`
- `plugins/orchestra/config/guard-corpus.json`: append only. New cases must pass `test_guard_corpus.py`. Changing an existing expectation is a B2 repair.
- B5 reads the matching rule of each table key from the table's `_doc` object, and covers the A8 and A12 edit cases with TypeScript tests (SPEC 10.3, D3). The TypeScript classifier lives in `hooks/mod/guard.ts`. The marker's `rules_sha256` becomes the SPEC 10.3 guard digest over the four files, computed in TypeScript; a `claude plugin test` case checks it equals the Python digest for the same root (D3-r1). B5 checks that `$.fs.read` reads `.py` files; if not, return to design.

Acceptance:
- `claude plugin validate plugins/orchestra` (2.1.289) exits 0 and lists the six events of SPEC 10.
- `CLAUDE_CODE_ENABLE_FUNCTION_HOOKS=1 claude plugin test plugins/orchestra` exits 0, including corpus parity over every case.
- `test_guard_corpus.py` and `test_hooks.py` exit 0.
- Marker lifecycle (SPEC 10.3, from the B1 checkpoint review), each case covered in `claude plugin test` with the mock clock: `session.end` with reason `clear` and with reason `resume` retires the old id and the next tick writes the new id; each of `prompt_input_exit`, `logout` and `other` cancels the tick; a second `session.start` leaves exactly one tick; `/clear` then a return to the first id gives the first id fresh markers again; a fresh write held in flight (a test `on` hook for `fs.write` that answers late) when `session.end` runs ends with `heartbeat_ms: 0` as the last recorded write; the same with `clock.now` or `session.id` held late instead; `/clear`, then `session.start` under the first id, writes fresh markers for that id; a rejected write does not skip the next queued write; a throwing tick writes nothing; no `XDG_STATE_HOME` and no `HOME` writes no marker.
- Live: record whether `session.start` fires after an in-process `/resume`, and whether `/resume` reuses the original id.
- Live (0.6): the SPEC 10 live list, each item recorded, with a screenshot of `/orchestra-board`. A scratch copy with an invalid rules file leaves Python guarding: `git stash` is still denied.

### B11: autonomy mod surface

| Field | Value |
| --- | --- |
| Goal | SPEC 12.7: `/orchestra-autonomy on|off|status`, the stop toast, the status band (API name from the tested build's types; skipped if absent). |
| Role | builder/implementation [v1 `orchestra:builder`] |
| Deps | B5, B10 |

Owned paths:
- New: `plugins/orchestra/hooks/mod/autonomy.ts`, `plugins/orchestra/hooks/mod/autonomy.test.ts`
- `plugins/orchestra/hooks/mod/orchestra.ts`: the registration lines only
- `plugins/orchestra/types/index.d.ts`, only if a type is needed

Acceptance:
- `CLAUDE_CODE_ENABLE_FUNCTION_HOOKS=1 claude plugin test plugins/orchestra` exits 0 with `autonomy.test.ts` included.
- `claude plugin validate plugins/orchestra` exits 0.
- Live (0.6): `/orchestra-autonomy on` with no ledger shows the template path; `status` renders; `off` disarms; the band appears while active, or its absence is recorded with the reason.

### S0: third-party notices and provenance tests

| Field | Value |
| --- | --- |
| Goal | SPEC 8.2 licensing and 8.3 provenance: `THIRD-PARTY-NOTICES` with the MIT texts and SHAs of the sources the accepted matrix cites and the idea-level credits; the provenance tests in `tests/test_skills.py`; the header-or-`Stub:` test rule; the lens-scoped code-reviewer sentence in `roles.json` (SPEC E7). |
| Role | builder/mechanical [v1 `orchestra:builder`] |
| Deps | B4, I2, MXR |

Owned paths:
- New: `plugins/orchestra/THIRD-PARTY-NOTICES`.
- `tests/test_skills.py`: the provenance tests only. They parse every `Source:` header under the SPEC 8.2 grammar; check that every SHA and every idea-level name in a header is credited in the notices; and check that every destination file named in `docs/SKILL-SOURCES.md` by a row with an upstream or idea-level source carries a header or a `Stub:` line. `orchestra/references/cli.md` is Orchestra text only and exempt: the provenance test skips it even when a row names it (SPEC 8.4). S0 also replaces the B4 assertion that requires a `Stub:` line in every skill file (`test_sentinel_and_stub_lines`) with the SPEC 8.3 header-or-`Stub:` rule, and re-anchors `test_worker_contract_phrases_do_not_repeat_in_role_skills` on the `Sentinel:` line instead of the `Stub:` split, keeping its assertion that no phrase of `orchestra-worker/SKILL.md` appears in a role skill (SPEC 8.3). S1 to S7 can then remove their `Stub:` lines (D3, R4 F1; D3-r1, red team F6).
- `plugins/orchestra/config/roles.json`: the code-reviewer prompt sentence only. "Final mode always covers all categories" becomes: final mode covers the categories of the lens its `Lens:` line names, and the four lens cards together cover every category (SPEC E7). Regenerate and commit the generated files (D3, R4 F2).

Acceptance:
- Every SHA and every idea-level name cited in `docs/SKILL-SOURCES.md` appears in the notices file, with its license text when the source is MIT at that SHA.
- `python3 -m unittest discover -s tests -p 'test_skills.py'` exits 0 on the B4 stubs, and still exits 0 in a scratch copy where `orchestra-worker/SKILL.md` and one other sourced skill file each get a valid `Source:` header and lose their `Stub:` line.
- `grep -n "always covers all categories" plugins/orchestra/config/roles.json plugins/orchestra/agents/code-reviewer*.md` prints nothing.
- `python3 scripts/build_release.py --out "$SCRATCH/s0"` on the committed candidate exits 0.
- `--check` exits 0 and the Codex package contains `THIRD-PARTY-NOTICES`.

### S1 to S7: skill content (parallel, one ticket per skill directory)

Common fields:

| Field | Value |
| --- | --- |
| Goal | Write the skill as Orchestra's own text from the accepted matrix rows whose destination is in the ticket's directory (SPEC 8.4): each row's base, merged elements and gap text, worked from the pinned upstream texts at the path the coordinator names in the brief. No concatenation, one voice, no rule repeated across files, E1 to E7 placed per SPEC 9, the SPEC 8.2 `Source:` header on every file a cited row names, the sentinel line kept unchanged, every `Stub:` line removed, and the avoid list honored. |
| Role | builder/mechanical [v1 `orchestra:builder`] |
| Deps | B4, S0, MXR (I2 through MX) |
| Starting artifact | The branch with B4, S0 and the accepted matrix merged |

Common acceptance, for the ticket's own directories:
- `python3 -m unittest discover -s tests -p 'test_skills.py'` exits 0 (budgets, phrases, source headers against `THIRD-PARTY-NOTICES`, worker-contract non-duplication).
- `--check` exits 0, and the agent total stays under 32,000 bytes.
- The stale-role grep over the ticket's directories prints nothing: `grep -rn "founder-mind\|red-teamer\|auditor\|gatekeeper\|janitor\|releaser\|builder-repair" <owned skill dirs>`.
- `grep -rn "should\|probably\|seems" <owned skill dirs>` matches only the E6 rule text and quoted examples.
- `grep -rln "^Stub:" <owned skill dirs>` prints nothing.
- The report lists, per file written, the matrix rows used.

| Ticket | Owned paths | Extra acceptance |
| --- | --- | --- |
| S1 | `plugins/orchestra/skills/orchestra/**` except `references/cli.md`; `plugins/orchestra/skills/orchestra-worker/**`; `tests/skill_phrases/orchestra.json`, `tests/skill_phrases/orchestra-worker.json` | `grep -rn --exclude=cli.md "review-groups\|audit-policy\|orchestra.py route" plugins/orchestra/skills/orchestra` prints nothing (`cli.md` belongs to B8, whose own grep covers it). `references/final-review.md` routes the four lenses without restating the lens-to-category table (SPEC 9): `grep -rn "requirements, correctness, tests, standards" plugins/orchestra/skills/orchestra plugins/orchestra/skills/orchestra-worker` prints nothing. Phrases include `STATUS: PASS|ISSUES|BLOCKED` (in `orchestra-worker`), `Mode:`, `Lens:`, `Round 5`, `standing-orders.md`, `progress.md`, `more than 50 changed lines`, the four lens names, `park`, and the `gh api` bypass rule, plus the SPEC 8.5 executor phrases (`Executor choice`, `single Agent dispatch`, `default whenever the host has the Workflow tool`, `reserve every card before the script`, `agentType: 'orchestra:`, `isolation: 'worktree'`, `never approves its own implementation`). `Round 5` and `more than 50 changed lines` appear in `orchestra.json` only (SPEC 9). `orchestrator.md` stays within 10,500 bytes. |
| S2 | `plugins/orchestra/skills/orchestra-design/**`; `tests/skill_phrases/orchestra-design.json` | Phrases cover glossary-first, decisions to the user, and the `product` mode dossier. |
| S3 | `plugins/orchestra/skills/orchestra-critique/**`; `tests/skill_phrases/orchestra-critique.json` | Live (0.6): a dispatched `orchestra:critic` with `Mode: spec` reads `references/spec.md` by its plugin-root path and quotes its sentinel. |
| S4 | `plugins/orchestra/skills/orchestra-build/**`; `tests/skill_phrases/orchestra-build.json` | Phrases cover tests first, `cleanup` lean-and-simplify, and working the round number the brief names. `repair.md` carries no fix-round cap (SPEC 9). |
| S5 | `plugins/orchestra/skills/orchestra-review/**`; `tests/skill_phrases/orchestra-review.json` | Phrases cover the four lens files, the lens-to-category table in `references/final.md` (its only copy, SPEC 9; phrase `requirements, correctness, tests, standards`), the anti-tautology rule, and reviewing as the specialist the brief names. `specialists.md` carries no size gate (SPEC 9). |
| S6 | `plugins/orchestra/skills/orchestra-investigate/**`; `tests/skill_phrases/orchestra-investigate.json` | Phrases cover evidence labels and read-only reporting. |
| S7 | `plugins/orchestra/skills/orchestra-operate/**`; `tests/skill_phrases/orchestra-operate.json` | Phrases cover exact command, exit code and log path, and release only under an explicit assignment. |

### S8: role and model docs

| Field | Value |
| --- | --- |
| Goal | `docs/roles.md`: the 7 roles, modes, mode files, two-skill preload, and the note that `disallowedTools: Agent` on every worker meets the 1(f) reviewer-independence clause. `docs/models.md`: orchestrator "user's selection", builder `cleanup`, `sandbox_mode`. |
| Role | builder/mechanical [v1 `orchestra:builder`] |
| Deps | B4 |

Owned paths: `docs/roles.md`, `docs/models.md`.

Acceptance: `grep -n "user's selection" docs/models.md` and `grep -n "disallowedTools" docs/roles.md` each print a line; the stale-role grep over both files matches only a v1-to-v2 mapping table.

### SC: skill cohesion critic

| Field | Value |
| --- | --- |
| Role | critic/standards [v1 `orchestra:auditor`], read-only, report returned as the final message |
| Deps | S0 to S7 accepted and merged |
| Owned | Nothing |
| Scope | All files under `plugins/orchestra/skills/**` together, against SPEC 8 and 9, `config/roles.json`, the engine CLI, `orchestra/references/briefs.md`, `docs/SKILL-SOURCES.md` and the SPEC 8.2 avoid list. The brief names the pinned-text path. |
| Acceptance | `grep -rln "^Stub:" plugins/orchestra/skills` prints nothing. PASS, or ISSUES naming file and line for: contradictions between files; a rule stated in more than one file (including the lens-to-category table anywhere outside `orchestra-review/references/final.md`); a rule that conflicts with the engine or with `briefs.md`; a cited file without its `Source:` header; content that does not trace to the file's matrix rows; rejected or avoid-list content; text that reads as concatenated upstream prose. Findings route to the owning S ticket under E1, then a fresh SC. |

### B7: user-facing docs

| Field | Value |
| --- | --- |
| Goal | Docs describe 2.0.0: the v1-to-v2 role mapping, guard changes and the class vocabulary, the API requirement for mods, the CLI after the trim and with the new commands, SessionEnd, scoped evidence, autonomy, the install-first release path, third-party notices, and release notes. |
| Role | builder/mechanical [v1 `orchestra:builder`] |
| Deps | B5, B8, B9, B10, B11, S0 |

Owned paths:
- `README.md`
- `docs/hooks.md`, `docs/cli.md`, `docs/source-parity.md` (drop the `route` rubric), `docs/VALIDATION.md`
- `plugins/orchestra/skills/orchestra/references/cli.md`
- `SPEC.md` and `PLAN.md`: a one-line pointer each

Acceptance:
- `grep -rn "founder-mind\|red-teamer\|gatekeeper\|janitor\|releaser\|builder-repair" README.md docs/hooks.md docs/cli.md plugins/orchestra/skills/orchestra/references/cli.md` matches only inside the v1-to-v2 mapping table.
- `grep -rn "review-groups\|audit-policy\|orchestra.py route" README.md docs/cli.md docs/source-parity.md plugins/orchestra/skills/orchestra/references/cli.md` prints nothing.
- `python3 scripts/build_release.py --out "$SCRATCH/b7"` on the committed candidate exits 0.

## 2. Integration, final review, gates, release

### INT (coordinator)

- Tickets are merged into `feat/v2-roles-guard-mods` strictly one at a time, in DAG order: merge, checkpoint review on the merged commit, accept, ledger row, then the next merge (0.3). Generated conflicts are resolved by regenerating (0.5).
- SC (the cohesion critic) is PASS on the merged skill files before the lens round. The skill files have no separate code-reviewer checkpoint; SC and `test_skills.py` cover them, and the lens round covers the whole diff.
- The last commit before the lens round is the coordinator's `docs/BUILD-LEDGER.md` entry (tickets, checkpoints, live-check results). It is committed with an explicit path. No follow-up PR is planned for the ledger.
- The result is the candidate: full SHA, clean tree.

### Final review loop

- RF1 to RF4: code-reviewer/final [v1 `orchestra:code-reviewer`], one card per lens (`Lens: correctness`, `architecture`, `security`, `cleanliness`), each covering every task, over `8c1f195..HEAD` with the review package. They run in parallel on the same SHA.
- Correctness findings route to builder/repair under E1.
- Confirmed findings from RF2 to RF4 route to one CL card: builder/cleanup, owning the cited paths, at the end of the run.
- After any repair or CL, the coordinator amends the ledger entry with a new explicit-path commit if a claim changed, and RF1 to RF4 run again on the new SHA. Surviving cleanup findings count as E1 rounds on CL.
- The loop ends when RF1 to RF4 are CLEAN on one SHA. That SHA is frozen.

### On the frozen SHA (parallel)

- G1, operator/gate [v1 `orchestra:gatekeeper`]. Gate set, the derived impact set (every unit module is a changed surface; this is not the owner-triggered full suite):
  - `test_engine.py`, `test_hooks.py`, `test_guard_corpus.py`, `test_integration.py`, `test_packaging.py`, `test_skills.py` (each run separately);
  - `generate.py --check`;
  - `claude plugin validate plugins/orchestra`;
  - `CLAUDE_CODE_ENABLE_FUNCTION_HOOKS=1 claude plugin test plugins/orchestra`;
  - `python3 scripts/build_release.py --out "$SCRATCH/g1"`;
  - `grep -rln "^Stub:" plugins/orchestra/skills` prints nothing.
  - Logs go to `$SCRATCH/g1-logs/`, outside the repository, each with exit code and path.
- A1 critic/spec [v1 `orchestra:auditor`] against `docs/SPEC-v2.md`.
- A2 critic/standards against `AGENTS.md` at blob `182417468e23…`.
- A3 critic/ledger: runs, because `docs/BUILD-LEDGER.md` gains claims.
- A4 critic/surface [v1 `orchestra:founder-mind`]: agent listing, README, the install path from 1.0.1, and the release notes draft.
- Any edit after the freeze voids RF1 to RF4, G1 and A1 to A4.

### L1, operator/release, executed by the coordinator with the user (U1)

Deps: G1, RF1 to RF4, A1 to A4, all CLEAN on the frozen SHA. This build has no engine run (0.1). Post-freeze evidence goes to the coordinator notes file `$SCRATCH/release-notes-log.md` (fixed path, 0), outside the repository, and to the user report, not to a repo commit.

0. Coordinator: `orchestra.py status` shows no active run (none was started for this build). Autonomy is off. Write the release plan to the notes file (E2).
1. User wizard, local install of v2 (Orchestra hooks are absent between uninstall and install, so the wizard runs in a plain terminal):
   - `test "$(git -C "$REPO" rev-parse HEAD)" = "$FROZEN"` and `git -C "$REPO" status --porcelain` is empty;
   - `claude plugin uninstall orchestra@orchestra-distribution`;
   - `claude plugin marketplace remove orchestra-distribution` (the local marketplace declares the same name);
   - `claude plugin marketplace add "$REPO"`;
   - `claude plugin install orchestra@orchestra-distribution`;
   - `claude plugin list` shows exactly one `orchestra@orchestra-distribution`, version 2.0.0;
   - `diff -rq ~/.claude/plugins/cache/orchestra-distribution/orchestra/2.0.0 "$REPO/plugins/orchestra"` is empty apart from known install metadata (copy or link is settled by this diff).
2. **Restart point A.** The user starts a new session in `$REPO`. Checks: exactly one Orchestra SessionStart context with the session-id line; the marker heartbeat advances (in the Desktop app this is the U2 check on embedded 2.1.286); then `orchestra.py start --new-run` under v2 (archiving any v1 state), then `orchestra.py interrupt --lease <lease>` with the lease that `start --new-run` printed, and `orchestra.py status` shows inactive. The coordinator in the new session resumes from `$SCRATCH/release-notes-log.md` (E2); `$SCRATCH` is fixed (0), so the path survives the restart.
3. Pre-push checks: no active run; `git stash` is denied by the v2 guard; `git fetch origin`; `git merge-base --is-ancestor origin/main "$FROZEN"` exits 0, else stop.
4. `git push origin feat/v2-roles-guard-mods` (non-force; allowed unarmed by A1).
5. `gh pr create --base main --head feat/v2-roles-guard-mods --title "Orchestra 2.0.0" --body-file "$SCRATCH/pr-body.md"` (body lists the role mapping and breaking changes).
6. `gh pr merge <N> --squash --delete-branch`. No `gh api` merge and no MCP or terminal-tool merge (U1).
7. `git switch main`, `git pull --ff-only origin main`, then `git diff --quiet "$FROZEN" HEAD` exits 0 (squash keeps the tree).
8. Version check: every manifest of SPEC B-F3 reads `2.0.0`.
9. `python3 scripts/build_release.py --out "$SCRATCH/release-2.0.0"` on clean `main`.
10. `git tag v2.0.0` (lightweight, matching v1.0.1), then `git push origin v2.0.0`.
11. `gh release create v2.0.0 "$SCRATCH"/release-2.0.0/*.tar.gz "$SCRATCH"/release-2.0.0/*.zip "$SCRATCH"/release-2.0.0/SHA256SUMS --verify-tag --title "Orchestra 2.0.0" --notes-file "$SCRATCH/release-notes.md"`.
12. User wizard, Claude reinstall from GitHub main: `claude plugin uninstall orchestra@orchestra-distribution`; `claude plugin marketplace remove orchestra-distribution`; `claude plugin marketplace add Y-B-1/orchestra-plugin`; `claude plugin install orchestra@orchestra-distribution`; `claude plugin list` shows one entry at 2.0.0.
13. F2 check: `diff -rq ~/.claude/plugins/cache/orchestra-distribution/orchestra/2.0.0 plugins/orchestra` on `main` is empty apart from install metadata.
14. User wizard, Codex (installs from remote `main`, so it follows the merge): `codex plugin marketplace upgrade orchestra-distribution`; `codex plugin remove orchestra@orchestra-distribution`; `codex plugin add orchestra@orchestra-distribution`; `python3.11 ~/.codex/plugins/cache/orchestra-distribution/orchestra/2.0.0/scripts/orchestra.py install-profiles`; `diff -rq` of the installed copy against `plugins/orchestra-codex`.
15. Codex live discovery: a Codex session shows the Orchestra hooks (re-approve the hook trust entries in `~/.codex/config.toml` if prompted; a user step) and the 9 profiles; the read-only role profiles carry `sandbox_mode = "read-only"`; v1 profiles are gone.
16. **Restart point B.** A fresh Claude session: the Agent listing shows the 8 worker agents and not `orchestra:orchestrator`; the plugin's agent list names the 9 v2 files and no v1 names; a dispatched worker reports `claude-sonnet-5-5`; the main session reports the picker's model; `git stash` denied, `git stash list` allowed; `/orchestra-board` renders; a Workflow `agent()` with `agentType: 'orchestra:builder'` and `Mode: repair` quotes both preload sentinels and the `repair.md` sentinel (SPEC 8.5).
17. Coordinator, outside the tickets: update `~/.claude/CLAUDE.md` and `~/.codex/AGENTS.md` (U5 list in the rulings).
18. **Restart point C.** Coordinator, last, outside the tickets: update the Claude Desktop app, which restarts it (U2). After restart, the marker heartbeat appears in a Desktop session.

## 3. Failure and repair routing

- **Fix rounds** per ticket after an independently checked BLOCKED (SPEC E1): rounds 1 to 3 builder/repair at Sonnet 5.5 medium; round 4 at the Opus 5.5 override [v1 `orchestra:builder-repair`]; round 5 breaker to critic/judge, then the designer-planner, and the user is told.
- **B1, mods do not co-load from the hooks array.** Pre-approved technical fallback: put `"modules": ["./mod/orchestra.ts"]` into `hooks/claude.json` and drop `hooks/mods.json`. Re-run the B1 live check.
- **B1, the validator rejects the `typeof` presence check.** Technical fallback in SPEC 10.2: rely on load-time validation. Record it.
- **B1/B5, function hooks do not run under `claude -p`** even with the env switch. Record it as accepted behavior: Python guards cover `-p` through the absent marker.
- **B4, a live check shows a preload sentinel missing.** Read `claude --debug`; fix the name or file. If preload itself fails, return to design (SPEC 3.3 rests on it).
- **B4, the Agent tool rejects the full model id.** Use the `opus` alias in the coordinator skill. Not a spec change.
- **B3, no classic SessionStart with `source` `clear`, `resume` or `fork` follows `/clear`, `/resume` or `/branch`, or `status` does not show the rebound `harness_session`.** Return to design for O6 before B3 acceptance. (A changed `session_id` alone is handled by the rebind, SPEC B-F5.)
- **B3, SessionEnd latency exceeds 10 s.** Return to design (timeout or release path).
- **B5, corpus parity fails.** Fix the TypeScript side. If the Python decision looks wrong, open a B2 repair card. B5 never changes existing expectations.
- **B9, scoped evidence breaks an existing review flow.** Repair under E1. If the scope rule itself is wrong, return to design (O3 interpretation).
- **B11, no status band API.** Skip the band (SPEC 12.7) and record it. Not a spec change.
- **Checkpoint BLOCKED on a merged commit.** Repair from a new worktree at the merged HEAD under E1; merge the repair and re-review before any other merge (0.3).
- **I2, a source is not MIT at the pinned SHA, or a path is missing.** That source is idea level only (SPEC 8.2). Not a spec change.
- **MXR ISSUES.** An MX repair card, then a fresh MXR. A capability with no fitting candidate is recorded as "none, Orchestra text" with the reason; it is not a spec change.
- **SC ISSUES.** The owning S ticket repairs under E1. A rule that conflicts with the engine is fixed in the skill text; if the engine behavior itself contradicts SPEC-v2, it goes to design.
- **S ticket over budget.** Move procedure text into a mode file. The coordinator may reallocate agent sub-budgets within the 32,000 total (SPEC 8.3).
- **Any contradiction with SPEC-v2** goes to the designer-planner, design mode.
- **Release failure.**
  - Step 2: two SessionStart contexts, or no marker. Stop; rerun the step 1 wizard; never hand-patch the cache.
  - Step 3: `origin/main` is not an ancestor. Stop and ask the user; rebase or merge is not authorized here.
  - Push, PR or merge failure: stop and report.
  - Reinstall mismatch: rerun the wizard step. Never hand-patch a cache.

## 4. Dependency graph

Edges (ticket: prerequisites):

- P0: none
- I1: accepted
- I2: none
- B1: P0
- B2: B1
- B4: B1, I1
- B3: B2, B4
- B8: B3
- B9: B8
- B10: B9
- B5: B2, B3, B4, B8, I1
- B11: B5, B10
- MX: I2
- MXR: MX
- S0: B4, I2, MXR
- S1 to S7: B4, S0, MXR
- S8: B4
- B7: B5, B8, B9, B10, B11, S0
- SC: S0 to S7
- INT candidate: every B and S card accepted, and SC PASS
- RF1 to RF4: INT candidate
- CL: RF2 to RF4 (only with confirmed findings); then RF1 to RF4 again
- G1, A1 to A4: the frozen SHA (RF1 to RF4 CLEAN on it)
- L1: G1, RF1 to RF4, A1 to A4

Readiness from accepted prerequisites:

- P0 and I2 are ready at start; I1 is accepted.
- B1 is ready on P0. MX is ready on I2; MXR on MX; S0 on MXR and B4.
- B2 and B4 are ready on B1 (and I1), in parallel.
- B3 is ready on B2 and B4. S8 is ready on B4. S1 to S7 are ready on B4, S0 and MXR, and run in parallel with B3 onward. SC is ready when S0 to S7 are merged.
- B8, B9 and B10 follow B3 in a chain. B5 is ready on B8 and runs in parallel with B9 and B10.
- B11 is ready on B5 and B10. B7 is ready on B11 (its other prerequisites are accepted by then).
- Every node becomes ready from accepted prerequisites, and none depends on an unknown ticket. The graph is acyclic: one topological order is P0, I2, MX, MXR, B1, B2, B4, S0, S1 to S8, SC, B3, B8, B5, B9, B10, B11, B7, INT, RF1 to RF4, CL, G1, A1 to A4, L1.

Repair card B2-r1 (from R2 and D3-r1), owned paths within the B2 set: `guards.py` (A5 rules 1 to 5), `guard-rules.json` (`_doc`), `guard-corpus.json` (append only), `hooks.py` (the marker check uses the guard digest; `_main_worktree` without `--path-format`), `test_guard_corpus.py`, `test_hooks.py`, `test_integration.py` (the bare-common-dir A15 case). The mod's `marker.ts` keeps hashing the table alone until B5, so until B5 merges the Python digest never matches and Python guards in full, which is the safe direction.

Parallel sets and their owned paths are disjoint:

- B2 and B4: guards/hooks/run-hook/claude.json/guard config/test_hooks/test_guard_corpus/test_integration (A15 test) versus roles/models/generate/engine/skills/test_engine/test_packaging/test_skills/skill_phrases.
- Integration is serial (0.3), so "parallel" means building at the same time in separate worktrees; merges never overlap.
- B3 to B10 chain, B5, B11, S0 to S8: engine.py, orchestra.py, hooks.py, policy, autonomy template and their tests (chain); `hooks/mod/**` except autonomy files, types, corpus (B5, then B11 after it); one skill directory and one phrase file each (S1 to S7); `docs/roles.md` and `docs/models.md` (S8); the notices file, the `test_skills.py` provenance tests and the `roles.json` code-reviewer sentence (S0, finished before S1 to S7 start); `docs/SKILL-SOURCES.md` (MX, finished before S0 starts). `skills/orchestra/references/cli.md` belongs to B8 and then B7, never to S1.

Shared paths, each serialized by an edge:

| Path | Tickets, in order |
| --- | --- |
| `orchestra_core/engine.py` | B4, B3, B8, B9, B10 |
| `orchestra.py` | B3, B8, B9, B10 |
| `orchestra_core/hooks.py` | B2, B3, B8, B10 |
| `hooks/claude.json` | B2, B3 |
| `generate.py` | B1, B4 |
| `tests/test_packaging.py` | B1, B4 |
| `tests/test_skills.py` | B4, S0 |
| `config/roles.json` | B4, S0 (code-reviewer prompt sentence only) |
| `tests/test_engine.py` | B4, B3, B8, B9, B10 |
| `tests/test_integration.py` | B2 (A15 test only), B3, B8, B9, B10 |
| `tests/test_hooks.py` | B2, B3, B8, B10 |
| `config/guard-corpus.json` | B2, B5 (append only) |
| `types/index.d.ts` | B1, B5, B11 |
| `hooks/mod/orchestra.ts` | B1, B5, B11 |
| `skills/orchestra/references/cli.md` | B8, B7 |
| `README.md` | B8, B7 |
| `skills/**` | B4, then one S ticket per directory |
| `tests/skill_phrases/<dir>.json` | B4, then the matching S ticket |

Counts: builder tickets B1 to B5, B7 to B11 (10) and S0 to S8 (9). Checkpoints: R1, R2, R3, R4, R5, R8, R9, R10. Critics: MXR, SC. Matrix: MX. Final: RF1 to RF4, CL if needed, G1, A1 to A4.

## Coordinator rulings (2026-10-04, revised)

- O1: revised by U7. Keep `settings.agent: orchestra:orchestrator`; the orchestrator file carries no `model` or `effort`.
- O2: the classic SessionEnd hook releases the lease under the O6 policy; the mod's `session.end` only retires its heartbeat.
- O3: in scope for 2.0.0 (U3b, ticket B9). Final, gate, release and completion evidence stay whole-repo; confirm before B9 acceptance.
- O4: `az repos pr update --status completed` stays behind the release check inside an armed run.
- O5: accept the 32,000-byte agent-file limit.
- O6 (SessionEnd reasons), O7 (autonomy caps), O8 (lease-free autonomy toggle): defaults in SPEC 13 apply unless the user overrides at the named confirmation point.
- Round 5 (user asleep, overnight run authorized): O12 autonomy boundary details as REASONED defaults, confirmed before B10 acceptance; O13 linked-worktree state resolution (A15); O14 no `docs/skill-authoring.md`. FF1/FF3: this build is tracked in `docs/BUILD-LEDGER.md`, not the engine (0.1). Worktrees are created by the coordinator (0.3). FF2: L1 step 2 always resets state under v2.
- Round 6: R1 fixes `$SCRATCH` as one scratch directory outside the repository (0). R2: B1 was dispatched under its current text; its owned paths and acceptance are unchanged. MX runs in the main checkout as a one-time exception (0.3).
- O9, O10, O11: confirmed by the user (round 4, SPEC 3.4). Option A trim ships in 2.0.0, and every in-scope item ships in 2.0.0.
- U5, coordinator only, after release (L1 step 17). `~/.claude/CLAUDE.md` and `~/.codex/AGENTS.md` must state:
  - the v1-to-v2 role mapping;
  - removal of the local `models.json` sonnet-5-5 patch note;
  - the round-4 Opus repair policy;
  - workflow-nudge now warns instead of blocking;
  - project rules live in `AGENTS.md`, never `CLAUDE.md` (nested `AGENTS.md` files do not load);
  - the Codex file uses role names only and keeps its model choices.
- U2: the Desktop app update is the coordinator's last step (L1 step 18).
- Project-kit `orchestra-autonomy-loop.sh` removal is a separate coordinator workstream after release (SPEC X10).
