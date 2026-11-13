---
name: test-quality
description: "Gives the rules for tests that can fail and the test-hygiene pass. Load when doing the hygiene pass before the PR or when writing tests that must be able to fail. Not for a routine unit that adds one behavior test."
---
# Test quality

## A test worth keeping
- Before you add a test, answer: which behavior it protects, which real regression would break it, and why existing tests miss it. No answer means extend an existing test or skip it.
- Assert through the public interface: what a user or caller sees.
- Expected values are literals or values from the spec. Never compute them with the code under test.
- Name the ways a test passes while proving nothing, and avoid them: restating the expected value or constant in the test so the code that reads it never runs; asserting on data the test built itself; asserting an empty list where "some result" is the point; pinning an exact error message where callers branch on the error type.
- The payload a mocked boundary receives, a cross-table invariant and a documented default are behavior. Assert the contract, no less and no more.
- Run the two-edit check. Break the behavior: the test must fail. Change internals and keep the behavior: the test must pass.
- Mock only at system boundaries (network, clock, randomness, storage), and prefer a real test database where the repo has one. Never mock your own modules. Give each external operation its own function, so a mock returns one shape with no conditional setup.
- Tells of a test coupled to the implementation: reading a side channel (a SQL query to confirm a write the interface can read back), asserting call counts or call order, testing a private method. Never export an internal only so a test can reach it.
- An "absence" check (nothing shown, no call made) needs a paired positive case in the same test.
- Use fake timers and fixed dates for time. Never use real sleeps.
- Tests that share module state (caches, singletons, stores) reset it between tests.
- If a test is hard to write, write the call you wish existed first. Heavy setup means the interface is too wide. A test that needs many mocks means you should inject the boundary.

## Lean tests
- One test per behavior. Table-driven cases instead of copies.
- Call a pure function directly, not through a subprocess or a built repo.
- No test of a mock, of a type the compiler checks (an invariant the types do not carry is behavior), or of wording.
- For a parser, state machine, retry or ordering rule where examples reach too little, add property tests against the real code, written as invariants. Show each property fail on a broken variant. Use the repo's property-test library; add none unasked.
- Share fixtures; do not rebuild them per test.
- The hygiene pass reports tests added minus tests removed. Every added test must prove a behavior no existing test proves.
- Expected values are literals.
- Runs: one full run per PR (`gate unit --full`), then scoped (`gate unit --scoped`). e2e rules: `<plugin>/skills/verify/references/e2e.md`.

## Red first
- For new behavior, write the test and see it fail for the right reason before the code exists. Name any exemption (rename, copy, style, docs, config).
- Use the fastest seam that can fail: a unit or component test. Write a slow or agentic e2e test after the behavior works and run it once, scoped. Never loop on one as the red signal.

## Never weaken a gate silently
- Every added skip, `.only`, suppression, raised timeout, changed snapshot, or lint or type config change gets one report line with its reason. A failing test is fixed, never silenced.

## Hygiene pass before the PR
- In the changed area, remove duplicate tests, tests of internals, and tests of mocks.
- Fix or delete every skipped test.
- Replace markup snapshots with behavior assertions.
- Remove suppressions that have no reason.
- In a repo with the e2e runner, each e2e test the diff added or touched covers one behavior, has no `.skip`, `.only` or sleep, and is picked up by the config's filters (check `e2e list --changed-since <base>`).
- Keep tests few, fast and at behavior level. Use the repo's tools. Add none.

## Read checks honestly
- A failure whose cause is unknown: load `orchestra:diagnose`.
- Read the exit code from the checker itself, never after a pipe. A pipe to `tail` hides failures.
- A check that passes at once on new code, or fails oddly, points at the wrong target, a cache or a stale build. Rerun on the real files.
- "Tests pass" means the tests you changed and the ones covering the changed code ran with zero failures in this state of the tree. Words like "should" or "probably" mean you have not run it.

Sources: mattpocock/skills@59db609, pstack-claude@47c6f80, orchestra v2.15.3.
