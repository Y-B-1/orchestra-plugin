# Orchestra 2.0.0 specification

Status: design approved for planning review. Settled product decisions are quoted under "Settled decisions" and are not reopened here. Open items are listed under "Open decisions" with a recommended default. Each is marked blocking or non-blocking.

- Starting artifact: branch `feat/v2-roles-guard-mods` at `0ea2ece8059abfb83419714caeda714dfaefd63f`. The tree was clean when inspected.
- Policy revision: `AGENTS.md` blob `182417468e23bfa02c1afbd15bac1d031141a18e`.
- Baseline, observed at the starting artifact: `python3 -m unittest discover -s tests` ran 89 tests, OK, exit 0, in 78 s on Python 3.14.6. `python3 plugins/orchestra/scripts/generate.py --check` exited 0 (44 Codex package files, 27 native profiles). Claude Code 2.1.289 is installed.
- Finding IDs (F1 to F7) refer to the private 2026-10-04 audit. That audit is not in this repository and must never be copied into it.

Evidence labels used throughout:
- **OBSERVED**: read in source or produced by a command.
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

## 2. Scope

Six areas are in scope:

- **A. Guard fixes**: the Python guard and hook adapter (`guards.py`, `hooks.py`, `run-hook.sh`, `hooks/claude.json`).
- **B. Bugs**:
  - the `.claude` path-index bug (F4) and its test;
  - the lease left active after a lost session (F5);
  - the hard-coded version in `test_packaging` (F3).
- **C. Role consolidation**: 14 Claude agent files and 13 Codex profiles become 7 dispatch roles. The roles are carried through `roles.json`, `models.json`, `generate.py`, engine role keys, skills, references and tests.
- **D. Skills**: per-role skills preloaded via `skills:`, with no double-loading. Binding constraints stay inline.
- **E. Minimal borrowed procedures**:
  - fix-round cap;
  - progress ledger and resume protocol;
  - review package;
  - standing-orders register;
  - PASS/ISSUES/BLOCKED report shape;
  - hedge-word verifier rule;
  - diff-size-gated specialist review.
- **F. Mods module (Claude Code only)**:
  - in-process guard;
  - session end handling;
  - standing-order injection and reviewer-independence refusal;
  - `/orchestra-board` pane;
  - verdict toasts;
  - a declared minimum Claude Code version.

Also in scope: the version bump to 2.0.0, plus an engine trim proposal (section 11) that is written up but not implemented.

## 3. Settled decisions (verbatim from the coordinator brief; not reopened)

1. Scope = all including Mods:
   - (a) guard fixes: allow non-force `git push`, `gh pr merge` etc. when no run armed (keep permit gate inside armed run); allow `git stash list/show`, `git restore --staged`; strip heredoc bodies before shlex; `az` gated only on `deployment ... create`; `switch -f` like `checkout -f`; drop bypassable `.claude/settings.json` Edit/Write block; narrow PreToolUse matcher to edit/shell tools; drop extra python probe in run-hook.sh; SubagentStart worker context only for orchestra:* agents.
   - (b) Bugs: `.claude` path-index bug (F4) and failing test_protected_patch_paths; lease left active after lost session (F5); test_packaging hard-coded version.
   - (c) Role consolidation 14 → ~7-8: merge builder-repair into builder (model override dispatch), red-teamer+auditor into one critic role with modes, fold founder-mind into designer-planner as product lens (+ shipped-surface audit as critic axis), gatekeeper+janitor+releaser into one Sonnet operator role with modes gate/cleanup/release, orchestrator kept as main-thread agent but not dispatchable as worker; keep effort variants (reviewer checkpoint, investigator code) ONLY if Agent tool path still needs them (Agent tool overrides model only; Workflow agent() accepts agentType+model+effort). Read-only roles get Edit/Write/NotebookEdit in disallowedTools. Apply consistently to Codex package/profiles with Codex model rules.
   - (d) Per-role skills split, preload via `skills:` frontmatter; stop double-loading (inlined brief + "Read references/…" lines with wrong relative paths); keep binding constraints inline.
   - (e) Borrow minimal: superpowers fix-round cap (rounds 1-3 same builder, 4 Opus repair, 5 breaker), progress ledger + resume protocol, review-package diff to reviewers; pstack standing-orders register pasted verbatim into briefs and PASS/ISSUES/BLOCKED report shape; OMC verifier rule rejecting "should/probably/seems"; gstack diff-size-gated specialist review.
   - (f) Mods module (Claude only): in-process guard via tool.call failing closed, session.end releasing lease, agent.spawn injecting standing orders and refusing reviewer dispatch by builder's own session where feasible, /orchestra-board pane, verdict toasts. Python guard stays for Codex; design how two guards avoid double-firing on Claude and share one rules table/test corpus; pin/declare min Claude Code version.
2. Engine: fix bugs only; NO trimming. The spec carries an "Engine trim proposal (not implemented)" section.
3. Version bump: semver. Removing agent names is breaking, so the version becomes 2.0.0. All manifests must agree, and tests assert equality rather than a literal.
4. Release is authorized by the user: push the branch, open a PR, merge to main, and reinstall locally for Claude Code and Codex. It is planned as the final operator/release ticket, executed by the coordinator.

Derived from decision 1(c), not a new choice: the effort variants stay. OBSERVED: the Orchestra skill and the user's global rules still dispatch single units through the Agent tool. The Agent tool can override the model but not the effort. So `investigator-code` (Sonnet low) and `code-reviewer-checkpoint` (Opus medium) remain as generated variant agent files. Workflow `agent()` dispatch may instead pass `agentType` plus `effort` against the base role.

## 4. Glossary

| Term | Meaning |
| --- | --- |
| Role | A dispatchable worker definition in `config/roles.json`. Its id is the persisted `role` field of an engine card. |
| Mode | One of a role's declared modes. Persisted as the card `mode`; the engine rejects undeclared modes. |
| Preset | A per-mode model/effort selection in `config/models.json`. |
| Variant | A generated agent file (Claude) or profile (Codex) for a preset whose model or effort differs from the role default and cannot be selected at dispatch. Named `<role>-<preset>` (Claude) or `orchestra_<role>_<preset>` (Codex). |
| Dispatch override | Selecting a preset's model at dispatch time instead of through a variant. Claude uses the Agent tool `model` parameter or Workflow `agent({model})`. Used only for `builder` repair round 4 on Claude. |
| orchestrator | The main-thread coordinator agent, selected by `settings.agent`. It is never dispatched as a worker. |
| investigator | Read-only discovery role. Modes: `code`, `docs`. |
| designer-planner | Design and planning role. Modes: `design`, `plan`, and `product`. `product` is the former founder-mind design dossier, the "product lens". |
| critic | Read-only independent challenge and conformance role. Its modes are listed in the row after this one. |
| critic modes | Plan challenge: `requirements`, `feasibility`, `scope`, `judge` (former red-teamer). Conformance: `spec`, `standards`, `ledger` (former auditor). Shipped surface: `surface` (former founder-mind audit). |
| builder | Implementation role. Modes: `implementation`, `frontend`, `sensitive`, `mechanical`, `repair`. |
| code-reviewer | Read-only exact-diff review role. Modes: `checkpoint`, `final`. |
| operator | Sonnet-medium operations role. Modes: `gate` (former gatekeeper), `cleanup` (former janitor), `release` (former releaser). |
| Armed run | A repository whose Orchestra state file exists with `session.active == true`. If there is no state file, or the session is inactive, the run is unarmed. |
| Permit | The engine's release permit for an exact remote, target, argv and artifact under the active lease. Unchanged. |
| Guard rules table | `plugins/orchestra/config/guard-rules.json`. The single data table of tool sets, wrappers, git deny rules, release-class rules and protected paths. Both guards read it. |
| Guard corpus | `plugins/orchestra/config/guard-corpus.json`. A list of `{command or tool payload, expected classification}` cases consumed by the Python unittest and by the mod's `claude plugin test`. |
| Liveness marker | A per-session JSON file the mod writes and heartbeats. It tells the Python PreToolUse hook on Claude that the in-process guard is active for that session. |
| Plugin standing orders | The generic worker contract (current `references/briefs.md`), inlined at generate time into every worker agent body. |
| Project standing-orders register | `standing-orders.md` in the run state directory. The coordinator writes it, copying the binding project rules verbatim. It is pasted verbatim into each brief, by the mod when loaded or by the coordinator otherwise. |
| Review package | Files the coordinator prepares for each review card, outside the repository: base and head SHAs, `git diff --stat`, the full diff, the ticket's acceptance criteria, and the changed paths. |
| Fix round | One repair attempt on a ticket after an independently checked BLOCKED review. |
| Breaker | Round 5. Repair stops, and the ticket routes to critic `judge` plus design or planning, with user escalation. |
| Progress ledger | `progress.md` in the run state directory. An append-only event log used by the resume protocol. |

## 5. Area A: guard fixes

The current guard is in `guards.py` (`classify_command`) and `hooks.py` (`handle_event` PreToolUse). Required behavior is listed below. Classification stays independent of run state. The hook layer applies run state.

| ID | Behavior | Today (OBSERVED) |
| --- | --- | --- |
| A1 | When the run is unarmed, a command classified `release` is allowed. This covers non-force `git push` with one destination, `gh pr merge`, `gh release create`, `npm/pnpm publish`, provider deploys and `az deployment ... create`. It is allowed even inside a multi-segment command such as `git push origin x && gh pr create`. Inside an armed run the permit gate is unchanged: `engine.check_release` must return a current permit, and multi-segment release stays denied. | `hooks.py:137-138` denies every release when `engine is None` (F1). |
| A2 | Rules that always deny stay in force whether or not a run is armed: force push, mirror, `+refspec`, `--all`/`--tags`/`--delete`, multiple destinations, `reset --hard`, `clean -f` without `-n`, `branch -D`, wholesale `add`, `commit -a`, and wholesale checkout/restore. | Unchanged |
| A3 | `git stash list` and `git stash show [args]` are allowed. Every other stash form (bare, push, pop, apply, drop, clear, save, branch, create, store) stays denied. | All stash forms denied |
| A4 | `git restore --staged <pathspec>` (alias `-S`) is allowed for any pathspec, including `.`, when neither `--worktree` nor `-W` is present. `restore --worktree`/`-W` with wholesale pathspecs stays denied. | `restore --staged .` denied |
| A5 | Heredoc bodies are removed before quote-aware segmentation and shlex. The operators are `<<WORD`, `<<-WORD`, `<<'WORD'` and `<<"WORD"`, and the body ends at the line equal to WORD (leading tabs are stripped for `<<-`). Safety rule: when the command consuming the heredoc is a shell interpreter (`sh`, `bash`, `zsh`, `dash`, `ksh`, including through the existing wrappers), the body is classified recursively as a script. A destructive body still denies. A heredoc with no terminator is malformed and denies. | Apostrophes in bodies raise "Malformed shell quoting" |
| A6 | `az` is release-class only when both `deployment` and `create` appear in its words. `az deployment group show`/`list`/`what-if` are allowed. `az repos pr update ... --status completed` stays release-class by default; see open decision O4. | Any `az ... deployment ...` is release-class |
| A7 | `git switch -f`, `--force` and `--discard-changes` deny with the same reason as `checkout -f`. | Allowed |
| A8 | The protected-path check no longer protects `settings.json` under `.claude` (or `.codex`). Still protected: `.claude/hooks.json`, `.codex/hooks.json`, `.codex/config.toml`, `orchestra-*`/`orchestra_*` files under a harness `agents/` directory, any `.orchestra` path component, and the run state directory. Exception: the coordinator-authored `progress.md` and `standing-orders.md` at the state-directory root. | `settings.json` is protected in every session and is bypassable via Bash (F7) |
| A9 | The `PreToolUse` matcher in `hooks/claude.json` narrows from `.*` to `Bash\|Edit\|Write\|MultiEdit`. `hooks/codex.json` is unchanged, because Codex matcher semantics are UNVERIFIED and the Codex advisory delegation check relies on `spawn_agent` reaching the hook. | `.*` on both harnesses |
| A10 | In the common case `run-hook.sh` starts Python once. It tries the versioned names `python3.14` down to `python3.11` via `command -v` with no probe, and execs the first one found. Only when none exist does it fall back to plain `python3`, with the version probe. The Homebrew PATH prefix stays. A new `--cli` first argument execs `orchestra.py` with the remaining arguments, so the mod reuses the same interpreter discovery. | Probe plus exec on every candidate (2 launches) |
| A11 | `SubagentStart` returns `WORKER_CONTEXT` only when the payload `agent_type` starts with `orchestra:`. Otherwise it returns `{}`. `SessionStart` worker detection is unchanged. | Returns worker context for every subagent |
| A12 | Mod handshake. On harness `claude`, PreToolUse first reads the liveness marker (section 10.3). The marker must exist for the payload `session_id`, be fresh (heartbeat less than 15 s old), and carry a `rules_sha256` equal to the SHA-256 of this copy's `guard-rules.json`. If so, the hook returns `{}` before any git or engine work. `--from-mod` skips the marker check. A `session_id` that does not match `^[A-Za-z0-9_-]{1,128}$` skips the marker check, and Python guards. | New |
| A13 | `guards.py` reads the guard rules table at import, and its decisions must match every corpus case. | Rules hard-coded |

Acceptance criteria for area A, each observable as a unittest or command:

- Every row A1 to A13 has at least one passing test. A1 needs tests in both directions: allowed unarmed, and denied armed without a permit.
- A5 has a test proving `bash <<'EOF'\ngit reset --hard\nEOF` denies, and that `cat <<'EOF'\nit's fine\nEOF` allows.
- A12 has tests for a fresh marker (skip), a stale marker, a wrong `rules_sha256`, a malformed `session_id`, and `--from-mod` (each guards).
- `python3 -m unittest discover -s tests -p 'test_hooks.py'` and `... -p 'test_guard_corpus.py'` exit 0.
- Latency is measured and reported as evidence, with no pass/fail threshold: 10 consecutive allowed Bash PreToolUse invocations through `run-hook.sh`, before and after.

## 6. Area B: bugs

- **B-F4.** `_protected` must check every occurrence of `.claude`/`.codex` in the resolved path's parts, not only the first. `test_protected_patch_paths` and `test_underscore_profile_protected` pass an explicit `cwd` (a temp directory). A new test runs the check with `cwd` set to a temp directory nested under a `.claude/plugins/...` path and asserts deny.
  - OBSERVED: at `0ea2ece` the test passes in this clone, because the clone is not under `~/.claude`. Per the audit it fails when the clone lives under `~/.claude` (F4, reproduced there).
- **B-F5.** A run must not stay armed after its harness session ends.
  - The SessionStart hook adds the harness `session_id` to the coordinator context, as a line telling the coordinator to pass `--harness-session <id>` to `start`.
  - `orchestra.py start --harness-session ID` records `session.harness_session` in run state. The key is optional, so state without it stays valid.
  - `hooks/claude.json` registers `SessionEnd` (timeout 10).
  - `handle_event('SessionEnd')` builds the engine for the payload `cwd`. It calls a new `Engine.end_harness_session(session_id)`. When the active session's `harness_session` equals the payload `session_id`, that call does what `interrupt` does (inactive, permits cleared, autonomy cleared, outcome `ended`). Otherwise it does nothing.
  - The call is idempotent. A run started without `--harness-session` is unaffected (legacy and manual CLI behavior, with Codex `Interrupt` unchanged).
  - After a session ends, `start` and `start --new-run` succeed without the lease being copied out of `status`.
  - New CLI `orchestra.py where` prints `{repo, state, standing_orders: bool}` and never prints the lease. The mod uses it.
- **B-F3.** `test_packaging` asserts that the following versions are equal and that the shared value is `2.0.0`, read from the files themselves with no literal in the equality assertion:
  - `plugins/orchestra/plugin.json`
  - `plugins/orchestra/.claude-plugin/plugin.json`
  - `plugins/orchestra/.codex-plugin/plugin.json`
  - `plugins/orchestra-codex/.codex-plugin/plugin.json`
  - the `orchestra` entry in `.claude-plugin/marketplace.json`

  The `2.0.0` value is checked in one place: the release ticket's command, not the unittest.
- **B-F2.** The installed cache was missing the PATH line. No source change is needed. The release ticket verifies that the reinstalled cache copy is byte-identical to the merged tree.

Acceptance: `python3 -m unittest discover -s tests -p 'test_hooks.py'`, `-p 'test_engine.py'`, `-p 'test_integration.py'` and `-p 'test_packaging.py'` exit 0. F5 has an integration test: start with a harness session, deliver a SessionEnd payload, then `start --new-run` succeeds.

## 7. Area C: role consolidation

### 7.1 Final roles (recommended names)

| Role | Modes | Claude default | Claude variants (files) | Codex default | Codex variants (profiles) | Tools disallowed (Claude) |
| --- | --- | --- | --- | --- | --- | --- |
| orchestrator | main | opus-5-5 high | none | no profile (unchanged) | none | none (main thread) |
| investigator | code, docs | sonnet-5-5 medium | `investigator-code` (sonnet low) | sol medium | `orchestra_investigator_code` (luna high) | Agent, Edit, Write, NotebookEdit |
| designer-planner | design, plan, product | opus-5-5 high | none | sol high | none | Agent |
| critic | requirements, feasibility, scope, judge, spec, standards, ledger, surface | opus-5-5 high | none | sol high | none | Agent, Edit, Write, NotebookEdit |
| builder | implementation, frontend, sensitive, mechanical, repair | sonnet-5-5 medium | none (repair round 4 = dispatch override `claude-opus-5-5`) | sol medium | `orchestra_builder_repair` (sol high) | Agent |
| code-reviewer | checkpoint, final | opus-5-5 high | `code-reviewer-checkpoint` (opus medium) | sol high | `orchestra_code_reviewer_checkpoint` (sol medium) | Agent, Edit, Write, NotebookEdit |
| operator | gate, cleanup, release | sonnet-5-5 medium | none | sol medium | `orchestra_operator_cleanup` (luna high) | Agent |

The result is 7 roles, 9 Claude agent files (down from 14) and 10 Codex profiles (down from 13): the 6 role defaults other than orchestrator (Codex generates no orchestrator profile, OBSERVED) plus the 4 named variants. `generate.py --check` therefore reports 19 native profiles instead of 27.

Model mapping checks against the current matrix:
- Every former Opus-high role (founder-mind, red-teamer, auditor) maps to an Opus-high role.
- Every former Sonnet-medium operations role maps to operator, which is Sonnet medium.
- Codex Luna stays limited to `investigator/code` and hygiene (`operator/cleanup`), per AGENTS.md.

Why these names:
- `critic` covers both the before-build challenge and the after-build conformance work without implying either one.
- `operator` covers gate, cleanup and release.
- `investigator`, `designer-planner`, `builder` and `code-reviewer` keep their v1 names to limit churn.
- Considered and rejected: `reviewer` for critic (it collides with code-reviewer), `verifier` (it implies machine proof), and `ops` (too terse for an agent listing).

### 7.2 Mechanics

- **models.json schema.**
  - The Claude preset `builder.repair` gains `"dispatch": "override"`. `generate.py` emits no variant file for override presets, and the coordination skill tells the coordinator to pass the model at dispatch.
  - Presets without `dispatch` behave as today: a variant file is emitted when the model or effort differs from the default.
  - Codex presets always produce variant profiles, because a Codex dispatch-time model override is UNVERIFIED.
- **Read-only roles.**
  - investigator, critic and code-reviewer, including their variants, get `disallowedTools: Agent, Edit, Write, NotebookEdit`.
  - Their report, research notes or review JSON body is returned as the final message, and the coordinator records it to the named path. The briefs contract changes to say so.
  - Bash can still write files, so this is partial protection only (REASONED).
  - On Codex, the equivalent read-only setting is applied only if investigation I1 confirms that a profile key exists for it. Otherwise the gap is recorded in `docs/roles.md`.
- **orchestrator not dispatchable.**
  - The engine already removes `orchestrator` from dispatchable roles (`engine.py` `_contracts`, OBSERVED).
  - On Claude, its description starts "Main-thread coordinator only; never dispatch as a subagent."
  - When mods are loaded, an `agent.offer` hook hides `orchestra:orchestrator` from the model's agent listing (section 10.4).
  - It keeps `settings.agent` (see O1).
- **Engine role keys.** These are persisted identifiers, renamed because decision 1(c) settles it, not by judgment:
  - `releaser` becomes `operator` with `mode == 'release'`. This covers the one-terminal-release-card rule, `_pre_release_ids` and `_completion_evidence`.
  - The review-capable set `('code-reviewer', 'auditor', 'red-teamer')` becomes `('code-reviewer', 'critic')` in `add_task`, `_read_review` and `_start_assignment`.
  - Builder `repair` validation is unchanged.
  - The audit and red-team method references move with the skills.
  - Changing `roles.json` changes the contract hash, so any live v1 run must start anew. OBSERVED: the local state directory holds 14 run directories and no `state.json`, so no local run is affected.
- **Contract root.** `_contracts` resolves `methods` relative to `plugins/orchestra/skills/` instead of `skills/orchestra/`, so per-role skill files count as method files. The containment check stays.
- **Codex package and install.**
  - `generate.py` regenerates `plugins/orchestra-codex/`.
  - `orchestra.py install-profiles` already removes receipt-owned profiles that are no longer generated (`profiles.py:91-92`, OBSERVED). So reinstall removes the old `orchestra_auditor.toml` and similar files without touching unowned files.
- **Routing.** `config/flow.json` lanes contain no role names (OBSERVED). Only its prose consumers change. `routing.audit_axes` keeps the `spec`/`standards`/`ledger` axes. The `surface` critic mode is dispatched by coordinator judgment and is not part of `audit-policy` (exclusion X6).

Acceptance criteria for area C:
- `ls plugins/orchestra/agents` lists exactly these files: `builder.md`, `code-reviewer.md`, `code-reviewer-checkpoint.md`, `critic.md`, `designer-planner.md`, `investigator.md`, `investigator-code.md`, `operator.md`, `orchestrator.md`.
- `ls plugins/orchestra/profiles/codex` lists exactly the 10 profiles in 7.1: `orchestra_builder`, `orchestra_builder_repair`, `orchestra_code_reviewer`, `orchestra_code_reviewer_checkpoint`, `orchestra_critic`, `orchestra_designer_planner`, `orchestra_investigator`, `orchestra_investigator_code`, `orchestra_operator`, `orchestra_operator_cleanup` (each `.toml`).
- `test_packaging` asserts the role set, the read-only `disallowedTools`, Luna assignments `[('investigator','code'), ('operator','cleanup')]`, and Codex `builder.repair == sol high`.
- `test_engine` covers: the operator release card as the terminal card; critic `review_of`; critic refused for inline execution; old role names rejected as an unavailable role.
- `generate.py --check` exits 0.

## 8. Area D: per-role skills

| Skill directory (`plugins/orchestra/skills/`) | Preloaded by | Source content |
| --- | --- | --- |
| `orchestra/` (existing) | main session (SessionStart context) | `SKILL.md`, plus `references/coordination.md`, `cli.md` and `briefs.md`, plus the new procedures from section 9 |
| `orchestra-investigate/` | investigator, investigator-code | `investigation.md` |
| `orchestra-design/` | designer-planner | `design.md`, `planning.md`, founder design dossier (as `product` mode) |
| `orchestra-critique/` | critic | `red-team.md`, `audit.md`, founder shipped-surface audit (as `surface` mode), verifier rule |
| `orchestra-build/` | builder | `building.md`, fix-round note |
| `orchestra-review/` | code-reviewer, code-reviewer-checkpoint | `review.md`, verifier rule, diff-size gating |
| `orchestra-operate/` | operator | `gates.md`, `closeout.md` |

Rules:
- A worker agent body contains three things only: the role prompt (binding constraints), the plugin standing orders (briefs contract), and one plugin-root line naming the CLI location.
- The body has no "Read references/…" or "Read SKILL.md" lines, and no inlined method text. Method text arrives once, through `skills:` frontmatter.
- The orchestrator body inlines the coordination procedure, because it is the binding main-thread contract, and drops the "Read SKILL.md and references/coordination.md" line.
- Codex profiles have no preload mechanism (REASONED). Their `developer_instructions` therefore contain the role prompt, the standing orders and the role skill body, all generated from the same files.
- The frontmatter skill name format for plugin skills (`orchestra-build` or `orchestra:orchestra-build`) is UNVERIFIED and is settled by I1 plus the live check in B4.

Acceptance criteria for area D:
- `grep -rn "Read references/\|Read SKILL.md" plugins/orchestra/agents` returns nothing.
- Each worker agent has exactly one `skills:` entry that resolves to an existing skill directory (test).
- The total size of `plugins/orchestra/agents/*.md` is under 32,000 bytes. OBSERVED baseline: 64,335.
- Live check: a dispatched `orchestra:builder` agent quotes a sentinel line from `orchestra-build/SKILL.md` in its first reply without calling Read or Skill.

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
- **E7 Diff-size gating.**
  - The final review always covers the 7 categories.
  - Specialist lenses (critic or code-reviewer briefs for security, frontend or visual work) are added only when two conditions hold: `git diff --shortstat BASE..HEAD` reports more than 50 changed lines, and the changed paths match the lens surface.
  - At 50 lines or fewer, no specialists are added.

Acceptance: each of E1 to E7 appears in exactly one skill file (orchestrator procedures in `skills/orchestra/references/coordination.md`; worker rules in the matching role skill). A grep-based packaging test asserts the key phrases: `STATUS: PASS|ISSUES|BLOCKED`, `Round 5`, `standing-orders.md`, `progress.md`, `more than 50 changed lines`.

## 10. Area F: mods module (Claude Code only)

### 10.1 Files and registration

- The module files are `plugins/orchestra/hooks/mods.json` (`{"modules": ["./mod/orchestra.ts"]}`), `plugins/orchestra/hooks/mod/*.ts`, `plugins/orchestra/hooks/mod/*.test.ts` and `plugins/orchestra/types/index.d.ts`. The types file holds `PluginState` for any `$.state` value.
- In `.claude-plugin/plugin.json`, `"hooks"` becomes `["./hooks/claude.json", "./hooks/mods.json"]` and `"types": "./types/index.d.ts"` is added.
  - OBSERVED: `claude plugin validate` accepted both a hooks array and a combined file in a scratch probe.
  - UNVERIFIED: whether both files load at runtime. The thin slice B1 proves it.
- The mod files are excluded from the Codex package (the `codex_package` exclusion list). `hooks/codex.json` is untouched.
- Module rules (documented engine constraints): relative imports only, no dynamic import, string-literal event names, `$` calls spelled in full, no Node or DOM.

### 10.2 Version floor

- Function hooks need Claude Code 2.1.287 or later; 2.1.289 is tested.
  - OBSERVED: `plugin.json` has no minimum-version field. `engines` and `minClaudeCodeVersion` are reported as unknown and ignored.
- The floor is therefore declared in `README.md` and `docs/hooks.md`, and enforced at runtime: in `session.start` the mod reads `$.session.version()`. If `base` is missing or lower than 2.1.287, the mod writes no marker and installs no guard, so the Python guard covers the session.
- A newer build whose API drifted fails module validation at load. That leaves no marker, and Python again covers the session (the safe direction).

### 10.3 In-process guard and the double-fire contract

- At `session.start` the mod reads `${$.plugin.root}/config/guard-rules.json` with `$.fs.read` and computes `rules_sha256`. It then writes the liveness marker `${XDG_STATE_HOME:-$HOME/.local/state}/orchestra/mods/<session_id>.json` containing `{session_id, heartbeat_ms, plugin_version, rules_sha256}`, and refreshes it every 5 s with `$.clock.every`. `session.end` overwrites the marker with `heartbeat_ms: 0`, which the Python check treats as stale.
- `on('tool.call', {tool: 'Bash'|'Edit'|'Write'|'MultiEdit'})` classifies the input with a TypeScript port of the shared rules:
  - `deny` returns `{deny: reason}`;
  - `allow` calls `next(e)`;
  - `release` delegates to Python through `$.process.run(['/bin/sh', <root>/scripts/run-hook.sh, 'PreToolUse', '--harness', 'claude', '--from-mod'], {stdin: payload})`, because only the engine knows the armed state and permits. That process starts only for release-class commands. Its deny is returned as `{deny}`.
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
  - The shell tokenizer is code in both languages. The corpus is the parity contract and must include every A-row case and every existing `test_hooks` command.

### 10.4 Agents

- `on('agent.offer', {agent: 'orchestra:orchestrator'})` returns `{isOffered: false}`.
  - Main-thread selection through `settings.agent` is not an offer per the documented types (REASONED). The B5 live check proves it.
- `on('agent.spawn')` handles `subagentType` values that start with `orchestra:`:
  - (a) If `parentAgentId` names an agent in `$.agent.list()` whose `type` starts with `orchestra:` and is not the orchestrator, it denies with "Workers do not delegate". This is defense in depth over `disallowedTools: Agent`.
  - (b) For `orchestra:code-reviewer*` and `orchestra:critic`, it denies when `parentAgentId` names an `orchestra:builder` agent. This is "refuse reviewer dispatch by builder's own session where feasible".
    - Not feasible and excluded: detecting that a resumed builder is reused as a reviewer through SendMessage, or that a Workflow agent with an unlisted id is a builder. Unlisted parents are allowed, so Workflow dispatch is never broken.
  - (c) If `orchestra.py where` (run once per session through `run-hook.sh --cli`, then cached) reports `standing_orders: true`, the hook appends `<state>/standing-orders.md` verbatim to `prompt` under the E4 heading, unless the prompt already contains that `sha256:` line.

### 10.5 UI (never logic)

- `/orchestra-board` is registered in `session.start` and answered by `command.run`. It opens a pane (`$.ui.open`, `ui.render` on `Pane`) that lists cards (id, role/mode, state, worker), the session's active flag and capacity. The data comes from `run-hook.sh --cli status`, refreshed every 5 s while the pane is open. The lease is never rendered.
- Verdict toasts: after a Bash `tool.call` whose command runs `orchestra.py` with `review`, `gate` or `accept`, the mod shows `$.ui.toast` with the receipt's verdict or exit. An unparseable result shows no toast.
- Drawing happens only in the terminal and the Desktop Code tab, and nothing depends on it.

Acceptance criteria for area F:
- `claude plugin validate plugins/orchestra` exits 0 and lists `tool.call`, `session.start`, `session.end`, `agent.offer`, `agent.spawn` and `command.run`.
- `claude plugin test plugins/orchestra` exits 0 with the corpus parity test included.
- Live, in an interactive session started with `claude --plugin-dir <worktree>/plugins/orchestra`:
  - the marker appears and its mtime advances;
  - `git stash` is denied, with no Python PreToolUse work, proven by a debug-log line or timing;
  - `git stash list` runs;
  - `/orchestra-board` renders;
  - `orchestra:orchestrator` is absent from the agent listing, while the main thread still runs as the orchestrator;
  - after `/exit` the marker is stale and the F5 SessionEnd has released the run.
- The same checks under `claude -p` are recorded as observed, whatever the outcome.

## 11. Engine trim proposal (not implemented)

Decision 2 forbids trimming in 2.0.0. This table is advisory, for the user's later decision. Evidence common to every row (OBSERVED): the local state root holds 14 run directories and zero `state.json` files, so the engine has never recorded a run on this machine. Runs on other machines are UNVERIFIED. Test counts come from `tests/test_engine.py` (45 tests) and the other test modules.

| Candidate | What it does | Evidence of use / non-use | What breaks if removed | Recommendation |
| --- | --- | --- | --- | --- |
| Release permits plus `release` CLI | Permit bound to remote, target, argv, artifact and lease. Executes the configured release with a timeout and receipt. | About 12 engine tests and 4 integration tests. Release is disabled by default policy. No local receipts. | Armed-run release gating (A1 keeps the permit gate inside armed runs) and release receipts. | **Keep** for 2.0.0. It is the only structural release check, and A1 removes its friction outside runs. Revisit after real runs exist. |
| Review groups (`review-groups`, `routing.review_groups`) | Groups reported builder cards by outcome; isolates foundations. | 1 routing test. Advisory output only. | The coordinator groups by hand, as the prose already says. | **Trim candidate.** Fold into coordination prose. |
| Audit policy (`audit-policy`, `routing.audit_axes`) | Maps boolean facts to audit axes. | 1 routing test. The coordinator supplies the booleans itself. | Nothing structural. | **Trim candidate.** |
| `route` CLI plus `flow.json` lanes | Maps coordinator-chosen booleans to a lane. | 3 routing tests. The global rules duplicate the lanes. | `route` output. `flow.json` is also read by docs. | **Trim candidate** (CLI). Keep `flow.json` as documentation data. |
| Autonomy ledger (`autonomy`, `hook_stop`) | Capped Stop-hook continuation under an intact ledger. | 2 engine tests plus 1 hook test. Never armed locally. | Explicit unattended continuation. | **Keep, reassess.** It is the only structural cap on unattended loops, and the user's rules require a ledger for unattended runs. |
| Lease and session | Coordinator consistency token. Requeues running cards on a new session. | Used by every coordinator command. F5 showed it is not secret, since `status` prints it. | Interruption semantics; protection against late reports. | **Keep.** F5 fixes the lockout. Consider not printing the lease from `status` later. |
| Contract-hash invalidation | Any change to `roles.json`, a method file or `SKILL.md` invalidates a live run. | 1 engine test. Every plugin update kills live runs. | Detection of instruction drift mid-run. | **Trim candidate**, or narrow it to role/mode sets only. |
| 7-category final review with artifact echo | Final JSON must cover 7 categories and echo the artifact. `required_review_categories` cannot shrink the set (F7). | Many engine tests. | Structural completeness check for final review. | **Keep the coverage check.** Fix the union so policy can narrow it (bug-class, deferred: X5). |
| Whole-repo artifact hash (F6) | Evidence bound to a hash of every tracked and untracked file. | REASONED: parallel writers stale each other's evidence. | Exact-artifact binding. | **Change, not trim**: bind to owned paths plus HEAD. This is an evidence-model change, deferred (O3). |
| Reservations (files/resources) | Overlap check at dispatch. | Many engine tests. Not enforced at edit time. | Collision detection between cards. | **Keep.** |
| Gates and secret scan | Run configured argv; record exit, log and hash. | Several engine and integration tests. | Gate evidence binding. | **Keep.** |
| `policy.reserved_ports`, `policy.denied_tools` | Policy keys with no consumer (F7, OBSERVED by grep). | None. | Nothing. | **Trim** (remove from the default policy) in a later release. |

## 12. Open decisions

| ID | Question | Recommendation | Blocking? |
| --- | --- | --- | --- |
| O1 | Keep `settings.agent: "orchestra:orchestrator"`, which forces the Opus-high coordinator in every session, including answer-lane questions? | Keep for 2.0.0: it is unchanged v1 behavior and outside the settled scope. Revisit separately. | No |
| O2 | Who releases the lease at session end? Decision 1(f) says the mod's `session.end` releases it. The documented ordering is that `session.end` fires after the classic SessionEnd hooks. | The classic `SessionEnd` hook, a Python implementation shared with Codex logic, performs the release in every Claude session, with or without mods. The mod's `session.end` retires the liveness marker and may call the same idempotent entry. This is a dossier deviation: it meets the same observable acceptance with one implementation that works without mods. | No (the acceptance criterion is identical either way) |
| O3 | Rebind evidence from the whole repo to owned paths (F6)? | Defer to 2.1. It is an evidence-model change, not one of the listed bugs, and decision 2 limits the engine to bug fixes. | No |
| O4 | Does `az repos pr update ... --status completed` stay release-class? A literal reading of "`az` gated only on `deployment ... create`" would un-gate it. | Keep it gated inside armed runs. It is the Azure Repos equivalent of `gh pr merge`, which decision 1(a) keeps under the permit gate. Unarmed, it is allowed by A1 anyway. | Confirm before B2 acceptance; default applies |
| O5 | Agent-file size budget (32,000 bytes) | Accept as the acceptance threshold. | No |

## 13. Exclusions

- X1: No engine trimming (section 11 is a proposal only).
- X2: No change to `hooks/codex.json` beyond the regenerated package. The Codex advisory `ORCHESTRA_ROLE` delegation check stays. It is dead on Claude, where narrowing the matcher removes it from the path.
- X3: The engine does not enforce the fix-round cap, review packages, the report shape or the verifier rule. They are prose procedures.
- X4: No new reservation enforcement at edit time.
- X5: Not fixed in 2.0.0: the `required_review_categories` union, and the lease printed by `status`.
- X6: `surface` is not added to `audit-policy` axes.
- X7: No `$.store`-based autonomy ledger, AbovePrompt liveness band, or workflow-nudge port. These were audit ideas outside decision 1(f).
- X8: No hostile-worker isolation claims. Mods are unsandboxed and can read environment variables.
- X9: `SPEC.md` and `PLAN.md` (v1) are kept as history. Each gets only a one-line pointer to the v2 documents.

## 14. Risks

| Risk | Direction | Mitigation |
| --- | --- | --- |
| Mods API is early-access and its `.d.ts` changes per build | A mod fails to load | Version floor plus a marker-gated Python fallback: a failure falls back to the full Python guard, never to an unguarded session. |
| The heartbeat window: after a crash unloads mods, up to 15 s of stale-but-fresh marker | Guard gap of 15 s or less | Short window, and the guard is best-effort by charter. The live check records the actual crash-unload behavior if it can be induced. |
| The shell tokenizer is implemented twice | Parity drift | The shared corpus is mandatory in both runners. The B5 checkpoint reviews parity. |
| Heredoc stripping could hide destructive input | Silent allow | A5 recursive rule for shell interpreters, with a test. Heredocs into other interpreters (for example `python3 -`) were not inspected before either. That gap is unchanged and documented. |
| Unarmed release allow (A1) widens what a non-Orchestra session may push | More allowed actions | This is the settled decision. Destructive rules still deny, and harness permissions still apply. |
| `skills:` preload name format or behavior differs from the docs | Methods missing in workers | Live check in B4. If it fails, the fallback is inlining the role skill at generate time, which is still a single source. This is routed back to design if chosen. |
| Agent tool `model` may accept aliases only | Round-4 override fails | I1 verifies. The fallback alias is `opus`. |
| Persisted role rename invalidates v1 runs and user-authored briefs that name old agents | Breaking change | The major version is 2.0.0. No local runs exist (OBSERVED). Release notes list the name mapping. |
| The user's global rules name v1 roles (founder-mind, red-teamer, auditor, gatekeeper, janitor, releaser, builder-repair) and a local `models.json` patch | Stale guidance after release | Reported to the user. This repository and its workers never edit user configuration. The repo already ships `claude-sonnet-5-5`, so the local patch becomes unnecessary (verified in the release ticket). |
| The E1 round-4 Opus repair differs from the user's global note that Opus repair fires after the first checked findings | Policy drift | Decision 1(e) settles this. Flagged to the user for their rules file. |
| Coordinator-authored files are allowed in the state dir (A8 exception) | A worker could edit `standing-orders.md` | Read-only roles lack Write. The coordinator verifies the register's `sha256:` line before dispatch. Advisory text only. |
