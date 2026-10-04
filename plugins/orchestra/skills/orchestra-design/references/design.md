Source: derived from obra/superpowers@8ca22dba9a94 skills/brainstorming/SKILL.md, skills/brainstorming/spec-document-reviewer-prompt.md, skills/writing-plans/SKILL.md (MIT); mattpocock/skills@d81f3a183412 skills/engineering/to-spec/SKILL.md, skills/engineering/improve-codebase-architecture/SKILL.md, skills/engineering/codebase-design/SKILL.md, skills/engineering/codebase-design/DEEPENING.md, skills/engineering/codebase-design/DESIGN-IT-TWICE.md, skills/engineering/domain-modeling/SKILL.md, skills/engineering/domain-modeling/ADR-FORMAT.md (MIT); garrytan/gstack@4015c2870b06 spec/SKILL.md, deslop-shared-libs/SKILL.md, review/specialists/maintainability.md (MIT); github/spec-kit@ae5ade7234be templates/commands/clarify.md, templates/commands/checklist.md, templates/commands/analyze.md (MIT); see THIRD-PARTY-NOTICES.
Sentinel: orchestra-design/references/design.md

# Designer-planner: design mode

Output: one spec. No tickets, no code.

## Ground the spec

1. Read the product dossier when the brief names one, the settled decisions, the glossary and any decision records for the area. Define terms first (see the core rules).
2. Verify the current state before you propose a change. Read the code and cite what you found by path. Record what works today and must not change as a do-not-touch list.
3. Answer five questions from evidence or from the user: who is affected, what happens now, what must happen instead, why now, and how anyone will know it is done. A vague answer to the last one is an open decision.
4. If the request spans independent subsystems, say so first and design the first one. Each part gets its own spec.

## Close the frontier

Before you declare the frontier empty, score each area Clear, Partial or Missing: scope and exclusions, domain and data, user flow, non-functional limits, integrations and their failures, edge cases, constraints and rejected alternatives, terminology, completion signals. Every Partial or Missing area that would change behavior or acceptance becomes a question in the next round. Skip a question about method, stack or task breakdown, which belong to planning. Replace a vague adjective ("fast", "robust") with a measure, or ask for one.

## Choose

Compare two or three feasible approaches with their trade-offs. Lead with your recommendation and drop every feature nobody asked for. Write a decision record only when a choice is hard to reverse, surprising without context and a real trade-off. Skip it when any of the three is missing.

For a change to structure or interfaces, use this method:
- Prefer deep modules: a small interface in front of much behavior. Name the seam where the interface lives and what sits behind it.
- Apply the deletion test. If deleting a module only moves its complexity to the callers, it earns its place. If the complexity vanishes, it was a pass-through.
- The interface is the test surface. Tests and callers cross the same seam. One adapter is a hypothetical seam; add a seam only where two real variants exist.
- Design the interface twice. Sketch two contrasting shapes, for example one minimal and one tuned for the most common caller, then compare them on leverage, locality and seam placement. Recommend one, or a hybrid.
- Extract shared code only with two verified callers. Reuse an existing helper first. Count the net lines saved, tests included. Reject a speculative abstraction.
- Give each unit one purpose. Keep files that change together together, and split by responsibility. In existing code, follow the local patterns and improve only what the work touches. Propose no unrelated refactor.

## Write the spec

Synthesize from what is settled. Do not re-interview, and do not restate the dossier. Include:
- Scope and explicit exclusions, including the do-not-touch list.
- Settled decisions, verbatim.
- Observable journeys, each with its failure directions: what the user sees when it goes wrong.
- Glossary of the terms the work uses.
- Constraints and dependencies. Cite the binding project sections for engine, permission, data and persisted identifiers.
- Test seams. Prefer an existing seam, and the highest one that works. List a seam no one has agreed to as an open decision.
- Acceptance criteria: numbered, pass or fail, each checkable by a command or an observation. Never write "works correctly" or "handles edge cases".

Cite what you found by path in the spec. The summary prose you return to the user stays free of file paths and code, which go stale. Quote a schema or type only where prose cannot fix the decision.

For visual work, name the host surfaces, themes, responsive states and motion rules. Acceptance requires inspected screenshots or live observation through the user's path. Tests do not prove appearance.

## Self-check, then return

Run these checks on the finished spec and fix every hit in place:
- Placeholders: TODO, TBD, "etc.", a section with nothing in it.
- Contradictions between sections, and the same concept under two names.
- Requirements that two readers would build differently, or that duplicate each other.
- Scope too wide for one plan.
- Features nobody asked for.
- Requirements that cannot be tested, or that name an implementation instead of a behavior.

Return the open decisions as a round, the evidence behind each fact, every deviation from the dossier and whether the spec is ready for independent challenge.
