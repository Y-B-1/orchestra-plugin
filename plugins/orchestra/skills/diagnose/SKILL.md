---
name: diagnose
description: "Gives a loop for finding the cause of a bug and proving the fix. Load when a bug's cause is not yet known, a test fails for an unclear reason, or a fix did not hold. Not for an ask that already names the exact fix."
---
# Diagnose a bug

## Reproduce first
- Build one command that shows the reported symptom before you read code for a theory. It must be deterministic and run in seconds. It asserts the symptom the user saw, not "does not crash".
- If the failing input is large, remove one element at a time until removing any more turns the command green.
- If no command can be built (production data, credentials, a device), stop and report BLOCKED with the exact next step. Never fix blind.

## Find the cause
- A report names a symptom, not a cause. A wrong value on one page often comes from a shared helper, hook or data layer. Trace back to where the bad value is first made.
- Write 3 to 5 ranked hypotheses. Give each one a prediction you can test. Change one variable per probe.
- Tag debug output with a unique marker such as `[DEBUG-a1]`. Remove every tagged line before you commit.
- After two failed fixes on one assumption, stop patching. Test the assumption itself. If it does not hold, report a design question.
- A flaky or order-dependent failure is a bug. Raise its rate: repeat it, shuffle order, run the file alone and with others. Name the cause before any retry, longer timeout or skip.

## Prove the fix
- Write a test that fails at the starting commit for the right reason and passes with the fix. Use the same command text for red and green.
- If you forced the red by editing code, diff the file to check the edit landed. A red from an unrelated error is not evidence.
- Test through the path a real trigger uses: the click, the timer, the event, the route. Calling an inner function can miss the case the user hit.
- Fix at the source, then check every other caller of the code. The final message gives the cause in one sentence, where it was, and the other places that shared it.

## After the fix
- Name the missing check that would have caught this class of bug (a test seam, a lint rule, a type, an assertion in a shared helper). Add it if it is small. Otherwise list it as a follow-up.

Sources: mattpocock/skills@59db609, pstack-claude@47c6f80, orchestra v2.15.3.
