Source: derived from obra/superpowers@8ca22dba9a94 skills/subagent-driven-development/SKILL.md skills/systematic-debugging/SKILL.md (MIT); garrytan/gstack@4015c2870b06 investigate/SKILL.md SKILL.md (MIT); bmad-code-org/BMAD-METHOD@3cae711ea527 skills/bmad-correct-course/checklist.md (MIT); see THIRD-PARTY-NOTICES.
Sentinel: orchestra/references/repair-rounds.md

# Repair rounds

A round is one repair plus one scoped independent re-review of it. Count rounds per ticket, starting at the first independently checked BLOCKED review. Record each round in `<state>/progress.md`, one line per round. The engine does not enforce the cap; you do.

| Round | Action |
| --- | --- |
| 1 to 3 | Builder in repair mode at the default model. Resume the same agent when the host allows; otherwise dispatch afresh with the brief and the report file. |
| 4 | Dispatch override: model `claude-opus-5-5` through the Agent tool. On Codex use the `orchestra_builder_repair` profile at Sol high. |
| Round 5 | Breaker. No further repair. Send the ticket to a critic for judgment, then to design or planning. Tell the user. |

Each repair brief carries the exact artifact, the failing scenario and the scope of the defect. Recheck every finding against source first. A finding that contradicts the spec stops the dependent change and goes to design.

## Why the breaker routes back

Repeated failed fixes mean the design is wrong, not the patch. After the third failed attempt state what was tried and escalate. At the breaker, list the change impact before routing: which cards, files, interfaces and accepted work the new direction touches. The critic judges the stuck ticket; you do not rule on your own run.
