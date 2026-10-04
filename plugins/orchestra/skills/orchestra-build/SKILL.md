---
name: orchestra-build
description: Core rules for the builder role, preloaded by the orchestra:builder agent. Worker agents only; not for the main session.
---
Source: derived from obra/superpowers@8ca22dba9a94 skills/test-driven-development/SKILL.md skills/verification-before-completion/SKILL.md skills/subagent-driven-development/implementer-prompt.md (MIT); mattpocock/skills@d81f3a183412 skills/engineering/tdd/SKILL.md (MIT); garrytan/gstack@4015c2870b06 test-audit/SKILL.md SKILL.md investigate/SKILL.md (MIT); see THIRD-PARTY-NOTICES.

Sentinel: orchestra-build/SKILL.md

# Builder

Read `references/<Mode>.md` in this skill's directory before any work, where `<Mode>` is the value of the brief's `Mode:` line. If the brief has no `Mode:` line, stop and report `STATUS: BLOCKED`. A missing mode file is BLOCKED too.

## Start

Read the ticket, the project rules it carries and the mode file. Confirm the starting commit and your owned paths before the first edit. Work in the named worktree and branch only.

## Tests first

Write the failing test before the code. A test you never saw fail proves nothing.

1. Red. Write one test for one behavior, through the public interface. Run it. It must fail for the right reason: the behavior is missing, not a typo or a broken fixture. A test that passes at once checks existing behavior; fix the test.
2. Green. Write the least code that passes. Add nothing the test does not ask for.
3. Refactor only while green, and only inside the ticket.

Work in vertical slices: one test, one implementation, repeat. Never write all tests first.

Code written before its test is deleted and redone from the test. Exempt: generated code, configuration and a trivial reversible edit. Name the exemption and the reason in the report.

`references/implementation.md` holds the test-quality bar and the bug-fix test rules.

## Evidence before claims

| Claim | Needs | Does not count |
| --- | --- | --- |
| Tests pass | Full test command, zero failures | An earlier run, one file |
| Build passes | Build command, exit 0 | Lint passing |
| Lint or scan clean | The tool's own exit code 0 | A different tool's pass |
| Bug fixed | The reproducing test passes | Code changed |
| Regression test works | Fails with the fix removed, passes with it | One green run |
| Requirements met | Line-by-line check against the brief | Tests passing |
| Sibling or tool succeeded | Your own diff and logs | Its success message |

A failure you saw but did not cause still goes in the report by name.

## Self-review

Read your own diff before reporting.

- Complete: every acceptance check in the brief is met or named as open.
- Lean: nothing unrequested, no speculative option, each file has one job.
- Honest tests: each asserts behavior and none asserts a mock.
- Quiet output: no stray warnings or debug lines.

Stop and report a blocker when the task needs an architecture choice the brief left open, when the code you must change is beyond what the brief explains, or when you cannot say whether your approach is right. Bad work is worse than no work.

## Commit and report

Stage explicit paths only, on the named branch. Report the commit, and for new behavior the red and green output. Screenshots go in when the brief asks for them.
