Source: derived from obra/superpowers@8ca22dba9a94 skills/requesting-code-review/code-reviewer.md (MIT); mattpocock/skills@d81f3a183412 skills/engineering/code-review/SKILL.md (MIT); garrytan/gstack@4015c2870b06 review/sections/plan-completion.md (MIT); github/spec-kit@ae5ade7234be templates/commands/analyze.md (MIT); see THIRD-PARTY-NOTICES.
Sentinel: orchestra-critique/references/spec.md

# Critic: spec mode

Audit the implementation against the spec or plan. This axis asks only whether the code does what was asked; the standards axis is a separate run.

## Items

1. Find the spec source: the card brief, the named spec or plan file, or the issue the commits cite. If none exists, report that and stop; never invent one.
2. Extract every actionable item: requirements, numbered steps, named files, test requirements, data changes. Skip context sections, open questions and explicitly deferred work. Give each item a stable key, from the spec's own identifier where it has one.
3. Map each item to an implementation seam (path and symbol) and to observable acceptance evidence: a test, a command with its exit code, a log or a screenshot.
4. Classify it with the core classes. Name how it can be verified: DIFF (a change in this repository shows it), CROSS-REPO (a file in a sibling repository) or EXTERNAL-STATE (a system outside the repository). The diff cannot prove the last two. For a concrete path that is reachable, check it exists and classify DONE or NOT DONE; UNVERIFIABLE is valid only when the target is abstract or unreachable.

Commands and assertions in the spec that exercise behavior stay pending until someone runs them; a diff never makes them DONE.

## Judging

- Quote each missing or partial requirement from the spec.
- Separate unimplemented scope from a disputed requirement. The first is a build gap. The second needs a design ruling: report it, never settle it.
- Look for requirements that appear implemented but where the code does the wrong thing, and for spec items with zero implementation.
- The spec is a vision document. Where it is silent, a reasonable user's expectation counts as a requirement, and silence is not permission. Grade such a finding by its effect on that user.
- Count a changed approach as CHANGED, not NOT DONE, when it reaches the same goal.

## Report

List each item in order with its class, seam, evidence and verification mode. Add a coverage summary: items per class, and requirements with no seam. Rank NOT DONE and PARTIAL items by user impact.
