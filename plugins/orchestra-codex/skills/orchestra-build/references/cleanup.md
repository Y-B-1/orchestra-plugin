Source: derived from obra/superpowers@8ca22dba9a94 skills/receiving-code-review/SKILL.md (MIT); mattpocock/skills@d81f3a183412 skills/engineering/improve-codebase-architecture/SKILL.md (MIT); garrytan/gstack@4015c2870b06 deslop-shared-libs/SKILL.md review/specialists/simplification.md review/specialists/maintainability.md (MIT); ideas: Claude Code simplify (idea level); see THIRD-PARTY-NOTICES.

Sentinel: orchestra-build/references/cleanup.md

# Builder: cleanup mode

Use this mode for the end-of-run lean-and-simplify pass. The brief lists confirmed findings from the architecture, security and cleanliness review lenses and the paths they cite. Edit those paths only. This is not repo hygiene or release work.

## Goal

Leave the same behavior in less code. Review the changed code for reuse, quality and efficiency, then fix what the findings name.

## Tags

Each change carries one tag. The review lens uses the same tags, so a finding and its fix share words.

| Tag | Meaning | Replacement |
| --- | --- | --- |
| delete | Dead code, unused flexibility, speculative feature | Nothing |
| stdlib | Hand-rolled code the standard library ships | The named function |
| native | A dependency or code doing what the platform already does | The named platform feature |
| speculative | An abstraction with one implementation, config nobody sets, a layer with one caller | Inline it |
| shrink | A smaller equivalent that saves five lines or more | The shorter form |

## Procedure

1. Read each cited finding and the code around it. Start from the recent work the findings point at.
2. Prove what is unused before you remove it. Search the repository for callers of the symbol; remove it only when nothing calls it. A caller found only in tests means the test keeps dead code alive: say so, and do not delete either without a finding that names it.
3. Apply the deletion test. If deleting a module only moves its complexity to the callers, it earns its place. If the complexity vanishes, it was a pass-through. Remove only a pass-through.
4. For repeated code, extract a shared helper only when two or more real callers exist today and the helper stays small and option-free. Name the destination and the callers you moved. At most five candidates, best three first; none is a valid answer.
5. Apply one tag per commit-sized change. Run the existing tests after each change. The tests pass unchanged; a cleanup that needs a test edit has changed behavior, so stop and report it.
6. Keep the pass inside the cited paths. Mention an unrelated candidate in the report; do not touch it.

## Never

- Delete a test, a validation, an error path, an edge-case branch, a security check or an accessibility feature. Coverage and safety are not leanness targets.
- Change behavior, interfaces other code uses, or output other code reads.
- Rename or restructure for taste.

## Report

List each finding ID with its tag and the lines removed, the search command and hit count behind each deletion, the net line change, and the exact check command with its exit code. A finding you did not act on gets a one-line reason.
