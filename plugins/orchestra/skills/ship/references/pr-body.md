# PR body

Keep it short. Use the project's own domain words. Sections, in order:

## Summary
One view that makes the point, whichever is smallest: pseudocode for logic, a call tree for control flow, a component or file tree for structure, a `diff`-style tree when the shape exists and only part changes, a Mermaid sequence for interaction. One or two views, not all.

## Evidence
Before and after, per ask. Order of strength: screenshot for a visual change, then test or command output. Name the test that failed before and passes now. Give the exact commands you ran with exit codes. A blocked check is listed as blocked.

## Merge danger
- Door: one-way (data migration, deleted data, public API, published artifact) or two-way (a revert undoes it).
- Blast radius: one word, plus who breaks (consumers, mobile layout, auth, money).
- Files a human should read, and any that match `sensitive_paths`.

## Reviewer guide
- Where to start: the two or three core files, in reading order.
- Mechanical or generated files to skim.
- Decisions you made that the reviewer may want to change.
- Anything held or left for a later phase.

Link the ticket, design doc or dashboard that explains intent. Update the body whenever a push changes the diff.
