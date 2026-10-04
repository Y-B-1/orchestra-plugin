Source: derived from obra/superpowers@8ca22dba9a94 skills/brainstorming/SKILL.md skills/writing-plans/SKILL.md (MIT); mattpocock/skills@d81f3a183412 skills/engineering/improve-codebase-architecture/SKILL.md skills/engineering/codebase-design/SKILL.md skills/engineering/codebase-design/DEEPENING.md skills/engineering/codebase-design/DESIGN-IT-TWICE.md (MIT); garrytan/gstack@4015c2870b06 deslop-shared-libs/SKILL.md review/specialists/maintainability.md (MIT); see THIRD-PARTY-NOTICES.
Sentinel: orchestra-review/references/architecture.md

# Code reviewer: architecture lens

Report findings only. Changes belong to the cleanup card, not to you.

## Placement

Follow callers and ownership. Decide whether new logic sits in the right layer: presentation, domain, persistence or transport. Cite the existing boundary the change crosses and the consequence.

## Module shape

- Each unit has one purpose and a clear interface. A reader understands it without opening its internals.
- Files that change together live together. Split by responsibility, not by file size.
- Apply the deletion test. If deleting a module only moves its complexity to the callers, it earns its place. If the complexity vanishes, it was a pass-through.
- The interface is the test surface. Tests that need the internals to change when the implementation changes test past the interface.
- A seam with one adapter is indirection. A seam needs two adapters, usually production and test.
- A new dependency on a remote or third-party service enters through a port that tests can replace.

## Existing code

Follow the patterns already there. Accept only the improvements the change needs. Flag unrelated refactoring as scope drift.

## Alternatives

When a design choice is costly to reverse, check that the author compared at least two feasible options. A decision record is due only for such choices. Do not demand one for a reversible choice.

## Shared code

Extract only with two verified callers. Check whether an existing helper already does the job. Count net lines saved. Reject an abstraction that serves a single use.
