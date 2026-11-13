# PR body

Keep it short: a reader gets it in a minute. Link logs and metric tables; never paste them. Use the project's own domain words. Open the PR ready, not as a draft. If the repo has its own template (`.github/pull_request_template.md` or a `PULL_REQUEST_TEMPLATE` folder), fill it and put the sections below inside or under it; never replace or ignore it. Sections, in order:

## Summary
One view that makes the point, whichever is smallest: pseudocode for logic, a call tree for control flow, a component or file tree for structure, a `diff`-style tree when the shape exists and only part changes, a Mermaid sequence for interaction. One or two views, not all. End with "Leaves out": what the change deliberately does not do.

## Evidence
Before and after, per ask. Order of strength: screenshot for a visual change, then test or command output. Name the test that failed before and passes now. Give the exact commands you ran with exit codes. A blocked check is listed as blocked. When the ask names an issue, close it (`Closes #N`) and map each acceptance criterion to its evidence.

## Merge danger
- Door: one-way (data migration, deleted data, public API, published artifact) or two-way (a revert undoes it, and nothing a revert cannot undo has happened: sent messages, data written in a new shape). Check the repo's standing list of one-way changes first.
- Order: what must deploy or migrate first, and how to roll back.
- Blast radius: one word, plus who breaks (consumers, mobile layout, auth, money).
- Files a human should read, and any file the `lean.py check` scan listed as sensitive or secret.

## Reviewer guide
- Where to start: the two or three core files, in reading order.
- Mechanical or generated files to skim.
- Decisions you made that the reviewer may want to change.
- Anything held or left for a later phase.

Link the ticket, design doc or dashboard that explains intent. Update the body whenever a push changes the diff.
