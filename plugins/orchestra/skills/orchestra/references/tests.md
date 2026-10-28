# Tests

Load when a unit adds or changes tests, and for the test hygiene pass before the PR. Builders get the always-on rules in their agent file; this file holds the rest.

## Write the test first
- New behavior and bug fixes: write one test per behavior, run it, and see it fail for the right reason before the code exists. Code written before its test is rewritten test-first or the exemption is named in the report (pure renames, copy, styles, docs, config).
- Red and green use the same command text.

## A test worth keeping
Before adding a test, answer: which behavior it protects, which realistic regression would break it, why existing tests miss it. No answer: extend an existing test or skip it.
- Assert through the public interface: what a user or caller sees.
- Expected values are literals or values from the spec, never recomputed with the code under test.
- Two imagined edits: break the behavior and the test must fail; change the internals and keep the behavior, and the test must pass.
- Mock only at system boundaries (network, clock, randomness, storage); never mock your own modules. An "absence" assertion (nothing shown, no call made) needs a paired positive case in the same test.
- Fake timers and fixed dates for anything time-dependent; never real sleeps.
- Tests that share module state (caches, singletons, stores) reset it between tests, or the module exposes a fresh instance.

## Never weaken a gate silently
Every added skip, `.only`, suppression, raised timeout, changed snapshot, CI change or lint or type config change gets one line in the report with the reason. `lean.py check` lists them; the reviewer judges each one. A failing test is fixed (code or test), never silenced.

## Hygiene pass before the PR
In the changed area and the suite: remove duplicate tests and tests of implementation details or mocks; delete or fix every skipped test; replace markup snapshots with behavior assertions; remove suppressions that have no reason. Keep tests few, fast and behavior-level. Use the repo's existing fast tools; never add tools unasked.

## Checks are evidence only when they can fail
Read a check's exit code from the checker itself, never after a pipe (`| tail` hides failures; use `; echo $?` or the bounded runner). A check that passes at once on new code, or fails oddly, points at the wrong target, a cache or a stale build: rerun on the real files. "Tests pass" means the tests you changed and the ones that cover the changed code ran with zero failures, in this state of the tree.
