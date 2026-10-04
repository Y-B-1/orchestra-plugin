Source: derived from mattpocock/skills@d81f3a183412 skills/engineering/to-tickets/SKILL.md (MIT); see THIRD-PARTY-NOTICES.

Sentinel: orchestra-build/references/mechanical.md

# Builder: mechanical mode

Use this mode for one transform applied across many places: a rename, a retype, a format change, a bulk move or a dependency bump. The brief states the exact transform and the command that verifies it.

## Procedure

1. Confirm the transform is the whole job. Anything beyond it is out of scope; report it.
2. Find every site first and count them. Use the search command from the brief or write one; record it and its count.
3. Check generated-source authority. Never edit a generated file by hand: change its source and regenerate with the project's command. Find the source before you touch the output.
4. Apply the transform in the smallest batches the blast radius allows, such as one package or directory per batch. Run the verification command after each batch.
5. For a change that breaks callers the moment it lands, work in three steps: add the new form beside the old, move callers over in batches, then delete the old form once no caller remains. Each step leaves the build green.
6. Search again at the end. The old form has zero hits, or each remaining hit is named with the reason it stays.

## Equivalence

A mechanical change keeps behavior. Show it: the existing tests pass unchanged and the build or type check passes. When no test covers a site, name it as uncovered. Do not add behavior, fix neighboring code or reformat what the transform did not touch.

Add a test only when the transform needs a guard, for example a test that fails while the old form still exists.

## Report

Give the transform, the site count before and after, the verification command with its exit code, and the sites left alone with reasons.
