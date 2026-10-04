Source: derived from obra/superpowers@8ca22dba9a94 skills/receiving-code-review/SKILL.md (MIT); mattpocock/skills@d81f3a183412 skills/engineering/improve-codebase-architecture/SKILL.md (MIT); garrytan/gstack@4015c2870b06 deslop-shared-libs/SKILL.md review/specialists/simplification.md review/specialists/maintainability.md (MIT); ideas: Claude Code simplify (idea level); see THIRD-PARTY-NOTICES.
Sentinel: orchestra-review/references/cleanliness.md

# Code reviewer: cleanliness lens

Judge the changed code for reuse, simplicity and efficiency. Report findings only. Cleanup work belongs to the cleanup card.

## Scope

Start from the recent work in the diff. At most five candidates, best three first; none is a valid answer. Do not demand broad refactors outside the diff.

## Tags

Tag each finding with one of: delete, stdlib, native, speculative, shrink.

- delete: code that nothing calls. Search for real usage before you claim it.
- stdlib: hand-written code that the standard library already provides.
- native: a dependency or helper that duplicates a platform feature.
- speculative: an abstraction, option or hook with one use or none.
- shrink: a smaller equivalent that saves five lines or more. Sketch it.

Report a delete finding for a module only when it is a pass-through under the deletion test in `architecture.md`.

## Reuse

Search for an existing equivalent symbol before you call code duplicate. Name the reusable seam and any compatibility limit.

## Efficiency

Trace repeated or hot work, unbounded loops, missing timeouts and needless I/O. Estimate the practical cost. Skip cost that does not matter at the real input size.

## Safety line

Never recommend deleting tests or validation.
