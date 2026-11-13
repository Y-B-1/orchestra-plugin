# Orchestra plugin development

Build the approved portable workflow, not an application. Keep source reference repositories read-only. Never publish private audit snapshots, credentials, personal paths or product delivery state.

The plugin is Orchestra: one coordinator skill (`skills/orchestra/SKILL.md`, under 200 lines, main session only), six role skills (`build`, `review`, `plan`, `critique`, `investigate`, `operate`) and seven shared situation skills (`diagnose`, `decide`, `test-quality`, `frontend-proof`, `large-work`, `ship`, `verify`) under `skills/`, each loaded only when its situation applies and at most 70 lines, with detail in `references/` files (at most 60 lines) that a routing row or skill names, the `/orchestra:goal` command, twelve agents, three hooks (`scripts/lean.py`, the guard in `scripts/guard.py`), the pre-PR `check` scan in `scripts/check.py` and the test gate in `scripts/gate.py`. `docs/COVERAGE.md` maps every mattpocock/skills and pstack skill to these parts. The main session is the coordinator: it writes the ask ledger (`.git/orchestra/sessions/<session id>/asks.md`, one per session), runs independent units in parallel in one Workflow and does one unit itself. Builders with disjoint files share the checkout; units that must edit the same file use separate worktrees. Builders do not delegate and never revert or stage sibling edits. Models: Opus 5.5 `claude-opus-5-5`, Sonnet 5.5 `claude-sonnet-5-5` and Haiku 5.5 `claude-haiku-5-5` only, pinned in each `agents/*.md` frontmatter with `effort` and a `tools:` allowlist: builder Sonnet 5.5 medium, builder-mechanical and builder-cleanup Haiku 5.5 high, reviewer Opus 5.5 medium, reviewer-light and reviewer-standards Sonnet 5.5 medium, planner Sonnet 5.5 high, critic Opus 5.5 high, critic-fable Fable 5.2 `claude-fable-5-2` high (the only agent on Fable: one at a time, enforced by the hook, with the Opus critic as fallback), investigator Haiku 5.5 high, investigator-research Sonnet 5.5 medium, operator Haiku 5.5 high. An agent that names a skill has `Skill` in its `tools:`. The coordinator follows the user's selection.

Use Python 3.11+ standard library and Git. Test the guard's denies and allows, the Stop hook, the goal CLI, invalid inputs and the plugin layout. Do not claim arbitrary-shell or hostile-agent isolation from a guard that reads command text. Check live hook discovery separately from unit tests.

Commit each working iteration with explicit paths. Never stage wholesale, stash, force push, reset hard or remove unpreserved work. The only public target is this clean package repository. Keep feedback concise; detailed evidence belongs in docs/BUILD-LEDGER.md.

Guard: the PreToolUse hook (Bash, PowerShell, MCP `merge_pull_request` tools) denies merging into the default branch (`gh pr merge`, `gh api` merge calls, a push to the default branch, a force push or delete of it). On the Agent and Workflow tools it denies a second `orchestra:critic-fable` and, during a run, an agent with no Orchestra type (`ORCHESTRA_MATRIX=off` turns that one off). Everything else runs, and Claude Code's permission mode decides it. No Orchestra hook ever asks. The Stop hook keeps a `/orchestra:goal` session going until every ask is done or dropped, the review line is closed, `lean.py gate status` exits 0, the branch is pushed and a pull request holding the current head is open (GitHub remote). Details: `docs/hooks.md`.

Checks run locally with `scripts/check.sh` (`--quick` is accepted and runs the same set). Before a release, run `python3 scripts/live-check.py` to test the hooks in real headless sessions (docs/live-check.md); it costs tokens, so check.sh never runs it. `.github/workflows/ci.yml` runs only when started by hand (`workflow_dispatch`).

## Agentic E2E (tester-army `e2e`)

Runner: `e2e` 0.23.0 with `@e2e-dev/web` 0.15.5, `@e2e-dev/decision` 0.3.2, `ai` 7.0.171, `@ai-sdk/typesafe-ai` 3.0.39 (needs Node 22.22.3+ or 24.8+; Node 20 fails). Orchestra is a plugin with no web UI, so `tests/agentic/template.e2e.ts` is the only test: a template for a project with a UI, tagged `template` and skipped. The old example.com scaffold was removed. This repo's real end-to-end check is `scripts/live-check.py` (real headless sessions, costs tokens, release only).

Config: `e2e.config.ts` sets `filters: [decisionFilter({ model: typeSafeAi.decisionModel('jev-latest') })]` (Jev decides which tests a change can affect) and the Jev decision executor (no screenshots) with Luna as its text model; vision steps use the `luna` agent (`--agent luna`). Key names (names only, values live in the gitignored `.env.e2e.local`): `TYPESAFE_AI_API_KEY` (Jev), `OPENROUTER_API_KEY` (Luna). Set `APP_URL` to the app under test, on an isolated port, never a shared one.

Commands, always scoped: commit first, then `npm run e2e:list` (preview, makes the filter's model call) and `npm run e2e:changed` (`e2e run --changed-since origin/main`). There is no script for a full run, and no full run unless the owner asks (`e2e run` with no flag runs every test; a change to `e2e.config.ts` or the lockfile also forces a full run). Through the gate: `lean.py gate e2e -- npx e2e run --changed-since origin/main`.

Tests follow the docs: arrange, act, assert, one behavior per test, a user path, and an ending `expect`. Read `.agents/skills/e2e/SKILL.md` before writing or running one. Python tests in `tests/` are unaffected.

Model routing (Jev acts and judges page text; Luna sees pixels):
- Write `agent.act` goals as a destination or result ("go to the Billing page"), never as a click ("click Billing"). Jev rates click goals "inconclusive".
- Route visual checks to Luna: `agent.assert("…", { agent: "luna", vision: true })`. Route canvas-only or image-only steps with `agent.act("…", { agent: "luna" })`.
- Jev has no vision in this config (the executor sets no `vision: true`). A step it cannot confirm fails as `AUTOMATION_UNSUPPORTED` or `ASSERTION_INCONCLUSIVE`. Before you call that a product bug, rerun the step once with `--agent luna`. Only a failure that Luna also reports is a bug.

Run tests to completion without asking:
- When a test you wrote fails because the screen contradicts your wording, read the failure screen, fix the wording, and rerun. Do this up to 2 times without asking.
- Ask the user only when Luna also reports the failure on a goal you cannot reword. That is a likely product bug.
- End every run with one report: pass or fail, the failing step if any, and which model handled each step.
