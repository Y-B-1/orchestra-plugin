# Agentic e2e

Rules for any e2e test written or run in a repo. A repo that uses the `e2e` runner (agentic e2e) follows all of them; read its project skill and the `e2e` section of its `AGENTS.md` first.

## Write from the user's point of view
- A test is a real path through the app, as a user or QA would walk it. One behavior per test. Never derive a test from the implementation (selectors, internals, state shape).
- Try to break it: a first-time user, edge input, state after a reload, error paths, a back button, a double submit.
- The runner's explore and bug-bash modes find problems; a repro test proves each one. Keep the repro test, not the exploration.

## Run only what the change can affect
- Commit first, then `e2e run --changed-since <base>`. Preview what would run with `e2e list`.
- The filters API (`decisionFilter`, the Jev decision model) leaves out tests unlikely to be affected by the change.
- Run through the gate: `python3 <plugin>/scripts/lean.py gate e2e -- e2e run --changed-since <base>`. It refuses an unscoped run.
- A full e2e run only when the owner asks (they set `ORCHESTRA_E2E_FULL=1`). Without a flag the runner runs everything, so never run it bare.
- A change to the e2e config or a lockfile forces a full run. Commit those apart from the rest, and tell the owner before anything runs.
- In CI, pass `--changed-since` only on `pull_request`, never on `pull_request_target`.
- Each run gets its own port. Never share a port or data dir with another run.

## Keys
- Read keys from the environment. Never print them, write them to a log or commit them.
- The Jev key is `TYPESAFE_AI_API_KEY`. Without it the filter warns and leaves nothing out, so every test runs.

## Another runner (Playwright, Cypress)
The same scoping rule applies with that runner's own filters: a changed-since or related-files option, `--grep`, a tag, `--last-failed`, a shard, or the test file paths. No full run unless the owner asks.
