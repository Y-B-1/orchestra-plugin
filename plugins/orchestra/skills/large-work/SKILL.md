---
name: large-work
description: "Gives a way to size, split, hand off and prove work too big for one builder. Load when an ask needs more than about 20 minutes of one builder's work, has open unknowns, runs long or overnight, or the context nears its limit. Not for prompts that are long but made of small asks."
---
# Large or uncertain work

## Size first
- Size by the diff, not the item count: tiny up to 50 changed lines, medium up to 400, large past that or past what one session can hold. Read the touched files first. When the area is unknown, run read-only investigators, one per area.
- Count the asks (changes the owner could accept or reject alone). The tier is the largest ask, never the sum.
- Most work is tiny or medium and needs no map. For a bug report or a feature request before it becomes a unit, read `references/triage.md`.

## Map before you cut
- Write the destination in one sentence. List what is still unknown.
- Turn each unknown into a short read-only research unit that runs in parallel with the known work. Do not cut unknown work into build units yet.
- When no open question is left after charting, drop the map and go back to normal planning. When the ask is too big to see through, or the owner asks for a map, read `references/map.md`.
- Split the known work into vertical slices. Each works end to end. Ship the thinnest first, then widen.
- Do a refactor that new code builds on (a shared helper, a split file) as its own first unit.
- Use a planner and a critic only for this ask, not for the small asks beside it.

## Freeze the interface
- When unit B uses something unit A creates (component, hook, type, API), write the contract in both briefs: name, signature or props, behavior, file. Freeze it before either unit starts.
- One symbol changed by two units is a conflict. Give it to one unit, or make the later unit depend on the earlier one.
- Name shared resources beyond files: dev server port, database, fixture, lockfile, build output, generated files. Units that share one run in order, or one unit owns it.
- Decide the data types and shapes first. Put scaffold (shared types, test setup, the check) before features, and subtraction (dead code) before scaffold.
- Before state is shared between units or actors, ask what happens if another one changes it at the same time. If the answer is not "nothing", isolate it.

## Specs that can be checked
- A spec states who is affected, what happens now, what must happen instead, and how "done" is checked.
- Acceptance items are pass or fail, checked by a command or by looking. Never write "works correctly" or "handles edge cases". Give a number for "fast".
- List what must not change, with paths. A unit that removes or replaces code gets a Keep list and a Remove list, and its report says which items still hold.

## Premises and spikes
- Label each premise observed (you read or ran it), reasoned, or unknown.
- An unknown that the plan depends on gets a spike first. A plan step that decides nothing is a gap.
- For a spike, a throwaway prototype, or a choice between candidate designs, read `references/spikes.md`.

## Run in verifiable units
- Verify each unit on the real artifact before the next starts. A break found at the unit that caused it is cheap; found after a batch it is buried.
- Mechanical changes: count the sites before and after with the same search and report both. Regenerate generated files from source, never by hand. For a rename of something persisted or public: add the new name, move callers in batches, then remove the old name.
- When the edit is repeated or checkable by script, build the lever (codemod, generator, rerunnable check) instead of hand edits or fan-out. Run it on the first unit, diff against the hand-done version, and keep it outside the builders' write scope.
- For a planned rewrite, declare where breakage between phases is allowed. Keep checks on the touched areas and run the full check at the end. Never keep throwaway compatibility code just to make every step green.
- For a long, unattended or multi-phase run, or work a person reviews later, or a hypothesis loop, read `references/run-log.md`.

## Hand off
- When the context nears its limit, or the work stops for the night, write a handoff. Read `references/handoff.md`.

Sources: mattpocock/skills@59db609 (wayfinder, triage, handoff, claude-handoff, prototype), pstack@47c6f80 (figure-it-out, show-me-your-work, foundational-thinking, outcome-oriented-execution, build-the-lever, arena, sequence-verifiable-units), orchestra v2.15.3 (wayfinder, triage, handoff, feasibility).
