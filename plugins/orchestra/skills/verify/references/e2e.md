# Agentic e2e

Rules for any e2e test written or run in a repo. A repo that uses the `e2e` runner (agentic e2e) follows all of them; read its project skill and the `e2e` section of its `AGENTS.md` first.

## Write from the user's point of view
- A test is a real path through the app, as a user or QA would walk it. One behavior per test. Never derive a test from the implementation (selectors, internals, state shape).
- Try to break it: a first-time user, edge input, state after a reload, error paths, a back button, a double submit.
- The runner's explore and bug-bash modes find problems; a repro test proves each one. Keep the repro test, not the exploration. `e2e explore --changed-since <base>` explores what the branch changed.
- A repro test lives inside the config's `tests` glob (bug bash uses `tests/bugbash/` with the `bugbash` tag), or the runner never selects it. Check the glob first.

## Run only what the change can affect
- Commit first, then `e2e run --changed-since <base>`. Preview what would run with `e2e list --changed-since <base>`. It reads committed changes only: a file only the working tree changed is named, never read.
- The flag scopes a run only when `filters` is set in the e2e config (`decisionFilter`, the Jev decision model). Without `filters`, nothing is left out.
- The filter fails open: with no model key, or when its calls fail, it warns and runs every test. Read the run's "left out" count; a run that left out none was not scoped.
- Run through the gate: `python3 <plugin>/scripts/lean.py gate e2e -- e2e run --changed-since <base>`. It refuses an unscoped run.
- A full e2e run only when the owner asks (they set `ORCHESTRA_E2E_FULL=1`). Without a flag the runner runs everything, so never run it bare.
- A change to the e2e config or a lockfile anywhere on the branch forces every test, because the filter reads the whole branch diff against the base. Splitting commits does not help. Put those changes on their own branch or PR, and tell the owner before anything runs.
- In CI, pass `--changed-since` only on `pull_request`, never on `pull_request_target`. Check out with `fetch-depth: 0`, or the run fails `INVALID_CHANGED_SINCE`.
- Each run gets its own port. Never share a port or data dir with another run.

## Keys
- Read keys from the environment. Never print them, write them to a log or commit them.
- The key name depends on the provider in the repo's `e2e.config.ts`: `AI_GATEWAY_API_KEY` for `gateway()`, `TYPESAFE_AI_API_KEY` for `typeSafeAi`. Without it the filter leaves nothing out.

## Upkeep
- `e2e doctor` checks that a run can start (config, engine, models). Run it before you blame the app.
- `e2e upgrade` refreshes the package and the project skill copy under `.agents/skills/e2e`. A stale copy hides newer flags, so run it when the copy is older than the installed version, and tell the owner.

## Another runner (Playwright, Cypress)
The same scoping rule applies with that runner's own filters: a changed-since or related-files option, `--grep`, a tag, `--last-failed`, a shard, or the test file paths. No full run unless the owner asks.
