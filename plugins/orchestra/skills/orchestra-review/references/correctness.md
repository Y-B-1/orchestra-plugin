Source: derived from obra/superpowers@8ca22dba9a94 skills/requesting-code-review/code-reviewer.md (MIT); mattpocock/skills@d81f3a183412 skills/engineering/code-review/SKILL.md (MIT); garrytan/gstack@4015c2870b06 review/SKILL.md review/checklist.md review/sections/adversarial.md (MIT); bmad-code-org/BMAD-METHOD@3cae711ea527 skills/bmad-review/references/lens-edge-case-hunter.md skills/bmad-review/references/lens-verification-gap.md skills/bmad-review/references/lens-adversarial.md skills/bmad-build/references/claims-check.md (MIT); github/spec-kit@ae5ade7234be .github/skills/code-review/SKILL.md (MIT); see THIRD-PARTY-NOTICES.
Sentinel: orchestra-review/references/correctness.md

# Code reviewer: correctness lens

Cover the sections below.

## Requirements

Map each changed behavior to the approved ask, journeys and constraints. Flag omissions and unrequested additions. Cite the spec line for each.

## Correctness

Walk each path with the author's narrative closed. Take the stance of someone who wants it to break.

### Critical pass

- Data safety: writes that can lose, duplicate or corrupt data. Partial failure between two writes.
- Races: check-then-act, shared state, retries that repeat a side effect.
- Trust boundary: model or external output used as code, a path, a query or a command without validation.
- Shell and query injection through interpolated input.
- Enums and branches: for every new value, read each switch and lookup that consumes it, including those outside the diff. Find the implicit branch that falls through.
- Handles: files, locks, connections and timers opened on one path and never released on another.
- Boundaries: empty, null, zero, maximum and malformed input. Error paths that swallow the failure.
- Integration contracts: caller and callee agree on shape, units and ordering.

Test a concrete counterexample when it is safe to run.

## Tests

- The change has tests for what it must do and for what it must prevent. Invalid input is covered.
- Evidence still matches the artifact. A check run before the last edit is stale.
- A report claim such as "all callers updated" is checked by search.

## Standards

Check the repository's own rules, naming and scope against the diff. Report violations you can quote. Leave deep conformance questions to the separate critic, but do not skip an obvious violation.
