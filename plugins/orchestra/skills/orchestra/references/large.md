# Large or uncertain work

Load when an ask is bigger than one builder can finish in about 20 minutes, has open questions nobody can answer yet, changes an interface many units depend on, or the whole prompt holds more than about 15 asks.

## Map before you cut
- Write the destination in one sentence and list what is still unknown. Unknowns become short read-only research units that run in parallel with the known work; do not cut unknown work into build units early.
- Ship the thinnest end-to-end slice first, then widen it. Do refactors the new code builds on (a shared helper, a split file) as their own first unit.

## Contracts between units
- When unit B uses something unit A creates (a component, a hook, a type, an API), write the contract in both briefs: name, signature or props, behavior, file. Check each pair before dispatch.
- Name shared resources beyond files: a dev server port, a database, a fixture, a lockfile, the build output folder, generated files. Units that share one run one after another or one unit owns it.
- One symbol changed by two units is a conflict: give it to one unit, or make the later unit depend on the earlier.

## Specs that can be checked
A planned ask's spec states who is affected, what happens now, what must happen instead, and how "done" is checked. Acceptance items are pass/fail and checkable by a command or by looking: never "works correctly", "handles edge cases" or "fast" without a number. List what must not change, with paths.

## Premises
Label each premise of a plan observed (you read or ran it), reasoned, or unknown. An unknown that the plan depends on gets a short spike first. A plan step that decides nothing is a gap.

## Mechanical changes across many files
Count the sites before and after with the same search, and report both numbers. Regenerate generated files from their source; never hand-edit them. For a rename of something persisted or public: add the new, move callers in batches, then remove the old.
