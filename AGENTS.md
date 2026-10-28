# Orchestra plugin development

Build the approved portable workflow, not an application. Keep source reference repositories read-only. Never publish private audit snapshots, credentials, personal paths or product delivery state.

The plugin is Orchestra 3.0.0: one coordinator skill (`skills/orchestra/SKILL.md`, under 200 lines), the `/orchestra:goal` command, five agents and three hooks in `scripts/lean.py`. The main session is the coordinator: it writes the ask ledger (`.git/orchestra/sessions/<session id>/asks.md`, one per session), runs independent units in parallel in one Workflow and does one unit itself. Builders with disjoint files share the checkout; units that must edit the same file use separate worktrees. Builders do not delegate and never revert or stage sibling edits. Models: Opus 5.5 `claude-opus-5-5`, Sonnet 5.5 `claude-sonnet-5-5` and Haiku 5.5 `claude-haiku-5-5` only, pinned in each `agents/*.md` frontmatter with `effort` and a `tools:` allowlist: builder Sonnet 5.5 medium, reviewer Opus 5.5 medium, planner Sonnet 5.5 high, critic Opus 5.5 high, investigator Haiku 5.5 high. The coordinator follows the user's selection.

Use Python 3.11+ standard library and Git. Test the guard's denies and allows, the Stop hook, the goal CLI, invalid inputs and the plugin layout. Do not claim arbitrary-shell or hostile-agent isolation from a guard that reads command text. Check live hook discovery separately from unit tests.

Commit each working iteration with explicit paths. Never stage wholesale, stash, force push, reset hard or remove unpreserved work. The only public target is this clean package repository. Keep feedback concise; detailed evidence belongs in docs/BUILD-LEDGER.md.

Guard: the PreToolUse hook on Bash denies only merging into the default branch (`gh pr merge`, `gh api` merge calls, a push to the default branch, a force push or delete of it). Everything else runs, and Claude Code's permission mode decides it. No Orchestra hook ever asks. The Stop hook keeps a `/orchestra:goal` session going until every ask is done or dropped and the branch is pushed. Details: `docs/hooks.md`.

Checks run locally with `scripts/check.sh` (`--quick` is accepted and runs the same set). Before a release, run `python3 scripts/live-check.py` to test the hooks in real headless sessions (docs/live-check.md); it costs tokens, so check.sh never runs it. `.github/workflows/ci.yml` runs only when started by hand (`workflow_dispatch`).

## Agentic E2E (tester-army `e2e`)

Agentic end-to-end tests live in `tests/agentic/` and run with `npm run test:e2e`. Read `.agents/skills/e2e/SKILL.md` before writing or running one. Model and keys: `e2e.config.ts` + gitignored `.env.e2e.local`; set `APP_URL` (default https://example.com). Python tests in `tests/` are unaffected.

Model routing (Jev acts and judges page text; Luna sees pixels):
- Write `agent.act` goals as a destination or result ("go to the Billing page"), never as a click ("click Billing"). Jev rates click goals "inconclusive".
- Route visual checks to Luna: `agent.assert("…", { agent: "luna", vision: true })`. Route canvas-only or image-only steps with `agent.act("…", { agent: "luna" })`.
- Jev has no vision. A step it cannot confirm fails as `AUTOMATION_UNSUPPORTED` or `ASSERTION_INCONCLUSIVE`. Before you call that a product bug, rerun the step once with `--agent luna`. Only a failure that Luna also reports is a bug.

Run tests to completion without asking:
- When a test you wrote fails because the screen contradicts your wording, read the failure screen, fix the wording, and rerun. Do this up to 2 times without asking.
- Ask the user only when Luna also reports the failure on a goal you cannot reword. That is a likely product bug.
- End every run with one report: pass or fail, the failing step if any, and which model handled each step.
