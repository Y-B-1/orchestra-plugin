# Blast radius lens

Find what the change breaks somewhere else. Listing callers is the easy part; the finding is breakage that grep does not show.

## Steps
1. Read the diff: symbols added, changed, deleted, and the behavior change the diff does not spell out.
2. Find the one fact the change is safe because of (for example "this call only drops entries that are already dead"). If it holds, most risks clear at once. Spend the time there.
3. Look where grep stops: the source and pinned version of a library you call, timing (teardown, microtasks, async order), an API's JSON, a database column, a wire format read by another language, a feature flag, a script or job, a config file, docs and generated code.
4. Rate each risk with a real chance and a real cost. Keep confirmed risks. List the checked and cleared ones apart. Cite a real `file:line`. Never invent a caller.
5. Prove the one fact by running real code: a small script or test that imports what the app ships and calls the exact function. Paste what happened.

## Certainty ladder (say where each fact stopped)
1. Said so. 2. Pointed at the line. 3. Walked the failure step by step and it cannot reach. 4. Ran it. 5. Reproduced in the running app.
Step 1 alone counts for nothing. Mark a fact unproven if you stopped below 4 and it is the safety fact.

## When a brief asserts something about existing code
"Make endpoint X public" is a hypothesis. Take the consumer census first, then judge.

## Report
What it does (including the hidden part); the safety fact and how far you proved it; risks; cleared; the cheapest test or repro to run before merge.
