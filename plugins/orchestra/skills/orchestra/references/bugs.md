# Bugs

Load when an ask reports something broken, a test fails for an unknown reason, or a fix did not hold. Give the builder this file's path in its brief.

## Reproduce first
1. Build a red loop before reading code for a theory: one command that shows the reported symptom, is deterministic and runs in seconds. It asserts the symptom the user saw, not "does not crash".
2. The bug report names a symptom, not a cause. A page that shows a wrong value usually has the fault in a shared helper, hook or data layer. Find where the bad value is first produced and fix it there; then check every other caller of that code.
3. When the failing input is large, cut it one element at a time until removing any remaining element turns the loop green.
4. If no loop can be built (needs production data, credentials, a device), stop and report BLOCKED with the exact next step. Never fix blind.

## Find the cause
- Write 3 to 5 ranked hypotheses, each with a prediction you can test. Change one variable per probe. Trace backward from the wrong value to its source.
- Debug output carries a unique tag such as `[DEBUG-a1]`, and every tagged line is gone before commit.
- Three disproved hypotheses, or two fixes that failed on the same assumption: stop patching. Test the assumption itself, then report it as a design question if it does not hold.
- A flaky or order-dependent failure is a bug. Raise its reproduction rate (repeat, shuffle, run the file alone and with others) until the cause is named. No retry, longer timeout or skip until then.

## Prove the fix
- The regression test fails at the starting commit for the right reason, and passes with the fix. Run red and green with the same command text; a red run on a different or wider command is not evidence.
- Before you trust a red run, check that the change you made to force it actually landed (diff the file), so the red is not from an unrelated error.
- Test through the path a real trigger uses (the click, the timer, the event, the route). A test that calls an internal function directly can miss the case the user hit.
- The final message names the cause in one sentence, where it was, and every other place that shared it.

## After the fix
Name the missing check that would have caught this bug class (a test seam, a lint rule, a type, an assertion in a shared helper). Add it when it is small; otherwise list it as a follow-up in the final message.
