---
name: large-work
description: "Gives a way to split an ask that is too big for one builder. Load when an ask needs more than about 20 minutes of one builder's work, has open unknowns, or changes an interface other units use. Not for prompts that are long but made of small asks."
---
# Large or uncertain work

## Map before you cut
- Write the destination in one sentence. List what is still unknown.
- Turn each unknown into a short read-only research unit that runs in parallel with the known work. Do not cut unknown work into build units yet.
- Split the known work into vertical slices. Each slice works end to end on its own. Ship the thinnest slice first, then widen.
- Do a refactor that new code builds on (a shared helper, a split file) as its own first unit.
- Use a planner and a critic only for this ask, not for the small asks beside it.

## Freeze the interface
- When unit B uses something unit A creates (a component, hook, type, API), write the contract in both briefs: name, signature or props, behavior, file. Freeze it before either unit starts.
- One symbol changed by two units is a conflict. Give it to one unit, or make the later unit depend on the earlier one.
- Name shared resources beyond files: a dev server port, a database, a fixture, a lockfile, the build output folder, generated files. Units that share one run in order, or one unit owns it.

## Specs that can be checked
- A spec states who is affected, what happens now, what must happen instead, and how "done" is checked.
- Acceptance items are pass or fail, checked by a command or by looking. Never write "works correctly" or "handles edge cases". Give a number for "fast".
- List what must not change, with paths. A unit that removes or replaces code gets a Keep list and a Remove list, and its report says which items still hold.

## Premises
- Label each premise observed (you read or ran it), reasoned, or unknown.
- An unknown that the plan depends on gets a short spike first. A plan step that decides nothing is a gap.

## Mechanical changes across many files
- Count the sites before and after with the same search. Report both numbers.
- Regenerate generated files from their source. Never edit them by hand.
- For a rename of something persisted or public: add the new name, move callers in batches, then remove the old name.

Sources: mattpocock/skills@59db609, orchestra v2.15.3.
