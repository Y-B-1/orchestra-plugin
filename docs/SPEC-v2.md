# Orchestra 2.0.0 specification

Status: design revised after the P0 red team, user decisions U1 to U8, coordinator rounds 3 and 4, the round 5 repair after the second P0 red team, and the round 6 plan-level repair (no product decision changed). Settled product decisions are quoted under "Settled decisions" and are not reopened here. Open items are listed under "Open decisions" with a recommended default. Each is marked blocking or non-blocking.

- Starting artifact: branch `feat/v2-roles-guard-mods` at `8c1f1953666cc6d5e0e81579e3b37aa2212c26f1`. The tree was clean when inspected. The first SPEC/PLAN draft was written against `0ea2ece`.
- Policy revision: `AGENTS.md` blob `182417468e23bfa02c1afbd15bac1d031141a18e`.
- Baseline, observed at `0ea2ece` (no code changed since): `python3 -m unittest discover -s tests` ran 89 tests, OK, exit 0, in 78 s on Python 3.14.6. `python3 plugins/orchestra/scripts/generate.py --check` exited 0 (44 Codex package files, 27 native profiles). Claude Code 2.1.289 is installed. Claude Desktop embeds Claude Code 2.1.286.
- Platform facts: `docs/RESEARCH-v2.md` (I1, cited as R-Q1 to R-Q6).
- Finding IDs (F1 to F7) refer to the private 2026-10-04 audit. That audit is not in this repository and must never be copied into it.

Evidence labels used throughout:
- **OBSERVED**: read in source or produced by a command.
- **DOCUMENTED**: stated in vendor documentation cited in RESEARCH-v2.
- **REASONED**: inferred from source or documentation.
- **UNVERIFIED**: must be proven by a live check named in the plan.

## 1. Binding project rules (carried inline from AGENTS.md)

- Python code uses Python 3.11+ and the standard library only.
- Codex models are limited to `gpt-6.1-sol` and `gpt-6-luna`:
  - First implementation: Sol medium.
  - Independent judgment, red team and checked repair: Sol high.
  - Bounded code discovery and hygiene: Luna high.
- Claude models are limited to `claude-opus-5-5` and `claude-sonnet-5-5`, following the per-role matrix in `config/models.json`.
- Never publish private audit snapshots, credentials or personal paths in the repo. `scripts/build_release.py` rejects any tracked file that contains a macOS personal home path, GitHub or Anthropic token shapes, or private keys.
- Commits use explicit paths only. Never stage wholesale, stash, force push or hard reset.
- Generated files are never hand-edited:
  - Generated: `plugins/*/agents/*.md`, `plugins/*/profiles/codex/*.toml`, and everything under `plugins/orchestra-codex/`.
  - Sources: `plugins/orchestra/scripts/generate.py` and `plugins/orchestra/config/*.json`, plus the skill files the generator reads.
  - `python3 plugins/orchestra/scripts/generate.py --check` must pass.
- Test invalid inputs, stale evidence, independent review, reservations, hooks, and install/uninstall behavior.
- Do not claim arbitrary-shell or hostile-worker isolation.
- Check live hook, mod and profile discovery separately from unit tests.
- Detailed run evidence belongs in `docs/BUILD-LEDGER.md`.

Script paths. The Python modules live under `plugins/orchestra/scripts/orchestra_core/` (`guards.py`, `hooks.py`, `engine.py`, `routing.py`, `paths.py`, `profiles.py`). The CLI is `plugins/orchestra/scripts/orchestra.py`. The generator is `plugins/orchestra/scripts/generate.py`. The hook launcher is `plugins/orchestra/scripts/run-hook.sh`.

## 2. Scope

Eight areas are in scope:

- **A. Guard fixes**: the Python guard and hook adapter (`orchestra_core/guards.py`, `orchestra_core/hooks.py`, `run-hook.sh`, `hooks/claude.json`), including the outside-a-run release allowance that the v2 release path relies on (U1).
- **B. Bugs**:
  - the `.claude` path-index bug (F4) and its test;
  - the lease left active after a lost session (F5);
  - the hard-coded version in `test_packaging` (F3).
- **C. Role consolidation**: 14 Claude agent files and 13 Codex profiles become 7 roles. The roles are carried through `roles.json`, `models.json`, `generate.py`, engine role keys, skills, references and tests. The main session model follows the user's picker (U7).
- **D. Skills**: one skill per role plus one shared worker skill, written in our own words on a superpowers base (U6 as amended, section 3.3), preloaded via `skills:`, with mode procedures in mode files and no double-loading. Binding constraints stay inline. Source texts are selected through a reviewed capability matrix before any authoring (section 8.4). The coordinator skill gains executor-choice guidance (section 8.5).
- **E. Borrowed procedures**:
  - fix-round cap;
  - progress ledger and resume protocol;
  - review package;
  - standing-orders register;
  - PASS/ISSUES/BLOCKED report shape;
  - hedge-word verifier rule;
  - four final-review lenses plus a builder cleanup pass, with extra specialists gated by diff size.
- **F. Mods module (Claude Code only)**:
  - in-process guard;
  - session end handling;
  - standing-order injection;
  - `/orchestra-board` pane;
  - verdict toasts;
  - a function-hook API presence check (U2).
- **G. Engine changes**: the approved trim (U4), policy-narrowable review categories and a lease-free `status` (U3a), and evidence bound to owned paths plus HEAD (U3b).
- **H. Autonomous overnight mode** (U8): an engine- and hook-enforced loop the user switches on and off.

Also in scope: the version bump to 2.0.0, and the install-first release path (U1).

## 3. Settled decisions

### 3.1 Round 1 (verbatim from the first coordinator brief; not reopened, except where 3.2 supersedes)

1. Scope = all including Mods:
   - (a) guard fixes: allow non-force `git push`, `gh pr merge` etc. when no run armed (keep permit gate inside armed run); allow `git stash list/show`, `git restore --staged`; strip heredoc bodies before shlex; `az` gated only on `deployment ... create`; `switch -f` like `checkout -f`; drop bypassable `.claude/settings.json` Edit/Write block; narrow PreToolUse matcher to edit/shell tools; drop extra python probe in run-hook.sh; SubagentStart worker context only for orchestra:* agents.
   - (b) Bugs: `.claude` path-index bug (F4) and failing test_protected_patch_paths; lease left active after lost session (F5); test_packaging hard-coded version.
   - (c) Role consolidation 14 → ~7-8: merge builder-repair into builder (model override dispatch), red-teamer+auditor into one critic role with modes, fold founder-mind into designer-planner as product lens (+ shipped-surface audit as critic axis), gatekeeper+janitor+releaser into one Sonnet operator role with modes gate/cleanup/release, orchestrator kept as main-thread agent but not dispatchable as worker; keep effort variants (reviewer checkpoint, investigator code) ONLY if Agent tool path still needs them (Agent tool overrides model only; Workflow agent() accepts agentType+model+effort). Read-only roles get Edit/Write/NotebookEdit in disallowedTools. Apply consistently to Codex package/profiles with Codex model rules.
   - (d) Per-role skills split, preload via `skills:` frontmatter; stop double-loading (inlined brief + "Read references/…" lines with wrong relative paths); keep binding constraints inline.
   - (e) Borrow minimal: superpowers fix-round cap (rounds 1-3 same builder, 4 Opus repair, 5 breaker), progress ledger + resume protocol, review-package diff to reviewers; pstack standing-orders register pasted verbatim into briefs and PASS/ISSUES/BLOCKED report shape; OMC verifier rule rejecting "should/probably/seems"; gstack diff-size-gated specialist review.
   - (f) Mods module (Claude only): in-process guard via tool.call failing closed, session.end releasing lease, agent.spawn injecting standing orders and refusing reviewer dispatch by builder's own session where feasible, /orchestra-board pane, verdict toasts. Python guard stays for Codex; design how two guards avoid double-firing on Claude and share one rules table/test corpus; pin/declare min Claude Code version.
2. Engine: fix bugs only; NO trimming. The spec carries an "Engine trim proposal (not implemented)" section. **Superseded by U3 and U4.**
3. Version bump: semver. Removing agent names is breaking, so the version becomes 2.0.0. All manifests must agree, and tests assert equality rather than a literal.
4. Release is authorized by the user: push the branch, open a PR, merge to main, and reinstall locally for Claude Code and Codex. It is planned as the final operator/release ticket, executed by the coordinator. **Sequencing refined by U1.**

The 1(f) clause "pin/declare min Claude Code version" is superseded by U2. The 1(f) clause "refusing reviewer dispatch by builder's own session where feasible" is met structurally (section 10.4).

Derived from decision 1(c), not a new choice: the effort variants stay. OBSERVED: the Orchestra skill and the user's global rules still dispatch single units through the Agent tool. The Agent tool can override the model but not the effort (R-Q2). So `investigator-code` (Sonnet low) and `code-reviewer-checkpoint` (Opus medium) remain as generated variant agent files. Workflow `agent()` dispatch may instead pass `agentType` plus `effort` against the base role.

### 3.2 Round 2 (user decisions U1 to U8, as given by the coordinator on 2026-10-04)

- **U1, install v2 first.** After gates, final review and audits pass on the frozen candidate, the user installs v2 from the local branch and restarts the session. The coordinator then pushes, opens the PR and merges, running v2 hooks with no armed run. The plan specifies exact local-install commands, handles the name collision with the installed `orchestra@orchestra-distribution`, and names the restart point. The v2 guard (A1) must allow, outside an armed run: non-force `git push` of a branch and a tag, `gh pr merge --squash --delete-branch`, and `gh release create`. Inside an armed run the permit gate still applies. After merge, reinstall from GitHub main for Claude Code and Codex. Bypassing the guard with `gh api` merges or MCP/terminal tools is forbidden.
- **U2, API gate.** Mods gate on API presence, not on a version floor. Desktop embeds Claude Code 2.1.286 and fires function hooks because the user's settings set `CLAUDE_CODE_ENABLE_FUNCTION_HOOKS=1`. The coordinator updates the Desktop app at the very end, as a final L1 coordinator step outside the tickets, since it restarts the app.
- **U3, pulled into 2.0.0.** (a) X5: let policy narrow the 7 final-review categories (fix the union), and stop `status` printing the lease token. (b) O3/F6: bind evidence to the card's owned paths plus HEAD instead of a whole-repo hash. Each gets a ticket with owned paths and tests.
- **U4, engine trim "option A" in 2.0.0.** Remove: (1) the `review-groups` CLI and `routing.review_groups`; (2) the `audit-policy` CLI and `routing.audit_axes`, keeping the audit-axis rules as coordination prose; (3) the `route` CLI, keeping `config/flow.json` as documentation data; (4) `policy.reserved_ports` and `policy.denied_tools` from the default policy; (5) narrow contract-hash invalidation so only role/mode set changes invalidate a live run. KEEP: release permits, autonomy ledger, lease, reservations, gates/secret scan, and the 7-category coverage check.
- **U5, global instruction files.** The coordinator (not workers) updates `~/.claude/CLAUDE.md` and `~/.codex/AGENTS.md` after release. The required content is listed in the PLAN coordinator rulings.
- **U6, role skills built on superpowers.** Base every Orchestra skill (worker role skills and the coordinator skill) on obra/superpowers (MIT, https://github.com/obra/superpowers), with the best parts of mattpocock/skills (MIT) and garrytan/gstack (MIT) on top. Investigation I2 fetches the upstream skill texts at pinned commit SHAs; the coordinator records the SHAs and a mapping table in `docs/RESEARCH-v2.md`. Adapt the text to Orchestra vocabulary, roles, engine and approval boundaries; do not paste blind. Avoid: the using-superpowers 1% bootstrap injection; the never-pause default; gstack's preamble, telemetry and personas. Add a THIRD-PARTY-NOTICES file with the MIT texts and pinned SHAs. Each adapted skill gets a one-line source header. Keep each role SKILL.md lean, with mode detail in on-demand references, under a named and tested byte budget. Each skill ticket's acceptance includes a phrase test for the key procedure.
- **U6 amendment, one skill per role, in our own words.** Each of the 7 roles gets exactly one skill, written as our own derived version. It merges the Superpowers base with the chosen Pocock, gstack and Claude built-in content into one coherent document. Do not stack several upstream skills on a worker. `SKILL.md` holds the always-loaded core, under the byte budget. Reference files inside the same skill folder hold the per-mode procedures, and the worker reads one only when its mode needs it. The agent file preloads only that one role skill. Added sources: Pocock `skills/engineering/*` (improve-codebase-architecture, codebase-design, domain-modeling, code-review, tdd, diagnosing-bugs, grill-with-docs, to-spec, to-tickets, prototype, triage, handoff, retro, writing-for-agents) and `productivity/grill-me`; gstack `cso`, `deslop-shared-libs` and `health` (content only); the Claude Code built-in `security-review` and `simplify` skills, folded in as content, not as a dependency. New review lenses: every integration's final review runs four separate code-reviewer lenses: correctness; architecture (deep modules, coupling, domain fit); security; cleanliness/leanness (dead code, duplication, needless abstraction, efficiency). Confirmed findings from lenses 2 to 4 go to a `builder` `cleanup` mode, which applies a lean-and-simplify pass at the end of the run, followed by fresh review. Add `cleanup` to builder's modes (Claude Sonnet 5.5 medium, Codex Sol medium). The 4 lenses always run on the final review; extra specialists stay gated.
- **U7, main-session model follows the picker.** Remove `model` and `effort` from the generated orchestrator agent file. Keep `settings.agent: orchestra:orchestrator`. This revises O1. Add a live check that the main session reports the picker's model. Matrix docs say the orchestrator row is "user's selection".
- **U8, autonomous overnight mode.** The user can switch it on and off. It is enforced by the harness and engine, not just text, and built on the existing engine `autonomy` command and the Stop-hook continuation. Toggle: CLI `orchestra.py autonomy arm|disarm|status`; on Claude, a mod command `/orchestra-autonomy on|off|status` that calls the same entry; `arm` refuses unless a ledger exists. Ledger `<state>/autonomy.md`, created from a template by `arm`, holds goal, completion criteria (runnable checks), max passes, max stalls (a pass with no newly accepted card), a wall-clock deadline, and approval boundaries. While armed, with the ledger intact and no cap reached, the classic Stop hook blocks and tells the coordinator to continue with the next ready card; on a cap, the deadline, completion, or an approval boundary it stops. Approval boundaries are hard and not configurable: release, merge, push to the default branch, deletion, credential entry, and any engine-gated action. At a boundary the run parks that card and keeps working on other cards. Release stays gated even when armed. On stop, a morning report (accepted, parked with reason, failures) goes to `<state>/progress.md` and is shown on the next SessionStart; with mods, also a toast and status band. `arm` checks and reports, without changing them, a permission mode that will not stall on prompts and Desktop keep-awake (a user step). Tests: engine tests for caps, deadline, boundary park and tampered ledger; hook tests for Stop continue and stop; a live check that one pass continues and the cap stops the run. The project-kit `orchestra-autonomy-loop.sh` hook is replaced by the plugin version; project cleanup is a separate coordinator workstream after release.

### 3.3 Round 3 (coordinator skills-delivery decision, probe-verified on Claude Code 2.1.289, 2026-10-04)

Probe evidence reported by the coordinator (scratchpad probe plugin, `claude -p`, Sonnet 5.5 subagent), recorded here as OBSERVED by the coordinator and not re-run by design:
- Agent frontmatter `skills: [alpha, beta, missing-skill]`: alpha and beta content both present with no tool call; `missing-skill` skipped silently with no error.
- A core skill saying "read references/<mode>.md where <mode> is the brief's Mode line": the worker read `references/repair.md` in 3 of 3 runs.
- A non-preloaded skill whose description matched the task, with the Skill tool allowed: invoked in 0 of 3 runs.
- Mods: `AgentSpawnInput` lets a hook rewrite only prompt, description, subagentType, model, background and cwd. `skills` exists only on `AgentSpec` (`agent.register`). There is no per-spawn skill injection.

Decisions (as given):
1. Each role agent preloads exactly two skills via frontmatter: `orchestra-worker` (shared worker contract: not alone, preserve sibling edits, no delegation/coordinator state, evidence + STATUS/ARTIFACT report contract, verifier wording rule E6) and its role skill (orchestra-investigate, -design, -critique, -build, -review, -operate). Orchestrator keeps the `orchestra` skill. No duplication of the worker contract inside role skills.
2. Mode procedures live in `skills/orchestra-<role>/references/<mode>.md`. The role SKILL.md core stays short and instructs: read references/<Mode>.md before work; if the brief has no Mode line or the file is missing, stop BLOCKED. Briefs must carry a `Mode:` line (add to briefs reference and the card schema check if cheap).
3. No reliance on model-invoked skills or the Skill tool inside workers; no mods agent.spawn skill injection. Model/effort per dispatch stays: variant agent files (investigator-code, code-reviewer-checkpoint) plus the Agent tool `model` override for builder repair round 4.
4. Add a generate.py/test check: every name in an agent's `skills:` resolves to `skills/<name>/SKILL.md` without `disable-model-invocation: true`, and every mode named in config resolves to a references file. Keep the existing live sentinel check in B4, extended to assert both preloaded sentinels and one mode-file read.
5. Content sourcing: Superpowers is the base; graft only Pocock improvements that add something; Claude built-ins security-review and simplify feed review/build cleanup; gstack only for cleanup/deslop ideas, no preamble/telemetry/personas. No upstream skill is embedded whole; each role skill and mode file cites its upstream sources (MIT notice in NOTICE file). A suggested source and mode map accompanied it.

How this revision applies round 3 against round 2:
- Decision 1 changes the U6 amendment's "the agent file preloads only that one role skill" to two skills per worker. Each role still has exactly one role skill, and no upstream skills are stacked. Applied; flagged as O9, confirmed in round 4 (section 3.4).
- The suggested map renamed persisted modes (for example builder `feature`, critic `redteam`, operator `gates`/`hygiene`), added modes (investigator `bug`, designer-planner `architecture`) and dropped designer-planner `product` and critic `surface`. Modes are persisted card identifiers, and decision 1(c) requires the product lens and the surface axis. This revision keeps the section 7.1 modes, folds bug diagnosis into `code.md` and the architecture method into `design.md`, and uses the map for source assignment only. Flagged as O10, confirmed in round 4.
- Decision 5 limits gstack to cleanup/deslop ideas, while the U6 amendment names gstack `cso` for the security lens. This revision keeps `cso` as an idea-level security candidate and flags the conflict as O11, confirmed in round 4.
- "NOTICE file" is read as the U6 file name `THIRD-PARTY-NOTICES`.

### 3.4 Round 4 (user decisions and a coordinator probe, 2026-10-04)

Decisions (as given by the coordinator):
- **A. Defaults confirmed.** "O9 (two preloaded skills per worker), O10 (keep section 7.1 modes; map is source assignment only), O11 (gstack cso only if it adds to the Claude security-review checklist). Option A trim stays in 2.0.0." Nothing moves to 2.1: "every in-scope item ships in 2.0.0; exclusions stay exclusions." (first clause paraphrased)
- **B. Skill curation is a selection, not an import.** "Add a card before any skill authoring, after I2: a capability matrix in docs/RESEARCH-v2.md (or docs/SKILL-SOURCES.md)." Rows are the capabilities Orchestra roles need; columns are the candidate texts in Superpowers, Pocock, gstack and the Claude built-ins security-review and simplify. Each row records the winner, grafts from runners-up, any gap filled from outside Superpowers, and rejected candidates with one-line reasons. "Superpowers wins ties; another repo wins only when its version is better for a subagent." Skills that do not fit subagents are rejected with a reason, not silently dropped. "A critic reviews the matrix before authoring starts." Authoring method: "each role skill and mode file is new text in Orchestra vocabulary, written from the matrix winners. No concatenation, one voice, no rule repeated across files (worker-contract rules live only in orchestra-worker), within the byte budget." Add "a critic cohesion review over all skill files (contradictions, duplicates, rules that conflict with the engine or briefs, missing provenance header)." Amended by the user correction in section 3.5: the matrix is a synthesis with a base per capability, not a contest with a winner.
- **C. Executor choice guidance** in the coordinator `orchestra` skill, as a new section with a phrase test. Three executors: inline; single Agent dispatch; Workflow, the default for 2+ independent units "whenever the host has the Workflow tool; the user's standing opt-in makes it the default with or without ultracode." Workflow mechanics: each `agent()` uses `agentType: 'orchestra:<role>'`, passes `effort` per the matrix, and carries a brief with a `Mode:` line. The coordinator reserves every card in the engine before starting the workflow script and records each agent's report against its card. Concurrent editors use `isolation: 'worktree'`. Hosts without Workflow (Codex) fall back to parallel role dispatch. The variant agent files stay for the Agent tool path.

Probe evidence reported by the coordinator (Claude Code 2.1.289, `claude -p`, scratchpad probe plugin), recorded as OBSERVED by the coordinator and not re-run by design: a Workflow `agent()` with `agentType: 'probe:probe'` had both preloaded skill sentinels and read `references/repair.md` from the brief's `Mode:` line (1 of 1 run).

How this revision applies round 4:
- O9, O10 and O11 are settled (section 13).
- B becomes section 8.4 and PLAN tickets MX (matrix), MXR (matrix critic) and SC (cohesion critic). The matrix lives in `docs/SKILL-SOURCES.md`, the brief's alternative name, so that a single ticket owns it; `docs/RESEARCH-v2.md` stays the coordinator's record of I2.
- C becomes section 8.5, written by S1.
- The round-4 repair model override stays on the Agent tool path (E1, R-Q2). A per-call `model` option on Workflow `agent()` is UNVERIFIED, so a round-4 repair card is dispatched with the Agent tool, not inside a workflow script.

### 3.5 Round 5 (P0 red team at `be83849`, user correction, coordinator rulings, 2026-10-04)

User correction (as relayed by the coordinator): "this is synthesis, not a competition. No 'winner'." Per capability the matrix records a **Base** (Superpowers, or the best-fitting source when Superpowers has none), **Merged in from others** (each stronger or more thorough element, its source, and why), the gaps filled, and synthesis notes. "Rejected" means only that an element conflicts with Orchestra (the avoid list, never-pause, personas, telemetry, host features subagents lack) or adds nothing. "The result is our own skills." Applied in 8.4.

The user is asleep and authorized an overnight run. The coordinator gave the following rulings for the red-team findings. Where a ruling reads a user decision, it is recorded as REASONED in section 13 (O12 to O14); the rest are technical or plan-level.
- SF1: a linked worktree of an armed repository resolves armed state from the main worktree (A15). It strengthens U8's hard boundaries. O13.
- SF2: the E1 fix-round cap and the E7 specialist size gate live only in `skills/orchestra/`. Worker mode files describe only the worker's own round or brief (8.2, section 9 acceptance).
- SF3: a fixed `Source:` header grammar, with tests that every SHA and idea-level name is credited in THIRD-PARTY-NOTICES and that every matrix destination file carries a header (8.2, 8.3).
- SF4: the matrix gains a column "Existing Orchestra / other", and every 8.2 file must appear as a destination (8.4).
- SF5: autonomy boundary details as defaults, confirmed before B10 acceptance. O12.
- SF6: executor phrases and the live check (8.5).
- SF7: the cohesion critic also reads the matrix and the avoid list (8.4).
- SF8: upstream texts at the pinned SHAs stay outside the repository; writers work only from them (8.4).
- SF9: every Codex worker profile carries both skill sentinels (8.3).
- SF10: `docs/skill-authoring.md` is dropped. O14.
- Feasibility rulings FF1 to FF3 (this build is not tracked in the engine; coordinator-made worktrees; the L1 state reset) are plan-level and live in PLAN 0.1, 0.3 and L1. Section 8.5's engine reservation stays as v2 product behavior.

## 4. Glossary

| Term | Meaning |
| --- | --- |
| Role | A dispatchable worker definition in `config/roles.json`. Its id is the persisted `role` field of an engine card. |
| Mode | One of a role's declared modes. Persisted as the card `mode`; the engine rejects undeclared modes. |
| Preset | A per-mode model/effort selection in `config/models.json`. |
| Variant | A generated agent file (Claude) or profile (Codex) for a preset whose model or effort differs from the role default and cannot be selected at dispatch. Named `<role>-<preset>` (Claude) or `orchestra_<role>_<preset>` (Codex). |
| Dispatch override | Selecting a preset's model at dispatch time instead of through a variant. Claude uses the Agent tool `model` parameter or Workflow `agent({model})`. Used only for `builder` repair round 4 on Claude. |
| orchestrator | The main-thread coordinator agent, selected by `settings.agent`. It is never dispatched as a worker. Its model and effort are the user's picker selection (U7). |
| investigator | Read-only discovery role. Modes: `code`, `docs`. |
| designer-planner | Design and planning role. Modes: `design`, `plan`, and `product`. `product` is the former founder-mind design dossier, the "product lens". |
| critic | Read-only independent challenge and conformance role. Its modes are listed in the row after this one. |
| critic modes | Plan challenge: `requirements`, `feasibility`, `scope`, `judge` (former red-teamer). Conformance: `spec`, `standards`, `ledger` (former auditor). Shipped surface: `surface` (former founder-mind audit). |
| builder | Implementation role. Modes: `implementation`, `frontend`, `sensitive`, `mechanical`, `repair`, `cleanup`. |
| builder cleanup | The end-of-run lean-and-simplify pass on confirmed findings from final-review lenses 2 to 4. Not repo hygiene. |
| code-reviewer | Read-only exact-diff review role. Modes: `checkpoint`, `final`. |
| Lens | A named final-review focus given in the code-reviewer brief: `correctness`, `architecture`, `security`, `cleanliness`. A lens is a brief field and a reference file, not a mode. |
| Specialist | An extra critic or code-reviewer brief for a surface such as frontend or visual work, added only under the E7 size gate. |
| operator | Sonnet-medium operations role. Modes: `gate` (former gatekeeper), `cleanup` (former janitor, repo hygiene and retro), `release` (former releaser). |
| Role skill | The one role-specific skill directory a role preloads (section 8). |
| Worker skill | `skills/orchestra-worker/`, the shared worker contract every worker preloads beside its role skill (section 8.1). |
| Mode file | `skills/<role skill>/references/<mode>.md`, the procedure a worker reads before work according to the brief's `Mode:` line. |
| Capability matrix | `docs/SKILL-SOURCES.md`: per needed capability, the base text, the elements merged in from other sources, gaps filled, synthesis notes, rejections and destination files (section 8.4). With the pinned upstream texts, the only input from which skill text is written. |
| Base | The upstream text a capability's skill text is built on: Superpowers, or the best-fitting source when Superpowers has none. |
| Main worktree | The worktree whose `.git` directory is the repository's common git directory: the parent of `git rev-parse --path-format=absolute --git-common-dir`. Run state lives under it. |
| Executor | How the coordinator runs a unit of work: inline, a single Agent dispatch, or a Workflow script (section 8.5). |
| Armed run | A repository whose Orchestra state file exists with `session.active == true`. If there is no state file, or the session is inactive, the run is unarmed. |
| Autonomy | The U8 overnight mode. "Autonomy active" means an armed run whose state has `autonomy.active == true` with an intact ledger snapshot. |
| Autonomy ledger | `<state>/autonomy.md`, the U8 ledger file. |
| Approval boundary | An action autonomy never takes (section 12.4). The card is parked instead. |
| Parked card | A card in state `parked` with a reason. It holds no capacity and no reservation, and its dependents stay blocked. |
| Morning report | The summary written when autonomy stops (section 12.6). |
| Permit | The engine's release permit for an exact remote, target, argv and artifact under the active lease. Unchanged. |
| Owned-path scope | The set of repository paths a card reserves (its files plus its repair chain's files). For a checkpoint review, the union over the covered cards. |
| Guard rules table | `plugins/orchestra/config/guard-rules.json`. The single data table of tool sets, wrappers, git deny rules, release-class and boundary-class rules, and protected paths. Both guards read it. |
| Guard corpus | `plugins/orchestra/config/guard-corpus.json`. A list of cases consumed by the Python unittest and by the mod's `claude plugin test`. Its class vocabulary is fixed in section 5.1. |
| Liveness marker | A per-session JSON file the mod writes and heartbeats. It tells the Python PreToolUse hook on Claude that the in-process guard is active for that session. |
| Plugin standing orders | The generic worker contract, now the worker skill `skills/orchestra-worker/SKILL.md`, preloaded by every worker. |
| Project standing-orders register | `standing-orders.md` in the run state directory. The coordinator writes it, copying the binding project rules verbatim. It is pasted verbatim into each brief, by the mod when loaded or by the coordinator otherwise. |
| Review package | Files the coordinator prepares for each review card, outside the repository: base and head SHAs, `git diff --stat`, the full diff, the ticket's acceptance criteria, and the changed paths. |
| Fix round | One repair attempt on a ticket after an independently checked BLOCKED review. |
| Breaker | Round 5. Repair stops, and the ticket routes to critic `judge` plus design or planning, with user escalation. |
| Progress ledger | `progress.md` in the run state directory. An append-only event log used by the resume protocol and the morning report. |

## 5. Area A: guard fixes

The current guard is in `orchestra_core/guards.py` (`classify_command`) and `orchestra_core/hooks.py` (`handle_event` PreToolUse). Required behavior is listed below. Classification stays independent of run state. The hook layer applies run state.

| ID | Behavior | Today (OBSERVED) |
| --- | --- | --- |
| A1 | When the run is unarmed, commands of class `release` and `release-multi` are allowed. This covers non-force `git push` of one branch or one tag to one remote (for example `git push origin feat/v2-roles-guard-mods` and `git push origin v2.0.0`), `gh pr merge N --squash --delete-branch`, `gh release create v2.0.0 <assets> --verify-tag ...`, `npm/pnpm publish`, provider deploys and `az deployment ... create`, including inside a multi-segment command such as `git push origin x && gh pr create`. Inside an armed run the permit gate is unchanged: `engine.check_release` must return a current permit, and `release-multi` is denied. With autonomy active both release classes are denied (section 12.4). A state file that exists but fails to load is treated as armed with no permit: release classes deny (fail closed). | `hooks.py` denies every release when `engine is None` (F1). `gh pr create`, `git tag v2.0.0` and `gh api ...` already classify `allow` (OBSERVED via `orchestra.py classify`). |
| A2 | Rules that always deny stay in force whether or not a run is armed: force push, mirror, `+refspec`, `--all`/`--tags`/`--delete`, multiple destinations, `reset --hard`, `clean -f` without `-n`, `branch -D`, wholesale `add`, `commit -a`, and wholesale checkout/restore. | Unchanged |
| A3 | `git stash list` and `git stash show [args]` are allowed. Every other stash form (bare, push, pop, apply, drop, clear, save, branch, create, store) stays denied. | All stash forms denied |
| A4 | `git restore --staged <pathspec>` (alias `-S`) is allowed for any pathspec, including `.`, when neither `--worktree` nor `-W` is present. `restore --worktree`/`-W` with wholesale pathspecs stays denied. | `restore --staged .` denied |
| A5 | Heredoc bodies are removed before quote-aware segmentation and shlex. The operators are `<<WORD`, `<<-WORD`, `<<'WORD'` and `<<"WORD"`, and the body ends at the line equal to WORD (leading tabs are stripped for `<<-`). Safety rule: when the command consuming the heredoc is a shell interpreter (`sh`, `bash`, `zsh`, `dash`, `ksh`, including through the existing wrappers), the body is classified recursively as a script. A destructive body still denies. A heredoc with no terminator is malformed and denies. | Apostrophes in bodies raise "Malformed shell quoting" |
| A6 | `az` is release-class only when both `deployment` and `create` appear in its words. `az deployment group show`/`list`/`what-if` are allowed. `az repos pr update ... --status completed` stays release-class (O4). | Any `az ... deployment ...` is release-class |
| A7 | `git switch -f`, `--force` and `--discard-changes` deny with the same reason as `checkout -f`. | Allowed |
| A8 | The protected-path check no longer protects `settings.json` under `.claude` (or `.codex`). Still protected: `.claude/hooks.json`, `.codex/hooks.json`, `.codex/config.toml`, `orchestra-*`/`orchestra_*` files under a harness `agents/` directory, any `.orchestra` path component, the run state directory, and the mods marker directory (A12). Exception: the coordinator-authored `progress.md`, `standing-orders.md` and `autonomy.md` at the state-directory root. | `settings.json` is protected in every session and is bypassable via Bash (F7) |
| A9 | The `PreToolUse` matcher in `hooks/claude.json` narrows from `.*` to `Bash\|Edit\|Write\|MultiEdit`. `hooks/codex.json` is unchanged, because Codex matcher semantics are UNVERIFIED and the Codex advisory delegation check relies on `spawn_agent` reaching the hook. | `.*` on both harnesses |
| A10 | In the common case `run-hook.sh` starts Python once. It tries the versioned names `python3.14` down to `python3.11` via `command -v` with no probe, and execs the first one found. Only when none exist does it fall back to plain `python3`, with the version probe. The Homebrew PATH prefix stays. A new `--cli` first argument execs `orchestra.py` with the remaining arguments, so the mod reuses the same interpreter discovery. | Probe plus exec on every candidate (2 launches) |
| A11 | `SubagentStart` returns `WORKER_CONTEXT` only when the payload `agent_type` starts with `orchestra:`. Otherwise it returns `{}`. `SessionStart` worker detection is unchanged. Owned by B3 (with the `test_session_context_only` update), not B2. | Returns worker context for every subagent |
| A12 | Mod handshake. On harness `claude`, PreToolUse first reads the liveness marker (section 10.3). The marker must exist for the payload `session_id`, be fresh (heartbeat less than 15 s old), and carry a `rules_sha256` equal to the SHA-256 of this copy's `guard-rules.json`. If so, the hook returns `{}` before any git or engine work. `--from-mod` skips the marker check. A `session_id` that does not match `^[A-Za-z0-9_-]{1,128}$` skips the marker check, and Python guards. Marker trust: the marker directory `${XDG_STATE_HOME:-$HOME/.local/state}/orchestra/mods/` is a protected path for Edit, Write, MultiEdit and `apply_patch`. A Bash write to it is not detected; that limit is documented (X8). | New |
| A13 | `guards.py` reads the guard rules table at import, and its decisions must match every corpus case. | Rules hard-coded |
| A14 | Boundary class. `classify_command` returns class `boundary` with category `delete` for: `rm` and `rmdir` (any flags), `unlink`, `find ... -delete`, `git rm`, `git branch -d`, `git tag -d`, `git worktree remove` and `git worktree prune`, `gh repo delete`, `gh release delete`. It returns class `boundary` with category `merge` for local `git merge`, `git pull`, `git rebase` and `git cherry-pick`. The hook allows `boundary` unless autonomy is active (section 12.4). | New |
| A15 | Linked-worktree state. When the payload `cwd`'s toplevel has no run state, the hook resolves state from the main worktree (glossary). If that run is armed, the hook applies its class mapping, its permit check and its autonomy state, exactly as in the main checkout. A bare common directory, or a main worktree with no state, stays unarmed. Classification is unchanged; only the state lookup moves. REASONED (O13). | A linked worktree has its own toplevel and no state, so it is treated as unarmed (SF1) |

Procedural limits, not guard rules (no isolation claim): `gh api` calls that merge or release, and MCP or terminal tools that push or merge, classify `allow` or never reach the shell guard. U1 forbids using them to bypass the guard. The L1 procedure and the coordinator skill state the rule; the guard does not enforce it.

### 5.1 Guard corpus class vocabulary (B2/B5 parity contract, fixed now)

Each corpus case is `{id, input, class, category?}`. `input` is `{command}` for a shell case or `{tool, path, cwd?}` for an edit case. `class` takes exactly one of five values. `category` is required only for `boundary` (`delete` or `merge`).

| Class | Meaning | Unarmed | Armed, autonomy off | Armed, autonomy active |
| --- | --- | --- | --- | --- |
| `allow` | No rule applies | allow | allow | allow |
| `deny` | An always-deny rule, a malformed payload, or a protected path | deny | deny | deny |
| `release` | One release-class segment, alone | allow | permit check | deny |
| `release-multi` | A release-class segment inside a multi-segment command | allow | deny | deny |
| `boundary` | A deletion or local merge (A14) | allow | allow | deny, except category `merge` when the current branch is not the default branch |

The default branch is read from `git symbolic-ref --short refs/remotes/origin/HEAD`, falling back to `main`. The current branch is the branch checked out in the payload `cwd`'s worktree (`git -C <cwd> symbolic-ref --short HEAD`), also in a linked worktree; it is never read from the main worktree whose state A15 resolves. The branch check runs only when autonomy is active. Both runners (Python unittest and `claude plugin test`) assert the class, and the category where present. Adding a class is a design change.

Acceptance criteria for area A, each observable as a unittest or command:

- Every row A1 to A15 has at least one passing test. A1 needs tests in both directions: allowed unarmed (branch push, tag push, `gh pr merge N --squash --delete-branch`, `gh release create`), and denied armed without a permit. A1 also needs a test that an unloadable state file denies release.
- A5 has a test proving `bash <<'EOF'\ngit reset --hard\nEOF` denies, and that `cat <<'EOF'\nit's fine\nEOF` allows.
- A12 has tests for a fresh marker (skip), a stale marker, a wrong `rules_sha256`, a malformed `session_id`, `--from-mod` (each guards), and an Edit to a file under the marker directory (deny).
- A15 has tests in `test_hooks.py` and `test_integration.py` on a temporary repository with a linked worktree (`git worktree add`): with the main checkout armed, a push from the linked worktree's `cwd` without a permit denies; with the main checkout unarmed, it allows; a bare common directory stays unarmed. The linked-worktree command strings are also corpus cases with their state-independent class. Corpus cases carry no run state (5.1), so the state lookup is tested in Python only; the mod delegates every state-dependent class to Python (10.3), so it inherits A15.
- The corpus uses only the five classes, and every case passes `tests/test_guard_corpus.py`.
- `python3 -m unittest discover -s tests -p 'test_hooks.py'` and `... -p 'test_guard_corpus.py'` exit 0.
- Latency is measured and reported as evidence, with no pass/fail threshold: 10 consecutive allowed Bash PreToolUse invocations through `run-hook.sh`, before and after.

## 6. Area B: bugs

- **B-F4.** `_protected` must check every occurrence of `.claude`/`.codex` in the resolved path's parts, not only the first. `test_protected_patch_paths` and `test_underscore_profile_protected` pass an explicit `cwd` (a temp directory). A new regression test sets `cwd` to a temp directory nested under a `.claude/plugins/...` path and asserts that an Edit to `.claude/hooks.json` relative to that cwd is denied. It uses `hooks.json`, not `settings.json`, because A8 stops protecting `settings.json`.
  - OBSERVED: at `0ea2ece` the existing test passes in this clone, because the clone is not under `~/.claude`. Per the audit it fails when the clone lives under `~/.claude` (F4).
- **B-F5.** A run must not stay armed after its harness session ends.
  - The SessionStart hook adds the harness `session_id` to the coordinator context, as a line telling the coordinator to pass `--harness-session <id>` to `start`.
  - `orchestra.py start --harness-session ID` records `session.harness_session` in run state. The key is optional, so state without it stays valid.
  - `hooks/claude.json` registers `SessionEnd` with `"timeout": 10`. SessionEnd hooks share a 1.5 s budget unless a hook sets a timeout, up to 60 s (DOCUMENTED, R-Q4). B3 measures the SessionEnd latency over 10 runs and records it.
  - `handle_event('SessionEnd')` reads `reason` and applies the reason policy (O6):
    - `clear` and `resume`: no release.
    - `logout`, `prompt_input_exit`, `other`, and a missing or unknown reason: release.
  - To release, it builds the engine for the payload `cwd` and calls a new `Engine.end_harness_session(session_id)`. When the active session's `harness_session` equals the payload `session_id`, that call does what `interrupt` does (inactive, permits cleared, autonomy cleared, outcome `ended`). Otherwise it does nothing.
  - The call is idempotent. A run started without `--harness-session` is unaffected (legacy and manual CLI behavior, with Codex `Interrupt` unchanged).
  - After a session ends, `start` and `start --new-run` succeed without the lease being copied out of `status` (which no longer prints it, section 11.2).
  - Lost-lease recovery is documented: end the harness session, which releases the lease through SessionEnd; for a run without a harness session, read `state.json` in the state directory. The lease is a consistency token, not a secret.
  - New CLI `orchestra.py where` prints `{repo, state, standing_orders: bool}` and never prints the lease. The mod uses it.
  - UNVERIFIED: whether `/clear` keeps the same `session_id`. B3 captures it live. If `/clear` changes the id, O6 returns to design before B3 acceptance, because the no-release default would then leave a run bound to a dead id.
- **B-F3.** `test_packaging` asserts that the following versions are equal, read from the files themselves with no literal in the equality assertion:
  - `plugins/orchestra/plugin.json`
  - `plugins/orchestra/.claude-plugin/plugin.json`
  - `plugins/orchestra/.codex-plugin/plugin.json`
  - `plugins/orchestra-codex/.codex-plugin/plugin.json`
  - the `orchestra` entry in `.claude-plugin/marketplace.json`

  The `2.0.0` value is checked in one place: the release ticket's command, not the unittest.
- **B-F2.** The installed cache was missing the PATH line. No source change is needed. The release ticket verifies that each installed cache copy is byte-identical to the tree it was installed from.

Acceptance: `python3 -m unittest discover -s tests -p 'test_hooks.py'`, `-p 'test_engine.py'`, `-p 'test_integration.py'` and `-p 'test_packaging.py'` exit 0. F5 has an integration test: start with a harness session, deliver a SessionEnd payload with reason `prompt_input_exit`, then `start --new-run` succeeds. Further tests: reason `clear` leaves the run armed; another id leaves the run armed; a repeated SessionEnd is idempotent.

## 7. Area C: role consolidation

### 7.1 Final roles

| Role | Modes | Claude default | Claude variants (files) | Codex default | Codex variants (profiles) | Tools disallowed (Claude) |
| --- | --- | --- | --- | --- | --- | --- |
| orchestrator | main | user's selection (no `model` or `effort` in the file) | none | no profile (unchanged) | none | none (main thread) |
| investigator | code, docs | sonnet-5-5 medium | `investigator-code` (sonnet low) | sol medium | `orchestra_investigator_code` (luna high) | Agent, Edit, Write, NotebookEdit |
| designer-planner | design, plan, product | opus-5-5 high | none | sol high | none | Agent |
| critic | requirements, feasibility, scope, judge, spec, standards, ledger, surface | opus-5-5 high | none | sol high | none | Agent, Edit, Write, NotebookEdit |
| builder | implementation, frontend, sensitive, mechanical, repair, cleanup | sonnet-5-5 medium | none (repair round 4 = dispatch override `claude-opus-5-5`; cleanup = default) | sol medium | `orchestra_builder_repair` (sol high); cleanup = default | Agent |
| code-reviewer | checkpoint, final | opus-5-5 high | `code-reviewer-checkpoint` (opus medium) | sol high | `orchestra_code_reviewer_checkpoint` (sol medium) | Agent, Edit, Write, NotebookEdit |
| operator | gate, cleanup, release | sonnet-5-5 medium | none | sol medium | `orchestra_operator_cleanup` (luna high) | Agent |

The result is 7 roles, 9 Claude agent files (down from 14) and 10 Codex profiles (down from 13): the 6 role defaults other than orchestrator (Codex generates no orchestrator profile, OBSERVED) plus the 4 named variants. The builder `cleanup` preset equals the builder default on both harnesses, so it adds no file. `generate.py --check` therefore reports 19 native profiles instead of 27.

Model mapping checks against the current matrix:
- Every former Opus-high worker role (founder-mind, red-teamer, auditor) maps to an Opus-high role.
- Every former Sonnet-medium operations role maps to operator, which is Sonnet medium.
- Codex Luna stays limited to `investigator/code` and hygiene (`operator/cleanup`), per AGENTS.md.
- The orchestrator row reads "user's selection" in `docs/models.md` and in the generated matrix docs (U7).

Why these names:
- `critic` covers both the before-build challenge and the after-build conformance work without implying either one.
- `operator` covers gate, cleanup and release.
- `investigator`, `designer-planner`, `builder` and `code-reviewer` keep their v1 names to limit churn.
- Considered and rejected: `reviewer` for critic (it collides with code-reviewer), `verifier` (it implies machine proof), and `ops` (too terse for an agent listing).

### 7.2 Mechanics

- **models.json schema.**
  - `claude.orchestrator` becomes `{"selection": "user"}`. `generate.py` emits no `model:` or `effort:` line for a role whose entry has `selection: "user"`. The test asserts the orchestrator file has neither line.
  - The Claude preset `builder.repair` gains `"dispatch": "override"`. `generate.py` emits no variant file for override presets, and the coordination skill tells the coordinator to pass the model at dispatch.
  - Presets without `dispatch` behave as today: a variant file is emitted when the model or effort differs from the default.
  - Codex presets always produce variant profiles when they differ from the default, because a Codex dispatch-time model override is UNVERIFIED (R-Q3).
- **Read-only roles.**
  - investigator, critic and code-reviewer, including their variants, get `disallowedTools: Agent, Edit, Write, NotebookEdit`.
  - Their Codex profiles (including variants) set `sandbox_mode = "read-only"` (DOCUMENTED, R-Q3).
  - Their report, research notes or review JSON body is returned as the final message, and the coordinator records it to the named path. The briefs contract says so.
  - Bash can still write files on Claude, so this is partial protection only (REASONED).
- **No delegation.** Every non-orchestrator agent file has `disallowedTools` containing `Agent` (OBSERVED in `generate.py` today; kept). This meets the 1(f) "refusing reviewer dispatch by builder's own session" clause structurally: a builder cannot dispatch any agent, reviewer or otherwise. `docs/roles.md` records this.
- **orchestrator not dispatchable.**
  - The engine already removes `orchestrator` from dispatchable roles (`engine.py` `_contracts`, OBSERVED).
  - On Claude, its description starts "Main-thread coordinator only; never dispatch as a subagent."
  - When mods are loaded, an `agent.offer` hook hides `orchestra:orchestrator` from the model's agent listing (section 10.4).
  - It keeps `settings.agent` in `plugins/orchestra/.claude-plugin/plugin.json` (U7). Its model is whatever the user picked.
- **Engine role keys.** These are persisted identifiers, renamed because decision 1(c) settles it, not by judgment:
  - `releaser` becomes `operator` with `mode == 'release'`. This covers the one-terminal-release-card rule, `_pre_release_ids` and `_completion_evidence`.
  - The review-capable set `('code-reviewer', 'auditor', 'red-teamer')` becomes `('code-reviewer', 'critic')` in `add_task`, `_read_review` and `_start_assignment`.
  - Builder `repair` validation is unchanged. Builder `cleanup` needs no `repair_of`.
  - Changing `roles.json` changes the role/mode map, so any live v1 run must start anew (section 11.1, item 5). OBSERVED: the local state directory holds 14 run directories and no `state.json`, so no local run is affected.
- **Contract root.** `_contracts` resolves `methods` relative to `plugins/orchestra/skills/` instead of `skills/orchestra/`. Each worker role lists two methods: `orchestra-worker/SKILL.md` and its role `SKILL.md` (for example `orchestra-build/SKILL.md`). The orchestrator lists `orchestra/references/coordination.md` and `orchestra/references/briefs.md`, which the generator inlines. The containment check stays. A missing method file still fails validation.
- **Codex package and install.**
  - `generate.py` regenerates `plugins/orchestra-codex/`.
  - `orchestra.py install-profiles` already removes receipt-owned profiles that are no longer generated (`profiles.py:91-92`, OBSERVED). So reinstall removes the old `orchestra_auditor.toml` and similar files without touching unowned files.
- **Routing.** `config/flow.json` stays as documentation data with no code consumer after the trim (section 11.1). The audit axes `spec`/`standards`/`ledger` and the `surface` mode become coordination prose in the coordinator skill.

Acceptance criteria for area C:
- `ls plugins/orchestra/agents` lists exactly these files: `builder.md`, `code-reviewer.md`, `code-reviewer-checkpoint.md`, `critic.md`, `designer-planner.md`, `investigator.md`, `investigator-code.md`, `operator.md`, `orchestrator.md`.
- `ls plugins/orchestra/profiles/codex` lists exactly the 10 profiles in 7.1: `orchestra_builder`, `orchestra_builder_repair`, `orchestra_code_reviewer`, `orchestra_code_reviewer_checkpoint`, `orchestra_critic`, `orchestra_designer_planner`, `orchestra_investigator`, `orchestra_investigator_code`, `orchestra_operator`, `orchestra_operator_cleanup` (each `.toml`).
- `test_packaging` asserts the role set, the read-only `disallowedTools`, `disallowedTools` containing `Agent` on every worker file, `sandbox_mode = "read-only"` on exactly the read-only role profiles, no `model:`/`effort:` in `orchestrator.md`, Luna assignments `[('investigator','code'), ('operator','cleanup')]`, and Codex `builder.repair == sol high`.
- `test_engine` covers: the operator release card as the terminal card; critic `review_of`; critic refused for inline execution; old role names rejected as an unavailable role; builder `cleanup` accepted without `repair_of`.
- `generate.py --check` exits 0.
- Live check: the main session reports the model selected in the picker, and switching the picker changes it (B4 and L1).

## 8. Area D: one skill per role, plus the shared worker skill

### 8.1 Layout and loading (section 3.3)

Skill directories under `plugins/orchestra/skills/`:

- `orchestra/`: the orchestrator's skill.
- `orchestra-worker/`: the shared worker contract, preloaded by every worker. It holds: you are not alone; preserve sibling edits; never delegate or change coordinator state; return evidence; the `STATUS:`/`ARTIFACT:` report contract (E5); the E6 verifier wording rule; the `Mode:` line rule (below). It has no `references/`.
- One role skill per worker role: `orchestra-investigate/`, `orchestra-design/`, `orchestra-critique/`, `orchestra-build/`, `orchestra-review/`, `orchestra-operate/`.

Each role skill has:
- `SKILL.md`: the always-loaded core. It tells the worker to read `references/<Mode>.md` before work, where `<Mode>` is the brief's `Mode:` line. If the brief has no `Mode:` line, or the file is missing, the worker stops with `STATUS: BLOCKED`.
- `references/<mode>.md`: exactly one file per mode the role declares in `config/roles.json`. Further reference files are allowed only when a mode file names them (for example the code-reviewer lens files, read by `final.md` according to the brief's `Lens:` line).

Loading:
- Each worker agent file preloads exactly two skills: `skills: [orchestra-worker, <role skill>]`. Variant files preload the same two as their base role. The orchestrator file lists `skills: [orchestra]`.
- Names are bare. Missing names are skipped silently (OBSERVED by the coordinator probe, section 3.3), so `generate.py` refuses to generate when a `skills:` name does not resolve to `skills/<name>/SKILL.md`, or when that file sets `disable-model-invocation: true` (DOCUMENTED, R-Q1). It also refuses when a worker role's mode has no `skills/<role skill>/references/<mode>.md`. The orchestrator's `main` mode is exempt.
- Workers never rely on the Skill tool or on model-invoked skills (0 of 3 probe runs invoked a matching non-preloaded skill). Mods cannot inject skills per spawn (`AgentSpawnInput` has no `skills`), so no mod does.
- No duplication: the worker contract lives only in `orchestra-worker/SKILL.md`. Role skills do not restate it. `orchestra/SKILL.md` and `orchestra/references/coordination.md` share no key phrase.

`roles.json` gains a `skill` field per worker role (for example `"skill": "orchestra-build"`). Its `methods` become `["orchestra-worker/SKILL.md", "<role skill>/SKILL.md"]`, resolved by the engine contract check (section 7.2).

Worker agent body (generated) contains two things only:
- the role prompt (binding constraints, kept inline per decision 1(d));
- one plugin-root line naming the CLI and skill location.

The body has no "Read references/…" or "Read SKILL.md" lines and no inlined method or contract text.

The orchestrator body inlines `orchestra/references/coordination.md` and `orchestra/references/briefs.md`, because they are the binding main-thread contract. `briefs.md` is the coordinator's guide to writing briefs (with Pocock writing-for-agents ideas) and no longer goes into worker bodies. Whether `skills:` preloads on a `settings.agent` main thread is UNVERIFIED; the SessionStart context also names the skill path, so the main thread has the core either way.

Briefs carry a `Mode:` line. The engine checks it cheaply: when a card names a `brief` file (the existing optional field), `add_task` requires a line `Mode: <card mode>` in that file and rejects the card otherwise. Cards without a `brief` file are unchanged.

Codex profiles have no preload mechanism (REASONED). Their `developer_instructions` contain the role prompt, the `orchestra-worker/SKILL.md` body and the role `SKILL.md` body, all generated from the same files. Codex workers read mode files by the plugin-root path.

### 8.2 Content and sources

Every skill is written in our own words. Superpowers is the base wherever it has a candidate. An element from Pocock, gstack, Spec-kit, BMAD or a Claude built-in is merged in when it is stronger or more thorough for a subagent (section 8.4). No upstream skill is embedded whole, and no worker loads stacked upstream skills. The text uses Orchestra vocabulary (cards, modes, leases, reservations, evidence, approval boundaries) and the engine's real commands. The synthesis per capability is recorded in the capability matrix (section 8.4), from I2's texts at their pinned SHAs. The "Sources" column below lists candidates only; the matrix decides.

Mode names are the persisted modes of section 7.1. The file list follows from them.

| Skill dir | Role | SKILL.md core | `references/` | Sources (candidates) |
| --- | --- | --- | --- | --- |
| `orchestra/` | orchestrator | Coordination loop: assign, dispatch, evidence, integration, approval boundaries, autonomy rules, executor choice (8.5) | `coordination.md` (inlined), `briefs.md` (inlined; requires `Mode:` and, for final review, `Lens:`), `cli.md` (B7), `triage.md`, `handoff.md` (E2 resume), `parallel.md` (dispatch, Workflow mechanics of 8.5, plan execution, E3 review package), `worktrees.md`, `finishing.md`, `repair-rounds.md` (E1), `final-review.md` (lens routing, cleanup loop, E7 size gate; names the four lenses but not their categories), `audit-axes.md` (former `audit-policy` rules), `autonomy.md` (section 12) | superpowers: dispatching-parallel-agents, subagent-driven-development, executing-plans, using-git-worktrees, finishing-a-development-branch. Pocock: triage, handoff, writing-for-agents. |
| `orchestra-worker/` | all workers | Worker contract (8.1) | none | superpowers: verification-before-completion (verifier wording). Existing `briefs.md` worker contract. |
| `orchestra-investigate/` | investigator | Read-only rules, evidence labels | `code.md` (diagnosis), `docs.md` | superpowers: systematic-debugging. Pocock: diagnosing-bugs, grill-with-docs. Existing `investigation.md`. |
| `orchestra-design/` | designer-planner | Separate design and plan artifacts, decisions to the user, glossary first | `design.md` (with the architecture method), `plan.md`, `product.md` | superpowers: brainstorming, writing-plans. Pocock: grill-with-docs, productivity/grill-me, domain-modeling, codebase-design, improve-codebase-architecture, GLOSSARY/ADR, to-spec, to-tickets, prototype (spikes). Spec-kit assess gate. Plan-conflict pre-flight and the Spike/Bounded/Architectural classes. Existing `design.md`, `planning.md`, `founder.md` (design dossier). |
| `orchestra-critique/` | critic | Independence, challenge stance | `requirements.md`, `feasibility.md`, `scope.md`, `judge.md`, `spec.md`, `standards.md`, `ledger.md`, `surface.md` | Pocock: grill-me style challenge. BMAD lenses. Existing `red-team.md`, `audit.md`, `founder.md` (shipped-surface audit). |
| `orchestra-build/` | builder | Tests first, verification before completion, ownership | `implementation.md`, `frontend.md`, `sensitive.md`, `mechanical.md`, `repair.md` (works the round the brief names; the E1 cap lives in `skills/orchestra/`), `cleanup.md` (lean-and-simplify pass) | superpowers: test-driven-development, executing-plans, receiving-code-review (repair). Pocock: tdd, implement. Claude Code built-in simplify and gstack deslop ideas (cleanup). Existing `building.md`. |
| `orchestra-review/` | code-reviewer | Exact-diff review, anti-tautology rule, verdict JSON with artifact echo | `checkpoint.md`, `final.md` (holds the E7 lens-to-category table, its only copy), and the lens files `correctness.md`, `architecture.md`, `security.md`, `cleanliness.md`, plus `specialists.md` (reviewing as the specialist the brief names; the E7 size gate lives in `skills/orchestra/`) | superpowers: requesting-code-review and its reviewer prompt. Pocock: code-review, smell baseline, improve-codebase-architecture and codebase-design (architecture lens). Claude Code built-ins: security-review (security), simplify (cleanliness). gstack: `deslop-shared-libs` and `health` (cleanliness), `cso` (security, only where it adds to the Claude security-review checklist; O11), diff-scope specialists. Existing `review.md`. |
| `orchestra-operate/` | operator | Exact commands, logs and exits; no release outside an assignment | `gate.md`, `cleanup.md` (repo hygiene and retro), `release.md` | superpowers: verification-before-completion (gate), finishing-a-development-branch and using-git-worktrees (release, hygiene). Pocock: retro (cleanup). Existing `gates.md`, `closeout.md`. |

Left out of runtime skills: superpowers `using-superpowers` (a trigger meta-skill, moot with preload) and `writing-skills` (authoring). `writing-skills` informs only the authoring method in 8.4. No contributor document is written (O14).

Avoid list, enforced by review and by the phrase tests where a phrase exists:
- the using-superpowers 1% bootstrap injection;
- the never-pause default (Orchestra waits on product decisions and approval boundaries);
- gstack's preamble, telemetry and personas.

Licensing:
- `plugins/orchestra/THIRD-PARTY-NOTICES` holds, per source, the repository URL, the pinned 40-character commit SHA, and the full MIT license text as found at that SHA. The Codex package copies it automatically (`codex_package` copies every non-excluded file, OBSERVED).
- Every `SKILL.md` and every reference file that a matrix row with an upstream or idea-level source names as a destination starts, right after any frontmatter, with one source header line in this grammar (`orchestra/references/cli.md` is exempt, 8.4):
  `Source: derived from <repo>@<sha12> <paths> (MIT)[; <repo>@<sha12> <paths> (MIT)]...[; ideas: <name> (idea level)[, <name> (idea level)]...]; see THIRD-PARTY-NOTICES.`
  A file with only idea-level sources writes `Source: ideas: <name> (idea level); see THIRD-PARTY-NOTICES.`
- I2 (RESEARCH-v2) confirmed MIT at pinned SHAs for Superpowers, Pocock, gstack, Spec-kit and BMAD (BMAD: do not use its trademark). The Claude Code built-in skills `security-review` and `simplify` have no published license and are used at idea level only, in our own words. pstack and OMC are idea level. An idea-level source is credited by name in THIRD-PARTY-NOTICES without license text. No text from a source whose license is not confirmed is copied.

### 8.3 Budgets

| Item | Budget (bytes) |
| --- | --- |
| Each `SKILL.md` (8 files: `orchestra`, `orchestra-worker` and 6 role skills) | at most 4,096 |
| `orchestra-worker/SKILL.md` (preloaded into every worker) | at most 2,048 |
| Each file under a skill's `references/`, except `cli.md` and `coordination.md` | at most 6,144 |
| `orchestra/references/briefs.md` (inlined into the orchestrator) | at most 1,800 |
| Generated `agents/orchestrator.md` | at most 10,500 |
| Each generated worker agent file | at most 2,650 |
| Total of `plugins/orchestra/agents/*.md` | under 32,000 (O5). OBSERVED baseline: 64,335 |

The total is the binding threshold. The per-file agent budgets are allocations within it. The coordinator may reallocate between them without a design change, as long as the total holds.

Acceptance criteria for area D:
- `grep -rn "Read references/\|Read SKILL.md" plugins/orchestra/agents` returns nothing.
- `tests/test_skills.py` asserts:
  - every worker agent file lists exactly `orchestra-worker` and its role skill under `skills:`, and the orchestrator lists exactly `orchestra`;
  - every listed name resolves to `skills/<name>/SKILL.md` without `disable-model-invocation: true`;
  - every worker mode in `roles.json` resolves to `references/<mode>.md` in its role skill;
  - the 8.3 budgets;
  - the per-directory phrase files in `tests/skill_phrases/<dir>.json`;
  - no phrase of `orchestra-worker/SKILL.md` appears in a role skill;
  - every `Source:` header parses under the 8.2 grammar, and every SHA and every idea-level name in it is credited in `THIRD-PARTY-NOTICES`;
  - every destination file named in `docs/SKILL-SOURCES.md` by a row with an upstream or idea-level source carries a header, or still carries the B4 `Stub:` line (the gate set requires that no `Stub:` line remains). `orchestra/references/cli.md` is skipped (8.4).
- `generate.py --check` fails on an unresolved skill name or mode file (a test in `tests/test_packaging.py` proves it on a scratch copy).
- `tests/test_packaging.py` asserts that every generated Codex worker profile's `developer_instructions` contains both skill sentinels: the `orchestra-worker/SKILL.md` sentinel and its role `SKILL.md` sentinel.
- Every `SKILL.md` and mode file carries one sentinel line, placed after the frontmatter and any `Source:` header. Authoring keeps it unchanged.
- `test_engine.py`: a card whose brief file lacks `Mode: <mode>` is rejected; a card without a brief file is accepted.
- Live check: a dispatched `orchestra:builder` with `Mode: repair` quotes the sentinel lines of `orchestra-worker/SKILL.md` and `orchestra-build/SKILL.md` without calling Read or Skill, then reads `orchestra-build/references/repair.md` and quotes its sentinel. `claude --debug` shows no skill-skip warning.

### 8.4 Capability matrix and authoring method (round 4 B, round 5 correction)

Skill curation is a synthesis, not an import and not a contest. Before any skill text is written, `docs/SKILL-SOURCES.md` records a capability matrix built from I2's texts at their pinned SHAs. The result is Orchestra's own skills.

Pinned upstream texts: the clones at the I2 SHAs stay outside the repository. During this build the coordinator names their path in each MX, S and SC brief. Matrix and skill writers work only from those pinned texts and the existing Orchestra skill files, never from memory or another revision.

Rows: the capabilities Orchestra roles need. At least: diagnosis and debugging; TDD; spec writing; design interview; planning; ticket splitting; architecture improvement; domain modeling; code review; security review; cleanup and leanness; verification before completion; receiving review and repair; parallel dispatch; worktrees; branch finishing and release; handoff.

Columns (candidate text per source: path at the pinned SHA, or "none"):
- Superpowers;
- Pocock;
- gstack;
- Existing Orchestra / other: the current Orchestra skill files, Spec-kit and BMAD (MIT at their pinned SHAs), and the Claude built-ins `security-review` and `simplify` (idea level).

Each row records:
- **Base**: Superpowers, or the best-fitting source when Superpowers has none;
- **Merged in from others**: each stronger or more thorough element, with its source and why it is stronger;
- **Gaps filled**: what no candidate covered, and how Orchestra text covers it;
- **Synthesis notes**: how the parts combine in one voice and in Orchestra vocabulary;
- **Rejected**: only elements that conflict with Orchestra (the 8.2 avoid list, never-pause, personas, telemetry, host features subagents lack) or add nothing, each with a one-line reason;
- **Destination**: the skill file(s) in 8.2 that carry the result.

Rules:
- Superpowers is the base wherever it has a candidate. Another element is merged in when it is stronger or more thorough for a subagent.
- Nothing is dropped silently. An upstream skill that I2 found and that maps to no row is listed under "Not used", with a reason.
- License limits from 8.2 apply: an idea-level element can be merged in, but its text is not copied.
- Every file in the 8.2 table appears as a destination of at least one row.
- `orchestra/references/cli.md` is Orchestra text only: the engine CLI reference, owned by PLAN B8 and B7. A row may list it as a destination, but no upstream text or idea is written into it, it carries no `Source:` header and no `Stub:` line, and the provenance tests (8.3) skip it.

A critic reviews the matrix before authoring starts (PLAN MXR). Authoring starts only from the accepted matrix.

Authoring method:
- Each role skill and mode file is new text in Orchestra vocabulary, written from its matrix rows (base plus merged elements plus gap text).
- No concatenation of upstream texts. One voice across all skill files.
- No rule is repeated across files. Worker-contract rules live only in `orchestra-worker/SKILL.md`. The E1 cap and the E7 size gate live only in `skills/orchestra/`. The E7 lens-to-category table lives only in `orchestra-review/references/final.md`.
- Every file stays within its 8.3 budget and carries its `Source:` header (8.2) when a row with an upstream or idea-level source names it.

A critic cohesion review runs over all skill files together after authoring (PLAN SC). It reads the skill files, `docs/SKILL-SOURCES.md` and the 8.2 avoid list. It looks for contradictions, duplicated rules, rules that conflict with the engine or with `briefs.md`, missing provenance headers, content that does not trace to the file's matrix rows, and rejected or avoid-list content.

Acceptance:
- `docs/SKILL-SOURCES.md` has every listed row, each with a base (or "none, Orchestra text" with the reason), merged elements or "none", a rejected entry (or "none"), and a destination. Every 8.2 file appears as a destination.
- The matrix critic report is PASS on the matrix commit before any S1 to S7 ticket starts.
- The cohesion critic report is PASS on the merged skill files before INT freezes the candidate.
- `test_skills.py` keeps the duplicate guard for the worker contract (8.3).

### 8.5 Executor choice (coordinator skill, round 4 C)

`orchestra/SKILL.md` gains an "Executor choice" section. The coordinator picks one of three executors per unit of work:

| Executor | Use when |
| --- | --- |
| inline | A question, a doc read, or a one-file reversible edit where the main session already holds the context |
| single Agent dispatch | One unit with nothing independent beside it that still needs a worker: deeper investigation, isolation, or a different model |
| Workflow | 2+ independent units in any phase (tickets, review lenses, audits, research angles) |

The main session never approves its own implementation, whichever executor built it.

Workflow is the default whenever the host has the Workflow tool. The user's standing opt-in makes it the default with or without ultracode.

Workflow mechanics, in `orchestra/references/parallel.md`:
- Each `agent()` uses `agentType: 'orchestra:<role>'`, so the role's skills preload (probe, section 3.4). It passes `effort` per the model matrix and carries a brief with a `Mode:` line.
- The coordinator reserves every card before the script starts, in the engine. After it, the coordinator records each agent's report against its card.
- Concurrent editors use `isolation: 'worktree'`.
- A round-4 repair card is not run inside a workflow script. It goes through the Agent tool with the `model` override (section 3.4).
- Hosts without Workflow (Codex) fall back to parallel role dispatch.
- The variant agent files (`investigator-code`, `code-reviewer-checkpoint`) stay for the Agent tool path.

Acceptance:
- `tests/skill_phrases/orchestra.json` asserts the phrases `Executor choice`, `single Agent dispatch`, `default whenever the host has the Workflow tool`, `reserve every card before the script`, `agentType: 'orchestra:`, `isolation: 'worktree'` and `never approves its own implementation` (case-insensitive match).
- Live check, twice: in the B4 live wizard under `--plugin-dir`, and at L1 restart point B. A Workflow `agent()` with `agentType: 'orchestra:builder'` and `Mode: repair` quotes both preload sentinels and the `repair.md` sentinel.

## 9. Area E: borrowed procedures (prose in skills; no engine features)

- **E1 Fix-round cap.** Rounds are counted per ticket from the first independently checked BLOCKED review.
  - Rounds 1 to 3: `builder` `repair` cards at the role default (Claude Sonnet 5.5 medium; Codex Sol medium). The same builder agent is resumed when the harness allows it, and is otherwise re-dispatched with the prior report.
  - Round 4: `builder` `repair` with a dispatch override. Claude uses `claude-opus-5-5`; Codex uses the `orchestra_builder_repair` profile (Sol high).
  - Round 5, the breaker: no further repair. The ticket goes to critic `judge`, then to design or planning, and the user is told.
  - The coordinator records the round number in the progress ledger. The engine does not enforce the cap (exclusion X3).
- **E2 Progress ledger and resume.**
  - The coordinator appends one line per event to `<state>/progress.md`: time, card, action, artifact SHA, round, and decision (what / why / cost if wrong).
  - Resume happens only on an explicit user request, in this order: read the ledger, run `status`, verify worker liveness (live process plus transcript mtime), inspect artifacts, `start` (a new lease requeues running cards), then re-dispatch.
- **E3 Review package.** Before dispatching a review card, the coordinator writes the package to `<state>/review-packages/<card>/`, outside the repository. Reviewers still read the source themselves.
- **E4 Standing-orders register.** At run start the coordinator writes `<state>/standing-orders.md`, copying the binding project rules verbatim. It is pasted verbatim into every brief, under the heading `## Standing orders (verbatim)` followed by a `sha256:` line. Without mods the coordinator pastes it. With mods, `agent.spawn` appends it (section 10.4).
- **E5 Report shape.**
  - Every worker report starts with `STATUS: PASS|ISSUES|BLOCKED` and `ARTIFACT: <full sha> <dirty fingerprint>`. A missing SHA is a gap and is treated as ISSUES.
  - The engine review JSON keeps `CLEAN`/`BLOCKED`. PASS maps to CLEAN; ISSUES and BLOCKED with findings map to BLOCKED.
- **E6 Verifier rule.** Critic and code-reviewer treat a completion claim that uses "should", "probably", "seems" (or similar hedges) without an attached command, exit code or log as unverified. Such a claim is a `tests`/`requirements` finding. Builders do not use these words for completion claims.
- **E7 Final-review lenses and size-gated specialists.**
  - Every integration's final review runs four separate code-reviewer `final` cards, one per lens. Each card covers every task and reports the categories of its lens:

    | Lens | Categories |
    | --- | --- |
    | correctness | requirements, correctness, tests, standards |
    | architecture | architecture |
    | security | security |
    | cleanliness | cleanup |

    Together they cover the policy's required categories (default all 7; section 11.2). A policy that narrows the categories still runs all four lenses; a lens whose categories are all outside the policy reports them anyway, and the engine ignores the extra categories.
  - Confirmed findings from the correctness lens route to `builder` `repair` under E1.
  - Confirmed findings from the architecture, security and cleanliness lenses route to one `builder` `cleanup` card at the end of the run: a lean-and-simplify pass over the cited paths. Fresh review follows: all four lenses on the new frozen candidate. Cleanup findings that survive the fresh review count as E1 fix rounds on the cleanup card.
  - Extra specialists (critic or code-reviewer briefs for frontend, visual or other surfaces beyond the four lenses) are added only when two conditions hold: `git diff --shortstat BASE..HEAD` reports more than 50 changed lines, and the changed paths match the specialist's surface. At 50 lines or fewer, no specialists are added. The four lenses are never gated.

Acceptance: each rule of E1 to E7 appears in exactly one skill file (orchestrator procedures in `skills/orchestra/`; worker-wide rules E5 and E6 in `skills/orchestra-worker/SKILL.md`; role rules in the matching role skill). E7 has two parts, each with one owner: the lens-to-category table lives only in `orchestra-review/references/final.md`; the lens routing, the cleanup loop and the specialist size gate live only in `orchestra/references/final-review.md`, which names the four lenses without restating their categories. The E1 cap and the E7 size gate are coordinator rules in `skills/orchestra/` only; `orchestra-build/references/repair.md` and `orchestra-review/references/specialists.md` describe only the worker's own round or brief. Phrase files:
- `orchestra-worker.json`: `STATUS: PASS|ISSUES|BLOCKED`.
- `orchestra.json`: `Round 5`, `standing-orders.md`, `progress.md`, `more than 50 changed lines`, and the four lens names.
- `orchestra-review.json`: the four lens names in the lens files, and `requirements, correctness, tests, standards` (the table row) in `final.md`.
- No other phrase file asserts `Round 5` or `more than 50 changed lines`, and no other phrase file asserts `requirements, correctness, tests, standards`.

## 10. Area F: mods module (Claude Code only)

### 10.1 Files and registration

- The module files are `plugins/orchestra/hooks/mods.json` (`{"modules": ["./mod/orchestra.ts"]}`), `plugins/orchestra/hooks/mod/*.ts`, `plugins/orchestra/hooks/mod/*.test.ts` and `plugins/orchestra/types/index.d.ts`. The types file holds `PluginState` for any `$.state` value.
- In `.claude-plugin/plugin.json`, `"hooks"` becomes `["./hooks/claude.json", "./hooks/mods.json"]` and `"types": "./types/index.d.ts"` is added.
  - OBSERVED: `claude plugin validate` accepted both a hooks array and a combined file in a scratch probe.
  - UNVERIFIED: whether both files load at runtime. The thin slice B1 proves it.
- The mod files are excluded from the Codex package (the `codex_package` exclusion list). `hooks/codex.json` is untouched.
- Module rules (documented engine constraints): relative imports only, no dynamic import, string-literal event names, `$` calls spelled in full, no Node or DOM.
- Function hooks run when the host enables them. `CLAUDE_CODE_ENABLE_FUNCTION_HOOKS=1` turns them on (DOCUMENTED, R-Q5); it is required for `claude -p` mod tests. The user's settings set it, which is why Desktop's embedded 2.1.286 fires them (U2).

### 10.2 API presence check (replaces the version floor)

- There is no version floor and no `$.session.version()` call.
- At `session.start`, before writing any marker, the mod checks that each `$` API it uses for the guard exists and is a function: `$.session.id`, `$.clock.every`, `$.clock.now`, `$.env.get`, `$.fs.read`, `$.fs.write`, `$.process.run`. If any is missing, the mod writes no marker and installs no guard; the Python guard covers the session.
- UI APIs (`$.ui.open`, `$.ui.toast`, the status band) are checked separately. If one is missing, only that UI feature is skipped.
- A build whose API drifted so far that the module fails validation at load also leaves no marker, so Python covers the session (the safe direction).
- UNVERIFIED: whether the module validator accepts a `typeof` presence check. B1 proves it. If it does not, B1 drops the explicit check and relies on load-time validation, which has the same safe outcome; this is a technical fallback, not a design change.
- `README.md` and `docs/hooks.md` state the requirement as an API requirement: function hooks enabled, tested on Claude Code 2.1.289 (CLI) and 2.1.286 (embedded in Desktop with `CLAUDE_CODE_ENABLE_FUNCTION_HOOKS=1`).

### 10.3 In-process guard and the double-fire contract

- At `session.start` the mod reads `${$.plugin.root}/config/guard-rules.json` with `$.fs.read` and computes `rules_sha256`. It writes the liveness marker `${XDG_STATE_HOME:-$HOME/.local/state}/orchestra/mods/<session_id>.json` containing `{session_id, heartbeat_ms, plugin_version, rules_sha256}`.
- Marker lifecycle. One tick runs per process, and every marker write goes through one serial write queue, so writes land in the order they were queued.
  - `session.start` cancels any running tick before it starts a new `$.clock.every` tick of 5 s. The declaration says `session.start` can fire again in one process (an enable, a worker respawn or a reload).
  - Each tick re-reads `$.session.id()`. If the id differs from the id the tick saw last, the tick queues `heartbeat_ms: 0` for the old id, removes the new id from the retired set, and remembers the new id. It then queues a fresh write for the current id unless that id is in the retired set. The retired-set check applies to fresh writes only; zero writes always run.
  - `session.end` adds `e.sessionId` to the retired set and queues `heartbeat_ms: 0` for it. Because the queue is serial, a fresh write already queued by an in-flight tick lands before the zero write, never after it. It does not touch the lease (O2).
  - On `e.reason` `clear`, the process continues under a new id and no `session.start` fires for it (declaration of `SessionEndInput`). The tick keeps running, and its next fire writes the marker for the new id. UNVERIFIED for `resume`: the declaration says only that the process continues under another id. The mod treats `resume` like `clear`; if `session.start` does fire, it cancels the old tick first, so no two ticks run. B5 records the observed behavior live.
  - On `prompt_input_exit`, `logout` and `other`, `session.end` also cancels the tick.
  - A resumed id that was retired earlier gets fresh markers again: the id change removes it from the retired set.
- The tick callback catches its own errors. A failed tick writes nothing, so the marker goes stale and Python guards in full. The heartbeat time comes from `$.clock.now()`, so `claude plugin test` can control it.
- If neither `XDG_STATE_HOME` nor `HOME` is set, the mod writes no marker and installs no guard.
- `on('tool.call', {tool: 'Bash'|'Edit'|'Write'|'MultiEdit'})` classifies the input with a TypeScript port of the shared rules:
  - `deny` returns `{deny: reason}`;
  - `allow` calls `next(e)`;
  - `release`, `release-multi` and `boundary` delegate to Python through `$.process.run(['/bin/sh', <root>/scripts/run-hook.sh, 'PreToolUse', '--harness', 'claude', '--from-mod'], {stdin: payload})`, because only the engine knows the armed state, autonomy and permits. That process starts only for those classes. Its deny is returned as `{deny}`.
- `.catch` on the guard returns `{deny: 'Orchestra guard error; failing closed'}`.
- If the rules fail to load, the mod writes no marker and installs no guard. Python covers the session.
- Why this cannot double-fire: on deny, the mod answers without `next`, so `classic.PreToolUse` (which fires inside `tool.call`, beneath plugin hooks) never runs. On allow, the classic Python hook runs, sees a fresh marker whose `rules_sha256` matches its own table, and exits before git or engine work. The marker's absence, staleness or rules mismatch makes Python guard in full. That covers mods disabled, unknown `-p` behavior, a worker crash that unloads mods, and a mixed dev/installed copy.
- Rejected alternatives:
  - Answering `classic.PreToolUse` without `next`. It would skip every other plugin's and every settings shell hook.
  - Removing the Python PreToolUse on Claude. That leaves no fallback when mods are not loaded.
  - Running both guards on every call. That is correct, but it keeps the per-call process cost the mod exists to remove.
- Shared rules and corpus:
  - Both guards read `config/guard-rules.json`.
  - `tests/test_guard_corpus.py` checks every corpus case against `classify_command`.
  - `hooks/mod/guard.test.ts` checks every case against the TypeScript classifier through `claude plugin test`.
  - The shell tokenizer is code in both languages. The corpus, with the section 5.1 vocabulary, is the parity contract and must include every A-row case and every existing `test_hooks` command.

### 10.4 Agents

- `on('agent.offer', {agent: 'orchestra:orchestrator'})` returns `{isOffered: false}`.
  - Main-thread selection through `settings.agent` is not an offer per the documented types (REASONED). The B5 live check proves it.
- `on('agent.spawn')` handles `subagentType` values that start with `orchestra:`. If `orchestra.py where` (run once per session through `run-hook.sh --cli`, then cached) reports `standing_orders: true`, the hook appends `<state>/standing-orders.md` verbatim to `prompt` under the E4 heading, unless the prompt already contains that `sha256:` line.
- No spawn refusals. The first draft's refusals of delegation by a worker and of reviewer dispatch by a builder could never fire, because every non-orchestrator agent has `disallowedTools: Agent` (section 7.2). They are dropped. The 1(f) clause is met by `disallowedTools: Agent`, recorded in `docs/roles.md`.

### 10.5 UI (never logic)

- `/orchestra-board` is registered in `session.start` and answered by `command.run`. It opens a pane (`$.ui.open`, `ui.render` on `Pane`) that lists cards (id, role/mode, state, worker), the session's active flag, autonomy state and capacity. The data comes from `run-hook.sh --cli status`, refreshed every 5 s while the pane is open. `status` no longer carries the lease (section 11.2).
- Verdict toasts: after a Bash `tool.call` whose command runs `orchestra.py` with `review`, `gate` or `accept`, the mod shows `$.ui.toast` with the receipt's verdict or exit. An unparseable result shows no toast.
- `/orchestra-autonomy on|off|status`, the autonomy toast and the status band are specified in section 12.7.
- Drawing happens only in the terminal and the Desktop Code tab, and nothing depends on it.

Acceptance criteria for area F:
- `claude plugin validate plugins/orchestra` (Claude Code 2.1.289) exits 0 and lists `tool.call`, `session.start`, `session.end`, `agent.offer`, `agent.spawn` and `command.run`.
- `CLAUDE_CODE_ENABLE_FUNCTION_HOOKS=1 claude plugin test plugins/orchestra` exits 0 with the corpus parity test included.
- Live, in an interactive session started with `claude --plugin-dir <worktree>/plugins/orchestra`, with the installed `orchestra@orchestra-distribution` disabled for the session and exactly one Orchestra SessionStart context observed:
  - the marker appears and its mtime advances;
  - `git stash` is denied, with no Python PreToolUse work, proven by a debug-log line or timing;
  - `git stash list` runs;
  - `/orchestra-board` renders;
  - `orchestra:orchestrator` is absent from the agent listing, while the main thread still runs as the orchestrator;
  - after `/exit` the marker is stale and the F5 SessionEnd has released the run.
- The same checks under `CLAUDE_CODE_ENABLE_FUNCTION_HOOKS=1 claude -p` are recorded as observed, whatever the outcome.

## 11. Area G: engine changes (approved for 2.0.0)

Evidence common to section 11 (OBSERVED): the local state root holds 14 run directories and zero `state.json` files, so the engine has never recorded a run on this machine. Runs on other machines are UNVERIFIED. Test counts come from `tests/test_engine.py` (45 tests) and the other test modules.

### 11.1 Approved trim (U4, option A)

| Removed | Why removal is safe |
| --- | --- |
| (1) `review-groups` CLI and `routing.review_groups` | Advisory output only, 1 routing test and 1 integration call. The coordinator groups reported cards by hand, as the coordination prose already says. |
| (2) `audit-policy` CLI and `routing.audit_axes` | The coordinator supplies the booleans itself; the function only echoes them as axes. The axis rules (`spec`, `standards`, `ledger`, plus `surface` by judgment) move to coordinator prose in `skills/orchestra/references/audit-axes.md`. |
| (3) `route` CLI (and `routing.route`) | It maps coordinator-chosen booleans to a lane; the global rules duplicate the lanes. `config/flow.json` stays as documentation data. With (1) to (3) gone, `orchestra_core/routing.py` and `tests/test_routing.py` are deleted. |
| (4) `policy.reserved_ports`, `policy.denied_tools` in `config/policy.default.json` | No consumer (F7, OBSERVED by grep). The engine merges policy with `update`, so an old policy file that still carries the keys loads unchanged. |
| (5) Contract-hash invalidation narrowed | The contract hash becomes a digest of the role-to-modes map only. Editing a method or skill file no longer invalidates a live run; adding, removing or renaming a role or a mode still does ("Role or method instructions changed; start a new run" stays the message for that case). A missing method file still fails validation. |

| Kept | Why |
| --- | --- |
| Release permits and `release` CLI | The only structural release check inside an armed run. A1 removes its friction outside runs. |
| Autonomy ledger and `hook_stop` | The base of U8 (section 12). |
| Lease and session | Coordinator consistency token; protects against late reports; F5 fixes the lockout. |
| Reservations | Collision detection between cards. |
| Gates and secret scan | Gate evidence binding; U8 completion checks reuse gate receipts. |
| Final-review category coverage check | Structural completeness of final review, made narrowable (11.2). |

Skill prose naming the removed commands is removed in the same release: `skills/orchestra/references/cli.md` and `README.md` (B8), `skills/orchestra/references/coordination.md` and `skills/orchestra/SKILL.md` (S1, which rewrites them), `docs/source-parity.md` and `docs/cli.md` (B7). Generated agent files follow on regeneration.

### 11.2 Review categories and lease-free status (U3a)

- `required_categories = set(policy['required_review_categories'])`. It must be a non-empty subset of `CATEGORIES`; `Engine` init rejects an empty list or an unknown category. The default policy keeps all 7. This removes the union at `engine.py` line 614 that made narrowing impossible (F7).
- `status` (CLI and `Engine.status()`) redacts `session.lease` and every task's `lease` field. The board and `where` therefore never see a lease.
- `hooks.py` Interrupt no longer reads the lease from `status`. A new internal `Engine.interrupt_active()` interrupts the active session under the state lock without a caller-supplied lease. It is a Python method only, with no CLI.
- `start` still prints the lease once; that is the coordinator's copy.

### 11.3 Evidence bound to owned paths plus HEAD (U3b)

- `Engine.artifact(scope=None)`. With `scope` (a sorted list of repository-relative paths), the artifact binds: `repo`, `identity`, `head`, `tree`, the sorted `scope`, a fingerprint over the scope's entries only (same entry encoding as today), the `ls-files --stage` index lines filtered to the scope, the porcelain status lines filtered to the scope, and `policy`.
- Scoped evidence applies to:
  - a task's `report_artifact`: scope = the task's reservation files (its files plus its repair chain's files, as `_reservation` computes them);
  - a non-final review: scope = the union of the covered tasks' reservation files. The receipt stores its `scope`. Verdict matching (`_review_verdicts`) recomputes the artifact with the receipt's stored scope and compares.
- Whole-repo evidence stays for final reviews, gates, release permits, release receipts and completion evidence, because those run on the frozen integrated candidate.
- HEAD stays bound, so any commit or merge still stales scoped evidence. That is the decided model ("owned paths plus HEAD"). The gain: an uncommitted edit by a sibling outside a card's scope no longer stales that card's evidence.
- A task with no reserved files gets the whole-repo artifact.
- CLI: `orchestra.py artifact --tasks ID[,ID]` prints the scoped artifact, so a reviewer can echo it in review JSON. `artifact` without `--tasks` is unchanged.

Acceptance for section 11:
- `test_engine.py`: narrowed categories accepted; an empty or unknown category list rejected at init; `status` has no `lease` key anywhere; an edited method keeps the run; a missing method still raises; an added mode invalidates the run; an edit outside a card's scope keeps its scoped verdict current; an edit inside the scope stales it; a new commit stales it; final reviews still use the whole-repo artifact.
- `test_hooks.py`: Interrupt still interrupts an active run through `interrupt_active`.
- `test_integration.py`: no `review-groups` call; `artifact --tasks` output matches what `review` accepts.
- `ls plugins/orchestra/scripts/orchestra_core/routing.py tests/test_routing.py` fails (both deleted).
- `python3 plugins/orchestra/scripts/orchestra.py route` exits non-zero (unknown command); likewise `audit-policy` and `review-groups`.

## 12. Area H: autonomous overnight mode (U8)

### 12.1 Toggle

- CLI: `orchestra.py autonomy arm|disarm|status`. It replaces the v1 form `autonomy LEDGER --max-passes N --max-stalls N`.
- `arm`, `disarm` and `status` take no `--lease`. REASONED: the Claude toggle `/orchestra-autonomy` must call the same entry (U8), and the mod never holds the lease. See O8.
- `arm` requires an armed run (an active session). It refuses otherwise.
- `arm` and the ledger file:
  - If `<state>/autonomy.md` does not exist, `arm` writes it from the template `plugins/orchestra/config/autonomy-template.md`, prints its path, and refuses ("fill the ledger, then arm again"). This reconciles "created from a template by `arm`" with "`arm` refuses unless a ledger exists" (interpretation, REASONED).
  - If it exists but a template placeholder remains or a field fails to parse, `arm` refuses and names the field.
  - Otherwise `arm` snapshots the ledger (the existing `_snapshot`/`_intact` mechanism), stores the parsed fields, sets `autonomy.active`, prints the preconditions report (12.5), and exits 0.
- `disarm` sets `autonomy.active` to false, records stop reason `disarmed`, writes the morning report, and clears a shown report from the previous stop. It is safe to call at any time.
- `status` prints `{active, passes, max_passes, stalls, max_stalls, deadline, parked, last_stop_reason}` and never the lease.
- `interrupt`, SessionEnd release and `finish` clear autonomy as today.

### 12.2 Ledger

The template has these fields, one per line, each with a placeholder the user replaces:

- `goal:` one line.
- `completion:` gate names, one per line under `## Completion checks`, each as `NAME: argv...`. Completion is reached when every named check has a passed, intact gate receipt with the same argv on the current whole-repo artifact. The Stop hook never runs commands; the coordinator runs the gates with `orchestra.py gate NAME -- ...`.
- `max_passes:` integer, 1 to 20 (the existing engine bound).
- `max_stalls:` integer, 1 to 2 (the existing engine bound). A stall is a pass with no newly accepted card. The progress measure therefore becomes the set of accepted card ids, not the v1 digest of accepted cards, artifact and gates.
- `deadline:` ISO 8601 with a UTC offset, in the future at `arm` time.
- `## Approval boundaries`: the fixed list of 12.4, printed by the template. The user may add lines; added lines are prose for the coordinator, and the fixed list cannot be removed (a ledger missing any fixed line fails `arm`).

The ledger is a coordinator-authored file in the state directory (A8 exception). Any change after `arm` breaks the snapshot, and the loop stops with reason `ledger-tampered`.

### 12.3 Loop (classic Stop hook)

`hook_stop` continues only when all of these hold: the session is active; autonomy is active; the ledger snapshot is intact; the pass and stall caps are not reached; the deadline has not passed; completion is not reached; and at least one card is ready, running or reported (not only accepted or parked). It then increments `passes`, updates `stalls`, and returns a block reason: "Autonomy pass N of M: continue with the next ready card; park any card that reaches an approval boundary."

Otherwise it does not continue. When autonomy was active, it sets `active` false, records the stop reason (`cap-passes`, `cap-stalls`, `deadline`, `complete`, `parked-only`, `no-ready-card`, `ledger-tampered`), and writes the morning report. A stop is final for this arm; the user re-arms.

Codex uses the same Stop hook (`hooks/codex.json` registers `Stop`, OBSERVED).

### 12.4 Approval boundaries (hard, not configurable)

| Boundary | Enforcement |
| --- | --- |
| Release | Engine: `permit` and `release` refuse while autonomy is active. Hook: classes `release` and `release-multi` deny while autonomy is active, even with a permit. |
| Merge | Hook: `gh pr merge` and `az repos pr update --status completed` are class `release` (denied). Local merge-family commands (class `boundary`, category `merge`) deny when the current branch is the default branch, and are allowed on any other branch (O12). The current branch is read from the payload `cwd`'s worktree (5.1). |
| Push | Hook: every push, to any branch, is class `release` and denies while autonomy is active (O12). |
| Deletion | Hook: class `boundary`, category `delete` (A14) denies. Claude has no delete tool. |
| Credential entry | Prose only. The coordinator skill forbids it and parks the card. Detecting credential entry in arbitrary commands or tools is not claimed (X8). |
| Any engine-gated action | Engine: every command that needs a permit refuses while autonomy is active. |

The hook's deny reason for a boundary reads "Approval boundary under autonomy: park this card with `orchestra.py park TASK --reason ...` and continue with other cards."

Parking:
- New CLI `orchestra.py park TASK --reason TEXT` (lease required) moves a queued, running or reported card to `parked` with the reason. It drops the card's assignment and releases its reservation and capacity. Dependents stay blocked.
- `orchestra.py unpark TASK` (lease required) returns a parked card to `queued`. The user's morning step.
- Parked cards count as not done for completion evidence, so a run with parked cards cannot `finish`.

Scope note: a builder working in a linked worktree of the armed repository gets the same boundaries, because the hook resolves state from the main worktree (A15). A separate clone is a different repository and stays unarmed. REASONED; recorded in `docs/hooks.md`.

### 12.5 Preconditions report (check and report; never change, never refuse)

`arm` prints:
- `permission_mode`: the highest-precedence `permissions.defaultMode` found in the Claude settings files (local project, project, user), or `unknown`, with a warning when it is not a mode that skips prompts. For Codex, the `approval_policy` in `~/.codex/config.toml`, or `unknown`. Reading only; how reliably this reflects the live session is UNVERIFIED and recorded by the B10 live check.
- `keep_awake`: always the line "User step: enable keep-awake in Claude Desktop (or keep the machine awake) for an overnight run."

### 12.6 Morning report

- On every stop (12.3) and on `disarm`, the engine appends to `<state>/progress.md` a section `## Autonomy report <ISO time>` with: stop reason; passes used; accepted cards (id, role/mode); parked cards with reasons; failures (failed gates and BLOCKED reviews recorded since `arm`).
- It also stores the report in state as `autonomy.report`.
- The SessionStart hook, on the coordinator path, reads state for the payload `cwd` read-only. When a report exists that is newer than the last `arm`, it appends the report (at most 2,000 characters, with the `progress.md` path) to the coordinator context. It stays shown on each SessionStart until the next `arm` or `disarm`.

### 12.7 Mods (Claude only)

- `/orchestra-autonomy on|off|status` is registered at `session.start` and answered by `command.run`. It calls `run-hook.sh --cli autonomy arm|disarm|status` and renders the result. `on` with no ledger shows the template path returned by `arm`.
- On a stop, the mod shows `$.ui.toast` with the stop reason and counts. Detection: the tick (10.3) reads `run-hook.sh --cli autonomy status` at most every 30 s while autonomy is active.
- A status band shows "Orchestra autonomy: pass N/M, deadline HH:MM" while active. The band API name is taken from `types/index.d.ts` of the tested build; if the build has none, the band is skipped (10.2).

Acceptance for section 12:
- `test_engine.py`: `arm` refuses without a run, without a ledger (and writes the template), with a placeholder, and with a fixed boundary line removed; the pass cap stops; the stall cap stops after passes with no newly accepted card; the deadline stops; completion stops; `parked-only` stops; a tampered ledger stops with `ledger-tampered`; `permit` and `release` refuse while active; `park` and `unpark` move cards and reservations; the morning report is written to `progress.md` with accepted, parked and failures.
- `test_hooks.py`: Stop returns block while active and in bounds; Stop returns `{}` at a cap and at the deadline; release and `boundary` delete classes deny while active and allow while armed with autonomy off; a merge-family command denies on the default branch and allows on another branch; in a linked worktree of the armed repository (A15) a push and an `rm` deny while autonomy is active; with autonomy active, a local `git merge` from a linked worktree on a non-default branch is allowed while the main worktree has the default branch checked out, and denies when the linked worktree has the default branch checked out while the main worktree is on another branch; SessionStart shows a pending report.
- Live check: in a `--plugin-dir` session with a two-card run, `autonomy arm` with `max_passes: 1`; one Stop continues into the next card; the next Stop stops with `cap-passes`; the next SessionStart shows the report.

## 13. Open decisions

| ID | Question | Recommendation | Blocking? |
| --- | --- | --- | --- |
| O1 | Revised by U7: keep `settings.agent: orchestra:orchestrator`, with no model or effort in the file, so the main session follows the picker. | Settled by U7. | No |
| O2 | Who releases the lease at session end? | The classic `SessionEnd` hook releases it in every Claude session, with or without mods, under the O6 reason policy. The mod's `session.end` only retires its heartbeat. This is a dossier deviation from 1(f) ("session.end releasing lease"): it meets the same observable acceptance with one implementation that also works without mods. | No |
| O3 | Rebind evidence from the whole repo to owned paths (F6)? | Settled by U3b: in 2.0.0, owned paths plus HEAD for task reports and non-final reviews (11.3). Interpretation to confirm: final reviews, gates, release and completion keep whole-repo evidence. | Confirm before B9 acceptance; default applies |
| O4 | Does `az repos pr update ... --status completed` stay release-class? | Keep it gated inside armed runs. It is the Azure Repos equivalent of `gh pr merge`. Unarmed, it is allowed by A1. | Confirm before B2 acceptance; default applies |
| O5 | Agent-file size budget (32,000 bytes total) | Accept as the acceptance threshold; per-file allocations in 8.3. | No |
| O6 | SessionEnd reason policy | No release on `clear` or `resume`; release on `logout`, `prompt_input_exit`, `other` and unknown reasons. Reopens if the B3 live capture shows `/clear` changes the `session_id`. | Confirm before B3 acceptance; default applies |
| O7 | Autonomy caps for an overnight run: keep the existing engine bounds (`max_passes` 1 to 20, `max_stalls` 1 to 2)? | Keep. A pass is a whole coordinator turn, which can dispatch and accept several cards. | Confirm before B10 acceptance; default applies |
| O8 | `autonomy` `arm`, `disarm` and `status` without a lease, so the mod toggle can call the same entry | Accept. Arming still needs an active run and a complete ledger; disarm is the safe direction; any process able to run the CLI could arm, which is within the best-effort charter (X8). | Confirm before B10 acceptance; default applies |
| O9 | Two preloaded skills per worker (`orchestra-worker` plus the role skill), per the coordinator's round 3 decision, against the U6 amendment's "preloads only that one role skill" | Settled in round 4 (section 3.4): two preloaded skills per worker. | No |
| O10 | Mode renames and additions in the round 3 suggested map | Settled in round 4: keep the section 7.1 modes; the map is source assignment only. Bug diagnosis lives in investigator `code.md`; the architecture method lives in `design.md`. | No |
| O11 | gstack scope: round 3 says cleanup/deslop ideas only; the U6 amendment names `cso` for the security lens | Settled in round 4: gstack `cso` is used only if it adds to the Claude security-review checklist; the matrix row records the verdict. | No |
| O12 | Autonomy boundary details (SF5) | REASONED default (coordinator ruling, round 5): at a boundary the run parks the card and continues with other cards; the stop reason is `parked-only` when only parked cards remain (U8's own later sentence); local merges on a non-default branch are allowed; every push is denied while autonomy is active. | Confirm before B10 acceptance; default applies |
| O13 | Linked worktrees of an armed repository (SF1) | REASONED (coordinator ruling, round 5): resolve state from the main worktree and apply that run's mapping, permit and autonomy (A15). This strengthens U8's hard boundaries. | No |
| O14 | `docs/skill-authoring.md` (SF10) | REASONED (coordinator ruling, round 5): dropped; it traces to no user decision. `writing-skills` informs only the 8.4 authoring method. | No |

## 14. Exclusions

- X1: No engine trimming beyond section 11.1.
- X2: No change to `hooks/codex.json` beyond the regenerated package. The Codex advisory `ORCHESTRA_ROLE` delegation check stays. It is dead on Claude, where narrowing the matcher removes it from the path.
- X3: The engine does not enforce the fix-round cap, review packages, the report shape, the verifier rule or the lens split. They are prose procedures. The engine's 7-category coverage check is what binds the lenses structurally.
- X4: No new reservation enforcement at edit time.
- X5: Withdrawn. The category union and the lease in `status` are fixed in 2.0.0 (U3a, section 11.2).
- X6: No audit-policy CLI. Audit axes, including `surface`, are coordinator prose.
- X7: No `$.store`-based autonomy ledger and no workflow-nudge port. The status band is in scope only for autonomy (12.7).
- X8: No hostile-worker isolation claims. Mods are unsandboxed and can read environment variables. Bash writes to protected paths, including the marker directory and the autonomy ledger, are not detected. Credential entry is not detected. `gh api` and MCP or terminal tools are not guarded; U1 forbids bypass procedurally.
- X9: `SPEC.md` and `PLAN.md` (v1) are kept as history. Each gets only a one-line pointer to the v2 documents.
- X10: Project kits' `orchestra-autonomy-loop.sh` hooks are not touched by this plan. Their removal is a separate coordinator workstream after release.
- X11: No Orchestra skill pastes upstream text blind. No skill uses the avoid list in 8.2.

## 15. Risks

| Risk | Direction | Mitigation |
| --- | --- | --- |
| Mods API is early-access and its `.d.ts` changes per build | A mod fails to load | API presence check plus a marker-gated Python fallback: a failure falls back to the full Python guard, never to an unguarded session. |
| The heartbeat window: after a crash unloads mods, up to 15 s of stale-but-fresh marker | Guard gap of 15 s or less | Short window, and the guard is best-effort by charter. The live check records the actual crash-unload behavior if it can be induced. |
| The shell tokenizer is implemented twice | Parity drift | The fixed corpus vocabulary and the shared corpus are mandatory in both runners. The B5 checkpoint reviews parity. |
| Heredoc stripping could hide destructive input | Silent allow | A5 recursive rule for shell interpreters, with a test. Heredocs into other interpreters (for example `python3 -`) were not inspected before either. That gap is unchanged and documented. |
| Unarmed release allow (A1) widens what a non-Orchestra session may push | More allowed actions | This is the settled decision, and U1 depends on it. Destructive rules still deny, and harness permissions still apply. |
| A `--plugin-dir` live session loads v2 next to the installed v1 | False live evidence | Live-check wizards disable `orchestra@orchestra-distribution` for the session and re-enable it on exit, and assert exactly one Orchestra SessionStart context. |
| `skills:` preload skips a wrong name silently | Methods missing in workers | Preload of bare names is OBSERVED (section 3.3). `generate.py` refuses unresolved names and missing mode files; the B4 live check asserts both sentinels and one mode-file read. |
| Agent tool `model` may reject the full id | Round-4 override fails | DOCUMENTED as accepted (R-Q2). The fallback alias is `opus`. |
| Persisted role rename invalidates v1 runs and user-authored briefs that name old agents | Breaking change | The major version is 2.0.0. No local runs exist (OBSERVED). Release notes list the name mapping. |
| The user's global rules name v1 roles and a local `models.json` patch | Stale guidance after release | The coordinator updates `~/.claude/CLAUDE.md` and `~/.codex/AGENTS.md` after release (U5). Workers never edit user configuration. |
| Scoped evidence still stales on every merge because HEAD is bound | Less benefit than a pure path scope | Decided model (U3b). The gain is for uncommitted sibling edits. |
| Autonomy runs unattended | Unwanted actions overnight | Hard boundaries enforced by engine and hook (12.4), caps and deadline in the engine, a tamper-evident ledger, and a morning report. Credential entry and non-shell tools stay prose-only (X8). |
| Upstream skill licenses differ from what the brief assumes | Licensing defect | I2 confirms each license at a pinned SHA; unconfirmed sources are idea-level only (8.2). |
| Skill files written by seven parallel tickets drift apart | Contradictory or duplicated rules | One accepted capability matrix as the only input, one authoring method, the worker-contract duplicate test, and the SC cohesion critic over all skill files (8.4). |
| Workflow `agent()` per-call `model` option is unverified | Round-4 override silently not applied | Round-4 repair uses the Agent tool path (8.5); the variant agent files stay. |
| Coordinator-authored files are allowed in the state dir (A8 exception) | A worker could edit `standing-orders.md` or `autonomy.md` | Read-only roles lack Write. The coordinator verifies the register's `sha256:` line before dispatch. The autonomy ledger is snapshot-checked on every Stop. |
