---
name: test-quality
description: "Gives the rules for tests that can fail and the test-hygiene pass. Load when doing the hygiene pass before the PR, or when a unit's tests keep failing for unclear reasons. Not for a routine unit that adds one behavior test."
---
# Test quality

## A test worth keeping
- Before you add a test, answer: which behavior it protects, which real regression would break it, and why existing tests miss it. No answer means extend an existing test or skip it.
- Assert through the public interface: what a user or caller sees.
- Expected values are literals or values from the spec. Never compute them with the code under test.
- Run the two-edit check. Break the behavior: the test must fail. Change internals and keep the behavior: the test must pass.
- Mock only at system boundaries (network, clock, randomness, storage). Never mock your own modules.
- An "absence" check (nothing shown, no call made) needs a paired positive case in the same test.
- Use fake timers and fixed dates for time. Never use real sleeps.
- Tests that share module state (caches, singletons, stores) reset it between tests.
- If a test is hard to write, write the call you wish existed first. Heavy setup means the interface is too wide. A test that needs many mocks means you should inject the boundary.

## Red first
- For new behavior, write the test and see it fail for the right reason before the code exists. Name any exemption (rename, copy, style, docs, config).

## Never weaken a gate silently
- Every added skip, `.only`, suppression, raised timeout, changed snapshot, or lint or type config change gets one report line with its reason. A failing test is fixed, never silenced.

## Hygiene pass before the PR
- In the changed area, remove duplicate tests, tests of internals, and tests of mocks.
- Fix or delete every skipped test.
- Replace markup snapshots with behavior assertions.
- Remove suppressions that have no reason.
- Keep tests few, fast and at behavior level. Use the repo's tools. Add none.

## Read checks honestly
- Read the exit code from the checker itself, never after a pipe. A pipe to `tail` hides failures.
- A check that passes at once on new code, or fails oddly, points at the wrong target, a cache or a stale build. Rerun on the real files.
- "Tests pass" means the tests you changed and the ones covering the changed code ran with zero failures in this state of the tree. Words like "should" or "probably" mean you have not run it.

Sources: mattpocock/skills@59db609, pstack-claude@47c6f80, orchestra v2.15.3.
