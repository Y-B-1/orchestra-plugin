Source: derived from obra/superpowers@8ca22dba9a94 skills/test-driven-development/SKILL.md skills/test-driven-development/writing-good-tests.md (MIT); mattpocock/skills@d81f3a183412 skills/engineering/tdd/SKILL.md skills/engineering/tdd/tests.md skills/engineering/tdd/mocking.md skills/engineering/implement/SKILL.md (MIT); garrytan/gstack@4015c2870b06 test-audit/SKILL.md (MIT); see THIRD-PARTY-NOTICES.

Sentinel: orchestra-build/references/implementation.md

# Builder: implementation mode

This is the first attempt at a ticket from a spec, a plan task or a bug diagnosis. Build exactly what the brief names, test first (see the core rules), and nothing beside it.

## Seams

A seam is the public boundary where a test observes behavior without reaching inside. Test at the seams the brief names. When it names none, pick the public interface of the module you change, then record the choice in your report. Do not test private functions or call order unless order is observable behavior.

## What a good test is

A test reads like a specification of one capability and survives a refactor that keeps behavior. Name the behavior, not the mechanism: "checkout confirms a valid cart", not "checkout calls the payment service".

- Verify through the interface. Do not query a database or file to confirm what the interface can return.
- Take the expected value from an independent source: a literal, a worked example or the spec. A test that recomputes the expected value the way the code does passes by construction.
- Mock only at system boundaries: external services, time, randomness, and sometimes the file system or database. Never mock your own modules. Inject boundary dependencies so a test can replace them.
- Keep test-only code in test utilities, never in production classes.
- Understand what a dependency does before you mock it.

## Value bar

Write a test only when you can answer all four questions. Otherwise extend an existing test or drop it.

1. Which behavior, invariant or contract does it protect?
2. Which credible regression makes it fail?
3. Why does existing coverage not catch that? Prefer a new row in a table-driven test over a near-copy.
4. Does it need a production hook that no production caller needs? If so, test at the real boundary.

A test that breaks under a behavior-preserving refactor asserts implementation. Rewrite it at the owning boundary. The exception is exact output that is a declared contract, such as prompt text, golden files or wire formats; phrase and golden tests are valid there.

## Bug fixes

The reproducing test fails at the starting commit, in its own assertion. An import error, fixture error or environment error is a defect in the test: correct it once or drop it. Then fix. The report records both runs: fails before the fix, passes after.

## Checks

While iterating, run the single test and the type or lint check for the code you touch. Run the owned and derived checks the brief lists before you report. Run the full suite only when the brief names it.

## Stuck

| Problem | Move |
| --- | --- |
| Cannot see how to test it | Write the call you wish existed, then the assertion, then the code |
| Test needs heavy setup | The interface is too wide; narrow it, or report the design problem |
| Everything needs a mock | The module is too coupled; inject the boundary |
| Brief contradicts the code | Stop and report the contradiction as a blocker |
