---
name: diagnose
description: "Gives a loop for finding the cause of a bug, fixing the root cause and proving it, plus correct mode for an owner correction. Load when a bug's cause is unknown, a test fails for an unclear reason, a fix did not hold, or the owner corrects a mistake. Not for an ask that already names the exact fix."
---
# Diagnose a bug

Redact every secret in commands, output and artifacts as `<REDACTED>`; quote only the lines that carry the signal. Read the glossary and decision records for the area if they exist.

## Reproduce first
- Build one command that shows the reported symptom before you read code for a theory. It must be red-capable (asserts the symptom the user saw, not "does not crash"), deterministic, fast and runnable unattended. Run it once and show the output.
- Seams to try, in order: failing test, request script, CLI on a fixture, headless browser, replay of a captured payload, throwaway harness, property or fuzz loop, `git bisect run`, old-versus-new diff. A human-driven script is the last resort.
- Tighten it: faster setup, sharper assertion, pinned time and seed.
- If the failing input is large, remove one element at a time until removing any more turns the command green.
- If no command can be built (production data, credentials, a device), stop and report BLOCKED. List what you tried and name what you need: access, a redacted artifact, or approval for temporary instrumentation. Never fix blind.
- Confirm the command shows the user's failure, not a neighbouring one.

## Find the cause
- A report names a symptom, not a cause. Trace back to where the bad value is first made. A wrong value on one page often comes from a shared helper, hook or data layer. After a regression, read the diff of the affected paths.
- Write 3 to 5 ranked hypotheses, each with a prediction: "if X is the cause, changing Y removes the bug". Discard any without a prediction. Change one variable per probe.
- When the owner is present, show the ranked list before probing so they can re-rank; do not wait if they are away.
- Prefer a debugger over logs; never "log everything". Tag debug output `[DEBUG-a1]` and remove every tagged line before you commit.
- Performance bug: take a baseline measurement first, then bisect. Measure before you fix.
- Flaky or order-dependent failure is a bug. Raise its rate: repeat, shuffle, run alone and with others. Name the cause before any retry, longer timeout or skip.
- A failure only after restart: suspect persisted state first (config, cache, lock file).

## Attack the premise
- When two fixes that share one assumption have failed, stop. Write the assumption in one sentence. Make an observation that comes out differently if it is false (look at how failures are distributed). Do this before a third fix.
- If the evidence contradicts it, the cause is elsewhere: look for what the failures share. If it confirms it, ask the next "why". If the premise cannot be tested, report a design question.

## Fix the root cause
- Ask "why" until the answer is a wrong decision in code. Then decide: if the system may legitimately be in that state, handle it where it broke. If the state should never exist, fix what produced it; a guard, retry, swallowed error or clamp hides the bug.
- A workaround that needs a paragraph of comment means the code is wrong.
- Check for the pattern: find every place with the same fault and fix them all.

## Prove the fix
- Write the regression test before the fix, at a seam that exercises the real call pattern (the click, timer, event, route). If only a shallow seam exists, that is a finding; report it.
- It fails at the start commit for the right reason and passes with the fix, using the same command text. If you forced red by editing code, diff to check the edit landed.
- Rerun the original reproduction. Delete throwaway harnesses.
- The final message gives: the cause in one sentence, where it was, the other callers or places that shared it, and the hypothesis that proved right.

## After the fix
- Name the missing check that would have caught this class (test seam, lint, type, assertion in a shared helper). Add it if small; else list it as a follow-up. If the deciding fact took a deep dig, propose a cheap always-on signal.

## Correct mode (the owner corrects one instance)
When the owner points at one mistake, read `references/correct.md` and apply the correction repo-wide. Do not stop at the instance named.

Sources: mattpocock/skills@59db609 (diagnosing-bugs), pstack-claude@47c6f80 (principle-attack-the-premise, principle-fix-root-causes, correct), orchestra v2.15.3.
