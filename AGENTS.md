# Orchestra plugin development

Build the approved portable workflow, not an application. Keep source reference repositories read-only. Never publish private audit snapshots, credentials, personal paths or product delivery state.

One main coordinator owns state, assignments and integration and can execute reserved inline work alongside disjoint workers. Workers do not delegate. Parallel writers use separate worktrees and own explicit paths; preserve sibling edits. Models follow `plugins/orchestra/config/models.json` (Opus 5.5 `claude-opus-5-5`, Sonnet 5.5 `claude-sonnet-5-5` and Haiku 5.5 `claude-haiku-5-5` only; the generator writes `agents/*.md`): the coordinator follows the user's selection; Opus 5.5 high for critic; Opus 5.5 medium for final reviewer and builder repair; Sonnet 5.5 high for designer-planner and checkpoint reviewer; Sonnet 5.5 medium for builders, the standards lens and docs investigator; Haiku 5.5 high for mechanical and cleanup builders, operator and code discovery. Each worker file pins a `tools:` allowlist from `config/roles.json`. Keep settings fixed in a worker session.

Use Python 3.11+ standard library and Git. Test invalid inputs, stale evidence, independent review, reservations, hooks and install/uninstall behavior. Do not claim arbitrary-shell or hostile-worker isolation from prompts or caller-supplied identifiers. Check live hook/profile discovery separately from unit tests.

Commit each working iteration with explicit paths. Never stage wholesale, stash, force push, reset hard or remove unpreserved work. The only public target is this clean package repository. Keep feedback concise; detailed evidence belongs in docs/BUILD-LEDGER.md.

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
