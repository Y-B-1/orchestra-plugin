# Orchestra plugin development

Build the approved portable workflow, not an application. Keep source reference repositories read-only. Never publish private audit snapshots, credentials, personal paths or product delivery state.

One main coordinator owns state, assignments and integration and can execute reserved inline work alongside disjoint workers. Workers do not delegate. Parallel writers use separate worktrees and own explicit paths; preserve sibling edits. Models follow `plugins/orchestra/config/models.json` (Opus 5.5 `claude-opus-5-5` and Sonnet 5.5 `claude-sonnet-5-5` only; the generator writes `agents/*.md`): Opus 5.5 high for coordinator, designer-planner, critic and final reviewer (except the standards lens, Sonnet 5.5 medium); Opus 5.5 medium for checkpoint reviewer and builder repair; Sonnet 5.5 medium for builders, operator and docs investigator; Sonnet 5.5 low for code discovery. Keep settings fixed in a worker session.

Use Python 3.11+ standard library and Git. Test invalid inputs, stale evidence, independent review, reservations, hooks and install/uninstall behavior. Do not claim arbitrary-shell or hostile-worker isolation from prompts or caller-supplied identifiers. Check live hook/profile discovery separately from unit tests.

Commit each working iteration with explicit paths. Never stage wholesale, stash, force push, reset hard or remove unpreserved work. The only public target is this clean package repository. Keep feedback concise; detailed evidence belongs in docs/BUILD-LEDGER.md.
