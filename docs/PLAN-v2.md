# Orchestra 2.0.0 plan

- Input: `docs/SPEC-v2.md`. The plan makes no product decisions. Every ticket cites SPEC sections, and a contradiction found while building goes back to design, not to builder judgment.
- Starting artifact: `feat/v2-roles-guard-mods` at `0ea2ece8059abfb83419714caeda714dfaefd63f`.
- Policy revision: `AGENTS.md` blob `182417468e23bfa02c1afbd15bac1d031141a18e`.

## 0. How to read this plan

### 0.1 Dispatch names during the build

The installed plugin is 1.0.1 until the release ticket L1. Until then, workers are dispatched under their **v1** agent names, and any engine run uses v1 role ids. Each ticket gives its v2 role first and then the v1 dispatch name in brackets.

| v2 role/mode | v1 dispatch name |
| --- | --- |
| critic/feasibility, scope, judge | `orchestra:red-teamer` |
| critic/spec, standards, ledger | `orchestra:auditor` |
| critic/surface | `orchestra:founder-mind` (audit) |
| builder/* | `orchestra:builder` |
| builder/repair (round 4) | `orchestra:builder-repair` |
| code-reviewer/checkpoint | `orchestra:code-reviewer-checkpoint` |
| code-reviewer/final | `orchestra:code-reviewer` |
| investigator/docs | `orchestra:investigator` |
| operator/gate | `orchestra:gatekeeper` |
| operator/release | `orchestra:releaser`. Executed by the coordinator, per the user's authorization. |

### 0.2 Models

- Claude builders run Sonnet 5.5 medium (all presets), except fix round 4, which runs Opus 5.5 (SPEC E1).
- Checkpoint review runs Opus 5.5 medium. Final review and critic run Opus 5.5 high. Investigator docs and operator run Sonnet 5.5 medium.
- If a ticket runs on Codex instead, the AGENTS.md mapping applies:
  - builder: `gpt-6.1-sol` medium;
  - review, critic and checked repair: `gpt-6.1-sol` high;
  - bounded discovery and hygiene: `gpt-6-luna` high.
- Model and effort stay fixed for the whole assignment.

### 0.3 Worktrees

Builder tickets that run at the same time each get their own git worktree, created from the merge-base the ticket names. The coordinator creates each worktree, merges it, and removes it.

### 0.4 Rules to restate verbatim in every brief

The plan's briefs restate these inline:

- Python 3.11+ stdlib only.
- Never hand-edit generated files (`plugins/*/agents/*.md`, `plugins/*/profiles/codex/*.toml`, `plugins/orchestra-codex/**`). Regenerate with `python3 plugins/orchestra/scripts/generate.py` and check with `--check`.
- No personal absolute paths, credentials or audit content in the repo. Refer to the audit by finding ID only.
- Explicit-path commits. Never stage wholesale, stash, force push or hard reset.
- Only `gpt-6.1-sol`/`gpt-6-luna` (Codex) and `claude-opus-5-5`/`claude-sonnet-5-5` (Claude).
- You are not alone. Preserve sibling edits. Never delegate, change coordinator state, or release.
- Report shape: `STATUS: PASS|ISSUES|BLOCKED`, `ARTIFACT: <full sha> <dirty fingerprint>`, changed paths, commands with exit codes and log paths, findings, uncertainties.

### 0.5 Shared generated resource

Every ticket that changes `plugins/orchestra/**` also changes the generated mirror `plugins/orchestra-codex/**`. Tickets that change `config/roles.json`, `config/models.json`, `generate.py` or skills also change `agents/` and `profiles/`.

- No ticket owns generated files. Each ticket regenerates inside its own worktree, so that its checks pass, and commits the regenerated output.
- At integration the coordinator merges in DAG order. Any conflict in a generated path is resolved by accepting either side and then rerunning `python3 plugins/orchestra/scripts/generate.py`. Generated output is never merged by hand.
- `--check` must exit 0 after every merge.

## 1. Tickets

The common check is:

```
python3 plugins/orchestra/scripts/generate.py --check
```

Unit test modules run one at a time with:

```
python3 -m unittest discover -s tests -p '<module>.py'
```

`tests/` has no `__init__.py` (OBSERVED), so `discover -p` is the supported form.

### P0: red team of SPEC-v2 and PLAN-v2 (prerequisite to every build)

| Field | Value |
| --- | --- |
| Role | critic/feasibility, then critic/scope [v1 `orchestra:red-teamer`], two independent cards; a third critic/judge card only if the first two disagree |
| Starting artifact | `0ea2ece` plus the two docs (uncommitted, or committed by the coordinator) |
| Owned | Nothing. Read-only. Report returned as the final message. |
| Deps | None |
| Acceptance | Each report is PASS, or ISSUES with findings that each map to a SPEC/PLAN section. Findings are repaired by the designer-planner. Product contradictions go to the user. |

### I1: investigation of unverified platform facts (read-only, parallel with P0)

| Field | Value |
| --- | --- |
| Role | investigator/docs [v1 `orchestra:investigator`], Sonnet 5.5 medium |
| Owned | Nothing. The coordinator records the result as `docs/RESEARCH-v2.md`, which expires with this release. |
| Deps | None |

Questions, each answered with a doc URL or an observed command:

1. Does agent frontmatter `skills:` take a bare skill name or `plugin:skill` for skills in the same plugin? Does `disable-model-invocation: true` on a skill block preload?
2. Does the Agent tool `model` parameter accept `claude-opus-5-5`, or only aliases (`opus`)?
3. Which Codex profile key makes a profile read-only (for example `sandbox_mode = "read-only"`), and does it apply to `[agents]` profiles?
4. Does a classic `SessionEnd` payload carry `session_id` and `cwd` equal to SessionStart's? Do subagent PreToolUse payloads carry the parent `session_id`?
5. Do mods function hooks load under `claude -p` on 2.1.289, and does any environment switch gate them?
6. What are the exact local reinstall commands?
   - Claude Code: marketplace update and plugin update for `orchestra@orchestra-distribution`.
   - Codex: plugin reinstall, then `orchestra.py install-profiles`.

Acceptance: every question is answered OBSERVED or DOCUMENTED (with a link), or explicitly UNKNOWN. An UNKNOWN on Q1 or Q2 sends B4 to its fallback (section 3).

### B1: thin end-to-end slice (version, mod skeleton loads, package exclusion)

| Field | Value |
| --- | --- |
| Goal | Prove the whole pipe before widening: 2.0.0 manifests; a mod module that loads next to the classic hooks from one plugin; Codex package excludes mod files. SPEC sections B-F3, 10.1, 10.2 and the marker part of 10.3. |
| Role | builder/implementation [v1 `orchestra:builder`] |
| Starting artifact | `0ea2ece` |
| Deps | P0 |

Owned paths:
- The five version manifests (SPEC B-F3), apart from the generated `plugins/orchestra-codex/.codex-plugin/plugin.json`.
- `plugins/orchestra/.claude-plugin/plugin.json`: the hooks array and `types`.
- New files: `plugins/orchestra/hooks/mods.json`, `plugins/orchestra/hooks/mod/orchestra.ts`, `plugins/orchestra/hooks/mod/marker.ts`, `plugins/orchestra/types/index.d.ts`.
- `plugins/orchestra/scripts/generate.py`, for the `codex_package` exclusion of `hooks/mods.json`, `hooks/mod/` and `types/` only.
- `tests/test_packaging.py`, for the version-equality test and an exclusion test only.

Mod skeleton scope:
- `session.start` applies the version floor (base 2.1.287 or later). If the floor passes, it writes the marker `${XDG_STATE_HOME:-$HOME/.local/state}/orchestra/mods/<session_id>.json` with `rules_sha256: null` and heartbeats it every 5 s.
- `session.end` writes `heartbeat_ms: 0`.
- There is no guard yet. A null `rules_sha256` never matches, so Python keeps guarding.

Acceptance (commands with exit 0):
- `test_packaging.py`, `--check`, and `claude plugin validate plugins/orchestra`. The validate output must list `session.start` and `session.end`.
- `python3 scripts/build_release.py --out <scratch dir>`, run on a committed candidate, rejects nothing.
- Live check: in an interactive session started with `claude --plugin-dir plugins/orchestra` from the worktree:
  - the SessionStart Orchestra context appears (classic hooks loaded);
  - the marker file appears and its `heartbeat_ms` advances over 10 s or more (mod loaded);
  - after `/exit`, `heartbeat_ms` is 0.
- The same is attempted under `claude -p` and the observed outcome recorded.
- An interactive check is a human step. The coordinator generates a bash wizard script in the scratchpad and the user runs it. The result is pasted into the ledger.

Checkpoint: R1, code-reviewer/checkpoint, on the B1 diff.

### B2: guard fixes, shared rules table and corpus

| Field | Value |
| --- | --- |
| Goal | SPEC sections A1 to A13 and B-F4, in Python. Creates the shared rules table and corpus. |
| Role | builder/sensitive [v1 `orchestra:builder`] |
| Starting artifact | B1 merged |
| Deps | B1 |
| Checkpoint | R2, code-reviewer/checkpoint, on the B2 diff plus the corpus |

Owned paths:
- `plugins/orchestra/scripts/guards.py`
- `plugins/orchestra/scripts/hooks.py`: PreToolUse, SubagentStart, `_protected`, the marker check, `--from-mod`
- `plugins/orchestra/scripts/run-hook.sh`
- `plugins/orchestra/hooks/claude.json`: matcher only
- New: `plugins/orchestra/config/guard-rules.json`, `plugins/orchestra/config/guard-corpus.json`
- `tests/test_hooks.py`
- New: `tests/test_guard_corpus.py`

Acceptance:
- `test_hooks.py`, `test_guard_corpus.py`, `test_integration.py` and `--check` all exit 0.
- Every A-row and B-F4 test in SPEC sections 5 and 6 exists. In particular, `test_release_unconfigured` is flipped (unarmed push allowed), and a new armed-run test denies without a permit.
- The corpus contains every command string in the existing `test_hooks.py` deny and allow tests.
- `bash -n plugins/orchestra/scripts/run-hook.sh` exits 0.
- Latency evidence (before/after, 10 runs each) is recorded.

### B4: role consolidation and skill split (schema foundation)

| Field | Value |
| --- | --- |
| Goal | SPEC sections 7 and 8, the mechanical parts: 7 roles, `dispatch: override`, read-only `disallowedTools`, per-role skill directories with `skills:` preload, no "Read references" lines, engine role keys and contract root. Skill content is moved and renamed, not yet rewritten. |
| Role | builder/implementation [v1 `orchestra:builder`] |
| Starting artifact | B1 merged |
| Deps | B1, I1. It may run in parallel with B2, in a separate worktree. |
| Checkpoint | R4, code-reviewer/checkpoint |

Owned paths:
- `plugins/orchestra/config/roles.json`
- `plugins/orchestra/config/models.json`
- `plugins/orchestra/config/flow.json`, only if a role name is found there. None was found (OBSERVED).
- `plugins/orchestra/scripts/generate.py`, for agent and profile generation (B1's exclusion edit stays)
- `plugins/orchestra/scripts/engine.py`: `_contracts` root, and role keys `releaser` to `operator`/release and `auditor`/`red-teamer` to `critic`
- `plugins/orchestra/skills/**`: create `orchestra-investigate/`, `orchestra-design/`, `orchestra-critique/`, `orchestra-build/`, `orchestra-review/` and `orchestra-operate/`, each with a `SKILL.md`; move the method references into them; keep `orchestra/` with `coordination.md`, `cli.md` and `briefs.md`
- `tests/test_engine.py`: role names only
- `tests/test_packaging.py`: role matrix only

Acceptance:
- `test_engine.py`, `test_packaging.py`, `test_routing.py`, `test_integration.py` and `--check` all exit 0.
- `--check` reports 19 native profiles.
- `ls plugins/orchestra/agents` and `ls plugins/orchestra/profiles/codex` match SPEC 7.2 acceptance exactly.
- `grep -rn "Read references/\|Read SKILL.md" plugins/orchestra/agents` prints nothing.
- `cat plugins/orchestra/agents/*.md | wc -c` is under 32000.
- `grep -rn "founder-mind\|red-teamer\|auditor\|gatekeeper\|janitor\|releaser\|builder-repair" plugins/orchestra --include=*.py --include=*.json` prints nothing, apart from deliberate legacy-mapping text.
- Live check: in an interactive `--plugin-dir` session:
  - `orchestra:orchestrator` is still the main agent;
  - a dispatched `orchestra:builder` echoes a sentinel line from `orchestra-build/SKILL.md` without a Read or Skill call;
  - a dispatched `orchestra:critic` cannot use Write (the tool is refused);
  - an Agent call with `model` set to the I1 Q2 answer runs `builder` on Opus.

### B3: lease release on session end (F5) and CLI additions

| Field | Value |
| --- | --- |
| Goal | SPEC B-F5: harness-session binding, classic SessionEnd release, SessionStart session-id context, and the `start --harness-session` and `where` CLI commands. |
| Role | builder/sensitive [v1 `orchestra:builder`] |
| Starting artifact | B2 and B4 merged |
| Deps | B2, B4 (shared `engine.py`, `hooks.py`, `hooks/claude.json`, `tests/test_engine.py`, `tests/test_hooks.py`) |
| Checkpoint | R3, code-reviewer/checkpoint |

Owned paths:
- `plugins/orchestra/scripts/engine.py`: `open_session` optional `harness_session`, `end_harness_session`
- `plugins/orchestra/scripts/orchestra.py`: `start --harness-session`, `where`
- `plugins/orchestra/scripts/hooks.py`: SessionEnd, plus the SessionStart context line
- `plugins/orchestra/hooks/claude.json`: SessionEnd entry
- `tests/test_engine.py`
- `tests/test_hooks.py`
- `tests/test_integration.py`

Acceptance:
- `test_engine.py`, `test_hooks.py`, `test_integration.py` and `--check` exit 0.
- The integration test passes: start with `--harness-session S`, a SessionEnd payload with S, then `start --new-run` exits 0.
- Further tests pass: a SessionEnd with another id leaves the run armed; a run without a harness session is untouched; a repeated SessionEnd is idempotent.
- `where` output contains no `lease` key (test).
- Live check: start a run in a `--plugin-dir` session, `/exit`, then `status` from a new shell shows `session.active: false`.

### B6: borrowed procedures and role documentation (prose)

| Field | Value |
| --- | --- |
| Goal | SPEC section 9 (E1 to E7) written into the skills. Merges founder content into `orchestra-design` (`product` mode) and `orchestra-critique` (`surface` mode). Updates the briefs contract for read-only roles returning reports. Updates the role and model docs. |
| Role | builder/mechanical [v1 `orchestra:builder`] |
| Starting artifact | B4 merged |
| Deps | B4. It may run in parallel with B2, B3 and B5. |

Owned paths:
- `plugins/orchestra/skills/**` text: every `SKILL.md` and reference file B4 created, plus `skills/orchestra/SKILL.md`, `references/coordination.md` and `references/briefs.md`
- `docs/roles.md`
- `docs/models.md`

Acceptance:
- `test_packaging.py` phrase test passes. B6 adds the test, sharing `test_packaging.py` serially after B4.
- `--check` exits 0, and the agents-size limit from B4 still holds.
- `grep -rn "should\|probably\|seems" plugins/orchestra/skills/orchestra-build/SKILL.md` finds only the verifier-rule sentence.

### B5: mods module (full)

| Field | Value |
| --- | --- |
| Goal | SPEC 10.3 to 10.5: the TypeScript classifier over `guard-rules.json`, the `tool.call` guard with fail-closed `.catch` and release delegation, the marker `rules_sha256`, `agent.offer`, `agent.spawn` (delegation refusal, reviewer independence, standing orders), `/orchestra-board`, and verdict toasts. |
| Role | builder/implementation [v1 `orchestra:builder`] |
| Starting artifact | B3 merged (B6 may or may not be merged yet; their paths do not overlap) |
| Deps | B2, B3, B4, I1 |
| Checkpoint | R5, code-reviewer/checkpoint, focused on guard parity and fail-closed paths |

Owned paths:
- `plugins/orchestra/hooks/mod/**`
- `plugins/orchestra/types/index.d.ts`
- `plugins/orchestra/config/guard-corpus.json`: append only. New cases must also pass `test_guard_corpus.py`. Changing an existing expectation is a B2 repair, not a B5 edit.

Acceptance:
- `claude plugin validate plugins/orchestra` exits 0 and lists the six events in SPEC 10.
- `claude plugin test plugins/orchestra` exits 0, including corpus parity over every corpus case.
- `test_guard_corpus.py`, `test_hooks.py` and `--check` exit 0.
- Live check: the full SPEC section 10 live list, run by a wizard script with the user. Each item is recorded as observed, with a screenshot of `/orchestra-board`.
- A failing mod guard (simulated by an invalid rules file in a scratch copy) leaves Python guarding. Observed: `git stash` is still denied.

### B7: user-facing docs

| Field | Value |
| --- | --- |
| Goal | Docs describe 2.0.0: the role mapping table v1 to v2, the guard behavior changes, the mods floor and fallback, the new CLI, SessionEnd, and release notes. |
| Role | builder/mechanical [v1 `orchestra:builder`] |
| Starting artifact | B3, B5 and B6 merged |
| Deps | B3, B5, B6 |

Owned paths:
- `README.md`
- `docs/hooks.md`
- `docs/cli.md`
- `docs/source-parity.md`
- `docs/VALIDATION.md`
- `plugins/orchestra/skills/orchestra/references/cli.md`
- `SPEC.md` and `PLAN.md`: a one-line superseded pointer each

Acceptance:
- `grep -rn "founder-mind\|red-teamer\|gatekeeper\|janitor\|releaser\|builder-repair" README.md docs/hooks.md docs/cli.md plugins/orchestra/skills` matches only inside the v1-to-v2 mapping table.
- `--check` exits 0.
- `python3 scripts/build_release.py --out <scratch dir>` on a committed candidate exits 0.

## 2. Integration, gates, final review, release

- **INT (coordinator).** Merge order: B1, then B2 and B4 (either order), then B3, then B6 and B5 (either order), then B7. After each merge, regenerate on any generated-path conflict and run `--check`. The result is the frozen candidate, identified by full SHA and a clean tree.
- **G1, operator/gate [v1 `orchestra:gatekeeper`]**, on the frozen candidate.
  - Gate set: the derived impact set. Changed surfaces are engine, hooks, guards, routing consumers, packaging and the CLI, so the set is all six unit modules, each run separately:
    - `test_engine.py`
    - `test_hooks.py`
    - `test_guard_corpus.py`
    - `test_integration.py`
    - `test_routing.py`
    - `test_packaging.py`
  - Also in the gate set: `generate.py --check`, `claude plugin validate plugins/orchestra`, `claude plugin test plugins/orchestra`, and `python3 scripts/build_release.py --out <scratch dir>`.
  - The impact set happens to cover every unit module. It is still derived from changed surfaces and is not the owner-triggered full suite. No extra e2e suite exists in this repo.
  - Logs go to the run state directory. Each entry records the exit code and log path.
- **Final reviews**, on the same frozen SHA, independent of every builder, and run in parallel:
  - RF: code-reviewer/final [v1 `orchestra:code-reviewer`], covering the 7 categories over `0ea2ece..HEAD` with the review package.
  - A1: critic/spec [v1 `orchestra:auditor`] against `docs/SPEC-v2.md`.
  - A2: critic/standards against `AGENTS.md` at blob `182417468e23…`.
  - A3: critic/ledger, run only if `docs/BUILD-LEDGER.md` gains claims.
  - A4: critic/surface [v1 `orchestra:founder-mind`], covering the shipped surface: agent listing, README, and the install/upgrade path from 1.0.1.
  - Any edit after these reviews voids G1, RF and A1 to A4.
- **L1, operator/release [v1 `orchestra:releaser`]**, executed by the coordinator under the user's authorization.
  - Deps: G1, RF, A1, A2, A4 (and A3 if it ran). Every one must be CLEAN on the same SHA.
  - Steps, using the reinstall commands from I1 Q6:
    1. `git push origin feat/v2-roles-guard-mods`. Non-force.
    2. `gh pr create` against `main`, with a body that lists the role-name mapping and breaking changes.
    3. `gh pr merge --squash`, matching repository history.
    4. Reinstall the Claude Code plugin from the marketplace.
    5. Reinstall the Codex plugin and run `orchestra.py install-profiles`. The receipt removes the v1 profiles.
    6. Verify that the installed Claude cache and Codex copies report `"version": "2.0.0"`.
    7. Run `diff -rq <installed cache dir> plugins/orchestra` against the merged `main` checkout. The output must be empty, apart from known install metadata. This is the F2 check.
    8. Live checks in a fresh session: the SessionStart context; `git stash` denied; `git stash list` allowed; the marker heartbeat; `/orchestra-board`; a dispatched worker shows the `claude-sonnet-5-5` model; the agent listing shows the 9 v2 agents and no v1 names.
    9. Write the `docs/BUILD-LEDGER.md` entry, then make a follow-up explicit-path commit through a PR, or include the entry before the freeze if the coordinator prefers. If added after the freeze, it is ledger-only and reviewed by A3.

## 3. Failure and repair routing

- **Fix rounds** apply per ticket after an independently checked BLOCKED (SPEC E1):
  - rounds 1 to 3: builder/repair at Sonnet 5.5 medium;
  - round 4: builder/repair at the Opus 5.5 override [v1 `orchestra:builder-repair`];
  - round 5: breaker. The ticket goes to critic/judge, then to the designer-planner, and the user is told.
- **B1, mods do not co-load from the hooks array.** Pre-approved technical fallback, not a product decision: put `"modules": ["./mod/orchestra.ts"]` into `hooks/claude.json` (a combined file validated in a scratch probe) and drop `hooks/mods.json`. Re-run the B1 live check.
- **B1/B5, function hooks do not run under `claude -p`.** Record the result and treat it as accepted behavior: Python guards cover `-p` through the absent marker. All live checks are interactive.
- **B4, I1 says `skills:` preload does not work for plugin skills** (Q1 UNKNOWN or negative). Stop B4. Return to design with the fallback (generate-time inlining of the role skill), because this changes SPEC section 8 acceptance.
- **B4, Agent tool rejects the full model id.** Use the alias from I1 in the coordination skill. This is not a spec change.
- **B5, corpus parity fails** because the tokenizer differs. Fix the TypeScript side. If the Python decision itself looks wrong, open a B2 repair card. B5 never changes existing expectations.
- **B3, I1 Q4 shows SessionEnd payloads lack `session_id`.** Return to design (SPEC B-F5 depends on it).
- **Any discovered contradiction with SPEC-v2** goes to the designer-planner, design mode.
- **Release failure.**
  - Push or PR failure: stop and report.
  - Merge conflict on `main`: rebase is not authorized. Return to the coordinator.
  - Reinstall mismatch: re-run the reinstall. Never hand-patch the cache.

## 4. Dependency graph

Edges (ticket: prerequisites):

- P0: none
- I1: none
- B1: P0
- B2: B1
- B4: B1, I1
- B3: B2, B4
- B6: B4
- B5: B2, B3, B4, I1
- B7: B3, B5, B6
- INT: B1, B2, B3, B4, B5, B6, B7
- G1: INT
- RF: INT
- A1: INT
- A2: INT
- A4: INT
- A3: INT (conditional)
- L1: G1, RF, A1, A2, A4 (and A3 if it ran)

Readiness, derived from accepted prerequisites:

- P0 and I1 are ready at start.
- B1 becomes ready on P0.
- B2 is ready on B1. B4 is ready on B1 and I1, so B2 and B4 run in parallel.
- B3 is ready on B2 and B4. B6 is ready on B4 and runs in parallel with B2 and B3.
- B5 is ready on B3, because B2, B4 and I1 are already accepted by then.
- B7 is ready on B5 and B6.
- Every node becomes ready from accepted prerequisites, and no node depends on an unknown ticket.
- The graph is acyclic, checked by a topological sort (see the coordinator's evidence record).

Shared paths, each serialized by an edge:

| Path | Tickets, in order |
| --- | --- |
| `engine.py` | B4, then B3 |
| `hooks.py` | B2, then B3 |
| `hooks/claude.json` | B2, then B3 |
| `generate.py` | B1, then B4 |
| `test_packaging.py` | B1, then B4, then B6 |
| `test_engine.py` | B4, then B3 |
| `test_hooks.py` | B2, then B3 |
| `test_integration.py` | B3 only (B2 runs it but does not edit it) |
| `guard-corpus.json` | B2, then B5 (append only) |
| `types/index.d.ts` | B1, then B5 |
| `skills/**` | B4, then B6 |

`skills/orchestra/references/cli.md` belongs to B7 alone. B6 does not edit it.

Builder ticket count: 7 (B1 to B7). Checkpoints: R1, R2, R3, R4, R5. Final: RF, plus A1, A2, A4 (and A3 if needed).

## Coordinator rulings (2026-10-04)

- O1: keep `settings.agent: orchestra:orchestrator`.
- O2: the classic SessionEnd hook releases the lease; the mod's `session.end` only retires its heartbeat.
- O3: F6 evidence rebinding is deferred to 2.1.
- O4: `az repos pr update --status completed` stays behind the release check inside an armed run.
- O5: accept the 32,000-byte agent-file limit.
- The coordinator updates the global instruction file after release (user-authorized).
